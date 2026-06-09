from __future__ import annotations

from pathlib import Path

import yaml

from app.models import SkillIR, ValidationItem
from app.utils import ensure_safe_relative_path


def validate_ir(ir: SkillIR) -> list[ValidationItem]:
    items: list[ValidationItem] = []
    if ir.schemaVersion != "1.0" or not ir.skill.name or not ir.skill.description:
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

    if not ir.workflow.steps:
        items.append(
            ValidationItem(
                id="ir-workflow-steps",
                ruleId="WF-001",
                level="blocking",
                title="IR 缺少工作流步骤",
                description="Skill IR 至少需要一个工作流步骤。",
                importance="没有步骤的 Skill 无法指导 Agent 执行流程。",
                suggestion="重新生成包含步骤的 Skill IR。",
                blocksDownload=True,
                field="workflow.steps",
            )
        )
    return items


def validate_rendered_package(package_root: Path, ir: SkillIR) -> list[ValidationItem]:
    items: list[ValidationItem] = []
    skill_dir = package_root / ir.skill.name
    skill_md_path = skill_dir / "SKILL.md"

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
        frontmatter = parse_frontmatter(skill_md_path.read_text(encoding="utf-8"))
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
        *ir.contextEngineering.scripts,
        *ir.contextEngineering.assets,
    ]
    for relative_path in referenced_paths:
        try:
            safe_path = ensure_safe_relative_path(relative_path)
        except ValueError:
            items.append(
                ValidationItem(
                    id=f"pkg-reference-unsafe-{relative_path}",
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
                    id=f"pkg-reference-missing-{safe_path}",
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

    skill_md = skill_md_path.read_text(encoding="utf-8")
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
    return items


def parse_frontmatter(markdown: str) -> dict:
    if not markdown.startswith("---\n"):
        raise ValueError("missing frontmatter")
    parts = markdown.split("---", 2)
    if len(parts) < 3:
        raise ValueError("unterminated frontmatter")
    data = yaml.safe_load(parts[1]) or {}
    if not isinstance(data, dict):
        raise ValueError("frontmatter must be a mapping")
    return data


def _looks_like_trigger_description(description: str) -> bool:
    lowered = description.strip().lower()
    return lowered.startswith("use when") and len(lowered.split()) >= 5


def blocking_count(items: list[ValidationItem]) -> int:
    return sum(1 for item in items if item.level == "blocking")


def warning_count(items: list[ValidationItem]) -> int:
    return sum(1 for item in items if item.level == "warning")
