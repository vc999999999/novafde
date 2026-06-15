from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml
import skills_ref

from app.models import QualityIssue, SkillBrief, SkillIR, SkillSpec, ValidationItem
from app.spec_builder import required_spec_trace_items
from app.utils import ensure_safe_relative_path


AGENT_SKILLS_VALIDATOR_VERSION = "0.1.1"
VALIDATION_RULE_SET_VERSION = "2.0"


def _safe_id_component(text: str) -> str:
    """Sanitize a string for use in a validation item ID."""
    return re.sub(r'[^a-zA-Z0-9._-]', '-', text)[:64]


def validate_ir(ir: SkillIR) -> list[ValidationItem]:
    items: list[ValidationItem] = []
    if ir.schemaVersion not in {"1.0", "1.1"} or not ir.skill.name or not ir.skill.description:
        items.append(
            ValidationItem(
                id="ir-required-fields",
                ruleId="IR-001",
                level="blocking",
                title="Skill IR 必填字段不完整",
                description="Skill IR 必须包含 schemaVersion、skill.name 和 skill.description。",
                importance="后续渲染依赖稳定的中间表示。",
                suggestion="重新生成或修复 Skill IR。",
                blocksDownload=True,
                field="skill_ir",
            )
        )
    else:
        items.append(
            ValidationItem(
                id="ir-required-fields-pass",
                ruleId="IR-001",
                level="pass",
                title="Skill IR 结构完整",
                description="Skill IR 已包含渲染所需的核心字段。",
                importance="结构化 IR 能让后端确定性渲染文件。",
                field="skill_ir",
            )
        )

    if not _looks_like_trigger_description(ir.skill.description):
        items.append(
            ValidationItem(
                id="ir-trigger-description",
                ruleId="TRIG-001",
                level="blocking",
                title="description 不是触发条件",
                description="description 必须以触发条件表达，而不是 Skill 摘要。",
                importance="Agent 根据 description 判断是否启用 Skill。",
                suggestion="把 description 改成以 Use when 开头，并包含用户意图和任务对象。",
                blocksDownload=True,
                field="skill.description",
            )
        )
    else:
        items.append(
            ValidationItem(
                id="ir-trigger-description-pass",
                ruleId="TRIG-001",
                level="pass",
                title="description 是触发条件",
                description="description 使用触发条件式表述。",
                importance="触发条件式描述能帮助 Agent 正确启用 Skill。",
                field="skill.description",
            )
        )

    incomplete_steps = [
        step.id or str(index + 1)
        for index, step in enumerate(ir.workflow.steps)
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
    if not ir.workflow.steps or incomplete_steps:
        detail = (
            "Skill IR 至少需要一个工作流步骤。"
            if not ir.workflow.steps
            else f"以下工作流步骤字段不完整：{', '.join(incomplete_steps)}。"
        )
        items.append(
            ValidationItem(
                id="ir-workflow-steps",
                ruleId="WF-001",
                level="blocking",
                title="IR 工作流步骤不完整",
                description=detail,
                importance="缺失动作、输入、输出、验证或失败处理会让 Agent 执行中断。",
                suggestion="让 Skill Creator 重新生成完整的工作流步骤。",
                blocksDownload=True,
                field="workflow.steps",
            )
        )
    else:
        items.append(
            ValidationItem(
                id="ir-workflow-steps-pass",
                ruleId="WF-001",
                level="pass",
                title="IR 工作流步骤完整",
                description=f"Skill IR 包含 {len(ir.workflow.steps)} 个完整步骤。",
                importance="完整步骤保证 Skill 可执行且可验证。",
                field="workflow.steps",
            )
        )

    # Mandatory rules are optional user input. Whether user-provided rules
    # survived generation is checked against the brief in evaluate_validation.
    if ir.quality.hardRestrictions:
        items.append(
            ValidationItem(
                id="ir-mandatory-rules-pass",
                ruleId="RULE-001",
                level="pass",
                title="IR 已保留强制规则",
                description=f"Skill IR 包含 {len(ir.quality.hardRestrictions)} 条强制规则。",
                importance="强制规则会以最高优先级进入生成的 Skill。",
                field="quality.hardRestrictions",
            )
        )

    resource_path_errors = _resource_path_errors(ir)
    if resource_path_errors:
        items.append(
            ValidationItem(
                id="ir-resource-paths",
                ruleId="PKG-005",
                level="blocking",
                title="资源路径不符合 Agent Skills 目录规范",
                description="；".join(resource_path_errors),
                importance="资源必须位于 Skill 目录内的 references/、scripts/ 或 assets/，否则最终包结构会混乱。",
                suggestion="将知识文件放入 references/，脚本放入 scripts/，资产放入 assets/。",
                blocksDownload=True,
                field="contextEngineering",
            )
        )
    missing_reference_purposes = [
        item.path
        for item in ir.contextEngineering.referenceFiles
        if not item.purpose.strip()
    ]
    if missing_reference_purposes:
        items.append(
            ValidationItem(
                id="ir-reference-purpose-missing",
                ruleId="CTX-001",
                level="warning",
                title="引用资源缺少加载目的",
                description=(
                    "以下 authored reference 没有说明什么时候加载："
                    f"{'，'.join(missing_reference_purposes)}。"
                ),
                importance="引用资源需要明确加载场景，才能让执行 Agent 按需读取而不是浪费上下文。",
                suggestion="为每个 referenceFiles 项补充 purpose，说明对应流程步骤或判断场景。",
                field="contextEngineering.referenceFiles",
            )
        )
    return items


def validate_rendered_package(package_root: Path, ir: SkillIR) -> list[ValidationItem]:
    items: list[ValidationItem] = []
    skill_dir = package_root / ir.skill.name
    skill_md_path = skill_dir / "SKILL.md"
    root_entry_errors = _non_skill_root_entries(package_root, ir.skill.name)
    if root_entry_errors:
        items.append(
            ValidationItem(
                id="pkg-canonical-root",
                ruleId="PKG-004",
                level="blocking",
                title="包根目录包含非 Skill 条目",
                description=(
                    "最终 Agent Skill 包顶层只能包含一个与 frontmatter.name "
                    f"一致的 Skill 目录；发现多余条目：{', '.join(root_entry_errors)}。"
                ),
                importance="Agent Skills 规范以 Skill 文件夹为安装单元，运行时元数据不能混入用户下载包根。",
                suggestion="仅打包 <skill-name>/ 目录；将 manifest、校验报告和安装说明保存在包外元数据目录。",
                blocksDownload=True,
                field="package_root",
            )
        )

    if not skill_md_path.exists():
        items.append(
            ValidationItem(
                id="pkg-skill-md-missing",
                ruleId="PKG-001",
                level="blocking",
                title="缺少 SKILL.md",
                description="包根目录下必须存在 SKILL.md。",
                importance="Skill 文件夹没有 SKILL.md 无法被 Agent 识别。",
                suggestion="重新渲染 Skill 文件。",
                blocksDownload=True,
                field="SKILL.md",
            )
        )
        return items

    try:
        skill_md_content = skill_md_path.read_text(encoding="utf-8")
        frontmatter = parse_frontmatter(skill_md_content)
        name = frontmatter.get("name")
        description = frontmatter.get("description")
        frontmatter_ok = name == ir.skill.name and isinstance(description, str) and _looks_like_trigger_description(description)
    except (ValueError, yaml.YAMLError):
        frontmatter_ok = False

    if not frontmatter_ok:
        items.append(
            ValidationItem(
                id="pkg-skill-md-frontmatter",
                ruleId="PKG-001",
                level="blocking",
                title="SKILL.md frontmatter 不合法",
                description="SKILL.md 必须包含 name 和触发条件式 description，且 name 与目录名一致。",
                importance="frontmatter 是 Agent 判断 Skill 身份和启用时机的入口。",
                suggestion="重新渲染 SKILL.md frontmatter。",
                blocksDownload=True,
                field="SKILL.md.frontmatter",
            )
        )
    else:
        items.append(
            ValidationItem(
                id="pkg-skill-md-pass",
                ruleId="PKG-001",
                level="pass",
                title="SKILL.md frontmatter 合法",
                description="包根目录包含可解析且与目录一致的 SKILL.md。",
                importance="合法 frontmatter 是可下载包的基础结构要求。",
                field="SKILL.md",
            )
        )

    referenced_paths = [
        *ir.contextEngineering.references,
        *(item.path for item in ir.contextEngineering.referenceFiles),
        *ir.contextEngineering.scripts,
        *ir.contextEngineering.assets,
    ]
    for relative_path in referenced_paths:
        try:
            safe_path = ensure_safe_relative_path(relative_path)
        except ValueError:
            items.append(
                ValidationItem(
                    id=f"pkg-reference-unsafe-{_safe_id_component(relative_path)}",
                    ruleId="PKG-002",
                    level="blocking",
                    title="引用路径不安全",
                    description=f"IR 引用了不安全路径：{relative_path}",
                    importance="不安全路径可能导致路径穿越。",
                    suggestion="仅使用包根目录内的相对路径。",
                    blocksDownload=True,
                    field="contextEngineering",
                )
            )
            continue
        if not (skill_dir / safe_path).exists():
            items.append(
                ValidationItem(
                    id=f"pkg-reference-missing-{_safe_id_component(safe_path)}",
                    ruleId="PKG-001",
                    level="blocking",
                    title="引用文件不存在",
                    description=f"SKILL.md 或 IR 引用了不存在的文件：{safe_path}",
                    importance="缺失引用会让 Agent 加载上下文失败。",
                    suggestion="重新渲染缺失文件或移除引用。",
                    blocksDownload=True,
                    field="contextEngineering",
                )
            )

    skill_md = skill_md_content
    if len(skill_md) > 12_000:
        items.append(
            ValidationItem(
                id="pkg-skill-md-too-long",
                ruleId="PKG-003",
                level="warning",
                title="SKILL.md 过长",
                description="SKILL.md 内容较长，可能应拆分部分上下文到 references/。",
                importance="过长主文件会增加 Agent 初始上下文负担。",
                suggestion="把详细领域知识移到 references/。",
                field="SKILL.md",
            )
        )

    if not ir.workflow.failureHandling:
        items.append(
            ValidationItem(
                id="pkg-failure-handling-warning",
                ruleId="WF-003",
                level="warning",
                title="缺少失败处理",
                description="工作流没有失败处理策略。",
                importance="失败处理能让 Agent 在信息不足或验证失败时可恢复。",
                suggestion="为关键步骤添加失败处理说明。",
                field="workflow.failureHandling",
            )
        )
    items.extend(validate_official_agent_skill(package_root, ir))
    return items


def _non_skill_root_entries(package_root: Path, skill_name: str) -> list[str]:
    if not package_root.exists():
        return []
    errors: list[str] = []
    for entry in sorted(package_root.iterdir(), key=lambda item: item.name):
        if entry.name == skill_name and entry.is_dir():
            continue
        errors.append(entry.name)
    return errors


def _resource_path_errors(ir: SkillIR) -> list[str]:
    errors: list[str] = []

    def check(paths: list[str], prefix: str, field: str) -> None:
        for raw_path in paths:
            try:
                safe_path = ensure_safe_relative_path(raw_path)
            except ValueError:
                errors.append(f"{field} 包含不安全路径：{raw_path}")
                continue
            if safe_path == prefix.rstrip("/") or not safe_path.startswith(prefix):
                errors.append(f"{field} 必须位于 {prefix} 下：{safe_path}")

    check(ir.contextEngineering.references, "references/", "references")
    check(
        [item.path for item in ir.contextEngineering.referenceFiles],
        "references/",
        "referenceFiles",
    )
    check(ir.contextEngineering.scripts, "scripts/", "scripts")
    check(ir.contextEngineering.assets, "assets/", "assets")
    return errors


def validate_official_agent_skill(
    package_root: Path,
    ir: SkillIR,
) -> list[ValidationItem]:
    installed_version = getattr(skills_ref, "__version__", "unknown")
    if installed_version != AGENT_SKILLS_VALIDATOR_VERSION:
        errors = [
            "skills-ref 版本不一致："
            f"期望 {AGENT_SKILLS_VALIDATOR_VERSION}，实际 {installed_version}。"
        ]
    else:
        errors = skills_ref.validate(package_root / ir.skill.name)
    if errors:
        return [
            ValidationItem(
                id="official-agent-skills-validation",
                ruleId="AGENT-SKILLS-001",
                level="blocking",
                title="官方 Agent Skills 校验失败",
                description="；".join(errors),
                importance="官方校验器定义了 Skill 包可被兼容运行时识别的基础规范。",
                suggestion="修复目录名、frontmatter 字段、名称或 description 后重新渲染。",
                blocksDownload=True,
                field=f"{ir.skill.name}/SKILL.md",
            )
        ]
    return [
        ValidationItem(
            id="official-agent-skills-validation-pass",
            ruleId="AGENT-SKILLS-001",
            level="pass",
            title="官方 Agent Skills 校验通过",
            description=(
                f"skills-ref {AGENT_SKILLS_VALIDATOR_VERSION} 已接受该 Skill 包。"
            ),
            importance="官方校验通过可降低跨运行时安装失败风险。",
            field=f"{ir.skill.name}/SKILL.md",
        )
    ]


def validate_spec_compliance(
    package_root: Path,
    ir: SkillIR,
    spec: SkillSpec,
) -> list[ValidationItem]:
    items: list[ValidationItem] = []
    if ir.schemaVersion != "1.1":
        items.append(
            _spec_blocker(
                "spec-ir-version",
                "SPEC-001",
                "SkillIR 未使用 SDD 追踪版本",
                "带 SkillSpec 的生成必须使用 SkillIR 1.1。",
                "schemaVersion",
            )
        )

    if ir.quality.hardRestrictions != spec.hardRestrictions:
        items.append(
            _spec_blocker(
                "spec-hard-restrictions",
                "SPEC-RULE-001",
                "权威硬限制不一致",
                "SkillIR.hardRestrictions 必须与当前 SkillSpec 原文、顺序完全一致。",
                "quality.hardRestrictions",
                spec_item_ids=[
                    restriction.id for restriction in spec.restrictionItems
                ],
            )
        )

    required = {
        item.specItemId: item
        for item in required_spec_trace_items(spec)
    }
    traces: dict[str, Any] = {}
    duplicate_ids: set[str] = set()
    for trace in ir.specTrace:
        if trace.specItemId in traces:
            duplicate_ids.add(trace.specItemId)
        traces[trace.specItemId] = trace
    missing_ids = sorted(set(required) - set(traces))
    if missing_ids or duplicate_ids:
        details = []
        if missing_ids:
            details.append(f"缺少：{', '.join(missing_ids)}")
        if duplicate_ids:
            details.append(f"重复：{', '.join(sorted(duplicate_ids))}")
        items.append(
            _spec_blocker(
                "spec-trace-coverage",
                "SPEC-TRACE-001",
                "Spec Trace 覆盖不完整",
                "；".join(details),
                "specTrace",
                spec_item_ids=[*missing_ids, *sorted(duplicate_ids)],
            )
        )

    payload = ir.model_dump(mode="json")
    invalid_details: list[str] = []
    invalid_ids: dict[str, None] = {}
    distinct_paths: dict[str, str] = {}

    def flag_invalid(spec_item_id: str, message: str) -> None:
        invalid_details.append(f"{spec_item_id}: {message}")
        invalid_ids[spec_item_id] = None

    for spec_item_id, requirement in required.items():
        trace = traces.get(spec_item_id)
        if trace is None:
            continue
        if not trace.irPaths or not trace.renderedPaths:
            flag_invalid(spec_item_id, "映射路径为空")
            continue
        matching_values: list[Any] = []
        for ir_path in trace.irPaths:
            allowed_prefixes = (
                requirement.irPathPrefix,
                *requirement.alternateIrPathPrefixes,
            )
            if not any(
                _matches_prefix(ir_path, prefix)
                for prefix in allowed_prefixes
            ):
                flag_invalid(
                    spec_item_id,
                    f"{ir_path} 不属于 {' 或 '.join(allowed_prefixes)}",
                )
                continue
            try:
                value = _resolve_ir_path(payload, ir_path)
            except (KeyError, IndexError, TypeError, ValueError):
                flag_invalid(spec_item_id, f"IR 路径无效 {ir_path}")
                continue
            if not _has_content(value):
                flag_invalid(spec_item_id, f"IR 路径内容为空 {ir_path}")
                continue
            matching_values.append(value)
            if requirement.requiresDistinctPath:
                owner = distinct_paths.setdefault(ir_path, spec_item_id)
                if owner != spec_item_id:
                    flag_invalid(spec_item_id, f"与 {owner} 复用了 {ir_path}")
        if matching_values and requirement.expectedValue is not None and not any(
            _contains_expected(value, requirement.expectedValue)
            for value in matching_values
        ):
            flag_invalid(spec_item_id, "规格原文未在映射内容中实现")
        for rendered_path in trace.renderedPaths:
            try:
                safe_path = ensure_safe_relative_path(rendered_path)
            except ValueError:
                flag_invalid(
                    spec_item_id, f"最终文件路径不安全 {rendered_path}"
                )
                continue
            if not (package_root / safe_path).is_file():
                flag_invalid(
                    spec_item_id, f"最终文件不存在 {rendered_path}"
                )

    if invalid_details:
        items.append(
            _spec_blocker(
                "spec-trace-invalid-paths",
                "SPEC-TRACE-002",
                "Spec Trace 映射无效",
                "；".join(invalid_details),
                "specTrace",
                spec_item_ids=list(invalid_ids),
            )
        )

    if not [item for item in items if item.level == "blocking"]:
        items.append(
            ValidationItem(
                id="spec-compliance-pass",
                ruleId="SPEC-001",
                level="pass",
                title="SkillSpec 一致性校验通过",
                description=f"{len(required)} 个必需规格条目均已映射到 IR 和最终文件。",
                importance="可追踪规格确保生成结果没有静默遗漏用户要求。",
                field="specTrace",
            )
        )
    return items


def _spec_blocker(
    item_id: str,
    rule_id: str,
    title: str,
    description: str,
    field: str,
    *,
    spec_item_ids: list[str] | None = None,
) -> ValidationItem:
    return ValidationItem(
        id=item_id,
        ruleId=rule_id,
        level="blocking",
        title=title,
        description=description,
        importance="SkillSpec 是当前生成不可修改的交付契约。",
        suggestion="让 Skill Creator 或 Repair Agent 补全映射，不得修改 SkillSpec。",
        blocksDownload=True,
        field=field,
        specItemIds=list(spec_item_ids or []),
    )


def _matches_prefix(path: str, prefix: str) -> bool:
    return path == prefix or path.startswith(f"{prefix}.") or path.startswith(
        f"{prefix}["
    )


_IR_PATH_SEGMENT = re.compile(r"([A-Za-z_][A-Za-z0-9_]*)(?:\[(\d+)\])?")


def _resolve_ir_path(payload: Any, path: str) -> Any:
    current = payload
    for raw_segment in path.split("."):
        match = _IR_PATH_SEGMENT.fullmatch(raw_segment)
        if match is None:
            raise ValueError(path)
        key, index = match.groups()
        if not isinstance(current, dict):
            raise TypeError(path)
        current = current[key]
        if index is not None:
            if not isinstance(current, list):
                raise TypeError(path)
            current = current[int(index)]
    return current


def _has_content(value: Any) -> bool:
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, dict)):
        return bool(value)
    return value is not None


