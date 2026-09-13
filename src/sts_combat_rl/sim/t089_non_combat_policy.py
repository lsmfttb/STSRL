"""Reusable, fail-closed boundaries for the T089 Non-Combat workflow.

T089 deliberately reuses the T065 wire schemas and ranker implementation.  This
module only binds the new task's identities, seed schedule, current-native
revalidation, held-out gate, conditional fresh-run gate, and retention/report
surfaces.  It does not start a simulator job; callers must explicitly inject a
simulator adapter/factory for scientific execution.
"""

from __future__ import annotations

import json
import math
import random
import statistics
from collections import defaultdict
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from sts_combat_rl.sim.action_space import ActionSpaceConfig
from sts_combat_rl.sim.non_combat_learning import (
    T065_MANDATORY_FAMILIES,
    T065_SPLITS,
    T065CounterfactualTarget,
    T065ModelRun,
    T065SourceState,
    T065TargetTable,
    canonical_source_selection_key,
    continuation_seeds_for_split,
    evaluate_model_on_split,
    file_sha256,
    generate_counterfactual_targets,
    load_non_combat_checkpoint,
    replay_source_state,
    run_complete_run_arm,
    screen_family,
    select_validation_checkpoint,
    train_frozen_model_seeds,
)
from sts_combat_rl.sim.non_combat_model_input import (
    NON_COMBAT_ACTION_FEATURE_SIZE,
    NON_COMBAT_MODEL_INPUT_SCHEMA_ID,
    NON_COMBAT_MODEL_INPUT_SCHEMA_VERSION,
    NON_COMBAT_STATE_FEATURE_SIZE,
    encode_non_combat_decision_context,
    non_combat_model_input_schema,
)
from sts_combat_rl.sim.non_combat_policy import ExpertNonCombatDriver
from sts_combat_rl.sim.online_controller import PolicyController
from sts_combat_rl.sim.policy_contract import DecisionContext, PolicyDecision

T089_TASK_ID = "T089"
T089_APPROVED_SPEC_COMMIT = "afffcdda5cebfe47a2cfa1624911d916191bab76"
T089_PUBLICATION_BASE = "6b739ee3f9b4bbd113aac141c755401d2a865252"
T089_T088_IMPLEMENTATION_HEAD = "a25f9a27deeaeb98d13a188538c7ac6f09a6f1a3"
T089_NATIVE_REPOSITORY = "lsmfttb/sts_lightspeed"
T089_NATIVE_REF = "refs/heads/stsrl/main"
T089_NATIVE_COMMIT = "20a6c2b3a9cea817c988178b814f083ff889853f"
T089_SELECTION_SHA256 = (
    "94857d0e310f34cdd2780920ec81f9dc60e179c94244b9e231952a43a5f4e8b8"
)
T089_PUBLIC_MODEL_SCHEMA = NON_COMBAT_MODEL_INPUT_SCHEMA_ID
T089_PUBLIC_MODEL_SCHEMA_VERSION = NON_COMBAT_MODEL_INPUT_SCHEMA_VERSION
T089_MODEL_SEEDS = (893001, 893002)
T089_TRAIN_CONTINUATION_SEEDS = (892001, 892002)
T089_VALIDATION_CONTINUATION_SEEDS = (892101, 892102)
T089_HELDOUT_CONTINUATION_SEEDS = (892201, 892202, 892203, 892204)
T089_HELDOUT_EXPERT_COMPARATOR_SEED = 895001
T089_HELDOUT_BOOTSTRAP_SEED = 89089
T089_FRESH_SEED_RANGE = (891001, 891256)
T089_FRESH_DRIVER_SEED = 894002
T089_FRESH_BOOTSTRAP_SEED = 891089
T089_BOOTSTRAP_REPLICATES = 10_000
T089_MAX_STEPS = 500
T089_BATTLE_SIMULATIONS = 400
T089_SUPPORTED_FAMILIES = T065_MANDATORY_FAMILIES
T089_CONTINUATION_SEED_MAP: Mapping[str, tuple[int, ...]] = {
    "train": T089_TRAIN_CONTINUATION_SEEDS,
    "validation": T089_VALIDATION_CONTINUATION_SEEDS,
    "heldout": T089_HELDOUT_CONTINUATION_SEEDS,
}
T089_TERMINAL_CLASSIFICATIONS = (
    "NON_COMBAT_POLICY_IMPROVEMENT_ESTABLISHED",
    "NON_COMBAT_POLICY_HARM_CONFIRMED",
    "NON_COMBAT_POLICY_IMPROVEMENT_NOT_ESTABLISHED",
    "NON_COMBAT_EVAL_SUPPORT_INSUFFICIENT",
    "INCOMPLETE",
)
T089_STAGES = (
    "INPUT_ELIGIBILITY",
    "CURRENT_NATIVE_REVALIDATION",
    "TARGET",
    "TRAIN",
    "HELDOUT_GATE",
    "FRESH_EVAL",
    "FINALIZE",
)


class T089ContractError(ValueError):
    """A T089 contract mismatch that must fail closed."""


class T089Incomplete(T089ContractError):
    """Evidence is missing, stale, conflicting, or malformed."""


@dataclass(frozen=True)
class T089WorkflowState:
    """Small control-plane state; scientific payloads stay in stage artifacts."""

    stage: str = "INPUT_ELIGIBILITY"
    terminal_classification: str | None = None
    fresh_evaluation_authorized: bool = False

    def __post_init__(self) -> None:
        if self.stage not in T089_STAGES:
            raise T089ContractError(f"unknown T089 stage {self.stage!r}")
        if self.terminal_classification not in (None, *T089_TERMINAL_CLASSIFICATIONS):
            raise T089ContractError("unknown T089 terminal classification")


