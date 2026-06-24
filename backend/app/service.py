from __future__ import annotations

import json
import os
import shutil
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from pydantic import BaseModel
from statistics import mean
from typing import Any


class _SimpleTextOutput(BaseModel):
    text: str

from app.adapter import DEFAULT_INSTALL_DIRS, PLATFORM_LABELS
from app.agent import PydanticSkillAgents, SkillAgentRuntime
from app.cli_contracts import CLI_COMMANDS
from app.models import (
    AgentCallMetadata,
    AppSettings,
    CliCommandSpec,
    GenerationResult,
    HistoryItem,
    InstallRequest,
    InstallResult,
    KnowledgeInfo,
    ModelConnectionProvider,
    ModelConnectionStatus,
    ModelProviderConfig,
    ModelProviderConfigCreate,
    ModelProviderConfigPatch,
    PreviewResponse,
    ProviderTestResult,
    PurposeInfo,
    QualityEvaluationReport,
    SkillDraft,
    SkillIR,
    SkillSpecResponse,
    SkillSpecRevisionSummary,
    SupplementInfo,
    SupplementRequest,
    TaskABCreateRequest,
    TaskABOutput,
    TaskABRun,
    TaskABTaskVerdict,
    TriggerEvalQuery,
    TriggerEvalSet,
    TriggerOptimizationCreateRequest,
    TriggerOptimizationRun,
    UserSupplement,
    ValidationResponse,
)
from app.loop_helpers import cap_provider_timeout, majority_task_ab_verdict
from app.orchestrator import QualityOrchestrator
from app.provider_runtime import ModelProviderRuntime, PydanticAgentRuntime
from app.quality import QualityPolicy
from app.rules import RULES
from app.secret_store import SecretStore
from app.settings import Settings
from app.storage import Storage
from app.trigger_loop import TriggerOptimizationEngine
from app.utils import make_id, now_ms, sanitize_skill_name, sha256_file


class InstallUnavailableError(Exception):
    """The generation has no installable final package."""


class InstallConflictError(Exception):
    """The target directory already contains this skill."""

    def __init__(self, path: Path) -> None:
        super().__init__(str(path))
        self.path = path


class DraftDeleteConflictError(Exception):
    """The draft still has a generation in progress."""


