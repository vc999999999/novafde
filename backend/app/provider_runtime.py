from __future__ import annotations

import asyncio
import os
import time
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any, TypeVar

import httpx
from anthropic import AsyncAnthropic
from openai import AsyncOpenAI
from pydantic import BaseModel
from pydantic_ai import Agent
from pydantic_ai.models import Model
from pydantic_ai.settings import ModelSettings
from pydantic_ai.models.anthropic import AnthropicModel
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.anthropic import AnthropicProvider
from pydantic_ai.providers.openai import OpenAIProvider

from app.models import AgentCallMetadata, ModelProviderConfig, ProviderRole, ProviderTestResult


OutputT = TypeVar("OutputT", bound=BaseModel)
ModelFactory = Callable[[ModelProviderConfig, ProviderRole], Model]

# Structured SkillIR outputs regularly exceed the 4096-token default that
# pydantic-ai applies to Anthropic-protocol models; a truncated tool call
# fails schema validation and burns every output retry.
MAX_OUTPUT_TOKENS = int(os.environ.get("SKILLFORGE_MAX_OUTPUT_TOKENS", "16384"))


class PydanticAgentRuntime:
    def __init__(self, model_factory: ModelFactory | None = None) -> None:
        self._model_factory = model_factory

    def run_structured(
        self,
        *,
        provider: ModelProviderConfig,
        role: ProviderRole,
        instructions: str,
        prompt: str,
        output_type: type[OutputT],
        prompt_version: str,
    ) -> tuple[OutputT, AgentCallMetadata]:
        started = time.perf_counter()
        model = (
            self._model_factory(provider, role)
            if self._model_factory is not None
            else self._build_model(provider)
        )
        agent = Agent(
            model,
            output_type=output_type,
            instructions=instructions,
            retries={"output": min(max(provider.retries, 1), 2), "tools": 1},
            model_settings=ModelSettings(max_tokens=MAX_OUTPUT_TOKENS),
        )
        result = asyncio.run(agent.run(prompt))
        usage = result.usage
        estimated_cost = None
        if (
            provider.inputPricePerMillionTokens > 0
            or provider.outputPricePerMillionTokens > 0
        ):
            estimated_cost = round(
                (
                    (usage.input_tokens or 0) * provider.inputPricePerMillionTokens
                    + (usage.output_tokens or 0) * provider.outputPricePerMillionTokens
                )
                / 1_000_000,
                8,
            )
        return result.output, AgentCallMetadata(
            providerId=provider.id,
            providerRole=role,
            protocol=provider.protocol,
            model=provider.defaultModel,
            promptVersion=prompt_version,
            inputTokens=usage.input_tokens or 0,
            outputTokens=usage.output_tokens or 0,
            requests=usage.requests,
            durationMs=max(0, round((time.perf_counter() - started) * 1000)),
            estimatedCostUsd=estimated_cost,
        )

    def _build_model(self, provider: ModelProviderConfig) -> Model:
        api_key = os.environ.get(provider.apiKeyRef.name)
        if not api_key:
            raise RuntimeError(
                f"Missing API key: environment variable {provider.apiKeyRef.name} is not set."
            )
        timeout = provider.timeoutMs / 1000
        if provider.protocol == "claude":
            client = AsyncAnthropic(
                api_key=api_key,
                base_url=provider.baseUrl,
                timeout=timeout,
                max_retries=provider.retries,
                default_headers=provider.customHeaders,
            )
            return AnthropicModel(
                provider.defaultModel,
                provider=AnthropicProvider(anthropic_client=client),
            )

        client = AsyncOpenAI(
            api_key=api_key,
            base_url=_openai_base_url(provider.baseUrl),
            timeout=timeout,
            max_retries=provider.retries,
            default_headers=provider.customHeaders,
        )
        return OpenAIChatModel(
            provider.defaultModel,
            provider=OpenAIProvider(openai_client=client),
        )


class ModelProviderRuntime:
    def __init__(self, transport: httpx.BaseTransport | None = None) -> None:
        self.transport = transport

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
        base = provider.baseUrl.rstrip("/")
        if provider.protocol == "claude":
            return f"{base}/v1/messages"
        return f"{_openai_base_url(base)}/chat/completions"

    def _headers_for(self, provider: ModelProviderConfig, api_key: str) -> dict[str, str]:
        headers = {"Content-Type": "application/json", "Accept": "application/json", **provider.customHeaders}
        if provider.protocol == "claude":
            headers["x-api-key"] = api_key
            headers["anthropic-version"] = "2023-06-01"
        else:
            headers["Authorization"] = f"Bearer {api_key}"
        return headers

    def _payload_for(self, provider: ModelProviderConfig, messages: list[dict[str, str]], *, system: str | None = None, max_tokens: int = 2048) -> dict[str, Any]:
        if provider.protocol == "claude":
            payload: dict[str, Any] = {
                "model": provider.defaultModel,
                "max_tokens": max_tokens,
                "messages": messages,
            }
            if system:
                payload["system"] = system
            return payload
        # OpenAI-compatible: system message goes into messages array
        openai_messages = list(messages)
        if system:
            openai_messages.insert(0, {"role": "system", "content": system})
        return {
            "model": provider.defaultModel,
            "max_tokens": max_tokens,
            "messages": openai_messages,
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


def _openai_base_url(base_url: str) -> str:
    base = base_url.rstrip("/")
    return base if base.endswith("/v1") else f"{base}/v1"
