from __future__ import annotations

from sts_combat_rl.sim.contract import SimulatorAction
from sts_combat_rl.sim.decision_record import (
    DECISION_RECORD_SCHEMA_VERSION,
    action_identity_dicts_for_actions,
)
from sts_combat_rl.sim.features import (
    IDENTITY_VOCABULARY_VERSION,
    TACTICAL_FEATURE_SCHEMA_ID,
    TACTICAL_FEATURE_SCHEMA_VERSION,
    build_public_tactical_actions,
    build_public_tactical_state,
    encode_lightspeed_battle_snapshot,
    encode_simulator_actions,
)
from sts_combat_rl.sim.public_run_context import build_public_run_context
from sts_combat_rl.sim.resource_outcome import (
    BATTLE_RESOURCE_OUTCOME_SCHEMA_ID,
    BATTLE_RESOURCE_OUTCOME_SCHEMA_VERSION,
    available_battle_resource_outcome,
    build_battle_resource_outcome,
)
from sts_combat_rl.sim.trainer_input import (
    TRAINER_INPUT_DATASET_FORMAT_VERSION,
    TrainerInputDataset,
    TrainerInputRecord,
)


def make_trainer_dataset(
    ascension_act_pairs: list[tuple[int, int]],
) -> TrainerInputDataset:
    records = [
        _record(index, ascension=ascension, act=act)
        for index, (ascension, act) in enumerate(ascension_act_pairs)
    ]
    return TrainerInputDataset(
        format_version=TRAINER_INPUT_DATASET_FORMAT_VERSION,
        reward_allocation="terminal_step",
        source_rollout_count=len(records),
        segment_count=len(records),
        snapshot_feature_size=len(records[0].snapshot_features) if records else None,
        action_feature_size=(
            len(records[0].legal_action_features[0]) if records else None
        ),
        decision_record_schema_version=DECISION_RECORD_SCHEMA_VERSION,
        tactical_feature_schema_id=TACTICAL_FEATURE_SCHEMA_ID,
        tactical_feature_schema_version=TACTICAL_FEATURE_SCHEMA_VERSION,
        identity_vocabulary_version=IDENTITY_VOCABULARY_VERSION,
        structured_battle_outcome_schema_id=BATTLE_RESOURCE_OUTCOME_SCHEMA_ID,
        structured_battle_outcome_schema_version=(
            BATTLE_RESOURCE_OUTCOME_SCHEMA_VERSION
        ),
        generation_metadata={"fixture": "t009"},
        records=records,
    )


def _record(index: int, *, ascension: int, act: int) -> TrainerInputRecord:
    raw = _raw(index, ascension=ascension, act=act, battle_active=True)
    actions = _actions()
    identities = action_identity_dicts_for_actions(actions)
    chosen_index = index % 2
    outcome_status, outcome_payload = _structured_outcome(
        index,
        ascension=ascension,
        act=act,
        victory=chosen_index == 0,
    )
    return TrainerInputRecord(
        example_index=index,
        rollout_index=index,
        seed=100 + index,
        step_index=index,
        screen_state="BATTLE",
        snapshot_features=encode_lightspeed_battle_snapshot(raw),
        legal_action_features=encode_simulator_actions(actions, raw),
        legal_action_kinds=[action.kind for action in actions],
        legal_action_identities=identities,
        eligible_action_indices=[0, 1],
        chosen_action_index=chosen_index,
        chosen_action_id=actions[chosen_index].action_id,
        chosen_action_identity=identities[chosen_index],
        chosen_action_kind=actions[chosen_index].kind,
        terminal_after_step=True,
        controller_provenance={
            "kind": "decision_policy",
            "name": "fixture",
            "config": {"information_regime": "normal_public_policy"},
        },
        source_metadata={
            "source_kind": "natural_run",
            "distribution_kind": "natural_run",
            "source_run_id": f"seed-{100 + index}-run-0",
            "source_battle_index": 0,
            "source_checkpoint_id": f"cp-{index}",
            "seed": 100 + index,
            "ascension": ascension,
            "act": act,
            "floor": index + 1,
            "room_type": "MONSTER",
            "encounter_id": f"FixtureEncounter{index}",
        },
        feature_schema_id=TACTICAL_FEATURE_SCHEMA_ID,
        tactical_state=build_public_tactical_state(raw),
        tactical_legal_actions=build_public_tactical_actions(actions, raw),
        public_context_status="available",
        public_run_context=build_public_run_context(
            raw,
            actions,
            projection=None,
            history=[],
        ),
        segment_index=index,
        segment_step_index=0,
        segment_decision_count=1,
        segment_end_reason="terminal_victory" if chosen_index == 0 else "terminal_loss",
        is_segment_final_step=True,
        segment_reward=1.0 if chosen_index == 0 else -1.0,
        step_reward=1.0 if chosen_index == 0 else -1.0,
        return_to_go=1.0 if chosen_index == 0 else -1.0,
        reward_contributions={"battle_outcome": 1.0 if chosen_index == 0 else -1.0},
        raw_reward_components={"terminal_absolute_current_hp": 45.0 - index},
        structured_battle_outcome_status=outcome_status,
        structured_battle_outcome=outcome_payload,
    )


