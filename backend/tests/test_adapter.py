from app.adapter import _guide_for


def test_codex_guide_uses_agents_skill_paths() -> None:
    guide = _guide_for("codex", "research")

    assert "~/.agents/skills/research/" in guide
    assert ".agents/skills/research/" in guide
    assert "~/.codex/skills/" not in guide


def test_hermes_openclaw_guide_has_separate_sections_and_paths() -> None:
    guide = _guide_for("hermes-openclaw", "research")

    assert "## Hermes" in guide
    assert "~/.hermes/skills/research/" in guide
    assert "## OpenClaw" in guide
    assert "skills/research/" in guide
    assert "~/.agents/skills/research/" in guide
    assert "~/.openclaw/skills/research/" in guide
