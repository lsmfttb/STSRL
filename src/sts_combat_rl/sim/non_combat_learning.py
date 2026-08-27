"""T065 learned public non-combat policy workflow.

This module owns the bounded, simulator-only T065 experiment.  It is kept
separate from the battle trainers and from the legacy command-line dispatcher:
the public model-input contract, source selection, counterfactual target
packing, optional PyTorch ranker, and gate reducers all live behind this
neutral workflow surface.

The real game remains the authority.  Collection helpers accept an adapter
factory and use :func:`execute_controlled_run`; they do not emulate game
mechanics.  The pure reducers are useful in tests and for deterministic
aggregation of retained artifacts without importing the simulator.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable, Iterable, Mapping, Sequence
import ast
from dataclasses import asdict, dataclass, field
import hashlib
import json
import math
from pathlib import Path
import random
import statistics
from tempfile import TemporaryDirectory
import time
from typing import Any
from concurrent.futures import ThreadPoolExecutor, as_completed

from sts_combat_rl.sim.action_space import ActionSpaceConfig
from sts_combat_rl.sim.contract import (
    CheckpointingSimulatorAdapter,
    SimulatorAction,
    SimulatorCheckpoint,
    SimulatorSnapshot,
    SimulatorTransition,
)
from sts_combat_rl.sim.controlled_run import (
    ControlledRun,
    ControlledRunStep,
    build_decision_context,
    execute_controlled_run,
)
from sts_combat_rl.sim.decision_record import (
    action_identity_dicts_for_actions,
    find_action_index_by_identity,
)
from sts_combat_rl.sim.features import (
    IDENTITY_VOCABULARY_VERSION,
    TACTICAL_FEATURE_SCHEMA_ID,
    TACTICAL_FEATURE_SCHEMA_VERSION,
    encode_lightspeed_battle_snapshot,
    encode_simulator_actions,
)
from sts_combat_rl.sim.lightspeed_source import lightspeed_source_identity_dict
from sts_combat_rl.sim.lightspeed_source import load_lightspeed_source_manifest
from sts_combat_rl.sim.non_combat_model_input import (
    NON_COMBAT_ACTION_FEATURE_SIZE,
    NON_COMBAT_CONTEXT_FEATURE_SIZE,
    NON_COMBAT_MODEL_INPUT_SCHEMA_ID,
    NON_COMBAT_MODEL_INPUT_SCHEMA_VERSION,
    NON_COMBAT_SNAPSHOT_FEATURE_SIZE,
    NON_COMBAT_STATE_FEATURE_SIZE,
    encode_non_combat_decision_context,
    non_combat_model_input_schema,
)
from sts_combat_rl.sim.non_combat_policy import (
    ExpertNonCombatDriver,
    StochasticNonCombatDriver,
)
from sts_combat_rl.sim.oracle_search import OracleSearchController
from sts_combat_rl.sim.online_controller import PolicyController, RoutedRunController
from sts_combat_rl.sim.policy_contract import DecisionContext, PolicyDecision
from sts_combat_rl.sim.public_context_model_input import (
    PUBLIC_CONTEXT_MODEL_INPUT_FEATURE_NAMES,
    PUBLIC_CONTEXT_MODEL_INPUT_FEATURE_SIZE,
    PUBLIC_CONTEXT_MODEL_INPUT_SCHEMA_ID,
    PUBLIC_CONTEXT_MODEL_INPUT_SCHEMA_VERSION,
)
from sts_combat_rl.sim.public_context_artifacts import (
    PUBLIC_CONTEXT_STATUS_VALUES,
    public_context_artifact_problems,
)
from sts_combat_rl.sim.native_public_projection import (
    NATIVE_PUBLIC_PROJECTION_SCHEMA_ID,
)
from sts_combat_rl.sim.public_run_context import (
    append_public_history_entry,
    build_public_history_entry,
    build_public_run_context,
    forbidden_public_context_problems,
    read_native_public_projection,
)


T065_TASK_ID = "T065"
T065_APPROVED_SPEC_COMMIT = "a13c92a66b4d9ad9f6a730293cadc8d66b4a699c"
T065_EXPERIMENT_SCHEMA_ID = "t065-learned-non-combat-policy-v1"
T065_EXPERIMENT_SCHEMA_VERSION = 1
T065_SOURCE_STATE_SCHEMA_ID = "t065-source-state-v1"
T065_TARGET_TABLE_SCHEMA_ID = "t065-counterfactual-target-table-v1"
T065_CHECKPOINT_SCHEMA_ID = "t065-non-combat-ranker-checkpoint-v1"
T065_STAGE5_REPORT_SCHEMA_ID = "t065-heldout-gate-report-v1"
T065_STAGE6_REPORT_SCHEMA_ID = "t065-complete-run-report-v1"
T065_DECISION_REPORT_SCHEMA_ID = "t065-terminal-decision-report-v1"
T065_SELECTION_MANIFEST_SCHEMA_ID = "t065-source-selection-manifest-v1"
T065_PREFLIGHT_SCHEMA_ID = "t065-readiness-preflight-v1"

T065_SOURCE_SEED_RANGE = (650001, 650256)
T065_STAGE6_SEED_RANGE = (651001, 651256)
T065_SOURCE_DRIVER_SEED = 654001
T065_STAGE6_DRIVER_SEED = 654002
T065_MODEL_SEEDS = (653001, 653002)
T065_TRAIN_CONTINUATION_SEEDS = (652001, 652002)
T065_VALIDATION_CONTINUATION_SEEDS = (652101, 652102)
T065_HELDOUT_CONTINUATION_SEEDS = (652201, 652202, 652203, 652204)
T065_STAGE5_BOOTSTRAP_SEED = 655001
T065_STAGE6_BOOTSTRAP_SEED = 655002
T065_BOOTSTRAP_REPLICATES = 10_000
T065_MAX_STEPS = 500
T065_NATIVE_PROBE_MAX_STEPS = 192
T065_BATTLE_SIMULATIONS = 20
T065_MAX_WORKERS = 16
T065_STAGE1_SHARD_COUNT = 16
T065_STAGE2_SHARD_COUNT = 16
T065_STAGE6_SHARD_COUNT = 16
T065_TRAINING_INTERPRETER = "/home/lsmft/stsrl-spikes/py313-torch/bin/python"
T065_LIGHTSPEED_BUILD_PYTHONPATH = (
    "/home/lsmft/stsrl-spikes/sts_lightspeed/build-py313-torch"
)
T065_RANKER_PARAMETER_COUNT = 325825
T065_RANKER_PARAMETER_SHAPES = (
    (64, NON_COMBAT_STATE_FEATURE_SIZE),
    (64,),
    (64, 64),
    (64,),
    (64, NON_COMBAT_ACTION_FEATURE_SIZE),
    (64,),
    (64, 64),
    (64,),
    (64, 128),
    (64,),
    (1, 64),
    (1,),
)

T065_MANDATORY_FAMILIES = (
    "MAP_SCREEN",
    "REST_ROOM",
    "REWARDS",
    "TREASURE_ROOM",
)
T065_SPLITS = ("train", "validation", "heldout")
T065_SPLIT_SEED_GROUPS: Mapping[str, tuple[int, int]] = {
    "train": (650001, 650154),
    "validation": (650155, 650205),
    "heldout": (650206, 650256),
}
T065_SPLIT_QUOTAS: Mapping[str, int] = {
    "train": 48,
    "validation": 16,
    "heldout": 16,
}
T065_SELECTION_DOMAIN = b"T065-source-selection-v1\n"
T065_LEARNED_POLICY_NAME = "learned_non_combat_v1"
T065_FROZEN_BATTLE_CONTROLLER_NAME = "oracle_search_v1_highest_mean_s20"
T065_FROZEN_BATTLE_CONTROLLER_VERSION = "oracle-search-controller-v1"
T065_FROZEN_BATTLE_INFORMATION_REGIME = "full_simulator_state_oracle_like"
T065_RETENTION_RELATIVE_PATH = "artifacts/t065-learned-non-combat-policy-v1"

T075_TASK_ID = "T075"
T075_APPROVED_SPEC_COMMIT = "e204c5d28cc0bee8013853e8680e8966f5c930a8"
T075_PLANNER_BASELINE = "95ccb6b55bc7a0214b632206ae169a533289fcf2"
T075_GROUP_DOMAIN = b"T075-replay-group-v1\n"
T075_SELECTION_STRATEGY_ID = "leakage-safe-global-owner-v1"
T075_REUSE_MANIFEST_SCHEMA_ID = "t075-retained-source-reuse-manifest-v1"
T075_OWNERSHIP_AUDIT_SCHEMA_ID = "t075-replay-group-ownership-audit-v1"
T075_SELECTION_MANIFEST_SCHEMA_ID = "t075-source-selection-manifest-v1"
T075_STAGE3_VALIDATION_SCHEMA_ID = "t075-stage3-validation-report-v1"
T075_TERMINAL_DECISION_SCHEMA_ID = "t075-terminal-decision-report-v1"
T075_RETENTION_MANIFEST_SCHEMA_ID = "t075-retention-manifest-v1"


class T065CaseD(ValueError):
    """A frozen fidelity/completeness failure that stops downstream stages."""

    def __init__(
        self,
        stage: str,
        problems: Sequence[str],
        *,
        failure_ids: Sequence[str] = (),
        failure_counts: Mapping[str, int] | None = None,
        simulator_identity: Mapping[str, Any] | None = None,
        preceding_stage_manifests: Mapping[str, Any] | None = None,
        failed_stage_artifacts: Mapping[str, Any] | None = None,
        failure_details: Sequence[Mapping[str, Any]] = (),
        failure_detail_counts: Mapping[str, Any] | None = None,
    ) -> None:
        self.stage = str(stage)
        self.problems = tuple(str(problem) for problem in problems)
        self.failure_ids = tuple(str(identifier) for identifier in failure_ids)
        self.failure_counts = {
            str(key): int(value) for key, value in (failure_counts or {}).items()
        }
        self.simulator_identity = dict(simulator_identity or {})
        self.preceding_stage_manifests = dict(preceding_stage_manifests or {})
        self.failed_stage_artifacts = dict(failed_stage_artifacts or {})
        self.failure_details = tuple(dict(detail) for detail in failure_details)
        self.failure_detail_counts = dict(failure_detail_counts or {})
        super().__init__(f"T065 Case D at {self.stage}: " + "; ".join(self.problems))

    def to_decision_report(
        self,
        *,
        simulator_identity: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Serialize the single frozen Case-D outcome for early failures."""

        identity = dict(simulator_identity or self.simulator_identity)
        identifiers = self.failure_ids or self.problems
        counts = dict(self.failure_counts)
        if "failure_count" not in counts:
            counts["failure_count"] = len(identifiers)
        skipped_after = {
            "stage0": ("stage1", "stage2", "stage3", "stage4", "stage5", "stage6"),
            "stage0-preflight": (
                "stage1",
                "stage2",
                "stage3",
                "stage4",
                "stage5",
                "stage6",
            ),
            "stage1": ("stage2", "stage3", "stage4", "stage5", "stage6"),
            "source-collection": ("stage2", "stage3", "stage4", "stage5", "stage6"),
            "source-selection": ("stage2", "stage3", "stage4", "stage5", "stage6"),
            "stage2": ("stage3", "stage4", "stage5", "stage6"),
            "counterfactual-targets": ("stage3", "stage4", "stage5", "stage6"),
            "target-completeness": ("stage3", "stage4", "stage5", "stage6"),
            "stage4": ("stage5", "stage6"),
            "stage5": ("stage6",),
            "stage6": (),
        }
        output = {
            "schema_id": T065_DECISION_REPORT_SCHEMA_ID,
            "schema_version": 1,
            "task_id": T065_TASK_ID,
            "case": "D",
            "stage": self.stage,
            "approved_spec_commit": T065_APPROVED_SPEC_COMMIT,
            "simulator_identity": identity,
            "failure_ids": list(identifiers),
            "failure_counts": counts,
            "no_replacement": True,
            "downstream_skipped": list(
                skipped_after.get(self.stage, ("stage4", "stage5", "stage6"))
            ),
            "preceding_stage_manifests": dict(self.preceding_stage_manifests),
            "failed_stage_artifacts": dict(self.failed_stage_artifacts),
            "recommendation": "repair the frozen fidelity failure and rerun T065",
            "problems": list(self.problems),
            "policy_conclusion": None,
        }
        # These are additive optional fields so legacy readers can continue to
        # consume the version-1 report while source-selection failures expose
        # both sides of a replay-equivalence collision.
        if self.failure_details:
            output["failure_details"] = [
                _json_safe(detail) for detail in self.failure_details
            ]
        if self.failure_detail_counts:
            output["failure_detail_counts"] = _json_safe(self.failure_detail_counts)
        return output


@dataclass(frozen=True)
class T065ExperimentConfig:
    """The scientific configuration with no post-observation choices."""

    source_seed_start: int = T065_SOURCE_SEED_RANGE[0]
    source_seed_end: int = T065_SOURCE_SEED_RANGE[1]
    stage6_seed_start: int = T065_STAGE6_SEED_RANGE[0]
    stage6_seed_end: int = T065_STAGE6_SEED_RANGE[1]
    source_driver_seed: int = T065_SOURCE_DRIVER_SEED
    stage6_driver_seed: int = T065_STAGE6_DRIVER_SEED
    source_step_cap: int = T065_MAX_STEPS
    battle_simulations: int = T065_BATTLE_SIMULATIONS
    player_class: str = "IRONCLAD"
    ascension: int = 20
    model_seeds: tuple[int, ...] = T065_MODEL_SEEDS

    def __post_init__(self) -> None:
        actual = (
            self.source_seed_start,
            self.source_seed_end,
            self.stage6_seed_start,
            self.stage6_seed_end,
            self.source_driver_seed,
            self.stage6_driver_seed,
            self.source_step_cap,
            self.battle_simulations,
            self.player_class,
            self.ascension,
            tuple(self.model_seeds),
        )
        expected = (
            *T065_SOURCE_SEED_RANGE,
            *T065_STAGE6_SEED_RANGE,
            T065_SOURCE_DRIVER_SEED,
            T065_STAGE6_DRIVER_SEED,
            T065_MAX_STEPS,
            T065_BATTLE_SIMULATIONS,
            "IRONCLAD",
            20,
            T065_MODEL_SEEDS,
        )
        if actual != expected:
            raise ValueError(
                "T065 scientific inputs are frozen; received "
                f"{actual!r}, expected {expected!r}"
            )

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["model_seeds"] = list(self.model_seeds)
        value["source_seed_range"] = list(T065_SOURCE_SEED_RANGE)
        value["stage6_seed_range"] = list(T065_STAGE6_SEED_RANGE)
        value["continuation_seeds"] = {
            "train": list(T065_TRAIN_CONTINUATION_SEEDS),
            "validation": list(T065_VALIDATION_CONTINUATION_SEEDS),
            "heldout": list(T065_HELDOUT_CONTINUATION_SEEDS),
        }
        value["screen_families"] = list(T065_MANDATORY_FAMILIES)
        value["split_quotas"] = dict(T065_SPLIT_QUOTAS)
        value["bootstrap"] = {
            "replicates": T065_BOOTSTRAP_REPLICATES,
            "stage5_seed": T065_STAGE5_BOOTSTRAP_SEED,
            "stage6_seed": T065_STAGE6_BOOTSTRAP_SEED,
        }
        return value


def inclusive_range(bounds: tuple[int, int]) -> tuple[int, ...]:
    """Expand one inclusive frozen integer range."""

    start, end = bounds
    if isinstance(start, bool) or isinstance(end, bool) or start > end:
        raise ValueError(f"invalid inclusive range {bounds!r}")
    return tuple(range(start, end + 1))


def continuation_seeds_for_split(split: str) -> tuple[int, ...]:
    """Return the immutable expert continuation seed tuple for one split."""

    try:
        return {
            "train": T065_TRAIN_CONTINUATION_SEEDS,
            "validation": T065_VALIDATION_CONTINUATION_SEEDS,
            "heldout": T065_HELDOUT_CONTINUATION_SEEDS,
        }[split]
    except KeyError as exc:
        raise ValueError(f"unsupported T065 split {split!r}") from exc


def split_for_source_seed(seed: int) -> str:
    """Assign a source seed using only the frozen seed-group partition."""

    if isinstance(seed, bool) or not isinstance(seed, int):
        raise ValueError("T065 source seed must be an integer")
    for split, (start, end) in T065_SPLIT_SEED_GROUPS.items():
        if start <= seed <= end:
            return split
    raise ValueError(f"source seed {seed} is outside the frozen T065 partition")


def source_shard_ranges(
    *,
    arm: str,
    worker_count: int = T065_MAX_WORKERS,
) -> tuple[dict[str, Any], ...]:
    """Return the exact 16x16 Stage 1 shard ranges."""

    if arm not in {"stochastic_non_combat_v1", "expert_non_combat_v1"}:
        raise ValueError(f"unsupported T065 source arm {arm!r}")
    _validate_workers(worker_count)
    return tuple(
        {
            "arm": arm,
            "shard_index": index,
            "seed_start": 650001 + 16 * index,
            "seed_end": 650016 + 16 * index,
            "seed_count": 16,
            "worker_count": worker_count,
        }
        for index in range(T065_STAGE1_SHARD_COUNT)
    )


def target_shard_ranges(
    *, worker_count: int = T065_MAX_WORKERS
) -> tuple[dict[str, Any], ...]:
    """Return the exact 16x20 selected-state Stage 2 shard ranges."""

    _validate_workers(worker_count)
    return tuple(
        {
            "shard_index": index,
            "selected_state_start": 20 * index,
            "selected_state_end": 20 * index + 19,
            "selected_state_count": 20,
            "worker_count": worker_count,
        }
        for index in range(T065_STAGE2_SHARD_COUNT)
    )


def stage6_shard_ranges(
    *,
    arm: str,
    worker_count: int = T065_MAX_WORKERS,
) -> tuple[dict[str, Any], ...]:
    """Return the exact 16x16 Stage 6 shard ranges for one arm."""

    if arm not in {"stochastic", "expert", "learned"}:
        raise ValueError(f"unsupported T065 Stage 6 arm {arm!r}")
    _validate_workers(worker_count)
    return tuple(
        {
            "arm": arm,
            "shard_index": index,
            "seed_start": 651001 + 16 * index,
            "seed_end": 651016 + 16 * index,
            "seed_count": 16,
            "worker_count": worker_count,
        }
        for index in range(T065_STAGE6_SHARD_COUNT)
    )


def frozen_action_space() -> ActionSpaceConfig:
    """Construct the one action-space configuration permitted by T065."""

    return ActionSpaceConfig.initial_no_potions()


def build_frozen_battle_controller() -> OracleSearchController:
    """Construct the exact battle controller used by every simulator stage."""

    controller = OracleSearchController(
        simulations=T065_BATTLE_SIMULATIONS,
        root_selection_rule="highest_mean",
        action_space=frozen_action_space(),
    )
    if controller.provenance.name != T065_FROZEN_BATTLE_CONTROLLER_NAME:
        raise ValueError(
            "current oracle controller provenance does not match frozen T065 "
            f"name {T065_FROZEN_BATTLE_CONTROLLER_NAME!r}"
        )
    return controller


def frozen_battle_provenance() -> dict[str, Any]:
    """Return and validate the exact serialized battle provenance."""

    provenance = build_frozen_battle_controller().provenance.to_dict()
    config = provenance.get("config", {})
    if not isinstance(config, Mapping):
        raise ValueError("oracle controller provenance config is malformed")
    if config.get("controller_version") != T065_FROZEN_BATTLE_CONTROLLER_VERSION:
        raise ValueError("oracle controller version is not the frozen T065 version")
    if config.get("information_regime") != T065_FROZEN_BATTLE_INFORMATION_REGIME:
        raise ValueError("oracle controller information regime is not oracle-like")
    if config.get("action_space") != frozen_action_space().to_dict():
        raise ValueError("oracle controller action-space provenance is not frozen")
    return provenance


@dataclass(frozen=True)
class T065SourceState:
    """Portable public state selected from one completed source run."""

    selected_state_index: int
    family: str
    split: str
    simulator_seed: int
    source_arm: str
    source_run_id: str
    source_step_index: int
    source_floor: float | None
    source_act: float | None
    screen_state: str
    snapshot_features: tuple[float, ...]
    public_context_features: tuple[float, ...]
    state_features: tuple[float, ...]
    legal_action_features: tuple[tuple[float, ...], ...]
    legal_action_kinds: tuple[str, ...]
    eligible_action_indices: tuple[int, ...]
    legal_action_identities: tuple[Mapping[str, Any], ...]
    action_trace: tuple[Mapping[str, Any], ...]
    public_state_identity: str
    public_context_status: str
    public_run_context: Mapping[str, Any]
    behavior_action_index: int | None = None
    behavior_action_identity: Mapping[str, Any] = field(default_factory=dict)
    terminal: bool = True
    terminal_status: str = "UNKNOWN"
    terminal_floor: float | None = None
    source_controller_provenance: Mapping[str, Any] = field(default_factory=dict)
    source_non_combat_provenance: Mapping[str, Any] = field(default_factory=dict)
    source_battle_provenance: Mapping[str, Any] = field(default_factory=dict)
    model_input_schema_id: str = NON_COMBAT_MODEL_INPUT_SCHEMA_ID
    model_input_schema_version: int = NON_COMBAT_MODEL_INPUT_SCHEMA_VERSION
    tactical_feature_schema_id: str = TACTICAL_FEATURE_SCHEMA_ID
    tactical_feature_schema_version: int = TACTICAL_FEATURE_SCHEMA_VERSION
    identity_vocabulary_version: str = IDENTITY_VOCABULARY_VERSION
    public_context_feature_schema_id: str = PUBLIC_CONTEXT_MODEL_INPUT_SCHEMA_ID
    public_context_feature_schema_version: int = (
        PUBLIC_CONTEXT_MODEL_INPUT_SCHEMA_VERSION
    )
    selection_digest: str = ""
    selection_canonical_json: str = ""

    def __post_init__(self) -> None:
        if self.selected_state_index < -1:
            raise ValueError("T065 selected_state_index must be -1 or non-negative")
        if self.source_arm not in {
            "stochastic_non_combat_v1",
            "expert_non_combat_v1",
        }:
            raise ValueError(f"unsupported T065 source arm {self.source_arm!r}")
        if self.family not in T065_MANDATORY_FAMILIES:
            raise ValueError(f"unsupported T065 source family {self.family!r}")
        if self.split not in T065_SPLITS:
            raise ValueError(f"unsupported T065 source split {self.split!r}")
        if split_for_source_seed(self.simulator_seed) != self.split:
            raise ValueError("T065 source split does not match simulator seed group")
        if self.model_input_schema_id != NON_COMBAT_MODEL_INPUT_SCHEMA_ID:
            raise ValueError("T065 source model-input schema id is unsupported")
        if self.model_input_schema_version != NON_COMBAT_MODEL_INPUT_SCHEMA_VERSION:
            raise ValueError("T065 source model-input schema version is unsupported")
        if self.tactical_feature_schema_id != TACTICAL_FEATURE_SCHEMA_ID:
            raise ValueError("T065 source tactical schema id is unsupported")
        if self.tactical_feature_schema_version != TACTICAL_FEATURE_SCHEMA_VERSION:
            raise ValueError("T065 source tactical schema version is unsupported")
        if self.identity_vocabulary_version != IDENTITY_VOCABULARY_VERSION:
            raise ValueError("T065 source identity vocabulary is unsupported")
        if (
            self.public_context_feature_schema_id
            != PUBLIC_CONTEXT_MODEL_INPUT_SCHEMA_ID
            or self.public_context_feature_schema_version
            != PUBLIC_CONTEXT_MODEL_INPUT_SCHEMA_VERSION
        ):
            raise ValueError("T065 source public-context schema is unsupported")
        if self.public_context_status not in PUBLIC_CONTEXT_STATUS_VALUES:
            raise ValueError("T065 source public-context status is unsupported")
        context_problems = public_context_artifact_problems(
            status=self.public_context_status,
            context=self.public_run_context,
            label="T065 source state",
            require_available=self.public_context_status == "available",
        )
        context_problems.extend(
            f"T065 source state: {problem}"
            for problem in forbidden_public_context_problems(self.public_run_context)
        )
        if context_problems:
            raise ValueError("; ".join(context_problems))
        if (
            self.public_context_status == "available"
            and self.public_run_context.get("projection_status") != "available"
        ):
            raise ValueError(
                "T065 available source context must declare projection_status=available"
            )
        if len(self.snapshot_features) != NON_COMBAT_SNAPSHOT_FEATURE_SIZE:
            raise ValueError("T065 source snapshot feature width is not 4634")
        if len(self.public_context_features) != NON_COMBAT_CONTEXT_FEATURE_SIZE:
            raise ValueError("T065 source public-context feature width is not 103")
        if len(self.state_features) != NON_COMBAT_STATE_FEATURE_SIZE:
            raise ValueError("T065 source state feature width is not 4737")
        if self.state_features != (
            self.snapshot_features + self.public_context_features
        ):
            raise ValueError("T065 source state is not snapshot/context concatenation")
        _validate_mandatory_family_projection(self.family, self.state_features)
        if len(self.legal_action_features) != len(self.legal_action_kinds):
            raise ValueError("T065 source action kinds are not aligned")
        if len(self.legal_action_features) != len(self.legal_action_identities):
            raise ValueError("T065 source action identities are not aligned")
        if any(
            len(row) != NON_COMBAT_ACTION_FEATURE_SIZE
            for row in self.legal_action_features
        ):
            raise ValueError("T065 source action feature width is not 92")
        if not self.eligible_action_indices:
            raise ValueError("T065 source has no eligible actions")
        if len(set(self.eligible_action_indices)) != len(self.eligible_action_indices):
            raise ValueError("T065 source eligible action indices contain duplicates")
        if any(
            index < 0 or index >= len(self.legal_action_features)
            for index in self.eligible_action_indices
        ):
            raise ValueError("T065 source eligible action index is outside actions")
        if self.behavior_action_index is not None:
            if self.behavior_action_index not in self.eligible_action_indices:
                raise ValueError("T065 source behavior action is not eligible")
            if not self.behavior_action_identity:
                raise ValueError("T065 source behavior action identity is missing")
            if dict(self.behavior_action_identity) != dict(
                self.legal_action_identities[self.behavior_action_index]
            ):
                raise ValueError("T065 source behavior action identity is misaligned")

    @property
    def state_identity(self) -> str:
        return self.public_state_identity

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": T065_SOURCE_STATE_SCHEMA_ID,
            "schema_version": 1,
            "selected_state_index": self.selected_state_index,
            "family": self.family,
            "split": self.split,
            "simulator_seed": self.simulator_seed,
            "source_arm": self.source_arm,
            "source_run_id": self.source_run_id,
            "source_step_index": self.source_step_index,
            "source_floor": self.source_floor,
            "source_act": self.source_act,
            "screen_state": self.screen_state,
            "snapshot_features": list(self.snapshot_features),
            "public_context_features": list(self.public_context_features),
            "state_features": list(self.state_features),
            "legal_action_features": [list(row) for row in self.legal_action_features],
            "legal_action_kinds": list(self.legal_action_kinds),
            "eligible_action_indices": list(self.eligible_action_indices),
            "legal_action_identities": [
                dict(row) for row in self.legal_action_identities
            ],
            "action_trace": [dict(row) for row in self.action_trace],
            "public_state_identity": self.public_state_identity,
            "public_context_status": self.public_context_status,
            "public_run_context": dict(self.public_run_context),
            "behavior_action_index": self.behavior_action_index,
            "behavior_action_identity": dict(self.behavior_action_identity),
            "terminal": self.terminal,
            "terminal_status": self.terminal_status,
            "terminal_floor": self.terminal_floor,
            "source_controller_provenance": dict(self.source_controller_provenance),
            "source_non_combat_provenance": dict(self.source_non_combat_provenance),
            "source_battle_provenance": dict(self.source_battle_provenance),
            "model_input_schema_id": self.model_input_schema_id,
            "model_input_schema_version": self.model_input_schema_version,
            "tactical_feature_schema_id": self.tactical_feature_schema_id,
            "tactical_feature_schema_version": self.tactical_feature_schema_version,
            "identity_vocabulary_version": self.identity_vocabulary_version,
            "public_context_feature_schema_id": self.public_context_feature_schema_id,
            "public_context_feature_schema_version": (
                self.public_context_feature_schema_version
            ),
            "selection_digest": self.selection_digest,
            "selection_canonical_json": self.selection_canonical_json,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "T065SourceState":
        if value.get("schema_id") != T065_SOURCE_STATE_SCHEMA_ID:
            raise ValueError("unsupported T065 source-state schema")
        if value.get("schema_version") != 1:
            raise ValueError("unsupported T065 source-state schema version")
        terminal = value.get("terminal")
        if not isinstance(terminal, bool):
            raise ValueError("T065 field 'terminal' must be a boolean")
        return cls(
            selected_state_index=_int_field(value, "selected_state_index"),
            family=_str_field(value, "family"),
            split=_str_field(value, "split"),
            simulator_seed=_int_field(value, "simulator_seed"),
            source_arm=_str_field(value, "source_arm"),
            source_run_id=_str_field(value, "source_run_id"),
            source_step_index=_int_field(value, "source_step_index"),
            source_floor=_optional_float(value.get("source_floor")),
            source_act=_optional_float(value.get("source_act")),
            screen_state=_str_field(value, "screen_state"),
            snapshot_features=_float_tuple(
                value.get("snapshot_features"), "snapshot_features"
            ),
            public_context_features=_float_tuple(
                value.get("public_context_features"), "public_context_features"
            ),
            state_features=_float_tuple(value.get("state_features"), "state_features"),
            legal_action_features=_float_matrix(
                value.get("legal_action_features"), "legal_action_features"
            ),
            legal_action_kinds=_str_tuple(
                value.get("legal_action_kinds"), "legal_action_kinds"
            ),
            eligible_action_indices=_int_tuple(
                value.get("eligible_action_indices"), "eligible_action_indices"
            ),
            legal_action_identities=_mapping_tuple(
                value.get("legal_action_identities"), "legal_action_identities"
            ),
            action_trace=_mapping_tuple(value.get("action_trace"), "action_trace"),
            public_state_identity=_str_field(value, "public_state_identity"),
            public_context_status=_str_field(value, "public_context_status"),
            public_run_context=_mapping_field(value, "public_run_context"),
            behavior_action_index=_optional_int(value.get("behavior_action_index")),
            behavior_action_identity=_mapping_field(value, "behavior_action_identity"),
            terminal=terminal,
            terminal_status=str(value.get("terminal_status", "UNKNOWN")),
            terminal_floor=_optional_float(value.get("terminal_floor")),
            source_controller_provenance=_mapping_field(
                value, "source_controller_provenance"
            ),
            source_non_combat_provenance=_mapping_field(
                value, "source_non_combat_provenance"
            ),
            source_battle_provenance=_mapping_field(value, "source_battle_provenance"),
            model_input_schema_id=_str_field(value, "model_input_schema_id"),
            model_input_schema_version=_int_field(value, "model_input_schema_version"),
            tactical_feature_schema_id=_str_field(value, "tactical_feature_schema_id"),
            tactical_feature_schema_version=_int_field(
                value, "tactical_feature_schema_version"
            ),
            identity_vocabulary_version=_str_field(
                value, "identity_vocabulary_version"
            ),
            public_context_feature_schema_id=_str_field(
                value, "public_context_feature_schema_id"
            ),
            public_context_feature_schema_version=_int_field(
                value, "public_context_feature_schema_version"
            ),
            selection_digest=str(value.get("selection_digest", "")),
            selection_canonical_json=str(value.get("selection_canonical_json", "")),
        )