def _actions() -> list[SimulatorAction]:
    return [
        SimulatorAction(
            action_id="end",
            label="End Turn",
            kind="end_turn",
            raw={"scope": "battle", "idx1": 0, "idx2": 0, "idx3": 0},
        ),
        SimulatorAction(
            action_id="strike",
            label="Strike",
            kind="card",
            raw={"scope": "battle", "idx1": 0, "idx2": 0, "idx3": 0},
        ),
    ]


def _structured_outcome(
    index: int,
    *,
    ascension: int,
    act: int,
    victory: bool,
) -> tuple[str, dict[str, object]]:
    start = _raw(index, ascension=ascension, act=act, battle_active=True)
    terminal = {
        **_raw(index, ascension=ascension, act=act, battle_active=False),
        "outcome": "PLAYER_VICTORY" if victory else "PLAYER_LOSS",
        "completed_battle_outcome": "PLAYER_VICTORY" if victory else "PLAYER_LOSS",
        "cur_hp": 45 - index if victory else 0,
        "gold": 100 + index,
        "potions": [
            {
                "slot_index": 0,
                "id": "Potion Slot",
                "name": "Potion Slot",
            },
            {
                "slot_index": 1,
                "id": "Weak Potion",
                "name": "Weak Potion",
            },
        ],
    }
    return available_battle_resource_outcome(
        build_battle_resource_outcome(start, terminal)
    )


def _raw(
    index: int,
    *,
    ascension: int,
    act: int,
    battle_active: bool,
) -> dict[str, object]:
    return {
        "screen_state": "BATTLE" if battle_active else "BOSS_REWARD",
        "battle_active": battle_active,
        "outcome": "UNDECIDED" if battle_active else "PLAYER_VICTORY",
        "completed_battle_outcome": "UNDECIDED" if battle_active else "PLAYER_VICTORY",
        "ascension": ascension,
        "act": act,
        "floor_num": index + 1,
        "room_type": "MONSTER",
        "encounter_id": f"FixtureEncounter{index}",
        "cur_hp": 60 - index,
        "max_hp": 80 + index,
        "gold": 90 + index,
        "potion_capacity": 2,
        "potions": [
            {
                "slot_index": 0,
                "id": "Potion Slot",
                "name": "Potion Slot",
            },
            {
                "slot_index": 1,
                "id": "Potion Slot",
                "name": "Potion Slot",
            },
        ],
        "deck": [
            {"id": "Strike_R", "name": "Strike", "type": "ATTACK"},
            {"id": "Defend_R", "name": "Defend", "type": "SKILL"},
        ],
        "relics": [
            {"id": "Burning Blood", "name": "Burning Blood", "counter": 0},
        ],
        "blue_key": False,
        "green_key": False,
        "red_key": False,
        "battle_player": {
            "current_hp": 60 - index,
            "max_hp": 80 + index,
            "energy": 3,
            "block": 0,
        },
        "battle_hand": [
            {
                "id": "Strike_R",
                "name": "Strike",
                "type": "ATTACK",
                "cost": 1,
                "playable": True,
                "requires_target": True,
            }
        ],
        "battle_hand_size": 1,
        "battle_draw_pile_size": 4,
        "battle_discard_pile_size": 1,
        "battle_exhaust_pile_size": 0,
        "battle_monsters": [
            {
                "id": "Cultist",
                "name": "Cultist",
                "current_hp": 48,
                "max_hp": 48,
                "intent": "ATTACK",
                "intent_category": "ATTACK",
            }
        ],
    }
