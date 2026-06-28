from __future__ import annotations

from dataclasses import dataclass, field
from io import StringIO

from sts_combat_rl.commands.model_guided_search_comparison import (
    run_model_guided_search_fixed_comparison_from_cohort_path,
    run_model_guided_search_v2_fixed_comparison_from_cohort_path,
)
from sts_combat_rl.sim.action_space import ActionSpaceConfig
from sts_combat_rl.sim.contract import (
    SimulatorAction,
    SimulatorCheckpoint,
    SimulatorSnapshot,
    SimulatorTransition,
)
from sts_combat_rl.sim.fixed_battle_evaluation import (
    FixedEvaluationReport,
    SingleBattleEvaluationResult,
)
from sts_combat_rl.sim.fixed_evaluation_set import (
    FixedCohort,
    FixedCohortRecord,
    FixedCohortSelectionConfig,
    dump_fixed_cohort_jsonl,
)
from sts_combat_rl.sim.model_guided_oracle_search import (
    ModelGuidedOracleSearchController,
    ModelGuidedOracleSearchV2Controller,
)
from sts_combat_rl.sim.model_guided_search_comparison import (
    BASELINE_ORACLE_LABEL,
    MODEL_GUIDED_ORACLE_LABEL,
    MODEL_GUIDED_ORACLE_V1_LABEL,
    MODEL_GUIDED_ORACLE_V2_LABEL,
    build_model_guided_search_fixed_comparison_report,
    comparison_aggregate_outcomes,
    comparison_budget_summary,
    comparison_v2_aggregate_outcomes,
    comparison_v2_budget_summary,
    comparison_v2_controller_summaries,
    comparison_controller_summaries,
    dump_model_guided_search_fixed_comparison_jsonl,
    dump_model_guided_search_v2_fixed_comparison_jsonl,
    format_model_guided_search_fixed_comparison_report,
    format_model_guided_search_v2_fixed_comparison_report,
    load_model_guided_search_fixed_comparison_jsonl,
    load_model_guided_search_v2_fixed_comparison_jsonl,
)
from sts_combat_rl.sim.online_controller import NATIVE_SEARCH_INFORMATION_REGIME
from sts_combat_rl.sim.oracle_search import (
    ORACLE_SEARCH_NATIVE_API,
    ORACLE_SEARCH_PATCH_IDENTITY,
    ORACLE_SEARCH_SCHEMA_ID,
    OracleSearchController,
)
from sts_combat_rl.sim.search_guidance_inference import (
    SearchGuidanceActionScore,
    SearchGuidanceCheckpointProvenance,
    SearchGuidanceInferenceResult,
)


def _checkpoint() -> SearchGuidanceCheckpointProvenance:
    return SearchGuidanceCheckpointProvenance(
        checkpoint_schema_id="torch-policy-value-checkpoint-v1",
        checkpoint_format_version=1,
        checkpoint_artifact_id="checkpoint-unit",
        checkpoint_path="/tmp/checkpoint-unit.pt",
        model_class="TinyPolicyValueNet",
        model_config={"hidden_size": 8},
        trainer_input_artifact_id="trainer-input-sha256:unit",
        trainer_input_sha256="unit",
        policy_target_kind="oracle_teacher_action_one_hot",
        policy_target_source="oracle_teacher_row.teacher_action",
        policy_target_kind_counts={"oracle_teacher_action_one_hot": 1},
        policy_target_source_counts={"oracle_teacher_row.teacher_action": 1},
        information_regime_counts={"normal_public_policy": 1},
        source_information_regime_counts={NATIVE_SEARCH_INFORMATION_REGIME: 1},
        oracle_like_supervision=True,
        training_data_provenance={"artifact": "unit"},
    )


def _actions() -> list[SimulatorAction]:
    return [
        SimulatorAction(
            action_id="battle:11",
            label="Strike",
            kind="card",
            raw={"scope": "battle", "bits": 11, "idx1": 0, "idx2": 0, "idx3": 0},
        ),
        SimulatorAction(
            action_id="battle:22",
            label="Defend",
            kind="card",
            raw={"scope": "battle", "bits": 22, "idx1": 0, "idx2": 0, "idx3": 0},
        ),
    ]


