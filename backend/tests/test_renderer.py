from app.models import ReferenceFile, SkillHandoff
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


def test_renderer_skips_directory_like_paths(tmp_path) -> None:
    ir = valid_ir()
    ir.contextEngineering.referenceFiles = [
        ReferenceFile(
            path="references/method.md",
            purpose="需要方法论时",
            content="# 方法论\n\n内容。",
        ),
        # A bare directory entry must not be written as a file: doing so used
        # to crash with EACCES/EISDIR once the real files created the folder.
        ReferenceFile(path="references", purpose="", content="x"),
    ]
    ir.contextEngineering.references = ["references", "references/extra.md"]

    skill_dir = render_skill_package(ir, tmp_path / "pkg")

    assert (skill_dir / "references").is_dir()
    assert (skill_dir / "references/method.md").is_file()
    assert (skill_dir / "references/extra.md").is_file()


def test_skill_md_renders_workflow_and_quality_lists(tmp_path) -> None:
    ir = valid_ir()
    ir.workflow.decisionPoints = ["证据不足时先扩大检索范围，再决定是否降级结论"]
    ir.workflow.failureHandling = ["List evidence gaps"]
    ir.quality.softGuidance = ["优先引用一手来源"]
    ir.agentKnowledge.examples = ["每条结论后附 [来源编号]"]
    ir.agentKnowledge.counterExamples = ["直接给出无出处的结论"]

    skill_dir = render_skill_package(ir, tmp_path / "pkg")
    skill_md = (skill_dir / "SKILL.md").read_text(encoding="utf-8")

    assert "## Decision Points" in skill_md
    assert "- 证据不足时先扩大检索范围，再决定是否降级结论" in skill_md
    assert "## Failure Handling" in skill_md
    assert "- List evidence gaps" in skill_md
    assert "## Soft Guidance" in skill_md
    assert "Recommendations only; every mandatory rule takes precedence." in skill_md
    assert "- 优先引用一手来源" in skill_md
    assert "## Positive Examples" in skill_md
    assert "- 每条结论后附 [来源编号]" in skill_md
    assert "## Counter Examples" in skill_md
    assert "- 直接给出无出处的结论" in skill_md


def test_skill_md_keeps_description_in_frontmatter_only(tmp_path) -> None:
    ir = valid_ir()

    skill_dir = render_skill_package(ir, tmp_path / "pkg")
    skill_md = (skill_dir / "SKILL.md").read_text(encoding="utf-8")

    body = skill_md.split("---\n", 2)[2]
    assert "## When to Use" not in skill_md
    assert ir.skill.description not in body


def test_skill_md_omits_empty_optional_sections(tmp_path) -> None:
    ir = valid_ir()
    ir.workflow.decisionPoints = []
    ir.workflow.failureHandling = []
    ir.quality.softGuidance = []
    ir.agentKnowledge.examples = []
    ir.agentKnowledge.counterExamples = []

    skill_dir = render_skill_package(ir, tmp_path / "pkg")
    skill_md = (skill_dir / "SKILL.md").read_text(encoding="utf-8")

    assert "## Decision Points" not in skill_md
    assert "## Failure Handling" not in skill_md
    assert "## Soft Guidance" not in skill_md
    assert "## Positive Examples" not in skill_md
    assert "## Counter Examples" not in skill_md


def test_skill_md_renders_explicit_skill_handoffs(tmp_path) -> None:
    ir = valid_ir()
    ir.workflow.skillHandoffs = [
        SkillHandoff(
            skill="web-research",
            whenToInvoke="When primary-source evidence is missing",
            input="Research question and evidence gaps",
            expectedOutput="Source-linked evidence set",
            failureHandling="Return the unresolved gaps to the current workflow",
        )
    ]

    skill_dir = render_skill_package(ir, tmp_path / "pkg")
    skill_md = (skill_dir / "SKILL.md").read_text(encoding="utf-8")

    assert "## Skill Orchestration" in skill_md
    assert "`web-research`" in skill_md
    assert "When primary-source evidence is missing" in skill_md
