from __future__ import annotations

import os
import time
from datetime import datetime, timezone
from typing import Any

import httpx

from app.models import ModelProviderConfig, ProviderRole, ProviderTestResult


class ModelProviderRuntime:
    def __init__(self, transport: httpx.BaseTransport | None = None) -> None:
        self.transport = transport

    def generate_structured_json(self, request: dict[str, Any], provider: ModelProviderConfig, provider_role: ProviderRole = "generation") -> dict[str, Any]:
        payload = self._payload_for(provider, request.get("messages", []), max_tokens=request.get("max_tokens", 2048))
        return {
            "providerId": provider.id,
            "providerRole": provider_role,
            "protocol": provider.protocol,
            "model": provider.defaultModel,
            "payload": payload,
        }

    def generate_text(self, request: dict[str, Any], provider: ModelProviderConfig, provider_role: ProviderRole = "generation") -> dict[str, Any]:
        return self.generate_structured_json(request, provider, provider_role)

    def stream_text(self, request: dict[str, Any], provider: ModelProviderConfig, provider_role: ProviderRole = "generation") -> dict[str, Any]:
        payload = self.generate_structured_json(request, provider, provider_role)
        payload["streaming"] = provider.streaming
        return payload

    def test_connection(self, provider: ModelProviderConfig) -> ProviderTestResult:
        started = time.perf_counter()
        api_key = os.environ.get(provider.apiKeyRef.name)
        if not api_key:
            return self._result(
                provider=provider,
                started=started,
                status="failed",
                failure_category="auth-missing",
                message=f"Missing environment variable {provider.apiKeyRef.name}.",
            )

        try:
            with httpx.Client(timeout=provider.timeoutMs / 1000, transport=self.transport) as client:
                response = client.post(
                    self._endpoint_for(provider),
                    headers=self._headers_for(provider, api_key),
                    json=self._payload_for(provider, [{"role": "user", "content": "ping"}], max_tokens=1),
                )
        except httpx.TimeoutException:
            return self._result(provider, started, "failed", "timeout", "Provider connection timed out.")
        except httpx.InvalidURL:
            return self._result(provider, started, "failed", "url-error", "Provider base URL is invalid.")
        except httpx.RequestError as exc:
            return self._result(provider, started, "failed", "network-error", f"Provider request failed: {exc.__class__.__name__}.")

        if 200 <= response.status_code < 300:
            return self._result(provider, started, "passed", None, "Provider connection test passed.")
        if response.status_code in {401, 403}:
            return self._result(provider, started, "failed", "auth-failed", "Provider rejected authentication.")
        if response.status_code == 404:
            return self._result(provider, started, "failed", "model-not-found", "Provider endpoint or model was not found.")
        if response.status_code == 400:
            return self._result(provider, started, "failed", "protocol-mismatch", "Provider rejected the protocol request shape.")
        return self._result(provider, started, "failed", "unknown", f"Provider returned HTTP {response.status_code}.")

    def _endpoint_for(self, provider: ModelProviderConfig) -> str:
        if provider.protocol == "claude":
            return f"{provider.baseUrl}/v1/messages"
        return f"{provider.baseUrl}/v1/chat/completions"

    def _headers_for(self, provider: ModelProviderConfig, api_key: str) -> dict[str, str]:
        headers = {"Content-Type": "application/json", **provider.customHeaders}
        if provider.protocol == "claude":
            headers["x-api-key"] = api_key
            headers["anthropic-version"] = "2023-06-01"
        else:
            headers["Authorization"] = f"Bearer {api_key}"
        return headers

    def _payload_for(self, provider: ModelProviderConfig, messages: list[dict[str, str]], max_tokens: int) -> dict[str, Any]:
        if provider.protocol == "claude":
            return {
                "model": provider.defaultModel,
                "max_tokens": max_tokens,
                "messages": messages,
            }
        return {
            "model": provider.defaultModel,
            "max_tokens": max_tokens,
            "messages": messages,
        }

    def _result(
        self,
        provider: ModelProviderConfig,
        started: float,
        status: str,
        failure_category: str | None,
        message: str,
    ) -> ProviderTestResult:
        return ProviderTestResult(
            status=status,
            protocol=provider.protocol,
            model=provider.defaultModel,
            latencyMs=max(0, round((time.perf_counter() - started) * 1000)),
            testedAt=datetime.now(timezone.utc).isoformat(),
            failureCategory=failure_category,
            message=message,
        )
