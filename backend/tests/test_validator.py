from app.models import (
    SkillIR,
    SkillMeta,
    SkillPlatforms,
    SkillQuality,
    SkillWorkflow,
    WorkflowStep,
)
from app.validator import validate_ir


def test_validate_ir_blocks_incomplete_creator_steps_and_missing_mandatory_rules() -> None:
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
    assert {"WF-001", "RULE-001"}.issubset(blocking_rule_ids)
