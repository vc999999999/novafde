"""CLI subprocess trigger probe (detection Path 1, highest fidelity).

Ported from Anthropic skill-creator's scripts/run_eval.py, adapted for NovaFDE:
  - NO writes into the user's real `.claude/` project. We create an isolated
    throwaway project root under the artifact tree, with its own
    `.claude/commands/`, and point `claude -p` at it via `cwd`.
  - CLAUDECODE env var is stripped so `claude -p` can run nested.
  - Cancel is cooperative: the loop passes a `cancel_check` callable that we
    poll between subprocess reads; on cancel we kill live children. The
    reference only killed on timeout -- cancel-time kill is a NovaFDE addition.
  - Early trigger detection via stream-json content_block_start tool_use
    events (Skill / Read) exactly as the reference does.

This module ONLY shells out when the caller has already confirmed `claude` is
present (`shutil.which("claude")`). The trigger_loop decides eligibility.
"""

from __future__ import annotations

import os
import select
import subprocess
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Callable


class ClaudeTriggerProbe:
    """Measures real trigger rates by running `claude -p` against a temp skill."""

    def __init__(
        self,
        *,
        artifact_root: Path,
        skill_name: str,
        skill_description: str,
        skill_md_text: str,
        num_workers: int = 8,
    ) -> None:
        self._artifact_root = Path(artifact_root)
        self._skill_name = skill_name
        self._skill_description = skill_description
        self._skill_md_text = skill_md_text
        self._num_workers = max(1, num_workers)
        self._temp_root = self._artifact_root / "trigger-temps" / uuid.uuid4().hex
        self._project_root = self._temp_root / "project"
        self._commands_dir = self._project_root / ".claude" / "commands"
        self._project_root.mkdir(parents=True, exist_ok=True)
        self._commands_dir.mkdir(parents=True, exist_ok=True)
        self._clean_name: str | None = None
        self._command_file: Path | None = None

    @property
    def project_root(self) -> Path:
        return self._project_root

    # ------------------------------------------------------------------

    def measure(
        self,
        *,
        queries: list[dict],
        candidate_name: str,
        candidate_description: str,
        runs_per_query: int = 3,
        trigger_threshold: float = 0.5,
        query_timeout_sec: int = 30,
        cancel_check: Callable[[], bool] | None = None,
    ) -> list[dict]:
        self._write_command_file(candidate_name, candidate_description)
        votes: dict[str, list[bool]] = {}

        def worker(query: str, cancel_snapshot: bool) -> bool:
            if cancel_snapshot:
                return False
            return _run_single_query(
                query=query,
                clean_name=self._clean_name,  # type: ignore[arg-type]
                skill_name=candidate_name,
                skill_description=candidate_description,
                timeout=query_timeout_sec,
                project_root=str(self._project_root),
                cancel_check=cancel_check,
            )

        with ThreadPoolExecutor(max_workers=self._num_workers) as pool:
            future_map: dict[Any, str] = {}
            for item in queries:
                query = item["query"]
                for _ in range(runs_per_query):
                    if cancel_check and cancel_check():
                        break
                    future = pool.submit(
                        worker, query, bool(cancel_check and cancel_check())
                    )
                    future_map[future] = query
            for future in as_completed(future_map):
                query = future_map[future]
                votes.setdefault(query, [])
                try:
                    votes[query].append(future.result())
                except Exception:
                    votes[query].append(False)

        results = []
        for item in queries:
            v = votes.get(item["query"], [])
            runs = len(v) or 1
            triggers = sum(1 for x in v if x)
            rate = triggers / runs
            should = bool(item.get("shouldTrigger"))
            passed = (rate >= trigger_threshold) if should else (rate < trigger_threshold)
            results.append(
                {
                    "query": item["query"],
                    "shouldTrigger": should,
                    "triggerRate": rate,
                    "triggers": triggers,
                    "runs": len(v),
                    "passed": passed,
                }
            )
        return results

    # ------------------------------------------------------------------

    def _write_command_file(self, skill_name: str, description: str) -> None:
        unique = uuid.uuid4().hex[:8]
        clean_name = f"{skill_name}-skill-{unique}"
        self._clean_name = clean_name

        if skill_name and self._skill_md_text:
            # Install the actual packaged skill under an isolated skills dir so
            # `claude` can discover and read it like a real skill. We rewrite
            # the frontmatter name/description to the unique detection target.
            content = self._rewrite_skill_md_name(self._skill_md_text, clean_name, description)
            skill_dir = self._project_root / ".claude" / "skills" / clean_name
            skill_dir.mkdir(parents=True, exist_ok=True)
            command_file = skill_dir / "SKILL.md"
        else:
            # Fallback: synthetic command-file skill (matches run_eval.py).
            indented = "\n  ".join(description.split("\n"))
            content = (
                f"---\n"
                f"name: {clean_name}\n"
                f"description: |\n  {indented}\n"
                f"---\n\n# {skill_name}\n\nThis skill handles: {description}\n"
            )
            command_file = self._commands_dir / f"{clean_name}.md"

        command_file.write_text(content, encoding="utf-8")
        self._command_file = command_file

    def close(self) -> None:
        import shutil

        shutil.rmtree(self._temp_root, ignore_errors=True)

    @staticmethod
    def _rewrite_skill_md_name(content: str, clean_name: str, description: str) -> str:
        # Rewrite the YAML frontmatter name + description to the detection
        # target so the in-environment skill name is deterministic and unique.
        lines = content.split("\n")
        out = []
        in_front = False
        front_done = False
        for line in lines:
            if line.strip() == "---" and not front_done:
                if not in_front:
                    in_front = True
                    out.append(line)
                    out.append(f"name: {clean_name}")
                    indented = description.replace("\n", "\n  ")
                    out.append("description: |")
                    out.append(f"  {indented}")
                    continue
                front_done = True
                out.append(line)
                continue
            if in_front and (line.startswith("name:") or line.startswith("description:")):
                continue
            out.append(line)
        return "\n".join(out)


