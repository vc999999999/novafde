from __future__ import annotations

import shutil
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.adapter import PLATFORM_LABELS, write_install_guides
from app.agent import DeterministicSkillIRProvider, ModelProvider
from app.cli_contracts import CLI_COMMANDS
from app.models import (
    CliCommandSpec,
    GenerationResult,
    HistoryItem,
    ModelProviderConfig,
    ModelProviderConfigCreate,
    ModelProviderConfigPatch,
    PreviewResponse,
    ProviderTestResult,
    SkillDraft,
    SkillDraftCreate,
    ValidationItem,
    ValidationResponse,
)
from app.normalizer import normalize_draft
from app.packager import build_download_info, create_zip, write_manifest, write_validation_report
from app.provider_runtime import ModelProviderRuntime
from app.repair import MAX_REPAIR_ATTEMPTS, repair_ir
from app.renderer import build_file_tree, render_skill_package
from app.rules import RULES
from app.settings import Settings
from app.storage import Storage
from app.utils import make_id, now_ms, sanitize_skill_name
from app.validator import blocking_count, validate_ir, validate_rendered_package, warning_count


class SkillForgeService:
    def __init__(self, settings: Settings, provider: ModelProvider | None = None) -> None:
        self.settings = settings
        self.settings.data_dir.mkdir(parents=True, exist_ok=True)
        self.settings.artifact_root.mkdir(parents=True, exist_ok=True)
        self.storage = Storage(settings.database_path)
        self.provider = provider or DeterministicSkillIRProvider()
        self.provider_runtime = ModelProviderRuntime()
        self._load_local_provider_config()

    def create_draft(self, payload: SkillDraftCreate) -> SkillDraft:
        timestamp = now_ms()
        draft = SkillDraft(
            id=payload.id or make_id("draft"),
            name=sanitize_skill_name(payload.name or payload.displayName),
            displayName=payload.displayName or payload.name or "Untitled Skill",
            language=payload.language,
            skillType=payload.skillType,
            targetPlatforms=payload.targetPlatforms,
            trigger=payload.trigger,
            workflow=payload.workflow,
            context=payload.context,
            knowledge=payload.knowledge,
            outputControl=payload.outputControl,
            supplement=payload.supplement,
            createdAt=payload.createdAt or timestamp,
            updatedAt=payload.updatedAt or timestamp,
        )
        return self.storage.save_draft(draft)

    def list_drafts(self) -> list[SkillDraft]:
        return self.storage.list_drafts()

    def get_draft(self, draft_id: str) -> SkillDraft | None:
        return self.storage.get_draft(draft_id)

    def patch_draft(self, draft_id: str, updates: dict[str, Any]) -> SkillDraft | None:
        draft = self.storage.get_draft(draft_id)
        if draft is None:
            return None
        merged = _deep_merge(draft.model_dump(mode="json"), updates)
        merged["id"] = draft.id
        merged["status"] = "draft"
        merged["name"] = sanitize_skill_name(merged.get("name") or merged.get("displayName"))
        merged["createdAt"] = draft.createdAt
        merged["updatedAt"] = now_ms()
        updated = SkillDraft.model_validate(merged)
        return self.storage.save_draft(updated)

    def generate(self, draft_id: str) -> GenerationResult | None:
        draft = self.storage.get_draft(draft_id)
        if draft is None:
            return None

        generation_id = make_id("gen")
        started_at = now_ms()
        artifact_dir = self.settings.artifact_root / generation_id
        if artifact_dir.exists():
            shutil.rmtree(artifact_dir)
        artifact_dir.mkdir(parents=True, exist_ok=True)

        generation_provider = self.storage.find_enabled_provider_for_role("generation")
        if generation_provider is None:
            validation_items = [_missing_provider_item()]
            generation = GenerationResult(
                id=generation_id,
                draftId=draft.id,
                status="failed",
                currentStage="injecting-rules",
                progress=15,
                validation=validation_items,
                blockingIssues=blocking_count(validation_items),
                warnings=warning_count(validation_items),
                startedAt=started_at,
                completedAt=now_ms(),
                errorMessage="缺少启用的 generation Model Provider，请先完成模型配置。",
                artifactDir=str(artifact_dir),
            )
            return self.storage.save_generation(generation)

        brief, brief_validation = normalize_draft(draft)
        if blocking_count(brief_validation):
            generation = GenerationResult(
                id=generation_id,
                draftId=draft.id,
                status="failed",
                currentStage="normalizing",
                progress=10,
                validation=brief_validation,
                blockingIssues=blocking_count(brief_validation),
                warnings=warning_count(brief_validation),
                startedAt=started_at,
                completedAt=now_ms(),
                errorMessage="生成输入存在阻塞问题，请补充草稿后重试。",
                modelProviderId=generation_provider.id,
                modelProtocol=generation_provider.protocol,
                providerConnectionRisk=_provider_connection_risk(generation_provider),
                artifactDir=str(artifact_dir),
            )
            return self.storage.save_generation(generation)

        ir = self.provider.generate_ir(brief)
        ir_validation = validate_ir(ir)
        repair_changes: list[str] = []
        for _attempt in range(MAX_REPAIR_ATTEMPTS):
            if not blocking_count(ir_validation):
                break
            ir, changes = repair_ir(ir, brief, ir_validation)
            if not changes:
                break
            repair_changes.extend(changes)
            ir_validation = validate_ir(ir)

        validation_items = [*brief_validation, *ir_validation]
        if repair_changes:
            validation_items.append(
                _repair_pass_item(repair_changes)
            )
        if blocking_count(validation_items):
            generation = GenerationResult(
                id=generation_id,
                draftId=draft.id,
                status="failed",
                currentStage="generating-ir",
                progress=45,
                validation=validation_items,
                blockingIssues=blocking_count(validation_items),
                warnings=warning_count(validation_items),
                startedAt=started_at,
                completedAt=now_ms(),
                errorMessage="Skill IR 存在阻塞问题，自动修复后仍未通过。",
                modelProviderId=generation_provider.id,
                modelProtocol=generation_provider.protocol,
                providerConnectionRisk=_provider_connection_risk(generation_provider),
                artifactDir=str(artifact_dir),
            )
            return self.storage.save_generation(generation)

        package_root = artifact_dir / "package"
        render_skill_package(ir, package_root)
        write_install_guides(package_root, ir)
        validation_items.extend(validate_rendered_package(package_root, ir))
        blocking_issues = blocking_count(validation_items)
        warnings = warning_count(validation_items)

        if blocking_issues:
            write_validation_report(package_root, validation_items)
            generation = GenerationResult(
                id=generation_id,
                draftId=draft.id,
                status="failed",
                currentStage="quality-gate",
                progress=75,
                files=build_file_tree(package_root),
                skillMd=(package_root / ir.skill.name / "SKILL.md").read_text(encoding="utf-8"),
                validation=validation_items,
                blockingIssues=blocking_issues,
                warnings=warnings,
                startedAt=started_at,
                completedAt=now_ms(),
                errorMessage="渲染包未通过阻塞校验。",
                modelProviderId=generation_provider.id,
                modelProtocol=generation_provider.protocol,
                providerConnectionRisk=_provider_connection_risk(generation_provider),
                artifactDir=str(artifact_dir),
            )
            return self.storage.save_generation(generation)

        generated_at = datetime.now(timezone.utc).isoformat()
        write_validation_report(package_root, validation_items)
        write_manifest(package_root, ir, validation_items)
        zip_name = f"{ir.skill.name}-package.zip"
        zip_path = artifact_dir / zip_name
        create_zip(package_root, zip_path)
        download_info = build_download_info(
            zip_path=zip_path,
            package_name=zip_name,
            platforms=[PLATFORM_LABELS[target] for target in ir.platforms.targets],
            generated_at=generated_at,
        )

        generation = GenerationResult(
            id=generation_id,
            draftId=draft.id,
            status="success",
            currentStage="packaging",
            progress=100,
            files=build_file_tree(package_root),
            skillMd=(package_root / ir.skill.name / "SKILL.md").read_text(encoding="utf-8"),
            validation=validation_items,
            blockingIssues=0,
            warnings=warnings,
            downloadInfo=download_info,
            startedAt=started_at,
            completedAt=now_ms(),
            modelProviderId=generation_provider.id,
            modelProtocol=generation_provider.protocol,
            providerConnectionRisk=_provider_connection_risk(generation_provider),
            artifactDir=str(artifact_dir),
            zipPath=str(zip_path),
        )
        return self.storage.save_generation(generation)

    def get_generation(self, generation_id: str) -> GenerationResult | None:
        return self.storage.get_generation(generation_id)

    def preview(self, generation_id: str) -> PreviewResponse | None:
        generation = self.storage.get_generation(generation_id)
        if generation is None:
            return None
        return PreviewResponse(files=generation.files, skillMd=generation.skillMd)

    def validation(self, generation_id: str) -> ValidationResponse | None:
        generation = self.storage.get_generation(generation_id)
        if generation is None:
            return None
        return ValidationResponse(
            generationId=generation.id,
            items=generation.validation,
            blockingIssues=generation.blockingIssues,
            warnings=generation.warnings,
        )

    def download_path(self, generation_id: str) -> Path | None:
        generation = self.storage.get_generation(generation_id)
        if generation is None or not generation.zipPath:
            return None
        path = Path(generation.zipPath)
        return path if path.exists() else None

    def history(self) -> list[HistoryItem]:
        items: list[HistoryItem] = []
        for draft in self.storage.list_drafts():
            generations = self.storage.list_generations_for_draft(draft.id)
            latest = generations[0] if generations else None
            if latest is None:
                status = "draft"
                updated_at = draft.updatedAt
            elif latest.status == "success":
                status = "downloadable"
                updated_at = latest.completedAt or latest.startedAt
            elif latest.status == "failed":
                status = "failed"
                updated_at = latest.completedAt or latest.startedAt
            else:
                status = "generating"
                updated_at = latest.startedAt
            items.append(
                HistoryItem(
                    id=draft.id,
                    displayName=draft.displayName,
                    name=draft.name,
                    status=status,
                    platforms=[PLATFORM_LABELS[target] for target in draft.targetPlatforms],
                    createdAt=_format_local(draft.createdAt),
                    updatedAt=_format_local(updated_at),
                )
            )
        return items

    def rules(self) -> list[dict[str, Any]]:
        return RULES

    def create_provider(self, payload: ModelProviderConfigCreate) -> ModelProviderConfig:
        provider = ModelProviderConfig(id=make_id("provider"), **payload.model_dump(mode="json", exclude={"apiKey"}))
        if payload.apiKey:
            _write_env_secret(self.settings.env_path, provider.apiKeyRef.name, payload.apiKey)
        return self.storage.save_provider(provider, now_ms())

    def list_providers(self) -> list[ModelProviderConfig]:
        return self.storage.list_providers()

    def get_provider(self, provider_id: str) -> ModelProviderConfig | None:
        return self.storage.get_provider(provider_id)

    def patch_provider(self, provider_id: str, updates: ModelProviderConfigPatch) -> ModelProviderConfig | None:
        provider = self.storage.get_provider(provider_id)
        if provider is None:
            return None
        merged = provider.model_dump(mode="json")
        update_payload = updates.model_dump(mode="json", exclude_none=True)
        api_key = update_payload.pop("apiKey", None)
        for key, value in update_payload.items():
            merged[key] = value
        merged["id"] = provider.id
        merged["lastTest"] = provider.lastTest.model_dump(mode="json") if provider.lastTest else None
        updated = ModelProviderConfig.model_validate(merged)
        if api_key:
            _write_env_secret(self.settings.env_path, updated.apiKeyRef.name, api_key)
        return self.storage.save_provider(updated, now_ms())

    def delete_provider(self, provider_id: str) -> bool:
        return self.storage.delete_provider(provider_id)

    def test_provider(self, provider_id: str) -> ProviderTestResult | None:
        provider = self.storage.get_provider(provider_id)
        if provider is None:
            return None
        result = self.provider_runtime.test_connection(provider)
        self.storage.save_provider_test_result(provider_id, result, now_ms())
        return result

    def cli_commands(self) -> list[CliCommandSpec]:
        return CLI_COMMANDS

    def _load_local_provider_config(self) -> None:
        if self.storage.list_providers() or not self.settings.provider_config_path.exists():
            return
        payload = json.loads(self.settings.provider_config_path.read_text(encoding="utf-8"))
        if not isinstance(payload, list):
            return
        for item in payload:
            if not isinstance(item, dict):
                continue
            provider_id = item.get("id") or make_id("provider")
            provider = ModelProviderConfig.model_validate({**item, "id": provider_id})
            self.storage.save_provider(provider, now_ms())


