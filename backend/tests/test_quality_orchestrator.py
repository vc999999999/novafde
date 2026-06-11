from pathlib import Path
import threading

from app.models import (
    AppSettings,
    AgentCallMetadata,
    CriterionScore,
    JudgeEvaluation,
    ModelProviderConfig,
    QualityIssue,
    RepairAgentResult,
    SkillIR,
)
from app.normalizer import normalize_draft
from app.orchestrator import QualityOrchestrator
from app.quality import QualityPolicy
from app.settings import Settings
from app.storage import Storage
from app.utils import make_id, now_ms
from tests.test_api_pipeline import build_draft_payload


def provider() -> ModelProviderConfig:
    return ModelProviderConfig(
        id="provider_test",
        name="test",
        protocol="openai-compatible",
        baseUrl="http://127.0.0.1:11434/v1",
        apiKeyRef={"type": "env", "name": "TEST_KEY"},
        defaultModel="test",
        roles=[
            "generation",
            "repair",
            "activation-evaluation",
            "implementation-evaluation",
        ],
    )


def metadata(role: str, provider_id: str = "provider_test") -> AgentCallMetadata:
    return AgentCallMetadata(
        providerId=provider_id,
        providerRole=role,
        protocol="openai-compatible",
        model="test",
        promptVersion=f"{role}-v1",
    )


def judge(dimension: str, score: int, *, user_issue: bool = False) -> JudgeEvaluation:
    criteria = (
        [
            "specificity",
            "completeness",
            "trigger-term-quality",
            "distinctiveness-conflict-risk",
        ]
        if dimension == "activation"
        else [
            "conciseness",
            "actionability",
            "workflow-clarity",
            "progressive-disclosure",
        ]
    )
    issue = QualityIssue(
        issueId=f"{dimension}-needs-fact",
        source=dimension,
        criterion="completeness",
        severity="quality_error",
        score=score,
        reason="缺少组织专属完成条件",
        evidence=["brief.completionCriteria"],
        suggestion="请用户补充验收边界",
        affectedPaths=["workflow.verification"],
        requiresUserInput=user_issue,
        userQuestion="什么条件代表该流程可以正式结束？" if user_issue else None,
        inputControl="long-text" if user_issue else None,
    )
    return JudgeEvaluation(
        dimension=dimension,
        criterionScores=[
            CriterionScore(
                criterion=name,
                score=score,
                reason="reason",
                evidence=["evidence"],
                suggestion="suggestion",
                requiresUserInput=user_issue and index == 1,
                userQuestion="什么条件代表该流程可以正式结束？" if user_issue and index == 1 else None,
                inputControl="long-text" if user_issue and index == 1 else None,
            )
            for index, name in enumerate(criteria, start=1)
        ],
        summary="summary",
        issues=[issue] if score < 4 else [],
        confidence=1,
        requiresRepair=score < 4,
        requiresUserInput=user_issue,
    )


def valid_ir() -> SkillIR:
    from app.agent import restore_authoritative_facts
    from app.models import SkillDraft

    draft = SkillDraft.model_validate(
        {
            **build_draft_payload(),
            "id": "draft_1",
            "createdAt": 1,
            "updatedAt": 1,
        }
    )
    brief, _ = normalize_draft(draft)
    payload = {
        "schemaVersion": "1.0",
        "skill": {
            "name": "product-research",
            "description": "Use when a product team needs evidence-backed competitor research and traceable conclusions.",
            "language": "en",
        },
        "workflow": {
            "objective": brief.desiredOutcome,
            "steps": [
                {
                    "id": "step_1",
                    "purpose": "Collect evidence",
                    "action": "Collect and classify sources against the research questions.",
                    "input": "Research scope and available sources",
                    "output": "Traceable evidence set",
                    "validation": "Every claim links to a source",
                    "failureHandling": "List evidence gaps instead of inventing conclusions",
                }
            ],
            "decisionPoints": [],
            "failureHandling": ["List evidence gaps"],
            "verification": ["Every claim links to a source"],
        },
        "contextEngineering": {
            "filesystemAssumptions": ["Load references only when needed."],
            "references": ["references/domain-knowledge.md"],
            "scripts": [],
            "assets": [],
        },
        "agentKnowledge": {
            "unknownKnowledge": brief.professionalInformation,
            "pitfalls": [item.model_dump(mode="json") for item in brief.pitfalls],
            "examples": [],
            "counterExamples": [],
            "relatedSkills": brief.relatedSkills,
            "supplementalContext": brief.supplementalContext,
        },
        "quality": {
            "freedomLevel": "medium",
            "hardRestrictions": brief.mandatoryRules,
            "softGuidance": [],
            "validationChecklist": ["Every claim links to a source"],
        },
        "platforms": {"targets": brief.targetPlatforms},
    }
    return restore_authoritative_facts(SkillIR.model_validate(payload), brief)