@dataclass(frozen=True)
class T065CounterfactualTarget:
    """One state/action row with all required continuation outcomes."""

    selected_state_index: int
    state_identity: str
    family: str
    split: str
    legal_action_index: int
    legal_action_identity: Mapping[str, Any]
    continuation_seeds: tuple[int, ...]
    terminal_floors: tuple[float, ...]
    terminal_acts: tuple[float | None, ...] = ()
    terminal_statuses: tuple[str, ...] = ()
    terminal_current_hps: tuple[float | None, ...] = ()
    terminal_max_hps: tuple[float | None, ...] = ()
    terminal_golds: tuple[float | None, ...] = ()
    terminal_potion_counts: tuple[float | None, ...] = ()
    q_floor: float = 0.0
    target_status: str = "complete"
    simulator_cost: Mapping[str, Any] = field(default_factory=dict)
    wall_clock_seconds: float = 0.0
    problems: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        continuation_count = len(self.continuation_seeds)
        if continuation_count != len(self.terminal_floors):
            raise ValueError("T065 target continuation seeds/floors are misaligned")
        if any(
            isinstance(seed, bool) or not isinstance(seed, int)
            for seed in self.continuation_seeds
        ):
            raise ValueError("T065 target continuation seed is invalid")
        if any(not math.isfinite(float(floor)) for floor in self.terminal_floors):
            raise ValueError("T065 target continuation floor is non-finite")
        if len(self.terminal_acts) != continuation_count:
            raise ValueError("T065 target continuation acts are misaligned")
        if len(self.terminal_statuses) != continuation_count:
            raise ValueError("T065 target continuation statuses are misaligned")
        if any(not status for status in self.terminal_statuses):
            raise ValueError("T065 target continuation status is empty")
        for label, values in (
            ("current HP", self.terminal_current_hps),
            ("max HP", self.terminal_max_hps),
            ("gold", self.terminal_golds),
            ("potion count", self.terminal_potion_counts),
        ):
            if len(values) != continuation_count:
                raise ValueError(f"T065 target continuation {label} is misaligned")
            if any(
                value is not None and not math.isfinite(float(value))
                for value in values
            ):
                raise ValueError(f"T065 target continuation {label} is non-finite")
        if not math.isfinite(float(self.q_floor)):
            raise ValueError("T065 q_floor must be finite")
        if (
            not math.isfinite(float(self.wall_clock_seconds))
            or float(self.wall_clock_seconds) < 0.0
        ):
            raise ValueError("T065 target wall-clock cost must be non-negative")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": T065_TARGET_TABLE_SCHEMA_ID,
            "schema_version": 1,
            "selected_state_index": self.selected_state_index,
            "state_identity": self.state_identity,
            "family": self.family,
            "split": self.split,
            "legal_action_index": self.legal_action_index,
            "legal_action_identity": dict(self.legal_action_identity),
            "continuation_seeds": list(self.continuation_seeds),
            "terminal_floors": list(self.terminal_floors),
            "terminal_acts": list(self.terminal_acts),
            "terminal_statuses": list(self.terminal_statuses),
            "terminal_current_hps": list(self.terminal_current_hps),
            "terminal_max_hps": list(self.terminal_max_hps),
            "terminal_golds": list(self.terminal_golds),
            "terminal_potion_counts": list(self.terminal_potion_counts),
            "q_floor": self.q_floor,
            "target_status": self.target_status,
            "simulator_cost": dict(self.simulator_cost),
            "wall_clock_seconds": self.wall_clock_seconds,
            "problems": list(self.problems),
        }


@dataclass(frozen=True)
class T065TargetTable:
    """Selected source states and complete all-action target rows."""

    states: tuple[T065SourceState, ...]
    targets: tuple[T065CounterfactualTarget, ...]
    source_artifact_identity: Mapping[str, Any] = field(default_factory=dict)
    simulator_identity: Mapping[str, Any] = field(default_factory=dict)
    execution_evidence: Mapping[str, Any] = field(default_factory=dict)
    expert_action_indices: Mapping[int, int] = field(default_factory=dict)
    expert_action_provenance: Mapping[str, Any] = field(default_factory=dict)
    schema_id: str = T065_TARGET_TABLE_SCHEMA_ID
    schema_version: int = 1

    def rows_for_state(
        self, selected_state_index: int
    ) -> tuple[T065CounterfactualTarget, ...]:
        return tuple(
            row
            for row in self.targets
            if row.selected_state_index == selected_state_index
        )

    def validate_complete(self, *, require_contiguous_indices: bool = True) -> None:
        problems: list[str] = []
        if self.schema_id != T065_TARGET_TABLE_SCHEMA_ID:
            problems.append("target table schema id is unsupported")
        if self.schema_version != 1:
            problems.append("target table schema version is unsupported")
        expected_expert_provenance = {
            "name": "expert_non_combat_v1",
            "version": 1,
            "seed": T065_SOURCE_DRIVER_SEED,
            "reset_rule": "reset_for_run(simulator_seed) at replayed source state",
            "purpose": "heldout comparison only; never a training feature or target",
        }
        if not self.expert_action_indices:
            problems.append("expert comparison action map is missing")
        if any(
            self.expert_action_provenance.get(key) != expected
            for key, expected in expected_expert_provenance.items()
        ):
            problems.append("expert comparison provenance is not frozen")
        by_state = {state.selected_state_index: state for state in self.states}
        if require_contiguous_indices and tuple(sorted(by_state)) != tuple(
            range(len(self.states))
        ):
            problems.append("selected-state indices are not contiguous")
        for state in self.states:
            if not state.terminal:
                problems.append(
                    f"state {state.selected_state_index}: source state is not terminal"
                )
            rows = self.rows_for_state(state.selected_state_index)
            expected_actions = tuple(state.eligible_action_indices)
            observed_actions = tuple(row.legal_action_index for row in rows)
            if observed_actions != expected_actions:
                problems.append(
                    f"state {state.selected_state_index}: target action rows "
                    f"{observed_actions!r} != eligible {expected_actions!r}"
                )
            expected_seeds = continuation_seeds_for_split(state.split)
            for row in rows:
                if row.family != state.family or row.split != state.split:
                    problems.append(
                        f"state {state.selected_state_index} action "
                        f"{row.legal_action_index}: target stratum mismatch"
                    )
                if row.continuation_seeds != expected_seeds:
                    problems.append(
                        f"state {state.selected_state_index} action "
                        f"{row.legal_action_index}: continuation seeds mismatch"
                    )
                if row.state_identity != state.state_identity:
                    problems.append(
                        f"state {state.selected_state_index}: target identity mismatch"
                    )
                if row.legal_action_index not in state.eligible_action_indices:
                    problems.append(
                        f"state {state.selected_state_index} action "
                        f"{row.legal_action_index}: target action is not eligible"
                    )
                elif (
                    row.legal_action_identity
                    != state.legal_action_identities[row.legal_action_index]
                ):
                    problems.append(
                        f"state {state.selected_state_index} action "
                        f"{row.legal_action_index}: action identity mismatch"
                    )
                if len(row.terminal_floors) != len(expected_seeds):
                    problems.append(
                        f"state {state.selected_state_index} action "
                        f"{row.legal_action_index}: missing continuation rows"
                    )
                if row.target_status != "complete" or row.problems:
                    problems.append(
                        f"state {state.selected_state_index} action "
                        f"{row.legal_action_index}: target status is invalid"
                    )
            expert_index = self.expert_action_indices.get(state.selected_state_index)
            if expert_index not in state.eligible_action_indices:
                problems.append(
                    f"state {state.selected_state_index}: expert comparison "
                    "action is missing or ineligible"
                )
        expected_rows = sum(len(state.eligible_action_indices) for state in self.states)
        if len(self.targets) != expected_rows:
            problems.append(
                f"target row count {len(self.targets)} does not match {expected_rows}"
            )
        if set(self.expert_action_indices) != set(by_state):
            problems.append(
                "expert comparison action map does not cover exactly the selected states"
            )
        if problems:
            raise T065CaseD("target-completeness", problems)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "schema_version": self.schema_version,
            "task_id": T065_TASK_ID,
            "approved_spec_commit": T065_APPROVED_SPEC_COMMIT,
            "frozen_config": T065ExperimentConfig().to_dict(),
            "model_input_schema": non_combat_model_input_schema(),
            "source_artifact_identity": dict(self.source_artifact_identity),
            "simulator_identity": dict(self.simulator_identity),
            "execution_evidence": dict(self.execution_evidence),
            "expert_action_indices": {
                str(index): action_index
                for index, action_index in self.expert_action_indices.items()
            },
            "expert_action_provenance": dict(self.expert_action_provenance),
            "states": [state.to_dict() for state in self.states],
            "targets": [target.to_dict() for target in self.targets],
        }


@dataclass(frozen=True)
class T065SourceArmReport:
    arm: str
    driver_seed: int
    requested_seed_count: int
    terminal_run_count: int
    truncated_run_count: int
    failed_run_count: int
    selected_candidate_count: int
    records: tuple[T065SourceState, ...] = ()
    run_summaries: tuple[Mapping[str, Any], ...] = ()
    problems: tuple[str, ...] = ()
    simulator_identity: Mapping[str, Any] = field(default_factory=dict)
    action_space: Mapping[str, Any] = field(default_factory=dict)
    battle_controller_provenance: Mapping[str, Any] = field(default_factory=dict)
    wall_clock_seconds: float = 0.0
    worker_count: int = 1
    shard_count: int = 1
    shard_specs: tuple[Mapping[str, Any], ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": T065_EXPERIMENT_SCHEMA_ID,
            "schema_version": T065_EXPERIMENT_SCHEMA_VERSION,
            "arm": self.arm,
            "driver_seed": self.driver_seed,
            "requested_seed_count": self.requested_seed_count,
            "terminal_run_count": self.terminal_run_count,
            "truncated_run_count": self.truncated_run_count,
            "failed_run_count": self.failed_run_count,
            "selected_candidate_count": self.selected_candidate_count,
            "records": [record.to_dict() for record in self.records],
            "run_summaries": [dict(row) for row in self.run_summaries],
            "problems": list(self.problems),
            "approved_spec_commit": T065_APPROVED_SPEC_COMMIT,
            "frozen_config": T065ExperimentConfig().to_dict(),
            "simulator_identity": dict(self.simulator_identity),
            "action_space": dict(self.action_space),
            "battle_controller_provenance": dict(self.battle_controller_provenance),
            "wall_clock_seconds": self.wall_clock_seconds,
            "worker_count": self.worker_count,
            "shard_count": self.shard_count,
            "shard_specs": [dict(spec) for spec in self.shard_specs],
        }


def canonical_source_candidate(record: T065SourceState) -> dict[str, Any]:
    """Serialize the exact candidate identity used by frozen selection."""

    return {
        "screen_family": record.family,
        "simulator_seed": record.simulator_seed,
        "source_behavior_arm": record.source_arm,
        "public_action_trace": [dict(item) for item in record.action_trace],
        "source_decision_step_index": record.source_step_index,
        "public_state_identity": record.public_state_identity,
        "ordered_legal_action_identities": [
            dict(item) for item in record.legal_action_identities
        ],
    }


def canonical_source_selection_key(record: T065SourceState) -> tuple[str, bytes]:
    """Return the frozen SHA-256 digest and canonical JSON tie-break bytes."""

    payload = _canonical_json_bytes(canonical_source_candidate(record))
    digest = hashlib.sha256(T065_SELECTION_DOMAIN + payload).hexdigest()
    return digest, payload


def replay_equivalence_key(record: T065SourceState) -> tuple[Any, ...]:
    """Return the cross-arm replay-equivalence identity."""

    return (
        record.family,
        record.public_state_identity,
        tuple(_canonical_json_bytes(item) for item in record.legal_action_identities),
    )


def _source_candidate_provenance(candidate: Any) -> dict[str, Any]:
    replay_identity = {
        "family": candidate.family,
        "public_state_identity": candidate.public_state_identity,
        "ordered_legal_action_identities": [
            dict(item) for item in candidate.legal_action_identities
        ],
    }
    replay_identity_digest = hashlib.sha256(
        _canonical_json_bytes(replay_identity)
    ).hexdigest()
    return {
        "family": candidate.family,
        "split": candidate.split,
        "source_arm": candidate.source_arm,
        "simulator_seed": candidate.simulator_seed,
        "source_run_id": candidate.source_run_id,
        "source_step_index": candidate.source_step_index,
        "branch_identity": (
            f"{candidate.source_run_id}@step{candidate.source_step_index}"
        ),
        "public_state_identity": candidate.public_state_identity,
        "replay_identity_digest": replay_identity_digest,
    }


def _cross_split_failure_counts(
    details: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    by_family: dict[str, int] = defaultdict(int)
    by_split_pair: dict[str, int] = defaultdict(int)
    for detail in details:
        current = detail["current"]
        by_family[str(detail["family"])] += 1
        by_split_pair[f"{detail['previous']['split']}->{current['split']}"] += 1
    return {
        "total": len(details),
        "by_type": {"replay-equivalent-cross-split": len(details)},
        "by_family": dict(sorted(by_family.items())),
        "by_split_pair": dict(sorted(by_split_pair.items())),
    }


def _cross_split_failure_sort_key(detail: Mapping[str, Any]) -> tuple[Any, ...]:
    previous = detail["previous"]
    current = detail["current"]
    return (
        str(detail["failure_type"]),
        str(detail["family"]),
        str(detail["replay_identity_digest"]),
        str(previous["family"]),
        str(previous["public_state_identity"]),
        str(previous["split"]),
        str(previous["source_arm"]),
        int(previous["simulator_seed"]),
        str(previous["source_run_id"]),
        int(previous["source_step_index"]),
        str(previous["branch_identity"]),
        str(current["family"]),
        str(current["public_state_identity"]),
        str(current["split"]),
        str(current["source_arm"]),
        int(current["simulator_seed"]),
        str(current["source_run_id"]),
        int(current["source_step_index"]),
        str(current["branch_identity"]),
    )


def select_source_candidates(
    candidates: Iterable[Any],
) -> tuple[tuple[Any, str, bytes], ...]:
    """Select candidates while retaining only the candidate representation."""

    problems: list[str] = []
    best_by_replay: dict[tuple[Any, ...], Any] = {}
    split_by_replay: dict[tuple[Any, ...], str] = {}
    candidate_by_replay: dict[tuple[Any, ...], Any] = {}
    failure_details: list[dict[str, Any]] = []
    for candidate in candidates:
        if candidate.family not in T065_MANDATORY_FAMILIES:
            continue
        if not candidate.terminal:
            # The frozen source pool is built only from terminal source runs;
            # failed/truncated runs remain in the arm report but never enter
            # the selected-state cohort.
            continue
        if candidate.split not in T065_SPLITS:
            problems.append(f"unsupported candidate split {candidate.split!r}")
            continue
        if candidate.split != split_for_source_seed(candidate.simulator_seed):
            problems.append(
                f"candidate {candidate.source_run_id}: split does not match seed group"
            )
            continue
        identity = replay_equivalence_key(candidate)
        prior_split = split_by_replay.get(identity)
        if prior_split is not None and prior_split != candidate.split:
            prior_candidate = candidate_by_replay[identity]
            previous = _source_candidate_provenance(prior_candidate)
            current = _source_candidate_provenance(candidate)
            replay_identity_digest = current["replay_identity_digest"]
            failure_details.append(
                {
                    "failure_type": "replay-equivalent-cross-split",
                    "family": candidate.family,
                    "replay_identity_digest": replay_identity_digest,
                    "previous": previous,
                    "current": current,
                    "failure_id": (
                        "replay-equivalent-cross-split:"
                        f"{replay_identity_digest}:"
                        f"{previous['source_run_id']}@step"
                        f"{previous['source_step_index']}"
                        f"[{previous['split']}]->"
                        f"{current['source_run_id']}@step"
                        f"{current['source_step_index']}"
                        f"[{current['split']}]"
                    ),
                    "problem": (
                        "replay-equivalent candidate crosses splits: "
                        f"{current['source_run_id']}"
                    ),
                }
            )
            problems.append(
                f"replay-equivalent candidate crosses splits: {candidate.source_run_id}"
            )
            continue
        split_by_replay[identity] = candidate.split
        candidate_by_replay[identity] = candidate
        prior = best_by_replay.get(identity)
        if prior is None or canonical_source_selection_key(
            candidate
        ) < canonical_source_selection_key(prior):
            best_by_replay[identity] = candidate

    if problems:
        failure_details.sort(key=_cross_split_failure_sort_key)
        cross_split_problems = [detail["problem"] for detail in failure_details]
        non_cross_split_problems = sorted(
            problem
            for problem in problems
            if not problem.startswith("replay-equivalent candidate crosses splits:")
        )
        ordered_problems = non_cross_split_problems + cross_split_problems
        ordered_failure_ids = non_cross_split_problems + [
            detail["failure_id"] for detail in failure_details
        ]
        cross_split_count = len(failure_details)
        raise T065CaseD(
            "source-selection",
            ordered_problems,
            failure_ids=ordered_failure_ids if failure_details else (),
            failure_counts={
                "failure_count": len(ordered_problems),
                "replay_equivalent_cross_split": cross_split_count,
            },
            failure_details=failure_details,
            failure_detail_counts=_cross_split_failure_counts(failure_details),
        )

    buckets: dict[tuple[str, str], list[Any]] = defaultdict(list)
    for candidate in best_by_replay.values():
        buckets[(candidate.family, candidate.split)].append(candidate)
    selected: list[tuple[Any, str, bytes]] = []
    for family in T065_MANDATORY_FAMILIES:
        for split in T065_SPLITS:
            bucket = sorted(
                buckets[(family, split)],
                key=canonical_source_selection_key,
            )
            quota = T065_SPLIT_QUOTAS[split]
            if len(bucket) < quota:
                raise T065CaseD(
                    "source-selection",
                    [
                        f"{family}/{split} has {len(bucket)} candidates, "
                        f"requires {quota}"
                    ],
                )
            for rank, candidate in enumerate(bucket[:quota]):
                digest, payload = canonical_source_selection_key(candidate)
                selected.append((candidate, digest, payload))
                del rank
    return tuple(selected)


def select_source_states(
    candidates: Iterable[T065SourceState],
) -> tuple[T065SourceState, ...]:
    """Deduplicate and select exactly the frozen family/split quotas."""

    selected: list[T065SourceState] = []
    for candidate, digest, payload in select_source_candidates(candidates):
        selected.append(
            _replace_source_state(
                candidate,
                selected_state_index=len(selected),
                selection_digest=digest,
                selection_canonical_json=payload.decode("utf-8"),
            )
        )
    return tuple(selected)


def _t075_group_payload(candidate: Any) -> dict[str, Any]:
    return {
        "family": candidate.family,
        "public_state_identity": candidate.public_state_identity,
        "ordered_legal_action_identities": [
            dict(item) for item in candidate.legal_action_identities
        ],
    }


def _t075_group_digest(candidate: Any) -> tuple[str, bytes]:
    payload = _canonical_json_bytes(_t075_group_payload(candidate))
    return hashlib.sha256(T075_GROUP_DOMAIN + payload).hexdigest(), payload


def _t075_candidate_locator(candidate: Any) -> dict[str, Any]:
    return {
        "source_index": int(getattr(candidate, "source_index", -1)),
        "record_index": int(getattr(candidate, "record_index", -1)),
        "source_arm": str(candidate.source_arm),
        "simulator_seed": int(candidate.simulator_seed),
        "source_run_id": str(candidate.source_run_id),
        "source_step_index": int(candidate.source_step_index),
    }


def _t075_member_provenance(
    candidate: Any, selection_digest: str, payload: bytes
) -> dict[str, Any]:
    value = _source_candidate_provenance(candidate)
    value.update(
        {
            "source_index": int(getattr(candidate, "source_index", -1)),
            "record_index": int(getattr(candidate, "record_index", -1)),
            "selection_digest": selection_digest,
            "selection_candidate_sha256": hashlib.sha256(payload).hexdigest(),
        }
    )
    return value


def select_t075_source_candidates(
    candidates: Iterable[Any],
) -> tuple[tuple[tuple[Any, str, bytes], ...], dict[str, Any]]:
    """Assign one global owner per replay group before the frozen quotas.

    The input may be compact source locators as well as full
    :class:`T065SourceState` instances.  Only candidate identity and
    provenance are retained by the ownership audit; the caller rereads the
    selected locators to materialize complete states.
    """

    groups: dict[str, dict[str, Any]] = {}
    candidate_count = 0
    by_arm: dict[str, int] = defaultdict(int)
    by_family: dict[str, int] = defaultdict(int)
    by_split: dict[str, int] = defaultdict(int)
    for candidate in candidates:
        if candidate.family not in T065_MANDATORY_FAMILIES:
            continue
        if not candidate.terminal:
            continue
        if candidate.split not in T065_SPLITS:
            raise T065CaseD(
                "cohort-ownership",
                [f"unsupported candidate split {candidate.split!r}"],
            )
        if candidate.split != split_for_source_seed(candidate.simulator_seed):
            raise T065CaseD(
                "cohort-ownership",
                [
                    f"candidate {candidate.source_run_id}: split does not match "
                    "seed group"
                ],
            )
        selection_digest, selection_payload = canonical_source_selection_key(candidate)
        group_digest, group_payload = _t075_group_digest(candidate)
        group = groups.setdefault(
            group_digest,
            {
                "group_digest": group_digest,
                "group_identity": json.loads(group_payload.decode("utf-8")),
                "members": [],
            },
        )
        group["members"].append(
            {
                "candidate": candidate,
                "selection_digest": selection_digest,
                "selection_payload": selection_payload,
                "member_key": (selection_digest, selection_payload),
            }
        )
        candidate_count += 1
        by_arm[str(candidate.source_arm)] += 1
        by_family[str(candidate.family)] += 1
        by_split[str(candidate.split)] += 1

    audit_groups: list[dict[str, Any]] = []
    owners: list[tuple[Any, str, bytes]] = []
    owner_counts = {
        family: {split: 0 for split in T065_SPLITS}
        for family in T065_MANDATORY_FAMILIES
    }
    group_counts_by_family = {family: 0 for family in T065_MANDATORY_FAMILIES}
    group_counts_by_split = {split: 0 for split in T065_SPLITS}
    singleton_count = 0
    non_singleton_count = 0
    cross_split_count = 0
    excluded_count = 0
    group_size_histogram: dict[str, int] = defaultdict(int)
    for group_digest in sorted(groups):
        group = groups[group_digest]
        members = sorted(group["members"], key=lambda item: item["member_key"])
        distinct_keys = {item["member_key"] for item in members}
        if len(distinct_keys) != len(members):
            raise T065CaseD(
                "cohort-ownership",
                [f"exact full-key tie in replay group {group_digest}"],
                failure_ids=(f"replay-group-tie:{group_digest}",),
                failure_counts={"tied_groups": 1, "tied_members": len(members)},
            )
        family = str(members[0]["candidate"].family)
        splits = {str(item["candidate"].split) for item in members}
        group_counts_by_family[family] += 1
        for split in splits:
            group_counts_by_split[split] += 1
        if len(members) == 1:
            singleton_count += 1
        else:
            non_singleton_count += 1
            excluded_count += len(members) - 1
        if len(splits) > 1:
            cross_split_count += 1
        group_size_histogram[str(len(members))] += 1
        owner = members[0]
        owner_candidate = owner["candidate"]
        owner_counts[owner_candidate.family][owner_candidate.split] += 1
        owners.append(
            (owner_candidate, owner["selection_digest"], owner["selection_payload"])
        )
        audit_groups.append(
            {
                "group_digest": group_digest,
                "family": family,
                "public_state_identity": owner_candidate.public_state_identity,
                "ordered_legal_action_identities": [
                    dict(item) for item in owner_candidate.legal_action_identities
                ],
                "member_count": len(members),
                "cross_split": len(splits) > 1,
                "members": [
                    _t075_member_provenance(
                        item["candidate"],
                        item["selection_digest"],
                        item["selection_payload"],
                    )
                    for item in members
                ],
                "owner": _t075_member_provenance(
                    owner_candidate,
                    owner["selection_digest"],
                    owner["selection_payload"],
                ),
            }
        )

    buckets: dict[tuple[str, str], list[tuple[Any, str, bytes]]] = defaultdict(list)
    for owner in owners:
        buckets[(owner[0].family, owner[0].split)].append(owner)
    selected: list[tuple[Any, str, bytes]] = []
    for family in T065_MANDATORY_FAMILIES:
        for split in T065_SPLITS:
            bucket = sorted(
                buckets[(family, split)], key=lambda item: (item[1], item[2])
            )
            quota = T065_SPLIT_QUOTAS[split]
            if len(bucket) < quota:
                raise T065CaseD(
                    "cohort-ownership",
                    [f"{family}/{split} has {len(bucket)} owners, requires {quota}"],
                    failure_counts={
                        "available_owners": len(bucket),
                        "required_owners": quota,
                    },
                )
            selected.extend(bucket[:quota])

    return tuple(selected), {
        "schema_id": T075_OWNERSHIP_AUDIT_SCHEMA_ID,
        "schema_version": 1,
        "task_id": T075_TASK_ID,
        "selection_strategy_id": T075_SELECTION_STRATEGY_ID,
        "replay_identity": "(family, public_state_identity, ordered_legal_action_identities)",
        "group_domain": T075_GROUP_DOMAIN.decode("utf-8").rstrip("\n"),
        "candidate_domain_counts": {
            "total": candidate_count,
            "by_arm": dict(sorted(by_arm.items())),
            "by_family": {
                family: by_family[family] for family in T065_MANDATORY_FAMILIES
            },
            "by_split": {split: by_split[split] for split in T065_SPLITS},
        },
        "group_count": len(audit_groups),
        "singleton_group_count": singleton_count,
        "non_singleton_group_count": non_singleton_count,
        "cross_split_group_count": cross_split_count,
        "excluded_non_owner_count": excluded_count,
        "group_counts_by_family": group_counts_by_family,
        "group_counts_by_split": group_counts_by_split,
        "group_size_histogram": {
            key: group_size_histogram[key]
            for key in sorted(group_size_histogram, key=int)
        },
        "owner_counts_by_family_split": owner_counts,
        "groups": audit_groups,
        "selected_count": len(selected),
        "problems": [],
    }


def select_t075_source_states(
    candidates: Iterable[T065SourceState],
) -> tuple[tuple[T065SourceState, ...], dict[str, Any]]:
    """Select the leakage-safe T075 cohort and return its ownership audit."""

    selected, audit = select_t075_source_candidates(candidates)
    states = tuple(
        _replace_source_state(
            candidate,
            selected_state_index=index,
            selection_digest=digest,
            selection_canonical_json=payload.decode("utf-8"),
        )
        for index, (candidate, digest, payload) in enumerate(selected)
    )
    return states, audit


@dataclass(frozen=True)
class T065Normalizers:
    """Training-only CPU float32 population statistics."""

    state_mean: tuple[float, ...]
    state_std: tuple[float, ...]
    action_mean: tuple[float, ...]
    action_std: tuple[float, ...]
    fitted_state_count: int
    fitted_action_count: int

    def __post_init__(self) -> None:
        if len(self.state_mean) != NON_COMBAT_STATE_FEATURE_SIZE:
            raise ValueError("T065 state normalizer width is not 4737")
        if len(self.state_std) != NON_COMBAT_STATE_FEATURE_SIZE:
            raise ValueError("T065 state normalizer std width is not 4737")
        if len(self.action_mean) != NON_COMBAT_ACTION_FEATURE_SIZE:
            raise ValueError("T065 action normalizer width is not 92")
        if len(self.action_std) != NON_COMBAT_ACTION_FEATURE_SIZE:
            raise ValueError("T065 action normalizer std width is not 92")
        if (
            isinstance(self.fitted_state_count, bool)
            or not isinstance(self.fitted_state_count, int)
            or self.fitted_state_count <= 0
            or isinstance(self.fitted_action_count, bool)
            or not isinstance(self.fitted_action_count, int)
            or self.fitted_action_count <= 0
        ):
            raise ValueError("T065 normalizer fitted counts must be positive integers")
        if any(
            not math.isfinite(float(value))
            for value in (
                self.state_mean + self.state_std + self.action_mean + self.action_std
            )
        ):
            raise ValueError("T065 normalizer values must be finite")
        if any(float(value) < 1.0 for value in self.state_std + self.action_std):
            raise ValueError("T065 normalizer standard deviations must be >= 1")

    def to_dict(self) -> dict[str, Any]:
        return {
            "state_mean": list(self.state_mean),
            "state_std": list(self.state_std),
            "action_mean": list(self.action_mean),
            "action_std": list(self.action_std),
            "fitted_state_count": self.fitted_state_count,
            "fitted_action_count": self.fitted_action_count,
            "dtype": "torch.float32",
            "device": "cpu",
            "std_semantics": "population_unbiased_false_clamp_min_1.0",
        }

    def normalize_state(self, values: Sequence[float]) -> list[float]:
        if len(values) != NON_COMBAT_STATE_FEATURE_SIZE:
            raise ValueError("T065 state normalization width mismatch")
        return _normalize_values_float32(values, self.state_mean, self.state_std)

    def normalize_action(self, values: Sequence[float]) -> list[float]:
        if len(values) != NON_COMBAT_ACTION_FEATURE_SIZE:
            raise ValueError("T065 action normalization width mismatch")
        return _normalize_values_float32(values, self.action_mean, self.action_std)


def fit_training_normalizers(
    states: Sequence[T065SourceState],
    targets: Sequence[T065CounterfactualTarget],
) -> T065Normalizers:
    """Fit normalizers from exactly the 192 training states and their rows."""

    if not states:
        raise ValueError("T065 normalizer fit requires training states")
    if any(state.split != "train" for state in states):
        raise ValueError("T065 normalizers may use training states only")
    ordered_states = sorted(states, key=lambda state: state.selected_state_index)
    state_rows = [list(state.state_features) for state in ordered_states]
    state_indices = {state.selected_state_index for state in ordered_states}
    action_rows: list[list[float]] = []
    for state in ordered_states:
        for action_index in state.eligible_action_indices:
            target = next(
                (
                    row
                    for row in targets
                    if row.selected_state_index == state.selected_state_index
                    and row.legal_action_index == action_index
                ),
                None,
            )
            if target is None:
                raise T065CaseD(
                    "normalizer-fit",
                    [
                        f"missing training target row for state "
                        f"{state.selected_state_index} action {action_index}"
                    ],
                )
            del target
            action_rows.append(list(state.legal_action_features[action_index]))
    if len(state_indices) != len(state_rows):
        raise ValueError("T065 training states contain duplicate selected indices")
    torch = _require_torch()
    state_tensor = torch.tensor(state_rows, dtype=torch.float32, device="cpu")
    action_tensor = torch.tensor(action_rows, dtype=torch.float32, device="cpu")
    _validate_tensor_width(state_tensor, NON_COMBAT_STATE_FEATURE_SIZE, "state")
    _validate_tensor_width(action_tensor, NON_COMBAT_ACTION_FEATURE_SIZE, "action")
    state_mean = state_tensor.mean(dim=0)
    state_std = state_tensor.std(dim=0, unbiased=False).clamp_min(1.0)
    action_mean = action_tensor.mean(dim=0)
    action_std = action_tensor.std(dim=0, unbiased=False).clamp_min(1.0)
    return T065Normalizers(
        state_mean=tuple(float(value) for value in state_mean.tolist()),
        state_std=tuple(float(value) for value in state_std.tolist()),
        action_mean=tuple(float(value) for value in action_mean.tolist()),
        action_std=tuple(float(value) for value in action_std.tolist()),
        fitted_state_count=len(state_rows),
        fitted_action_count=len(action_rows),
    )


@dataclass(frozen=True)
class T065ModelRun:
    """One exact model-seed run and its validation-only selection metric."""

    model_seed: int
    model: Any = field(repr=False, compare=False)
    normalizers: T065Normalizers
    validation_mae: float
    training_steps: int = 1500
    checkpoint_path: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def score(
        self, state_features: Sequence[float], action_features: Sequence[float]
    ) -> float:
        """Score one already-encoded row with the frozen ranker."""

        return _model_score(
            self.model, self.normalizers, state_features, action_features
        )

    @property
    def checkpoint_artifact_id(self) -> str:
        value = self.metadata.get("checkpoint_artifact_id")
        return str(value) if value is not None else ""


def _build_ranker_module() -> Any:
    """Build the exact T065 two-tower action-conditioned ranker lazily."""

    torch = _require_torch()
    nn = torch.nn

    class _Ranker(nn.Module):
        def __init__(self) -> None:
            super().__init__()
            self.state_encoder = nn.Sequential(
                nn.Linear(NON_COMBAT_STATE_FEATURE_SIZE, 64),
                nn.ReLU(),
                nn.Linear(64, 64),
                nn.ReLU(),
            )
            self.action_encoder = nn.Sequential(
                nn.Linear(NON_COMBAT_ACTION_FEATURE_SIZE, 64),
                nn.ReLU(),
                nn.Linear(64, 64),
                nn.ReLU(),
            )
            self.joint_head = nn.Sequential(
                nn.Linear(128, 64),
                nn.ReLU(),
                nn.Linear(64, 1),
            )

        def forward(self, state: Any, action: Any) -> Any:
            state_embedding = self.state_encoder(state)
            action_embedding = self.action_encoder(action)
            return self.joint_head(
                torch.cat((state_embedding, action_embedding), dim=-1)
            )

    return _Ranker()


def train_non_combat_ranker(
    *,
    states: Sequence[T065SourceState],
    targets: Sequence[T065CounterfactualTarget],
    model_seed: int,
    normalizers: T065Normalizers | None = None,
    source_artifact_identity: Mapping[str, Any] | None = None,
    target_artifact_identity: Mapping[str, Any] | None = None,
    checkpoint_path: Path | None = None,
) -> T065ModelRun:
    """Train one model with the exact frozen 1500-step CPU procedure."""

    if model_seed not in T065_MODEL_SEEDS:
        raise ValueError(f"T065 model seed {model_seed} is not frozen")
    identity_problems = _checkpoint_artifact_identity_problems(
        source_artifact_identity, "source_artifact_identity"
    ) + _checkpoint_artifact_identity_problems(
        target_artifact_identity, "target_artifact_identity"
    )
    if identity_problems:
        raise ValueError("; ".join(identity_problems))
    selected_states = tuple(
        sorted(states, key=lambda state: state.selected_state_index)
    )
    training_states = tuple(
        state for state in selected_states if state.split == "train"
    )
    validation_states = tuple(
        state for state in selected_states if state.split == "validation"
    )
    if not training_states or not validation_states:
        raise ValueError("T065 training requires train and validation states")
    if normalizers is None:
        normalizers = fit_training_normalizers(training_states, targets)
    if normalizers.fitted_state_count != len(training_states):
        raise ValueError(
            "T065 normalizers do not describe the complete training states"
        )

    rows = _target_rows_for_states(training_states, targets)
    validation_rows = _target_rows_for_states(validation_states, targets)
    if not rows or not validation_rows:
        raise T065CaseD(
            "training-input", ["training or validation target rows are empty"]
        )
    torch = _require_torch()
    torch.set_num_threads(1)
    torch.manual_seed(model_seed)
    model = _build_ranker_module()
    model.train()
    optimizer = torch.optim.Adam(
        model.parameters(),
        lr=1e-3,
        betas=(0.9, 0.999),
        eps=1e-8,
        weight_decay=0.0,
        amsgrad=False,
    )
    loss_function = torch.nn.HuberLoss(delta=1.0, reduction="mean")
    generator = torch.Generator(device="cpu")
    generator.manual_seed(model_seed + 1_000_000)
    state_matrix = torch.tensor(
        [normalizers.normalize_state(state.state_features) for state, _, _ in rows],
        dtype=torch.float32,
        device="cpu",
    )
    action_matrix = torch.tensor(
        [
            normalizers.normalize_action(state.legal_action_features[action_index])
            for state, action_index, _ in rows
        ],
        dtype=torch.float32,
        device="cpu",
    )
    target_vector = torch.tensor(
        [target for _, _, target in rows], dtype=torch.float32, device="cpu"
    )
    for _step in range(1500):
        indices = torch.randint(0, len(rows), (64,), generator=generator)
        predictions = model(state_matrix[indices], action_matrix[indices]).reshape(-1)
        loss = loss_function(predictions, target_vector[indices])
        optimizer.zero_grad(set_to_none=False)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=10.0)
        optimizer.step()
    validation_mae = _evaluate_model_rows(model, normalizers, validation_rows)
    metadata = _checkpoint_metadata(
        model_seed=model_seed,
        normalizers=normalizers,
        source_artifact_identity=source_artifact_identity or {},
        target_artifact_identity=target_artifact_identity or {},
        split_provenance={
            "train": {
                "state_count": len(training_states),
                "target_row_count": len(rows),
            },
            "validation": {
                "state_count": len(validation_states),
                "target_row_count": len(validation_rows),
            },
            "heldout": {
                "state_count": sum(
                    state.split == "heldout" for state in selected_states
                ),
                "target_row_count": sum(
                    target.split == "heldout" for target in targets
                ),
            },
        },
        source_provenance={
            "artifact_identity": dict(source_artifact_identity or {}),
            "kind": "selected_public_source_states",
            "normal_information": True,
        },
        target_provenance={
            "artifact_identity": dict(target_artifact_identity or {}),
            "kind": "counterfactual_q_floor",
            "all_eligible_actions": True,
            "continuation_policy": "expert_non_combat_v1",
        },
    )
    run = T065ModelRun(
        model_seed=model_seed,
        model=model,
        normalizers=normalizers,
        validation_mae=validation_mae,
        metadata=metadata,
    )
    if checkpoint_path is not None:
        save_non_combat_checkpoint(run, checkpoint_path)
        object.__setattr__(run, "checkpoint_path", str(checkpoint_path))
        object.__setattr__(
            run,
            "metadata",
            {**metadata, "checkpoint_artifact_id": file_sha256(checkpoint_path)},
        )
    return run


