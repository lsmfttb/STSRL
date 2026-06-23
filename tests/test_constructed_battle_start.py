from __future__ import annotations

from dataclasses import dataclass, replace
from io import StringIO
from typing import Any

import pytest

from sts_combat_rl.sim.battle_start_pool import collect_natural_battle_start_pool
from sts_combat_rl.sim.constructed_battle_start import (
    CONSTRUCTED_DISTRIBUTION_KIND,
    NATURAL_DISTRIBUTION_KIND,
    ConstructedBattleStartPolicy,
    build_constructed_battle_start_artifact,
    build_constructed_battle_start_audit_report,
    dump_constructed_battle_start_artifact_jsonl,
    format_constructed_battle_start_audit_report,
    load_constructed_battle_start_artifact_jsonl,
    record_to_manifest_constructed,
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
class _Payload:
    seed: int
    phase: int


class FakeConstructedAdapter:
    """Two-battle A20 run with native-like battle-start rebuild methods."""

    checkpoint_adapter_id = "fake-constructed"
    supports_checkpoint_restore = True

    def __init__(self, *, boss_room: bool = False) -> None:
        self.seed = 0
        self.phase = 0
        self.boss_room = boss_room
        self.hp_bonus = 0
        self.added_potion = False
        self.replacement_encounter: str | None = None
        self._checkpoint_counter = 0

    def reset(self, seed: int | None = None) -> SimulatorSnapshot:
        self.seed = int(seed or 0)
        self.phase = 0
        self.hp_bonus = 0
        self.added_potion = False
        self.replacement_encounter = None
        return self._snapshot()

    def legal_actions(self, snapshot: SimulatorSnapshot) -> list[SimulatorAction]:
        del snapshot
        kind = "card" if self.phase in {1, 3} else "event"
        scope = "battle" if kind == "card" else "game"
        return [
            SimulatorAction(
                action_id=f"{scope}:{self.phase}",
                label=f"{scope} {self.phase}",
                kind=kind,
                raw={
                    "scope": scope,
                    "bits": self.phase,
                    "idx1": 0,
                    "idx2": 0,
                    "idx3": 0,
                },
            )
        ]

    def step(self, action: SimulatorAction) -> SimulatorTransition:
        del action
        if self.phase < 4:
            self.phase += 1
        return SimulatorTransition(
            snapshot=self._snapshot(),
            terminal=self.phase == 4,
        )

    def capture_checkpoint(self, snapshot: SimulatorSnapshot) -> SimulatorCheckpoint:
        del snapshot
        self._checkpoint_counter += 1
        return SimulatorCheckpoint(
            adapter_id=self.checkpoint_adapter_id,
            checkpoint_id=f"fake-constructed:{self._checkpoint_counter}",
            payload=_Payload(self.seed, self.phase),
        )

    def restore_checkpoint(self, checkpoint: SimulatorCheckpoint) -> SimulatorSnapshot:
        self.seed = checkpoint.payload.seed
        self.phase = checkpoint.payload.phase
        self.hp_bonus = 0
        self.added_potion = False
        self.replacement_encounter = None
        return self._snapshot()

    def legal_battle_start_encounters(
        self,
        snapshot: SimulatorSnapshot,
    ) -> list[dict[str, Any]]:
        if self.boss_room:
            raise AssertionError("Boss replacements must not ask native candidates")
        if not snapshot.raw.get("battle_active"):
            raise ValueError("not in battle")
        return [
            {"id": 1, "encounter_id": "CULTIST"},
            {"id": 2, "encounter_id": "JAW_WORM"},
        ]

    def rebuild_battle_start(
        self,
        snapshot: SimulatorSnapshot,
        *,
        hp_bonus: int = 0,
        add_random_potion: bool = False,
        encounter_id: int | None = None,
    ) -> SimulatorSnapshot:
        if not snapshot.raw.get("battle_active"):
            raise ValueError("not in battle")
        self.hp_bonus = int(hp_bonus)
        self.added_potion = bool(add_random_potion)
        if encounter_id == 2:
            self.replacement_encounter = "JAW_WORM"
        elif encounter_id is not None:
            self.replacement_encounter = "CULTIST"
        return self._snapshot()

    def _snapshot(self) -> SimulatorSnapshot:
        battle_active = self.phase in {1, 3}
        completed_outcome = "PLAYER_VICTORY" if self.phase in {2, 4} else None
        current_hp = min(80, 50 + self.hp_bonus)
        room_type = "BOSS" if self.boss_room and battle_active else "MONSTER"
        encounter = (
            "SLIME_BOSS"
            if self.boss_room and battle_active
            else self.replacement_encounter or "CULTIST"
        )
        raw: dict[str, Any] = {
            "screen_state": "BATTLE" if battle_active else "EVENT",
            "battle_active": battle_active,
            "outcome": "PLAYER_VICTORY" if self.phase == 4 else "UNDECIDED",
            "ascension": 20,
            "act": 1,
            "floor_num": self.phase + 1,
            "room_type": room_type,
            "encounter_id": encounter if battle_active else None,
            "cur_hp": current_hp,
            "max_hp": 80,
            "gold": 99,
            "battle_player": {"current_hp": current_hp, "max_hp": 80},
            "battle_potion_count": 1 if self.added_potion else 0,
            "battle_potion_capacity": 2,
            "battle_potions": self._potions(),
            "deck": [
                {
                    "deck_index": 0,
                    "id": 1,
                    "name": "Strike",
                    "type": "ATTACK",
                    "upgraded": False,
                    "misc": 0,
                    "bottled": False,
                }
            ],
            "relics": [
                {
                    "relic_index": 0,
                    "id": 1,
                    "name": "Burning Blood",
                    "data": 0,
                    "data_visibility": "available",
                }
            ],
            "blue_key": False,
            "green_key": False,
            "red_key": False,
        }
        if battle_active:
            raw["battle_outcome"] = "UNDECIDED"
        if completed_outcome is not None:
            raw["completed_battle_outcome"] = completed_outcome
        return SimulatorSnapshot(
            observation=[self.seed, self.phase, current_hp], raw=raw
        )

    def _potions(self) -> list[dict[str, Any]]:
        potions = [
            {"potion_index": 0, "id": 0, "name": "EMPTY_POTION_SLOT"},
            {"potion_index": 1, "id": 0, "name": "EMPTY_POTION_SLOT"},
        ]
        if self.added_potion:
            potions[0] = {"potion_index": 0, "id": 9, "name": "FIRE_POTION"}
        return potions


class FakeUnsupportedTransformAdapter(FakeConstructedAdapter):
    def rebuild_battle_start(self, *args: Any, **kwargs: Any) -> SimulatorSnapshot:
        raise RuntimeError("native rebuild_battle_start unsupported")


class FakeNoOpTransformAdapter(FakeConstructedAdapter):
    def rebuild_battle_start(
        self, snapshot: SimulatorSnapshot, **kwargs: Any
    ) -> SimulatorSnapshot:
        del kwargs
        return snapshot


def _controller() -> RoutedRunController:
    return RoutedRunController(
        battle=PolicyController(FirstEligiblePolicy()),
        non_combat=PolicyController(FirstEligiblePolicy()),
    )


def _pool(adapter: FakeConstructedAdapter | None = None):
    return collect_natural_battle_start_pool(
        adapter or FakeConstructedAdapter(),
        _controller(),
        seeds=[7],
        max_steps=5,
    )


def _trigger_policy(**overrides: Any) -> ConstructedBattleStartPolicy:
    return ConstructedBattleStartPolicy(
        seed=1,
        hp_probability=0.999,
        potion_probability=0.999,
        encounter_probability=0.999,
        **overrides,
    )


def test_constructed_artifact_applies_supported_later_battle_transforms() -> None:
    pool = _pool()
    artifact = build_constructed_battle_start_artifact(
        lambda: FakeConstructedAdapter(),
        pool,
        policy=_trigger_policy(),
    )
    report = build_constructed_battle_start_audit_report(artifact)

    first_hp = next(
        record
        for record in artifact.records
        if record.source_record_index == 0
        and record.transform_type == "current_hp_addition"
    )
    later_hp = next(
        record
        for record in artifact.records
        if record.source_record_index == 1
        and record.transform_type == "current_hp_addition"
    )
    later_potion = next(
        record
        for record in artifact.records
        if record.source_record_index == 1
        and record.transform_type == "potion_addition"
    )
    later_encounter = next(
        record
        for record in artifact.records
        if record.source_record_index == 1
        and record.transform_type == "encounter_replacement"
    )

    assert first_hp.eligibility["eligible"] is False
    assert (
        "first_battle_or_missing_prior_opportunity" in first_hp.eligibility["reasons"]
    )
    assert later_hp.resulting_distribution_kind == CONSTRUCTED_DISTRIBUTION_KIND
    assert 1 <= later_hp.actual_change["current_hp_delta"] <= 3
    assert (
        later_hp.actual_change["after_current_hp"] <= later_hp.actual_change["max_hp"]
    )
    assert later_potion.resulting_distribution_kind == CONSTRUCTED_DISTRIBUTION_KIND
    assert (
        later_potion.actual_change["after_potion_count"]
        <= later_potion.actual_change["potion_capacity"]
    )
    assert later_potion.actual_change["added_potion"]["name"] == "FIRE_POTION"
    assert later_encounter.resulting_distribution_kind == CONSTRUCTED_DISTRIBUTION_KIND
    assert later_encounter.actual_change["target_encounter_id"] == "JAW_WORM"
    assert report.constructed_record_count >= 3
    assert report.cap_violation_count == 0
    assert report.passed is True


def test_constructed_policy_is_repeatable_and_seeded() -> None:
    pool = _pool()
    policy = ConstructedBattleStartPolicy(
        seed=11,
        hp_probability=0.5,
        potion_probability=0.5,
        encounter_probability=0.5,
    )

    first = build_constructed_battle_start_artifact(
        lambda: FakeConstructedAdapter(),
        pool,
        policy=policy,
    )
    repeated = build_constructed_battle_start_artifact(
        lambda: FakeConstructedAdapter(),
        pool,
        policy=policy,
    )
    changed = build_constructed_battle_start_artifact(
        lambda: FakeConstructedAdapter(),
        pool,
        policy=ConstructedBattleStartPolicy(
            seed=12,
            hp_probability=0.5,
            potion_probability=0.5,
            encounter_probability=0.5,
        ),
    )

    assert [record_to_manifest_constructed(record) for record in first.records] == [
        record_to_manifest_constructed(record) for record in repeated.records
    ]
    assert [record.proposal for record in first.records] != [
        record.proposal for record in changed.records
    ]


def test_noop_and_unsupported_transforms_remain_natural() -> None:
    pool = _pool()

    no_op = build_constructed_battle_start_artifact(
        lambda: FakeNoOpTransformAdapter(),
        pool,
        policy=_trigger_policy(),
    )
    unsupported = build_constructed_battle_start_artifact(
        lambda: FakeUnsupportedTransformAdapter(),
        pool,
        policy=_trigger_policy(),
    )
    unsupported_report = build_constructed_battle_start_audit_report(unsupported)
    text = format_constructed_battle_start_audit_report(unsupported_report)

    assert all(
        record.resulting_distribution_kind == NATURAL_DISTRIBUTION_KIND
        for record in no_op.records
        if record.proposal.get("triggered")
    )
    assert all(
        record.resulting_distribution_kind == NATURAL_DISTRIBUTION_KIND
        for record in unsupported.records
        if record.native_support_status == "unsupported"
    )
    assert unsupported_report.unsupported_native_operation_counts
    assert unsupported_report.passed is False
    assert "no constructed supplement rows were produced" in unsupported_report.problems
    assert "unsupported native operations:" in text
    assert "audit passed: no" in text


def test_constructed_artifact_preserves_source_and_round_trips_jsonl() -> None:
    pool = _pool()
    artifact = build_constructed_battle_start_artifact(
        lambda: FakeConstructedAdapter(),
        pool,
        policy=_trigger_policy(),
    )
    stream = StringIO()

    dump_constructed_battle_start_artifact_jsonl(artifact, stream)
    loaded = load_constructed_battle_start_artifact_jsonl(StringIO(stream.getvalue()))

    assert loaded.source_record_count == len(pool.records)
    assert loaded.mixture_manifest.source_natural_count == len(pool.records)
    assert loaded.mixture_manifest.distribution_counts[
        NATURAL_DISTRIBUTION_KIND
    ] == len(pool.records)
    assert (
        loaded.mixture_manifest.distribution_counts[CONSTRUCTED_DISTRIBUTION_KIND]
        == loaded.mixture_manifest.constructed_record_count
    )
    assert all(
        record.source_record["distribution_kind"] == NATURAL_DISTRIBUTION_KIND
        for record in loaded.records
    )
    assert loaded == artifact


def test_boss_encounter_replacement_is_out_of_scope() -> None:
    pool = _pool(FakeConstructedAdapter(boss_room=True))

    artifact = build_constructed_battle_start_artifact(
        lambda: FakeConstructedAdapter(boss_room=True),
        pool,
        policy=_trigger_policy(transform_types=("encounter_replacement",)),
    )
    report = build_constructed_battle_start_audit_report(artifact)

    assert all(record.eligibility["eligible"] is False for record in artifact.records)
    assert all(
        "visible_boss_replacement_out_of_scope" in record.eligibility["reasons"]
        for record in artifact.records
    )
    assert report.boss_replacement_violation_count == 0


def test_constructed_artifact_rejects_non_a20_sources() -> None:
    pool = _pool()
    pool.records[0].structural_metadata["ascension"] = 0

    with pytest.raises(ValueError, match="require A20 source records"):
        build_constructed_battle_start_artifact(
            lambda: FakeConstructedAdapter(),
            pool,
            policy=_trigger_policy(),
        )


def test_proposals_do_not_depend_on_process_local_checkpoint_ids() -> None:
    pool = _pool()
    volatile_pool = replace(
        pool,
        records=[
            replace(
                record,
                source_checkpoint_id=f"volatile-process-{record.record_index}",
            )
            for record in pool.records
        ],
    )
    policy = ConstructedBattleStartPolicy(
        seed=11,
        hp_probability=0.5,
        potion_probability=0.5,
        encounter_probability=0.5,
    )

    first = build_constructed_battle_start_artifact(
        lambda: FakeConstructedAdapter(),
        pool,
        policy=policy,
    )
    volatile = build_constructed_battle_start_artifact(
        lambda: FakeConstructedAdapter(),
        volatile_pool,
        policy=policy,
    )

    assert [record.proposal_seed for record in first.records] == [
        record.proposal_seed for record in volatile.records
    ]
    assert [record.proposal for record in first.records] == [
        record.proposal for record in volatile.records
    ]
    assert [record.actual_change for record in first.records] == [
        record.actual_change for record in volatile.records
    ]


def test_constructed_policy_rejects_automatic_probability() -> None:
    with pytest.raises(ValueError, match="never automatic"):
        build_constructed_battle_start_artifact(
            lambda: FakeConstructedAdapter(),
            _pool(),
            policy=ConstructedBattleStartPolicy(
                seed=1,
                hp_probability=1.0,
            ),
        )
