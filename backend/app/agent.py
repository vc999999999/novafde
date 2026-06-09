from __future__ import annotations

from typing import Protocol

from app.models import (
    AgentKnowledge,
    ContextEngineering,
    SkillBrief,
    SkillIR,
    SkillMeta,
    SkillPlatforms,
    SkillQuality,
    SkillWorkflow,
)


class ModelProvider(Protocol):
    def generate_ir(self, brief: SkillBrief) -> SkillIR:
        ...


class DeterministicSkillIRProvider:
    """Offline provider used by the MVP when no model integration is configured."""

    def generate_ir(self, brief: SkillBrief) -> SkillIR:
        common_phrase = f" Common user phrases include: {', '.join(brief.commonPhrases[:3])}." if brief.commonPhrases else ""
        task_type = f" for {brief.taskType}" if brief.taskType else ""
        description = f"Use when the user asks to {brief.triggerIntent}{task_type}.{common_phrase}".strip()

        references: list[str] = []
        if brief.needsReferences or brief.unknownKnowledge or brief.pitfalls:
            references.append("references/domain-knowledge.md")
        scripts = ["scripts/README.md"] if brief.needsScripts else []
        assets = ["assets/template.json"] if brief.needsAssets else []

        verification = [step.validation for step in brief.workflowSteps if step.validation.strip()]
        failure_handling = [step.failureHandling for step in brief.workflowSteps if step.failureHandling.strip()]

        return SkillIR(
            skill=SkillMeta(
                name=brief.skillName,
                description=description,
                language=brief.outputLanguage,
            ),
            workflow=SkillWorkflow(
                objective=brief.workflowObjective or brief.triggerIntent,
                steps=brief.workflowSteps,
                decisionPoints=brief.antiTriggers,
                failureHandling=failure_handling,
                verification=verification,
            ),
            contextEngineering=ContextEngineering(
                filesystemAssumptions=[
                    "Load SKILL.md first, then load referenced files only when the current step needs them.",
                    brief.loadingRule or "Prefer references/ for domain knowledge and keep generated scripts user-reviewed.",
                ],
                references=references,
                scripts=scripts,
                assets=assets,
            ),
            agentKnowledge=AgentKnowledge(
                unknownKnowledge=brief.unknownKnowledge,
                pitfalls=brief.pitfalls,
                examples=brief.positiveExamples,
                counterExamples=brief.antiTriggers,
            ),
            quality=SkillQuality(
                freedomLevel=brief.freedomLevel,
                hardRestrictions=[] if not brief.allowHardLimits else ["Do not invent facts that are not present in user input or references."],
                softGuidance=[
                    "Prefer concise, workflow-specific instructions over generic AI advice.",
                    "Ask for missing critical inputs before continuing a workflow step.",
                ],
                validationChecklist=verification,
            ),
            platforms=SkillPlatforms(targets=brief.targetPlatforms),
        )
