from __future__ import annotations

"""Shared utility helpers for the NovaFDE backend.

Provides timestamp generation, ID creation, path safety checks,
text sanitization, file hashing, and secret redaction used across
the generation pipeline.
"""

import json
import re
import time
import unicodedata
from hashlib import sha256
from pathlib import Path, PurePosixPath
from typing import Any
from uuid import uuid4


def now_ms() -> int:
    """Return the current time as milliseconds since the Unix epoch."""
    return int(time.time() * 1000)


def make_id(prefix: str) -> str:
    """Generate a prefixed unique identifier using a truncated UUID4 hex string."""
    return f"{prefix}_{uuid4().hex[:12]}"


def sanitize_skill_name(value: str | None) -> str:
    """Normalize and convert *value* into a URL-safe, lowercase hyphenated slug.

    Strips diacritics, keeps only ASCII alphanumerics, and truncates to 64
    characters.  Returns ``"untitled-skill"`` when the result is empty.
    """
    normalized = unicodedata.normalize("NFKD", value or "")
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii").lower()
    parts = re.findall(r"[a-z0-9]+", ascii_text)
    slug = "-".join(parts).strip("-")[:64].rstrip("-")
    return slug or "untitled-skill"


def ensure_safe_relative_path(path: str) -> str:
    """Validate that *path* is a safe relative POSIX path with no traversal segments.

    Raises :class:`ValueError` if the path is empty, absolute, or contains
    empty/dot/double-dot segments.
    """
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
    """Format a byte count as a human-readable string (B, KB, or MB)."""
    if byte_count < 1024:
        return f"{byte_count} B"
    if byte_count < 1024 * 1024:
        return f"{byte_count / 1024:.1f} KB"
    return f"{byte_count / (1024 * 1024):.1f} MB"


def sha256_file(path: Path) -> str:
    """Compute the SHA-256 hex digest of the file at *path* using 1 MB chunks."""
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def hash_directory(root: Path) -> dict[str, str]:
    """Return a sorted mapping of relative POSIX paths to their SHA-256 hex digests."""
    return {
        path.relative_to(root).as_posix(): sha256_file(path)
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def sha256_json(value: Any) -> str:
    """Compute a deterministic SHA-256 hex digest of a JSON-serializable *value*."""
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return sha256(payload.encode("utf-8")).hexdigest()


_SECRET_PATTERNS = (
    re.compile(r"\bsk-[A-Za-z0-9_-]{12,}\b"),
    re.compile(r"\b(?:api[_ -]?key|token|password)\s*[:=]\s*['\"]?[A-Za-z0-9+/=_-]{8,}['\"]?"),
)


def redact_secrets(value: str) -> str:
    """Replace patterns that resemble API keys or credentials with ``[REDACTED]``."""
    redacted = value
    for pattern in _SECRET_PATTERNS:
        redacted = pattern.sub("[REDACTED]", redacted)
    return redacted
