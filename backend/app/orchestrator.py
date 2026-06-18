from __future__ import annotations

import shutil
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, cast

from app.adapter import PLATFORM_LABELS
from app.agent import SkillAgentRuntime
from app.models import (
    AppSettings,
    AgentCallMetadata,
    GenerationAttempt,
    GenerationResult,
    GenerationStageAttempt,
    ModelProviderConfig,
    QualityEvaluationReport,
    QualityIssue,
    SkillBrief,
    SkillIR,
    SkillSpec,
    SkillSpecRevision,
    SupplementSpecItem,
    UserQuestion,
    UserSupplement,
    ValidationItem,
)
from app.normalizer import normalize_draft
from app.packager import (
    build_download_info,
    create_zip,
    write_manifest,
    write_quality_report,
    write_validation_report,
)
from app.prompts import (
    KNOWLEDGE_PROMPT_VERSION,
    QUALITY_PROMPT_VERSION,
    WORKFLOW_PROMPT_VERSION,
)
from app.quality import QualityPolicy, aggregate_quality_report, select_best_attempt
from app.renderer import build_file_tree, render_skill_md_text, render_skill_package
from app.settings import Settings
from app.spec_builder import build_skill_spec, enforce_spec_contract
from app.staged_generation import (
    KnowledgeGenerationResult,
    QualityGenerationResult,
    WorkflowGenerationResult,
    assemble_partial_skill_ir,
    assemble_skill_ir,
    validate_knowledge_result,
    validate_quality_result,
    validate_workflow_result,
)
from app.state_machine import assert_generation_transition
from app.storage import Storage
from app.utils import (
    hash_directory,
    make_id,
    now_ms,
    redact_secrets,
    sha256_file,
    sha256_json,
)
from app.validator import blocking_count, evaluate_validation, warning_count


class CandidateRenderError(RuntimeError):
    """Raised when rendering a candidate package fails.

    Must propagate as an exception: callers of _evaluate_candidate unpack a
    tuple, so returning a failed GenerationResult from inside it would crash
    the caller and overwrite the failure code.
    """

    failure_code = "RENDER_FAILED"


class StageGenerationError(RuntimeError):
    def __init__(self, stage: str, errors: list[str]) -> None:
        super().__init__("；".join(errors))
        self.stage = stage
        self.errors = errors


class UserCancelledError(RuntimeError):
    pass


STAGED_GENERATION_PROMPT_VERSION = (
    f"{WORKFLOW_PROMPT_VERSION}+{KNOWLEDGE_PROMPT_VERSION}+"
    f"{QUALITY_PROMPT_VERSION}"
)

_INITIAL_CANDIDATE_PROGRESS = {
    "render": 62,
    "validation": 66,
    "activation": 70,
    "implementation": 73,
    "aggregate": 76,
}
_REPAIR_CANDIDATE_OFFSETS = {
    "render": 1,
    "validation": 2,
    "activation": 3,
    "implementation": 4,
    "aggregate": 5,
}


def _repair_progress(round_number: int) -> int:
    return min(78 + max(0, round_number - 1) * 4, 87)


def _candidate_progress(round_number: int, phase: str) -> int:
    if round_number <= 0:
        return _INITIAL_CANDIDATE_PROGRESS[phase]
    return min(
        _repair_progress(round_number) + _REPAIR_CANDIDATE_OFFSETS[phase],
        87,
    )


