from __future__ import annotations

import json
from typing import Literal, Protocol

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
        rendered_skill_md: str = "",
        rendered_files: list[str] | None = None,
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
        rendered_skill_md: str = "",
        rendered_files: list[str] | None = None,
    ) -> tuple[RepairAgentResult, AgentCallMetadata]:
        payload = {
            "round": round_number,
            "brief": brief.model_dump(mode="json"),
            "originalSkillIR": original_ir.model_dump(mode="json"),
            "currentSkillIR": current_ir.model_dump(mode="json"),
            "bestSkillIR": best_ir.model_dump(mode="json"),
            "renderedSkillMd": rendered_skill_md,
            "renderedFiles": rendered_files or [],
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
        return _coerce_dimension(evaluation, "activation"), metadata

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
        return _coerce_dimension(evaluation, "implementation"), metadata


def _coerce_dimension(
    evaluation: JudgeEvaluation,
    dimension: Literal["activation", "implementation"],
) -> JudgeEvaluation:
    """Force the dimension the caller requested and re-run model validation.

    Plain assignment would skip the criteria/dimension consistency check, so a
    judge that self-declared the wrong dimension with the wrong criteria set
    would slip through; re-validation turns that into a provider failure.
    """
    if evaluation.dimension == dimension:
        return evaluation
    payload = evaluation.model_dump(mode="json")
    payload["dimension"] = dimension
    return JudgeEvaluation.model_validate(payload)


def restore_authoritative_facts(ir: SkillIR, brief: SkillBrief) -> SkillIR:
    """Enforce identity facts and guarantee user-supplied facts survive generation.

    The model is allowed to rephrase, reorganize, and expand user knowledge.
    Identity fields stay authoritative, every mandatory rule stays verbatim,
    and fields the model dropped entirely fall back to the original brief so
    user facts are never silently lost. Coverage beyond this deterministic
    floor is enforced by the validator instead of verbatim overwrites.
    """
    restored = ir.model_copy(deep=True)
    restored.skill.name = brief.skillName
    restored.skill.language = brief.outputLanguage
    restored.platforms.targets = list(brief.targetPlatforms)
    model_rules = [
        rule
        for rule in restored.quality.hardRestrictions
        if rule not in brief.mandatoryRules
    ]
    restored.quality.hardRestrictions = [*brief.mandatoryRules, *model_rules]
    if not restored.workflow.objective.strip():
        restored.workflow.objective = brief.desiredOutcome
    if not restored.agentKnowledge.unknownKnowledge and brief.professionalInformation:
        restored.agentKnowledge.unknownKnowledge = list(brief.professionalInformation)
    if not restored.agentKnowledge.pitfalls and brief.pitfalls:
        restored.agentKnowledge.pitfalls = [item.model_copy(deep=True) for item in brief.pitfalls]
    missing_related = [
        skill
        for skill in brief.relatedSkills
        if skill not in restored.agentKnowledge.relatedSkills
    ]
    restored.agentKnowledge.relatedSkills = [
        *restored.agentKnowledge.relatedSkills,
        *missing_related,
    ]
    if not restored.agentKnowledge.supplementalContext.strip():
        restored.agentKnowledge.supplementalContext = brief.supplementalContext
    if brief.specialCases and not restored.workflow.decisionPoints:
        restored.workflow.decisionPoints.append(brief.specialCases)
    authored_paths = {item.path for item in restored.contextEngineering.referenceFiles}
    has_fallback_reference = any(
        path not in authored_paths for path in restored.contextEngineering.references
    )
    needs_references = brief.needsReferences or bool(
        brief.professionalInformation
        or brief.mandatoryRules
        or brief.pitfalls
        or brief.relatedSkills
        or brief.supplementalContext
    )
    # unknownKnowledge and supplementalContext reach the rendered package only
    # through the fallback digest file; authored referenceFiles carry their own
    # content and give no guarantee these fields land anywhere.
    needs_digest = bool(
        restored.agentKnowledge.unknownKnowledge
        or restored.agentKnowledge.supplementalContext.strip()
    ) or (needs_references and not authored_paths)
    digest_path = "references/domain-knowledge.md"
    if (
        needs_digest
        and not has_fallback_reference
        and digest_path not in authored_paths
        and digest_path not in restored.contextEngineering.references
    ):
        restored.contextEngineering.references.append(digest_path)
    return restored
