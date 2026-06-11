import json
import os
from pathlib import Path

import httpx
from fastapi.testclient import TestClient

from app.main import create_app
from app.models import ModelProviderConfig, ProviderTestResult
from app.provider_runtime import ModelProviderRuntime
from app.secret_store import SecretStore
from app.settings import Settings
from tests.test_api_pipeline import build_draft_payload
from tests.agent_support import build_test_agents


def make_client(tmp_path: Path) -> TestClient:
    return TestClient(create_app(Settings(data_dir=tmp_path), agents=build_test_agents()))


def build_provider_payload(protocol: str = "anthropic") -> dict:
    return {
        "name": f"{protocol}-primary",
        "protocol": protocol,
        "baseUrl": "https://api.example.test",
        "apiKeyRef": {"type": "env", "name": "SKILLFORGE_TEST_API_KEY"},
        "defaultModel": "test-model",
        "roles": ["generation", "repair", "validation-explanation"],
        "timeoutMs": 120000,
        "retries": 2,
        "streaming": True,
        "customHeaders": {"X-Trace-Source": "skillforge-test"},
        "enabled": True,
    }


def test_provider_config_api_masks_keys_and_rejects_sensitive_header(tmp_path: Path, monkeypatch) -> None:
    client = make_client(tmp_path)
    monkeypatch.setenv("SKILLFORGE_TEST_API_KEY", "secret-token")

    empty_response = client.get("/api/model-providers")
    assert empty_response.status_code == 200
    assert empty_response.json() == []

    create_response = client.post("/api/model-providers", json=build_provider_payload())
    assert create_response.status_code == 201
    provider = create_response.json()
    assert provider["id"].startswith("provider_")
    assert provider["protocol"] == "anthropic"
    assert provider["apiKeyRef"] == {"type": "env", "name": "SKILLFORGE_TEST_API_KEY"}
    assert "secret-token" not in json.dumps(provider)

    list_response = client.get("/api/model-providers")
    assert list_response.status_code == 200
    assert len(list_response.json()) == 1
    assert "secret-token" not in json.dumps(list_response.json())

    patch_response = client.patch(f"/api/model-providers/{provider['id']}", json={"enabled": False})
    assert patch_response.status_code == 200
    assert patch_response.json()["enabled"] is False

    unsafe_payload = build_provider_payload("openai-compatible")
    unsafe_payload["customHeaders"] = {"Authorization": "Bearer leaked"}
    unsafe_response = client.post("/api/model-providers", json=unsafe_payload)
    assert unsafe_response.status_code == 422


