from __future__ import annotations

from dataclasses import replace
from io import StringIO
import json
from pathlib import Path

import pytest

from sts_combat_rl.sim.decision_record import (
    DECISION_RECORD_SCHEMA_VERSION,
    action_identity_dicts_for_actions,
    stable_action_identity_id,
)
from sts_combat_rl.sim.contract import SimulatorAction
from sts_combat_rl.sim.features import (
    IDENTITY_VOCABULARY_VERSION,
    TACTICAL_FEATURE_SCHEMA_ID,
    TACTICAL_FEATURE_SCHEMA_VERSION,
    build_public_tactical_actions,
    build_public_tactical_state,
    encode_lightspeed_battle_snapshot,
    encode_simulator_actions,
)
from sts_combat_rl.sim.trainer_input import (
    TRAINER_INPUT_DATASET_FORMAT_VERSION,
    TrainerInputDataset,
    TrainerInputRecord,
    dump_trainer_input_dataset_jsonl,
    load_trainer_input_dataset_jsonl_text,
    trainer_input_dataset_to_jsonl_text,
)
from sts_combat_rl.sim.public_run_context import build_public_run_context


def test_trainer_input_v1_fixture_migrates_to_current_schema() -> None:
    text = Path("tests/fixtures/trainer_input_v1_legacy.jsonl").read_text(
        encoding="utf-8"
    )

    dataset = load_trainer_input_dataset_jsonl_text(text)
    record = dataset.records[0]

    assert dataset.format_version == TRAINER_INPUT_DATASET_FORMAT_VERSION
    assert dataset.decision_record_schema_version == DECISION_RECORD_SCHEMA_VERSION
    assert dataset.migration_report.source_version == 1
    assert (
        dataset.migration_report.target_version == TRAINER_INPUT_DATASET_FORMAT_VERSION
    )
    assert dataset.migration_report.applied_versions == (2, 3, 4)
    assert "v1 omitted per-decision controller provenance" in (
        dataset.migration_report.losses
    )
    assert record.controller_provenance == {}
    assert record.source_metadata["source_kind"] == "unknown"
    assert record.legal_action_identities[0]["action_id"] is None
    assert record.legal_action_identities[1]["occurrence"] == 1
    assert record.chosen_action_identity == record.legal_action_identities[1]
    assert dataset.tactical_feature_schema_id == "legacy-unversioned"
    assert record.tactical_state == {}
    assert record.tactical_legal_actions == []
    assert (
        "v2 fixed numeric features cannot reconstruct v2 structured tactical inputs"
        in (dataset.migration_report.losses)
    )
    assert record.public_context_status == "legacy_unavailable"
    assert record.public_run_context == {}
    assert any("public run context" in item for item in dataset.migration_report.losses)
    assert any("controller provenance is missing" in item for item in dataset.problems)


def test_trainer_input_writer_rejects_non_current_schema() -> None:
    current = _current_dataset()
    legacy = replace(current, format_version=1)

    with pytest.raises(ValueError, match="only emits current format version"):
        dump_trainer_input_dataset_jsonl(legacy, StringIO())


def test_trainer_input_writer_rejects_non_current_record_schema() -> None:
    current = _current_dataset()
    bad_record = replace(current.records[0], record_schema_version=99)
    corrupted = replace(current, records=[bad_record])

    with pytest.raises(ValueError, match="record 0 schema 99"):
        dump_trainer_input_dataset_jsonl(corrupted, StringIO())


def test_trainer_input_loader_reports_malformed_action_identity() -> None:
    current = _current_dataset()
    rows = [
        json.loads(line)
        for line in trainer_input_dataset_to_jsonl_text(current).splitlines()
    ]
    record = rows[1]["record"]
    record["legal_action_identities"][1]["stable_id"] = "bad"
    record["chosen_action_identity"]["stable_id"] = "bad"
    corrupted_text = "\n".join(
        json.dumps(row, sort_keys=True, separators=(",", ":")) for row in rows
    )

    loaded = load_trainer_input_dataset_jsonl_text(corrupted_text)

    assert any("legal action identity 1 is invalid" in item for item in loaded.problems)
    assert any("chosen action identity is invalid" in item for item in loaded.problems)


