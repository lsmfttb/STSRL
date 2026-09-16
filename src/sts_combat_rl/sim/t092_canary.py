"""Authorized-only paired T092 semantic-parity canary seam.

The file-level readiness helpers do not restore a checkpoint or invoke native
Search.  Native work is performed one arm per fresh process by the separately
authorized process-isolated execution entrypoint.
"""

from __future__ import annotations

import math
import os
import sys
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, dataclass
from typing import Any, Protocol

from sts_combat_rl.commands.t085_native_execution import (
    restore_t085_canonical_record,
)
from sts_combat_rl.sim.action_space import ActionSpaceConfig
from sts_combat_rl.sim.battle_search_v2 import (
    BATTLE_SEARCH_V2_NATIVE_API,
    BATTLE_SEARCH_V2_PATCH_IDENTITY,
)
from sts_combat_rl.sim.battle_start_pool import BattleStartCheckpointRecord
from sts_combat_rl.sim.controlled_run import execute_controlled_run
from sts_combat_rl.sim.controller_contract import (
    ControllerDecision,
    ControllerProvenance,
)
from sts_combat_rl.sim.oracle_search import (
    build_oracle_search_report,
    select_oracle_root_action,
)
from sts_combat_rl.sim.policy_contract import DecisionContext
from sts_combat_rl.sim.public_run_context import (
    build_public_run_context,
    read_native_public_projection,
)
from sts_combat_rl.sim.t090_battle_student import (
    T090SplitEntry,
    canonical_sha256,
    validate_t090_split_manifest,
)
from sts_combat_rl.sim.t092_internal_search_state import (
    T092_FROZEN_TEACHER_CONFIG,
    T092Incomplete,
    T092_NATIVE_API,
    T092_NATIVE_IDENTITY,
    T092_NATIVE_PATCH_IDENTITY,
    parse_native_occurrences,
    select_t092_canary_sources,
    validate_parent_bound_occurrence_identities,
    validate_retained_occurrence,
)
from sts_combat_rl.t085_corrected_leaf_value_search_evaluation import (
    T085BattleStartRecord,
)

T092_CANARY_EVIDENCE_SCHEMA_ID = "t092-paired-semantic-parity-canary-v1"
T092_CANARY_PLAN_SCHEMA_ID = "t092-paired-canary-plan-v1"
T092_CANARY_ARM_RECORD_SCHEMA_ID = "t092-paired-canary-arm-record-v1"
T092_CANARY_START_COUNT = 12
T092_CANARY_CLASSIFICATION = "MECHANICS_INFORMATION_BOUNDARY_ONLY"
T092_PUBLICATION_NATIVE_IDENTITY = {
    "repository": "lsmfttb/sts_lightspeed",
    "ref": "refs/heads/stsrl/main",
    "commit": "20a6c2b3a9cea817c988178b814f083ff889853f",
}


class T092CanaryError(ValueError):
    """The bounded T092 canary is incomplete or semantically inconsistent."""


class T092CanaryStartRunner(Protocol):
    def __call__(self, source: T090SplitEntry) -> Mapping[str, Any]: ...


def select_t092_canary_entries(
    split_manifest: Mapping[str, Any],
) -> tuple[T090SplitEntry, ...]:
    """Use the T090 immutable ledger and T092's A/B/C hash selection exactly."""

    entries = validate_t090_split_manifest(split_manifest)
    by_identity = {entry.source_identity: entry for entry in entries}
    selected = select_t092_canary_sources(
        [
            {
                "source_identity": entry.source_identity,
                "source_group": entry.source_group,
                "split": entry.split,
                "canonical_position": entry.canonical_position,
            }
            for entry in entries
        ]
    )
    result = tuple(by_identity[str(row["source_identity"])] for row in selected)
    if len(result) != T092_CANARY_START_COUNT:
        raise T092CanaryError("T092 canary must select exactly 12 sources")
    return result


def build_t092_canary_plan(split_manifest: Mapping[str, Any]) -> dict[str, Any]:
    """Build a deterministic no-execution plan for independent review."""

    selected = select_t092_canary_entries(split_manifest)
    return {
        "schema_id": T092_CANARY_PLAN_SCHEMA_ID,
        "schema_version": 1,
        "task_id": "T092",
        "execution_authorized": False,
        "selection_domain_separator": 900492,
        "split_manifest_sha256": canonical_sha256(split_manifest),
        "arm_native_identities": {
            "OFF": dict(T092_PUBLICATION_NATIVE_IDENTITY),
            "ON": dict(T092_NATIVE_IDENTITY),
        },
        "teacher_config": dict(T092_FROZEN_TEACHER_CONFIG),
        "worker_plan": {
            "stage_worker_count": 12,
            "shard_count": 12,
            "one_selected_start_per_shard": True,
            "reason": "twelve independent paired restores; capped by canary shard count",
        },
        "selected_sources": [asdict(entry) for entry in selected],
        "output_schema_id": T092_CANARY_EVIDENCE_SCHEMA_ID,
    }


