from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.models import (
    AcceptanceCriterionSpec,
    ActivationContract,
    FileContract,
    RelatedSkillSpec,
    RestrictionSpec,
    SpecialCaseSpec,
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

DERIVED_WORKFLOW_STAGES_ZH = [
    "确认任务输入、适用约束和成功目标",
    "执行请求并形成符合目标的交付结果",
    "依据目标结果检查、修正并完成交付物",
]
DERIVED_WORKFLOW_STAGES_EN = [
    "Confirm the task inputs, applicable constraints, and success target",
    "Execute the requested work and produce the intended deliverable",
    "Validate, refine, and complete the deliverable against the target outcome",
]
DERIVED_SPECIAL_CASES_ZH = [
    "必要输入不足时，先列出缺口并请求补充，不得编造业务事实。",
    "信息无法验证时，明确标记不确定性并说明验证方式。",
    "请求涉及不安全或越权操作时，停止该操作并提供安全替代方案。",
]
DERIVED_SPECIAL_CASES_EN = [
    "When required inputs are missing, list the gaps and request them instead of inventing business facts.",
    "When information cannot be verified, label the uncertainty and explain how to validate it.",
    "When a request requires unsafe or unauthorized action, stop that action and provide a safe alternative.",
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
    items.extend(
        RequiredSpecTraceItem(
            item.id,
            "workflow.decisionPoints",
            item.statement,
            alternateIrPathPrefixes=("workflow.failureHandling",),
        )
        for item in _special_case_items(spec)
        if item.statement.strip()
    )
    if not spec.specialCaseItems and spec.specialCases.strip():
        items.append(
            RequiredSpecTraceItem(
                "special-cases.01",
                "workflow.decisionPoints",
                spec.specialCases,
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


def _special_case_items(spec: SkillSpec) -> list[Any]:
    return list(spec.specialCaseItems)


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
    workflow_statements = (
        list(brief.roughProcess)
        if brief.roughProcess
        else list(
            DERIVED_WORKFLOW_STAGES_ZH
            if brief.outputLanguage == "zh-CN"
            else DERIVED_WORKFLOW_STAGES_EN
        )
    )
    workflow_source = "user" if brief.roughProcess else "derived"
    if brief.specialCases.strip():
        special_case_statements = [brief.specialCases.strip()]
        special_case_source = "user"
    else:
        special_case_statements = list(
            DERIVED_SPECIAL_CASES_ZH
            if brief.outputLanguage == "zh-CN"
            else DERIVED_SPECIAL_CASES_EN
        )
        special_case_source = "derived"
    legacy_special_cases = "\n".join(special_case_statements)
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
                source=workflow_source,
            )
            for index, stage in enumerate(workflow_statements, start=1)
        ],
        completionCriteria=completion,
        specialCases=legacy_special_cases,
        specialCaseItems=[
            SpecialCaseSpec(
                id=f"special-cases.{index:02d}",
                statement=statement,
                source=special_case_source,
            )
            for index, statement in enumerate(special_case_statements, start=1)
        ],
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


_PACKAGE_DIRS = {"references", "scripts", "assets", "agents"}


def _normalize_rendered_path(path: str, skill_name: str) -> str:
    cleaned = path.replace("\\", "/").strip().lstrip("/")
    while cleaned.startswith("./"):
        cleaned = cleaned[2:]
    segments = [segment for segment in cleaned.split("/") if segment]
    while (
        len(segments) > 1
        and segments[0] == skill_name
        and segments[1] == skill_name
    ):
        segments.pop(0)
    if not segments or segments[0] == skill_name:
        return "/".join(segments) or cleaned
    if segments[0] == "SKILL.md" or segments[0] in _PACKAGE_DIRS:
        return "/".join([skill_name, *segments])
    if len(segments) > 1 and (
        segments[1] == "SKILL.md" or segments[1] in _PACKAGE_DIRS
    ):
        return "/".join([skill_name, *segments[1:]])
    return "/".join(segments)


def _normalize_package_relative_path(path: str, skill_name: str) -> str:
    cleaned = path.replace("\\", "/").strip().lstrip("/")
    while cleaned.startswith("./"):
        cleaned = cleaned[2:]
    segments = [segment for segment in cleaned.split("/") if segment]
    while segments and segments[0] == skill_name:
        segments.pop(0)
    return "/".join(segments)


# Spec items whose canonical IR path is the prefix itself.
_EXACT_IR_PATH_PREFIXES = {
    "skill.name",
    "platforms.targets",
    "skill.description",
    "workflow.objective",
}


def _matches_ir_prefix(path: str, prefix: str) -> bool:
    return path == prefix or path.startswith(f"{prefix}.") or path.startswith(
        f"{prefix}["
    )


def _canonical_ir_path(
    ir: SkillIR, requirement: RequiredSpecTraceItem
) -> str | None:
    prefix = requirement.irPathPrefix
    if prefix in _EXACT_IR_PATH_PREFIXES:
        return prefix
    expected = requirement.expectedValue
    if not isinstance(expected, str):
        return None
    if prefix == "agentKnowledge.unknownKnowledge":
        if expected in ir.agentKnowledge.unknownKnowledge:
            index = ir.agentKnowledge.unknownKnowledge.index(expected)
            return f"{prefix}[{index}]"
        return None
    if prefix == "quality.hardRestrictions":
        if expected in ir.quality.hardRestrictions:
            return f"{prefix}[{ir.quality.hardRestrictions.index(expected)}]"
        return None
    if prefix == "workflow.decisionPoints":
        if expected in ir.workflow.decisionPoints:
            return f"{prefix}[{ir.workflow.decisionPoints.index(expected)}]"
        alternate = "workflow.failureHandling"
        if expected in ir.workflow.failureHandling:
            return (
                f"{alternate}[{ir.workflow.failureHandling.index(expected)}]"
            )
        return None
    if prefix == "quality.validationChecklist":
        if expected in ir.quality.validationChecklist:
            return (
                f"{prefix}[{ir.quality.validationChecklist.index(expected)}]"
            )
        return None
    return None


def enforce_spec_contract(ir: SkillIR, spec: SkillSpec) -> SkillIR:
    """Deterministically repair spec-trace facts no agent should be trusted with.

    Rendered paths and the package layout are decided by the renderer, not the
    model, so wrong or missing skill-directory prefixes are normalized instead
    of failing the candidate — both in specTrace.renderedPaths and in
    contextEngineering file paths. Incremental knowledge, user supplements,
    special cases, and acceptance criteria are authoritative facts that must
    survive every candidate, so missing values are restored to their fixed IR
    homes. Finally, irPaths bookkeeping is repaired: paths that point outside
    the required section or at stale paraphrases are replaced by the canonical
    path whenever the contract determines one.
    """
    enforced = ir.model_copy(deep=True)
    original_skill_name = enforced.skill.name
    context = enforced.contextEngineering
    for reference_file in context.referenceFiles:
        normalized = _normalize_package_relative_path(
            reference_file.path, original_skill_name
        )
        if normalized:
            reference_file.path = normalized
    for field in ("references", "scripts", "assets"):
        normalized_paths = []
        for path in getattr(context, field):
            normalized = _normalize_package_relative_path(
                path, original_skill_name
            )
            if normalized and normalized not in normalized_paths:
                normalized_paths.append(normalized)
        setattr(context, field, normalized_paths)

    enforced.skill.name = spec.identity.skillName
    enforced.skill.language = spec.identity.outputLanguage
    enforced.platforms.targets = list(spec.identity.targetPlatforms)
    enforced.quality.hardRestrictions = list(spec.hardRestrictions)
    skill_name = enforced.skill.name

    knowledge = enforced.agentKnowledge.unknownKnowledge
    for statement in (
        *spec.incrementalKnowledge,
        *(supplement.statement for supplement in spec.userSupplements),
    ):
        if statement not in knowledge:
            knowledge.append(statement)
    special_cases = [
        item.statement for item in _special_case_items(spec)
    ] or ([spec.specialCases] if spec.specialCases.strip() else [])
    for statement in special_cases:
        if (
            statement not in enforced.workflow.decisionPoints
            and statement not in enforced.workflow.failureHandling
        ):
            enforced.workflow.decisionPoints.append(statement)
    for pitfall in spec.pitfalls:
        if not any(
            candidate.id == pitfall.id if pitfall.id else candidate == pitfall
            for candidate in enforced.agentKnowledge.pitfalls
        ):
            enforced.agentKnowledge.pitfalls.append(pitfall.model_copy(deep=True))
    for related in spec.relatedSkills:
        if related.name not in enforced.agentKnowledge.relatedSkills:
            enforced.agentKnowledge.relatedSkills.append(related.name)
    for criterion in spec.acceptanceCriteria:
        if (
            criterion.required
            and criterion.statement not in enforced.quality.validationChecklist
        ):
            enforced.quality.validationChecklist.append(criterion.statement)

    enforced.specTrace = build_spec_trace(enforced, spec)
    return enforced


def build_spec_trace(ir: SkillIR, spec: SkillSpec) -> list[SpecTraceItem]:
    skill_md = f"{ir.skill.name}/SKILL.md"
    knowledge_paths = _knowledge_rendered_paths(ir)
    traces: list[SpecTraceItem] = []

    def add(spec_item_id: str, ir_path: str, rendered_paths: list[str]) -> None:
        traces.append(
            SpecTraceItem(
                specItemId=spec_item_id,
                irPaths=[ir_path],
                renderedPaths=rendered_paths,
            )
        )

    add("identity.name", "skill.name", [skill_md])
    add("identity.platforms", "platforms.targets", [skill_md])
    add("activation.usage", "skill.description", [skill_md])
    add("activation.outcome", "workflow.objective", [skill_md])

    for index, stage in enumerate(spec.workflowStages):
        if stage.required and index < len(ir.workflow.steps):
            add(stage.id, f"workflow.steps[{index}]", [skill_md])

    for item in _special_case_items(spec):
        path = _list_value_path(
            ir.workflow.decisionPoints,
            ir.workflow.failureHandling,
            item.statement,
        )
        if path:
            add(item.id, path, [skill_md])
    if not spec.specialCaseItems and spec.specialCases.strip():
        path = _list_value_path(
            ir.workflow.decisionPoints,
            ir.workflow.failureHandling,
            spec.specialCases,
        )
        if path:
            add("special-cases.01", path, [skill_md])

    for index, statement in enumerate(spec.incrementalKnowledge, start=1):
        if statement in ir.agentKnowledge.unknownKnowledge:
            item_index = ir.agentKnowledge.unknownKnowledge.index(statement)
            add(
                f"knowledge.incremental.{index:02d}",
                f"agentKnowledge.unknownKnowledge[{item_index}]",
                knowledge_paths,
            )
    for supplement in spec.userSupplements:
        if supplement.statement in ir.agentKnowledge.unknownKnowledge:
            item_index = ir.agentKnowledge.unknownKnowledge.index(
                supplement.statement
            )
            add(
                supplement.id,
                f"agentKnowledge.unknownKnowledge[{item_index}]",
                knowledge_paths,
            )
    for index, pitfall in enumerate(spec.pitfalls, start=1):
        item_index = next(
            (
                candidate_index
                for candidate_index, candidate in enumerate(
                    ir.agentKnowledge.pitfalls
                )
                if (
                    candidate.id == pitfall.id
                    if pitfall.id
                    else candidate == pitfall
                )
            ),
            None,
        )
        if item_index is not None:
            add(
                f"pitfall.{pitfall.id}" if pitfall.id else f"pitfall.{index:02d}",
                f"agentKnowledge.pitfalls[{item_index}]",
                knowledge_paths,
            )
    for index, restriction in enumerate(spec.restrictionItems):
        if index < len(ir.quality.hardRestrictions):
            add(
                restriction.id,
                f"quality.hardRestrictions[{index}]",
                [skill_md],
            )
    for index, related in enumerate(spec.relatedSkills, start=1):
        if related.name in ir.agentKnowledge.relatedSkills:
            item_index = ir.agentKnowledge.relatedSkills.index(related.name)
            add(
                f"related-skill.{index:02d}",
                f"agentKnowledge.relatedSkills[{item_index}]",
                knowledge_paths,
            )
    for criterion in spec.acceptanceCriteria:
        if (
            criterion.required
            and criterion.statement in ir.quality.validationChecklist
        ):
            item_index = ir.quality.validationChecklist.index(
                criterion.statement
            )
            add(
                criterion.id,
                f"quality.validationChecklist[{item_index}]",
                [skill_md],
            )

    context = ir.contextEngineering
    if spec.fileContract.needsReferences:
        if context.referenceFiles:
            path = context.referenceFiles[0].path
            add(
                "files.references",
                "contextEngineering.referenceFiles[0]",
                [f"{ir.skill.name}/{path}"],
            )
        elif context.references:
            path = context.references[0]
            add(
                "files.references",
                "contextEngineering.references[0]",
                [f"{ir.skill.name}/{path}"],
            )
    if spec.fileContract.needsScripts and context.scripts:
        add(
            "files.scripts",
            "contextEngineering.scripts[0]",
            [f"{ir.skill.name}/{context.scripts[0]}"],
        )
    if spec.fileContract.needsAssets and context.assets:
        add(
            "files.assets",
            "contextEngineering.assets[0]",
            [f"{ir.skill.name}/{context.assets[0]}"],
        )
    return traces


def _list_value_path(
    primary: list[str],
    alternate: list[str],
    statement: str,
) -> str | None:
    if statement in primary:
        return f"workflow.decisionPoints[{primary.index(statement)}]"
    if statement in alternate:
        return f"workflow.failureHandling[{alternate.index(statement)}]"
    return None


def _knowledge_rendered_paths(ir: SkillIR) -> list[str]:
    if ir.contextEngineering.referenceFiles:
        return [
            f"{ir.skill.name}/{ir.contextEngineering.referenceFiles[0].path}"
        ]
    if ir.contextEngineering.references:
        return [
            f"{ir.skill.name}/{ir.contextEngineering.references[0]}"
        ]
    return [f"{ir.skill.name}/SKILL.md"]