@pytest.mark.parametrize(
    ("legal_action_identities", "chosen_action_identity", "expected_problems"),
    [
        ([], None, ("legal action identities are missing",)),
        (None, {}, ("chosen action identity is missing",)),
        (
            [],
            {},
            (
                "legal action identities are missing",
                "chosen action identity is missing",
            ),
        ),
    ],
)
def test_trainer_input_loader_reports_missing_action_identities(
    legal_action_identities: list[dict[str, object]] | None,
    chosen_action_identity: dict[str, object] | None,
    expected_problems: tuple[str, ...],
) -> None:
    current = _current_dataset()
    rows = [
        json.loads(line)
        for line in trainer_input_dataset_to_jsonl_text(current).splitlines()
    ]
    record = rows[1]["record"]
    if legal_action_identities is not None:
        record["legal_action_identities"] = legal_action_identities
    if chosen_action_identity is not None:
        record["chosen_action_identity"] = chosen_action_identity

    loaded = load_trainer_input_dataset_jsonl_text(_jsonl_text(rows))

    for expected in expected_problems:
        assert any(expected in item for item in loaded.problems)


@pytest.mark.parametrize(
    ("legal_action_identities", "chosen_action_identity", "expected_problem"),
    [
        ([], None, "legal action identities are missing"),
        (None, {}, "chosen action identity is missing"),
        ([], {}, "legal action identities are missing"),
    ],
)
def test_trainer_input_writer_rejects_missing_action_identities(
    legal_action_identities: list[dict[str, object]] | None,
    chosen_action_identity: dict[str, object] | None,
    expected_problem: str,
) -> None:
    current = _current_dataset()
    record = current.records[0]
    corrupted = replace(
        current,
        records=[
            replace(
                record,
                legal_action_identities=(
                    record.legal_action_identities
                    if legal_action_identities is None
                    else legal_action_identities
                ),
                chosen_action_identity=(
                    record.chosen_action_identity
                    if chosen_action_identity is None
                    else chosen_action_identity
                ),
            )
        ],
    )

    with pytest.raises(ValueError, match=expected_problem):
        dump_trainer_input_dataset_jsonl(corrupted, StringIO())


def _corrupt_identity_kind(record: dict[str, object]) -> None:
    _replace_chosen_identity(record, kind="end_turn")


def _corrupt_identity_duplicate_occurrence(record: dict[str, object]) -> None:
    _replace_chosen_identity(record, occurrence=0)


def _corrupt_identity_skipped_occurrence(record: dict[str, object]) -> None:
    _replace_chosen_identity(record, occurrence=2)


def _corrupt_chosen_action_id(record: dict[str, object]) -> None:
    record["chosen_action_id"] = "not-the-chosen-identity"


def _replace_chosen_identity(record: dict[str, object], **changes: object) -> None:
    identities = record["legal_action_identities"]
    assert isinstance(identities, list)
    chosen_index = record["chosen_action_index"]
    assert isinstance(chosen_index, int)
    identity = dict(identities[chosen_index])
    identity.update(changes)
    identity["stable_id"] = stable_action_identity_id(
        action_id=identity["action_id"],
        occurrence=identity["occurrence"],
        kind=identity["kind"],
    )
    identities[chosen_index] = identity
    record["chosen_action_identity"] = dict(identity)


@pytest.mark.parametrize(
    ("corrupt_record", "expected_problem"),
    [
        (_corrupt_identity_kind, "does not match action kind"),
        (
            _corrupt_identity_duplicate_occurrence,
            "occurrence 0 does not match expected 1",
        ),
        (
            _corrupt_identity_skipped_occurrence,
            "occurrence 2 does not match expected 1",
        ),
        (_corrupt_chosen_action_id, "chosen action id does not match"),
    ],
)
def test_trainer_input_loader_reports_identity_action_inconsistency(
    corrupt_record,
    expected_problem: str,
) -> None:
    rows = _current_dataset_rows()
    corrupt_record(rows[1]["record"])

    loaded = load_trainer_input_dataset_jsonl_text(_jsonl_text(rows))

    assert any(expected_problem in item for item in loaded.problems)


