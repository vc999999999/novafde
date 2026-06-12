from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.models import (
    AcceptanceCriterionSpec,
    ActivationContract,
    FileContract,
    RelatedSkillSpec,
    RestrictionSpec,
    SkillBrief,
    SkillIR,
    SkillSpec,
    SkillSpecIdentity,
    SpecTraceItem,
    SupplementSpecItem,
    WorkflowStageSpec,
)


SYSTEM_BASELINE_RESTRICTIONS = [
    "不得编造缺失的用户业务事实。",
    "未通过验收条件前不得声称任务已完成。",
    "信息不足时必须报告缺口或请求用户补充。",
]


@dataclass(frozen=True)
class RequiredSpecTraceItem:
    specItemId: str
    irPathPrefix: str
    expectedValue: Any = None
    requiresDistinctPath: bool = False
    alternateIrPathPrefixes: tuple[str, ...] = ()


def required_spec_trace_items(spec: SkillSpec) -> list[RequiredSpecTraceItem]:
    items = [
        RequiredSpecTraceItem("identity.name", "skill.name", spec.identity.skillName),
        RequiredSpecTraceItem(
            "identity.platforms",
            "platforms.targets",
            spec.identity.targetPlatforms,
        ),
        RequiredSpecTraceItem("activation.usage", "skill.description"),
        RequiredSpecTraceItem("activation.outcome", "workflow.objective"),
    ]
    items.extend(
        RequiredSpecTraceItem(
            stage.id,
            "workflow.steps",
            requiresDistinctPath=True,
        )
        for stage in spec.workflowStages
        if stage.required
    )
    if spec.specialCases.strip():
        items.append(
            RequiredSpecTraceItem(
                "special-cases.01",
                "workflow.decisionPoints",
                alternateIrPathPrefixes=("workflow.failureHandling",),
            )
        )
    items.extend(
        RequiredSpecTraceItem(
            f"knowledge.incremental.{index:02d}",
            "agentKnowledge.unknownKnowledge",
            statement,
        )
        for index, statement in enumerate(spec.incrementalKnowledge, start=1)
    )
    items.extend(
        RequiredSpecTraceItem(
            supplement.id,
            "agentKnowledge.unknownKnowledge",
            supplement.statement,
        )
        for supplement in spec.userSupplements
    )
    items.extend(
        RequiredSpecTraceItem(
            f"pitfall.{pitfall.id}" if pitfall.id else f"pitfall.{index:02d}",
            "agentKnowledge.pitfalls",
        )
        for index, pitfall in enumerate(spec.pitfalls, start=1)
    )
    items.extend(
        RequiredSpecTraceItem(
            restriction.id,
            "quality.hardRestrictions",
            restriction.statement,
        )
        for restriction in spec.restrictionItems
    )
    if spec.fileContract.needsReferences:
        items.append(
            RequiredSpecTraceItem(
                "files.references",
                "contextEngineering.references",
                alternateIrPathPrefixes=(
                    "contextEngineering.referenceFiles",
                ),
            )
        )
    if spec.fileContract.needsScripts:
        items.append(
            RequiredSpecTraceItem(
                "files.scripts",
                "contextEngineering.scripts",
            )
        )
    if spec.fileContract.needsAssets:
        items.append(
            RequiredSpecTraceItem(
                "files.assets",
                "contextEngineering.assets",
            )
        )
    items.extend(
        RequiredSpecTraceItem(
            f"related-skill.{index:02d}",
            "agentKnowledge.relatedSkills",
            related.name,
        )
        for index, related in enumerate(spec.relatedSkills, start=1)
    )
    items.extend(
        RequiredSpecTraceItem(
            criterion.id,
            "quality.validationChecklist",
            criterion.statement,
        )
        for criterion in spec.acceptanceCriteria
        if criterion.required
    )
    return items


