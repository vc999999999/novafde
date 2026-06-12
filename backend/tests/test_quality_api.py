import json
import sqlite3
import time
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import create_app
from app.models import GenerationAttempt
from app.settings import Settings
from tests.agent_support import build_test_agents
from tests.test_api_pipeline import build_draft_payload, create_generation_provider


TERMINAL = {"succeeded", "degraded", "failed", "interrupted", "awaiting_user_input"}


def wait_for_generation(client: TestClient, generation_id: str) -> dict:
    for _ in range(100):
        payload = client.get(f"/api/generations/{generation_id}").json()
        if payload["status"] in TERMINAL:
            return payload
        time.sleep(0.01)
    raise AssertionError("generation did not reach a terminal or input state")


def test_async_generation_quality_and_attempt_endpoints(tmp_path: Path) -> None:
    client = TestClient(
        create_app(Settings(data_dir=tmp_path), agents=build_test_agents())
    )
    create_generation_provider(client)
    draft = client.post("/api/drafts", json=build_draft_payload()).json()

    response = client.post("/api/generations", json={"draftId": draft["id"]})

    assert response.status_code == 201
    generation_id = response.json()["id"]
    completed = wait_for_generation(client, generation_id)
    assert completed["status"] == "succeeded"

    quality = client.get(f"/api/generations/{generation_id}/quality")
    assert quality.status_code == 200
    assert quality.json()["overallScore"] == 100

    attempts = client.get(f"/api/generations/{generation_id}/attempts")
    assert attempts.status_code == 200
    assert len(attempts.json()) == 1
    assert attempts.json()[0]["qualityReport"]["passedStrictGate"] is True


def test_generation_spec_api_returns_current_and_revision_history(tmp_path: Path) -> None:
    client = TestClient(
        create_app(Settings(data_dir=tmp_path), agents=build_test_agents())
    )
    create_generation_provider(client)
    draft = client.post("/api/drafts", json=build_draft_payload()).json()

    generation = client.post(f"/api/drafts/{draft['id']}/generate").json()
    response = client.get(f"/api/generations/{generation['id']}/spec")

    assert response.status_code == 200
    payload = response.json()
    assert payload["revision"] == 1
    assert payload["sha256"] == generation["skillSpecSha256"]
    assert payload["current"]["identity"]["skillName"] == "product-research"
    assert payload["revisions"] == [
        {
            "revision": 1,
            "sha256": payload["sha256"],
            "createdAt": generation["startedAt"],
            "sourceIssueIds": [],
        }
    ]


def test_legacy_generation_without_spec_remains_readable(tmp_path: Path) -> None:
    settings = Settings(data_dir=tmp_path)
    client = TestClient(create_app(settings, agents=build_test_agents()))
    generation = client.app.state.service.storage.create_generation_shell(
        generation_id="gen_legacy_without_spec",
        draft_id="draft_legacy",
        started_at=1,
    )
    payload = generation.model_dump(mode="json")
    for key in [
        "skillSpecAvailable",
        "skillSpecRevision",
        "skillSpecSha256",
        "skillSpecRevisions",
    ]:
        payload.pop(key)
    with sqlite3.connect(settings.database_path) as connection:
        connection.execute(
            "UPDATE generations SET payload = ? WHERE id = ?",
            (json.dumps(payload), generation.id),
        )
    attempt = GenerationAttempt(
        id="attempt_legacy",
        runId=generation.id,
        round=0,
        skillIR={},
        renderedPath="",
        isStructurallyValid=False,
        isSecuritySafe=False,
        createdAt=1,
    )
    client.app.state.service.storage.save_attempt(attempt)
    attempt_payload = attempt.model_dump(mode="json")
    attempt_payload.pop("skillSpecRevision")
    attempt_payload.pop("skillSpecSha256")
    with sqlite3.connect(settings.database_path) as connection:
        connection.execute(
            "UPDATE generation_attempts SET payload = ? WHERE id = ?",
            (json.dumps(attempt_payload), attempt.id),
        )

    response = client.get(f"/api/generations/{generation.id}")
    spec_response = client.get(f"/api/generations/{generation.id}/spec")

    assert response.status_code == 200
    assert response.json()["skillSpecAvailable"] is False
    assert response.json()["skillSpecRevision"] is None
    assert spec_response.status_code == 404
    loaded_attempt = client.app.state.service.storage.list_attempts(generation.id)[0]
    assert loaded_attempt.skillSpecRevision is None
    assert loaded_attempt.skillSpecSha256 is None