@dataclass(frozen=True)
class T092CanaryArmController:
    """One frozen Search arm; ON differs solely by its opt-in native API."""

    telemetry_enabled: bool
    simulations: int = 400

    def __post_init__(self) -> None:
        if self.simulations != 400:
            raise T092CanaryError("T092 canary requires frozen Search-v2@400")
        object.__setattr__(
            self,
            "provenance",
            ControllerProvenance(
                kind="t092_paired_search_v2_canary",
                name=("t092_telemetry_on" if self.telemetry_enabled else "t092_telemetry_off"),
                config={
                    "task_id": "T092",
                    "arm": "ON" if self.telemetry_enabled else "OFF",
                    "native_identity": dict(
                        T092_NATIVE_IDENTITY
                        if self.telemetry_enabled
                        else T092_PUBLICATION_NATIVE_IDENTITY
                    ),
                    "teacher_config": dict(T092_FROZEN_TEACHER_CONFIG),
                },
            ),
        )

    def select_action(
        self,
        adapter: object,
        snapshot: object,
        actions: Sequence[object],
        context: DecisionContext,
        step_index: int,
    ) -> ControllerDecision:
        method = (
            "battle_search_v2_with_internal_teacher_telemetry"
            if self.telemetry_enabled
            else "battle_search_v2"
        )
        search = getattr(adapter, method, None)
        if not callable(search):
            raise T092CanaryError(f"T092 canary adapter lacks {method}")
        if self.telemetry_enabled:
            raw = search(snapshot, simulations=400, include_potions=False)
            expected_api, expected_patch = T092_NATIVE_API, T092_NATIVE_PATCH_IDENTITY
        else:
            raw = search(
                snapshot,
                simulations=400,
                include_potions=False,
                policy_prior_callback=None,
                leaf_value_callback=None,
            )
            expected_api, expected_patch = (
                BATTLE_SEARCH_V2_NATIVE_API,
                BATTLE_SEARCH_V2_PATCH_IDENTITY,
            )
        if not isinstance(raw, Mapping):
            raise T092CanaryError("T092 native search did not return a mapping")
        report = build_oracle_search_report(
            raw,
            actions,  # type: ignore[arg-type]
            context,
            expected_native_api=expected_api,
            expected_patch_identity=expected_patch,
        )
        if not report.search_ok:
            raise T092CanaryError("T092 canary native root mapping failed")
        target = select_oracle_root_action(report, selection_rule="highest_mean")
        semantic = _root_semantic_record(report, target.to_dict())
        metadata: dict[str, Any] = {
            "t092_canary_decision": {
                "arm": "ON" if self.telemetry_enabled else "OFF",
                "decision_step_index": step_index,
                "root_semantics": semantic,
                "native_report": dict(raw) if self.telemetry_enabled else None,
            }
        }
        return ControllerDecision(
            selected_index=target.legal_action_index,
            provenance=self.provenance,
            reason="t092_canary:highest_mean",
            score=target.score,
            metadata=metadata,
        )


def _root_semantic_record(report: Any, target: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "ordered_root_actions": [
            {
                "action_identity": dict(row.action_identity),
                "visits": row.visits,
                "evaluation_sum": row.evaluation_sum,
                "mean_value": row.mean_value,
            }
            for row in report.root_actions
        ],
        "root_visits": report.root_visits,
        "native_simulator_steps": report.native_simulator_steps,
        "best_action_value": report.best_action_value,
        "min_action_value": report.min_action_value,
        "outcome_player_hp": report.outcome_player_hp,
        "selected_action_identity": dict(target["action_identity"]),
        "selection_rule": target["selection_rule"],
    }


