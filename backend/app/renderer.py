from __future__ import annotations

import json
import shutil
from pathlib import Path

import yaml

from app.models import FileNode, ReferenceFile, SkillIR
from app.utils import ensure_safe_relative_path, format_size


RENDERER_VERSION = "1.1"


def render_skill_package(ir: SkillIR, package_root: Path) -> Path:
    if package_root.exists():
        # Safety: refuse to remove root-like paths or suspiciously short paths
        if len(package_root.parts) < 3:
            raise ValueError(f"Refusing to remove suspicious path: {package_root}")
        shutil.rmtree(package_root)
    skill_dir = package_root / ir.skill.name
    skill_dir.mkdir(parents=True, exist_ok=True)

    _write_skill_md(skill_dir / "SKILL.md", ir)
    authored_files = [
        (ensure_safe_relative_path(item.path), item)
        for item in ir.contextEngineering.referenceFiles
    ]
    reference_paths = [
        ensure_safe_relative_path(path) for path in ir.contextEngineering.references
    ]
    script_paths = [
        ensure_safe_relative_path(path) for path in ir.contextEngineering.scripts
    ]
    asset_paths = [
        ensure_safe_relative_path(path) for path in ir.contextEngineering.assets
    ]
    planned = {
        *(path for path, _ in authored_files),
        *reference_paths,
        *script_paths,
        *asset_paths,
    }

    authored_paths: set[str] = set()
    for safe_path, reference_file in authored_files:
        if _is_directory_path(safe_path, planned):
            continue
        authored_paths.add(safe_path)
        _write_authored_reference(skill_dir / safe_path, reference_file, ir)
    for safe_path in reference_paths:
        if safe_path in authored_paths or _is_directory_path(safe_path, planned):
            continue
        _write_reference(skill_dir / safe_path, ir)
    for safe_path in script_paths:
        if _is_directory_path(safe_path, planned):
            continue
        _write_script_readme(skill_dir / safe_path)
    for safe_path in asset_paths:
        if _is_directory_path(safe_path, planned):
            continue
        _write_asset_template(skill_dir / safe_path, ir)
    return skill_dir