def test_supplement_endpoint_rejects_run_that_is_not_waiting(tmp_path: Path) -> None:
    client = TestClient(
        create_app(Settings(data_dir=tmp_path), agents=build_test_agents())
    )
    create_generation_provider(client)
    draft = client.post("/api/drafts", json=build_draft_payload()).json()
    generation = client.post(f"/api/drafts/{draft['id']}/generate").json()

    response = client.post(
        f"/api/generations/{generation['id']}/supplement",
        json={"answers": [], "skip": True},
    )

    assert response.status_code == 409


def test_generation_endpoint_rejects_untested_model_connection(tmp_path: Path) -> None:
    client = TestClient(
        create_app(Settings(data_dir=tmp_path), agents=build_test_agents())
    )
    response = client.post(
        "/api/model-providers",
        json={
            "name": "untested",
            "protocol": "openai-compatible",
            "baseUrl": "http://127.0.0.1:11434",
            "apiKeyRef": {"type": "env", "name": "UNTESTED_KEY"},
            "defaultModel": "local-model",
            "roles": [
                "generation",
                "repair",
                "activation-evaluation",
                "implementation-evaluation",
            ],
        },
    )
    assert response.status_code == 201
    draft = client.post("/api/drafts", json=build_draft_payload()).json()

    generation = client.post("/api/generations", json={"draftId": draft["id"]})

    assert generation.status_code == 409
    assert "not connected" in generation.json()["detail"]


def test_regenerate_endpoint_rejects_untested_model_connection(tmp_path: Path) -> None:
    client = TestClient(
        create_app(Settings(data_dir=tmp_path), agents=build_test_agents())
    )
    draft = client.post("/api/drafts", json=build_draft_payload()).json()
    generation = client.app.state.service.storage.create_generation_shell(
        generation_id="gen_existing",
        draft_id=draft["id"],
        started_at=1,
    )

    response = client.post(f"/api/generations/{generation.id}/regenerate")

    assert response.status_code == 409
    assert "not connected" in response.json()["detail"]


def test_diagnostics_include_criterion_averages_and_model_pass_rates(
    tmp_path: Path,
) -> None:
    client = TestClient(
        create_app(Settings(data_dir=tmp_path), agents=build_test_agents())
    )
    create_generation_provider(client)
    draft = client.post("/api/drafts", json=build_draft_payload()).json()
    generation = client.post(f"/api/drafts/{draft['id']}/generate").json()
    assert generation["status"] == "succeeded"

    response = client.get("/api/diagnostics/metrics")

    assert response.status_code == 200
    metrics = response.json()
    assert metrics["criterionAverageScores"]["activation.specificity"] == 100
    assert metrics["criterionAverageScores"]["implementation.actionability"] == 100
    assert metrics["models"]["test-model"]["strictPassRate"] == 100


def test_history_exposes_latest_generation_id_for_resume_and_redownload(
    tmp_path: Path,
) -> None:
    client = TestClient(
        create_app(Settings(data_dir=tmp_path), agents=build_test_agents())
    )
    create_generation_provider(client)
    draft = client.post("/api/drafts", json=build_draft_payload()).json()
    generation = client.post(f"/api/drafts/{draft['id']}/generate").json()

    response = client.get("/api/history")

    assert response.status_code == 200
    item = next(item for item in response.json() if item["id"] == draft["id"])
    assert item["generationId"] == generation["id"]
