from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from app.models import GenerationResult, ModelProviderConfig, ProviderRole, ProviderTestResult, SkillDraft


class Storage:
    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._init()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
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
        return SkillDraft.model_validate(json.loads(row["payload"]))

    def list_drafts(self) -> list[SkillDraft]:
        with self._connect() as connection:
            rows = connection.execute("SELECT payload FROM drafts ORDER BY updated_at DESC").fetchall()
        return [SkillDraft.model_validate(json.loads(row["payload"])) for row in rows]

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
        return GenerationResult.model_validate(json.loads(row["payload"]))

    def list_generations_for_draft(self, draft_id: str) -> list[GenerationResult]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT payload FROM generations WHERE draft_id = ? ORDER BY updated_at DESC",
                (draft_id,),
            ).fetchall()
        return [GenerationResult.model_validate(json.loads(row["payload"])) for row in rows]

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