@pytest.mark.parametrize(
    ("corrupt_record", "expected_problem"),
    [
        (_corrupt_identity_kind, "does not match action kind"),
        (
            _corrupt_identity_duplicate_occurrence,
            "occurrence 0 does not match expected 1",
        ),
        (
            _corrupt_identity_skipped_occurrence,
            "occurrence 2 does not match expected 1",
        ),
        (_corrupt_chosen_action_id, "chosen action id does not match"),
    ],
)
def test_trainer_input_writer_rejects_identity_action_inconsistency(
    corrupt_record,
    expected_problem: str,
) -> None:
    rows = _current_dataset_rows()
    corrupt_record(rows[1]["record"])
    corrupted = load_trainer_input_dataset_jsonl_text(_jsonl_text(rows))

    with pytest.raises(ValueError, match=expected_problem):
        dump_trainer_input_dataset_jsonl(corrupted, StringIO())


def _current_dataset():
    raw = {
        "screen_state": "BATTLE",
        "battle_active": True,
        "ascension": 20,
        "act": 1,
        "floor_num": 3,
        "room_type": "MONSTER",
        "battle_turn": 1,
        "battle_player": {
            "current_hp": 70,
            "max_hp": 80,
            "energy": 3,
            "block": 0,
        },
        "battle_hand_size": 1,
        "battle_draw_pile_size": 4,
        "battle_discard_pile_size": 0,
        "battle_exhaust_pile_size": 0,
        "battle_hand": [
            {
                "id": "Strike_R",
                "type": "ATTACK",
                "cost": 1,
                "playable": True,
                "requires_target": True,
            }
        ],
        "battle_monsters": [
            {"id": "Cultist", "current_hp": 48, "intent": "ATTACK"},
            {"id": "JawWorm", "current_hp": 40, "intent": "BUFF"},
        ],
    }
    actions = [
        SimulatorAction(
            action_id="card:Strike_R",
            label="Strike Cultist",
            kind="card",
            raw={"scope": "battle", "idx1": 0, "idx2": 0, "idx3": 0},
        ),
        SimulatorAction(
            action_id="card:Strike_R",
            label="Strike Jaw Worm",
            kind="card",
            raw={"scope": "battle", "idx1": 0, "idx2": 1, "idx3": 0},
        ),
    ]
    identities = action_identity_dicts_for_actions(actions)
    record = TrainerInputRecord(
        example_index=0,
        rollout_index=0,
        seed=11,
        step_index=3,
        screen_state="BATTLE",
        snapshot_features=encode_lightspeed_battle_snapshot(raw),
        legal_action_features=encode_simulator_actions(actions, raw),
        legal_action_kinds=[action.kind for action in actions],
        legal_action_identities=identities,
        eligible_action_indices=[0, 1],
        chosen_action_index=1,
        chosen_action_id=actions[1].action_id,
        chosen_action_identity=identities[1],
        chosen_action_kind="card",
        terminal_after_step=True,
        controller_provenance={"controller": "test"},
        source_metadata={"source_kind": "natural_run"},
        feature_schema_id=TACTICAL_FEATURE_SCHEMA_ID,
        tactical_state=build_public_tactical_state(raw),
        tactical_legal_actions=build_public_tactical_actions(actions, raw),
        public_context_status="available",
        public_run_context=build_public_run_context(
            raw,
            actions,
            projection=None,
        ),
        segment_index=0,
        segment_step_index=0,
        segment_decision_count=1,
        segment_end_reason="terminal_victory",
        is_segment_final_step=True,
        segment_reward=1.0,
        step_reward=1.0,
        return_to_go=1.0,
        reward_contributions={"win": 1.0},
        raw_reward_components={"hp_delta": None},
    )
    return TrainerInputDataset(
        format_version=TRAINER_INPUT_DATASET_FORMAT_VERSION,
        reward_allocation="terminal_step",
        source_rollout_count=1,
        segment_count=1,
        snapshot_feature_size=len(record.snapshot_features),
        action_feature_size=len(record.legal_action_features[0]),
        decision_record_schema_version=DECISION_RECORD_SCHEMA_VERSION,
        tactical_feature_schema_id=TACTICAL_FEATURE_SCHEMA_ID,
        tactical_feature_schema_version=TACTICAL_FEATURE_SCHEMA_VERSION,
        identity_vocabulary_version=IDENTITY_VOCABULARY_VERSION,
        records=[record],
    )


def _current_dataset_rows() -> list[dict[str, object]]:
    return [
        json.loads(line)
        for line in trainer_input_dataset_to_jsonl_text(_current_dataset()).splitlines()
    ]


def _jsonl_text(rows: list[dict[str, object]]) -> str:
    return "\n".join(
        json.dumps(row, sort_keys=True, separators=(",", ":")) for row in rows
    )
