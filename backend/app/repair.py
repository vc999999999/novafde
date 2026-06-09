from __future__ import annotations

from app.models import SkillBrief, SkillIR, ValidationItem


MAX_REPAIR_ATTEMPTS = 2


def repair_ir(ir: SkillIR, brief: SkillBrief, issues: list[ValidationItem]) -> tuple[SkillIR, list[str]]:
    repaired = ir.model_copy(deep=True)
    changes: list[str] = []
    blocking_rule_ids = {issue.ruleId for issue in issues if issue.level == "blocking"}

    if "TRIG-001" in blocking_rule_ids:
        task_type = f" for {brief.taskType}" if brief.taskType else ""
        repaired.skill.description = f"Use when the user asks to {brief.triggerIntent}{task_type}."
        changes.append("rewrote description as a trigger condition")

    if "WF-001" in blocking_rule_ids and not repaired.workflow.steps and brief.workflowSteps:
        repaired.workflow.steps = brief.workflowSteps
        repaired.workflow.verification = [step.validation for step in brief.workflowSteps if step.validation.strip()]
        repaired.workflow.failureHandling = [step.failureHandling for step in brief.workflowSteps if step.failureHandling.strip()]
        changes.append("restored workflow steps from normalized brief")

    return repaired, changes
