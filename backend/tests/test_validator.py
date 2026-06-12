from pathlib import Path

from app.models import (
    ReferenceFile,
    SpecTraceItem,
    SkillIR,
    SkillMeta,
    SkillPlatforms,
    SkillQuality,
    SkillWorkflow,
    WorkflowStep,
)
from app.normalizer import normalize_draft
from app.renderer import render_skill_package
from app.spec_builder import build_skill_spec, required_spec_trace_items
from app.validator import validate_ir, validate_rendered_package
from app.validator import validate_official_agent_skill, validate_spec_compliance
from tests.test_api_pipeline import build_draft_payload


def test_validate_ir_blocks_incomplete_creator_steps_but_not_missing_rules() -> None:
    ir = SkillIR(
        skill=SkillMeta(
            name="research",
            description="Use when the user needs a structured research workflow.",
            language="en",
        ),
        workflow=SkillWorkflow(
            objective="Produce a supported conclusion",
            steps=[
                WorkflowStep(
                    id="step_1",
                    purpose="Collect evidence",
                    action="",
                    input="User materials",
                    output="Evidence list",
                    validation="Every item has a source",
                    failureHandling="Ask for missing sources",
                )
            ],
        ),
        quality=SkillQuality(hardRestrictions=[]),
        platforms=SkillPlatforms(targets=["codex"]),
    )

    issues = validate_ir(ir)

    blocking_rule_ids = {item.ruleId for item in issues if item.level == "blocking"}
    assert "WF-001" in blocking_rule_ids
    # Mandatory rules are optional user input: an empty list does not block.
    # Loss of user-provided rules is caught in evaluate_validation instead.
    assert "RULE-001" not in blocking_rule_ids


def _brief_and_spec():
    from app.models import SkillDraft

    draft = SkillDraft.model_validate(
        {
            **build_draft_payload(),
            "id": "draft_trace",
            "createdAt": 1,
            "updatedAt": 1,
        }
    )
    brief, _ = normalize_draft(draft)
    return brief, build_skill_spec(brief, revision=1)


def _trace_for(ir: SkillIR, spec) -> list[SpecTraceItem]:
    workflow_index = 0
    restriction_index = 0
    knowledge_index = 0
    pitfall_index = 0
    related_index = 0
    traces: list[SpecTraceItem] = []
    for item in required_spec_trace_items(spec):
        if item.irPathPrefix == "workflow.steps":
            ir_path = f"workflow.steps[{workflow_index}]"
            workflow_index += 1
        elif item.irPathPrefix == "quality.hardRestrictions":
            ir_path = f"quality.hardRestrictions[{restriction_index}]"
            restriction_index += 1
        elif item.irPathPrefix == "agentKnowledge.unknownKnowledge":
            ir_path = f"agentKnowledge.unknownKnowledge[{knowledge_index}]"
            knowledge_index += 1
        elif item.irPathPrefix == "agentKnowledge.pitfalls":
            ir_path = f"agentKnowledge.pitfalls[{pitfall_index}]"
            pitfall_index += 1
        elif item.irPathPrefix == "agentKnowledge.relatedSkills":
            ir_path = f"agentKnowledge.relatedSkills[{related_index}]"
            related_index += 1
        elif item.irPathPrefix == "quality.validationChecklist":
            ir_path = (
                "quality.validationChecklist["
                f"{ir.quality.validationChecklist.index(item.expectedValue)}]"
            )
        elif item.irPathPrefix == "workflow.failureHandling":
            ir_path = "workflow.failureHandling[0]"
        elif item.irPathPrefix == "contextEngineering.references":
            ir_path = "contextEngineering.references[0]"
        else:
            ir_path = item.irPathPrefix
        traces.append(
            SpecTraceItem(
                specItemId=item.specItemId,
                irPaths=[ir_path],
                renderedPaths=[f"{ir.skill.name}/SKILL.md"],
            )
        )
    return traces


def test_spec_compliance_blocks_missing_trace(tmp_path: Path) -> None:
    from tests.test_quality_orchestrator import valid_ir

    _brief, spec = _brief_and_spec()
    ir = valid_ir()
    ir.specTrace = []
    render_skill_package(ir, tmp_path)

    items = validate_spec_compliance(tmp_path, ir, spec)

    assert any(
        item.ruleId == "SPEC-TRACE-001" and item.level == "blocking"
        for item in items
    )


def test_rendered_package_blocks_non_skill_root_entries(tmp_path: Path) -> None:
    from tests.test_quality_orchestrator import valid_ir

    ir = valid_ir()
    render_skill_package(ir, tmp_path)
    (tmp_path / "package-manifest.json").write_text("{}", encoding="utf-8")
    (tmp_path / "install").mkdir()

    items = validate_rendered_package(tmp_path, ir)

    assert any(
        item.ruleId == "PKG-004"
        and item.level == "blocking"
        and "package-manifest.json" in item.description
        and "install" in item.description
        for item in items
    )


def test_validate_ir_blocks_resource_paths_outside_standard_dirs() -> None:
    from tests.test_quality_orchestrator import valid_ir

    ir = valid_ir()
    ir.contextEngineering.references = ["docs/domain.md"]
    ir.contextEngineering.scripts = ["helpers/run.py"]
    ir.contextEngineering.assets = ["template.json"]

    items = validate_ir(ir)

    assert any(
        item.ruleId == "PKG-005"
        and item.level == "blocking"
        and "references/" in item.description
        and "scripts/" in item.description
        and "assets/" in item.description
        for item in items
    )


