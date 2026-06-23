from __future__ import annotations

from dataclasses import dataclass, replace
from io import StringIO
import json

import pytest

from sts_combat_rl.sim.battle_start_pool import (
    CHECKPOINT_INFORMATION_REGIME,
    LEGACY_UNKNOWN_INFORMATION_REGIME,
    NATURAL_SAMPLING_COMPONENT,
    STRUCTURAL_SAMPLING_COMPONENT,
    build_battle_start_pool_coverage_report,
    collect_natural_battle_start_pool,
    dump_natural_battle_start_pool_jsonl,
    load_natural_battle_start_pool_jsonl,
    restore_battle_start_record,
    sample_battle_start_pool,
    verify_battle_start_pool_restores,
)
from sts_combat_rl.sim.contract import (
    SimulatorAction,
    SimulatorCheckpoint,
    SimulatorSnapshot,
    SimulatorTransition,
)
from sts_combat_rl.sim.online_controller import PolicyController, RoutedRunController
from sts_combat_rl.sim.policy import FirstEligiblePolicy


@dataclass
class _PoolPayload:
    seed: int
    phase: int


class FakePoolAdapter:
    """Run with two battles and duplicate non-combat action ids before the second."""

    @property
    def checkpoint_adapter_id(self) -> str:
        return self._adapter_id

    @property
    def supports_checkpoint_restore(self) -> bool:
        return True

    def __init__(self, adapter_id: str = "pool") -> None:
        self._adapter_id = adapter_id
        self.seed = 0
        self.phase = 0
        self._checkpoint_counter = 0

    def reset(self, seed: int | None = None) -> SimulatorSnapshot:
        self.seed = 0 if seed is None else seed
        self.phase = 0
        return self._snapshot()

    def legal_actions(self, snapshot: SimulatorSnapshot) -> list[SimulatorAction]:
        del snapshot
        if self.phase == 2:
            return [
                SimulatorAction(
                    action_id="game:duplicate",
                    label="first duplicate",
                    kind="event",
                ),
                SimulatorAction(
                    action_id="game:duplicate",
                    label="wrong duplicate",
                    kind="event",
                ),
            ]
        return [
            SimulatorAction(
                action_id=f"{'battle' if self.phase in {1, 3} else 'game'}:{self.phase}",
                label=f"phase {self.phase}",
                kind="card" if self.phase in {1, 3} else "event",
            )
        ]

    def step(self, action: SimulatorAction) -> SimulatorTransition:
        if self.phase == 2 and action.label == "wrong duplicate":
            self.phase = 4
        else:
            self.phase += 1
        return SimulatorTransition(snapshot=self._snapshot(), terminal=self.phase == 4)

    def capture_checkpoint(self, snapshot: SimulatorSnapshot) -> SimulatorCheckpoint:
        del snapshot
        self._checkpoint_counter += 1
        return SimulatorCheckpoint(
            adapter_id=self._adapter_id,
            checkpoint_id=f"{self._adapter_id}:{self._checkpoint_counter}",
            payload=_PoolPayload(self.seed, self.phase),
        )

    def restore_checkpoint(self, checkpoint: SimulatorCheckpoint) -> SimulatorSnapshot:
        if checkpoint.adapter_id != self._adapter_id:
            raise ValueError("foreign checkpoint")
        self.seed = checkpoint.payload.seed
        self.phase = checkpoint.payload.phase
        return self._snapshot()

    def _snapshot(self) -> SimulatorSnapshot:
        battle_active = self.phase in {1, 3}
        next_act = 2 if self.phase >= 3 else 1
        raw: dict[str, object] = {
            "screen_state": "BATTLE" if battle_active else "EVENT",
            "battle_active": battle_active,
            "outcome": "PLAYER_LOSS" if self.phase == 4 else "UNDECIDED",
            "ascension": 20,
            "act": next_act,
            "floor_num": self.phase + 1,
            "room_type": "ELITE" if self.phase == 3 else "MONSTER",
            "encounter_id": f"ENCOUNTER_{self.phase}" if battle_active else None,
        }
        if battle_active:
            raw["battle_outcome"] = "UNDECIDED"
        elif self.phase == 2:
            # Regression surface for a winning battle that enters rewards while
            # the run itself remains undecided.
            raw["completed_battle_outcome"] = "PLAYER_VICTORY"
        elif self.phase == 4:
            raw["completed_battle_outcome"] = "PLAYER_LOSS"
        return SimulatorSnapshot(
            observation=[self.seed, self.phase],
            raw=raw,
        )