def _battle_snapshot() -> SimulatorSnapshot:
    return SimulatorSnapshot(
        observation=(1, 2, 3),
        raw={
            "screen_state": "BATTLE",
            "battle_active": True,
            "outcome": "UNDECIDED",
            "ascension": 20,
            "act": 1,
            "floor_num": 5,
            "room_type": "MONSTER",
            "encounter_id": "Cultist",
            "cur_hp": 70,
            "max_hp": 80,
        },
    )


def _raw_search(simulations: int) -> dict[str, object]:
    return {
        "schema_id": ORACLE_SEARCH_SCHEMA_ID,
        "native_api": ORACLE_SEARCH_NATIVE_API,
        "patch_identity": ORACLE_SEARCH_PATCH_IDENTITY,
        "information_regime": NATIVE_SEARCH_INFORMATION_REGIME,
        "simulations_requested": simulations,
        "root_visits": simulations,
        "include_potions": False,
        "native_simulator_steps": 21,
        "model_calls": None,
        "best_action_value": 0.50,
        "min_action_value": 0.49,
        "outcome_player_hp": 66,
        "root_row_count": 2,
        "search_edge_count": 2,
        "unsearched_legal_action_count": 0,
        "unmapped_search_edge_count": 0,
        "root_rows": [
            {
                "scope": "battle",
                "bits": 11,
                "kind": "card",
                "label": "Strike",
                "idx1": 0,
                "idx2": 0,
                "idx3": 0,
                "search_tree_present": True,
                "search_edge_index": 0,
                "visits": 6,
                "evaluation_sum": 3.0,
                "mean_value": 0.50,
            },
            {
                "scope": "battle",
                "bits": 22,
                "kind": "card",
                "label": "Defend",
                "idx1": 0,
                "idx2": 0,
                "idx3": 0,
                "search_tree_present": True,
                "search_edge_index": 1,
                "visits": 4,
                "evaluation_sum": 1.96,
                "mean_value": 0.49,
            },
        ],
    }


class _ComparisonAdapter:
    supports_checkpoint_restore = True
    checkpoint_adapter_id = "comparison-adapter"

    def reset(self, *, seed: int | None = None) -> SimulatorSnapshot:
        del seed
        return _battle_snapshot()

    def legal_actions(self, snapshot: SimulatorSnapshot) -> list[SimulatorAction]:
        del snapshot
        return _actions()

    def step(self, action: SimulatorAction) -> SimulatorTransition:
        if action.raw.get("bits") == 22:
            raw = {
                "screen_state": "BOSS_REWARD",
                "battle_active": False,
                "outcome": "PLAYER_VICTORY",
                "completed_battle_outcome": "PLAYER_VICTORY",
                "cur_hp": 66,
                "max_hp": 80,
                "floor_num": 5,
            }
        else:
            raw = {
                "screen_state": "GAME_OVER",
                "battle_active": False,
                "outcome": "PLAYER_LOSS",
                "completed_battle_outcome": "PLAYER_LOSS",
                "cur_hp": 0,
                "max_hp": 80,
                "floor_num": 5,
            }
        return SimulatorTransition(
            snapshot=SimulatorSnapshot(observation=(9, 9), raw=raw),
            terminal=True,
            info={},
        )

    def capture_checkpoint(self, snapshot: SimulatorSnapshot) -> SimulatorCheckpoint:
        del snapshot
        return SimulatorCheckpoint(
            checkpoint_id="comparison-cp",
            adapter_id=self.checkpoint_adapter_id,
            payload=None,
        )

    def restore_checkpoint(self, checkpoint: SimulatorCheckpoint) -> SimulatorSnapshot:
        del checkpoint
        return _battle_snapshot()

    def battle_search(
        self,
        snapshot: SimulatorSnapshot,
        *,
        simulations: int,
        include_potions: bool = False,
    ) -> dict[str, object]:
        del snapshot, include_potions
        return _raw_search(simulations)


@dataclass
class _FakeGuidanceScorer:
    probabilities: tuple[float, ...] = (0.10, 0.90)
    checkpoint_provenance: SearchGuidanceCheckpointProvenance = field(
        default_factory=_checkpoint
    )
    name: str = "fake_comparison_guidance"

    def score_decision_context(self, context) -> SearchGuidanceInferenceResult:
        return SearchGuidanceInferenceResult(
            scorer_name=self.name,
            checkpoint_provenance=self.checkpoint_provenance,
            legal_action_count=len(context.legal_action_features),
            eligible_action_count=len(context.eligible_action_indices),
            action_scores=[
                SearchGuidanceActionScore(
                    legal_action_index=index,
                    action_kind=context.legal_action_kinds[index],
                    eligible=index in context.eligible_action_indices,
                    policy_logit=float(index),
                    policy_probability=probability,
                    action_identity=_context_action_identity(context, index),
                )
                for index, probability in enumerate(self.probabilities)
            ],
            duration_ms=1.0,
        )


