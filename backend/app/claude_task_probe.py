"""CLI subprocess Task A/B probe: run `claude -p` with and without an isolated skill."""

from __future__ import annotations

import os
import shutil
import time
import uuid
from pathlib import Path
from typing import Callable

from app.claude_trigger_probe import ClaudeTriggerProbe, _run_single_prompt_output


class ClaudeTaskProbe:
    """Runs paired with-skill / baseline prompts in isolated temp projects."""

    def __init__(
        self,
        *,
        artifact_root: Path,
        skill_name: str,
        skill_description: str,
        skill_md_text: str,
    ) -> None:
        self._temp_root = Path(artifact_root) / "task-ab-temps" / uuid.uuid4().hex
        self._baseline_root = self._temp_root / "baseline"
        self._baseline_root.mkdir(parents=True, exist_ok=True)
        self._skill_probe = ClaudeTriggerProbe(
            artifact_root=self._temp_root,
            skill_name=skill_name,
            skill_description=skill_description,
            skill_md_text=skill_md_text,
            num_workers=1,
        )
        self._skill_name = skill_name
        self._skill_description = skill_description

    @property
    def with_skill_project_root(self) -> Path:
        return self._skill_probe.project_root

    @property
    def baseline_project_root(self) -> Path:
        return self._baseline_root

    def prepare(self) -> None:
        self._skill_probe._write_command_file(self._skill_name, self._skill_description)

    def run_with_skill(
        self,
        prompt: str,
        *,
        timeout_sec: int,
        cancel_check: Callable[[], bool] | None = None,
    ) -> tuple[str, int, str]:
        return self._run(prompt, self._skill_probe.project_root, timeout_sec, cancel_check)

    def run_baseline(
        self,
        prompt: str,
        *,
        timeout_sec: int,
        cancel_check: Callable[[], bool] | None = None,
    ) -> tuple[str, int, str]:
        return self._run(prompt, self._baseline_root, timeout_sec, cancel_check)

    def close(self) -> None:
        try:
            self._skill_probe.close()
        except Exception:
            pass
        shutil.rmtree(self._temp_root, ignore_errors=True)

    @staticmethod
    def _run(
        prompt: str,
        project_root: Path,
        timeout_sec: int,
        cancel_check: Callable[[], bool] | None,
    ) -> tuple[str, int, str]:
        started = time.perf_counter()
        text, exit_reason = _run_single_prompt_output(
            query=prompt,
            project_root=str(project_root),
            timeout=timeout_sec,
            cancel_check=cancel_check,
        )
        duration_ms = max(0, round((time.perf_counter() - started) * 1000))
        return text, duration_ms, exit_reason


def resolve_cli_model() -> str | None:
    return os.environ.get("ANTHROPIC_MODEL") or os.environ.get("CLAUDE_MODEL")