def _is_directory_path(path: str, planned: set[str]) -> bool:
    """A path that is an ancestor of another planned file is a directory, not
    a writable file; models occasionally emit such entries and writing them
    would fail with EISDIR/EACCES once the real files create the directory."""
    prefix = f"{path}/"
    return any(other.startswith(prefix) for other in planned if other != path)


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
    ]
    if ir.skill.overview.strip():
        lines.extend([ir.skill.overview.strip(), ""])

    if ir.quality.hardRestrictions:
        lines.extend(["## Mandatory Rules", ""])
        lines.extend(f"- {rule}" for rule in ir.quality.hardRestrictions)
        lines.append("")

    if ir.quality.softGuidance:
        lines.extend(
            [
                "## Soft Guidance",
                "",
                "Recommendations only; every mandatory rule takes precedence.",
                "",
            ]
        )
        lines.extend(f"- {item}" for item in ir.quality.softGuidance)
        lines.append("")

    lines.extend(
        [
        "## Workflow",
        "",
        f"**Objective:** {ir.workflow.objective}",
        "",
        ]
    )
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

    if ir.workflow.decisionPoints:
        lines.extend(["## Decision Points", ""])
        lines.extend(f"- {item}" for item in ir.workflow.decisionPoints)
        lines.append("")

    if ir.workflow.failureHandling:
        lines.extend(["## Failure Handling", ""])
        lines.extend(f"- {item}" for item in ir.workflow.failureHandling)
        lines.append("")

    if ir.workflow.skillHandoffs:
        lines.extend(["## Skill Orchestration", ""])
        for handoff in ir.workflow.skillHandoffs:
            lines.extend(
                [
                    f"### `{handoff.skill}`",
                    "",
                    f"- **Invoke when:** {handoff.whenToInvoke}",
                    f"- **Input:** {handoff.input}",
                    f"- **Expected output:** {handoff.expectedOutput}",
                    f"- **Failure handling:** {handoff.failureHandling}",
                    "",
                ]
            )

    lines.extend(["## Context Loading", ""])
    for assumption in ir.contextEngineering.filesystemAssumptions:
        lines.append(f"- {assumption}")
    authored_paths = {item.path for item in ir.contextEngineering.referenceFiles}
    for reference_file in ir.contextEngineering.referenceFiles:
        if reference_file.purpose.strip():
            lines.append(f"- Load `{reference_file.path}` when: {reference_file.purpose.strip()}")
        else:
            lines.append(f"- Load `{reference_file.path}` when its domain knowledge is needed.")
    for relative_path in ir.contextEngineering.references:
        if relative_path in authored_paths:
            continue
        lines.append(f"- Load `{relative_path}` when domain rules, examples, or pitfalls are needed.")
    if ir.contextEngineering.scripts:
        lines.append("- Scripts are optional helpers and must be reviewed before execution.")
    if ir.contextEngineering.assets:
        lines.append("- Assets contain templates or examples referenced by the workflow.")
    lines.append("")

    reference_paths = [
        *(item.path for item in ir.contextEngineering.referenceFiles),
        *(path for path in ir.contextEngineering.references if path not in authored_paths),
    ]
    if ir.agentKnowledge.unknownKnowledge and reference_paths:
        lines.extend(["## Domain Knowledge", ""])
        joined = ", ".join(f"`{path}`" for path in reference_paths)
        lines.append(f"Detailed domain knowledge is stored in {joined}.")
        lines.append("")

    if ir.agentKnowledge.relatedSkills:
        lines.extend(["## Related Skills", ""])
        lines.extend(f"- `{skill}`" for skill in ir.agentKnowledge.relatedSkills)
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

    if ir.agentKnowledge.examples:
        lines.extend(["## Positive Examples", ""])
        lines.extend(f"- {item}" for item in ir.agentKnowledge.examples)
        lines.append("")

    if ir.agentKnowledge.counterExamples:
        lines.extend(["## Counter Examples", ""])
        lines.extend(f"- {item}" for item in ir.agentKnowledge.counterExamples)
        lines.append("")

    checklist = ir.quality.validationChecklist or ir.workflow.verification
    if checklist:
        lines.extend(["## Verification Checklist", ""])
        lines.extend(f"- {item}" for item in checklist)
        lines.append("")

    lines.extend(["## Platform Notes", ""])
    lines.append("Use the generated files under `install/` for platform-specific installation paths.")
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def _write_authored_reference(path: Path, reference_file: ReferenceFile, ir: SkillIR) -> None:
    content = reference_file.content.strip()
    if not content:
        # The model declared the file but wrote no content; fall back to the
        # deterministic digest of user-supplied knowledge so the path resolves.
        _write_reference(path, ir)
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    if not content.startswith("#"):
        title = reference_file.purpose.strip() or path.stem.replace("-", " ").title()
        content = f"# {title}\n\n{content}"
    path.write_text(content + "\n", encoding="utf-8")


def _write_reference(path: Path, ir: SkillIR) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["# Domain Knowledge", ""]
    if ir.quality.hardRestrictions:
        lines.append("## Mandatory Rules")
        lines.extend(f"- {item}" for item in ir.quality.hardRestrictions)
        lines.append("")
    if ir.agentKnowledge.unknownKnowledge:
        lines.append("## Professional Information")
        lines.extend(f"- {item}" for item in ir.agentKnowledge.unknownKnowledge)
        lines.append("")
    if ir.agentKnowledge.relatedSkills:
        lines.append("## Dependent or Collaborative Skills")
        lines.extend(f"- {item}" for item in ir.agentKnowledge.relatedSkills)
        lines.append("")
    if ir.agentKnowledge.supplementalContext:
        lines.append("## Supplemental Context")
        lines.append(
            "This optional context has lower priority than every mandatory rule above."
        )
        lines.append("")
        lines.append(ir.agentKnowledge.supplementalContext)
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
