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

import json
import math
import time
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import asdict, dataclass, field, replace
from hashlib import sha256
from pathlib import Path
from typing import Any, Literal

from sts_combat_rl.sim.action_space import ActionSpaceConfig
from sts_combat_rl.sim.assisted_source_generation import (
    ASSISTED_SOURCE_POOL_FORMAT_VERSION,
    ASSISTED_SOURCE_POOL_SCHEMA_ID,
    load_assisted_source_pool_jsonl,
    restore_assisted_battle_start_record,
)
from sts_combat_rl.sim.battle_search_v2 import _node_context
from sts_combat_rl.sim.battle_start_pool import (
    BATTLE_START_POOL_FORMAT_VERSION,
    BattleStartCheckpointRecord,
    NaturalBattleStartPool,
    collect_natural_battle_start_pool,
    dump_natural_battle_start_pool_jsonl,
    load_natural_battle_start_pool_jsonl,
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
    OracleSearchReport,
    build_oracle_search_report,
    oracle_search_controller_metadata,
    select_oracle_root_action,
)
from sts_combat_rl.sim.search_guidance_inference import (
    SEARCH_V2_LEAF_NATIVE_UTILITY_TARGET_KIND,
    SearchGuidanceScorer,
    search_guidance_scorer_checkpoint_provenance,
    validate_search_guidance_result,
)
from sts_combat_rl.sim.torch_policy_value import OUTCOME_TARGET_KIND
from sts_combat_rl.t085_corrected_leaf_value_search_evaluation import (
    T085_COHORT_C_RUN_COUNT,
    T085_COHORT_C_SEED_END,
    T085_COHORT_C_SEED_START,
    T085_INPUT_ARTIFACT_IDENTITIES,
    T085_NATIVE_IDENTITY,
    T085_SEARCH_400_ARMS,
    T085_SOURCE_MANIFEST_SCHEMA_ID,
    T085_T052_COHORT_PATH,
    T085_T052_COHORT_SHA256,
    T085BattleStartRecord,
    T085EvaluationIntegrityError,
    T085OutcomeRecord,
    T085SourceRunRecord,
    build_t085_cohort_selection,
    build_t085_evaluation_selection_evidence,
    run_t085_paired_evaluation,
    select_search_400_subset,
    sha256_file,
    validate_t085_evaluation_selection_evidence,
    validate_t085_source_generation_contract,
    write_t085_json_artifact,
)
from sts_combat_rl.t085_corrected_leaf_value_search_repair import T085_ARTIFACT_ROOT

T085_NATIVE_V2_API = "StepSimulator.battle_search_v2.v1"
T085_NATIVE_V2_PATCH = "sts_lightspeed_battle_search_v2_tree_internal_v1"
T085_NATIVE_TERMINAL_LABEL_SCHEMA_ID = "t085-native-terminal-root-label-v1"
T085_NATIVE_SELECTION_SCHEMA_ID = "t085-native-selection-artifact-v1"
T085_NATIVE_OUTCOMES_SCHEMA_ID = "t085-native-outcome-records-v1"
T085_NATIVE_EXECUTION_VERSION = "t085-native-execution-v1"
T085_NATIVE_SHARD_SCHEMA_ID = "t085-native-shard-manifest-v1"
T085_C_SOURCE_SHARD_MANIFEST_SCHEMA_ID = "t085-cohort-c-source-shard-manifest-v1"
T085_C_SOURCE_POOL_SCHEMA_ID = "natural-battle-start-pool-v4-jsonl"
T085_NATIVE_SEARCH_BACKENDS = ("battle_search", "battle_search_v2")
T085NativeSearchBackend = Literal["battle_search", "battle_search_v2"]
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
            else OUTCOME_TARGET_KIND
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


def _require_t085_stable_path(path: str | Path, label: str) -> Path:
    resolved = Path(path).resolve()
    try:
        resolved.relative_to(T085_ARTIFACT_ROOT.resolve())
    except ValueError as exc:
        raise T085NativeExecutionError(
            f"T085 {label} must be under the stable ignored T085 artifact root"
        ) from exc
    return resolved


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
    if pool.source_controller_provenance != controller.provenance.to_dict():
        raise T085NativeExecutionError(
            "T085 Cohort C source pool controller provenance is not exact"
        )
    summaries = pool.source_run_summaries
    if len(summaries) != len(expected_seeds):
        raise T085NativeExecutionError(
            "T085 Cohort C source pool lacks one summary per source run"
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
        "selection_rule": (
            "sha256(source_run_identity:complete_source_identity) per source run"
        ),
        "one_record_per_source_run": True,
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
    "build_t085_cohort_c_source_controller",
    "build_t085_cohort_c_source_manifest_from_paths",
    "build_t085_native_arms",
    "build_t085_native_evaluation_plan",
    "finalize_t085_native_root_edge_label",
    "load_t085_native_evaluation_plan",
    "prepare_t085_native_root_edge_label",
    "resolve_t085_canonical_records",
    "restore_t085_canonical_record",
    "run_t085_cohort_c_source_generation_from_paths",
    "run_t085_native_paired_evaluation",
    "run_t085_native_paired_evaluation_from_paths",
    "write_t085_native_selection_artifact",
]