def train_frozen_model_seeds(
    *,
    states: Sequence[T065SourceState],
    targets: Sequence[T065CounterfactualTarget],
    source_artifact_identity: Mapping[str, Any] | None = None,
    target_artifact_identity: Mapping[str, Any] | None = None,
    checkpoint_directory: Path | None = None,
) -> tuple[T065ModelRun, ...]:
    """Fit exactly model seeds 653001 and 653002 from shared normalizers."""

    identity_problems = _checkpoint_artifact_identity_problems(
        source_artifact_identity, "source_artifact_identity"
    ) + _checkpoint_artifact_identity_problems(
        target_artifact_identity, "target_artifact_identity"
    )
    if identity_problems:
        raise ValueError("; ".join(identity_problems))
    ordered_states = tuple(sorted(states, key=lambda state: state.selected_state_index))
    training_states = tuple(state for state in ordered_states if state.split == "train")
    validation_states = tuple(
        state for state in ordered_states if state.split == "validation"
    )
    heldout_states = tuple(
        state for state in ordered_states if state.split == "heldout"
    )
    expected_split_counts = (
        len(training_states),
        len(validation_states),
        len(heldout_states),
    )
    if expected_split_counts != (192, 64, 64):
        raise T065CaseD(
            "training-input",
            [
                "T065 training requires exactly 192/64/64 train/validation/heldout "
                f"states, got {expected_split_counts}"
            ],
        )
    normalizers = fit_training_normalizers(training_states, targets)
    runs = []
    for model_seed in T065_MODEL_SEEDS:
        path = (
            checkpoint_directory / f"model-{model_seed}.pt"
            if checkpoint_directory is not None
            else None
        )
        runs.append(
            train_non_combat_ranker(
                states=states,
                targets=targets,
                model_seed=model_seed,
                normalizers=normalizers,
                source_artifact_identity=source_artifact_identity,
                target_artifact_identity=target_artifact_identity,
                checkpoint_path=path,
            )
        )
    return tuple(runs)


def select_validation_checkpoint(runs: Sequence[T065ModelRun]) -> T065ModelRun:
    """Choose only by validation MAE, then lower model seed on exact ties."""

    if tuple(sorted(run.model_seed for run in runs)) != tuple(sorted(T065_MODEL_SEEDS)):
        raise ValueError("T065 checkpoint selection requires both frozen model seeds")
    for run in runs:
        schema_problems = _checkpoint_schema_problems(run.metadata)
        if schema_problems:
            raise ValueError("; ".join(schema_problems))
    if any(not math.isfinite(run.validation_mae) for run in runs):
        raise ValueError("T065 validation MAE must be finite")
    return min(runs, key=lambda run: (run.validation_mae, run.model_seed))


def save_non_combat_checkpoint(run: T065ModelRun, path: Path) -> None:
    """Persist model weights plus the complete frozen input provenance."""

    torch = _require_torch()
    path.parent.mkdir(parents=True, exist_ok=True)
    metadata = dict(run.metadata)
    metadata.update(
        {
            "checkpoint_schema_id": T065_CHECKPOINT_SCHEMA_ID,
            "checkpoint_format_version": 1,
            "model_seed": run.model_seed,
            "training_steps": run.training_steps,
            "validation_q_floor_mae": run.validation_mae,
            "normalizers": run.normalizers.to_dict(),
        }
    )
    schema_problems = _checkpoint_schema_problems(metadata)
    if schema_problems:
        raise ValueError("; ".join(schema_problems))
    torch.save(
        {
            "checkpoint_schema_id": T065_CHECKPOINT_SCHEMA_ID,
            "checkpoint_format_version": 1,
            "model_seed": run.model_seed,
            "training_steps": run.training_steps,
            "validation_q_floor_mae": run.validation_mae,
            "metadata": metadata,
            "normalizers": run.normalizers.to_dict(),
            "state_dict": run.model.state_dict(),
        },
        path,
    )


def load_non_combat_checkpoint(path: Path) -> T065ModelRun:
    """Load a checkpoint strictly; schema mismatches fail closed."""

    torch = _require_torch()
    try:
        raw = torch.load(path, map_location="cpu", weights_only=True)
    except TypeError:
        raw = torch.load(path, map_location="cpu")
    if not isinstance(raw, Mapping):
        raise ValueError("T065 checkpoint root must be an object")
    if raw.get("checkpoint_schema_id") != T065_CHECKPOINT_SCHEMA_ID:
        raise ValueError("unsupported T065 checkpoint schema")
    if raw.get("checkpoint_format_version") != 1:
        raise ValueError("unsupported T065 checkpoint format version")
    metadata = raw.get("metadata")
    if not isinstance(metadata, Mapping):
        raise ValueError("T065 checkpoint metadata is missing")
    schema_problems = _checkpoint_schema_problems(metadata)
    if schema_problems:
        raise ValueError("; ".join(schema_problems))
    if raw.get("model_seed") != metadata.get("model_seed"):
        raise ValueError("T065 checkpoint root and metadata model seeds do not match")
    if raw.get("training_steps") != metadata.get("training_steps"):
        raise ValueError(
            "T065 checkpoint root and metadata training steps do not match"
        )
    if raw.get("validation_q_floor_mae") != metadata.get("validation_q_floor_mae"):
        raise ValueError(
            "T065 checkpoint root and metadata validation metrics do not match"
        )
    if raw.get("normalizers") != metadata.get("normalizers"):
        raise ValueError("T065 checkpoint normalizer copies do not match")
    normalizers = _normalizers_from_dict(raw.get("normalizers"))
    model_seed = raw.get("model_seed")
    if isinstance(model_seed, bool) or not isinstance(model_seed, int):
        raise ValueError("T065 checkpoint model seed is invalid")
    if model_seed not in T065_MODEL_SEEDS:
        raise ValueError("T065 checkpoint model seed is not frozen")
    model = _build_ranker_module()
    state_dict = raw.get("state_dict")
    if not isinstance(state_dict, Mapping):
        raise ValueError("T065 checkpoint state_dict is missing")
    model.load_state_dict(state_dict, strict=True)
    model.eval()
    validation_mae = float(metadata.get("validation_q_floor_mae", float("nan")))
    if not math.isfinite(validation_mae):
        raise ValueError("T065 checkpoint validation MAE is not finite")
    loaded_metadata = dict(metadata)
    loaded_metadata["checkpoint_artifact_id"] = file_sha256(path)
    return T065ModelRun(
        model_seed=model_seed,
        model=model,
        normalizers=normalizers,
        validation_mae=validation_mae,
        training_steps=int(metadata.get("training_steps", 1500)),
        checkpoint_path=str(path),
        metadata=loaded_metadata,
    )