def _contains_expected(value: Any, expected: Any) -> bool:
    if value == expected:
        return True
    if isinstance(value, list):
        return expected in value
    if isinstance(value, dict) and isinstance(expected, str):
        return expected in value.values()
    return False


def parse_frontmatter(markdown: str) -> dict:
    normalized = markdown.replace("\r\n", "\n")
    if not normalized.startswith("---\n"):
        raise ValueError("missing frontmatter")
    parts = normalized.split("---\n", 2)
    if len(parts) < 3:
        raise ValueError("unterminated frontmatter")
    data = yaml.safe_load(parts[1]) or {}
    if not isinstance(data, dict):
        raise ValueError("frontmatter must be a mapping")
    return data


_ENGLISH_TRIGGER_PATTERNS = [
    re.compile(r"\buse\b[^.!?]{0,80}?\bwhen\b"),
    re.compile(r"\bwhen\s+(the\s+|a\s+|an\s+)?(user|users|you|team|developer|request)"),
    re.compile(r"\btrigger(s|ed)?\b"),
    re.compile(r"\buse\s+(this\s+skill\s+|it\s+)?for\b"),
    re.compile(r"\bapplies\s+when\b"),
]
_CJK_TRIGGER_MARKERS = [
    "当用户",
    "当需要",
    "用户需要",
    "用户想要",
    "用户希望",
    "适用于",
    "时使用",
    "时启用",
    "时触发",
    "用于",
]