class ScriptedAgents:
    def __init__(
        self,
        *,
        activation_scores: list[int],
        implementation_scores: list[int],
        require_user_input_on_first: bool = False,
    ) -> None:
        self.activation_scores = activation_scores
        self.implementation_scores = implementation_scores
        self.require_user_input_on_first = require_user_input_on_first
        self.repair_calls = 0
        self.activation_calls = 0
        self.implementation_calls = 0

    def generate(self, brief, provider_config):
        return valid_ir(), metadata("generation")

    def repair(self, **kwargs):
        self.repair_calls += 1
        result = RepairAgentResult(
            skillIR=kwargs["current_ir"].model_copy(deep=True),
            changedPaths=["skill.description"],
            resolvedIssueIds=[issue.issueId for issue in kwargs["issues"]],
        )
        result.skillIR.skill.description += f" Repair round {self.repair_calls}."
        return result, metadata("repair")

    def evaluate_activation(self, brief, ir, provider_config):
        index = min(self.activation_calls, len(self.activation_scores) - 1)
        self.activation_calls += 1
        return (
            judge(
                "activation",
                self.activation_scores[index],
                user_issue=self.require_user_input_on_first and index == 0,
            ),
            metadata("activation-evaluation"),
        )

    def evaluate_implementation(self, brief, ir, rendered_skill_md, file_paths, provider_config):
        index = min(self.implementation_calls, len(self.implementation_scores) - 1)
        self.implementation_calls += 1
        return (
            judge(
                "implementation",
                self.implementation_scores[index],
                user_issue=self.require_user_input_on_first and index == 0,
            ),
            metadata("implementation-evaluation"),
        )


def setup_run(
    tmp_path: Path,
    agents: ScriptedAgents,
    settings: Settings | None = None,
):
    from app.models import SkillDraft

    settings = settings or Settings(data_dir=tmp_path)
    storage = Storage(settings.database_path)
    draft = SkillDraft.model_validate(
        {
            **build_draft_payload(),
            "id": "draft_1",
            "createdAt": now_ms(),
            "updatedAt": now_ms(),
        }
    )
    storage.save_draft(draft)
    storage.save_provider(provider(), now_ms())
    run_id = make_id("gen")
    storage.create_generation_shell(
        generation_id=run_id,
        draft_id=draft.id,
        started_at=now_ms(),
    )
    orchestrator = QualityOrchestrator(
        settings=settings,
        storage=storage,
        agents=agents,
        policy=QualityPolicy(),
    )
    return orchestrator, storage, run_id


def test_render_failure_fails_with_render_failed_code(tmp_path: Path) -> None:
    class UnsafePathAgents(ScriptedAgents):
        def generate(self, brief, provider_config):
            ir, meta = super().generate(brief, provider_config)
            ir.contextEngineering.references = ["../escape.md"]
            return ir, meta

    agents = UnsafePathAgents(activation_scores=[4], implementation_scores=[4])
    orchestrator, storage, run_id = setup_run(tmp_path, agents)

    orchestrator.run(run_id)
    generation = storage.get_generation(run_id)

    assert generation is not None
    assert generation.status == "failed"
    assert generation.failureCode == "RENDER_FAILED"


