"""Bounded native execution seam for the T085 paired evaluation.

Source generation and battle mechanics remain owned by the pinned
``sts_lightspeed`` simulator.  This module composes the existing T085 source
and restore/parity validators, wraps an existing simulator adapter, and
retains a terminal label only when the selected action's *pre-action* native
search root edge proves the transition terminal.  The retained utility is the
native root-edge mean verbatim; this module never reimplements
``evaluateEndState`` or computes a game-mechanics formula in Python.

The paired runner owns restore/controller stepping.  The canonical restore
helper is called on the unwrapped simulator adapter and its verified snapshot
is then primed into the terminal-label proxy; the runner performs search before
every in-battle ``step`` and derives survival from the simulator's authoritative
terminal transition.  Caller-supplied survival, utility, cohort, arm, budget,
or provenance fields are not accepted.
"""

from __future__ import annotations

import ctypes
import gc
import json
import math
import os
import tempfile
import time
from collections.abc import Callable, Iterable, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field, replace
from hashlib import sha256
from pathlib import Path
from typing import Any, Literal

try:
    import fcntl
except ImportError:  # pragma: no cover - exercised only on Windows
    fcntl = None

from sts_combat_rl.sim.action_space import ActionSpaceConfig
from sts_combat_rl.sim.assisted_source_generation import (
    ASSISTED_SOURCE_POOL_FORMAT_VERSION,
    ASSISTED_SOURCE_POOL_MERGE_VERSION,
    ASSISTED_SOURCE_POOL_SCHEMA_ID,
    AssistedSourcePoolArtifact,
    assistance_schedule_by_level,
    collect_assisted_battle_start_pool,
    dump_assisted_source_pool_jsonl,
    dump_merged_assisted_source_pool_shards_jsonl,
    load_assisted_source_pool_jsonl,
    restore_assisted_battle_start_record,
)
from sts_combat_rl.sim.battle_search_v2 import _node_context
from sts_combat_rl.sim.battle_start_pool import (
    BATTLE_START_POOL_FORMAT_VERSION,
    BATTLE_START_POOL_SHARD_MERGE_SCHEMA_ID,
    BATTLE_START_POOL_SHARD_MERGE_VERSION,
    BattleStartCheckpointRecord,
    NaturalBattleStartPool,
    collect_natural_battle_start_pool,
    dump_merged_natural_battle_start_pool_shards_jsonl,
    dump_natural_battle_start_pool_jsonl,
    load_natural_battle_start_pool_jsonl,
    load_natural_battle_start_pool_metadata_jsonl,
    record_from_manifest,
    restore_battle_start_record,
)
from sts_combat_rl.sim.contract import (
    SimulatorAction,
    SimulatorSnapshot,
    SimulatorTransition,
)
from sts_combat_rl.sim.controlled_run import (
    ControlledRun,
    build_decision_context,
    execute_controlled_run,
)
from sts_combat_rl.sim.controller_contract import (
    ControllerDecision,
    ControllerProvenance,
    OnlineController,
)
from sts_combat_rl.sim.decision_record import action_identity_dicts_for_actions
from sts_combat_rl.sim.fixed_evaluation_set import load_fixed_cohort_jsonl
from sts_combat_rl.sim.lightspeed_source import load_lightspeed_source_manifest
from sts_combat_rl.sim.non_combat_policy import ExpertNonCombatDriver
from sts_combat_rl.sim.online_controller import (
    NATIVE_SEARCH_INFORMATION_REGIME,
    PolicyController,
    RoutedRunController,
)
from sts_combat_rl.sim.oracle_search import (
    ORACLE_SEARCH_NATIVE_API,
    ORACLE_SEARCH_PATCH_IDENTITY,
    ORACLE_SEARCH_SCHEMA_ID,
    OracleSearchController,
    OracleSearchReport,
    build_oracle_search_report,
    oracle_search_controller_metadata,
    select_oracle_root_action,
)
from sts_combat_rl.sim.public_context_artifacts import PUBLIC_CONTEXT_AVAILABLE
from sts_combat_rl.sim.search_guidance_inference import (
    SEARCH_V2_LEAF_NATIVE_UTILITY_TARGET_KIND,
    SearchGuidanceScorer,
    search_guidance_scorer_checkpoint_provenance,
    validate_search_guidance_result,
)
from sts_combat_rl.t085_corrected_leaf_value_search_evaluation import (
    T085_ARTIFACT_ROOT,
    T085_COHORT_B_RUN_COUNT,
    T085_COHORT_B_SEED_END,
    T085_COHORT_B_SEED_START,
    T085_COHORT_B_SELECTED_COUNT,
    T085_COHORT_C_MIN_SELECTED_COUNT,
    T085_COHORT_C_RUN_COUNT,
    T085_COHORT_C_SEED_END,
    T085_COHORT_C_SEED_START,
    T085_INPUT_ARTIFACT_IDENTITIES,
    T085_NATIVE_IDENTITY,
    T085_SEARCH_400_ARMS,
    T085_SOURCE_MANIFEST_SCHEMA_ID,
    T085_T042_SCALE_MANIFEST_SHA256,
    T085_T052_COHORT_PATH,
    T085_T052_COHORT_SHA256,
    T085BattleStartRecord,
    T085EvaluationIntegrityError,
    T085OutcomeRecord,
    T085SourceRunRecord,
    build_t085_cohort_selection,
    build_t085_evaluation_selection_evidence,
    run_t085_paired_evaluation,
    select_cohort_b,
    select_cohort_c,
    select_search_400_subset,
    sha256_file,
    validate_t085_evaluation_selection_evidence,
    validate_t085_source_generation_contract,
    write_t085_json_artifact,
)

T085_NATIVE_V2_API = "StepSimulator.battle_search_v2.v1"
T085_NATIVE_V2_PATCH = "sts_lightspeed_battle_search_v2_tree_internal_v1"
T085_NATIVE_TERMINAL_LABEL_SCHEMA_ID = "t085-native-terminal-root-label-v1"
T085_NATIVE_SELECTION_SCHEMA_ID = "t085-native-selection-artifact-v1"
T085_NATIVE_SELECTION_INPUT_SCHEMA_ID = "t085-native-selection-input-v1"
T085_NATIVE_SELECTION_RESTORE_SHARD_SCHEMA_ID = "t085-native-selection-restore-shard-v1"
T085_NATIVE_SELECTION_RESTORE_EVIDENCE_SCHEMA_ID = (
    "t085-native-selection-restore-evidence-v1"
)
T085_NATIVE_OUTCOMES_SCHEMA_ID = "t085-native-outcome-records-v1"
T085_NATIVE_EXECUTION_VERSION = "t085-native-execution-v1"
T085_NATIVE_SHARD_SCHEMA_ID = "t085-native-shard-manifest-v1"
T085_C_SOURCE_SHARD_MANIFEST_SCHEMA_ID = "t085-cohort-c-source-shard-manifest-v1"
T085_C_SOURCE_POOL_SCHEMA_ID = "natural-battle-start-pool-v4-jsonl"
T085_B_SOURCE_SHARD_MANIFEST_SCHEMA_ID = "t085-cohort-b-source-shard-manifest-v1"
T085_B_SOURCE_POOL_SCHEMA_ID = ASSISTED_SOURCE_POOL_SCHEMA_ID
T085_BOUNDED_RUN_TRUNCATION_FAILURE_REASON = "bounded_run_truncated"
T085_NATIVE_SEARCH_BACKENDS = ("battle_search", "battle_search_v2")
T085NativeSearchBackend = Literal["battle_search", "battle_search_v2"]
T085_HISTORICAL_OUTCOME_TARGET_KIND = "terminal_battle_survival_probability"


def _release_t085_chunk_memory() -> None:
    """Collect Python wrappers and return released native heap pages when able."""

    gc.collect()
    if os.name != "nt":
        try:
            trim = getattr(ctypes.CDLL(None), "malloc_trim", None)
        except OSError:
            trim = None
        if callable(trim):
            trim(0)


@contextmanager
def _t085_cohort_b_finalization_lock(
    artifact_root: str | Path,
):
    """Serialize Cohort-B artifact finalization across processes sharing a root."""

    root = Path(artifact_root).resolve()
    root.mkdir(parents=True, exist_ok=True)
    lock_path = root / ".t085-cohort-b-finalization.lock"
    with lock_path.open("a+", encoding="utf-8") as lock_file:
        if fcntl is None:  # pragma: no cover - exercised only on Windows
            import msvcrt

            lock_file.seek(0)
            lock_file.write("0")
            lock_file.flush()
            msvcrt.locking(lock_file.fileno(), msvcrt.LK_LOCK, 1)
        else:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            if fcntl is None:  # pragma: no cover - exercised only on Windows
                import msvcrt

                lock_file.seek(0)
                msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


def _write_t085_json_artifact_atomically(
    path: str | Path,
    payload: Mapping[str, object],
    *,
    schema_id: str,
) -> dict[str, object]:
    """Write a T085 JSON artifact through a same-root temporary file."""

    target = _require_t085_stable_path(path, "JSON artifact output")
    temporary = target.with_name(f".{target.name}.{os.getpid()}.tmp")
    try:
        reference = write_t085_json_artifact(
            temporary,
            payload,
            schema_id=schema_id,
        )
        os.replace(temporary, target)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise
    reference["path"] = str(target)
    return reference


T085NativeSourceArtifactKind = Literal["fixed_cohort", "natural_pool", "assisted_pool"]

_TERMINAL_OUTCOMES = frozenset({"PLAYER_VICTORY", "PLAYER_LOSS"})

T085_PRIMARY_ARMS = (
    "baseline",
    "old_value_64001",
    "corrected_value_85001",
    "old_value_64002",
    "corrected_value_85002",
)
T085_SECONDARY_ARMS = (
    "prior_only_64001",
    "prior_corrected_85001",
    "prior_only_64002",
    "prior_corrected_85002",
)


@dataclass(frozen=True)
class T085NativeShardPlan:
    """Explicit 16-worker partition contract for restored paired evaluation."""

    shard_index: int
    shard_count: int
    worker_count: int

    def __post_init__(self) -> None:
        for value, label in (
            (self.shard_index, "shard_index"),
            (self.shard_count, "shard_count"),
            (self.worker_count, "worker_count"),
        ):
            if isinstance(value, bool) or not isinstance(value, int):
                raise T085NativeExecutionError(f"T085 {label} must be an integer")
        if self.shard_count != 16:
            raise T085NativeExecutionError(
                "T085 native paired evaluation requires exactly 16 shards"
            )
        if not 0 <= self.shard_index < self.shard_count:
            raise T085NativeExecutionError(
                "T085 shard_index must be in [0, shard_count)"
            )
        if self.worker_count != 16:
            raise T085NativeExecutionError(
                "T085 native paired evaluation requires worker_count=16"
            )

    def to_dict(self, *, selection_identity_sha256: str) -> dict[str, object]:
        return {
            "schema_id": T085_NATIVE_SHARD_SCHEMA_ID,
            "task_id": "T085",
            "shard_index": self.shard_index,
            "shard_count": self.shard_count,
            "worker_count": self.worker_count,
            "effective_worker_count": self.worker_count,
            "partition_scheme": "sha256(selection_identity)[:8] mod shard_count",
            "merge_key": "cohort/record_identity/arm",
            "selection_identity_sha256": selection_identity_sha256,
            # A shard is a finished partition, not a complete scientific
            # evaluation.  Some deterministic partitions legitimately have no
            # rows from one or more cohorts; the merge stage owns the full
            # support/completeness gate.
            "artifact_scope": "paired_evaluation_shard",
            "shard_finished": True,
            "partial": True,
            "complete": False,
        }


@dataclass(frozen=True)
class T085CohortBSourceGenerationPlan:
    """Fixed assisted source-generation contract for one Cohort-B shard."""

    shard_index: int
    shard_count: int = 16
    worker_count: int = 16

    def __post_init__(self) -> None:
        for value, label in (
            (self.shard_index, "shard_index"),
            (self.shard_count, "shard_count"),
            (self.worker_count, "worker_count"),
        ):
            if isinstance(value, bool) or not isinstance(value, int):
                raise T085NativeExecutionError(
                    f"T085 Cohort B {label} must be an integer"
                )
        if self.shard_count != 16:
            raise T085NativeExecutionError(
                "T085 Cohort B source generation requires exactly 16 shards"
            )
        if not 0 <= self.shard_index < self.shard_count:
            raise T085NativeExecutionError(
                "T085 Cohort B source shard_index must be in [0, 16)"
            )
        if self.worker_count != 16:
            raise T085NativeExecutionError(
                "T085 Cohort B source generation requires worker_count=16"
            )

    @property
    def seed_inventory(self) -> tuple[int, ...]:
        """Return the contiguous 64-seed range assigned to this shard."""

        per_shard = T085_COHORT_B_RUN_COUNT // self.shard_count
        start = T085_COHORT_B_SEED_START + self.shard_index * per_shard
        return tuple(range(start, start + per_shard))

    @property
    def full_seed_inventory(self) -> tuple[int, ...]:
        return tuple(range(T085_COHORT_B_SEED_START, T085_COHORT_B_SEED_END + 1))

    def to_dict(
        self,
        *,
        native_identity: Mapping[str, object],
        t042_anchor: Mapping[str, object],
    ) -> dict[str, object]:
        anchor = dict(t042_anchor)
        return {
            "schema_id": T085_B_SOURCE_SHARD_MANIFEST_SCHEMA_ID,
            "task_id": "T085",
            "cohort": "B",
            "artifact_scope": "source_generation_shard",
            "partial": True,
            "complete": False,
            "shard_index": self.shard_index,
            "shard_count": self.shard_count,
            "worker_count": self.worker_count,
            "effective_worker_count": self.worker_count,
            "partition_scheme": "contiguous_seed_ranges",
            "source_run_seed_start": T085_COHORT_B_SEED_START,
            "source_run_seed_end": T085_COHORT_B_SEED_END,
            "source_run_count": T085_COHORT_B_RUN_COUNT,
            "shard_source_run_count": len(self.seed_inventory),
            "shard_source_run_seed_start": self.seed_inventory[0],
            "shard_source_run_seed_end": self.seed_inventory[-1],
            "shard_source_run_seed_inventory": list(self.seed_inventory),
            "max_outer_steps": 500,
            "action_space": "initial_no_potions",
            "battle_controller": "oracle_search",
            "battle_simulations": 20,
            "root_selection": "highest_mean",
            "non_combat_controller": "expert_non_combat_v1",
            "non_combat_policy_seed": 42042,
            "assistance_level": "assist_hp75_potion",
            "assistance_policy_seed": 42042,
            # battle_search v1 has no callback surface.  Recording explicit
            # nulls makes the no-guidance boundary auditable in the shard.
            "policy_prior_callback": None,
            "leaf_value_callback": None,
            "native_identity": dict(native_identity),
            "t042_scale_manifest": anchor,
            "t042_scale_manifest_sha256": T085_T042_SCALE_MANIFEST_SHA256,
        }


@dataclass(frozen=True)
class T085CohortCSourceGenerationPlan:
    """Fixed source-generation contract for one Cohort-C worker shard."""

    shard_index: int
    shard_count: int = 16
    worker_count: int = 16

    def __post_init__(self) -> None:
        for value, label in (
            (self.shard_index, "shard_index"),
            (self.shard_count, "shard_count"),
            (self.worker_count, "worker_count"),
        ):
            if isinstance(value, bool) or not isinstance(value, int):
                raise T085NativeExecutionError(
                    f"T085 Cohort C {label} must be an integer"
                )
        if self.shard_count != 16:
            raise T085NativeExecutionError(
                "T085 Cohort C source generation requires exactly 16 shards"
            )
        if not 0 <= self.shard_index < self.shard_count:
            raise T085NativeExecutionError(
                "T085 Cohort C source shard_index must be in [0, 16)"
            )
        if self.worker_count != 16:
            raise T085NativeExecutionError(
                "T085 Cohort C source generation requires worker_count=16"
            )

    @property
    def seed_inventory(self) -> tuple[int, ...]:
        """Return the contiguous eight-seed range assigned to this shard."""

        per_shard = T085_COHORT_C_RUN_COUNT // self.shard_count
        start = T085_COHORT_C_SEED_START + self.shard_index * per_shard
        return tuple(range(start, start + per_shard))

    @property
    def full_seed_inventory(self) -> tuple[int, ...]:
        return tuple(range(T085_COHORT_C_SEED_START, T085_COHORT_C_SEED_END + 1))

    def to_dict(self, *, native_identity: Mapping[str, object]) -> dict[str, object]:
        return {
            "schema_id": T085_C_SOURCE_SHARD_MANIFEST_SCHEMA_ID,
            "task_id": "T085",
            "cohort": "C",
            "artifact_scope": "source_generation_shard",
            "partial": True,
            "complete": False,
            "shard_index": self.shard_index,
            "shard_count": self.shard_count,
            "worker_count": self.worker_count,
            "effective_worker_count": self.worker_count,
            "partition_scheme": "contiguous_seed_ranges",
            "source_run_seed_start": T085_COHORT_C_SEED_START,
            "source_run_seed_end": T085_COHORT_C_SEED_END,
            "source_run_count": T085_COHORT_C_RUN_COUNT,
            "shard_source_run_count": len(self.seed_inventory),
            "shard_source_run_seed_start": self.seed_inventory[0],
            "shard_source_run_seed_end": self.seed_inventory[-1],
            "shard_source_run_seed_inventory": list(self.seed_inventory),
            "max_outer_steps": 500,
            "action_space": "initial_no_potions",
            "battle_controller": "unguided_search_v2",
            "battle_simulations": 100,
            "root_selection": "highest_mean",
            "non_combat_controller": "expert_non_combat_v1",
            "non_combat_policy_seed": 42042,
            "assistance_level": "assist_0",
            "assistance_policy_seed": None,
            "policy_prior_callback": None,
            "leaf_value_callback": None,
            "native_identity": dict(native_identity),
        }


def resolve_t085_canonical_records(
    path: str | Path = T085_T052_COHORT_PATH,
    *,
    expected_sha256: str = T085_T052_COHORT_SHA256,
    artifact_kind: Literal[
        "fixed_cohort", "natural_pool", "assisted_pool"
    ] = "fixed_cohort",
    expected_source_run_count: int | None = None,
    expected_source_run_identity_inventory: Sequence[str] | None = None,
    expected_source_run_seed_inventory: Sequence[int] | None = None,
    expected_assistance_level: str | None = None,
    expected_source_manifest_path: str | Path | None = None,
    expected_source_manifest_sha256: str | None = None,
) -> dict[str, BattleStartCheckpointRecord]:
    """Load one explicitly typed, verified full-record source artifact.

    The explicit kind is intentional: a natural or assisted source pool must
    never be silently interpreted as the T052 fixed cohort, and vice versa.
    """
    resolved = Path(path).resolve(strict=True)
    source_manifest_binding = _validate_t085_source_manifest_binding(
        resolved,
        artifact_kind=artifact_kind,
        manifest_path=expected_source_manifest_path,
        manifest_sha256=expected_source_manifest_sha256,
    )
    digest = sha256_file(resolved)
    if digest != expected_sha256:
        raise T085NativeExecutionError(
            "T085 canonical cohort bytes do not match the accepted SHA-256"
        )
    with resolved.open(encoding="utf-8") as stream:
        if artifact_kind == "fixed_cohort":
            loaded = load_fixed_cohort_jsonl(stream)
            full_records: Iterable[object] = loaded.records
            source_pool = None
        elif artifact_kind == "natural_pool":
            source_pool = load_natural_battle_start_pool_jsonl(stream)
            full_records = source_pool.records
        elif artifact_kind == "assisted_pool":
            loaded_assisted = load_assisted_source_pool_jsonl(stream)
            source_pool = loaded_assisted.pool
            full_records = loaded_assisted.records
            if (
                expected_assistance_level is not None
                and loaded_assisted.assistance_level != expected_assistance_level
            ):
                raise T085NativeExecutionError(
                    "T085 assisted source-pool assistance level does not match "
                    "selection evidence"
                )
        else:  # pragma: no cover - Literal protects callers, fail closed at runtime
            raise T085NativeExecutionError(
                f"unsupported T085 source artifact kind {artifact_kind!r}"
            )
    if source_pool is not None:
        source_run_count = getattr(source_pool, "source_run_count", None)
        source_controller_provenance = getattr(
            source_pool, "source_controller_provenance", None
        )
        source_run_summaries = getattr(source_pool, "source_run_summaries", None)
        if not isinstance(source_run_count, int) or source_run_count <= 0:
            raise T085NativeExecutionError(
                "T085 source pool lacks a positive source_run_count"
            )
        if (
            not isinstance(source_controller_provenance, Mapping)
            or not source_controller_provenance
        ):
            raise T085NativeExecutionError(
                "T085 source pool lacks controller provenance"
            )
        if not isinstance(source_run_summaries, Sequence) or isinstance(
            source_run_summaries, (str, bytes)
        ):
            raise T085NativeExecutionError(
                "T085 source pool lacks current source-run summaries"
            )
        summary_ids = [
            getattr(summary, "source_run_id", None) for summary in source_run_summaries
        ]
        summary_seeds = [
            getattr(summary, "source_seed", None) for summary in source_run_summaries
        ]
        if any(not isinstance(value, str) or not value for value in summary_ids):
            raise T085NativeExecutionError(
                "T085 source pool source-run summaries have invalid identities"
            )
        if any(
            isinstance(value, bool) or not isinstance(value, int)
            for value in summary_seeds
        ):
            raise T085NativeExecutionError(
                "T085 source pool source-run summaries have invalid seeds"
            )
        if (
            len(summary_ids) != source_run_count
            or len(set(summary_ids)) != source_run_count
        ):
            raise T085NativeExecutionError(
                "T085 source pool source-run summary count/uniqueness is invalid"
            )
        if (
            expected_source_run_count is not None
            and source_run_count != expected_source_run_count
        ):
            raise T085NativeExecutionError(
                "T085 source pool count does not match selection evidence"
            )
        if expected_source_run_identity_inventory is not None and summary_ids != list(
            expected_source_run_identity_inventory
        ):
            raise T085NativeExecutionError(
                "T085 source pool source-run identities do not match selection evidence"
            )
        if expected_source_run_seed_inventory is not None and summary_seeds != list(
            expected_source_run_seed_inventory
        ):
            raise T085NativeExecutionError(
                "T085 source pool source-run seeds do not match selection evidence"
            )
        expected_distribution = (
            "assisted_run" if artifact_kind == "assisted_pool" else "natural_run"
        )
        for index, record in enumerate(full_records):
            if not isinstance(record, BattleStartCheckpointRecord):
                raise T085NativeExecutionError(
                    f"T085 {artifact_kind} record {index} is not a full restore record"
                )
            if record.distribution_kind != expected_distribution:
                raise T085NativeExecutionError(
                    f"T085 source pool record {index} has wrong distribution kind"
                )
            if (
                not record.source_controller_provenance
                or not record.source_battle_controller_provenance
            ):
                raise T085NativeExecutionError(
                    f"T085 source pool record {index} lacks controller provenance"
                )
        if source_manifest_binding is not None:
            expected_pool_seeds = tuple(summary_seeds)
            if artifact_kind == "assisted_pool":
                _validate_t085_b_source_pool(
                    loaded_assisted,
                    controller=build_t085_cohort_b_source_controller(),
                    expected_seeds=expected_pool_seeds,
                )
            else:
                merged_source_metadata = _validate_t085_c_merged_source_metadata(
                    resolved,
                    source_pool,
                )
                _validate_t085_c_source_pool(
                    source_pool,
                    controller=build_t085_cohort_c_source_controller(),
                    expected_seeds=expected_pool_seeds,
                )
        if source_manifest_binding is not None:
            source_manifest, _ = source_manifest_binding
            if source_manifest.get("source_run_count") != source_run_count:
                raise T085NativeExecutionError(
                    "T085 source manifest source_run_count does not match pool"
                )
            if source_manifest.get("source_run_identity_inventory") != summary_ids:
                raise T085NativeExecutionError(
                    "T085 source manifest source-run identities do not match pool"
                )
            if source_manifest.get("source_run_seed_inventory") != summary_seeds:
                raise T085NativeExecutionError(
                    "T085 source manifest source-run seeds do not match pool"
                )
            source_pool_reference = source_manifest.get("source_pool_artifact")
            if isinstance(source_pool_reference, Mapping):
                if source_pool_reference.get("record_count") != len(full_records):
                    raise T085NativeExecutionError(
                        "T085 source manifest record_count does not match pool"
                    )
                if source_pool_reference.get("source_run_count") != source_run_count:
                    raise T085NativeExecutionError(
                        "T085 source manifest source_run_count does not match pool"
                    )
            source_controller = source_manifest.get("source_controller_provenance")
            if (
                source_controller is not None
                and source_controller != source_pool.source_controller_provenance
            ):
                raise T085NativeExecutionError(
                    "T085 source manifest controller provenance does not match pool"
                )
            source_merge = source_manifest.get("source_pool_merge")
            if isinstance(source_merge, Mapping):
                if artifact_kind == "assisted_pool":
                    actual_merge = {
                        "merge_version": ASSISTED_SOURCE_POOL_MERGE_VERSION,
                        "shard_count": len(loaded_assisted.source_shards),
                        "source_shards": [
                            dict(shard) for shard in loaded_assisted.source_shards
                        ],
                    }
                else:
                    actual_merge = merged_source_metadata
                if dict(source_merge) != actual_merge:
                    raise T085NativeExecutionError(
                        "T085 source manifest merge provenance does not match pool"
                    )
    records: dict[str, BattleStartCheckpointRecord] = {}
    for index, full in enumerate(full_records):
        if isinstance(full, BattleStartCheckpointRecord):
            record = full
        else:
            # Fixed-cohort rows are a separate schema and require this
            # repository-owned conversion into the restore record.
            if artifact_kind != "fixed_cohort":
                raise T085NativeExecutionError(
                    f"{artifact_kind} loader did not return full restore records"
                )
            raw = {
                "record_index": full.cohort_index,
                "source_checkpoint_id": full.source_checkpoint_id,
                "source_run_id": full.source_run_id,
                "source_seed": full.source_seed,
                "source_battle_index": full.source_battle_index,
                "structural_metadata": full.structural_metadata,
                "source_controller_provenance": full.source_controller_provenance,
                "source_battle_controller_provenance": full.source_battle_controller_provenance,
                "source_non_combat_controller_provenance": full.source_non_combat_controller_provenance,
                "action_trace": list(full.action_trace),
                "snapshot_observation": list(full.snapshot_observation),
                "snapshot_raw": full.snapshot_raw,
                "distribution_kind": full.source_distribution_kind,
                "checkpoint_information_regime": full.checkpoint_information_regime,
                "public_context_status": full.public_context_status,
                "public_run_context": full.public_run_context,
                "assistance_history": list(full.assistance_history),
                "battle_outcome": None,
                "battle_completed": False,
                "completed_battle_resource_outcome_status": "legacy_unavailable",
                "completed_battle_resource_outcome": {},
            }
            record = record_from_manifest(
                raw,
                label=f"T085 canonical record {index}",
                allowed_distribution_kinds=frozenset({"natural_run", "assisted_run"}),
                allow_assistance_history=True,
            )
        if record.source_checkpoint_id in records:
            raise T085NativeExecutionError(
                "T085 canonical cohort contains duplicate checkpoint identities"
            )
        records[record.source_checkpoint_id] = record
    if not records:
        raise T085NativeExecutionError("T085 canonical cohort contains no full records")
    return records


