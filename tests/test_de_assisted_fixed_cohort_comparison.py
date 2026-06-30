from __future__ import annotations

from dataclasses import dataclass, field, replace
from io import StringIO

from sts_combat_rl.commands.de_assisted_fixed_cohort_comparison import (
    run_de_assisted_fixed_cohort_comparison_from_cohort_path,
)
from sts_combat_rl.sim.action_space import ActionSpaceConfig
from sts_combat_rl.sim.battle_start_pool import (
    ASSISTED_RUN_DISTRIBUTION_KIND,
    NATURAL_DISTRIBUTION_KIND,
)
from sts_combat_rl.sim.contract import (
    SimulatorAction,
    SimulatorCheckpoint,
    SimulatorSnapshot,
    SimulatorTransition,
)
from sts_combat_rl.sim.de_assisted_fixed_cohort_comparison import (
    BASELINE_ORACLE_LABEL,
    MODEL_GUIDED_ORACLE_V2_LABEL,
    RAW_CHECKPOINT_POLICY_LABEL,
    SCRIPTED_POLICY_LABEL,
    de_assisted_aggregate_outcomes,
    de_assisted_budget_summary,
    de_assisted_controller_summaries,
    dump_de_assisted_fixed_cohort_comparison_jsonl,
    format_de_assisted_fixed_cohort_comparison_report,
    load_de_assisted_fixed_cohort_comparison_jsonl,
)
from sts_combat_rl.sim.fixed_evaluation_set import (
    FixedCohort,
    FixedCohortRecord,
    FixedCohortSelectionConfig,
    dump_fixed_cohort_jsonl,
)
from sts_combat_rl.sim.model_guided_oracle_search import (
    ModelGuidedOracleSearchV2Controller,
)
from sts_combat_rl.sim.model_scoring import ActionKindPriorScorer
from sts_combat_rl.sim.online_controller import (
    NATIVE_SEARCH_INFORMATION_REGIME,
    PolicyController,
)
from sts_combat_rl.sim.oracle_search import (
    ORACLE_SEARCH_NATIVE_API,
    ORACLE_SEARCH_PATCH_IDENTITY,
    ORACLE_SEARCH_SCHEMA_ID,
    OracleSearchController,
)
from sts_combat_rl.sim.policy import ScoredActionPolicy
from sts_combat_rl.sim.search_guidance_inference import (
    SearchGuidanceActionScore,
    SearchGuidanceCheckpointProvenance,
    SearchGuidanceInferenceResult,
)
from sts_combat_rl.sim.search_guidance_policy import SearchGuidancePolicyController


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
        policy_target_kind_counts={"oracle_teacher_action_one_hot": 2},
        policy_target_source_counts={"oracle_teacher_row.teacher_action": 2},
        information_regime_counts={"normal_public_policy": 2},
        source_information_regime_counts={NATIVE_SEARCH_INFORMATION_REGIME: 2},
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
    checkpoint_adapter_id = "de-assisted-comparison-adapter"

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
            checkpoint_id="de-assisted-comparison-cp",
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
    name: str = "fake_de_assisted_guidance"

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


def _natural_record() -> FixedCohortRecord:
    snapshot = _battle_snapshot()
    return FixedCohortRecord(
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
            "source_kind": NATURAL_DISTRIBUTION_KIND,
            "distribution_kind": NATURAL_DISTRIBUTION_KIND,
            "source_run_id": "seed-1-run-0",
            "source_battle_index": 0,
        },
        source_controller_provenance={"kind": "source", "name": "source"},
        source_battle_controller_provenance={"kind": "battle", "name": "battle"},
        source_non_combat_controller_provenance={
            "kind": "non_combat",
            "name": "non_combat",
        },
        action_trace=(),
        snapshot_observation=tuple(snapshot.observation),
        snapshot_raw=dict(snapshot.raw),
        source_distribution_kind=NATURAL_DISTRIBUTION_KIND,
    )


def _cohort() -> FixedCohort:
    natural = _natural_record()
    assisted = replace(
        natural,
        cohort_index=1,
        source_pool_record_index=1,
        source_checkpoint_id="cp-1",
        source_run_id="seed-2-assisted-run-0",
        source_seed=2,
        structural_metadata={
            **natural.structural_metadata,
            "seed": 2,
            "source_kind": ASSISTED_RUN_DISTRIBUTION_KIND,
            "distribution_kind": ASSISTED_RUN_DISTRIBUTION_KIND,
            "assistance_level": "assist_hp50",
            "source_run_id": "seed-2-assisted-run-0",
        },
        source_distribution_kind=ASSISTED_RUN_DISTRIBUTION_KIND,
    )
    return FixedCohort(
        source_pool_format_version=3,
        source_pool_controller_provenance={"kind": "source", "name": "source"},
        selection_config=FixedCohortSelectionConfig(selection_seed=7),
        records=[natural, assisted],
    )