def run_t092_native_canary_arm(
    *,
    source: T090SplitEntry,
    selected: T085BattleStartRecord,
    canonical: BattleStartCheckpointRecord,
    telemetry_enabled: bool,
    adapter_factory: Callable[[], object],
    worker: Mapping[str, Any],
    implementation_head: str,
    native_binary: Mapping[str, Any],
) -> dict[str, Any]:
    """Restore and execute exactly one arm in its already-isolated process.

    The caller owns process isolation.  This deliberately has no OFF/ON
    companion factory: allowing both extensions in one interpreter is forbidden
    by the T092 process-isolation amendment.
    """

    if not callable(adapter_factory):
        raise T092CanaryError("T092 isolated arm adapter factory is unavailable")
    if not isinstance(implementation_head, str) or len(implementation_head) != 40:
        raise T092CanaryError("T092 isolated arm implementation identity is invalid")
    worker_identity = _validate_worker(worker)
    expected_native_identity = (
        T092_NATIVE_IDENTITY if telemetry_enabled else T092_PUBLICATION_NATIVE_IDENTITY
    )
    if not isinstance(native_binary, Mapping) or set(native_binary) != {
        "path", "sha256", "size_bytes"
    }:
        raise T092CanaryError("T092 isolated arm native binary evidence is invalid")
    if (
        not isinstance(native_binary["path"], str)
        or not native_binary["path"]
        or not isinstance(native_binary["sha256"], str)
        or len(native_binary["sha256"]) != 64
        or any(character not in "0123456789abcdef" for character in native_binary["sha256"])
        or isinstance(native_binary["size_bytes"], bool)
        or not isinstance(native_binary["size_bytes"], int)
        or native_binary["size_bytes"] <= 0
    ):
        raise T092CanaryError("T092 isolated arm native binary evidence is malformed")
    base_adapter = adapter_factory()
    try:
        restored, restore_method = restore_t085_canonical_record(
            base_adapter, selected, {selected.selection_identity: canonical}
        )
        legal_actions = getattr(base_adapter, "legal_actions", None)
        if not callable(legal_actions):
            raise T092CanaryError("T092 canary adapter lacks legal_actions")
        root_actions = list(legal_actions(restored))
        expected_context = canonical.public_run_context
        actual_context = build_public_run_context(
            restored.raw,
            root_actions,
            projection=read_native_public_projection(base_adapter, restored),
            history=(
                expected_context.get("history", [])
                if isinstance(expected_context, Mapping)
                else []
            ),
        )
        if not isinstance(expected_context, Mapping) or actual_context != expected_context:
            raise T092CanaryError("T092 canary restore public/legal parity failed")
        restored_adapter = _RestoredAdapter(base_adapter, restored)
        started = time.perf_counter()
        controlled = execute_controlled_run(
            restored_adapter,
            T092CanaryArmController(telemetry_enabled=telemetry_enabled),
            seed=None,
            max_steps=200,
            action_space=ActionSpaceConfig.initial_no_potions(),
        )
        elapsed = time.perf_counter() - started
        decisions, occurrences = _collect_arm_records(
            controlled,
            source=source,
            telemetry_enabled=telemetry_enabled,
        )
        terminal = _terminal_record(controlled)
        return {
            "schema_id": T092_CANARY_ARM_RECORD_SCHEMA_ID,
            "schema_version": 1,
            "task_id": "T092",
            "arm": "ON" if telemetry_enabled else "OFF",
            "source_identity": source.source_identity,
            "source_group": source.source_group,
            "split": source.split,
            "canonical_position": source.canonical_position,
            "restore_binding": {
                "selection_identity": selected.selection_identity,
                "source_checkpoint_id": canonical.source_checkpoint_id,
                "source_run_identity": canonical.source_run_id,
                "source_seed": canonical.source_seed,
                "source_battle_index": canonical.source_battle_index,
            },
            "implementation_head": implementation_head,
            "native_identity": dict(expected_native_identity),
            "native_binary": dict(native_binary),
            "native_api": (
                T092_NATIVE_API if telemetry_enabled else BATTLE_SEARCH_V2_NATIVE_API
            ),
            "teacher_config": dict(T092_FROZEN_TEACHER_CONFIG),
            "process_identity": {
                "pid": os.getpid(),
                "python_executable": sys.executable,
            },
            "worker": worker_identity,
            "restore_method": restore_method,
            "restored_snapshot_present": restored is not None,
            "restore_public_legal_parity": True,
            "decision_records": decisions,
            "terminal": terminal,
            "internal_occurrences": occurrences,
            "cost": {"wall_clock_time_s": elapsed},
        }
    finally:
        close = getattr(base_adapter, "close", None)
        if callable(close):
            try:
                close()
            except BaseException:
                if sys.exc_info()[0] is None:
                    raise


