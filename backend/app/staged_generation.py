from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel, Field

from app.models import (
    AgentKnowledge,
    ContextEngineering,
    FreedomLevel,
    SkillBrief,
    SkillHandoff,
    SkillIR,
    SkillMeta,
    SkillPlatforms,
    SkillQuality,
    SkillSpec,
    SkillWorkflow,
    SpecTraceItem,
    WorkflowStep,
)
from app.spec_builder import enforce_spec_contract, required_spec_trace_items


class WorkflowGenerationResult(BaseModel):
    description: str
    overview: str = ""
    objective: str
    steps: list[WorkflowStep] = Field(default_factory=list)
    decisionPoints: list[str] = Field(default_factory=list)
    failureHandling: list[str] = Field(default_factory=list)
    verification: list[str] = Field(default_factory=list)
    skillHandoffs: list[SkillHandoff] = Field(default_factory=list)


class KnowledgeGenerationResult(BaseModel):
    contextEngineering: ContextEngineering = Field(default_factory=ContextEngineering)
    agentKnowledge: AgentKnowledge = Field(default_factory=AgentKnowledge)


class QualityGenerationResult(BaseModel):
    freedomLevel: FreedomLevel = "medium"
    softGuidance: list[str] = Field(default_factory=list)
    validationChecklist: list[str] = Field(default_factory=list)


class SemanticTraceItem(BaseModel):
    specItemId: str
    irPaths: list[str] = Field(default_factory=list)


class SemanticTraceResult(BaseModel):
    items: list[SemanticTraceItem] = Field(default_factory=list)


def validate_workflow_result(
    result: WorkflowGenerationResult,
    spec: SkillSpec,
) -> list[str]:
    errors: list[str] = []
    required_stages = [stage for stage in spec.workflowStages if stage.required]
    if not result.description.strip():
        errors.append("触发描述为空")
    if not result.objective.strip():
        errors.append("工作流目标为空")
    if len(result.steps) < len(required_stages):
        errors.append("工作流步骤数量少于必需规格阶段")
    incomplete = [
        step.id or f"step-{index}"
        for index, step in enumerate(result.steps, start=1)
        if not all(
            value.strip()
            for value in (
                step.purpose,
                step.action,
                step.input,
                step.output,
                step.validation,
                step.failureHandling,
            )
        )
    ]
    if incomplete:
        errors.append(f"工作流步骤字段不完整：{', '.join(incomplete)}")
    return errors


def validate_knowledge_result(
    result: KnowledgeGenerationResult,
    spec: SkillSpec,
) -> list[str]:
    errors: list[str] = []
    context = result.contextEngineering
    if (
        spec.fileContract.needsReferences
        and not context.references
        and not context.referenceFiles
    ):
        errors.append("缺少 references 文件")
    if spec.fileContract.needsScripts and not context.scripts:
        errors.append("缺少 scripts 文件")
    if spec.fileContract.needsAssets and not context.assets:
        errors.append("缺少 assets 文件")
    for reference in context.referenceFiles:
        if not reference.path.strip() or not reference.content.strip():
            errors.append("referenceFiles 必须包含文件路径和内容")
            break
    return errors


def validate_quality_result(
    result: QualityGenerationResult,
    spec: SkillSpec,
) -> list[str]:
    required = [
        criterion.statement
        for criterion in spec.acceptanceCriteria
        if criterion.required
    ]
    if any(statement not in result.validationChecklist for statement in required):
        return ["验收标准未进入 validationChecklist"]
    return []


def validate_semantic_trace_result(
    result: SemanticTraceResult,
    spec: SkillSpec,
    ir: SkillIR,
) -> list[str]:
    required_ids = {
        "activation.usage",
        "activation.outcome",
        *(
            stage.id
            for stage in spec.workflowStages
            if stage.required
        ),
    }
    allowed_prefixes = {
        "activation.usage": ("skill.description",),
        "activation.outcome": ("workflow.objective",),
        **{
            stage.id: ("workflow.steps",)
            for stage in spec.workflowStages
            if stage.required
        },
    }
    errors: list[str] = []
    seen: set[str] = set()
    workflow_paths: dict[str, str] = {}
    payload = ir.model_dump(mode="json")
    for item in result.items:
        if item.specItemId not in required_ids:
            errors.append(f"不允许由语义阶段映射 {item.specItemId}")
            continue
        if item.specItemId in seen:
            errors.append(f"语义映射重复：{item.specItemId}")
            continue
        seen.add(item.specItemId)
        if not item.irPaths:
            errors.append(f"语义映射路径为空：{item.specItemId}")
            continue
        for path in item.irPaths:
            if not any(
                _matches_prefix(path, prefix)
                for prefix in allowed_prefixes[item.specItemId]
            ):
                errors.append(f"语义映射路径不属于固定区域：{item.specItemId}")
                continue
            if not _path_has_content(payload, path):
                errors.append(f"语义映射路径无效：{item.specItemId} -> {path}")
                continue
            if item.specItemId.startswith("workflow.stage."):
                owner = workflow_paths.setdefault(path, item.specItemId)
                if owner != item.specItemId:
                    errors.append(f"{item.specItemId} 复用了 {path}")
    missing = sorted(required_ids - seen)
    if missing:
        errors.append(f"缺少语义映射：{', '.join(missing)}")
    return errors


