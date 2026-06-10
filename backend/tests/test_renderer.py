from app.models import ReferenceFile
from app.renderer import render_skill_package
from app.utils import hash_directory
from tests.test_quality_orchestrator import valid_ir


def test_same_skill_ir_renders_identical_file_contents(tmp_path) -> None:
    ir = valid_ir()
    first_root = tmp_path / "first"
    second_root = tmp_path / "second"

    render_skill_package(ir, first_root)
    render_skill_package(ir, second_root)

    assert hash_directory(first_root) == hash_directory(second_root)


def test_authored_reference_files_render_model_content(tmp_path) -> None:
    ir = valid_ir()
    ir.contextEngineering.referenceFiles = [
        ReferenceFile(
            path="references/research-method.md",
            purpose="需要执行证据分级时",
            content="# 证据分级\n\n按事实、推断、假设三层标注。",
        ),
        ReferenceFile(path="references/empty-shell.md", purpose="", content=""),
    ]

    skill_dir = render_skill_package(ir, tmp_path / "pkg")

    authored = (skill_dir / "references/research-method.md").read_text(encoding="utf-8")
    assert "按事实、推断、假设三层标注。" in authored
    # Empty content falls back to the deterministic digest so the path resolves.
    fallback = (skill_dir / "references/empty-shell.md").read_text(encoding="utf-8")
    assert fallback.startswith("# Domain Knowledge")
    skill_md = (skill_dir / "SKILL.md").read_text(encoding="utf-8")
    assert "Load `references/research-method.md` when: 需要执行证据分级时" in skill_md