def build_skill_spec(
    brief: SkillBrief,
    *,
    revision: int,
    source_issue_ids: list[str] | None = None,
    supplements: list[SupplementSpecItem] | None = None,
) -> SkillSpec:
    user_restrictions = [
        RestrictionSpec(
            id=f"restriction.user.{index:02d}",
            statement=statement,
            source="user",
        )
        for index, statement in enumerate(brief.mandatoryRules, start=1)
    ]
    system_restrictions = [
        RestrictionSpec(
            id=f"restriction.system.{index:02d}",
            statement=statement,
            source="system",
        )
        for index, statement in enumerate(SYSTEM_BASELINE_RESTRICTIONS, start=1)
    ]
    completion = brief.completionCriteria.strip()
    acceptance_statement = (
        completion
        if completion
        else f"交付结果必须实现目标：{brief.desiredOutcome}"
    )
    acceptance_source = "user" if completion else "derived"
    return SkillSpec(
        revision=revision,
        identity=SkillSpecIdentity(
            skillName=brief.skillName,
            displayName=brief.displayName,
            targetPlatforms=list(brief.targetPlatforms),
            outputLanguage=brief.outputLanguage,
        ),
        activationContract=ActivationContract(
            usage=brief.usage,
            desiredOutcome=brief.desiredOutcome,
        ),
        workflowStages=[
            WorkflowStageSpec(
                id=f"workflow.stage.{index:02d}",
                statement=stage,
            )
            for index, stage in enumerate(brief.roughProcess, start=1)
        ],
        completionCriteria=completion,
        specialCases=brief.specialCases,
        incrementalKnowledge=list(brief.professionalInformation),
        pitfalls=[item.model_copy(deep=True) for item in brief.pitfalls],
        hardRestrictions=[
            *brief.mandatoryRules,
            *SYSTEM_BASELINE_RESTRICTIONS,
        ],
        restrictionItems=[*user_restrictions, *system_restrictions],
        fileContract=FileContract(
            needsReferences=brief.needsReferences,
            needsScripts=brief.needsScripts,
            needsAssets=brief.needsAssets,
        ),
        relatedSkills=[
            RelatedSkillSpec(name=name)
            for name in brief.relatedSkills
        ],
        acceptanceCriteria=[
            AcceptanceCriterionSpec(
                id="acceptance.01",
                statement=acceptance_statement,
                source=acceptance_source,
            )
        ],
        userSupplements=[
            item.model_copy(deep=True) for item in supplements or []
        ],
        sourceIssueIds=list(source_issue_ids or []),
    )


_PACKAGE_DIRS = {"references", "scripts", "assets", "install"}


def _normalize_rendered_path(path: str, skill_name: str) -> str:
    cleaned = path.strip().lstrip("/")
    while cleaned.startswith("./"):
        cleaned = cleaned[2:]
    segments = [segment for segment in cleaned.split("/") if segment]
    if not segments or segments[0] == skill_name:
        return "/".join(segments) or cleaned
    if segments[0] == "SKILL.md" or segments[0] in _PACKAGE_DIRS:
        return "/".join([skill_name, *segments])
    if len(segments) > 1 and (
        segments[1] == "SKILL.md" or segments[1] in _PACKAGE_DIRS
    ):
        return "/".join([skill_name, *segments[1:]])
    return "/".join(segments)


def enforce_spec_contract(ir: SkillIR, spec: SkillSpec) -> SkillIR:
    """Deterministically repair spec-trace facts no agent should be trusted with.

    Rendered paths are decided by the renderer, not the model, so wrong or
    missing skill-directory prefixes are normalized instead of failing the
    candidate. User supplement statements are appended verbatim to the IR and
    given a trace entry when the agent omitted them, because supplements are
    authoritative user facts that must survive every candidate.
    """
    enforced = ir.model_copy(deep=True)
    skill_name = enforced.skill.name
    for trace in enforced.specTrace:
        trace.renderedPaths = [
            _normalize_rendered_path(path, skill_name)
            for path in trace.renderedPaths
        ]
    for supplement in spec.userSupplements:
        if supplement.statement not in enforced.agentKnowledge.unknownKnowledge:
            enforced.agentKnowledge.unknownKnowledge.append(supplement.statement)
    traced_ids = {trace.specItemId for trace in enforced.specTrace}
    for supplement in spec.userSupplements:
        if supplement.id in traced_ids:
            continue
        index = enforced.agentKnowledge.unknownKnowledge.index(
            supplement.statement
        )
        enforced.specTrace.append(
            SpecTraceItem(
                specItemId=supplement.id,
                irPaths=[f"agentKnowledge.unknownKnowledge[{index}]"],
                renderedPaths=[f"{skill_name}/SKILL.md"],
            )
        )
    return enforced