def assemble_skill_ir(
    brief: SkillBrief,
    spec: SkillSpec,
    workflow: WorkflowGenerationResult,
    knowledge: KnowledgeGenerationResult,
    quality: QualityGenerationResult,
    semantic_trace: SemanticTraceResult,
) -> SkillIR:
    agent_knowledge = knowledge.agentKnowledge.model_copy(deep=True)
    for statement in spec.incrementalKnowledge:
        if statement not in agent_knowledge.unknownKnowledge:
            agent_knowledge.unknownKnowledge.append(statement)
    for supplement in spec.userSupplements:
        if supplement.statement not in agent_knowledge.unknownKnowledge:
            agent_knowledge.unknownKnowledge.append(supplement.statement)
    if not agent_knowledge.pitfalls and spec.pitfalls:
        agent_knowledge.pitfalls = [
            item.model_copy(deep=True) for item in spec.pitfalls
        ]
    for related in spec.relatedSkills:
        if related.name not in agent_knowledge.relatedSkills:
            agent_knowledge.relatedSkills.append(related.name)
    if not agent_knowledge.supplementalContext.strip():
        agent_knowledge.supplementalContext = brief.supplementalContext

    context = knowledge.contextEngineering.model_copy(deep=True)
    if (
        spec.fileContract.needsReferences
        and not context.references
        and not context.referenceFiles
    ):
        context.references.append("references/domain-knowledge.md")

    checklist = list(quality.validationChecklist)
    for criterion in spec.acceptanceCriteria:
        if criterion.required and criterion.statement not in checklist:
            checklist.append(criterion.statement)

    decision_points = list(workflow.decisionPoints)
    failure_handling = list(workflow.failureHandling)
    if (
        spec.specialCases.strip()
        and spec.specialCases not in decision_points
        and spec.specialCases not in failure_handling
    ):
        decision_points.append(spec.specialCases)

    ir = SkillIR(
        schemaVersion="1.1",
        skill=SkillMeta(
            name=spec.identity.skillName,
            description=workflow.description,
            language=spec.identity.outputLanguage,
            overview=workflow.overview,
        ),
        workflow=SkillWorkflow(
            objective=workflow.objective,
            steps=[item.model_copy(deep=True) for item in workflow.steps],
            decisionPoints=decision_points,
            failureHandling=failure_handling,
            verification=list(workflow.verification),
            skillHandoffs=[
                item.model_copy(deep=True) for item in workflow.skillHandoffs
            ],
        ),
        contextEngineering=context,
        agentKnowledge=agent_knowledge,
        quality=SkillQuality(
            freedomLevel=quality.freedomLevel,
            hardRestrictions=list(spec.hardRestrictions),
            softGuidance=list(quality.softGuidance),
            validationChecklist=checklist,
        ),
        platforms=SkillPlatforms(targets=list(spec.identity.targetPlatforms)),
        specTrace=[
            SpecTraceItem(
                specItemId=item.specItemId,
                irPaths=list(item.irPaths),
                renderedPaths=[f"{spec.identity.skillName}/SKILL.md"],
            )
            for item in semantic_trace.items
        ],
    )
    ir = enforce_spec_contract(ir, spec)
    _add_deterministic_traces(ir, spec)
    return ir


