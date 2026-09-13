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
import time
from collections import defaultdict
from collections.abc import Callable, Iterable, Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from sts_combat_rl.sim.action_space import ActionSpaceConfig
from sts_combat_rl.sim.non_combat_learning import (
    T065_MANDATORY_FAMILIES,
    T065_MAX_WORKERS,
    T065_SPLITS,
    T065_STAGE6_REPORT_SCHEMA_ID,
    T065_STAGE6_SHARD_COUNT,
    T065CompleteRunArmReport,
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
    NON_COMBAT_SNAPSHOT_FEATURE_SIZE,
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
T089_WORKER_COUNT = T065_MAX_WORKERS
T089_SHARD_COUNT = T065_STAGE6_SHARD_COUNT
T089_REVALIDATION_STATE_COUNT = 320
T089_REVALIDATION_STATES_PER_SHARD = T089_REVALIDATION_STATE_COUNT // T089_SHARD_COUNT
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


def _t089_revalidation_shard_ranges() -> tuple[tuple[int, int], ...]:
    if T089_REVALIDATION_STATE_COUNT % T089_SHARD_COUNT:
        raise T089ContractError("T089 revalidation cohort cannot form exact shards")
    return tuple(
        (
            index * T089_REVALIDATION_STATES_PER_SHARD,
            (index + 1) * T089_REVALIDATION_STATES_PER_SHARD - 1,
        )
        for index in range(T089_SHARD_COUNT)
    )


def _validate_t089_revalidation_execution_evidence(
    value: Mapping[str, Any],
) -> dict[str, Any]:
    if (
        value.get("schema_id") != "t089-current-native-revalidation-execution-v1"
        or value.get("schema_version") != 1
        or value.get("worker_count") != T089_WORKER_COUNT
        or value.get("shard_count") != T089_SHARD_COUNT
        or value.get("requested_state_count") != T089_REVALIDATION_STATE_COUNT
        or value.get("completed_state_count") != T089_REVALIDATION_STATE_COUNT
    ):
        raise T089Incomplete("T089 revalidation execution topology is invalid")
    _require_finite_nonnegative(
        value.get("wall_clock_seconds"), "T089 revalidation total wall clock"
    )
    specs = value.get("shard_specs")
    if not isinstance(specs, Sequence) or isinstance(specs, (str, bytes)):
        raise T089Incomplete("T089 revalidation shard evidence is missing")
    expected_ranges = _t089_revalidation_shard_ranges()
    if len(specs) != len(expected_ranges):
        raise T089Incomplete("T089 revalidation shard count is invalid")
    for expected_index, (expected_start, expected_end) in enumerate(expected_ranges):
        spec = specs[expected_index]
        if not isinstance(spec, Mapping):
            raise T089Incomplete("T089 revalidation shard evidence is invalid")
        integer_fields = (
            "shard_index",
            "selected_state_start",
            "selected_state_end",
            "selected_state_count",
            "requested_state_count",
            "completed_state_count",
            "problem_count",
        )
        for key in integer_fields:
            field = spec.get(key)
            if isinstance(field, bool) or not isinstance(field, int):
                raise T089Incomplete(f"T089 revalidation shard field {key} is invalid")
        if (
            spec.get("shard_index") != expected_index
            or spec.get("selected_state_start") != expected_start
            or spec.get("selected_state_end") != expected_end
            or spec.get("selected_state_count") != expected_end - expected_start + 1
            or spec.get("requested_state_count") != T089_REVALIDATION_STATES_PER_SHARD
            or spec.get("completed_state_count") != T089_REVALIDATION_STATES_PER_SHARD
            or spec.get("problem_count") != 0
        ):
            raise T089Incomplete("T089 revalidation shard topology is invalid")
        expected_indices = list(range(expected_start, expected_end + 1))
        if spec.get("requested_state_indices") != expected_indices:
            raise T089Incomplete("T089 revalidation requested indices are invalid")
        if spec.get("completed_state_indices") != expected_indices:
            raise T089Incomplete("T089 revalidation completed indices are invalid")
        _require_finite_nonnegative(
            spec.get("wall_clock_seconds"),
            f"T089 revalidation shard {expected_index} wall clock",
        )
        problems = spec.get("problems")
        if not isinstance(problems, Sequence) or isinstance(problems, (str, bytes)):
            raise T089Incomplete("T089 revalidation shard problems are invalid")
        if problems or len(problems) != spec["problem_count"]:
            raise T089Incomplete("T089 revalidation shard contains problems")
    return dict(value)


def validate_t089_revalidation_rows(
    rows: Iterable[Mapping[str, Any]],
    states: Sequence[T065SourceState],
    *,
    native_identity: Mapping[str, Any] | None = None,
    execution_evidence: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Validate a complete current-native revalidation report without replacement."""

    expected_states = tuple(states)
    validate_t089_selected_cohort(expected_states)
    if execution_evidence is None:
        raise T089Incomplete("T089 revalidation execution evidence is missing")
    validated_execution = _validate_t089_revalidation_execution_evidence(
        execution_evidence
    )
    by_index: dict[int, Mapping[str, Any]] = {}
    for row in rows:
        index = row.get("selected_state_index")
        if isinstance(index, bool) or not isinstance(index, int) or index in by_index:
            raise T089Incomplete(
                "current-native revalidation has duplicate/invalid state index"
            )
        by_index[index] = row
    if tuple(sorted(by_index)) != tuple(range(T089_REVALIDATION_STATE_COUNT)):
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
        "state_count": T089_REVALIDATION_STATE_COUNT,
        "mismatch_count": 0,
        "replacement_performed": False,
        "dropped_state_count": 0,
        "split_movement_count": 0,
        "wall_clock_seconds": validated_execution["wall_clock_seconds"],
        "execution_evidence": validated_execution,
        "rows": [
            dict(by_index[index]) for index in range(T089_REVALIDATION_STATE_COUNT)
        ],
        "passed": True,
    }


def revalidate_t089_cohort(
    adapter_factory: Callable[[], Any],
    states: Sequence[T065SourceState],
    *,
    native_identity: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Replay every retained state in sixteen explicit native shards."""

    expected = tuple(states)
    validate_t089_selected_cohort(expected)
    if len(expected) != T089_REVALIDATION_STATE_COUNT:
        raise T089Incomplete("T089 revalidation cohort is not exactly 320 states")

    def run_shard(
        shard_index: int, start: int, end: int
    ) -> tuple[int, list[dict[str, Any]], dict[str, Any]]:
        started = time.perf_counter()
        requested_indices = list(range(start, end + 1))
        shard_rows: list[dict[str, Any]] = []
        problems: list[str] = []
        completed_indices: list[int] = []
        for state in expected[start : end + 1]:
            try:
                _snapshot, _actions, context, _checkpoint = replay_source_state(
                    adapter_factory(), state
                )
                encoded = encode_non_combat_decision_context(context)
                observed = {
                    **_state_identity_payload(state),
                    "state_features": list(encoded.state_features),
                    "public_context_features": list(
                        encoded.state_features[NON_COMBAT_SNAPSHOT_FEATURE_SIZE:]
                    ),
                    "eligible_action_indices": list(encoded.eligible_action_indices),
                    "ordered_legal_action_identities": [
                        dict(item) for item in context.legal_action_identities
                    ],
                }
                completed_indices.append(state.selected_state_index)
            except (OSError, RuntimeError, TypeError, ValueError) as exc:
                problems.append(f"state {state.selected_state_index}: {exc}")
                observed = {
                    "selected_state_index": state.selected_state_index,
                    "error": str(exc),
                }
            shard_rows.append(observed)
        return (
            shard_index,
            shard_rows,
            {
                "shard_index": shard_index,
                "selected_state_start": start,
                "selected_state_end": end,
                "selected_state_count": len(requested_indices),
                "requested_state_indices": requested_indices,
                "requested_state_count": len(requested_indices),
                "completed_state_indices": completed_indices,
                "completed_state_count": len(completed_indices),
                "wall_clock_seconds": time.perf_counter() - started,
                "problem_count": len(problems),
                "problems": problems,
            },
        )

    started = time.perf_counter()
    shard_results: dict[int, tuple[list[dict[str, Any]], dict[str, Any]]] = {}
    with ThreadPoolExecutor(max_workers=T089_WORKER_COUNT) as executor:
        futures = {
            executor.submit(run_shard, index, start, end): index
            for index, (start, end) in enumerate(_t089_revalidation_shard_ranges())
        }
        for future in as_completed(futures):
            index, shard_rows, shard_spec = future.result()
            shard_results[index] = (shard_rows, shard_spec)
    rows = [row for index in range(T089_SHARD_COUNT) for row in shard_results[index][0]]
    execution_evidence = {
        "schema_id": "t089-current-native-revalidation-execution-v1",
        "schema_version": 1,
        "worker_count": T089_WORKER_COUNT,
        "shard_count": T089_SHARD_COUNT,
        "requested_state_count": T089_REVALIDATION_STATE_COUNT,
        "completed_state_count": sum(
            spec["completed_state_count"] for _, spec in shard_results.values()
        ),
        "wall_clock_seconds": time.perf_counter() - started,
        "shard_specs": [shard_results[index][1] for index in range(T089_SHARD_COUNT)],
    }
    return validate_t089_revalidation_rows(
        rows,
        expected,
        native_identity=native_identity,
        execution_evidence=execution_evidence,
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
    """Run one explicitly-authorized T089 fresh arm through 16 real shards.

    The shared T065 executor owns one shard's complete-run semantics.  T089
    owns this outer orchestration so its exact fresh cohort is visibly split
    into sixteen concurrent, sixteen-seed shards without changing T065's
    defaults or schemas.
    """

    if arm not in {"baseline", "candidate"}:
        raise T089ContractError("T089 fresh arm must be baseline or candidate")
    if battle_controller_factory is None:
        raise T089Incomplete(
            "T089 fresh evaluation requires an explicit Search-v2@400 factory"
        )
    if arm == "candidate" and model_run is None:
        raise T089Incomplete("T089 candidate arm requires the selected checkpoint")
    requested = t089_fresh_simulator_seeds() if seeds is None else tuple(seeds)
    if requested != t089_fresh_simulator_seeds():
        raise T089Incomplete("T089 fresh execution requires the exact 256-seed cohort")
    native_identity = dict(
        simulator_identity
        or {
            "repository": T089_NATIVE_REPOSITORY,
            "ref": T089_NATIVE_REF,
            "commit": T089_NATIVE_COMMIT,
        }
    )
    shard_ranges = _t089_fresh_shard_ranges()

    def run_shard(
        shard_index: int, seed_start: int, seed_end: int
    ) -> T065CompleteRunArmReport:
        return run_complete_run_arm(
            adapter_factory,
            arm="expert" if arm == "baseline" else "learned",
            seeds=range(seed_start, seed_end + 1),
            model_run=model_run,
            driver_seed=T089_FRESH_DRIVER_SEED,
            max_steps=T089_MAX_STEPS,
            worker_count=T089_WORKER_COUNT,
            shard_count=T089_SHARD_COUNT,
            battle_controller_factory=battle_controller_factory,
            learned_policy_factory=lambda run: T089LearnedNonCombatPolicy(run),
            allowed_seed_range=T089_FRESH_SEED_RANGE,
            allowed_driver_seed=T089_FRESH_DRIVER_SEED,
            simulator_identity=native_identity,
        )

    started = time.perf_counter()
    shard_reports: dict[int, T065CompleteRunArmReport] = {}
    with ThreadPoolExecutor(max_workers=T089_WORKER_COUNT) as executor:
        futures = {
            executor.submit(run_shard, index, seed_start, seed_end): index
            for index, (seed_start, seed_end) in enumerate(shard_ranges)
        }
        for future in as_completed(futures):
            shard_reports[futures[future]] = future.result()

    decorated_reports = [
        _decorate_t089_shard_report(shard_reports[index], arm=arm)
        for index in range(T089_SHARD_COUNT)
    ]
    first = decorated_reports[0]
    for report in decorated_reports[1:]:
        if (
            dict(report.simulator_identity) != dict(first.simulator_identity)
            or dict(report.action_space) != dict(first.action_space)
            or dict(report.controller_provenance) != dict(first.controller_provenance)
            or dict(report.driver_provenance) != dict(first.driver_provenance)
        ):
            raise T089Incomplete("T089 fresh shard provenance is inconsistent")
    shard_specs: list[dict[str, Any]] = []
    for index, ((seed_start, seed_end), report) in enumerate(
        zip(shard_ranges, decorated_reports, strict=True)
    ):
        expected_shard_seeds = tuple(range(seed_start, seed_end + 1))
        if (
            report.requested_seeds != expected_shard_seeds
            or report.worker_count != T089_WORKER_COUNT
            or report.shard_count != T089_SHARD_COUNT
        ):
            raise T089Incomplete("T089 fresh shard report topology is invalid")
        completed_seeds = [
            int(row["simulator_seed"])
            for row in report.rows
            if isinstance(row, Mapping)
            and isinstance(row.get("simulator_seed"), int)
            and not isinstance(row.get("simulator_seed"), bool)
        ]
        cost: dict[str, float] = {}
        for row in report.rows:
            row_cost = row.get("simulator_cost")
            if isinstance(row_cost, Mapping):
                for key, value in row_cost.items():
                    if isinstance(value, (int, float)) and not isinstance(value, bool):
                        cost[key] = cost.get(key, 0.0) + float(value)
        shard_specs.append(
            {
                "arm": arm,
                "shard_index": index,
                "seed_start": seed_start,
                "seed_end": seed_end,
                "seed_count": seed_end - seed_start + 1,
                "worker_count": T089_WORKER_COUNT,
                "requested_seeds": list(report.requested_seeds),
                "requested_seed_count": len(report.requested_seeds),
                "completed_seeds": completed_seeds,
                "completed_seed_count": len(completed_seeds),
                "completed_row_count": len(report.rows),
                "decision_count": len(report.decision_events),
                "wall_clock_seconds": report.wall_clock_seconds,
                "problem_count": len(report.problems),
                "problems": list(report.problems),
                "simulator_cost": cost,
            }
        )
    return T065CompleteRunArmReport(
        arm=arm,
        driver_seed=T089_FRESH_DRIVER_SEED,
        requested_seeds=tuple(
            seed for report in decorated_reports for seed in report.requested_seeds
        ),
        rows=tuple(row for report in decorated_reports for row in report.rows),
        decision_events=tuple(
            event for report in decorated_reports for event in report.decision_events
        ),
        wall_clock_seconds=time.perf_counter() - started,
        worker_count=T089_WORKER_COUNT,
        shard_count=T089_SHARD_COUNT,
        shard_specs=tuple(shard_specs),
        problems=tuple(
            problem for report in decorated_reports for problem in report.problems
        ),
        simulator_identity=dict(first.simulator_identity),
        action_space=dict(first.action_space),
        controller_provenance=dict(first.controller_provenance),
        driver_provenance=dict(first.driver_provenance),
    )


def _t089_fresh_shard_ranges() -> tuple[tuple[int, int], ...]:
    start, end = T089_FRESH_SEED_RANGE
    cohort_size = end - start + 1
    if cohort_size % T089_SHARD_COUNT:
        raise T089ContractError("T089 fresh cohort cannot form exact shards")
    shard_size = cohort_size // T089_SHARD_COUNT
    return tuple(
        (start + index * shard_size, start + (index + 1) * shard_size - 1)
        for index in range(T089_SHARD_COUNT)
    )


def _decorate_t089_shard_report(
    report: T065CompleteRunArmReport, *, arm: str
) -> T065CompleteRunArmReport:
    events_by_seed: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for raw_event in report.decision_events:
        event = dict(raw_event)
        seed = event.get("simulator_seed")
        if isinstance(seed, int) and not isinstance(seed, bool):
            event["decision_ordinal"] = len(events_by_seed[seed])
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
            family: count
            for family in sorted(
                {
                    event.get("screen_family")
                    for event in events
                    if event.get("status") == "unsupported_fallback"
                    and isinstance(event.get("screen_family"), str)
                }
            )
            if (
                count := sum(
                    event.get("screen_family") == family
                    and event.get("status") == "unsupported_fallback"
                    for event in events
                )
            )
        }
        row["supported_inference_failures"] = sum(
            event.get("status") == "learned_failure" for event in events
        )
        rows.append(row)
    return replace(
        report,
        arm=arm,
        rows=tuple(rows),
        decision_events=tuple(
            event for events in events_by_seed.values() for event in events
        ),
    )


def _require_finite_nonnegative(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise T089Incomplete(f"{label} is not numeric")
    result = float(value)
    if not math.isfinite(result) or result < 0:
        raise T089Incomplete(f"{label} is not finite and non-negative")
    return result


def _require_finite_number(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise T089Incomplete(f"{label} is not numeric")
    result = float(value)
    if not math.isfinite(result):
        raise T089Incomplete(f"{label} is not finite")
    return result


def _validate_t089_shard_specs(value: Any, *, arm: str) -> tuple[dict[str, Any], ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise T089Incomplete(f"T089 {arm} shard evidence is missing")
    if len(value) != T089_SHARD_COUNT:
        raise T089Incomplete(
            f"T089 {arm} shard evidence must contain exactly {T089_SHARD_COUNT} shards"
        )
    expected_ranges = _t089_fresh_shard_ranges()
    validated: list[dict[str, Any]] = []
    for expected_index, (expected_start, expected_end) in enumerate(expected_ranges):
        spec = value[expected_index]
        if not isinstance(spec, Mapping):
            raise T089Incomplete(f"T089 {arm} shard evidence is invalid")
        for key in (
            "shard_index",
            "seed_start",
            "seed_end",
            "seed_count",
            "worker_count",
            "requested_seed_count",
            "completed_seed_count",
            "completed_row_count",
            "decision_count",
            "problem_count",
        ):
            item = spec.get(key)
            if isinstance(item, bool) or not isinstance(item, int):
                raise T089Incomplete(f"T089 {arm} shard field {key} is invalid")
        if (
            spec.get("arm") != arm
            or spec["shard_index"] != expected_index
            or spec["seed_start"] != expected_start
            or spec["seed_end"] != expected_end
            or spec["seed_count"] != expected_end - expected_start + 1
            or spec["worker_count"] != T089_WORKER_COUNT
            or spec["requested_seed_count"] != spec["seed_count"]
            or spec["completed_seed_count"] != spec["seed_count"]
            or spec["completed_row_count"] != spec["seed_count"]
            or spec["decision_count"] < 0
            or spec["problem_count"] < 0
        ):
            raise T089Incomplete(f"T089 {arm} shard topology or completion is invalid")
        expected_seeds = list(range(expected_start, expected_end + 1))
        if spec.get("requested_seeds") != expected_seeds:
            raise T089Incomplete(f"T089 {arm} shard requested seeds are invalid")
        if spec.get("completed_seeds") != expected_seeds:
            raise T089Incomplete(f"T089 {arm} shard completed seeds are invalid")
        _require_finite_nonnegative(
            spec.get("wall_clock_seconds"),
            f"T089 {arm} shard {expected_index} wall clock",
        )
        problems = spec.get("problems")
        if not isinstance(problems, Sequence) or isinstance(problems, (str, bytes)):
            raise T089Incomplete(f"T089 {arm} shard problems are invalid")
        if len(problems) != spec["problem_count"]:
            raise T089Incomplete(f"T089 {arm} shard problem count is invalid")
        if problems:
            raise T089Incomplete(f"T089 {arm} shard contains execution problems")
        cost = spec.get("simulator_cost")
        if not isinstance(cost, Mapping) or not cost:
            raise T089Incomplete(f"T089 {arm} shard cost is missing")
        for key, cost_value in cost.items():
            _require_finite_nonnegative(
                cost_value, f"T089 {arm} shard {expected_index} cost {key}"
            )
        validated.append(dict(spec))
    return tuple(validated)


def _validate_t089_search_controller_provenance(
    value: Mapping[str, Any],
    *,
    arm: str,
    simulator_identity: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate the complete routed Search-v2@400 controller provenance."""

    expected_non_combat_name = (
        "expert_non_combat_v1" if arm == "baseline" else "learned_non_combat_t089_v1"
    )
    expected_name = "oracle_search_v1_highest_mean_s400+" + expected_non_combat_name
    if (
        value.get("schema_version") != 1
        or value.get("kind") != "routed_run"
        or value.get("name") != expected_name
    ):
        raise T089Incomplete(f"T089 {arm} controller provenance identity is invalid")
    config = value.get("config")
    if not isinstance(config, Mapping) or config.get("reproducible") is not True:
        raise T089Incomplete(f"T089 {arm} controller reproducibility is invalid")
    battle = config.get("battle")
    non_combat = config.get("non_combat")
    if not isinstance(battle, Mapping) or not isinstance(non_combat, Mapping):
        raise T089Incomplete(f"T089 {arm} routed controller children are missing")
    if (
        battle.get("schema_version") != 1
        or battle.get("kind") != "oracle_battle_search"
        or battle.get("name") != "oracle_search_v1_highest_mean_s400"
    ):
        raise T089Incomplete(f"T089 {arm} Search-v2 controller identity is invalid")
    battle_config = battle.get("config")
    if not isinstance(battle_config, Mapping):
        raise T089Incomplete(f"T089 {arm} Search-v2 controller config is missing")
    if battle_config.get("information_regime") != "full_simulator_state_oracle_like":
        raise T089Incomplete(f"T089 {arm} Battle information regime is invalid")
    if not _t089_native_identity_matches(
        battle_config.get("native_source_identity", {})
        if isinstance(battle_config.get("native_source_identity"), Mapping)
        else {}
    ) or not _t089_native_identity_matches(simulator_identity):
        raise T089Incomplete(f"T089 {arm} Battle native identity is invalid")
    if battle_config.get("search_budget") != {
        "simulations": T089_BATTLE_SIMULATIONS,
        "budget_unit": "native_random_terminal_playouts",
    }:
        raise T089Incomplete(f"T089 {arm} Battle search budget is invalid")
    if battle_config.get("root_selection_rule") != "highest_mean":
        raise T089Incomplete(f"T089 {arm} Battle root selection is invalid")
    if (
        battle_config.get("action_space")
        != ActionSpaceConfig.initial_no_potions().to_dict()
    ):
        raise T089Incomplete(f"T089 {arm} Battle action space is invalid")
    if battle_config.get("include_potions") is not False:
        raise T089Incomplete(f"T089 {arm} Battle potion scope is invalid")
    if battle_config.get("rollout_configuration") != {
        "rollout_policy": "BattleScumSearcher2::playoutRandom",
        "leaf_value": "BattleScumSearcher2::evaluateEndState",
        "model_calls": 0,
    }:
        raise T089Incomplete(f"T089 {arm} Battle rollout provenance is invalid")
    if non_combat.get("name") != expected_non_combat_name:
        raise T089Incomplete(f"T089 {arm} Non-Combat controller identity is invalid")
    non_combat_config = non_combat.get("config")
    if (
        not isinstance(non_combat_config, Mapping)
        or non_combat_config.get("seed") != T089_FRESH_DRIVER_SEED
    ):
        raise T089Incomplete(f"T089 {arm} Non-Combat driver seed is invalid")
    return dict(value)


def _validate_t089_decision_events(
    events: Sequence[Any],
    rows_by_seed: Mapping[int, Mapping[str, Any]],
    *,
    expected_arm: str,
) -> dict[int, tuple[Mapping[str, Any], ...]]:
    """Recompute every learned/fallback counter from explicit event evidence."""

    events_by_seed: dict[int, list[Mapping[str, Any]]] = defaultdict(list)
    seen_event_keys: set[tuple[int, int]] = set()
    seen_event_payloads: set[str] = set()
    allowed_statuses = {
        "learned_success",
        "learned_failure",
        "unsupported_fallback",
    }
    expected_seeds = set(rows_by_seed)
    for raw_event in events:
        if not isinstance(raw_event, Mapping):
            raise T089Incomplete(f"T089 {expected_arm} decision event is invalid")
        event = dict(raw_event)
        seed = event.get("simulator_seed")
        if (
            isinstance(seed, bool)
            or not isinstance(seed, int)
            or seed not in expected_seeds
        ):
            raise T089Incomplete(f"T089 {expected_arm} event seed is invalid")
        family = event.get("screen_family")
        status = event.get("status")
        ordinal = event.get("decision_ordinal")
        if not isinstance(family, str) or not family:
            raise T089Incomplete(f"T089 {expected_arm} event family is invalid")
        if status not in allowed_statuses:
            raise T089Incomplete(f"T089 {expected_arm} event status is invalid")
        if isinstance(ordinal, bool) or not isinstance(ordinal, int) or ordinal < 0:
            raise T089Incomplete(f"T089 {expected_arm} event ordinal is invalid")
        event_key = (seed, ordinal)
        if event_key in seen_event_keys:
            raise T089Incomplete(f"T089 {expected_arm} duplicate event ordinal")
        try:
            payload_key = json.dumps(
                event, sort_keys=True, separators=(",", ":"), allow_nan=False
            )
        except (TypeError, ValueError) as exc:
            raise T089Incomplete(
                f"T089 {expected_arm} event payload is not serializable"
            ) from exc
        if payload_key in seen_event_payloads:
            raise T089Incomplete(f"T089 {expected_arm} duplicate decision event")
        seen_event_keys.add(event_key)
        seen_event_payloads.add(payload_key)
        if status in {"learned_success", "learned_failure"}:
            if family not in T089_SUPPORTED_FAMILIES:
                raise T089Incomplete(
                    f"T089 {expected_arm} supported event family is invalid"
                )
        elif family in T089_SUPPORTED_FAMILIES:
            raise T089Incomplete(
                f"T089 {expected_arm} supported family cannot use fallback"
            )
        if status in {"learned_success", "unsupported_fallback"}:
            action_index = event.get("action_index")
            if (
                isinstance(action_index, bool)
                or not isinstance(action_index, int)
                or action_index < 0
            ):
                raise T089Incomplete(
                    f"T089 {expected_arm} selected action evidence is invalid"
                )
        if status == "learned_success":
            _require_finite_number(event.get("score"), f"T089 {expected_arm} score")
        if status == "learned_failure" and (
            not isinstance(event.get("error"), str) or not event["error"]
        ):
            raise T089Incomplete(f"T089 {expected_arm} learned failure is unreported")
        events_by_seed[seed].append(event)

    for seed, seed_events in events_by_seed.items():
        if [event["decision_ordinal"] for event in seed_events] != list(
            range(len(seed_events))
        ):
            raise T089Incomplete(
                f"T089 {expected_arm} event ordinals are not contiguous"
            )

    for seed, row in rows_by_seed.items():
        seed_events = events_by_seed.get(seed, [])
        learned_count_value = row.get("learned_decision_count")
        failure_count_value = row.get("supported_inference_failures")
        learned_family_value = row.get("learned_decisions_by_family")
        fallback_family_value = row.get("fallback_decisions_by_family")
        if (
            isinstance(learned_count_value, bool)
            or not isinstance(learned_count_value, int)
            or learned_count_value < 0
            or isinstance(failure_count_value, bool)
            or not isinstance(failure_count_value, int)
            or failure_count_value < 0
            or not isinstance(learned_family_value, Mapping)
            or set(learned_family_value) != set(T089_SUPPORTED_FAMILIES)
            or not isinstance(fallback_family_value, Mapping)
        ):
            raise T089Incomplete(f"T089 {expected_arm} row counters are malformed")
        if any(
            isinstance(count, bool) or not isinstance(count, int) or count < 0
            for count in learned_family_value.values()
        ) or any(
            not isinstance(family, str)
            or isinstance(count, bool)
            or not isinstance(count, int)
            or count < 0
            for family, count in fallback_family_value.items()
        ):
            raise T089Incomplete(f"T089 {expected_arm} row family counters are invalid")
        learned_by_family = {
            family: sum(
                event.get("screen_family") == family
                and event.get("status") == "learned_success"
                for event in seed_events
            )
            for family in T089_SUPPORTED_FAMILIES
        }
        fallback_by_family: dict[str, int] = {}
        for event in seed_events:
            if event.get("status") == "unsupported_fallback":
                family = str(event["screen_family"])
                fallback_by_family[family] = fallback_by_family.get(family, 0) + 1
        learned_count = sum(
            event.get("status") == "learned_success" for event in seed_events
        )
        failure_count = sum(
            event.get("status") == "learned_failure" for event in seed_events
        )
        if expected_arm == "baseline" and seed_events:
            raise T089Incomplete("T089 baseline cannot claim learned decisions")
        if learned_count_value != learned_count:
            raise T089Incomplete(
                f"T089 {expected_arm} learned decision count disagrees with events"
            )
        if learned_family_value != learned_by_family:
            raise T089Incomplete(
                f"T089 {expected_arm} learned family counts disagree with events"
            )
        if failure_count_value != failure_count:
            raise T089Incomplete(
                f"T089 {expected_arm} supported failure count disagrees with events"
            )
        if fallback_family_value != fallback_by_family:
            raise T089Incomplete(
                f"T089 {expected_arm} fallback family counts disagree with events"
            )
    return {seed: tuple(seed_events) for seed, seed_events in events_by_seed.items()}


def _validate_t089_fresh_arm_report(
    value: Mapping[str, Any], *, expected_arm: str
) -> tuple[tuple[Mapping[str, Any], ...], dict[str, Any]]:
    """Validate one complete serializable arm before any paired reduction."""

    if not isinstance(value, Mapping):
        raise T089Incomplete(f"T089 {expected_arm} arm is not a serialized report")
    if value.get("schema_id") != T065_STAGE6_REPORT_SCHEMA_ID:
        raise T089Incomplete(f"T089 {expected_arm} arm schema is invalid")
    if value.get("schema_version") != 1 or value.get("arm") != expected_arm:
        raise T089Incomplete(f"T089 {expected_arm} arm identity is invalid")
    if value.get("driver_seed") != T089_FRESH_DRIVER_SEED:
        raise T089Incomplete(f"T089 {expected_arm} arm driver seed is invalid")
    expected_seeds = t089_fresh_simulator_seeds()
    requested = value.get("requested_seeds")
    if (
        not isinstance(requested, Sequence)
        or isinstance(requested, (str, bytes))
        or tuple(requested) != expected_seeds
    ):
        raise T089Incomplete(f"T089 {expected_arm} arm seed manifest is invalid")
    simulator_identity = value.get("simulator_identity")
    if not isinstance(simulator_identity, Mapping) or not _t089_native_identity_matches(
        simulator_identity
    ):
        raise T089Incomplete(f"T089 {expected_arm} arm native identity is invalid")
    action_space = value.get("action_space")
    expected_action_space = ActionSpaceConfig.initial_no_potions().to_dict()
    if action_space != expected_action_space:
        raise T089Incomplete(f"T089 {expected_arm} arm action space is invalid")
    controller_provenance = value.get("controller_provenance")
    if not isinstance(controller_provenance, Mapping):
        raise T089Incomplete(
            f"T089 {expected_arm} arm controller provenance is missing"
        )
    validated_controller = _validate_t089_search_controller_provenance(
        controller_provenance,
        arm=expected_arm,
        simulator_identity=simulator_identity,
    )
    driver_provenance = value.get("driver_provenance")
    if not isinstance(driver_provenance, Mapping):
        raise T089Incomplete(f"T089 {expected_arm} arm driver provenance is missing")
    driver_config = driver_provenance.get("config")
    expected_driver_name = (
        "expert_non_combat_v1"
        if expected_arm == "baseline"
        else "learned_non_combat_t089_v1"
    )
    if (
        driver_provenance.get("name") != expected_driver_name
        or driver_provenance.get("version") != 1
        or not isinstance(driver_config, Mapping)
        or driver_config.get("seed") != T089_FRESH_DRIVER_SEED
    ):
        raise T089Incomplete(f"T089 {expected_arm} arm driver provenance is invalid")
    if (
        isinstance(value.get("worker_count"), bool)
        or value.get("worker_count") != T089_WORKER_COUNT
        or isinstance(value.get("shard_count"), bool)
        or value.get("shard_count") != T089_SHARD_COUNT
    ):
        raise T089Incomplete(f"T089 {expected_arm} worker/shard topology is invalid")
    shard_specs = _validate_t089_shard_specs(value.get("shard_specs"), arm=expected_arm)
    wall_clock = _require_finite_nonnegative(
        value.get("wall_clock_seconds"),
        f"T089 {expected_arm} wall clock",
    )
    problems = value.get("problems")
    if not isinstance(problems, Sequence) or isinstance(problems, (str, bytes)):
        raise T089Incomplete(f"T089 {expected_arm} problem evidence is missing")
    if problems:
        raise T089Incomplete(f"T089 {expected_arm} arm contains execution problems")
    events = value.get("decision_events")
    if not isinstance(events, Sequence) or isinstance(events, (str, bytes)):
        raise T089Incomplete(f"T089 {expected_arm} decision events are missing")
    raw_rows = value.get("rows")
    if not isinstance(raw_rows, Sequence) or isinstance(raw_rows, (str, bytes)):
        raise T089Incomplete(f"T089 {expected_arm} arm rows are missing")
    if len(raw_rows) != len(expected_seeds):
        raise T089Incomplete(f"T089 {expected_arm} arm row count is not 256")
    rows_by_seed: dict[int, Mapping[str, Any]] = {}
    for raw_row in raw_rows:
        if not isinstance(raw_row, Mapping):
            raise T089Incomplete(f"T089 {expected_arm} arm row is not an object")
        seed = raw_row.get("simulator_seed")
        if (
            isinstance(seed, bool)
            or not isinstance(seed, int)
            or seed in rows_by_seed
            or seed not in expected_seeds
        ):
            raise T089Incomplete(
                f"T089 {expected_arm} arm row seed manifest is invalid"
            )
        if raw_row.get("arm") != expected_arm:
            raise T089Incomplete(f"T089 {expected_arm} per-run arm identity is invalid")
        if raw_row.get("terminal") is not True:
            raise T089Incomplete(f"T089 {expected_arm} run is not terminal")
        if (
            raw_row.get("truncated") is not False
            or raw_row.get("controller_failure") is not False
        ):
            raise T089Incomplete(
                f"T089 {expected_arm} run has invalid completion status"
            )
        floor = raw_row.get("terminal_floor")
        if (
            isinstance(floor, bool)
            or not isinstance(floor, (int, float))
            or not math.isfinite(float(floor))
        ):
            raise T089Incomplete(f"T089 {expected_arm} terminal floor is invalid")
        if not isinstance(raw_row.get("terminal_status"), str):
            raise T089Incomplete(f"T089 {expected_arm} terminal status is missing")
        if raw_row.get("controller_provenance") != validated_controller:
            raise T089Incomplete(
                f"T089 {expected_arm} per-run controller provenance is invalid"
            )
        if raw_row.get("action_space") != expected_action_space:
            raise T089Incomplete(f"T089 {expected_arm} per-run action space is invalid")
        steps = raw_row.get("simulator_steps")
        if isinstance(steps, bool) or not isinstance(steps, int) or steps < 0:
            raise T089Incomplete(f"T089 {expected_arm} simulator step count is invalid")
        cost = raw_row.get("simulator_cost")
        if not isinstance(cost, Mapping) or not cost:
            raise T089Incomplete(f"T089 {expected_arm} simulator cost is missing")
        for key, cost_value in cost.items():
            _require_finite_nonnegative(cost_value, f"T089 {expected_arm} cost {key}")
        rows_by_seed[seed] = dict(raw_row)
    if tuple(sorted(rows_by_seed)) != expected_seeds:
        raise T089Incomplete(f"T089 {expected_arm} arm does not cover exact seeds")
    events_by_seed = _validate_t089_decision_events(
        events, rows_by_seed, expected_arm=expected_arm
    )
    expected_event_count = 0
    for spec in shard_specs:
        shard_seeds = set(range(int(spec["seed_start"]), int(spec["seed_end"]) + 1))
        shard_event_count = sum(
            len(seed_events)
            for seed, seed_events in events_by_seed.items()
            if seed in shard_seeds
        )
        if spec["decision_count"] != shard_event_count:
            raise T089Incomplete(
                f"T089 {expected_arm} shard decision count disagrees with events"
            )
        expected_event_count += shard_event_count
        expected_cost: dict[str, float] = {}
        for seed in shard_seeds:
            for key, cost_value in rows_by_seed[seed]["simulator_cost"].items():
                expected_cost[key] = expected_cost.get(key, 0.0) + float(cost_value)
        if dict(spec["simulator_cost"]) != expected_cost:
            raise T089Incomplete(
                f"T089 {expected_arm} shard cost disagrees with completed rows"
            )
    if expected_event_count != len(events):
        raise T089Incomplete(f"T089 {expected_arm} event aggregate is invalid")
    per_run_provenance = {
        str(seed): {
            "simulator_seed": seed,
            "arm": expected_arm,
            "controller_provenance": dict(row["controller_provenance"]),
            "action_space": dict(row["action_space"]),
            "simulator_steps": row["simulator_steps"],
            "simulator_cost": dict(row["simulator_cost"]),
        }
        for seed, row in rows_by_seed.items()
    }
    summary = {
        "arm": expected_arm,
        "driver_seed": T089_FRESH_DRIVER_SEED,
        "requested_seeds": list(expected_seeds),
        "simulator_identity": dict(simulator_identity),
        "action_space": dict(action_space),
        "controller_provenance": validated_controller,
        "driver_provenance": dict(driver_provenance),
        "worker_count": T089_WORKER_COUNT,
        "shard_count": T089_SHARD_COUNT,
        "shard_specs": [dict(spec) for spec in shard_specs],
        "wall_clock_seconds": wall_clock,
        "per_run_provenance": per_run_provenance,
        "per_run_decision_evidence": {
            str(seed): {
                "learned_decision_count": row["learned_decision_count"],
                "learned_decisions_by_family": dict(row["learned_decisions_by_family"]),
                "supported_inference_failures": row["supported_inference_failures"],
                "fallback_decisions_by_family": dict(
                    row["fallback_decisions_by_family"]
                ),
            }
            for seed, row in rows_by_seed.items()
        },
    }
    return tuple(rows_by_seed[seed] for seed in expected_seeds), summary


def _validate_t089_fresh_arm_summary(
    value: Mapping[str, Any], *, expected_arm: str
) -> None:
    """Validate retained provenance after the raw arm rows are reduced."""

    if not isinstance(value, Mapping):
        raise T089Incomplete(f"T089 retained {expected_arm} arm is not an object")
    if (
        value.get("arm") != expected_arm
        or value.get("driver_seed") != T089_FRESH_DRIVER_SEED
    ):
        raise T089Incomplete(f"T089 retained {expected_arm} arm identity is invalid")
    expected_seeds = t089_fresh_simulator_seeds()
    requested = value.get("requested_seeds")
    if (
        not isinstance(requested, Sequence)
        or isinstance(requested, (str, bytes))
        or tuple(requested) != expected_seeds
    ):
        raise T089Incomplete(f"T089 retained {expected_arm} seed manifest is invalid")
    simulator_identity = value.get("simulator_identity")
    if not isinstance(simulator_identity, Mapping) or not _t089_native_identity_matches(
        simulator_identity
    ):
        raise T089Incomplete(f"T089 retained {expected_arm} native identity is invalid")
    if value.get("action_space") != ActionSpaceConfig.initial_no_potions().to_dict():
        raise T089Incomplete(f"T089 retained {expected_arm} action space is invalid")
    controller = value.get("controller_provenance")
    if not isinstance(controller, Mapping):
        raise T089Incomplete(
            f"T089 retained {expected_arm} controller provenance is missing"
        )
    _validate_t089_search_controller_provenance(
        controller, arm=expected_arm, simulator_identity=simulator_identity
    )
    driver = value.get("driver_provenance")
    driver_config = driver.get("config") if isinstance(driver, Mapping) else None
    if (
        not isinstance(driver, Mapping)
        or driver.get("name")
        != (
            "expert_non_combat_v1"
            if expected_arm == "baseline"
            else "learned_non_combat_t089_v1"
        )
        or driver.get("version") != 1
        or not isinstance(driver_config, Mapping)
        or driver_config.get("seed") != T089_FRESH_DRIVER_SEED
    ):
        raise T089Incomplete(
            f"T089 retained {expected_arm} driver provenance is invalid"
        )
    if (
        value.get("worker_count") != T089_WORKER_COUNT
        or value.get("shard_count") != T089_SHARD_COUNT
    ):
        raise T089Incomplete(
            f"T089 retained {expected_arm} worker/shard topology is invalid"
        )
    shard_specs = _validate_t089_shard_specs(value.get("shard_specs"), arm=expected_arm)
    _require_finite_nonnegative(
        value.get("wall_clock_seconds"), f"T089 retained {expected_arm} wall clock"
    )
    per_run = value.get("per_run_provenance")
    if not isinstance(per_run, Mapping) or set(per_run) != {
        str(seed) for seed in expected_seeds
    }:
        raise T089Incomplete(
            f"T089 retained {expected_arm} per-run provenance is incomplete"
        )
    for seed in expected_seeds:
        item = per_run[str(seed)]
        if not isinstance(item, Mapping) or item.get("arm") != expected_arm:
            raise T089Incomplete(
                f"T089 retained {expected_arm} per-run identity is invalid"
            )
        if item.get("simulator_seed") != seed:
            raise T089Incomplete(
                f"T089 retained {expected_arm} per-run seed provenance is invalid"
            )
        if item.get("controller_provenance") != controller or item.get(
            "action_space"
        ) != value.get("action_space"):
            raise T089Incomplete(
                f"T089 retained {expected_arm} per-run provenance is invalid"
            )
        steps = item.get("simulator_steps")
        if isinstance(steps, bool) or not isinstance(steps, int) or steps < 0:
            raise T089Incomplete(
                f"T089 retained {expected_arm} per-run steps are invalid"
            )
        cost = item.get("simulator_cost")
        if not isinstance(cost, Mapping) or not cost:
            raise T089Incomplete(
                f"T089 retained {expected_arm} per-run cost is missing"
            )
        for key, cost_value in cost.items():
            _require_finite_nonnegative(
                cost_value, f"T089 retained {expected_arm} per-run cost {key}"
            )
    decision_evidence = value.get("per_run_decision_evidence")
    if not isinstance(decision_evidence, Mapping) or set(decision_evidence) != {
        str(seed) for seed in expected_seeds
    }:
        raise T089Incomplete(
            f"T089 retained {expected_arm} decision evidence is incomplete"
        )
    zero_fallback = expected_arm == "baseline"
    for seed in expected_seeds:
        evidence = decision_evidence[str(seed)]
        if not isinstance(evidence, Mapping):
            raise T089Incomplete(
                f"T089 retained {expected_arm} decision evidence is invalid"
            )
        learned_by_family = evidence.get("learned_decisions_by_family")
        fallback_by_family = evidence.get("fallback_decisions_by_family")
        learned_count = evidence.get("learned_decision_count")
        failure_count = evidence.get("supported_inference_failures")
        if (
            not isinstance(learned_by_family, Mapping)
            or set(learned_by_family) != set(T089_SUPPORTED_FAMILIES)
            or not isinstance(fallback_by_family, Mapping)
            or (zero_fallback and fallback_by_family)
            or isinstance(learned_count, bool)
            or not isinstance(learned_count, int)
            or learned_count < 0
            or isinstance(failure_count, bool)
            or not isinstance(failure_count, int)
            or failure_count < 0
        ):
            raise T089Incomplete(
                f"T089 retained {expected_arm} decision evidence is malformed"
            )
        if any(
            isinstance(count, bool) or not isinstance(count, int) or count < 0
            for count in learned_by_family.values()
        ) or any(
            not isinstance(family, str)
            or not family
            or isinstance(count, bool)
            or not isinstance(count, int)
            or count < 0
            for family, count in fallback_by_family.items()
        ):
            raise T089Incomplete(
                f"T089 retained {expected_arm} decision evidence counts are invalid"
            )
        if any(family in T089_SUPPORTED_FAMILIES for family in fallback_by_family):
            raise T089Incomplete(
                f"T089 retained {expected_arm} supported family fallback is invalid"
            )
        if expected_arm == "baseline" and (learned_count or failure_count):
            raise T089Incomplete("T089 baseline retained learned evidence is invalid")
        if sum(learned_by_family.values()) != learned_count:
            raise T089Incomplete(
                f"T089 retained {expected_arm} learned evidence total is invalid"
            )
    for spec in shard_specs:
        shard_seeds = range(int(spec["seed_start"]), int(spec["seed_end"]) + 1)
        expected_cost: dict[str, float] = {}
        expected_decisions = 0
        for seed in shard_seeds:
            item = per_run[str(seed)]
            for key, cost_value in item["simulator_cost"].items():
                expected_cost[key] = expected_cost.get(key, 0.0) + float(cost_value)
            evidence = decision_evidence[str(seed)]
            expected_decisions += evidence["learned_decision_count"]
            expected_decisions += evidence["supported_inference_failures"]
            expected_decisions += sum(evidence["fallback_decisions_by_family"].values())
        if dict(spec["simulator_cost"]) != expected_cost:
            raise T089Incomplete(
                f"T089 retained {expected_arm} shard cost aggregate is invalid"
            )
        if spec["decision_count"] != expected_decisions:
            raise T089Incomplete(
                f"T089 retained {expected_arm} shard decision aggregate is invalid"
            )


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
    baseline_arm: Mapping[str, Any],
    candidate_arm: Mapping[str, Any],
) -> dict[str, Any]:
    """Build a paired report only from validated complete-run arm artifacts."""

    baseline_rows, baseline_summary = _validate_t089_fresh_arm_report(
        baseline_arm, expected_arm="baseline"
    )
    candidate_rows, candidate_summary = _validate_t089_fresh_arm_report(
        candidate_arm, expected_arm="candidate"
    )
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
    report = {
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
        "arm_reports": {
            "baseline": baseline_summary,
            "candidate": candidate_summary,
        },
    }
    validate_t089_fresh_report(report)
    return report


def _validate_t089_support_report(value: Mapping[str, Any]) -> None:
    if (
        value.get("schema_id") != "t089-fresh-support-report-v1"
        or value.get("schema_version") != 1
        or value.get("task_id") != T089_TASK_ID
        or value.get("run_count") != 256
    ):
        raise T089Incomplete("T089 fresh support report identity is invalid")
    total = value.get("learned_decision_count")
    if isinstance(total, bool) or not isinstance(total, int) or total < 0:
        raise T089Incomplete("T089 fresh support total is invalid")
    counts = value.get("learned_decisions_by_family")
    if not isinstance(counts, Mapping) or set(counts) != set(T089_SUPPORTED_FAMILIES):
        raise T089Incomplete("T089 fresh support family cells are invalid")
    for family in T089_SUPPORTED_FAMILIES:
        count = counts[family]
        if isinstance(count, bool) or not isinstance(count, int) or count < 0:
            raise T089Incomplete("T089 fresh support family count is invalid")
    failures = value.get("supported_inference_failure_seeds")
    if not isinstance(failures, Sequence) or isinstance(failures, (str, bytes)):
        raise T089Incomplete("T089 fresh support failure cells are invalid")
    if not isinstance(value.get("passed"), bool):
        raise T089Incomplete("T089 fresh support passed flag is invalid")
    expected_classification = (
        None if value["passed"] else "NON_COMBAT_EVAL_SUPPORT_INSUFFICIENT"
    )
    if value.get("classification") != expected_classification:
        raise T089Incomplete("T089 fresh support classification is invalid")


def _recompute_t089_retained_support(
    baseline_summary: Mapping[str, Any], candidate_summary: Mapping[str, Any]
) -> dict[str, Any]:
    """Recompute the support gate from retained per-run evidence only."""

    expected_seeds = t089_fresh_simulator_seeds()
    baseline_evidence = baseline_summary["per_run_decision_evidence"]
    candidate_evidence = candidate_summary["per_run_decision_evidence"]
    baseline_families = {family: 0 for family in T089_SUPPORTED_FAMILIES}
    for seed in expected_seeds:
        evidence = baseline_evidence[str(seed)]
        learned_by_family = evidence["learned_decisions_by_family"]
        if (
            evidence["learned_decision_count"] != 0
            or evidence["supported_inference_failures"] != 0
            or evidence["fallback_decisions_by_family"]
            or any(learned_by_family.values())
        ):
            raise T089Incomplete("T089 baseline retained support evidence is nonzero")
        for family in T089_SUPPORTED_FAMILIES:
            baseline_families[family] += learned_by_family[family]
    if any(baseline_families.values()):
        raise T089Incomplete("T089 baseline retained support totals are nonzero")

    learned_total = 0
    learned_by_family = {family: 0 for family in T089_SUPPORTED_FAMILIES}
    failure_seeds: list[int] = []
    for seed in expected_seeds:
        evidence = candidate_evidence[str(seed)]
        if evidence["supported_inference_failures"]:
            failure_seeds.append(seed)
        if any(
            family in T089_SUPPORTED_FAMILIES
            for family in evidence["fallback_decisions_by_family"]
        ):
            raise T089Incomplete("T089 candidate has supported family fallback")
        learned_total += evidence["learned_decision_count"]
        for family in T089_SUPPORTED_FAMILIES:
            learned_by_family[family] += evidence["learned_decisions_by_family"][family]
    if failure_seeds:
        raise T089Incomplete("T089 candidate has supported inference failures")
    passed = (
        learned_total >= 128
        and learned_by_family["MAP_SCREEN"] >= 32
        and learned_by_family["REWARDS"] >= 32
        and learned_by_family["REST_ROOM"] >= 1
        and learned_by_family["TREASURE_ROOM"] >= 1
        and not failure_seeds
    )
    return {
        "schema_id": "t089-fresh-support-report-v1",
        "schema_version": 1,
        "task_id": T089_TASK_ID,
        "run_count": 256,
        "learned_decision_count": learned_total,
        "learned_decisions_by_family": learned_by_family,
        "supported_inference_failure_seeds": failure_seeds,
        "passed": passed,
        "classification": None if passed else "NON_COMBAT_EVAL_SUPPORT_INSUFFICIENT",
    }


def validate_t089_fresh_report(value: Mapping[str, Any]) -> None:
    """Validate a reduced fresh report before it can enter terminal evidence."""

    if (
        value.get("schema_id") != "t089-fresh-run-report-v1"
        or value.get("schema_version") != 1
        or value.get("task_id") != T089_TASK_ID
    ):
        raise T089Incomplete("T089 fresh report identity is invalid")
    arm_reports = value.get("arm_reports")
    if not isinstance(arm_reports, Mapping) or set(arm_reports) != {
        "baseline",
        "candidate",
    }:
        raise T089Incomplete("T089 fresh arm provenance is missing")
    baseline_summary = arm_reports["baseline"]
    candidate_summary = arm_reports["candidate"]
    _validate_t089_fresh_arm_summary(baseline_summary, expected_arm="baseline")
    _validate_t089_fresh_arm_summary(candidate_summary, expected_arm="candidate")
    if value.get("battle_provenance") != t089_battle_provenance():
        raise T089Incomplete("T089 fresh Battle provenance is invalid")
    expected_seeds = t089_fresh_simulator_seeds()
    pairs = value.get("paired_rows")
    if (
        not isinstance(pairs, Sequence)
        or isinstance(pairs, (str, bytes))
        or len(pairs) != 256
    ):
        raise T089Incomplete("T089 fresh paired rows are incomplete")
    pair_by_seed: dict[int, Mapping[str, Any]] = {}
    for pair in pairs:
        if not isinstance(pair, Mapping):
            raise T089Incomplete("T089 fresh paired row is not an object")
        seed = pair.get("simulator_seed")
        if (
            isinstance(seed, bool)
            or not isinstance(seed, int)
            or seed in pair_by_seed
            or seed not in expected_seeds
        ):
            raise T089Incomplete("T089 fresh paired seed identity is invalid")
        if pair.get("family") != "ALL":
            raise T089Incomplete("T089 fresh paired family is invalid")
        for key in ("baseline_terminal_floor", "candidate_terminal_floor", "delta"):
            if (
                isinstance(pair.get(key), bool)
                or not isinstance(pair.get(key), (int, float))
                or not math.isfinite(float(pair[key]))
            ):
                raise T089Incomplete(f"T089 fresh paired metric {key} is invalid")
        if not isinstance(pair.get("candidate_act2_plus"), bool) or not isinstance(
            pair.get("baseline_act2_plus"), bool
        ):
            raise T089Incomplete("T089 fresh Act-2 cells are invalid")
        expected_delta = float(pair["candidate_terminal_floor"]) - float(
            pair["baseline_terminal_floor"]
        )
        if not math.isclose(float(pair["delta"]), expected_delta):
            raise T089Incomplete("T089 fresh paired delta is inconsistent")
        pair_by_seed[seed] = pair
    if tuple(sorted(pair_by_seed)) != expected_seeds:
        raise T089Incomplete("T089 fresh paired rows do not cover exact seeds")
    deltas = [float(pair_by_seed[seed]["delta"]) for seed in expected_seeds]
    if not math.isclose(
        _require_finite_number(
            value.get("mean_terminal_floor_delta"), "T089 fresh mean delta"
        ),
        statistics.fmean(deltas),
    ):
        raise T089Incomplete("T089 fresh mean delta is inconsistent")
    if not math.isclose(
        _require_finite_number(
            value.get("median_terminal_floor_delta"), "T089 fresh median delta"
        ),
        statistics.median(deltas),
    ):
        raise T089Incomplete("T089 fresh median delta is inconsistent")
    bootstrap = value.get("bootstrap")
    if (
        not isinstance(bootstrap, Mapping)
        or bootstrap.get("seed") != T089_FRESH_BOOTSTRAP_SEED
        or bootstrap.get("replicates") != T089_BOOTSTRAP_REPLICATES
        or bootstrap.get("sampling_unit") != "simulator_seed"
    ):
        raise T089Incomplete("T089 fresh bootstrap identity is invalid")
    low, high = _bootstrap_interval(
        [{"family": "ALL", "delta": delta} for delta in deltas],
        delta_key="delta",
        families=("ALL",),
        per_family=256,
        seed=T089_FRESH_BOOTSTRAP_SEED,
        replicates=T089_BOOTSTRAP_REPLICATES,
    )
    if not math.isclose(
        _require_finite_number(bootstrap.get("lower_95"), "T089 fresh lower CI"),
        low,
    ) or not math.isclose(
        _require_finite_number(bootstrap.get("upper_95"), "T089 fresh upper CI"),
        high,
    ):
        raise T089Incomplete("T089 fresh bootstrap interval is inconsistent")
    support = value.get("support")
    if not isinstance(support, Mapping):
        raise T089Incomplete("T089 fresh support report is missing")
    _validate_t089_support_report(support)
    expected_support = _recompute_t089_retained_support(
        baseline_summary, candidate_summary
    )
    if dict(support) != expected_support:
        raise T089Incomplete("T089 fresh support report is not evidence-derived")
    candidate_invalid = value.get("candidate_invalid_or_truncated")
    baseline_invalid = value.get("baseline_invalid_or_truncated")
    candidate_act2 = value.get("candidate_act2_plus")
    baseline_act2 = value.get("baseline_act2_plus")
    if any(
        isinstance(item, bool) or not isinstance(item, int) or item < 0
        for item in (candidate_invalid, baseline_invalid, candidate_act2, baseline_act2)
    ):
        raise T089Incomplete("T089 fresh summary counts are invalid")
    expected_candidate_act2 = sum(
        bool(pair_by_seed[seed]["candidate_act2_plus"]) for seed in expected_seeds
    )
    expected_baseline_act2 = sum(
        bool(pair_by_seed[seed]["baseline_act2_plus"]) for seed in expected_seeds
    )
    if (
        candidate_act2 != expected_candidate_act2
        or baseline_act2 != expected_baseline_act2
    ):
        raise T089Incomplete("T089 fresh Act-2 counts are inconsistent")
    if candidate_invalid != 0 or baseline_invalid != 0:
        raise T089Incomplete("T089 fresh invalid-run counts are not zero")
    if support["passed"]:
        expected_classification = (
            "NON_COMBAT_POLICY_IMPROVEMENT_ESTABLISHED"
            if low > 0
            and candidate_invalid <= baseline_invalid
            and candidate_act2 >= baseline_act2
            else "NON_COMBAT_POLICY_HARM_CONFIRMED"
            if high < 0
            else "NON_COMBAT_POLICY_IMPROVEMENT_NOT_ESTABLISHED"
        )
    else:
        expected_classification = "NON_COMBAT_EVAL_SUPPORT_INSUFFICIENT"
    if value.get("classification") != expected_classification:
        raise T089Incomplete("T089 fresh terminal classification is inconsistent")


def _validate_t089_heldout_report(value: Mapping[str, Any]) -> None:
    """Validate the serialized held-out gate and recompute its frozen metrics."""

    if (
        value.get("schema_id") != "t089-heldout-gate-report-v1"
        or value.get("schema_version") != 1
        or value.get("task_id") != T089_TASK_ID
        or value.get("model_seeds") != list(T089_MODEL_SEEDS)
    ):
        raise T089Incomplete("T089 held-out report identity is invalid")
    selected_seed = value.get("selected_model_seed")
    if selected_seed not in T089_MODEL_SEEDS:
        raise T089Incomplete("T089 held-out selected model seed is invalid")
    selected_mae = value.get("selected_validation_mae")
    if (
        isinstance(selected_mae, bool)
        or not isinstance(selected_mae, (int, float))
        or not math.isfinite(float(selected_mae))
    ):
        raise T089Incomplete("T089 held-out selected validation MAE is invalid")
    results = value.get("model_results")
    if not isinstance(results, Mapping) or set(results) != {
        str(seed) for seed in T089_MODEL_SEEDS
    }:
        raise T089Incomplete("T089 held-out model result cells are incomplete")
    selected_rows = results[str(selected_seed)]
    non_selected_seed = (
        T089_MODEL_SEEDS[0]
        if selected_seed == T089_MODEL_SEEDS[1]
        else T089_MODEL_SEEDS[1]
    )
    non_selected_rows = results[str(non_selected_seed)]
    if (
        not isinstance(selected_rows, Sequence)
        or isinstance(selected_rows, (str, bytes))
        or len(selected_rows) != 64
    ):
        raise T089Incomplete("T089 held-out selected rows are incomplete")
    if (
        not isinstance(non_selected_rows, Sequence)
        or isinstance(non_selected_rows, (str, bytes))
        or len(non_selected_rows) != 64
    ):
        raise T089Incomplete("T089 held-out non-selected rows are incomplete")
    selected_metrics: list[dict[str, Any]] = []
    family_counts = {family: 0 for family in T089_SUPPORTED_FAMILIES}
    for row in selected_rows:
        if not isinstance(row, Mapping) or row.get("family") not in family_counts:
            raise T089Incomplete("T089 held-out selected row identity is invalid")
        delta = row.get("delta")
        if (
            isinstance(delta, bool)
            or not isinstance(delta, (int, float))
            or not math.isfinite(float(delta))
        ):
            raise T089Incomplete("T089 held-out delta is invalid")
        family_counts[row["family"]] += 1
        selected_metrics.append({"family": row["family"], "delta": float(delta)})
    if family_counts != {family: 16 for family in T089_SUPPORTED_FAMILIES}:
        raise T089Incomplete("T089 held-out family cells are invalid")
    non_selected_counts = {family: 0 for family in T089_SUPPORTED_FAMILIES}
    for row in non_selected_rows:
        if not isinstance(row, Mapping) or row.get("family") not in family_counts:
            raise T089Incomplete("T089 held-out non-selected row identity is invalid")
        if (
            isinstance(row.get("delta"), bool)
            or not isinstance(row.get("delta"), (int, float))
            or not math.isfinite(float(row["delta"]))
        ):
            raise T089Incomplete("T089 held-out non-selected delta is invalid")
        non_selected_counts[row["family"]] += 1
    if non_selected_counts != {family: 16 for family in T089_SUPPORTED_FAMILIES}:
        raise T089Incomplete("T089 held-out non-selected family cells are invalid")
    aggregate = statistics.fmean(row["delta"] for row in selected_metrics)
    median = statistics.median(row["delta"] for row in selected_metrics)
    family_means = {
        family: statistics.fmean(
            row["delta"] for row in selected_metrics if row["family"] == family
        )
        for family in T089_SUPPORTED_FAMILIES
    }
    non_selected_mean = statistics.fmean(
        float(row["delta"]) for row in non_selected_rows
    )
    if (
        not math.isclose(
            _require_finite_number(
                value.get("aggregate_mean_delta"),
                "T089 held-out aggregate mean",
            ),
            aggregate,
        )
        or not math.isclose(
            _require_finite_number(value.get("median_delta"), "T089 held-out median"),
            median,
        )
        or not math.isclose(
            _require_finite_number(
                value.get("non_selected_model_mean_delta"),
                "T089 held-out non-selected mean",
            ),
            non_selected_mean,
        )
        or value.get("family_mean_deltas") != family_means
    ):
        raise T089Incomplete("T089 held-out summary metrics are inconsistent")
    bootstrap = value.get("bootstrap")
    if (
        not isinstance(bootstrap, Mapping)
        or bootstrap.get("seed") != T089_HELDOUT_BOOTSTRAP_SEED
        or bootstrap.get("replicates") != T089_BOOTSTRAP_REPLICATES
        or bootstrap.get("sampling_unit") != "source_state"
    ):
        raise T089Incomplete("T089 held-out bootstrap identity is invalid")
    low, high = _bootstrap_interval(
        selected_metrics,
        delta_key="delta",
        families=T089_SUPPORTED_FAMILIES,
        per_family=16,
        seed=T089_HELDOUT_BOOTSTRAP_SEED,
        replicates=T089_BOOTSTRAP_REPLICATES,
    )
    if not math.isclose(
        _require_finite_number(bootstrap.get("lower_95"), "T089 held-out lower CI"),
        low,
    ) or not math.isclose(
        _require_finite_number(bootstrap.get("upper_95"), "T089 held-out upper CI"),
        high,
    ):
        raise T089Incomplete("T089 held-out bootstrap interval is inconsistent")
    violations = value.get("violations")
    problems = value.get("problems")
    if (
        not isinstance(violations, Sequence)
        or isinstance(violations, (str, bytes))
        or not all(isinstance(item, str) for item in violations)
    ):
        raise T089Incomplete("T089 held-out violations are invalid")
    if (
        not isinstance(problems, Sequence)
        or isinstance(problems, (str, bytes))
        or not all(isinstance(item, str) for item in problems)
    ):
        raise T089Incomplete("T089 held-out problems are invalid")
    conditions = (
        (aggregate > 0, "aggregate mean delta is not positive"),
        (median >= 0, "median delta is negative"),
        (
            sum(value >= 0 for value in family_means.values()) >= 3,
            "fewer than three family means are non-negative",
        ),
        (low > 0, "held-out bootstrap lower bound is not positive"),
        (
            non_selected_mean >= 0,
            "non-selected model seed has a negative aggregate delta",
        ),
        (not violations, "identity/schema/restore/legal-action/fallback violation"),
    )
    expected_problems = [message for condition, message in conditions if not condition]
    if (
        list(problems) != expected_problems
        or value.get("passed") != (not expected_problems)
        or value.get("fresh_evaluation_authorized") != (not expected_problems)
    ):
        raise T089Incomplete("T089 held-out gate classification is inconsistent")


def t089_terminal_report(
    classification: str,
    *,
    heldout: Mapping[str, Any] | None = None,
    fresh: Mapping[str, Any] | None = None,
    reason: str | None = None,
) -> dict[str, Any]:
    if classification not in T089_TERMINAL_CLASSIFICATIONS:
        raise T089ContractError("unknown T089 terminal classification")
    if classification == "INCOMPLETE":
        if not reason or heldout is not None or fresh is not None:
            raise T089ContractError(
                "INCOMPLETE requires an explicit missing/invalid-evidence reason"
            )
    else:
        if heldout is None:
            raise T089ContractError(f"{classification} requires held-out evidence")
        if not isinstance(heldout, Mapping):
            raise T089ContractError("held-out evidence must be an object")
        _validate_t089_heldout_report(heldout)
        heldout_passed = bool(heldout["passed"])
        if (
            classification == "NON_COMBAT_POLICY_IMPROVEMENT_NOT_ESTABLISHED"
            and not heldout_passed
        ):
            if fresh is not None:
                raise T089ContractError(
                    "fresh evidence is forbidden after a failed held-out gate"
                )
        else:
            if not heldout_passed:
                raise T089ContractError(
                    "fresh terminal classifications require a passing held-out gate"
                )
            if fresh is None or not isinstance(fresh, Mapping):
                raise T089ContractError(f"{classification} requires fresh evidence")
            validate_t089_fresh_report(fresh)
            if fresh.get("classification") != classification:
                raise T089ContractError(
                    "terminal classification does not match fresh evidence"
                )
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
