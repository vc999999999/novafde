from __future__ import annotations

import json
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from app.creator_skill import load_creator_skill
from app.models import (
    DownloadInfo,
    QualityEvaluationReport,
    SkillIR,
    SkillSpec,
    ValidationItem,
)
from app.prompts import GENERATION_PROMPT_VERSION
from app.renderer import RENDERER_VERSION
from app.utils import ensure_safe_relative_path, format_size
from app.validator import (
    AGENT_SKILLS_VALIDATOR_VERSION,
    VALIDATION_RULE_SET_VERSION,
)


def write_manifest(
    output_root: Path,
    ir: SkillIR,
    validation_items: list[ValidationItem],
    quality_report: QualityEvaluationReport | None = None,
    selection_reason: str | None = None,
    skill_spec: SkillSpec | None = None,
    skill_spec_sha256: str | None = None,
    package_root: Path | None = None,
) -> Path:
    package_root = package_root or output_root
    creator = load_creator_skill()
    manifest = {
        "schemaVersion": "1.0",
        "versions": {
            "skillIrSchemaVersion": ir.schemaVersion,
            "packageFormatVersion": "1.0",
            "creatorSkillVersion": creator.version,
            "creatorSkillSha256": creator.sha256,
            "generationPromptVersion": GENERATION_PROMPT_VERSION,
            "skillSpecSchemaVersion": (
                skill_spec.schemaVersion if skill_spec is not None else None
            ),
            "skillSpecRevision": (
                skill_spec.revision if skill_spec is not None else None
            ),
            "skillSpecSha256": skill_spec_sha256,
            "agentSkillsValidatorVersion": AGENT_SKILLS_VALIDATOR_VERSION,
            "rendererVersion": RENDERER_VERSION,
            "validationRuleSetVersion": VALIDATION_RULE_SET_VERSION,
        },
        "skillName": ir.skill.name,
        "targets": ir.platforms.targets,
        "files": sorted(_relative_files(package_root)),
        "validation": {
            "blockingIssues": sum(1 for item in validation_items if item.level == "blocking"),
            "warnings": sum(1 for item in validation_items if item.level == "warning"),
        },
        "quality": (
            {
                "overallScore": quality_report.overallScore,
                "validationScore": quality_report.validationScore,
                "activationScore": quality_report.activationScore,
                "implementationScore": quality_report.implementationScore,
                "passedStrictGate": quality_report.passedStrictGate,
                "passedDegradedGate": quality_report.passedDegradedGate,
                "rubricVersion": quality_report.rubricVersion,
                "selectionReason": selection_reason,
            }
            if quality_report
            else None
        ),
    }
    output_root.mkdir(parents=True, exist_ok=True)
    path = output_root / "package-manifest.json"
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (output_root / "skillforge-manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return path


def write_validation_report(output_root: Path, validation_items: list[ValidationItem]) -> Path:
    payload = {
        "items": [item.model_dump(mode="json") for item in validation_items],
        "blockingIssues": sum(1 for item in validation_items if item.level == "blocking"),
        "warnings": sum(1 for item in validation_items if item.level == "warning"),
    }
    output_root.mkdir(parents=True, exist_ok=True)
    path = output_root / "validation-report.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def write_quality_report(
    output_root: Path,
    report: QualityEvaluationReport,
    *,
    degraded: bool,
    repair_rounds: int,
    selection_reason: str | None = None,
) -> Path:
    output_root.mkdir(parents=True, exist_ok=True)
    json_path = output_root / "quality-report.json"
    json_path.write_text(
        report.model_dump_json(indent=2),
        encoding="utf-8",
    )
    if not degraded:
        return json_path

    lines = [
        "# SkillForge Quality Report",
        "",
        "> 本包未达到 SkillForge 高质量门槛，属于低分版本，需要人工检查。",
        "",
        f"- Overall Score: {report.overallScore}",
        f"- Validation Score: {report.validationScore}",
        f"- Activation Score: {report.activationScore}",
        f"- Implementation Score: {report.implementationScore}",
        f"- Repair rounds: {repair_rounds}",
        f"- Selection reason: {selection_reason or 'highest-scoring safe candidate'}",
        "",
        "## Remaining Issues",
        "",
    ]
    for issue in report.issues:
        lines.extend(
            [
                f"### {issue.criterion}",
                "",
                f"- Reason: {issue.reason}",
                f"- Suggestion: {issue.suggestion}",
                "",
            ]
        )
    markdown_path = output_root / "QUALITY_REPORT.md"
    markdown_path.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")
    return markdown_path


def create_zip(package_root: Path, zip_path: Path) -> None:
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    if zip_path.exists():
        zip_path.unlink()
    with ZipFile(zip_path, "w", ZIP_DEFLATED) as zip_file:
        for directory in sorted(_relative_dirs(package_root)):
            safe_dir = ensure_safe_relative_path(directory.rstrip("/") or ".")
            if safe_dir != ".":
                zip_file.write(package_root / safe_dir, f"{safe_dir}/")
        for relative_file in sorted(_relative_files(package_root)):
            safe_file = ensure_safe_relative_path(relative_file)
            zip_file.write(package_root / safe_file, safe_file)
    validate_zip_entries(zip_path)


def build_download_info(zip_path: Path, package_name: str, platforms: list[str], generated_at: str) -> DownloadInfo:
    with ZipFile(zip_path) as zip_file:
        file_count = len([item for item in zip_file.infolist() if not item.is_dir()])
    return DownloadInfo(
        packageName=package_name,
        generatedAt=generated_at,
        platforms=platforms,
        fileCount=file_count,
        size=format_size(zip_path.stat().st_size),
    )


def validate_zip_entries(zip_path: Path) -> None:
    with ZipFile(zip_path) as zip_file:
        for name in zip_file.namelist():
            ensure_safe_relative_path(name.rstrip("/"))


def _relative_files(root: Path) -> list[str]:
    resolved_root = root.resolve()
    return [
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file() and path.resolve().is_relative_to(resolved_root)
    ]


def _relative_dirs(root: Path) -> list[str]:
    resolved_root = root.resolve()
    return [
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_dir() and path.resolve().is_relative_to(resolved_root)
    ]
