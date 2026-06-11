import pytest
from pydantic import ValidationError

from app.agent import _coerce_dimension, restore_authoritative_facts
from app.models import (
    CriterionScore,
    JudgeEvaluation,
    KnowledgePitfall,
    SkillBrief,
    SkillIR,
)


def build_brief() -> SkillBrief:
    pitfall = KnowledgePitfall(
        id="pit_1",
        description="把营销话术当成事实",
        goodExample="标记来源",
        badExample="直接写成结论",
    )
    return SkillBrief(
        skillName="product-research",
        displayName="Product Research",
        usage="当产品团队需要竞品调研时使用",
        desiredOutcome="形成可验证的研究结论",
        roughProcess=["整理证据"],
        completionCriteria="每个结论都有来源",
        professionalInformation=["区分事实、推断和假设"],
        mandatoryRules=["不得编造来源"],
        pitfalls=[pitfall],
        relatedSkills=["web-research"],
        supplementalContext="表达保持简洁。",
        targetPlatforms=["codex"],
    )


def empty_ir_payload() -> dict:
    return {
        "schemaVersion": "1.0",
        "skill": {
            "name": "model-renamed",
            "description": "Use when the user needs a product research workflow.",
            "language": "en",
        },
        "workflow": {
            "objective": "",
            "steps": [],
            "decisionPoints": [],
            "failureHandling": [],
            "verification": [],
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


def test_restores_dropped_user_facts_and_identity_fields() -> None:
    brief = build_brief()

    ir = restore_authoritative_facts(SkillIR.model_validate(empty_ir_payload()), brief)

    assert ir.skill.name == brief.skillName
    assert ir.skill.language == brief.outputLanguage
    assert ir.platforms.targets == brief.targetPlatforms
    assert ir.workflow.objective == brief.desiredOutcome
    assert ir.agentKnowledge.unknownKnowledge == brief.professionalInformation
    assert ir.agentKnowledge.pitfalls == brief.pitfalls
    assert ir.quality.hardRestrictions == brief.mandatoryRules
    assert ir.agentKnowledge.relatedSkills == brief.relatedSkills
    assert ir.agentKnowledge.supplementalContext == brief.supplementalContext
    # User supplied knowledge so the package must contain a reference file.
    assert ir.contextEngineering.references == ["references/domain-knowledge.md"]


def test_preserves_model_refinements_while_keeping_mandatory_rules_verbatim() -> None:
    brief = build_brief()
    payload = empty_ir_payload()
    payload["workflow"]["objective"] = "交付带证据链的竞品研究报告"
    payload["agentKnowledge"]["unknownKnowledge"] = ["事实、推断、假设三层分级标注法"]
    payload["agentKnowledge"]["pitfalls"] = [
        {
            "id": "pit_1",
            "description": "引用营销话术却不标注来源类型",
            "goodExample": "结论旁标记「来源：厂商宣传」",
            "badExample": "把宣传语直接写成事实结论",
        }
    ]
    payload["quality"]["hardRestrictions"] = ["每个结论必须附带来源链接"]
    payload["contextEngineering"]["referenceFiles"] = [
        {
            "path": "references/research-method.md",
            "purpose": "需要执行证据分级时",
            "content": "# 证据分级\n\n详细方法……",
        }
    ]

    ir = restore_authoritative_facts(SkillIR.model_validate(payload), brief)

    # Model refinements survive.
    assert ir.workflow.objective == "交付带证据链的竞品研究报告"
    assert ir.agentKnowledge.unknownKnowledge == ["事实、推断、假设三层分级标注法"]
    assert ir.agentKnowledge.pitfalls[0].description == "引用营销话术却不标注来源类型"
    assert ir.contextEngineering.referenceFiles[0].path == "references/research-method.md"
    # Authored files keep their own content, but unknownKnowledge and
    # supplementalContext only land on disk through the fallback digest, so
    # the digest must still be added next to authored files.
    assert ir.contextEngineering.references == ["references/domain-knowledge.md"]
    # User mandatory rules stay verbatim and first; model additions follow.
    assert ir.quality.hardRestrictions == [
        "不得编造来源",
        "每个结论必须附带来源链接",
    ]
    assert ir.agentKnowledge.relatedSkills == brief.relatedSkills


def test_authored_domain_knowledge_file_counts_as_digest() -> None:
    brief = build_brief()
    payload = empty_ir_payload()
    payload["contextEngineering"]["referenceFiles"] = [
        {
            "path": "references/domain-knowledge.md",
            "purpose": "需要领域知识时",
            "content": "# 领域知识\n\n模型整理的内容。",
        }
    ]

    ir = restore_authoritative_facts(SkillIR.model_validate(payload), brief)

    # The model authored the digest path itself, so no duplicate is appended.
    assert ir.contextEngineering.references == []


_ACTIVATION_CRITERIA = [
    "specificity",
    "completeness",
    "trigger-term-quality",
    "distinctiveness-conflict-risk",
]
_IMPLEMENTATION_CRITERIA = [
    "conciseness",
    "actionability",
    "workflow-clarity",
    "progressive-disclosure",
]


def make_evaluation(dimension: str) -> JudgeEvaluation:
    criteria = (
        _ACTIVATION_CRITERIA if dimension == "activation" else _IMPLEMENTATION_CRITERIA
    )
    return JudgeEvaluation(
        dimension=dimension,
        criterionScores=[
            CriterionScore(criterion=name, score=4, reason="reason", suggestion="none")
            for name in criteria
        ],
        summary="summary",
    )


def test_coerce_dimension_returns_matching_evaluation_unchanged() -> None:
    evaluation = make_evaluation("activation")

    assert _coerce_dimension(evaluation, "activation") is evaluation


def test_coerce_dimension_rejects_wrong_criteria_set() -> None:
    # A judge that self-declared the other dimension with that dimension's
    # criteria must fail re-validation instead of slipping through.
    evaluation = make_evaluation("implementation")

    with pytest.raises(ValidationError):
        _coerce_dimension(evaluation, "activation")