class LearnedNonCombatPolicy:
    """Normal-information learned policy with explicit expert fallback."""

    name = T065_LEARNED_POLICY_NAME
    version = 1
    supported_families = frozenset(T065_MANDATORY_FAMILIES)

    def __init__(
        self,
        model_run: T065ModelRun,
        *,
        fallback: ExpertNonCombatDriver | None = None,
    ) -> None:
        self.model_run = model_run
        self.fallback = fallback or ExpertNonCombatDriver(seed=T065_STAGE6_DRIVER_SEED)
        self.decision_events: list[dict[str, Any]] = []

    @property
    def provenance_config(self) -> Mapping[str, Any]:
        return {
            "seed": T065_STAGE6_DRIVER_SEED,
            "version": self.version,
            "supported_screen_families": list(T065_MANDATORY_FAMILIES),
            "fallback_policy": self.fallback.name,
            "fallback_provenance": {
                "name": self.fallback.name,
                "version": self.fallback.version,
                "seed": T065_STAGE6_DRIVER_SEED,
            },
            "checkpoint_schema_id": T065_CHECKPOINT_SCHEMA_ID,
            "checkpoint_artifact_id": self.model_run.checkpoint_artifact_id,
            "model_seed": self.model_run.model_seed,
            "model_input_schema": non_combat_model_input_schema(),
            "information_regime": "normal_public_policy",
            "expert_action_or_score_is_model_input": False,
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
                    "mandatory": False,
                    "status": "unsupported_fallback",
                    "action_index": decision.legal_action_index,
                    "reason": decision.reason,
                }
            )
            return PolicyDecision(
                legal_action_index=decision.legal_action_index,
                score=decision.score,
                reason=f"{self.name}:expert_fallback:{family}",
            )
        try:
            encoded = encode_non_combat_decision_context(context)
            scores = {
                index: self.model_run.score(
                    encoded.state_features, encoded.action_features[index]
                )
                for index in encoded.eligible_action_indices
            }
            selected = min(
                scores,
                key=lambda index: (-scores[index], index),
            )
        except (RuntimeError, ValueError) as exc:
            self.decision_events.append(
                {
                    "screen_family": family,
                    "mandatory": True,
                    "status": "learned_failure",
                    "error": str(exc),
                }
            )
            raise
        self.decision_events.append(
            {
                "screen_family": family,
                "mandatory": True,
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


def build_learned_non_combat_controller(
    model_run: T065ModelRun,
) -> PolicyController:
    """Wrap the learned public policy in the canonical controller boundary."""

    return PolicyController(
        LearnedNonCombatPolicy(
            model_run,
            fallback=ExpertNonCombatDriver(seed=T065_STAGE6_DRIVER_SEED),
        )
    )


def screen_family(screen_state: str) -> str:
    """Map the simulator screen label to the frozen T065 family vocabulary."""

    normalized = str(screen_state).upper()
    aliases = {
        "MAP": "MAP_SCREEN",
        "MAP_SCREEN": "MAP_SCREEN",
        "REST": "REST_ROOM",
        "REST_ROOM": "REST_ROOM",
        "REWARDS": "REWARDS",
        "TREASURE": "TREASURE_ROOM",
        "TREASURE_ROOM": "TREASURE_ROOM",
    }
    return aliases.get(normalized, normalized)


def _validate_mandatory_family_projection(
    family: str, state_features: Sequence[float]
) -> None:
    """Require the existing T033 screen positions to identify the family."""

    expected_feature = {
        "MAP_SCREEN": "run_position.screen.map",
        "REST_ROOM": "run_position.screen.rest",
        "REWARDS": "run_position.screen.rewards",
        "TREASURE_ROOM": "run_position.screen.treasure",
    }.get(family)
    if expected_feature is None:
        return
    names = {
        name: index
        for index, name in enumerate(PUBLIC_CONTEXT_MODEL_INPUT_FEATURE_NAMES)
    }
    context_features = state_features[NON_COMBAT_SNAPSHOT_FEATURE_SIZE:]
    if len(context_features) != NON_COMBAT_CONTEXT_FEATURE_SIZE:
        raise T065CaseD(
            "public-input",
            [f"{family}: public-context feature width is not 103"],
        )
    if context_features[names[expected_feature]] != 1.0:
        raise T065CaseD(
            "public-input",
            [f"{family}: T033 screen position {expected_feature!r} is not 1.0"],
        )
    if context_features[names["run_position.screen.other"]] != 0.0:
        raise T065CaseD(
            "public-input",
            [f"{family}: T033 screen.other position is not 0.0"],
        )


def collect_source_arm(
    adapter_factory: Callable[[], Any],
    *,
    source_arm: str,
    seeds: Iterable[int] | None = None,
    driver_seed: int = T065_SOURCE_DRIVER_SEED,
    max_steps: int = T065_MAX_STEPS,
    record_sink: Callable[[T065SourceState], None] | None = None,
) -> T065SourceArmReport:
    """Collect one fixed source arm through ``execute_controlled_run``.

    The factory must create an isolated authoritative simulator adapter for
    each run.  The observer records only public decision fields; native raw
    snapshots and checkpoints are intentionally not serialized.
    """

    if source_arm not in {"stochastic_non_combat_v1", "expert_non_combat_v1"}:
        raise ValueError(f"unsupported T065 source arm {source_arm!r}")
    if driver_seed != T065_SOURCE_DRIVER_SEED:
        raise ValueError("T065 source driver seed is frozen at 654001")
    if max_steps != T065_MAX_STEPS:
        raise ValueError("T065 source step cap is frozen at 500")
    run_seeds = tuple(
        inclusive_range(T065_SOURCE_SEED_RANGE) if seeds is None else tuple(seeds)
    )
    if run_seeds != tuple(sorted(run_seeds)) or len(set(run_seeds)) != len(run_seeds):
        raise ValueError("T065 source seeds must be a sorted unique explicit sequence")
    if any(seed not in inclusive_range(T065_SOURCE_SEED_RANGE) for seed in run_seeds):
        raise ValueError("T065 source seed is outside the frozen range")
    started = time.perf_counter()
    simulator_identity = lightspeed_source_identity_dict()
    action_space = frozen_action_space().to_dict()
    battle_controller_provenance = frozen_battle_provenance()
    candidates: list[T065SourceState] = []
    candidate_count = 0
    run_summaries: list[Mapping[str, Any]] = []
    problems: list[str] = []
    terminal_runs = 0
    truncated_runs = 0
    failed_runs = 0
    for seed in run_seeds:
        adapter = adapter_factory()
        driver_class = (
            StochasticNonCombatDriver
            if source_arm == "stochastic_non_combat_v1"
            else ExpertNonCombatDriver
        )
        non_combat = driver_class(seed=driver_seed)
        battle = build_frozen_battle_controller()
        controller = RoutedRunController(
            battle=battle,
            non_combat=PolicyController(non_combat),
        )
        observed: list[T065SourceState] = []
        public_trace: list[Mapping[str, Any]] = []

        def observe(
            snapshot: SimulatorSnapshot,
            actions: Sequence[SimulatorAction],
            context: DecisionContext,
            step_index: int,
        ) -> None:
            del snapshot
            if (
                context.screen_state == "BATTLE"
                or context.screen_state.upper() == "BATTLE"
            ):
                return
            family = screen_family(context.screen_state)
            if family not in T065_MANDATORY_FAMILIES:
                return
            encoded = encode_non_combat_decision_context(context)
            _validate_mandatory_family_projection(family, encoded.state_features)
            legal_identities = tuple(
                dict(identity)
                for identity in action_identity_dicts_for_actions(actions)
            )
            state_identity = public_state_identity(
                family=family,
                state_features=encoded.state_features,
                public_run_context=context.public_run_context,
                legal_action_identities=legal_identities,
            )
            observed.append(
                T065SourceState(
                    selected_state_index=-1,
                    family=family,
                    split=split_for_source_seed(seed),
                    simulator_seed=seed,
                    source_arm=source_arm,
                    source_run_id=f"{source_arm}:{seed}",
                    source_step_index=step_index,
                    source_floor=_number_or_none(
                        context.tactical_state, "scalars", "floor_num"
                    ),
                    source_act=_number_or_none(
                        context.tactical_state, "scalars", "act"
                    ),
                    screen_state=context.screen_state,
                    snapshot_features=tuple(context.snapshot_features),
                    public_context_features=tuple(
                        encoded.state_features[NON_COMBAT_SNAPSHOT_FEATURE_SIZE:]
                    ),
                    state_features=encoded.state_features,
                    legal_action_features=encoded.action_features,
                    legal_action_kinds=tuple(context.legal_action_kinds),
                    eligible_action_indices=encoded.eligible_action_indices,
                    legal_action_identities=legal_identities,
                    action_trace=tuple(dict(item) for item in public_trace),
                    public_state_identity=state_identity,
                    public_context_status=encoded.public_context_status,
                    public_run_context=dict(context.public_run_context),
                    source_controller_provenance={},
                    source_non_combat_provenance={},
                    source_battle_provenance={},
                )
            )

        def after_transition(step: ControlledRunStep) -> None:
            # The complete portable trace includes battle and non-combat
            # actions.  Omitting battle actions would replay a different run.
            public_trace.append(dict(step.chosen_action_identity))
            if step.controller_role == "non_combat_driver" and observed:
                last = observed[-1]
                if last.source_step_index == step.step_index:
                    observed[-1] = _replace_source_state(
                        last,
                        behavior_action_index=step.chosen_action_index,
                        behavior_action_identity=dict(step.chosen_action_identity),
                        source_controller_provenance=dict(
                            step.provenance.to_dict() if step.provenance else {}
                        ),
                        source_non_combat_provenance=dict(
                            step.provenance.to_dict() if step.provenance else {}
                        ),
                    )

        try:
            run = execute_controlled_run(
                adapter,
                controller,
                seed=seed,
                max_steps=max_steps,
                action_space=frozen_action_space(),
                before_decision=observe,
                after_transition=after_transition,
            )
        except (RuntimeError, ValueError) as exc:
            failed_runs += 1
            problems.append(f"seed {seed}: {exc}")
            run_summaries.append(
                {
                    "source_run_id": f"{source_arm}:{seed}",
                    "simulator_seed": seed,
                    "source_arm": source_arm,
                    "terminal": False,
                    "outcome": "ERROR",
                    "step_count": None,
                    "terminal_floor": None,
                    "problems": [str(exc)],
                    "controller_provenance": {},
                    "action_space": action_space,
                }
            )
            continue
        if run.terminal:
            terminal_runs += 1
        elif len(run.steps) >= max_steps:
            truncated_runs += 1
        if run.problems:
            failed_runs += 1
            problems.extend(f"seed {seed}: {problem}" for problem in run.problems)
        terminal_floor = _raw_number(run.final_raw, "floor_num", "floor")
        terminal_status = str(run.outcome)
        for candidate in observed:
            finalized = _replace_source_state(
                candidate,
                terminal=run.terminal,
                terminal_status=terminal_status,
                terminal_floor=terminal_floor,
                source_controller_provenance=dict(run.controller_provenance),
                source_battle_provenance=dict(
                    _nested_provenance(run.controller_provenance, "battle")
                ),
            )
            if record_sink is None:
                candidates.append(finalized)
            else:
                record_sink(finalized)
            candidate_count += 1
        run_summaries.append(
            {
                "source_run_id": f"{source_arm}:{seed}",
                "simulator_seed": seed,
                "source_arm": source_arm,
                "terminal": run.terminal,
                "outcome": run.outcome,
                "step_count": len(run.steps),
                "terminal_floor": terminal_floor,
                "problems": list(run.problems),
                "controller_provenance": dict(run.controller_provenance),
                "action_space": action_space,
                "simulator_cost": _controlled_run_cost(run),
            }
        )
    return T065SourceArmReport(
        arm=source_arm,
        driver_seed=driver_seed,
        requested_seed_count=len(run_seeds),
        terminal_run_count=terminal_runs,
        truncated_run_count=truncated_runs,
        failed_run_count=failed_runs,
        selected_candidate_count=candidate_count,
        records=tuple(candidates),
        run_summaries=tuple(run_summaries),
        problems=tuple(problems),
        simulator_identity=simulator_identity,
        action_space=action_space,
        battle_controller_provenance=battle_controller_provenance,
        wall_clock_seconds=time.perf_counter() - started,
    )


def collect_source_arm_sharded(
    adapter_factory: Callable[[], Any],
    *,
    source_arm: str,
    worker_count: int = T065_MAX_WORKERS,
) -> T065SourceArmReport:
    """Collect a small/legacy arm using the frozen shard shape.

    This compatibility API aggregates every source record in memory.  The
    frozen full-scale T065 collection path must call
    :func:`collect_source_arm_sharded_to_path` instead.
    """

    _validate_workers(worker_count)
    shard_specs = source_shard_ranges(arm=source_arm, worker_count=worker_count)

    def collect(spec: Mapping[str, Any]) -> T065SourceArmReport:
        return collect_source_arm(
            adapter_factory,
            source_arm=source_arm,
            seeds=range(int(spec["seed_start"]), int(spec["seed_end"]) + 1),
        )

    started = time.perf_counter()
    with ThreadPoolExecutor(
        max_workers=min(worker_count, len(shard_specs))
    ) as executor:
        futures = [executor.submit(collect, spec) for spec in shard_specs]
        shard_reports = [future.result() for future in futures]
    shard_evidence: list[Mapping[str, Any]] = []
    for spec, report in zip(shard_specs, shard_reports, strict=True):
        shard_evidence.append(
            {
                **dict(spec),
                "requested_seed_count": report.requested_seed_count,
                "terminal_run_count": report.terminal_run_count,
                "truncated_run_count": report.truncated_run_count,
                "failed_run_count": report.failed_run_count,
                "candidate_count": report.selected_candidate_count,
                "wall_clock_seconds": report.wall_clock_seconds,
                "problems": list(report.problems),
            }
        )
    return T065SourceArmReport(
        arm=source_arm,
        driver_seed=T065_SOURCE_DRIVER_SEED,
        requested_seed_count=sum(
            report.requested_seed_count for report in shard_reports
        ),
        terminal_run_count=sum(report.terminal_run_count for report in shard_reports),
        truncated_run_count=sum(report.truncated_run_count for report in shard_reports),
        failed_run_count=sum(report.failed_run_count for report in shard_reports),
        selected_candidate_count=sum(
            report.selected_candidate_count for report in shard_reports
        ),
        records=tuple(record for report in shard_reports for record in report.records),
        run_summaries=tuple(
            summary for report in shard_reports for summary in report.run_summaries
        ),
        problems=tuple(
            problem for report in shard_reports for problem in report.problems
        ),
        simulator_identity=dict(shard_reports[0].simulator_identity),
        action_space=dict(shard_reports[0].action_space),
        battle_controller_provenance=dict(
            shard_reports[0].battle_controller_provenance
        ),
        wall_clock_seconds=time.perf_counter() - started,
        worker_count=worker_count,
        shard_count=len(shard_specs),
        shard_specs=tuple(shard_evidence),
    )


@dataclass(frozen=True)
class _T065SourceShardFragment:
    """A bounded shard result: metadata plus a streamed record fragment."""

    shard_index: int
    report: T065SourceArmReport
    fragment_path: Path


def _validate_source_shard_report(
    spec: Mapping[str, Any],
    report: T065SourceArmReport,
    *,
    source_arm: str,
    simulator_identity: Mapping[str, Any],
    action_space: Mapping[str, Any],
    battle_controller_provenance: Mapping[str, Any],
) -> None:
    expected_start = int(spec["seed_start"])
    expected_end = int(spec["seed_end"])
    expected_seeds = set(range(expected_start, expected_end + 1))
    summary_seeds = {
        summary.get("simulator_seed")
        for summary in report.run_summaries
        if isinstance(summary, Mapping)
    }
    if (
        report.arm != source_arm
        or report.driver_seed != T065_SOURCE_DRIVER_SEED
        or report.requested_seed_count != 16
        or report.terminal_run_count != 16
        or report.truncated_run_count != 0
        or report.failed_run_count != 0
        or report.problems
        or report.records
        or len(report.run_summaries) != 16
        or summary_seeds != expected_seeds
        or dict(report.simulator_identity) != dict(simulator_identity)
        or dict(report.action_space) != dict(action_space)
        or dict(report.battle_controller_provenance)
        != dict(battle_controller_provenance)
    ):
        raise ValueError(
            f"T065 source shard {spec['shard_index']} evidence is incomplete or mismatched"
        )
    for summary in report.run_summaries:
        if (
            not isinstance(summary, Mapping)
            or summary.get("source_arm") != source_arm
            or not summary.get("terminal")
            or summary.get("problems")
        ):
            raise ValueError(
                f"T065 source shard {spec['shard_index']} run evidence is invalid"
            )


def collect_source_arm_sharded_to_path(
    adapter_factory: Callable[[], Any],
    output_path: Path,
    *,
    source_arm: str,
    worker_count: int = T065_MAX_WORKERS,
) -> T065SourceArmReport:
    """Collect and atomically write a source arm without aggregate records.

    Workers stream each finalized record into a private shard fragment.  The
    returned report keeps only small summaries; the final source JSON is
    published after every shard has passed its frozen evidence checks.
    """

    if worker_count != T065_MAX_WORKERS:
        raise ValueError(
            "T065 bounded source collection requires exactly "
            f"{T065_MAX_WORKERS} workers"
        )
    _validate_workers(worker_count)
    if source_arm not in {"stochastic_non_combat_v1", "expert_non_combat_v1"}:
        raise ValueError(f"unsupported T065 source arm {source_arm!r}")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.exists():
        raise FileExistsError(
            f"T065 source output already exists; refusing to reuse or overwrite: {output_path}"
        )
    shard_specs = source_shard_ranges(arm=source_arm, worker_count=worker_count)
    simulator_identity = lightspeed_source_identity_dict()
    action_space = frozen_action_space().to_dict()
    battle_controller_provenance = frozen_battle_provenance()
    started = time.perf_counter()

    with TemporaryDirectory(
        prefix=f".{output_path.name}.shards-", dir=output_path.parent
    ) as temporary_directory:
        fragment_directory = Path(temporary_directory)

        def collect_shard(spec: Mapping[str, Any]) -> _T065SourceShardFragment:
            shard_index = int(spec["shard_index"])
            fragment_path = (
                fragment_directory / f"shard-{shard_index:02d}.records.jsonl"
            )
            try:
                with fragment_path.open("w", encoding="utf-8", newline="\n") as stream:

                    def sink(record: T065SourceState) -> None:
                        stream.write(
                            json.dumps(record.to_dict(), sort_keys=True) + "\n"
                        )

                    report = collect_source_arm(
                        adapter_factory,
                        source_arm=source_arm,
                        seeds=range(int(spec["seed_start"]), int(spec["seed_end"]) + 1),
                        record_sink=sink,
                    )
                    stream.flush()
            except BaseException:
                fragment_path.unlink(missing_ok=True)
                raise
            return _T065SourceShardFragment(shard_index, report, fragment_path)

        fragments: dict[int, _T065SourceShardFragment] = {}
        futures = {}
        try:
            with ThreadPoolExecutor(
                max_workers=min(worker_count, len(shard_specs))
            ) as executor:
                futures = {
                    executor.submit(collect_shard, spec): spec for spec in shard_specs
                }
                for future in as_completed(futures):
                    result = future.result()
                    fragments[result.shard_index] = result
                    del futures[future]
        except BaseException:
            for future in futures:
                future.cancel()
            raise
        if set(fragments) != set(range(len(shard_specs))):
            raise ValueError("T065 source shard result is missing")

        shard_evidence: list[Mapping[str, Any]] = []
        run_summaries: list[Mapping[str, Any]] = []
        total_requested = 0
        total_terminal = 0
        total_truncated = 0
        total_failed = 0
        total_candidates = 0
        for spec in shard_specs:
            result = fragments[int(spec["shard_index"])]
            report = result.report
            _validate_source_shard_report(
                spec,
                report,
                source_arm=source_arm,
                simulator_identity=simulator_identity,
                action_space=action_space,
                battle_controller_provenance=battle_controller_provenance,
            )
            shard_evidence.append(
                {
                    **dict(spec),
                    "requested_seed_count": report.requested_seed_count,
                    "terminal_run_count": report.terminal_run_count,
                    "truncated_run_count": report.truncated_run_count,
                    "failed_run_count": report.failed_run_count,
                    "candidate_count": report.selected_candidate_count,
                    "wall_clock_seconds": report.wall_clock_seconds,
                    "problems": list(report.problems),
                }
            )
            run_summaries.extend(report.run_summaries)
            total_requested += report.requested_seed_count
            total_terminal += report.terminal_run_count
            total_truncated += report.truncated_run_count
            total_failed += report.failed_run_count
            total_candidates += report.selected_candidate_count

        final_temporary_path = fragment_directory / output_path.name
        top_level = {
            "action_space": action_space,
            "approved_spec_commit": T065_APPROVED_SPEC_COMMIT,
            "arm": source_arm,
            "battle_controller_provenance": battle_controller_provenance,
            "driver_seed": T065_SOURCE_DRIVER_SEED,
            "failed_run_count": total_failed,
            "frozen_config": T065ExperimentConfig().to_dict(),
            "problems": [],
            "records": None,
            "run_summaries": None,
            "schema_id": T065_EXPERIMENT_SCHEMA_ID,
            "schema_version": T065_EXPERIMENT_SCHEMA_VERSION,
            "selected_candidate_count": total_candidates,
            "shard_count": len(shard_specs),
            "shard_specs": shard_evidence,
            "simulator_identity": simulator_identity,
            "terminal_run_count": total_terminal,
            "truncated_run_count": total_truncated,
            "wall_clock_seconds": time.perf_counter() - started,
            "worker_count": worker_count,
            "requested_seed_count": total_requested,
        }
        with final_temporary_path.open("w", encoding="utf-8", newline="\n") as stream:
            stream.write("{\n")
            keys = tuple(sorted(top_level))
            for key_index, key in enumerate(keys):
                if key_index:
                    stream.write(",\n")
                stream.write(json.dumps(key) + ": ")
                if key == "records":
                    stream.write("[\n")
                    record_index = 0
                    for spec in shard_specs:
                        fragment = fragments[int(spec["shard_index"])].fragment_path
                        with fragment.open("r", encoding="utf-8") as source:
                            expected_start = int(spec["seed_start"])
                            expected_end = int(spec["seed_end"])
                            shard_record_count = 0
                            for line_number, line in enumerate(source, start=1):
                                if not line.strip():
                                    raise ValueError(
                                        f"T065 source shard {spec['shard_index']} "
                                        f"record {line_number} is empty"
                                    )
                                try:
                                    raw_record = json.loads(line)
                                except json.JSONDecodeError as exc:
                                    raise ValueError(
                                        f"T065 source shard {spec['shard_index']} "
                                        f"record {line_number} is invalid JSON"
                                    ) from exc
                                if not isinstance(raw_record, Mapping):
                                    raise ValueError(
                                        f"T065 source shard {spec['shard_index']} "
                                        f"record {line_number} is not an object"
                                    )
                                try:
                                    state = T065SourceState.from_dict(raw_record)
                                except (TypeError, ValueError) as exc:
                                    raise ValueError(
                                        f"T065 source shard {spec['shard_index']} "
                                        f"record {line_number} is invalid"
                                    ) from exc
                                if (
                                    state.source_arm != source_arm
                                    or not expected_start
                                    <= state.simulator_seed
                                    <= expected_end
                                    or not state.terminal
                                    or state.selected_state_index != -1
                                    or not state.terminal_status
                                    or state.terminal_status == "UNKNOWN"
                                ):
                                    raise ValueError(
                                        f"T065 source shard {spec['shard_index']} "
                                        f"record {line_number} has invalid source semantics"
                                    )
                                if record_index:
                                    stream.write(",\n")
                                stream.write(
                                    "  " + line.rstrip("\n").replace("\n", "\n  ")
                                )
                                record_index += 1
                                shard_record_count += 1
                            expected_record_count = fragments[
                                int(spec["shard_index"])
                            ].report.selected_candidate_count
                            if shard_record_count != expected_record_count:
                                raise ValueError(
                                    f"T065 source shard {spec['shard_index']} "
                                    "record count does not match shard report"
                                )
                    if record_index != total_candidates:
                        raise ValueError(
                            "T065 source record count does not match shards"
                        )
                    stream.write("\n]")
                elif key == "run_summaries":
                    stream.write(json.dumps(run_summaries, indent=2, sort_keys=True))
                else:
                    stream.write(json.dumps(top_level[key], indent=2, sort_keys=True))
            stream.write("\n}\n")
        final_temporary_path.replace(output_path)

    return T065SourceArmReport(
        arm=source_arm,
        driver_seed=T065_SOURCE_DRIVER_SEED,
        requested_seed_count=total_requested,
        terminal_run_count=total_terminal,
        truncated_run_count=total_truncated,
        failed_run_count=total_failed,
        selected_candidate_count=total_candidates,
        records=(),
        run_summaries=tuple(run_summaries),
        problems=(),
        simulator_identity=simulator_identity,
        action_space=action_space,
        battle_controller_provenance=battle_controller_provenance,
        wall_clock_seconds=time.perf_counter() - started,
        worker_count=worker_count,
        shard_count=len(shard_specs),
        shard_specs=tuple(shard_evidence),
    )


def replay_source_state(
    adapter: CheckpointingSimulatorAdapter,
    state: T065SourceState,
) -> tuple[
    SimulatorSnapshot, tuple[SimulatorAction, ...], DecisionContext, SimulatorCheckpoint
]:
    """Replay a portable action trace and capture one process-local checkpoint."""

    if not adapter.supports_checkpoint_restore:
        raise T065CaseD(
            "replay",
            ["adapter does not expose exact checkpoint capture/restore"],
        )
    snapshot = adapter.reset(seed=state.simulator_seed)
    public_history: list[dict[str, Any]] = []
    for trace_index, identity in enumerate(state.action_trace):
        actions = tuple(adapter.legal_actions(snapshot))
        pre_projection = read_native_public_projection(adapter, snapshot)
        pre_context = build_public_run_context(
            snapshot.raw,
            actions,
            projection=pre_projection,
            history=public_history,
        )
        try:
            action_index = find_action_index_by_identity(actions, identity)
        except ValueError as exc:
            raise T065CaseD(
                "replay",
                [f"state {state.selected_state_index} trace {trace_index}: {exc}"],
            ) from exc
        transition = adapter.step(actions[action_index])
        if transition.terminal:
            raise T065CaseD(
                "replay",
                [f"state {state.selected_state_index}: trace reached terminal early"],
            )
        post_projection = read_native_public_projection(adapter, transition.snapshot)
        post_context = build_public_run_context(
            transition.snapshot.raw,
            (),
            projection=post_projection,
            history=public_history,
            include_candidates=False,
        )
        history_entry = build_public_history_entry(
            history_index=len(public_history),
            step_index=trace_index,
            pre_context=pre_context,
            post_context=post_context,
            selected_action_index=action_index,
        )
        public_history = append_public_history_entry(public_history, history_entry)
        snapshot = transition.snapshot
    actions = tuple(adapter.legal_actions(snapshot))
    projection = read_native_public_projection(adapter, snapshot)
    context_payload = build_public_run_context(
        snapshot.raw,
        actions,
        projection=projection,
        history=public_history,
    )
    context = build_decision_context(
        snapshot.raw,
        actions,
        frozen_action_space(),
        public_run_context=context_payload,
    )
    encoded = encode_non_combat_decision_context(context)
    _validate_mandatory_family_projection(state.family, encoded.state_features)
    identities = tuple(
        dict(item) for item in action_identity_dicts_for_actions(actions)
    )
    actual_identity = public_state_identity(
        family=state.family,
        state_features=encoded.state_features,
        public_run_context=context_payload,
        legal_action_identities=identities,
    )
    if actual_identity != state.public_state_identity:
        raise T065CaseD(
            "replay",
            [f"state {state.selected_state_index}: public state identity mismatch"],
        )
    if identities != tuple(dict(item) for item in state.legal_action_identities):
        raise T065CaseD(
            "replay",
            [f"state {state.selected_state_index}: legal action identity mismatch"],
        )
    checkpoint = adapter.capture_checkpoint(snapshot)
    return snapshot, actions, context, checkpoint


def generate_counterfactual_targets(
    adapter_factory: Callable[[], CheckpointingSimulatorAdapter],
    states: Sequence[T065SourceState],
    *,
    max_steps: int = T065_MAX_STEPS,
    require_contiguous_indices: bool = True,
    source_artifact_identity: Mapping[str, Any] | None = None,
    simulator_identity: Mapping[str, Any] | None = None,
) -> T065TargetTable:
    """Evaluate every eligible action and every split-specific continuation seed."""

    if max_steps != T065_MAX_STEPS:
        raise ValueError("T065 continuation step cap is frozen at 500")
    generation_started = time.perf_counter()
    ordered_states = tuple(sorted(states, key=lambda state: state.selected_state_index))
    targets: list[T065CounterfactualTarget] = []
    expert_action_indices: dict[int, int] = {}
    for state in ordered_states:
        if state.source_floor is None:
            raise T065CaseD(
                "counterfactual-targets",
                [f"state {state.selected_state_index}: source floor is missing"],
            )
        adapter = adapter_factory()
        _snapshot, actions, context, checkpoint = replay_source_state(adapter, state)
        encoded = encode_non_combat_decision_context(context)
        if tuple(encoded.eligible_action_indices) != tuple(
            state.eligible_action_indices
        ):
            raise T065CaseD(
                "replay",
                [f"state {state.selected_state_index}: eligible action mismatch"],
            )
        expert_action_indices[state.selected_state_index] = (
            _expert_comparison_action_index(context, state.simulator_seed)
        )
        continuation_seeds = continuation_seeds_for_split(state.split)
        for action_index in state.eligible_action_indices:
            row_started = time.perf_counter()
            terminal_floors: list[float] = []
            terminal_acts: list[float | None] = []
            terminal_statuses: list[str] = []
            terminal_current_hps: list[float | None] = []
            terminal_max_hps: list[float | None] = []
            terminal_golds: list[float | None] = []
            terminal_potion_counts: list[float | None] = []
            cost: dict[str, float] = defaultdict(float)
            for continuation_seed in continuation_seeds:
                restored_snapshot = adapter.restore_checkpoint(checkpoint)
                restored_actions = tuple(adapter.legal_actions(restored_snapshot))
                if tuple(
                    dict(item)
                    for item in action_identity_dicts_for_actions(restored_actions)
                ) != tuple(
                    dict(item) for item in action_identity_dicts_for_actions(actions)
                ):
                    raise T065CaseD(
                        "counterfactual-targets",
                        [
                            f"state {state.selected_state_index}: restore legal-action "
                            "identity mismatch"
                        ],
                    )
                restored_features = encode_lightspeed_battle_snapshot(
                    restored_snapshot.raw
                )
                if tuple(restored_features) != tuple(context.snapshot_features):
                    raise T065CaseD(
                        "counterfactual-targets",
                        [
                            f"state {state.selected_state_index}: restore public "
                            "snapshot mismatch"
                        ],
                    )
                restored_projection = read_native_public_projection(
                    adapter, restored_snapshot
                )
                restored_history = context.public_run_context.get("history", [])
                if not isinstance(restored_history, Sequence) or isinstance(
                    restored_history, (str, bytes)
                ):
                    raise T065CaseD(
                        "counterfactual-targets",
                        [
                            f"state {state.selected_state_index}: replay history "
                            "is malformed during restore verification"
                        ],
                    )
                restored_public_context = build_public_run_context(
                    restored_snapshot.raw,
                    restored_actions,
                    projection=restored_projection,
                    history=[
                        item for item in restored_history if isinstance(item, Mapping)
                    ],
                )
                if restored_public_context != context.public_run_context:
                    raise T065CaseD(
                        "counterfactual-targets",
                        [
                            f"state {state.selected_state_index}: restore public "
                            "context mismatch"
                        ],
                    )
                forced = adapter.step(restored_actions[action_index])
                cost["simulator_steps"] += 1.0
                if forced.terminal:
                    final_raw = forced.snapshot.raw
                    continuation_run = None
                else:
                    continuation_controller = RoutedRunController(
                        battle=build_frozen_battle_controller(),
                        non_combat=PolicyController(
                            ExpertNonCombatDriver(seed=continuation_seed)
                        ),
                    )
                    continuation_run = execute_controlled_run(
                        _ContinuationAdapter(adapter, forced.snapshot),
                        continuation_controller,
                        seed=state.simulator_seed,
                        max_steps=max_steps,
                        action_space=frozen_action_space(),
                    )
                    if continuation_run.problems or not continuation_run.terminal:
                        problems = list(continuation_run.problems)
                        if not continuation_run.terminal:
                            problems.append("continuation truncated before terminal")
                        raise T065CaseD(
                            "counterfactual-targets",
                            [
                                f"state {state.selected_state_index} action "
                                f"{action_index} continuation {continuation_seed}: "
                                + "; ".join(problems)
                            ],
                        )
                    final_raw = continuation_run.final_raw
                    cost["simulator_steps"] += float(len(continuation_run.steps))
                    _add_search_cost(cost, continuation_run)
                terminal_floor = _raw_number(final_raw, "floor_num", "floor")
                if terminal_floor is None:
                    raise T065CaseD(
                        "counterfactual-targets",
                        [
                            f"state {state.selected_state_index} action "
                            f"{action_index}: terminal floor is missing"
                        ],
                    )
                terminal_floors.append(terminal_floor)
                terminal_act = _raw_number(final_raw, "act")
                if terminal_act is None:
                    raise T065CaseD(
                        "counterfactual-targets",
                        [
                            f"state {state.selected_state_index} action "
                            f"{action_index}: terminal Act is missing"
                        ],
                    )
                terminal_status = final_raw.get("outcome")
                if not isinstance(terminal_status, str) or not terminal_status:
                    raise T065CaseD(
                        "counterfactual-targets",
                        [
                            f"state {state.selected_state_index} action "
                            f"{action_index}: terminal status is missing"
                        ],
                    )
                terminal_acts.append(terminal_act)
                terminal_statuses.append(terminal_status)
                terminal_current_hps.append(_terminal_current_hp(final_raw))
                terminal_max_hps.append(_terminal_max_hp(final_raw))
                terminal_golds.append(_raw_number(final_raw, "gold"))
                terminal_potion_counts.append(_terminal_potion_count(final_raw))
            source_floor = float(state.source_floor)
            q_floor = sum(
                max(0.0, floor - source_floor) for floor in terminal_floors
            ) / len(terminal_floors)
            targets.append(
                T065CounterfactualTarget(
                    selected_state_index=state.selected_state_index,
                    state_identity=state.state_identity,
                    family=state.family,
                    split=state.split,
                    legal_action_index=action_index,
                    legal_action_identity=dict(
                        state.legal_action_identities[action_index]
                    ),
                    continuation_seeds=continuation_seeds,
                    terminal_floors=tuple(terminal_floors),
                    terminal_acts=tuple(terminal_acts),
                    terminal_statuses=tuple(terminal_statuses),
                    terminal_current_hps=tuple(terminal_current_hps),
                    terminal_max_hps=tuple(terminal_max_hps),
                    terminal_golds=tuple(terminal_golds),
                    terminal_potion_counts=tuple(terminal_potion_counts),
                    q_floor=q_floor,
                    simulator_cost=dict(cost),
                    wall_clock_seconds=time.perf_counter() - row_started,
                )
            )
    table = T065TargetTable(
        states=ordered_states,
        targets=tuple(targets),
        source_artifact_identity=dict(source_artifact_identity or {}),
        simulator_identity=dict(simulator_identity or {}),
        execution_evidence={
            "worker_count": 1,
            "shard_count": 1,
            "state_count": len(ordered_states),
            "target_count": len(targets),
            "wall_clock_seconds": time.perf_counter() - generation_started,
        },
        expert_action_indices=expert_action_indices,
        expert_action_provenance={
            "name": "expert_non_combat_v1",
            "version": 1,
            "seed": T065_SOURCE_DRIVER_SEED,
            "reset_rule": "reset_for_run(simulator_seed) at replayed source state",
            "purpose": "heldout comparison only; never a training feature or target",
        },
    )
    table.validate_complete(require_contiguous_indices=require_contiguous_indices)
    return table


def generate_counterfactual_targets_sharded(
    adapter_factory: Callable[[], CheckpointingSimulatorAdapter],
    states: Sequence[T065SourceState],
    *,
    worker_count: int = T065_MAX_WORKERS,
    max_steps: int = T065_MAX_STEPS,
    source_artifact_identity: Mapping[str, Any] | None = None,
    simulator_identity: Mapping[str, Any] | None = None,
) -> T065TargetTable:
    """Generate Stage 2 in exact 20-state shards with at most 16 workers."""

    _validate_workers(worker_count)
    ordered_states = tuple(sorted(states, key=lambda state: state.selected_state_index))
    if len(ordered_states) != 320:
        raise T065CaseD(
            "target-sharding",
            [
                f"Stage 2 requires exactly 320 selected states, got {len(ordered_states)}"
            ],
        )
    specs = target_shard_ranges(worker_count=worker_count)
    started = time.perf_counter()

    def generate(spec: Mapping[str, Any]) -> T065TargetTable:
        start = int(spec["selected_state_start"])
        end = int(spec["selected_state_end"])
        shard_states = tuple(
            state
            for state in ordered_states
            if start <= state.selected_state_index <= end
        )
        if len(shard_states) != 20:
            raise T065CaseD(
                "target-sharding",
                [f"Stage 2 shard {spec['shard_index']} does not own 20 states"],
            )
        table = generate_counterfactual_targets(
            adapter_factory,
            shard_states,
            max_steps=max_steps,
            require_contiguous_indices=False,
            source_artifact_identity=source_artifact_identity,
            simulator_identity=simulator_identity,
        )
        # The shard has globally indexed states, so validate rows without
        # imposing the full-table contiguous-index invariant.
        table.validate_complete(require_contiguous_indices=False)
        return table

    with ThreadPoolExecutor(max_workers=min(worker_count, len(specs))) as executor:
        futures = [executor.submit(generate, spec) for spec in specs]
        shards = [future.result() for future in futures]
    shard_evidence = tuple(
        {
            **dict(spec),
            "state_count": len(table.states),
            "target_count": len(table.targets),
            "wall_clock_seconds": table.execution_evidence.get(
                "wall_clock_seconds", 0.0
            ),
        }
        for spec, table in zip(specs, shards, strict=True)
    )
    targets = tuple(
        target
        for table in sorted(
            shards,
            key=lambda table: min(state.selected_state_index for state in table.states),
        )
        for target in table.targets
    )
    merged = T065TargetTable(
        states=ordered_states,
        targets=targets,
        source_artifact_identity=dict(source_artifact_identity or {}),
        simulator_identity=dict(simulator_identity or {}),
        expert_action_indices={
            index: action_index
            for table in shards
            for index, action_index in table.expert_action_indices.items()
        },
        expert_action_provenance=(
            dict(shards[0].expert_action_provenance) if shards else {}
        ),
        execution_evidence={
            "worker_count": worker_count,
            "shard_count": len(specs),
            "wall_clock_seconds": time.perf_counter() - started,
            "shards": [dict(evidence) for evidence in shard_evidence],
        },
    )
    merged.validate_complete()
    return merged


@dataclass(frozen=True)
class T065HeldoutStateResult:
    """Action-value comparison for one held-out source state."""

    selected_state_index: int
    family: str
    split: str
    source_behavior: str
    screen_state: str
    source_act: float | None
    source_floor: float | None
    public_state_identity: str
    source_behavior_action_index: int | None
    source_behavior_action_identity: Mapping[str, Any]
    model_seed: int
    model_action_index: int
    model_action_identity: Mapping[str, Any]
    expert_action_index: int
    expert_action_identity: Mapping[str, Any]
    model_q_floor: float
    expert_q_floor: float
    delta: float
    predicted_action_values: Mapping[str, float] = field(default_factory=dict)
    empirical_best_action_indices: tuple[int, ...] = ()
    empirical_action_values: Mapping[str, float] = field(default_factory=dict)
    rank_correlation: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "selected_state_index": self.selected_state_index,
            "family": self.family,
            "split": self.split,
            "source_behavior": self.source_behavior,
            "screen_state": self.screen_state,
            "source_act": self.source_act,
            "source_floor": self.source_floor,
            "public_state_identity": self.public_state_identity,
            "source_behavior_action_index": self.source_behavior_action_index,
            "source_behavior_action_identity": dict(
                self.source_behavior_action_identity
            ),
            "model_seed": self.model_seed,
            "model_action_index": self.model_action_index,
            "model_action_identity": dict(self.model_action_identity),
            "expert_action_index": self.expert_action_index,
            "expert_action_identity": dict(self.expert_action_identity),
            "model_q_floor": self.model_q_floor,
            "expert_q_floor": self.expert_q_floor,
            "delta": self.delta,
            "predicted_action_values": dict(self.predicted_action_values),
            "empirical_best_action_indices": list(self.empirical_best_action_indices),
            "empirical_action_values": dict(self.empirical_action_values),
            "rank_correlation": self.rank_correlation,
        }


def _average_ranks(values: Sequence[float]) -> tuple[float, ...]:
    """Return one-based average ranks, preserving deterministic tie handling."""

    ordered = sorted(enumerate(values), key=lambda item: (item[1], item[0]))
    ranks = [0.0] * len(values)
    cursor = 0
    while cursor < len(ordered):
        end = cursor + 1
        while end < len(ordered) and ordered[end][1] == ordered[cursor][1]:
            end += 1
        rank = (cursor + 1 + end) / 2.0
        for index, _value in ordered[cursor:end]:
            ranks[index] = rank
        cursor = end
    return tuple(ranks)


def _spearman_rank_correlation(
    predicted: Sequence[float], empirical: Sequence[float]
) -> float | None:
    """Compute Spearman correlation when both action rankings are defined."""

    if len(predicted) != len(empirical) or len(predicted) < 2:
        return None
    predicted_ranks = _average_ranks(predicted)
    empirical_ranks = _average_ranks(empirical)
    predicted_mean = statistics.fmean(predicted_ranks)
    empirical_mean = statistics.fmean(empirical_ranks)
    covariance = sum(
        (left - predicted_mean) * (right - empirical_mean)
        for left, right in zip(predicted_ranks, empirical_ranks, strict=True)
    )
    predicted_ss = sum((value - predicted_mean) ** 2 for value in predicted_ranks)
    empirical_ss = sum((value - empirical_mean) ** 2 for value in empirical_ranks)
    if predicted_ss == 0.0 or empirical_ss == 0.0:
        return None
    result = covariance / math.sqrt(predicted_ss * empirical_ss)
    return result if math.isfinite(result) else None


@dataclass(frozen=True)
class T065HeldoutReport:
    """Frozen Stage 5 held-out gate result."""

    selected_model_seed: int
    selected_validation_mae: float
    model_results: Mapping[str, tuple[T065HeldoutStateResult, ...]]
    aggregate_mean_delta: float
    median_delta: float
    family_mean_deltas: Mapping[str, float]
    p_positive: float
    non_selected_model_mean_delta: float
    passed: bool
    problems: tuple[str, ...] = ()
    schema_id: str = T065_STAGE5_REPORT_SCHEMA_ID
    schema_version: int = 1

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "schema_version": self.schema_version,
            "selected_model_seed": self.selected_model_seed,
            "selected_validation_mae": self.selected_validation_mae,
            "model_results": {
                str(seed): [result.to_dict() for result in results]
                for seed, results in self.model_results.items()
            },
            "aggregate_mean_delta": self.aggregate_mean_delta,
            "median_delta": self.median_delta,
            "family_mean_deltas": dict(self.family_mean_deltas),
            "p_positive": self.p_positive,
            "non_selected_model_mean_delta": self.non_selected_model_mean_delta,
            "passed": self.passed,
            "problems": list(self.problems),
        }