def test_repair_receives_best_attempt_issues_after_regression(tmp_path: Path) -> None:
    class RecordingAgents(ScriptedAgents):
        def __init__(self) -> None:
            super().__init__(
                activation_scores=[4, 4, 4, 4],
                implementation_scores=[3, 2, 2, 2],
            )
            self.repair_issue_reasons: list[list[str]] = []

        def repair(self, **kwargs):
            self.repair_issue_reasons.append(
                [issue.reason for issue in kwargs["issues"]]
            )
            self.repair_calls += 1
            result = RepairAgentResult(
                skillIR=kwargs["current_ir"].model_copy(deep=True),
                changedPaths=["workflow.objective"],
                resolvedIssueIds=[issue.issueId for issue in kwargs["issues"]],
            )
            result.skillIR.workflow.objective += f" Repair round {self.repair_calls}."
            return result, metadata("repair")

        def evaluate_implementation(
            self, brief, ir, rendered_skill_md, file_paths, provider_config
        ):
            evaluation, meta = super().evaluate_implementation(
                brief, ir, rendered_skill_md, file_paths, provider_config
            )
            for issue in evaluation.issues:
                issue.reason = f"round-call-{self.implementation_calls}"
            return evaluation, meta

    agents = RecordingAgents()
    orchestrator, storage, run_id = setup_run(tmp_path, agents)

    orchestrator.run(run_id)
    generation = storage.get_generation(run_id)

    assert generation is not None
    assert generation.status == "degraded"
    assert len(agents.repair_issue_reasons) >= 2
    # Round 1 regressed below round 0, so the second repair starts from the
    # best attempt (round 0) and must receive that attempt's issues, not the
    # ones criticizing the regressed latest attempt.
    judge_reasons = [
        reason
        for reason in agents.repair_issue_reasons[1]
        if reason.startswith("round-call-")
    ]
    assert judge_reasons == ["round-call-1"]


def test_orchestrator_packages_first_strict_candidate(tmp_path: Path) -> None:
    agents = ScriptedAgents(activation_scores=[4], implementation_scores=[4])
    orchestrator, storage, run_id = setup_run(tmp_path, agents)

    orchestrator.run(run_id)
    generation = storage.get_generation(run_id)

    assert generation is not None
    assert generation.status == "succeeded"
    assert generation.currentRound == 0
    assert generation.qualityReport is not None
    assert generation.qualityReport.overallScore == 100
    assert generation.zipPath and Path(generation.zipPath).exists()
    assert agents.repair_calls == 0


def test_orchestrator_runs_at_most_three_repairs_and_selects_best_candidate(tmp_path: Path) -> None:
    agents = ScriptedAgents(
        activation_scores=[3, 2, 3, 2],
        implementation_scores=[3, 2, 3, 2],
    )
    orchestrator, storage, run_id = setup_run(tmp_path, agents)

    orchestrator.run(run_id)
    generation = storage.get_generation(run_id)
    attempts = storage.list_attempts(run_id)

    assert generation is not None
    assert generation.status == "degraded"
    assert agents.repair_calls == 3
    assert len(attempts) == 4
    assert generation.finalAttemptId == attempts[0].id
    assert generation.downloadInfo is not None
    assert "-low-score-" in generation.downloadInfo.packageName


def test_orchestrator_pauses_for_user_fact_and_resumes_same_run(tmp_path: Path) -> None:
    agents = ScriptedAgents(
        activation_scores=[3, 4],
        implementation_scores=[3, 4],
        require_user_input_on_first=True,
    )
    orchestrator, storage, run_id = setup_run(tmp_path, agents)

    orchestrator.run(run_id)
    waiting = storage.get_generation(run_id)

    assert waiting is not None
    assert waiting.status == "awaiting_user_input"
    assert waiting.userQuestions
    assert agents.repair_calls == 0

    orchestrator.resume_with_supplement(
        run_id,
        answers=[
            {
                "issueId": waiting.userQuestions[0].issueId,
                "answer": "所有结论有来源并通过负责人复核。",
            }
        ],
        skip=False,
    )
    completed = storage.get_generation(run_id)

    assert completed is not None
    assert completed.status == "succeeded"
    assert completed.id == run_id
    assert agents.repair_calls == 1
    assert storage.list_supplements(run_id)


def test_orchestrator_stops_after_two_non_improving_repairs(tmp_path: Path) -> None:
    agents = ScriptedAgents(
        activation_scores=[3, 3, 3, 3],
        implementation_scores=[3, 3, 3, 3],
    )
    orchestrator, storage, run_id = setup_run(tmp_path, agents)

    orchestrator.run(run_id)
    generation = storage.get_generation(run_id)

    assert generation is not None
    assert generation.status == "degraded"
    assert agents.repair_calls == 2
    assert len(storage.list_attempts(run_id)) == 3