class _RestoredAdapter:
    """Expose exactly one already-restored snapshot to controlled-run reset."""

    def __init__(self, base_adapter: object, restored: object) -> None:
        self._base_adapter = base_adapter
        self._restored = restored

    def reset(self, seed: int | None = None) -> object:
        if seed is not None or self._restored is None:
            raise T092CanaryError("T092 canary attempted to reseed a restored arm")
        snapshot, self._restored = self._restored, None
        return snapshot

    def __getattr__(self, name: str) -> Any:
        return getattr(self._base_adapter, name)


def _collect_arm_records(
    controlled: Any, *, source: T090SplitEntry, telemetry_enabled: bool
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if not getattr(controlled, "terminal", False) or getattr(controlled, "problems", None):
        raise T092CanaryError("T092 canary arm did not reach a clean terminal")
    decisions: list[dict[str, Any]] = []
    occurrences: list[dict[str, Any]] = []
    for step in getattr(controlled, "steps", []):
        metadata = getattr(step, "decision_metadata", {})
        record = metadata.get("t092_canary_decision") if isinstance(metadata, Mapping) else None
        if not isinstance(record, Mapping):
            continue
        if record.get("arm") != ("ON" if telemetry_enabled else "OFF"):
            raise T092CanaryError("T092 canary arm decision provenance drifted")
        semantic = record.get("root_semantics")
        if not isinstance(semantic, Mapping):
            raise T092CanaryError("T092 canary decision lacks root semantics")
        decision_identity = f"{source.source_identity}:battle-decision:{getattr(step, 'step_index', -1)}"
        decisions.append({"decision_identity": decision_identity, "root_semantics": dict(semantic)})
        if telemetry_enabled:
            raw = record.get("native_report")
            if not isinstance(raw, Mapping):
                raise T092CanaryError("T092 ON arm lacks its native telemetry report")
            occurrences.extend(
                asdict(item)
                for item in parse_native_occurrences(
                    raw,
                    source_identity=source.source_identity,
                    source_group=source.source_group,
                    split=source.split,
                    parent_root_decision_identity=decision_identity,
                    native_identity=T092_NATIVE_IDENTITY,
                )
            )
    if not decisions:
        raise T092CanaryError("T092 canary arm has no Battle decisions")
    return decisions, occurrences


def _terminal_record(controlled: Any) -> dict[str, Any]:
    steps = list(getattr(controlled, "steps", []))
    final = steps[-1] if steps else None
    outcome = getattr(final, "next_battle_outcome", None) if final is not None else None
    if not isinstance(outcome, str) or not outcome:
        raise T092CanaryError("T092 canary terminal Battle outcome is unavailable")
    return {
        "outcome": outcome,
        "terminal_current_hp": getattr(final, "next_player_hp", None),
        "battle_decision_count": sum(
            getattr(step, "battle_active", False) is True for step in steps
        ),
    }


def _validate_worker(value: Mapping[str, Any]) -> dict[str, int]:
    required = {"stage_worker_count", "worker_index", "shard_count", "shard_index"}
    if set(value) != required:
        raise T092CanaryError("T092 canary worker fields are incomplete")
    result: dict[str, int] = {}
    for key in required:
        raw = value[key]
        if isinstance(raw, bool) or not isinstance(raw, int) or raw < 0:
            raise T092CanaryError("T092 canary worker value is invalid")
        result[key] = raw
    if not result["stage_worker_count"] or not result["shard_count"]:
        raise T092CanaryError("T092 canary worker/shard count must be positive")
    if result["worker_index"] >= result["stage_worker_count"] or result["shard_index"] >= result["shard_count"]:
        raise T092CanaryError("T092 canary worker/shard index is outside its plan")
    return result


def execute_t092_canary(
    *, split_manifest: Mapping[str, Any], runner: T092CanaryStartRunner
) -> dict[str, Any]:
    """Execute only an explicitly injected, separately authorized paired run."""

    if not callable(runner):
        raise T092CanaryError("T092 canary runner must be callable")
    selected = select_t092_canary_entries(split_manifest)
    entries = [_validate_pair_record(runner(source), source) for source in selected]
    all_occurrences = [row for entry in entries for row in entry["on"]["internal_occurrences"]]
    evidence = {
        "schema_id": T092_CANARY_EVIDENCE_SCHEMA_ID,
        "schema_version": 1,
        "task_id": "T092",
        "classification": T092_CANARY_CLASSIFICATION,
        "formal_execution_authorized": False,
        "training_eligible": False,
        "split_manifest_sha256": canonical_sha256(split_manifest),
        "arm_native_identities": {
            "OFF": dict(T092_PUBLICATION_NATIVE_IDENTITY),
            "ON": dict(T092_NATIVE_IDENTITY),
        },
        "teacher_config": dict(T092_FROZEN_TEACHER_CONFIG),
        "source_execution_entries": entries,
        "source_execution_entries_sha256": canonical_sha256(entries),
        "semantic_parity": {"passed": True, "mismatch_count": 0},
        "internal_occurrences": all_occurrences,
    }
    validate_t092_canary_evidence(evidence, split_manifest=split_manifest)
    return evidence


def validate_t092_canary_evidence(
    evidence: Mapping[str, Any], *, split_manifest: Mapping[str, Any]
) -> None:
    """Validate already-produced paired evidence without invoking native work."""

    if (
        evidence.get("schema_id") != T092_CANARY_EVIDENCE_SCHEMA_ID
        or evidence.get("schema_version") != 1
        or evidence.get("task_id") != "T092"
        or evidence.get("classification") != T092_CANARY_CLASSIFICATION
        or evidence.get("formal_execution_authorized") is not False
        or evidence.get("training_eligible") is not False
        or evidence.get("split_manifest_sha256") != canonical_sha256(split_manifest)
        or evidence.get("arm_native_identities")
        != {"OFF": T092_PUBLICATION_NATIVE_IDENTITY, "ON": T092_NATIVE_IDENTITY}
        or evidence.get("teacher_config") != T092_FROZEN_TEACHER_CONFIG
    ):
        raise T092CanaryError("T092 paired canary evidence provenance is invalid")
    selected = select_t092_canary_entries(split_manifest)
    raw_entries = evidence.get("source_execution_entries")
    if not isinstance(raw_entries, Sequence) or len(raw_entries) != T092_CANARY_START_COUNT:
        raise T092CanaryError("T092 paired canary evidence does not contain 12 starts")
    entries = [_validate_pair_record(item, source) for item, source in zip(raw_entries, selected, strict=True)]
    if evidence.get("source_execution_entries_sha256") != canonical_sha256(entries):
        raise T092CanaryError("T092 paired canary entry hash is invalid")
    if evidence.get("semantic_parity") != {"passed": True, "mismatch_count": 0}:
        raise T092CanaryError("T092 paired canary parity summary is invalid")
    expected_occurrences = [row for entry in entries for row in entry["on"]["internal_occurrences"]]
    if evidence.get("internal_occurrences") != expected_occurrences:
        raise T092CanaryError("T092 paired canary internal rows are incomplete")


def _validate_pair_record(raw: Mapping[str, Any], source: T090SplitEntry) -> dict[str, Any]:
    if not isinstance(raw, Mapping):
        raise T092CanaryError("T092 canary runner did not return a mapping")
    required = {
        "source_identity",
        "source_group",
        "split",
        "canonical_position",
        "arm_native_identities",
        "teacher_config",
        "worker",
        "arm_artifacts",
        "off",
        "on",
    }
    if set(raw) != required:
        raise T092CanaryError("T092 canary pair fields are incomplete")
    for key, expected in {
        "source_identity": source.source_identity,
        "source_group": source.source_group,
        "split": source.split,
        "canonical_position": source.canonical_position,
        "arm_native_identities": {
            "OFF": T092_PUBLICATION_NATIVE_IDENTITY,
            "ON": T092_NATIVE_IDENTITY,
        },
        "teacher_config": T092_FROZEN_TEACHER_CONFIG,
    }.items():
        if raw.get(key) != expected:
            raise T092CanaryError(f"T092 canary pair provenance mismatch: {key}")
    _validate_worker(raw["worker"])
    artifacts = raw.get("arm_artifacts")
    if not isinstance(artifacts, Mapping) or set(artifacts) != {"OFF", "ON"}:
        raise T092CanaryError("T092 canary pair arm artifact bindings are incomplete")
    artifact_paths: set[str] = set()
    artifact_hashes: set[str] = set()
    for arm in ("OFF", "ON"):
        artifact = artifacts[arm]
        if not isinstance(artifact, Mapping) or set(artifact) != {
            "path", "sha256", "size_bytes", "schema_id"
        }:
            raise T092CanaryError("T092 canary arm artifact binding is malformed")
        path, digest, size, schema = (
            artifact["path"], artifact["sha256"], artifact["size_bytes"], artifact["schema_id"]
        )
        if (
            not isinstance(path, str) or not path
            or not isinstance(digest, str) or len(digest) != 64
            or any(character not in "0123456789abcdef" for character in digest)
            or isinstance(size, bool) or not isinstance(size, int) or size <= 0
            or schema != T092_CANARY_ARM_RECORD_SCHEMA_ID
        ):
            raise T092CanaryError("T092 canary arm artifact identity is invalid")
        artifact_paths.add(path)
        artifact_hashes.add(digest)
    if len(artifact_paths) != 2 or len(artifact_hashes) != 2:
        raise T092CanaryError("T092 canary arms must retain distinct immutable artifacts")
    off, on = raw.get("off"), raw.get("on")
    if not isinstance(off, Mapping) or not isinstance(on, Mapping):
        raise T092CanaryError("T092 canary pair lacks OFF/ON arms")
    _validate_arm_record(
        off,
        arm="OFF",
        expected_native_identity=T092_PUBLICATION_NATIVE_IDENTITY,
        source=source,
    )
    _validate_arm_record(
        on,
        arm="ON",
        expected_native_identity=T092_NATIVE_IDENTITY,
        source=source,
    )
    if (
        off.get("worker") != raw.get("worker")
        or on.get("worker") != raw.get("worker")
        or off.get("implementation_head") != on.get("implementation_head")
        or off.get("restore_binding") != on.get("restore_binding")
        or off.get("process_identity", {}).get("pid")
        == on.get("process_identity", {}).get("pid")
    ):
        raise T092CanaryError("T092 canary arms are not independently paired")
    off_decisions, on_decisions = off.get("decision_records"), on.get("decision_records")
    if not isinstance(off_decisions, Sequence) or not isinstance(on_decisions, Sequence) or list(off_decisions) != list(on_decisions):
        raise T092CanaryError("INTERNAL_TELEMETRY_SEMANTIC_PARITY_INVALID: root mismatch")
    if off.get("terminal") != on.get("terminal"):
        raise T092CanaryError("INTERNAL_TELEMETRY_SEMANTIC_PARITY_INVALID: terminal mismatch")
    if not isinstance(on.get("internal_occurrences"), Sequence):
        raise T092CanaryError("T092 ON arm lacks internal occurrence retention")
    return dict(raw)


def _validate_arm_record(
    arm_record: Mapping[str, Any], *, arm: str,
    expected_native_identity: Mapping[str, Any], source: T090SplitEntry,
) -> None:
    required = {
        "schema_id",
        "schema_version",
        "task_id",
        "arm",
        "source_identity",
        "source_group",
        "split",
        "canonical_position",
        "restore_binding",
        "implementation_head",
        "native_identity",
        "native_binary",
        "native_api",
        "teacher_config",
        "process_identity",
        "worker",
        "restore_method",
        "restored_snapshot_present",
        "restore_public_legal_parity",
        "decision_records",
        "terminal",
        "internal_occurrences",
        "cost",
    }
    if set(arm_record) != required:
        raise T092CanaryError(f"T092 {arm} arm fields are incomplete")
    expected_api = T092_NATIVE_API if arm == "ON" else BATTLE_SEARCH_V2_NATIVE_API
    if (
        arm_record.get("schema_id") != T092_CANARY_ARM_RECORD_SCHEMA_ID
        or arm_record.get("schema_version") != 1
        or arm_record.get("task_id") != "T092"
        or arm_record.get("arm") != arm
        or arm_record.get("source_identity") != source.source_identity
        or arm_record.get("source_group") != source.source_group
        or arm_record.get("split") != source.split
        or arm_record.get("canonical_position") != source.canonical_position
        or arm_record.get("native_identity") != expected_native_identity
        or arm_record.get("native_api") != expected_api
        or arm_record.get("teacher_config") != T092_FROZEN_TEACHER_CONFIG
        or arm_record.get("restored_snapshot_present") is not True
        or arm_record.get("restore_public_legal_parity") is not True
        or not isinstance(arm_record.get("restore_method"), str)
        or not arm_record.get("restore_method")
    ):
        raise T092CanaryError(f"T092 {arm} arm provenance/restore parity is invalid")
    implementation_head = arm_record.get("implementation_head")
    if (
        not isinstance(implementation_head, str)
        or len(implementation_head) != 40
        or any(character not in "0123456789abcdef" for character in implementation_head)
    ):
        raise T092CanaryError(f"T092 {arm} arm implementation identity is invalid")
    restore = arm_record.get("restore_binding")
    if not isinstance(restore, Mapping) or set(restore) != {
        "selection_identity", "source_checkpoint_id", "source_run_identity",
        "source_seed", "source_battle_index",
    } or restore.get("selection_identity") != source.source_identity:
        raise T092CanaryError(f"T092 {arm} arm restore binding is invalid")
    if (
        not isinstance(restore.get("source_checkpoint_id"), str)
        or not restore["source_checkpoint_id"]
        or not isinstance(restore.get("source_run_identity"), str)
        or not restore["source_run_identity"]
        or isinstance(restore.get("source_seed"), bool)
        or not isinstance(restore.get("source_seed"), int)
        or isinstance(restore.get("source_battle_index"), bool)
        or not isinstance(restore.get("source_battle_index"), int)
        or restore["source_battle_index"] < 0
    ):
        raise T092CanaryError(f"T092 {arm} arm restore binding is malformed")
    binary = arm_record.get("native_binary")
    if not isinstance(binary, Mapping) or set(binary) != {"path", "sha256", "size_bytes"}:
        raise T092CanaryError(f"T092 {arm} arm binary provenance is invalid")
    if (
        not isinstance(binary.get("path"), str) or not binary["path"]
        or not isinstance(binary.get("sha256"), str) or len(binary["sha256"]) != 64
        or any(character not in "0123456789abcdef" for character in binary["sha256"])
        or isinstance(binary.get("size_bytes"), bool)
        or not isinstance(binary.get("size_bytes"), int) or binary["size_bytes"] <= 0
    ):
        raise T092CanaryError(f"T092 {arm} arm binary provenance is malformed")
    process = arm_record.get("process_identity")
    if not isinstance(process, Mapping) or set(process) != {"pid", "python_executable"}:
        raise T092CanaryError(f"T092 {arm} arm process identity is invalid")
    if (
        isinstance(process.get("pid"), bool) or not isinstance(process.get("pid"), int)
        or process["pid"] <= 0 or not isinstance(process.get("python_executable"), str)
        or not process["python_executable"]
    ):
        raise T092CanaryError(f"T092 {arm} arm process identity is malformed")
    _validate_worker(arm_record["worker"])
    decisions = arm_record.get("decision_records")
    if not isinstance(decisions, Sequence) or isinstance(decisions, (str, bytes)) or not decisions:
        raise T092CanaryError(f"T092 {arm} arm decision records are unavailable")
    for item in decisions:
        if not isinstance(item, Mapping) or set(item) != {"decision_identity", "root_semantics"}:
            raise T092CanaryError(f"T092 {arm} arm decision record is malformed")
        decision_identity = item["decision_identity"]
        if not isinstance(decision_identity, str) or not decision_identity:
            raise T092CanaryError(f"T092 {arm} arm decision identity is invalid")
        _validate_root_semantics(item["root_semantics"], arm=arm)
    terminal = arm_record.get("terminal")
    if not isinstance(terminal, Mapping) or set(terminal) != {
        "outcome", "terminal_current_hp", "battle_decision_count"
    }:
        raise T092CanaryError(f"T092 {arm} arm terminal evidence is malformed")
    if not isinstance(terminal["outcome"], str) or not terminal["outcome"]:
        raise T092CanaryError(f"T092 {arm} arm terminal outcome is unavailable")
    if isinstance(terminal["battle_decision_count"], bool) or not isinstance(terminal["battle_decision_count"], int) or terminal["battle_decision_count"] <= 0:
        raise T092CanaryError(f"T092 {arm} arm terminal decision count is invalid")
    if len(decisions) != terminal["battle_decision_count"]:
        raise T092CanaryError(f"T092 {arm} arm terminal decision count disagrees with records")
    hp = terminal["terminal_current_hp"]
    if hp is not None and (isinstance(hp, bool) or not isinstance(hp, (int, float))):
        raise T092CanaryError(f"T092 {arm} arm terminal HP is invalid")
    cost = arm_record.get("cost")
    if not isinstance(cost, Mapping) or set(cost) != {"wall_clock_time_s"}:
        raise T092CanaryError(f"T092 {arm} arm cost fields are invalid")
    wall = cost["wall_clock_time_s"]
    if (
        isinstance(wall, bool)
        or not isinstance(wall, (int, float))
        or not math.isfinite(float(wall))
        or wall < 0
    ):
        raise T092CanaryError(f"T092 {arm} arm wall-clock cost is invalid")
    occurrences = arm_record.get("internal_occurrences")
    if not isinstance(occurrences, Sequence) or isinstance(occurrences, (str, bytes)):
        raise T092CanaryError(f"T092 {arm} arm occurrence payload is invalid")
    if arm == "OFF" and occurrences:
        raise T092CanaryError("T092 OFF arm must not retain internal telemetry rows")
    if arm == "ON":
        decision_ids = {
            str(item["decision_identity"])
            for item in decisions
            if isinstance(item, Mapping)
        }
        validated_occurrences = []
        for raw in occurrences:
            if not isinstance(raw, Mapping):
                raise T092CanaryError("T092 ON arm occurrence is malformed")
            try:
                occurrence = validate_retained_occurrence(
                    raw,
                    source_identity=source.source_identity,
                    source_group=source.source_group,
                    split=source.split,
                    parent_root_decision_identities=decision_ids,
                )
            except T092Incomplete as exc:
                raise T092CanaryError(
                    "T092 ON arm occurrence violates retained schema/firewall"
                ) from exc
            validated_occurrences.append(occurrence)
        try:
            validate_parent_bound_occurrence_identities(validated_occurrences)
        except T092Incomplete as exc:
            raise T092CanaryError(
                "T092 ON arm parent-bound occurrence identity is duplicate"
            ) from exc


def _validate_root_semantics(value: object, *, arm: str) -> None:
    """Retain only the exact root-parity envelope emitted by this runner."""

    if not isinstance(value, Mapping) or set(value) != {
        "ordered_root_actions",
        "root_visits",
        "native_simulator_steps",
        "best_action_value",
        "min_action_value",
        "outcome_player_hp",
        "selected_action_identity",
        "selection_rule",
    }:
        raise T092CanaryError(f"T092 {arm} arm root semantic evidence is malformed")
    actions = value["ordered_root_actions"]
    if (
        not isinstance(actions, Sequence)
        or isinstance(actions, (str, bytes))
        or not actions
    ):
        raise T092CanaryError(f"T092 {arm} arm root actions are malformed")
    action_identities: list[Mapping[str, Any]] = []
    for action in actions:
        if not isinstance(action, Mapping) or set(action) != {
            "action_identity", "visits", "evaluation_sum", "mean_value"
        }:
            raise T092CanaryError(f"T092 {arm} arm root action evidence is malformed")
        identity = action["action_identity"]
        visits, evaluation_sum, mean_value = (
            action["visits"],
            action["evaluation_sum"],
            action["mean_value"],
        )
        if (
            not isinstance(identity, Mapping)
            or not identity
            or isinstance(visits, bool)
            or not isinstance(visits, int)
            or visits < 0
            or (
                evaluation_sum is not None
                and (
                    isinstance(evaluation_sum, bool)
                    or not isinstance(evaluation_sum, (int, float))
                    or not math.isfinite(float(evaluation_sum))
                )
            )
            or (visits == 0 and mean_value is not None)
            or (
                visits > 0
                and (
                    isinstance(mean_value, bool)
                    or not isinstance(mean_value, (int, float))
                    or not math.isfinite(float(mean_value))
                )
            )
        ):
            raise T092CanaryError(f"T092 {arm} arm root action values are invalid")
        action_identities.append(identity)
    if (
        isinstance(value["root_visits"], bool)
        or not isinstance(value["root_visits"], int)
        or value["root_visits"] < 0
        or isinstance(value["native_simulator_steps"], bool)
        or not isinstance(value["native_simulator_steps"], int)
        or value["native_simulator_steps"] < 0
    ):
        raise T092CanaryError(f"T092 {arm} arm root counters are invalid")
    for key in ("best_action_value", "min_action_value", "outcome_player_hp"):
        scalar = value[key]
        if scalar is not None and (
            isinstance(scalar, bool)
            or not isinstance(scalar, (int, float))
            or not math.isfinite(float(scalar))
        ):
            raise T092CanaryError(f"T092 {arm} arm root scalar {key} is invalid")
    selected = value["selected_action_identity"]
    if (
        value["selection_rule"] != "highest_mean"
        or not isinstance(selected, Mapping)
        or not selected
        or not any(dict(selected) == dict(identity) for identity in action_identities)
    ):
        raise T092CanaryError(f"T092 {arm} arm root selection evidence is invalid")


__all__ = [
    "T092_CANARY_EVIDENCE_SCHEMA_ID",
    "T092_CANARY_ARM_RECORD_SCHEMA_ID",
    "T092_CANARY_PLAN_SCHEMA_ID",
    "T092_CANARY_START_COUNT",
    "T092CanaryArmController",
    "T092CanaryError",
    "run_t092_native_canary_arm",
    "build_t092_canary_plan",
    "execute_t092_canary",
    "select_t092_canary_entries",
    "validate_t092_canary_evidence",
]
