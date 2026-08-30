"""Regression coverage for the T077 retained state-160 restore boundary."""

from __future__ import annotations

from pathlib import Path

import pytest

from sts_combat_rl.sim.lightspeed import LightSpeedAdapter
from sts_combat_rl.sim.t077_continuation import iter_selected_states_strict
from sts_combat_rl.sim.t078_restore_fidelity import audit_restored_source_state

_RETAINED_SELECTED_STATES = Path(
    "/mnt/d/DeadlycatCoding/STSRL/artifacts/"
    "t075-leakage-safe-non-combat-cohort-repair/selected-states.jsonl"
)


def test_t078_retained_state_160_public_context_restores_after_branch() -> None:
    """State 160 preserves the retained context before and after root mutation."""

    pytest.importorskip("slaythespire")
    state = next(
        item
        for item in iter_selected_states_strict(_RETAINED_SELECTED_STATES)
        if item.selected_state_index == 160
    )
    result = audit_restored_source_state(
        LightSpeedAdapter(seed=1, ascension=20, player_class="IRONCLAD"),
        state,
        exercise_branch_restore=True,
    )

    assert result["snapshot_transition_annotation_present"] is True
    assert result["restore_count"] == 2
    assert result["passed"] is True
    assert result["failures"] == []
