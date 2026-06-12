from app.models import SkillDraft
from app.normalizer import normalize_draft
from app.spec_builder import build_skill_spec
from app.staged_generation import (
    KnowledgeGenerationResult,
    QualityGenerationResult,
    SemanticTraceResult,
    WorkflowGenerationResult,
    assemble_skill_ir,
    validate_knowledge_result,
    validate_quality_result,
    validate_semantic_trace_result,
    validate_workflow_result,
)
from tests.test_api_pipeline import build_draft_payload


def _brief_and_spec():
    draft = SkillDraft.model_validate(
        {
            **build_draft_payload(),
            "id": "draft_staged",
            "createdAt": 1,
            "updatedAt": 1,
        }
    )
    brief, _ = normalize_draft(draft)
    return brief, build_skill_spec(brief, revision=1)


def _workflow(brief) -> WorkflowGenerationResult:
    return WorkflowGenerationResult.model_validate(
        {
            "description": "Use when product teams need evidence-backed competitor research.",
            "overview": "Build a traceable research conclusion from supplied evidence.",
            "objective": brief.desiredOutcome,
            "steps": [
                {
                    "id": f"step_{index}",
                    "purpose": stage,
                    "action": f"执行阶段：{stage}",
                    "input": "用户请求与已有材料",
                    "output": f"{stage}的可验证结果",
                    "validation": "结果与来源可以回溯",
                    "failureHandling": "信息不足时列出缺口",
                }
                for index, stage in enumerate(brief.roughProcess, start=1)
            ],
            "decisionPoints": [],
            "failureHandling": [],
            "verification": [],
            "skillHandoffs": [],
        }
    )


def _knowledge() -> KnowledgeGenerationResult:
    return KnowledgeGenerationResult.model_validate(
        {
            "contextEngineering": {
                "filesystemAssumptions": ["仅在相关步骤加载参考资料。"],
                "references": ["references/domain-knowledge.md"],
                "referenceFiles": [],
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
        }
    )


def _quality() -> QualityGenerationResult:
    return QualityGenerationResult(
        freedomLevel="medium",
        softGuidance=["先验证证据，再形成结论。"],
        validationChecklist=["模型自行生成的检查项"],
    )


def _semantic_trace() -> SemanticTraceResult:
    return SemanticTraceResult.model_validate(
        {
            "items": [
                {
                    "specItemId": "activation.usage",
                    "irPaths": ["skill.description"],
                },
                {
                    "specItemId": "activation.outcome",
                    "irPaths": ["workflow.objective"],
                },
                *[
                    {
                        "specItemId": f"workflow.stage.{index:02d}",
                        "irPaths": [f"workflow.steps[{index - 1}]"],
                    }
                    for index in range(1, 4)
                ],
            ],
        }
    )


def test_assemble_skill_ir_restores_authoritative_facts_and_traces() -> None:
    brief, spec = _brief_and_spec()
    workflow = _workflow(brief)
    knowledge = _knowledge()
    quality = _quality()
    semantic = _semantic_trace()

    ir = assemble_skill_ir(brief, spec, workflow, knowledge, quality, semantic)

    assert ir.skill.name == spec.identity.skillName
    assert ir.skill.language == spec.identity.outputLanguage
    assert ir.platforms.targets == spec.identity.targetPlatforms
    assert ir.quality.hardRestrictions == spec.hardRestrictions
    assert spec.specialCases in ir.workflow.decisionPoints
    assert spec.acceptanceCriteria[0].statement in ir.quality.validationChecklist
    assert set(spec.incrementalKnowledge).issubset(ir.agentKnowledge.unknownKnowledge)
    assert {item.name for item in spec.relatedSkills}.issubset(
        ir.agentKnowledge.relatedSkills
    )

    traces = {item.specItemId: item for item in ir.specTrace}
    required_ids = {
        "identity.name",
        "identity.platforms",
        "activation.usage",
        "activation.outcome",
        "special-cases.01",
        "acceptance.01",
        "files.references",
        *(
            f"workflow.stage.{index:02d}"
            for index in range(1, len(spec.workflowStages) + 1)
        ),
    }
    assert required_ids.issubset(traces)
    assert traces["special-cases.01"].irPaths[0].startswith(
        "workflow.decisionPoints["
    )
    assert traces["acceptance.01"].irPaths[0].startswith(
        "quality.validationChecklist["
    )
    assert traces["files.references"].renderedPaths == [
        f"{ir.skill.name}/references/domain-knowledge.md"
    ]


def test_stage_validators_report_owned_contract_failures() -> None:
    brief, spec = _brief_and_spec()
    workflow = _workflow(brief)
    workflow.steps = workflow.steps[:1]
    knowledge = _knowledge()
    knowledge.contextEngineering.references = []
    quality = _quality()
    semantic = SemanticTraceResult(items=[])

    assert "工作流步骤数量少于必需规格阶段" in validate_workflow_result(
        workflow, spec
    )
    assert "缺少 references 文件" in validate_knowledge_result(knowledge, spec)
    assert "验收标准未进入 validationChecklist" in validate_quality_result(
        quality, spec
    )

    assembled = assemble_skill_ir(
        brief,
        spec,
        _workflow(brief),
        _knowledge(),
        _quality(),
        _semantic_trace(),
    )
    errors = validate_semantic_trace_result(semantic, spec, assembled)
    assert "缺少语义映射" in errors[0]


def test_semantic_trace_rejects_non_semantic_spec_ids_and_reused_steps() -> None:
    brief, spec = _brief_and_spec()
    ir = assemble_skill_ir(
        brief,
        spec,
        _workflow(brief),
        _knowledge(),
        _quality(),
        _semantic_trace(),
    )
    semantic = SemanticTraceResult.model_validate(
        {
            "items": [
                {
                    "specItemId": "identity.name",
                    "irPaths": ["skill.name"],
                },
                {
                    "specItemId": "activation.usage",
                    "irPaths": ["skill.description"],
                },
                {
                    "specItemId": "activation.outcome",
                    "irPaths": ["workflow.objective"],
                },
                *[
                    {
                        "specItemId": stage.id,
                        "irPaths": ["workflow.steps[0]"],
                    }
                    for stage in spec.workflowStages
                ],
            ]
        }
    )

    errors = validate_semantic_trace_result(semantic, spec, ir)

    assert any("不允许由语义阶段映射 identity.name" in error for error in errors)
    assert any("复用了 workflow.steps[0]" in error for error in errors)