def restore_t085_canonical_record(
    adapter: object,
    selected: T085BattleStartRecord,
    canonical_records: Mapping[str, BattleStartCheckpointRecord],
) -> tuple[SimulatorSnapshot, str]:
    """Restore one selected row only through the accepted canonical helpers."""
    canonical = canonical_records.get(selected.complete_source_identity)
    structural = canonical.structural_metadata if canonical is not None else {}
    identity_matches = (
        canonical is not None
        and canonical.source_checkpoint_id == selected.complete_source_identity
        and canonical.source_run_id == selected.source_run_identity
        and canonical.source_seed == selected.source_run_seed
        and canonical.source_battle_index == _selected_battle_index(selected)
        and structural.get("act") == selected.act
        and str(structural.get("room_type", "")).upper() == selected.room_type
    )
    if not identity_matches:
        raise T085NativeExecutionError(
            "T085 selected row does not match canonical checkpoint/source/seed/battle/act/room identity"
        )
    if canonical.distribution_kind == "assisted_run":
        return restore_assisted_battle_start_record(adapter, canonical)
    return restore_battle_start_record(adapter, canonical)


def load_t085_native_evaluation_plan(
    path: str | Path, *, expected_sha256: str | None = None
) -> T085NativeEvaluationPlan:
    """Load a previously written, current-schema T085 selection artifact."""
    if expected_sha256 is not None and sha256_file(path) != expected_sha256:
        raise T085NativeExecutionError("T085 selection artifact SHA-256 mismatch")
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise T085NativeExecutionError(
            "T085 selection artifact is unavailable or invalid"
        ) from exc
    if (
        not isinstance(payload, Mapping)
        or payload.get("schema_id") != T085_NATIVE_SELECTION_SCHEMA_ID
    ):
        raise T085NativeExecutionError("T085 selection artifact schema is not current")
    raw_cohorts = payload.get("cohorts")
    raw_evidence = payload.get("selection_evidence")
    if not isinstance(raw_cohorts, Mapping) or not isinstance(raw_evidence, Mapping):
        raise T085NativeExecutionError("T085 selection artifact lacks cohorts/evidence")
    cohorts = {
        str(name): tuple(T085BattleStartRecord.from_mapping(item) for item in records)
        for name, records in raw_cohorts.items()
        if isinstance(records, Sequence) and not isinstance(records, (str, bytes))
    }
    if set(cohorts) != {"A", "B", "C", "B@400"}:
        raise T085NativeExecutionError(
            "T085 selection artifact cohort matrix is incomplete"
        )
    plan = T085NativeEvaluationPlan(
        cohorts=cohorts,
        selection_evidence={
            str(k): dict(v) for k, v in raw_evidence.items() if isinstance(v, Mapping)
        },
        native_identity=dict(payload.get("native_identity", {}))
        if isinstance(payload.get("native_identity"), Mapping)
        else {},
    )
    _validate_plan(plan)
    return plan


@dataclass(frozen=True)
class _T085ScorerCallback:
    scorer: SearchGuidanceScorer
    corrected: bool
    kind: Literal["policy", "value"]
    root_context: Any | None = None

    def bind(self, root_context: Any) -> _T085ScorerCallback:
        return replace(self, root_context=root_context)

    def __call__(self, raw, native_actions):
        if self.root_context is None:
            raise T085NativeExecutionError(
                "T085 scorer callback was not bound to root context"
            )
        context = _node_context(
            raw,
            native_actions,
            ActionSpaceConfig.initial_no_potions(),
            self.root_context,
        )
        provenance = search_guidance_scorer_checkpoint_provenance(self.scorer)
        result = self.scorer.score_decision_context(context)
        validate_search_guidance_result(
            result, context=context, expected_checkpoint=provenance
        )
        if not result.inference_ok:
            raise T085NativeExecutionError(
                "T085 checkpoint scorer returned invalid inference result"
            )
        if self.kind == "policy":
            return [float(score.policy_probability) for score in result.action_scores]
        prediction = result.value_prediction
        value = (
            prediction.native_leaf_utility
            if self.corrected and prediction is not None
            else prediction.battle_survival_probability
            if prediction is not None
            else None
        )
        if value is None or not math.isfinite(float(value)):
            raise T085NativeExecutionError(
                "T085 checkpoint scorer returned no finite target value"
            )
        return float(value)


def t085_scorer_callbacks(
    scorer: SearchGuidanceScorer,
    *,
    root_context: Any,
    corrected: bool,
) -> tuple[Callable[..., object], Callable[..., object]]:
    """Adapt the existing scorer to native callbacks with target-gated semantics."""
    provenance = search_guidance_scorer_checkpoint_provenance(scorer)
    if corrected != (
        provenance.outcome_target_kind == SEARCH_V2_LEAF_NATIVE_UTILITY_TARGET_KIND
    ):
        raise T085NativeExecutionError(
            "T085 scorer target kind does not match arm semantics"
        )

    return (
        _T085ScorerCallback(scorer, corrected, "policy", root_context),
        _T085ScorerCallback(scorer, corrected, "value", root_context),
    )


def _selected_battle_index(selected: T085BattleStartRecord) -> int:
    prefix = f"{selected.source_run_identity}:"
    if not selected.battle_identity.startswith(prefix):
        raise T085NativeExecutionError(
            "T085 battle identity is not source-run qualified"
        )
    try:
        value = int(selected.battle_identity.removeprefix(prefix))
    except ValueError as exc:
        raise T085NativeExecutionError("T085 battle identity index is invalid") from exc
    if value < 0:
        raise T085NativeExecutionError("T085 battle identity index is negative")
    return value


def run_t085_native_restore_smoke(
    adapter_factory: Callable[[], object],
    canonical_path: str | Path,
    output_path: str | Path,
    *,
    limit: int = 1,
) -> dict[str, object]:
    """Execute a real canonical restore pass and retain its auditable artifact."""
    if limit < 1:
        raise T085NativeExecutionError("T085 restore smoke limit must be positive")
    canonical = resolve_t085_canonical_records(canonical_path)
    rows = []
    for record in list(canonical.values())[:limit]:
        adapter = adapter_factory()
        snapshot, method = (
            restore_assisted_battle_start_record(adapter, record)
            if record.distribution_kind == "assisted_run"
            else restore_battle_start_record(adapter, record)
        )
        rows.append(
            {
                "source_checkpoint_id": record.source_checkpoint_id,
                "source_run_id": record.source_run_id,
                "restore_method": method,
                "snapshot_fingerprint": sha256(
                    json.dumps(dict(snapshot.raw), sort_keys=True, default=str).encode()
                ).hexdigest(),
            }
        )
    payload = {
        "schema_id": "t085-native-canonical-restore-smoke-v1",
        "task_id": "T085",
        "canonical_sha256": sha256_file(Path(canonical_path)),
        "restored_records": rows,
    }
    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return payload


@dataclass(frozen=True)
class T085NativeArm:
    """An explicit, provenance-bearing Search v2 evaluation arm."""

    name: str
    checkpoint: object | None
    policy_prior_callback: Callable[..., object] | None
    leaf_value_callback: Callable[..., object] | None
    target_kind: str | None

    def __post_init__(self) -> None:
        try:
            json.dumps(self.checkpoint, sort_keys=True)
        except (TypeError, ValueError) as exc:
            raise T085NativeExecutionError(
                "T085 arm checkpoint provenance must be JSON-safe"
            ) from exc
        base_name = self.name.removesuffix("@400")
        if base_name == "baseline":
            if (
                self.checkpoint is not None
                or self.policy_prior_callback is not None
                or self.leaf_value_callback is not None
            ):
                raise T085NativeExecutionError(
                    "T085 baseline must be native v2 with both callbacks None"
                )
        elif base_name.startswith("corrected_"):
            if (
                self.checkpoint is None
                or self.leaf_value_callback is None
                or self.target_kind != "search_v2_leaf_continuation_native_utility_v1"
            ):
                raise T085NativeExecutionError(
                    "T085 corrected arm lacks explicit checkpoint/utility callback provenance"
                )
        elif base_name.startswith("old_"):
            if (
                self.checkpoint is None
                or self.leaf_value_callback is None
                or self.target_kind != "terminal_battle_survival_probability"
            ):
                raise T085NativeExecutionError(
                    "T085 old arm lacks explicit checkpoint/survival callback provenance"
                )
        elif base_name.startswith("prior_only_"):
            if (
                self.checkpoint is None
                or self.policy_prior_callback is None
                or self.leaf_value_callback is not None
            ):
                raise T085NativeExecutionError(
                    "T085 prior-only arm lacks explicit prior provenance"
                )
        elif base_name.startswith("prior_corrected_"):
            if (
                self.checkpoint is None
                or self.policy_prior_callback is None
                or self.leaf_value_callback is None
                or self.target_kind != "search_v2_leaf_continuation_native_utility_v1"
            ):
                raise T085NativeExecutionError(
                    "T085 prior-corrected arm lacks explicit provenance"
                )
        else:
            raise T085NativeExecutionError(f"unknown T085 arm {self.name!r}")

    @property
    def provenance(self) -> dict[str, object]:
        return {
            "task_id": "T085",
            "arm": self.name,
            "native_search_api": T085_NATIVE_V2_API,
            "policy_prior_callback": self.policy_prior_callback is not None,
            "leaf_value_callback": self.leaf_value_callback is not None,
            "checkpoint_provenance": self.checkpoint,
            "target_kind": self.target_kind,
        }


def build_t085_native_arms(
    *,
    old_checkpoint_64001: object,
    corrected_checkpoint_85001: object,
    old_checkpoint_64002: object,
    corrected_checkpoint_85002: object,
    old_value_callback_64001: Callable[..., object],
    corrected_value_callback_85001: Callable[..., object],
    old_value_callback_64002: Callable[..., object],
    corrected_value_callback_85002: Callable[..., object],
    prior_callback_64001: Callable[..., object],
    prior_callback_64002: Callable[..., object],
) -> dict[str, T085NativeArm]:
    """Construct the frozen primary arms; baseline is always native v2 unguided."""
    arms = {
        "baseline": T085NativeArm("baseline", None, None, None, None),
        "old_value_64001": T085NativeArm(
            "old_value_64001",
            old_checkpoint_64001,
            None,
            old_value_callback_64001,
            "terminal_battle_survival_probability",
        ),
        "corrected_value_85001": T085NativeArm(
            "corrected_value_85001",
            corrected_checkpoint_85001,
            None,
            corrected_value_callback_85001,
            "search_v2_leaf_continuation_native_utility_v1",
        ),
        "old_value_64002": T085NativeArm(
            "old_value_64002",
            old_checkpoint_64002,
            None,
            old_value_callback_64002,
            "terminal_battle_survival_probability",
        ),
        "corrected_value_85002": T085NativeArm(
            "corrected_value_85002",
            corrected_checkpoint_85002,
            None,
            corrected_value_callback_85002,
            "search_v2_leaf_continuation_native_utility_v1",
        ),
    }
    arms.update(
        {
            "baseline@400": replace(arms["baseline"], name="baseline@400"),
            "corrected_value_85001@400": replace(
                arms["corrected_value_85001"], name="corrected_value_85001@400"
            ),
            "corrected_value_85002@400": replace(
                arms["corrected_value_85002"], name="corrected_value_85002@400"
            ),
            "prior_only_64001": T085NativeArm(
                "prior_only_64001",
                old_checkpoint_64001,
                prior_callback_64001,
                None,
                None,
            ),
            "prior_corrected_85001": T085NativeArm(
                "prior_corrected_85001",
                corrected_checkpoint_85001,
                prior_callback_64001,
                corrected_value_callback_85001,
                "search_v2_leaf_continuation_native_utility_v1",
            ),
            "prior_only_64002": T085NativeArm(
                "prior_only_64002",
                old_checkpoint_64002,
                prior_callback_64002,
                None,
                None,
            ),
            "prior_corrected_85002": T085NativeArm(
                "prior_corrected_85002",
                corrected_checkpoint_85002,
                prior_callback_64002,
                corrected_value_callback_85002,
                "search_v2_leaf_continuation_native_utility_v1",
            ),
        }
    )
    return arms


def _accepted_t064_parent_sha(repair_seed: int) -> str:
    key = f"t064_parent_{repair_seed}"
    reference = T085_INPUT_ARTIFACT_IDENTITIES.get(key)
    if not isinstance(reference, Mapping) or not isinstance(
        reference.get("sha256"), str
    ):
        raise T085NativeExecutionError(
            f"T085 accepted T064 parent identity is missing for {repair_seed}"
        )
    return str(reference["sha256"])


