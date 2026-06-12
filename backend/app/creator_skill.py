from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from hashlib import sha256
from pathlib import Path


CREATOR_SKILL_VERSION = "1.1.0"


@dataclass(frozen=True)
class CreatorSkillBundle:
    version: str
    sourceUrl: str
    sourceRevision: str
    importedAt: str
    sha256: str
    content: str


@lru_cache(maxsize=1)
def load_creator_skill() -> CreatorSkillBundle:
    root = (
        Path(__file__).parent
        / "resources"
        / "skill_creator"
        / CREATOR_SKILL_VERSION
    )
    content = (root / "SKILL.md").read_text(encoding="utf-8")
    provenance = json.loads(
        (root / "provenance.json").read_text(encoding="utf-8")
    )
    actual_sha256 = sha256(content.encode("utf-8")).hexdigest()
    expected_sha256 = str(provenance["contentSha256"])
    if actual_sha256 != expected_sha256:
        raise RuntimeError(
            "Skill Creator snapshot hash mismatch: "
            f"expected {expected_sha256}, got {actual_sha256}"
        )
    return CreatorSkillBundle(
        version=str(provenance["version"]),
        sourceUrl=str(provenance["sourceUrl"]),
        sourceRevision=str(provenance["sourceRevision"]),
        importedAt=str(provenance["importedAt"]),
        sha256=actual_sha256,
        content=content,
    )
