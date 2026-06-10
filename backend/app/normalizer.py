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
    items: list[ValidationItem] = []
    _required_text(
        items,
        value=brief.displayName,
        item_id="brief-display-name",
        rule_id="NAME-001",
        title="缺少 Skill 名称",
        description="生成前必须填写用户可识别的 Skill 名称。",
        importance="名称用于草稿识别、文件夹命名和生成结果展示。",
        suggestion="填写一个简洁、明确的 Skill 名称。",
        field="displayName",
    )
    _required_text(
        items,
        value=brief.usage,
        item_id="brief-purpose-usage",
        rule_id="PURPOSE-001",
        title="缺少使用时机",
        description="生成前必须说明用户什么时候需要使用这个 Skill。",
        importance="使用时机会由 Skill Creator 转换为 frontmatter description 的触发条件。",
        suggestion="说明典型任务或用户意图，例如“当产品团队需要系统化完成竞品调研时使用”。",
        field="purpose.usage",
    )
    _required_text(
        items,
        value=brief.desiredOutcome,
        item_id="brief-purpose-outcome",
        rule_id="PURPOSE-002",
        title="缺少目标结果",
        description="生成前必须说明这个 Skill 最终要得到什么结果。",
        importance="目标结果决定工作流的方向和最终产物。",
        suggestion="补充清晰、可观察的最终结果。",
        field="purpose.desiredOutcome",
    )
    _required_list(
        items,
        values=brief.roughProcess,
        item_id="brief-process",
        rule_id="PROCESS-001",
        title="缺少大致执行流程",
        description="生成前至少需要一条用户认可的大致执行流程。",
        importance="Skill Creator 会以此为业务事实，扩展为完整的 Agent 工作流。",
        suggestion="按顺序写出主要阶段，不需要填写逐步输入、输出或失败处理。",
        field="purpose.process",
    )
    _required_text(
        items,
        value=brief.completionCriteria,
        item_id="brief-completion-criteria",
        rule_id="PROCESS-002",
        title="缺少完成标准",
        description="生成前必须说明怎样才算完成。",
        importance="完成标准会成为工作流验证和质量门槛。",
        suggestion="补充可判断的验收条件。",
        field="purpose.completionCriteria",
    )
    _required_list(
        items,
        values=brief.professionalInformation,
        item_id="brief-professional-information",
        rule_id="KNOW-001",
        title="缺少专业信息",
        description="生成前必须提供 Agent 需要知道的专业信息、业务经验或领域知识。",
        importance="这些信息是 Skill 相对于通用 Agent 的核心增量。",
        suggestion="补充领域概念、业务经验、内部流程或判断依据。",
        field="knowledge.professionalInformation",
    )
    _required_list(
        items,
        values=brief.mandatoryRules,
        item_id="brief-mandatory-rules",
        rule_id="RULE-001",
        title="缺少必须遵守的规则",
        description="生成前必须明确至少一条不可被其他输入覆盖的强制规则。",
        importance="强制规则拥有最高优先级，并会进入 Skill 的硬性约束。",
        suggestion="补充 Agent 在任何情况下都必须遵守的规则。",
        field="knowledge.mandatoryRules",
    )
    _required_list(
        items,
        values=brief.pitfalls,
        item_id="brief-pitfalls",
        rule_id="KNOW-002",
        title="缺少常见错误或反例",
        description="生成前必须由用户提供至少一个常见错误、反例或错误结果。",
        importance="用户经验定义了 Skill 真正需要规避的错误边界。",
        suggestion="添加错误描述、正确做法和错误示例。",
        field="knowledge.pitfalls",
    )
    return items


def _required_text(
    items: list[ValidationItem],
    *,
    value: str,
    item_id: str,
    rule_id: str,
    title: str,
    description: str,
    importance: str,
    suggestion: str,
    field: str,
) -> None:
    _append_required_result(
        items,
        present=bool(value.strip()),
        item_id=item_id,
        rule_id=rule_id,
        title=title,
        description=description,
        importance=importance,
        suggestion=suggestion,
        field=field,
    )


def _required_list(
    items: list[ValidationItem],
    *,
    values: list[object],
    item_id: str,
    rule_id: str,
    title: str,
    description: str,
    importance: str,
    suggestion: str,
    field: str,
) -> None:
    _append_required_result(
        items,
        present=bool(values),
        item_id=item_id,
        rule_id=rule_id,
        title=title,
        description=description,
        importance=importance,
        suggestion=suggestion,
        field=field,
    )


def _append_required_result(
    items: list[ValidationItem],
    *,
    present: bool,
    item_id: str,
    rule_id: str,
    title: str,
    description: str,
    importance: str,
    suggestion: str,
    field: str,
) -> None:
    items.append(
        ValidationItem(
            id=f"{item_id}-pass" if present else item_id,
            ruleId=rule_id,
            level="pass" if present else "blocking",
            title=f"{title.removeprefix('缺少')}已提供" if present else title,
            description=description if not present else f"{field} 已包含生成所需信息。",
            importance=importance,
            suggestion="" if present else suggestion,
            blocksDownload=not present,
            field=field,
            inputLayer="required",
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