def _load_t085_training_manifest(
    path: str | Path,
    *,
    expected_sha256: str,
) -> dict[int, dict[str, object]]:
    """Load the repository-owned training manifest and its accepted checkpoints."""

    resolved = Path(path).resolve(strict=True)
    expected_path = (
        T085_ARTIFACT_ROOT.resolve() / "training" / "t085-training-manifest.json"
    )
    if resolved != expected_path:
        raise T085NativeExecutionError(
            "T085 training manifest must be the stable repository-owned manifest"
        )
    if sha256_file(resolved) != expected_sha256:
        raise T085NativeExecutionError("T085 training manifest SHA-256 mismatch")
    try:
        payload = json.loads(resolved.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise T085NativeExecutionError(
            "T085 training manifest is unavailable or invalid"
        ) from exc
    if not isinstance(payload, Mapping):
        raise T085NativeExecutionError("T085 training manifest is not an object")
    if (
        payload.get("schema_id") != "t085-corrected-value-training-manifest-v1"
        or payload.get("task_id") != "T085"
        or payload.get("training_completed") is not True
    ):
        raise T085NativeExecutionError(
            "T085 training manifest schema/completion identity is invalid"
        )
    if dict(payload.get("native_identity", {})) != T085_NATIVE_IDENTITY:
        raise T085NativeExecutionError(
            "T085 training manifest has the wrong native identity"
        )
    repairs = payload.get("repairs")
    if not isinstance(repairs, Sequence) or isinstance(repairs, (str, bytes)):
        raise T085NativeExecutionError("T085 training manifest repairs are missing")
    by_seed: dict[int, dict[str, object]] = {}
    for raw_repair in repairs:
        if not isinstance(raw_repair, Mapping):
            raise T085NativeExecutionError("T085 training manifest repair is malformed")
        seed = raw_repair.get("repair_seed")
        if seed not in (85001, 85002) or seed in by_seed:
            raise T085NativeExecutionError(
                "T085 training manifest must contain one repair for each accepted seed"
            )
        checkpoint = raw_repair.get("checkpoint")
        parent = raw_repair.get("parent_checkpoint")
        if not isinstance(checkpoint, Mapping) or not isinstance(parent, Mapping):
            raise T085NativeExecutionError(
                "T085 training manifest repair lacks checkpoint/parent references"
            )
        if checkpoint.get("schema_id") != "torch-policy-value-checkpoint-v1":
            raise T085NativeExecutionError(
                "T085 corrected checkpoint reference has the wrong schema"
            )
        if parent.get("sha256") != _accepted_t064_parent_sha(int(seed)):
            raise T085NativeExecutionError(
                "T085 corrected checkpoint parent is not the accepted T064 identity"
            )
        expected_parent = T085_INPUT_ARTIFACT_IDENTITIES[f"t064_parent_{seed}"]
        if parent.get("path") != expected_parent.get("path"):
            raise T085NativeExecutionError(
                "T085 corrected checkpoint parent path is not the accepted T064 path"
            )
        checkpoint_path = checkpoint.get("path")
        checkpoint_sha = checkpoint.get("sha256")
        if (
            not isinstance(checkpoint_path, str)
            or not isinstance(checkpoint_sha, str)
            or len(checkpoint_sha) != 64
        ):
            raise T085NativeExecutionError(
                "T085 corrected checkpoint reference lacks exact path/SHA"
            )
        try:
            Path(checkpoint_path).resolve().relative_to(T085_ARTIFACT_ROOT.resolve())
        except ValueError as exc:
            raise T085NativeExecutionError(
                "T085 corrected checkpoint reference is outside the stable T085 root"
            ) from exc
        by_seed[int(seed)] = dict(checkpoint)
    if set(by_seed) != {85001, 85002}:
        raise T085NativeExecutionError(
            "T085 training manifest does not cover both corrected checkpoints"
        )
    return by_seed


def _source_map_expectations(
    plan: T085NativeEvaluationPlan,
    cohort: Literal["B", "C"],
) -> dict[str, object]:
    evidence = plan.selection_evidence.get(cohort)
    if not isinstance(evidence, Mapping):
        raise T085NativeExecutionError(
            f"T085 selection evidence {cohort} is missing source inventory"
        )
    source_count = evidence.get("source_run_count")
    source_ids = evidence.get("source_run_identity_inventory")
    source_seeds = evidence.get("source_run_seed_inventory")
    if (
        not isinstance(source_count, int)
        or not isinstance(source_ids, Sequence)
        or isinstance(source_ids, (str, bytes))
        or not isinstance(source_seeds, Sequence)
        or isinstance(source_seeds, (str, bytes))
    ):
        raise T085NativeExecutionError(
            f"T085 selection evidence {cohort} lacks complete source inventory"
        )
    source_manifest = evidence.get("source_manifest")
    if not isinstance(source_manifest, Mapping):
        raise T085NativeExecutionError(
            f"T085 selection evidence {cohort} lacks source manifest binding"
        )
    source_manifest_path = source_manifest.get("path")
    source_manifest_sha256 = source_manifest.get("sha256")
    if (
        not isinstance(source_manifest_path, str)
        or not source_manifest_path
        or not isinstance(source_manifest_sha256, str)
        or len(source_manifest_sha256) != 64
    ):
        raise T085NativeExecutionError(
            f"T085 selection evidence {cohort} has an invalid source manifest binding"
        )
    return {
        "expected_source_run_count": source_count,
        "expected_source_run_identity_inventory": tuple(source_ids),
        "expected_source_run_seed_inventory": tuple(source_seeds),
        "expected_assistance_level": ("assist_hp75_potion" if cohort == "B" else None),
        "expected_source_manifest_path": source_manifest_path,
        "expected_source_manifest_sha256": source_manifest_sha256,
    }


def _validate_t085_a_map_binding(
    path: str | Path,
    digest: str,
    plan: T085NativeEvaluationPlan,
) -> None:
    if digest != T085_T052_COHORT_SHA256:
        raise T085NativeExecutionError(
            "T085 A map must use the accepted T052 fixed-cohort SHA-256"
        )
    evidence = plan.selection_evidence["A"]
    artifact = evidence.get("artifact") if isinstance(evidence, Mapping) else None
    if not isinstance(artifact, Mapping):
        raise T085NativeExecutionError(
            "T085 A selection evidence lacks artifact binding"
        )
    if (
        artifact.get("sha256") != digest
        or Path(str(artifact.get("path"))).resolve() != Path(path).resolve()
        or artifact.get("schema_id") != "fixed-cohort-v3-jsonl"
    ):
        raise T085NativeExecutionError(
            "T085 A map is not the exact fixed-cohort artifact in selection evidence"
        )


def run_t085_native_paired_evaluation_from_paths(
    *,
    adapter_factory: Callable[[], object],
    selection_path: str | Path,
    selection_sha256: str,
    a_full_map_path: str | Path,
    b_full_map_path: str | Path,
    c_full_map_path: str | Path,
    a_sha256: str,
    b_sha256: str,
    c_sha256: str,
    old_checkpoint_64001: str | Path,
    corrected_checkpoint_85001: str | Path,
    old_checkpoint_64002: str | Path,
    corrected_checkpoint_85002: str | Path,
    old_checkpoint_64001_sha256: str,
    corrected_checkpoint_85001_sha256: str,
    old_checkpoint_64002_sha256: str,
    corrected_checkpoint_85002_sha256: str,
    training_manifest_path: str | Path,
    training_manifest_sha256: str,
    shard_index: int,
    shard_count: int,
    worker_count: int,
    b_artifact_kind: Literal["assisted_pool", "fixed_cohort"] = "assisted_pool",
    c_artifact_kind: Literal["natural_pool", "fixed_cohort"] = "natural_pool",
    selection_output_path: str | Path,
    report_output_path: str | Path,
    outcomes_output_path: str | Path,
) -> dict[str, object]:
    """Complete path-bound T085 workflow; no caller result callback exists."""
    if b_artifact_kind != "assisted_pool" or c_artifact_kind != "natural_pool":
        raise T085NativeExecutionError(
            "T085 paired evaluation requires the assisted B pool and natural C pool"
        )
    plan = load_t085_native_evaluation_plan(
        selection_path, expected_sha256=selection_sha256
    )
    maps = {
        "A": resolve_t085_canonical_records(
            a_full_map_path,
            expected_sha256=a_sha256,
            artifact_kind="fixed_cohort",
        ),
        "B": resolve_t085_canonical_records(
            b_full_map_path,
            expected_sha256=b_sha256,
            artifact_kind=b_artifact_kind,
            **_source_map_expectations(plan, "B"),
        ),
        "C": resolve_t085_canonical_records(
            c_full_map_path,
            expected_sha256=c_sha256,
            artifact_kind=c_artifact_kind,
            **_source_map_expectations(plan, "C"),
        ),
    }
    maps["B@400"] = maps["B"]
    _validate_t085_a_map_binding(a_full_map_path, a_sha256, plan)
    shard = T085NativeShardPlan(shard_index, shard_count, worker_count)
    training_references = _load_t085_training_manifest(
        training_manifest_path,
        expected_sha256=training_manifest_sha256,
    )
    from sts_combat_rl.commands.model_guided_oracle_search import (
        build_torch_guidance_scorer_from_checkpoint,
    )

    old1 = build_torch_guidance_scorer_from_checkpoint(Path(old_checkpoint_64001))
    new1 = build_torch_guidance_scorer_from_checkpoint(Path(corrected_checkpoint_85001))
    old2 = build_torch_guidance_scorer_from_checkpoint(Path(old_checkpoint_64002))
    new2 = build_torch_guidance_scorer_from_checkpoint(Path(corrected_checkpoint_85002))

    # Validate each loaded scorer independently after loading.  The explicit
    # SHA arguments bind the path bytes; scorer provenance binds schema and
    # target semantics, so an arbitrary checkpoint cannot masquerade as an arm.
    for path, expected_sha256, scorer, corrected, label, seed in (
        (
            old_checkpoint_64001,
            old_checkpoint_64001_sha256,
            old1,
            False,
            "old 64001",
            85001,
        ),
        (
            corrected_checkpoint_85001,
            corrected_checkpoint_85001_sha256,
            new1,
            True,
            "corrected 85001",
            85001,
        ),
        (
            old_checkpoint_64002,
            old_checkpoint_64002_sha256,
            old2,
            False,
            "old 64002",
            85002,
        ),
        (
            corrected_checkpoint_85002,
            corrected_checkpoint_85002_sha256,
            new2,
            True,
            "corrected 85002",
            85002,
        ),
    ):
        if not corrected:
            accepted = _accepted_t064_parent_sha(seed)
            if expected_sha256 != accepted:
                raise T085NativeExecutionError(
                    f"T085 {label} SHA-256 is not the accepted T064 parent identity"
                )
        else:
            manifest_reference = training_references[seed]
            if manifest_reference["sha256"] != expected_sha256:
                raise T085NativeExecutionError(
                    f"T085 {label} SHA-256 is not the identity in the validated training manifest"
                )
            if Path(manifest_reference["path"]).resolve() != Path(path).resolve():
                raise T085NativeExecutionError(
                    f"T085 {label} path is not the identity in the validated training manifest"
                )
        if sha256_file(path) != expected_sha256:
            raise T085NativeExecutionError(f"T085 {label} checkpoint SHA-256 mismatch")
        provenance = search_guidance_scorer_checkpoint_provenance(scorer, label=label)
        if provenance.checkpoint_schema_id != "torch-policy-value-checkpoint-v1":
            raise T085NativeExecutionError(
                f"T085 {label} checkpoint schema is unsupported"
            )
        expected_artifact_id = (
            f"torch-policy-value-checkpoint-v1-sha256:{expected_sha256}"
        )
        if provenance.checkpoint_artifact_id != expected_artifact_id:
            raise T085NativeExecutionError(
                f"T085 {label} scorer provenance is not bound to the checked bytes"
            )
        expected_target = (
            SEARCH_V2_LEAF_NATIVE_UTILITY_TARGET_KIND
            if corrected
            else T085_HISTORICAL_OUTCOME_TARGET_KIND
        )
        if provenance.outcome_target_kind != expected_target:
            raise T085NativeExecutionError(
                f"T085 {label} checkpoint target kind is not {expected_target!r}"
            )

    # Root context is supplied at callback invocation by native Search v2; the
    # concrete controller path validates it before constructing callbacks.
    def callback_pair(scorer, corrected):
        return t085_scorer_callbacks(scorer, root_context=None, corrected=corrected)

    # Native callback construction is deferred to the controller boundary;
    # this workflow still binds every checkpoint identity before execution.
    p1, v1 = callback_pair(old1, False)
    _p2, v2 = callback_pair(new1, True)
    p3, v3 = callback_pair(old2, False)
    _p4, v4 = callback_pair(new2, True)
    arms = build_t085_native_arms(
        old_checkpoint_64001=search_guidance_scorer_checkpoint_provenance(
            old1
        ).to_dict(),
        corrected_checkpoint_85001=search_guidance_scorer_checkpoint_provenance(
            new1
        ).to_dict(),
        old_checkpoint_64002=search_guidance_scorer_checkpoint_provenance(
            old2
        ).to_dict(),
        corrected_checkpoint_85002=search_guidance_scorer_checkpoint_provenance(
            new2
        ).to_dict(),
        old_value_callback_64001=v1,
        corrected_value_callback_85001=v2,
        old_value_callback_64002=v3,
        corrected_value_callback_85002=v4,
        prior_callback_64001=p1,
        prior_callback_64002=p3,
    )
    return run_t085_native_paired_evaluation(
        plan,
        adapter_factory=adapter_factory,
        canonical_records_by_cohort=maps,
        arms=arms,
        selection_output_path=selection_output_path,
        report_output_path=report_output_path,
        outcomes_output_path=outcomes_output_path,
        search_backend="battle_search_v2",
        shard_index=shard.shard_index,
        shard_count=shard.shard_count,
        worker_count=shard.worker_count,
    )


class T085NativeExecutionError(T085EvaluationIntegrityError):
    """Raised when native terminal utility cannot be proven for a row."""


def _positive_int(value: object, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise T085NativeExecutionError(f"{label} must be a positive integer")
    return value


def _validate_t085_native_source_manifest(
    backend: T085NativeSearchBackend | None = None,
) -> dict[str, object]:
    """Require the repository-owned manifest to name T085's pinned native API."""

    try:
        manifest = load_lightspeed_source_manifest()
    except (OSError, ValueError) as exc:
        raise T085NativeExecutionError(
            "T085 native execution is INCOMPLETE: the pinned sts_lightspeed "
            "source manifest cannot be loaded"
        ) from exc

    expected_repository = f"https://github.com/{T085_NATIVE_IDENTITY['repository']}"
    actual_repository = manifest.integration.repository_url.rstrip("/")
    actual_repository = actual_repository.removesuffix(".git")
    if (
        actual_repository != expected_repository
        or manifest.integration.ref != T085_NATIVE_IDENTITY["ref"]
        or manifest.integration.commit != T085_NATIVE_IDENTITY["commit"]
    ):
        raise T085NativeExecutionError(
            "T085 native execution is INCOMPLETE: source manifest is not bound "
            "to the accepted sts_lightspeed identity"
        )
    if backend is not None:
        capability = (
            "native_battle_search_v2_tree_internal"
            if backend == "battle_search_v2"
            else "native_battle_search_root"
        )
        if capability not in manifest.capability_ids:
            raise T085NativeExecutionError(
                f"T085 native execution is INCOMPLETE: source manifest lacks "
                f"{capability}"
            )
    return dict(T085_NATIVE_IDENTITY)


def _is_battle_snapshot(snapshot: SimulatorSnapshot) -> bool:
    raw = snapshot.raw
    return (
        bool(raw.get("battle_active")) or str(raw.get("screen_state", "")) == "BATTLE"
    )


def _native_search_report(
    adapter: object,
    snapshot: SimulatorSnapshot,
    actions: Sequence[SimulatorAction],
    context: Any,
    *,
    simulations: int,
    backend: T085NativeSearchBackend,
    policy_prior_callback: Callable[..., object] | None = None,
    leaf_value_callback: Callable[..., object] | None = None,
) -> OracleSearchReport:
    """Run and validate one native search on the supplied current snapshot."""

    _positive_int(simulations, "native search simulations")
    _validate_t085_native_source_manifest(backend)
    if backend == "battle_search":
        method_name = "battle_search"
        expected_api = ORACLE_SEARCH_NATIVE_API
        expected_patch = ORACLE_SEARCH_PATCH_IDENTITY
    elif backend == "battle_search_v2":
        method_name = "battle_search_v2"
        expected_api = T085_NATIVE_V2_API
        expected_patch = T085_NATIVE_V2_PATCH
    else:
        raise T085NativeExecutionError(
            f"unknown T085 native search backend {backend!r}"
        )

    search = getattr(adapter, method_name, None)
    if not callable(search):
        raise T085NativeExecutionError(
            f"T085 native execution is INCOMPLETE: adapter lacks {method_name}"
        )
    try:
        if backend == "battle_search":
            raw_search = search(
                snapshot,
                simulations=simulations,
                include_potions=False,
            )
        else:
            # Explicitly pass both callbacks as None.  This is the accepted
            # native evaluateEndState path, not a Python value callback.
            raw_search = search(
                snapshot,
                simulations=simulations,
                include_potions=False,
                policy_prior_callback=policy_prior_callback,
                leaf_value_callback=leaf_value_callback,
            )
    except (AttributeError, RuntimeError, TypeError, ValueError) as exc:
        raise T085NativeExecutionError(
            f"T085 native {method_name} failed on the current pre-action snapshot"
        ) from exc
    if not isinstance(raw_search, Mapping):
        raise T085NativeExecutionError(
            f"T085 native {method_name} did not return a mapping"
        )
    if (
        backend == "battle_search_v2"
        and policy_prior_callback is None
        and leaf_value_callback is None
    ):
        _validate_unguided_v2_telemetry(raw_search)
    try:
        report = build_oracle_search_report(
            raw_search,
            actions,
            context,
            expected_native_api=expected_api,
            expected_patch_identity=expected_patch,
        )
    except (TypeError, ValueError) as exc:
        raise T085NativeExecutionError(
            f"T085 native {method_name} root report is malformed"
        ) from exc
    if not report.search_ok:
        raise T085NativeExecutionError(
            f"T085 native {method_name} root mapping failed: "
            + "; ".join(report.problems)
        )
    if report.schema_id != ORACLE_SEARCH_SCHEMA_ID:
        raise T085NativeExecutionError("T085 native root report schema is not current")
    if report.simulations_requested != simulations:
        raise T085NativeExecutionError(
            "T085 native root report budget does not match the requested budget"
        )
    return report


def _validate_unguided_v2_telemetry(raw_search: Mapping[str, object]) -> None:
    telemetry = raw_search.get("tree_internal_telemetry")
    if not isinstance(telemetry, Mapping):
        raise T085NativeExecutionError(
            "T085 battle_search_v2 omitted tree-internal telemetry"
        )
    if telemetry.get("policy_prior_scope") != "disabled":
        raise T085NativeExecutionError(
            "T085 unguided battle_search_v2 unexpectedly enabled policy priors"
        )
    if telemetry.get("leaf_value_boundary") != "disabled":
        raise T085NativeExecutionError(
            "T085 unguided battle_search_v2 unexpectedly enabled a value callback"
        )
    for field_name in ("policy_prior_calls", "leaf_value_calls"):
        value = telemetry.get(field_name)
        if isinstance(value, bool) or not isinstance(value, int) or value != 0:
            raise T085NativeExecutionError(
                f"T085 unguided battle_search_v2 {field_name} is not zero"
            )


@dataclass(frozen=True)
class T085NativeRootEdgeLabel:
    """Pre-action native root-edge statistics, finalized only after terminal proof."""

    backend: T085NativeSearchBackend
    native_identity: Mapping[str, object]
    simulations: int
    selected_legal_action_index: int
    selected_action_identity: Mapping[str, object]
    search_edge_index: int
    visits: int
    evaluation_sum: float | None
    mean_value: float | None
    search_tree_present: bool
    terminal_outcome: str | None = None
    _pre_action_snapshot_token: int = field(repr=False, compare=False, default=0)

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_id": T085_NATIVE_TERMINAL_LABEL_SCHEMA_ID,
            "backend": self.backend,
            "native_api": (
                ORACLE_SEARCH_NATIVE_API
                if self.backend == "battle_search"
                else T085_NATIVE_V2_API
            ),
            "native_patch_identity": (
                ORACLE_SEARCH_PATCH_IDENTITY
                if self.backend == "battle_search"
                else T085_NATIVE_V2_PATCH
            ),
            "native_identity": dict(self.native_identity),
            "search_simulations": self.simulations,
            "selected_legal_action_index": self.selected_legal_action_index,
            "selected_action_identity": dict(self.selected_action_identity),
            "search_edge_index": self.search_edge_index,
            "visits": self.visits,
            "evaluation_sum": self.evaluation_sum,
            "mean_value": self.mean_value,
            "search_tree_present": self.search_tree_present,
            "terminal_outcome": self.terminal_outcome,
            "label_role": "auxiliary_terminal_utility_label_only",
            "does_not_replace_controller_search": True,
            "utility_source": "pre_action_selected_root_edge_mean",
            "terminal_proof": "same_action_native_transition_outcome",
        }


def prepare_t085_native_root_edge_label(
    adapter: object,
    snapshot: SimulatorSnapshot,
    actions: Sequence[SimulatorAction],
    chosen_action_index: int,
    *,
    simulations: int,
    backend: T085NativeSearchBackend = "battle_search",
    policy_prior_callback: Callable[..., object] | None = None,
    leaf_value_callback: Callable[..., object] | None = None,
) -> T085NativeRootEdgeLabel:
    """Search the current state before stepping and select the chosen root edge."""

    if not _is_battle_snapshot(snapshot):
        raise T085NativeExecutionError(
            "T085 native terminal labeling requires a pre-action battle snapshot"
        )
    action_list = list(actions)
    if not action_list:
        raise T085NativeExecutionError("T085 native terminal labeling has no actions")
    if (
        isinstance(chosen_action_index, bool)
        or not isinstance(chosen_action_index, int)
        or chosen_action_index < 0
        or chosen_action_index >= len(action_list)
    ):
        raise T085NativeExecutionError("chosen action index is outside current actions")
    context = build_decision_context(
        snapshot.raw,
        action_list,
        ActionSpaceConfig.initial_no_potions(),
    )
    report = _native_search_report(
        adapter,
        snapshot,
        action_list,
        context,
        simulations=simulations,
        backend=backend,
        policy_prior_callback=policy_prior_callback,
        leaf_value_callback=leaf_value_callback,
    )
    identities = action_identity_dicts_for_actions(action_list)
    expected_identity = identities[chosen_action_index]
    matches = [
        stat
        for stat in report.root_actions
        if stat.legal_action_index == chosen_action_index
    ]
    if len(matches) != 1:
        raise T085NativeExecutionError(
            "native root report does not contain exactly one selected legal action"
        )
    selected = matches[0]
    if selected.action_identity != expected_identity:
        raise T085NativeExecutionError(
            "native root edge identity does not match the selected action occurrence"
        )
    if selected.eligible is not True:
        raise T085NativeExecutionError(
            "selected native root edge is outside T085's no-potion action space"
        )
    search_edge_index = selected.native_action.get("search_edge_index")
    if (
        isinstance(search_edge_index, bool)
        or not isinstance(search_edge_index, int)
        or search_edge_index < 0
    ):
        raise T085NativeExecutionError(
            "selected native root edge has no valid search_edge_index"
        )
    if selected.evaluation_sum is not None and not math.isfinite(
        float(selected.evaluation_sum)
    ):
        raise T085NativeExecutionError("selected native evaluation_sum is not finite")
    if selected.mean_value is not None and not math.isfinite(
        float(selected.mean_value)
    ):
        raise T085NativeExecutionError("selected native mean_value is not finite")
    return T085NativeRootEdgeLabel(
        backend=backend,
        native_identity=_validate_t085_native_source_manifest(backend),
        simulations=simulations,
        selected_legal_action_index=chosen_action_index,
        selected_action_identity=dict(selected.action_identity),
        search_edge_index=search_edge_index,
        visits=selected.visits,
        evaluation_sum=selected.evaluation_sum,
        mean_value=selected.mean_value,
        search_tree_present=selected.search_tree_present,
        _pre_action_snapshot_token=id(snapshot),
    )


def _authoritative_terminal_outcome(transition: SimulatorTransition) -> str | None:
    """Read a terminal win/loss label emitted by the simulator transition."""

    candidates: list[object] = []
    if isinstance(transition.info, Mapping):
        candidates.extend(
            transition.info.get(name)
            for name in ("completed_battle_outcome", "battle_outcome", "outcome")
            if name in transition.info
        )
    if isinstance(transition.snapshot.raw, Mapping):
        candidates.extend(
            transition.snapshot.raw.get(name)
            for name in ("completed_battle_outcome", "battle_outcome", "outcome")
            if name in transition.snapshot.raw
        )
    recognized = {
        value
        for value in candidates
        if isinstance(value, str) and value in _TERMINAL_OUTCOMES
    }
    if len(recognized) > 1:
        raise T085NativeExecutionError(
            "native transition exposes conflicting terminal outcomes"
        )
    return next(iter(recognized), None)


def finalize_t085_native_root_edge_label(
    label: T085NativeRootEdgeLabel,
    transition: SimulatorTransition,
    *,
    pre_action_snapshot: SimulatorSnapshot,
    pre_action_actions: Sequence[SimulatorAction],
    selected_action: SimulatorAction,
) -> T085NativeRootEdgeLabel:
    """Finalize a label after proving snapshot, action, and terminal pairing."""

    if id(pre_action_snapshot) != label._pre_action_snapshot_token:
        raise T085NativeExecutionError(
            "native terminal label was not paired with its pre-action snapshot"
        )
    if not _is_battle_snapshot(pre_action_snapshot):
        raise T085NativeExecutionError(
            "native terminal label pre-action snapshot is not a battle state"
        )
    action_list = list(pre_action_actions)
    identity_matches = [
        index for index, action in enumerate(action_list) if action is selected_action
    ]
    if len(identity_matches) != 1:
        raise T085NativeExecutionError(
            "native terminal label selected action is not unique in its pre-action list"
        )
    selected_index = identity_matches[0]
    if selected_index != label.selected_legal_action_index:
        raise T085NativeExecutionError(
            "native terminal label selected action index changed"
        )
    if action_identity_dicts_for_actions(action_list)[selected_index] != dict(
        label.selected_action_identity
    ):
        raise T085NativeExecutionError(
            "native terminal label selected action identity changed"
        )
    if transition.snapshot is pre_action_snapshot:
        raise T085NativeExecutionError(
            "native terminal transition reused the pre-action snapshot"
        )
    if isinstance(transition.info, Mapping):
        if (
            "action_id" in transition.info
            and transition.info["action_id"] != selected_action.action_id
        ):
            raise T085NativeExecutionError(
                "native terminal transition action id does not match selected action"
            )
        if (
            "action_kind" in transition.info
            and transition.info["action_kind"] != selected_action.kind
        ):
            raise T085NativeExecutionError(
                "native terminal transition action kind does not match selected action"
            )

    outcome = _authoritative_terminal_outcome(transition)
    if outcome is None:
        raise T085NativeExecutionError(
            "T085 native root-edge mean is not proven terminal by the simulator"
        )
    if label.terminal_outcome is not None and label.terminal_outcome != outcome:
        raise T085NativeExecutionError("native terminal label outcome changed")
    if label.search_tree_present is not True:
        raise T085NativeExecutionError(
            "selected native root edge is not marked as present/visited"
        )
    if label.visits <= 0:
        raise T085NativeExecutionError(
            "selected native root edge has no visited simulations"
        )
    if label.evaluation_sum is None or label.mean_value is None:
        raise T085NativeExecutionError(
            "selected native root edge has no finite native utility mean"
        )
    evaluation_sum = float(label.evaluation_sum)
    mean_value = float(label.mean_value)
    if not math.isfinite(evaluation_sum) or not math.isfinite(mean_value):
        raise T085NativeExecutionError(
            "selected native root edge utility is not finite"
        )
    if not math.isclose(
        evaluation_sum / label.visits,
        mean_value,
        rel_tol=1e-12,
        abs_tol=1e-12,
    ):
        raise T085NativeExecutionError(
            "selected native root edge evaluation_sum/visits disagrees with mean"
        )
    return replace(label, terminal_outcome=outcome)


class T085NativeTerminalSearchAdapter:
    """Adapter proxy that enforces pre-step native terminal labeling."""

    def __init__(
        self,
        base_adapter: object,
        *,
        search_simulations: int,
        search_backend: T085NativeSearchBackend = "battle_search",
        policy_prior_callback: Callable[..., object] | None = None,
        leaf_value_callback: Callable[..., object] | None = None,
    ) -> None:
        _positive_int(search_simulations, "T085 native search simulations")
        if search_backend not in T085_NATIVE_SEARCH_BACKENDS:
            raise T085NativeExecutionError(
                f"unknown T085 native search backend {search_backend!r}"
            )
        if isinstance(base_adapter, T085NativeTerminalSearchAdapter):
            raise T085NativeExecutionError("native adapter proxy cannot be nested")
        self._base_adapter = base_adapter
        self._search_simulations = search_simulations
        self._search_backend = search_backend
        self._policy_prior_callback = policy_prior_callback
        self._leaf_value_callback = leaf_value_callback
        self._current_snapshot: SimulatorSnapshot | None = None
        self._current_actions: list[SimulatorAction] = []
        self._terminal_labels: list[T085NativeRootEdgeLabel] = []
        self._step_count = 0
        self._search_call_count = 0
        self._restored_snapshot: SimulatorSnapshot | None = None
        _validate_t085_native_source_manifest(search_backend)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._base_adapter, name)

    @property
    def native_terminal_labels(self) -> tuple[T085NativeRootEdgeLabel, ...]:
        return tuple(self._terminal_labels)

    @property
    def simulator_step_count(self) -> int:
        return self._step_count

    @property
    def native_search_call_count(self) -> int:
        return self._search_call_count

    def reset(self, seed: int | None = None) -> SimulatorSnapshot:
        if self._restored_snapshot is not None:
            snapshot = self._restored_snapshot
            self._restored_snapshot = None
            self._current_snapshot = snapshot
            self._current_actions = []
            self._terminal_labels.clear()
            self._step_count = 0
            self._search_call_count = 0
            return snapshot
        reset = getattr(self._base_adapter, "reset", None)
        if not callable(reset):
            raise T085NativeExecutionError("wrapped adapter lacks reset")
        snapshot = reset(seed)
        if not isinstance(snapshot, SimulatorSnapshot):
            raise T085NativeExecutionError("adapter reset did not return a snapshot")
        self._current_snapshot = snapshot
        self._current_actions = []
        self._terminal_labels.clear()
        self._step_count = 0
        self._search_call_count = 0
        return snapshot

    def restore_checkpoint(self, checkpoint: object) -> SimulatorSnapshot:
        restore = getattr(self._base_adapter, "restore_checkpoint", None)
        if not callable(restore):
            raise T085NativeExecutionError("wrapped adapter lacks restore_checkpoint")
        snapshot = restore(checkpoint)
        if not isinstance(snapshot, SimulatorSnapshot):
            raise T085NativeExecutionError(
                "adapter restore_checkpoint did not return a snapshot"
            )
        self._current_snapshot = snapshot
        self._current_actions = []
        self._restored_snapshot = snapshot
        return snapshot

    def prime_restored_snapshot(self, snapshot: SimulatorSnapshot) -> None:
        """Prime ``execute_controlled_run`` to preserve an already-restored start.

        Canonical replay helpers deliberately receive the base simulator
        adapter.  This seam transfers only their verified snapshot into the
        native-label proxy; it does not expose a caller-controlled outcome or
        bypass the proxy's reset contract.
        """
        if not isinstance(snapshot, SimulatorSnapshot):
            raise T085NativeExecutionError("cannot prime a non-snapshot restore")
        self._current_snapshot = snapshot
        self._restored_snapshot = snapshot

    def legal_actions(self, snapshot: SimulatorSnapshot) -> list[SimulatorAction]:
        legal_actions = getattr(self._base_adapter, "legal_actions", None)
        if not callable(legal_actions):
            raise T085NativeExecutionError("wrapped adapter lacks legal_actions")
        actions = list(legal_actions(snapshot))
        self._current_snapshot = snapshot
        self._current_actions = actions
        return actions

    def _chosen_action_index(self, action: SimulatorAction) -> int:
        identity_matches = [
            index
            for index, candidate in enumerate(self._current_actions)
            if candidate is action
        ]
        if len(identity_matches) == 1:
            return identity_matches[0]
        equality_matches = [
            index
            for index, candidate in enumerate(self._current_actions)
            if candidate == action
        ]
        if len(equality_matches) != 1:
            raise T085NativeExecutionError(
                "step action is not uniquely bound to the current legal action list"
            )
        return equality_matches[0]

    def step(self, action: SimulatorAction) -> SimulatorTransition:
        if self._current_snapshot is None:
            raise T085NativeExecutionError(
                "native execution step has no current snapshot; restore/reset first"
            )
        pending: T085NativeRootEdgeLabel | None = None
        if _is_battle_snapshot(self._current_snapshot):
            if not self._current_actions:
                raise T085NativeExecutionError(
                    "native execution step has no current legal actions"
                )
            index = self._chosen_action_index(action)
            # This call is intentionally before base_adapter.step.  The
            # adapter's current native snapshot is therefore the root state.
            pending = prepare_t085_native_root_edge_label(
                self._base_adapter,
                self._current_snapshot,
                self._current_actions,
                index,
                simulations=self._search_simulations,
                backend=self._search_backend,
                # Terminal utility labels are always the native no-callback
                # evaluateEndState path, independent of controller guidance.
                policy_prior_callback=None,
                leaf_value_callback=None,
            )
            self._search_call_count += 1
        step = getattr(self._base_adapter, "step", None)
        if not callable(step):
            raise T085NativeExecutionError("wrapped adapter lacks step")
        transition = step(action)
        if not isinstance(transition, SimulatorTransition):
            raise T085NativeExecutionError("adapter step did not return a transition")
        self._step_count += 1
        if (
            pending is not None
            and _authoritative_terminal_outcome(transition) is not None
        ):
            if self._terminal_labels:
                raise T085NativeExecutionError(
                    "T085 native execution produced duplicate terminal labels"
                )
            self._terminal_labels.append(
                finalize_t085_native_root_edge_label(
                    pending,
                    transition,
                    pre_action_snapshot=self._current_snapshot,
                    pre_action_actions=self._current_actions,
                    selected_action=action,
                )
            )
        self._current_snapshot = transition.snapshot
        self._current_actions = []
        return transition


@dataclass(frozen=True)
class T085UnguidedBattleSearchV2Controller:
    """Minimal Cohort-C controller for native v2 with both callbacks absent."""

    simulations: int = 100
    action_space: ActionSpaceConfig = field(
        default_factory=ActionSpaceConfig.initial_no_potions
    )
    provenance: ControllerProvenance = field(init=False)  # type: ignore[assignment]

    def __post_init__(self) -> None:
        _positive_int(self.simulations, "T085 unguided v2 simulations")
        if (
            self.action_space.to_dict()
            != ActionSpaceConfig.initial_no_potions().to_dict()
        ):
            raise T085NativeExecutionError(
                "T085 unguided v2 requires initial_no_potions action space"
            )
        native_identity = _validate_t085_native_source_manifest("battle_search_v2")
        object.__setattr__(
            self,
            "provenance",
            ControllerProvenance(
                kind="t085_native_battle_search_v2",
                name=f"t085_unguided_search_v2_s{self.simulations}",
                config={
                    "task_id": "T085",
                    "execution_version": T085_NATIVE_EXECUTION_VERSION,
                    "information_regime": NATIVE_SEARCH_INFORMATION_REGIME,
                    "native_identity": native_identity,
                    "native_search_schema_id": ORACLE_SEARCH_SCHEMA_ID,
                    "native_search_api": T085_NATIVE_V2_API,
                    "native_search_patch_identity": T085_NATIVE_V2_PATCH,
                    "search_budget": self.simulations,
                    "root_selection_rule": "highest_mean",
                    "action_space": self.action_space.to_dict(),
                    "policy_prior_callback": None,
                    "leaf_value_callback": None,
                    "native_leaf_value": "BattleScumSearcher2::evaluateEndState",
                },
            ),
        )

    def select_action(
        self,
        adapter: object,
        snapshot: SimulatorSnapshot,
        actions: Sequence[SimulatorAction],
        context: Any,
        step_index: int,
    ) -> ControllerDecision:
        report = _native_search_report(
            adapter,
            snapshot,
            actions,
            context,
            simulations=self.simulations,
            backend="battle_search_v2",
        )
        target = select_oracle_root_action(report, selection_rule="highest_mean")
        metadata = oracle_search_controller_metadata(report, target)
        metadata["t085_native_execution"] = {
            "execution_version": T085_NATIVE_EXECUTION_VERSION,
            "controller_step_index": step_index,
            "callbacks_disabled": True,
            "native_leaf_value": "BattleScumSearcher2::evaluateEndState",
        }
        return ControllerDecision(
            selected_index=target.legal_action_index,
            provenance=self.provenance,
            reason="t085_unguided_search_v2:highest_mean",
            score=target.score,
            metadata=metadata,
        )


def build_t085_cohort_c_source_controller() -> RoutedRunController:
    """Build the exact repository-owned current-occupancy source controller."""

    return RoutedRunController(
        battle=T085UnguidedBattleSearchV2Controller(simulations=100),
        non_combat=PolicyController(ExpertNonCombatDriver(seed=42042)),
    )


def build_t085_cohort_b_source_controller() -> RoutedRunController:
    """Build the exact T085 Cohort-B assisted source controller."""

    native_identity = _validate_t085_native_source_manifest("battle_search")
    return RoutedRunController(
        battle=OracleSearchController(
            simulations=20,
            root_selection_rule="highest_mean",
            action_space=ActionSpaceConfig.initial_no_potions(),
            native_source_identity=native_identity,
        ),
        non_combat=PolicyController(ExpertNonCombatDriver(seed=42042)),
    )


def _require_t085_stable_path(path: str | Path, label: str) -> Path:
    resolved = Path(path).resolve()
    try:
        resolved.relative_to(T085_ARTIFACT_ROOT.resolve())
    except ValueError as exc:
        raise T085NativeExecutionError(
            f"T085 {label} must be under the stable ignored T085 artifact root"
        ) from exc
    return resolved


def _load_t085_t042_scale_manifest() -> dict[str, object]:
    """Load and verify the accepted T042 source-generation anchor.

    The anchor is configuration evidence only.  Cohort B always uses fresh
    ``851001..852024`` source runs and never reuses the accepted T042 pool.
    """

    reference = T085_INPUT_ARTIFACT_IDENTITIES.get("t042_scale_manifest")
    if not isinstance(reference, Mapping):
        raise T085NativeExecutionError(
            "T085 accepted T042 scale-manifest identity is missing"
        )
    expected_path = reference.get("path")
    if not isinstance(expected_path, str) or not expected_path:
        raise T085NativeExecutionError(
            "T085 accepted T042 scale-manifest path is missing"
        )
    if reference.get("schema_id") != "t042-assisted-source-scale-manifest-v2":
        raise T085NativeExecutionError(
            "T085 accepted T042 scale-manifest schema is invalid"
        )
    if reference.get("sha256") != T085_T042_SCALE_MANIFEST_SHA256:
        raise T085NativeExecutionError(
            "T085 accepted T042 scale-manifest SHA is not the fixed identity"
        )
    expected_byte_count = reference.get("byte_count")
    if (
        isinstance(expected_byte_count, bool)
        or not isinstance(expected_byte_count, int)
        or expected_byte_count <= 0
    ):
        raise T085NativeExecutionError(
            "T085 accepted T042 scale-manifest byte count is invalid"
        )
    path = Path(expected_path).resolve(strict=True)
    if path.stat().st_size != expected_byte_count:
        raise T085NativeExecutionError(
            "T085 accepted T042 scale-manifest byte count mismatch"
        )
    if sha256_file(path) != T085_T042_SCALE_MANIFEST_SHA256:
        raise T085NativeExecutionError(
            "T085 accepted T042 scale-manifest bytes do not match the fixed SHA"
        )
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise T085NativeExecutionError(
            "T085 accepted T042 scale-manifest is unavailable or invalid"
        ) from exc
    if not isinstance(payload, Mapping):
        raise T085NativeExecutionError(
            "T085 accepted T042 scale-manifest is not an object"
        )
    frozen = {
        "schema_id": "t042-assisted-source-scale-manifest-v2",
        "runs_per_arm": 1000,
        "workers": 16,
        "base_shards": 16,
        "sim_steps": 500,
        "oracle_search_simulations": 20,
        "non_combat_seed": 42042,
        "assistance_policy_seed": 42042,
    }
    for key, expected in frozen.items():
        if payload.get(key) != expected:
            raise T085NativeExecutionError(
                f"T085 T042 scale-manifest field {key} is not the accepted value"
            )
    shard_counts = payload.get("shard_counts")
    if (
        not isinstance(shard_counts, Mapping)
        or shard_counts.get("assist_hp75_potion") != 256
    ):
        raise T085NativeExecutionError(
            "T085 T042 scale-manifest assist_hp75_potion shard count is invalid"
        )
    arms = payload.get("arms")
    hp75 = arms.get("assist_hp75_potion") if isinstance(arms, Mapping) else None
    if not isinstance(hp75, Mapping):
        raise T085NativeExecutionError(
            "T085 T042 scale-manifest lacks assist_hp75_potion evidence"
        )
    for key, expected in (
        ("command_passed", True),
        ("terminal_source_runs", 1000),
        ("truncated_source_runs", 0),
    ):
        if hp75.get(key) != expected:
            raise T085NativeExecutionError(
                f"T085 T042 assist_hp75_potion field {key} is not accepted"
            )
    return {
        "path": str(path),
        "schema_id": reference["schema_id"],
        "sha256": T085_T042_SCALE_MANIFEST_SHA256,
        "byte_count": expected_byte_count,
        "runs_per_arm": 1000,
        "workers": 16,
        "base_shards": 16,
        "sim_steps": 500,
        "oracle_search_simulations": 20,
        "non_combat_seed": 42042,
        "assistance_policy_seed": 42042,
        "assist_hp75_potion": {
            "shard_count": 256,
            "terminal_source_runs": 1000,
            "truncated_source_runs": 0,
            "pool_path": hp75.get("pool_path"),
            "pool_sha256": hp75.get("pool_sha256"),
            "pool_size_bytes": hp75.get("pool_size_bytes"),
        },
    }


