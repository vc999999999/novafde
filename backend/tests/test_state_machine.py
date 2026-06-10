import pytest

from app.state_machine import assert_generation_transition


def test_state_machine_allows_defined_quality_loop_transitions() -> None:
    assert_generation_transition("queued", "normalizing")
    assert_generation_transition("aggregating_scores", "repairing_round_1")
    assert_generation_transition("awaiting_user_input", "repairing_round_1")
    assert_generation_transition("packaging_low_score", "degraded")


def test_state_machine_rejects_skipping_validation_and_terminal_reentry() -> None:
    with pytest.raises(ValueError, match="Invalid generation transition"):
        assert_generation_transition("generating_initial_ir", "succeeded")
    with pytest.raises(ValueError, match="Invalid generation transition"):
        assert_generation_transition("succeeded", "repairing_round_1")
