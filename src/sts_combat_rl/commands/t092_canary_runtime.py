"""Pinned, native-free T092 canary restore-map recipe.

The callable is imported only after a real Maintainer authorization has been
validated by :mod:`t092_canary_execution`.  It admits the existing T087/T085
artifacts through their established verifier, projects the immutable T090
ledger, and returns no adapter or native module object.  Each actual arm is
subsequently created in a fresh child process by the isolated runner.
"""

from __future__ import annotations

import hashlib
import json
import math
import resource
import time
from collections.abc import Mapping
from dataclasses import asdict
from pathlib import Path
from typing import Any

from sts_combat_rl.commands.t088_canary import _admit_t088_canary_inputs_from_paths
from sts_combat_rl.sim.battle_start_pool import record_from_manifest, record_to_manifest
from sts_combat_rl.sim.t090_battle_student import canonical_sha256, validate_t090_split_manifest
from sts_combat_rl.sim.t092_canary import select_t092_canary_entries
from sts_combat_rl.sim.t092_canary_process import T092CanaryProcessError
from sts_combat_rl.t085_corrected_leaf_value_search_evaluation import (
    T085BattleStartRecord,
)

T092_SHARED_ARTIFACT_ROOT = Path("/mnt/d/DeadlyCatCoding/STSRL/artifacts")
T092_SPLIT_MANIFEST_PATH = T092_SHARED_ARTIFACT_ROOT / "t090-formal-413-2bfcb27-20260915-retry1/t090-split-manifest.json"
T092_T087_FORMAL_PATH = T092_SHARED_ARTIFACT_ROOT / "t087-formal-natural-413-8d7e44-20260911/t087-formal-natural-evidence.json"
T092_T087_REPORT_PATH = T092_SHARED_ARTIFACT_ROOT / "t087-final-8d7e44-20260911/t087-dense-combat-diagnostics-report.json"
T092_T087_RETENTION_PATH = T092_SHARED_ARTIFACT_ROOT / "t087-final-8d7e44-20260911/t087-retention-manifest.json"
T092_T085_ROOT = T092_SHARED_ARTIFACT_ROOT / "t085-corrected-leaf-value-search-repair"
T092_T085_SELECTION_PATH = T092_T085_ROOT / "selection/t085-native-selection.json"
T092_T085_RESTORE_PATH = T092_T085_ROOT / "selection/t085-native-selection-restore-evidence.json"
T092_A_POOL_PATH = Path("/mnt/d/DeadlyCatCoding/STSRL/artifacts/t052-t051-boss-later-act-fixed-cohort-diagnostic-pr/t052-fixed-cohort.jsonl")
T092_B_ROOT = T092_T085_ROOT / "source/cohort-b-formal-d62ff35579b54d70a7428afdf84743c94df3fe0c"
T092_C_ROOT = T092_T085_ROOT / "source/cohort-c-formal-d62ff35579b54d70a7428afdf84743c94df3fe0c"

T092_CANARY_ARM_PROCESS_SPECS = {
    "OFF": {
        "python_executable": "/usr/bin/python3.14",
        "extension_path": "/home/lsmft/stsrl-spikes/sts_lightspeed-t088-20a6/build-py/slaythespire.cpython-314-x86_64-linux-gnu.so",
        "extension_sha256": "b996f949e77b3d76a3991c4e24977c80722f0e09e1e0f235384a4158ee6351bb",
        "extension_size_bytes": 1632040,
        "native_identity": {
            "repository": "lsmfttb/sts_lightspeed", "ref": "refs/heads/stsrl/main",
            "commit": "20a6c2b3a9cea817c988178b814f083ff889853f",
        },
        "stsrl_source_root": "/mnt/d/DeadlyCatCoding/STSRL-T092",
    },
    "ON": {
        "python_executable": "/usr/bin/python3.14",
        "extension_path": "/mnt/d/DeadlyCatCoding/sts_lightspeed-T092/build-t092-py/slaythespire.cpython-314-x86_64-linux-gnu.so",
        "extension_sha256": "1deacad6192e48ab0dd6a63abd7b40d20e226311db7dcc4234e0038df79f6ccb",
        "extension_size_bytes": 1648424,
        "native_identity": {
            "repository": "lsmfttb/sts_lightspeed", "ref": "refs/heads/planner/t092-internal-search-state-telemetry",
            "commit": "a439c70b568eab78dea42fe857dab56fa27cda3f",
        },
        "stsrl_source_root": "/mnt/d/DeadlyCatCoding/STSRL-T092",
    },
}

