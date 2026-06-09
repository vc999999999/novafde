from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from app.models import (
    GenerationResult,
    ModelProviderConfig,
    ModelProviderConfigCreate,
    ModelProviderConfigPatch,
    ProviderTestResult,
    SkillDraft,
    SkillDraftCreate,
)
from app.service import SkillForgeService
from app.settings import Settings


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved_settings = settings or Settings()
    service = SkillForgeService(resolved_settings)
    app = FastAPI(title="SkillForge Backend", version="0.1.0")
    app.state.service = service

    app.add_middleware(
        CORSMiddleware,
        allow_origins=resolved_settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/api/drafts", response_model=SkillDraft, status_code=201)
    def create_draft(payload: SkillDraftCreate) -> SkillDraft:
        return service.create_draft(payload)

    @app.get("/api/drafts", response_model=list[SkillDraft])
    def list_drafts() -> list[SkillDraft]:
        return service.list_drafts()

    @app.get("/api/drafts/{draft_id}", response_model=SkillDraft)
    def get_draft(draft_id: str) -> SkillDraft:
        draft = service.get_draft(draft_id)
        if draft is None:
            raise HTTPException(status_code=404, detail="Draft not found")
        return draft

    @app.patch("/api/drafts/{draft_id}", response_model=SkillDraft)
    def patch_draft(draft_id: str, updates: dict[str, Any]) -> SkillDraft:
        draft = service.patch_draft(draft_id, updates)
        if draft is None:
            raise HTTPException(status_code=404, detail="Draft not found")
        return draft

    @app.post("/api/drafts/{draft_id}/generate", response_model=GenerationResult, status_code=201)
    def generate(draft_id: str) -> GenerationResult:
        generation = service.generate(draft_id)
        if generation is None:
            raise HTTPException(status_code=404, detail="Draft not found")
        return generation

    @app.get("/api/generations/{generation_id}", response_model=GenerationResult)
    def get_generation(generation_id: str) -> GenerationResult:
        generation = service.get_generation(generation_id)
        if generation is None:
            raise HTTPException(status_code=404, detail="Generation not found")
        return generation

    @app.get("/api/generations/{generation_id}/preview")
    def preview(generation_id: str) -> dict[str, Any]:
        payload = service.preview(generation_id)
        if payload is None:
            raise HTTPException(status_code=404, detail="Generation not found")
        return payload.model_dump(mode="json")

    @app.get("/api/generations/{generation_id}/validation")
    def validation(generation_id: str) -> dict[str, Any]:
        payload = service.validation(generation_id)
        if payload is None:
            raise HTTPException(status_code=404, detail="Generation not found")
        return payload.model_dump(mode="json")

    @app.get("/api/generations/{generation_id}/download")
    def download(generation_id: str) -> FileResponse:
        path = service.download_path(generation_id)
        if path is None:
            raise HTTPException(status_code=404, detail="Download not found")
        return FileResponse(path, media_type="application/zip", filename=path.name)

    @app.post("/api/generations/{generation_id}/regenerate", response_model=GenerationResult, status_code=201)
    def regenerate(generation_id: str) -> GenerationResult:
        generation = service.get_generation(generation_id)
        if generation is None:
            raise HTTPException(status_code=404, detail="Generation not found")
        regenerated = service.generate(generation.draftId)
        if regenerated is None:
            raise HTTPException(status_code=404, detail="Draft not found")
        return regenerated

    @app.get("/api/history")
    def history() -> list[dict[str, Any]]:
        return [item.model_dump(mode="json") for item in service.history()]

    @app.get("/api/rules")
    def rules() -> list[dict[str, Any]]:
        return service.rules()

    @app.get("/api/model-providers", response_model=list[ModelProviderConfig])
    def list_model_providers() -> list[ModelProviderConfig]:
        return service.list_providers()

    @app.post("/api/model-providers", response_model=ModelProviderConfig, status_code=201)
    def create_model_provider(payload: ModelProviderConfigCreate) -> ModelProviderConfig:
        return service.create_provider(payload)

    @app.get("/api/model-providers/{provider_id}", response_model=ModelProviderConfig)
    def get_model_provider(provider_id: str) -> ModelProviderConfig:
        provider = service.get_provider(provider_id)
        if provider is None:
            raise HTTPException(status_code=404, detail="Model provider not found")
        return provider

    @app.patch("/api/model-providers/{provider_id}", response_model=ModelProviderConfig)
    def patch_model_provider(provider_id: str, updates: ModelProviderConfigPatch) -> ModelProviderConfig:
        provider = service.patch_provider(provider_id, updates)
        if provider is None:
            raise HTTPException(status_code=404, detail="Model provider not found")
        return provider

    @app.delete("/api/model-providers/{provider_id}", status_code=204)
    def delete_model_provider(provider_id: str) -> None:
        deleted = service.delete_provider(provider_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Model provider not found")

    @app.post("/api/model-providers/{provider_id}/test", response_model=ProviderTestResult)
    def test_model_provider(provider_id: str) -> ProviderTestResult:
        result = service.test_provider(provider_id)
        if result is None:
            raise HTTPException(status_code=404, detail="Model provider not found")
        return result

    @app.get("/api/cli/commands")
    def cli_commands() -> list[dict[str, Any]]:
        return [command.model_dump(mode="json") for command in service.cli_commands()]

    return app


app = create_app()
