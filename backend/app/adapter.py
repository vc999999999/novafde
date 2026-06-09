from __future__ import annotations

from pathlib import Path

from app.models import SkillIR, TargetPlatform


PLATFORM_LABELS: dict[TargetPlatform, str] = {
    "claude-code": "Claude Code",
    "codex": "Codex",
    "hermes-openclaw": "Hermes/OpenClaw",
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
            f"Copy `{skill_name}/` into `~/.codex/skills/{skill_name}/` for a personal Skill.\n\n"
            "For project Skills, use the project-specific Codex skills directory configured in that workspace.\n"
        )
    return (
        "# Hermes/OpenClaw Installation\n\n"
        f"Copy `{skill_name}/` into the configured Hermes/OpenClaw skills directory.\n\n"
        "The exact path is deployment-specific, so keep it configurable and verify it in your runtime settings.\n"
    )