def test_de_assisted_comparison_runs_four_arms_on_identical_sources(
    tmp_path,
) -> None:
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
    guided = ModelGuidedOracleSearchV2Controller(
        simulations=10,
        scorer=_FakeGuidanceScorer(),
        policy_probability_weight=0.10,
        action_space=action_space,
        native_source_identity={"integration_commit": "abc"},
    )
    raw_policy = SearchGuidancePolicyController(_FakeGuidanceScorer())
    scripted = PolicyController(
        ScoredActionPolicy(ActionKindPriorScorer(), name=SCRIPTED_POLICY_LABEL)
    )

    report = run_de_assisted_fixed_cohort_comparison_from_cohort_path(
        adapter_factory=_ComparisonAdapter,
        cohort_path=cohort_path,
        controller_arms=(
            (BASELINE_ORACLE_LABEL, "baseline_oracle_search", baseline),
            (MODEL_GUIDED_ORACLE_V2_LABEL, "guided_v2", guided),
            (RAW_CHECKPOINT_POLICY_LABEL, "raw_policy", raw_policy),
            (SCRIPTED_POLICY_LABEL, "scripted_policy", scripted),
        ),
        action_space=action_space,
        max_battle_steps=3,
        run_scale="smoke",
    )

    assert report.evaluation_successful
    assert not report.source_match_problems
    assert report.cohort_identity == _cohort().identity

    summaries = de_assisted_controller_summaries(report)
    assert summaries[BASELINE_ORACLE_LABEL]["losses"] == 2
    assert summaries[MODEL_GUIDED_ORACLE_V2_LABEL]["authoritative_wins"] == 2
    assert summaries[RAW_CHECKPOINT_POLICY_LABEL]["authoritative_wins"] == 2
    assert summaries[SCRIPTED_POLICY_LABEL]["losses"] == 2
    assert summaries[BASELINE_ORACLE_LABEL]["model_calls"] == 0.0
    assert summaries[MODEL_GUIDED_ORACLE_V2_LABEL]["model_calls"] == 2.0
    assert summaries[RAW_CHECKPOINT_POLICY_LABEL]["model_calls"] == 2
    assert summaries[SCRIPTED_POLICY_LABEL]["model_calls"] is None

    aggregates = de_assisted_aggregate_outcomes(report)
    assert (
        aggregates[BASELINE_ORACLE_LABEL]["assistance_level"]["unassisted_or_missing"][
            "win_rate"
        ]
        == 0.0
    )
    assert (
        aggregates[MODEL_GUIDED_ORACLE_V2_LABEL]["assistance_level"]["assist_hp50"][
            "win_rate"
        ]
        == 1.0
    )

    budget = de_assisted_budget_summary(report)
    assert budget["equal_configured_native_playout_budget_for_search_arms"] is True
    assert budget["observed"][MODEL_GUIDED_ORACLE_V2_LABEL]["root_visits"] == 20.0
    assert budget["observed"][RAW_CHECKPOINT_POLICY_LABEL]["model_calls"] == 2

    text = format_de_assisted_fixed_cohort_comparison_report(report)
    assert "De-assisted fixed-cohort comparison" in text
    assert "source starts matched: yes" in text
    assert "assist_hp50: 1" in text
    assert "not controller-promotion" in text
    assert "checkpoint_raw_policy:" in text

    buffer = StringIO()
    dump_de_assisted_fixed_cohort_comparison_jsonl(report, buffer)
    assert '"schema_id": "de-assisted-fixed-cohort-comparison-v1"' in buffer.getvalue()
    assert '"label": "checkpoint_raw_policy"' in buffer.getvalue()

    loaded = load_de_assisted_fixed_cohort_comparison_jsonl(StringIO(buffer.getvalue()))
    assert loaded.evaluation_successful
    assert loaded.arms[2].label == RAW_CHECKPOINT_POLICY_LABEL
    assert loaded.arms[2].report.authoritative_wins == 2
