from __future__ import annotations

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


def assemble_skill_ir(
    brief: SkillBrief,
    spec: SkillSpec,
    workflow: WorkflowGenerationResult,
    knowledge: KnowledgeGenerationResult,
    quality: QualityGenerationResult,
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
    special_cases = [
        item.statement for item in spec.specialCaseItems
    ] or ([spec.specialCases] if spec.specialCases.strip() else [])
    for statement in special_cases:
        if statement not in decision_points and statement not in failure_handling:
            decision_points.append(statement)

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
        specTrace=[],
    )
    ir = enforce_spec_contract(ir, spec)
    return ir


def assemble_partial_skill_ir(
    brief: SkillBrief,
    spec: SkillSpec,
    *,
    workflow: WorkflowGenerationResult | None = None,
    knowledge: KnowledgeGenerationResult | None = None,
    quality: QualityGenerationResult | None = None,
) -> SkillIR:
    """Build a renderable preview IR from whichever staged outputs exist."""
    workflow = workflow or _placeholder_workflow(brief, spec)
    knowledge = knowledge or KnowledgeGenerationResult(
        contextEngineering=ContextEngineering(
            filesystemAssumptions=[
                "正在生成上下文资料；完成后会按需加载 references、scripts 或 assets。",
            ],
        ),
        agentKnowledge=AgentKnowledge(),
    )
    quality = quality or QualityGenerationResult()
    return assemble_skill_ir(brief, spec, workflow, knowledge, quality)


def _placeholder_workflow(
    brief: SkillBrief,
    spec: SkillSpec,
) -> WorkflowGenerationResult:
    stages = [stage for stage in spec.workflowStages if stage.required]
    steps = [
        WorkflowStep(
            id=f"pending_{index}",
            purpose=stage.statement,
            action=f"待生成：{stage.statement}",
            input="用户草稿、生成规格与已补充信息",
            output="待生成的阶段结果",
            validation="完成后由质量流水线校验",
            failureHandling="生成失败时保留当前可读草稿，便于继续修复。",
        )
        for index, stage in enumerate(stages, start=1)
    ]
    return WorkflowGenerationResult(
        description=spec.activationContract.usage,
        overview="阶段性预览：后续生成步骤会继续补全和修订内容。",
        objective=spec.activationContract.desiredOutcome or brief.desiredOutcome,
        steps=steps,
        decisionPoints=[],
        failureHandling=[],
        verification=[],
        skillHandoffs=[],
    )


def missing_trace_ids(ir: SkillIR, spec: SkillSpec) -> list[str]:
    required = {
        item.specItemId for item in required_spec_trace_items(spec)
    }
    actual = {item.specItemId for item in ir.specTrace}
    return sorted(required - actual)