def test_attempt_and_final_artifact_store_audit_hashes(tmp_path: Path) -> None:
    agents = ScriptedAgents(activation_scores=[4], implementation_scores=[4])
    orchestrator, storage, run_id = setup_run(tmp_path, agents)

    orchestrator.run(run_id)
    generation = storage.get_generation(run_id)
    attempt = storage.list_attempts(run_id)[0]

    assert generation is not None
    assert generation.normalizedBrief
    assert generation.artifactSha256
    assert generation.finalSelectionReason == "strict_quality_gate_passed"
    assert attempt.fileHashes
    assert {call.providerRole for call in attempt.agentCalls} == {
        "generation",
        "activation-evaluation",
        "implementation-evaluation",
    }
    assert storage.list_run_events(run_id)


class ConcurrentJudgeAgents(ScriptedAgents):
    def __init__(self) -> None:
        super().__init__(activation_scores=[4], implementation_scores=[4])
        self.activation_started = threading.Event()
        self.implementation_started = threading.Event()

    def evaluate_activation(self, brief, ir, provider_config):
        self.activation_started.set()
        if not self.implementation_started.wait(timeout=1):
            raise AssertionError("implementation judge did not start concurrently")
        return super().evaluate_activation(brief, ir, provider_config)

    def evaluate_implementation(self, brief, ir, rendered_skill_md, file_paths, provider_config):
        self.implementation_started.set()
        if not self.activation_started.wait(timeout=1):
            raise AssertionError("activation judge did not start concurrently")
        return super().evaluate_implementation(
            brief,
            ir,
            rendered_skill_md,
            file_paths,
            provider_config,
        )


def test_orchestrator_runs_activation_and_implementation_judges_concurrently(
    tmp_path: Path,
) -> None:
    agents = ConcurrentJudgeAgents()
    orchestrator, storage, run_id = setup_run(tmp_path, agents)

    orchestrator.run(run_id)
    generation = storage.get_generation(run_id)

    assert generation is not None
    assert generation.status == "succeeded"
    assert agents.activation_calls == 1
    assert agents.implementation_calls == 1


def test_orchestrator_reuses_implementation_when_only_description_changes(
    tmp_path: Path,
) -> None:
    agents = ScriptedAgents(
        activation_scores=[2, 4],
        implementation_scores=[4, 4],
    )
    orchestrator, storage, run_id = setup_run(tmp_path, agents)

    orchestrator.run(run_id)
    generation = storage.get_generation(run_id)
    attempts = storage.list_attempts(run_id)

    assert generation is not None
    assert generation.status == "succeeded"
    assert agents.activation_calls == 2
    assert agents.implementation_calls == 1
    assert attempts[1].implementationReusedFromAttemptId == attempts[0].id


class NoChangeRepairAgents(ScriptedAgents):
    def repair(self, **kwargs):
        self.repair_calls += 1
        return (
            RepairAgentResult(
                skillIR=kwargs["current_ir"].model_copy(deep=True),
                changedPaths=[],
                resolvedIssueIds=[],
            ),
            metadata("repair"),
        )


def test_orchestrator_reuses_both_judges_for_identical_skill_ir(
    tmp_path: Path,
) -> None:
    agents = NoChangeRepairAgents(
        activation_scores=[3],
        implementation_scores=[3],
    )
    orchestrator, storage, run_id = setup_run(tmp_path, agents)

    orchestrator.run(run_id)
    generation = storage.get_generation(run_id)
    attempts = storage.list_attempts(run_id)

    assert generation is not None
    assert generation.status == "degraded"
    assert agents.activation_calls == 1
    assert agents.implementation_calls == 1
    assert len(attempts) == 3
    assert attempts[1].activationReusedFromAttemptId == attempts[0].id
    assert attempts[1].implementationReusedFromAttemptId == attempts[0].id


class FailingPreferredProviderAgents(ScriptedAgents):
    def __init__(self) -> None:
        super().__init__(activation_scores=[4], implementation_scores=[4])
        self.generation_provider_ids: list[str] = []

    def generate(self, brief, provider_config):
        self.generation_provider_ids.append(provider_config.id)
        if provider_config.id == "provider_primary":
            raise RuntimeError("primary unavailable")
        return valid_ir(), metadata("generation", provider_config.id)


