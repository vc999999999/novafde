from pydantic_ai.models.test import TestModel

from app.agent import PydanticSkillAgents
from app.provider_runtime import PydanticAgentRuntime


def build_test_agents() -> PydanticSkillAgents:
    skill_ir = {
        "schemaVersion": "1.0",
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
                    "purpose": "Execute the workflow",
                    "action": "Follow the supplied process and preserve traceable evidence.",
                    "input": "User request and supplied domain context",
                    "output": "A validated workflow result",
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

    def model_factory(_provider, role):
        if role == "generation":
            return TestModel(custom_output_args=skill_ir)
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
