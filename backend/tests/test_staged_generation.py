from app.models import SkillDraft
from app.normalizer import normalize_draft
from app.spec_builder import build_skill_spec, required_spec_trace_items
from app.staged_generation import (
    KnowledgeGenerationResult,
    QualityGenerationResult,
    WorkflowGenerationResult,
    assemble_skill_ir,
    validate_knowledge_result,
    validate_quality_result,
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


def test_assemble_skill_ir_restores_authoritative_facts_and_traces() -> None:
    brief, spec = _brief_and_spec()
    workflow = _workflow(brief)
    knowledge = _knowledge()
    quality = _quality()
    ir = assemble_skill_ir(brief, spec, workflow, knowledge, quality)

    assert ir.skill.name == spec.identity.skillName
    assert ir.skill.language == spec.identity.outputLanguage
    assert ir.platforms.targets == spec.identity.targetPlatforms
    assert ir.quality.hardRestrictions == spec.hardRestrictions
    assert all(
        item.statement in ir.workflow.decisionPoints
        for item in spec.specialCaseItems
    )
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
        "acceptance.01",
        "files.references",
        *(item.id for item in spec.specialCaseItems),
        *(
            f"workflow.stage.{index:02d}"
            for index in range(1, len(spec.workflowStages) + 1)
        ),
    }
    assert required_ids.issubset(traces)
    assert traces["activation.usage"].irPaths == ["skill.description"]
    assert traces["activation.outcome"].irPaths == ["workflow.objective"]
    assert traces["workflow.stage.01"].irPaths == ["workflow.steps[0]"]
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
    )
    assert {
        item.specItemId for item in assembled.specTrace
    } == {
        item.specItemId
        for item in required_spec_trace_items(spec)
    }
