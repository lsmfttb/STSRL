"""Tests for the fixed battle evaluation module."""

from __future__ import annotations

import json
from io import StringIO

import pytest

from sts_combat_rl.sim.contract import (
    SimulatorAction,
    SimulatorCheckpoint,
    SimulatorSnapshot,
    SimulatorTransition,
)
from sts_combat_rl.sim.controller_contract import (
    ControllerDecision,
    ControllerProvenance,
)
from sts_combat_rl.sim.fixed_evaluation_set import (
    FixedCohortRecord,
)
from sts_combat_rl.sim.fixed_battle_evaluation import (
    AggregateSlice,
    FixedEvaluationReport,
    SingleBattleEvaluationResult,
    build_evaluation_aggregates,
    dump_fixed_evaluation_report_jsonl,
    evaluate_fixed_cohort,
    format_fixed_evaluation_report,
    load_fixed_evaluation_report_jsonl,
)
from sts_combat_rl.sim.public_context_artifacts import PUBLIC_CONTEXT_LEGACY_LOSS
from sts_combat_rl.sim.public_run_context import build_public_run_context
from sts_combat_rl.sim.resource_outcome import BATTLE_RESOURCE_OUTCOME_LEGACY_LOSS


# ── Test helpers ────────────────────────────────────────────────────────────


def _make_observation() -> tuple[float, ...]:
    return (1.0, 2.0, 3.0)


def _make_snapshot(
    raw: dict | None = None,
    observation: tuple[float, ...] | None = None,
) -> SimulatorSnapshot:
    return SimulatorSnapshot(
        observation=observation or _make_observation(),
        raw=raw
        or {
            "screen_state": "BATTLE",
            "battle_active": True,
            "cur_hp": 70,
            "max_hp": 80,
            "floor_num": 5,
        },
    )


def _make_action(
    action_id: int = 1,
    kind: str = "PLAY_CARD",
    label: str = "Strike",
) -> SimulatorAction:
    return SimulatorAction(
        action_id=action_id,
        kind=kind,
        label=label,
        raw={"idx1": 0, "idx2": 1},
    )


def _make_public_context() -> dict[str, object]:
    snapshot = _make_snapshot()
    actions = [_make_action()]
    return build_public_run_context(snapshot.raw, actions, projection=None)


def _make_transition(
    snapshot: SimulatorSnapshot | None = None,
    terminal: bool = False,
) -> SimulatorTransition:
    return SimulatorTransition(
        snapshot=snapshot or _make_snapshot(),
        terminal=terminal,
        info={},
    )


def _make_cohort_record(
    cohort_index: int = 0,
    *,
    seed: int = 1,
    run_id: str = "seed-1-run-0",
    battle_index: int = 0,
    checkpoint_id: str = "cp-0",
    encounter_id: str = "Cultist",
    action_trace: tuple = (),
) -> FixedCohortRecord:
    return FixedCohortRecord(
        cohort_index=cohort_index,
        source_pool_record_index=cohort_index,
        source_checkpoint_id=checkpoint_id,
        source_run_id=run_id,
        source_seed=seed,
        source_battle_index=battle_index,
        structural_stratum=(20, 1, "MONSTER", encounter_id),
        structural_metadata={
            "ascension": 20,
            "act": 1,
            "floor": 5,
            "room_type": "MONSTER",
            "encounter_id": encounter_id,
            "seed": seed,
            "source_kind": "natural_run",
            "distribution_kind": "natural_run",
            "source_run_id": run_id,
            "source_battle_index": battle_index,
        },
        source_controller_provenance={
            "kind": "routed_run",
            "name": "test",
            "config": {},
        },
        source_battle_controller_provenance={
            "kind": "decision_policy",
            "name": "test",
            "config": {},
        },
        source_non_combat_controller_provenance={
            "kind": "decision_policy",
            "name": "test",
            "config": {},
        },
        action_trace=action_trace,
        snapshot_observation=(1.0, 2.0, 3.0),
        snapshot_raw={
            "screen_state": "BATTLE",
            "battle_active": True,
            "cur_hp": 70,
            "max_hp": 80,
            "floor_num": 5,
        },
        source_distribution_kind="natural_run",
    )


class _FakeWinController:
    """Controller that selects always the first eligible action and returns a win."""

    provenance = ControllerProvenance(
        kind="test",
        name="fake_win",
        config={"information_regime": "normal_public_policy"},
    )

    def select_action(self, adapter, snapshot, actions, context, step_index):
        eligible = context.eligible_action_indices
        idx = eligible[0] if eligible else 0
        return ControllerDecision(
            selected_index=idx,
            provenance=self.provenance,
            reason="always-first",
        )


class _FakeIllegalController:
    """Controller that selects outside legal bounds."""

    provenance = ControllerProvenance(
        kind="test",
        name="fake_illegal",
        config={"information_regime": "normal_public_policy"},
    )

    def select_action(self, adapter, snapshot, actions, context, step_index):
        return ControllerDecision(
            selected_index=999,
            provenance=self.provenance,
            reason="illegal",
        )


class _FakeCrashingController:
    """Controller that raises during select_action."""

    provenance = ControllerProvenance(
        kind="test",
        name="fake_crash",
        config={},
    )

    def select_action(self, adapter, snapshot, actions, context, step_index):
        raise RuntimeError("controller exploded")