class QualityOrchestrator:
    def __init__(
        self,
        *,
        settings: Settings,
        storage: Storage,
        agents: SkillAgentRuntime,
        policy: QualityPolicy | None = None,
    ) -> None:
        self.settings = settings
        self.storage = storage
        self.agents = agents
        self.policy = policy or QualityPolicy()

    def run(self, run_id: str) -> GenerationResult:
        generation = self._require_generation(run_id)
        draft = self.storage.get_draft(generation.draftId)
        if draft is None:
            return self._fail(generation, "DRAFT_NOT_FOUND", "草稿不存在。")

        self._transition(generation, "normalizing", "normalizing", 5)
        brief, brief_validation = normalize_draft(draft)
        brief = _redact_brief(brief)
        if generation.targetPlatformsOverride:
            brief.targetPlatforms = list(generation.targetPlatformsOverride)
        generation.normalizedBrief = brief.model_dump(mode="json")
        generation.promptBundleVersion = STAGED_GENERATION_PROMPT_VERSION
        generation.qualityPolicyVersion = self.policy.version
        spec = build_skill_spec(brief, revision=1)
        self._append_skill_spec(
            generation,
            spec,
            created_at=generation.startedAt,
        )
        self.storage.save_generation(generation)
        if blocking_count(brief_validation):
            generation.validation = brief_validation
            generation.blockingIssues = blocking_count(brief_validation)
            generation.warnings = warning_count(brief_validation)
            return self._fail(
                generation,
                "BRIEF_VALIDATION_FAILED",
                "生成输入存在阻塞问题，请补充草稿后重试。",
            )

        if self._cancel_requested(generation.id):
            return self._interrupt(generation)

        generation_provider = self._provider_for("generation")
        if generation_provider is None:
            generation.validation = [
                ValidationItem(
                    id="provider-generation-missing",
                    ruleId="PROVIDER-001",
                    level="blocking",
                    title="缺少 generation Model Provider",
                    description="生成前必须配置并启用 generation Provider。",
                    importance="质量闭环不能在没有真实模型的情况下生成静态替代作品。",
                    suggestion="在设置页配置并测试模型连接。",
                    blocksDownload=True,
                    field="modelProvider",
                    inputLayer="required",
                )
            ]
            generation.blockingIssues = 1
            return self._fail(
                generation,
                "PROVIDER_MISSING",
                "缺少启用的 generation Model Provider。",
            )

        try:
            ir, generation_calls = self._generate_staged_ir(
                generation,
                brief,
                spec,
            )
        except UserCancelledError:
            return self._interrupt(generation)
        except StageGenerationError as exc:
            return self._fail(
                generation,
                f"{exc.stage.upper()}_STAGE_FAILED",
                f"{exc.stage} 阶段生成失败：{exc}",
            )
        except Exception as exc:
            return self._fail(
                generation,
                "GENERATION_MODEL_FAILED",
                f"分阶段生成 SkillIR 失败：{exc}",
            )
        return self._process_candidates(
            generation=generation,
            brief=brief,
            spec=spec,
            original_ir=ir,
            current_ir=ir,
            start_round=0,
            parent_attempt_id=None,
            changed_paths=[],
            pending_agent_calls=generation_calls,
            input_issue_ids=[],
        )

    def fail_unhandled(
        self,
        generation: GenerationResult,
        code: str,
        message: str,
    ) -> GenerationResult:
        return self._fail(generation, code, message)

    def resume_with_supplement(
        self,
        run_id: str,
        *,
        answers: list[dict[str, Any]],
        skip: bool,
    ) -> GenerationResult:
        generation = self._require_generation(run_id)
        if generation.status != "awaiting_user_input":
            raise ValueError("Generation is not awaiting user input")
        draft = self.storage.get_draft(generation.draftId)
        if draft is None:
            return self._fail(generation, "DRAFT_NOT_FOUND", "草稿不存在。")

        answer_by_issue = {
            str(item["issueId"]): item.get("answer")
            for item in answers
            if item.get("issueId")
        }
        additions: list[str] = []
        new_supplement_items: list[SupplementSpecItem] = []
        for question in generation.userQuestions:
            answer = answer_by_issue.get(question.issueId)
            skipped = skip or answer is None
            normalized_answer = answer if isinstance(answer, (str, list)) else None
            self.storage.save_supplement(
                UserSupplement(
                    id=make_id("supplement"),
                    runId=run_id,
                    issueId=question.issueId,
                    question=question.question,
                    answer=normalized_answer,
                    skipped=skipped,
                    mergedPaths=[] if skipped else ["supplement.content"],
                    createdAt=now_ms(),
                )
            )
            if not skipped:
                if isinstance(normalized_answer, list):
                    answer_text = "、".join(normalized_answer)
                else:
                    answer_text = normalized_answer or ""
                addition = f"[{question.question}] {answer_text}"
                additions.append(addition)
                new_supplement_items.append(
                    SupplementSpecItem(
                        id=f"supplement.{question.issueId}",
                        question=question.question,
                        statement=addition,
                    )
                )

        if additions:
            current = draft.supplement.content.strip()
            draft.supplement.content = "\n".join(
                item for item in [current, *additions] if item
            )
            draft.updatedAt = now_ms()
            self.storage.save_draft(draft)
        self.storage.add_run_event(
            run_id,
            "supplement_received",
            {
                "issueIds": [question.issueId for question in generation.userQuestions],
                "skipped": skip,
            },
            now_ms(),
        )

        brief, _ = normalize_draft(draft)
        brief = _redact_brief(brief)
        if generation.targetPlatformsOverride:
            brief.targetPlatforms = list(generation.targetPlatformsOverride)
        previous_spec = self._current_spec(generation)
        if new_supplement_items or previous_spec is None:
            # Only genuine user input creates a new immutable spec revision;
            # a skipped supplement keeps the current contract unchanged.
            carried = {
                item.id: item
                for item in (previous_spec.userSupplements if previous_spec else [])
            }
            for item in new_supplement_items:
                carried[item.id] = item
            spec = build_skill_spec(
                brief,
                revision=(generation.skillSpecRevision or 0) + 1,
                source_issue_ids=[
                    item.id.removeprefix("supplement.")
                    for item in new_supplement_items
                ],
                supplements=list(carried.values()),
            )
            self._append_skill_spec(generation, spec, created_at=now_ms())
        else:
            spec = previous_spec
        attempts = self.storage.list_attempts(run_id)
        reports = {item.attemptId: item for item in self.storage.list_quality_reports(run_id)}
        if not attempts:
            return self._fail(generation, "NO_ATTEMPT", "没有可继续修复的候选。")
        original_ir = SkillIR.model_validate(attempts[0].skillIR)
        try:
            best_attempt = select_best_attempt(attempts, reports)
        except ValueError:
            best_attempt = attempts[-1]
        current_ir = SkillIR.model_validate(best_attempt.skillIR)
        next_round = max(item.round for item in attempts) + 1
        if next_round > generation.maxRepairRounds:
            return self._finalize_best(generation, attempts, reports)

        report = reports.get(best_attempt.id)
        issues = report.issues if report else []
        repair_provider = self._provider_for("repair") or self._provider_for("generation")
        if repair_provider is None:
            return self._fail(generation, "REPAIR_PROVIDER_MISSING", "缺少修复模型 Provider。")
        self._transition(
            generation,
            f"repairing_round_{next_round}",
            "repairing",
            _repair_progress(next_round),
            current_round=next_round,
            provider=repair_provider,
        )
        rendered_skill_md, rendered_files = _rendered_artifacts(best_attempt)
        try:
            (repaired, metadata), repair_provider = self._call_with_provider_fallback(
                generation,
                "repair",
                lambda provider: self.agents.repair(
                    brief=brief,
                    spec=spec,
                    original_ir=original_ir,
                    current_ir=current_ir,
                    best_ir=current_ir,
                    issues=issues,
                    allowed_paths=_allowed_paths(issues),
                    locked_paths=_locked_paths(),
                    round_number=next_round,
                    provider=provider,
                    rendered_skill_md=rendered_skill_md,
                    rendered_files=rendered_files,
                ),
            )
        except Exception as exc:
            return self._finalize_after_provider_failure(
                generation,
                code="REPAIR_MODEL_FAILED",
                message=f"模型修复失败：{exc}",
            )
        generation.userQuestions = []
        generation.awaitingUserInputIssueIds = []
        self.storage.save_generation(generation)
        return self._process_candidates(
            generation=generation,
            brief=brief,
            spec=spec,
            original_ir=original_ir,
            current_ir=repaired.skillIR,
            start_round=next_round,
            parent_attempt_id=best_attempt.id,
            changed_paths=repaired.changedPaths,
            pending_agent_calls=[metadata],
            input_issue_ids=[issue.issueId for issue in issues],
        )

    def _process_candidates(
        self,
        *,
        generation: GenerationResult,
        brief: SkillBrief,
        spec: SkillSpec,
        original_ir: SkillIR,
        current_ir: SkillIR,
        start_round: int,
        parent_attempt_id: str | None,
        changed_paths: list[str],
        pending_agent_calls: list[AgentCallMetadata],
        input_issue_ids: list[str],
    ) -> GenerationResult:
        round_number = start_round
        while True:
            if self._cancel_requested(generation.id):
                return self._interrupt(generation)
            try:
                attempt, report, validation_items = self._evaluate_candidate(
                    generation=generation,
                    brief=brief,
                    spec=spec,
                    ir=current_ir,
                    round_number=round_number,
                    parent_attempt_id=parent_attempt_id,
                    changed_paths=changed_paths,
                    pending_agent_calls=pending_agent_calls,
                    input_issue_ids=input_issue_ids,
                )
            except Exception as exc:
                attempts = self.storage.list_attempts(generation.id)
                reports = {
                    item.attemptId: item
                    for item in self.storage.list_quality_reports(generation.id)
                }
                if reports:
                    generation.errorMessage = f"本轮模型评测失败，已选择历史最佳候选：{exc}"
                    generation.finalSelectionReason = "provider_failure_with_previous_safe_candidate"
                    return self._finalize_best(generation, attempts, reports)
                return self._fail(
                    generation,
                    getattr(exc, "failure_code", "EVALUATION_MODEL_FAILED"),
                    f"候选评测失败：{exc}",
                )
            generation.validation = validation_items
            generation.blockingIssues = blocking_count(validation_items)
            generation.warnings = warning_count(validation_items)
            generation.qualityReport = report
            generation.currentRound = round_number
            self._refresh_best_attempt(generation)
            self.storage.save_generation(generation)
            if self._cancel_requested(generation.id):
                return self._interrupt(generation)

            if report.passedStrictGate:
                generation.finalSelectionReason = "strict_quality_gate_passed"
                return self._finalize(generation, attempt, report, degraded=False)

            questions = self._new_user_questions(generation, report)
            if questions and round_number < generation.maxRepairRounds:
                assert_generation_transition(generation.status, "awaiting_user_input")
                generation.status = "awaiting_user_input"
                generation.currentStage = "awaiting-user-input"
                generation.progress = 60
                generation.userQuestions = questions
                generation.awaitingUserInputIssueIds = [item.issueId for item in questions]
                generation.promptedIssueIds = list(
                    dict.fromkeys(
                        [*generation.promptedIssueIds, *generation.awaitingUserInputIssueIds]
                    )
                )
                self.storage.add_run_event(
                    generation.id,
                    "awaiting_user_input",
                    {"issueIds": generation.awaitingUserInputIssueIds},
                    now_ms(),
                )
                return self.storage.save_generation(generation)

            if (
                round_number >= generation.maxRepairRounds
                or self._should_stop_for_stagnation(generation.id)
            ):
                attempts = self.storage.list_attempts(generation.id)
                reports = {
                    item.attemptId: item
                    for item in self.storage.list_quality_reports(generation.id)
                }
                return self._finalize_best(generation, attempts, reports)

            next_round = round_number + 1
            repair_provider = self._provider_for("repair") or self._provider_for("generation")
            if repair_provider is None:
                return self._fail(
                    generation,
                    "REPAIR_PROVIDER_MISSING",
                    "缺少修复模型 Provider。",
                )
            best_attempt = self._best_attempt(generation.id)
            best_ir = (
                SkillIR.model_validate(best_attempt.skillIR)
                if best_attempt is not None
                else current_ir
            )
            rendered_skill_md, rendered_files = _rendered_artifacts(best_attempt or attempt)
            # Repair starts from the best attempt, so feed it that attempt's
            # issues; the latest report may criticize content the best IR
            # does not contain when a repair round regressed.
            repair_issues = report.issues
            if best_attempt is not None and best_attempt.id != attempt.id:
                best_report = next(
                    (
                        item
                        for item in self.storage.list_quality_reports(generation.id)
                        if item.attemptId == best_attempt.id
                    ),
                    None,
                )
                if best_report is not None:
                    repair_issues = best_report.issues
            self._transition(
                generation,
                f"repairing_round_{next_round}",
                "repairing",
                _repair_progress(next_round),
                current_round=next_round,
                provider=repair_provider,
            )
            try:
                (repaired, metadata), repair_provider = self._call_with_provider_fallback(
                    generation,
                    "repair",
                    lambda provider: self.agents.repair(
                        brief=brief,
                        spec=spec,
                        original_ir=original_ir,
                        current_ir=best_ir,
                        best_ir=best_ir,
                        issues=repair_issues,
                        allowed_paths=_allowed_paths(repair_issues),
                        locked_paths=_locked_paths(),
                        round_number=next_round,
                        provider=provider,
                        rendered_skill_md=rendered_skill_md,
                        rendered_files=rendered_files,
                    ),
                )
            except Exception as exc:
                return self._finalize_after_provider_failure(
                    generation,
                    code="REPAIR_MODEL_FAILED",
                    message=f"模型修复失败：{exc}",
                )
            if self._cancel_requested(generation.id):
                return self._interrupt(generation)
            parent_attempt_id = generation.bestAttemptId or attempt.id
            current_ir = repaired.skillIR
            changed_paths = repaired.changedPaths
            pending_agent_calls = [metadata]
            input_issue_ids = [issue.issueId for issue in repair_issues]
            round_number = next_round

    def _evaluate_candidate(
        self,
        *,
        generation: GenerationResult,
        brief: SkillBrief,
        spec: SkillSpec,
        ir: SkillIR,
        round_number: int,
        parent_attempt_id: str | None,
        changed_paths: list[str],
        pending_agent_calls: list[AgentCallMetadata],
        input_issue_ids: list[str],
    ) -> tuple[GenerationAttempt, QualityEvaluationReport, list[ValidationItem]]:
        candidate_started = time.perf_counter()
        ir = enforce_spec_contract(ir, spec)
        attempt_id = make_id("attempt")
        package_root = (
            self.settings.artifact_root
            / generation.id
            / "attempts"
            / attempt_id
            / "package"
        )
        # --- Render candidate package ---
        self._transition(
            generation,
            "rendering_candidate",
            "rendering-files",
            _candidate_progress(round_number, "render"),
            current_round=round_number,
        )
        try:
            render_skill_package(ir, package_root)
        except Exception as exc:
            raise CandidateRenderError(f"渲染 Skill 包失败：{exc}") from exc
        file_hashes = hash_directory(package_root)
        file_paths = sorted(file_hashes)
        (
            skill_ir_sha256,
            activation_signature,
            implementation_signature,
        ) = _evaluation_signatures(brief, spec, ir, file_paths)
        previous_attempts = self.storage.list_attempts(generation.id)
        previous_reports = {
            item.attemptId: item
            for item in self.storage.list_quality_reports(generation.id)
        }
        (
            activation,
            activation_reused_from,
            implementation,
            implementation_reused_from,
        ) = _reusable_evaluations(
            previous_attempts,
            previous_reports,
            activation_signature=activation_signature,
            implementation_signature=implementation_signature,
        )

        self._transition(
            generation,
            "running_validation_checks",
            "running-validation-checks",
            _candidate_progress(round_number, "validation"),
        )
        validation_items, validation_issues, validation_score = evaluate_validation(
            package_root,
            ir,
            brief,
            spec,
        )
        has_blocker = any(
            issue.severity in {"security_blocker", "structure_blocker"}
            for issue in validation_issues
        )
        attempt = GenerationAttempt(
            id=attempt_id,
            runId=generation.id,
            round=round_number,
            parentAttemptId=parent_attempt_id,
            skillIR=ir.model_dump(mode="json"),
            renderedPath=str(package_root),
            isStructurallyValid=not any(
                issue.severity == "structure_blocker" for issue in validation_issues
            ),
            isSecuritySafe=not any(
                issue.severity == "security_blocker" for issue in validation_issues
            ),
            changedPaths=changed_paths,
            providerId=generation.modelProviderId,
            modelName=(
                pending_agent_calls[-1].model
                if pending_agent_calls
                else None
            ),
            promptVersion=(
                pending_agent_calls[-1].promptVersion
                if pending_agent_calls
                else generation.promptBundleVersion
            ),
            inputIssueIds=input_issue_ids,
            agentCalls=list(pending_agent_calls),
            fileHashes=file_hashes,
            skillIRSha256=skill_ir_sha256,
            activationSignature=activation_signature,
            implementationSignature=implementation_signature,
            activationReusedFromAttemptId=activation_reused_from,
            implementationReusedFromAttemptId=implementation_reused_from,
            createdAt=now_ms(),
            skillSpecRevision=spec.revision,
            skillSpecSha256=generation.skillSpecSha256,
        )
        self.storage.save_attempt(attempt)

        if not has_blocker:
            needs_activation = activation is None
            needs_implementation = implementation is None
            activation_provider = self._provider_for("activation-evaluation")
            implementation_provider = self._provider_for("implementation-evaluation")
            if (
                needs_activation
                and activation_provider is None
                or needs_implementation
                and implementation_provider is None
            ):
                validation_issues.append(
                    QualityIssue(
                        issueId="judge-provider-missing",
                        source="validation",
                        criterion="PROVIDER-003",
                        severity="structure_blocker",
                        reason="缺少可用的 Judge Provider。",
                        suggestion="为评估角色配置 Provider。",
                    )
                )
            elif needs_activation and needs_implementation:
                self._transition(
                    generation,
                    "evaluating_activation",
                    "evaluating-activation",
                    _candidate_progress(round_number, "activation"),
                )
                with ThreadPoolExecutor(
                    max_workers=2,
                    thread_name_prefix=f"judges-{generation.id}",
                ) as executor:
                    activation_future = executor.submit(
                        self._call_with_provider_fallback,
                        generation,
                        "activation-evaluation",
                        lambda provider: self.agents.evaluate_activation(
                            brief,
                            spec,
                            ir,
                            provider,
                        ),
                        False,
                    )
                    implementation_future = executor.submit(
                        self._call_with_provider_fallback,
                        generation,
                        "implementation-evaluation",
                        lambda provider: self.agents.evaluate_implementation(
                            brief,
                            spec,
                            ir,
                            (package_root / ir.skill.name / "SKILL.md").read_text(
                                encoding="utf-8"
                            ),
                            file_paths,
                            provider,
                        ),
                        False,
                    )
                    (
                        (activation, activation_metadata),
                        activation_provider,
                    ) = activation_future.result()
                    (
                        (implementation, implementation_metadata),
                        implementation_provider,
                    ) = implementation_future.result()
                attempt.agentCalls.append(activation_metadata)
                self._record_provider_selection(generation, activation_provider)
                self._transition(
                    generation,
                    "evaluating_implementation",
                    "evaluating-implementation",
                    _candidate_progress(round_number, "implementation"),
                )
                attempt.agentCalls.append(implementation_metadata)
                self._record_provider_selection(generation, implementation_provider)
            elif needs_activation:
                self._transition(
                    generation,
                    "evaluating_activation",
                    "evaluating-activation",
                    _candidate_progress(round_number, "activation"),
                )
                (
                    (activation, activation_metadata),
                    activation_provider,
                ) = self._call_with_provider_fallback(
                    generation,
                    "activation-evaluation",
                    lambda provider: self.agents.evaluate_activation(
                        brief,
                        spec,
                        ir,
                        provider,
                    ),
                )
                attempt.agentCalls.append(activation_metadata)
                self._transition(
                    generation,
                    "evaluating_implementation",
                    "evaluating-implementation",
                    _candidate_progress(round_number, "implementation"),
                )
            elif needs_implementation:
                self._transition(
                    generation,
                    "evaluating_implementation",
                    "evaluating-implementation",
                    _candidate_progress(round_number, "implementation"),
                )
                (
                    (implementation, implementation_metadata),
                    implementation_provider,
                ) = self._call_with_provider_fallback(
                    generation,
                    "implementation-evaluation",
                    lambda provider: self.agents.evaluate_implementation(
                        brief,
                        spec,
                        ir,
                        (package_root / ir.skill.name / "SKILL.md").read_text(
                            encoding="utf-8"
                        ),
                        file_paths,
                        provider,
                    ),
                )
                attempt.agentCalls.append(implementation_metadata)

        self._transition(
            generation,
            "aggregating_scores",
            "aggregating-scores",
            _candidate_progress(round_number, "aggregate"),
        )
        report = aggregate_quality_report(
            attempt_id=attempt.id,
            validation_score=validation_score,
            validation_issues=validation_issues,
            activation=activation,
            implementation=implementation,
            policy=self.policy,
        )
        attempt.durationMs = max(0, round((time.perf_counter() - candidate_started) * 1000))
        self.storage.save_attempt(attempt)
        self.storage.save_quality_report(generation.id, report)
        self.storage.add_run_event(
            generation.id,
            "candidate_evaluated",
            {
                "attemptId": attempt.id,
                "round": attempt.round,
                "scores": {
                    "validation": report.validationScore,
                    "activation": report.activationScore,
                    "implementation": report.implementationScore,
                    "overall": report.overallScore,
                },
                "agentCalls": [
                    call.model_dump(mode="json")
                    for call in attempt.agentCalls
                ],
            },
            report.evaluatedAt,
        )
        return attempt, report, validation_items

    def _finalize_best(
        self,
        generation: GenerationResult,
        attempts: list[GenerationAttempt],
        reports: dict[str, QualityEvaluationReport],
    ) -> GenerationResult:
        self._transition(
            generation,
            "selecting_best_candidate",
            "selecting-best-candidate",
            88,
        )
        try:
            attempt = select_best_attempt(attempts, reports)
        except ValueError:
            return self._fail(
                generation,
                "NO_SAFE_CANDIDATE",
                "没有结构完整且安全的候选可供交付。",
            )
        report = reports[attempt.id]
        if not report.passedDegradedGate:
            return self._fail(
                generation,
                "QUALITY_BELOW_MINIMUM",
                "所有候选均低于最低可用质量线。",
            )
        if generation.finalSelectionReason is None:
            generation.finalSelectionReason = (
                "highest_scoring_safe_candidate_after_stagnation_or_round_limit"
            )
        return self._finalize(generation, attempt, report, degraded=True)

    def _finalize(
        self,
        generation: GenerationResult,
        attempt: GenerationAttempt,
        report: QualityEvaluationReport,
        *,
        degraded: bool,
    ) -> GenerationResult:
        status = "packaging_low_score" if degraded else "packaging_high_quality"
        self._transition(generation, status, "packaging", 94)
        ir = SkillIR.model_validate(attempt.skillIR)
        source_root = Path(attempt.renderedPath)
        final_root = self.settings.artifact_root / generation.id / "final" / "package"
        metadata_root = self.settings.artifact_root / generation.id / "final" / "metadata"
        if final_root.exists():
            # Safety: verify path is within artifact_root before removing
            if not final_root.resolve().is_relative_to(self.settings.artifact_root.resolve()):
                raise ValueError(f"Refusing to remove directory outside artifact root: {final_root}")
            shutil.rmtree(final_root)
        if metadata_root.exists():
            if not metadata_root.resolve().is_relative_to(self.settings.artifact_root.resolve()):
                raise ValueError(f"Refusing to remove directory outside artifact root: {metadata_root}")
            shutil.rmtree(metadata_root)
        final_root.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(source_root, final_root)
        # Validate against the spec revision this candidate was generated and
        # evaluated under; a newer revision created by a later supplement must
        # not retroactively fail an older, already-passing candidate.
        spec_entry = self._spec_entry_for_revision(
            generation, attempt.skillSpecRevision
        )
        attempt_spec = spec_entry.spec if spec_entry else None
        validation_items, _issues, _score = evaluate_validation(
            final_root,
            ir,
            self._brief(generation),
            attempt_spec,
        )
        if blocking_count(validation_items):
            return self._fail(
                generation,
                "FINAL_VALIDATION_FAILED",
                "最终包未通过 SkillSpec 或官方 Agent Skills 校验。",
            )
        write_validation_report(metadata_root, validation_items)
        write_quality_report(
            metadata_root,
            report,
            degraded=degraded,
            repair_rounds=generation.currentRound,
            selection_reason=generation.finalSelectionReason,
        )
        write_manifest(
            metadata_root,
            ir,
            validation_items,
            report,
            selection_reason=generation.finalSelectionReason,
            skill_spec=attempt_spec,
            skill_spec_sha256=spec_entry.sha256 if spec_entry else None,
            package_root=final_root,
        )
        score_label = round(report.overallScore or 0)
        zip_name = (
            f"{ir.skill.name}-low-score-{score_label}.zip"
            if degraded
            else f"{ir.skill.name}-package.zip"
        )
        zip_path = self.settings.artifact_root / generation.id / zip_name
        create_zip(final_root, zip_path)
        terminal_status = "degraded" if degraded else "succeeded"
        assert_generation_transition(generation.status, terminal_status)
        generation.status = terminal_status
        generation.currentStage = "packaging"
        generation.progress = 100
        generation.finalAttemptId = attempt.id
        generation.bestAttemptId = attempt.id
        generation.finalRound = attempt.round
        generation.qualityReport = report
        reports = self.storage.list_quality_reports(generation.id)
        supplements = self.storage.list_supplements(generation.id)
        if supplements and reports and reports[0].overallScore is not None and report.overallScore is not None:
            generation.supplementScoreDelta = round(
                report.overallScore - reports[0].overallScore,
                2,
            )
        generation.files = build_file_tree(final_root)
        generation.skillMd = (
            final_root / ir.skill.name / "SKILL.md"
        ).read_text(encoding="utf-8")
        generation.validation = validation_items
        generation.blockingIssues = blocking_count(validation_items)
        generation.warnings = warning_count(validation_items)
        generation.downloadInfo = build_download_info(
            zip_path=zip_path,
            package_name=zip_name,
            platforms=[PLATFORM_LABELS[target] for target in ir.platforms.targets],
            generated_at=datetime.now(timezone.utc).isoformat(),
        )
        generation.artifactDir = str(final_root.parent)
        generation.zipPath = str(zip_path)
        generation.artifactSha256 = sha256_file(zip_path)
        generation.completedAt = now_ms()
        generation.errorMessage = (
            "该作品未达到高质量门槛，已返回历史最高分的低分版本。"
            if degraded
            else None
        )
        self.storage.add_run_event(
            generation.id,
            "completed",
            {
                "status": generation.status,
                "attemptId": attempt.id,
                "overallScore": report.overallScore,
                "selectionReason": generation.finalSelectionReason,
                "artifactSha256": generation.artifactSha256,
            },
            generation.completedAt,
        )
        return self.storage.save_generation(generation)

    def _refresh_best_attempt(self, generation: GenerationResult) -> None:
        attempts = self.storage.list_attempts(generation.id)
        reports = {
            item.attemptId: item
            for item in self.storage.list_quality_reports(generation.id)
        }
        try:
            generation.bestAttemptId = select_best_attempt(attempts, reports).id
        except ValueError:
            pass

    def _finalize_after_provider_failure(
        self,
        generation: GenerationResult,
        *,
        code: str,
        message: str,
    ) -> GenerationResult:
        attempts = self.storage.list_attempts(generation.id)
        reports = {
            item.attemptId: item
            for item in self.storage.list_quality_reports(generation.id)
        }
        if not reports:
            return self._fail(generation, code, message)
        generation.errorMessage = message
        generation.finalSelectionReason = "provider_failure_with_previous_safe_candidate"
        self.storage.add_run_event(
            generation.id,
            "provider_failure_using_previous_candidate",
            {"code": code, "message": message},
            now_ms(),
        )
        return self._finalize_best(generation, attempts, reports)

    def _best_attempt(self, run_id: str) -> GenerationAttempt | None:
        attempts = self.storage.list_attempts(run_id)
        reports = {
            item.attemptId: item
            for item in self.storage.list_quality_reports(run_id)
        }
        try:
            return select_best_attempt(attempts, reports)
        except ValueError:
            return None

    def _should_stop_for_stagnation(self, run_id: str) -> bool:
        attempts = self.storage.list_attempts(run_id)
        reports = self.storage.list_quality_reports(run_id)
        if len(attempts) >= 3 and not attempts[-1].changedPaths and not attempts[-2].changedPaths:
            return True
        if len(reports) < 3:
            return False
        recent = reports[-3:]
        scores = [item.overallScore for item in recent]
        if any(score is None for score in scores):
            return False
        issue_sets = [
            {issue.issueId for issue in report.issues}
            for report in recent
        ]
        return (
            cast(float, scores[1]) - cast(float, scores[0]) < 1
            and cast(float, scores[2]) - cast(float, scores[1]) < 1
            and issue_sets[0] == issue_sets[1] == issue_sets[2]
        )

    def _new_user_questions(
        self,
        generation: GenerationResult,
        report: QualityEvaluationReport,
    ) -> list[UserQuestion]:
        questions: list[UserQuestion] = []
        seen = set(generation.promptedIssueIds)
        for issue in report.issues:
            if (
                not issue.requiresUserInput
                or not issue.userQuestion
                or issue.issueId in seen
            ):
                continue
            questions.append(
                UserQuestion(
                    issueId=issue.issueId,
                    question=issue.userQuestion,
                    inputControl=issue.inputControl or "long-text",
                    options=issue.options,
                )
            )
            seen.add(issue.issueId)
            if len(questions) == 5:
                break
        return questions

    def _provider_for(self, role: str) -> ModelProviderConfig | None:
        providers = self._providers_for(role)
        return providers[0] if providers else None

    def _providers_for(self, role: str) -> list[ModelProviderConfig]:
        app_settings = self._app_settings()
        preferred = {
            "generation": app_settings.defaultGenerateProvider,
            "repair": app_settings.defaultRepairProvider,
            "activation-evaluation": app_settings.defaultValidateProvider,
            "implementation-evaluation": app_settings.defaultValidateProvider,
            "validation-explanation": app_settings.defaultValidateProvider,
        }.get(role, "")
        if preferred:
            provider = self.storage.get_provider(preferred)
            if provider and provider.enabled and (
                role in provider.roles
                or (
                    role in {"activation-evaluation", "implementation-evaluation"}
                    and "validation-explanation" in provider.roles
                )
            ):
                preferred_provider = provider
            else:
                preferred_provider = None
        else:
            preferred_provider = None

        candidates = [
            provider
            for provider in self.storage.list_providers()
            if provider.enabled and role in provider.roles
        ]
        if role in {"activation-evaluation", "implementation-evaluation"}:
            candidates.extend(
                provider
                for provider in self.storage.list_providers()
                if provider.enabled and "validation-explanation" in provider.roles
            )
        if role == "repair" or (
            role in {"activation-evaluation", "implementation-evaluation"}
            and not candidates
        ):
            candidates.extend(
                provider
                for provider in self.storage.list_providers()
                if provider.enabled and "generation" in provider.roles
            )
        ordered = [preferred_provider, *candidates]
        deduplicated: list[ModelProviderConfig] = []
        seen: set[str] = set()
        for provider in ordered:
            if provider is None or provider.id in seen:
                continue
            seen.add(provider.id)
            deduplicated.append(provider)
        return deduplicated

    def _call_with_provider_fallback(
        self,
        generation: GenerationResult,
        role: str,
        call: Any,
        persist_selection: bool = True,
    ) -> tuple[Any, ModelProviderConfig]:
        errors: list[str] = []
        for index, provider in enumerate(self._providers_for(role)):
            try:
                result = call(provider)
                if index > 0:
                    self.storage.add_run_event(
                        generation.id,
                        "provider_fallback",
                        {
                            "role": role,
                            "providerId": provider.id,
                            "previousErrors": errors,
                        },
                        now_ms(),
                    )
                if persist_selection:
                    self._record_provider_selection(generation, provider)
                return result, provider
            except Exception as exc:
                errors.append(f"{provider.id}: {exc}")
        raise RuntimeError(
            f"All providers failed for role {role}: {'; '.join(errors) or 'none configured'}"
        )

    def _record_provider_selection(
        self,
        generation: GenerationResult,
        provider: ModelProviderConfig,
    ) -> None:
        generation.modelProviderId = provider.id
        generation.modelProtocol = provider.protocol
        self.storage.save_generation(generation)

    def _app_settings(self) -> AppSettings:
        raw = self.storage.get_setting("app_settings")
        if not raw:
            return AppSettings()
        try:
            return AppSettings.model_validate_json(raw)
        except Exception:
            return AppSettings()

    def _brief(self, generation: GenerationResult) -> SkillBrief:
        draft = self.storage.get_draft(generation.draftId)
        if draft is None:
            raise ValueError("Draft not found")
        brief, _ = normalize_draft(draft)
        brief = _redact_brief(brief)
        if generation.targetPlatformsOverride:
            brief.targetPlatforms = list(generation.targetPlatformsOverride)
        return brief

    def _require_generation(self, run_id: str) -> GenerationResult:
        generation = self.storage.get_generation(run_id)
        if generation is None:
            raise ValueError("Generation not found")
        return generation

    def _generate_staged_ir(
        self,
        generation: GenerationResult,
        brief: SkillBrief,
        spec: SkillSpec,
    ) -> tuple[SkillIR, list[AgentCallMetadata]]:
        calls: list[AgentCallMetadata] = []
        self._update_skill_md_preview(generation, brief, spec)

        workflow, metadata = self._run_generation_stage(
            generation,
            stage="workflow",
            current_stage="generating-workflow",
            progress=10,
            message="正在构建工作流骨架",
            call=lambda provider, feedback: self.agents.generate_workflow(
                brief, spec, provider, feedback
            ),
            validate=lambda result: validate_workflow_result(result, spec),
            on_result=lambda result: self._update_skill_md_preview(
                generation,
                brief,
                spec,
                workflow=result,
            ),
        )
        calls.append(metadata)
        self._update_skill_md_preview(generation, brief, spec, workflow=workflow)

        knowledge, metadata = self._run_generation_stage(
            generation,
            stage="knowledge",
            current_stage="generating-knowledge",
            progress=28,
            message="正在生成知识与文件",
            call=lambda provider, feedback: self.agents.generate_knowledge(
                brief, spec, workflow, provider, feedback
            ),
            validate=lambda result: validate_knowledge_result(result, spec),
            on_result=lambda result: self._update_skill_md_preview(
                generation,
                brief,
                spec,
                workflow=workflow,
                knowledge=result,
            ),
        )
        calls.append(metadata)
        self._update_skill_md_preview(
            generation,
            brief,
            spec,
            workflow=workflow,
            knowledge=knowledge,
        )

        quality, metadata = self._run_generation_stage(
            generation,
            stage="quality",
            current_stage="generating-quality",
            progress=46,
            message="正在生成规则与验收控制",
            call=lambda provider, feedback: self.agents.generate_quality(
                brief, spec, workflow, knowledge, provider, feedback
            ),
            validate=lambda result: validate_quality_result(result, spec),
            on_result=lambda result: self._update_skill_md_preview(
                generation,
                brief,
                spec,
                workflow=workflow,
                knowledge=knowledge,
                quality=result,
            ),
        )
        calls.append(metadata)
        self._update_skill_md_preview(
            generation,
            brief,
            spec,
            workflow=workflow,
            knowledge=knowledge,
            quality=quality,
        )

        return (
            assemble_skill_ir(
                brief,
                spec,
                workflow,
                knowledge,
                quality,
            ),
            calls,
        )

    def _run_generation_stage(
        self,
        generation: GenerationResult,
        *,
        stage: str,
        current_stage: str,
        progress: int,
        message: str,
        call: Any,
        validate: Any,
        on_result: Any | None = None,
    ) -> tuple[Any, AgentCallMetadata]:
        feedback: list[str] = []
        last_errors: list[str] = []
        for attempt_number in range(1, generation.stageMaxAttempts + 1):
            if self._cancel_requested(generation.id):
                raise UserCancelledError()
            generation.stageAttempt = attempt_number
            generation.stageMessage = message
            self._transition(
                generation,
                "generating_initial_ir",
                current_stage,
                progress,
            )
            started_at = now_ms()
            result: Any = None
            metadata: AgentCallMetadata | None = None
            provider: ModelProviderConfig | None = None
            try:
                (result, metadata), provider = self._call_with_provider_fallback(
                    generation,
                    "generation",
                    lambda selected: call(selected, feedback),
                )
                last_errors = list(validate(result))
                if on_result is not None and result is not None:
                    on_result(result)
            except Exception as exc:
                last_errors = [str(exc)]
            completed_at = now_ms()
            stage_attempt = GenerationStageAttempt(
                stage=stage,
                attempt=attempt_number,
                status="failed" if last_errors else "succeeded",
                errors=last_errors,
                result=(
                    result.model_dump(mode="json")
                    if result is not None
                    else {}
                ),
                providerId=provider.id if provider else (
                    metadata.providerId if metadata else None
                ),
                modelName=metadata.model if metadata else None,
                promptVersion=metadata.promptVersion if metadata else "",
                inputTokens=metadata.inputTokens if metadata else 0,
                outputTokens=metadata.outputTokens if metadata else 0,
                durationMs=(
                    metadata.durationMs
                    if metadata
                    else max(0, completed_at - started_at)
                ),
                startedAt=started_at,
                completedAt=completed_at,
            )
            generation.stageAttempts.append(stage_attempt)
            self.storage.add_run_event(
                generation.id,
                "generation_stage_attempt",
                stage_attempt.model_dump(mode="json"),
                completed_at,
            )
            if not last_errors and result is not None and metadata is not None:
                if stage not in generation.completedStages:
                    generation.completedStages.append(stage)
                generation.stageMessage = f"{message}已完成"
                self.storage.save_generation(generation)
                if self._cancel_requested(generation.id):
                    raise UserCancelledError()
                return result, metadata
            feedback = last_errors
            generation.stageMessage = (
                f"{message}未通过检查，准备第 {attempt_number + 1} 次尝试"
                if attempt_number < generation.stageMaxAttempts
                else f"{message}失败"
            )
            self.storage.save_generation(generation)
        raise StageGenerationError(stage, last_errors)

    def _update_skill_md_preview(
        self,
        generation: GenerationResult,
        brief: SkillBrief,
        spec: SkillSpec,
        *,
        workflow: WorkflowGenerationResult | None = None,
        knowledge: KnowledgeGenerationResult | None = None,
        quality: QualityGenerationResult | None = None,
    ) -> None:
        try:
            preview_ir = assemble_partial_skill_ir(
                brief,
                spec,
                workflow=workflow,
                knowledge=knowledge,
                quality=quality,
            )
            generation.skillMd = render_skill_md_text(preview_ir)
            self.storage.save_generation(generation)
        except Exception as exc:
            self.storage.add_run_event(
                generation.id,
                "skill_md_preview_failed",
                {"message": str(exc)},
                now_ms(),
            )

    def _cancel_requested(self, run_id: str) -> bool:
        current = self.storage.get_generation(run_id)
        return bool(current and current.cancelRequested)

    def _interrupt(self, generation: GenerationResult) -> GenerationResult:
        current = self.storage.get_generation(generation.id)
        if current is not None:
            generation.cancelRequested = current.cancelRequested
        assert_generation_transition(generation.status, "interrupted")
        generation.status = "interrupted"
        generation.currentStage = None
        generation.completedAt = now_ms()
        generation.failureCode = "USER_CANCELLED"
        generation.errorMessage = "用户已停止生成。"
        generation.stageMessage = "生成已停止"
        self.storage.add_run_event(
            generation.id,
            "cancelled",
            {"stage": generation.currentStage, "attempt": generation.stageAttempt},
            generation.completedAt,
        )
        return self.storage.save_generation(generation)

    def _append_skill_spec(
        self,
        generation: GenerationResult,
        spec: SkillSpec,
        *,
        created_at: int,
    ) -> None:
        payload = spec.model_dump(mode="json")
        spec_sha256 = sha256_json(payload)
        generation.skillSpecRevisions.append(
            SkillSpecRevision(
                revision=spec.revision,
                sha256=spec_sha256,
                spec=spec,
                createdAt=created_at,
                sourceIssueIds=list(spec.sourceIssueIds),
            )
        )
        generation.skillSpecAvailable = True
        generation.skillSpecRevision = spec.revision
        generation.skillSpecSha256 = spec_sha256

    def _current_spec(self, generation: GenerationResult) -> SkillSpec | None:
        if not generation.skillSpecRevisions:
            return None
        return generation.skillSpecRevisions[-1].spec

    def _spec_entry_for_revision(
        self,
        generation: GenerationResult,
        revision: int | None,
    ) -> SkillSpecRevision | None:
        if not generation.skillSpecRevisions:
            return None
        if revision is not None:
            for entry in reversed(generation.skillSpecRevisions):
                if entry.revision == revision:
                    return entry
        return generation.skillSpecRevisions[-1]

    def _transition(
        self,
        generation: GenerationResult,
        status: str,
        stage: str | None,
        progress: int,
        *,
        current_round: int | None = None,
        provider: ModelProviderConfig | None = None,
    ) -> None:
        # status is a string literal matching GenerationStatus; validated at runtime by assert_generation_transition
        assert_generation_transition(generation.status, status)
        generation.status = status  # type: ignore[assignment]
        generation.currentStage = stage  # type: ignore[assignment]
        generation.progress = min(max(generation.progress, progress), 99)
        if current_round is not None:
            generation.currentRound = current_round
        if provider is not None:
            generation.modelProviderId = provider.id
            generation.modelProtocol = provider.protocol
            if provider.lastTest is None:
                generation.providerConnectionRisk = "untested"
            elif provider.lastTest.status == "failed":
                generation.providerConnectionRisk = (
                    f"test-failed:{provider.lastTest.failureCategory or 'unknown'}"
                )
            else:
                generation.providerConnectionRisk = None
        self.storage.add_run_event(
            generation.id,
            "state_transition",
            {
                "status": status,
                "stage": stage,
                "progress": generation.progress,
                "round": generation.currentRound,
                "providerId": generation.modelProviderId,
            },
            now_ms(),
        )
        self.storage.save_generation(generation)

    def _fail(
        self,
        generation: GenerationResult,
        code: str,
        message: str,
    ) -> GenerationResult:
        assert_generation_transition(generation.status, "failed")
        generation.status = "failed"
        generation.currentStage = None
        generation.completedAt = now_ms()
        generation.failureCode = code
        generation.errorMessage = message
        self.storage.add_run_event(
            generation.id,
            "failed",
            {"code": code, "message": message},
            generation.completedAt,
        )
        return self.storage.save_generation(generation)


