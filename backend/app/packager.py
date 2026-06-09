from __future__ import annotations

import json
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from app.models import DownloadInfo, SkillIR, ValidationItem
from app.utils import ensure_safe_relative_path, format_size


def write_manifest(package_root: Path, ir: SkillIR, validation_items: list[ValidationItem]) -> Path:
    manifest = {
        "schemaVersion": "1.0",
        "skillName": ir.skill.name,
        "targets": ir.platforms.targets,
        "files": sorted(_relative_files(package_root)),
        "validation": {
            "blockingIssues": sum(1 for item in validation_items if item.level == "blocking"),
            "warnings": sum(1 for item in validation_items if item.level == "warning"),
        },
    }
    path = package_root / "package-manifest.json"
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def write_validation_report(package_root: Path, validation_items: list[ValidationItem]) -> Path:
    payload = {
        "items": [item.model_dump(mode="json") for item in validation_items],
        "blockingIssues": sum(1 for item in validation_items if item.level == "blocking"),
        "warnings": sum(1 for item in validation_items if item.level == "warning"),
    }
    path = package_root / "validation-report.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


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
    return [path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_file()]


def _relative_dirs(root: Path) -> list[str]:
    return [path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_dir()]
