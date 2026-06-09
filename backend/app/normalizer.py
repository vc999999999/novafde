from __future__ import annotations

from app.models import SkillBrief, SkillDraft, ValidationItem
from app.utils import sanitize_skill_name


def normalize_draft(draft: SkillDraft) -> tuple[SkillBrief, list[ValidationItem]]:
    skill_name = sanitize_skill_name(draft.name or draft.displayName)
    unknown_knowledge = [
        *draft.knowledge.industryRules,
        *draft.knowledge.internalProcesses,
        *draft.knowledge.personalExperience,
    ]
    brief = SkillBrief(
        skillName=skill_name,
        displayName=draft.displayName or skill_name,
        triggerIntent=draft.trigger.intent.strip(),
        taskType=draft.trigger.taskType.strip(),
        positiveExamples=[item.strip() for item in draft.trigger.positiveExamples if item.strip()],
        antiTriggers=[item.strip() for item in draft.trigger.negativeExamples if item.strip()],
        commonPhrases=[item.strip() for item in draft.trigger.commonPhrases if item.strip()],
        workflowObjective=draft.workflow.objective.strip(),
        workflowSteps=draft.workflow.steps,
        preconditions=draft.workflow.preconditions.strip(),
        contextFiles=[item.strip() for item in draft.context.filesToRead if item.strip()],
        needsReferences=draft.context.needsReferences,
        needsScripts=draft.context.needsScripts,
        needsAssets=draft.context.needsAssets,
        loadingRule=draft.context.loadingRule.strip(),
        unknownKnowledge=[item.strip() for item in unknown_knowledge if item.strip()],
        pitfalls=draft.knowledge.pitfalls,
        targetPlatforms=draft.targetPlatforms,
        outputLanguage=draft.language,
        freedomLevel=draft.outputControl.freedom,
        allowHardLimits=draft.outputControl.allowHardLimits,
        validationStrictness=draft.outputControl.validationStrictness,
        allowDownloadWithWarnings=draft.outputControl.allowDownloadWithWarnings,
    )
    return brief, validate_brief(brief)


def validate_brief(brief: SkillBrief) -> list[ValidationItem]:
    items: list[ValidationItem] = []
    if not brief.triggerIntent:
        items.append(
            ValidationItem(
                id="brief-trigger-intent",
                ruleId="BRIEF-001",
                level="blocking",
                title="缺少触发意图",
                description="生成前必须明确用户在什么意图下需要启用这个 Skill。",
                importance="触发意图会进入 description 和 Agent 启用判断，缺失会导致误触发或不触发。",
                suggestion="在触发条件中补充用户意图，例如“帮助产品团队系统化完成竞品调研”。",
                blocksDownload=True,
                field="trigger.intent",
            )
        )
    else:
        items.append(
            ValidationItem(
                id="brief-trigger-intent-pass",
                ruleId="BRIEF-001",
                level="pass",
                title="触发意图已提供",
                description="Brief 已包含用于生成触发条件的用户意图。",
                importance="清晰的触发意图能降低误触发概率。",
                field="trigger.intent",
            )
        )

    if not brief.workflowSteps:
        items.append(
            ValidationItem(
                id="brief-workflow-steps",
                ruleId="WF-001",
                level="blocking",
                title="缺少工作流步骤",
                description="生成前至少需要一个工作流步骤。",
                importance="Skill 必须是可执行流程，而不是泛泛说明。",
                suggestion="添加至少一个包含目的、动作、输入、输出、验证和失败处理的步骤。",
                blocksDownload=True,
                field="workflow.steps",
            )
        )
    else:
        incomplete_steps = [
            step.id or str(index + 1)
            for index, step in enumerate(brief.workflowSteps)
            if not all(
                [
                    step.purpose.strip(),
                    step.action.strip(),
                    step.input.strip(),
                    step.output.strip(),
                    step.validation.strip(),
                    step.failureHandling.strip(),
                ]
            )
        ]
        if incomplete_steps:
            items.append(
                ValidationItem(
                    id="brief-workflow-steps-incomplete",
                    ruleId="WF-001",
                    level="blocking",
                    title="工作流步骤不完整",
                    description=f"以下步骤缺少动作、输入、输出、验证或失败处理：{', '.join(incomplete_steps)}。",
                    importance="不完整步骤会让 Agent 在执行中断档。",
                    suggestion="补齐每个步骤的目的、动作、输入、输出、验证和失败处理。",
                    blocksDownload=True,
                    field="workflow.steps",
                )
            )
        else:
            items.append(
                ValidationItem(
                    id="brief-workflow-steps-pass",
                    ruleId="WF-001",
                    level="pass",
                    title="工作流步骤完整",
                    description=f"Brief 已包含 {len(brief.workflowSteps)} 个完整步骤。",
                    importance="完整步骤让 Skill 具备可执行性和可验证性。",
                    field="workflow.steps",
                )
            )
    return items