def _deep_merge(base: dict[str, Any], updates: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in updates.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _format_local(timestamp_ms: int) -> str:
    return datetime.fromtimestamp(timestamp_ms / 1000, tz=timezone.utc).strftime("%Y-%m-%d %H:%M")


def _write_env_secret(env_path: Path, name: str, value: str) -> None:
    env_path.parent.mkdir(parents=True, exist_ok=True)
    os.environ[name] = value
    lines = env_path.read_text(encoding="utf-8").splitlines() if env_path.exists() else []
    prefix = f"{name}="
    next_line = f"{name}={value}"
    replaced = False
    next_lines: list[str] = []
    for line in lines:
        if line.startswith(prefix):
            if not replaced:
                next_lines.append(next_line)
                replaced = True
            continue
        next_lines.append(line)
    if not replaced:
        next_lines.append(next_line)
    env_path.write_text("\n".join(next_lines) + "\n", encoding="utf-8")


def _repair_pass_item(changes: list[str]) -> ValidationItem:
    return ValidationItem(
        id="repair-loop-applied",
        ruleId="REPAIR-001",
        level="pass",
        title="自动修复循环已执行",
        description=f"后端修复了 IR 问题：{'; '.join(changes)}。",
        importance="修复循环让模型输出的小偏差可以在确定性校验中被收敛。",
        field="skill_ir",
    )


def _missing_provider_item() -> ValidationItem:
    return ValidationItem(
        id="provider-generation-missing",
        ruleId="PROVIDER-001",
        level="blocking",
        title="缺少 generation Model Provider",
        description="最新 PRD 要求模型调用前至少存在一个启用的 generation Provider。",
        importance="生成链路必须通过统一 Model Provider 接口，不应绕过 Provider 配置。",
        suggestion="通过 /api/model-providers 或 scripts/setup-llm.sh 配置 Claude 或 OpenAI-compatible Provider。",
        blocksDownload=True,
        field="modelProvider",
    )


def _provider_connection_risk(provider: ModelProviderConfig) -> str | None:
    if provider.lastTest is None:
        return "untested"
    if provider.lastTest.status == "failed":
        return f"test-failed:{provider.lastTest.failureCategory or 'unknown'}"
    return None