class SkillForgeService:
    def __init__(
        self,
        settings: Settings,
        agents: SkillAgentRuntime | None = None,
    ) -> None:
        self.settings = settings
        self.settings.data_dir.mkdir(parents=True, exist_ok=True)
        self.settings.artifact_root.mkdir(parents=True, exist_ok=True)
        self.storage = Storage(settings.database_path)
        self.storage.recover_interrupted_generations()
        self.storage.recover_interrupted_trigger_runs()
        self._cleanup_expired_attempts()
        self.secret_store = SecretStore(
            encrypted_path=settings.encrypted_secrets_path,
            key_path=settings.secret_key_path,
            prefer_keyring=settings.use_system_keyring,
        )
        self.provider_runtime = ModelProviderRuntime(key_resolver=self._resolve_api_key)
        self._load_local_provider_config()
        self.agents = agents or PydanticSkillAgents(
            PydanticAgentRuntime(key_resolver=self._resolve_api_key)
        )
        self.orchestrator = QualityOrchestrator(
            settings=settings,
            storage=self.storage,
            agents=self.agents,
            policy=QualityPolicy(),
        )
        self._executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="skillforge")
        self._resume_lock = threading.Lock()
        self._resuming_runs: set[str] = set()
        self.trigger_engine = TriggerOptimizationEngine(
            storage=self.storage,
            agents=self.agents,
            orchestrator=self.orchestrator,
        )

    def create_draft(self, payload: dict[str, Any]) -> SkillDraft:
        timestamp = now_ms()
        draft = SkillDraft(
            id=payload.get("id") or make_id("draft"),
            name=sanitize_skill_name(payload.get("name") or payload.get("displayName")),
            displayName=payload.get("displayName") or payload.get("name"),
            targetPlatforms=payload.get("targetPlatforms", ["claude-code"]),
            purpose=PurposeInfo.model_validate(payload.get("purpose", {})),
            knowledge=KnowledgeInfo.model_validate(payload.get("knowledge", {})),
            supplement=SupplementInfo.model_validate(payload.get("supplement", {})),
            createdAt=payload.get("createdAt") or timestamp,
            updatedAt=payload.get("updatedAt") or timestamp,
        )
        return self.storage.save_draft(draft)

    def list_drafts(self) -> list[SkillDraft]:
        return self.storage.list_drafts()

    def get_draft(self, draft_id: str) -> SkillDraft | None:
        return self.storage.get_draft(draft_id)

    def patch_draft(self, draft_id: str, updates: dict[str, Any]) -> SkillDraft | None:
        draft = self.storage.get_draft(draft_id)
        if draft is None:
            return None
        merged = _deep_merge(draft.model_dump(mode="json"), updates)
        merged["id"] = draft.id
        merged["status"] = "draft"
        merged["name"] = sanitize_skill_name(merged.get("name") or merged.get("displayName"))
        merged["createdAt"] = draft.createdAt
        merged["updatedAt"] = now_ms()
        updated = SkillDraft.model_validate(merged)
        return self.storage.save_draft(updated)

    def delete_draft(self, draft_id: str) -> bool:
        if self.storage.get_draft(draft_id) is None:
            return False
        terminal = {"succeeded", "degraded", "failed", "interrupted"}
        generations = self.storage.list_generations_for_draft(draft_id)
        if any(generation.status not in terminal for generation in generations):
            raise DraftDeleteConflictError(
                "该记录有正在进行的生成任务，请先取消后再删除。"
            )
        deleted_ids = self.storage.delete_draft_cascade(draft_id)
        if deleted_ids is None:
            return False
        artifact_root = self.settings.artifact_root.resolve()
        for generation_id in deleted_ids:
            artifact_dir = (self.settings.artifact_root / generation_id).resolve()
            if artifact_dir.is_relative_to(artifact_root) and artifact_dir.is_dir():
                shutil.rmtree(artifact_dir, ignore_errors=True)
        return True

    def generate(
        self,
        draft_id: str,
        *,
        max_repair_rounds: int = 3,
        target_platforms: list[str] | None = None,
    ) -> GenerationResult | None:
        draft = self.storage.get_draft(draft_id)
        if draft is None:
            return None
        generation_id = make_id("gen")
        self.storage.create_generation_shell(
            generation_id=generation_id,
            draft_id=draft.id,
            started_at=now_ms(),
            max_repair_rounds=max_repair_rounds,
            target_platforms=target_platforms,
        )
        return self.orchestrator.run(generation_id)

    def start_generation(
        self,
        draft_id: str,
        *,
        max_repair_rounds: int = 3,
        target_platforms: list[str] | None = None,
    ) -> GenerationResult | None:
        draft = self.storage.get_draft(draft_id)
        if draft is None:
            return None
        generation = self.storage.create_generation_shell(
            generation_id=make_id("gen"),
            draft_id=draft.id,
            started_at=now_ms(),
            max_repair_rounds=max_repair_rounds,
            target_platforms=target_platforms,
        )
        self._executor.submit(self._run_generation, generation.id)
        return generation

    def submit_supplement(
        self,
        generation_id: str,
        payload: SupplementRequest,
        *,
        background: bool = True,
    ) -> GenerationResult | None:
        generation = self.storage.get_generation(generation_id)
        if generation is None:
            return None
        answers = [item.model_dump(mode="json") for item in payload.answers]
        if background:
            with self._resume_lock:
                if generation_id in self._resuming_runs:
                    return generation
                self._resuming_runs.add(generation_id)
            answer_by_issue = {
                item["issueId"]: item.get("answer")
                for item in answers
            }
            for question in generation.userQuestions:
                answer = answer_by_issue.get(question.issueId)
                skipped = payload.skip or answer is None
                self.storage.save_supplement(
                    UserSupplement(
                        id=make_id("supplement"),
                        runId=generation_id,
                        issueId=question.issueId,
                        question=question.question,
                        answer=None if skipped else answer,
                        skipped=skipped,
                        mergedPaths=[] if skipped else ["supplement.content"],
                        createdAt=now_ms(),
                    )
                )
            self._executor.submit(
                self._resume_generation,
                generation_id,
                answers,
                payload.skip,
            )
            return generation
        return self.orchestrator.resume_with_supplement(
            generation_id,
            answers=answers,
            skip=payload.skip,
        )

    def quality_report(self, generation_id: str) -> QualityEvaluationReport | None:
        generation = self.storage.get_generation(generation_id)
        if generation is None or not generation.bestAttemptId:
            return generation.qualityReport if generation else None
        return self.storage.get_quality_report(generation.bestAttemptId)

    def generation_spec(self, generation_id: str) -> SkillSpecResponse | None:
        generation = self.storage.get_generation(generation_id)
        if generation is None or not generation.skillSpecRevisions:
            return None
        current = generation.skillSpecRevisions[-1]
        return SkillSpecResponse(
            current=current.spec,
            revision=current.revision,
            sha256=current.sha256,
            revisions=[
                SkillSpecRevisionSummary(
                    revision=item.revision,
                    sha256=item.sha256,
                    createdAt=item.createdAt,
                    sourceIssueIds=item.sourceIssueIds,
                )
                for item in generation.skillSpecRevisions
            ],
        )

    def quality_payload(self, generation_id: str) -> dict[str, Any] | None:
        report = self.quality_report(generation_id)
        generation = self.storage.get_generation(generation_id)
        if report is None or generation is None:
            return None
        attempts = self.storage.list_attempts(generation_id)
        reports = {
            item.attemptId: item
            for item in self.storage.list_quality_reports(generation_id)
        }
        return {
            **report.model_dump(mode="json"),
            "qualityPolicyVersion": generation.qualityPolicyVersion,
            "repairHistory": [
                {
                    "attemptId": attempt.id,
                    "round": attempt.round,
                    "changedPaths": attempt.changedPaths,
                    "scores": (
                        {
                            "validation": reports[attempt.id].validationScore,
                            "activation": reports[attempt.id].activationScore,
                            "implementation": reports[attempt.id].implementationScore,
                            "overall": reports[attempt.id].overallScore,
                        }
                        if attempt.id in reports
                        else None
                    ),
                }
                for attempt in attempts
            ],
        }

    def attempts(self, generation_id: str) -> list[dict[str, Any]] | None:
        if self.storage.get_generation(generation_id) is None:
            return None
        reports = {
            item.attemptId: item
            for item in self.storage.list_quality_reports(generation_id)
        }
        generation = self.storage.get_generation(generation_id)
        return [
            {
                **attempt.model_dump(mode="json"),
                "isBest": generation is not None and generation.bestAttemptId == attempt.id,
                "qualityReport": (
                    reports[attempt.id].model_dump(mode="json")
                    if attempt.id in reports
                    else None
                ),
            }
            for attempt in self.storage.list_attempts(generation_id)
        ]

    def close(self) -> None:
        self._executor.shutdown(wait=True)

    def get_generation(self, generation_id: str) -> GenerationResult | None:
        return self.storage.get_generation(generation_id)

    def cancel_generation(self, generation_id: str) -> GenerationResult | None:
        generation = self.storage.get_generation(generation_id)
        if generation is None:
            return None
        if generation.status in {"succeeded", "degraded", "failed", "interrupted"}:
            return generation

        timestamp = now_ms()
        generation.cancelRequested = True
        if generation.status in {"queued", "normalizing", "awaiting_user_input"}:
            generation.status = "interrupted"
            generation.currentStage = None
            generation.completedAt = timestamp
            generation.failureCode = "USER_CANCELLED"
            generation.errorMessage = "用户已停止生成。"
            generation.stageMessage = "生成已停止"
            event = "cancelled"
        else:
            generation.stageMessage = "正在等待当前模型调用结束后停止"
            event = "cancel_requested"

        self.storage.add_run_event(
            generation.id,
            event,
            {
                "stage": generation.currentStage,
                "attempt": generation.stageAttempt,
            },
            timestamp,
        )
        return self.storage.save_generation(generation)

    # ---- Trigger description optimization ----------------------------------

    def start_trigger_optimization(
        self,
        generation_id: str,
        *,
        eval_set_id: str,
        max_iterations: int = 5,
        runs_per_query: int = 3,
        trigger_threshold: float = 0.5,
        holdout: float = 0.4,
        query_timeout_sec: int = 30,
    ) -> TriggerOptimizationRun | None:
        generation = self.storage.get_generation(generation_id)
        if generation is None:
            return None
        if generation.status not in {"succeeded", "degraded"}:
            return None
        if eval_set_id == "auto":
            eval_set = self.build_trigger_eval_set_from_draft(generation_id)
        else:
            eval_set = self.storage.get_trigger_eval_set(eval_set_id)
        if eval_set is None or len(eval_set.queries) < 2:
            return None
        run = TriggerOptimizationRun(
            id=make_id("topt"),
            generationId=generation_id,
            evalSetId=eval_set.id,
            status="queued",
            createdAt=now_ms(),
        )
        self.storage.save_trigger_optimization(run)
        self._executor.submit(
            self._run_trigger_optimization,
            run.id,
            json.dumps(eval_set.model_dump(mode="json"), ensure_ascii=False),
            max_iterations=max_iterations,
            runs_per_query=runs_per_query,
            trigger_threshold=trigger_threshold,
            holdout=holdout,
            query_timeout_sec=query_timeout_sec,
        )
        return run

    def build_trigger_eval_set_from_draft(self, generation_id: str) -> TriggerEvalSet | None:
        generation = self.storage.get_generation(generation_id)
        if generation is None:
            return None
        draft = self.storage.get_draft(generation.draftId)
        if draft is None:
            return None
        skill_name = (draft.displayName or draft.name or "skill").strip()
        queries: list[TriggerEvalQuery] = []
        for text in (
            draft.purpose.usage.strip(),
            draft.purpose.desiredOutcome.strip(),
            skill_name,
        ):
            if text:
                queries.append(TriggerEvalQuery(query=text, shouldTrigger=True))
        for text in (
            "帮我查一下今天上海的天气怎么样？",
            "用 Python 写一段快速排序代码",
            "把下面这段英文翻译成中文",
        ):
            queries.append(TriggerEvalQuery(query=text, shouldTrigger=False))
        if len(queries) < 2:
            return None
        eval_set_id = f"auto-{generation_id}"
        existing = self.storage.get_trigger_eval_set(eval_set_id)
        now = now_ms()
        return self.storage.save_trigger_eval_set(
            TriggerEvalSet(
                id=eval_set_id,
                name=f"{skill_name} auto",
                queries=queries,
                createdAt=existing.createdAt if existing else now,
                updatedAt=now,
            )
        )

    def _run_trigger_optimization(
        self,
        run_id: str,
        eval_set_payload: dict | str,
        *,
        max_iterations: int,
        runs_per_query: int,
        trigger_threshold: float,
        holdout: float,
        query_timeout_sec: int,
    ) -> None:
        import json as _json

        run = self.storage.get_trigger_optimization(run_id)
        if run is None:
            return
        try:
            if isinstance(eval_set_payload, str):
                eval_set = TriggerEvalSet.model_validate(_json.loads(eval_set_payload))
            else:
                eval_set = TriggerEvalSet.model_validate(eval_set_payload)
            result = self.trigger_engine.run_optimization(
                run,
                eval_queries=[q.model_dump(mode="json") for q in eval_set.queries],
                max_iterations=max_iterations,
                runs_per_query=runs_per_query,
                trigger_threshold=trigger_threshold,
                holdout=holdout,
                query_timeout_sec=query_timeout_sec,
            )
            if result.status == "completed" and result.chosenDescription:
                if result.chosenDescription.strip() != result.originalDescription.strip():
                    provenance = {
                        "originalDescription": result.originalDescription,
                        "chosenDescription": result.chosenDescription,
                        "detectionPath": result.detectionPath,
                        "iterationsRun": result.provenance.iterationsRun,
                        "trainScore": result.trainScore,
                        "testScore": result.testScore,
                        "exitReason": result.provenance.exitReason,
                        "claudeBinaryPresent": result.provenance.claudeBinaryPresent,
                        "runId": result.id,
                    }
                    try:
                        self.orchestrator.apply_optimized_description(
                            result.generationId,
                            result.chosenDescription,
                            optimization_provenance=provenance,
                        )
                    except Exception as writeback_exc:
                        run = self.storage.get_trigger_optimization(run_id)
                        if run is not None:
                            run.writebackFailed = True
                            run.writebackError = str(writeback_exc)
                            if run.errorMessage:
                                run.errorMessage = f"{run.errorMessage} 写回失败: {writeback_exc}"
                            else:
                                run.errorMessage = f"写回失败: {writeback_exc}"
                            self.storage.save_trigger_optimization(run)
                            self.storage.add_trigger_run_event(
                                run_id,
                                "writing_back",
                                {"status": "failed", "reason": str(writeback_exc)},
                                now_ms(),
                            )
        except Exception as exc:
            run = self.storage.get_trigger_optimization(run_id)
            if run is not None and run.status not in {"completed", "failed", "interrupted"}:
                run.status = "failed"
                run.errorMessage = str(exc)
                run.completedAt = now_ms()
                self.storage.save_trigger_optimization(run)

    def cancel_trigger_optimization(self, run_id: str) -> TriggerOptimizationRun | None:
        run = self.storage.get_trigger_optimization(run_id)
        if run is None:
            return None
        if run.status in {"completed", "failed", "interrupted"}:
            return run
        run.cancelRequested = True
        self.storage.save_trigger_optimization(run)
        return run

    def get_trigger_optimization(self, run_id: str) -> TriggerOptimizationRun | None:
        return self.storage.get_trigger_optimization(run_id)

    def list_trigger_optimizations_for_generation(self, generation_id: str) -> list[TriggerOptimizationRun]:
        return self.storage.list_trigger_optimizations_for_generation(generation_id)

    def trigger_run_events(self, run_id: str) -> list[dict[str, Any]] | None:
        if self.storage.get_trigger_optimization(run_id) is None:
            return None
        return self.storage.list_trigger_run_events(run_id)

    def apply_optimized_description_to_generation(
        self,
        generation_id: str,
        new_description: str,
        *,
        optimization_run_id: str | None = None,
    ) -> GenerationResult | None:
        run = self.storage.get_generation(generation_id)
        if run is None:
            return None
        provenance = {"runId": optimization_run_id} if optimization_run_id else {}
        try:
            return self.orchestrator.apply_optimized_description(
                generation_id,
                new_description,
                optimization_provenance=provenance,
            )
        except ValueError:
            return None

    def create_trigger_eval_set(self, name: str, queries: list[TriggerEvalQuery]) -> TriggerEvalSet:
        now = now_ms()
        return self.storage.save_trigger_eval_set(
            TriggerEvalSet(id=make_id("tes"), name=name, queries=queries, createdAt=now, updatedAt=now)
        )

    def get_trigger_eval_set(self, eval_set_id: str) -> TriggerEvalSet | None:
        return self.storage.get_trigger_eval_set(eval_set_id)

    def list_trigger_eval_sets(self) -> list[TriggerEvalSet]:
        return self.storage.list_trigger_eval_sets()

    def delete_trigger_eval_set(self, eval_set_id: str) -> bool:
        return self.storage.delete_trigger_eval_set(eval_set_id)

    def update_trigger_eval_set(
        self,
        eval_set_id: str,
        *,
        name: str,
        queries: list[TriggerEvalQuery],
    ) -> TriggerEvalSet | None:
        existing = self.storage.get_trigger_eval_set(eval_set_id)
        if existing is None:
            return None
        if len(queries) < 2:
            return None
        now = now_ms()
        return self.storage.save_trigger_eval_set(
            TriggerEvalSet(
                id=eval_set_id,
                name=name.strip() or existing.name,
                queries=queries,
                createdAt=existing.createdAt,
                updatedAt=now,
            )
        )

    # ---- Task A/B ----------------------------------------------------------

    def start_task_ab(
        self,
        generation_id: str,
        prompts: list[str],
        *,
        runs_per_prompt: int = 1,
        query_timeout_sec: int = 60,
    ) -> TaskABRun | None:
        generation = self.storage.get_generation(generation_id)
        if generation is None:
            return None
        if generation.status not in {"succeeded", "degraded"}:
            return None
        run = TaskABRun(
            id=make_id("tab"),
            generationId=generation_id,
            status="queued",
            prompts=[TaskABPrompt(prompt=p) for p in prompts],
            createdAt=now_ms(),
        )
        self.storage.save_task_ab_run(run)
        self._executor.submit(
            self._run_task_ab,
            run.id,
            runs_per_prompt=runs_per_prompt,
            query_timeout_sec=query_timeout_sec,
        )
        return run

    def _task_ab_cancel_requested(self, run_id: str) -> bool:
        record = self.storage.get_task_ab_run(run_id)
        return record is not None and record.cancelRequested

    def _run_task_ab(
        self,
        run_id: str,
        *,
        runs_per_prompt: int,
        query_timeout_sec: int,
    ) -> None:
        run = self.storage.get_task_ab_run(run_id)
        if run is None:
            return
        cli_probe = None
        try:
            generation = self.storage.get_generation(run.generationId)
            if generation is None or not generation.finalAttemptId:
                raise RuntimeError("找不到最终生成。")
            grader_providers = self.orchestrator._providers_for("task-evaluation")
            if not grader_providers:
                raise RuntimeError("没有可用的 task-evaluation provider。")
            grader_provider = grader_providers[0]
            timeout_ms = max(1000, query_timeout_sec * 1000)
            execution_provider = self._resolve_provider_for_role("generation")
            if execution_provider is not None:
                execution_provider = cap_provider_timeout(execution_provider, timeout_ms)

            cli_present = shutil.which("claude") is not None
            use_cli = False
            if cli_present:
                try:
                    from app.claude_task_probe import ClaudeTaskProbe, resolve_cli_model

                    skill_name, skill_description, skill_md = self._resolve_final_skill_identity(
                        run.generationId
                    )
                    cli_probe = ClaudeTaskProbe(
                        artifact_root=self.settings.artifact_root,
                        skill_name=skill_name,
                        skill_description=skill_description,
                        skill_md_text=skill_md,
                    )
                    cli_probe.prepare()
                    use_cli = True
                    run.detectionPath = "cli"
                    run.cliModel = resolve_cli_model()
                except Exception as exc:
                    run.errorMessage = run.errorMessage or f"CLI 探测失败,降级为 judge: {exc}"

            if not use_cli:
                if execution_provider is None:
                    raise RuntimeError("没有可用的 generation provider。")
                run.detectionPath = "judge"
                run.cliModel = None

            run.graderProviderId = grader_provider.id
            run.status = "running_with_skill"
            self.storage.save_task_ab_run(run)
            self.storage.add_task_ab_event(
                run.id,
                "running_with_skill",
                {
                    "prompts": len(run.prompts),
                    "runsPerPrompt": runs_per_prompt,
                    "detectionPath": run.detectionPath,
                },
                now_ms(),
            )

            def _interrupt() -> None:
                run.status = "interrupted"
                run.errorMessage = run.errorMessage or "用户已取消。"
                run.completedAt = now_ms()
                self.storage.save_task_ab_run(run)
                self.storage.add_task_ab_event(run.id, "interrupted", {}, run.completedAt)

            with_outputs: list[TaskABOutput] = []
            baseline_outputs: list[TaskABOutput] = []
            verdicts: list[TaskABTaskVerdict] = []

            for tp in run.prompts:
                if self._task_ab_cancel_requested(run_id):
                    _interrupt()
                    return

                round_verdicts: list[str] = []
                last_with_text = ""
                last_baseline_text = ""
                last_with_ms = 0
                last_baseline_ms = 0
                last_reasoning = ""

                for _ in range(max(1, runs_per_prompt)):
                    if self._task_ab_cancel_requested(run_id):
                        _interrupt()
                        return

                    run.status = "running_with_skill"
                    self.storage.save_task_ab_run(run)
                    last_with_text, last_with_ms = self._task_ab_with_skill_output(
                        tp.prompt,
                        generation,
                        execution_provider,
                        cli_probe=cli_probe,
                        query_timeout_sec=query_timeout_sec,
                        cancel_check=lambda: self._task_ab_cancel_requested(run_id),
                    )

                    run.status = "running_baseline"
                    self.storage.save_task_ab_run(run)
                    last_baseline_text, last_baseline_ms = self._task_ab_baseline_output(
                        tp.prompt,
                        generation,
                        execution_provider,
                        cli_probe=cli_probe,
                        query_timeout_sec=query_timeout_sec,
                        cancel_check=lambda: self._task_ab_cancel_requested(run_id),
                    )

                    run.status = "grading"
                    self.storage.save_task_ab_run(run)
                    from app.models import TaskABVerdictModel

                    verdict_model, _ = self.agents.grade_task_ab(
                        prompt=tp.prompt,
                        with_skill_output=last_with_text,
                        baseline_output=last_baseline_text,
                        provider=grader_provider,
                    )
                    round_verdicts.append(verdict_model.betterConfig)
                    last_reasoning = verdict_model.reasoning

                with_outputs.append(
                    TaskABOutput(
                        config="with_skill",
                        outputText=last_with_text,
                        durationMs=last_with_ms,
                    )
                )
                baseline_outputs.append(
                    TaskABOutput(
                        config="baseline",
                        outputText=last_baseline_text,
                        durationMs=last_baseline_ms,
                    )
                )
                majority = majority_task_ab_verdict(round_verdicts)
                verdicts.append(
                    TaskABTaskVerdict(
                        prompt=tp.prompt,
                        betterConfig=majority,
                        reasoning=last_reasoning,
                    )
                )

            run.outputs.extend(with_outputs)
            run.outputs.extend(baseline_outputs)
            run.verdicts = verdicts
            run.status = "completed"
            run.completedAt = now_ms()
            run.summary = _task_ab_summary(verdicts)
            self.storage.save_task_ab_run(run)
            self.storage.add_task_ab_event(
                run.id, "completed", {"summary": run.summary}, run.completedAt
            )
        except Exception as exc:
            run = self.storage.get_task_ab_run(run_id)
            if run is not None and run.status not in {"completed", "failed", "interrupted"}:
                run.status = "failed"
                run.errorMessage = str(exc)
                run.completedAt = now_ms()
                self.storage.save_task_ab_run(run)
        finally:
            if cli_probe is not None:
                try:
                    cli_probe.close()
                except Exception:
                    pass

    def _resolve_final_skill_identity(self, generation_id: str) -> tuple[str, str, str]:
        generation = self.storage.get_generation(generation_id)
        if generation is None or not generation.finalAttemptId:
            raise RuntimeError("生成尚未完成或缺少最终候选。")
        attempts = {a.id: a for a in self.storage.list_attempts(generation_id)}
        attempt = attempts.get(generation.finalAttemptId)
        if attempt is None:
            raise RuntimeError("找不到最终候选尝试记录。")
        ir = SkillIR.model_validate(attempt.skillIR)
        skill_md = self.orchestrator.read_final_skill_md(generation_id) or generation.skillMd or ""
        return ir.skill.name, ir.skill.description, skill_md

    def _task_ab_with_skill_output(
        self,
        prompt: str,
        generation: GenerationResult,
        provider: ModelProviderConfig | None,
        *,
        cli_probe: Any,
        query_timeout_sec: int,
        cancel_check: Any,
    ) -> tuple[str, int]:
        if cli_probe is not None:
            try:
                text, duration_ms, _ = cli_probe.run_with_skill(
                    prompt,
                    timeout_sec=query_timeout_sec,
                    cancel_check=cancel_check,
                )
                return text, duration_ms
            except Exception:
                pass
        if provider is None:
            return "[error: no execution provider]", 0
        text, meta = self._run_prompt_with_skill(prompt, generation, provider)
        return text, meta.durationMs if meta else 0

    def _task_ab_baseline_output(
        self,
        prompt: str,
        generation: GenerationResult,
        provider: ModelProviderConfig | None,
        *,
        cli_probe: Any,
        query_timeout_sec: int,
        cancel_check: Any,
    ) -> tuple[str, int]:
        if cli_probe is not None:
            try:
                text, duration_ms, _ = cli_probe.run_baseline(
                    prompt,
                    timeout_sec=query_timeout_sec,
                    cancel_check=cancel_check,
                )
                return text, duration_ms
            except Exception:
                pass
        if provider is None:
            return "[error: no execution provider]", 0
        text, meta = self._run_prompt_baseline(prompt, generation, provider)
        return text, meta.durationMs if meta else 0

    def _run_prompt_with_skill(
        self,
        prompt: str,
        generation: GenerationResult,
        provider: ModelProviderConfig,
    ) -> tuple[str, AgentCallMetadata | None]:
        skill_text = self.orchestrator.read_final_skill_md(generation.id)
        if not skill_text:
            skill_text = generation.skillMd or ""

        system_context = ""
        if skill_text:
            system_context = (
                "You have access to the following skill/instructions. "
                "Follow them carefully when responding:\n\n"
                f"{skill_text}\n\n"
                "--- End of skill instructions ---\n\n"
            )

        full_prompt = f"{system_context}User request: {prompt}"

        try:
            result, meta = self.agents.runtime.run_structured(
                provider=provider,
                role="generation",
                instructions=(
                    "You are a helpful assistant with access to a skill. "
                    "Use the skill instructions provided in the context to guide your response."
                ),
                prompt=full_prompt,
                output_type=_SimpleTextOutput,
                prompt_version="task-ab-with-skill-v1",
            )
            return result.text, meta
        except Exception:
            # Fallback: use provider_runtime directly for raw text
            text, _ = self._raw_provider_call(provider, full_prompt)
            return text, None

    def _run_prompt_baseline(
        self,
        prompt: str,
        generation: GenerationResult,
        provider: ModelProviderConfig,
    ) -> tuple[str, AgentCallMetadata | None]:
        # Same provider, same model, same prompt — but WITHOUT skill context.
        try:
            result, meta = self.agents.runtime.run_structured(
                provider=provider,
                role="generation",
                instructions=(
                    "You are a helpful assistant. Respond to the user's request to the best of your ability."
                ),
                prompt=prompt,
                output_type=_SimpleTextOutput,
                prompt_version="task-ab-baseline-v1",
            )
            return result.text, meta
        except Exception:
            text, _ = self._raw_provider_call(provider, prompt)
            return text, None

    def _raw_provider_call(
        self,
        provider: ModelProviderConfig,
        prompt: str,
    ) -> tuple[str, AgentCallMetadata | None]:
        """Fallback: call the provider directly without structured output."""
        import time
        started = time.perf_counter()
        api_key = self._resolve_api_key(provider.apiKeyRef.name)
        if not api_key:
            return "[error: missing api key]", None

        messages = [{"role": "user", "content": prompt}]
        if provider.protocol == "anthropic":
            import anthropic
            client = anthropic.Anthropic(
                api_key=api_key,
                base_url=provider.baseUrl,
                timeout=provider.timeoutMs / 1000,
                max_retries=provider.retries,
            )
            resp = client.messages.create(
                model=provider.defaultModel,
                max_tokens=4096,
                messages=messages,
            )
            text = resp.content[0].text if resp.content else ""
        else:
            from openai import OpenAI
            client = OpenAI(
                api_key=api_key,
                base_url=provider.baseUrl.rstrip("/") + "/v1",
                timeout=provider.timeoutMs / 1000,
                max_retries=provider.retries,
            )
            resp = client.chat.completions.create(
                model=provider.defaultModel,
                messages=messages,
                max_tokens=4096,
            )
            text = resp.choices[0].message.content or ""

        duration_ms = max(0, round((time.perf_counter() - started) * 1000))
        meta = AgentCallMetadata(
            providerId=provider.id,
            providerRole="task-evaluation",
            protocol=provider.protocol,
            model=provider.defaultModel,
            promptVersion="task-ab-fallback-v1",
            inputTokens=0,
            outputTokens=0,
            requests=1,
            durationMs=duration_ms,
            estimatedCostUsd=None,
        )
        return text, meta

    def cancel_task_ab(self, run_id: str) -> TaskABRun | None:
        run = self.storage.get_task_ab_run(run_id)
        if run is None:
            return None
        if run.status in {"completed", "failed", "interrupted"}:
            return run
        run.cancelRequested = True
        self.storage.save_task_ab_run(run)
        return run

    def get_task_ab_run(self, run_id: str) -> TaskABRun | None:
        return self.storage.get_task_ab_run(run_id)

    def list_task_ab_runs_for_generation(self, generation_id: str) -> list[TaskABRun]:
        return self.storage.list_task_ab_runs_for_generation(generation_id)

    def task_ab_run_events(self, run_id: str) -> list[dict[str, Any]] | None:
        if self.storage.get_task_ab_run(run_id) is None:
            return None
        return self.storage.list_task_ab_events(run_id)

    def preview(self, generation_id: str) -> PreviewResponse | None:
        generation = self.storage.get_generation(generation_id)
        if generation is None:
            return None
        return PreviewResponse(files=generation.files, skillMd=generation.skillMd)

    def validation(self, generation_id: str) -> ValidationResponse | None:
        generation = self.storage.get_generation(generation_id)
        if generation is None:
            return None
        return ValidationResponse(
            generationId=generation.id,
            items=generation.validation,
            blockingIssues=generation.blockingIssues,
            warnings=generation.warnings,
        )

    def download_path(self, generation_id: str) -> Path | None:
        generation = self.storage.get_generation(generation_id)
        if generation is None or not generation.zipPath:
            return None
        path = Path(generation.zipPath).resolve()
        artifact_root = self.settings.artifact_root.resolve()
        if not path.is_relative_to(artifact_root) or not path.is_file():
            return None
        if not generation.artifactSha256 or sha256_file(path) != generation.artifactSha256:
            return None
        return path

    def install_skill(
        self,
        generation_id: str,
        payload: InstallRequest,
    ) -> InstallResult | None:
        generation = self.storage.get_generation(generation_id)
        if generation is None:
            return None
        if generation.status not in {"succeeded", "degraded"} or not generation.artifactDir:
            raise InstallUnavailableError("生成尚未产出可安装的最终包。")

        package_root = (Path(generation.artifactDir) / "package").resolve()
        artifact_root = self.settings.artifact_root.resolve()
        if not package_root.is_relative_to(artifact_root) or not package_root.is_dir():
            raise InstallUnavailableError("最终包目录不存在或不在产物目录内。")
        skill_dirs = [
            entry
            for entry in package_root.iterdir()
            if entry.is_dir() and (entry / "SKILL.md").is_file()
        ]
        if len(skill_dirs) != 1:
            raise InstallUnavailableError("最终包内未找到唯一的 Skill 目录。")
        source = skill_dirs[0]
        skill_name = source.name

        platform = payload.platform
        if platform is None and payload.targetDir is None:
            platforms = generation.targetPlatformsOverride
            if not platforms:
                draft = self.storage.get_draft(generation.draftId)
                platforms = draft.targetPlatforms if draft else []
            platform = next(
                (target for target in platforms if target in DEFAULT_INSTALL_DIRS),
                "claude-code",
            )
        if payload.targetDir:
            target_base = Path(payload.targetDir).expanduser()
        else:
            target_base = Path(DEFAULT_INSTALL_DIRS[platform]).expanduser()
        if not target_base.is_absolute():
            raise InstallUnavailableError("安装目录必须是绝对路径。")
        destination = (target_base / skill_name).resolve()
        home = Path.home().resolve()
        if destination in {home, Path("/")} or destination.is_relative_to(artifact_root):
            raise InstallUnavailableError("安装目录不合法。")

        overwrote = False
        if destination.exists():
            if not payload.overwrite:
                raise InstallConflictError(destination)
            if not destination.is_dir() or destination.name != skill_name:
                raise InstallUnavailableError("目标位置已被非 Skill 内容占用，请手动处理。")
            shutil.rmtree(destination)
            overwrote = True
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(source, destination)
        file_count = sum(1 for item in destination.rglob("*") if item.is_file())
        installed_at = datetime.now(timezone.utc).isoformat()
        self.storage.add_run_event(
            generation_id,
            "installed_locally",
            {
                "skillName": skill_name,
                "installedPath": str(destination),
                "platform": platform,
                "overwrote": overwrote,
                "fileCount": file_count,
            },
            now_ms(),
        )
        return InstallResult(
            generationId=generation_id,
            skillName=skill_name,
            platform=platform,
            installedPath=str(destination),
            fileCount=file_count,
            overwrote=overwrote,
            installedAt=installed_at,
        )

    def run_events(self, generation_id: str) -> list[dict[str, Any]] | None:
        if self.storage.get_generation(generation_id) is None:
            return None
        return self.storage.list_run_events(generation_id)

    def error_patterns(self) -> list[dict[str, Any]]:
        return self.storage.list_error_patterns()

    def diagnostics_metrics(self) -> dict[str, Any]:
        runs = self.storage.list_generations()
        terminal = [
            run for run in runs
            if run.status in {"succeeded", "degraded", "failed", "interrupted"}
        ]
        strict_count = sum(run.status == "succeeded" for run in terminal)
        degraded_count = sum(run.status == "degraded" for run in terminal)
        failed_count = sum(run.status in {"failed", "interrupted"} for run in terminal)
        first_pass_count = 0
        score_improvements: list[float] = []
        criterion_scores: dict[str, list[float]] = {}
        regressions = 0
        model_calls: dict[str, list[Any]] = {}
        model_attempt_results: dict[str, list[bool]] = {}
        supplement_runs = 0
        skipped_supplements = 0
        supplement_count = 0

        for run in terminal:
            reports = self.storage.list_quality_reports(run.id)
            reports_by_attempt = {report.attemptId: report for report in reports}
            if reports and reports[0].passedStrictGate:
                first_pass_count += 1
            for report in reports:
                for evaluation in [report.activation, report.implementation]:
                    if evaluation is None:
                        continue
                    for criterion in evaluation.criterionScores:
                        key = f"{evaluation.dimension}.{criterion.criterion}"
                        criterion_scores.setdefault(key, []).append(
                            criterion.score / 4 * 100
                        )
            for previous, current in zip(reports, reports[1:]):
                if previous.overallScore is None or current.overallScore is None:
                    continue
                improvement = current.overallScore - previous.overallScore
                score_improvements.append(improvement)
                regressions += improvement < 0
            for attempt in self.storage.list_attempts(run.id):
                for call in attempt.agentCalls:
                    model_calls.setdefault(call.model, []).append(call)
                report = reports_by_attempt.get(attempt.id)
                if report is not None:
                    for model in {call.model for call in attempt.agentCalls}:
                        model_attempt_results.setdefault(model, []).append(
                            report.passedStrictGate
                        )
            supplements = self.storage.list_supplements(run.id)
            if supplements:
                supplement_runs += 1
            supplement_count += len(supplements)
            skipped_supplements += sum(item.skipped for item in supplements)

        def rate(numerator: int, denominator: int) -> float:
            return round(numerator / denominator * 100, 2) if denominator else 0

        model_metrics = {}
        for model, calls in model_calls.items():
            durations = sorted(call.durationMs for call in calls)
            p95_index = max(0, round((len(durations) - 1) * 0.95))
            model_metrics[model] = {
                "calls": len(calls),
                "inputTokens": sum(call.inputTokens for call in calls),
                "outputTokens": sum(call.outputTokens for call in calls),
                "estimatedCostUsd": round(
                    sum(call.estimatedCostUsd or 0 for call in calls),
                    6,
                ),
                "p95LatencyMs": durations[p95_index] if durations else 0,
                "strictPassRate": rate(
                    sum(model_attempt_results.get(model, [])),
                    len(model_attempt_results.get(model, [])),
                ),
            }

        technical_failure_rate = rate(failed_count, len(terminal))
        alerts = []
        if technical_failure_rate > 20:
            alerts.append("技术失败率超过 20%。")
        if any(
            pattern["criterion"] == "RULE-001"
            for pattern in self.storage.list_error_patterns()
        ):
            alerts.append("检测到强制规则完整性问题。")

        # Trigger-optimization / TaskAB empirical-loop metrics (optional).
        all_trigger_runs: list[TriggerOptimizationRun] = []
        for gen in self.storage.list_generations():
            all_trigger_runs.extend(
                self.storage.list_trigger_optimizations_for_generation(gen.id)
            )
        all_ab_runs: list[TaskABRun] = []
        for gen in self.storage.list_generations():
            all_ab_runs.extend(self.storage.list_task_ab_runs_for_generation(gen.id))

        trigger_completed = [r for r in all_trigger_runs if r.status == "completed"]
        cli_detected = sum(1 for r in trigger_completed if r.detectionPath == "cli")
        judge_detected = sum(1 for r in trigger_completed if r.detectionPath == "judge")
        trigger_train_scores: list[float] = []
        trigger_test_scores: list[float] = []
        for r in trigger_completed:
            parts = r.trainScore.split("/")
            if len(parts) == 2 and parts[1] != "0":
                trigger_train_scores.append(int(parts[0]) / int(parts[1]) * 100)
            if r.testScore:
                tp = r.testScore.split("/")
                if len(tp) == 2 and tp[1] != "0":
                    trigger_test_scores.append(int(tp[0]) / int(tp[1]) * 100)

        ab_completed = [r for r in all_ab_runs if r.status == "completed"]
        ab_summary_agg = _task_ab_summary([v for r in ab_completed for v in r.verdicts])

        return {
            "runCount": len(terminal),
            "firstRoundStrictPassRate": rate(first_pass_count, len(terminal)),
            "finalStrictPassRate": rate(strict_count, len(terminal)),
            "degradedDeliveryRate": rate(degraded_count, len(terminal)),
            "technicalFailureRate": technical_failure_rate,
            "averageRepairRounds": round(
                mean(run.currentRound for run in terminal),
                2,
            ) if terminal else 0,
            "averageScoreImprovement": round(mean(score_improvements), 2)
            if score_improvements else 0,
            "scoreRegressionRate": rate(regressions, len(score_improvements)),
            "supplementPromptRate": rate(supplement_runs, len(terminal)),
            "supplementSkipRate": rate(skipped_supplements, supplement_count),
            "criterionAverageScores": {
                criterion: round(mean(scores), 2)
                for criterion, scores in criterion_scores.items()
            },
            "issueFrequency": self.storage.list_error_patterns(),
            "models": model_metrics,
            "alerts": alerts,
            "triggerOptimization": {
                "runCount": len(all_trigger_runs),
                "completedCount": len(trigger_completed),
                "cliDetectionCount": cli_detected,
                "judgeDetectionCount": judge_detected,
                "averageTrainScore": round(mean(trigger_train_scores), 2) if trigger_train_scores else 0,
                "averageTestScore": round(mean(trigger_test_scores), 2) if trigger_test_scores else None,
            },
            "taskAB": {
                "runCount": len(all_ab_runs),
                "completedCount": len(ab_completed),
                **ab_summary_agg,
            },
        }

    def history(self) -> list[HistoryItem]:
        items: list[HistoryItem] = []
        for draft in self.storage.list_drafts():
            generations = self.storage.list_generations_for_draft(draft.id)
            latest = generations[0] if generations else None
            if latest is None:
                status = "draft"
                updated_at = draft.updatedAt
            elif latest.status == "succeeded":
                status = "downloadable"
                updated_at = latest.completedAt or latest.startedAt
            elif latest.status == "degraded":
                status = "degraded"
                updated_at = latest.completedAt or latest.startedAt
            elif latest.status == "awaiting_user_input":
                status = "awaiting-user-input"
                updated_at = latest.startedAt
            elif latest.status == "interrupted":
                status = "interrupted"
                updated_at = latest.completedAt or latest.startedAt
            elif latest.status == "failed":
                status = "failed"
                updated_at = latest.completedAt or latest.startedAt
            elif latest.status in {
                "running_validation_checks",
                "evaluating_activation",
                "evaluating_implementation",
                "aggregating_scores",
            }:
                status = "validating"
                updated_at = latest.startedAt
            else:
                status = "generating"
                updated_at = latest.startedAt
            items.append(
                HistoryItem(
                    id=draft.id,
                    generationId=latest.id if latest else None,
                    displayName=draft.displayName,
                    name=draft.name,
                    status=status,
                    platforms=[PLATFORM_LABELS[target] for target in draft.targetPlatforms],
                    createdAt=_format_local(draft.createdAt),
                    updatedAt=_format_local(updated_at),
                )
            )
        return items

    def rules(self) -> list[dict[str, Any]]:
        return RULES

    def create_provider(self, payload: ModelProviderConfigCreate) -> ModelProviderConfig:
        provider = ModelProviderConfig(id=make_id("provider"), **payload.model_dump(mode="json", exclude={"apiKey"}))
        if payload.apiKey:
            self.secret_store.set(provider.apiKeyRef.name, payload.apiKey)
        return self.storage.save_provider(provider, now_ms())

    def list_providers(self) -> list[ModelProviderConfig]:
        return self.storage.list_providers()

    def get_provider(self, provider_id: str) -> ModelProviderConfig | None:
        return self.storage.get_provider(provider_id)

    def patch_provider(self, provider_id: str, updates: ModelProviderConfigPatch) -> ModelProviderConfig | None:
        provider = self.storage.get_provider(provider_id)
        if provider is None:
            return None
        merged = provider.model_dump(mode="json")
        update_payload = updates.model_dump(mode="json", exclude_none=True)
        api_key = update_payload.pop("apiKey", None)
        for key, value in update_payload.items():
            merged[key] = value
        merged["id"] = provider.id
        merged["lastTest"] = provider.lastTest.model_dump(mode="json") if provider.lastTest else None
        updated = ModelProviderConfig.model_validate(merged)
        if api_key:
            self.secret_store.set(updated.apiKeyRef.name, api_key)
        saved = self.storage.save_provider(updated, now_ms())
        # If the key reference was renamed, drop the now-orphaned secret so a
        # stale key cannot linger in the keychain after the provider moved on.
        if updated.apiKeyRef.name != provider.apiKeyRef.name:
            self._forget_secret_if_unused(provider.apiKeyRef.name)
        return saved

    def delete_provider(self, provider_id: str) -> bool:
        provider = self.storage.get_provider(provider_id)
        deleted = self.storage.delete_provider(provider_id)
        # Remove the stored API key too, so deleting a provider really clears
        # its secret instead of leaving it behind in the keychain.
        if deleted and provider is not None:
            self._forget_secret_if_unused(provider.apiKeyRef.name)
        return deleted

    def _forget_secret_if_unused(self, key_name: str) -> None:
        still_referenced = any(
            other.apiKeyRef.name == key_name for other in self.storage.list_providers()
        )
        if not still_referenced:
            self.secret_store.delete(key_name)

    def test_provider(self, provider_id: str) -> ProviderTestResult | None:
        provider = self.storage.get_provider(provider_id)
        if provider is None:
            return None
        result = self.provider_runtime.test_connection(provider)
        self.storage.save_provider_test_result(provider_id, result, now_ms())
        return result

    def connection_status(self) -> ModelConnectionStatus:
        app_settings = self.get_settings()
        generation_provider = self._resolve_provider_for_role(
            "generation",
            app_settings.defaultGenerateProvider,
        )
        if generation_provider is None:
            return ModelConnectionStatus(
                status="unconfigured",
                message="尚未配置启用的 generation Provider。",
            )

        judge_provider = (
            self._resolve_provider_for_role(
                "activation-evaluation",
                app_settings.defaultValidateProvider,
            )
            or self._resolve_provider_for_role(
                "validation-explanation",
                app_settings.defaultValidateProvider,
            )
            or generation_provider
        )
        repair_provider = (
            self._resolve_provider_for_role(
                "repair",
                app_settings.defaultRepairProvider,
            )
            or generation_provider
        )
        required_providers = {
            "生成": generation_provider,
            "修复": repair_provider,
            "评测": judge_provider,
        }
        untested_roles = [
            role
            for role, provider in required_providers.items()
            if provider.lastTest is None
        ]
        failed = [
            (role, provider.lastTest)
            for role, provider in required_providers.items()
            if provider.lastTest is not None and provider.lastTest.status == "failed"
        ]
        if failed:
            role, last_test = failed[0]
            status = "error"
            message = f"{role} Provider 连接失败：{last_test.message}"
            checked_at = last_test.testedAt
        elif untested_roles:
            status = "disconnected"
            message = f"{'、'.join(untested_roles)} Provider 尚未通过连接测试。"
            checked_at = None
        else:
            status = "connected"
            message = "生成、修复和评测模型连接均可用。"
            checked_at = max(
                provider.lastTest.testedAt
                for provider in required_providers.values()
                if provider.lastTest is not None
            )

        return ModelConnectionStatus(
            status=status,
            generationProvider=_connection_provider(generation_provider),
            judgeProvider=_connection_provider(judge_provider),
            checkedAt=checked_at,
            message=message,
        )

    def cli_commands(self) -> list[CliCommandSpec]:
        return CLI_COMMANDS

    def get_settings(self) -> AppSettings:
        raw = self.storage.get_setting("app_settings")
        if raw:
            try:
                return AppSettings.model_validate_json(raw)
            except Exception:
                pass
        return AppSettings()

    def save_settings(self, settings: AppSettings) -> AppSettings:
        self.storage.save_setting("app_settings", settings.model_dump_json())
        return settings

    def model_is_connected(self) -> bool:
        return self.connection_status().status == "connected"

    def _run_generation(self, generation_id: str) -> None:
        try:
            self.orchestrator.run(generation_id)
        except Exception as exc:
            generation = self.storage.get_generation(generation_id)
            if generation is not None and generation.status not in {
                "succeeded",
                "degraded",
                "failed",
                "interrupted",
            }:
                self.orchestrator.fail_unhandled(
                    generation,
                    "UNHANDLED_BACKGROUND_ERROR",
                    f"后台生成任务异常：{exc}",
                )

    def _resume_generation(
        self,
        generation_id: str,
        answers: list[dict[str, Any]],
        skip: bool,
    ) -> None:
        try:
            self.orchestrator.resume_with_supplement(
                generation_id,
                answers=answers,
                skip=skip,
            )
        except Exception as exc:
            generation = self.storage.get_generation(generation_id)
            if generation is not None and generation.status not in {
                "succeeded",
                "degraded",
                "failed",
                "interrupted",
            }:
                self.orchestrator.fail_unhandled(
                    generation,
                    "SUPPLEMENT_RESUME_FAILED",
                    f"补充信息后恢复任务失败：{exc}",
                )
        finally:
            with self._resume_lock:
                self._resuming_runs.discard(generation_id)

    def _resolve_provider_for_role(self, role: str, preferred_id: str = "") -> ModelProviderConfig | None:
        """Find the best provider for a role, preferring the saved default.

        Falls back to the first enabled provider with the required role if the
        preferred provider is not found, disabled, or lacks the required role.
        """
        if preferred_id:
            provider = self.storage.get_provider(preferred_id)
            if provider and provider.enabled and role in provider.roles:
                return provider
        return self.storage.find_enabled_provider_for_role(role)

    def _load_local_provider_config(self) -> None:
        if self.storage.list_providers() or not self.settings.provider_config_path.exists():
            return
        payload = json.loads(self.settings.provider_config_path.read_text(encoding="utf-8"))
        if not isinstance(payload, list):
            return
        for item in payload:
            if not isinstance(item, dict):
                continue
            provider_id = item.get("id") or make_id("provider")
            provider = ModelProviderConfig.model_validate({**item, "id": provider_id})
            self.storage.save_provider(provider, now_ms())

    def _resolve_api_key(self, name: str) -> str | None:
        """Resolve a provider key: environment variable first, then the
        encrypted secret store where UI-saved keys are persisted."""
        return os.environ.get(name) or self.secret_store.get(name)

    def _cleanup_expired_attempts(self) -> None:
        cutoff = now_ms() - self.settings.attempt_retention_days * 86_400_000
        for generation in self.storage.list_generations():
            if not generation.completedAt or generation.completedAt >= cutoff:
                continue
            attempts_dir = self.settings.artifact_root / generation.id / "attempts"
            if attempts_dir.exists():
                try:
                    # Verify path is within artifact_root before removing
                    if attempts_dir.resolve().is_relative_to(self.settings.artifact_root.resolve()):
                        shutil.rmtree(attempts_dir)
                except OSError:
                    pass


def _deep_merge(base: dict[str, Any], updates: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in updates.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _format_local(timestamp_ms: int) -> str:
    return datetime.fromtimestamp(timestamp_ms / 1000, tz=timezone.utc).strftime("%Y-%m-%d %H:%M")


def _connection_provider(provider: ModelProviderConfig) -> ModelConnectionProvider:
    return ModelConnectionProvider(
        id=provider.id,
        name=provider.name,
        model=provider.defaultModel,
        protocol=provider.protocol,
    )


def _task_ab_summary(verdicts: list[TaskABTaskVerdict]) -> dict[str, Any]:
    with_skill = sum(1 for v in verdicts if v.betterConfig == "with_skill")
    baseline = sum(1 for v in verdicts if v.betterConfig == "baseline")
    ties = sum(1 for v in verdicts if v.betterConfig == "tie")
    return {
        "total": len(verdicts),
        "withSkillWins": with_skill,
        "baselineWins": baseline,
        "ties": ties,
        "withSkillWinRate": round(with_skill / len(verdicts), 2) if verdicts else 0,
    }
