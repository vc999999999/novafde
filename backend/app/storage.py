from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from app.models import (
    GenerationAttempt,
    GenerationResult,
    ModelProviderConfig,
    ProviderRole,
    ProviderTestResult,
    QualityEvaluationReport,
    QualityIssue,
    SkillDraft,
    TaskABRun,
    TriggerEvalSet,
    TriggerOptimizationRun,
    UserSupplement,
)
from app.utils import now_ms


class Storage:
    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._init()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA busy_timeout=5000")
        return connection

    def _init(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS drafts (
                  id TEXT PRIMARY KEY,
                  payload TEXT NOT NULL,
                  created_at INTEGER NOT NULL,
                  updated_at INTEGER NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS generations (
                  id TEXT PRIMARY KEY,
                  draft_id TEXT NOT NULL,
                  payload TEXT NOT NULL,
                  created_at INTEGER NOT NULL,
                  updated_at INTEGER NOT NULL,
                  FOREIGN KEY(draft_id) REFERENCES drafts(id)
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS model_providers (
                  id TEXT PRIMARY KEY,
                  payload TEXT NOT NULL,
                  created_at INTEGER NOT NULL,
                  updated_at INTEGER NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS app_settings (
                  key TEXT PRIMARY KEY,
                  value TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS generation_attempts (
                  id TEXT PRIMARY KEY,
                  run_id TEXT NOT NULL,
                  round INTEGER NOT NULL,
                  payload TEXT NOT NULL,
                  created_at INTEGER NOT NULL,
                  FOREIGN KEY(run_id) REFERENCES generations(id)
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS quality_reports (
                  attempt_id TEXT PRIMARY KEY,
                  run_id TEXT NOT NULL,
                  payload TEXT NOT NULL,
                  evaluated_at INTEGER NOT NULL,
                  FOREIGN KEY(attempt_id) REFERENCES generation_attempts(id),
                  FOREIGN KEY(run_id) REFERENCES generations(id)
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS user_supplements (
                  id TEXT PRIMARY KEY,
                  run_id TEXT NOT NULL,
                  issue_id TEXT NOT NULL,
                  payload TEXT NOT NULL,
                  created_at INTEGER NOT NULL,
                  FOREIGN KEY(run_id) REFERENCES generations(id)
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS error_patterns (
                  id TEXT PRIMARY KEY,
                  category TEXT NOT NULL,
                  payload TEXT NOT NULL,
                  occurrence_count INTEGER NOT NULL DEFAULT 1,
                  updated_at INTEGER NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS run_events (
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  run_id TEXT NOT NULL,
                  event TEXT NOT NULL,
                  payload TEXT NOT NULL,
                  created_at INTEGER NOT NULL,
                  FOREIGN KEY(run_id) REFERENCES generations(id)
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS trigger_eval_sets (
                  id TEXT PRIMARY KEY,
                  payload TEXT NOT NULL,
                  created_at INTEGER NOT NULL,
                  updated_at INTEGER NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS trigger_optimizations (
                  id TEXT PRIMARY KEY,
                  generation_id TEXT NOT NULL,
                  status TEXT NOT NULL,
                  payload TEXT NOT NULL,
                  created_at INTEGER NOT NULL,
                  updated_at INTEGER NOT NULL,
                  FOREIGN KEY(generation_id) REFERENCES generations(id)
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS trigger_run_events (
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  run_id TEXT NOT NULL,
                  phase TEXT NOT NULL,
                  payload TEXT NOT NULL,
                  created_at INTEGER NOT NULL,
                  FOREIGN KEY(run_id) REFERENCES trigger_optimizations(id)
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS task_ab_runs (
                  id TEXT PRIMARY KEY,
                  generation_id TEXT NOT NULL,
                  status TEXT NOT NULL,
                  payload TEXT NOT NULL,
                  created_at INTEGER NOT NULL,
                  updated_at INTEGER NOT NULL,
                  FOREIGN KEY(generation_id) REFERENCES generations(id)
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS task_ab_events (
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  run_id TEXT NOT NULL,
                  phase TEXT NOT NULL,
                  payload TEXT NOT NULL,
                  created_at INTEGER NOT NULL,
                  FOREIGN KEY(run_id) REFERENCES task_ab_runs(id)
                )
                """
            )

    def recover_interrupted_trigger_runs(self) -> int:
        """Mark non-terminal trigger/task runs as interrupted on startup.

        Kept separate from recover_interrupted_generations so an interrupted
        empirical loop never collides with generation diagnostics or the
        generation state machine.
        """
        terminal = {"completed", "failed", "interrupted"}
        counter = 0
        for table, model_cls in (
            ("trigger_optimizations", TriggerOptimizationRun),
            ("task_ab_runs", TaskABRun),
        ):
            with self._connect() as connection:
                rows = connection.execute(
                    f"SELECT id, payload FROM {table}"  # noqa: S608 - static table name
                ).fetchall()
                for row in rows:
                    record = model_cls.model_validate(json.loads(row["payload"]))
                    if record.status in terminal:
                        continue
                    record.status = "interrupted"
                    record.errorMessage = record.errorMessage or "本地应用在此运行完成前关闭，已标记为中断。"
                    record.completedAt = now_ms()
                    payload = json.dumps(record.model_dump(mode="json"), ensure_ascii=False)
                    connection.execute(
                        f"UPDATE {table} SET payload = ?, updated_at = ? WHERE id = ?",  # noqa: S608
                        (payload, record.completedAt, record.id),
                    )
                    counter += 1
        return counter

    def create_generation_shell(
        self,
        *,
        generation_id: str,
        draft_id: str,
        started_at: int,
        max_repair_rounds: int = 3,
        target_platforms: list[str] | None = None,
    ) -> GenerationResult:
        generation = GenerationResult(
            id=generation_id,
            draftId=draft_id,
            status="queued",
            currentStage="queued",
            progress=0,
            startedAt=started_at,
            maxRepairRounds=max_repair_rounds,
            targetPlatformsOverride=target_platforms,
        )
        return self.save_generation(generation)

    def recover_interrupted_generations(self) -> int:
        terminal = {"succeeded", "degraded", "failed", "interrupted"}
        recovered = 0
        with self._connect() as connection:
            rows = connection.execute("SELECT id, payload FROM generations").fetchall()
            for row in rows:
                generation = GenerationResult.model_validate(
                    _migrate_generation_payload(json.loads(row["payload"]))
                )
                if generation.status in terminal:
                    continue
                generation.status = "interrupted"
                generation.currentStage = None
                generation.completedAt = now_ms()
                generation.errorMessage = "本地应用在生成完成前关闭，任务已标记为中断。"
                generation.failureCode = "LOCAL_PROCESS_INTERRUPTED"
                payload = json.dumps(generation.model_dump(mode="json"), ensure_ascii=False)
                connection.execute(
                    "UPDATE generations SET payload = ?, updated_at = ? WHERE id = ?",
                    (payload, generation.completedAt, generation.id),
                )
                recovered += 1
        return recovered

    def save_draft(self, draft: SkillDraft) -> SkillDraft:
        payload = json.dumps(draft.model_dump(mode="json"), ensure_ascii=False)
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO drafts (id, payload, created_at, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                  payload = excluded.payload,
                  updated_at = excluded.updated_at
                """,
                (draft.id, payload, draft.createdAt, draft.updatedAt),
            )
        return draft

    def get_draft(self, draft_id: str) -> SkillDraft | None:
        with self._connect() as connection:
            row = connection.execute("SELECT payload FROM drafts WHERE id = ?", (draft_id,)).fetchone()
        if row is None:
            return None
        raw_payload = json.loads(row["payload"])
        migrated_payload = _migrate_draft_payload(raw_payload)
        draft = SkillDraft.model_validate(migrated_payload)
        if migrated_payload != raw_payload:
            self.save_draft(draft)
        return draft

    def list_drafts(self) -> list[SkillDraft]:
        with self._connect() as connection:
            rows = connection.execute("SELECT payload FROM drafts ORDER BY updated_at DESC").fetchall()
        drafts: list[SkillDraft] = []
        for row in rows:
            raw_payload = json.loads(row["payload"])
            migrated_payload = _migrate_draft_payload(raw_payload)
            draft = SkillDraft.model_validate(migrated_payload)
            if migrated_payload != raw_payload:
                self.save_draft(draft)
            drafts.append(draft)
        return drafts

    def delete_draft_cascade(self, draft_id: str) -> list[str] | None:
        """Delete a draft and all data tied to its generations.

        Returns the ids of the deleted generations, or None when the draft
        does not exist.
        """
        with self._connect() as connection:
            row = connection.execute(
                "SELECT id FROM drafts WHERE id = ?", (draft_id,)
            ).fetchone()
            if row is None:
                return None
            generation_ids = [
                generation_row["id"]
                for generation_row in connection.execute(
                    "SELECT id FROM generations WHERE draft_id = ?", (draft_id,)
                ).fetchall()
            ]
            if generation_ids:
                placeholders = ",".join("?" * len(generation_ids))
                for table, column in (
                    ("run_events", "run_id"),
                    ("user_supplements", "run_id"),
                    ("quality_reports", "run_id"),
                    ("generation_attempts", "run_id"),
                ):
                    connection.execute(
                        f"DELETE FROM {table} WHERE {column} IN ({placeholders})",
                        generation_ids,
                    )
                connection.execute(
                    "DELETE FROM generations WHERE draft_id = ?", (draft_id,)
                )
            connection.execute("DELETE FROM drafts WHERE id = ?", (draft_id,))
        return generation_ids

    def save_generation(self, generation: GenerationResult) -> GenerationResult:
        payload = json.dumps(generation.model_dump(mode="json"), ensure_ascii=False)
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO generations (id, draft_id, payload, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                  payload = excluded.payload,
                  updated_at = excluded.updated_at
                """,
                (generation.id, generation.draftId, payload, generation.startedAt, generation.completedAt or generation.startedAt),
            )
        return generation

    def get_generation(self, generation_id: str) -> GenerationResult | None:
        with self._connect() as connection:
            row = connection.execute("SELECT payload FROM generations WHERE id = ?", (generation_id,)).fetchone()
        if row is None:
            return None
        return GenerationResult.model_validate(
            _migrate_generation_payload(json.loads(row["payload"]))
        )

    def list_generations_for_draft(self, draft_id: str) -> list[GenerationResult]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT payload FROM generations WHERE draft_id = ? ORDER BY updated_at DESC",
                (draft_id,),
            ).fetchall()
        return [
            GenerationResult.model_validate(
                _migrate_generation_payload(json.loads(row["payload"]))
            )
            for row in rows
        ]

    def list_generations(self) -> list[GenerationResult]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT payload FROM generations ORDER BY created_at ASC"
            ).fetchall()
        return [
            GenerationResult.model_validate(
                _migrate_generation_payload(json.loads(row["payload"]))
            )
            for row in rows
        ]

    def save_attempt(self, attempt: GenerationAttempt) -> GenerationAttempt:
        payload = json.dumps(attempt.model_dump(mode="json"), ensure_ascii=False)
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO generation_attempts (id, run_id, round, payload, created_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET payload = excluded.payload
                """,
                (attempt.id, attempt.runId, attempt.round, payload, attempt.createdAt),
            )
        return attempt

    def list_attempts(self, run_id: str) -> list[GenerationAttempt]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT payload FROM generation_attempts WHERE run_id = ? ORDER BY round ASC, created_at ASC",
                (run_id,),
            ).fetchall()
        return [GenerationAttempt.model_validate(json.loads(row["payload"])) for row in rows]

    def save_quality_report(
        self,
        run_id: str,
        report: QualityEvaluationReport,
    ) -> QualityEvaluationReport:
        payload = json.dumps(report.model_dump(mode="json"), ensure_ascii=False)
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO quality_reports (attempt_id, run_id, payload, evaluated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(attempt_id) DO UPDATE SET
                  payload = excluded.payload,
                  evaluated_at = excluded.evaluated_at
                """,
                (report.attemptId, run_id, payload, report.evaluatedAt),
            )
        self.record_quality_issues(report.issues, report.evaluatedAt)
        return report

    def record_quality_issues(
        self,
        issues: list[QualityIssue],
        updated_at: int,
    ) -> None:
        with self._connect() as connection:
            for issue in issues:
                pattern_id = f"{issue.source}:{issue.criterion}"
                payload = json.dumps(
                    {
                        "patternId": pattern_id,
                        "source": issue.source,
                        "criterion": issue.criterion,
                        "severity": issue.severity,
                        "triggerConditions": [issue.reason],
                        "badExample": issue.evidence,
                        "goodExample": [],
                        "suggestedFix": issue.suggestion,
                        "affectedSkillTypes": [],
                        "resolutionRate": 0,
                        "status": "observed",
                        "version": "1.0",
                    },
                    ensure_ascii=False,
                )
                connection.execute(
                    """
                    INSERT INTO error_patterns (
                      id, category, payload, occurrence_count, updated_at
                    )
                    VALUES (?, ?, ?, 1, ?)
                    ON CONFLICT(id) DO UPDATE SET
                      occurrence_count = error_patterns.occurrence_count + 1,
                      updated_at = excluded.updated_at
                    """,
                    (pattern_id, issue.source, payload, updated_at),
                )

    def list_error_patterns(self) -> list[dict]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT id, category, payload, occurrence_count, updated_at
                FROM error_patterns
                ORDER BY occurrence_count DESC, updated_at DESC
                """
            ).fetchall()
        return [
            {
                "id": row["id"],
                "category": row["category"],
                **json.loads(row["payload"]),
                "occurrenceCount": row["occurrence_count"],
                "updatedAt": row["updated_at"],
            }
            for row in rows
        ]

    def add_run_event(
        self,
        run_id: str,
        event: str,
        payload: dict,
        created_at: int,
    ) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO run_events (run_id, event, payload, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (run_id, event, json.dumps(payload, ensure_ascii=False), created_at),
            )

    def list_run_events(self, run_id: str) -> list[dict]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT event, payload, created_at
                FROM run_events
                WHERE run_id = ?
                ORDER BY id ASC
                """,
                (run_id,),
            ).fetchall()
        return [
            {
                "event": row["event"],
                "payload": json.loads(row["payload"]),
                "createdAt": row["created_at"],
            }
            for row in rows
        ]

    def get_quality_report(self, attempt_id: str) -> QualityEvaluationReport | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT payload FROM quality_reports WHERE attempt_id = ?",
                (attempt_id,),
            ).fetchone()
        return QualityEvaluationReport.model_validate(json.loads(row["payload"])) if row else None

    def list_quality_reports(self, run_id: str) -> list[QualityEvaluationReport]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT payload FROM quality_reports WHERE run_id = ? ORDER BY evaluated_at ASC",
                (run_id,),
            ).fetchall()
        return [QualityEvaluationReport.model_validate(json.loads(row["payload"])) for row in rows]

    def save_supplement(self, supplement: UserSupplement) -> UserSupplement:
        payload = json.dumps(supplement.model_dump(mode="json"), ensure_ascii=False)
        with self._connect() as connection:
            connection.execute(
                "DELETE FROM user_supplements WHERE run_id = ? AND issue_id = ?",
                (supplement.runId, supplement.issueId),
            )
            connection.execute(
                """
                INSERT INTO user_supplements (id, run_id, issue_id, payload, created_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET payload = excluded.payload
                """,
                (
                    supplement.id,
                    supplement.runId,
                    supplement.issueId,
                    payload,
                    supplement.createdAt,
                ),
            )
        return supplement

    def list_supplements(self, run_id: str) -> list[UserSupplement]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT payload FROM user_supplements WHERE run_id = ? ORDER BY created_at ASC",
                (run_id,),
            ).fetchall()
        return [UserSupplement.model_validate(json.loads(row["payload"])) for row in rows]

    def save_provider(self, provider: ModelProviderConfig, updated_at: int) -> ModelProviderConfig:
        payload = json.dumps(provider.model_dump(mode="json"), ensure_ascii=False)
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO model_providers (id, payload, created_at, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                  payload = excluded.payload,
                  updated_at = excluded.updated_at
                """,
                (provider.id, payload, updated_at, updated_at),
            )
        return provider

    def get_provider(self, provider_id: str) -> ModelProviderConfig | None:
        with self._connect() as connection:
            row = connection.execute("SELECT payload FROM model_providers WHERE id = ?", (provider_id,)).fetchone()
        if row is None:
            return None
        return ModelProviderConfig.model_validate(json.loads(row["payload"]))

    def list_providers(self) -> list[ModelProviderConfig]:
        with self._connect() as connection:
            rows = connection.execute("SELECT payload FROM model_providers ORDER BY updated_at DESC").fetchall()
        return [ModelProviderConfig.model_validate(json.loads(row["payload"])) for row in rows]

    def delete_provider(self, provider_id: str) -> bool:
        with self._connect() as connection:
            cursor = connection.execute("DELETE FROM model_providers WHERE id = ?", (provider_id,))
            return cursor.rowcount > 0

    def find_enabled_provider_for_role(self, role: ProviderRole) -> ModelProviderConfig | None:
        for provider in self.list_providers():
            if provider.enabled and role in provider.roles:
                return provider
        return None

    def save_provider_test_result(self, provider_id: str, result: ProviderTestResult, updated_at: int) -> ModelProviderConfig | None:
        provider = self.get_provider(provider_id)
        if provider is None:
            return None
        updated = provider.model_copy(update={"lastTest": result})
        return self.save_provider(updated, updated_at)

    def get_setting(self, key: str) -> str | None:
        with self._connect() as connection:
            row = connection.execute("SELECT value FROM app_settings WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else None

    def save_setting(self, key: str, value: str) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO app_settings (key, value)
                VALUES (?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
                """,
                (key, value),
            )

    # ---- Trigger eval sets ------------------------------------------------

    def save_trigger_eval_set(self, eval_set: TriggerEvalSet) -> TriggerEvalSet:
        payload = json.dumps(eval_set.model_dump(mode="json"), ensure_ascii=False)
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO trigger_eval_sets (id, payload, created_at, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                  payload = excluded.payload,
                  updated_at = excluded.updated_at
                """,
                (eval_set.id, payload, eval_set.createdAt, eval_set.updatedAt),
            )
        return eval_set

    def get_trigger_eval_set(self, eval_set_id: str) -> TriggerEvalSet | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT payload FROM trigger_eval_sets WHERE id = ?",
                (eval_set_id,),
            ).fetchone()
        return TriggerEvalSet.model_validate(json.loads(row["payload"])) if row else None

    def list_trigger_eval_sets(self) -> list[TriggerEvalSet]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT payload FROM trigger_eval_sets ORDER BY updated_at DESC"
            ).fetchall()
        return [TriggerEvalSet.model_validate(json.loads(row["payload"])) for row in rows]

    def delete_trigger_eval_set(self, eval_set_id: str) -> bool:
        with self._connect() as connection:
            cursor = connection.execute(
                "DELETE FROM trigger_eval_sets WHERE id = ?",
                (eval_set_id,),
            )
        return cursor.rowcount > 0

    # ---- Trigger optimization runs ----------------------------------------

    def save_trigger_optimization(self, run: TriggerOptimizationRun) -> TriggerOptimizationRun:
        payload = json.dumps(run.model_dump(mode="json"), ensure_ascii=False)
        updated_at = run.completedAt if run.completedAt is not None else run.createdAt
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO trigger_optimizations
                  (id, generation_id, status, payload, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                  status = excluded.status,
                  payload = excluded.payload,
                  updated_at = excluded.updated_at
                """,
                (run.id, run.generationId, run.status, payload, run.createdAt, updated_at),
            )
        return run

    def get_trigger_optimization(self, run_id: str) -> TriggerOptimizationRun | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT payload FROM trigger_optimizations WHERE id = ?",
                (run_id,),
            ).fetchone()
        return TriggerOptimizationRun.model_validate(json.loads(row["payload"])) if row else None

    def list_trigger_optimizations_for_generation(
        self, generation_id: str
    ) -> list[TriggerOptimizationRun]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT payload FROM trigger_optimizations WHERE generation_id = ? ORDER BY created_at DESC",
                (generation_id,),
            ).fetchall()
        return [TriggerOptimizationRun.model_validate(json.loads(row["payload"])) for row in rows]

    def add_trigger_run_event(
        self,
        run_id: str,
        phase: str,
        payload: dict,
        created_at: int,
    ) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO trigger_run_events (run_id, phase, payload, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (run_id, phase, json.dumps(payload, ensure_ascii=False), created_at),
            )

    def list_trigger_run_events(self, run_id: str) -> list[dict]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT phase, payload, created_at
                FROM trigger_run_events
                WHERE run_id = ?
                ORDER BY id ASC
                """,
                (run_id,),
            ).fetchall()
        return [
            {
                "phase": row["phase"],
                "payload": json.loads(row["payload"]),
                "createdAt": row["created_at"],
            }
            for row in rows
        ]

    # ---- Task A/B runs ----------------------------------------------------

    def save_task_ab_run(self, run: TaskABRun) -> TaskABRun:
        payload = json.dumps(run.model_dump(mode="json"), ensure_ascii=False)
        updated_at = run.completedAt if run.completedAt is not None else run.createdAt
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO task_ab_runs (id, generation_id, status, payload, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                  status = excluded.status,
                  payload = excluded.payload,
                  updated_at = excluded.updated_at
                """,
                (run.id, run.generationId, run.status, payload, run.createdAt, updated_at),
            )
        return run

    def get_task_ab_run(self, run_id: str) -> TaskABRun | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT payload FROM task_ab_runs WHERE id = ?",
                (run_id,),
            ).fetchone()
        return TaskABRun.model_validate(json.loads(row["payload"])) if row else None

    def list_task_ab_runs_for_generation(self, generation_id: str) -> list[TaskABRun]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT payload FROM task_ab_runs WHERE generation_id = ? ORDER BY created_at DESC",
                (generation_id,),
            ).fetchall()
        return [TaskABRun.model_validate(json.loads(row["payload"])) for row in rows]

    def add_task_ab_event(
        self,
        run_id: str,
        phase: str,
        payload: dict,
        created_at: int,
    ) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO task_ab_events (run_id, phase, payload, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (run_id, phase, json.dumps(payload, ensure_ascii=False), created_at),
            )

    def list_task_ab_events(self, run_id: str) -> list[dict]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT phase, payload, created_at
                FROM task_ab_events
                WHERE run_id = ?
                ORDER BY id ASC
                """,
                (run_id,),
            ).fetchall()
        return [
            {
                "phase": row["phase"],
                "payload": json.loads(row["payload"]),
                "createdAt": row["created_at"],
            }
            for row in rows
        ]


def _migrate_draft_payload(payload: dict) -> dict:
    if "purpose" in payload:
        return payload

    trigger = payload.get("trigger") or {}
    workflow = payload.get("workflow") or {}
    legacy_knowledge = payload.get("knowledge") or {}
    legacy_steps = workflow.get("steps") or []
    supplement = payload.get("supplement") or {}

    process: list[str] = []
    completion_criteria: list[str] = []
    special_cases: list[str] = []
    for step in legacy_steps:
        purpose = str(step.get("purpose") or "").strip()
        action = str(step.get("action") or "").strip()
        if purpose and action:
            process.append(f"{purpose}：{action}")
        elif purpose or action:
            process.append(purpose or action)
        validation = str(step.get("validation") or "").strip()
        if validation:
            completion_criteria.append(validation)
        failure_handling = str(step.get("failureHandling") or "").strip()
        if failure_handling:
            special_cases.append(failure_handling)

    industry_rules = _clean_string_list(legacy_knowledge.get("industryRules"))
    professional_information = [
        *industry_rules,
        *_clean_string_list(legacy_knowledge.get("internalProcesses")),
        *_clean_string_list(legacy_knowledge.get("personalExperience")),
    ]
    related_skills = _clean_string_list(trigger.get("relatedTools"))
    messages = supplement.get("messages") if isinstance(supplement, dict) else []
    supplement_content = "\n".join(
        str(message.get("content") or "").strip()
        for message in messages or []
        if isinstance(message, dict)
        and message.get("role", "user") == "user"
        and str(message.get("content") or "").strip()
    )

    return {
        "id": payload.get("id"),
        "status": "draft",
        "name": payload.get("name", ""),
        "displayName": payload.get("displayName", ""),
        "targetPlatforms": payload.get("targetPlatforms") or ["claude-code"],
        "purpose": {
            "usage": str(trigger.get("intent") or "").strip(),
            "desiredOutcome": str(workflow.get("objective") or "").strip(),
            "process": process,
            "completionCriteria": completion_criteria[0] if completion_criteria else "",
            "specialCases": special_cases[0] if special_cases else "",
        },
        "knowledge": {
            "professionalInformation": professional_information,
            "mandatoryRules": industry_rules,
            "pitfalls": legacy_knowledge.get("pitfalls") or [],
            "relatedSkills": related_skills,
        },
        "supplement": {"content": supplement_content},
        "createdAt": payload.get("createdAt", 0),
        "updatedAt": payload.get("updatedAt", 0),
    }


def _migrate_generation_payload(payload: dict) -> dict:
    migrated = dict(payload)
    migrated["status"] = {
        "idle": "queued",
        "generating": "generating_initial_ir",
        "validating": "running_validation_checks",
        "success": "succeeded",
    }.get(migrated.get("status"), migrated.get("status"))
    return migrated


def _clean_string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]