def _looks_like_trigger_description(description: str) -> bool:
    """Accept a description that contains trigger language anywhere.

    The official recommended structure is "what the skill does + when to use
    it", so the trigger phrase is allowed to follow a summary sentence instead
    of being forced to the start.
    """
    text = description.strip()
    if not text:
        return False
    lowered = text.lower()
    has_cjk = any("一" <= ch <= "鿿" for ch in text)
    if has_cjk:
        return len(text) >= 10 and any(marker in text for marker in _CJK_TRIGGER_MARKERS)
    if len(lowered.split()) < 5:
        return False
    return any(pattern.search(lowered) for pattern in _ENGLISH_TRIGGER_PATTERNS)


def blocking_count(items: list[ValidationItem]) -> int:
    return sum(1 for item in items if item.level == "blocking")


def warning_count(items: list[ValidationItem]) -> int:
    return sum(1 for item in items if item.level == "warning")


def evaluate_validation(
    package_root: Path,
    ir: SkillIR,
    brief: SkillBrief,
    spec: SkillSpec | None = None,
) -> tuple[list[ValidationItem], list[QualityIssue], float]:
    items = [*validate_ir(ir), *validate_rendered_package(package_root, ir)]
    if spec is not None:
        items.extend(validate_spec_compliance(package_root, ir, spec))
    if brief.professionalInformation and not ir.agentKnowledge.unknownKnowledge:
        items.append(
            ValidationItem(
                id="professional-information-lost",
                ruleId="KNOW-001",
                level="blocking",
                title="用户专业信息在生成中丢失",
                description="SkillBrief 提供了专业信息，但 Skill IR 中没有任何领域知识。",
                importance="用户知识可以被改写和扩充，但不允许整体丢失。",
                suggestion="把用户专业信息整理进 agentKnowledge 与 references。",
                blocksDownload=True,
                field="agentKnowledge.unknownKnowledge",
            )
        )
    if brief.pitfalls and not ir.agentKnowledge.pitfalls:
        items.append(
            ValidationItem(
                id="pitfalls-lost",
                ruleId="KNOW-002",
                level="blocking",
                title="用户提供的反例在生成中丢失",
                description="SkillBrief 提供了常见错误或反例，但 Skill IR 中没有任何 pitfall。",
                importance="用户经验定义了 Skill 需要规避的错误边界，不允许整体丢失。",
                suggestion="恢复或改写用户提供的 pitfalls。",
                blocksDownload=True,
                field="agentKnowledge.pitfalls",
            )
        )
    missing_rules = [
        rule for rule in brief.mandatoryRules if rule not in ir.quality.hardRestrictions
    ]
    if missing_rules:
        items.append(
            ValidationItem(
                id="mandatory-rules-lost",
                ruleId="RULE-001",
                level="blocking",
                title="用户强制规则在生成中丢失",
                description=f"缺少规则：{'；'.join(missing_rules)}",
                importance="用户强制规则必须完整保留。",
                suggestion="恢复原始 SkillBrief 中的强制规则。",
                blocksDownload=True,
                field="quality.hardRestrictions",
            )
        )

    model_added_rules = getattr(ir, "_model_added_hard_restrictions", [])
    if model_added_rules:
        items.append(
            ValidationItem(
                id="model-added-hard-restrictions",
                ruleId="RULE-002",
                level="warning",
                title="模型新增硬限制已被降级",
                description=(
                    "以下非权威硬限制已从 hardRestrictions 移除并转入软性指导："
                    f"{'；'.join(model_added_rules)}"
                ),
                importance="业务硬限制只能来自用户，系统硬限制只能来自确定性基线。",
                suggestion="如确需成为硬限制，请由用户明确补充并创建新的 SkillSpec 修订。",
                field="quality.hardRestrictions",
            )
        )

    skill_md_path = package_root / ir.skill.name / "SKILL.md"
    if skill_md_path.exists():
        line_count = len(skill_md_path.read_text(encoding="utf-8").splitlines())
        if line_count > 500:
            items.append(
                ValidationItem(
                    id="skill-md-line-count",
                    ruleId="PKG-003",
                    level="warning",
                    title="SKILL.md 超过 500 行",
                    description=f"当前 SKILL.md 共 {line_count} 行。",
                    importance="过长主文件会增加初始上下文负担。",
                    suggestion="将详细知识下沉到 references/。",
                    field="SKILL.md",
                )
            )
    if len(ir.skill.description) > 1024:
        items.append(
            ValidationItem(
                id="description-too-long",
                ruleId="TRIG-002",
                level="blocking",
                title="description 超过长度限制",
                description="frontmatter.description 不得超过 1024 个字符。",
                importance="描述必须保持可发现且符合 Skill 规范。",
                suggestion="保留触发条件并删除实现细节。",
                blocksDownload=True,
                field="skill.description",
            )
        )

    issues = [
        _quality_issue_from_validation(item, ir=ir, spec=spec)
        for item in items
        if item.level != "pass"
    ]
    blocker_count = sum(
        issue.severity in {"security_blocker", "structure_blocker"}
        for issue in issues
    )
    warning_total = sum(issue.severity == "warning" for issue in issues)
    score = max(0.0, 100.0 - blocker_count * 40.0 - warning_total * 5.0)
    return items, issues, score


def _quality_issue_from_validation(
    item: ValidationItem,
    *,
    ir: SkillIR | None = None,
    spec: SkillSpec | None = None,
) -> QualityIssue:
    if item.level == "blocking":
        severity = "security_blocker" if item.ruleId == "PKG-002" else "structure_blocker"
    else:
        severity = "warning"
    return QualityIssue(
        issueId=item.id,
        source="validation",
        criterion=item.ruleId,
        severity=severity,
        reason=item.description,
        evidence=[item.field] if item.field else [],
        suggestion=item.suggestion,
        affectedPaths=[item.field] if item.field else [],
        autoFixable=item.ruleId in {"TRIG-001", "PKG-001"},
        specItemIds=_spec_item_ids_for_issue(item, ir, spec),
    )


def _spec_item_ids_for_issue(
    item: ValidationItem,
    ir: SkillIR | None,
    spec: SkillSpec | None,
) -> list[str]:
    if spec is None or not item.ruleId.startswith("SPEC-"):
        return []
    if item.specItemIds:
        return list(item.specItemIds)
    return [
        requirement.specItemId
        for requirement in required_spec_trace_items(spec)
    ]