def _allowed_paths(issues: list[QualityIssue]) -> list[str]:
    paths = [
        path
        for issue in issues
        for path in issue.affectedPaths
        if path
    ]
    return list(dict.fromkeys(paths)) or [
        "skill.description",
        "workflow",
        "contextEngineering",
        "agentKnowledge",
    ]


def _locked_paths() -> list[str]:
    # User knowledge fields (unknownKnowledge, pitfalls, objective, ...) are
    # intentionally not locked: the model may rephrase and expand them, while
    # the validator and restore_authoritative_facts guarantee nothing is lost.
    return [
        "skill.name",
        "skill.language",
        "quality.hardRestrictions",
        "platforms.targets",
    ]


def _rendered_artifacts(attempt: GenerationAttempt | None) -> tuple[str, list[str]]:
    if attempt is None:
        return "", []
    rendered_files = sorted(attempt.fileHashes)
    try:
        ir = SkillIR.model_validate(attempt.skillIR)
        skill_md = (
            Path(attempt.renderedPath) / ir.skill.name / "SKILL.md"
        ).read_text(encoding="utf-8")
    except Exception:
        skill_md = ""
    return skill_md, rendered_files


def _redact_brief(brief: SkillBrief) -> SkillBrief:
    payload = brief.model_dump(mode="json")

    def redact(value: Any) -> Any:
        if isinstance(value, str):
            return redact_secrets(value)
        if isinstance(value, list):
            return [redact(item) for item in value]
        if isinstance(value, dict):
            return {key: redact(item) for key, item in value.items()}
        return value

    return SkillBrief.model_validate(redact(payload))