T092_COMPACT_RESTORE_INPUTS_SCHEMA_ID = "t092-selected-restore-inputs-v1"


def t092_canary_runtime_input_identities() -> Mapping[str, Any]:
    """Return the reviewable, canonical identity map without loading a pool."""

    path = Path(__file__).resolve().parents[3] / "docs/t092_canary_runtime_identity_map.json"
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise T092CanaryProcessError("T092 runtime identity map is unavailable") from exc
    if (
        not isinstance(value, Mapping)
        or value.get("schema_id") != "t092-canary-runtime-input-identities-v3"
        or value.get("schema_version") != 3
        or value.get("task_id") != "T092"
        or value.get("execution_authorized") is not False
        or value.get("runtime_factory")
        != "sts_combat_rl.commands.t092_canary_runtime:t092_canary_runtime"
        or value.get("compact_restore_input_schema_id")
        != T092_COMPACT_RESTORE_INPUTS_SCHEMA_ID
    ):
        raise T092CanaryProcessError("T092 runtime identity map is malformed")
    return dict(value)


def _read_split() -> Mapping[str, Any]:
    try:
        split = json.loads(T092_SPLIT_MANIFEST_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise T092CanaryProcessError("T092 split manifest is unavailable") from exc
    if not isinstance(split, Mapping):
        raise T092CanaryProcessError("T092 split manifest is malformed")
    try:
        validate_t090_split_manifest(split)
    except ValueError as exc:
        raise T092CanaryProcessError("T092 split manifest is invalid") from exc
    return split


def build_t092_compact_restore_inputs(*, implementation_head: str) -> dict[str, Any]:
    """Admit large accepted inputs once and retain only the selected twelve.

    This is a native-free, explicit one-time preparation step.  The resulting
    private restore payload is hash-bound before any authorized arm worker is
    started, so 12 workers never independently parse the T087/T085 corpus.
    """

    started = time.perf_counter()
    try:
        if not isinstance(implementation_head, str) or len(implementation_head) != 40:
            raise ValueError("implementation head is invalid")
        split = _read_split()
        _formal, gate, identities = _admit_t088_canary_inputs_from_paths(
            implementation_head=implementation_head,
            t087_formal_path=T092_T087_FORMAL_PATH,
            t087_report_path=T092_T087_REPORT_PATH,
            t087_retention_path=T092_T087_RETENTION_PATH,
            t085_selection_path=T092_T085_SELECTION_PATH,
            t085_restore_path=T092_T085_RESTORE_PATH,
            a_pool_path=T092_A_POOL_PATH,
            b_pool_path=T092_B_ROOT / "cohort-b-merged.pool.jsonl",
            c_pool_path=T092_C_ROOT / "cohort-c-merged.pool.jsonl",
            b_source_manifest_path=T092_B_ROOT / "cohort-b-source-manifest.json",
            c_source_manifest_path=T092_C_ROOT / "cohort-c-source-manifest.json",
        )
    except (OSError, ValueError) as exc:
        raise T092CanaryProcessError("T092 accepted restore maps are unavailable") from exc
    source_records: dict[str, dict[str, Any]] = {}
    canonical_records: dict[str, dict[str, Any]] = {}
    for source in select_t092_canary_entries(split):
        cohort = source.source_group
        selected = next(
            (row for row in gate.cohorts[cohort] if row.selection_identity == source.source_identity),
            None,
        )
        canonical = gate.canonical_records_by_cohort[cohort].get(source.source_identity)
        if selected is None or canonical is None:
            raise T092CanaryProcessError("T092 selected source lacks an accepted restore map")
        source_records[source.source_identity] = asdict(selected)
        canonical_records[source.source_identity] = record_to_manifest(canonical)
    if len(source_records) != 12 or set(source_records) != set(canonical_records):
        raise T092CanaryProcessError("T092 canary restore maps are incomplete")
    return {
        "schema_id": T092_COMPACT_RESTORE_INPUTS_SCHEMA_ID,
        "schema_version": 1,
        "task_id": "T092",
        "implementation_head": implementation_head,
        "split_manifest_sha256": canonical_sha256(split),
        "accepted_input_identities": identities,
        "selected_sources": [asdict(source) for source in select_t092_canary_entries(split)],
        "source_records": source_records,
        "canonical_records": canonical_records,
        "admission_cost": {
            "wall_clock_time_s": time.perf_counter() - started,
            "max_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024,
        },
    }


def build_t092_runtime_input_identities(
    compact_reference: Mapping[str, Any],
) -> dict[str, Any]:
    """Bind an immutable compact payload into the future authorization map."""

    baseline = dict(t092_canary_runtime_input_identities())
    if not isinstance(compact_reference, Mapping) or set(compact_reference) != {
        "path", "sha256", "size_bytes", "schema_id"
    } or compact_reference.get("schema_id") != T092_COMPACT_RESTORE_INPUTS_SCHEMA_ID:
        raise T092CanaryProcessError("T092 compact restore artifact identity is invalid")
    baseline["compact_restore_inputs"] = dict(compact_reference)
    return baseline


def _validate_compact_restore_inputs(
    payload: Mapping[str, Any], *, implementation_head: str | None = None,
) -> tuple[dict[str, T085BattleStartRecord], dict[str, object]]:
    required = {
        "schema_id", "schema_version", "task_id", "implementation_head",
        "split_manifest_sha256", "accepted_input_identities", "selected_sources",
        "source_records", "canonical_records", "admission_cost",
    }
    if set(payload) != required or (
        payload.get("schema_id") != T092_COMPACT_RESTORE_INPUTS_SCHEMA_ID
        or payload.get("schema_version") != 1
        or payload.get("task_id") != "T092"
        or not isinstance(payload.get("implementation_head"), str)
        or len(payload["implementation_head"]) != 40
        or (
            implementation_head is not None
            and payload.get("implementation_head") != implementation_head
        )
        or not isinstance(payload.get("selected_sources"), list)
        or not isinstance(payload.get("source_records"), Mapping)
        or not isinstance(payload.get("canonical_records"), Mapping)
        or not isinstance(payload.get("admission_cost"), Mapping)
    ):
        raise T092CanaryProcessError("T092 compact restore artifact is malformed")
    cost = payload["admission_cost"]
    if (
        set(cost) != {"wall_clock_time_s", "max_rss_bytes"}
        or isinstance(cost.get("wall_clock_time_s"), bool)
        or not isinstance(cost.get("wall_clock_time_s"), (int, float))
        or not math.isfinite(float(cost["wall_clock_time_s"]))
        or cost["wall_clock_time_s"] < 0
        or isinstance(cost.get("max_rss_bytes"), bool)
        or not isinstance(cost.get("max_rss_bytes"), int)
        or cost["max_rss_bytes"] <= 0
    ):
        raise T092CanaryProcessError("T092 compact admission cost is invalid")
    split = _read_split()
    selected = select_t092_canary_entries(split)
    if (
        payload["split_manifest_sha256"] != canonical_sha256(split)
        or payload["selected_sources"] != [asdict(item) for item in selected]
        or set(payload["source_records"]) != {item.source_identity for item in selected}
        or set(payload["canonical_records"]) != set(payload["source_records"])
    ):
        raise T092CanaryProcessError("T092 compact restore selection binding is invalid")
    source_records: dict[str, T085BattleStartRecord] = {}
    canonical_records: dict[str, object] = {}
    for source in selected:
        raw_source = payload["source_records"][source.source_identity]
        raw_canonical = payload["canonical_records"][source.source_identity]
        if not isinstance(raw_source, Mapping) or not isinstance(raw_canonical, Mapping):
            raise T092CanaryProcessError("T092 compact restore record is malformed")
        try:
            source_record = T085BattleStartRecord.from_mapping(raw_source)
            canonical = record_from_manifest(
                raw_canonical,
                label="T092 compact canonical checkpoint",
                allowed_distribution_kinds=frozenset({"natural_run", "assisted_run"}),
                allow_assistance_history=True,
            )
        except ValueError as exc:
            raise T092CanaryProcessError("T092 compact restore record is invalid") from exc
        if (
            source_record.selection_identity != source.source_identity
            or canonical.source_checkpoint_id != source.source_identity
            or canonical.source_run_id != source_record.source_run_identity
            or canonical.source_seed != source_record.source_run_seed
        ):
            raise T092CanaryProcessError("T092 compact source/restore identity mismatches")
        source_records[source.source_identity] = source_record
        canonical_records[source.source_identity] = canonical
    return source_records, canonical_records


def validate_t092_runtime_input_identities(
    identities: Mapping[str, Any], *, implementation_head: str | None = None,
) -> tuple[dict[str, T085BattleStartRecord], dict[str, object]]:
    """Validate the dynamic compact reference and deserialize only 12 records."""

    baseline = dict(t092_canary_runtime_input_identities())
    if not isinstance(identities, Mapping) or set(identities) != {
        *baseline.keys(), "compact_restore_inputs"
    }:
        raise T092CanaryProcessError("T092 runtime input identities are incomplete")
    for key, value in baseline.items():
        if identities.get(key) != value:
            raise T092CanaryProcessError("T092 runtime input identity map drifted")
    compact = identities["compact_restore_inputs"]
    if not isinstance(compact, Mapping) or set(compact) != {
        "path", "sha256", "size_bytes", "schema_id"
    } or compact.get("schema_id") != T092_COMPACT_RESTORE_INPUTS_SCHEMA_ID:
        raise T092CanaryProcessError("T092 compact restore input reference is invalid")
    path = Path(str(compact["path"])).resolve()
    try:
        raw = path.read_bytes()
        payload = json.loads(raw)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise T092CanaryProcessError("T092 compact restore input is unavailable") from exc
    if (
        not isinstance(compact.get("sha256"), str)
        or hashlib.sha256(raw).hexdigest() != compact["sha256"]
        or len(raw) != compact.get("size_bytes")
        or not isinstance(payload, Mapping)
    ):
        raise T092CanaryProcessError("T092 compact restore input hash mismatches")
    return _validate_compact_restore_inputs(
        payload, implementation_head=implementation_head
    )


def t092_canary_runtime(
    runtime_input_identities: Mapping[str, Any], implementation_head: str,
) -> Mapping[str, Any]:
    """Return only the hash-bound selected-12 restore maps for one worker."""

    source_records, canonical_records = validate_t092_runtime_input_identities(
        runtime_input_identities, implementation_head=implementation_head
    )
    return {
        "arm_process_specs": T092_CANARY_ARM_PROCESS_SPECS,
        "source_records": source_records,
        "canonical_records": canonical_records,
    }


__all__ = [
    "T092_CANARY_ARM_PROCESS_SPECS", "T092_COMPACT_RESTORE_INPUTS_SCHEMA_ID",
    "build_t092_compact_restore_inputs", "build_t092_runtime_input_identities",
    "t092_canary_runtime", "t092_canary_runtime_input_identities",
    "validate_t092_runtime_input_identities",
]
