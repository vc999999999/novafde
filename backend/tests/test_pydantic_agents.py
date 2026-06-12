import pytest
from pydantic_ai.models.test import TestModel

from app.agent import PydanticSkillAgents
from app.creator_skill import load_creator_skill
from app.models import (
    JudgeEvaluation,
    KnowledgePitfall,
    ModelProviderConfig,
    RepairAgentResult,
    SkillBrief,
    SkillIR,
)
from app.provider_runtime import PydanticAgentRuntime
from app.spec_builder import build_skill_spec


def build_brief() -> SkillBrief:
    return SkillBrief(
        skillName="product-research",
        displayName="Product Research",
        usage="当产品团队需要竞品调研时使用",
        desiredOutcome="形成可验证的研究结论",
        roughProcess=["整理证据"],
        completionCriteria="每个结论都有来源",
        professionalInformation=["区分事实、推断和假设"],
        mandatoryRules=["不得编造来源"],
        pitfalls=[
            KnowledgePitfall(
                id="pit_1",
                description="把营销话术当成事实",
                goodExample="标记来源",
                badExample="直接写成结论",
            )
        ],
        relatedSkills=["web-research"],
        supplementalContext="表达保持简洁。",
        targetPlatforms=["codex"],
    )


def build_provider() -> ModelProviderConfig:
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


def generated_ir_payload() -> dict:
    return {
        "schemaVersion": "1.0",
        "skill": {
            "name": "model-overwrite",
            "description": "Use when the user needs a product research workflow.",
            "language": "en",
        },
        "workflow": {
            "objective": "model overwrite",
            "steps": [
                {
                    "id": "step_1",
                    "purpose": "Collect evidence",
                    "action": "Collect and classify sources",
                    "input": "User scope",
                    "output": "Evidence set",
                    "validation": "Every claim has a source",
                    "failureHandling": "Request missing sources",
                }
            ],
            "decisionPoints": [],
            "failureHandling": ["Request missing sources"],
            "verification": ["Every claim has a source"],
        },
        "contextEngineering": {
            "filesystemAssumptions": [],
            "references": [],
            "scripts": [],
            "assets": [],
        },
        "agentKnowledge": {
            "unknownKnowledge": [],
            "pitfalls": [],
            "examples": [],
            "counterExamples": [],
            "relatedSkills": [],
            "supplementalContext": "",
        },
        "quality": {
            "freedomLevel": "medium",
            "hardRestrictions": [],
            "softGuidance": [],
            "validationChecklist": [],
        },
        "platforms": {"targets": []},
    }


def test_generation_agent_returns_typed_ir_and_restores_authoritative_facts() -> None:
    runtime = PydanticAgentRuntime(
        model_factory=lambda _provider, _role: TestModel(
            custom_output_args=generated_ir_payload()
        )
    )
    agents = PydanticSkillAgents(runtime)
    brief = build_brief()
    spec = build_skill_spec(brief, revision=1)

    ir, metadata = agents.generate(brief, spec, build_provider())

    assert isinstance(ir, SkillIR)
    assert ir.skill.name == brief.skillName
    assert ir.skill.language == brief.outputLanguage
    # Model-authored objective is preserved; dropped user facts are restored.
    assert ir.workflow.objective == "model overwrite"
    assert ir.agentKnowledge.unknownKnowledge == brief.professionalInformation
    assert ir.quality.hardRestrictions == spec.hardRestrictions
    assert ir.platforms.targets == brief.targetPlatforms
    assert metadata.providerId == "provider_test"
    assert metadata.promptVersion == "generation-v3.3-sdd"


def test_agent_metadata_estimates_cost_from_provider_token_rates() -> None:
    runtime = PydanticAgentRuntime(
        model_factory=lambda _provider, _role: TestModel(
            custom_output_args=generated_ir_payload()
        )
    )
    agents = PydanticSkillAgents(runtime)
    provider = build_provider().model_copy(
        update={
            "inputPricePerMillionTokens": 2.0,
            "outputPricePerMillionTokens": 8.0,
        }
    )

    brief = build_brief()
    _ir, metadata = agents.generate(
        brief,
        build_skill_spec(brief, revision=1),
        provider,
    )

    expected = round(
        (
            metadata.inputTokens * provider.inputPricePerMillionTokens
            + metadata.outputTokens * provider.outputPricePerMillionTokens
        )
        / 1_000_000,
        8,
    )
    assert metadata.inputTokens + metadata.outputTokens > 0
    assert metadata.estimatedCostUsd == expected


