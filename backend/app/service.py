from __future__ import annotations

import json
import os
import shutil
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any

from app.adapter import DEFAULT_INSTALL_DIRS, PLATFORM_LABELS
from app.agent import PydanticSkillAgents, SkillAgentRuntime
from app.cli_contracts import CLI_COMMANDS
from app.models import (
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
    SkillSpecResponse,
    SkillSpecRevisionSummary,
    SupplementInfo,
    SupplementRequest,
    UserSupplement,
    ValidationResponse,
)
from app.orchestrator import QualityOrchestrator
from app.provider_runtime import ModelProviderRuntime, PydanticAgentRuntime
from app.quality import QualityPolicy
from app.rules import RULES
from app.secret_store import SecretStore
from app.settings import Settings
from app.storage import Storage
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
        """Find the best provider for a role, preferring the saved default."""
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