class _FakeEvalAdapter:
    """Fake adapter for evaluation tests that supports restore.

    It replays action traces from the cohort record's source seed.
    The first legal action returned is _make_action(1, "ATTACK").
    After a terminal step the screen goes to "BOSS_REWARD".
    """

    def __init__(self, seed: int = 1, ascension: int = 20):
        self.seed = seed
        self.ascension = ascension
        self._current_step = 0
        self._terminal = False

    @property
    def supports_checkpoint_restore(self) -> bool:
        return True

    @property
    def checkpoint_adapter_id(self) -> str:
        return "fake-adapter"

    def reset(self, *, seed: int | None = None) -> SimulatorSnapshot:
        self._current_step = 0
        self._terminal = False
        return _make_snapshot(
            raw={
                "screen_state": "BATTLE",
                "battle_active": True,
                "cur_hp": 70,
                "max_hp": 80,
                "floor_num": 5,
            }
        )

    def legal_actions(self, snapshot: SimulatorSnapshot) -> list[SimulatorAction]:
        return [_make_action(1, "ATTACK", "Strike")]

    def step(self, action: SimulatorAction) -> SimulatorTransition:
        self._current_step += 1
        # After a few steps, pretend the player wins.
        if self._current_step >= 3:
            return SimulatorTransition(
                snapshot=_make_snapshot(
                    raw={
                        "screen_state": "BOSS_REWARD",
                        "battle_active": False,
                        "outcome": "PLAYER_VICTORY",
                        "completed_battle_outcome": "PLAYER_VICTORY",
                        "cur_hp": 65,
                        "max_hp": 80,
                        "floor_num": 5,
                    }
                ),
                terminal=True,
                info={},
            )
        return SimulatorTransition(
            snapshot=_make_snapshot(
                raw={
                    "screen_state": "BATTLE",
                    "battle_active": True,
                    "cur_hp": 70 - self._current_step * 2,
                    "max_hp": 80,
                    "floor_num": 5,
                }
            ),
            terminal=False,
            info={},
        )

    def capture_checkpoint(self, snapshot: SimulatorSnapshot) -> SimulatorCheckpoint:
        return SimulatorCheckpoint(
            checkpoint_id="fake-cp",
            adapter_id=self.checkpoint_adapter_id,
            native={},
        )

    def restore_checkpoint(self, checkpoint: SimulatorCheckpoint) -> SimulatorSnapshot:
        return self.reset(seed=self.seed)


class _FakeTruncationAdapter:
    """Adapter where battle never terminates (for truncation tests)."""

    supports_checkpoint_restore = True
    checkpoint_adapter_id = "fake-trunc-adapter"

    def __init__(self, seed: int = 1, ascension: int = 20):
        self.seed = seed
        self.ascension = ascension

    def reset(self, *, seed: int | None = None) -> SimulatorSnapshot:
        return _make_snapshot()

    def legal_actions(self, snapshot: SimulatorSnapshot) -> list[SimulatorAction]:
        return [_make_action(1, "ATTACK", "Strike")]

    def step(self, action: SimulatorAction) -> SimulatorTransition:
        return SimulatorTransition(
            snapshot=_make_snapshot(),
            terminal=False,
            info={},
        )

    def capture_checkpoint(self, snapshot: SimulatorSnapshot) -> SimulatorCheckpoint:
        return SimulatorCheckpoint(
            checkpoint_id="fc", adapter_id=self.checkpoint_adapter_id, native={}
        )

    def restore_checkpoint(self, checkpoint: SimulatorCheckpoint) -> SimulatorSnapshot:
        return self.reset(seed=self.seed)


class _FakeRestoreFailAdapter:
    """Adapter where reset always raises."""

    supports_checkpoint_restore = True
    checkpoint_adapter_id = "fake-fail-adapter"

    def __init__(self, seed: int = 1, ascension: int = 20):
        self.seed = seed
        self.ascension = ascension

    def reset(self, *, seed: int | None = None) -> SimulatorSnapshot:
        raise RuntimeError("simulator unavailable")


class _FakeLossAdapter:
    """Adapter where the player loses after one attack."""

    supports_checkpoint_restore = True
    checkpoint_adapter_id = "fake-loss-adapter"

    def __init__(self, seed: int = 1, ascension: int = 20):
        self.seed = seed
        self.ascension = ascension
        self._called = False

    def reset(self, *, seed: int | None = None) -> SimulatorSnapshot:
        self._called = False
        return _make_snapshot(
            raw={
                "screen_state": "BATTLE",
                "battle_active": True,
                "cur_hp": 70,
                "max_hp": 80,
                "floor_num": 5,
            }
        )

    def legal_actions(self, snapshot: SimulatorSnapshot) -> list[SimulatorAction]:
        return [_make_action(1, "ATTACK", "Strike")]

    def step(self, action: SimulatorAction) -> SimulatorTransition:
        self._called = True
        return SimulatorTransition(
            snapshot=_make_snapshot(
                raw={
                    "screen_state": "GAME_OVER",
                    "battle_active": False,
                    "outcome": "PLAYER_LOSS",
                    "completed_battle_outcome": "PLAYER_LOSS",
                    "cur_hp": 0,
                    "max_hp": 80,
                }
            ),
            terminal=True,
            info={},
        )

    def capture_checkpoint(self, snapshot: SimulatorSnapshot) -> SimulatorCheckpoint:
        return SimulatorCheckpoint(
            checkpoint_id="lcp", adapter_id=self.checkpoint_adapter_id, native={}
        )

    def restore_checkpoint(self, checkpoint: SimulatorCheckpoint) -> SimulatorSnapshot:
        return self.reset(seed=self.seed)


