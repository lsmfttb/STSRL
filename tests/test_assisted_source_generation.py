from __future__ import annotations

from dataclasses import dataclass
from io import StringIO

from sts_combat_rl.sim.assisted_source_generation import (
    ASSISTANCE_LEVELS,
    ASSIST_LEVEL_HP50,
    ASSIST_LEVEL_HP50_POTION_ELITE_BOSS,
    ASSISTED_RUN_DISTRIBUTION_KIND,
    build_assisted_a20_coverage_report,
    collect_assisted_battle_start_pool,
    dump_assisted_source_coverage_comparison_report_json,
    dump_assisted_source_pool_jsonl,
    load_assisted_source_pool_jsonl,
    merge_assisted_source_pool_shards,
    verify_assisted_source_pool_restores,
    write_assisted_a20_coverage_report,
)
from sts_combat_rl.commands.assisted_source_generation import (
    merge_assisted_a20_coverage_from_paths,
    merge_assisted_source_pool_from_paths,
    run_assisted_source_coverage_report_from_paths,
)
from sts_combat_rl.sim.contract import (
    SimulatorAction,
    SimulatorCheckpoint,
    SimulatorSnapshot,
    SimulatorTransition,
)
from sts_combat_rl.sim.lightspeed_source import lightspeed_source_identity_dict
from sts_combat_rl.sim.online_controller import PolicyController, RoutedRunController
from sts_combat_rl.sim.policy import FirstEligiblePolicy
from sts_combat_rl.sim.training_gate import TrainingScaleGateConfig


@dataclass(frozen=True)
class _AssistedPayload:
    seed: int
    phase: int
    hp: int
    potions: tuple[str | None, ...]


class _AssistedAdapter:
    @property
    def checkpoint_adapter_id(self) -> str:
        return self._adapter_id

    @property
    def supports_checkpoint_restore(self) -> bool:
        return True

    def __init__(self, adapter_id: str = "assisted") -> None:
        self._adapter_id = adapter_id
        self.seed = 0
        self.phase = 0
        self.hp = 20
        self.potions: tuple[str | None, ...] = (None, None)
        self._checkpoint_counter = 0

    def reset(self, seed: int | None = None) -> SimulatorSnapshot:
        self.seed = 0 if seed is None else seed
        self.phase = 0
        self.hp = 20
        self.potions = (None, None)
        return self._snapshot()

    def legal_actions(self, snapshot: SimulatorSnapshot) -> list[SimulatorAction]:
        del snapshot
        return [
            SimulatorAction(
                action_id=f"{'battle' if self.phase in {1, 3} else 'game'}:{self.phase}",
                label=f"phase {self.phase}",
                kind="card" if self.phase in {1, 3} else "event",
            )
        ]

    def step(self, action: SimulatorAction) -> SimulatorTransition:
        del action
        self.phase += 1
        return SimulatorTransition(snapshot=self._snapshot(), terminal=self.phase == 4)

    def capture_checkpoint(self, snapshot: SimulatorSnapshot) -> SimulatorCheckpoint:
        del snapshot
        self._checkpoint_counter += 1
        return SimulatorCheckpoint(
            adapter_id=self._adapter_id,
            checkpoint_id=f"{self._adapter_id}:{self._checkpoint_counter}",
            payload=_AssistedPayload(self.seed, self.phase, self.hp, self.potions),
        )

    def restore_checkpoint(self, checkpoint: SimulatorCheckpoint) -> SimulatorSnapshot:
        if checkpoint.adapter_id != self._adapter_id:
            raise ValueError("foreign checkpoint")
        self.seed = checkpoint.payload.seed
        self.phase = checkpoint.payload.phase
        self.hp = checkpoint.payload.hp
        self.potions = checkpoint.payload.potions
        return self._snapshot()

    def rebuild_battle_start(
        self,
        snapshot: SimulatorSnapshot,
        *,
        hp_bonus: int = 0,
        add_random_potion: bool = False,
        encounter_id: int | None = None,
    ) -> SimulatorSnapshot:
        del snapshot, encounter_id
        self.hp = min(80, self.hp + hp_bonus)
        if add_random_potion and None in self.potions:
            potions = list(self.potions)
            potions[potions.index(None)] = "Strength Potion"
            self.potions = tuple(potions)
        return self._snapshot()

    def _snapshot(self) -> SimulatorSnapshot:
        battle_active = self.phase in {1, 3}
        room_type = "ELITE" if self.phase == 3 else "MONSTER"
        raw: dict[str, object] = {
            "screen_state": "BATTLE" if battle_active else "EVENT",
            "battle_active": battle_active,
            "outcome": "PLAYER_VICTORY" if self.phase == 4 else "UNDECIDED",
            "ascension": 20,
            "act": 2 if self.phase >= 3 else 1,
            "floor_num": self.phase + 1,
            "room_type": room_type,
            "encounter_id": f"{room_type}_{self.phase}" if battle_active else None,
            "cur_hp": self.hp,
            "max_hp": 80,
            "gold": 99,
            "potion_count": sum(1 for potion in self.potions if potion is not None),
            "potion_capacity": len(self.potions),
            "potions": [
                {"id": potion or "Potion Slot", "name": potion or "Potion Slot"}
                for potion in self.potions
            ],
        }
        if battle_active:
            raw["battle_outcome"] = "UNDECIDED"
        elif self.phase in {2, 4}:
            raw["completed_battle_outcome"] = "PLAYER_VICTORY"
        return SimulatorSnapshot(
            observation=[
                self.seed,
                self.phase,
                self.hp,
                sum(1 for potion in self.potions if potion is not None),
            ],
            raw=raw,
        )


