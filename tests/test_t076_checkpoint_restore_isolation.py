"""Native regression for the retained T075 state-67 restore contamination."""

from __future__ import annotations

from copy import deepcopy

import pytest

from sts_combat_rl.sim.controlled_run import execute_controlled_run
from sts_combat_rl.sim.lightspeed import LightSpeedAdapter
from sts_combat_rl.sim.non_combat_learning import (
    _ContinuationAdapter,
    build_frozen_battle_controller,
    frozen_action_space,
)
from sts_combat_rl.sim.non_combat_policy import ExpertNonCombatDriver
from sts_combat_rl.sim.online_controller import PolicyController, RoutedRunController

STATE_67_SOURCE_SEED = 650212
STATE_67_CONTINUATION_SEED = 652201
NEXT_CONTINUATION_SEED = 652202
STATE_67_ACTION_TRACE = (
    ("game:0", "event"),
    ("game:1", "card_select"),
    ("game:3", "map"),
    ("battle:2", "card"),
    ("battle:65539", "card"),
    ("battle:1", "card"),
    ("battle:2147483648", "end_turn"),
    ("battle:3", "card"),
    ("battle:65537", "card"),
    ("battle:2147483648", "end_turn"),
    ("battle:65540", "card"),
    ("battle:65536", "card"),
    ("battle:2147483648", "end_turn"),
    ("battle:2", "card"),
    ("game:134217728", "reward_gold"),
    ("game:512", "reward_card"),
    ("game:805306368", "skip"),
    ("game:2", "map"),
    ("battle:1", "card"),
    ("battle:2", "card"),
    ("battle:2147483648", "end_turn"),
    ("battle:2", "card"),
    ("battle:0", "card"),
    ("battle:2147483648", "end_turn"),
    ("battle:0", "card"),
    ("battle:1", "card"),
    ("battle:2147483648", "end_turn"),
    ("battle:0", "card"),
    ("battle:0", "card"),
    ("game:134217728", "reward_gold"),
    ("game:256", "reward_card"),
    ("game:805306368", "skip"),
    ("game:2", "map"),
    ("game:0", "event"),
    ("game:4", "card_select"),
    ("game:1", "map"),
    ("battle:4", "card"),
    ("battle:65538", "card"),
    ("battle:2147483648", "end_turn"),
    ("battle:1", "card"),
    ("game:256", "reward_card"),
    ("game:402653184", "reward_potion"),
    ("game:805306368", "skip"),
)
STATE_67_ROOT_ACTION_IDENTITIES = (
    ("game:0", "map"),
    ("game:1", "map"),
    ("game:2", "map"),
    ("game:3221225472", "game_potion_discard"),
)


def _action_index(actions, identity: tuple[str, str]) -> int:
    matches = [
        index
        for index, action in enumerate(actions)
        if (action.action_id, action.kind) == identity
    ]
    assert len(matches) == 1, f"expected one legal action for {identity!r}"
    return matches[0]


def _restore_matches_state_67(
    adapter: LightSpeedAdapter,
    checkpoint,
    expected_raw: dict[str, object],
) -> None:
    restored = adapter.restore_checkpoint(checkpoint)
    assert restored.raw == expected_raw
    assert (
        tuple(
            (action.action_id, action.kind)
            for action in adapter.legal_actions(restored)
        )
        == STATE_67_ROOT_ACTION_IDENTITIES
    )


def test_t076_retained_state_67_checkpoint_restore_is_branch_isolated() -> None:
    """T075 state 67 stays immutable across every root branch and continuation."""

    pytest.importorskip("slaythespire")
    adapter = LightSpeedAdapter(seed=STATE_67_SOURCE_SEED, ascension=20)
    snapshot = adapter.reset(seed=STATE_67_SOURCE_SEED)
    for identity in STATE_67_ACTION_TRACE:
        actions = adapter.legal_actions(snapshot)
        snapshot = adapter.step(actions[_action_index(actions, identity)]).snapshot

    root_actions = adapter.legal_actions(snapshot)
    assert (
        tuple((action.action_id, action.kind) for action in root_actions)
        == STATE_67_ROOT_ACTION_IDENTITIES
    )
    expected_raw = deepcopy(snapshot.raw)
    checkpoint = adapter.capture_checkpoint(snapshot)

    for root_identity in STATE_67_ROOT_ACTION_IDENTITIES:
        restored = adapter.restore_checkpoint(checkpoint)
        restored_actions = adapter.legal_actions(restored)
        adapter.step(restored_actions[_action_index(restored_actions, root_identity)])
        _restore_matches_state_67(adapter, checkpoint, expected_raw)

    restored = adapter.restore_checkpoint(checkpoint)
    restored_actions = adapter.legal_actions(restored)
    forced = adapter.step(
        restored_actions[
            _action_index(restored_actions, STATE_67_ROOT_ACTION_IDENTITIES[-1])
        ]
    )
    continuation = execute_controlled_run(
        _ContinuationAdapter(adapter, forced.snapshot),
        RoutedRunController(
            battle=build_frozen_battle_controller(),
            non_combat=PolicyController(
                ExpertNonCombatDriver(seed=STATE_67_CONTINUATION_SEED)
            ),
        ),
        seed=STATE_67_SOURCE_SEED,
        max_steps=500,
        action_space=frozen_action_space(),
    )
    assert continuation.terminal and not continuation.problems

    # This is the exact next restore in the retained T075 failure sequence.
    assert NEXT_CONTINUATION_SEED == 652202
    _restore_matches_state_67(adapter, checkpoint, expected_raw)