def test_spec_compliance_accepts_complete_trace(tmp_path: Path) -> None:
    from tests.test_quality_orchestrator import valid_ir

    _brief, spec = _brief_and_spec()
    ir = valid_ir()
    ir.specTrace = _trace_for(ir, spec)
    render_skill_package(ir, tmp_path)

    items = validate_spec_compliance(tmp_path, ir, spec)

    assert not [item for item in items if item.level == "blocking"]


def test_spec_compliance_blocks_modified_hard_restrictions(tmp_path: Path) -> None:
    from tests.test_quality_orchestrator import valid_ir

    _brief, spec = _brief_and_spec()
    ir = valid_ir()
    ir.quality.hardRestrictions = [*spec.hardRestrictions, "模型新增限制"]
    ir.specTrace = _trace_for(ir, spec)
    render_skill_package(ir, tmp_path)

    items = validate_spec_compliance(tmp_path, ir, spec)

    assert any(
        item.ruleId == "SPEC-RULE-001" and item.level == "blocking"
        for item in items
    )


def test_spec_compliance_blocks_invalid_ir_and_rendered_paths(tmp_path: Path) -> None:
    from tests.test_quality_orchestrator import valid_ir

    _brief, spec = _brief_and_spec()
    ir = valid_ir()
    ir.specTrace = _trace_for(ir, spec)
    ir.specTrace[0].irPaths = ["workflow.steps[999]"]
    ir.specTrace[0].renderedPaths = [f"{ir.skill.name}/missing.md"]
    render_skill_package(ir, tmp_path)

    items = validate_spec_compliance(tmp_path, ir, spec)

    assert any(
        item.ruleId == "SPEC-TRACE-002" and item.level == "blocking"
        for item in items
    )


def test_spec_compliance_accepts_authored_reference_file_contract(
    tmp_path: Path,
) -> None:
    from tests.test_quality_orchestrator import valid_ir

    _brief, spec = _brief_and_spec()
    ir = valid_ir()
    ir.contextEngineering.references = []
    ir.contextEngineering.referenceFiles = [
        ReferenceFile(
            path="references/domain-knowledge.md",
            purpose="需要领域判断标准时",
            content="# Domain Knowledge\n\nEvidence rules.",
        )
    ]
    ir.specTrace = _trace_for(ir, spec)
    file_trace = next(
        item for item in ir.specTrace if item.specItemId == "files.references"
    )
    file_trace.irPaths = ["contextEngineering.referenceFiles[0]"]
    file_trace.renderedPaths = [
        f"{ir.skill.name}/references/domain-knowledge.md"
    ]
    render_skill_package(ir, tmp_path)

    items = validate_spec_compliance(tmp_path, ir, spec)

    assert not [item for item in items if item.level == "blocking"]


def test_official_agent_skill_validator_accepts_rendered_package(tmp_path: Path) -> None:
    from tests.test_quality_orchestrator import valid_ir

    ir = valid_ir()
    render_skill_package(ir, tmp_path)

    items = validate_official_agent_skill(tmp_path, ir)

    assert any(
        item.ruleId == "AGENT-SKILLS-001" and item.level == "pass"
        for item in items
    )


def test_official_agent_skill_validator_rejects_illegal_frontmatter(
    tmp_path: Path,
) -> None:
    from tests.test_quality_orchestrator import valid_ir

    ir = valid_ir()
    skill_dir = render_skill_package(ir, tmp_path)
    skill_md = skill_dir / "SKILL.md"
    skill_md.write_text(
        skill_md.read_text(encoding="utf-8").replace(
            f"name: {ir.skill.name}\n",
            f"name: {ir.skill.name}\nunexpected: true\n",
            1,
        ),
        encoding="utf-8",
    )

    items = validate_official_agent_skill(tmp_path, ir)

    assert any(
        item.ruleId == "AGENT-SKILLS-001" and item.level == "blocking"
        for item in items
    )

def test_spec_trace_issues_bind_only_failing_spec_item_ids(tmp_path: Path) -> None:
    from tests.test_quality_orchestrator import valid_ir

    _brief, spec = _brief_and_spec()
    ir = valid_ir()
    ir.specTrace = _trace_for(ir, spec)
    corrupted = ir.specTrace[0]
    corrupted.renderedPaths = [f"{ir.skill.name}/missing.md"]
    removed = ir.specTrace.pop()
    render_skill_package(ir, tmp_path)

    items = validate_spec_compliance(tmp_path, ir, spec)

    coverage = next(item for item in items if item.ruleId == "SPEC-TRACE-001")
    assert coverage.specItemIds == [removed.specItemId]
    invalid = next(item for item in items if item.ruleId == "SPEC-TRACE-002")
    assert invalid.specItemIds == [corrupted.specItemId]


def test_enforce_spec_contract_rebuilds_all_trace_metadata(tmp_path: Path) -> None:
    from app.spec_builder import enforce_spec_contract
    from tests.test_quality_orchestrator import valid_ir

    brief, spec = _brief_and_spec()
    ir = valid_ir()
    ir.specTrace = []

    enforced = enforce_spec_contract(ir, spec)
    render_skill_package(enforced, tmp_path)
    items = validate_spec_compliance(tmp_path, enforced, spec)

    assert not any(
        item.ruleId in {"SPEC-TRACE-001", "SPEC-TRACE-002"}
        and item.level == "blocking"
        for item in items
    )