def evaluate_model_on_split(
    model_run: T065ModelRun,
    table: T065TargetTable,
    *,
    split: str,
    expert_action_indices: Mapping[int, int] | None = None,
) -> tuple[T065HeldoutStateResult, ...]:
    """Score every eligible action and compare against an explicit expert row."""

    if split not in T065_SPLITS:
        raise ValueError(f"unsupported T065 evaluation split {split!r}")
    table.validate_complete()
    expert_actions = dict(table.expert_action_indices)
    expert_actions.update(expert_action_indices or {})
    results: list[T065HeldoutStateResult] = []
    for state in table.states:
        if state.split != split:
            continue
        rows_by_action = {
            row.legal_action_index: row
            for row in table.rows_for_state(state.selected_state_index)
        }
        if state.selected_state_index not in expert_actions:
            if (
                state.behavior_action_index is None
                or state.source_arm != "expert_non_combat_v1"
            ):
                raise T065CaseD(
                    "heldout-evaluation",
                    [
                        f"state {state.selected_state_index}: explicit expert "
                        "comparison action is missing"
                    ],
                )
            expert_index = state.behavior_action_index
        else:
            expert_index = expert_actions[state.selected_state_index]
        if expert_index not in rows_by_action:
            raise T065CaseD(
                "heldout-evaluation",
                [
                    f"state {state.selected_state_index}: expert action "
                    f"{expert_index} is not an eligible target row"
                ],
            )
        predicted: dict[int, float] = {}
        for action_index in state.eligible_action_indices:
            predicted[action_index] = model_run.score(
                state.state_features,
                state.legal_action_features[action_index],
            )
        model_index = min(predicted, key=lambda index: (-predicted[index], index))
        empirical_values = {
            index: rows_by_action[index].q_floor
            for index in state.eligible_action_indices
        }
        best_value = max(empirical_values.values())
        best_actions = tuple(
            index
            for index in state.eligible_action_indices
            if empirical_values[index] == best_value
        )
        ordered_predicted = tuple(
            predicted[index] for index in state.eligible_action_indices
        )
        ordered_empirical = tuple(
            empirical_values[index] for index in state.eligible_action_indices
        )
        results.append(
            T065HeldoutStateResult(
                selected_state_index=state.selected_state_index,
                family=state.family,
                split=split,
                source_behavior=state.source_arm,
                screen_state=state.screen_state,
                source_act=state.source_act,
                source_floor=state.source_floor,
                public_state_identity=state.public_state_identity,
                source_behavior_action_index=state.behavior_action_index,
                source_behavior_action_identity=dict(state.behavior_action_identity),
                model_seed=model_run.model_seed,
                model_action_index=model_index,
                model_action_identity=dict(state.legal_action_identities[model_index]),
                expert_action_index=expert_index,
                expert_action_identity=dict(
                    state.legal_action_identities[expert_index]
                ),
                model_q_floor=empirical_values[model_index],
                expert_q_floor=empirical_values[expert_index],
                delta=empirical_values[model_index] - empirical_values[expert_index],
                predicted_action_values={
                    str(index): value for index, value in predicted.items()
                },
                empirical_best_action_indices=best_actions,
                empirical_action_values={
                    str(index): empirical_values[index]
                    for index in state.eligible_action_indices
                },
                rank_correlation=_spearman_rank_correlation(
                    ordered_predicted, ordered_empirical
                ),
            )
        )
    expected = 64 if split == "heldout" else None
    if expected is not None and len(results) != expected:
        raise T065CaseD(
            "heldout-evaluation",
            [f"heldout state count {len(results)} does not match 64"],
        )
    if split == "heldout":
        family_counts = {
            family: sum(result.family == family for result in results)
            for family in T065_MANDATORY_FAMILIES
        }
        if any(count != 16 for count in family_counts.values()):
            raise T065CaseD(
                "heldout-evaluation",
                [f"heldout family counts are not 16 each: {family_counts!r}"],
            )
    return tuple(results)


def heldout_bootstrap_probability(
    results: Sequence[T065HeldoutStateResult],
    *,
    replicates: int = T065_BOOTSTRAP_REPLICATES,
    seed: int = T065_STAGE5_BOOTSTRAP_SEED,
) -> float:
    """Compute the exact family-stratified Stage 5 positive probability."""

    if replicates != T065_BOOTSTRAP_REPLICATES or seed != T065_STAGE5_BOOTSTRAP_SEED:
        raise ValueError("T065 Stage 5 bootstrap inputs are frozen")
    by_family: dict[str, list[float]] = defaultdict(list)
    for result in results:
        by_family[result.family].append(float(result.delta))
    if tuple(sorted(by_family)) != tuple(sorted(T065_MANDATORY_FAMILIES)):
        raise T065CaseD("heldout-bootstrap", ["heldout family set is incomplete"])
    if any(len(by_family[family]) != 16 for family in T065_MANDATORY_FAMILIES):
        raise T065CaseD(
            "heldout-bootstrap", ["each heldout family must have 16 states"]
        )
    if any(
        not math.isfinite(delta) for values in by_family.values() for delta in values
    ):
        raise T065CaseD("heldout-bootstrap", ["heldout paired delta is non-finite"])
    rng = random.Random(seed)
    positive = 0
    for _ in range(replicates):
        sampled = [
            rng.choice(by_family[family])
            for family in T065_MANDATORY_FAMILIES
            for _index in range(16)
        ]
        if statistics.fmean(sampled) > 0.0:
            positive += 1
    return positive / replicates


def build_stage5_report(
    model_runs: Sequence[T065ModelRun],
    table: T065TargetTable,
    *,
    expert_action_indices: Mapping[int, int] | None = None,
) -> T065HeldoutReport:
    """Freeze validation selection, then apply every Stage 5 condition."""

    selected = select_validation_checkpoint(model_runs)
    results = {
        str(run.model_seed): evaluate_model_on_split(
            run,
            table,
            split="heldout",
            expert_action_indices=expert_action_indices,
        )
        for run in model_runs
    }
    selected_results = results[str(selected.model_seed)]
    deltas = [result.delta for result in selected_results]
    family_means = {
        family: statistics.fmean(
            result.delta for result in selected_results if result.family == family
        )
        for family in T065_MANDATORY_FAMILIES
    }
    non_selected = next(
        run for run in model_runs if run.model_seed != selected.model_seed
    )
    non_selected_mean = statistics.fmean(
        result.delta for result in results[str(non_selected.model_seed)]
    )
    p_positive = heldout_bootstrap_probability(selected_results)
    problems: list[str] = []
    passed = True
    conditions = (
        (statistics.fmean(deltas) > 0.0, "aggregate mean delta is not positive"),
        (statistics.median(deltas) >= 0.0, "median delta is negative"),
        (
            sum(value >= 0.0 for value in family_means.values()) >= 3,
            "fewer than three family mean deltas are non-negative",
        ),
        (p_positive >= 0.90, "Stage 5 bootstrap probability is below 0.90"),
        (
            non_selected_mean >= 0.0,
            "non-selected model seed has a negative aggregate delta",
        ),
    )
    for condition, message in conditions:
        if not condition:
            passed = False
            problems.append(message)
    return T065HeldoutReport(
        selected_model_seed=selected.model_seed,
        selected_validation_mae=selected.validation_mae,
        model_results=results,
        aggregate_mean_delta=statistics.fmean(deltas),
        median_delta=statistics.median(deltas),
        family_mean_deltas=family_means,
        p_positive=p_positive,
        non_selected_model_mean_delta=non_selected_mean,
        passed=passed,
        problems=tuple(problems),
    )


@dataclass(frozen=True)
class T065Coverage:
    """Frozen Stage 6 learned-control coverage counts."""

    D: int
    L: int
    M: int
    F: int

    def __post_init__(self) -> None:
        if any(
            isinstance(value, bool) or not isinstance(value, int) or value < 0
            for value in (self.D, self.L, self.M, self.F)
        ):
            raise ValueError("T065 coverage counts must be non-negative integers")

    @property
    def learned_coverage(self) -> float:
        return self.L / self.D if self.D else 0.0

    @property
    def mandatory_failure_rate(self) -> float:
        return self.F / self.M if self.M else 0.0

    @property
    def passed(self) -> bool:
        return (
            self.D > 0
            and self.M > 0
            and self.learned_coverage >= 0.60
            and self.mandatory_failure_rate <= 0.01
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "D": self.D,
            "L": self.L,
            "M": self.M,
            "F": self.F,
            "learned_coverage": self.learned_coverage,
            "mandatory_failure_rate": self.mandatory_failure_rate,
            "passed": self.passed,
        }


def compute_learned_coverage(
    decision_events: Sequence[Mapping[str, Any]],
) -> T065Coverage:
    """Apply the exact Stage 6 D/L/M/F classification to policy events."""

    D = L = M = F = 0
    for event in decision_events:
        if bool(event.get("battle")):
            continue
        D += 1
        family = str(event.get("screen_family", ""))
        if family not in T065_MANDATORY_FAMILIES:
            continue
        M += 1
        status = str(event.get("status", ""))
        if status == "learned_success":
            L += 1
        elif status == "learned_failure":
            F += 1
        elif status == "unsupported_fallback":
            # Unsupported fallback is intentionally counted in D only.
            continue
        else:
            F += 1
    return T065Coverage(D=D, L=L, M=M, F=F)


def matched_bootstrap_probability(
    deltas: Sequence[float],
    *,
    replicates: int = T065_BOOTSTRAP_REPLICATES,
    seed: int = T065_STAGE6_BOOTSTRAP_SEED,
) -> float:
    """Compute the exact Stage 6 matched-seed bootstrap probability."""

    if replicates != T065_BOOTSTRAP_REPLICATES or seed != T065_STAGE6_BOOTSTRAP_SEED:
        raise ValueError("T065 Stage 6 bootstrap inputs are frozen")
    if len(deltas) != 256:
        raise T065CaseD(
            "stage6-bootstrap", ["Stage 6 paired cohort must have 256 seeds"]
        )
    if any(not math.isfinite(float(delta)) for delta in deltas):
        raise T065CaseD("stage6-bootstrap", ["Stage 6 paired delta is non-finite"])
    rng = random.Random(seed)
    positive = 0
    for _ in range(replicates):
        sampled = [deltas[rng.randrange(len(deltas))] for _index in range(256)]
        if statistics.fmean(sampled) > 0.0:
            positive += 1
    return positive / replicates


@dataclass(frozen=True)
class T065Stage6Report:
    """Matched complete-run outcome and coverage gate."""

    paired_terminal_floor_deltas: tuple[float, ...]
    learned_terminal_floor_mean: float
    expert_terminal_floor_mean: float
    mean_terminal_floor_delta: float
    p_positive: float
    coverage: T065Coverage
    learned_act2_entry_count: int
    expert_act2_entry_count: int
    controller_error_count: int
    truncation_count: int
    valid: bool
    passed: bool
    problems: tuple[str, ...] = ()
    execution_evidence: Mapping[str, Any] = field(default_factory=dict)
    schema_id: str = T065_STAGE6_REPORT_SCHEMA_ID
    schema_version: int = 1

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "schema_version": self.schema_version,
            "paired_terminal_floor_deltas": list(self.paired_terminal_floor_deltas),
            "learned_terminal_floor_mean": self.learned_terminal_floor_mean,
            "expert_terminal_floor_mean": self.expert_terminal_floor_mean,
            "mean_terminal_floor_delta": self.mean_terminal_floor_delta,
            "p_positive": self.p_positive,
            "coverage": self.coverage.to_dict(),
            "learned_act2_entry_count": self.learned_act2_entry_count,
            "expert_act2_entry_count": self.expert_act2_entry_count,
            "controller_error_count": self.controller_error_count,
            "truncation_count": self.truncation_count,
            "valid": self.valid,
            "passed": self.passed,
            "problems": list(self.problems),
            "execution_evidence": dict(self.execution_evidence),
        }


def build_stage6_report(
    paired_rows: Sequence[Mapping[str, Any]],
    coverage: T065Coverage,
    *,
    execution_evidence: Mapping[str, Any] | None = None,
    arm_reports: Sequence["T065CompleteRunArmReport"] | None = None,
) -> T065Stage6Report:
    """Validate the complete 256-seed matched cohort and apply the gate."""

    problems: list[str] = []
    if arm_reports is not None:
        expected_arm_names = {"stochastic", "expert", "learned"}
        reports_by_arm = {report.arm: report for report in arm_reports}
        if (
            set(reports_by_arm) != expected_arm_names
            or len(reports_by_arm) != 3
            or len(reports_by_arm) != len(arm_reports)
        ):
            problems.append("Stage 6 does not contain exactly three required arms")
        expected_arm_seeds = inclusive_range(T065_STAGE6_SEED_RANGE)
        expected_simulator_identity = lightspeed_source_identity_dict()
        expected_action_space = frozen_action_space().to_dict()
        expected_battle_provenance = frozen_battle_provenance()
        for arm in sorted(expected_arm_names):
            report = reports_by_arm.get(arm)
            if report is None:
                continue
            if (
                _mapping_or_empty(report.simulator_identity)
                != expected_simulator_identity
            ):
                problems.append(f"Stage 6 {arm} arm simulator identity is not exact")
            if _mapping_or_empty(report.action_space) != expected_action_space:
                problems.append(f"Stage 6 {arm} arm action-space is not exact")
            if report.driver_seed != T065_STAGE6_DRIVER_SEED:
                problems.append(f"Stage 6 {arm} arm driver seed is not 654002")
            expected_driver_name = {
                "stochastic": "stochastic_non_combat_v1",
                "expert": "expert_non_combat_v1",
                "learned": T065_LEARNED_POLICY_NAME,
            }[arm]
            driver = _mapping_or_empty(report.driver_provenance)
            driver_config = _mapping_or_empty(driver.get("config"))
            if arm == "learned":
                fallback = _mapping_or_empty(driver_config.get("fallback_provenance"))
                driver_seed_valid = (
                    driver_config.get("seed") == T065_STAGE6_DRIVER_SEED
                    and fallback.get("seed") == T065_STAGE6_DRIVER_SEED
                    and fallback.get("name") == "expert_non_combat_v1"
                    and fallback.get("version") == 1
                )
            else:
                driver_seed_valid = driver_config.get("seed") == T065_STAGE6_DRIVER_SEED
            if (
                driver.get("name") != expected_driver_name
                or driver.get("version") != 1
                or not isinstance(driver.get("config"), Mapping)
                or not driver_seed_valid
            ):
                problems.append(f"Stage 6 {arm} arm driver provenance is not frozen")
            controller = _mapping_or_empty(report.controller_provenance)
            controller_config = _mapping_or_empty(controller.get("config"))
            if (
                controller.get("kind") != "routed_run"
                or not isinstance(controller_config, Mapping)
                or controller_config.get("battle") != expected_battle_provenance
            ):
                problems.append(f"Stage 6 {arm} arm battle provenance is not exact")
            non_combat = (
                controller_config.get("non_combat", {})
                if isinstance(controller_config, Mapping)
                else {}
            )
            non_combat_config = (
                non_combat.get("config", {})
                if isinstance(non_combat, Mapping)
                and isinstance(non_combat.get("config"), Mapping)
                else {}
            )
            if (
                not isinstance(non_combat, Mapping)
                or non_combat.get("kind") != "decision_policy"
                or non_combat.get("name") != expected_driver_name
                or non_combat_config.get("information_regime") != "normal_public_policy"
                or controller.get("name")
                != f"{T065_FROZEN_BATTLE_CONTROLLER_NAME}+{expected_driver_name}"
            ):
                problems.append(
                    f"Stage 6 {arm} arm non-combat controller provenance is not exact"
                )
            if non_combat_config and isinstance(driver.get("config"), Mapping):
                comparable_config = dict(non_combat_config)
                comparable_config.pop("policy_class", None)
                comparable_config.pop("information_regime", None)
                if comparable_config != driver_config:
                    problems.append(
                        f"Stage 6 {arm} arm driver/controller config diverges"
                    )
            if tuple(sorted(report.requested_seeds)) != expected_arm_seeds:
                problems.append(
                    f"Stage 6 {arm} arm does not request exactly 651001..651256"
                )
            if len(report.rows) != len(expected_arm_seeds):
                problems.append(
                    f"Stage 6 {arm} arm has {len(report.rows)} rows, expected 256"
                )
            if (
                report.shard_count != T065_STAGE6_SHARD_COUNT
                or len(report.shard_specs) != T065_STAGE6_SHARD_COUNT
                or report.worker_count != T065_MAX_WORKERS
            ):
                problems.append(f"Stage 6 {arm} arm shard evidence is incomplete")
            expected_shard_specs = stage6_shard_ranges(
                arm=arm, worker_count=T065_MAX_WORKERS
            )
            expected_cohort = set(expected_arm_seeds)
            requested_union: set[int] = set()
            completed_union: set[int] = set()
            range_union: set[int] = set()
            for expected_spec, actual_spec in zip(
                expected_shard_specs, report.shard_specs, strict=False
            ):
                if not isinstance(actual_spec, Mapping):
                    problems.append(f"Stage 6 {arm} shard evidence is not an object")
                    continue
                for key in (
                    "arm",
                    "shard_index",
                    "seed_start",
                    "seed_end",
                    "seed_count",
                    "worker_count",
                ):
                    if actual_spec.get(key) != expected_spec[key]:
                        problems.append(
                            f"Stage 6 {arm} shard {expected_spec['shard_index']} "
                            f"{key} is not frozen"
                        )
                if (
                    actual_spec.get("requested_seed_count") != 16
                    or actual_spec.get("completed_row_count") != 16
                ):
                    problems.append(
                        f"Stage 6 {arm} shard {expected_spec['shard_index']} "
                        "does not cover exactly 16 requested/completed seeds"
                    )
                expected_seeds = set(
                    range(
                        int(expected_spec["seed_start"]),
                        int(expected_spec["seed_end"]) + 1,
                    )
                )
                for field_name in ("requested_seeds", "completed_seeds"):
                    actual_seeds = actual_spec.get(field_name)
                    if (
                        not isinstance(actual_seeds, Sequence)
                        or isinstance(actual_seeds, (str, bytes))
                        or any(
                            isinstance(seed, bool) or not isinstance(seed, int)
                            for seed in actual_seeds
                        )
                        or set(actual_seeds) != expected_seeds
                        or len(actual_seeds) != len(expected_seeds)
                    ):
                        problems.append(
                            f"Stage 6 {arm} shard {expected_spec['shard_index']} "
                            f"{field_name} does not match its frozen seed range"
                        )
                    elif field_name == "requested_seeds":
                        requested_union.update(actual_seeds)
                    else:
                        completed_union.update(actual_seeds)
                start = actual_spec.get("seed_start")
                end = actual_spec.get("seed_end")
                if (
                    isinstance(start, int)
                    and not isinstance(start, bool)
                    and isinstance(end, int)
                    and not isinstance(end, bool)
                    and start <= end
                ):
                    range_union.update(range(start, end + 1))
            if (
                range_union != expected_cohort
                or requested_union != expected_cohort
                or completed_union != expected_cohort
            ):
                problems.append(
                    f"Stage 6 {arm} shard seed ranges overlap or do not cover "
                    "the complete cohort"
                )
            if (
                len(report.shard_specs) == T065_STAGE6_SHARD_COUNT
                and len(range_union) != T065_STAGE6_SHARD_COUNT * 16
            ):
                problems.append(
                    f"Stage 6 {arm} shard ranges do not contain 16 distinct seeds "
                    "per shard"
                )
            if (
                len(requested_union) != T065_STAGE6_SHARD_COUNT * 16
                or len(completed_union) != T065_STAGE6_SHARD_COUNT * 16
            ):
                problems.append(
                    f"Stage 6 {arm} requested/completed shard seeds overlap or "
                    "are incomplete"
                )
            problems.extend(f"{arm} arm: {problem}" for problem in report.problems)
            row_seeds: set[int] = set()
            for row in report.rows:
                if not isinstance(row, Mapping):
                    problems.append(f"Stage 6 {arm} contains a non-object row")
                    continue
                seed = row.get("simulator_seed")
                if isinstance(seed, bool) or not isinstance(seed, int):
                    problems.append(f"Stage 6 {arm} row has an invalid simulator seed")
                elif seed in row_seeds:
                    problems.append(f"Stage 6 {arm} has duplicate row seed {seed}")
                else:
                    row_seeds.add(seed)
                if _mapping_or_empty(row.get("action_space")) != expected_action_space:
                    problems.append(f"Stage 6 {arm} seed {seed}: action-space mismatch")
                if row.get("controller_provenance") != dict(controller):
                    problems.append(
                        f"Stage 6 {arm} seed {seed}: controller provenance mismatch"
                    )
                if not bool(row.get("terminal")):
                    problems.append(f"Stage 6 {arm} seed {seed}: run is non-terminal")
                if bool(row.get("truncated")):
                    problems.append(f"Stage 6 {arm} seed {seed}: run was truncated")
                if bool(row.get("controller_error")):
                    problems.append(f"Stage 6 {arm} seed {seed}: controller error")
                floor = row.get("terminal_floor")
                if (
                    isinstance(floor, bool)
                    or not isinstance(floor, (int, float))
                    or not math.isfinite(float(floor))
                ):
                    problems.append(
                        f"Stage 6 {arm} seed {seed}: terminal floor is invalid"
                    )
            if row_seeds != set(expected_arm_seeds):
                problems.append(
                    f"Stage 6 {arm} row seed set does not match requested seeds"
                )
    if coverage.D == 0:
        problems.append("Stage 6 learned-control denominator D is zero")
    if coverage.M == 0:
        problems.append("Stage 6 mandatory-family denominator M is zero")
    expected_seeds = inclusive_range(T065_STAGE6_SEED_RANGE)
    by_seed: dict[int, Mapping[str, Any]] = {}
    for row in paired_rows:
        seed = row.get("simulator_seed")
        if isinstance(seed, bool) or not isinstance(seed, int):
            problems.append("Stage 6 paired row has invalid simulator seed")
            continue
        if seed in by_seed:
            problems.append(f"Stage 6 has duplicate simulator seed {seed}")
        by_seed[seed] = row
    if arm_reports is not None:
        reports_by_arm = {report.arm: report for report in arm_reports}
        expert_report = reports_by_arm.get("expert")
        learned_report = reports_by_arm.get("learned")
        stochastic_report = reports_by_arm.get("stochastic")
        if expert_report is not None and learned_report is not None:
            expected_pair_identity = dict(learned_report.simulator_identity)
            expected_pair_action_space = dict(learned_report.action_space)
            for seed, row in by_seed.items():
                if row.get("simulator_identity") != expected_pair_identity:
                    problems.append(
                        f"Stage 6 paired seed {seed}: simulator identity mismatch"
                    )
                if row.get("action_space") != expected_pair_action_space:
                    problems.append(
                        f"Stage 6 paired seed {seed}: action-space mismatch"
                    )
                if row.get("learned_controller_provenance") != dict(
                    learned_report.controller_provenance
                ):
                    problems.append(
                        f"Stage 6 paired seed {seed}: learned provenance mismatch"
                    )
                if row.get("expert_controller_provenance") != dict(
                    expert_report.controller_provenance
                ):
                    problems.append(
                        f"Stage 6 paired seed {seed}: expert provenance mismatch"
                    )
                if stochastic_report is None or row.get(
                    "stochastic_controller_provenance"
                ) != dict(stochastic_report.controller_provenance):
                    problems.append(
                        f"Stage 6 paired seed {seed}: stochastic provenance mismatch"
                    )
                driver_provenance = row.get("driver_provenance")
                expected_driver_provenance = {
                    "learned": dict(learned_report.driver_provenance),
                    "expert": dict(expert_report.driver_provenance),
                    "stochastic": (
                        dict(stochastic_report.driver_provenance)
                        if stochastic_report is not None
                        else {}
                    ),
                }
                if driver_provenance != expected_driver_provenance:
                    problems.append(
                        f"Stage 6 paired seed {seed}: driver provenance mismatch"
                    )
    if tuple(sorted(by_seed)) != expected_seeds:
        problems.append("Stage 6 paired cohort does not contain exactly 651001..651256")
    deltas: list[float] = []
    learned_floors: list[float] = []
    expert_floors: list[float] = []
    for seed in expected_seeds:
        row = by_seed.get(seed)
        if row is None:
            continue
        for field_name in ("learned_terminal_floor", "expert_terminal_floor"):
            value = row.get(field_name)
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(float(value))
            ):
                problems.append(f"seed {seed}: {field_name} is invalid")
        if bool(row.get("truncated")):
            problems.append(f"seed {seed}: required run was truncated")
        if bool(row.get("controller_error")):
            problems.append(f"seed {seed}: controller error")
        if "learned_terminal" in row and not bool(row.get("learned_terminal")):
            problems.append(f"seed {seed}: learned run is non-terminal")
        if "expert_terminal" in row and not bool(row.get("expert_terminal")):
            problems.append(f"seed {seed}: expert run is non-terminal")
        learned = float(row.get("learned_terminal_floor", float("nan")))
        expert = float(row.get("expert_terminal_floor", float("nan")))
        learned_floors.append(learned)
        expert_floors.append(expert)
        deltas.append(learned - expert)
    valid = not problems and len(deltas) == 256
    if valid:
        p_positive = matched_bootstrap_probability(deltas)
        learned_mean = statistics.fmean(learned_floors)
        expert_mean = statistics.fmean(expert_floors)
        mean_delta = statistics.fmean(deltas)
    else:
        p_positive = 0.0
        learned_mean = expert_mean = mean_delta = float("nan")
    learned_act2 = sum(
        1 for row in by_seed.values() if bool(row.get("learned_act2_entry"))
    )
    expert_act2 = sum(
        1 for row in by_seed.values() if bool(row.get("expert_act2_entry"))
    )
    controller_errors = sum(
        1 for row in by_seed.values() if bool(row.get("controller_error"))
    )
    truncations = sum(1 for row in by_seed.values() if bool(row.get("truncated")))
    passed = valid and (
        mean_delta > 0.0
        and p_positive >= 0.80
        and learned_act2 >= expert_act2
        and controller_errors == 0
        and truncations == 0
        and coverage.passed
        and (learned_act2 > expert_act2 or p_positive >= 0.95)
    )
    if valid and not passed:
        problems.append("one or more frozen Stage 6 gate conditions failed")
    return T065Stage6Report(
        paired_terminal_floor_deltas=tuple(deltas),
        learned_terminal_floor_mean=learned_mean,
        expert_terminal_floor_mean=expert_mean,
        mean_terminal_floor_delta=mean_delta,
        p_positive=p_positive,
        coverage=coverage,
        learned_act2_entry_count=learned_act2,
        expert_act2_entry_count=expert_act2,
        controller_error_count=controller_errors,
        truncation_count=truncations,
        valid=valid,
        passed=passed,
        problems=tuple(problems),
        execution_evidence=dict(execution_evidence or {}),
    )