class MissingOutcomePoolAdapter(FakePoolAdapter):
    """Pool adapter that exits one battle without an authoritative outcome."""

    def _snapshot(self) -> SimulatorSnapshot:
        snapshot = super()._snapshot()
        raw = dict(snapshot.raw)
        if self.phase == 2:
            raw.pop("completed_battle_outcome", None)
        return SimulatorSnapshot(observation=snapshot.observation, raw=raw)


def _controller() -> RoutedRunController:
    return RoutedRunController(
        battle=PolicyController(FirstEligiblePolicy()),
        non_combat=PolicyController(FirstEligiblePolicy()),
    )


def _pool() -> object:
    return collect_natural_battle_start_pool(
        FakePoolAdapter(),
        _controller(),
        seeds=[7, 8],
        max_steps=10,
    )


def test_natural_pool_captures_provenance_coverage_and_seeded_sampling() -> None:
    pool = _pool()
    report = build_battle_start_pool_coverage_report(pool)  # type: ignore[arg-type]
    sampled = sample_battle_start_pool(  # type: ignore[arg-type]
        pool,
        sample_count=12,
        seed=99,
        structural_fraction=0.5,
    )
    same_sampled = sample_battle_start_pool(  # type: ignore[arg-type]
        pool,
        sample_count=12,
        seed=99,
        structural_fraction=0.5,
    )
    sampled_report = build_battle_start_pool_coverage_report(  # type: ignore[arg-type]
        pool,
        sampled=sampled,
    )

    assert len(pool.records) == 4  # type: ignore[union-attr]
    assert all(record.source_controller_provenance for record in pool.records)  # type: ignore[union-attr]
    assert all(record.source_battle_controller_provenance for record in pool.records)  # type: ignore[union-attr]
    assert all(
        record.source_non_combat_controller_provenance for record in pool.records
    )  # type: ignore[union-attr]
    assert all(
        record.checkpoint_information_regime == CHECKPOINT_INFORMATION_REGIME
        for record in pool.records
    )  # type: ignore[union-attr]
    assert all(record.public_context_status == "available" for record in pool.records)  # type: ignore[union-attr]
    assert all(record.public_run_context for record in pool.records)  # type: ignore[union-attr]
    assert report.natural_battle_start_count == 4
    assert report.unique_source_start_count == 4
    assert report.reported_battle_win_count == 2
    assert report.completed_battle_count == 4
    assert report.completed_outcomes_complete is True
    assert report.resource_outcome_status_counts["available"] == 4
    assert report.later_act_source_run_count == 2
    assert sampled == same_sampled
    assert {sample.sampling_component for sample in sampled} <= {
        NATURAL_SAMPLING_COMPONENT,
        STRUCTURAL_SAMPLING_COMPONENT,
    }
    assert all(
        sample.source_checkpoint_id == sample.record.source_checkpoint_id
        for sample in sampled
    )
    assert sampled_report.sampled_draw_count == 12


def test_coverage_fails_when_a_completed_battle_omits_its_outcome() -> None:
    pool = _pool()
    missing_outcome = replace(
        pool.records[0],
        battle_completed=True,
        battle_outcome=None,
    )

    report = build_battle_start_pool_coverage_report(
        replace(pool, records=[missing_outcome, *pool.records[1:]])
    )

    assert report.completed_outcomes_complete is False
    assert report.completed_battle_outcome_missing_count == 1
    assert "completed battle outcomes are missing" in report.problems[0]


def test_collector_marks_battle_exit_without_outcome_unavailable() -> None:
    pool = collect_natural_battle_start_pool(
        MissingOutcomePoolAdapter(),
        _controller(),
        seeds=[7],
        max_steps=4,
    )
    report = build_battle_start_pool_coverage_report(pool)

    assert pool.records[0].battle_completed is False
    assert pool.records[0].completed_battle_resource_outcome_status == "unavailable"
    assert (
        pool.records[0].completed_battle_resource_outcome["reason"]
        == "missing_authoritative_battle_outcome"
    )
    assert any(
        "without authoritative terminal outcome" in problem
        for problem in report.problems
    )