def test_orchestrator_falls_back_to_next_provider_without_using_repair_round(
    tmp_path: Path,
) -> None:
    agents = FailingPreferredProviderAgents()
    orchestrator, storage, run_id = setup_run(tmp_path, agents)
    storage.save_provider(
        provider().model_copy(
            update={"id": "provider_primary", "name": "primary"},
        ),
        now_ms() + 1,
    )
    storage.save_setting(
        "app_settings",
        AppSettings(defaultGenerateProvider="provider_primary").model_dump_json(),
    )

    orchestrator.run(run_id)
    generation = storage.get_generation(run_id)
    attempts = storage.list_attempts(run_id)
    events = storage.list_run_events(run_id)

    assert generation is not None
    assert generation.status == "succeeded"
    assert generation.currentRound == 0
    assert agents.generation_provider_ids == ["provider_primary", "provider_test"]
    assert attempts[0].agentCalls[0].providerId == "provider_test"
    assert any(event["event"] == "provider_fallback" for event in events)


class RepairFailureAgents(ScriptedAgents):
    def repair(self, **kwargs):
        self.repair_calls += 1
        raise RuntimeError("repair provider unavailable")


def test_repair_provider_failure_delivers_previous_safe_candidate(
    tmp_path: Path,
) -> None:
    agents = RepairFailureAgents(
        activation_scores=[3],
        implementation_scores=[3],
    )
    orchestrator, storage, run_id = setup_run(tmp_path, agents)

    orchestrator.run(run_id)
    generation = storage.get_generation(run_id)

    assert generation is not None
    assert generation.status == "degraded"
    assert generation.finalSelectionReason == "provider_failure_with_previous_safe_candidate"
    assert generation.downloadInfo is not None
    assert agents.repair_calls == 1


class TokenHeavyAgents(ScriptedAgents):
    def _with_usage(self, result):
        payload, call = result
        return payload, call.model_copy(update={"inputTokens": 10, "outputTokens": 10})

    def generate(self, brief, provider_config):
        return self._with_usage(super().generate(brief, provider_config))

    def evaluate_activation(self, brief, ir, provider_config):
        return self._with_usage(super().evaluate_activation(brief, ir, provider_config))

    def evaluate_implementation(self, brief, ir, rendered_skill_md, file_paths, provider_config):
        return self._with_usage(
            super().evaluate_implementation(
                brief,
                ir,
                rendered_skill_md,
                file_paths,
                provider_config,
            )
        )


def test_run_budget_stops_repairs_and_selects_checked_safe_candidate(
    tmp_path: Path,
) -> None:
    agents = TokenHeavyAgents(
        activation_scores=[3],
        implementation_scores=[3],
    )
    settings = Settings(data_dir=tmp_path, max_run_tokens=1)
    orchestrator, storage, run_id = setup_run(tmp_path, agents, settings)

    orchestrator.run(run_id)
    generation = storage.get_generation(run_id)

    assert generation is not None
    assert generation.status == "degraded"
    assert generation.finalSelectionReason == "budget_limit:max_run_tokens"
    assert agents.repair_calls == 0
    assert any(
        event["event"] == "budget_limit_reached"
        for event in storage.list_run_events(run_id)
    )


def test_user_skip_does_not_prompt_same_issue_twice(tmp_path: Path) -> None:
    agents = ScriptedAgents(
        activation_scores=[3, 3, 3],
        implementation_scores=[3, 3, 3],
        require_user_input_on_first=True,
    )
    orchestrator, storage, run_id = setup_run(tmp_path, agents)

    orchestrator.run(run_id)
    waiting = storage.get_generation(run_id)
    assert waiting is not None
    assert waiting.status == "awaiting_user_input"

    orchestrator.resume_with_supplement(run_id, answers=[], skip=True)
    completed = storage.get_generation(run_id)
    awaiting_events = [
        event
        for event in storage.list_run_events(run_id)
        if event["event"] == "awaiting_user_input"
    ]

    assert completed is not None
    assert completed.status == "degraded"
    assert len(awaiting_events) == 1
    assert storage.list_supplements(run_id)[0].skipped is True


def test_candidates_below_degraded_minimum_fail_without_zip(tmp_path: Path) -> None:
    agents = ScriptedAgents(
        activation_scores=[1, 1, 1, 1],
        implementation_scores=[1, 1, 1, 1],
    )
    orchestrator, storage, run_id = setup_run(tmp_path, agents)

    orchestrator.run(run_id)
    generation = storage.get_generation(run_id)

    assert generation is not None
    assert generation.status == "failed"
    assert generation.failureCode == "QUALITY_BELOW_MINIMUM"
    assert generation.downloadInfo is None