def advance_t089_workflow(
    state: T089WorkflowState,
    *,
    passed: bool,
    terminal_classification: str | None = None,
) -> T089WorkflowState:
    """Advance one stage without allowing fresh evaluation after a failed gate."""

    if state.terminal_classification is not None:
        raise T089ContractError("T089 workflow is already terminal")
    if (
        terminal_classification is not None
        and terminal_classification not in T089_TERMINAL_CLASSIFICATIONS
    ):
        raise T089ContractError("unknown T089 terminal classification")
    if not passed:
        classification = terminal_classification or "INCOMPLETE"
        if state.stage == "HELDOUT_GATE" and classification == "INCOMPLETE":
            classification = "NON_COMBAT_POLICY_IMPROVEMENT_NOT_ESTABLISHED"
        if state.stage == "FRESH_EVAL" and classification == "INCOMPLETE":
            classification = "INCOMPLETE"
        return T089WorkflowState(
            stage=state.stage,
            terminal_classification=classification,
            fresh_evaluation_authorized=False,
        )
    index = T089_STAGES.index(state.stage)
    if index + 1 >= len(T089_STAGES):
        return T089WorkflowState(
            stage=state.stage,
            terminal_classification=terminal_classification or "INCOMPLETE",
            fresh_evaluation_authorized=False,
        )
    next_stage = T089_STAGES[index + 1]
    authorized = state.stage == "HELDOUT_GATE" and next_stage == "FRESH_EVAL"
    return T089WorkflowState(
        stage=next_stage,
        terminal_classification=terminal_classification,
        fresh_evaluation_authorized=authorized,
    )


@dataclass(frozen=True)
class T089ExperimentConfig:
    """The complete immutable T089 scientific configuration."""

    task_id: str = T089_TASK_ID
    approved_spec_commit: str = T089_APPROVED_SPEC_COMMIT
    publication_base: str = T089_PUBLICATION_BASE
    native_repository: str = T089_NATIVE_REPOSITORY
    native_ref: str = T089_NATIVE_REF
    native_commit: str = T089_NATIVE_COMMIT
    model_seeds: tuple[int, ...] = T089_MODEL_SEEDS
    battle_simulations: int = T089_BATTLE_SIMULATIONS
    max_steps: int = T089_MAX_STEPS
    heldout_expert_comparator_seed: int = T089_HELDOUT_EXPERT_COMPARATOR_SEED
    fresh_driver_seed: int = T089_FRESH_DRIVER_SEED

    def __post_init__(self) -> None:
        expected = (
            T089_TASK_ID,
            T089_APPROVED_SPEC_COMMIT,
            T089_PUBLICATION_BASE,
            T089_NATIVE_REPOSITORY,
            T089_NATIVE_REF,
            T089_NATIVE_COMMIT,
            T089_MODEL_SEEDS,
            T089_BATTLE_SIMULATIONS,
            T089_MAX_STEPS,
            T089_HELDOUT_EXPERT_COMPARATOR_SEED,
            T089_FRESH_DRIVER_SEED,
        )
        actual = (
            self.task_id,
            self.approved_spec_commit,
            self.publication_base,
            self.native_repository,
            self.native_ref,
            self.native_commit,
            tuple(self.model_seeds),
            self.battle_simulations,
            self.max_steps,
            self.heldout_expert_comparator_seed,
            self.fresh_driver_seed,
        )
        if actual != expected:
            raise T089ContractError(
                f"T089 scientific configuration is frozen; received {actual!r}, "
                f"expected {expected!r}"
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "approved_spec_commit": self.approved_spec_commit,
            "publication_base": self.publication_base,
            "native_identity": {
                "repository": self.native_repository,
                "ref": self.native_ref,
                "commit": self.native_commit,
            },
            "model_seeds": list(self.model_seeds),
            "continuation_seeds": {
                split: list(values)
                for split, values in T089_CONTINUATION_SEED_MAP.items()
            },
            "heldout_expert_comparator_seed": self.heldout_expert_comparator_seed,
            "fresh": {
                "simulator_seed_range": list(T089_FRESH_SEED_RANGE),
                "driver_seed": self.fresh_driver_seed,
                "bootstrap_seed": T089_FRESH_BOOTSTRAP_SEED,
            },
            "heldout_bootstrap": {
                "seed": T089_HELDOUT_BOOTSTRAP_SEED,
                "replicates": T089_BOOTSTRAP_REPLICATES,
            },
            "battle": t089_battle_provenance(),
            "max_steps": self.max_steps,
            "screen_families": list(T089_SUPPORTED_FAMILIES),
        }


def t089_battle_provenance() -> dict[str, Any]:
    """Return the exact frozen Search-v2@400 identity without probing native."""

    return {
        "implementation": "BattleScumSearcher2",
        "controller": "unguided_search_v2",
        "version": "search-v2",
        "information_regime": "full_simulator_state_oracle_like",
        "native_identity": {
            "repository": T089_NATIVE_REPOSITORY,
            "ref": T089_NATIVE_REF,
            "commit": T089_NATIVE_COMMIT,
        },
        "search_budget": {
            "simulations": T089_BATTLE_SIMULATIONS,
            "budget_unit": "native_tree_search_playouts",
        },
        "root_selection": "highest_mean",
        "policy_prior_callback": None,
        "learned_leaf_value_callback": None,
        "rollout_continuation": "playoutRandom",
        "terminal_utility": "evaluateEndState",
        "action_space": ActionSpaceConfig.initial_no_potions().to_dict(),
        "model_calls": 0,
    }


def _t089_native_identity_matches(value: Mapping[str, Any]) -> bool:
    canonical = {
        "repository": T089_NATIVE_REPOSITORY,
        "ref": T089_NATIVE_REF,
        "commit": T089_NATIVE_COMMIT,
    }
    if dict(value) == canonical:
        return True
    return (
        value.get("integration_commit") == T089_NATIVE_COMMIT
        and value.get("integration_ref") == T089_NATIVE_REF
        and (
            value.get("integration_repository_url")
            in {
                "https://github.com/lsmfttb/sts_lightspeed",
                "https://github.com/lsmfttb/sts_lightspeed.git",
            }
        )
    )