def test_provider_create_accepts_user_key_without_leaking_it(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("SKILLFORGE_UI_TEST_API_KEY", raising=False)
    settings = Settings(data_dir=tmp_path / "data", use_system_keyring=False)
    client = TestClient(create_app(settings))

    payload = {
        **build_provider_payload("anthropic"),
        "apiKeyRef": {"type": "env", "name": "SKILLFORGE_UI_TEST_API_KEY"},
        "apiKey": "secret-token-from-ui",
    }
    response = client.post("/api/model-providers", json=payload)

    assert response.status_code == 201
    provider = response.json()
    assert provider["apiKeyRef"] == {"type": "env", "name": "SKILLFORGE_UI_TEST_API_KEY"}
    assert "secret-token-from-ui" not in json.dumps(provider)
    assert b"secret-token-from-ui" not in settings.encrypted_secrets_path.read_bytes()
    # After fix: API keys are no longer written to os.environ for security.
    # Keys are only stored in SecretStore and loaded on demand.
    assert os.environ.get("SKILLFORGE_UI_TEST_API_KEY") is None


def test_deleting_provider_clears_its_stored_secret(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("SKILLFORGE_UI_TEST_API_KEY", raising=False)
    settings = Settings(data_dir=tmp_path / "data", use_system_keyring=False)
    client = TestClient(create_app(settings))
    service = client.app.state.service

    payload = {
        **build_provider_payload("anthropic"),
        "apiKeyRef": {"type": "env", "name": "SKILLFORGE_UI_TEST_API_KEY"},
        "apiKey": "secret-token-from-ui",
    }
    provider = client.post("/api/model-providers", json=payload).json()
    assert service.secret_store.get("SKILLFORGE_UI_TEST_API_KEY") == "secret-token-from-ui"

    delete_response = client.delete(f"/api/model-providers/{provider['id']}")
    assert delete_response.status_code == 204
    # The orphaned key must not linger in the store after the provider is gone.
    assert service.secret_store.get("SKILLFORGE_UI_TEST_API_KEY") is None


def test_deleting_provider_keeps_secret_shared_with_another_provider(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("SKILLFORGE_SHARED_TEST_KEY", raising=False)
    settings = Settings(data_dir=tmp_path / "data", use_system_keyring=False)
    client = TestClient(create_app(settings))
    service = client.app.state.service

    shared_ref = {"type": "env", "name": "SKILLFORGE_SHARED_TEST_KEY"}
    first = client.post(
        "/api/model-providers",
        json={**build_provider_payload("anthropic"), "apiKeyRef": shared_ref, "apiKey": "shared-secret"},
    ).json()
    client.post(
        "/api/model-providers",
        json={**build_provider_payload("openai-compatible"), "apiKeyRef": shared_ref},
    )

    assert client.delete(f"/api/model-providers/{first['id']}").status_code == 204
    # A second provider still references the key, so it must be preserved.
    assert service.secret_store.get("SKILLFORGE_SHARED_TEST_KEY") == "shared-secret"


def test_app_loads_local_provider_config_file_and_normalizes_legacy_protocol(tmp_path: Path) -> None:
    provider_config_path = tmp_path / "providers.local.json"
    # Local config files written before the rename used protocol "claude".
    provider_config_path.write_text(
        json.dumps([{**build_provider_payload("claude"), "id": "provider_local"}], ensure_ascii=False),
        encoding="utf-8",
    )
    client = TestClient(create_app(Settings(data_dir=tmp_path / "data", provider_config_path=provider_config_path)))

    response = client.get("/api/model-providers")
    assert response.status_code == 200
    providers = response.json()
    assert len(providers) == 1
    assert providers[0]["id"] == "provider_local"
    assert providers[0]["protocol"] == "anthropic"
    assert providers[0]["apiKeyRef"]["name"] == "SKILLFORGE_TEST_API_KEY"


def test_provider_connection_test_classifies_missing_key_without_leaking_secret(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    create_response = client.post("/api/model-providers", json=build_provider_payload("openai-compatible"))
    provider = create_response.json()

    test_response = client.post(f"/api/model-providers/{provider['id']}/test")
    assert test_response.status_code == 200
    result = test_response.json()
    assert result["status"] == "failed"
    assert result["failureCategory"] == "auth-missing"
    assert result["protocol"] == "openai-compatible"
    assert "SKILLFORGE_TEST_API_KEY" in result["message"]
    assert "secret" not in json.dumps(result).lower()


def test_generation_is_blocked_without_enabled_generation_provider(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    draft_response = client.post("/api/drafts", json=build_draft_payload())
    assert draft_response.status_code == 201

    generation_response = client.post(f"/api/drafts/{draft_response.json()['id']}/generate")
    assert generation_response.status_code == 409
    assert "not connected" in generation_response.json()["detail"]


def test_generation_records_provider_metadata_when_configured(tmp_path: Path, monkeypatch) -> None:
    client = make_client(tmp_path)
    monkeypatch.setenv("SKILLFORGE_TEST_API_KEY", "secret-token")
    provider = client.post("/api/model-providers", json=build_provider_payload("anthropic")).json()
    client.app.state.service.storage.save_provider_test_result(
        provider["id"],
        ProviderTestResult(
            status="passed",
            protocol="anthropic",
            model=provider["defaultModel"],
            latencyMs=1,
            testedAt="2026-06-10T00:00:00Z",
            message="ready",
        ),
        1,
    )
    draft = client.post("/api/drafts", json=build_draft_payload()).json()

    generation_response = client.post(f"/api/drafts/{draft['id']}/generate")
    assert generation_response.status_code == 201
    generation = generation_response.json()
    assert generation["status"] == "succeeded"
    assert generation["modelProviderId"] == provider["id"]
    assert generation["modelProtocol"] == "anthropic"
    assert generation["providerConnectionRisk"] is None


def test_runtime_resolves_key_from_secret_store_when_not_in_env(tmp_path: Path, monkeypatch) -> None:
    # Regression: UI-saved keys live in the SecretStore, never os.environ. The
    # runtime must resolve them through the injected resolver, not just env.
    monkeypatch.delenv("SKILLFORGE_TEST_API_KEY", raising=False)
    store = SecretStore(
        encrypted_path=tmp_path / "secrets.enc",
        key_path=tmp_path / "secrets.key",
        prefer_keyring=False,
    )
    store.set("SKILLFORGE_TEST_API_KEY", "stored-in-vault")

    seen_requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_requests.append(request)
        return httpx.Response(200, json={"ok": True})

    runtime = ModelProviderRuntime(transport=httpx.MockTransport(handler), key_resolver=store.get)
    provider = ModelProviderConfig.model_validate({**build_provider_payload("anthropic"), "id": "provider_vault"})

    result = runtime.test_connection(provider)

    assert result.status == "passed"
    assert seen_requests[0].headers["x-api-key"] == "stored-in-vault"


def test_service_resolves_ui_saved_key_for_connection_test(tmp_path: Path, monkeypatch) -> None:
    # End-to-end wiring: a key submitted through the API must be readable by the
    # service key resolver even though it is never written to the environment.
    monkeypatch.delenv("SKILLFORGE_UI_TEST_API_KEY", raising=False)
    settings = Settings(data_dir=tmp_path / "data", use_system_keyring=False)
    client = TestClient(create_app(settings))

    payload = {
        **build_provider_payload("anthropic"),
        "apiKeyRef": {"type": "env", "name": "SKILLFORGE_UI_TEST_API_KEY"},
        "apiKey": "secret-token-from-ui",
    }
    create_response = client.post("/api/model-providers", json=payload)
    assert create_response.status_code == 201

    service = client.app.state.service
    assert service._resolve_api_key("SKILLFORGE_UI_TEST_API_KEY") == "secret-token-from-ui"


def test_runtime_builds_protocol_specific_minimal_connection_requests(monkeypatch) -> None:
    monkeypatch.setenv("SKILLFORGE_TEST_API_KEY", "secret-token")
    seen_requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_requests.append(request)
        return httpx.Response(200, json={"ok": True})

    runtime = ModelProviderRuntime(transport=httpx.MockTransport(handler))
    anthropic_provider = ModelProviderConfig.model_validate({**build_provider_payload("anthropic"), "id": "provider_anthropic"})
    openai_provider = ModelProviderConfig.model_validate({**build_provider_payload("openai-compatible"), "id": "provider_openai"})

    assert runtime.test_connection(anthropic_provider).status == "passed"
    assert runtime.test_connection(openai_provider).status == "passed"

    anthropic_request = seen_requests[0]
    assert anthropic_request.url.path == "/v1/messages"
    assert anthropic_request.headers["x-api-key"] == "secret-token"
    assert json.loads(anthropic_request.content)["max_tokens"] == 1

    openai_request = seen_requests[1]
    assert openai_request.url.path == "/v1/chat/completions"
    assert openai_request.headers["authorization"] == "Bearer secret-token"
    assert json.loads(openai_request.content)["max_tokens"] == 1