# ── Tests ───────────────────────────────────────────────────────────────────


class TestEvaluateFixedCohort:
    """Controller evaluation on restored battle starts."""

    def test_win_evaluation(self):
        cohort_records = [_make_cohort_record(0)]
        controller = _FakeWinController()
        report = evaluate_fixed_cohort(
            adapter_factory=lambda: _FakeEvalAdapter(),
            cohort_records=cohort_records,
            controller=controller,
            cohort_identity="test-identity",
            source_pool_format_version=2,
            selection_config={"selection_seed": 1},
            max_battle_steps=200,
        )
        assert report.total_battles == 1
        assert report.authoritative_wins == 1
        assert report.errors == 0
        assert report.truncations == 0
        assert report.evaluation_successful
        assert report.battle_results[0].termination_status == "win"
        assert report.battle_results[0].restoration_method in (
            "seed_action_trace",
            "native_checkpoint",
        )
        assert report.battle_results[0].decision_count > 0
        assert report.battle_results[0].structured_battle_outcome_status == "available"
        assert (
            report.battle_results[0].structured_battle_outcome["schema_id"]
            == "structured-battle-outcome-v1"
        )

    def test_truncation_reported(self):
        cohort_records = [_make_cohort_record(0)]
        controller = _FakeWinController()
        report = evaluate_fixed_cohort(
            adapter_factory=lambda: _FakeTruncationAdapter(),
            cohort_records=cohort_records,
            controller=controller,
            cohort_identity="test",
            source_pool_format_version=2,
            selection_config={"selection_seed": 1},
            max_battle_steps=5,
        )
        assert report.total_battles == 1
        assert report.truncations == 1
        assert not report.evaluation_successful
        assert report.battle_results[0].termination_status == "truncated"
        assert (
            report.battle_results[0].structured_battle_outcome_status == "unavailable"
        )
        assert len(report.problems) >= 1
        assert any("truncat" in p for p in report.problems)

    def test_restore_failure_is_error(self):
        cohort_records = [_make_cohort_record(0)]
        controller = _FakeWinController()
        report = evaluate_fixed_cohort(
            adapter_factory=lambda: _FakeRestoreFailAdapter(),
            cohort_records=cohort_records,
            controller=controller,
            cohort_identity="test",
            source_pool_format_version=2,
            selection_config={"selection_seed": 1},
            max_battle_steps=200,
        )
        assert report.errors == 1
        assert report.battle_results[0].termination_status == "error"
        assert (
            report.battle_results[0].structured_battle_outcome_status == "unavailable"
        )
        assert report.battle_results[0].restoration_method == "failed"
        assert len(report.battle_results[0].problems) >= 1

    def test_illegal_selection_is_error(self):
        cohort_records = [_make_cohort_record(0)]
        controller = _FakeIllegalController()
        report = evaluate_fixed_cohort(
            adapter_factory=lambda: _FakeEvalAdapter(),
            cohort_records=cohort_records,
            controller=controller,
            cohort_identity="test",
            source_pool_format_version=2,
            selection_config={"selection_seed": 1},
            max_battle_steps=200,
        )
        assert report.errors == 1
        assert report.battle_results[0].termination_status == "error"
        assert any(
            "outside" in p or "illegal" in p.lower()
            for p in report.battle_results[0].problems
        )

    def test_controller_crash_is_error(self):
        cohort_records = [_make_cohort_record(0)]
        controller = _FakeCrashingController()
        report = evaluate_fixed_cohort(
            adapter_factory=lambda: _FakeEvalAdapter(),
            cohort_records=cohort_records,
            controller=controller,
            cohort_identity="test",
            source_pool_format_version=2,
            selection_config={"selection_seed": 1},
            max_battle_steps=200,
        )
        assert report.errors == 1

    def test_loss_evaluation(self):
        cohort_records = [_make_cohort_record(0)]
        controller = _FakeWinController()
        report = evaluate_fixed_cohort(
            adapter_factory=lambda: _FakeLossAdapter(),
            cohort_records=cohort_records,
            controller=controller,
            cohort_identity="test",
            source_pool_format_version=2,
            selection_config={"selection_seed": 1},
            max_battle_steps=200,
        )
        assert report.losses == 1
        assert report.authoritative_wins == 0
        assert report.battle_results[0].termination_status == "loss"

    def test_hp_tracking(self):
        cohort_records = [_make_cohort_record(0)]
        controller = _FakeWinController()
        report = evaluate_fixed_cohort(
            adapter_factory=lambda: _FakeEvalAdapter(),
            cohort_records=cohort_records,
            controller=controller,
            cohort_identity="test",
            source_pool_format_version=2,
            selection_config={"selection_seed": 1},
            max_battle_steps=200,
        )
        r = report.battle_results[0]
        assert r.battle_initial_hp is not None
        assert r.terminal_absolute_hp is not None
        assert r.hp_loss is not None

    def test_wall_clock_time_recorded(self):
        cohort_records = [_make_cohort_record(0)]
        controller = _FakeWinController()
        report = evaluate_fixed_cohort(
            adapter_factory=lambda: _FakeEvalAdapter(),
            cohort_records=cohort_records,
            controller=controller,
            cohort_identity="test",
            source_pool_format_version=2,
            selection_config={"selection_seed": 1},
            max_battle_steps=200,
        )
        assert report.battle_results[0].wall_clock_time_s >= 0.0

    def test_provenance_preserved(self):
        cohort_records = [_make_cohort_record(0)]
        controller = _FakeWinController()
        report = evaluate_fixed_cohort(
            adapter_factory=lambda: _FakeEvalAdapter(),
            cohort_records=cohort_records,
            controller=controller,
            cohort_identity="test",
            source_pool_format_version=2,
            selection_config={"selection_seed": 1},
            max_battle_steps=200,
        )
        assert report.controller_provenance["kind"] == "test"
        assert report.information_regime == "normal_public_policy"

    def test_deterministic_controller_deterministic_result(self):
        """Identical controller/config runs produce identical non-timing results."""

        def run():
            report = evaluate_fixed_cohort(
                adapter_factory=lambda: _FakeEvalAdapter(),
                cohort_records=[_make_cohort_record(0)],
                controller=_FakeWinController(),
                cohort_identity="test",
                source_pool_format_version=2,
                selection_config={"selection_seed": 1},
                max_battle_steps=200,
            )
            r = report.battle_results[0]
            return (
                r.termination_status,
                r.decision_count,
                r.terminal_absolute_hp,
                r.hp_loss,
                r.restoration_method,
            )

        a = run()
        b = run()
        assert a == b

    def test_empty_cohort(self):
        report = evaluate_fixed_cohort(
            adapter_factory=lambda: _FakeEvalAdapter(),
            cohort_records=[],
            controller=_FakeWinController(),
            cohort_identity="empty",
            source_pool_format_version=2,
            selection_config={},
            max_battle_steps=200,
        )
        assert report.total_battles == 0