def _evaluation_signatures(
    brief: SkillBrief,
    spec: SkillSpec,
    ir: SkillIR,
    file_paths: list[str],
) -> tuple[str, str, str]:
    ir_payload = ir.model_dump(mode="json")
    implementation_ir = ir.model_copy(deep=True)
    implementation_ir.skill.description = ""
    return (
        sha256_json(ir_payload),
        sha256_json(
            {
                "description": ir.skill.description,
                "usage": brief.usage,
                "desiredOutcome": brief.desiredOutcome,
                "relatedSkills": brief.relatedSkills,
                "skillSpec": spec.model_dump(mode="json"),
            }
        ),
        sha256_json(
            {
                "brief": brief.model_dump(mode="json"),
                "skillSpec": spec.model_dump(mode="json"),
                "skillIRWithoutDescription": implementation_ir.model_dump(mode="json"),
                "filePaths": file_paths,
            }
        ),
    )


def _reusable_evaluations(
    attempts: list[GenerationAttempt],
    reports: dict[str, QualityEvaluationReport],
    *,
    activation_signature: str,
    implementation_signature: str,
) -> tuple[
    Any,
    str | None,
    Any,
    str | None,
]:
    activation = None
    activation_attempt_id = None
    implementation = None
    implementation_attempt_id = None
    for attempt in reversed(attempts):
        report = reports.get(attempt.id)
        if report is None:
            continue
        if (
            activation is None
            and attempt.activationSignature == activation_signature
            and report.activation is not None
        ):
            activation = report.activation.model_copy(deep=True)
            activation_attempt_id = attempt.id
        if (
            implementation is None
            and attempt.implementationSignature == implementation_signature
            and report.implementation is not None
        ):
            implementation = report.implementation.model_copy(deep=True)
            implementation_attempt_id = attempt.id
        if activation is not None and implementation is not None:
            break
    return (
        activation,
        activation_attempt_id,
        implementation,
        implementation_attempt_id,
    )
