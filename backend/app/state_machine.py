from __future__ import annotations

import logging

from app.models import GenerationStatus

_LOG = logging.getLogger(__name__)


TERMINAL_STATUSES: set[GenerationStatus] = {
    "succeeded",
    "degraded",
    "interrupted",
    "failed",
}

_REPAIR_STATES: set[GenerationStatus] = {
    "repairing_round_1",
    "repairing_round_2",
    "repairing_round_3",
}

_ALLOWED: dict[GenerationStatus, set[GenerationStatus]] = {
    "queued": {"normalizing"},
    "normalizing": {"generating_initial_ir"},
    "generating_initial_ir": {"rendering_candidate"},
    "rendering_candidate": {"running_validation_checks"},
    "running_validation_checks": {
        "evaluating_activation",
        "evaluating_implementation",
        "aggregating_scores",
        "selecting_best_candidate",
    },
    "evaluating_activation": {
        "evaluating_implementation",
        "selecting_best_candidate",
    },
    "evaluating_implementation": {
        "aggregating_scores",
        "selecting_best_candidate",
    },
    "aggregating_scores": {
        "awaiting_user_input",
        "selecting_best_candidate",
        "packaging_high_quality",
        "packaging_low_score",
        *_REPAIR_STATES,
    },
    "awaiting_user_input": {"selecting_best_candidate", *_REPAIR_STATES},
    "selecting_best_candidate": {"packaging_high_quality", "packaging_low_score"},
    "packaging_high_quality": {"succeeded"},
    "packaging_low_score": {"degraded"},
    "succeeded": set(),
    "degraded": set(),
    "interrupted": set(),
    "failed": set(),
}

for repair_state in _REPAIR_STATES:
    _ALLOWED[repair_state] = {"rendering_candidate", "selecting_best_candidate"}


def assert_generation_transition(
    current: GenerationStatus,
    target: GenerationStatus,
) -> None:
    if current == target:
        _LOG.debug("Same-state transition: %s -> %s", current, target)
        return
    if target == "failed" and current not in TERMINAL_STATUSES:
        return
    if target not in _ALLOWED.get(current, set()):
        raise ValueError(f"Invalid generation transition: {current} -> {target}")