class _NoRebuildAdapter(_AssistedAdapter):
    rebuild_battle_start = None


def _controller() -> RoutedRunController:
    return RoutedRunController(
        battle=PolicyController(FirstEligiblePolicy()),
        non_combat=PolicyController(FirstEligiblePolicy()),
    )


def test_assisted_pool_records_hp_potion_provenance_and_restores() -> None:
    artifact, coverage = collect_assisted_battle_start_pool(
        _AssistedAdapter(),
        _controller(),
        seeds=[7],
        max_steps=10,
        assistance_level=ASSIST_LEVEL_HP50_POTION_ELITE_BOSS,
        policy_seed=42,
    )

    assert coverage.natural_battle_start_count == 2
    assert [record.distribution_kind for record in artifact.records] == [
        ASSISTED_RUN_DISTRIBUTION_KIND,
        ASSISTED_RUN_DISTRIBUTION_KIND,
    ]
    first, second = artifact.records
    assert first.snapshot_raw["cur_hp"] == 40
    assert first.assistance_history[-1]["actual_change"]["current_hp_delta"] == 20
    assert first.assistance_history[-1]["actual_change"]["potion_count_delta"] == 0
    assert second.snapshot_raw["cur_hp"] == 40
    assert second.snapshot_raw["potion_count"] == 1
    assert second.assistance_history[-1]["actual_change"]["potion_count_delta"] == 1
    assert "assistance_level" not in second.public_run_context

    stream = StringIO()
    dump_assisted_source_pool_jsonl(artifact, stream)
    loaded = load_assisted_source_pool_jsonl(StringIO(stream.getvalue()))
    restore = verify_assisted_source_pool_restores(lambda: _AssistedAdapter(), loaded)

    assert restore.restore_ok
    assert restore.replay_restored_count == 2
    assert restore.context_matched_count == 2


def test_assisted_pool_records_unsupported_native_rebuild_as_noop() -> None:
    artifact, _ = collect_assisted_battle_start_pool(
        _NoRebuildAdapter(),
        _controller(),
        seeds=[3],
        max_steps=3,
        assistance_level=ASSIST_LEVEL_HP50,
        policy_seed=99,
    )

    decision = artifact.records[0].assistance_history[-1]

    assert decision["native_support_status"] == "unsupported"
    assert decision["actual_change"]["applied"] is False
    assert decision["actual_change"]["reason"] == "unsupported_native_operation"
    assert artifact.records[0].snapshot_raw["cur_hp"] == 20


def test_assisted_source_coverage_report_loads_required_schedule_arms(tmp_path) -> None:
    arm_specs: list[list[str]] = []
    for level in ASSISTANCE_LEVELS:
        artifact, _ = collect_assisted_battle_start_pool(
            _AssistedAdapter(),
            _controller(),
            seeds=[5],
            max_steps=5,
            assistance_level=level,
            policy_seed=11,
        )
        pool_path = tmp_path / f"{level}.jsonl"
        coverage_path = tmp_path / f"{level}-coverage.json"
        with pool_path.open("w", encoding="utf-8", newline="\n") as stream:
            dump_assisted_source_pool_jsonl(artifact, stream)
        restore = verify_assisted_source_pool_restores(
            lambda: _AssistedAdapter(),
            artifact,
        )
        coverage = build_assisted_a20_coverage_report(
            artifact,
            restore_report=restore,
            input_artifacts={
                "natural_pool": {
                    "path": str(pool_path),
                    "sha256": _sha256(pool_path),
                    "record_count": len(artifact.records),
                }
            },
            source_identity=lightspeed_source_identity_dict(),
        )
        write_assisted_a20_coverage_report(coverage_path, coverage)
        arm_specs.append([level, str(pool_path), str(coverage_path)])

    report = run_assisted_source_coverage_report_from_paths(
        output_path=tmp_path / "assisted-report.json",
        arm_specs=arm_specs,
    )
    stream = StringIO()
    dump_assisted_source_coverage_comparison_report_json(report, stream)

    assert report.schema_id == "assisted-run-source-coverage-comparison-v1"
    assert report.command_passed
    assert set(report.to_dict()["required_schedules"]) == set(ASSISTANCE_LEVELS)
    assert report.to_dict()["comparison"]["required_levels_present"] is True


