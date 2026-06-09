import pytest

from app.utils import ensure_safe_relative_path, sanitize_skill_name


def test_sanitize_skill_name_creates_filesystem_safe_slug() -> None:
    assert sanitize_skill_name(" Product Research / 北美 ") == "product-research"
    assert sanitize_skill_name("../A..B__C!!") == "a-b-c"
    assert sanitize_skill_name("   ") == "untitled-skill"


def test_ensure_safe_relative_path_blocks_traversal_and_absolute_paths() -> None:
    assert ensure_safe_relative_path("references/domain-guide.md") == "references/domain-guide.md"

    with pytest.raises(ValueError, match="unsafe path"):
        ensure_safe_relative_path("../secrets.txt")

    with pytest.raises(ValueError, match="unsafe path"):
        ensure_safe_relative_path("/tmp/secrets.txt")
