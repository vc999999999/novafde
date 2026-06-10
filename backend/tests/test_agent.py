from app.agent import restore_authoritative_facts
from app.models import KnowledgePitfall, SkillBrief, SkillIR


def test_llm_ir_parser_restores_authoritative_user_business_facts() -> None:
    pitfall = KnowledgePitfall(
        id="pit_1",
        description="把营销话术当成事实",
        goodExample="标记来源",
        badExample="直接写成结论",
    )
    brief = SkillBrief(
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
    raw_ir = {
            "schemaVersion": "1.0",
            "skill": {
                "name": "product-research",
                "description": "Use when the user needs a product research workflow.",
                "language": "en",
            },
            "workflow": {
                "objective": "模型擅自改写的目标",
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

    ir = restore_authoritative_facts(SkillIR.model_validate(raw_ir), brief)

    assert ir.workflow.objective == brief.desiredOutcome
    assert ir.agentKnowledge.unknownKnowledge == brief.professionalInformation
    assert ir.agentKnowledge.pitfalls == brief.pitfalls
    assert ir.quality.hardRestrictions == brief.mandatoryRules
    assert ir.agentKnowledge.relatedSkills == brief.relatedSkills
    assert ir.agentKnowledge.supplementalContext == brief.supplementalContext