def _context_action_identity(context, index: int) -> dict[str, object]:
    if index < len(context.tactical_legal_actions):
        identity = context.tactical_legal_actions[index].get("identity", {})
        if isinstance(identity, dict):
            return dict(identity)
    return {}


def _cohort() -> FixedCohort:
    snapshot = _battle_snapshot()
    return FixedCohort(
        source_pool_format_version=3,
        source_pool_controller_provenance={"kind": "source", "name": "source"},
        selection_config=FixedCohortSelectionConfig(selection_seed=7),
        records=[
            FixedCohortRecord(
                cohort_index=0,
                source_pool_record_index=0,
                source_checkpoint_id="cp-0",
                source_run_id="seed-1-run-0",
                source_seed=1,
                source_battle_index=0,
                structural_stratum=(20, 1, "MONSTER", "Cultist"),
                structural_metadata={
                    "ascension": 20,
                    "act": 1,
                    "floor": 5,
                    "room_type": "MONSTER",
                    "encounter_id": "Cultist",
                    "seed": 1,
                    "source_kind": "natural_run",
                    "distribution_kind": "natural_run",
                    "source_run_id": "seed-1-run-0",
                    "source_battle_index": 0,
                },
                source_controller_provenance={"kind": "source", "name": "source"},
                source_battle_controller_provenance={
                    "kind": "battle",
                    "name": "battle",
                },
                source_non_combat_controller_provenance={
                    "kind": "non_combat",
                    "name": "non_combat",
                },
                action_trace=(),
                snapshot_observation=tuple(snapshot.observation),
                snapshot_raw=dict(snapshot.raw),
                source_distribution_kind="natural_run",
            )
        ],
    )


def test_comparison_runs_both_controllers_on_identical_sources(tmp_path) -> None:
    cohort_path = tmp_path / "cohort.jsonl"
    with cohort_path.open("w", encoding="utf-8", newline="\n") as stream:
        dump_fixed_cohort_jsonl(_cohort(), stream)
    action_space = ActionSpaceConfig.initial_no_potions()
    baseline = OracleSearchController(
        simulations=10,
        root_selection_rule="highest_mean",
        action_space=action_space,
        native_source_identity={"integration_commit": "abc"},
    )
    model_guided = ModelGuidedOracleSearchController(
        simulations=10,
        scorer=_FakeGuidanceScorer(),
        policy_probability_weight=0.10,
        action_space=action_space,
        native_source_identity={"integration_commit": "abc"},
    )

    report = run_model_guided_search_fixed_comparison_from_cohort_path(
        adapter_factory=_ComparisonAdapter,
        cohort_path=cohort_path,
        baseline_controller=baseline,
        model_guided_controller=model_guided,
        action_space=action_space,
        max_battle_steps=3,
        run_scale="smoke",
    )

    assert report.evaluation_successful
    assert not report.source_match_problems
    assert report.baseline_report.losses == 1
    assert report.model_guided_report.authoritative_wins == 1
    model_config = report.model_guided_report.controller_provenance["config"]
    assert (
        model_config["guidance_scorer"]["checkpoint_provenance"][
            "checkpoint_artifact_id"
        ]
        == "checkpoint-unit"
    )

    summaries = comparison_controller_summaries(report)
    baseline_summary = summaries[BASELINE_ORACLE_LABEL]["search_telemetry_summary"]
    model_summary = summaries[MODEL_GUIDED_ORACLE_LABEL]["search_telemetry_summary"]
    assert baseline_summary["model_calls"]["total"] == 0.0
    assert model_summary["model_calls"]["total"] == 1.0
    assert baseline_summary["native_simulator_steps"]["total"] == 21.0
    assert model_summary["native_simulator_steps"]["total"] == 21.0

    aggregates = comparison_aggregate_outcomes(report)
    assert aggregates[BASELINE_ORACLE_LABEL]["natural_weighted"]["win_rate"] == 0.0
    assert aggregates[MODEL_GUIDED_ORACLE_LABEL]["natural_weighted"]["win_rate"] == 1.0

    budget = comparison_budget_summary(report)
    assert budget["equal_native_playout_budget"] is True
    assert budget["baseline_observed"]["model_calls"] == 0.0
    assert budget["model_guided_observed"]["model_calls"] == 1.0

    text = format_model_guided_search_fixed_comparison_report(report)
    assert "Model-guided search fixed-cohort comparison" in text
    assert "run scale: smoke-scale" in text
    assert "source starts matched: yes" in text
    assert "full_simulator_state_oracle_like diagnostics only" in text
    assert "natural-weighted win rate: baseline=0.0000, model-guided=1.0000" in text
    assert "model calls: total=1" in text

    buffer = StringIO()
    dump_model_guided_search_fixed_comparison_jsonl(report, buffer)
    assert '"schema_id": "model-guided-search-fixed-comparison-v1"' in (
        buffer.getvalue()
    )
    loaded = load_model_guided_search_fixed_comparison_jsonl(
        StringIO(buffer.getvalue())
    )
    assert loaded.evaluation_successful
    assert loaded.model_guided_report.authoritative_wins == 1
    assert loaded.baseline_report.losses == 1