def _t085_source_pool_reference(
    path: Path,
    *,
    record_count: int,
    source_run_count: int,
) -> dict[str, object]:
    return {
        "path": str(path),
        "schema_id": T085_C_SOURCE_POOL_SCHEMA_ID,
        "sha256": sha256_file(path),
        "byte_count": path.stat().st_size,
        "format_version": BATTLE_START_POOL_FORMAT_VERSION,
        "distribution_kind": "natural_run",
        "record_count": record_count,
        "source_run_count": source_run_count,
    }


def _t085_assisted_source_pool_reference(
    path: Path,
    *,
    record_count: int,
    source_run_count: int,
) -> dict[str, object]:
    """Describe the outer assisted JSONL and its inner pool format."""

    return {
        "path": str(path),
        "schema_id": T085_B_SOURCE_POOL_SCHEMA_ID,
        "sha256": sha256_file(path),
        "byte_count": path.stat().st_size,
        "format_version": ASSISTED_SOURCE_POOL_FORMAT_VERSION,
        "source_pool_format_version": BATTLE_START_POOL_FORMAT_VERSION,
        "distribution_kind": "assisted_run",
        "record_count": record_count,
        "source_run_count": source_run_count,
    }


def _validate_t085_assisted_controller_provenance(
    actual: Mapping[str, object],
    *,
    controller: RoutedRunController,
    expected_source_run_count: int,
) -> None:
    """Accept exact shard provenance or the repository merge wrapper only."""

    expected = controller.provenance.to_dict()
    if dict(actual) == expected:
        return
    if (
        actual.get("schema_version") != expected.get("schema_version")
        or actual.get("kind") != expected.get("kind")
        or actual.get("name") != expected.get("name")
    ):
        raise T085NativeExecutionError(
            "T085 Cohort B merged source controller provenance identity mismatch"
        )
    actual_config = actual.get("config")
    expected_config = expected.get("config")
    if not isinstance(actual_config, Mapping) or not isinstance(
        expected_config, Mapping
    ):
        raise T085NativeExecutionError(
            "T085 Cohort B source controller provenance config is invalid"
        )
    base_config = {
        key: value
        for key, value in actual_config.items()
        if key != "assisted_source_pool_merge"
    }
    if base_config != dict(expected_config):
        raise T085NativeExecutionError(
            "T085 Cohort B merged source controller changed its controller config"
        )
    merge = actual_config.get("assisted_source_pool_merge")
    if not isinstance(merge, Mapping):
        raise T085NativeExecutionError(
            "T085 Cohort B merged source controller lacks merge provenance"
        )
    if (
        merge.get("merge_version") != "assisted-source-pool-shard-merge-v1"
        or merge.get("shard_count") != 16
        or not isinstance(merge.get("shards"), list)
        or len(merge["shards"]) != 16
    ):
        raise T085NativeExecutionError(
            "T085 Cohort B merged source controller merge provenance is incomplete"
        )
    merge_counts = {
        key: merge.get(key)
        for key in (
            "source_run_count",
            "terminal_run_count",
            "truncated_run_count",
        )
    }
    if any(
        isinstance(value, bool) or not isinstance(value, int) or value < 0
        for value in merge_counts.values()
    ) or (
        merge_counts["source_run_count"] != expected_source_run_count
        or merge_counts["terminal_run_count"] + merge_counts["truncated_run_count"]
        != expected_source_run_count
    ):
        raise T085NativeExecutionError(
            "T085 Cohort B merged source controller run counts are invalid"
        )


def _validate_t085_assisted_merged_source_shards(
    artifact: AssistedSourcePoolArtifact,
    *,
    expected_seeds: Sequence[int],
) -> None:
    """Require the complete B pool to retain the 16 verified source shards."""

    expected_seed_list = list(expected_seeds)
    if len(expected_seed_list) != T085_COHORT_B_RUN_COUNT:
        return
    raw_shards = getattr(artifact, "source_shards", None)
    if not isinstance(raw_shards, Sequence) or isinstance(raw_shards, (str, bytes)):
        raise T085NativeExecutionError(
            "T085 Cohort B complete source pool lacks shard provenance"
        )
    if len(raw_shards) != 16:
        raise T085NativeExecutionError(
            "T085 Cohort B complete source pool must retain all 16 source shards"
        )
    normalized_shards: list[dict[str, object]] = []
    expected_record_count = 0
    terminal_run_count = 0
    truncated_run_count = 0
    for shard_index, raw_shard in enumerate(raw_shards):
        if not isinstance(raw_shard, Mapping):
            raise T085NativeExecutionError(
                "T085 Cohort B source shard provenance is malformed"
            )
        shard_start = expected_seed_list[shard_index * 64]
        shard_end = expected_seed_list[(shard_index + 1) * 64 - 1]
        expected = {
            "merge_version": ASSISTED_SOURCE_POOL_MERGE_VERSION,
            "shard_index": shard_index,
            "schema_id": ASSISTED_SOURCE_POOL_SCHEMA_ID,
            "format_version": ASSISTED_SOURCE_POOL_FORMAT_VERSION,
            "assistance_level": "assist_hp75_potion",
            "source_run_count": 64,
            "source_seed_range": {
                "min": shard_start,
                "max": shard_end,
                "count": 64,
            },
        }
        if any(raw_shard.get(key) != value for key, value in expected.items()):
            raise T085NativeExecutionError(
                "T085 Cohort B merged source shard range/provenance is not exact"
            )
        shard_terminal_run_count = raw_shard.get("terminal_run_count")
        shard_truncated_run_count = raw_shard.get("truncated_run_count")
        if any(
            isinstance(value, bool) or not isinstance(value, int) or value < 0
            for value in (shard_terminal_run_count, shard_truncated_run_count)
        ) or (shard_terminal_run_count + shard_truncated_run_count != 64):
            raise T085NativeExecutionError(
                "T085 Cohort B merged source shard run counts are invalid"
            )
        terminal_run_count += shard_terminal_run_count
        truncated_run_count += shard_truncated_run_count
        path_value = raw_shard.get("path")
        sha_value = raw_shard.get("sha256")
        if not isinstance(path_value, str) or not Path(path_value).is_absolute():
            raise T085NativeExecutionError(
                "T085 Cohort B merged source shard path is not absolute"
            )
        if not isinstance(sha_value, str) or len(sha_value) != 64:
            raise T085NativeExecutionError(
                "T085 Cohort B merged source shard SHA-256 is invalid"
            )
        shard_path = Path(path_value).resolve()
        try:
            actual_sha = sha256_file(shard_path)
        except OSError as exc:
            raise T085NativeExecutionError(
                "T085 Cohort B merged source shard is unavailable"
            ) from exc
        if actual_sha != sha_value:
            raise T085NativeExecutionError(
                "T085 Cohort B merged source shard SHA-256 changed"
            )
        record_count = raw_shard.get("record_count")
        if isinstance(record_count, bool) or not isinstance(record_count, int):
            raise T085NativeExecutionError(
                "T085 Cohort B merged source shard record count is invalid"
            )
        if record_count < 0:
            raise T085NativeExecutionError(
                "T085 Cohort B merged source shard record count is negative"
            )
        expected_record_count += record_count
        normalized_shards.append(dict(raw_shard))
    if expected_record_count != len(artifact.records):
        raise T085NativeExecutionError(
            "T085 Cohort B merged source shard records do not cover the pool"
        )
    if (
        terminal_run_count != artifact.pool.terminal_run_count
        or truncated_run_count != artifact.pool.truncated_run_count
    ):
        raise T085NativeExecutionError(
            "T085 Cohort B merged source shard counts do not cover the pool"
        )
    provenance = artifact.pool.source_controller_provenance
    config = provenance.get("config") if isinstance(provenance, Mapping) else None
    merge = (
        config.get("assisted_source_pool_merge")
        if isinstance(config, Mapping)
        else None
    )
    if not isinstance(merge, Mapping) or merge.get("shards") != normalized_shards:
        raise T085NativeExecutionError(
            "T085 Cohort B merged source controller provenance is not bound to shards"
        )


def _validate_t085_c_merged_source_metadata(
    pool_path: Path,
    pool: NaturalBattleStartPool,
) -> dict[str, object]:
    """Validate the generic natural-pool merge evidence used by Cohort C."""

    try:
        metadata, metadata_record_count = load_natural_battle_start_pool_metadata_jsonl(
            pool_path
        )
    except (OSError, ValueError) as exc:
        raise T085NativeExecutionError(
            "T085 Cohort C merged source pool metadata is unavailable"
        ) from exc
    if (
        metadata.get("format_version") != BATTLE_START_POOL_FORMAT_VERSION
        or metadata.get("record_count") != metadata_record_count
        or metadata_record_count != len(pool.records)
    ):
        raise T085NativeExecutionError(
            "T085 Cohort C merged source pool record metadata is not exact"
        )
    merge = metadata.get("source_pool_merge")
    if not isinstance(merge, Mapping):
        raise T085NativeExecutionError(
            "T085 Cohort C source pool lacks repository merge evidence"
        )
    source_shards = merge.get("source_shards")
    if (
        merge.get("schema_id") != BATTLE_START_POOL_SHARD_MERGE_SCHEMA_ID
        or merge.get("merge_version") != BATTLE_START_POOL_SHARD_MERGE_VERSION
        or merge.get("shard_count") != 16
        or not isinstance(source_shards, list)
        or len(source_shards) != 16
    ):
        raise T085NativeExecutionError(
            "T085 Cohort C source pool merge evidence is not a 16-shard merge"
        )
    expected_record_count = 0
    for shard_index, raw_shard in enumerate(source_shards):
        if not isinstance(raw_shard, Mapping):
            raise T085NativeExecutionError(
                "T085 Cohort C source shard merge evidence is malformed"
            )
        expected_start = T085_COHORT_C_SEED_START + shard_index * 8
        expected_end = expected_start + 7
        expected = {
            "merge_version": BATTLE_START_POOL_SHARD_MERGE_VERSION,
            "shard_index": shard_index,
            "format_version": BATTLE_START_POOL_FORMAT_VERSION,
            "source_run_count": 8,
            "terminal_run_count": 8,
            "truncated_run_count": 0,
            "source_seed_range": {
                "min": expected_start,
                "max": expected_end,
                "count": 8,
            },
        }
        if any(raw_shard.get(key) != value for key, value in expected.items()):
            raise T085NativeExecutionError(
                "T085 Cohort C source shard merge range/provenance is not exact"
            )
        path_value = raw_shard.get("path")
        sha_value = raw_shard.get("sha256")
        if not isinstance(path_value, str) or not Path(path_value).is_absolute():
            raise T085NativeExecutionError(
                "T085 Cohort C source shard merge path is not absolute"
            )
        if not isinstance(sha_value, str) or len(sha_value) != 64:
            raise T085NativeExecutionError(
                "T085 Cohort C source shard merge SHA-256 is invalid"
            )
        shard_path = Path(path_value).resolve()
        try:
            actual_sha = sha256_file(shard_path)
        except OSError as exc:
            raise T085NativeExecutionError(
                "T085 Cohort C source shard merge input is unavailable"
            ) from exc
        if actual_sha != sha_value:
            raise T085NativeExecutionError(
                "T085 Cohort C source shard merge input SHA-256 changed"
            )
        record_count = raw_shard.get("record_count")
        if isinstance(record_count, bool) or not isinstance(record_count, int):
            raise T085NativeExecutionError(
                "T085 Cohort C source shard merge record count is invalid"
            )
        if record_count < 0:
            raise T085NativeExecutionError(
                "T085 Cohort C source shard merge record count is negative"
            )
        expected_record_count += record_count
    if expected_record_count != len(pool.records):
        raise T085NativeExecutionError(
            "T085 Cohort C source shard records do not cover the merged pool"
        )
    if (
        metadata.get("source_run_count") != T085_COHORT_C_RUN_COUNT
        or metadata.get("terminal_run_count") != T085_COHORT_C_RUN_COUNT
        or metadata.get("truncated_run_count") != 0
    ):
        raise T085NativeExecutionError(
            "T085 Cohort C merged source pool run counts are not complete"
        )
    return dict(merge)


def _validate_t085_b_source_pool(
    artifact: AssistedSourcePoolArtifact,
    *,
    controller: RoutedRunController,
    expected_seeds: Sequence[int],
) -> None:
    """Validate the actual outer/inner assisted source-pool contract."""

    if artifact.schema_id != ASSISTED_SOURCE_POOL_SCHEMA_ID:
        raise T085NativeExecutionError(
            "T085 Cohort B source pool is not assisted-run-source-pool-v1"
        )
    if artifact.format_version != ASSISTED_SOURCE_POOL_FORMAT_VERSION:
        raise T085NativeExecutionError(
            "T085 Cohort B assisted source pool format is not current"
        )
    if artifact.source_pool_format_version != BATTLE_START_POOL_FORMAT_VERSION:
        raise T085NativeExecutionError(
            "T085 Cohort B inner source pool is not battle-start-pool v4"
        )
    if artifact.assistance_level != "assist_hp75_potion":
        raise T085NativeExecutionError(
            "T085 Cohort B source pool assistance level is not assist_hp75_potion"
        )
    if (
        artifact.assistance_schedule.to_dict()
        != assistance_schedule_by_level("assist_hp75_potion").to_dict()
    ):
        raise T085NativeExecutionError(
            "T085 Cohort B source pool assistance schedule is not frozen"
        )
    if artifact.policy_seed != 42042:
        raise T085NativeExecutionError(
            "T085 Cohort B source pool assistance policy seed is not 42042"
        )
    pool = artifact.pool
    if pool.format_version != BATTLE_START_POOL_FORMAT_VERSION:
        raise T085NativeExecutionError(
            "T085 Cohort B source pool inner format is not current"
        )
    expected_seed_list = list(expected_seeds)
    if pool.source_run_count != len(expected_seed_list):
        raise T085NativeExecutionError(
            "T085 Cohort B source pool run count does not match its shard"
        )
    run_counts = (pool.terminal_run_count, pool.truncated_run_count)
    if (
        any(
            isinstance(value, bool) or not isinstance(value, int) or value < 0
            for value in run_counts
        )
        or sum(run_counts) != pool.source_run_count
    ):
        raise T085NativeExecutionError(
            "T085 Cohort B source pool terminal/truncated run counts are invalid"
        )
    if pool.problems:
        raise T085NativeExecutionError(
            "T085 Cohort B source pool contains source-generation problems"
        )
    expected_controller = controller.provenance.to_dict()
    _validate_t085_assisted_controller_provenance(
        pool.source_controller_provenance,
        controller=controller,
        expected_source_run_count=pool.source_run_count,
    )
    _validate_t085_assisted_merged_source_shards(
        artifact,
        expected_seeds=expected_seed_list,
    )
    summaries = pool.source_run_summaries
    if len(summaries) != len(expected_seed_list):
        raise T085NativeExecutionError(
            "T085 Cohort B source pool lacks one summary per source run"
        )
    summary_ids = [summary.source_run_id for summary in summaries]
    summary_seeds = [summary.source_seed for summary in summaries]
    if summary_seeds != expected_seed_list or len(set(summary_ids)) != len(summary_ids):
        raise T085NativeExecutionError(
            "T085 Cohort B source pool source-run inventory is not exact"
        )
    if any(
        not isinstance(summary.terminal, bool)
        or isinstance(summary.problem_count, bool)
        or not isinstance(summary.problem_count, int)
        or summary.problem_count < 0
        or summary.problem_count != len(summary.problems)
        or summary.problems
        for summary in summaries
    ):
        raise T085NativeExecutionError(
            "T085 Cohort B source pool source-run execution problems are present"
        )
    terminal_summary_count = sum(1 for summary in summaries if summary.terminal)
    if terminal_summary_count != pool.terminal_run_count:
        raise T085NativeExecutionError(
            "T085 Cohort B source pool summary terminal count is not bound"
        )
    summary_by_run = dict(zip(summary_ids, summaries, strict=True))
    expected_battle_provenance = controller.battle.provenance.to_dict()
    expected_non_combat_provenance = controller.non_combat.provenance.to_dict()
    expected_seed_set = set(expected_seed_list)
    for index, record in enumerate(pool.records):
        if not isinstance(record, BattleStartCheckpointRecord):
            raise T085NativeExecutionError(
                f"T085 Cohort B source record {index} is not a full restore record"
            )
        if record.distribution_kind != "assisted_run":
            raise T085NativeExecutionError(
                f"T085 Cohort B source record {index} is not assisted_run"
            )
        if record.source_seed not in expected_seed_set:
            raise T085NativeExecutionError(
                f"T085 Cohort B source record {index} has a seed outside its shard"
            )
        summary = summary_by_run.get(record.source_run_id)
        if summary is None or summary.source_seed != record.source_seed:
            raise T085NativeExecutionError(
                f"T085 Cohort B source record {index} is not bound to a source summary"
            )
        if record.source_controller_provenance != expected_controller:
            raise T085NativeExecutionError(
                f"T085 Cohort B source record {index} has the wrong controller"
            )
        if record.source_battle_controller_provenance != expected_battle_provenance:
            raise T085NativeExecutionError(
                f"T085 Cohort B source record {index} has the wrong battle controller"
            )
        if (
            record.source_non_combat_controller_provenance
            != expected_non_combat_provenance
        ):
            raise T085NativeExecutionError(
                f"T085 Cohort B source record {index} has the wrong non-combat controller"
            )


def _validate_t085_c_source_pool(
    pool: NaturalBattleStartPool,
    *,
    controller: RoutedRunController,
    expected_seeds: Sequence[int],
) -> None:
    """Validate source-pool metadata before it can become T085 evidence."""

    if pool.format_version != 4:
        raise T085NativeExecutionError(
            "T085 Cohort C source pool is not current battle-start-pool v4"
        )
    if pool.source_run_count != len(expected_seeds):
        raise T085NativeExecutionError(
            "T085 Cohort C source pool run count does not match its shard"
        )
    terminal_run_count = getattr(pool, "terminal_run_count", None)
    truncated_run_count = getattr(pool, "truncated_run_count", None)
    if terminal_run_count != pool.source_run_count or truncated_run_count != 0:
        raise T085NativeExecutionError(
            "T085 Cohort C source pool must contain only complete, non-truncated runs"
        )
    if getattr(pool, "problems", ()):
        raise T085NativeExecutionError(
            "T085 Cohort C source pool contains source-generation problems"
        )
    if pool.source_controller_provenance != controller.provenance.to_dict():
        raise T085NativeExecutionError(
            "T085 Cohort C source pool controller provenance is not exact"
        )
    summaries = pool.source_run_summaries
    if len(summaries) != len(expected_seeds):
        raise T085NativeExecutionError(
            "T085 Cohort C source pool lacks one summary per source run"
        )
    if any(
        not getattr(summary, "terminal", False)
        or getattr(summary, "problem_count", 0) != 0
        or getattr(summary, "problems", ())
        for summary in summaries
    ):
        raise T085NativeExecutionError(
            "T085 Cohort C source pool source-run completeness is not proven"
        )
    actual_seeds = [summary.source_seed for summary in summaries]
    if actual_seeds != list(expected_seeds):
        raise T085NativeExecutionError(
            "T085 Cohort C source pool seed order/domain is not exact"
        )
    summary_by_run = {summary.source_run_id: summary for summary in summaries}
    if len(summary_by_run) != len(summaries):
        raise T085NativeExecutionError(
            "T085 Cohort C source pool source-run identities are not unique"
        )
    expected_battle_provenance = controller.battle.provenance.to_dict()
    expected_non_combat_provenance = controller.non_combat.provenance.to_dict()
    expected_seed_set = set(expected_seeds)
    for index, record in enumerate(pool.records):
        if record.distribution_kind != "natural_run":
            raise T085NativeExecutionError(
                f"T085 Cohort C source record {index} is not natural_run"
            )
        if record.source_seed not in expected_seed_set:
            raise T085NativeExecutionError(
                f"T085 Cohort C source record {index} has a seed outside its shard"
            )
        summary = summary_by_run.get(record.source_run_id)
        if summary is None or summary.source_seed != record.source_seed:
            raise T085NativeExecutionError(
                f"T085 Cohort C source record {index} is not bound to a source summary"
            )
        if record.source_battle_controller_provenance != expected_battle_provenance:
            raise T085NativeExecutionError(
                f"T085 Cohort C source record {index} has the wrong battle controller"
            )
        if (
            record.source_non_combat_controller_provenance
            != expected_non_combat_provenance
        ):
            raise T085NativeExecutionError(
                f"T085 Cohort C source record {index} has the wrong non-combat controller"
            )


def _t085_cohort_c_selection_rank(
    record: BattleStartCheckpointRecord,
) -> tuple[str, str]:
    """Rank a battle start by the frozen source-run/battle identity pair."""

    # ``source_checkpoint_id`` is the portable complete identity of this
    # battle-start record.  Include the source-run identity explicitly so a
    # source artifact cannot make two runs compete only on an opaque local
    # checkpoint label.
    ranking_identity = f"{record.source_run_id}:{record.source_checkpoint_id}"
    return sha256(ranking_identity.encode("utf-8")).hexdigest(), ranking_identity


def _t085_source_run_representatives(
    records: Sequence[BattleStartCheckpointRecord],
    summaries: Sequence[object],
    *,
    cohort: str,
) -> list[BattleStartCheckpointRecord]:
    """Choose one deterministic complete-source representative per run."""

    by_run: dict[str, list[BattleStartCheckpointRecord]] = {}
    for record in records:
        by_run.setdefault(record.source_run_id, []).append(record)
    selected: list[BattleStartCheckpointRecord] = []
    for summary in summaries:
        source_run_id = getattr(summary, "source_run_id", None)
        candidates = by_run.get(source_run_id)
        if not isinstance(source_run_id, str) or not candidates:
            raise T085NativeExecutionError(
                f"T085 Cohort {cohort} source manifest cannot bind a run "
                "without a battle-start record"
            )
        selected.append(min(candidates, key=_t085_cohort_c_selection_rank))
    complete_ids = [record.source_checkpoint_id for record in selected]
    if len(complete_ids) != len(set(complete_ids)):
        raise T085NativeExecutionError(
            f"T085 Cohort {cohort} complete source identities are not unique"
        )
    return selected


def _t085_b_source_run_representatives(
    records: Sequence[BattleStartCheckpointRecord],
    summaries: Sequence[object],
) -> list[BattleStartCheckpointRecord | None]:
    """Choose valid-run representatives and leave truncated runs unidentifiable."""

    by_run: dict[str, list[BattleStartCheckpointRecord]] = {}
    for record in records:
        by_run.setdefault(record.source_run_id, []).append(record)
    selected: list[BattleStartCheckpointRecord | None] = []
    for summary in summaries:
        source_run_id = getattr(summary, "source_run_id", None)
        if not isinstance(source_run_id, str):
            raise T085NativeExecutionError(
                "T085 Cohort B source manifest has an invalid source run identity"
            )
        terminal = getattr(summary, "terminal", None)
        if terminal is False:
            selected.append(None)
            continue
        if terminal is not True:
            raise T085NativeExecutionError(
                "T085 Cohort B source manifest has an invalid run terminal flag"
            )
        candidates = by_run.get(source_run_id)
        if not candidates:
            raise T085NativeExecutionError(
                "T085 Cohort B source manifest cannot bind a valid run "
                "without a battle-start record"
            )
        selected.append(min(candidates, key=_t085_cohort_c_selection_rank))
    complete_ids = [
        record.source_checkpoint_id for record in selected if record is not None
    ]
    if len(complete_ids) != len(set(complete_ids)):
        raise T085NativeExecutionError(
            "T085 Cohort B complete source identities are not unique"
        )
    return selected


def _t085_b_source_run_inventory(
    summaries: Sequence[object],
    representatives: Sequence[BattleStartCheckpointRecord | None],
) -> list[dict[str, object]]:
    """Serialize terminal status while retaining every ordered source run."""

    if len(summaries) != len(representatives):
        raise T085NativeExecutionError(
            "T085 Cohort B source summary/representative counts do not match"
        )
    inventory: list[dict[str, object]] = []
    for summary, representative in zip(summaries, representatives, strict=True):
        terminal = getattr(summary, "terminal", None)
        source_run_id = getattr(summary, "source_run_id", None)
        source_seed = getattr(summary, "source_seed", None)
        if (
            not isinstance(source_run_id, str)
            or not isinstance(source_seed, int)
            or isinstance(source_seed, bool)
            or not isinstance(terminal, bool)
        ):
            raise T085NativeExecutionError(
                "T085 Cohort B source run inventory contains malformed summary data"
            )
        if terminal:
            if representative is None:
                raise T085NativeExecutionError(
                    "T085 Cohort B valid source run lacks complete identity"
                )
            complete_source_identity: str | None = representative.source_checkpoint_id
            source_valid = True
            failure_reason: str | None = None
        else:
            if representative is not None:
                raise T085NativeExecutionError(
                    "T085 Cohort B invalid source run has a complete identity"
                )
            complete_source_identity = None
            source_valid = False
            failure_reason = T085_BOUNDED_RUN_TRUNCATION_FAILURE_REASON
        inventory.append(
            {
                "source_run_seed": source_seed,
                "source_run_identity": source_run_id,
                "complete_source_identity": complete_source_identity,
                "source_valid": source_valid,
                "failure_reason": failure_reason,
            }
        )
    return inventory


