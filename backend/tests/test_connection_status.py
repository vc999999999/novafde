from pathlib import Path

from fastapi.testclient import TestClient

from app.main import create_app
from app.settings import Settings
from app.models import ProviderTestResult
from tests.test_model_providers import build_provider_payload


def test_connection_status_is_unconfigured_without_generation_provider(tmp_path: Path) -> None:
    client = TestClient(create_app(Settings(data_dir=tmp_path)))

    response = client.get("/api/providers/connection-status")

    assert response.status_code == 200
    assert response.json()["status"] == "unconfigured"
    assert response.json()["generationProvider"] is None


def test_connection_status_is_disconnected_until_provider_test_passes(tmp_path: Path) -> None:
    client = TestClient(create_app(Settings(data_dir=tmp_path)))
    provider = client.post("/api/model-providers", json=build_provider_payload()).json()

    response = client.get("/api/providers/connection-status")

    assert response.status_code == 200
    assert response.json()["status"] == "disconnected"
    assert response.json()["generationProvider"]["id"] == provider["id"]


def test_connection_status_requires_separate_judge_provider_to_pass_test(
    tmp_path: Path,
) -> None:
    client = TestClient(create_app(Settings(data_dir=tmp_path)))
    generation_payload = build_provider_payload()
    generation_payload["roles"] = ["generation", "repair"]
    generation = client.post("/api/model-providers", json=generation_payload).json()
    judge_payload = build_provider_payload("openai-compatible")
    judge_payload["name"] = "judge"
    judge_payload["apiKeyRef"] = {"type": "env", "name": "JUDGE_TEST_API_KEY"}
    judge_payload["roles"] = [
        "activation-evaluation",
        "implementation-evaluation",
    ]
    judge = client.post("/api/model-providers", json=judge_payload).json()
    client.app.state.service.storage.save_provider_test_result(
        generation["id"],
        ProviderTestResult(
            status="passed",
            protocol=generation["protocol"],
            model=generation["defaultModel"],
            latencyMs=1,
            testedAt="2026-06-10T00:00:00Z",
            message="ready",
        ),
        1,
    )
    client.put(
        "/api/settings",
        json={
            "defaultGenerateProvider": generation["id"],
            "defaultRepairProvider": generation["id"],
            "defaultValidateProvider": judge["id"],
            "blockOnMissingConfig": True,
        },
    )

    response = client.get("/api/providers/connection-status")

    assert response.status_code == 200
    assert response.json()["status"] == "disconnected"
    assert response.json()["judgeProvider"]["id"] == judge["id"]
