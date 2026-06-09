from __future__ import annotations

import json
import shutil
from pathlib import Path

import yaml

from app.models import FileNode, SkillIR
from app.utils import ensure_safe_relative_path, format_size


def render_skill_package(ir: SkillIR, package_root: Path) -> Path:
    if package_root.exists():
        shutil.rmtree(package_root)
    skill_dir = package_root / ir.skill.name
    (skill_dir / "references").mkdir(parents=True, exist_ok=True)
    (skill_dir / "scripts").mkdir(parents=True, exist_ok=True)
    (skill_dir / "assets").mkdir(parents=True, exist_ok=True)

    _write_skill_md(skill_dir / "SKILL.md", ir)
    for relative_path in ir.contextEngineering.references:
        _write_reference(skill_dir / ensure_safe_relative_path(relative_path), ir)
    for relative_path in ir.contextEngineering.scripts:
        _write_script_readme(skill_dir / ensure_safe_relative_path(relative_path))
    for relative_path in ir.contextEngineering.assets:
        _write_asset_template(skill_dir / ensure_safe_relative_path(relative_path), ir)
    return skill_dir


def build_file_tree(root: Path) -> list[FileNode]:
    def node_for(path: Path) -> FileNode:
        if path.is_dir():
            children = [node_for(child) for child in sorted(path.iterdir(), key=_tree_sort_key)]
            return FileNode(name=path.name, type="folder", children=children)
        return FileNode(name=path.name, type="file", size=format_size(path.stat().st_size))

    return [node_for(child) for child in sorted(root.iterdir(), key=_tree_sort_key)]


def _tree_sort_key(path: Path) -> tuple[bool, bool, str]:
    return (path.is_file(), path.name == "install", path.name)


def _write_skill_md(path: Path, ir: SkillIR) -> None:
    frontmatter = yaml.safe_dump(
        {"name": ir.skill.name, "description": ir.skill.description},
        allow_unicode=True,
        sort_keys=False,
    ).strip()
    lines = [
        "---",
        frontmatter,
        "---",
        "",
        f"# {ir.skill.name}",
        "",
        "## SKILL.md Scope",
        "",
        "This SKILL.md contains the core trigger, workflow, context navigation, and validation rules for the Skill package.",
        "",
        "## When to Use",
        "",
        ir.skill.description,
        "",
        "## Workflow",
        "",
        f"**Objective:** {ir.workflow.objective}",
        "",
    ]
    for index, step in enumerate(ir.workflow.steps, start=1):
        lines.extend(
            [
                f"### Step {index}: {step.purpose}",
                "",
                f"- **Action:** {step.action}",
                f"- **Input:** {step.input}",
                f"- **Output:** {step.output}",
                f"- **Verification:** {step.validation}",
                f"- **Failure handling:** {step.failureHandling}",
                "",
            ]
        )

    lines.extend(["## Context Loading", ""])
    for assumption in ir.contextEngineering.filesystemAssumptions:
        lines.append(f"- {assumption}")
    if ir.contextEngineering.references:
        lines.append("- Load `references/domain-knowledge.md` when domain rules, examples, or pitfalls are needed.")
    if ir.contextEngineering.scripts:
        lines.append("- Scripts are optional helpers and must be reviewed before execution.")
    if ir.contextEngineering.assets:
        lines.append("- Assets contain templates or examples referenced by the workflow.")
    lines.append("")

    if ir.agentKnowledge.unknownKnowledge:
        lines.extend(["## Domain Knowledge", ""])
        lines.append("Detailed domain knowledge is stored in `references/domain-knowledge.md`.")
        lines.append("")

    if ir.agentKnowledge.pitfalls:
        lines.extend(["## Pitfalls", ""])
        for pitfall in ir.agentKnowledge.pitfalls:
            lines.extend(
                [
                    f"- **Avoid:** {pitfall.description}",
                    f"  - Good: {pitfall.goodExample}",
                    f"  - Bad: {pitfall.badExample}",
                ]
            )
        lines.append("")

    lines.extend(["## Verification Checklist", ""])
    checklist = ir.quality.validationChecklist or ir.workflow.verification
    for item in checklist:
        lines.append(f"- {item}")
    lines.append("")

    lines.extend(["## Platform Notes", ""])
    lines.append("Use the generated files under `install/` for platform-specific installation paths.")
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def _write_reference(path: Path, ir: SkillIR) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["# Domain Knowledge", ""]
    if ir.agentKnowledge.unknownKnowledge:
        lines.append("## Rules and Experience")
        lines.extend(f"- {item}" for item in ir.agentKnowledge.unknownKnowledge)
        lines.append("")
    if ir.agentKnowledge.examples:
        lines.append("## Positive Examples")
        lines.extend(f"- {item}" for item in ir.agentKnowledge.examples)
        lines.append("")
    if ir.agentKnowledge.counterExamples:
        lines.append("## Counter Examples")
        lines.extend(f"- {item}" for item in ir.agentKnowledge.counterExamples)
        lines.append("")
    if ir.agentKnowledge.pitfalls:
        lines.append("## Pitfalls")
        for pitfall in ir.agentKnowledge.pitfalls:
            lines.extend(
                [
                    f"### {pitfall.description or pitfall.id}",
                    "",
                    f"- Good example: {pitfall.goodExample}",
                    f"- Bad example: {pitfall.badExample}",
                    "",
                ]
            )
    path.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")


def _write_script_readme(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "# Scripts\n\nNo executable helper is generated by default. Add scripts only when stable, repeatable logic is needed and review before running them.\n",
        encoding="utf-8",
    )


def _write_asset_template(path: Path, ir: SkillIR) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "skill": ir.skill.name,
        "workflowObjective": ir.workflow.objective,
        "steps": [step.model_dump(mode="json") for step in ir.workflow.steps],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