def _t085_validate_b_shard_manifest(
    manifest_path: Path,
    *,
    pool_path: Path,
    plan: T085CohortBSourceGenerationPlan,
    native_identity: Mapping[str, object],
    t042_anchor: Mapping[str, object],
    controller: RoutedRunController,
) -> dict[str, object]:
    """Validate one T085 B source shard before repository-owned merging."""

    try:
        document = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise T085NativeExecutionError(
            f"T085 Cohort B source shard manifest is unavailable: {manifest_path}"
        ) from exc
    if not isinstance(document, Mapping):
        raise T085NativeExecutionError(
            "T085 Cohort B source shard manifest is not an object"
        )
    if (
        document.get("schema_id") != T085_B_SOURCE_SHARD_MANIFEST_SCHEMA_ID
        or document.get("task_id") != "T085"
        or document.get("cohort") != "B"
        or document.get("artifact_scope") != "source_generation_shard"
        or document.get("partial") is not True
        or document.get("complete") is not False
        or document.get("shard_count") != 16
        or document.get("worker_count") != 16
        or document.get("effective_worker_count") != 16
        or document.get("partition_scheme") != "contiguous_seed_ranges"
        or document.get("shard_index") != plan.shard_index
    ):
        raise T085NativeExecutionError(
            "T085 Cohort B source shard manifest has the wrong shard contract"
        )
    expected_seed_inventory = list(plan.seed_inventory)
    if (
        document.get("shard_source_run_count") != len(expected_seed_inventory)
        or document.get("shard_source_run_seed_start") != expected_seed_inventory[0]
        or document.get("shard_source_run_seed_end") != expected_seed_inventory[-1]
        or document.get("shard_source_run_seed_inventory") != expected_seed_inventory
        or document.get("source_run_seed_inventory") != expected_seed_inventory
    ):
        raise T085NativeExecutionError(
            "T085 Cohort B source shard manifest seed inventory is not exact"
        )
    expected_configuration = {
        "source_run_seed_start": T085_COHORT_B_SEED_START,
        "source_run_seed_end": T085_COHORT_B_SEED_END,
        "source_run_count": T085_COHORT_B_RUN_COUNT,
        "max_outer_steps": 500,
        "action_space": "initial_no_potions",
        "battle_controller": "oracle_search",
        "battle_simulations": 20,
        "root_selection": "highest_mean",
        "non_combat_controller": "expert_non_combat_v1",
        "non_combat_policy_seed": 42042,
        "assistance_level": "assist_hp75_potion",
        "assistance_policy_seed": 42042,
    }
    if any(
        document.get(key) != expected
        for key, expected in expected_configuration.items()
    ):
        raise T085NativeExecutionError(
            "T085 Cohort B source shard manifest configuration is not exact"
        )
    if document.get("native_identity") != dict(native_identity):
        raise T085NativeExecutionError(
            "T085 Cohort B source shard manifest native identity mismatch"
        )
    anchor_reference = document.get("t042_scale_manifest")
    if not isinstance(anchor_reference, Mapping) or dict(anchor_reference) != dict(
        t042_anchor
    ):
        raise T085NativeExecutionError(
            "T085 Cohort B source shard manifest T042 anchor mismatch"
        )
    if document.get("t042_scale_manifest_sha256") != T085_T042_SCALE_MANIFEST_SHA256:
        raise T085NativeExecutionError(
            "T085 Cohort B source shard manifest T042 anchor SHA mismatch"
        )
    if (
        document.get("policy_prior_callback") is not None
        or document.get("leaf_value_callback") is not None
    ):
        raise T085NativeExecutionError(
            "T085 Cohort B source generation must not carry Search callbacks"
        )
    source_pool_reference = document.get("source_pool_artifact")
    if not isinstance(source_pool_reference, Mapping):
        raise T085NativeExecutionError(
            "T085 Cohort B source shard lacks source pool binding"
        )
    if (
        Path(str(source_pool_reference.get("path"))).resolve() != pool_path.resolve()
        or source_pool_reference.get("schema_id") != T085_B_SOURCE_POOL_SCHEMA_ID
        or source_pool_reference.get("sha256") != sha256_file(pool_path)
        or source_pool_reference.get("byte_count") != pool_path.stat().st_size
        or source_pool_reference.get("format_version")
        != ASSISTED_SOURCE_POOL_FORMAT_VERSION
        or source_pool_reference.get("source_pool_format_version")
        != BATTLE_START_POOL_FORMAT_VERSION
        or source_pool_reference.get("distribution_kind") != "assisted_run"
    ):
        raise T085NativeExecutionError(
            "T085 Cohort B source shard is not bound to its assisted pool"
        )
    with pool_path.open(encoding="utf-8") as stream:
        try:
            artifact = load_assisted_source_pool_jsonl(stream)
        except (OSError, ValueError) as exc:
            raise T085NativeExecutionError(
                "T085 Cohort B source shard pool is invalid"
            ) from exc
    _validate_t085_b_source_pool(
        artifact,
        controller=controller,
        expected_seeds=plan.seed_inventory,
    )
    if (
        source_pool_reference.get("record_count") != len(artifact.records)
        or source_pool_reference.get("source_run_count")
        != artifact.pool.source_run_count
        or document.get("record_count") != len(artifact.records)
        or document.get("terminal_run_count") != artifact.pool.terminal_run_count
        or document.get("truncated_run_count") != artifact.pool.truncated_run_count
    ):
        raise T085NativeExecutionError(
            "T085 Cohort B source shard manifest counts are not bound to its pool"
        )
    representatives = _t085_b_source_run_representatives(
        artifact.records,
        artifact.pool.source_run_summaries,
    )
    if document.get("complete_source_identity_inventory") != [
        record.source_checkpoint_id if record is not None else None
        for record in representatives
    ]:
        raise T085NativeExecutionError(
            "T085 Cohort B source shard complete-source inventory is not exact"
        )
    expected_source_run_inventory = _t085_b_source_run_inventory(
        artifact.pool.source_run_summaries,
        representatives,
    )
    document_source_run_inventory = document.get("source_run_inventory")
    if document_source_run_inventory is None:
        if any(not entry["source_valid"] for entry in expected_source_run_inventory):
            raise T085NativeExecutionError(
                "T085 Cohort B invalid source runs require source_run_inventory"
            )
    elif document_source_run_inventory != expected_source_run_inventory:
        raise T085NativeExecutionError(
            "T085 Cohort B source shard run validity inventory is not exact"
        )
    if document.get("source_run_identity_inventory") != [
        summary.source_run_id for summary in artifact.pool.source_run_summaries
    ]:
        raise T085NativeExecutionError(
            "T085 Cohort B source shard run identity inventory is not exact"
        )
    if (
        document.get("source_controller_provenance")
        != artifact.pool.source_controller_provenance
    ):
        raise T085NativeExecutionError(
            "T085 Cohort B source shard controller provenance is not exact"
        )
    return dict(document)


def _finalize_t085_cohort_b_source_shard_from_chunks(
    *,
    temporary_shards: Sequence[Path],
    temporary_dir: str,
    pool_path: Path,
    manifest_path: Path,
    plan: T085CohortBSourceGenerationPlan,
    native_identity: Mapping[str, object],
    t042_anchor: Mapping[str, object],
    controller: RoutedRunController,
) -> dict[str, object]:
    """Finalize one B shard while its caller holds the root finalization lock."""

    artifact: AssistedSourcePoolArtifact | None = None
    try:
        merged_temporary_path = Path(temporary_dir) / "merged.jsonl"
        with merged_temporary_path.open("w", encoding="utf-8", newline="\n") as stream:
            try:
                dump_merged_assisted_source_pool_shards_jsonl(
                    temporary_shards,
                    stream,
                )
            except (OSError, ValueError) as exc:
                raise T085NativeExecutionError(
                    "T085 Cohort B source chunk merge failed"
                ) from exc
        with merged_temporary_path.open(encoding="utf-8") as stream:
            try:
                artifact = load_assisted_source_pool_jsonl(stream)
            except (OSError, ValueError) as exc:
                raise T085NativeExecutionError(
                    "T085 Cohort B merged source pool is invalid"
                ) from exc
        # The streaming merger records every one-seed input as an internal
        # merge shard. This output is still one externally contracted
        # 64-seed shard, so discard temporary-path provenance and expose the
        # original controller. The outer 16-shard merge adds source_shards.
        if isinstance(artifact, AssistedSourcePoolArtifact):
            artifact = replace(
                artifact,
                pool=replace(
                    artifact.pool,
                    source_controller_provenance=controller.provenance.to_dict(),
                ),
                source_shards=(),
            )
        _validate_t085_b_source_pool(
            artifact,
            controller=controller,
            expected_seeds=plan.seed_inventory,
        )
        with merged_temporary_path.open("w", encoding="utf-8", newline="\n") as stream:
            dump_assisted_source_pool_jsonl(artifact, stream)
        os.replace(merged_temporary_path, pool_path)

        representatives = _t085_b_source_run_representatives(
            artifact.records,
            artifact.pool.source_run_summaries,
        )
        source_pool_reference = _t085_assisted_source_pool_reference(
            pool_path,
            record_count=len(artifact.records),
            source_run_count=artifact.pool.source_run_count,
        )
        manifest = plan.to_dict(
            native_identity=native_identity,
            t042_anchor=t042_anchor,
        )
        manifest.update(
            {
                "source_pool_artifact": source_pool_reference,
                "source_run_seed_inventory": [
                    summary.source_seed
                    for summary in artifact.pool.source_run_summaries
                ],
                "source_run_identity_inventory": [
                    summary.source_run_id
                    for summary in artifact.pool.source_run_summaries
                ],
                "complete_source_identity_inventory": [
                    record.source_checkpoint_id if record is not None else None
                    for record in representatives
                ],
                "source_run_inventory": _t085_b_source_run_inventory(
                    artifact.pool.source_run_summaries,
                    representatives,
                ),
                "record_count": len(artifact.records),
                "terminal_run_count": artifact.pool.terminal_run_count,
                "truncated_run_count": artifact.pool.truncated_run_count,
                "source_controller_provenance": (
                    artifact.pool.source_controller_provenance
                ),
            }
        )
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_reference = _write_t085_json_artifact_atomically(
            manifest_path,
            manifest,
            schema_id=T085_B_SOURCE_SHARD_MANIFEST_SCHEMA_ID,
        )
        return {
            "status": "partial",
            "task_id": "T085",
            "cohort": "B",
            "source_generation_valid": True,
            "pool_artifact": source_pool_reference,
            "source_shard_manifest": manifest_reference,
            "shard": manifest,
        }
    finally:
        if artifact is not None:
            del artifact
        _release_t085_chunk_memory()


def run_t085_cohort_b_source_generation_from_paths(
    *,
    adapter_factory: Callable[[], object],
    pool_output_path: str | Path,
    shard_manifest_output_path: str | Path,
    shard_index: int,
    shard_count: int = 16,
    worker_count: int = 16,
) -> dict[str, object]:
    """Run one exact 64-seed Cohort-B assisted source-generation shard."""

    if not callable(adapter_factory):
        raise T085NativeExecutionError(
            "T085 Cohort B source generation requires an adapter factory"
        )
    plan = T085CohortBSourceGenerationPlan(
        shard_index=shard_index,
        shard_count=shard_count,
        worker_count=worker_count,
    )
    t042_anchor = _load_t085_t042_scale_manifest()
    native_identity = _validate_t085_native_source_manifest("battle_search")
    controller = build_t085_cohort_b_source_controller()
    pool_path = _require_t085_stable_path(pool_output_path, "source pool output")
    manifest_path = _require_t085_stable_path(
        shard_manifest_output_path,
        "source shard manifest output",
    )
    pool_path.parent.mkdir(parents=True, exist_ok=True)
    # The simulator adapter retains substantial state while collecting a run.
    # Keep the collector lifetime bounded to one seed, then use the existing
    # streaming merger so record indices and provenance retain shard order.
    with tempfile.TemporaryDirectory(
        prefix=f".t085-b-shard-{shard_index:02d}-",
        dir=str(pool_path.parent),
    ) as temporary_dir:
        temporary_shards: list[Path] = []
        for chunk_index, seed in enumerate(plan.seed_inventory):
            adapter = adapter_factory()
            try:
                collected = collect_assisted_battle_start_pool(
                    adapter,
                    controller,
                    seeds=(seed,),
                    max_steps=500,
                    action_space=ActionSpaceConfig.initial_no_potions(),
                    assistance_level="assist_hp75_potion",
                    policy_seed=42042,
                    source_run_index_offset=chunk_index,
                )
            finally:
                close = getattr(adapter, "close", None)
                shutdown = getattr(adapter, "shutdown", None)
                if callable(close):
                    close()
                elif callable(shutdown):
                    shutdown()
                del adapter
                _release_t085_chunk_memory()
            if not isinstance(collected, tuple) or len(collected) != 2:
                raise T085NativeExecutionError(
                    "T085 Cohort B source collector did not return artifact and coverage"
                )
            artifact, _coverage = collected
            _validate_t085_b_source_pool(
                artifact,
                controller=controller,
                expected_seeds=(seed,),
            )
            chunk_path = Path(temporary_dir) / f"chunk-{chunk_index:03d}.jsonl"
            with chunk_path.open("w", encoding="utf-8", newline="\n") as stream:
                dump_assisted_source_pool_jsonl(artifact, stream)
            temporary_shards.append(chunk_path)
            del artifact, collected, _coverage

        with _t085_cohort_b_finalization_lock(pool_path.parent):
            return _finalize_t085_cohort_b_source_shard_from_chunks(
                temporary_shards=temporary_shards,
                temporary_dir=temporary_dir,
                pool_path=pool_path,
                manifest_path=manifest_path,
                plan=plan,
                native_identity=native_identity,
                t042_anchor=t042_anchor,
                controller=controller,
            )


def merge_t085_cohort_b_source_pool_from_paths(
    *,
    shard_paths: Sequence[str | Path],
    shard_manifest_paths: Sequence[str | Path],
    merged_pool_output_path: str | Path,
) -> dict[str, object]:
    """Merge exactly 16 verified B shards into one complete assisted pool."""

    if len(shard_paths) != 16 or len(shard_manifest_paths) != 16:
        raise T085NativeExecutionError(
            "T085 Cohort B source merge requires exactly 16 pools and 16 shard manifests"
        )
    t042_anchor = _load_t085_t042_scale_manifest()
    native_identity = _validate_t085_native_source_manifest("battle_search")
    controller = build_t085_cohort_b_source_controller()
    pairs: list[tuple[int, Path, Path, dict[str, object]]] = []
    for pool_path_raw, manifest_path_raw in zip(
        shard_paths, shard_manifest_paths, strict=True
    ):
        pool_path = _require_t085_stable_path(pool_path_raw, "source shard pool")
        manifest_path = _require_t085_stable_path(
            manifest_path_raw,
            "source shard manifest",
        )
        try:
            raw_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise T085NativeExecutionError(
                f"T085 Cohort B source shard manifest is unavailable: {manifest_path}"
            ) from exc
        raw_shard_index = (
            raw_manifest.get("shard_index")
            if isinstance(raw_manifest, Mapping)
            else None
        )
        if isinstance(raw_shard_index, bool) or not isinstance(raw_shard_index, int):
            raise T085NativeExecutionError(
                "T085 Cohort B source shard index is invalid"
            )
        manifest = _t085_validate_b_shard_manifest(
            manifest_path,
            pool_path=pool_path,
            plan=T085CohortBSourceGenerationPlan(shard_index=raw_shard_index),
            native_identity=native_identity,
            t042_anchor=t042_anchor,
            controller=controller,
        )
        pairs.append((raw_shard_index, pool_path, manifest_path, manifest))
    if {item[0] for item in pairs} != set(range(16)):
        raise T085NativeExecutionError(
            "T085 Cohort B source merge must cover every shard index 0..15 exactly once"
        )
    pairs.sort(key=lambda item: item[0])
    for expected_index, (_, pool_path, manifest_path, _manifest) in enumerate(pairs):
        expected_plan = T085CohortBSourceGenerationPlan(shard_index=expected_index)
        _t085_validate_b_shard_manifest(
            manifest_path,
            pool_path=pool_path,
            plan=expected_plan,
            native_identity=native_identity,
            t042_anchor=t042_anchor,
            controller=controller,
        )
    merged_path = _require_t085_stable_path(
        merged_pool_output_path,
        "merged Cohort B source pool output",
    )
    merged_path.parent.mkdir(parents=True, exist_ok=True)
    with merged_path.open("w", encoding="utf-8", newline="\n") as stream:
        try:
            merge_summary = dump_merged_assisted_source_pool_shards_jsonl(
                [item[1] for item in pairs],
                stream,
            )
        except (OSError, ValueError) as exc:
            raise T085NativeExecutionError(
                "T085 Cohort B source shard merge failed"
            ) from exc
    with merged_path.open(encoding="utf-8") as stream:
        merged_artifact = load_assisted_source_pool_jsonl(stream)
    _validate_t085_b_source_pool(
        merged_artifact,
        controller=controller,
        expected_seeds=tuple(
            range(T085_COHORT_B_SEED_START, T085_COHORT_B_SEED_END + 1)
        ),
    )
    if (
        merged_artifact.pool.source_run_count != T085_COHORT_B_RUN_COUNT
        or merged_artifact.pool.terminal_run_count
        + merged_artifact.pool.truncated_run_count
        != T085_COHORT_B_RUN_COUNT
    ):
        raise T085NativeExecutionError(
            "T085 Cohort B merged source pool is not the complete 1024-run pool"
        )
    output_reference = _t085_assisted_source_pool_reference(
        merged_path,
        record_count=len(merged_artifact.records),
        source_run_count=merged_artifact.pool.source_run_count,
    )
    return {
        "status": "merged",
        "task_id": "T085",
        "cohort": "B",
        "source_generation_valid": True,
        "artifact_scope": "source_generation_merge",
        "partial": True,
        "complete": False,
        "native_identity": native_identity,
        "t042_scale_manifest": t042_anchor,
        "pool_artifact": output_reference,
        "source_shards": [item[3] for item in pairs],
        "merge_summary": {
            "assistance_level": merge_summary.assistance_level,
            "source_shards": [dict(item) for item in merge_summary.source_shards],
            "source_run_count": merge_summary.source_run_count,
            "terminal_run_count": merge_summary.terminal_run_count,
            "truncated_run_count": merge_summary.truncated_run_count,
            "record_count": merge_summary.record_count,
            "assistance_decision_count": merge_summary.assistance_decision_count,
        },
    }


def build_t085_cohort_b_source_manifest_from_paths(
    *,
    pool_path: str | Path,
    pool_sha256: str,
    manifest_output_path: str | Path,
) -> dict[str, object]:
    """Build the complete B manifest under the root finalization lock."""

    with _t085_cohort_b_finalization_lock(Path(pool_path).resolve().parent):
        try:
            return _build_t085_cohort_b_source_manifest_from_paths_unlocked(
                pool_path=pool_path,
                pool_sha256=pool_sha256,
                manifest_output_path=manifest_output_path,
            )
        finally:
            _release_t085_chunk_memory()


def _build_t085_cohort_b_source_manifest_from_paths_unlocked(
    *,
    pool_path: str | Path,
    pool_sha256: str,
    manifest_output_path: str | Path,
) -> dict[str, object]:
    """Finalize a merged complete Cohort-B assisted pool."""

    resolved_pool = _require_t085_stable_path(pool_path, "merged source pool")
    resolved_pool = resolved_pool.resolve(strict=True)
    if sha256_file(resolved_pool) != pool_sha256:
        raise T085NativeExecutionError(
            "T085 Cohort B merged source pool SHA-256 mismatch"
        )
    t042_anchor = _load_t085_t042_scale_manifest()
    native_identity = _validate_t085_native_source_manifest("battle_search")
    controller = build_t085_cohort_b_source_controller()
    with resolved_pool.open(encoding="utf-8") as stream:
        try:
            artifact = load_assisted_source_pool_jsonl(stream)
        except (OSError, ValueError) as exc:
            raise T085NativeExecutionError(
                "T085 Cohort B merged assisted source pool is invalid"
            ) from exc
    expected_seeds = tuple(range(T085_COHORT_B_SEED_START, T085_COHORT_B_SEED_END + 1))
    _validate_t085_b_source_pool(
        artifact,
        controller=controller,
        expected_seeds=expected_seeds,
    )
    if artifact.pool.source_run_count != T085_COHORT_B_RUN_COUNT:
        raise T085NativeExecutionError(
            "T085 Cohort B source manifest requires all 1024 source runs"
        )
    representatives = _t085_b_source_run_representatives(
        artifact.records,
        artifact.pool.source_run_summaries,
    )
    pool_reference = _t085_assisted_source_pool_reference(
        resolved_pool,
        record_count=len(artifact.records),
        source_run_count=artifact.pool.source_run_count,
    )
    manifest_path = _require_t085_stable_path(
        manifest_output_path,
        "source manifest output",
    )
    source_run_summaries = artifact.pool.source_run_summaries
    source_run_inventory = _t085_b_source_run_inventory(
        source_run_summaries,
        representatives,
    )
    manifest = {
        "schema_id": T085_SOURCE_MANIFEST_SCHEMA_ID,
        "task_id": "T085",
        "cohort": "B",
        "ascension": 20,
        "max_outer_steps": 500,
        "action_space": "initial_no_potions",
        "battle_controller": "oracle_search",
        "battle_simulations": 20,
        "root_selection": "highest_mean",
        "non_combat_controller": "expert_non_combat_v1",
        "non_combat_policy_seed": 42042,
        "assistance_level": "assist_hp75_potion",
        "assistance_policy_seed": 42042,
        "policy_prior_callback": None,
        "leaf_value_callback": None,
        "native_identity": native_identity,
        "t042_scale_manifest": t042_anchor,
        "t042_scale_manifest_sha256": T085_T042_SCALE_MANIFEST_SHA256,
        "source_outcome_independent": True,
        "repaired_checkpoint_used": False,
        "source_manifest_frozen": True,
        "source_run_count": T085_COHORT_B_RUN_COUNT,
        "source_run_seeds": list(expected_seeds),
        "source_run_seed_inventory": [
            summary.source_seed for summary in source_run_summaries
        ],
        "source_run_identity_inventory": [
            summary.source_run_id for summary in source_run_summaries
        ],
        "complete_source_identity_inventory": [
            record.source_checkpoint_id if record is not None else None
            for record in representatives
        ],
        "source_run_inventory": source_run_inventory,
        "source_pool_artifact": pool_reference,
        "source_controller_provenance": artifact.pool.source_controller_provenance,
        "source_pool_merge": {
            "merge_version": ASSISTED_SOURCE_POOL_MERGE_VERSION,
            "shard_count": len(getattr(artifact, "source_shards", ())),
            "source_shards": [
                dict(shard) for shard in getattr(artifact, "source_shards", ())
            ],
        },
        "selection_rule": (
            "sha256(source_run_identity:complete_source_identity) per source run"
        ),
        "one_record_per_source_run": True,
        "source_pool_complete": True,
        "terminal_run_count": artifact.pool.terminal_run_count,
        "truncated_run_count": artifact.pool.truncated_run_count,
    }
    if manifest["source_run_seed_inventory"] != list(expected_seeds):
        raise T085NativeExecutionError(
            "T085 Cohort B merged source summary seed order is not exact"
        )
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    reference = _write_t085_json_artifact_atomically(
        manifest_path,
        manifest,
        schema_id=T085_SOURCE_MANIFEST_SCHEMA_ID,
    )
    bound_manifest = dict(manifest)
    bound_manifest.update(
        {
            "source_manifest_path": reference["path"],
            "source_manifest_sha256": reference["sha256"],
            "source_manifest_byte_count": reference["byte_count"],
        }
    )
    validate_t085_source_generation_contract(bound_manifest, cohort="B")
    return bound_manifest


def run_t085_cohort_c_source_generation_from_paths(
    *,
    adapter_factory: Callable[[], object],
    pool_output_path: str | Path,
    shard_manifest_output_path: str | Path,
    shard_index: int,
    shard_count: int = 16,
    worker_count: int = 16,
) -> dict[str, object]:
    """Run one exact eight-seed Cohort-C source-generation shard.

    The source pool is a current ``battle-start-pool`` JSONL artifact and is
    therefore directly consumable by :func:`resolve_t085_canonical_records`
    after all 16 shards are merged.  This function intentionally emits a
    partial shard manifest; it cannot claim the 128-run source contract until
    the deterministic merge/finalization step has been completed.
    """

    if not callable(adapter_factory):
        raise T085NativeExecutionError(
            "T085 Cohort C source generation requires an adapter factory"
        )
    plan = T085CohortCSourceGenerationPlan(
        shard_index=shard_index,
        shard_count=shard_count,
        worker_count=worker_count,
    )
    native_identity = _validate_t085_native_source_manifest("battle_search_v2")
    controller = build_t085_cohort_c_source_controller()
    pool = collect_natural_battle_start_pool(
        adapter_factory(),
        controller,
        seeds=plan.seed_inventory,
        max_steps=500,
        action_space=ActionSpaceConfig.initial_no_potions(),
    )
    _validate_t085_c_source_pool(
        pool,
        controller=controller,
        expected_seeds=plan.seed_inventory,
    )
    pool_path = _require_t085_stable_path(pool_output_path, "source pool output")
    manifest_path = _require_t085_stable_path(
        shard_manifest_output_path,
        "source shard manifest output",
    )
    pool_path.parent.mkdir(parents=True, exist_ok=True)
    with pool_path.open("w", encoding="utf-8", newline="\n") as stream:
        dump_natural_battle_start_pool_jsonl(pool, stream)
    representatives = _t085_source_run_representatives(
        pool.records,
        pool.source_run_summaries,
        cohort="C",
    )
    source_pool_reference = _t085_source_pool_reference(
        pool_path,
        record_count=len(pool.records),
        source_run_count=pool.source_run_count,
    )
    manifest = plan.to_dict(native_identity=native_identity)
    manifest.update(
        {
            "source_pool_artifact": source_pool_reference,
            "source_run_seed_inventory": [
                summary.source_seed for summary in pool.source_run_summaries
            ],
            "source_run_identity_inventory": [
                summary.source_run_id for summary in pool.source_run_summaries
            ],
            "complete_source_identity_inventory": [
                record.source_checkpoint_id for record in representatives
            ],
            "record_count": len(pool.records),
            "source_controller_provenance": pool.source_controller_provenance,
        }
    )
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_reference = write_t085_json_artifact(
        manifest_path,
        manifest,
        schema_id=T085_C_SOURCE_SHARD_MANIFEST_SCHEMA_ID,
    )
    return {
        "status": "partial",
        "task_id": "T085",
        "cohort": "C",
        "source_generation_valid": True,
        "pool_artifact": source_pool_reference,
        "source_shard_manifest": manifest_reference,
        "shard": manifest,
    }