def test_generation_agent_propagates_model_failure_without_static_fallback() -> None:
    def fail_factory(_provider: ModelProviderConfig, _role: str):
        raise RuntimeError("provider unavailable")

    agents = PydanticSkillAgents(PydanticAgentRuntime(model_factory=fail_factory))

    with pytest.raises(RuntimeError, match="provider unavailable"):
        brief = build_brief()
        agents.generate(
            brief,
            build_skill_spec(brief, revision=1),
            build_provider(),
        )


def test_repair_agent_preserves_locked_user_facts() -> None:
    payload = {
        "skillIR": generated_ir_payload(),
        "changedPaths": ["skill.description"],
        "resolvedIssueIds": ["activation-specificity"],
        "unresolvedIssues": [],
    }
    runtime = PydanticAgentRuntime(
        model_factory=lambda _provider, _role: TestModel(custom_output_args=payload)
    )
    agents = PydanticSkillAgents(runtime)
    brief = build_brief()
    spec = build_skill_spec(brief, revision=1)
    current = SkillIR.model_validate(generated_ir_payload())

    result, _metadata = agents.repair(
        brief=brief,
        spec=spec,
        original_ir=current,
        current_ir=current,
        best_ir=current,
        issues=[],
        allowed_paths=["skill.description"],
        locked_paths=["quality.hardRestrictions", "platforms.targets"],
        round_number=1,
        provider=build_provider(),
    )

    assert isinstance(result, RepairAgentResult)
    assert result.skillIR.quality.hardRestrictions == spec.hardRestrictions
    assert result.skillIR.platforms.targets == brief.targetPlatforms
    assert result.changedPaths == ["skill.description"]


def test_model_added_hard_restrictions_are_demoted_to_soft_guidance() -> None:
    payload = generated_ir_payload()
    payload["quality"]["hardRestrictions"] = [
        "不得编造来源",
        "模型自行增加的业务限制",
    ]
    runtime = PydanticAgentRuntime(
        model_factory=lambda _provider, _role: TestModel(custom_output_args=payload)
    )
    brief = build_brief()
    spec = build_skill_spec(brief, revision=1)

    ir, _metadata = PydanticSkillAgents(runtime).generate(
        brief,
        spec,
        build_provider(),
    )

    assert ir.quality.hardRestrictions == spec.hardRestrictions
    assert "模型自行增加的业务限制" in ir.quality.softGuidance


def test_versioned_creator_skill_snapshot_has_matching_sha256() -> None:
    bundle = load_creator_skill()

    assert bundle.version == "1.1.0"
    assert bundle.sourceUrl.startswith("https://github.com/anthropics/skills/")
    assert bundle.sha256
    assert "Progressive disclosure" in bundle.content


def test_judge_agent_recalculates_dimension_score_from_criterion_scores() -> None:
    judge_payload = {
        "dimension": "activation",
        "criterionScores": [
            {
                "criterion": name,
                "score": 3,
                "reason": "mostly clear",
                "evidence": ["description"],
                "suggestion": "make it more specific",
            }
            for name in [
                "specificity",
                "completeness",
                "trigger-term-quality",
                "distinctiveness-conflict-risk",
            ]
        ],
        "dimensionScore": 100,
        "summary": "good",
        "issues": [],
        "confidence": 0.9,
        "requiresRepair": True,
        "requiresUserInput": False,
        "userQuestions": [],
    }
    runtime = PydanticAgentRuntime(
        model_factory=lambda _provider, _role: TestModel(custom_output_args=judge_payload)
    )
    agents = PydanticSkillAgents(runtime)

    brief = build_brief()
    evaluation, _metadata = agents.evaluate_activation(
        brief,
        build_skill_spec(brief, revision=1),
        SkillIR.model_validate(generated_ir_payload()),
        build_provider(),
    )

    assert isinstance(evaluation, JudgeEvaluation)
    assert evaluation.dimensionScore == 75
