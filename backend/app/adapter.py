from __future__ import annotations

from pathlib import Path

from app.models import SkillIR, TargetPlatform


PLATFORM_LABELS: dict[TargetPlatform, str] = {
    "claude-code": "Claude Code",
    "codex": "Codex",
    "hermes-openclaw": "Hermes/OpenClaw",
}

# Personal-scope install locations; must stay consistent with _guide_for below.
DEFAULT_INSTALL_DIRS: dict[TargetPlatform, str] = {
    "claude-code": "~/.claude/skills",
    "codex": "~/.agents/skills",
    "hermes-openclaw": "~/.hermes/skills",
}


def write_install_guides(package_root: Path, ir: SkillIR) -> list[Path]:
    install_dir = package_root / "install"
    install_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for platform in ir.platforms.targets:
        path = install_dir / f"{platform}.md"
        path.write_text(_guide_for(platform, ir.skill.name), encoding="utf-8")
        written.append(path)
    return written


def _guide_for(platform: TargetPlatform, skill_name: str) -> str:
    if platform == "claude-code":
        return (
            "# Claude Code Installation\n\n"
            f"Copy `{skill_name}/` into one of these locations:\n\n"
            f"- Personal: `~/.claude/skills/{skill_name}/`\n"
            f"- Project: `.claude/skills/{skill_name}/`\n\n"
            "Restart or refresh Claude Code after installation.\n"
        )
    if platform == "codex":
        return (
            "# Codex Installation\n\n"
            f"Copy `{skill_name}/` into one of these locations:\n\n"
            f"- Personal: `~/.agents/skills/{skill_name}/`\n"
            f"- Project: `.agents/skills/{skill_name}/`\n"
        )
    return (
        "# Hermes/OpenClaw Installation\n\n"
        "## Hermes\n\n"
        f"- Personal: `~/.hermes/skills/{skill_name}/`\n\n"
        "## OpenClaw\n\n"
        f"- Workspace: `skills/{skill_name}/`\n"
        f"- Shared Agent Skills: `~/.agents/skills/{skill_name}/`\n"
        f"- Personal OpenClaw: `~/.openclaw/skills/{skill_name}/`\n"
    )