def _validate_t085_c_shard_manifest(
    manifest_path: Path,
    *,
    pool_path: Path,
    plan: T085CohortCSourceGenerationPlan,
    native_identity: Mapping[str, object],
    controller: RoutedRunController,
) -> dict[str, object]:
    """Validate one C source shard before the repository-owned merge."""

    try:
        document = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise T085NativeExecutionError(
            f"T085 Cohort C source shard manifest is unavailable: {manifest_path}"
        ) from exc
    if not isinstance(document, Mapping):
        raise T085NativeExecutionError(
            "T085 Cohort C source shard manifest is not an object"
        )
    if (
        document.get("schema_id") != T085_C_SOURCE_SHARD_MANIFEST_SCHEMA_ID
        or document.get("task_id") != "T085"
        or document.get("cohort") != "C"
        or document.get("artifact_scope") != "source_generation_shard"
        or document.get("partial") is not True
        or document.get("complete") is not False
        or document.get("shard_count") != 16
        or document.get("worker_count") != 16
        or document.get("effective_worker_count") != 16
        or document.get("partition_scheme") != "contiguous_seed_ranges"
        or document.get("shard_index") != plan.shard_index
    ):
        raise T085NativeExecutionError(
            "T085 Cohort C source shard manifest has the wrong shard contract"
        )
    expected_seed_inventory = list(plan.seed_inventory)
    if (
        document.get("shard_source_run_count") != len(expected_seed_inventory)
        or document.get("shard_source_run_seed_start") != expected_seed_inventory[0]
        or document.get("shard_source_run_seed_end") != expected_seed_inventory[-1]
        or document.get("shard_source_run_seed_inventory") != expected_seed_inventory
        or document.get("source_run_seed_inventory") != expected_seed_inventory
    ):
        raise T085NativeExecutionError(
            "T085 Cohort C source shard manifest seed inventory is not exact"
        )
    expected_configuration = {
        "source_run_seed_start": T085_COHORT_C_SEED_START,
        "source_run_seed_end": T085_COHORT_C_SEED_END,
        "source_run_count": T085_COHORT_C_RUN_COUNT,
        "max_outer_steps": 500,
        "action_space": "initial_no_potions",
        "battle_controller": "unguided_search_v2",
        "battle_simulations": 100,
        "root_selection": "highest_mean",
        "non_combat_controller": "expert_non_combat_v1",
        "non_combat_policy_seed": 42042,
        "assistance_level": "assist_0",
        "assistance_policy_seed": None,
        "policy_prior_callback": None,
        "leaf_value_callback": None,
    }
    if any(
        document.get(key) != expected
        for key, expected in expected_configuration.items()
    ):
        raise T085NativeExecutionError(
            "T085 Cohort C source shard manifest configuration is not exact"
        )
    if document.get("native_identity") != dict(native_identity):
        raise T085NativeExecutionError(
            "T085 Cohort C source shard manifest native identity mismatch"
        )
    source_pool_reference = document.get("source_pool_artifact")
    if not isinstance(source_pool_reference, Mapping):
        raise T085NativeExecutionError(
            "T085 Cohort C source shard lacks source pool binding"
        )
    try:
        pool_sha256 = sha256_file(pool_path)
        pool_size = pool_path.stat().st_size
    except OSError as exc:
        raise T085NativeExecutionError(
            "T085 Cohort C source shard pool is unavailable"
        ) from exc
    if (
        Path(str(source_pool_reference.get("path"))).resolve() != pool_path.resolve()
        or source_pool_reference.get("schema_id") != T085_C_SOURCE_POOL_SCHEMA_ID
        or source_pool_reference.get("sha256") != pool_sha256
        or source_pool_reference.get("byte_count") != pool_size
        or source_pool_reference.get("format_version")
        != BATTLE_START_POOL_FORMAT_VERSION
        or source_pool_reference.get("distribution_kind") != "natural_run"
    ):
        raise T085NativeExecutionError(
            "T085 Cohort C source shard is not bound to its natural pool"
        )
    try:
        with pool_path.open(encoding="utf-8") as stream:
            pool = load_natural_battle_start_pool_jsonl(stream)
    except (OSError, ValueError) as exc:
        raise T085NativeExecutionError(
            "T085 Cohort C source shard pool is invalid"
        ) from exc
    _validate_t085_c_source_pool(
        pool,
        controller=controller,
        expected_seeds=plan.seed_inventory,
    )
    if (
        source_pool_reference.get("record_count") != len(pool.records)
        or source_pool_reference.get("source_run_count") != pool.source_run_count
        or document.get("record_count") != len(pool.records)
        or document.get("terminal_run_count") != pool.terminal_run_count
        or document.get("truncated_run_count") != pool.truncated_run_count
    ):
        raise T085NativeExecutionError(
            "T085 Cohort C source shard manifest counts are not bound to its pool"
        )
    representatives = _t085_source_run_representatives(
        pool.records,
        pool.source_run_summaries,
        cohort="C",
    )
    if document.get("complete_source_identity_inventory") != [
        record.source_checkpoint_id for record in representatives
    ]:
        raise T085NativeExecutionError(
            "T085 Cohort C source shard complete-source inventory is not exact"
        )
    if document.get("source_run_identity_inventory") != [
        summary.source_run_id for summary in pool.source_run_summaries
    ]:
        raise T085NativeExecutionError(
            "T085 Cohort C source shard run identity inventory is not exact"
        )
    if (
        document.get("source_controller_provenance")
        != pool.source_controller_provenance
    ):
        raise T085NativeExecutionError(
            "T085 Cohort C source shard controller provenance is not exact"
        )
    return dict(document)


def merge_t085_cohort_c_source_pool_from_paths(
    *,
    shard_paths: Sequence[str | Path],
    shard_manifest_paths: Sequence[str | Path],
    merged_pool_output_path: str | Path,
) -> dict[str, object]:
    """Merge exactly 16 verified C natural source shards."""

    if len(shard_paths) != 16 or len(shard_manifest_paths) != 16:
        raise T085NativeExecutionError(
            "T085 Cohort C source merge requires exactly 16 pools and 16 shard manifests"
        )
    native_identity = _validate_t085_native_source_manifest("battle_search_v2")
    controller = build_t085_cohort_c_source_controller()
    pairs: list[tuple[int, Path, Path, dict[str, object]]] = []
    for pool_path_raw, manifest_path_raw in zip(
        shard_paths, shard_manifest_paths, strict=True
    ):
        pool_path = _require_t085_stable_path(pool_path_raw, "source shard pool")
        manifest_path = _require_t085_stable_path(
            manifest_path_raw,
            "source shard manifest",
        )
        try:
            raw_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise T085NativeExecutionError(
                f"T085 Cohort C source shard manifest is unavailable: {manifest_path}"
            ) from exc
        raw_shard_index = (
            raw_manifest.get("shard_index")
            if isinstance(raw_manifest, Mapping)
            else None
        )
        if isinstance(raw_shard_index, bool) or not isinstance(raw_shard_index, int):
            raise T085NativeExecutionError(
                "T085 Cohort C source shard index is invalid"
            )
        manifest = _validate_t085_c_shard_manifest(
            manifest_path,
            pool_path=pool_path,
            plan=T085CohortCSourceGenerationPlan(shard_index=raw_shard_index),
            native_identity=native_identity,
            controller=controller,
        )
        pairs.append((raw_shard_index, pool_path, manifest_path, manifest))
    if {item[0] for item in pairs} != set(range(16)):
        raise T085NativeExecutionError(
            "T085 Cohort C source merge must cover every shard index 0..15 exactly once"
        )
    pairs.sort(key=lambda item: item[0])
    for expected_index, (_, pool_path, manifest_path, _manifest) in enumerate(pairs):
        _validate_t085_c_shard_manifest(
            manifest_path,
            pool_path=pool_path,
            plan=T085CohortCSourceGenerationPlan(shard_index=expected_index),
            native_identity=native_identity,
            controller=controller,
        )
    merged_path = _require_t085_stable_path(
        merged_pool_output_path,
        "merged Cohort C source pool output",
    )
    merged_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with merged_path.open("w", encoding="utf-8", newline="\n") as stream:
            merge_summary = dump_merged_natural_battle_start_pool_shards_jsonl(
                [item[1] for item in pairs],
                stream,
            )
        with merged_path.open(encoding="utf-8") as stream:
            merged_pool = load_natural_battle_start_pool_jsonl(stream)
    except (OSError, ValueError) as exc:
        raise T085NativeExecutionError(
            "T085 Cohort C source shard merge failed"
        ) from exc
    _validate_t085_c_source_pool(
        merged_pool,
        controller=controller,
        expected_seeds=tuple(
            range(T085_COHORT_C_SEED_START, T085_COHORT_C_SEED_END + 1)
        ),
    )
    if (
        merged_pool.source_run_count != T085_COHORT_C_RUN_COUNT
        or merged_pool.terminal_run_count != T085_COHORT_C_RUN_COUNT
        or merged_pool.truncated_run_count != 0
    ):
        raise T085NativeExecutionError(
            "T085 Cohort C merged source pool is not the complete 128-run pool"
        )
    output_reference = _t085_source_pool_reference(
        merged_path,
        record_count=len(merged_pool.records),
        source_run_count=merged_pool.source_run_count,
    )
    return {
        "status": "merged",
        "task_id": "T085",
        "cohort": "C",
        "source_generation_valid": True,
        "artifact_scope": "source_generation_merge",
        "partial": True,
        "complete": False,
        "native_identity": native_identity,
        "pool_artifact": output_reference,
        "source_shards": [item[3] for item in pairs],
        "merge_summary": {
            "schema_id": merge_summary.schema_id,
            "merge_version": merge_summary.merge_version,
            "source_shards": [dict(item) for item in merge_summary.source_shards],
            "source_run_count": merge_summary.source_run_count,
            "terminal_run_count": merge_summary.terminal_run_count,
            "truncated_run_count": merge_summary.truncated_run_count,
            "record_count": merge_summary.record_count,
        },
    }


def build_t085_cohort_c_source_manifest_from_paths(
    *,
    pool_path: str | Path,
    pool_sha256: str,
    manifest_output_path: str | Path,
) -> dict[str, object]:
    """Finalize a merged 128-run Cohort-C pool into T085 source evidence."""

    resolved_pool = _require_t085_stable_path(pool_path, "merged source pool")
    resolved_pool = resolved_pool.resolve(strict=True)
    if sha256_file(resolved_pool) != pool_sha256:
        raise T085NativeExecutionError(
            "T085 Cohort C merged source pool SHA-256 mismatch"
        )
    with resolved_pool.open(encoding="utf-8") as stream:
        pool = load_natural_battle_start_pool_jsonl(stream)
    source_pool_merge = _validate_t085_c_merged_source_metadata(
        resolved_pool,
        pool,
    )
    expected_seeds = tuple(range(T085_COHORT_C_SEED_START, T085_COHORT_C_SEED_END + 1))
    controller = build_t085_cohort_c_source_controller()
    _validate_t085_c_source_pool(
        pool,
        controller=controller,
        expected_seeds=expected_seeds,
    )
    if pool.source_run_count != T085_COHORT_C_RUN_COUNT:
        raise T085NativeExecutionError(
            "T085 Cohort C source manifest requires all 128 source runs"
        )
    by_run: dict[str, list[BattleStartCheckpointRecord]] = {}
    for record in pool.records:
        by_run.setdefault(record.source_run_id, []).append(record)
    selected_by_run: list[BattleStartCheckpointRecord] = []
    for summary in pool.source_run_summaries:
        candidates = by_run.get(summary.source_run_id, [])
        if not candidates:
            raise T085NativeExecutionError(
                "T085 Cohort C source manifest cannot bind a run without a battle start"
            )
        selected_by_run.append(
            min(
                candidates,
                key=_t085_cohort_c_selection_rank,
            )
        )
    complete_ids = [record.source_checkpoint_id for record in selected_by_run]
    if len(set(complete_ids)) != T085_COHORT_C_RUN_COUNT:
        raise T085NativeExecutionError(
            "T085 Cohort C selected source identities are not unique"
        )
    pool_reference = _t085_source_pool_reference(
        resolved_pool,
        record_count=len(pool.records),
        source_run_count=pool.source_run_count,
    )
    native_identity = _validate_t085_native_source_manifest("battle_search_v2")
    manifest_path = _require_t085_stable_path(
        manifest_output_path,
        "source manifest output",
    )
    manifest = {
        "schema_id": T085_SOURCE_MANIFEST_SCHEMA_ID,
        "task_id": "T085",
        "cohort": "C",
        "ascension": 20,
        "max_outer_steps": 500,
        "action_space": "initial_no_potions",
        "battle_controller": "unguided_search_v2",
        "battle_simulations": 100,
        "root_selection": "highest_mean",
        "non_combat_controller": "expert_non_combat_v1",
        "non_combat_policy_seed": 42042,
        "assistance_level": "assist_0",
        "assistance_policy_seed": None,
        "policy_prior_callback": None,
        "leaf_value_callback": None,
        "native_identity": native_identity,
        "source_outcome_independent": True,
        "repaired_checkpoint_used": False,
        "source_manifest_frozen": True,
        "source_run_count": T085_COHORT_C_RUN_COUNT,
        "source_run_seeds": list(expected_seeds),
        "source_run_seed_inventory": [
            summary.source_seed for summary in pool.source_run_summaries
        ],
        "source_run_identity_inventory": [
            summary.source_run_id for summary in pool.source_run_summaries
        ],
        "complete_source_identity_inventory": complete_ids,
        "source_pool_artifact": pool_reference,
        "source_controller_provenance": pool.source_controller_provenance,
        "source_pool_merge": source_pool_merge,
        "selection_rule": (
            "sha256(source_run_identity:complete_source_identity) per source run"
        ),
        "one_record_per_source_run": True,
        "source_pool_complete": True,
        "terminal_run_count": pool.terminal_run_count,
        "truncated_run_count": pool.truncated_run_count,
    }
    if manifest["source_run_seed_inventory"] != list(expected_seeds):
        raise T085NativeExecutionError(
            "T085 Cohort C merged source summary seed order is not exact"
        )
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    reference = write_t085_json_artifact(
        manifest_path,
        manifest,
        schema_id=T085_SOURCE_MANIFEST_SCHEMA_ID,
    )
    bound_manifest = dict(manifest)
    bound_manifest.update(
        {
            "source_manifest_path": reference["path"],
            "source_manifest_sha256": reference["sha256"],
            "source_manifest_byte_count": reference["byte_count"],
        }
    )
    validate_t085_source_generation_contract(bound_manifest, cohort="C")
    return bound_manifest


def _validate_t085_source_manifest_binding(
    pool_path: Path,
    *,
    artifact_kind: T085NativeSourceArtifactKind,
    manifest_path: str | Path | None,
    manifest_sha256: str | None,
) -> tuple[dict[str, object], Path] | None:
    """Bind a source pool path to its frozen T085 source manifest."""

    if (manifest_path is None) != (manifest_sha256 is None):
        raise T085NativeExecutionError(
            "T085 source manifest path and SHA-256 must be supplied together"
        )
    if manifest_path is None:
        return None
    if artifact_kind == "fixed_cohort":
        raise T085NativeExecutionError(
            "fixed-cohort artifacts cannot carry a T085 source-generation manifest"
        )
    resolved_manifest = _require_t085_stable_path(
        manifest_path,
        "source-generation manifest",
    ).resolve(strict=True)
    actual_sha256 = sha256_file(resolved_manifest)
    if actual_sha256 != manifest_sha256:
        raise T085NativeExecutionError(
            "T085 source-generation manifest SHA-256 mismatch"
        )
    try:
        document = json.loads(resolved_manifest.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise T085NativeExecutionError(
            "T085 source-generation manifest is unavailable or invalid"
        ) from exc
    if not isinstance(document, Mapping):
        raise T085NativeExecutionError(
            "T085 source-generation manifest is not an object"
        )
    expected_cohort = "B" if artifact_kind == "assisted_pool" else "C"
    if (
        document.get("schema_id") != T085_SOURCE_MANIFEST_SCHEMA_ID
        or document.get("task_id") != "T085"
        or document.get("cohort") != expected_cohort
    ):
        raise T085NativeExecutionError(
            "T085 source-generation manifest schema/cohort identity is invalid"
        )
    source_pool = document.get("source_pool_artifact")
    if not isinstance(source_pool, Mapping):
        raise T085NativeExecutionError(
            "T085 source-generation manifest lacks source_pool_artifact binding"
        )
    expected_pool_schema_id = (
        ASSISTED_SOURCE_POOL_SCHEMA_ID
        if artifact_kind == "assisted_pool"
        else T085_C_SOURCE_POOL_SCHEMA_ID
    )
    expected_pool_format_version = (
        ASSISTED_SOURCE_POOL_FORMAT_VERSION
        if artifact_kind == "assisted_pool"
        else BATTLE_START_POOL_FORMAT_VERSION
    )
    if (
        Path(str(source_pool.get("path"))).resolve() != pool_path.resolve()
        or source_pool.get("schema_id") != expected_pool_schema_id
        or source_pool.get("sha256") != sha256_file(pool_path)
        or source_pool.get("byte_count") != pool_path.stat().st_size
        or source_pool.get("format_version") != expected_pool_format_version
        or (
            artifact_kind == "assisted_pool"
            and source_pool.get("source_pool_format_version")
            != BATTLE_START_POOL_FORMAT_VERSION
        )
        or source_pool.get("distribution_kind")
        != ("assisted_run" if artifact_kind == "assisted_pool" else "natural_run")
    ):
        raise T085NativeExecutionError(
            "T085 source-generation manifest is not bound to this source pool"
        )
    if artifact_kind == "natural_pool":
        expected_native_identity = _validate_t085_native_source_manifest(
            "battle_search_v2"
        )
        if document.get("native_identity") != expected_native_identity:
            raise T085NativeExecutionError(
                "T085 Cohort C source manifest has the wrong native identity"
            )
        if any(
            document.get(callback_name) is not None
            for callback_name in ("policy_prior_callback", "leaf_value_callback")
        ):
            raise T085NativeExecutionError(
                "T085 Cohort C source manifest must disable both Search guidance callbacks"
            )
    else:
        expected_native_identity = _validate_t085_native_source_manifest(
            "battle_search"
        )
        if document.get("native_identity") != expected_native_identity:
            raise T085NativeExecutionError(
                "T085 Cohort B source manifest has the wrong native identity"
            )
        if any(
            document.get(callback_name) is not None
            for callback_name in ("policy_prior_callback", "leaf_value_callback")
        ):
            raise T085NativeExecutionError(
                "T085 Cohort B source generation must disable Search guidance callbacks"
            )
        anchor = document.get("t042_scale_manifest")
        accepted_anchor = _load_t085_t042_scale_manifest()
        if (
            not isinstance(anchor, Mapping)
            or document.get("t042_scale_manifest_sha256")
            != T085_T042_SCALE_MANIFEST_SHA256
            or dict(anchor) != dict(accepted_anchor)
        ):
            raise T085NativeExecutionError(
                "T085 Cohort B source manifest is not bound to the accepted T042 anchor"
            )
    bound = dict(document)
    bound.update(
        {
            "source_manifest_path": str(resolved_manifest),
            "source_manifest_sha256": actual_sha256,
            "source_manifest_byte_count": resolved_manifest.stat().st_size,
        }
    )
    try:
        validate_t085_source_generation_contract(bound, cohort=expected_cohort)
    except T085EvaluationIntegrityError as exc:
        raise T085NativeExecutionError(
            "T085 source-generation manifest failed its frozen contract"
        ) from exc
    return bound, resolved_manifest


@dataclass(frozen=True)
class T085NativeArmController:
    """Repository-owned Search v2 selector for one explicit T085 arm."""

    arm: T085NativeArm
    simulations: int = 100
    action_space: ActionSpaceConfig = field(
        default_factory=ActionSpaceConfig.initial_no_potions
    )
    provenance: ControllerProvenance = field(init=False)  # type: ignore[assignment]

    def __post_init__(self) -> None:
        _positive_int(self.simulations, "T085 arm simulations")
        if (
            self.action_space.to_dict()
            != ActionSpaceConfig.initial_no_potions().to_dict()
        ):
            raise T085NativeExecutionError(
                "T085 arms require initial_no_potions action space"
            )
        _validate_t085_native_source_manifest("battle_search_v2")
        object.__setattr__(
            self,
            "provenance",
            ControllerProvenance(
                kind="t085_native_battle_search_v2",
                name=f"t085_{self.arm.name}_search_v2_s{self.simulations}",
                config={
                    **self.arm.provenance,
                    "search_budget": self.simulations,
                    "root_selection_rule": "highest_mean",
                    "action_space": self.action_space.to_dict(),
                },
            ),
        )

    def select_action(self, adapter, snapshot, actions, context, step_index):
        del step_index
        search = getattr(adapter, "battle_search_v2", None)
        if not callable(search):
            raise T085NativeExecutionError("T085 arm requires battle_search_v2")
        policy_callback = self.arm.policy_prior_callback
        leaf_callback = self.arm.leaf_value_callback
        if hasattr(policy_callback, "bind"):
            policy_callback = policy_callback.bind(context)
        if hasattr(leaf_callback, "bind"):
            leaf_callback = leaf_callback.bind(context)
        raw = search(
            snapshot,
            simulations=self.simulations,
            include_potions=False,
            policy_prior_callback=policy_callback,
            leaf_value_callback=leaf_callback,
        )
        if self.arm.name == "baseline":
            _validate_unguided_v2_telemetry(raw)
        report = build_oracle_search_report(
            raw,
            actions,
            context,
            expected_native_api=T085_NATIVE_V2_API,
            expected_patch_identity=T085_NATIVE_V2_PATCH,
        )
        if not report.search_ok:
            raise T085NativeExecutionError(
                "T085 arm root mapping failed: " + "; ".join(report.problems)
            )
        target = select_oracle_root_action(report, selection_rule="highest_mean")
        metadata = oracle_search_controller_metadata(report, target)
        metadata["t085_arm"] = self.arm.provenance
        return ControllerDecision(
            target.legal_action_index,
            self.provenance,
            f"t085:{self.arm.name}:highest_mean",
            target.score,
            metadata,
        )


@dataclass(frozen=True)
class T085NativeEvaluationPlan:
    """Validated A/B/C/Search@400 selection and restore/parity composition."""

    cohorts: Mapping[str, tuple[T085BattleStartRecord, ...]]
    selection_evidence: Mapping[str, Mapping[str, object]]
    native_identity: Mapping[str, object]

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_id": T085_NATIVE_SELECTION_SCHEMA_ID,
            "task_id": "T085",
            "native_identity": dict(self.native_identity),
            "cohorts": {
                cohort: [asdict(record) for record in records]
                for cohort, records in self.cohorts.items()
            },
            "selection_evidence": {
                cohort: dict(evidence)
                for cohort, evidence in self.selection_evidence.items()
            },
        }


def _coerce_battle_starts(
    records: Sequence[T085BattleStartRecord | Mapping[str, object]],
) -> tuple[T085BattleStartRecord, ...]:
    result: list[T085BattleStartRecord] = []
    for record in records:
        if isinstance(record, T085BattleStartRecord):
            result.append(record)
        elif isinstance(record, Mapping):
            result.append(T085BattleStartRecord.from_mapping(record))
        else:
            raise T085NativeExecutionError("T085 battle-start record is malformed")
    return tuple(result)


def _require_identity_inventory(values: Iterable[str], label: str) -> tuple[str, ...]:
    if isinstance(values, (str, bytes)):
        raise T085NativeExecutionError(f"{label} must be an identity inventory")
    inventory = tuple(values)
    if not inventory or any(
        not isinstance(value, str) or not value for value in inventory
    ):
        raise T085NativeExecutionError(f"{label} must be non-empty")
    if len(set(inventory)) != len(inventory):
        raise T085NativeExecutionError(f"{label} contains duplicate identities")
    return inventory


def build_t085_native_evaluation_plan(
    *,
    cohort_a_records: Sequence[T085BattleStartRecord | Mapping[str, object]],
    cohort_a_restore_results: Mapping[str, Mapping[str, object]],
    cohort_b_source_manifest: Mapping[str, object],
    cohort_b_source_runs: Sequence[T085SourceRunRecord | Mapping[str, object]],
    cohort_b_battle_starts: Sequence[T085BattleStartRecord | Mapping[str, object]],
    cohort_b_restore_results: Mapping[str, Mapping[str, object]],
    cohort_c_source_manifest: Mapping[str, object],
    cohort_c_source_runs: Sequence[T085SourceRunRecord | Mapping[str, object]],
    cohort_c_battle_starts: Sequence[T085BattleStartRecord | Mapping[str, object]],
    cohort_c_restore_results: Mapping[str, Mapping[str, object]],
    t084_complete_source_identities: Iterable[str],
    t052_complete_source_identities: Iterable[str],
) -> T085NativeEvaluationPlan:
    """Compose explicit native B/C source pools and restore/parity evidence."""

    native_identity = _validate_t085_native_source_manifest()
    t084_ids = _require_identity_inventory(
        t084_complete_source_identities,
        "T084 complete-source identity inventory",
    )
    t052_ids = _require_identity_inventory(
        t052_complete_source_identities,
        "T052 complete-source identity inventory",
    )
    cohort_a = _coerce_battle_starts(cohort_a_records)
    selected_b, evidence_b = build_t085_cohort_selection(
        cohort="B",
        source_manifest=cohort_b_source_manifest,
        source_runs=cohort_b_source_runs,
        battle_starts=cohort_b_battle_starts,
        restore_results=cohort_b_restore_results,
        t084_complete_source_identities=t084_ids,
        t052_complete_source_identities=t052_ids,
    )
    selected_c, evidence_c = build_t085_cohort_selection(
        cohort="C",
        source_manifest=cohort_c_source_manifest,
        source_runs=cohort_c_source_runs,
        battle_starts=cohort_c_battle_starts,
        restore_results=cohort_c_restore_results,
    )
    selected_400, _ = select_search_400_subset(selected_b)
    selection_evidence = build_t085_evaluation_selection_evidence(
        cohort_a_records=cohort_a,
        cohort_a_restore_results=cohort_a_restore_results,
        cohort_b_records=selected_b,
        cohort_b_selection_evidence=evidence_b,
        cohort_c_records=selected_c,
        cohort_c_selection_evidence=evidence_c,
        search_400_records=selected_400,
    )
    cohorts = {
        "A": cohort_a,
        "B": selected_b,
        "C": selected_c,
        "B@400": selected_400,
    }
    validate_t085_evaluation_selection_evidence(cohorts, selection_evidence)
    return T085NativeEvaluationPlan(
        cohorts=cohorts,
        selection_evidence=selection_evidence,
        native_identity=native_identity,
    )


def _validate_plan(plan: T085NativeEvaluationPlan) -> None:
    if not isinstance(plan, T085NativeEvaluationPlan):
        raise T085NativeExecutionError("T085 native evaluation plan is malformed")
    expected = {"A", "B", "C", "B@400"}
    if set(plan.cohorts) != expected or set(plan.selection_evidence) != expected:
        raise T085NativeExecutionError(
            "T085 native evaluation plan must cover A, B, C, and B@400"
        )
    actual_identity = _validate_t085_native_source_manifest()
    if dict(plan.native_identity) != actual_identity:
        raise T085NativeExecutionError(
            "T085 native evaluation plan has the wrong native identity"
        )
    validate_t085_evaluation_selection_evidence(
        plan.cohorts,
        plan.selection_evidence,
    )


