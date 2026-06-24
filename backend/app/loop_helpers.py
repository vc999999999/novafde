"""Pure helpers shared by empirical-loop modules (no heavy imports)."""

from __future__ import annotations

from app.models import ModelProviderConfig, TaskABVerdict


def cap_provider_timeout(provider: ModelProviderConfig, timeout_ms: int) -> ModelProviderConfig:
    cap = max(1000, timeout_ms)
    if provider.timeoutMs <= cap:
        return provider
    return provider.model_copy(update={"timeoutMs": cap})


def majority_task_ab_verdict(votes: list[str]) -> TaskABVerdict:
    if not votes:
        return "tie"
    counts: dict[TaskABVerdict, int] = {"with_skill": 0, "baseline": 0, "tie": 0}
    for vote in votes:
        if vote in counts:
            counts[vote] += 1  # type: ignore[literal-required]
    max_count = max(counts.values())
    winners = [key for key, count in counts.items() if count == max_count]
    if len(winners) != 1:
        return "tie"
    return winners[0]
