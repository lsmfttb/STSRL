from __future__ import annotations

from dataclasses import dataclass, field, replace
from io import StringIO

import pytest

from sts_combat_rl.commands.root_prior_guided_search_comparison import (
    run_root_prior_guided_search_comparison_from_cohort_path,
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
from sts_combat_rl.sim.controlled_run import build_decision_context
from sts_combat_rl.sim.decision_record import action_identity_dicts_for_actions
from sts_combat_rl.sim.fixed_evaluation_set import (
    FixedCohort,
    FixedCohortRecord,
    FixedCohortSelectionConfig,
    dump_fixed_cohort_jsonl,
)
from sts_combat_rl.sim.model_guided_oracle_search import (
    ModelGuidedOracleSearchV2Controller,
)
from sts_combat_rl.sim.native_root_prior_allocation import (
    NATIVE_ROOT_PRIOR_ALLOCATION_METADATA_SCHEMA_ID,
    NATIVE_ROOT_PRIOR_ALLOCATION_STRATEGY,
    NATIVE_ROOT_PRIOR_SEARCH_NATIVE_API,
    NATIVE_ROOT_PRIOR_SEARCH_PATCH_IDENTITY,
    build_root_action_prior_vector,
)
from sts_combat_rl.sim.online_controller import NATIVE_SEARCH_INFORMATION_REGIME
from sts_combat_rl.sim.oracle_search import (
    ORACLE_SEARCH_NATIVE_API,
    ORACLE_SEARCH_PATCH_IDENTITY,
    ORACLE_SEARCH_SCHEMA_ID,
    OracleSearchController,
)
from sts_combat_rl.sim.root_prior_guided_search import (
    RootPriorGuidedSearchController,
)
from sts_combat_rl.sim.root_prior_guided_search_comparison import (
    BASELINE_ORACLE_LABEL,
    POST_SEARCH_MODEL_GUIDED_LABEL,
    ROOT_PRIOR_GUIDED_LABEL,
    build_root_prior_guided_search_comparison_report,
    dump_root_prior_guided_search_comparison_jsonl,
    format_root_prior_guided_search_comparison_report,
    load_root_prior_guided_search_comparison_jsonl,
    root_prior_allocation_summary,
    root_prior_guided_budget_summary,
    root_prior_guided_controller_summaries,
    root_prior_guided_outcome_comparison,
)
from sts_combat_rl.sim.search_guidance_inference import (
    SearchGuidanceActionScore,
    SearchGuidanceCheckpointProvenance,
    SearchGuidanceInferenceResult,
)


def _checkpoint(
    artifact_id: str = "checkpoint-unit",
) -> SearchGuidanceCheckpointProvenance:
    return SearchGuidanceCheckpointProvenance(
        checkpoint_schema_id="torch-policy-value-checkpoint-v1",
        checkpoint_format_version=1,
        checkpoint_artifact_id=artifact_id,
        checkpoint_path=f"/tmp/{artifact_id}.pt",
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


def _raw_search(
    simulations: int,
    *,
    native_api: str = ORACLE_SEARCH_NATIVE_API,
    patch_identity: str = ORACLE_SEARCH_PATCH_IDENTITY,
    defend_mean: float = 0.49,
    allocated: tuple[int, int] | None = None,
    priors: tuple[float, float] | None = None,
) -> dict[str, object]:
    rows = [
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
            "evaluation_sum": defend_mean * 4,
            "mean_value": defend_mean,
        },
    ]
    if allocated is not None and priors is not None:
        for row, allocation, prior in zip(rows, allocated, priors, strict=True):
            row["allocated_root_visits"] = allocation
            row["root_prior"] = prior
    raw: dict[str, object] = {
        "schema_id": ORACLE_SEARCH_SCHEMA_ID,
        "native_api": native_api,
        "patch_identity": patch_identity,
        "information_regime": NATIVE_SEARCH_INFORMATION_REGIME,
        "simulations_requested": simulations,
        "root_visits": simulations,
        "include_potions": False,
        "native_simulator_steps": 21,
        "model_calls": None,
        "best_action_value": max(0.50, defend_mean),
        "min_action_value": min(0.50, defend_mean),
        "outcome_player_hp": 66,
        "root_row_count": 2,
        "search_edge_count": 2,
        "unsearched_legal_action_count": 0,
        "unmapped_search_edge_count": 0,
        "root_rows": rows,
    }
    if native_api == NATIVE_ROOT_PRIOR_SEARCH_NATIVE_API:
        raw["allocation_metadata"] = {
            "schema_id": NATIVE_ROOT_PRIOR_ALLOCATION_METADATA_SCHEMA_ID,
            "allocation_strategy": NATIVE_ROOT_PRIOR_ALLOCATION_STRATEGY,
            "prior_temperature": 1.0,
            "min_visits_per_legal_action": 1,
            "prior_allocation_weight": 1.0,
            "legal_action_prior_count": 2,
        }
    return raw


class _ComparisonAdapter:
    supports_checkpoint_restore = True
    checkpoint_adapter_id = "root-prior-comparison-adapter"

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
            checkpoint_id="root-prior-comparison-cp",
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

    def battle_search_with_root_priors(
        self,
        snapshot: SimulatorSnapshot,
        *,
        actions,
        context,
        simulations: int,
        include_potions: bool = False,
        root_action_priors=None,
        prior_temperature: float = 1.0,
        min_visits_per_legal_action: int = 1,
        prior_allocation_weight: float = 1.0,
    ) -> dict[str, object]:
        del snapshot, include_potions, prior_temperature
        del min_visits_per_legal_action, prior_allocation_weight
        vector = build_root_action_prior_vector(actions, context, root_action_priors)
        allocated = (2, 8) if vector[1] > vector[0] else (5, 5)
        return _raw_search(
            simulations,
            native_api=NATIVE_ROOT_PRIOR_SEARCH_NATIVE_API,
            patch_identity=NATIVE_ROOT_PRIOR_SEARCH_PATCH_IDENTITY,
            defend_mean=0.60,
            allocated=allocated,
            priors=(vector[0], vector[1]),
        )


@dataclass
class _FakeGuidanceScorer:
    probabilities: tuple[float, ...] = (0.10, 0.90)
    checkpoint_provenance: SearchGuidanceCheckpointProvenance = field(
        default_factory=_checkpoint
    )
    name: str = "fake_root_prior_guidance"

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


def _assistance_history() -> tuple[dict[str, object], ...]:
    return (
        {
            "source_battle_index": 0,
            "assistance_level": "assist_hp50",
            "distribution_kind": ASSISTED_RUN_DISTRIBUTION_KIND,
            "actual_change": {"native_rebuild_called": False},
        },
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
        assistance_history=_assistance_history(),
    )
    return FixedCohort(
        source_pool_format_version=3,
        source_pool_controller_provenance={"kind": "source", "name": "source"},
        selection_config=FixedCohortSelectionConfig(selection_seed=7),
        records=[natural, assisted],
    )


def test_root_prior_guided_controller_uses_model_priors_for_allocation_only() -> None:
    action_space = ActionSpaceConfig.initial_no_potions()
    snapshot = _battle_snapshot()
    actions = _actions()
    context = build_decision_context(snapshot.raw, actions, action_space)
    controller = RootPriorGuidedSearchController(
        simulations=10,
        scorer=_FakeGuidanceScorer(),
        root_selection_rule="highest_mean",
        action_space=action_space,
    )

    decision = controller.select_action(
        _ComparisonAdapter(),
        snapshot,
        actions,
        context,
        step_index=0,
    )

    assert decision.selected_index == 1
    report = decision.metadata["root_prior_guided_decision_reports"][0]
    identities = action_identity_dicts_for_actions(actions)
    assert report["root_action_priors"][str(identities[0]["stable_id"])] == 0.10
    assert report["root_action_priors"][str(identities[1]["stable_id"])] == 0.90
    assert report["target"]["selection_rule"] == "highest_mean"
    assert report["allocation_metadata"]["schema_id"] == (
        NATIVE_ROOT_PRIOR_ALLOCATION_METADATA_SCHEMA_ID
    )
    telemetry = decision.metadata["search_decision_telemetry"][0]
    assert telemetry["model_calls"] == 1
    assert telemetry["search_backend"]["native_api"] == (
        NATIVE_ROOT_PRIOR_SEARCH_NATIVE_API
    )


def test_root_prior_guided_controller_rejects_invalid_zero_priors() -> None:
    action_space = ActionSpaceConfig.initial_no_potions()
    snapshot = _battle_snapshot()
    actions = _actions()
    context = build_decision_context(snapshot.raw, actions, action_space)
    controller = RootPriorGuidedSearchController(
        simulations=10,
        scorer=_FakeGuidanceScorer(probabilities=(0.0, 0.0)),
        action_space=action_space,
    )

    with pytest.raises(ValueError, match="no positive eligible priors"):
        controller.select_action(
            _ComparisonAdapter(),
            snapshot,
            actions,
            context,
            step_index=0,
        )


def test_root_prior_guided_comparison_runs_required_arms(tmp_path) -> None:
    cohort_path = tmp_path / "cohort.jsonl"
    with cohort_path.open("w", encoding="utf-8", newline="\n") as stream:
        dump_fixed_cohort_jsonl(_cohort(), stream)

    action_space = ActionSpaceConfig.initial_no_potions()
    scorer = _FakeGuidanceScorer()
    baseline = OracleSearchController(
        simulations=10,
        root_selection_rule="highest_mean",
        action_space=action_space,
        native_source_identity={"integration_commit": "abc"},
    )
    guided = ModelGuidedOracleSearchV2Controller(
        simulations=10,
        scorer=scorer,
        policy_probability_weight=0.10,
        action_space=action_space,
        native_source_identity={"integration_commit": "abc"},
    )
    root_prior = RootPriorGuidedSearchController(
        simulations=10,
        scorer=scorer,
        root_selection_rule="highest_mean",
        action_space=action_space,
        native_source_identity={"integration_commit": "abc"},
    )

    report = run_root_prior_guided_search_comparison_from_cohort_path(
        adapter_factory=_ComparisonAdapter,
        cohort_path=cohort_path,
        controller_arms=(
            (BASELINE_ORACLE_LABEL, "baseline_oracle_search", baseline),
            (POST_SEARCH_MODEL_GUIDED_LABEL, "post_search_v2", guided),
            (ROOT_PRIOR_GUIDED_LABEL, "root_prior_allocation", root_prior),
        ),
        action_space=action_space,
        max_battle_steps=3,
        run_scale="smoke",
        comparison_task_id="T048",
        worker_count=1,
        shard_count=1,
    )

    assert report.evaluation_successful
    assert report.comparison_config["task_id"] == "T048"
    assert not report.source_match_problems
    summaries = root_prior_guided_controller_summaries(report)
    assert summaries[BASELINE_ORACLE_LABEL]["losses"] == 2
    assert summaries[POST_SEARCH_MODEL_GUIDED_LABEL]["authoritative_wins"] == 2
    assert summaries[ROOT_PRIOR_GUIDED_LABEL]["authoritative_wins"] == 2
    assert summaries[ROOT_PRIOR_GUIDED_LABEL]["model_calls"] == 2.0

    budget = root_prior_guided_budget_summary(report)
    assert budget["equal_configured_native_playout_budget_for_required_arms"] is True
    assert budget["observed"][ROOT_PRIOR_GUIDED_LABEL]["root_visits"] == 20.0

    allocation = root_prior_allocation_summary(
        report.arms[2].report,
    )
    assert allocation["decision_count"] == 2
    assert allocation["malformed_metadata_count"] == 0
    assert allocation["allocation_strategy_counts"] == {
        NATIVE_ROOT_PRIOR_ALLOCATION_STRATEGY: 2
    }

    outcome = root_prior_guided_outcome_comparison(report)
    assert outcome["status_vs_baseline"] == "improved"
    assert outcome["status_vs_post_search_model_guided"] == "tied"

    text = format_root_prior_guided_search_comparison_report(report)
    assert "Root-prior guided search comparison" in text
    assert "source starts matched: yes" in text
    assert "assist_hp50: 1" in text
    assert "not normal-information" in text
    assert "no controller-promotion claim" in text
    assert "root-prior vs baseline: improved" in text

    buffer = StringIO()
    dump_root_prior_guided_search_comparison_jsonl(report, buffer)
    assert '"schema_id": "root-prior-guided-search-comparison-v1"' in (
        buffer.getvalue()
    )
    assert '"label": "root_prior_guided_oracle_search"' in buffer.getvalue()

    loaded = load_root_prior_guided_search_comparison_jsonl(StringIO(buffer.getvalue()))
    assert loaded.evaluation_successful
    assert loaded.arms[2].label == ROOT_PRIOR_GUIDED_LABEL
    assert loaded.arms[2].report.authoritative_wins == 2


def test_root_prior_guided_comparison_validates_required_contract(tmp_path) -> None:
    cohort_path = tmp_path / "cohort.jsonl"
    with cohort_path.open("w", encoding="utf-8", newline="\n") as stream:
        dump_fixed_cohort_jsonl(_cohort(), stream)

    action_space = ActionSpaceConfig.initial_no_potions()
    scorer = _FakeGuidanceScorer()
    baseline = OracleSearchController(
        simulations=10,
        root_selection_rule="highest_mean",
        action_space=action_space,
    )
    guided = ModelGuidedOracleSearchV2Controller(
        simulations=10,
        scorer=scorer,
        policy_probability_weight=0.10,
        action_space=action_space,
    )
    mismatched_root_prior = RootPriorGuidedSearchController(
        simulations=5,
        scorer=_FakeGuidanceScorer(
            checkpoint_provenance=_checkpoint("checkpoint-other")
        ),
        root_selection_rule="highest_mean",
        action_space=action_space,
    )

    report = run_root_prior_guided_search_comparison_from_cohort_path(
        adapter_factory=_ComparisonAdapter,
        cohort_path=cohort_path,
        controller_arms=(
            (BASELINE_ORACLE_LABEL, "baseline_oracle_search", baseline),
            (POST_SEARCH_MODEL_GUIDED_LABEL, "post_search_v2", guided),
            (ROOT_PRIOR_GUIDED_LABEL, "root_prior_allocation", mismatched_root_prior),
        ),
        action_space=action_space,
        max_battle_steps=3,
        run_scale="smoke",
        worker_count=1,
        shard_count=1,
    )

    assert not report.evaluation_successful
    assert "required search arms do not share equal native root budget" in (
        report.problems
    )
    assert "checkpoint provenance mismatch between guided arms" in report.problems

    missing = build_root_prior_guided_search_comparison_report(
        arms=((BASELINE_ORACLE_LABEL, "baseline", report.arms[0].report),),
        comparison_config={"run_scale": "smoke"},
    )
    assert "missing required arm 'model_guided_oracle_search_v2'" in missing.problems
    assert "missing required arm 'root_prior_guided_oracle_search'" in (
        missing.problems
    )