def write_t085_native_selection_artifact(
    plan: T085NativeEvaluationPlan,
    path: str | Path,
) -> dict[str, object]:
    """Retain the validated source/selection/parity composition."""

    _validate_plan(plan)
    return write_t085_json_artifact(
        path,
        plan.to_dict(),
        schema_id=T085_NATIVE_SELECTION_SCHEMA_ID,
    )


def _t085_required_sha256(value: object, label: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise T085NativeExecutionError(f"{label} must be a SHA-256 hex digest")
    return value


def _sha256_json(value: object) -> str:
    return sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _t085_required_string_list(value: object, label: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not value:
        raise T085NativeExecutionError(f"{label} must be a non-empty list")
    result = tuple(value)
    if any(not isinstance(item, str) or not item for item in result):
        raise T085NativeExecutionError(f"{label} must contain non-empty strings")
    if len(set(result)) != len(result):
        raise T085NativeExecutionError(f"{label} contains duplicate identities")
    return result


def _t085_path_reference(
    path: str | Path,
    *,
    schema_id: str,
    expected_sha256: str | None = None,
) -> dict[str, object]:
    resolved = Path(path).resolve(strict=True)
    digest = sha256_file(resolved)
    if expected_sha256 is not None and digest != expected_sha256:
        raise T085NativeExecutionError(
            f"T085 path-bound artifact hash mismatch: {resolved}"
        )
    return {
        "path": str(resolved),
        "schema_id": schema_id,
        "sha256": digest,
        "byte_count": resolved.stat().st_size,
    }


def _t085_validate_path_reference(
    raw: object,
    label: str,
    *,
    expected_schema_id: str | None = None,
    require_stable_root: bool = False,
) -> dict[str, object]:
    if not isinstance(raw, Mapping):
        raise T085NativeExecutionError(f"{label} must be an artifact reference")
    path_value = raw.get("path")
    if not isinstance(path_value, str) or not path_value:
        raise T085NativeExecutionError(f"{label}.path is missing")
    path = Path(path_value).resolve()
    if require_stable_root:
        _require_t085_stable_path(path, label)
    schema_id = raw.get("schema_id")
    if expected_schema_id is not None and schema_id != expected_schema_id:
        raise T085NativeExecutionError(f"{label}.schema_id is not current")
    if not isinstance(schema_id, str) or not schema_id:
        raise T085NativeExecutionError(f"{label}.schema_id is missing")
    digest = _t085_required_sha256(raw.get("sha256"), f"{label}.sha256")
    byte_count = raw.get("byte_count")
    if (
        isinstance(byte_count, bool)
        or not isinstance(byte_count, int)
        or byte_count <= 0
    ):
        raise T085NativeExecutionError(f"{label}.byte_count must be positive")
    if not path.is_file() or path.stat().st_size != byte_count:
        raise T085NativeExecutionError(f"{label} is unavailable or changed size")
    if sha256_file(path) != digest:
        raise T085NativeExecutionError(f"{label} hash changed")
    return {
        "path": str(path),
        "schema_id": schema_id,
        "sha256": digest,
        "byte_count": byte_count,
    }


def _load_t085_native_selection_input(
    path: str | Path,
    *,
    expected_sha256: str,
) -> tuple[dict[str, object], tuple[str, ...], tuple[str, ...]]:
    """Load the path-bound, outcome-blind identity input for native selection.

    The regular T085 input-eligibility manifest proves the accepted T084/T064
    lineage, but it intentionally does not materialize the complete source-run
    identity inventory needed by the B overlap gate.  This small companion
    artifact is therefore explicit: its T084 inventory must come from the
    retained upstream source-identity index, while its T052 inventory is
    rechecked against the accepted fixed cohort below.  No battle outcome,
    terminal HP, or model output is consumed here.
    """

    resolved = _require_t085_stable_path(path, "selection input")
    resolved = resolved.resolve(strict=True)
    actual_sha256 = sha256_file(resolved)
    if actual_sha256 != _t085_required_sha256(expected_sha256, "selection input SHA"):
        raise T085NativeExecutionError("T085 selection input SHA-256 mismatch")
    try:
        payload = json.loads(resolved.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise T085NativeExecutionError(
            "T085 selection input is unavailable or invalid"
        ) from exc
    if not isinstance(payload, Mapping):
        raise T085NativeExecutionError("T085 selection input is not an object")
    if (
        payload.get("schema_id") != T085_NATIVE_SELECTION_INPUT_SCHEMA_ID
        or payload.get("task_id") != "T085"
        or dict(payload.get("native_identity", {})) != T085_NATIVE_IDENTITY
    ):
        raise T085NativeExecutionError(
            "T085 selection input schema/task/native identity is invalid"
        )
    accepted_inputs = payload.get("accepted_inputs")
    if not isinstance(accepted_inputs, Mapping) or dict(accepted_inputs) != dict(
        T085_INPUT_ARTIFACT_IDENTITIES
    ):
        raise T085NativeExecutionError(
            "T085 selection input is not bound to the accepted input identities"
        )
    raw_inventories = payload.get("complete_source_identity_inventories")
    if not isinstance(raw_inventories, Mapping) or set(raw_inventories) != {
        "T084",
        "T052",
    }:
        raise T085NativeExecutionError(
            "T085 selection input must contain exact T084 and T052 inventories"
        )
    t084_ids = _t085_required_string_list(
        raw_inventories.get("T084"),
        "selection input T084 inventory",
    )
    t052_ids = _t085_required_string_list(
        raw_inventories.get("T052"),
        "selection input T052 inventory",
    )
    provenance = payload.get("identity_inventory_provenance")
    if not isinstance(provenance, Mapping) or set(provenance) != {"T084", "T052"}:
        raise T085NativeExecutionError(
            "T085 selection input lacks identity inventory provenance"
        )
    for lineage in ("T084", "T052"):
        entry = provenance.get(lineage)
        if not isinstance(entry, Mapping):
            raise T085NativeExecutionError(
                f"T085 selection input {lineage} identity provenance is malformed"
            )
        if entry.get("source_role") != "complete_source_identity_inventory":
            raise T085NativeExecutionError(
                f"T085 selection input {lineage} identity source role is invalid"
            )
        _t085_validate_path_reference(
            entry.get("artifact"),
            f"selection input identity provenance {lineage}",
        )
    source_artifacts = payload.get("source_artifacts")
    if not isinstance(source_artifacts, Mapping) or set(source_artifacts) != {
        "A",
        "B",
        "C",
    }:
        raise T085NativeExecutionError(
            "T085 selection input must bind A, B, and C source artifacts"
        )
    return (
        {
            "path": str(resolved),
            "schema_id": T085_NATIVE_SELECTION_INPUT_SCHEMA_ID,
            "sha256": actual_sha256,
            "byte_count": resolved.stat().st_size,
            "source_artifacts": {
                str(key): dict(value)
                for key, value in source_artifacts.items()
                if isinstance(value, Mapping)
            },
        },
        t084_ids,
        t052_ids,
    )


def _t085_canonical_to_battle_start(
    canonical: BattleStartCheckpointRecord,
) -> T085BattleStartRecord:
    """Project only public identity/structure from a full restore record."""

    structural = canonical.structural_metadata
    act = structural.get("act")
    room_type = structural.get("room_type")
    if isinstance(act, bool) or not isinstance(act, int) or act <= 0:
        raise T085NativeExecutionError(
            f"T085 canonical record {canonical.source_checkpoint_id} has invalid act"
        )
    if not isinstance(room_type, str) or not room_type:
        raise T085NativeExecutionError(
            f"T085 canonical record {canonical.source_checkpoint_id} has invalid room type"
        )
    # ``restore_ok`` denotes that the retained source record is a candidate;
    # fresh restore/parity evidence is produced separately by the shard runner.
    # Public-context availability is a structural eligibility gate, never an
    # outcome gate.
    return T085BattleStartRecord(
        source_run_seed=canonical.source_seed,
        source_run_identity=canonical.source_run_id,
        complete_source_identity=canonical.source_checkpoint_id,
        battle_identity=f"{canonical.source_run_id}:{canonical.source_battle_index}",
        act=act,
        room_type=room_type.upper(),
        restore_ok=True,
        public_context_match=canonical.public_context_status
        == PUBLIC_CONTEXT_AVAILABLE,
        source_valid=True,
        failure_reason=None,
        source_artifact_record_identity=canonical.source_checkpoint_id,
    )


@dataclass(frozen=True)
class _T085SelectionRestoreInputs:
    input_reference: Mapping[str, object]
    source_bindings: Mapping[str, Mapping[str, object]]
    source_manifests: Mapping[str, Mapping[str, object]]
    canonical_records_by_cohort: Mapping[str, Mapping[str, BattleStartCheckpointRecord]]
    source_runs: Mapping[str, tuple[T085SourceRunRecord, ...]]
    battle_starts: Mapping[str, tuple[T085BattleStartRecord, ...]]
    selected: Mapping[str, tuple[T085BattleStartRecord, ...]]
    t084_complete_source_identities: tuple[str, ...]
    t052_complete_source_identities: tuple[str, ...]
    selection_identity_sha256: str


def _t085_selection_source_binding(
    input_sources: Mapping[str, object],
    cohort: str,
    *,
    map_path: str | Path,
    map_sha256: str,
    map_schema_id: str,
    manifest_path: str | Path | None = None,
    manifest_sha256: str | None = None,
) -> dict[str, object]:
    raw = input_sources.get(cohort)
    if not isinstance(raw, Mapping):
        raise T085NativeExecutionError(
            f"T085 selection input lacks {cohort} source binding"
        )
    supplied_map = _t085_validate_path_reference(
        raw.get("map"),
        f"selection input source {cohort}.map",
        expected_schema_id=map_schema_id,
    )
    actual_map = _t085_path_reference(
        map_path,
        schema_id=map_schema_id,
        expected_sha256=map_sha256,
    )
    if supplied_map != actual_map:
        raise T085NativeExecutionError(
            f"T085 {cohort} source map is not the map bound by selection input"
        )
    binding: dict[str, object] = {"map": actual_map}
    if manifest_path is None or manifest_sha256 is None:
        if raw.get("source_manifest") is not None:
            raise T085NativeExecutionError(
                f"T085 {cohort} selection binding unexpectedly carries a source manifest"
            )
    else:
        supplied_manifest = _t085_validate_path_reference(
            raw.get("source_manifest"),
            f"selection input source {cohort}.source_manifest",
            expected_schema_id=T085_SOURCE_MANIFEST_SCHEMA_ID,
            require_stable_root=True,
        )
        actual_manifest = _t085_path_reference(
            manifest_path,
            schema_id=T085_SOURCE_MANIFEST_SCHEMA_ID,
            expected_sha256=manifest_sha256,
        )
        if supplied_manifest != actual_manifest:
            raise T085NativeExecutionError(
                f"T085 {cohort} source manifest is not the manifest bound by selection input"
            )
        binding["source_manifest"] = actual_manifest
    return binding


def _t085_load_frozen_source_manifest_and_map(
    *,
    cohort: Literal["B", "C"],
    map_path: str | Path,
    map_sha256: str,
    manifest_path: str | Path,
    manifest_sha256: str,
) -> tuple[
    dict[str, object],
    dict[str, BattleStartCheckpointRecord],
    tuple[T085SourceRunRecord, ...],
    tuple[T085BattleStartRecord, ...],
]:
    artifact_kind: Literal["assisted_pool", "natural_pool"] = (
        "assisted_pool" if cohort == "B" else "natural_pool"
    )
    bound, resolved_manifest = _validate_t085_source_manifest_binding(
        Path(map_path).resolve(strict=True),
        artifact_kind=artifact_kind,
        manifest_path=manifest_path,
        manifest_sha256=manifest_sha256,
    ) or (None, None)
    if bound is None or resolved_manifest is None:
        raise T085NativeExecutionError(
            f"T085 Cohort {cohort} source manifest binding is missing"
        )
    manifest = dict(bound)
    try:
        validate_t085_source_generation_contract(manifest, cohort=cohort)
    except T085EvaluationIntegrityError as exc:
        raise T085NativeExecutionError(
            f"T085 Cohort {cohort} source manifest contract is invalid"
        ) from exc
    if manifest.get("source_pool_complete") is not True:
        raise T085NativeExecutionError(
            f"T085 Cohort {cohort} source manifest is not finalized"
        )
    source_count = T085_COHORT_B_RUN_COUNT if cohort == "B" else T085_COHORT_C_RUN_COUNT
    expected_seeds = tuple(
        range(
            T085_COHORT_B_SEED_START if cohort == "B" else T085_COHORT_C_SEED_START,
            (T085_COHORT_B_SEED_END if cohort == "B" else T085_COHORT_C_SEED_END) + 1,
        )
    )
    raw_seeds = manifest.get("source_run_seed_inventory")
    raw_run_ids = manifest.get("source_run_identity_inventory")
    raw_complete_ids = manifest.get("complete_source_identity_inventory")
    if raw_seeds != list(expected_seeds) or not isinstance(raw_run_ids, list):
        raise T085NativeExecutionError(
            f"T085 Cohort {cohort} source manifest seed/run inventory is not exact"
        )
    if not isinstance(raw_complete_ids, list):
        raise T085NativeExecutionError(
            f"T085 Cohort {cohort} source manifest complete inventory is missing"
        )
    if (
        len(raw_run_ids) != source_count
        or len(raw_complete_ids) != source_count
        or len(set(raw_run_ids)) != source_count
    ):
        raise T085NativeExecutionError(
            f"T085 Cohort {cohort} source manifest inventory count is invalid"
        )
    if cohort == "B":
        valid_complete_ids = [
            value for value in raw_complete_ids if isinstance(value, str)
        ]
        if (
            any(
                value is not None and not isinstance(value, str)
                for value in raw_complete_ids
            )
            or any(not value for value in valid_complete_ids)
            or len(set(valid_complete_ids)) != len(valid_complete_ids)
        ):
            raise T085NativeExecutionError(
                "T085 Cohort B source manifest complete identity inventory is invalid"
            )
        raw_run_inventory = manifest.get("source_run_inventory")
        if (
            not isinstance(raw_run_inventory, list)
            or len(raw_run_inventory) != source_count
        ):
            if any(value is None for value in raw_complete_ids):
                raise T085NativeExecutionError(
                    "T085 Cohort B invalid source runs lack source_run_inventory"
                )
            run_statuses = [(True, None)] * source_count
        else:
            run_statuses = [
                (entry["source_valid"], entry["failure_reason"])
                for entry in raw_run_inventory
                if isinstance(entry, Mapping)
            ]
            if len(run_statuses) != source_count:
                raise T085NativeExecutionError(
                    "T085 Cohort B source_run_inventory is malformed"
                )
    else:
        if (
            any(not isinstance(value, str) or not value for value in raw_complete_ids)
            or len(set(raw_complete_ids)) != source_count
        ):
            raise T085NativeExecutionError(
                f"T085 Cohort {cohort} source manifest complete identity inventory is invalid"
            )
        run_statuses = [(True, None)] * source_count
    canonical = resolve_t085_canonical_records(
        map_path,
        expected_sha256=map_sha256,
        artifact_kind=artifact_kind,
        expected_source_run_count=source_count,
        expected_source_run_identity_inventory=tuple(raw_run_ids),
        expected_source_run_seed_inventory=expected_seeds,
        expected_assistance_level=("assist_hp75_potion" if cohort == "B" else None),
        expected_source_manifest_path=resolved_manifest,
        expected_source_manifest_sha256=manifest_sha256,
    )
    source_runs: list[T085SourceRunRecord] = []
    battle_starts: list[T085BattleStartRecord] = []
    for index, (seed, run_id, complete_id) in enumerate(
        zip(
            expected_seeds,
            raw_run_ids,
            raw_complete_ids,
            strict=True,
        )
    ):
        source_valid, failure_reason = run_statuses[index]
        if not isinstance(run_id, str) or not run_id:
            raise T085NativeExecutionError(
                f"T085 Cohort {cohort} source manifest inventory contains invalid identities"
            )
        if not source_valid:
            source_runs.append(
                T085SourceRunRecord(
                    source_run_seed=seed,
                    source_run_identity=run_id,
                    complete_source_identity=None,
                    source_valid=False,
                    failure_reason=failure_reason,
                )
            )
            continue
        if not isinstance(complete_id, str) or not complete_id:
            raise T085NativeExecutionError(
                f"T085 Cohort {cohort} valid source run lacks complete identity"
            )
        record = canonical.get(complete_id)
        if record is None:
            raise T085NativeExecutionError(
                f"T085 Cohort {cohort} complete identity is absent from its full map: {complete_id}"
            )
        if record.source_run_id != run_id or record.source_seed != seed:
            raise T085NativeExecutionError(
                f"T085 Cohort {cohort} complete identity has mismatched run/seed: {complete_id}"
            )
        source_runs.append(
            T085SourceRunRecord(
                source_run_seed=seed,
                source_run_identity=run_id,
                complete_source_identity=complete_id,
            )
        )
        battle_starts.append(_t085_canonical_to_battle_start(record))
    if len(source_runs) != source_count or (
        cohort == "C" and len(battle_starts) != source_count
    ):
        raise T085NativeExecutionError(
            f"T085 Cohort {cohort} full source map does not cover all source runs"
        )
    return manifest, canonical, tuple(source_runs), tuple(battle_starts)


def _t085_prepare_selection_restore_inputs(
    *,
    selection_input_path: str | Path,
    selection_input_sha256: str,
    a_full_map_path: str | Path,
    b_full_map_path: str | Path,
    c_full_map_path: str | Path,
    a_sha256: str,
    b_sha256: str,
    c_sha256: str,
    b_source_manifest_path: str | Path,
    b_source_manifest_sha256: str,
    c_source_manifest_path: str | Path,
    c_source_manifest_sha256: str,
) -> _T085SelectionRestoreInputs:
    input_reference, t084_ids, input_t052_ids = _load_t085_native_selection_input(
        selection_input_path,
        expected_sha256=selection_input_sha256,
    )
    input_sources = input_reference.get("source_artifacts")
    if not isinstance(input_sources, Mapping):
        raise T085NativeExecutionError(
            "T085 selection input source bindings are missing"
        )
    a_map = resolve_t085_canonical_records(
        a_full_map_path,
        expected_sha256=a_sha256,
        artifact_kind="fixed_cohort",
    )
    a_binding = _t085_selection_source_binding(
        input_sources,
        "A",
        map_path=a_full_map_path,
        map_sha256=a_sha256,
        map_schema_id="fixed-cohort-v3-jsonl",
    )
    if tuple(a_map) != input_t052_ids:
        raise T085NativeExecutionError(
            "T085 selection input T052 inventory is not the exact A map inventory"
        )
    b_manifest, b_map, b_runs, b_starts = _t085_load_frozen_source_manifest_and_map(
        cohort="B",
        map_path=b_full_map_path,
        map_sha256=b_sha256,
        manifest_path=b_source_manifest_path,
        manifest_sha256=b_source_manifest_sha256,
    )
    b_binding = _t085_selection_source_binding(
        input_sources,
        "B",
        map_path=b_full_map_path,
        map_sha256=b_sha256,
        map_schema_id=ASSISTED_SOURCE_POOL_SCHEMA_ID,
        manifest_path=b_source_manifest_path,
        manifest_sha256=b_source_manifest_sha256,
    )
    c_manifest, c_map, c_runs, c_starts = _t085_load_frozen_source_manifest_and_map(
        cohort="C",
        map_path=c_full_map_path,
        map_sha256=c_sha256,
        manifest_path=c_source_manifest_path,
        manifest_sha256=c_source_manifest_sha256,
    )
    c_binding = _t085_selection_source_binding(
        input_sources,
        "C",
        map_path=c_full_map_path,
        map_sha256=c_sha256,
        map_schema_id=T085_C_SOURCE_POOL_SCHEMA_ID,
        manifest_path=c_source_manifest_path,
        manifest_sha256=c_source_manifest_sha256,
    )
    if a_sha256 != T085_T052_COHORT_SHA256:
        raise T085NativeExecutionError(
            "T085 A selection map must use the accepted T052 SHA-256"
        )
    if len(a_map) != 93:
        raise T085NativeExecutionError("T085 A selection map must contain 93 records")
    a_starts = tuple(
        _t085_canonical_to_battle_start(record) for record in a_map.values()
    )
    selected_b, _ = select_cohort_b(b_runs, b_starts)
    selected_c, _ = select_cohort_c(c_runs, c_starts)
    if len(selected_b) != T085_COHORT_B_SELECTED_COUNT:
        raise T085NativeExecutionError("T085 B selection did not produce 192 records")
    if len(selected_c) < T085_COHORT_C_MIN_SELECTED_COUNT:
        raise T085NativeExecutionError(
            "T085 C selection did not produce at least 96 records"
        )
    selected_400, _ = select_search_400_subset(selected_b)
    selected = {
        "A": a_starts,
        "B": selected_b,
        "C": selected_c,
        "B@400": selected_400,
    }
    selection_identity_sha256 = _sha256_json(
        {
            cohort: [record.selection_identity for record in records]
            for cohort, records in selected.items()
        }
    )
    return _T085SelectionRestoreInputs(
        input_reference=input_reference,
        source_bindings={"A": a_binding, "B": b_binding, "C": c_binding},
        source_manifests={"B": b_manifest, "C": c_manifest},
        canonical_records_by_cohort={"A": a_map, "B": b_map, "C": c_map},
        source_runs={"B": b_runs, "C": c_runs},
        battle_starts={"B": b_starts, "C": c_starts},
        selected=selected,
        t084_complete_source_identities=t084_ids,
        t052_complete_source_identities=tuple(a_map),
        selection_identity_sha256=selection_identity_sha256,
    )


def _t085_selection_shard_for(
    cohort: str,
    selection_identity: str,
    *,
    shard_count: int,
) -> int:
    return (
        int(
            sha256(f"{cohort}/{selection_identity}".encode()).hexdigest()[:8],
            16,
        )
        % shard_count
    )


def _t085_selection_unique_records(
    selected: Mapping[str, Sequence[T085BattleStartRecord]],
) -> tuple[tuple[str, T085BattleStartRecord], ...]:
    rows: list[tuple[str, T085BattleStartRecord]] = []
    seen: set[tuple[str, str]] = set()
    for cohort in ("A", "B", "C"):
        for record in selected[cohort]:
            key = (cohort, record.selection_identity)
            if key in seen:
                raise T085NativeExecutionError(
                    f"T085 selection contains duplicate restore identity {key}"
                )
            seen.add(key)
            rows.append((cohort, record))
    return tuple(rows)


def _t085_restore_selection_record(
    *,
    adapter_factory: Callable[[], object],
    cohort: str,
    record: T085BattleStartRecord,
    canonical_records: Mapping[str, BattleStartCheckpointRecord],
) -> dict[str, object]:
    """Restore on a fresh base adapter; no terminal search proxy is involved."""

    identity = record.selection_identity
    try:
        base_adapter = adapter_factory()
        restored = restore_t085_canonical_record(
            base_adapter,
            record,
            canonical_records,
        )
        if not isinstance(restored, tuple) or len(restored) != 2:
            raise T085NativeExecutionError(
                "T085 canonical restore did not return (snapshot, method)"
            )
        snapshot, method = restored
        if not isinstance(snapshot, SimulatorSnapshot) or not isinstance(method, str):
            raise T085NativeExecutionError(
                "T085 canonical restore returned an invalid snapshot/method"
            )
        fingerprint = sha256(
            json.dumps(dict(snapshot.raw), sort_keys=True, default=str).encode("utf-8")
        ).hexdigest()
        return {
            "cohort": cohort,
            "selection_identity": identity,
            "source_run_seed": record.source_run_seed,
            "source_run_identity": record.source_run_identity,
            "complete_source_identity": record.complete_source_identity,
            "battle_identity": record.battle_identity,
            "act": record.act,
            "room_type": record.room_type,
            "restore_ok": True,
            "public_context_match": True,
            "restore_method": method,
            "snapshot_fingerprint": fingerprint,
            "failure_reason": None,
        }
    except (AttributeError, OSError, RuntimeError, TypeError, ValueError) as exc:
        return {
            "cohort": cohort,
            "selection_identity": identity,
            "source_run_seed": record.source_run_seed,
            "source_run_identity": record.source_run_identity,
            "complete_source_identity": record.complete_source_identity,
            "battle_identity": record.battle_identity,
            "act": record.act,
            "room_type": record.room_type,
            "restore_ok": False,
            "public_context_match": False,
            "restore_method": None,
            "snapshot_fingerprint": None,
            "failure_reason": str(exc),
        }


def run_t085_native_selection_restore_from_paths(
    *,
    adapter_factory: Callable[[], object],
    selection_input_path: str | Path,
    selection_input_sha256: str,
    a_full_map_path: str | Path,
    b_full_map_path: str | Path,
    c_full_map_path: str | Path,
    a_sha256: str,
    b_sha256: str,
    c_sha256: str,
    b_source_manifest_path: str | Path,
    b_source_manifest_sha256: str,
    c_source_manifest_path: str | Path,
    c_source_manifest_sha256: str,
    shard_index: int,
    shard_count: int,
    worker_count: int,
    restore_output_path: str | Path,
) -> dict[str, object]:
    """Run one explicit restore/parity shard for outcome-blind selection.

    This stage only restores the deterministically selected public identities.
    It intentionally does not call ``execute_controlled_run`` or Search; the
    later paired-evaluation command owns model/scorer execution.
    """

    shard = T085NativeShardPlan(shard_index, shard_count, worker_count)
    if not callable(adapter_factory):
        raise T085NativeExecutionError(
            "T085 selection restore requires an adapter factory"
        )
    context = _t085_prepare_selection_restore_inputs(
        selection_input_path=selection_input_path,
        selection_input_sha256=selection_input_sha256,
        a_full_map_path=a_full_map_path,
        b_full_map_path=b_full_map_path,
        c_full_map_path=c_full_map_path,
        a_sha256=a_sha256,
        b_sha256=b_sha256,
        c_sha256=c_sha256,
        b_source_manifest_path=b_source_manifest_path,
        b_source_manifest_sha256=b_source_manifest_sha256,
        c_source_manifest_path=c_source_manifest_path,
        c_source_manifest_sha256=c_source_manifest_sha256,
    )
    assigned: list[dict[str, object]] = []
    for cohort, record in _t085_selection_unique_records(context.selected):
        if (
            _t085_selection_shard_for(
                cohort,
                record.selection_identity,
                shard_count=shard.shard_count,
            )
            != shard.shard_index
        ):
            continue
        assigned.append(
            _t085_restore_selection_record(
                adapter_factory=adapter_factory,
                cohort=cohort,
                record=record,
                canonical_records=context.canonical_records_by_cohort[cohort],
            )
        )
    assigned.sort(key=lambda row: (str(row["cohort"]), str(row["selection_identity"])))
    payload = {
        "schema_id": T085_NATIVE_SELECTION_RESTORE_SHARD_SCHEMA_ID,
        "task_id": "T085",
        "artifact_scope": "selection_restore_shard",
        "partial": True,
        "complete": False,
        "shard_index": shard.shard_index,
        "shard_count": shard.shard_count,
        "worker_count": shard.worker_count,
        "effective_worker_count": shard.worker_count,
        "partition_scheme": "sha256(cohort/selection_identity)[:8] mod shard_count",
        "input_artifact": dict(context.input_reference),
        "source_bindings": {
            cohort: dict(binding) for cohort, binding in context.source_bindings.items()
        },
        "native_identity": dict(T085_NATIVE_IDENTITY),
        "selection_identity_sha256": context.selection_identity_sha256,
        "selected_records": {
            cohort: [asdict(record) for record in records]
            for cohort, records in context.selected.items()
        },
        "assigned_restore_evidence": assigned,
        "assigned_record_count": len(assigned),
        "restore_stage_complete": all(
            row.get("restore_ok") is True and row.get("public_context_match") is True
            for row in assigned
        ),
        "outcome_blind_selection": True,
        "search_invoked": False,
        "paired_evaluation_complete": False,
    }
    reference = write_t085_json_artifact(
        restore_output_path,
        payload,
        schema_id=T085_NATIVE_SELECTION_RESTORE_SHARD_SCHEMA_ID,
    )
    return {
        "status": "partial",
        "task_id": "T085",
        "restore_evidence_artifact": reference,
        "shard": payload,
    }


def _load_t085_selection_restore_shard(path: str | Path) -> dict[str, object]:
    resolved = Path(path).resolve(strict=True)
    try:
        payload = json.loads(resolved.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise T085NativeExecutionError(
            f"T085 selection restore shard is unavailable or invalid: {resolved}"
        ) from exc
    if not isinstance(payload, Mapping):
        raise T085NativeExecutionError("T085 selection restore shard is not an object")
    required = {
        "schema_id",
        "task_id",
        "artifact_scope",
        "partial",
        "complete",
        "shard_index",
        "shard_count",
        "worker_count",
        "effective_worker_count",
        "partition_scheme",
        "input_artifact",
        "source_bindings",
        "native_identity",
        "selection_identity_sha256",
        "selected_records",
        "assigned_restore_evidence",
        "assigned_record_count",
        "restore_stage_complete",
    }
    if not required.issubset(payload):
        raise T085NativeExecutionError(
            "T085 selection restore shard is missing required fields"
        )
    if (
        payload.get("schema_id") != T085_NATIVE_SELECTION_RESTORE_SHARD_SCHEMA_ID
        or payload.get("task_id") != "T085"
        or payload.get("artifact_scope") != "selection_restore_shard"
        or payload.get("partial") is not True
        or payload.get("complete") is not False
        or payload.get("shard_count") != 16
        or payload.get("worker_count") != 16
        or payload.get("effective_worker_count") != 16
        or payload.get("partition_scheme")
        != "sha256(cohort/selection_identity)[:8] mod shard_count"
        or payload.get("native_identity") != T085_NATIVE_IDENTITY
    ):
        raise T085NativeExecutionError(
            "T085 selection restore shard contract is invalid"
        )
    index = payload.get("shard_index")
    if isinstance(index, bool) or not isinstance(index, int) or not 0 <= index < 16:
        raise T085NativeExecutionError("T085 selection restore shard index is invalid")
    _t085_required_sha256(
        payload.get("selection_identity_sha256"),
        "selection restore selection identity SHA",
    )
    if not isinstance(payload.get("selected_records"), Mapping):
        raise T085NativeExecutionError(
            "T085 selection restore shard selected records are missing"
        )
    evidence = payload.get("assigned_restore_evidence")
    if not isinstance(evidence, list):
        raise T085NativeExecutionError(
            "T085 selection restore shard evidence is not a list"
        )
    assigned_count = payload.get("assigned_record_count")
    if (
        isinstance(assigned_count, bool)
        or not isinstance(assigned_count, int)
        or assigned_count < 0
        or assigned_count != len(evidence)
    ):
        raise T085NativeExecutionError(
            "T085 selection restore shard assigned count is not exact"
        )
    stage_complete = payload.get("restore_stage_complete")
    if not isinstance(stage_complete, bool) or stage_complete != all(
        isinstance(row, Mapping)
        and row.get("restore_ok") is True
        and row.get("public_context_match") is True
        for row in evidence
    ):
        raise T085NativeExecutionError(
            "T085 selection restore shard completion flag is not exact"
        )
    return dict(payload)


def finalize_t085_native_selection_restore_from_paths(
    *,
    shard_paths: Sequence[str | Path],
    selection_output_path: str | Path,
    restore_evidence_output_path: str | Path,
) -> dict[str, object]:
    """Merge exactly 16 restore shards and freeze the current selection artifact."""

    if len(shard_paths) != 16:
        raise T085NativeExecutionError(
            "T085 selection restore finalization requires exactly 16 shard artifacts"
        )
    shards = [_load_t085_selection_restore_shard(path) for path in shard_paths]
    indices = [int(shard["shard_index"]) for shard in shards]
    if sorted(indices) != list(range(16)):
        raise T085NativeExecutionError(
            "T085 selection restore shards must cover each index 0..15 exactly once"
        )
    first = shards[0]
    common_keys = (
        "input_artifact",
        "source_bindings",
        "native_identity",
        "selection_identity_sha256",
        "selected_records",
    )
    for shard in shards[1:]:
        if any(shard[key] != first[key] for key in common_keys):
            raise T085NativeExecutionError(
                "T085 selection restore shards are bound to different inputs/selections"
            )
    selected_raw = first["selected_records"]
    if not isinstance(selected_raw, Mapping) or set(selected_raw) != {
        "A",
        "B",
        "C",
        "B@400",
    }:
        raise T085NativeExecutionError(
            "T085 selection restore shard cohort matrix is incomplete"
        )
    selected: dict[str, tuple[T085BattleStartRecord, ...]] = {}
    for cohort in ("A", "B", "C", "B@400"):
        raw_records = selected_raw.get(cohort)
        if not isinstance(raw_records, list):
            raise T085NativeExecutionError(
                f"T085 selection restore selected {cohort} records are malformed"
            )
        selected[cohort] = tuple(
            T085BattleStartRecord.from_mapping(record)
            for record in raw_records
            if isinstance(record, Mapping)
        )
        if len(selected[cohort]) != len(raw_records):
            raise T085NativeExecutionError(
                f"T085 selection restore selected {cohort} records are malformed"
            )
    expected_selection_digest = _sha256_json(
        {
            cohort: [record.selection_identity for record in records]
            for cohort, records in selected.items()
        }
    )
    if first["selection_identity_sha256"] != expected_selection_digest:
        raise T085NativeExecutionError(
            "T085 selection restore selected identity digest is inconsistent"
        )
    expected_unique = {
        (cohort, record.selection_identity)
        for cohort, record in _t085_selection_unique_records(selected)
    }
    selected_by_key = {
        (cohort, record.selection_identity): record
        for cohort, records in selected.items()
        if cohort != "B@400"
        for record in records
    }
    combined: dict[tuple[str, str], dict[str, object]] = {}
    for shard in shards:
        evidence = shard["assigned_restore_evidence"]
        assert isinstance(evidence, list)
        for raw in evidence:
            if not isinstance(raw, Mapping):
                raise T085NativeExecutionError(
                    "T085 selection restore evidence row is malformed"
                )
            cohort = raw.get("cohort")
            identity = raw.get("selection_identity")
            if not isinstance(cohort, str) or not isinstance(identity, str):
                raise T085NativeExecutionError(
                    "T085 selection restore evidence identity is malformed"
                )
            key = (cohort, identity)
            if key not in expected_unique:
                raise T085NativeExecutionError(
                    "T085 selection restore evidence contains an unselected row"
                )
            selected_record = selected_by_key.get(key)
            if selected_record is None or any(
                raw.get(field_name) != getattr(selected_record, field_name)
                for field_name in (
                    "source_run_seed",
                    "source_run_identity",
                    "complete_source_identity",
                    "battle_identity",
                    "act",
                    "room_type",
                )
            ):
                raise T085NativeExecutionError(
                    "T085 selection restore evidence identity does not match "
                    "the selected record"
                )
            if (
                _t085_selection_shard_for(cohort, identity, shard_count=16)
                != shard["shard_index"]
            ):
                raise T085NativeExecutionError(
                    "T085 selection restore evidence is on the wrong shard"
                )
            if key in combined:
                raise T085NativeExecutionError(
                    "T085 selection restore evidence contains a duplicate row"
                )
            combined[key] = dict(raw)
    if set(combined) != expected_unique:
        raise T085NativeExecutionError(
            "T085 selection restore shards do not cover every selected A/B/C record"
        )
    failed = [
        key
        for key, row in combined.items()
        if row.get("restore_ok") is not True
        or row.get("public_context_match") is not True
    ]
    if failed:
        raise T085NativeExecutionError(
            "T085 selection restore/parity failed for "
            + ", ".join(f"{cohort}/{identity}" for cohort, identity in failed)
        )
    input_artifact = first["input_artifact"]
    source_bindings = first["source_bindings"]
    if not isinstance(input_artifact, Mapping) or not isinstance(
        source_bindings, Mapping
    ):
        raise T085NativeExecutionError(
            "T085 selection restore input binding is malformed"
        )
    input_path = input_artifact.get("path")
    input_sha = input_artifact.get("sha256")
    a_binding = source_bindings.get("A")
    b_binding = source_bindings.get("B")
    c_binding = source_bindings.get("C")
    if not all(
        isinstance(value, Mapping) for value in (a_binding, b_binding, c_binding)
    ):
        raise T085NativeExecutionError(
            "T085 selection restore source bindings are malformed"
        )
    # Re-run the complete path-bound resolver from the shard's embedded
    # references.  This prevents a finalizer caller from swapping maps after
    # the simulator restore stage.
    a_map_ref = a_binding["map"]
    b_map_ref = b_binding["map"]
    c_map_ref = c_binding["map"]
    b_manifest_ref = b_binding.get("source_manifest")
    c_manifest_ref = c_binding.get("source_manifest")
    if not all(
        isinstance(value, Mapping) for value in (a_map_ref, b_map_ref, c_map_ref)
    ):
        raise T085NativeExecutionError(
            "T085 selection restore map references are malformed"
        )
    if not isinstance(b_manifest_ref, Mapping) or not isinstance(
        c_manifest_ref, Mapping
    ):
        raise T085NativeExecutionError(
            "T085 selection restore manifest references are missing"
        )
    context = _t085_prepare_selection_restore_inputs(
        selection_input_path=str(input_path),
        selection_input_sha256=str(input_sha),
        a_full_map_path=str(a_map_ref["path"]),
        b_full_map_path=str(b_map_ref["path"]),
        c_full_map_path=str(c_map_ref["path"]),
        a_sha256=str(a_map_ref["sha256"]),
        b_sha256=str(b_map_ref["sha256"]),
        c_sha256=str(c_map_ref["sha256"]),
        b_source_manifest_path=str(b_manifest_ref["path"]),
        b_source_manifest_sha256=str(b_manifest_ref["sha256"]),
        c_source_manifest_path=str(c_manifest_ref["path"]),
        c_source_manifest_sha256=str(c_manifest_ref["sha256"]),
    )
    restore_results_by_cohort: dict[str, dict[str, Mapping[str, object]]] = {
        "A": {},
        "B": {},
        "C": {},
    }
    for (cohort, identity), result in combined.items():
        restore_results_by_cohort[cohort][identity] = result
    plan = build_t085_native_evaluation_plan(
        cohort_a_records=context.selected["A"],
        cohort_a_restore_results=restore_results_by_cohort["A"],
        cohort_b_source_manifest=context.source_manifests["B"],
        cohort_b_source_runs=context.source_runs["B"],
        cohort_b_battle_starts=context.battle_starts["B"],
        cohort_b_restore_results=restore_results_by_cohort["B"],
        cohort_c_source_manifest=context.source_manifests["C"],
        cohort_c_source_runs=context.source_runs["C"],
        cohort_c_battle_starts=context.battle_starts["C"],
        cohort_c_restore_results=restore_results_by_cohort["C"],
        t084_complete_source_identities=context.t084_complete_source_identities,
        t052_complete_source_identities=context.t052_complete_source_identities,
    )
    selection_reference = write_t085_native_selection_artifact(
        plan,
        selection_output_path,
    )
    final_evidence = {
        "schema_id": T085_NATIVE_SELECTION_RESTORE_EVIDENCE_SCHEMA_ID,
        "task_id": "T085",
        "artifact_scope": "selection_restore_evidence",
        "partial": False,
        "complete": True,
        "shard_count": 16,
        "worker_count": 16,
        "input_artifact": dict(context.input_reference),
        "source_bindings": {
            cohort: dict(binding) for cohort, binding in context.source_bindings.items()
        },
        "native_identity": dict(T085_NATIVE_IDENTITY),
        "selection_identity_sha256": context.selection_identity_sha256,
        "shard_artifacts": [
            {
                "path": str(Path(path).resolve()),
                "sha256": sha256_file(path),
                "byte_count": Path(path).stat().st_size,
            }
            for path in shard_paths
        ],
        "restore_evidence": [combined[key] for key in sorted(combined)],
        "restore_parity_passed": True,
        "selection_artifact": selection_reference,
        "outcome_blind_selection": True,
        "search_invoked": False,
        "paired_evaluation_complete": False,
    }
    evidence_reference = write_t085_json_artifact(
        restore_evidence_output_path,
        final_evidence,
        schema_id=T085_NATIVE_SELECTION_RESTORE_EVIDENCE_SCHEMA_ID,
    )
    return {
        "status": "complete",
        "task_id": "T085",
        "selection_artifact": selection_reference,
        "restore_evidence_artifact": evidence_reference,
        "record_counts": {
            cohort: len(records) for cohort, records in plan.cohorts.items()
        },
    }


def _native_execution_provenance(
    *,
    backend: T085NativeSearchBackend,
    native_identity: Mapping[str, object],
) -> dict[str, object]:
    return {
        "schema_id": T085_NATIVE_TERMINAL_LABEL_SCHEMA_ID,
        "execution_version": T085_NATIVE_EXECUTION_VERSION,
        "native_identity": dict(native_identity),
        "search_backend": backend,
        "native_api": (
            ORACLE_SEARCH_NATIVE_API
            if backend == "battle_search"
            else T085_NATIVE_V2_API
        ),
        "native_patch_identity": (
            ORACLE_SEARCH_PATCH_IDENTITY
            if backend == "battle_search"
            else T085_NATIVE_V2_PATCH
        ),
        "utility_source": "pre_action_native_selected_root_edge_mean",
        "terminal_proof": "same_action_transition_completed_battle_outcome",
        "required_edge_properties": [
            "search_tree_present",
            "visits_positive",
            "evaluation_sum_finite",
            "mean_value_finite",
            "evaluation_sum_divided_by_visits_matches_mean",
        ],
        "search_call_order": "native_search_before_adapter_step_on_current_snapshot",
        "python_mechanics": False,
    }


def _cohort_for_record(
    plan: T085NativeEvaluationPlan,
    record: T085BattleStartRecord,
    arm: str,
) -> str:
    candidate_cohorts = ("B@400",) if arm in T085_SEARCH_400_ARMS else ("A", "B", "C")
    matches = [
        cohort
        for cohort in candidate_cohorts
        if any(
            candidate is record
            or candidate.selection_identity == record.selection_identity
            for candidate in plan.cohorts[cohort]
        )
    ]
    if len(matches) != 1:
        raise T085NativeExecutionError(
            "T085 native evaluation record is not uniquely bound to a cohort"
        )
    return matches[0]


def run_t085_native_paired_evaluation(
    plan: T085NativeEvaluationPlan,
    *,
    adapter_factory: Callable[[], object],
    canonical_records_path: str | Path = T085_T052_COHORT_PATH,
    canonical_records_by_cohort: Mapping[str, Mapping[str, BattleStartCheckpointRecord]]
    | None = None,
    arms: Mapping[str, T085NativeArm],
    selection_output_path: str | Path,
    report_output_path: str | Path,
    outcomes_output_path: str | Path,
    search_backend: T085NativeSearchBackend = "battle_search",
    shard_index: int,
    shard_count: int,
    worker_count: int,
) -> dict[str, object]:
    """Run T085 using a repository-owned restore/controller battle loop.

    The injected callables are dependency factories/restorers only. They cannot
    supply outcomes, metrics, arm identity, budgets, or provenance. Those are
    derived here from the simulator transition and ``ControlledRunStep`` data.
    """

    _validate_plan(plan)
    if not callable(adapter_factory):
        raise T085NativeExecutionError(
            "T085 native paired evaluation requires an adapter factory"
        )
    if search_backend not in T085_NATIVE_SEARCH_BACKENDS:
        raise T085NativeExecutionError(
            f"unknown T085 native search backend {search_backend!r}"
        )
    native_identity = _validate_t085_native_source_manifest(search_backend)
    shard = T085NativeShardPlan(shard_index, shard_count, worker_count)
    if canonical_records_by_cohort is None:
        canonical_records_by_cohort = {
            "A": resolve_t085_canonical_records(canonical_records_path)
        }
    required_record_maps = {"A", "B", "C", "B@400"}
    if not required_record_maps.issubset(canonical_records_by_cohort):
        raise T085NativeExecutionError(
            "T085 paired evaluation requires separately verified full-record maps for A/T052, B, and C"
        )
    for cohort_name, selected_records in plan.cohorts.items():
        source_map = canonical_records_by_cohort[cohort_name]
        for selected in selected_records:
            canonical = source_map.get(selected.complete_source_identity)
            if canonical is None:
                raise T085NativeExecutionError(
                    f"T085 selection {cohort_name} is not bound to its full-record map: "
                    f"{selected.complete_source_identity}"
                )
            # Check the complete identity before any simulator work.  The
            # restore helper repeats this boundary for defense in depth.
            if (
                canonical.source_run_id != selected.source_run_identity
                or canonical.source_seed != selected.source_run_seed
                or canonical.source_battle_index != _selected_battle_index(selected)
                or canonical.structural_metadata.get("act") != selected.act
                or str(canonical.structural_metadata.get("room_type", "")).upper()
                != selected.room_type
            ):
                raise T085NativeExecutionError(
                    f"T085 selection {cohort_name} full-record identity mismatch: "
                    f"{selected.complete_source_identity}"
                )
    if search_backend != "battle_search_v2":
        raise T085NativeExecutionError("T085 arms require native battle_search_v2")
    expected_arm_names = (
        set(T085_PRIMARY_ARMS) | set(T085_SECONDARY_ARMS) | set(T085_SEARCH_400_ARMS)
    )
    if set(arms) != expected_arm_names:
        raise T085NativeExecutionError(
            "T085 arm inventory is incomplete or contains unknown arms"
        )
    if any(not isinstance(arm, T085NativeArm) for arm in arms.values()):
        raise T085NativeExecutionError("T085 arm inventory is malformed")
    selection_reference = write_t085_native_selection_artifact(
        plan,
        selection_output_path,
    )
    shard_manifest = shard.to_dict(
        selection_identity_sha256=sha256(
            json.dumps(
                {
                    cohort: [record.selection_identity for record in records]
                    for cohort, records in plan.cohorts.items()
                },
                sort_keys=True,
            ).encode("utf-8")
        ).hexdigest()
    )
    retained_rows: list[dict[str, object]] = []
    retained_labels: list[dict[str, object]] = []

    def evaluate_record(
        record: T085BattleStartRecord,
        arm: str,
        budget: int,
    ) -> T085OutcomeRecord:
        base_adapter = adapter_factory()
        started = time.perf_counter()
        selected_arm = arms[arm]
        cohort = _cohort_for_record(plan, record, arm)
        restored = restore_t085_canonical_record(
            base_adapter, record, canonical_records_by_cohort[cohort]
        )
        if isinstance(restored, tuple):
            snapshot = restored[0]
        else:
            snapshot = restored
        if not isinstance(snapshot, SimulatorSnapshot):
            raise T085NativeExecutionError(
                "T085 restore did not return a SimulatorSnapshot"
            )
        adapter = T085NativeTerminalSearchAdapter(
            base_adapter,
            search_simulations=budget,
            search_backend=search_backend,
            policy_prior_callback=selected_arm.policy_prior_callback,
            leaf_value_callback=selected_arm.leaf_value_callback,
        )
        adapter.prime_restored_snapshot(snapshot)
        controller: OnlineController = T085NativeArmController(
            selected_arm,
            simulations=budget,
        )
        controlled: ControlledRun = execute_controlled_run(
            adapter,
            controller,
            seed=None,
            max_steps=200,
            action_space=ActionSpaceConfig.initial_no_potions(),
        )
        wall_clock_seconds = time.perf_counter() - started
        terminal_outcome = (
            last_step.next_battle_outcome
            if (last_step := (controlled.steps[-1] if controlled.steps else None))
            else None
        )
        if terminal_outcome is None:
            terminal_outcome = str(
                controlled.final_raw.get(
                    "completed_battle_outcome",
                    controlled.final_raw.get("battle_outcome", controlled.outcome),
                )
            )
        if controlled.problems or terminal_outcome not in _TERMINAL_OUTCOMES:
            raise T085NativeExecutionError(
                "T085 native evaluation did not complete a proven terminal battle: "
                + "; ".join(controlled.problems)
            )
        labels = adapter.native_terminal_labels
        if len(labels) != 1:
            raise T085NativeExecutionError(
                "T085 native evaluation is INCOMPLETE: executor did not produce "
                "exactly one proven terminal battle label"
            )
        label = labels[0]
        if label.terminal_outcome not in _TERMINAL_OUTCOMES:
            raise T085NativeExecutionError(
                "T085 native evaluation is INCOMPLETE: terminal outcome is unknown"
            )
        selected_identity = label.selected_action_identity.get("stable_id")
        if not isinstance(selected_identity, str) or not selected_identity:
            raise T085NativeExecutionError(
                "T085 native terminal label lacks selected action identity"
            )
        payload: dict[str, object] = {
            "cohort": _cohort_for_record(plan, record, arm),
            "record_identity": record.selection_identity,
            "arm": arm,
            "battle_survived": terminal_outcome == "PLAYER_VICTORY",
            "terminal_native_utility": label.mean_value,
            "selected_root_action_identity": selected_identity,
            "source_run_identity": record.source_run_identity,
            "search_budget": budget,
            "wall_clock_seconds": wall_clock_seconds,
            "controller_provenance": controlled.controller_provenance,
            "arm_provenance": selected_arm.provenance,
            "inference_diagnostics": {
                str(key): value
                for step in controlled.steps
                for key, value in step.decision_metadata.items()
                if isinstance(value, (int, float)) and not isinstance(value, bool)
            },
        }
        if last_step is not None:
            payload["terminal_current_hp"] = last_step.next_player_hp
            payload["turn_count"] = len(controlled.steps)
            payload["simulator_steps"] = len(controlled.steps)
            payload["search_steps"] = sum(
                1 for step in controlled.steps if step.battle_active
            )
            payload["learned_value_callback_count"] = sum(
                1
                for step in controlled.steps
                if step.decision_metadata.get("t085_arm", {}).get("leaf_value_callback")
            )
            resource_outcome = last_step.next_snapshot_raw.get(
                "completed_battle_resource_outcome"
            )
            if isinstance(resource_outcome, Mapping):
                payload["structured_battle_resource_outcome"] = dict(resource_outcome)
        row = T085OutcomeRecord.from_mapping(payload)
        row_payload = asdict(row)
        row_payload["shard"] = shard_manifest
        row_payload["native_terminal_utility_provenance"] = label.to_dict()
        retained_rows.append(row_payload)
        retained_labels.append(label.to_dict())
        return row

    report = run_t085_paired_evaluation(
        plan.cohorts,
        evaluate_record=evaluate_record,
        selection_evidence=plan.selection_evidence,
        shard_index=shard.shard_index,
        shard_count=shard.shard_count,
    )
    report_payload = dict(report)
    report_payload["task_id"] = "T085"
    report_payload["selection_artifact"] = selection_reference
    report_payload["shard"] = shard_manifest
    report_payload["selection_binding"] = {
        "selection_artifact": selection_reference,
        "shard": shard_manifest,
    }
    report_payload["native_execution_provenance"] = _native_execution_provenance(
        backend=search_backend,
        native_identity=native_identity,
    )
    report_reference = write_t085_json_artifact(
        report_output_path,
        report_payload,
        schema_id="t085-paired-evaluation-report-v1",
    )
    outcomes_payload = {
        "schema_id": T085_NATIVE_OUTCOMES_SCHEMA_ID,
        "task_id": "T085",
        "artifact_scope": "paired_evaluation_shard",
        "partial": True,
        "complete": False,
        "native_identity": native_identity,
        "selection_artifact": selection_reference,
        "paired_report_artifact": report_reference,
        "selection_binding": report_payload["selection_binding"],
        "shard": shard_manifest,
        "native_execution_provenance": _native_execution_provenance(
            backend=search_backend,
            native_identity=native_identity,
        ),
        "outcomes": retained_rows,
        "native_terminal_labels": retained_labels,
    }
    outcomes_reference = write_t085_json_artifact(
        outcomes_output_path,
        outcomes_payload,
        schema_id=T085_NATIVE_OUTCOMES_SCHEMA_ID,
    )
    return {
        # The shard itself is verified as an execution partition, but it is
        # never a complete T085 result.  A later merge must consume all 16
        # partial artifacts and re-run the full selection/support gates.
        "status": "partial",
        "task_id": "T085",
        "selection_artifact": selection_reference,
        "paired_report_artifact": report_reference,
        "outcomes_artifact": outcomes_reference,
        "shard": shard_manifest,
        "report": report,
    }


__all__ = [
    "T085_NATIVE_SELECTION_INPUT_SCHEMA_ID",
    "T085_NATIVE_SELECTION_RESTORE_EVIDENCE_SCHEMA_ID",
    "T085_NATIVE_SELECTION_RESTORE_SHARD_SCHEMA_ID",
    "T085CohortBSourceGenerationPlan",
    "T085CohortCSourceGenerationPlan",
    "T085NativeArm",
    "T085NativeArmController",
    "T085NativeEvaluationPlan",
    "T085NativeExecutionError",
    "T085NativeRootEdgeLabel",
    "T085NativeSearchBackend",
    "T085NativeShardPlan",
    "T085NativeTerminalSearchAdapter",
    "T085UnguidedBattleSearchV2Controller",
    "build_t085_cohort_b_source_controller",
    "build_t085_cohort_b_source_manifest_from_paths",
    "build_t085_cohort_c_source_controller",
    "build_t085_cohort_c_source_manifest_from_paths",
    "build_t085_native_arms",
    "build_t085_native_evaluation_plan",
    "finalize_t085_native_root_edge_label",
    "finalize_t085_native_selection_restore_from_paths",
    "load_t085_native_evaluation_plan",
    "merge_t085_cohort_b_source_pool_from_paths",
    "merge_t085_cohort_c_source_pool_from_paths",
    "prepare_t085_native_root_edge_label",
    "resolve_t085_canonical_records",
    "restore_t085_canonical_record",
    "run_t085_cohort_b_source_generation_from_paths",
    "run_t085_cohort_c_source_generation_from_paths",
    "run_t085_native_paired_evaluation",
    "run_t085_native_paired_evaluation_from_paths",
    "run_t085_native_selection_restore_from_paths",
    "write_t085_native_selection_artifact",
]