def validate_t089_battle_provenance(value: Mapping[str, Any]) -> None:
    """Reject any Search budget, callback, or native identity drift."""

    expected = t089_battle_provenance()
    if dict(value) != expected:
        raise T089ContractError("T089 Battle controller provenance is not exact")


def t089_model_input_contract() -> dict[str, Any]:
    """Return the unchanged T065 public model-input contract."""

    schema = dict(non_combat_model_input_schema())
    if schema.get("schema_id") != T089_PUBLIC_MODEL_SCHEMA:
        raise T089ContractError("T065 model-input schema id changed")
    if schema.get("schema_version") != T089_PUBLIC_MODEL_SCHEMA_VERSION:
        raise T089ContractError("T065 model-input schema version changed")
    if schema.get("state_feature_size") != NON_COMBAT_STATE_FEATURE_SIZE:
        raise T089ContractError("T065 state feature width changed")
    if schema.get("action_feature_size") != NON_COMBAT_ACTION_FEATURE_SIZE:
        raise T089ContractError("T065 action feature width changed")
    return schema


def validate_t089_public_model_input(
    *,
    state_features: Sequence[float],
    action_features: Sequence[float],
    context: Mapping[str, Any] | None = None,
) -> None:
    """Validate public-only dimensions and recursively reject hidden inputs."""

    if len(state_features) != NON_COMBAT_STATE_FEATURE_SIZE:
        raise T089ContractError("T089 state input must have width 4737")
    if len(action_features) != NON_COMBAT_ACTION_FEATURE_SIZE:
        raise T089ContractError("T089 action input must have width 92")
    if any(
        isinstance(value, bool) or not math.isfinite(float(value))
        for value in state_features
    ):
        raise T089ContractError("T089 state input contains a non-finite value")
    if any(
        isinstance(value, bool) or not math.isfinite(float(value))
        for value in action_features
    ):
        raise T089ContractError("T089 action input contains a non-finite value")
    if context is not None:
        forbidden = (
            "hidden_rng",
            "rng_state",
            "random_state",
            "draw_order",
            "unrevealed",
            "future_encounter",
            "second_boss",
            "checkpoint",
            "native_object",
            "native_payload",
            "simulator_state",
            "expert_score",
            "expert_action",
            "target_value",
            "search_internal",
        )
        encoded = json.dumps(context, sort_keys=True, default=str).lower()
        if any(token in encoded for token in forbidden):
            raise T089Incomplete("T089 deployable model input contains hidden data")


def t089_continuation_seeds(split: str) -> tuple[int, ...]:
    """Return the exact T089 continuation seed tuple for one split."""

    return continuation_seeds_for_split(split, seed_map=T089_CONTINUATION_SEED_MAP)


def t089_fresh_simulator_seeds() -> tuple[int, ...]:
    return tuple(range(T089_FRESH_SEED_RANGE[0], T089_FRESH_SEED_RANGE[1] + 1))


