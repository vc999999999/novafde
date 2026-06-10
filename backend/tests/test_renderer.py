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
