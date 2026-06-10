from __future__ import annotations

import json
from typing import Protocol

from app.models import (
    AgentCallMetadata,
    JudgeEvaluation,
    ModelProviderConfig,
    QualityIssue,
    RepairAgentResult,
    SkillBrief,
    SkillIR,
)
from app.prompts import (
    ACTIVATION_INSTRUCTIONS,
    ACTIVATION_PROMPT_VERSION,
    GENERATION_INSTRUCTIONS,
    GENERATION_PROMPT_VERSION,
    IMPLEMENTATION_INSTRUCTIONS,
    IMPLEMENTATION_PROMPT_VERSION,
    REPAIR_INSTRUCTIONS,
    REPAIR_PROMPT_VERSION,
)
from app.provider_runtime import PydanticAgentRuntime


class SkillAgentRuntime(Protocol):
    def generate(
        self,
        brief: SkillBrief,
        provider: ModelProviderConfig,
    ) -> tuple[SkillIR, AgentCallMetadata]:
        ...

    def repair(
        self,
        *,
        brief: SkillBrief,
        original_ir: SkillIR,
        current_ir: SkillIR,
        best_ir: SkillIR,
        issues: list[QualityIssue],
        allowed_paths: list[str],
        locked_paths: list[str],
        round_number: int,
        provider: ModelProviderConfig,
    ) -> tuple[RepairAgentResult, AgentCallMetadata]:
        ...

    def evaluate_activation(
        self,
        brief: SkillBrief,
        ir: SkillIR,
        provider: ModelProviderConfig,
    ) -> tuple[JudgeEvaluation, AgentCallMetadata]:
        ...

    def evaluate_implementation(
        self,
        brief: SkillBrief,
        ir: SkillIR,
        rendered_skill_md: str,
        file_paths: list[str],
        provider: ModelProviderConfig,
    ) -> tuple[JudgeEvaluation, AgentCallMetadata]:
        ...


class PydanticSkillAgents:
    def __init__(self, runtime: PydanticAgentRuntime | None = None) -> None:
        self.runtime = runtime or PydanticAgentRuntime()

    def generate(
        self,
        brief: SkillBrief,
        provider: ModelProviderConfig,
    ) -> tuple[SkillIR, AgentCallMetadata]:
        ir, metadata = self.runtime.run_structured(
            provider=provider,
            role="generation",
            instructions=GENERATION_INSTRUCTIONS,
            prompt=f"Create a SkillIR from this SkillBrief:\n{brief.model_dump_json(indent=2)}",
            output_type=SkillIR,
            prompt_version=GENERATION_PROMPT_VERSION,
        )
        return restore_authoritative_facts(ir, brief), metadata

    def repair(
        self,
        *,
        brief: SkillBrief,
        original_ir: SkillIR,
        current_ir: SkillIR,
        best_ir: SkillIR,
        issues: list[QualityIssue],
        allowed_paths: list[str],
        locked_paths: list[str],
        round_number: int,
        provider: ModelProviderConfig,
    ) -> tuple[RepairAgentResult, AgentCallMetadata]:
        payload = {
            "round": round_number,
            "brief": brief.model_dump(mode="json"),
            "originalSkillIR": original_ir.model_dump(mode="json"),
            "currentSkillIR": current_ir.model_dump(mode="json"),
            "bestSkillIR": best_ir.model_dump(mode="json"),
            "issues": [issue.model_dump(mode="json") for issue in issues],
            "allowedPaths": allowed_paths,
            "lockedPaths": locked_paths,
        }
        result, metadata = self.runtime.run_structured(
            provider=provider,
            role="repair",
            instructions=REPAIR_INSTRUCTIONS,
            prompt=json.dumps(payload, ensure_ascii=False, indent=2),
            output_type=RepairAgentResult,
            prompt_version=REPAIR_PROMPT_VERSION,
        )
        result.skillIR = restore_authoritative_facts(result.skillIR, brief)
        return result, metadata

    def evaluate_activation(
        self,
        brief: SkillBrief,
        ir: SkillIR,
        provider: ModelProviderConfig,
    ) -> tuple[JudgeEvaluation, AgentCallMetadata]:
        payload = {
            "skillName": ir.skill.name,
            "description": ir.skill.description,
            "usage": brief.usage,
            "desiredOutcome": brief.desiredOutcome,
            "relatedSkills": brief.relatedSkills,
        }
        evaluation, metadata = self.runtime.run_structured(
            provider=provider,
            role="activation-evaluation",
            instructions=ACTIVATION_INSTRUCTIONS,
            prompt=json.dumps(payload, ensure_ascii=False, indent=2),
            output_type=JudgeEvaluation,
            prompt_version=ACTIVATION_PROMPT_VERSION,
        )
        evaluation.dimension = "activation"
        return evaluation, metadata

    def evaluate_implementation(
        self,
        brief: SkillBrief,
        ir: SkillIR,
        rendered_skill_md: str,
        file_paths: list[str],
        provider: ModelProviderConfig,
    ) -> tuple[JudgeEvaluation, AgentCallMetadata]:
        payload = {
            "brief": brief.model_dump(mode="json"),
            "skillIR": ir.model_dump(mode="json"),
            "renderedSkillMd": rendered_skill_md,
            "filePaths": file_paths,
        }
        evaluation, metadata = self.runtime.run_structured(
            provider=provider,
            role="implementation-evaluation",
            instructions=IMPLEMENTATION_INSTRUCTIONS,
            prompt=json.dumps(payload, ensure_ascii=False, indent=2),
            output_type=JudgeEvaluation,
            prompt_version=IMPLEMENTATION_PROMPT_VERSION,
        )
        evaluation.dimension = "implementation"
        return evaluation, metadata


def restore_authoritative_facts(ir: SkillIR, brief: SkillBrief) -> SkillIR:
    restored = ir.model_copy(deep=True)
    restored.skill.name = brief.skillName
    restored.skill.language = brief.outputLanguage
    restored.workflow.objective = brief.desiredOutcome
    restored.agentKnowledge.unknownKnowledge = list(brief.professionalInformation)
    restored.agentKnowledge.pitfalls = [item.model_copy(deep=True) for item in brief.pitfalls]
    restored.agentKnowledge.relatedSkills = list(brief.relatedSkills)
    restored.agentKnowledge.supplementalContext = brief.supplementalContext
    restored.quality.hardRestrictions = list(brief.mandatoryRules)
    restored.platforms.targets = list(brief.targetPlatforms)
    if brief.specialCases and brief.specialCases not in restored.workflow.decisionPoints:
        restored.workflow.decisionPoints.append(brief.specialCases)
    restored.contextEngineering.references = (
        ["references/domain-knowledge.md"]
        if brief.needsReferences
        else []
    )
    restored.contextEngineering.scripts = (
        ["scripts/README.md"]
        if brief.needsScripts
        else []
    )
    restored.contextEngineering.assets = (
        ["assets/template.json"]
        if brief.needsAssets
        else []
    )
    return restored
