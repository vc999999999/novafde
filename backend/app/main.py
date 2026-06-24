from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import ValidationError

from app.models import (
    AppSettings,
    GenerationCreateRequest,
    GenerationResult,
    InstallRequest,
    InstallResult,
    ModelProviderConfig,
    ModelProviderConfigCreate,
    ModelProviderConfigPatch,
    ProviderTestResult,
    SkillDraft,
    SupplementRequest,
    TaskABCreateRequest,
    TaskABRun,
    TriggerEvalQuery,
    TriggerEvalSet,
    TriggerOptimizationCreateRequest,
    TriggerOptimizationRun,
)
from app.agent import SkillAgentRuntime
from app.service import (
    DraftDeleteConflictError,
    InstallConflictError,
    InstallUnavailableError,
    SkillForgeService,
)
from app.settings import Settings


# Only these SkillDraft fields may be updated via PATCH.
# id, status, createdAt, updatedAt are always server-controlled.
PATCHABLE_DRAFT_FIELDS: set[str] = {
    "name",
    "displayName",
    "targetPlatforms",
    "purpose",
    "knowledge",
    "supplement",
}


def create_app(
    settings: Settings | None = None,
    agents: SkillAgentRuntime | None = None,
) -> FastAPI:
    resolved_settings = settings or Settings()
    service = SkillForgeService(resolved_settings, agents=agents)

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        yield
        service.close()

    app = FastAPI(title="SkillForge Backend", version="0.2.0", lifespan=lifespan)
    app.state.service = service

    @app.exception_handler(ValidationError)
    async def handle_payload_validation_error(
        _request: Request, error: ValidationError
    ) -> JSONResponse:
        first = error.errors()[0] if error.errors() else {}
        message = first.get("msg", "invalid payload")
        return JSONResponse(status_code=422, content={"detail": message})

    app.add_middleware(
        CORSMiddleware,
        allow_origins=resolved_settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    if "*" in resolved_settings.cors_origins:
        import logging
        logging.getLogger(__name__).warning(
            "CORS allow_origins='*' with allow_credentials=True is insecure. "
            "Restrict cors_origins in settings."
        )

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/runtime")
    def runtime() -> dict[str, str | bool]:
        return {
            "mode": "local",
            "database": "sqlite",
            "loopbackOnly": True,
            "bindHost": resolved_settings.bind_host,
        }

    @app.get("/api/providers/connection-status")
    def provider_connection_status() -> dict[str, Any]:
        return service.connection_status().model_dump(mode="json")

    @app.post("/api/drafts", response_model=SkillDraft, status_code=201)
    def create_draft(payload: dict[str, Any]) -> SkillDraft:
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
        # Only allow known SkillDraft fields through to prevent callers
        # from overwriting server-controlled fields before the merge.
        filtered = {k: v for k, v in updates.items() if k in PATCHABLE_DRAFT_FIELDS}
        draft = service.patch_draft(draft_id, filtered)
        if draft is None:
            raise HTTPException(status_code=404, detail="Draft not found")
        return draft

    @app.delete("/api/drafts/{draft_id}", status_code=204)
    def delete_draft(draft_id: str) -> None:
        try:
            deleted = service.delete_draft(draft_id)
        except DraftDeleteConflictError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        if not deleted:
            raise HTTPException(status_code=404, detail="Draft not found")

    @app.post("/api/drafts/{draft_id}/generate", response_model=GenerationResult, status_code=201)
    def generate(draft_id: str) -> GenerationResult:
        if not service.model_is_connected():
            raise HTTPException(
                status_code=409,
                detail="Model Provider is not connected and tested",
            )
        generation = service.generate(draft_id)
        if generation is None:
            raise HTTPException(status_code=404, detail="Draft not found")
        return generation

    @app.post("/api/generations", response_model=GenerationResult, status_code=201)
    def create_generation(payload: GenerationCreateRequest) -> GenerationResult:
        if not service.model_is_connected():
            raise HTTPException(
                status_code=409,
                detail="Model Provider is not connected and tested",
            )
        generation = service.start_generation(
            payload.draftId,
            max_repair_rounds=payload.maxRepairRounds,
            target_platforms=payload.targetPlatforms,
        )
        if generation is None:
            raise HTTPException(status_code=404, detail="Draft not found")
        return generation

    @app.get("/api/generations/{generation_id}", response_model=GenerationResult)
    def get_generation(generation_id: str) -> GenerationResult:
        generation = service.get_generation(generation_id)
        if generation is None:
            raise HTTPException(status_code=404, detail="Generation not found")
        return generation

    @app.post("/api/generations/{generation_id}/cancel", response_model=GenerationResult)
    def cancel_generation(generation_id: str) -> GenerationResult:
        generation = service.cancel_generation(generation_id)
        if generation is None:
            raise HTTPException(status_code=404, detail="Generation not found")
        return generation

    @app.get("/api/generations/{generation_id}/quality")
    def generation_quality(generation_id: str) -> dict[str, Any]:
        payload = service.quality_payload(generation_id)
        if payload is None:
            raise HTTPException(status_code=404, detail="Quality report not found")
        return payload

    @app.get("/api/generations/{generation_id}/spec")
    def generation_spec(generation_id: str) -> dict[str, Any]:
        payload = service.generation_spec(generation_id)
        if payload is None:
            raise HTTPException(status_code=404, detail="SkillSpec not found")
        return payload.model_dump(mode="json")

    @app.get("/api/generations/{generation_id}/attempts")
    def generation_attempts(generation_id: str) -> list[dict[str, Any]]:
        attempts = service.attempts(generation_id)
        if attempts is None:
            raise HTTPException(status_code=404, detail="Generation not found")
        return attempts

    @app.get("/api/generations/{generation_id}/trace")
    def generation_trace(generation_id: str) -> list[dict[str, Any]]:
        events = service.run_events(generation_id)
        if events is None:
            raise HTTPException(status_code=404, detail="Generation not found")
        return events

    @app.get("/api/diagnostics/error-patterns")
    def error_patterns() -> list[dict[str, Any]]:
        return service.error_patterns()

    @app.get("/api/diagnostics/metrics")
    def diagnostics_metrics() -> dict[str, Any]:
        return service.diagnostics_metrics()

    @app.post(
        "/api/generations/{generation_id}/supplement",
        response_model=GenerationResult,
        status_code=202,
    )
    def submit_supplement(
        generation_id: str,
        payload: SupplementRequest,
    ) -> GenerationResult:
        generation = service.get_generation(generation_id)
        if generation is None:
            raise HTTPException(status_code=404, detail="Generation not found")
        if generation.status != "awaiting_user_input":
            if service.storage.list_supplements(generation_id):
                return generation
            raise HTTPException(
                status_code=409,
                detail="Generation is not awaiting user input",
            )
        resumed = service.submit_supplement(generation_id, payload)
        if resumed is None:
            raise HTTPException(status_code=404, detail="Generation not found")
        return resumed

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

    @app.post("/api/generations/{generation_id}/install", response_model=InstallResult)
    def install(generation_id: str, payload: InstallRequest) -> InstallResult:
        try:
            result = service.install_skill(generation_id, payload)
        except InstallConflictError as exc:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "INSTALL_TARGET_EXISTS",
                    "message": "目标目录已存在同名 Skill，确认后可覆盖安装。",
                    "path": str(exc.path),
                },
            ) from exc
        except InstallUnavailableError as exc:
            raise HTTPException(
                status_code=409,
                detail={"code": "INSTALL_UNAVAILABLE", "message": str(exc)},
            ) from exc
        if result is None:
            raise HTTPException(status_code=404, detail="Generation not found")
        return result

    @app.post("/api/generations/{generation_id}/regenerate", response_model=GenerationResult, status_code=201)
    def regenerate(generation_id: str) -> GenerationResult:
        if not service.model_is_connected():
            raise HTTPException(
                status_code=409,
                detail="Model Provider is not connected and tested",
            )
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

    @app.get("/api/settings", response_model=AppSettings)
    def get_settings() -> AppSettings:
        return service.get_settings()

    @app.put("/api/settings", response_model=AppSettings)
    def save_settings(payload: AppSettings) -> AppSettings:
        return service.save_settings(payload)

    # ---- Trigger eval sets ------------------------------------------------

    @app.post("/api/trigger-eval-sets", response_model=TriggerEvalSet, status_code=201)
    def create_trigger_eval_set(payload: dict[str, Any]) -> TriggerEvalSet:
        name = str(payload.get("name", "")).strip()
        queries_payload = payload.get("queries") or []
        queries = [
            TriggerEvalQuery(query=str(q.get("query", "")), shouldTrigger=bool(q.get("shouldTrigger")))
            for q in queries_payload
            if q.get("query")
        ]
        return service.create_trigger_eval_set(name=name or "unnamed", queries=queries)

    @app.get("/api/trigger-eval-sets", response_model=list[TriggerEvalSet])
    def list_trigger_eval_sets() -> list[TriggerEvalSet]:
        return service.list_trigger_eval_sets()

    @app.get("/api/trigger-eval-sets/{eval_set_id}", response_model=TriggerEvalSet)
    def get_trigger_eval_set(eval_set_id: str) -> TriggerEvalSet:
        result = service.get_trigger_eval_set(eval_set_id)
        if result is None:
            raise HTTPException(status_code=404, detail="Eval set not found")
        return result

    @app.put("/api/trigger-eval-sets/{eval_set_id}", response_model=TriggerEvalSet)
    def update_trigger_eval_set(eval_set_id: str, payload: dict[str, Any]) -> TriggerEvalSet:
        name = str(payload.get("name", "")).strip()
        queries_payload = payload.get("queries") or []
        queries = [
            TriggerEvalQuery(query=str(q.get("query", "")), shouldTrigger=bool(q.get("shouldTrigger")))
            for q in queries_payload
            if q.get("query")
        ]
        result = service.update_trigger_eval_set(eval_set_id, name=name, queries=queries)
        if result is None:
            raise HTTPException(
                status_code=404,
                detail="Eval set not found or needs at least 2 queries",
            )
        return result

    @app.delete("/api/trigger-eval-sets/{eval_set_id}", status_code=204)
    def delete_trigger_eval_set(eval_set_id: str) -> None:
        if not service.delete_trigger_eval_set(eval_set_id):
            raise HTTPException(status_code=404, detail="Eval set not found")

    # ---- Trigger optimization runs -----------------------------------------

    @app.post(
        "/api/generations/{generation_id}/trigger-optimization",
        response_model=TriggerOptimizationRun,
        status_code=201,
    )
    def start_trigger_optimization(
        generation_id: str,
        payload: TriggerOptimizationCreateRequest,
    ) -> TriggerOptimizationRun:
        if not service.model_is_connected():
            raise HTTPException(
                status_code=409,
                detail="Model Provider is not connected and tested",
            )
        run = service.start_trigger_optimization(
            generation_id,
            eval_set_id=payload.evalSetId,
            max_iterations=payload.maxIterations,
            runs_per_query=payload.runsPerQuery,
            trigger_threshold=payload.triggerThreshold,
            holdout=payload.holdout,
            query_timeout_sec=payload.queryTimeoutSec,
        )
        if run is None:
            raise HTTPException(
                status_code=409,
                detail=(
                    "Generation is not finalized, eval set is missing, or auto eval set "
                    "could not be built (draft needs usage/outcome with at least 2 queries)"
                ),
            )
        return run

    @app.get("/api/trigger-optimizations/{run_id}", response_model=TriggerOptimizationRun)
    def get_trigger_optimization(run_id: str) -> TriggerOptimizationRun:
        run = service.get_trigger_optimization(run_id)
        if run is None:
            raise HTTPException(status_code=404, detail="Run not found")
        return run

    @app.post("/api/trigger-optimizations/{run_id}/cancel", response_model=TriggerOptimizationRun)
    def cancel_trigger_optimization(run_id: str) -> TriggerOptimizationRun:
        run = service.cancel_trigger_optimization(run_id)
        if run is None:
            raise HTTPException(status_code=404, detail="Run not found")
        return run

    @app.get("/api/trigger-optimizations/{run_id}/events")
    def trigger_optimization_events(run_id: str) -> list[dict[str, Any]]:
        events = service.trigger_run_events(run_id)
        if events is None:
            raise HTTPException(status_code=404, detail="Run not found")
        return events

    # ---- Task A/B ---------------------------------------------------------

    @app.post("/api/generations/{generation_id}/task-ab", response_model=TaskABRun, status_code=201)
    def start_task_ab(
        generation_id: str,
        payload: TaskABCreateRequest,
    ) -> TaskABRun:
        if not service.model_is_connected():
            raise HTTPException(
                status_code=409,
                detail="Model Provider is not connected and tested",
            )
        run = service.start_task_ab(
            generation_id,
            prompts=payload.prompts,
            runs_per_prompt=payload.runsPerPrompt,
            query_timeout_sec=payload.queryTimeoutSec,
        )
        if run is None:
            raise HTTPException(
                status_code=409,
                detail="Generation is not finalized",
            )
        return run

    @app.get("/api/task-ab/{run_id}", response_model=TaskABRun)
    def get_task_ab(run_id: str) -> TaskABRun:
        run = service.get_task_ab_run(run_id)
        if run is None:
            raise HTTPException(status_code=404, detail="Run not found")
        return run

    @app.post("/api/task-ab/{run_id}/cancel", response_model=TaskABRun)
    def cancel_task_ab(run_id: str) -> TaskABRun:
        run = service.cancel_task_ab(run_id)
        if run is None:
            raise HTTPException(status_code=404, detail="Run not found")
        return run

    @app.get("/api/task-ab/{run_id}/events")
    def task_ab_events(run_id: str) -> list[dict[str, Any]]:
        events = service.task_ab_run_events(run_id)
        if events is None:
            raise HTTPException(status_code=404, detail="Run not found")
        return events

    return app


app = create_app()
