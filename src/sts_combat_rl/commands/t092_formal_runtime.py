"""Pinned ON-only runtime recipe for an authorized T092 formal shard.

The formal restore payload is an immutable, per-shard private artifact prepared
from accepted T087/T090 records.  This module validates its hash-bound identity
before it asks the existing isolated-arm boundary to construct a simulator.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import asdict
from pathlib import Path
from typing import Any

from sts_combat_rl.sim.battle_start_pool import record_from_manifest, record_to_manifest
from sts_combat_rl.t085_corrected_leaf_value_search_evaluation import T085BattleStartRecord
from sts_combat_rl.sim.t090_battle_student import T090SplitEntry, validate_t090_split_manifest
from sts_combat_rl.sim.t092_canary_process import T092CanaryProcessError, execute_t092_isolated_arm

T092_FORMAL_RESTORE_SHARD_SCHEMA_ID = "t092-formal-restore-shard-input-v1"
T092_FORMAL_RESTORE_MANIFEST_SCHEMA_ID = "t092-formal-restore-input-manifest-v1"


def build_t092_formal_restore_payloads(
    *, implementation_head: str, upstream_identities: Mapping[str, Any]
) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    """One-time native-free admission of all accepted T087/T090 restores.

    Callers write each returned source payload separately.  This deliberately
    does not construct Search or a simulator, and later workers never repeat
    this large admission or deserialize another worker's checkpoints.
    """
    from sts_combat_rl.commands.t088_canary import _admit_t088_canary_inputs_from_paths
    from sts_combat_rl.commands.t092_canary_runtime import (
        T092_A_POOL_PATH, T092_B_ROOT, T092_C_ROOT, T092_T085_RESTORE_PATH,
        T092_T085_SELECTION_PATH, T092_T087_FORMAL_PATH, T092_T087_REPORT_PATH,
        T092_T087_RETENTION_PATH, _read_split,
    )
    if not isinstance(implementation_head, str) or len(implementation_head) != 40:
        raise T092CanaryProcessError("T092 formal implementation head is invalid")
    required_upstream = {"t087_source_cohort", "t090_source_ledger", "t091_reference", "task_native_provenance"}
    if not isinstance(upstream_identities, Mapping) or set(upstream_identities) != required_upstream:
        raise T092CanaryProcessError("T092 formal upstream artifact identities are incomplete")
    for key, value in upstream_identities.items():
        if not isinstance(value, Mapping) or set(value) != {"path", "sha256", "size_bytes", "schema_id"}:
            raise T092CanaryProcessError("T092 formal upstream artifact identity is malformed")
        try:
            raw = Path(str(value["path"])).read_bytes()
        except OSError as exc:
            raise T092CanaryProcessError("T092 formal upstream artifact is unavailable") from exc
        if hashlib.sha256(raw).hexdigest() != value.get("sha256") or len(raw) != value.get("size_bytes"):
            raise T092CanaryProcessError("T092 formal upstream artifact hash mismatches")
    split = _read_split()
    try:
        _formal, gate, _upstream = _admit_t088_canary_inputs_from_paths(
            implementation_head=implementation_head, t087_formal_path=T092_T087_FORMAL_PATH,
            t087_report_path=T092_T087_REPORT_PATH, t087_retention_path=T092_T087_RETENTION_PATH,
            t085_selection_path=T092_T085_SELECTION_PATH, t085_restore_path=T092_T085_RESTORE_PATH,
            a_pool_path=T092_A_POOL_PATH, b_pool_path=T092_B_ROOT / "cohort-b-merged.pool.jsonl",
            c_pool_path=T092_C_ROOT / "cohort-c-merged.pool.jsonl",
            b_source_manifest_path=T092_B_ROOT / "cohort-b-source-manifest.json",
            c_source_manifest_path=T092_C_ROOT / "cohort-c-source-manifest.json")
    except (OSError, ValueError) as exc:
        raise T092CanaryProcessError("T092 formal accepted restore inputs are unavailable") from exc
    entries = tuple(validate_t090_split_manifest(split))
    if len(entries) != 413:
        raise T092CanaryProcessError("T092 formal source selection is not 413 starts")
    payloads: dict[str, dict[str, Any]] = {}
    for entry in entries:
        selected = next((row for row in gate.cohorts[entry.source_group] if row.selection_identity == entry.source_identity), None)
        canonical = gate.canonical_records_by_cohort[entry.source_group].get(entry.source_identity)
        if selected is None or canonical is None:
            raise T092CanaryProcessError("T092 formal source lacks an accepted restore map")
        payloads[entry.source_identity] = {
            "schema_id": T092_FORMAL_RESTORE_SHARD_SCHEMA_ID, "schema_version": 1, "task_id": "T092",
            "implementation_head": implementation_head, "source": asdict(entry),
            "source_record": asdict(selected), "canonical_record": record_to_manifest(canonical),
        }
    return {
        "schema_id": T092_FORMAL_RESTORE_MANIFEST_SCHEMA_ID,
        "schema_version": 1,
        "task_id": "T092",
        "implementation_head": implementation_head,
        "sources": {},
        **dict(upstream_identities),
    }, payloads


def _reference(value: object, *, schema_id: str = T092_FORMAL_RESTORE_SHARD_SCHEMA_ID) -> dict[str, Any]:
    if not isinstance(value, Mapping) or set(value) != {"path", "sha256", "size_bytes", "schema_id"}:
        raise T092CanaryProcessError("T092 formal restore-shard reference is malformed")
    result = dict(value)
    if result.get("schema_id") != schema_id:
        raise T092CanaryProcessError("T092 formal restore-shard schema is invalid")
    return result


class _FormalRunner:
    def __init__(self, *, specs: Mapping[str, Any], shard_references: Mapping[str, Mapping[str, Any]],
                 implementation_head: str, output_root: Path) -> None:
        if not isinstance(specs, Mapping) or set(specs) != {"ON"}:
            raise T092CanaryProcessError("T092 formal runtime requires exactly one ON native specification")
        self._spec = specs["ON"]
        self._shard_references = dict(shard_references)
        self._head = implementation_head
        self._root = output_root.resolve()

    def __call__(self, source: Mapping[str, Any], worker: Mapping[str, Any]) -> Mapping[str, Any]:
        entry = T090SplitEntry(**dict(source))
        ref = self._shard_references.get(entry.source_identity)
        if ref is None:
            raise T092CanaryProcessError("T092 formal source lacks a hash-bound restore record")
        try:
            raw = Path(str(ref["path"])).read_bytes()
            payload = json.loads(raw)
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise T092CanaryProcessError("T092 formal restore shard is unavailable") from exc
        if not isinstance(payload, Mapping) or hashlib.sha256(raw).hexdigest() != ref.get("sha256") or len(raw) != ref.get("size_bytes"):
            raise T092CanaryProcessError("T092 formal restore shard hash mismatches")
        required = {"schema_id", "schema_version", "task_id", "implementation_head", "source", "source_record", "canonical_record"}
        if set(payload) != required or payload.get("schema_id") != T092_FORMAL_RESTORE_SHARD_SCHEMA_ID or payload.get("schema_version") != 1 or payload.get("task_id") != "T092" or payload.get("implementation_head") != self._head or payload.get("source") != asdict(entry):
            raise T092CanaryProcessError("T092 formal restore shard provenance is malformed")
        try:
            selected = T085BattleStartRecord.from_mapping(payload["source_record"])
            canonical = record_from_manifest(payload["canonical_record"], label="T092 formal canonical checkpoint", allowed_distribution_kinds=frozenset({"natural_run", "assisted_run"}), allow_assistance_history=True)
        except (KeyError, TypeError, ValueError) as exc:
            raise T092CanaryProcessError("T092 formal restore shard is malformed") from exc
        if selected.selection_identity != entry.source_identity or canonical.source_checkpoint_id != entry.source_identity:
            raise T092CanaryProcessError("T092 formal restore identity mismatches")
        digest = hashlib.sha256(entry.source_identity.encode("utf-8")).hexdigest()[:16]
        record, _artifact = execute_t092_isolated_arm(arm="ON", spec=self._spec, source=entry,
            selected=selected, canonical=canonical, worker=worker, implementation_head=self._head,
            output_path=self._root / "formal-arms" / f"shard-{worker['shard_index']}-{digest}-on.json")
        return record


def t092_formal_runtime(*, input_identities: Mapping[str, Any], implementation_head: str, output_root: Path) -> _FormalRunner:
    """Load only this worker's retained restore payload, never the 413 corpus."""
    required_inputs = {"formal_restore_manifest", "arm_process_specs", "t087_source_cohort",
                       "t090_source_ledger", "t091_reference", "task_native_provenance"}
    if not isinstance(input_identities, Mapping) or set(input_identities) != required_inputs:
        raise T092CanaryProcessError("T092 formal runtime input identity is incomplete")
    ref = _reference(input_identities["formal_restore_manifest"], schema_id=T092_FORMAL_RESTORE_MANIFEST_SCHEMA_ID)
    try:
        raw = Path(str(ref["path"])).read_bytes()
        payload = json.loads(raw)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise T092CanaryProcessError("T092 formal restore-shard payload is unavailable") from exc
    if not isinstance(payload, Mapping) or hashlib.sha256(raw).hexdigest() != ref.get("sha256") or len(raw) != ref.get("size_bytes"):
        raise T092CanaryProcessError("T092 formal restore-shard hash mismatches")
    required = {"schema_id", "schema_version", "task_id", "implementation_head", "sources",
                "t087_source_cohort", "t090_source_ledger", "t091_reference", "task_native_provenance"}
    if set(payload) != required or payload.get("schema_id") != T092_FORMAL_RESTORE_MANIFEST_SCHEMA_ID or payload.get("schema_version") != 1 or payload.get("task_id") != "T092" or payload.get("implementation_head") != implementation_head or not isinstance(payload.get("sources"), Mapping):
        raise T092CanaryProcessError("T092 formal restore manifest is malformed")
    for key in ("t087_source_cohort", "t090_source_ledger", "t091_reference", "task_native_provenance"):
        if payload.get(key) != input_identities.get(key):
            raise T092CanaryProcessError("T092 formal restore manifest upstream identity mismatches")
    references: dict[str, Mapping[str, Any]] = {}
    for source_id, item in payload["sources"].items():
        if not isinstance(source_id, str) or not source_id:
            raise T092CanaryProcessError("T092 formal restore source identity is invalid")
        references[source_id] = _reference(item)
    specs = input_identities["arm_process_specs"]
    return _FormalRunner(specs=specs, shard_references=references,
        implementation_head=implementation_head, output_root=output_root)