def _add_deterministic_traces(ir: SkillIR, spec: SkillSpec) -> None:
    traces = {item.specItemId: item for item in ir.specTrace}
    skill_md = f"{ir.skill.name}/SKILL.md"

    def add(spec_item_id: str, ir_path: str, rendered_paths: list[str]) -> None:
        traces[spec_item_id] = SpecTraceItem(
            specItemId=spec_item_id,
            irPaths=[ir_path],
            renderedPaths=rendered_paths,
        )

    add("identity.name", "skill.name", [skill_md])
    add("identity.platforms", "platforms.targets", [skill_md])

    for index, statement in enumerate(spec.incrementalKnowledge, start=1):
        knowledge_index = ir.agentKnowledge.unknownKnowledge.index(statement)
        add(
            f"knowledge.incremental.{index:02d}",
            f"agentKnowledge.unknownKnowledge[{knowledge_index}]",
            _knowledge_rendered_paths(ir),
        )
    for supplement in spec.userSupplements:
        knowledge_index = ir.agentKnowledge.unknownKnowledge.index(
            supplement.statement
        )
        add(
            supplement.id,
            f"agentKnowledge.unknownKnowledge[{knowledge_index}]",
            _knowledge_rendered_paths(ir),
        )
    for index, pitfall in enumerate(spec.pitfalls, start=1):
        spec_item_id = (
            f"pitfall.{pitfall.id}" if pitfall.id else f"pitfall.{index:02d}"
        )
        pitfall_index = next(
            (
                item_index
                for item_index, candidate in enumerate(ir.agentKnowledge.pitfalls)
                if (
                    pitfall.id
                    and candidate.id == pitfall.id
                    or candidate == pitfall
                )
            ),
            None,
        )
        if pitfall_index is not None:
            add(
                spec_item_id,
                f"agentKnowledge.pitfalls[{pitfall_index}]",
                [skill_md],
            )
    for restriction_index, restriction in enumerate(spec.restrictionItems):
        add(
            restriction.id,
            f"quality.hardRestrictions[{restriction_index}]",
            [skill_md],
        )
    for index, related in enumerate(spec.relatedSkills, start=1):
        related_index = ir.agentKnowledge.relatedSkills.index(related.name)
        add(
            f"related-skill.{index:02d}",
            f"agentKnowledge.relatedSkills[{related_index}]",
            [skill_md],
        )

    _add_file_trace(ir, spec, traces)
    ir.specTrace = list(traces.values())


def _add_file_trace(
    ir: SkillIR,
    spec: SkillSpec,
    traces: dict[str, SpecTraceItem],
) -> None:
    skill_name = ir.skill.name
    context = ir.contextEngineering
    if spec.fileContract.needsReferences:
        if context.referenceFiles:
            path = context.referenceFiles[0].path
            ir_path = "contextEngineering.referenceFiles[0]"
        elif context.references:
            path = context.references[0]
            ir_path = "contextEngineering.references[0]"
        else:
            path = ""
            ir_path = ""
        if path:
            traces["files.references"] = SpecTraceItem(
                specItemId="files.references",
                irPaths=[ir_path],
                renderedPaths=[f"{skill_name}/{path}"],
            )
    if spec.fileContract.needsScripts and context.scripts:
        traces["files.scripts"] = SpecTraceItem(
            specItemId="files.scripts",
            irPaths=["contextEngineering.scripts[0]"],
            renderedPaths=[f"{skill_name}/{context.scripts[0]}"],
        )
    if spec.fileContract.needsAssets and context.assets:
        traces["files.assets"] = SpecTraceItem(
            specItemId="files.assets",
            irPaths=["contextEngineering.assets[0]"],
            renderedPaths=[f"{skill_name}/{context.assets[0]}"],
        )


def _knowledge_rendered_paths(ir: SkillIR) -> list[str]:
    paths = [
        *(item.path for item in ir.contextEngineering.referenceFiles),
        *ir.contextEngineering.references,
    ]
    if not paths:
        return [f"{ir.skill.name}/SKILL.md"]
    return [f"{ir.skill.name}/{paths[0]}"]


def semantic_trace_spec_item_ids(spec: SkillSpec) -> set[str]:
    return {
        "activation.usage",
        "activation.outcome",
        *(stage.id for stage in spec.workflowStages if stage.required),
    }


def missing_trace_ids(ir: SkillIR, spec: SkillSpec) -> list[str]:
    required = {
        item.specItemId for item in required_spec_trace_items(spec)
    }
    actual = {item.specItemId for item in ir.specTrace}
    return sorted(required - actual)


def _matches_prefix(path: str, prefix: str) -> bool:
    return path == prefix or path.startswith(f"{prefix}.") or path.startswith(
        f"{prefix}["
    )


_PATH_SEGMENT = re.compile(r"([A-Za-z_][A-Za-z0-9_]*)(?:\[(\d+)\])?")


def _path_has_content(payload: Any, path: str) -> bool:
    current = payload
    try:
        for raw_segment in path.split("."):
            match = _PATH_SEGMENT.fullmatch(raw_segment)
            if match is None or not isinstance(current, dict):
                return False
            key, raw_index = match.groups()
            current = current[key]
            if raw_index is not None:
                if not isinstance(current, list):
                    return False
                current = current[int(raw_index)]
    except (KeyError, IndexError, TypeError, ValueError):
        return False
    if isinstance(current, str):
        return bool(current.strip())
    if isinstance(current, (list, dict)):
        return bool(current)
    return current is not None
