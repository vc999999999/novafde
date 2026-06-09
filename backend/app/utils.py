from __future__ import annotations

import re
import time
import unicodedata
from pathlib import PurePosixPath
from uuid import uuid4


def now_ms() -> int:
    return int(time.time() * 1000)


def make_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:12]}"


def sanitize_skill_name(value: str | None) -> str:
    normalized = unicodedata.normalize("NFKD", value or "")
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii").lower()
    parts = re.findall(r"[a-z0-9]+", ascii_text)
    slug = "-".join(parts).strip("-")
    return slug or "untitled-skill"


def ensure_safe_relative_path(path: str) -> str:
    normalized = path.replace("\\", "/").strip()
    pure_path = PurePosixPath(normalized)
    if (
        not normalized
        or pure_path.is_absolute()
        or any(part in {"", ".", ".."} for part in pure_path.parts)
    ):
        raise ValueError(f"unsafe path: {path}")
    return pure_path.as_posix()


def format_size(byte_count: int) -> str:
    if byte_count < 1024:
        return f"{byte_count} B"
    if byte_count < 1024 * 1024:
        return f"{byte_count / 1024:.1f} KB"
    return f"{byte_count / (1024 * 1024):.1f} MB"
