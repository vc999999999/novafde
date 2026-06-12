from __future__ import annotations

from app.models import SkillBrief, SkillDraft, ValidationItem
from app.utils import sanitize_skill_name


def normalize_draft(draft: SkillDraft) -> tuple[SkillBrief, list[ValidationItem]]:
    purpose = draft.purpose
    knowledge = draft.knowledge
    process = _clean_list(purpose.process)
    professional_information = _clean_list(knowledge.professionalInformation)
    mandatory_rules = _clean_list(knowledge.mandatoryRules)
    related_skills = _clean_list(knowledge.relatedSkills)
    pitfalls = [
        pitfall
        for pitfall in knowledge.pitfalls
        if all(
            [
                pitfall.description.strip(),
                pitfall.goodExample.strip(),
                pitfall.badExample.strip(),
            ]
        )
    ]
    supplement = draft.supplement.content.strip()
    all_text = "\n".join(
        [
            purpose.usage,
            purpose.desiredOutcome,
            *process,
            purpose.completionCriteria,
            purpose.specialCases,
            *professional_information,
            *mandatory_rules,
            supplement,
        ]
    )

    brief = SkillBrief(
        skillName=sanitize_skill_name(draft.name or draft.displayName),
        displayName=draft.displayName.strip(),
        usage=purpose.usage.strip(),
        desiredOutcome=purpose.desiredOutcome.strip(),
        roughProcess=process,
        completionCriteria=purpose.completionCriteria.strip(),
        specialCases=purpose.specialCases.strip(),
        professionalInformation=professional_information,
        mandatoryRules=mandatory_rules,
        pitfalls=pitfalls,
        relatedSkills=related_skills,
        supplementalContext=supplement,
        targetPlatforms=draft.targetPlatforms,
        outputLanguage=_infer_output_language(all_text),
        needsReferences=bool(
            professional_information
            or mandatory_rules
            or pitfalls
            or related_skills
            or supplement
        ),
        needsScripts=_contains_any(
            all_text,
            ["脚本", "自动化", "命令行", "批量处理", "script", "automation", "command"],
        ),
        needsAssets=_contains_any(
            all_text,
            ["模板", "样例文件", "示例文件", "素材", "template", "sample file", "asset"],
        ),
    )
    return brief, validate_brief(brief)