def _run_single_query(
    *,
    query: str,
    clean_name: str,
    skill_name: str,
    skill_description: str,
    timeout: int,
    project_root: str,
    cancel_check: Callable[[], bool] | None,
) -> bool:
    """Run `claude -p` once; return whether the skill triggered.

    Mirrors scripts/run_eval.py run_single_query: stream-json + early
    content_block_start tool_use detection. Adds cancel-aware child kill.
    """
    cmd = [
        "claude",
        "-p",
        query,
        "--output-format",
        "stream-json",
        "--verbose",
        "--include-partial-messages",
    ]
    # `claude -p` refuses to nest inside an existing Claude Code session
    # unless the CLAUDECODE guard env is cleared (see run_eval.py:83).
    env = {k: v for k, v in os.environ.items() if k != "CLAUDECODE"}

    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        cwd=project_root,
        env=env,
    )

    pending_tool_name: str | None = None
    accumulated_json = ""
    triggered = False
    start = time.time()
    buffer = ""

    try:
        while time.time() - start < timeout:
            if cancel_check and cancel_check():
                break
            if process.poll() is not None:
                remaining = process.stdout.read() if process.stdout else b""
                if remaining:
                    buffer += remaining.decode("utf-8", errors="replace")
                break

            ready, _, _ = select.select([process.stdout], [], [], 1.0)
            if not ready:
                continue
            chunk = os.read(process.stdout.fileno(), 8192)
            if not chunk:
                break
            buffer += chunk.decode("utf-8", errors="replace")

            while "\n" in buffer:
                line, buffer = buffer.split("\n", 1)
                line = line.strip()
                if not line:
                    continue
                try:
                    import json

                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if event.get("type") == "stream_event":
                    se = event.get("event", {})
                    se_type = se.get("type", "")
                    if se_type == "content_block_start":
                        cb = se.get("content_block", {})
                        if cb.get("type") == "tool_use":
                            tool_name = cb.get("name", "")
                            if tool_name in ("Skill", "Read"):
                                pending_tool_name = tool_name
                                accumulated_json = ""
                            else:
                                return False
                    elif se_type == "content_block_delta" and pending_tool_name:
                        delta = se.get("delta", {})
                        if delta.get("type") == "input_json_delta":
                            accumulated_json += delta.get("partial_json", "")
                            if clean_name in accumulated_json:
                                return True
                    elif se_type in ("content_block_stop", "message_stop"):
                        if pending_tool_name:
                            return clean_name in accumulated_json
                        if se_type == "message_stop":
                            return False
                elif event.get("type") == "assistant":
                    message = event.get("message", {})
                    for content_item in message.get("content", []):
                        if content_item.get("type") != "tool_use":
                            continue
                        tool_name = content_item.get("name", "")
                        tool_input = content_item.get("input", {})
                        if tool_name == "Skill" and clean_name in tool_input.get("skill", ""):
                            triggered = True
                        elif tool_name == "Read" and clean_name in tool_input.get("file_path", ""):
                            triggered = True
                    return triggered
                elif event.get("type") == "result":
                    return triggered
        return triggered
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()


def _run_single_prompt_output(
    *,
    query: str,
    project_root: str,
    timeout: int,
    cancel_check: Callable[[], bool] | None,
) -> tuple[str, str]:
    """Run `claude -p` once and return the assistant text plus an exit reason."""
    cmd = [
        "claude",
        "-p",
        query,
        "--output-format",
        "stream-json",
        "--verbose",
        "--include-partial-messages",
    ]
    env = {k: v for k, v in os.environ.items() if k != "CLAUDECODE"}

    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        cwd=project_root,
        env=env,
    )

    text_parts: list[str] = []
    result_text = ""
    exit_reason = "completed"
    start = time.time()
    buffer = ""

    try:
        while time.time() - start < timeout:
            if cancel_check and cancel_check():
                exit_reason = "cancelled"
                break
            if process.poll() is not None:
                remaining = process.stdout.read() if process.stdout else b""
                if remaining:
                    buffer += remaining.decode("utf-8", errors="replace")
                break

            ready, _, _ = select.select([process.stdout], [], [], 1.0)
            if not ready:
                continue
            chunk = os.read(process.stdout.fileno(), 8192)
            if not chunk:
                break
            buffer += chunk.decode("utf-8", errors="replace")

            while "\n" in buffer:
                line, buffer = buffer.split("\n", 1)
                line = line.strip()
                if not line:
                    continue
                try:
                    import json

                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue

                if event.get("type") == "stream_event":
                    se = event.get("event", {})
                    if se.get("type") == "content_block_delta":
                        delta = se.get("delta", {})
                        if delta.get("type") == "text_delta":
                            text_parts.append(delta.get("text", ""))
                elif event.get("type") == "assistant":
                    message = event.get("message", {})
                    for content_item in message.get("content", []):
                        if content_item.get("type") == "text":
                            text_parts.append(content_item.get("text", ""))
                elif event.get("type") == "result":
                    if isinstance(event.get("result"), str):
                        result_text = event["result"]
                    subtype = event.get("subtype", "")
                    if subtype and subtype != "success":
                        exit_reason = subtype

        if process.poll() is None and exit_reason == "completed":
            exit_reason = "timeout"
        output = result_text.strip() or "".join(text_parts).strip()
        return output or "[empty output]", exit_reason
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()