def test_assisted_source_pool_shard_merge_preserves_replay_identity() -> None:
    first, _ = collect_assisted_battle_start_pool(
        _AssistedAdapter(),
        _controller(),
        seeds=[5],
        max_steps=5,
        assistance_level=ASSIST_LEVEL_HP50,
        policy_seed=11,
    )
    second, _ = collect_assisted_battle_start_pool(
        _AssistedAdapter(),
        _controller(),
        seeds=[6],
        max_steps=5,
        assistance_level=ASSIST_LEVEL_HP50,
        policy_seed=11,
    )

    merged = merge_assisted_source_pool_shards(
        [first, second],
        shard_identities=[
            {"path": "first.jsonl", "sha256": "a" * 64},
            {"path": "second.jsonl", "sha256": "b" * 64},
        ],
    )

    assert merged.pool.source_run_count == 2
    assert merged.pool.terminal_run_count == 2
    assert [record.record_index for record in merged.records] == list(
        range(len(merged.records))
    )
    assert len({record.source_checkpoint_id for record in merged.records}) == len(
        merged.records
    )
    assert all(
        decision["source_record_index"] == record.record_index
        for record in merged.records
        for decision in record.assistance_history[-1:]
    )
    assert [shard["path"] for shard in merged.source_shards] == [
        "first.jsonl",
        "second.jsonl",
    ]

    stream = StringIO()
    dump_assisted_source_pool_jsonl(merged, stream)
    loaded = load_assisted_source_pool_jsonl(StringIO(stream.getvalue()))
    restore = verify_assisted_source_pool_restores(lambda: _AssistedAdapter(), loaded)

    assert restore.restore_ok
    assert loaded.source_shards == merged.source_shards


def test_assisted_source_pool_path_merge_streams_loadable_artifact(tmp_path) -> None:
    shard_paths = []
    for seed in (5, 6):
        artifact, _ = collect_assisted_battle_start_pool(
            _AssistedAdapter(),
            _controller(),
            seeds=[seed],
            max_steps=5,
            assistance_level=ASSIST_LEVEL_HP50,
            policy_seed=11,
        )
        shard_path = tmp_path / f"shard-{seed}.jsonl"
        with shard_path.open("w", encoding="utf-8", newline="\n") as stream:
            dump_assisted_source_pool_jsonl(artifact, stream)
        shard_paths.append(shard_path)

    merged_path = tmp_path / "merged.jsonl"
    summary = merge_assisted_source_pool_from_paths(
        output_path=merged_path,
        shard_paths=shard_paths,
    )

    with merged_path.open("r", encoding="utf-8") as stream:
        loaded = load_assisted_source_pool_jsonl(stream)
    restore = verify_assisted_source_pool_restores(lambda: _AssistedAdapter(), loaded)

    assert summary.record_count == len(loaded.records)
    assert summary.assistance_decision_count == len(loaded.assistance_decisions)
    assert [shard["path"] for shard in loaded.source_shards] == [
        str(path) for path in shard_paths
    ]
    assert restore.restore_ok


def test_assisted_coverage_merge_uses_shard_restore_reports(tmp_path) -> None:
    shard_paths = []
    coverage_paths = []
    artifacts = []
    for seed in (5, 6):
        artifact, _ = collect_assisted_battle_start_pool(
            _AssistedAdapter(),
            _controller(),
            seeds=[seed],
            max_steps=5,
            assistance_level=ASSIST_LEVEL_HP50,
            policy_seed=11,
        )
        artifacts.append(artifact)
        shard_path = tmp_path / f"shard-{seed}.jsonl"
        coverage_path = tmp_path / f"coverage-{seed}.json"
        with shard_path.open("w", encoding="utf-8", newline="\n") as stream:
            dump_assisted_source_pool_jsonl(artifact, stream)
        restore = verify_assisted_source_pool_restores(
            lambda: _AssistedAdapter(),
            artifact,
        )
        coverage = build_assisted_a20_coverage_report(
            artifact,
            restore_report=restore,
            input_artifacts={"natural_pool": {"path": str(shard_path)}},
            source_identity=lightspeed_source_identity_dict(),
        )
        write_assisted_a20_coverage_report(coverage_path, coverage)
        shard_paths.append(shard_path)
        coverage_paths.append(coverage_path)

    merged = merge_assisted_source_pool_shards(
        artifacts,
        shard_identities=[
            {"path": str(path), "sha256": _sha256(path)} for path in shard_paths
        ],
    )
    merged_path = tmp_path / "merged.jsonl"
    with merged_path.open("w", encoding="utf-8", newline="\n") as stream:
        dump_assisted_source_pool_jsonl(merged, stream)

    report = merge_assisted_a20_coverage_from_paths(
        output_path=tmp_path / "merged-coverage.json",
        pool_path=merged_path,
        coverage_shard_paths=coverage_paths,
        restore_limit=0,
        gate_config=TrainingScaleGateConfig(),
        gate_override="none",
    )

    payload = report.to_dict()
    assert payload["natural_coverage"]["natural_battle_start_count"] == len(
        merged.records
    )
    assert payload["restore_verification"]["checkpoint_count"] == len(merged.records)
    assert payload["restore_verification"]["restore_ok"] is True
    assert len(payload["input_artifacts"]["coverage_shards"]) == 2


def _sha256(path) -> str:
    import hashlib

    return hashlib.sha256(path.read_bytes()).hexdigest()
