from app.agent import restore_authoritative_facts
from app.models import KnowledgePitfall, SkillBrief, SkillIR


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
    # No fallback reference is forced when the model authored its own files.
    assert ir.contextEngineering.references == []
    # User mandatory rules stay verbatim and first; model additions follow.
    assert ir.quality.hardRestrictions == [
        "不得编造来源",
        "每个结论必须附带来源链接",
    ]
    assert ir.agentKnowledge.relatedSkills == brief.relatedSkills
