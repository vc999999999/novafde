from pydantic_ai.models.test import TestModel

from app.agent import PydanticSkillAgents
from app.provider_runtime import PydanticAgentRuntime


def build_test_agents() -> PydanticSkillAgents:
    skill_ir = {
        "schemaVersion": "1.1",
        "skill": {
            "name": "generated-skill",
            "description": "Use when the user needs a structured evidence-backed workflow with traceable outputs.",
            "language": "en",
        },
        "workflow": {
            "objective": "Complete the requested workflow",
            "steps": [
                {
                    "id": "step_1",
                    "purpose": "Define the research scope",
                    "action": "Define the product domain, audience, and research questions.",
                    "input": "User request and supplied domain context",
                    "output": "Research scope",
                    "validation": "Research questions are explicit.",
                    "failureHandling": "Request missing facts and do not invent business information.",
                },
                {
                    "id": "step_2",
                    "purpose": "Organize evidence",
                    "action": "Classify sources, metrics, and hypotheses.",
                    "input": "Research scope and available sources",
                    "output": "Traceable evidence set",
                    "validation": "Every source has a role and provenance.",
                    "failureHandling": "Report evidence gaps.",
                },
                {
                    "id": "step_3",
                    "purpose": "Produce conclusions",
                    "action": "Create conclusions linked to the classified evidence.",
                    "input": "Traceable evidence set",
                    "output": "Validated research conclusions",
                    "validation": "Check the result against the supplied completion criteria.",
                    "failureHandling": "Request missing facts and do not invent business information.",
                }
            ],
            "decisionPoints": [],
            "failureHandling": ["Request missing facts"],
            "verification": ["Check the supplied completion criteria"],
        },
        "contextEngineering": {
            "filesystemAssumptions": ["Load referenced files only when the current step needs them."],
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
            "validationChecklist": ["Check the supplied completion criteria"],
        },
        "platforms": {"targets": []},
        "specTrace": [
            {
                "specItemId": "identity.name",
                "irPaths": ["skill.name"],
                "renderedPaths": ["product-research/SKILL.md"],
            },
            {
                "specItemId": "identity.platforms",
                "irPaths": ["platforms.targets"],
                "renderedPaths": ["product-research/SKILL.md"],
            },
            {
                "specItemId": "activation.usage",
                "irPaths": ["skill.description"],
                "renderedPaths": ["product-research/SKILL.md"],
            },
            {
                "specItemId": "activation.outcome",
                "irPaths": ["workflow.objective"],
                "renderedPaths": ["product-research/SKILL.md"],
            },
            *[
                {
                    "specItemId": f"workflow.stage.{index:02d}",
                    "irPaths": [f"workflow.steps[{index - 1}]"],
                    "renderedPaths": ["product-research/SKILL.md"],
                }
                for index in range(1, 4)
            ],
            {
                "specItemId": "special-cases.01",
                "irPaths": ["workflow.decisionPoints[0]"],
                "renderedPaths": ["product-research/SKILL.md"],
            },
            *[
                {
                    "specItemId": f"knowledge.incremental.{index:02d}",
                    "irPaths": [f"agentKnowledge.unknownKnowledge[{index - 1}]"],
                    "renderedPaths": ["product-research/references/domain-knowledge.md"],
                }
                for index in range(1, 4)
            ],
            {
                "specItemId": "pitfall.pit_1",
                "irPaths": ["agentKnowledge.pitfalls[0]"],
                "renderedPaths": ["product-research/references/domain-knowledge.md"],
            },
            *[
                {
                    "specItemId": spec_item_id,
                    "irPaths": ["quality.hardRestrictions"],
                    "renderedPaths": ["product-research/SKILL.md"],
                }
                for spec_item_id in (
                    [
                        "restriction.user.01",
                        "restriction.user.02",
                        "restriction.system.01",
                        "restriction.system.02",
                        "restriction.system.03",
                    ]
                )
            ],
            {
                "specItemId": "files.references",
                "irPaths": ["contextEngineering.references[0]"],
                "renderedPaths": ["product-research/references/domain-knowledge.md"],
            },
            {
                "specItemId": "related-skill.01",
                "irPaths": ["agentKnowledge.relatedSkills[0]"],
                "renderedPaths": ["product-research/references/domain-knowledge.md"],
            },
            {
                "specItemId": "related-skill.02",
                "irPaths": ["agentKnowledge.relatedSkills[1]"],
                "renderedPaths": ["product-research/references/domain-knowledge.md"],
            },
            {
                "specItemId": "acceptance.01",
                "irPaths": ["quality.validationChecklist"],
                "renderedPaths": ["product-research/SKILL.md"],
            },
        ],
    }
    judge = {
        "dimension": "activation",
        "summary": "passes",
        "issues": [],
        "confidence": 1,
        "requiresRepair": False,
        "requiresUserInput": False,
        "userQuestions": [],
    }
    repair = {
        "skillIR": skill_ir,
        "changedPaths": [],
        "resolvedIssueIds": [],
        "unresolvedIssues": [],
    }
    staged_outputs = [
        {
            "description": skill_ir["skill"]["description"],
            "overview": "Create evidence-backed conclusions with traceable outputs.",
            "objective": skill_ir["workflow"]["objective"],
            "steps": skill_ir["workflow"]["steps"],
            "decisionPoints": skill_ir["workflow"]["decisionPoints"],
            "failureHandling": skill_ir["workflow"]["failureHandling"],
            "verification": skill_ir["workflow"]["verification"],
            "skillHandoffs": [],
        },
        {
            "contextEngineering": skill_ir["contextEngineering"],
            "agentKnowledge": skill_ir["agentKnowledge"],
        },
        {
            "freedomLevel": skill_ir["quality"]["freedomLevel"],
            "softGuidance": skill_ir["quality"]["softGuidance"],
            "validationChecklist": [
                "每个结论都有来源，无法验证的内容明确标记为假设"
            ],
        },
        {
            "items": [
                item
                for item in skill_ir["specTrace"]
                if (
                    item["specItemId"].startswith("activation.")
                    or item["specItemId"].startswith("workflow.stage.")
                )
            ]
        },
    ]
    generation_call = 0

    def model_factory(_provider, role):
        nonlocal generation_call
        if role == "generation":
            output = staged_outputs[generation_call % len(staged_outputs)]
            generation_call += 1
            return TestModel(custom_output_args=output)
        if role == "repair":
            return TestModel(custom_output_args=repair)
        return TestModel(
            custom_output_args={
                **judge,
                "dimension": "activation" if role == "activation-evaluation" else "implementation",
                "criterionScores": [
                    {
                        "criterion": criterion,
                        "score": 4,
                        "reason": "complete",
                        "evidence": ["candidate"],
                        "suggestion": "none",
                    }
                    for criterion in (
                        [
                            "specificity",
                            "completeness",
                            "trigger-term-quality",
                            "distinctiveness-conflict-risk",
                        ]
                        if role == "activation-evaluation"
                        else [
                            "conciseness",
                            "actionability",
                            "workflow-clarity",
                            "progressive-disclosure",
                        ]
                    )
                ],
            }
        )

    return PydanticSkillAgents(PydanticAgentRuntime(model_factory=model_factory))