def test_v2_comparison_runs_three_controllers_on_identical_sources(tmp_path) -> None:
    cohort_path = tmp_path / "cohort.jsonl"
    with cohort_path.open("w", encoding="utf-8", newline="\n") as stream:
        dump_fixed_cohort_jsonl(_cohort(), stream)
    action_space = ActionSpaceConfig.initial_no_potions()
    baseline = OracleSearchController(
        simulations=10,
        root_selection_rule="highest_mean",
        action_space=action_space,
        native_source_identity={"integration_commit": "abc"},
    )
    model_guided_v1 = ModelGuidedOracleSearchController(
        simulations=10,
        scorer=_FakeGuidanceScorer(),
        policy_probability_weight=0.10,
        action_space=action_space,
        native_source_identity={"integration_commit": "abc"},
    )
    model_guided_v2 = ModelGuidedOracleSearchV2Controller(
        simulations=10,
        scorer=_FakeGuidanceScorer(),
        policy_probability_weight=0.10,
        action_space=action_space,
        native_source_identity={"integration_commit": "abc"},
    )

    report = run_model_guided_search_v2_fixed_comparison_from_cohort_path(
        adapter_factory=_ComparisonAdapter,
        cohort_path=cohort_path,
        baseline_controller=baseline,
        model_guided_v1_controller=model_guided_v1,
        model_guided_v2_controller=model_guided_v2,
        action_space=action_space,
        max_battle_steps=3,
        run_scale="smoke",
    )

    assert report.evaluation_successful
    assert not report.source_match_problems
    assert report.baseline_report.losses == 1
    assert report.model_guided_v1_report.authoritative_wins == 1
    assert report.model_guided_v2_report.authoritative_wins == 1

    summaries = comparison_v2_controller_summaries(report)
    assert (
        summaries[MODEL_GUIDED_ORACLE_V1_LABEL]["controller_name"]
        == "model_guided_oracle_search_v1_s10_pw0.1"
    )
    assert (
        summaries[MODEL_GUIDED_ORACLE_V2_LABEL]["controller_name"]
        == "model_guided_oracle_search_v2_s10_pw0.1"
    )
    assert (
        summaries[BASELINE_ORACLE_LABEL]["search_telemetry_summary"]["model_calls"][
            "total"
        ]
        == 0.0
    )
    assert (
        summaries[MODEL_GUIDED_ORACLE_V1_LABEL]["search_telemetry_summary"][
            "model_calls"
        ]["total"]
        == 1.0
    )
    assert (
        summaries[MODEL_GUIDED_ORACLE_V2_LABEL]["search_telemetry_summary"][
            "model_calls"
        ]["total"]
        == 1.0
    )

    aggregates = comparison_v2_aggregate_outcomes(report)
    assert aggregates[BASELINE_ORACLE_LABEL]["natural_weighted"]["win_rate"] == 0.0
    assert (
        aggregates[MODEL_GUIDED_ORACLE_V1_LABEL]["natural_weighted"]["win_rate"] == 1.0
    )
    assert (
        aggregates[MODEL_GUIDED_ORACLE_V2_LABEL]["natural_weighted"]["win_rate"] == 1.0
    )

    budget = comparison_v2_budget_summary(report)
    assert budget["equal_native_playout_budget"] is True
    assert budget["observed"][BASELINE_ORACLE_LABEL]["model_calls"] == 0.0
    assert budget["observed"][MODEL_GUIDED_ORACLE_V1_LABEL]["model_calls"] == 1.0
    assert budget["observed"][MODEL_GUIDED_ORACLE_V2_LABEL]["model_calls"] == 1.0

    text = format_model_guided_search_v2_fixed_comparison_report(report)
    assert "Model-guided Oracle search v2 fixed-cohort comparison" in text
    assert "run scale: smoke-scale" in text
    assert "source starts matched: yes" in text
    assert "model_guided_oracle_search_v2:" in text

    buffer = StringIO()
    dump_model_guided_search_v2_fixed_comparison_jsonl(report, buffer)
    assert '"schema_id": "model-guided-search-fixed-comparison-v2"' in (
        buffer.getvalue()
    )
    loaded = load_model_guided_search_v2_fixed_comparison_jsonl(
        StringIO(buffer.getvalue())
    )
    assert loaded.evaluation_successful
    assert loaded.model_guided_v1_report.authoritative_wins == 1
    assert loaded.model_guided_v2_report.authoritative_wins == 1
    assert loaded.baseline_report.losses == 1