class TestEvaluationAggregates:
    """Aggregate slice computation."""

    def _make_result(
        self,
        cohort_index: int,
        status: str,
        hp_loss: int | None = None,
        encounter_id: str = "Cultist",
        room_type: str = "MONSTER",
        decision_count: int = 5,
    ) -> SingleBattleEvaluationResult:
        return SingleBattleEvaluationResult(
            cohort_index=cohort_index,
            source_checkpoint_id=f"cp-{cohort_index}",
            source_seed=1,
            source_run_id=f"run-{cohort_index}",
            source_battle_index=cohort_index,
            structural_stratum=(20, 1, room_type, encounter_id),
            structural_metadata={
                "ascension": 20,
                "act": 1,
                "room_type": room_type,
                "encounter_id": encounter_id,
            },
            restoration_method="seed_action_trace",
            controller_provenance={"kind": "test", "name": "test"},
            information_regime="normal_public_policy",
            action_space_config={},
            termination_status=status,
            terminal_absolute_hp=60 - hp_loss if hp_loss is not None else None,
            hp_loss=hp_loss,
            decision_count=decision_count,
            simulator_step_count=decision_count,
            wall_clock_time_s=0.1 * decision_count,
        )

    def test_natural_weighted(self):
        results = [
            self._make_result(0, "win", hp_loss=5),
            self._make_result(1, "loss", hp_loss=15),
            self._make_result(2, "win", hp_loss=8),
        ]
        report = FixedEvaluationReport(
            cohort_identity="test",
            controller_provenance={"kind": "test", "name": "test"},
            information_regime="normal_public_policy",
            action_space_config={},
            max_battle_steps=200,
            source_pool_format_version=2,
            selection_config={},
            battle_results=results,
        )
        aggs = build_evaluation_aggregates(report)
        assert aggs.natural_weighted.battle_count == 3
        assert aggs.natural_weighted.win_count == 2
        assert aggs.natural_weighted.loss_count == 1
        assert aggs.natural_weighted.win_rate == pytest.approx(2 / 3, 0.01)
        assert aggs.natural_weighted.mean_hp_loss == pytest.approx(28 / 3, 0.1)

    def test_encounter_macro(self):
        results = [
            self._make_result(0, "win", hp_loss=5, encounter_id="A"),
            self._make_result(1, "loss", hp_loss=10, encounter_id="A"),
            self._make_result(2, "win", hp_loss=3, encounter_id="B"),
        ]
        report = FixedEvaluationReport(
            cohort_identity="test",
            controller_provenance={"kind": "test", "name": "test"},
            information_regime="normal_public_policy",
            action_space_config={},
            max_battle_steps=200,
            source_pool_format_version=2,
            selection_config={},
            battle_results=results,
        )
        aggs = build_evaluation_aggregates(report)
        assert len(aggs.encounter_macro) == 2
        assert aggs.encounter_macro["A"].battle_count == 2
        assert aggs.encounter_macro["A"].win_rate == 0.5
        assert aggs.encounter_macro["B"].win_rate == 1.0

    def test_room_type_macro(self):
        results = [
            self._make_result(0, "win", room_type="MONSTER"),
            self._make_result(1, "win", room_type="MONSTER"),
            self._make_result(2, "loss", room_type="ELITE"),
        ]
        report = FixedEvaluationReport(
            cohort_identity="test",
            controller_provenance={"kind": "test", "name": "test"},
            information_regime="normal_public_policy",
            action_space_config={},
            max_battle_steps=200,
            source_pool_format_version=2,
            selection_config={},
            battle_results=results,
        )
        aggs = build_evaluation_aggregates(report)
        assert len(aggs.room_type_macro) == 2
        assert aggs.room_type_macro["MONSTER"].win_rate == 1.0
        assert aggs.room_type_macro["ELITE"].win_rate == 0.0

    def test_per_stratum(self):
        results = [
            self._make_result(0, "win", encounter_id="A", room_type="MONSTER"),
            self._make_result(1, "loss", encounter_id="A", room_type="MONSTER"),
            self._make_result(2, "win", encounter_id="B", room_type="ELITE"),
        ]
        report = FixedEvaluationReport(
            cohort_identity="test",
            controller_provenance={"kind": "test", "name": "test"},
            information_regime="normal_public_policy",
            action_space_config={},
            max_battle_steps=200,
            source_pool_format_version=2,
            selection_config={},
            battle_results=results,
        )
        aggs = build_evaluation_aggregates(report)
        assert len(aggs.per_stratum) == 2  # (20,1,MONSTER,A) and (20,1,ELITE,B)
        stratum_monster_a = (20, 1, "MONSTER", "A")
        stratum_elite_b = (20, 1, "ELITE", "B")
        assert aggs.per_stratum[stratum_monster_a].battle_count == 2
        assert aggs.per_stratum[stratum_elite_b].battle_count == 1

    def test_error_excluded_from_aggregates(self):
        results = [
            self._make_result(0, "win", hp_loss=5),
            self._make_result(1, "error"),
        ]
        report = FixedEvaluationReport(
            cohort_identity="test",
            controller_provenance={"kind": "test", "name": "test"},
            information_regime="normal_public_policy",
            action_space_config={},
            max_battle_steps=200,
            source_pool_format_version=2,
            selection_config={},
            battle_results=results,
        )
        aggs = build_evaluation_aggregates(report)
        # Only the win contributes to aggregates.
        assert aggs.natural_weighted.battle_count == 1
        assert aggs.natural_weighted.win_count == 1

    def test_weighted_aggregate_100_1_case(self):
        """Natural weighting: 100 sources in one stratum, 1 in another.

        Two strata, each contributing one selected record (quota=1).
        Source count 100 for stratum A, 1 for stratum B.
        Expected weighted win rate: (50*1 + 50*0) / 100 = 0.5? No - with
        source_weight / selected_count, per-result weight is source/selected.
        A: 100/1=100, B: 1/1=1. Expected: (100*1 + 1*0) / (100+1) ≈ 0.99.
        """
        from sts_combat_rl.sim.fixed_battle_evaluation import (
            _build_weighted_aggregate_slice,
        )

        results = [
            self._make_result(0, "win", hp_loss=5, encounter_id="A"),
            self._make_result(1, "loss", hp_loss=15, encounter_id="B"),
        ]
        weights = {(20, 1, "MONSTER", "A"): 100.0, (20, 1, "MONSTER", "B"): 1.0}
        slc = _build_weighted_aggregate_slice(results, weights)
        expected_wr = 100.0 / 101.0
        assert slc.win_rate == pytest.approx(expected_wr, 0.01)
        # Without weights, it would be 0.5.
        unweighted = _build_weighted_aggregate_slice(results, {})
        assert unweighted.win_rate == 0.5

    def test_weighted_aggregate_hp_loss(self):
        """Weighted HP loss: 100 weight for 5 loss, 1 weight for 15 loss.

        Expected: (100*5 + 1*15) / (100 + 1) ≈ 5.099.
        """
        from sts_combat_rl.sim.fixed_battle_evaluation import (
            _build_weighted_aggregate_slice,
        )

        results = [
            self._make_result(0, "win", hp_loss=5, encounter_id="A"),
            self._make_result(1, "loss", hp_loss=15, encounter_id="B"),
        ]
        weights = {(20, 1, "MONSTER", "A"): 100.0, (20, 1, "MONSTER", "B"): 1.0}
        slc = _build_weighted_aggregate_slice(results, weights)
        expected_mean = (100.0 * 5 + 1.0 * 15) / (100.0 + 1.0)
        assert slc.mean_hp_loss == pytest.approx(expected_mean, 0.1)

    def test_per_stratum_counts_persist_roundtrip(self):
        """per_stratum_source_counts survives JSONL dump/load.

        Two results: win in A (100 sources), loss in B (1 source).
        After round-trip the loaded counts produce the expected weighted result.
        """
        result_a = SingleBattleEvaluationResult(
            cohort_index=0,
            source_checkpoint_id="cp-0",
            source_seed=1,
            source_run_id="r",
            source_battle_index=0,
            structural_stratum=(20, 1, "MONSTER", "A"),
            structural_metadata={},
            restoration_method="seed_action_trace",
            controller_provenance={"kind": "test"},
            information_regime="normal_public_policy",
            action_space_config={},
            termination_status="win",
            terminal_absolute_hp=65,
            hp_loss=5,
            decision_count=3,
            simulator_step_count=3,
            wall_clock_time_s=0.3,
        )
        result_b = SingleBattleEvaluationResult(
            cohort_index=1,
            source_checkpoint_id="cp-1",
            source_seed=1,
            source_run_id="r",
            source_battle_index=1,
            structural_stratum=(20, 1, "MONSTER", "B"),
            structural_metadata={},
            restoration_method="seed_action_trace",
            controller_provenance={"kind": "test"},
            information_regime="normal_public_policy",
            action_space_config={},
            termination_status="loss",
            terminal_absolute_hp=0,
            hp_loss=15,
            decision_count=3,
            simulator_step_count=3,
            wall_clock_time_s=0.3,
        )
        report = FixedEvaluationReport(
            cohort_identity="id",
            controller_provenance={"kind": "test", "name": "fake"},
            information_regime="normal_public_policy",
            action_space_config={},
            max_battle_steps=200,
            source_pool_format_version=2,
            selection_config={},
            per_stratum_source_counts={
                "20/1/MONSTER/A": 100,
                "20/1/MONSTER/B": 1,
            },
            battle_results=[result_a, result_b],
        )

        buf = StringIO()
        dump_fixed_evaluation_report_jsonl(report, buf)
        buf.seek(0)
        loaded = load_fixed_evaluation_report_jsonl(buf)

        assert loaded.per_stratum_source_counts == {
            "20/1/MONSTER/A": 100,
            "20/1/MONSTER/B": 1,
        }
        # Build aggregates with the loaded counts — should use weighted path.
        aggs = build_evaluation_aggregates(
            loaded, per_stratum_source_counts=loaded.per_stratum_source_counts
        )
        # Win in stratum A (weight 100), loss in stratum B (weight 1).
        assert aggs.natural_weighted.win_rate == pytest.approx(100.0 / 101.0, 0.01)

    def test_weighted_aggregate_quota_2(self):
        """Two selected from a 100-source stratum: each weight = 100/2 = 50."""
        from sts_combat_rl.sim.fixed_battle_evaluation import (
            _build_weighted_aggregate_slice,
        )

        results = [
            self._make_result(0, "win", hp_loss=5, encounter_id="A"),
            self._make_result(1, "loss", hp_loss=10, encounter_id="A"),
        ]
        weights = {(20, 1, "MONSTER", "A"): 50.0}
        slc = _build_weighted_aggregate_slice(results, weights)
        assert slc.win_rate == 0.5
        expected_mean = (50.0 * 5 + 50.0 * 10) / 100.0
        assert slc.mean_hp_loss == pytest.approx(expected_mean, 0.1)

    def test_weighted_aggregate_no_weights_fallback(self):
        """Empty weights dict falls back to equal-weight."""
        from sts_combat_rl.sim.fixed_battle_evaluation import (
            _build_weighted_aggregate_slice,
        )

        results = [
            self._make_result(0, "win", hp_loss=5, encounter_id="A"),
            self._make_result(1, "loss", hp_loss=15, encounter_id="B"),
        ]
        slc = _build_weighted_aggregate_slice(results, {})
        assert slc.win_rate == 0.5
        assert slc.mean_hp_loss == 10.0
        """All errors/truncations => win_rate is None."""
        results = [
            self._make_result(0, "truncated"),
            self._make_result(1, "error"),
        ]
        report = FixedEvaluationReport(
            cohort_identity="test",
            controller_provenance={"kind": "test", "name": "test"},
            information_regime="normal_public_policy",
            action_space_config={},
            max_battle_steps=200,
            source_pool_format_version=2,
            selection_config={},
            battle_results=results,
        )
        aggs = build_evaluation_aggregates(report)
        assert aggs.natural_weighted.win_rate is None