def test_portable_pool_manifest_replays_duplicate_action_ids_in_fresh_adapters() -> (
    None
):
    pool = _pool()
    stream = StringIO()
    dump_natural_battle_start_pool_jsonl(pool, stream)  # type: ignore[arg-type]
    loaded = load_natural_battle_start_pool_jsonl(StringIO(stream.getvalue()))

    restored, method = restore_battle_start_record(
        FakePoolAdapter("fresh"), loaded.records[1]
    )
    verification = verify_battle_start_pool_restores(
        lambda: FakePoolAdapter("fresh"),
        loaded,
    )

    assert method == "seed_action_trace"
    assert restored.raw == loaded.records[1].snapshot_raw
    assert loaded.records[1].native_checkpoint is None
    assert loaded.records[1].action_trace[2]["occurrence"] == 0
    assert loaded.records[1].completed_battle_resource_outcome_status == "available"
    assert (
        loaded.records[1].completed_battle_resource_outcome["schema_id"]
        == "structured-battle-outcome-v1"
    )
    assert verification.restore_ok is True
    assert verification.replay_restored_count == 4
    assert verification.context_matched_count == 4


def test_v1_migration_preserves_missing_duplicate_information_and_fails_closed() -> (
    None
):
    pool = _pool()
    current = StringIO()
    dump_natural_battle_start_pool_jsonl(pool, current)  # type: ignore[arg-type]
    rows = [json.loads(line) for line in current.getvalue().splitlines()]
    metadata = rows[0]["metadata"]
    metadata["format_version"] = 1
    metadata["source_non_combat_policy"] = pool.records[
        0
    ].source_non_combat_controller_provenance["name"]  # type: ignore[union-attr]
    metadata["source_battle_policy"] = pool.records[
        0
    ].source_battle_controller_provenance["name"]  # type: ignore[union-attr]
    metadata.pop("source_controller_provenance")
    metadata.pop("migration_report")
    for row in rows[1:]:
        record = row["record"]
        structural = record.pop("structural_metadata")
        for field_name in ("ascension", "act", "floor", "room_type", "encounter_id"):
            record[field_name] = structural[field_name]
        record["checkpoint_id"] = record.pop("source_checkpoint_id")
        record["seed"] = record.pop("source_seed")
        record["battle_index"] = record.pop("source_battle_index")
        record["observation"] = record.pop("snapshot_observation")
        record["raw_snapshot"] = record.pop("snapshot_raw")
        record["action_trace"] = [
            identity["action_id"] for identity in record["action_trace"]
        ]
        record["source_non_combat_policy"] = record.pop(
            "source_non_combat_controller_provenance"
        )["name"]
        record["source_battle_policy"] = record.pop(
            "source_battle_controller_provenance"
        )["name"]
        record.pop("source_controller_provenance")
        record.pop("battle_outcome")
        record.pop("distribution_kind")
    legacy = "\n".join(json.dumps(row) for row in rows)

    loaded = load_natural_battle_start_pool_jsonl(StringIO(legacy))

    assert loaded.migration_report.source_version == 1
    assert loaded.migration_report.losses
    assert (
        loaded.records[1].checkpoint_information_regime
        == LEGACY_UNKNOWN_INFORMATION_REGIME
    )
    assert loaded.records[1].public_context_status == "legacy_unavailable"
    assert loaded.records[1].action_trace[2]["occurrence"] is None
    with pytest.raises(ValueError, match="omitted duplicate occurrence"):
        restore_battle_start_record(FakePoolAdapter("fresh"), loaded.records[1])


def test_incomplete_manifest_fails_instead_of_guessing_source_seed() -> None:
    pool = _pool()
    stream = StringIO()
    dump_natural_battle_start_pool_jsonl(pool, stream)  # type: ignore[arg-type]
    rows = [json.loads(line) for line in stream.getvalue().splitlines()]
    rows[1]["record"].pop("source_seed")

    with pytest.raises(ValueError, match="source seed"):
        load_natural_battle_start_pool_jsonl(
            StringIO("\n".join(json.dumps(row) for row in rows))
        )
