from __future__ import annotations

import pytest

from sts_combat_rl.sim.contract import SimulatorAction
from sts_combat_rl.sim.decision_record import (
    action_identity_dicts_for_actions,
    find_action_index_by_identity,
    source_metadata_from_snapshot,
)


def test_action_identity_disambiguates_duplicate_action_ids() -> None:
    actions = [
        SimulatorAction(action_id="card:Strike_R", label="Strike A", kind="card"),
        SimulatorAction(action_id="card:Strike_R", label="Strike B", kind="card"),
        SimulatorAction(action_id="end", label="End Turn", kind="end_turn"),
    ]

    identities = action_identity_dicts_for_actions(actions)

    assert identities[0]["action_id"] == "card:Strike_R"
    assert identities[0]["occurrence"] == 0
    assert identities[1]["action_id"] == "card:Strike_R"
    assert identities[1]["occurrence"] == 1
    assert identities[0]["stable_id"] != identities[1]["stable_id"]
    assert find_action_index_by_identity(actions, identities[1]) == 1


def test_action_identity_rejects_unmatched_identity() -> None:
    actions = [
        SimulatorAction(action_id="end", label="End Turn", kind="end_turn"),
    ]
    identity = action_identity_dicts_for_actions(
        [SimulatorAction(action_id="card", label="Card", kind="card")]
    )[0]

    with pytest.raises(ValueError, match="matched 0 legal actions"):
        find_action_index_by_identity(actions, identity)


def test_source_metadata_uses_visible_structural_fields() -> None:
    metadata = source_metadata_from_snapshot(
        {
            "seed": 99,
            "ascension_level": 20,
            "act": 2,
            "floor_num": 28,
            "screen_state": "BATTLE",
            "battle_monsters": [{"id": "SlaverBlue"}, {"id": "SlaverRed"}],
        },
        seed=None,
    )

    assert metadata["source_kind"] == "natural_run"
    assert metadata["distribution_kind"] == "natural_run"
    assert metadata["seed"] == 99
    assert metadata["ascension"] == 20
    assert metadata["encounter_id"] == "SlaverBlue+SlaverRed"