class TestEvaluationReportSerialization:
    """JSONL round-trip tests."""

    def test_dump_load_round_trip(self):
        result = SingleBattleEvaluationResult(
            cohort_index=0,
            source_checkpoint_id="cp-0",
            source_seed=1,
            source_run_id="run-0",
            source_battle_index=0,
            structural_stratum=(20, 1, "MONSTER", "Cultist"),
            structural_metadata={"encounter_id": "Cultist"},
            restoration_method="seed_action_trace",
            controller_provenance={"kind": "test"},
            information_regime="normal_public_policy",
            action_space_config={},
            termination_status="win",
            terminal_absolute_hp=65,
            hp_loss=5,
            decision_count=3,
            simulator_step_count=3,
            wall_clock_time_s=0.3,
            controller_compute_telemetry={"nodes": 42},
            battle_initial_hp=70,
            battle_initial_max_hp=80,
        )
        report = FixedEvaluationReport(
            cohort_identity="id-abc",
            controller_provenance={"kind": "test", "name": "fake"},
            information_regime="normal_public_policy",
            action_space_config={},
            max_battle_steps=200,
            source_pool_format_version=2,
            selection_config={"selection_seed": 1},
            battle_results=[result],
            problems=[],
        )

        buf = StringIO()
        dump_fixed_evaluation_report_jsonl(report, buf)
        buf.seek(0)
        loaded = load_fixed_evaluation_report_jsonl(buf)

        assert loaded.cohort_identity == report.cohort_identity
        assert loaded.max_battle_steps == report.max_battle_steps
        assert len(loaded.battle_results) == 1
        lr = loaded.battle_results[0]
        assert lr.termination_status == "win"
        assert lr.terminal_absolute_hp == 65
        assert lr.hp_loss == 5
        assert lr.controller_compute_telemetry == {"nodes": 42}

    def test_public_context_fields_round_trip(self):
        public_context = _make_public_context()
        result = SingleBattleEvaluationResult(
            cohort_index=0,
            source_checkpoint_id="cp-0",
            source_seed=1,
            source_run_id="run-0",
            source_battle_index=0,
            structural_stratum=(20, 1, "MONSTER", "Cultist"),
            structural_metadata={"encounter_id": "Cultist"},
            restoration_method="seed_action_trace",
            controller_provenance={"kind": "test"},
            information_regime="normal_public_policy",
            action_space_config={},
            termination_status="error",
            terminal_absolute_hp=None,
            hp_loss=None,
            decision_count=0,
            simulator_step_count=0,
            wall_clock_time_s=0.0,
            public_context_status="available",
            public_run_context=public_context,
            public_context_replay_status="mismatch",
            public_context_replay_mismatches=[
                "result 0 public context replay: $.current.screen.value differs"
            ],
        )
        report = FixedEvaluationReport(
            cohort_identity="id-abc",
            controller_provenance={"kind": "test", "name": "fake"},
            information_regime="normal_public_policy",
            action_space_config={},
            max_battle_steps=200,
            source_pool_format_version=2,
            selection_config={"selection_seed": 1},
            battle_results=[result],
        )

        buf = StringIO()
        dump_fixed_evaluation_report_jsonl(report, buf)
        buf.seek(0)
        loaded = load_fixed_evaluation_report_jsonl(buf)

        loaded_result = loaded.battle_results[0]
        assert loaded_result.public_context_status == "available"
        assert loaded_result.public_run_context == public_context
        assert loaded_result.public_context_replay_status == "mismatch"
        assert loaded_result.public_context_replay_mismatches == [
            "result 0 public context replay: $.current.screen.value differs"
        ]

    def test_v1_migration_records_explicit_public_context_loss(self):
        result = SingleBattleEvaluationResult(
            cohort_index=0,
            source_checkpoint_id="cp-0",
            source_seed=1,
            source_run_id="run-0",
            source_battle_index=0,
            structural_stratum=(20, 1, "MONSTER", "Cultist"),
            structural_metadata={"encounter_id": "Cultist"},
            restoration_method="seed_action_trace",
            controller_provenance={"kind": "test"},
            information_regime="normal_public_policy",
            action_space_config={},
            termination_status="win",
            terminal_absolute_hp=65,
            hp_loss=5,
            decision_count=3,
            simulator_step_count=3,
            wall_clock_time_s=0.3,
        )
        report = FixedEvaluationReport(
            cohort_identity="id-abc",
            controller_provenance={"kind": "test", "name": "fake"},
            information_regime="normal_public_policy",
            action_space_config={},
            max_battle_steps=200,
            source_pool_format_version=2,
            selection_config={"selection_seed": 1},
            battle_results=[result],
        )
        buf = StringIO()
        dump_fixed_evaluation_report_jsonl(report, buf)
        rows = [json.loads(line) for line in buf.getvalue().splitlines()]
        rows[0]["metadata"]["format_version"] = 1
        for row in rows[1:]:
            row["result"].pop("public_context_status", None)
            row["result"].pop("public_run_context", None)
            row["result"].pop("public_context_replay_status", None)
            row["result"].pop("public_context_replay_mismatches", None)
        legacy_text = "\n".join(json.dumps(row, sort_keys=True) for row in rows)

        loaded = load_fixed_evaluation_report_jsonl(StringIO(legacy_text))

        loaded_result = loaded.battle_results[0]
        assert loaded.migration_report.applied_versions == (2, 3)
        assert PUBLIC_CONTEXT_LEGACY_LOSS in loaded.migration_report.losses
        assert BATTLE_RESOURCE_OUTCOME_LEGACY_LOSS in loaded.migration_report.losses
        assert loaded_result.public_context_status == "legacy_unavailable"
        assert loaded_result.public_run_context == {}
        assert loaded_result.public_context_replay_status == "legacy_unavailable"
        assert loaded_result.public_context_replay_mismatches == []
        assert loaded_result.structured_battle_outcome_status == "legacy_unavailable"
        assert loaded_result.structured_battle_outcome == {}

    def test_load_missing_metadata_raises(self):
        buf = StringIO('{"type": "result", "result": {}}\n')
        with pytest.raises(ValueError, match="missing evaluation report metadata"):
            load_fixed_evaluation_report_jsonl(buf)

    def test_load_invalid_json_raises(self):
        buf = StringIO("not json\n")
        with pytest.raises(ValueError, match="invalid JSON"):
            load_fixed_evaluation_report_jsonl(buf)

    def test_none_telemetry_preserved(self):
        result = SingleBattleEvaluationResult(
            cohort_index=0,
            source_checkpoint_id="cp-0",
            source_seed=1,
            source_run_id="r",
            source_battle_index=0,
            structural_stratum=(20, 1, "M", "C"),
            structural_metadata={},
            restoration_method="seed_action_trace",
            controller_provenance={},
            information_regime="normal_public_policy",
            action_space_config={},
            termination_status="win",
            terminal_absolute_hp=None,
            hp_loss=None,
            decision_count=0,
            simulator_step_count=0,
            wall_clock_time_s=0.0,
            controller_compute_telemetry=None,  # explicit None
        )
        report = FixedEvaluationReport(
            cohort_identity="test",
            controller_provenance={},
            information_regime="normal_public_policy",
            action_space_config={},
            max_battle_steps=200,
            source_pool_format_version=2,
            selection_config={},
            battle_results=[result],
        )
        buf = StringIO()
        dump_fixed_evaluation_report_jsonl(report, buf)
        buf.seek(0)
        loaded = load_fixed_evaluation_report_jsonl(buf)
        assert loaded.battle_results[0].controller_compute_telemetry is None