def _canonical_json(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _state_identity_payload(state: T065SourceState) -> dict[str, Any]:
    return {
        "selected_state_index": state.selected_state_index,
        "family": state.family,
        "split": state.split,
        "simulator_seed": state.simulator_seed,
        "public_state_identity": state.public_state_identity,
        "state_features": list(state.state_features),
        "public_context_features": list(state.public_context_features),
        "ordered_legal_action_identities": [
            dict(item) for item in state.legal_action_identities
        ],
        "eligible_action_indices": list(state.eligible_action_indices),
    }


def validate_t089_selected_cohort(states: Sequence[T065SourceState]) -> dict[str, Any]:
    """Validate exact T075 320-state ordering, quotas, and split ownership."""

    ordered = tuple(states)
    if len(ordered) != 320 or tuple(
        row.selected_state_index for row in ordered
    ) != tuple(range(320)):
        raise T089Incomplete("T089 selected cohort is not exactly 320 ordered states")
    counts: dict[str, dict[str, int]] = {
        family: {split: 0 for split in T065_SPLITS}
        for family in T089_SUPPORTED_FAMILIES
    }
    replay_keys: set[bytes] = set()
    for index, state in enumerate(ordered):
        expected_family = T089_SUPPORTED_FAMILIES[index // 80]
        offset = index % 80
        expected_split = (
            "train" if offset < 48 else "validation" if offset < 64 else "heldout"
        )
        if state.family != expected_family or state.split != expected_split:
            raise T089Incomplete("T075 cohort family/split ownership changed")
        expected_digest, expected_payload = canonical_source_selection_key(state)
        if (
            state.selection_digest != expected_digest
            or state.selection_canonical_json != expected_payload.decode("utf-8")
        ):
            raise T089Incomplete(
                "T075 cohort selection identity does not match the frozen candidate"
            )
        replay_key = _canonical_json(
            {
                "family": state.family,
                "public_state_identity": state.public_state_identity,
                "ordered_legal_action_identities": [
                    dict(item) for item in state.legal_action_identities
                ],
            }
        )
        if replay_key in replay_keys:
            raise T089Incomplete("T075 cohort contains a replay-equivalent duplicate")
        replay_keys.add(replay_key)
        counts[state.family][state.split] += 1
    expected_counts = {
        family: {"train": 48, "validation": 16, "heldout": 16}
        for family in T089_SUPPORTED_FAMILIES
    }
    if counts != expected_counts:
        raise T089Incomplete("T075 cohort quotas are not exact")
    return {
        "schema_id": "t089-selected-cohort-validation-v1",
        "schema_version": 1,
        "task_id": T089_TASK_ID,
        "selection_sha256": T089_SELECTION_SHA256,
        "selected_state_count": 320,
        "unique_replay_key_count": len(replay_keys),
        "counts_by_family_split": counts,
        "replacement_performed": False,
        "reselection_performed": False,
    }


def _revalidation_diff(
    expected: T065SourceState, observed: Mapping[str, Any]
) -> list[str]:
    differences: list[str] = []
    for key, expected_value in _state_identity_payload(expected).items():
        actual = observed.get(key)
        if actual != expected_value:
            differences.append(key)
    return differences


def validate_t089_revalidation_rows(
    rows: Iterable[Mapping[str, Any]],
    states: Sequence[T065SourceState],
    *,
    native_identity: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Validate a complete current-native revalidation report without replacement."""

    expected_states = tuple(states)
    validate_t089_selected_cohort(expected_states)
    by_index: dict[int, Mapping[str, Any]] = {}
    for row in rows:
        index = row.get("selected_state_index")
        if isinstance(index, bool) or not isinstance(index, int) or index in by_index:
            raise T089Incomplete(
                "current-native revalidation has duplicate/invalid state index"
            )
        by_index[index] = row
    if tuple(sorted(by_index)) != tuple(range(320)):
        raise T089Incomplete(
            "current-native revalidation does not cover all 320 states"
        )
    failures = []
    for state in expected_states:
        row = by_index[state.selected_state_index]
        differences = _revalidation_diff(state, row)
        if differences:
            failures.append(
                {
                    "selected_state_index": state.selected_state_index,
                    "differences": differences,
                }
            )
    identity = dict(native_identity or {})
    if not _t089_native_identity_matches(identity):
        raise T089Incomplete(
            "current-native revalidation identity is not T089 canonical"
        )
    if failures:
        raise T089Incomplete(f"current-native revalidation mismatch: {failures[0]}")
    return {
        "schema_id": "t089-current-native-revalidation-v1",
        "schema_version": 1,
        "task_id": T089_TASK_ID,
        "native_identity": identity,
        "state_count": 320,
        "mismatch_count": 0,
        "replacement_performed": False,
        "dropped_state_count": 0,
        "split_movement_count": 0,
        "passed": True,
    }


def revalidate_t089_cohort(
    adapter_factory: Callable[[], Any],
    states: Sequence[T065SourceState],
    *,
    native_identity: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Replay every retained state and compare public/legal identity exactly."""

    expected = tuple(states)
    validate_t089_selected_cohort(expected)
    rows: list[dict[str, Any]] = []
    for state in expected:
        try:
            _snapshot, _actions, context, _checkpoint = replay_source_state(
                adapter_factory(), state
            )
            encoded = encode_non_combat_decision_context(context)
            observed = {
                **_state_identity_payload(state),
                "state_features": list(encoded.state_features),
                "public_context_features": list(encoded.public_context_features),
                "eligible_action_indices": list(encoded.eligible_action_indices),
                "ordered_legal_action_identities": [
                    dict(item) for item in context.legal_action_identities
                ],
            }
        except (OSError, RuntimeError, TypeError, ValueError) as exc:
            observed = {
                "selected_state_index": state.selected_state_index,
                "error": str(exc),
            }
        rows.append(observed)
    return validate_t089_revalidation_rows(
        rows, expected, native_identity=native_identity
    )


def generate_t089_targets(
    adapter_factory: Callable[[], Any],
    states: Sequence[T065SourceState],
    *,
    source_artifact_identity: Mapping[str, Any],
    simulator_identity: Mapping[str, Any],
    battle_controller_factory: Callable[[], Any] | None = None,
) -> T065TargetTable:
    """Generate fresh all-action labels using the parameterized T065 writer."""

    validate_t089_selected_cohort(states)
    if source_artifact_identity.get("sha256") != T089_SELECTION_SHA256:
        raise T089Incomplete("T089 source cohort artifact SHA-256 is not T075")
    if not _t089_native_identity_matches(simulator_identity):
        raise T089Incomplete("T089 target native identity is not canonical")
    if battle_controller_factory is None:
        raise T089Incomplete(
            "T089 target generation requires an explicit Search-v2@400 factory"
        )
    table = generate_counterfactual_targets(
        adapter_factory,
        states,
        max_steps=T089_MAX_STEPS,
        source_artifact_identity=source_artifact_identity,
        simulator_identity=simulator_identity,
        continuation_seed_map=T089_CONTINUATION_SEED_MAP,
        expert_comparator_seed=T089_HELDOUT_EXPERT_COMPARATOR_SEED,
        battle_controller_factory=battle_controller_factory,
        task_id=T089_TASK_ID,
        approved_spec_commit=T089_APPROVED_SPEC_COMMIT,
        frozen_config=T089ExperimentConfig().to_dict(),
    )
    return replace(
        table,
        execution_evidence={
            **dict(table.execution_evidence),
            "battle_controller_provenance": t089_battle_provenance(),
            "target_identity": "q_floor=mean(max(0,terminal_floor-source_floor))",
            "all_eligible_actions": True,
            "continuation_seed_map": {
                split: list(seeds)
                for split, seeds in T089_CONTINUATION_SEED_MAP.items()
            },
            "heldout_expert_comparator_seed": T089_HELDOUT_EXPERT_COMPARATOR_SEED,
        },
    )


def train_t089_model_seeds(
    *,
    states: Sequence[T065SourceState],
    targets: Sequence[T065CounterfactualTarget],
    source_artifact_identity: Mapping[str, Any],
    target_artifact_identity: Mapping[str, Any],
    checkpoint_directory: Path | None = None,
) -> tuple[T065ModelRun, ...]:
    """Train exactly the T065 ranker with the T089 seed pair."""

    if source_artifact_identity.get("sha256") != T089_SELECTION_SHA256:
        raise T089Incomplete("T089 source cohort artifact SHA-256 is not T075")
    return train_frozen_model_seeds(
        states=states,
        targets=targets,
        source_artifact_identity=source_artifact_identity,
        target_artifact_identity=target_artifact_identity,
        checkpoint_directory=checkpoint_directory,
        model_seeds=T089_MODEL_SEEDS,
        model_class="T065ActionConditionedRanker",
        source_driver_seed=T089_HELDOUT_EXPERT_COMPARATOR_SEED,
        battle_controller_name="unguided_search_v2",
    )


def validate_t089_target_table(table: T065TargetTable) -> dict[str, Any]:
    """Validate the inherited target schema plus every T089 identity binding."""

    table.validate_complete()
    if table.task_id != T089_TASK_ID:
        raise T089Incomplete("target table task identity is not T089")
    if table.approved_spec_commit != T089_APPROVED_SPEC_COMMIT:
        raise T089Incomplete("target table approved specification is not T089")
    if table.source_artifact_identity.get("sha256") != T089_SELECTION_SHA256:
        raise T089Incomplete("target table source cohort SHA-256 is not T075")
    if not _t089_native_identity_matches(table.simulator_identity):
        raise T089Incomplete("target table simulator identity is not T089 canonical")
    if dict(table.frozen_config or {}) != T089ExperimentConfig().to_dict():
        raise T089Incomplete("target table frozen configuration is not T089")
    expected_map = {
        split: tuple(values) for split, values in T089_CONTINUATION_SEED_MAP.items()
    }
    observed_map = {
        split: tuple(values)
        for split, values in (table.continuation_seed_map or {}).items()
    }
    if observed_map != expected_map:
        raise T089Incomplete("target table continuation seed map is not exact")
    if (
        table.expert_action_provenance.get("seed")
        != T089_HELDOUT_EXPERT_COMPARATOR_SEED
    ):
        raise T089Incomplete("target table held-out comparator seed is not 895001")
    evidence = table.execution_evidence
    if evidence.get("battle_controller_provenance") != t089_battle_provenance():
        raise T089Incomplete("target table Search-v2@400 provenance is missing")
    return {
        "schema_id": "t089-target-table-validation-v1",
        "schema_version": 1,
        "task_id": T089_TASK_ID,
        "state_count": len(table.states),
        "target_row_count": len(table.targets),
        "all_eligible_actions": True,
        "continuation_seed_map": {
            split: list(values) for split, values in expected_map.items()
        },
        "passed": True,
    }


def select_t089_validation_checkpoint(runs: Sequence[T065ModelRun]) -> T065ModelRun:
    return select_validation_checkpoint(
        runs,
        expected_model_seeds=T089_MODEL_SEEDS,
        expected_model_class="T065ActionConditionedRanker",
        expected_source_driver_seed=T089_HELDOUT_EXPERT_COMPARATOR_SEED,
        expected_battle_controller_name="unguided_search_v2",
    )


def load_t089_checkpoint(path: Path) -> T065ModelRun:
    return load_non_combat_checkpoint(
        path,
        expected_model_seeds=T089_MODEL_SEEDS,
        expected_model_class="T065ActionConditionedRanker",
        expected_source_driver_seed=T089_HELDOUT_EXPERT_COMPARATOR_SEED,
        expected_battle_controller_name="unguided_search_v2",
    )


class T089LearnedNonCombatPolicy:
    """Public four-family ranker with explicit expert fallback elsewhere."""

    name = "learned_non_combat_t089_v1"
    version = 1
    supported_families = frozenset(T089_SUPPORTED_FAMILIES)

    def __init__(self, model_run: T065ModelRun) -> None:
        self.model_run = model_run
        self.fallback = ExpertNonCombatDriver(seed=T089_FRESH_DRIVER_SEED)
        self.decision_events: list[dict[str, Any]] = []

    @property
    def provenance_config(self) -> Mapping[str, Any]:
        return {
            "seed": T089_FRESH_DRIVER_SEED,
            "version": self.version,
            "supported_screen_families": list(T089_SUPPORTED_FAMILIES),
            "fallback_policy": self.fallback.name,
            "fallback_provenance": {
                "name": self.fallback.name,
                "version": self.fallback.version,
                "seed": T089_FRESH_DRIVER_SEED,
            },
            "checkpoint_schema_id": "t065-non-combat-ranker-checkpoint-v1",
            "checkpoint_artifact_id": self.model_run.checkpoint_artifact_id,
            "model_seed": self.model_run.model_seed,
            "model_input_schema": t089_model_input_contract(),
            "information_regime": "normal_public_policy",
            "expert_action_or_score_is_model_input": False,
            "battle_controller": t089_battle_provenance(),
        }

    def reset_for_run(self, simulator_seed: int | None) -> None:
        self.fallback.reset_for_run(simulator_seed)
        self.decision_events.clear()

    def select_action(self, context: DecisionContext) -> PolicyDecision:
        family = screen_family(context.screen_state)
        if family not in self.supported_families:
            decision = self.fallback.select_action(context)
            self.decision_events.append(
                {
                    "screen_family": family,
                    "status": "unsupported_fallback",
                    "action_index": decision.legal_action_index,
                }
            )
            return PolicyDecision(
                legal_action_index=decision.legal_action_index,
                score=decision.score,
                reason=f"{self.name}:expert_fallback:{family}",
            )
        encoded = encode_non_combat_decision_context(context)
        scores = {
            index: self.model_run.score(
                encoded.state_features, encoded.action_features[index]
            )
            for index in encoded.eligible_action_indices
        }
        if not scores:
            raise T089Incomplete(f"{family}: supported learned action set is empty")
        selected = min(scores, key=lambda index: (-scores[index], index))
        self.decision_events.append(
            {
                "screen_family": family,
                "status": "learned_success",
                "action_index": selected,
                "score": scores[selected],
            }
        )
        return PolicyDecision(
            legal_action_index=selected,
            score=scores[selected],
            reason=f"{self.name}:q_floor",
        )


def build_t089_learned_non_combat_controller(
    model_run: T065ModelRun,
) -> PolicyController:
    return PolicyController(T089LearnedNonCombatPolicy(model_run))


def run_t089_complete_run_arm(
    adapter_factory: Callable[[], Any],
    *,
    arm: str,
    model_run: T065ModelRun | None = None,
    seeds: Iterable[int] | None = None,
    battle_controller_factory: Callable[[], Any] | None = None,
    simulator_identity: Mapping[str, Any] | None = None,
) -> Any:
    """Run one explicitly-authorized T089 fresh arm through shared execution."""

    if arm not in {"baseline", "candidate"}:
        raise T089ContractError("T089 fresh arm must be baseline or candidate")
    if battle_controller_factory is None:
        raise T089Incomplete(
            "T089 fresh evaluation requires an explicit Search-v2@400 factory"
        )
    if arm == "candidate" and model_run is None:
        raise T089Incomplete("T089 candidate arm requires the selected checkpoint")
    report = run_complete_run_arm(
        adapter_factory,
        arm="expert" if arm == "baseline" else "learned",
        seeds=seeds,
        model_run=model_run,
        driver_seed=T089_FRESH_DRIVER_SEED,
        max_steps=T089_MAX_STEPS,
        battle_controller_factory=battle_controller_factory,
        learned_policy_factory=lambda run: T089LearnedNonCombatPolicy(run),
        allowed_seed_range=T089_FRESH_SEED_RANGE,
        allowed_driver_seed=T089_FRESH_DRIVER_SEED,
        simulator_identity=simulator_identity
        or {
            "repository": T089_NATIVE_REPOSITORY,
            "ref": T089_NATIVE_REF,
            "commit": T089_NATIVE_COMMIT,
        },
    )
    events_by_seed: dict[int, list[Mapping[str, Any]]] = defaultdict(list)
    for event in report.decision_events:
        seed = event.get("simulator_seed")
        if isinstance(seed, int) and not isinstance(seed, bool):
            events_by_seed[seed].append(event)
    rows: list[Mapping[str, Any]] = []
    for raw in report.rows:
        row = dict(raw)
        seed = row.get("simulator_seed")
        events = events_by_seed.get(seed, [])
        row["arm"] = arm
        row["controller_failure"] = bool(row.get("controller_error"))
        row["act2_plus"] = bool(row.get("act2_entry"))
        row["learned_decisions_by_family"] = {
            family: sum(
                event.get("screen_family") == family
                and event.get("status") == "learned_success"
                for event in events
            )
            for family in T089_SUPPORTED_FAMILIES
        }
        row["learned_decision_count"] = sum(
            event.get("status") == "learned_success" for event in events
        )
        row["fallback_decisions_by_family"] = {
            family: sum(
                event.get("screen_family") == family
                and event.get("status") == "unsupported_fallback"
                for event in events
            )
            for family in T089_SUPPORTED_FAMILIES
        }
        row["supported_inference_failures"] = sum(
            event.get("status") == "learned_failure" for event in events
        )
        rows.append(row)
    return replace(report, arm=arm, rows=tuple(rows))


def _bootstrap_interval(
    rows: Sequence[Mapping[str, Any]],
    *,
    delta_key: str,
    families: Sequence[str],
    per_family: int,
    seed: int,
    replicates: int,
) -> tuple[float, float]:
    by_family: dict[str, tuple[float, ...]] = {}
    for family in families:
        values = tuple(
            float(row[delta_key]) for row in rows if row.get("family") == family
        )
        if len(values) != per_family or any(not math.isfinite(v) for v in values):
            raise T089Incomplete(f"bootstrap family {family} is incomplete")
        by_family[family] = values
    rng = random.Random(seed)
    means: list[float] = []
    for _ in range(replicates):
        sample = [
            rng.choice(by_family[family])
            for family in families
            for _ in range(per_family)
        ]
        means.append(statistics.fmean(sample))
    means.sort()
    low_index = int(0.025 * (replicates - 1))
    high_index = int(0.975 * (replicates - 1))
    return means[low_index], means[high_index]


def build_t089_heldout_gate(
    model_runs: Sequence[T065ModelRun],
    table: T065TargetTable,
    *,
    expert_action_indices: Mapping[int, int] | None = None,
    violations: Sequence[str] = (),
) -> dict[str, Any]:
    """Apply the frozen held-out local policy gate before fresh evaluation."""

    validate_t089_target_table(table)
    selected = select_t089_validation_checkpoint(model_runs)
    results_by_seed = {
        str(run.model_seed): evaluate_model_on_split(
            run, table, split="heldout", expert_action_indices=expert_action_indices
        )
        for run in model_runs
    }
    selected_rows = tuple(results_by_seed[str(selected.model_seed)])
    rows = [
        {
            "selected_state_index": result.selected_state_index,
            "family": result.family,
            "delta": result.delta,
        }
        for result in selected_rows
    ]
    lower, upper = _bootstrap_interval(
        rows,
        delta_key="delta",
        families=T089_SUPPORTED_FAMILIES,
        per_family=16,
        seed=T089_HELDOUT_BOOTSTRAP_SEED,
        replicates=T089_BOOTSTRAP_REPLICATES,
    )
    deltas = [float(result.delta) for result in selected_rows]
    family_means = {
        family: statistics.fmean(
            result.delta for result in selected_rows if result.family == family
        )
        for family in T089_SUPPORTED_FAMILIES
    }
    non_selected = next(
        run for run in model_runs if run.model_seed != selected.model_seed
    )
    non_selected_mean = statistics.fmean(
        result.delta for result in results_by_seed[str(non_selected.model_seed)]
    )
    problems = [str(item) for item in violations]
    conditions = (
        (statistics.fmean(deltas) > 0, "aggregate mean delta is not positive"),
        (statistics.median(deltas) >= 0, "median delta is negative"),
        (
            sum(value >= 0 for value in family_means.values()) >= 3,
            "fewer than three family means are non-negative",
        ),
        (lower > 0, "held-out bootstrap lower bound is not positive"),
        (
            non_selected_mean >= 0,
            "non-selected model seed has a negative aggregate delta",
        ),
        (not problems, "identity/schema/restore/legal-action/fallback violation"),
    )
    for passed, problem in conditions:
        if not passed and problem not in problems:
            problems.append(problem)
    return {
        "schema_id": "t089-heldout-gate-report-v1",
        "schema_version": 1,
        "task_id": T089_TASK_ID,
        "selected_model_seed": selected.model_seed,
        "selected_validation_mae": selected.validation_mae,
        "model_seeds": list(T089_MODEL_SEEDS),
        "aggregate_mean_delta": statistics.fmean(deltas),
        "median_delta": statistics.median(deltas),
        "family_mean_deltas": family_means,
        "bootstrap": {
            "seed": T089_HELDOUT_BOOTSTRAP_SEED,
            "replicates": T089_BOOTSTRAP_REPLICATES,
            "lower_95": lower,
            "upper_95": upper,
            "sampling_unit": "source_state",
        },
        "non_selected_model_mean_delta": non_selected_mean,
        "model_results": {
            seed: [result.to_dict() for result in results]
            for seed, results in results_by_seed.items()
        },
        "violations": list(violations),
        "passed": not problems,
        "problems": problems,
        "fresh_evaluation_authorized": not problems,
    }


def validate_t089_fresh_support(
    candidate_rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Apply the exact natural occupancy support gate without adding runs."""

    if len(candidate_rows) != 256:
        raise T089Incomplete("fresh candidate arm must contain exactly 256 rows")
    required = {family: 0 for family in T089_SUPPORTED_FAMILIES}
    learned_total = 0
    inference_failures: list[Any] = []
    for row in candidate_rows:
        count = row.get("learned_decision_count", 0)
        if isinstance(count, bool) or not isinstance(count, int) or count < 0:
            raise T089Incomplete("fresh learned decision count is invalid")
        learned_total += count
        family_counts = row.get("learned_decisions_by_family", {})
        if not isinstance(family_counts, Mapping):
            raise T089Incomplete("fresh family coverage is missing")
        for family in T089_SUPPORTED_FAMILIES:
            value = family_counts.get(family, 0)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise T089Incomplete("fresh family coverage count is invalid")
            required[family] += value
        if (
            sum(family_counts.get(family, 0) for family in T089_SUPPORTED_FAMILIES)
            != count
        ):
            raise T089Incomplete("fresh family coverage does not match learned count")
        raw_failures = row.get("supported_inference_failures", 0)
        if (
            isinstance(raw_failures, bool)
            or not isinstance(raw_failures, int)
            or raw_failures < 0
        ):
            raise T089Incomplete("fresh supported inference failure count is invalid")
        if raw_failures:
            inference_failures.append(row.get("simulator_seed"))
    passed = (
        learned_total >= 128
        and required["MAP_SCREEN"] >= 32
        and required["REWARDS"] >= 32
        and required["REST_ROOM"] >= 1
        and required["TREASURE_ROOM"] >= 1
        and not inference_failures
    )
    return {
        "schema_id": "t089-fresh-support-report-v1",
        "schema_version": 1,
        "task_id": T089_TASK_ID,
        "run_count": len(candidate_rows),
        "learned_decision_count": learned_total,
        "learned_decisions_by_family": required,
        "supported_inference_failure_seeds": inference_failures,
        "passed": passed,
        "classification": None if passed else "NON_COMBAT_EVAL_SUPPORT_INSUFFICIENT",
    }


def build_t089_fresh_report(
    baseline_rows: Sequence[Mapping[str, Any]],
    candidate_rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Build the paired 256-seed fresh-run report and terminal classification."""

    expected_seeds = t089_fresh_simulator_seeds()
    baseline_by_seed = {row.get("simulator_seed"): row for row in baseline_rows}
    candidate_by_seed = {row.get("simulator_seed"): row for row in candidate_rows}
    if (
        tuple(sorted(baseline_by_seed)) != expected_seeds
        or tuple(sorted(candidate_by_seed)) != expected_seeds
    ):
        raise T089Incomplete("fresh arms do not contain exact simulator seed range")
    pairs: list[dict[str, Any]] = []
    for seed in expected_seeds:
        baseline = baseline_by_seed[seed]
        candidate = candidate_by_seed[seed]
        for row, label in ((baseline, "baseline"), (candidate, "candidate")):
            if (
                not bool(row.get("terminal"))
                or bool(row.get("truncated"))
                or bool(row.get("controller_failure"))
            ):
                raise T089Incomplete(f"fresh {label} row {seed} is invalid")
            floor = row.get("terminal_floor")
            if (
                isinstance(floor, bool)
                or not isinstance(floor, (int, float))
                or not math.isfinite(float(floor))
            ):
                raise T089Incomplete(
                    f"fresh {label} row {seed} terminal floor is invalid"
                )
        pairs.append(
            {
                "simulator_seed": seed,
                "family": "ALL",
                "baseline_terminal_floor": float(baseline["terminal_floor"]),
                "candidate_terminal_floor": float(candidate["terminal_floor"]),
                "delta": float(candidate["terminal_floor"])
                - float(baseline["terminal_floor"]),
                "candidate_act2_plus": bool(candidate.get("act2_plus", False)),
                "baseline_act2_plus": bool(baseline.get("act2_plus", False)),
            }
        )
    support = validate_t089_fresh_support(candidate_rows)
    low, high = _bootstrap_interval(
        pairs,
        delta_key="delta",
        families=("ALL",),
        per_family=256,
        seed=T089_FRESH_BOOTSTRAP_SEED,
        replicates=T089_BOOTSTRAP_REPLICATES,
    )
    deltas = [row["delta"] for row in pairs]
    invalid_candidate = sum(
        bool(row.get("truncated")) or bool(row.get("controller_failure"))
        for row in candidate_rows
    )
    invalid_baseline = sum(
        bool(row.get("truncated")) or bool(row.get("controller_failure"))
        for row in baseline_rows
    )
    candidate_act2 = sum(row["candidate_act2_plus"] for row in pairs)
    baseline_act2 = sum(row["baseline_act2_plus"] for row in pairs)
    if not support["passed"]:
        classification = "NON_COMBAT_EVAL_SUPPORT_INSUFFICIENT"
    elif (
        low > 0
        and invalid_candidate <= invalid_baseline
        and candidate_act2 >= baseline_act2
    ):
        classification = "NON_COMBAT_POLICY_IMPROVEMENT_ESTABLISHED"
    elif high < 0:
        classification = "NON_COMBAT_POLICY_HARM_CONFIRMED"
    else:
        classification = "NON_COMBAT_POLICY_IMPROVEMENT_NOT_ESTABLISHED"
    return {
        "schema_id": "t089-fresh-run-report-v1",
        "schema_version": 1,
        "task_id": T089_TASK_ID,
        "paired_rows": pairs,
        "mean_terminal_floor_delta": statistics.fmean(deltas),
        "median_terminal_floor_delta": statistics.median(deltas),
        "bootstrap": {
            "seed": T089_FRESH_BOOTSTRAP_SEED,
            "replicates": T089_BOOTSTRAP_REPLICATES,
            "lower_95": low,
            "upper_95": high,
            "sampling_unit": "simulator_seed",
        },
        "support": support,
        "candidate_invalid_or_truncated": invalid_candidate,
        "baseline_invalid_or_truncated": invalid_baseline,
        "candidate_act2_plus": candidate_act2,
        "baseline_act2_plus": baseline_act2,
        "classification": classification,
        "battle_provenance": t089_battle_provenance(),
    }


def t089_terminal_report(
    classification: str,
    *,
    heldout: Mapping[str, Any] | None = None,
    fresh: Mapping[str, Any] | None = None,
    reason: str | None = None,
) -> dict[str, Any]:
    if classification not in T089_TERMINAL_CLASSIFICATIONS:
        raise T089ContractError("unknown T089 terminal classification")
    if classification == "NON_COMBAT_POLICY_IMPROVEMENT_ESTABLISHED" and fresh is None:
        raise T089ContractError("established improvement requires fresh evidence")
    return {
        "schema_id": "t089-terminal-report-v1",
        "schema_version": 1,
        "task_id": T089_TASK_ID,
        "approved_spec_commit": T089_APPROVED_SPEC_COMMIT,
        "native_identity": {
            "repository": T089_NATIVE_REPOSITORY,
            "ref": T089_NATIVE_REF,
            "commit": T089_NATIVE_COMMIT,
        },
        "classification": classification,
        "heldout_gate": dict(heldout or {}),
        "fresh_report": dict(fresh or {}),
        "claim_boundary": "simulator-side public Non-Combat update with Battle frozen to Search v2 @400; not deployment, Heart, or normal-information optimality",
        "teacher_ambiguity": "q_floor labels condition on one restored simulator future; no T034 hidden-future averaging",
        "reason": reason,
        "downstream_decision": "separate Battle-student update task required before any alternating co-improvement",
    }


def t089_artifact_identity(
    path: Path, *, role: str, repository_root: Path
) -> dict[str, Any]:
    path = path.resolve()
    root = repository_root.resolve()
    try:
        relative = path.relative_to(root).as_posix()
    except ValueError as exc:
        raise T089ContractError("retained artifact is outside repository root") from exc
    if not relative.startswith("artifacts/"):
        raise T089ContractError("retained artifact must live under artifacts/")
    return {
        "role": role,
        "path": relative,
        "sha256": file_sha256(path),
        "size_bytes": path.stat().st_size,
    }


def build_t089_retention_manifest(
    artifacts: Mapping[str, Mapping[str, Any]],
    *,
    regeneration_commands: Sequence[str],
    retention_reason: str,
) -> dict[str, Any]:
    """Build a strict, non-recursive manifest for the required T089 roles."""

    required = {
        "input_eligibility",
        "current_native_revalidation",
        "target_table",
        "training_normalizers",
        "training_batch_plans",
        "checkpoint_893001",
        "checkpoint_893002",
        "validation_selection",
        "heldout_gate",
        "fresh_run",
        "terminal_report",
    }
    missing = sorted(required - set(artifacts))
    if missing:
        raise T089Incomplete(f"T089 retention manifest missing roles: {missing}")
    if not regeneration_commands or not retention_reason:
        raise T089Incomplete(
            "T089 retention requires regeneration and retention metadata"
        )
    normalized = []
    for role in sorted(artifacts):
        item = dict(artifacts[role])
        if (
            item.get("role") != role
            or not isinstance(item.get("path"), str)
            or not item["path"].startswith("artifacts/")
        ):
            raise T089Incomplete(f"T089 artifact identity is invalid for {role}")
        if not isinstance(item.get("sha256"), str) or len(item["sha256"]) != 64:
            raise T089Incomplete(f"T089 artifact hash is invalid for {role}")
        if (
            isinstance(item.get("size_bytes"), bool)
            or not isinstance(item.get("size_bytes"), int)
            or item["size_bytes"] < 0
        ):
            raise T089Incomplete(f"T089 artifact size is invalid for {role}")
        normalized.append(item)
    return {
        "schema_id": "t089-retention-manifest-v1",
        "schema_version": 1,
        "task_id": T089_TASK_ID,
        "approved_spec_commit": T089_APPROVED_SPEC_COMMIT,
        "native_identity": {
            "repository": T089_NATIVE_REPOSITORY,
            "ref": T089_NATIVE_REF,
            "commit": T089_NATIVE_COMMIT,
        },
        "artifacts": normalized,
        "regeneration_commands": list(regeneration_commands),
        "retention_reason": retention_reason,
        "deletion_condition": "delete only after T089 downstream research no longer requires the evidence",
        "recursive_discovery_used": False,
    }