def _manual_result(
    checkpoint_id: str,
    *,
    status: str,
    restoration_method: str = "seed_action_trace",
) -> SingleBattleEvaluationResult:
    return SingleBattleEvaluationResult(
        cohort_index=0,
        source_checkpoint_id=checkpoint_id,
        source_seed=1,
        source_run_id="run-0",
        source_battle_index=0,
        structural_stratum=(20, 1, "MONSTER", "Cultist"),
        structural_metadata={"encounter_id": "Cultist"},
        restoration_method=restoration_method,
        controller_provenance={"kind": "test", "name": "test"},
        information_regime=NATIVE_SEARCH_INFORMATION_REGIME,
        action_space_config={},
        termination_status=status,
        terminal_absolute_hp=None,
        hp_loss=None,
        decision_count=0,
        simulator_step_count=0,
        wall_clock_time_s=0.0,
        problems=["problem"] if status in {"error", "truncated"} else [],
    )


def _manual_report(
    result: SingleBattleEvaluationResult,
    *,
    name: str,
) -> FixedEvaluationReport:
    return FixedEvaluationReport(
        cohort_identity="cohort-id",
        controller_provenance={
            "kind": "test",
            "name": name,
            "config": {
                "information_regime": NATIVE_SEARCH_INFORMATION_REGIME,
                "search_budget": {"simulations": 5},
            },
        },
        information_regime=NATIVE_SEARCH_INFORMATION_REGIME,
        action_space_config={},
        max_battle_steps=5,
        source_pool_format_version=3,
        selection_config={"selection_seed": 1},
        per_stratum_source_counts={"20/1/MONSTER/Cultist": 1},
        battle_results=[result],
        problems=["report problem"] if result.termination_status == "error" else [],
    )


def test_comparison_fails_closed_on_source_mismatch_and_counts_failures() -> None:
    baseline_report = _manual_report(
        _manual_result("cp-a", status="error", restoration_method="failed"),
        name="baseline",
    )
    model_report = _manual_report(
        _manual_result("cp-b", status="truncated"),
        name="model",
    )

    report = build_model_guided_search_fixed_comparison_report(
        baseline_report=baseline_report,
        model_guided_report=model_report,
        comparison_config={"run_scale": "fixed"},
    )

    assert not report.evaluation_successful
    assert any("source battle mismatch" in p for p in report.source_match_problems)
    summaries = comparison_controller_summaries(report)
    assert summaries[BASELINE_ORACLE_LABEL]["restore_failures"] == 1
    assert summaries[BASELINE_ORACLE_LABEL]["errors"] == 1
    assert summaries[MODEL_GUIDED_ORACLE_LABEL]["truncations"] == 1

    text = format_model_guided_search_fixed_comparison_report(report)
    assert "run scale: fixed" in text
    assert "source starts matched: no" in text
    assert "restore/truncation/error counts: baseline=1/0/1, model-guided=0/1/0" in text