class TestEvaluationReportFormatting:
    """Format tests."""

    def test_format_includes_all_sections(self):
        result = SingleBattleEvaluationResult(
            cohort_index=0,
            source_checkpoint_id="cp-0",
            source_seed=1,
            source_run_id="r",
            source_battle_index=0,
            structural_stratum=(20, 1, "MONSTER", "Cultist"),
            structural_metadata={},
            restoration_method="seed_action_trace",
            controller_provenance={"kind": "test", "name": "fake"},
            information_regime="normal_public_policy",
            action_space_config={},
            termination_status="win",
            terminal_absolute_hp=65,
            hp_loss=5,
            decision_count=3,
            simulator_step_count=3,
            wall_clock_time_s=0.3,
        )
        report = FixedEvaluationReport(
            cohort_identity="test-id",
            controller_provenance={"kind": "test", "name": "fake"},
            information_regime="normal_public_policy",
            action_space_config={},
            max_battle_steps=200,
            source_pool_format_version=2,
            selection_config={},
            battle_results=[result],
        )
        output = format_fixed_evaluation_report(report)
        assert "cohort identity: test-id" in output
        assert "controller: fake" in output
        assert "information regime: normal_public_policy" in output
        assert "authoritative wins: 1" in output
        assert "natural-weighted aggregate" in output
        assert "encounter-macro" in output
        assert "room-type-macro" in output
        assert "per-stratum" in output
        assert "evaluation successful: yes" in output

    def test_format_shows_errors_and_truncations(self):
        results = [
            SingleBattleEvaluationResult(
                cohort_index=0,
                source_checkpoint_id="c0",
                source_seed=1,
                source_run_id="r",
                source_battle_index=0,
                structural_stratum=(20, 1, "M", "C"),
                structural_metadata={},
                restoration_method="seed_action_trace",
                controller_provenance={"kind": "test", "name": "test"},
                information_regime="normal_public_policy",
                action_space_config={},
                termination_status="error",
                terminal_absolute_hp=None,
                hp_loss=None,
                decision_count=0,
                simulator_step_count=0,
                wall_clock_time_s=0.0,
                problems=["kapow"],
            ),
            SingleBattleEvaluationResult(
                cohort_index=1,
                source_checkpoint_id="c1",
                source_seed=1,
                source_run_id="r",
                source_battle_index=1,
                structural_stratum=(20, 1, "M", "C"),
                structural_metadata={},
                restoration_method="seed_action_trace",
                controller_provenance={"kind": "test", "name": "test"},
                information_regime="normal_public_policy",
                action_space_config={},
                termination_status="truncated",
                terminal_absolute_hp=40,
                hp_loss=10,
                decision_count=10,
                simulator_step_count=10,
                wall_clock_time_s=1.0,
            ),
        ]
        report = FixedEvaluationReport(
            cohort_identity="test",
            controller_provenance={"kind": "test", "name": "test"},
            information_regime="normal_public_policy",
            action_space_config={},
            max_battle_steps=200,
            source_pool_format_version=2,
            selection_config={},
            battle_results=results,
            problems=["eval had problems"],
        )
        output = format_fixed_evaluation_report(report)
        assert "errors: 1" in output
        assert "truncations: 1" in output
        assert "evaluation successful: no" in output
        assert "eval had problems" in output


class TestAggregateSlice:
    """Unit tests for AggregateSlice dataclass."""

    def test_empty_slice(self):
        slc = AggregateSlice()
        assert slc.battle_count == 0
        assert slc.win_rate is None
        assert slc.mean_hp_loss is None

    def test_all_wins(self):
        slc = AggregateSlice(
            battle_count=3, win_count=3, loss_count=0, total_hp_loss=15
        )
        assert slc.win_rate == 1.0
        assert slc.mean_hp_loss == 5.0

    def test_all_losses(self):
        slc = AggregateSlice(
            battle_count=2, win_count=0, loss_count=2, total_hp_loss=20
        )
        assert slc.win_rate == 0.0
        assert slc.mean_hp_loss == 10.0