def terminal_decision_report(
    *,
    stage5: T065HeldoutReport | None = None,
    stage6: T065Stage6Report | None = None,
    case_d: T065CaseD | None = None,
    simulator_identity: Mapping[str, Any] | None = None,
    preceding_stage_manifests: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Return exactly one planner-facing Case A/B/C/D recommendation."""

    if case_d is not None:
        report = case_d.to_decision_report(simulator_identity=simulator_identity)
        if preceding_stage_manifests:
            report["preceding_stage_manifests"] = dict(preceding_stage_manifests)
        return report
    if stage5 is None:
        raise ValueError("T065 terminal decision requires Stage 5 or Case D")
    identity = dict(simulator_identity or {})
    preceding = dict(preceding_stage_manifests or {})
    if not stage5.passed:
        problems = stage5.problems or ("Stage 5 gate failed",)
        failure_ids = [f"stage5-gate:{problem}" for problem in problems]
        return {
            "schema_id": T065_DECISION_REPORT_SCHEMA_ID,
            "schema_version": 1,
            "task_id": T065_TASK_ID,
            "case": "C",
            "stage": "stage5",
            "approved_spec_commit": T065_APPROVED_SPEC_COMMIT,
            "simulator_identity": identity,
            "failure_ids": failure_ids,
            "failure_counts": {
                "failed_gate_conditions": len(failure_ids),
                "failure_count": len(failure_ids),
            },
            "no_replacement": True,
            "downstream_skipped": ["stage6"],
            "preceding_stage_manifests": preceding,
            "recommendation": "close this v1 target/model formulation and run at most one narrow diagnostic",
            "stage5_passed": False,
            "stage6_run": False,
            "problems": list(problems),
            "policy_conclusion": None,
        }
    if stage6 is None:
        raise ValueError("Stage 6 is required after a passing Stage 5 gate")
    if not stage6.valid:
        problems = stage6.problems or ("Stage 6 report is invalid",)
        return {
            "schema_id": T065_DECISION_REPORT_SCHEMA_ID,
            "schema_version": 1,
            "task_id": T065_TASK_ID,
            "case": "D",
            "approved_spec_commit": T065_APPROVED_SPEC_COMMIT,
            "simulator_identity": identity,
            "failure_ids": [f"stage6:{problem}" for problem in problems],
            "failure_counts": {
                "failure_count": len(problems),
                "controller_errors": stage6.controller_error_count,
                "truncations": stage6.truncation_count,
            },
            "no_replacement": True,
            "downstream_skipped": [],
            "preceding_stage_manifests": preceding,
            "recommendation": "repair the frozen fidelity failure and rerun T065",
            "stage": "stage6",
            "stage5_passed": True,
            "stage6_run": True,
            "problems": list(problems),
            "policy_conclusion": None,
        }
    if stage6.passed:
        case = "A"
        recommendation = "accept learned_non_combat_v1 experimentally and review a narrower joint-policy task"
        conclusion = "experimental public non-combat policy only; no natural A20 or live-game promotion"
    else:
        case = "B"
        recommendation = "do not promote; choose one narrow follow-up from the observed transfer failure"
        conclusion = None
    return {
        "schema_id": T065_DECISION_REPORT_SCHEMA_ID,
        "schema_version": 1,
        "task_id": T065_TASK_ID,
        "case": case,
        "approved_spec_commit": T065_APPROVED_SPEC_COMMIT,
        "simulator_identity": identity,
        "preceding_stage_manifests": preceding,
        "recommendation": recommendation,
        "stage5_passed": True,
        "stage6_run": True,
        "stage6_passed": stage6.passed,
        "problems": list(stage6.problems),
        "policy_conclusion": conclusion,
    }


def write_t065_terminal_decision_report(
    path: Path,
    case_d: T065CaseD | None = None,
    *,
    report: Mapping[str, Any] | None = None,
    simulator_identity: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Persist any terminal decision at the shared decision-report schema."""

    if (case_d is None) == (report is None):
        raise ValueError("provide exactly one Case-D failure or decision report")
    if case_d is not None:
        output = case_d.to_decision_report(simulator_identity=simulator_identity)
    else:
        output = dict(report or {})
        if output.get("schema_id") != T065_DECISION_REPORT_SCHEMA_ID:
            raise ValueError("T065 terminal decision has an unsupported schema")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return output


@dataclass(frozen=True)
class T065CompleteRunArmReport:
    """Compact report for one complete-run arm or shard."""

    arm: str
    driver_seed: int
    requested_seeds: tuple[int, ...]
    rows: tuple[Mapping[str, Any], ...]
    decision_events: tuple[Mapping[str, Any], ...] = ()
    wall_clock_seconds: float = 0.0
    worker_count: int = T065_MAX_WORKERS
    shard_count: int = T065_STAGE6_SHARD_COUNT
    shard_specs: tuple[Mapping[str, Any], ...] = ()
    problems: tuple[str, ...] = ()
    simulator_identity: Mapping[str, Any] = field(default_factory=dict)
    action_space: Mapping[str, Any] = field(default_factory=dict)
    controller_provenance: Mapping[str, Any] = field(default_factory=dict)
    driver_provenance: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": T065_STAGE6_REPORT_SCHEMA_ID,
            "schema_version": 1,
            "arm": self.arm,
            "driver_seed": self.driver_seed,
            "requested_seeds": list(self.requested_seeds),
            "rows": [dict(row) for row in self.rows],
            "decision_events": [dict(event) for event in self.decision_events],
            "wall_clock_seconds": self.wall_clock_seconds,
            "worker_count": self.worker_count,
            "shard_count": self.shard_count,
            "shard_specs": [dict(spec) for spec in self.shard_specs],
            "problems": list(self.problems),
            "simulator_identity": dict(self.simulator_identity),
            "action_space": dict(self.action_space),
            "controller_provenance": dict(self.controller_provenance),
            "driver_provenance": dict(self.driver_provenance),
        }


def run_complete_run_arm(
    adapter_factory: Callable[[], Any],
    *,
    arm: str,
    seeds: Iterable[int] | None = None,
    model_run: T065ModelRun | None = None,
    driver_seed: int = T065_STAGE6_DRIVER_SEED,
    max_steps: int = T065_MAX_STEPS,
    worker_count: int = T065_MAX_WORKERS,
    shard_count: int = T065_STAGE6_SHARD_COUNT,
) -> T065CompleteRunArmReport:
    """Run one complete-run arm using the canonical executor.

    ``seeds`` is explicit for shard jobs, while the default is the complete
    frozen 256-seed cohort.  Parallel orchestration is intentionally owned by
    the command/script layer so each adapter remains process-local and every
    shard can report its own range and wall-clock cost.
    """

    if arm not in {"stochastic", "expert", "learned"}:
        raise ValueError(f"unsupported T065 complete-run arm {arm!r}")
    if driver_seed != T065_STAGE6_DRIVER_SEED:
        raise ValueError("T065 Stage 6 driver seed is frozen at 654002")
    if max_steps != T065_MAX_STEPS:
        raise ValueError("T065 Stage 6 step cap is frozen at 500")
    _validate_workers(worker_count)
    if shard_count != T065_STAGE6_SHARD_COUNT:
        raise ValueError("T065 Stage 6 shard count is frozen at 16")
    run_seeds = tuple(
        inclusive_range(T065_STAGE6_SEED_RANGE) if seeds is None else tuple(seeds)
    )
    if tuple(sorted(run_seeds)) != run_seeds or len(set(run_seeds)) != len(run_seeds):
        raise ValueError("T065 Stage 6 seeds must be sorted and unique")
    if any(seed not in inclusive_range(T065_STAGE6_SEED_RANGE) for seed in run_seeds):
        raise ValueError("T065 Stage 6 seed is outside the frozen range")
    if arm == "learned" and model_run is None:
        raise ValueError("learned Stage 6 arm requires the validation-selected model")
    rows: list[Mapping[str, Any]] = []
    events: list[Mapping[str, Any]] = []
    problems: list[str] = []
    arm_controller_provenance: Mapping[str, Any] = {}
    arm_driver_provenance: Mapping[str, Any] = {}
    started = time.perf_counter()
    for seed in run_seeds:
        adapter = adapter_factory()
        learned_policy: LearnedNonCombatPolicy | None = None
        if arm == "stochastic":
            non_combat_policy: Any = StochasticNonCombatDriver(seed=driver_seed)
        elif arm == "expert":
            non_combat_policy = ExpertNonCombatDriver(seed=driver_seed)
        else:
            learned_policy = LearnedNonCombatPolicy(
                model_run,
                fallback=ExpertNonCombatDriver(seed=driver_seed),
            )
            non_combat_policy = learned_policy
        controller = RoutedRunController(
            battle=build_frozen_battle_controller(),
            non_combat=PolicyController(non_combat_policy),
        )
        if not arm_controller_provenance:
            arm_controller_provenance = dict(controller.provenance.to_dict())
            arm_driver_provenance = {
                "name": non_combat_policy.name,
                "version": non_combat_policy.version,
                "config": dict(non_combat_policy.provenance_config),
            }
        try:
            run = execute_controlled_run(
                adapter,
                controller,
                seed=seed,
                max_steps=max_steps,
                action_space=frozen_action_space(),
            )
        except (RuntimeError, ValueError) as exc:
            run = None
            problems.append(f"seed {seed}: {exc}")
            if learned_policy is not None:
                events.extend(
                    {"simulator_seed": seed, **dict(event)}
                    for event in learned_policy.decision_events
                )
        if run is None:
            rows.append(
                {
                    "simulator_seed": seed,
                    "arm": arm,
                    "terminal": False,
                    "terminal_floor": None,
                    "terminal_act": None,
                    "terminal_status": "ERROR",
                    "terminal_current_hp": None,
                    "terminal_max_hp": None,
                    "terminal_gold": None,
                    "terminal_potion_count": None,
                    "terminal_visible_act_boss": None,
                    "truncated": False,
                    "controller_error": True,
                    "problems": [problems[-1]],
                }
            )
            continue
        run_problems = list(run.problems)
        truncated = not run.terminal and len(run.steps) >= max_steps
        if truncated:
            run_problems.append("run reached the 500-step non-terminal cap")
        elif not run.terminal:
            run_problems.append("run ended non-terminal before the step cap")
        if run_problems:
            problems.extend(f"seed {seed}: {problem}" for problem in run_problems)
        terminal_floor = _raw_number(run.final_raw, "floor_num", "floor")
        terminal_act = _raw_number(run.final_raw, "act")
        terminal_visible_act_boss = _json_safe(
            run.public_run_context.get(
                "visible_act_boss", run.final_raw.get("visible_act_boss")
            )
        )
        act2_entry = _run_entered_act2(run)
        row = {
            "simulator_seed": seed,
            "arm": arm,
            "terminal": run.terminal,
            "terminal_floor": terminal_floor,
            "terminal_act": terminal_act,
            "terminal_status": str(run.outcome),
            "terminal_current_hp": _terminal_current_hp(run.final_raw),
            "terminal_max_hp": _terminal_max_hp(run.final_raw),
            "terminal_gold": _raw_number(run.final_raw, "gold"),
            "terminal_potion_count": _terminal_potion_count(run.final_raw),
            "terminal_visible_act_boss": terminal_visible_act_boss,
            "truncated": truncated,
            "controller_error": bool(run_problems) and not truncated,
            "problems": run_problems,
            "learned_decision_count": (
                sum(
                    event.get("status") in {"learned_success", "learned_failure"}
                    for event in learned_policy.decision_events
                )
                if learned_policy is not None
                else 0
            ),
            "act2_entry": act2_entry,
            "controller_provenance": dict(run.controller_provenance),
            "action_space": frozen_action_space().to_dict(),
            "simulator_steps": len(run.steps),
            "simulator_cost": _controlled_run_cost(run),
        }
        if learned_policy is not None:
            run_events = [
                {"simulator_seed": seed, **dict(event)}
                for event in learned_policy.decision_events
            ]
            events.extend(run_events)
            row["intentional_unsupported_fallback_count"] = sum(
                event.get("status") == "unsupported_fallback"
                for event in learned_policy.decision_events
            )
            row["supported_failure_count"] = sum(
                event.get("status") == "learned_failure"
                for event in learned_policy.decision_events
            )
        rows.append(row)
    return T065CompleteRunArmReport(
        arm=arm,
        driver_seed=driver_seed,
        requested_seeds=run_seeds,
        rows=tuple(rows),
        decision_events=tuple(events),
        wall_clock_seconds=time.perf_counter() - started,
        worker_count=worker_count,
        shard_count=shard_count,
        problems=tuple(problems),
        simulator_identity=lightspeed_source_identity_dict(),
        action_space=frozen_action_space().to_dict(),
        controller_provenance=dict(arm_controller_provenance),
        driver_provenance=dict(arm_driver_provenance),
    )


def run_complete_run_arm_sharded(
    adapter_factory: Callable[[], Any],
    *,
    arm: str,
    model_run: T065ModelRun | None = None,
    worker_count: int = T065_MAX_WORKERS,
) -> T065CompleteRunArmReport:
    """Run one Stage 6 arm across the frozen 16 seed shards."""

    _validate_workers(worker_count)
    specs = stage6_shard_ranges(arm=arm, worker_count=worker_count)

    def run(spec: Mapping[str, Any]) -> T065CompleteRunArmReport:
        return run_complete_run_arm(
            adapter_factory,
            arm=arm,
            seeds=range(int(spec["seed_start"]), int(spec["seed_end"]) + 1),
            model_run=model_run,
            worker_count=worker_count,
            shard_count=T065_STAGE6_SHARD_COUNT,
        )

    started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=min(worker_count, len(specs))) as executor:
        futures = [executor.submit(run, spec) for spec in specs]
        shards = [future.result() for future in futures]
    shard_evidence: list[Mapping[str, Any]] = []
    for spec, report in zip(specs, shards, strict=True):
        completed_seeds = tuple(
            int(row["simulator_seed"])
            for row in report.rows
            if isinstance(row, Mapping)
            and isinstance(row.get("simulator_seed"), int)
            and not isinstance(row.get("simulator_seed"), bool)
        )
        shard_evidence.append(
            {
                **dict(spec),
                "requested_seeds": list(report.requested_seeds),
                "completed_seeds": list(completed_seeds),
                "requested_seed_count": len(report.requested_seeds),
                "completed_row_count": len(report.rows),
                "decision_count": len(report.decision_events),
                "wall_clock_seconds": report.wall_clock_seconds,
                "problem_count": len(report.problems),
                "problems": list(report.problems),
            }
        )
    shards = sorted(shards, key=lambda report: report.requested_seeds[0])
    return T065CompleteRunArmReport(
        arm=arm,
        driver_seed=T065_STAGE6_DRIVER_SEED,
        requested_seeds=tuple(
            seed for report in shards for seed in report.requested_seeds
        ),
        rows=tuple(row for report in shards for row in report.rows),
        decision_events=tuple(
            event for report in shards for event in report.decision_events
        ),
        wall_clock_seconds=time.perf_counter() - started,
        worker_count=worker_count,
        shard_count=T065_STAGE6_SHARD_COUNT,
        shard_specs=tuple(shard_evidence),
        problems=tuple(problem for report in shards for problem in report.problems),
        simulator_identity=dict(shards[0].simulator_identity) if shards else {},
        action_space=dict(shards[0].action_space) if shards else {},
        controller_provenance=(dict(shards[0].controller_provenance) if shards else {}),
        driver_provenance=(dict(shards[0].driver_provenance) if shards else {}),
    )


def build_stage6_paired_rows(
    expert_report: T065CompleteRunArmReport,
    learned_report: T065CompleteRunArmReport,
    *,
    stochastic_report: T065CompleteRunArmReport | None = None,
) -> tuple[dict[str, Any], ...]:
    """Join complete expert and learned arms by the frozen simulator seed."""

    if expert_report.arm != "expert" or learned_report.arm != "learned":
        raise ValueError("Stage 6 pairing requires expert and learned reports")
    if stochastic_report is not None and stochastic_report.arm != "stochastic":
        raise ValueError("Stage 6 pairing received an invalid stochastic report")
    expert = {int(row["simulator_seed"]): row for row in expert_report.rows}
    learned = {int(row["simulator_seed"]): row for row in learned_report.rows}
    rows: list[dict[str, Any]] = []
    for seed in inclusive_range(T065_STAGE6_SEED_RANGE):
        expert_row = expert.get(seed)
        learned_row = learned.get(seed)
        if expert_row is None or learned_row is None:
            continue
        rows.append(
            {
                "simulator_seed": seed,
                "learned_terminal_floor": learned_row.get("terminal_floor"),
                "expert_terminal_floor": expert_row.get("terminal_floor"),
                "learned_terminal": bool(learned_row.get("terminal")),
                "expert_terminal": bool(expert_row.get("terminal")),
                "learned_act2_entry": learned_row.get("act2_entry", False),
                "expert_act2_entry": expert_row.get("act2_entry", False),
                "truncated": bool(learned_row.get("truncated"))
                or bool(expert_row.get("truncated")),
                "controller_error": bool(learned_row.get("controller_error"))
                or bool(expert_row.get("controller_error")),
                "simulator_identity": dict(learned_report.simulator_identity),
                "action_space": dict(learned_report.action_space),
                "learned_controller_provenance": dict(
                    learned_report.controller_provenance
                ),
                "expert_controller_provenance": dict(
                    expert_report.controller_provenance
                ),
                "stochastic_controller_provenance": (
                    dict(stochastic_report.controller_provenance)
                    if stochastic_report is not None
                    else {}
                ),
                "driver_provenance": {
                    "learned": dict(learned_report.driver_provenance),
                    "expert": dict(expert_report.driver_provenance),
                    "stochastic": (
                        dict(stochastic_report.driver_provenance)
                        if stochastic_report is not None
                        else {}
                    ),
                },
            }
        )
    return tuple(rows)


def run_stage6_experiment(
    adapter_factory: Callable[[], Any],
    *,
    stage5: T065HeldoutReport,
    selected_model: T065ModelRun,
    worker_count: int = T065_MAX_WORKERS,
) -> tuple[
    T065CompleteRunArmReport,
    T065CompleteRunArmReport,
    T065CompleteRunArmReport,
    T065Stage6Report,
]:
    """Run Stage 6 only after the valid Stage 5 gate passes."""

    if not stage5.passed:
        raise ValueError("T065 Stage 6 is conditionally skipped when Stage 5 fails")
    _validate_workers(worker_count)
    if worker_count != T065_MAX_WORKERS:
        raise ValueError("T065 Stage 6 requires exactly 16 workers")
    stochastic = run_complete_run_arm_sharded(
        adapter_factory, arm="stochastic", worker_count=worker_count
    )
    expert = run_complete_run_arm_sharded(
        adapter_factory, arm="expert", worker_count=worker_count
    )
    learned = run_complete_run_arm_sharded(
        adapter_factory,
        arm="learned",
        model_run=selected_model,
        worker_count=worker_count,
    )
    coverage = compute_learned_coverage(learned.decision_events)
    paired = build_stage6_paired_rows(expert, learned, stochastic_report=stochastic)
    report = build_stage6_report(
        paired,
        coverage,
        execution_evidence={
            "worker_count": worker_count,
            "shard_count_per_arm": T065_STAGE6_SHARD_COUNT,
            "arms": {
                report.arm: {
                    "requested_seed_count": len(report.requested_seeds),
                    "completed_row_count": len(report.rows),
                    "decision_count": len(report.decision_events),
                    "wall_clock_seconds": report.wall_clock_seconds,
                    "worker_count": report.worker_count,
                    "shard_count": report.shard_count,
                    "shard_specs": [dict(spec) for spec in report.shard_specs],
                    "problem_count": len(report.problems),
                    "problems": list(report.problems),
                }
                for report in (stochastic, expert, learned)
            },
        },
        arm_reports=(stochastic, expert, learned),
    )
    return stochastic, expert, learned, report


@dataclass(frozen=True)
class T065PreflightReport:
    """Cheap readiness checks that run before simulator-scale collection."""

    schema: Mapping[str, Any]
    action_space: Mapping[str, Any]
    battle_controller_name: str | None
    snapshot_feature_size: int
    action_feature_size: int
    context_feature_size: int
    state_feature_size: int
    passed: bool
    problems: tuple[str, ...] = ()
    simulator_identity: Mapping[str, Any] = field(default_factory=dict)
    capability_checks: Mapping[str, Mapping[str, Any]] = field(default_factory=dict)
    runtime_checks: Mapping[str, Mapping[str, Any]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": "t065-readiness-preflight-v1",
            "schema_version": 1,
            "schema": dict(self.schema),
            "action_space": dict(self.action_space),
            "battle_controller_name": self.battle_controller_name,
            "snapshot_feature_size": self.snapshot_feature_size,
            "action_feature_size": self.action_feature_size,
            "context_feature_size": self.context_feature_size,
            "state_feature_size": self.state_feature_size,
            "passed": self.passed,
            "problems": list(self.problems),
            "approved_spec_commit": T065_APPROVED_SPEC_COMMIT,
            "simulator_identity": dict(self.simulator_identity),
            "capability_checks": {
                str(key): dict(value) for key, value in self.capability_checks.items()
            },
            "runtime_checks": {
                str(key): dict(value) for key, value in self.runtime_checks.items()
            },
        }


def read_t065_preflight(path: Path) -> dict[str, Any]:
    """Read the explicit Stage 0 artifact without importing optional runtimes."""

    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise T065CaseD(
            "stage0-preflight",
            [f"{path}: preflight artifact cannot be read: {exc}"],
            failure_ids=(f"preflight:{path}",),
            failure_counts={"preflight_artifacts": 1},
        ) from exc
    if not isinstance(value, dict):
        raise T065CaseD(
            "stage0-preflight",
            [f"{path}: preflight artifact root is not an object"],
            failure_ids=(f"preflight:{path}",),
            failure_counts={"preflight_artifacts": 1},
        )
    return {str(key): item for key, item in value.items()}


def _preflight_evidence_digest(value: Mapping[str, Any]) -> str:
    payload = {
        str(key): item for key, item in value.items() if key != "evidence_digest"
    }
    return hashlib.sha256(_canonical_json_bytes(payload)).hexdigest()


def _is_sha256(value: Any) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _parameter_shapes(value: Any) -> tuple[tuple[int, ...], ...] | None:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return None
    result: list[tuple[int, ...]] = []
    for shape in value:
        if not isinstance(shape, Sequence) or isinstance(shape, (str, bytes)):
            return None
        if any(
            isinstance(dimension, bool) or not isinstance(dimension, int)
            for dimension in shape
        ):
            return None
        result.append(tuple(shape))
    return tuple(result)


def validate_t065_preflight(path: Path) -> dict[str, Any]:
    """Require a fully passed Stage 0 artifact for every scientific workflow."""

    value = read_t065_preflight(path)
    problems: list[str] = []
    if value.get("schema_id") != T065_PREFLIGHT_SCHEMA_ID:
        problems.append("preflight schema id is unsupported")
    if value.get("schema_version") != 1:
        problems.append("preflight schema version is unsupported")
    if value.get("approved_spec_commit") != T065_APPROVED_SPEC_COMMIT:
        problems.append("preflight approved spec commit is not frozen")
    if value.get("passed") is not True:
        problems.append("preflight did not pass all Stage 0 checks")
    if value.get("simulator_identity") != lightspeed_source_identity_dict():
        problems.append("preflight simulator identity is not the pinned identity")
    if value.get("action_space") != frozen_action_space().to_dict():
        problems.append("preflight action space is not frozen")
    if value.get("battle_controller_name") != T065_FROZEN_BATTLE_CONTROLLER_NAME:
        problems.append("preflight battle controller is not frozen")
    expected_sizes = {
        "snapshot_feature_size": NON_COMBAT_SNAPSHOT_FEATURE_SIZE,
        "context_feature_size": NON_COMBAT_CONTEXT_FEATURE_SIZE,
        "state_feature_size": NON_COMBAT_STATE_FEATURE_SIZE,
        "action_feature_size": NON_COMBAT_ACTION_FEATURE_SIZE,
    }
    for key, expected in expected_sizes.items():
        if value.get(key) != expected:
            problems.append(f"preflight {key} is not {expected}")
    schema = value.get("schema")
    if not isinstance(schema, Mapping):
        problems.append("preflight model-input schema is missing")
    else:
        expected_schema = non_combat_model_input_schema()
        for key, expected in expected_schema.items():
            actual = schema.get(key)
            if key == "public_context_feature_names" and isinstance(actual, Sequence):
                actual = list(actual)
            if actual != expected:
                problems.append(f"preflight schema field {key!r} is not frozen")
    capability_checks = value.get("capability_checks")
    required_capabilities = (
        "pinned_simulator_manifest",
        "model_input_schema",
        "mandatory_t033_family_positions",
        "public_input_firewall",
        "legacy_cli_boundary",
        "t074_import_isolation",
        "frozen_controller_action_space",
    )
    if not isinstance(capability_checks, Mapping):
        problems.append("preflight capability checks are missing")
    else:
        for name in required_capabilities:
            check = capability_checks.get(name)
            if not isinstance(check, Mapping) or check.get("status") != "passed":
                problems.append(f"preflight capability check {name} did not pass")
    runtime_checks = value.get("runtime_checks")
    if not isinstance(runtime_checks, Mapping):
        problems.append("preflight runtime checks are missing")
    else:
        simulator_check = runtime_checks.get("simulator_runtime")
        expected_simulator_evidence = {
            "status": "passed",
            "execution_environment": "wsl",
            "python_interpreter": T065_TRAINING_INTERPRETER,
            "native_build_pythonpath": T065_LIGHTSPEED_BUILD_PYTHONPATH,
            "native_module": "slaythespire",
            "simulator_class": "StepSimulator",
            "player_class": "IRONCLAD",
            "ascension": 20,
            "simulator_seed": 1,
            "simulator_identity": lightspeed_source_identity_dict(),
            "checkpoint_restore": True,
            "public_projection": True,
            "decision_context_schema_id": "public-run-context-v1",
            "probe_max_steps": T065_NATIVE_PROBE_MAX_STEPS,
            "probe_strategy": "execute_controlled_run_before_decision_observer",
            "battle_controller_name": T065_FROZEN_BATTLE_CONTROLLER_NAME,
            "non_combat_driver_seed": T065_SOURCE_DRIVER_SEED,
        }
        if not isinstance(simulator_check, Mapping) or any(
            simulator_check.get(key) != expected
            for key, expected in expected_simulator_evidence.items()
        ):
            problems.append("preflight simulator runtime evidence is not frozen")
        if not isinstance(simulator_check, Mapping) or not isinstance(
            simulator_check.get("observed_screen"), str
        ):
            problems.append("preflight simulator observed-screen evidence is missing")
        if isinstance(simulator_check, Mapping) and (
            simulator_check.get("checkpoint_restore_equal") is not True
            or not isinstance(simulator_check.get("checkpoint_restores"), int)
            or simulator_check.get("checkpoint_restores", 0) < 1
            or not isinstance(simulator_check.get("nodes_examined"), int)
            or simulator_check.get("nodes_examined", 0) < 1
        ):
            problems.append("preflight simulator checkpoint evidence is incomplete")
        if isinstance(simulator_check, Mapping) and (
            simulator_check.get("evidence_digest")
            != _preflight_evidence_digest(simulator_check)
        ):
            problems.append("preflight simulator runtime evidence digest is invalid")
        simulator_families = (
            simulator_check.get("mandatory_families")
            if isinstance(simulator_check, Mapping)
            else None
        )
        if not isinstance(simulator_families, Mapping) or set(
            simulator_families
        ) != set(T065_MANDATORY_FAMILIES):
            problems.append(
                "preflight simulator runtime mandatory-family evidence is incomplete"
            )
        else:
            for family in T065_MANDATORY_FAMILIES:
                family_check = simulator_families[family]
                if not isinstance(family_check, Mapping) or any(
                    not isinstance(family_check.get(key), str)
                    or not _is_sha256(family_check.get(key))
                    for key in (
                        "projection_digest",
                        "action_identity_digest",
                        "state_feature_digest",
                        "action_feature_digest",
                        "public_context_digest",
                    )
                ):
                    problems.append(
                        f"preflight native projection evidence is missing for {family}"
                    )
                elif (
                    family_check.get("status") != "passed"
                    or family_check.get("screen_family") != family
                    or family_check.get("projection_schema_id")
                    != NATIVE_PUBLIC_PROJECTION_SCHEMA_ID
                    or family_check.get("decision_context_schema_id")
                    != "public-run-context-v1"
                    or family_check.get("state_feature_size")
                    != NON_COMBAT_STATE_FEATURE_SIZE
                    or family_check.get("action_feature_size")
                    != NON_COMBAT_ACTION_FEATURE_SIZE
                    or not isinstance(family_check.get("decision_context_screen"), str)
                    or not family_check.get("decision_context_screen")
                    or not isinstance(
                        family_check.get("projection_screen_identity"), str
                    )
                    or family_check.get("projection_screen_identity")
                    != family_check.get("decision_context_screen")
                    or isinstance(family_check.get("action_count"), bool)
                    or not isinstance(family_check.get("action_count"), int)
                    or family_check.get("action_count", 0) < 1
                ):
                    problems.append(
                        f"preflight native projection evidence is invalid for {family}"
                    )
        torch_check = runtime_checks.get("torch_runtime")
        expected_torch_evidence = {
            "status": "passed",
            "execution_environment": "wsl",
            "python_interpreter": T065_TRAINING_INTERPRETER,
            "native_build_pythonpath": T065_LIGHTSPEED_BUILD_PYTHONPATH,
            "device": "cpu",
            "cpu": True,
            "torch_threads": 1,
            "manual_seed": 653001,
            "minibatch_rng_seed": 1_653_001,
            "state_parameter_count": T065_RANKER_PARAMETER_COUNT,
            "model_input_schema": non_combat_model_input_schema(),
        }
        if not isinstance(torch_check, Mapping) or any(
            torch_check.get(key) != expected
            for key, expected in expected_torch_evidence.items()
        ):
            problems.append("preflight torch runtime evidence is not frozen")
        if (
            not isinstance(torch_check, Mapping)
            or isinstance(torch_check.get("rng_contract"), bool)
            or not isinstance(torch_check.get("rng_contract"), int)
            or not 0 <= torch_check["rng_contract"] < 2**31
        ):
            problems.append("preflight torch RNG evidence is missing")
        if isinstance(torch_check, Mapping) and (
            torch_check.get("evidence_digest")
            != _preflight_evidence_digest(torch_check)
        ):
            problems.append("preflight torch runtime evidence digest is invalid")
        if isinstance(torch_check, Mapping) and (
            _parameter_shapes(torch_check.get("parameter_shapes"))
            != T065_RANKER_PARAMETER_SHAPES
            or torch_check.get("parameter_devices") != ["cpu"]
            or torch_check.get("all_parameters_cpu") is not True
            or not isinstance(torch_check.get("torch_version"), str)
            or not torch_check.get("torch_version")
            or not isinstance(torch_check.get("rng_state_digest"), str)
            or not _is_sha256(torch_check.get("rng_state_digest"))
            or not _is_sha256(torch_check.get("minibatch_rng_state_digest"))
        ):
            problems.append("preflight torch CPU/thread/RNG evidence is incomplete")
    if problems:
        raise T065CaseD(
            "stage0-preflight",
            problems,
            failure_ids=tuple(f"preflight:{problem}" for problem in problems),
            failure_counts={"failed_checks": len(problems)},
            simulator_identity=_mapping_or_empty(value.get("simulator_identity")),
        )
    return value