def validate_brief(brief: SkillBrief) -> list[ValidationItem]:
    """Validate the normalized brief.

    Only identity and intent fields block generation. Knowledge fields
    (professional information, mandatory rules, pitfalls) and the completion
    criteria are recommended: missing values surface as warnings, the model
    derives what it can, and the quality loop asks the user mid-run when a
    user-specific fact is genuinely required (awaiting_user_input).
    """
    items: list[ValidationItem] = []
    _check_field(
        items,
        present=bool(brief.displayName.strip()),
        required=True,
        item_id="brief-display-name",
        rule_id="NAME-001",
        subject="Skill 名称",
        description="生成前必须填写用户可识别的 Skill 名称。",
        importance="名称用于草稿识别、文件夹命名和生成结果展示。",
        suggestion="填写一个简洁、明确的 Skill 名称。",
        field="displayName",
    )
    _check_field(
        items,
        present=bool(brief.usage.strip()),
        required=True,
        item_id="brief-purpose-usage",
        rule_id="PURPOSE-001",
        subject="使用时机",
        description="生成前必须说明用户什么时候需要使用这个 Skill。",
        importance="使用时机会由 Skill Creator 转换为 frontmatter description 的触发条件。",
        suggestion="说明典型任务或用户意图，例如“当产品团队需要系统化完成竞品调研时使用”。",
        field="purpose.usage",
    )
    _check_field(
        items,
        present=bool(brief.desiredOutcome.strip()),
        required=True,
        item_id="brief-purpose-outcome",
        rule_id="PURPOSE-002",
        subject="目标结果",
        description="生成前必须说明这个 Skill 最终要得到什么结果。",
        importance="目标结果决定工作流的方向和最终产物。",
        suggestion="补充清晰、可观察的最终结果。",
        field="purpose.desiredOutcome",
    )
    _check_field(
        items,
        present=bool(brief.roughProcess),
        required=False,
        item_id="brief-process",
        rule_id="PROCESS-001",
        subject="大致执行流程",
        description="未提供大致执行流程，系统会根据使用场景和目标结果推导标准工作流。",
        importance="用户流程会提升业务贴合度；留空时系统仅生成安全的通用执行阶段。",
        suggestion="如有明确业务步骤，可按顺序补充主要阶段。",
        field="purpose.process",
    )
    _check_field(
        items,
        present=bool(brief.completionCriteria.strip()),
        required=False,
        item_id="brief-completion-criteria",
        rule_id="PROCESS-002",
        subject="完成标准",
        description="未提供完成标准，Skill Creator 会自行推导，评测发现缺口时会在生成中向你确认。",
        importance="完成标准会成为工作流验证和质量门槛，填写后生成质量更稳定。",
        suggestion="补充可判断的验收条件。",
        field="purpose.completionCriteria",
    )
    _check_field(
        items,
        present=bool(brief.professionalInformation),
        required=False,
        item_id="brief-professional-information",
        rule_id="KNOW-001",
        subject="专业信息",
        description="未提供专业信息。纯流程型 Skill 可以不填；有领域知识时填写能显著提升质量。",
        importance="专业信息是 Skill 相对于通用 Agent 的核心增量。",
        suggestion="补充领域概念、业务经验、内部流程或判断依据。",
        field="knowledge.professionalInformation",
    )
    _check_field(
        items,
        present=bool(brief.mandatoryRules),
        required=False,
        item_id="brief-mandatory-rules",
        rule_id="RULE-001",
        subject="必须遵守的规则",
        description="未提供强制规则。只在确有不可违反的业务约束时填写，不要为了凑数编写规则。",
        importance="强制规则拥有最高优先级，会原样进入 Skill 的硬性约束。",
        suggestion="补充 Agent 在任何情况下都必须遵守的规则。",
        field="knowledge.mandatoryRules",
    )
    _check_field(
        items,
        present=bool(brief.pitfalls),
        required=False,
        item_id="brief-pitfalls",
        rule_id="KNOW-002",
        subject="常见错误或反例",
        description="未提供常见错误或反例。踩过坑后再补充即可，填写能帮 Skill 规避真实的错误边界。",
        importance="用户经验定义了 Skill 真正需要规避的错误边界。",
        suggestion="添加错误描述、正确做法和错误示例。",
        field="knowledge.pitfalls",
    )
    return items


def _check_field(
    items: list[ValidationItem],
    *,
    present: bool,
    required: bool,
    item_id: str,
    rule_id: str,
    subject: str,
    description: str,
    importance: str,
    suggestion: str,
    field: str,
) -> None:
    if present:
        items.append(
            ValidationItem(
                id=f"{item_id}-pass",
                ruleId=rule_id,
                level="pass",
                title=f"{subject}已提供",
                description=f"{field} 已包含生成所需信息。",
                importance=importance,
                field=field,
                inputLayer="required" if required else "advanced",
            )
        )
        return
    items.append(
        ValidationItem(
            id=item_id,
            ruleId=rule_id,
            level="blocking" if required else "warning",
            title=f"缺少{subject}" if required else f"建议补充{subject}",
            description=description,
            importance=importance,
            suggestion=suggestion,
            blocksDownload=required,
            field=field,
            inputLayer="required" if required else "advanced",
        )
    )


def _clean_list(values: list[str]) -> list[str]:
    return [item.strip() for item in values if item.strip()]


def _contains_any(text: str, keywords: list[str]) -> bool:
    lowered = text.lower()
    return any(keyword.lower() in lowered for keyword in keywords)


def _infer_output_language(text: str) -> str:
    for character in text:
        if (
            "\u4e00" <= character <= "\u9fff"     # CJK Unified Ideographs
            or "\u3400" <= character <= "\u4dbf"   # CJK Extension A
            or "\u3040" <= character <= "\u309f"   # Hiragana
            or "\u30a0" <= character <= "\u30ff"   # Katakana
        ):
            return "zh-CN"
    return "en"
