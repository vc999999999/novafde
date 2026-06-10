import time
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import create_app
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