def _probe_native_mandatory_families(
    adapter: Any,
    snapshot: SimulatorSnapshot,
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    """Follow a bounded real run and audit every mandatory family.

    The pinned seed-1 runtime starts in an event and reaches rooms only after
    several native battles. A broad action frontier spends its budget in
    hidden-state battle branches, so this probe uses the frozen battle search
    controller and seeded expert non-combat driver for one reproducible,
    real transition path. No context is synthesized without a native
    projection.
    """

    if not bool(getattr(adapter, "supports_checkpoint_restore", False)):
        raise ValueError("simulator runtime lacks checkpoint capture/restore")
    transition_only_keys = getattr(
        adapter, "checkpoint_fingerprint_transition_only_raw_keys", None
    )
    if transition_only_keys != frozenset({"completed_battle_outcome"}):
        raise ValueError(
            "simulator runtime lacks the pinned checkpoint fingerprint "
            "transition-only boundary"
        )
    fingerprint_builder = getattr(adapter, "checkpoint_fingerprint", None)
    if not callable(fingerprint_builder):
        raise ValueError("simulator runtime lacks checkpoint fingerprint contract")

    family_evidence: dict[str, dict[str, Any]] = {}
    restore_count = 0
    restore_mismatches = 0
    observed_nodes = 0

    def snapshot_digest(value: SimulatorSnapshot) -> str:
        fingerprint = fingerprint_builder(value)
        if (
            not isinstance(fingerprint, tuple)
            or len(fingerprint) != 2
            or fingerprint[0] != tuple(value.observation)
            or not isinstance(fingerprint[1], Mapping)
        ):
            raise ValueError(
                "simulator runtime checkpoint fingerprint must contain "
                "observation tuple and stateful raw"
            )
        expected_stateful_raw = {
            key: item
            for key, item in value.raw.items()
            if key not in transition_only_keys
        }
        if dict(fingerprint[1]) != expected_stateful_raw:
            raise ValueError(
                "simulator runtime checkpoint fingerprint omitted or added "
                "stateful snapshot data"
            )
        return hashlib.sha256(
            _canonical_json_bytes(
                {
                    "observation": tuple(fingerprint[0]),
                    "stateful_raw": dict(fingerprint[1]),
                }
            )
        ).hexdigest()

    def observe(
        observed_snapshot: SimulatorSnapshot,
        actions: Sequence[SimulatorAction],
        decision_context: DecisionContext,
        step_index: int,
    ) -> None:
        nonlocal restore_count, restore_mismatches, observed_nodes
        observed_nodes += 1
        if not actions:
            raise ValueError("simulator runtime returned no legal actions")
        projection = read_native_public_projection(adapter, observed_snapshot)
        if projection is None:
            raise ValueError("simulator runtime lacks native public projection")
        public_context = decision_context.public_run_context
        if public_context.get("projection_status") != "available":
            raise ValueError("native probe decision context lacks native projection")
        action_identities = tuple(
            dict(item) for item in action_identity_dicts_for_actions(actions)
        )
        checkpoint = adapter.capture_checkpoint(observed_snapshot)
        restored_snapshot = adapter.restore_checkpoint(checkpoint)
        restore_count += 1
        if snapshot_digest(restored_snapshot) != snapshot_digest(observed_snapshot):
            restore_mismatches += 1
        restored_actions = tuple(adapter.legal_actions(restored_snapshot))
        restored_identities = tuple(
            dict(item) for item in action_identity_dicts_for_actions(restored_actions)
        )
        if restored_identities != action_identities:
            raise ValueError("simulator runtime restore changed legal action identity")
        restored_projection = read_native_public_projection(adapter, restored_snapshot)
        if restored_projection is None or (
            restored_projection.canonical_payload != projection.canonical_payload
        ):
            raise ValueError("simulator runtime restore changed native projection")

        screen_field = public_context.get("current", {}).get("screen")
        if not isinstance(screen_field, Mapping):
            raise ValueError("native public context screen field is malformed")
        if screen_field.get("availability") != "available":
            raise ValueError("native public context screen is not available")
        screen_value = screen_field.get("value")
        if not isinstance(screen_value, str) or not screen_value:
            raise ValueError("native public context screen value is missing")
        family = screen_family(screen_value)
        if family not in T065_MANDATORY_FAMILIES or family in family_evidence:
            return
        encoded = encode_non_combat_decision_context(
            decision_context,
            public_context_status="available",
        )
        _validate_mandatory_family_projection(family, encoded.state_features)
        if any(
            len(action_features) != NON_COMBAT_ACTION_FEATURE_SIZE
            for action_features in encoded.action_features
        ):
            raise ValueError(
                f"{family}: native action feature width is not "
                f"{NON_COMBAT_ACTION_FEATURE_SIZE}"
            )
        family_evidence[family] = {
            "status": "passed",
            "screen_family": family,
            "projection_schema_id": projection.schema_id,
            "projection_digest": hashlib.sha256(
                projection.canonical_payload.encode("utf-8")
            ).hexdigest(),
            "action_count": len(actions),
            "action_identity_digest": hashlib.sha256(
                _canonical_json_bytes(action_identities)
            ).hexdigest(),
            "decision_context_screen": screen_value,
            "projection_screen_identity": projection.screen_identity,
            "state_feature_size": len(encoded.state_features),
            "state_feature_digest": hashlib.sha256(
                _canonical_json_bytes(list(encoded.state_features))
            ).hexdigest(),
            "action_feature_size": NON_COMBAT_ACTION_FEATURE_SIZE,
            "action_feature_digest": hashlib.sha256(
                _canonical_json_bytes(
                    [list(features) for features in encoded.action_features]
                )
            ).hexdigest(),
            "public_context_digest": hashlib.sha256(
                _canonical_json_bytes(public_context)
            ).hexdigest(),
            "decision_context_schema_id": public_context["schema_id"],
            "observed_step_index": step_index,
        }

    controller = RoutedRunController(
        battle=build_frozen_battle_controller(),
        non_combat=PolicyController(
            ExpertNonCombatDriver(seed=T065_SOURCE_DRIVER_SEED)
        ),
    )
    run = execute_controlled_run(
        adapter,
        controller,
        seed=1,
        max_steps=T065_NATIVE_PROBE_MAX_STEPS,
        action_space=frozen_action_space(),
        before_decision=observe,
    )
    if run.problems:
        raise ValueError(
            "native runtime probe controlled run failed: " + "; ".join(run.problems)
        )
    missing = [
        family for family in T065_MANDATORY_FAMILIES if family not in family_evidence
    ]
    if missing:
        raise ValueError(
            "simulator runtime probe did not reach mandatory families: "
            + ", ".join(missing)
        )
    return family_evidence, {
        "nodes_examined": observed_nodes,
        "checkpoint_restores": restore_count,
        "checkpoint_restore_equal": restore_mismatches == 0,
        "probe_max_steps": T065_NATIVE_PROBE_MAX_STEPS,
        "probe_strategy": "execute_controlled_run_before_decision_observer",
        "battle_controller_name": T065_FROZEN_BATTLE_CONTROLLER_NAME,
        "non_combat_driver_seed": T065_SOURCE_DRIVER_SEED,
    }


def build_t065_preflight_report(
    *,
    adapter_factory: Callable[[], Any] | None = None,
    check_simulator_runtime: bool = False,
    check_torch_runtime: bool = False,
) -> T065PreflightReport:
    """Run explicit pure checks and optionally requested runtime checks.

    Runtime checks are deliberately opt-in: importing this module and running
    the default preflight never imports optional PyTorch or the external
    simulator.  A deferred runtime check is reported as incomplete rather than
    silently treated as passed.
    """

    problems: list[str] = []
    capability_checks: dict[str, dict[str, Any]] = {}
    runtime_checks: dict[str, dict[str, Any]] = {}
    try:
        simulator_identity = lightspeed_source_identity_dict(
            load_lightspeed_source_manifest()
        )
        capability_checks["pinned_simulator_manifest"] = {
            "status": "passed",
            "identity": dict(simulator_identity),
        }
    except (OSError, ValueError) as exc:
        simulator_identity = {}
        capability_checks["pinned_simulator_manifest"] = {
            "status": "failed",
            "error": str(exc),
        }
        problems.append(f"pinned simulator manifest unavailable: {exc}")
    schema = non_combat_model_input_schema()
    snapshot_size = len(encode_lightspeed_battle_snapshot({}))
    action_size = len(
        encode_simulator_actions(
            [SimulatorAction(action_id="preflight", label="", kind="game_unknown")],
            {},
        )[0]
    )
    context_size = PUBLIC_CONTEXT_MODEL_INPUT_FEATURE_SIZE
    if snapshot_size != NON_COMBAT_SNAPSHOT_FEATURE_SIZE:
        problems.append(f"snapshot feature size is {snapshot_size}, expected 4634")
    if action_size != NON_COMBAT_ACTION_FEATURE_SIZE:
        problems.append(f"action feature size is {action_size}, expected 92")
    if context_size != PUBLIC_CONTEXT_MODEL_INPUT_FEATURE_SIZE:
        problems.append("public context feature size is not 103")
    if len(PUBLIC_CONTEXT_MODEL_INPUT_FEATURE_NAMES) != 103:
        problems.append("public context feature-name tuple is not 103 values")
    capability_checks["model_input_schema"] = {
        "status": "passed"
        if schema.get("state_feature_size") == 4737
        and schema.get("action_feature_size") == 92
        else "failed",
        "schema": dict(schema),
    }
    action = SimulatorAction(action_id="preflight", label="", kind="game_unknown")
    try:
        public_contexts: dict[str, list[float]] = {}
        for family, raw_screen in (
            ("MAP_SCREEN", "MAP_SCREEN"),
            ("REST_ROOM", "REST_ROOM"),
            ("REWARDS", "REWARDS"),
            ("TREASURE_ROOM", "TREASURE_ROOM"),
        ):
            public_context = build_public_run_context(
                {"screen_state": raw_screen, "battle_active": False},
                [action],
                projection=None,
            )
            encoded = encode_non_combat_decision_context(
                build_decision_context(
                    {"screen_state": raw_screen, "battle_active": False},
                    [action],
                    frozen_action_space(),
                    public_run_context=public_context,
                ),
                public_context_status="available",
            )
            _validate_mandatory_family_projection(family, encoded.state_features)
            public_contexts[family] = list(encoded.state_features[-103:])
        capability_checks["mandatory_t033_family_positions"] = {
            "status": "passed",
            "families": sorted(public_contexts),
        }
    except (RuntimeError, ValueError, T065CaseD) as exc:
        capability_checks["mandatory_t033_family_positions"] = {
            "status": "failed",
            "error": str(exc),
        }
        problems.append(f"mandatory T033 family projection check failed: {exc}")
    try:
        hidden_problems = forbidden_public_context_problems(
            {"checkpoint": {"native_payload": "forbidden"}}
        )
        if not hidden_problems:
            raise ValueError(
                "hidden/private-field audit did not reject a forbidden field"
            )
        capability_checks["public_input_firewall"] = {
            "status": "passed",
            "audit": "hidden/private fields rejected",
        }
    except ValueError as exc:
        capability_checks["public_input_firewall"] = {
            "status": "failed",
            "error": str(exc),
        }
        problems.append(str(exc))
    legacy_cli_paths = (
        Path(__file__).resolve().parents[1] / "commands" / "cli_parser.py",
        Path(__file__).resolve().parents[1] / "commands" / "lightspeed_cli.py",
        Path(__file__).resolve().parents[1] / "commands" / "cli_validation.py",
        Path(__file__).resolve().parents[1] / "cli.py",
    )
    legacy_problems = []
    for path in legacy_cli_paths:
        try:
            source = path.read_text(encoding="utf-8").lower()
        except OSError as exc:
            legacy_problems.append(f"{path}: {exc}")
        else:
            if "t065" in source:
                legacy_problems.append(f"{path}: contains a T065-specific route")
    capability_checks["legacy_cli_boundary"] = {
        "status": "passed" if not legacy_problems else "failed",
        "paths": [str(path) for path in legacy_cli_paths],
    }
    problems.extend(legacy_problems)
    policy_contract = Path(__file__).with_name("policy_contract.py")
    try:
        tree = ast.parse(policy_contract.read_text(encoding="utf-8"))
        imported = {
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        }
        imported.update(
            node.module
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module
        )
        if "torch" in imported or any(
            module.startswith("sts_combat_rl.commands") for module in imported
        ):
            raise ValueError(
                "T074 policy contract imports an upward/optional dependency"
            )
        capability_checks["t074_import_isolation"] = {"status": "passed"}
    except (OSError, SyntaxError, ValueError) as exc:
        capability_checks["t074_import_isolation"] = {
            "status": "failed",
            "error": str(exc),
        }
        problems.append(f"T074 import isolation check failed: {exc}")
    controller_name: str | None = None
    try:
        controller_name = build_frozen_battle_controller().provenance.name
    except (RuntimeError, ValueError) as exc:
        problems.append(f"frozen battle controller unavailable: {exc}")
    if frozen_action_space().to_dict() != {
        "excluded_kinds": [
            "game_potion_discard",
            "game_potion_use",
            "potion",
            "potion_discard",
            "reward_potion",
            "shop_reward_potion",
        ],
        "preferred_kinds": ["card", "end_turn"],
        "allow_excluded_fallback": True,
        "include_non_combat_potions": True,
    }:
        problems.append("frozen action-space dictionary does not match T065")
    capability_checks["frozen_controller_action_space"] = {
        "status": "passed"
        if controller_name == T065_FROZEN_BATTLE_CONTROLLER_NAME
        else "failed",
        "controller_name": controller_name,
        "action_space": frozen_action_space().to_dict(),
    }
    if check_simulator_runtime:
        if adapter_factory is None:
            runtime_checks["simulator_runtime"] = {
                "status": "failed",
                "error": "--simulator-runtime requires an adapter factory",
            }
            problems.append(
                "simulator runtime was requested without an adapter factory"
            )
        else:
            try:
                adapter = adapter_factory()
                snapshot = adapter.reset(seed=1)
                family_evidence, probe_evidence = _probe_native_mandatory_families(
                    adapter, snapshot
                )
                simulator_evidence = {
                    "status": "passed",
                    "execution_environment": "wsl",
                    "python_interpreter": T065_TRAINING_INTERPRETER,
                    "native_build_pythonpath": T065_LIGHTSPEED_BUILD_PYTHONPATH,
                    "native_module": "slaythespire",
                    "simulator_class": "StepSimulator",
                    "player_class": "IRONCLAD",
                    "ascension": 20,
                    "simulator_seed": 1,
                    "simulator_identity": dict(simulator_identity),
                    "checkpoint_restore": True,
                    "public_projection": True,
                    "decision_context_schema_id": "public-run-context-v1",
                    "observed_screen": next(iter(family_evidence.values()))[
                        "decision_context_screen"
                    ],
                    "mandatory_families": family_evidence,
                    **probe_evidence,
                }
                if simulator_evidence["checkpoint_restore_equal"] is not True:
                    raise ValueError(
                        "simulator runtime checkpoint restore changed the public snapshot"
                    )
                simulator_evidence["evidence_digest"] = _preflight_evidence_digest(
                    simulator_evidence
                )
                runtime_checks["simulator_runtime"] = simulator_evidence
            except (RuntimeError, ValueError, OSError) as exc:
                runtime_checks["simulator_runtime"] = {
                    "status": "failed",
                    "error": str(exc),
                }
                problems.append(f"simulator runtime preflight failed: {exc}")
    else:
        runtime_checks["simulator_runtime"] = {
            "status": "deferred",
            "execution_environment": "wsl",
            "python_interpreter": T065_TRAINING_INTERPRETER,
            "native_build_pythonpath": T065_LIGHTSPEED_BUILD_PYTHONPATH,
            "native_module": "slaythespire",
            "mandatory_family_probe": "explicit WSL runtime only",
            "command_boundary": "preflight --simulator-runtime (WSL pinned build)",
        }
        problems.append(
            "simulator runtime preflight is deferred; run the explicit runtime command"
        )
    if check_torch_runtime:
        try:
            torch = _require_torch()
            torch.set_num_threads(1)
            if torch.get_num_threads() != 1:
                raise RuntimeError("PyTorch CPU thread count could not be set to one")
            torch.manual_seed(653001)
            model = _build_ranker_module()
            generator = torch.Generator(device="cpu")
            generator.manual_seed(1_653_001)
            torch_evidence = {
                "status": "passed",
                "execution_environment": "wsl",
                "python_interpreter": T065_TRAINING_INTERPRETER,
                "native_build_pythonpath": T065_LIGHTSPEED_BUILD_PYTHONPATH,
                "device": "cpu",
                "cpu": True,
                "torch_threads": torch.get_num_threads(),
                "manual_seed": 653001,
                "minibatch_rng_seed": 1_653_001,
                "state_parameter_count": sum(
                    parameter.numel() for parameter in model.parameters()
                ),
                "model_input_schema": non_combat_model_input_schema(),
                "rng_contract": int(
                    torch.randint(0, 2**31, (1,), generator=generator).item()
                ),
                "minibatch_rng_state_digest": hashlib.sha256(
                    bytes(generator.get_state().tolist())
                ).hexdigest(),
                "torch_version": str(torch.__version__),
                "parameter_shapes": [
                    list(parameter.shape) for parameter in model.parameters()
                ],
                "parameter_devices": sorted(
                    {str(parameter.device) for parameter in model.parameters()}
                ),
                "all_parameters_cpu": all(
                    parameter.device.type == "cpu" for parameter in model.parameters()
                ),
                "rng_state_digest": hashlib.sha256(
                    bytes(torch.get_rng_state().tolist())
                ).hexdigest(),
            }
            torch_evidence["evidence_digest"] = _preflight_evidence_digest(
                torch_evidence
            )
            runtime_checks["torch_runtime"] = torch_evidence
        except (RuntimeError, ImportError, OSError) as exc:
            runtime_checks["torch_runtime"] = {"status": "failed", "error": str(exc)}
            problems.append(f"PyTorch runtime preflight failed: {exc}")
    else:
        runtime_checks["torch_runtime"] = {
            "status": "deferred",
            "execution_environment": "wsl",
            "python_interpreter": T065_TRAINING_INTERPRETER,
            "native_build_pythonpath": T065_LIGHTSPEED_BUILD_PYTHONPATH,
            "device": "cpu",
            "mandatory_model_probe": "explicit WSL runtime only",
            "command_boundary": "preflight --torch-runtime (optional train dependency)",
        }
        problems.append(
            "PyTorch runtime preflight is deferred; run the explicit runtime command"
        )
    return T065PreflightReport(
        schema=schema,
        action_space=frozen_action_space().to_dict(),
        battle_controller_name=controller_name,
        snapshot_feature_size=snapshot_size,
        action_feature_size=action_size,
        context_feature_size=context_size,
        state_feature_size=snapshot_size + context_size,
        passed=not problems,
        problems=tuple(problems),
        simulator_identity=simulator_identity,
        capability_checks=capability_checks,
        runtime_checks=runtime_checks,
    )


def public_state_identity(
    *,
    family: str,
    state_features: Sequence[float],
    public_run_context: Mapping[str, Any],
    legal_action_identities: Sequence[Mapping[str, Any]],
) -> str:
    """Hash only the portable public state and ordered legal identities."""

    payload = {
        "family": family,
        "state_features": [float(value) for value in state_features],
        "public_run_context": _json_safe(public_run_context),
        "ordered_legal_action_identities": [
            _json_safe(identity) for identity in legal_action_identities
        ],
    }
    return hashlib.sha256(_canonical_json_bytes(payload)).hexdigest()


def write_source_states(path: Path, states: Sequence[T065SourceState]) -> str:
    """Write one compact current-schema source-state JSONL artifact."""

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as stream:
        for state in states:
            stream.write(json.dumps(state.to_dict(), sort_keys=True) + "\n")
    return file_sha256(path)


def write_source_selection_manifest(
    path: Path,
    *,
    selected_states: Sequence[T065SourceState],
    selected_artifact_identity: Mapping[str, Any],
    source_artifacts: Sequence[Mapping[str, Any]],
    simulator_identity: Mapping[str, Any] | None = None,
    approved_spec_commit: str = T065_APPROVED_SPEC_COMMIT,
) -> dict[str, Any]:
    """Write the compact deterministic source-selection manifest."""

    states = tuple(selected_states)
    if len(states) != 320:
        raise T065CaseD(
            "source-selection-manifest",
            [f"selected source state count {len(states)} does not match 320"],
        )
    if tuple(state.selected_state_index for state in states) != tuple(range(320)):
        raise T065CaseD(
            "source-selection-manifest",
            ["selected source-state indices are not globally contiguous"],
        )
    counts: dict[str, dict[str, int]] = {
        family: {split: 0 for split in T065_SPLITS}
        for family in T065_MANDATORY_FAMILIES
    }
    for state in states:
        if state.family not in counts or state.split not in T065_SPLITS:
            raise T065CaseD(
                "source-selection-manifest",
                [f"unsupported selected state stratum {state.family}/{state.split}"],
            )
        counts[state.family][state.split] += 1
    if any(
        counts[family][split] != T065_SPLIT_QUOTAS[split]
        for family in T065_MANDATORY_FAMILIES
        for split in T065_SPLITS
    ):
        raise T065CaseD(
            "source-selection-manifest",
            [f"selected source quota counts are invalid: {counts!r}"],
        )
    if approved_spec_commit != T065_APPROVED_SPEC_COMMIT:
        raise ValueError("approved T065 spec commit does not match the frozen head")
    manifest = {
        "schema_id": T065_SELECTION_MANIFEST_SCHEMA_ID,
        "schema_version": 1,
        "task_id": T065_TASK_ID,
        "approved_spec_commit": approved_spec_commit,
        "selection_domain": T065_SELECTION_DOMAIN.decode("utf-8").rstrip("\n"),
        "selection_algorithm": {
            "deduplication": "(screen_family, public_state_identity, ordered_legal_action_identities)",
            "sort": "sha256(domain + canonical_candidate_json), canonical_json_bytes",
            "family_order": list(T065_MANDATORY_FAMILIES),
            "split_order": list(T065_SPLITS),
            "quota_by_split": dict(T065_SPLIT_QUOTAS),
            "replacement": False,
        },
        "source_artifacts": [dict(item) for item in source_artifacts],
        "simulator_identity": dict(simulator_identity or {}),
        "selected_artifact": dict(selected_artifact_identity),
        "selected_state_count": len(states),
        "counts_by_family_split": counts,
        "states": [
            {
                "selected_state_index": state.selected_state_index,
                "family": state.family,
                "split": state.split,
                "simulator_seed": state.simulator_seed,
                "source_arm": state.source_arm,
                "source_run_id": state.source_run_id,
                "source_step_index": state.source_step_index,
                "public_state_identity": state.public_state_identity,
                "selection_digest": state.selection_digest,
            }
            for state in states
        ],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return manifest


def read_source_states(path: Path) -> tuple[T065SourceState, ...]:
    """Read current source-state rows with strict schema validation."""

    rows: list[T065SourceState] = []
    with path.open("r", encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, 1):
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"source-state line {line_number} is invalid JSON"
                ) from exc
            if not isinstance(value, Mapping):
                raise ValueError(f"source-state line {line_number} is not an object")
            rows.append(T065SourceState.from_dict(value))
    return tuple(rows)


def write_target_table(path: Path, table: T065TargetTable) -> str:
    """Write the compact target-table document and return its SHA-256."""

    table.validate_complete()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(table.to_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return file_sha256(path)


def read_target_table(path: Path) -> T065TargetTable:
    """Read a current target table; no legacy fields are guessed."""

    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, Mapping):
        raise ValueError("T065 target table root must be an object")
    if value.get("schema_id") != T065_TARGET_TABLE_SCHEMA_ID:
        raise ValueError("unsupported T065 target-table schema")
    if value.get("schema_version") != 1:
        raise ValueError("unsupported T065 target-table schema version")
    if value.get("task_id") != T065_TASK_ID:
        raise ValueError("T065 target table task id is invalid")
    if value.get("approved_spec_commit") != T065_APPROVED_SPEC_COMMIT:
        raise ValueError("T065 target table approved spec commit is invalid")
    if value.get("frozen_config") != T065ExperimentConfig().to_dict():
        raise ValueError("T065 target table frozen configuration is invalid")
    schema_problems = _schema_from_document(value.get("model_input_schema"))
    if schema_problems:
        raise ValueError("; ".join(schema_problems))
    source_identity_problems = _checkpoint_artifact_identity_problems(
        value.get("source_artifact_identity"), "target-table source_artifact_identity"
    )
    if source_identity_problems:
        raise ValueError("; ".join(source_identity_problems))
    raw_states = value.get("states")
    raw_targets = value.get("targets")
    if not isinstance(raw_states, Sequence) or isinstance(raw_states, (str, bytes)):
        raise ValueError("T065 target table states must be a list")
    if not isinstance(raw_targets, Sequence) or isinstance(raw_targets, (str, bytes)):
        raise ValueError("T065 target table targets must be a list")
    for key in (
        "source_artifact_identity",
        "simulator_identity",
        "execution_evidence",
        "expert_action_provenance",
    ):
        if key not in value or not isinstance(value[key], Mapping):
            raise ValueError(f"T065 target table field {key!r} is missing")
    states = tuple(
        T065SourceState.from_dict(row) for row in raw_states if isinstance(row, Mapping)
    )
    if len(states) != len(raw_states):
        raise ValueError("T065 target table contains a non-object state")
    targets = tuple(_target_from_dict(row) for row in raw_targets)
    table = T065TargetTable(
        states=states,
        targets=targets,
        source_artifact_identity=_mapping_or_empty(
            value.get("source_artifact_identity")
        ),
        simulator_identity=_mapping_or_empty(value.get("simulator_identity")),
        execution_evidence=_mapping_or_empty(value.get("execution_evidence")),
        expert_action_indices=_int_keyed_int_mapping(
            value.get("expert_action_indices")
        ),
        expert_action_provenance=_mapping_or_empty(
            value.get("expert_action_provenance")
        ),
    )
    table.validate_complete()
    return table


def write_t065_manifest(
    path: Path,
    *,
    approved_spec_commit: str,
    simulator_identity: Mapping[str, Any],
    artifacts: Mapping[str, Path],
    regeneration_commands: Sequence[str],
    stage_evidence: Mapping[str, Mapping[str, Any]] | None = None,
    preceding_stage_manifests: Mapping[str, Mapping[str, Any]] | None = None,
    failed_stage_artifacts: Mapping[str, Mapping[str, Any]] | None = None,
    retention_reason: str = (
        "T065 compact source/target/model/gate evidence retained for exact "
        "stage-local reuse and maintainer review"
    ),
) -> dict[str, Any]:
    """Write a lightweight reproducibility/retention manifest."""

    if approved_spec_commit != T065_APPROVED_SPEC_COMMIT:
        raise ValueError("approved T065 spec commit does not match the frozen head")
    if not artifacts:
        raise ValueError("T065 retention manifest requires artifacts")
    if not regeneration_commands:
        raise ValueError("T065 retention manifest requires regeneration commands")
    entries: list[dict[str, Any]] = []
    for role, artifact_path in sorted(artifacts.items()):
        if not artifact_path.is_file():
            raise ValueError(f"T065 retained artifact is missing: {artifact_path}")
        entry = {
            "role": role,
            "path": str(artifact_path),
            "sha256": file_sha256(artifact_path),
            "size_bytes": artifact_path.stat().st_size,
        }
        if role.startswith("checkpoint_"):
            seed_text = role.removeprefix("checkpoint_")
            if not seed_text.isdigit():
                raise ValueError(f"T065 checkpoint artifact role is invalid: {role}")
            entry["identity"] = {"model_seed": int(seed_text)}
        entries.append(entry)
    artifact_roles = [str(entry["role"]) for entry in entries]
    normalized_stage_evidence: dict[str, dict[str, Any]] = {}
    for stage, raw_evidence in (stage_evidence or {}).items():
        if not isinstance(raw_evidence, Mapping):
            raise ValueError(f"T065 stage evidence for {stage!r} must be an object")
        evidence = dict(raw_evidence)
        referenced_roles = evidence.get("artifact_roles", artifact_roles)
        if not isinstance(referenced_roles, Sequence) or isinstance(
            referenced_roles, (str, bytes)
        ):
            raise ValueError(f"T065 stage evidence for {stage!r} has invalid roles")
        if any(role not in artifact_roles for role in referenced_roles):
            raise ValueError(
                f"T065 stage evidence for {stage!r} references an unknown role"
            )
        evidence["artifact_roles"] = list(referenced_roles)
        normalized_stage_evidence[str(stage)] = evidence
    manifest = {
        "schema_id": "t065-retention-manifest-v1",
        "schema_version": 1,
        "task_id": T065_TASK_ID,
        "experiment_schema_id": T065_EXPERIMENT_SCHEMA_ID,
        "approved_spec_commit": approved_spec_commit,
        "simulator_identity": dict(simulator_identity),
        "frozen_config": T065ExperimentConfig().to_dict(),
        "model_input_schema": non_combat_model_input_schema(),
        "artifacts": entries,
        "regeneration_commands": list(regeneration_commands),
        "stage_evidence": normalized_stage_evidence,
        "preceding_stage_manifests": {
            str(role): dict(identity)
            for role, identity in (preceding_stage_manifests or {}).items()
        },
        "failed_stage_artifacts": {
            str(role): dict(identity)
            for role, identity in (failed_stage_artifacts or {}).items()
        },
        "retention_root": str(path.parent),
        "retention_reason": retention_reason,
        "deletion_condition": "delete only after T065 follow-up no longer needs the compact evidence",
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return manifest


class _ContinuationAdapter:
    """Adapter view whose reset returns an already-forced simulator state."""

    def __init__(self, adapter: Any, snapshot: SimulatorSnapshot) -> None:
        self._adapter = adapter
        self._snapshot = snapshot

    def reset(self, seed: int | None = None) -> SimulatorSnapshot:
        del seed
        return self._snapshot

    def legal_actions(self, snapshot: SimulatorSnapshot) -> Sequence[SimulatorAction]:
        return self._adapter.legal_actions(snapshot)

    def step(self, action: SimulatorAction) -> SimulatorTransition:
        transition = self._adapter.step(action)
        self._snapshot = transition.snapshot
        return transition

    def __getattr__(self, name: str) -> Any:
        return getattr(self._adapter, name)


def file_sha256(path: Path) -> str:
    """Hash a retained artifact without loading it all into memory."""

    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _target_rows_for_states(
    states: Sequence[T065SourceState],
    targets: Sequence[T065CounterfactualTarget],
) -> list[tuple[T065SourceState, int, float]]:
    by_state: dict[int, dict[int, T065CounterfactualTarget]] = defaultdict(dict)
    for target in targets:
        by_state[target.selected_state_index][target.legal_action_index] = target
    result: list[tuple[T065SourceState, int, float]] = []
    for state in sorted(states, key=lambda item: item.selected_state_index):
        for action_index in state.eligible_action_indices:
            target = by_state.get(state.selected_state_index, {}).get(action_index)
            if target is None:
                raise T065CaseD(
                    "target-completeness",
                    [
                        f"missing target row for state {state.selected_state_index} "
                        f"action {action_index}"
                    ],
                )
            if target.target_status != "complete" or target.problems:
                raise T065CaseD(
                    "target-completeness",
                    [
                        f"state {state.selected_state_index} action "
                        f"{action_index}: target row is not complete"
                    ],
                )
            if len(target.terminal_floors) != len(target.continuation_seeds):
                raise T065CaseD(
                    "target-completeness",
                    [
                        f"state {state.selected_state_index} action "
                        f"{action_index}: continuation rows are incomplete"
                    ],
                )
            if not math.isfinite(target.q_floor):
                raise T065CaseD("target-completeness", ["non-finite q_floor"])
            result.append((state, action_index, target.q_floor))
    return result


def _expert_comparison_action_index(
    context: DecisionContext,
    simulator_seed: int,
) -> int:
    """Select the frozen expert comparison action without entering training."""

    expert = ExpertNonCombatDriver(seed=T065_SOURCE_DRIVER_SEED)
    expert.reset_for_run(simulator_seed)
    decision = expert.select_action(context)
    if decision.legal_action_index not in context.eligible_action_indices:
        raise T065CaseD(
            "expert-comparison-action",
            [
                f"expert selected ineligible action {decision.legal_action_index} "
                f"at simulator seed {simulator_seed}"
            ],
        )
    return decision.legal_action_index


def _evaluate_model_rows(
    model: Any,
    normalizers: T065Normalizers,
    rows: Sequence[tuple[T065SourceState, int, float]],
) -> float:
    if not rows:
        raise ValueError("T065 model evaluation requires rows")
    errors = [
        abs(
            _model_score(
                model,
                normalizers,
                state.state_features,
                state.legal_action_features[action_index],
            )
            - target
        )
        for state, action_index, target in rows
    ]
    return statistics.fmean(errors)


def _model_score(
    model: Any,
    normalizers: T065Normalizers,
    state_features: Sequence[float],
    action_features: Sequence[float],
) -> float:
    torch = _require_torch()
    state = torch.tensor(
        [normalizers.normalize_state(state_features)], dtype=torch.float32
    )
    action = torch.tensor(
        [normalizers.normalize_action(action_features)], dtype=torch.float32
    )
    model.eval()
    with torch.no_grad():
        value = model(state, action).reshape(-1)[0].item()
    if not math.isfinite(float(value)):
        raise ValueError("T065 model prediction is non-finite")
    return float(value)


def _normalize_values_float32(
    values: Sequence[float],
    mean: Sequence[float],
    std: Sequence[float],
) -> list[float]:
    """Apply the frozen normalizer arithmetic in CPU float32."""

    torch = _require_torch()
    value_tensor = torch.tensor(values, dtype=torch.float32, device="cpu")
    mean_tensor = torch.tensor(mean, dtype=torch.float32, device="cpu")
    std_tensor = torch.tensor(std, dtype=torch.float32, device="cpu")
    return [
        float(value) for value in ((value_tensor - mean_tensor) / std_tensor).tolist()
    ]


def _frozen_training_config(model_seed: int) -> dict[str, Any]:
    return {
        "framework": "pytorch_cpu",
        "steps": 1500,
        "candidate_action_batch_size": 64,
        "loss": "HuberLoss(delta=1.0,reduction=mean)",
        "optimizer": {
            "name": "Adam",
            "lr": 1e-3,
            "betas": [0.9, 0.999],
            "eps": 1e-8,
            "weight_decay": 0.0,
            "amsgrad": False,
        },
        "gradient_clip_norm": 10.0,
        "torch_threads": 1,
        "minibatch_rng_seed": model_seed + 1_000_000,
        "sampling": "torch.randint_with_replacement",
    }


def _checkpoint_metadata(
    *,
    model_seed: int,
    normalizers: T065Normalizers,
    source_artifact_identity: Mapping[str, Any],
    target_artifact_identity: Mapping[str, Any],
    split_provenance: Mapping[str, Mapping[str, Any]],
    source_provenance: Mapping[str, Any],
    target_provenance: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        **non_combat_model_input_schema(),
        "non_combat_model_input_schema_id": NON_COMBAT_MODEL_INPUT_SCHEMA_ID,
        "non_combat_model_input_schema_version": NON_COMBAT_MODEL_INPUT_SCHEMA_VERSION,
        "tactical_feature_names": [
            "DecisionContext.snapshot_features[0:4634] from encode_lightspeed_battle_snapshot",
        ],
        "tactical_action_feature_names": [
            "DecisionContext.legal_action_features[0:92] from encode_simulator_actions",
        ],
        "public_context_feature_names": list(PUBLIC_CONTEXT_MODEL_INPUT_FEATURE_NAMES),
        "model_class": "T065ActionConditionedRanker",
        "model_seed": model_seed,
        "training_config": _frozen_training_config(model_seed),
        "target_identity": "q_floor=mean(max(0,terminal_floor-source_floor))",
        "source_artifact_identity": dict(source_artifact_identity),
        "target_artifact_identity": dict(target_artifact_identity),
        "split_provenance": {
            str(split): dict(provenance)
            for split, provenance in split_provenance.items()
        },
        "source_provenance": dict(source_provenance),
        "target_provenance": dict(target_provenance),
        "behavior_provenance": {
            "source_driver_seed": T065_SOURCE_DRIVER_SEED,
            "continuation_policy": "expert_non_combat_v1",
            "battle_controller": T065_FROZEN_BATTLE_CONTROLLER_NAME,
            "human_or_expert_action_supervision": False,
        },
        "normalizers": normalizers.to_dict(),
    }


def _checkpoint_schema_problems(metadata: Mapping[str, Any]) -> list[str]:
    problems = _schema_from_document(metadata)
    if metadata.get("non_combat_model_input_schema_id") != (
        NON_COMBAT_MODEL_INPUT_SCHEMA_ID
    ):
        problems.append("T065 checkpoint non-combat schema id is unsupported")
    if metadata.get("non_combat_model_input_schema_version") != (
        NON_COMBAT_MODEL_INPUT_SCHEMA_VERSION
    ):
        problems.append("T065 checkpoint non-combat schema version is unsupported")
    model_seed = metadata.get("model_seed")
    if (
        isinstance(model_seed, bool)
        or not isinstance(model_seed, int)
        or model_seed not in T065_MODEL_SEEDS
    ):
        problems.append("T065 checkpoint model seed is not frozen")
    else:
        if metadata.get("training_config") != _frozen_training_config(model_seed):
            problems.append("T065 checkpoint training configuration is not frozen")
    if metadata.get("model_class") != "T065ActionConditionedRanker":
        problems.append("T065 checkpoint model class is unsupported")
    if metadata.get("training_steps") != 1500:
        problems.append("T065 checkpoint training step count is not 1500")
    if metadata.get("target_identity") != (
        "q_floor=mean(max(0,terminal_floor-source_floor))"
    ):
        problems.append("T065 checkpoint target identity is unsupported")
    if metadata.get("behavior_provenance") != {
        "source_driver_seed": T065_SOURCE_DRIVER_SEED,
        "continuation_policy": "expert_non_combat_v1",
        "battle_controller": T065_FROZEN_BATTLE_CONTROLLER_NAME,
        "human_or_expert_action_supervision": False,
    }:
        problems.append("T065 checkpoint behavior provenance is not frozen")
    problems.extend(
        _checkpoint_artifact_identity_problems(
            metadata.get("source_artifact_identity"), "source_artifact_identity"
        )
    )
    problems.extend(
        _checkpoint_artifact_identity_problems(
            metadata.get("target_artifact_identity"), "target_artifact_identity"
        )
    )
    split_provenance = metadata.get("split_provenance")
    if not isinstance(split_provenance, Mapping) or set(split_provenance) != {
        "train",
        "validation",
        "heldout",
    }:
        problems.append("T065 checkpoint split provenance is missing or incomplete")
    else:
        for split in ("train", "validation", "heldout"):
            entry = split_provenance.get(split)
            if not isinstance(entry, Mapping) or any(
                isinstance(entry.get(key), bool)
                or not isinstance(entry.get(key), int)
                or entry.get(key, -1) < 0
                for key in ("state_count", "target_row_count")
            ):
                problems.append(
                    f"T065 checkpoint {split} split provenance is incomplete"
                )
    expected_provenance_fields = {
        "source_provenance": ("artifact_identity", "kind", "normal_information"),
        "target_provenance": (
            "artifact_identity",
            "kind",
            "all_eligible_actions",
            "continuation_policy",
        ),
    }
    for key, required_fields in expected_provenance_fields.items():
        value = metadata.get(key)
        if not isinstance(value, Mapping) or not value:
            problems.append(f"T065 checkpoint {key} is missing or empty")
        else:
            missing_fields = [field for field in required_fields if field not in value]
            if missing_fields:
                problems.append(
                    f"T065 checkpoint {key} fields are missing: "
                    + ", ".join(missing_fields)
                )
            problems.extend(
                _checkpoint_artifact_identity_problems(
                    value.get("artifact_identity"), f"{key}.artifact_identity"
                )
            )
            if not isinstance(value.get("kind"), str) or not value.get("kind"):
                problems.append(f"T065 checkpoint {key} kind is missing")
            if (
                key == "source_provenance"
                and value.get("normal_information") is not True
            ):
                problems.append(
                    "T065 checkpoint source_provenance normal_information is invalid"
                )
            if key == "target_provenance":
                if value.get("all_eligible_actions") is not True:
                    problems.append(
                        "T065 checkpoint target_provenance all_eligible_actions "
                        "is invalid"
                    )
                if not isinstance(
                    value.get("continuation_policy"), str
                ) or not value.get("continuation_policy"):
                    problems.append(
                        "T065 checkpoint target_provenance continuation_policy "
                        "is missing"
                    )
    normalizer = metadata.get("normalizers")
    if not isinstance(normalizer, Mapping):
        problems.append("T065 checkpoint normalizers are missing")
    return problems


def _checkpoint_artifact_identity_problems(
    value: Mapping[str, Any] | None,
    label: str,
) -> list[str]:
    """Require a complete, non-empty artifact identity in checkpoint metadata."""

    if not isinstance(value, Mapping) or not value:
        return [f"T065 checkpoint {label} is missing or empty"]
    problems: list[str] = []
    path = value.get("path")
    if not isinstance(path, str) or not path:
        problems.append(f"T065 checkpoint {label} path is missing")
    if not _is_sha256(value.get("sha256")):
        problems.append(f"T065 checkpoint {label} sha256 is invalid")
    for identity_field in ("size_bytes", "record_count"):
        number = value.get(identity_field)
        if isinstance(number, bool) or not isinstance(number, int) or number < 0:
            problems.append(f"T065 checkpoint {label} {identity_field} is invalid")
    return problems


def _schema_from_document(value: Any) -> list[str]:
    if not isinstance(value, Mapping):
        return ["T065 model-input schema metadata is missing"]
    expected = non_combat_model_input_schema()
    problems: list[str] = []
    for key, expected_value in expected.items():
        actual = value.get(key)
        if key == "public_context_feature_names" and isinstance(actual, Sequence):
            actual = list(actual)
        if actual != expected_value:
            problems.append(f"T065 schema field {key!r} does not match frozen value")
    return problems


def _normalizers_from_dict(value: Any) -> T065Normalizers:
    if not isinstance(value, Mapping):
        raise ValueError("T065 normalizers must be an object")
    if value.get("dtype") != "torch.float32":
        raise ValueError("T065 normalizer dtype is unsupported")
    if value.get("device") != "cpu":
        raise ValueError("T065 normalizer device is unsupported")
    if value.get("std_semantics") != "population_unbiased_false_clamp_min_1.0":
        raise ValueError("T065 normalizer standard-deviation semantics are unsupported")
    return T065Normalizers(
        state_mean=_float_tuple(value.get("state_mean"), "state_mean"),
        state_std=_float_tuple(value.get("state_std"), "state_std"),
        action_mean=_float_tuple(value.get("action_mean"), "action_mean"),
        action_std=_float_tuple(value.get("action_std"), "action_std"),
        fitted_state_count=_int_field(value, "fitted_state_count"),
        fitted_action_count=_int_field(value, "fitted_action_count"),
    )


def _target_from_dict(value: Any) -> T065CounterfactualTarget:
    if not isinstance(value, Mapping):
        raise ValueError("T065 target row must be an object")
    if (
        value.get("schema_id") != T065_TARGET_TABLE_SCHEMA_ID
        or value.get("schema_version") != 1
    ):
        raise ValueError("unsupported T065 target row schema")
    return T065CounterfactualTarget(
        selected_state_index=_int_field(value, "selected_state_index"),
        state_identity=_str_field(value, "state_identity"),
        family=_str_field(value, "family"),
        split=_str_field(value, "split"),
        legal_action_index=_int_field(value, "legal_action_index"),
        legal_action_identity=_mapping_field(value, "legal_action_identity"),
        continuation_seeds=_int_tuple(
            value.get("continuation_seeds"), "continuation_seeds"
        ),
        terminal_floors=_float_tuple(value.get("terminal_floors"), "terminal_floors"),
        terminal_acts=_required_optional_float_tuple(value, "terminal_acts"),
        terminal_statuses=_str_tuple(
            value.get("terminal_statuses"), "terminal_statuses"
        ),
        terminal_current_hps=_required_optional_float_tuple(
            value, "terminal_current_hps"
        ),
        terminal_max_hps=_required_optional_float_tuple(value, "terminal_max_hps"),
        terminal_golds=_required_optional_float_tuple(value, "terminal_golds"),
        terminal_potion_counts=_required_optional_float_tuple(
            value, "terminal_potion_counts"
        ),
        q_floor=_finite_float_field(value, "q_floor"),
        target_status=_str_field(value, "target_status"),
        simulator_cost=_mapping_field(value, "simulator_cost"),
        wall_clock_seconds=_finite_float_field(value, "wall_clock_seconds"),
        problems=_str_tuple(value.get("problems"), "problems"),
    )


def _replace_source_state(state: T065SourceState, **changes: Any) -> T065SourceState:
    values = {
        field_name: getattr(state, field_name)
        for field_name in state.__dataclass_fields__
    }
    values.update(changes)
    return T065SourceState(**values)


def _run_entered_act2(run: ControlledRun) -> bool:
    if (
        _raw_number(run.final_raw, "act") is not None
        and _raw_number(run.final_raw, "act") >= 2
    ):
        return True
    return any(
        step.next_snapshot_raw.get("act") is not None
        and float(step.next_snapshot_raw.get("act")) >= 2
        for step in run.steps
    )


def _controlled_run_cost(run: ControlledRun) -> dict[str, float]:
    """Aggregate exposed simulator/search cost without inferring hidden work."""

    cost: dict[str, float] = {
        "simulator_steps": float(len(run.steps)),
        "battle_decisions": float(
            sum(step.controller_role == "battle_agent" for step in run.steps)
        ),
        "non_combat_decisions": float(
            sum(step.controller_role == "non_combat_driver" for step in run.steps)
        ),
        "native_search_simulator_steps": 0.0,
        "native_search_wall_clock_seconds": 0.0,
        "native_search_decisions": 0.0,
    }
    for step in run.steps:
        metadata = step.decision_metadata
        native_steps = metadata.get("oracle_search_native_simulator_steps")
        if isinstance(native_steps, (int, float)) and not isinstance(
            native_steps, bool
        ):
            cost["native_search_simulator_steps"] += float(native_steps)
        native_wall = metadata.get("oracle_search_wall_clock_time_s")
        if isinstance(native_wall, (int, float)) and not isinstance(native_wall, bool):
            cost["native_search_wall_clock_seconds"] += float(native_wall)
        if "oracle_search_decision_count" in metadata:
            cost["native_search_decisions"] += float(
                metadata.get("oracle_search_decision_count", 0.0)
            )
    return cost


def _add_search_cost(cost: dict[str, float], run: ControlledRun) -> None:
    run_cost = _controlled_run_cost(run)
    for key in (
        "native_search_simulator_steps",
        "native_search_wall_clock_seconds",
        "native_search_decisions",
    ):
        cost[key] += run_cost[key]


def _validate_workers(worker_count: int) -> None:
    if (
        isinstance(worker_count, bool)
        or not isinstance(worker_count, int)
        or not 1 <= worker_count <= T065_MAX_WORKERS
    ):
        raise ValueError("T065 worker_count must be between 1 and 16")


def _require_torch() -> Any:
    try:
        import torch
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "T065 training requires the optional train dependency (PyTorch)"
        ) from exc
    return torch


def _validate_tensor_width(tensor: Any, expected: int, label: str) -> None:
    if tensor.ndim != 2 or tensor.shape[1] != expected:
        raise ValueError(f"T065 {label} tensor width does not match {expected}")


def _canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        _json_safe(value),
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return [_json_safe(item) for item in value]
    return str(value)


def _raw_number(raw: Mapping[str, Any], *keys: str) -> float | None:
    for key in keys:
        value = raw.get(key)
        if isinstance(value, bool):
            continue
        if isinstance(value, (int, float)) and math.isfinite(float(value)):
            return float(value)
    return None


def _terminal_current_hp(raw: Mapping[str, Any]) -> float | None:
    direct = _raw_number(raw, "cur_hp", "current_hp")
    if direct is not None:
        return direct
    for field_name in ("battle_player", "player"):
        nested = raw.get(field_name)
        if isinstance(nested, Mapping):
            value = _raw_number(nested, "cur_hp", "current_hp")
            if value is not None:
                return value
    return None


def _terminal_max_hp(raw: Mapping[str, Any]) -> float | None:
    direct = _raw_number(raw, "max_hp", "maxHp")
    if direct is not None:
        return direct
    for field_name in ("battle_player", "player"):
        nested = raw.get(field_name)
        if isinstance(nested, Mapping):
            value = _raw_number(nested, "max_hp", "maxHp")
            if value is not None:
                return value
    return None


def _terminal_potion_count(raw: Mapping[str, Any]) -> float | None:
    direct = _raw_number(raw, "battle_potion_count", "potion_count")
    if direct is not None:
        return direct
    for field_name in ("battle_potions", "potions"):
        potions = raw.get(field_name)
        if isinstance(potions, Sequence) and not isinstance(potions, (str, bytes)):
            return float(len(potions))
    return None


def _number_or_none(value: Mapping[str, Any], nested: str, key: str) -> float | None:
    nested_value = value.get(nested)
    if isinstance(nested_value, Mapping):
        return _raw_number(nested_value, key)
    return None


def _int_field(value: Mapping[str, Any], key: str) -> int:
    raw = value.get(key)
    if isinstance(raw, bool) or not isinstance(raw, int):
        raise ValueError(f"T065 field {key!r} must be an integer")
    return raw


def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError("T065 optional integer is invalid")
    return value


def _str_field(value: Mapping[str, Any], key: str) -> str:
    raw = value.get(key)
    if not isinstance(raw, str) or not raw:
        raise ValueError(f"T065 field {key!r} must be a non-empty string")
    return raw


def _mapping_field(value: Mapping[str, Any], key: str) -> dict[str, Any]:
    raw = value.get(key)
    if not isinstance(raw, Mapping):
        raise ValueError(f"T065 field {key!r} must be an object")
    return {str(item_key): _json_safe(item) for item_key, item in raw.items()}


def _mapping_or_empty(value: Any) -> dict[str, Any]:
    return (
        {str(key): _json_safe(item) for key, item in value.items()}
        if isinstance(value, Mapping)
        else {}
    )


def _int_keyed_int_mapping(value: Any) -> dict[int, int]:
    if value in (None, {}):
        return {}
    if not isinstance(value, Mapping):
        raise ValueError("T065 expert action indices must be an object")
    result: dict[int, int] = {}
    for raw_key, raw_value in value.items():
        try:
            key = int(raw_key)
        except (TypeError, ValueError) as exc:
            raise ValueError("T065 expert action index key is invalid") from exc
        if isinstance(raw_value, bool) or not isinstance(raw_value, int):
            raise ValueError("T065 expert action index value is invalid")
        result[key] = raw_value
    return result


def _nested_provenance(provenance: Mapping[str, Any], child: str) -> dict[str, Any]:
    config = provenance.get("config")
    if not isinstance(config, Mapping):
        return {}
    value = config.get(child)
    return dict(value) if isinstance(value, Mapping) else {}


def _float_tuple(value: Any, label: str) -> tuple[float, ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise ValueError(f"T065 {label} must be a numeric list")
    if any(
        isinstance(item, bool) or not isinstance(item, (int, float)) for item in value
    ):
        raise ValueError(f"T065 {label} contains a non-numeric value")
    result = tuple(float(item) for item in value)
    if any(not math.isfinite(item) for item in result):
        raise ValueError(f"T065 {label} contains non-finite values")
    return result


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("T065 optional float is invalid")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError("T065 optional float is non-finite")
    return result


def _finite_float_field(value: Mapping[str, Any], key: str) -> float:
    raw = value.get(key)
    if isinstance(raw, bool) or not isinstance(raw, (int, float)):
        raise ValueError(f"T065 field {key!r} must be a finite number")
    result = float(raw)
    if not math.isfinite(result):
        raise ValueError(f"T065 field {key!r} must be a finite number")
    return result


def _optional_float_tuple(value: Any) -> tuple[float | None, ...]:
    if value in (None, []):
        return ()
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise ValueError("T065 optional float list is invalid")
    return tuple(_optional_float(item) for item in value)


def _required_optional_float_tuple(
    value: Mapping[str, Any], key: str
) -> tuple[float | None, ...]:
    if key not in value:
        raise ValueError(f"T065 target field {key!r} is missing")
    return _optional_float_tuple(value[key])


def _int_tuple(value: Any, label: str) -> tuple[int, ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise ValueError(f"T065 {label} must be an integer list")
    result = tuple(_optional_int(item) for item in value)
    if any(item is None for item in result):
        raise ValueError(f"T065 {label} contains a null integer")
    return tuple(int(item) for item in result)


def _str_tuple(value: Any, label: str) -> tuple[str, ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise ValueError(f"T065 {label} must be a string list")
    if not all(isinstance(item, str) for item in value):
        raise ValueError(f"T065 {label} contains a non-string")
    return tuple(value)


def _float_matrix(value: Any, label: str) -> tuple[tuple[float, ...], ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise ValueError(f"T065 {label} must be a matrix")
    return tuple(_float_tuple(row, f"{label} row") for row in value)


def _mapping_tuple(value: Any, label: str) -> tuple[Mapping[str, Any], ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise ValueError(f"T065 {label} must be an object list")
    if not all(isinstance(item, Mapping) for item in value):
        raise ValueError(f"T065 {label} contains a non-object")
    return tuple(_mapping_or_empty(item) for item in value)


def _step_legal_identities(context: DecisionContext) -> Sequence[Mapping[str, Any]]:
    return [
        item.get("identity", {})
        for item in context.tactical_legal_actions
        if isinstance(item, Mapping)
    ]
