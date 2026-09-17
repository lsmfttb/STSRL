"""Fail-closed, authorization-gated T092 formal collection plumbing.

This is deliberately a T092 collector, not a reuse of the T088 tournament.
It consumes the immutable T090 split and root reference, executes one ON-only
telemetry arm per restored start (only after an exact Maintainer authorization),
and aggregates retained shards without ever constructing a simulator itself.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import sqlite3
import tempfile
from array import array
from collections import Counter, defaultdict
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict
from pathlib import Path
from typing import Any

from sts_combat_rl.sim.t090_battle_student import (
    T090Incomplete,
    canonical_sha256,
    validate_t090_source_execution_ledger,
    validate_t090_split_manifest,
)
from sts_combat_rl.sim.t092_canary import (
    T092_CANARY_ARM_RECORD_SCHEMA_ID,
    T092_CANARY_EXECUTION_CONFIG,
    T092CanaryError,
    _validate_arm_record,
    validate_t092_canary_evidence,
)
from sts_combat_rl.sim.t092_internal_search_state import (
    T092_FROZEN_TEACHER_CONFIG,
    T092_N_MINS,
    T092_NATIVE_IDENTITY,
    T092Incomplete,
    T092Occurrence,
    support_pairs,
    validate_parent_bound_occurrence_identities,
    validate_retained_occurrence,
)

T092_FORMAL_AUTHORIZATION_SCHEMA_ID = "t092-maintainer-formal-authorization-v1"
T092_FORMAL_PLAN_SCHEMA_ID = "t092-formal-413-plan-v1"
T092_FORMAL_SHARD_SCHEMA_ID = "t092-formal-telemetry-shard-v1"
T092_FORMAL_EVIDENCE_SCHEMA_ID = "t092-formal-telemetry-evidence-v1"
T092_FORMAL_RETENTION_SCHEMA_ID = "t092-formal-retention-manifest-v1"
T092_T090_ROOT_REFERENCE_SCHEMA_ID = "t092-t090-root-reproduction-reference-v1"
T092_FORMAL_SHARD_ASSIGNMENT = "canonical-global-ordinal-modulo-v1"
T092_FORMAL_DEFAULT_WORKERS = 8
T092_FORMAL_DEFAULT_SHARDS = 8


class T092FormalError(T092Incomplete):
    """A formal input, authorization, shard, or report is incomplete."""


def _sha(value: object) -> bool:
    return isinstance(value, str) and len(value) == 40 and all(c in "0123456789abcdef" for c in value)


def _artifact(value: object, label: str) -> dict[str, Any]:
    if not isinstance(value, Mapping) or set(value) != {"path", "sha256", "size_bytes", "schema_id"}:
        raise T092FormalError(f"{label} artifact identity is malformed")
    result = dict(value)
    if (not isinstance(result["path"], str) or not result["path"]
            or not isinstance(result["sha256"], str) or len(result["sha256"]) != 64
            or any(c not in "0123456789abcdef" for c in result["sha256"])
            or isinstance(result["size_bytes"], bool) or not isinstance(result["size_bytes"], int)
            or result["size_bytes"] < 0 or not isinstance(result["schema_id"], str) or not result["schema_id"]):
        raise T092FormalError(f"{label} artifact identity is malformed")
    return result


def _stream_artifact_hash(value: object, label: str) -> dict[str, Any]:
    """Verify an artifact identity without retaining its payload in memory."""

    artifact = _artifact(value, label)
    digest = hashlib.sha256()
    size = 0
    try:
        with Path(artifact["path"]).open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
                size += len(block)
    except OSError as exc:
        raise T092FormalError(f"{label} artifact is unavailable") from exc
    if digest.hexdigest() != artifact["sha256"] or size != artifact["size_bytes"]:
        raise T092FormalError(f"{label} artifact hash mismatches")
    return artifact


def _topology(*, shard_index: int, shard_count: int, worker_count: int) -> dict[str, int | str]:
    if (any(isinstance(x, bool) or not isinstance(x, int) for x in (shard_index, shard_count, worker_count))
            or shard_count <= 0 or worker_count <= 0 or worker_count > shard_count
            or shard_index < 0 or shard_index >= shard_count):
        raise T092FormalError("T092 formal worker topology is invalid")
    return {"shard_index": shard_index, "shard_count": shard_count,
            "worker_count": worker_count, "assignment": T092_FORMAL_SHARD_ASSIGNMENT}


def build_t092_formal_plan(split_manifest: Mapping[str, Any], *, shard_count: int = T092_FORMAL_DEFAULT_SHARDS,
                           worker_count: int = T092_FORMAL_DEFAULT_WORKERS) -> dict[str, Any]:
    """Build the exact no-reselection 413-start plan before any native import."""
    try:
        entries = validate_t090_split_manifest(split_manifest)
    except (TypeError, ValueError) as exc:
        raise T092FormalError("T092 formal split manifest is invalid") from exc
    if len(entries) != 413 or Counter(item.source_group for item in entries) != {"A": 93, "B": 192, "C": 128}:
        raise T092FormalError("T092 formal plan is not the exact 413-start T087/T090 cohort")
    _topology(shard_index=0, shard_count=shard_count, worker_count=worker_count)
    return {
        "schema_id": T092_FORMAL_PLAN_SCHEMA_ID, "schema_version": 1, "task_id": "T092",
        "execution_authorized": False, "split_manifest_sha256": canonical_sha256(split_manifest),
        "teacher_config": dict(T092_FROZEN_TEACHER_CONFIG), "native_identity": dict(T092_NATIVE_IDENTITY),
        "execution_config": dict(T092_CANARY_EXECUTION_CONFIG),
        "worker_plan": {"shard_count": shard_count, "worker_count": worker_count,
                        "assignment": T092_FORMAL_SHARD_ASSIGNMENT,
                        "effective_worker_memory_limit_bytes": 2 * 1024**3,
                        "reason": "8 effective workers: 16GiB aggregate budget / 2GiB per worker"},
        "sources": [asdict(item) for item in entries],
    }


_T092_ROOT_REFERENCE_ARTIFACT_KEYS = {
    "teacher_rows_artifact",
    "decision_provenance_artifact",
}


def _read_artifact_json(value: Mapping[str, Any], label: str) -> Any:
    """Read and hash-check one retained JSON artifact identity."""

    artifact = _artifact(value, label)
    try:
        encoded = Path(artifact["path"]).read_bytes()
        parsed = json.loads(encoded)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise T092FormalError(f"{label} artifact is unavailable") from exc
    if hashlib.sha256(encoded).hexdigest() != artifact["sha256"] or len(encoded) != artifact["size_bytes"]:
        raise T092FormalError(f"{label} artifact hash mismatches")
    return parsed


def _read_t090_source_ledger(
    source_ledger: Mapping[str, Any], *, split_manifest: Mapping[str, Any]
) -> tuple[Mapping[str, Any], ...]:
    """Read the exact T090 ledger and reject duplicate/aliased source refs."""

    payload = _read_artifact_json(source_ledger, "T090 source ledger")
    if (
        not isinstance(payload, Mapping)
        or payload.get("schema_id") != "t090-source-execution-ledger-v1"
        or payload.get("schema_version") != 1
        or payload.get("task_id") != "T090"
        or not isinstance(payload.get("entries"), list)
        or payload.get("entries_sha256") != canonical_sha256(payload["entries"])
    ):
        raise T092FormalError("T090 source ledger payload schema is invalid")
    try:
        validate_t090_source_execution_ledger(payload, split_manifest=split_manifest)
    except (T090Incomplete, TypeError, ValueError) as exc:
        raise T092FormalError("T090 source ledger is incomplete or out of canonical order") from exc
    try:
        split_entries = validate_t090_split_manifest(split_manifest)
    except (TypeError, ValueError) as exc:
        raise T092FormalError("T092 split manifest is invalid") from exc
    split_by_source = {entry.source_identity: entry for entry in split_entries}
    seen_sources: set[str] = set()
    seen_positions: set[int] = set()
    result: list[Mapping[str, Any]] = []
    for entry in payload["entries"]:
        if not isinstance(entry, Mapping):
            raise T092FormalError("T090 source ledger entry is malformed")
        identity = entry.get("source_identity")
        position = entry.get("canonical_position")
        if (
            not isinstance(identity, str)
            or not identity
            or identity != identity.strip()
            or identity in seen_sources
            or isinstance(position, bool)
            or not isinstance(position, int)
        ):
            raise T092FormalError(
                "T090 source ledger contains duplicate or aliased source references"
            )
        expected = split_by_source.get(identity)
        if (
            expected is None
            or entry.get("source_group") != expected.source_group
            or entry.get("split") != expected.split
            or position != expected.canonical_position
        ):
            raise T092FormalError("T090 source ledger provenance disagrees with split")
        seen_sources.add(identity)
        seen_positions.add(position)
        result.append(entry)
    if seen_sources != set(split_by_source) or seen_positions != set(range(len(split_entries))):
        raise T092FormalError("T090 source ledger does not cover the exact split")
    return tuple(result)


def _reject_artifact_aliases(artifacts: Sequence[Mapping[str, Any]], label: str) -> None:
    """Require separate artifact identities, not aliases of one JSON file."""

    paths = {item["path"] for item in artifacts}
    hashes = {item["sha256"] for item in artifacts}
    sizes = {item["size_bytes"] for item in artifacts}
    if len(paths) != len(artifacts) or len(hashes) != len(artifacts) or len(sizes) != len(artifacts):
        raise T092FormalError(f"{label} contains aliased artifact references")


def validate_t092_t090_root_reference(
    value: Mapping[str, Any], *, split_manifest: Mapping[str, Any],
    require_input_artifacts: bool = False, verify_input_artifacts: bool = True,
) -> dict[str, Any]:
    """Require the canonical T090 root table, never inferred rows.

    With required artifacts and ``verify_input_artifacts=False``, the worker
    path still checks every bound file's schema identity, alias separation,
    size, and hash, but streams bytes instead of parsing the large payloads.
    """
    required = {"schema_id", "schema_version", "task_id", "split_manifest_sha256", "source_ledger", "rows", "rows_sha256"}
    allowed = required | _T092_ROOT_REFERENCE_ARTIFACT_KEYS
    if not isinstance(value, Mapping) or not set(value).issubset(allowed) or not required.issubset(value) or value.get("schema_id") != T092_T090_ROOT_REFERENCE_SCHEMA_ID or value.get("schema_version") != 1 or value.get("task_id") != "T092" or value.get("split_manifest_sha256") != canonical_sha256(split_manifest):
        raise T092FormalError("T092 T090 root reference is malformed")
    if require_input_artifacts and not _T092_ROOT_REFERENCE_ARTIFACT_KEYS.issubset(value):
        raise T092FormalError("T092 root reference lacks hash-bound teacher/provenance artifacts")
    source_ledger = _artifact(value.get("source_ledger"), "T090 source ledger")
    if source_ledger["schema_id"] != "t090-source-execution-ledger-v1":
        raise T092FormalError("T090 source ledger schema is not accepted")
    if _T092_ROOT_REFERENCE_ARTIFACT_KEYS.issubset(value):
        teacher_artifact = _artifact(value["teacher_rows_artifact"], "T090 teacher rows")
        provenance_artifact = _artifact(value["decision_provenance_artifact"], "T090 decision provenance")
        if teacher_artifact["schema_id"] != "t090-root-teacher-rows-v1" or provenance_artifact["schema_id"] != "t090-root-decision-provenance-v1":
            raise T092FormalError("T090 root input artifact schemas are invalid")
        _reject_artifact_aliases(
            [source_ledger, teacher_artifact, provenance_artifact],
            "T092 root input",
        )
        if require_input_artifacts and not verify_input_artifacts:
            _stream_artifact_hash(source_ledger, "T090 source ledger")
            _stream_artifact_hash(teacher_artifact, "T090 teacher rows")
            _stream_artifact_hash(provenance_artifact, "T090 decision provenance")
            return _validate_t092_root_rows(value)
        if not verify_input_artifacts:
            return _validate_t092_root_rows(value)
        _read_t090_source_ledger(source_ledger, split_manifest=split_manifest)
        teacher_rows = _read_artifact_json(value["teacher_rows_artifact"], "T090 teacher rows")
        provenance_rows = _read_artifact_json(value["decision_provenance_artifact"], "T090 decision provenance")
        if not isinstance(teacher_rows, list) or not isinstance(provenance_rows, list):
            raise T092FormalError("T090 teacher/provenance artifacts are not JSON arrays")
    return _validate_t092_root_rows(value)


def _validate_t092_root_rows(value: Mapping[str, Any]) -> dict[str, Any]:
    """Validate the bounded canonical root table after input admission."""

    rows = value.get("rows")
    if not isinstance(rows, Sequence) or isinstance(rows, (str, bytes)) or len(rows) != 6369 or value.get("rows_sha256") != canonical_sha256(rows):
        raise T092FormalError("T092 root reference does not retain 6,369 canonical rows")
    seen: set[str] = set()
    multi = s0 = 0
    for row in rows:
        if not isinstance(row, Mapping) or set(row) != {"decision_identity", "ordered_root_actions", "selected_action_identity"}:
            raise T092FormalError("T092 root reference row is malformed")
        decision, actions, selected = row.get("decision_identity"), row.get("ordered_root_actions"), row.get("selected_action_identity")
        if not isinstance(decision, str) or not decision or decision in seen or not isinstance(actions, Sequence) or isinstance(actions, (str, bytes)) or not actions or not isinstance(selected, Mapping):
            raise T092FormalError("T092 root reference row is incomplete")
        seen.add(decision)
        if len(actions) > 1:
            multi += 1
            s0 += int(all(isinstance(a, Mapping) and isinstance(a.get("visits"), int) and a["visits"] > 0 and _finite(a.get("mean_value")) for a in actions))
    if multi != 6210 or len(rows) - multi != 159 or s0 != 309:
        raise T092FormalError("T092 root reference does not reproduce frozen T090 counts")
    return dict(value)


def build_t092_t090_root_reference(
    *, teacher_rows: Sequence[Mapping[str, Any]], decision_provenance: Sequence[Mapping[str, Any]],
    source_ledger: Mapping[str, Any], split_manifest: Mapping[str, Any],
    teacher_rows_artifact: Mapping[str, Any] | None = None,
    decision_provenance_artifact: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Materialize the exact root comparison table from accepted T090 rows."""
    ledger = _artifact(source_ledger, "T090 source ledger")
    if ledger["schema_id"] != "t090-source-execution-ledger-v1":
        raise T092FormalError("T090 source ledger schema is not accepted")
    try:
        split_entries = validate_t090_split_manifest(split_manifest)
    except (TypeError, ValueError) as exc:
        raise T092FormalError("T092 split manifest is invalid") from exc
    split_by_source = {entry.source_identity: entry for entry in split_entries}
    ledger_sources = _read_t090_source_ledger(ledger, split_manifest=split_manifest)
    ledger_by_source = {item["source_identity"]: item for item in ledger_sources}
    root_artifacts: dict[str, dict[str, Any]] = {}
    if (teacher_rows_artifact is None) != (decision_provenance_artifact is None):
        raise T092FormalError("T090 root teacher/provenance artifact identities must be supplied together")
    if teacher_rows_artifact is not None and decision_provenance_artifact is not None:
        teacher_identity = _artifact(teacher_rows_artifact, "T090 teacher rows")
        provenance_identity = _artifact(decision_provenance_artifact, "T090 decision provenance")
        if teacher_identity["schema_id"] != "t090-root-teacher-rows-v1" or provenance_identity["schema_id"] != "t090-root-decision-provenance-v1":
            raise T092FormalError("T090 root input artifact schemas are invalid")
        _reject_artifact_aliases(
            [ledger, teacher_identity, provenance_identity], "T092 root input"
        )
        if _read_artifact_json(teacher_identity, "T090 teacher rows") != list(teacher_rows) or _read_artifact_json(provenance_identity, "T090 decision provenance") != list(decision_provenance):
            raise T092FormalError("T090 root input artifact payload disagrees with loaded rows")
        root_artifacts = {"teacher_rows_artifact": teacher_identity, "decision_provenance_artifact": provenance_identity}
    provenance: dict[str, Mapping[str, Any]] = {}
    for row in decision_provenance:
        if not isinstance(row, Mapping) or not isinstance(row.get("decision_identity"), str) or not row["decision_identity"] or row["decision_identity"] in provenance:
            raise T092FormalError("T090 decision provenance contains duplicate or aliased decision references")
        provenance[row["decision_identity"]] = row
    rows: list[dict[str, Any]] = []
    seen_decisions: set[str] = set()
    for raw in teacher_rows:
        if not isinstance(raw, Mapping):
            raise T092FormalError("T090 teacher row is malformed")
        decision = raw.get("decision_identity")
        root_rows = raw.get("root_rows")
        details = provenance.get(decision)
        source_identity = raw.get("source_identity")
        if not isinstance(decision, str) or decision in seen_decisions or not isinstance(source_identity, str) or source_identity not in split_by_source or raw.get("source_group") != split_by_source[source_identity].source_group or not isinstance(root_rows, Sequence) or isinstance(root_rows, (str, bytes)) or not isinstance(details, Mapping) or details.get("selection_rule") != "highest_mean" or not isinstance(details.get("selected_action_identity"), Mapping):
            raise T092FormalError("T090 root evidence is incomplete")
        seen_decisions.add(decision)
        actions: list[dict[str, Any]] = []
        for action in root_rows:
            if not isinstance(action, Mapping) or set(action) != {"legal_action_identity", "visits", "mean_value"} or not isinstance(action.get("legal_action_identity"), Mapping) or isinstance(action.get("visits"), bool) or not isinstance(action.get("visits"), int) or action["visits"] < 0 or (action["visits"] == 0 and action.get("mean_value") is not None) or (action["visits"] > 0 and not _finite(action.get("mean_value"))):
                raise T092FormalError("T090 root action evidence is malformed")
            actions.append({"action_identity": dict(action["legal_action_identity"]), "visits": action["visits"], "mean_value": action["mean_value"]})
        rows.append({"decision_identity": decision, "ordered_root_actions": actions, "selected_action_identity": dict(details["selected_action_identity"])})
    if set(provenance) != seen_decisions:
        raise T092FormalError("T090 teacher rows and decision provenance references differ")
    result = {"schema_id": T092_T090_ROOT_REFERENCE_SCHEMA_ID, "schema_version": 1, "task_id": "T092", "split_manifest_sha256": canonical_sha256(split_manifest), "source_ledger": ledger, **root_artifacts, "rows": rows, "rows_sha256": canonical_sha256(rows)}
    # The builder has already read and hash-checked each supplied input
    # artifact above.  Re-validating the 560 MB teacher array here would add a
    # needless second full parse; formal admission performs the durable
    # hash/schema check again when the saved reference is consumed.
    validate_t092_t090_root_reference(
        result, split_manifest=split_manifest, verify_input_artifacts=False
    )
    return result


def _finite(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))


def _accepted_canary_reference(
    value: object, *, split_manifest: Mapping[str, Any], implementation_head: str,
    validate_payload: bool = True,
) -> dict[str, Any]:
    """Validate the retained parity evidence reference.

    Authorization preparation performs the full semantic validation once. A
    worker revalidates the exact reference and streams its hash, but does not
    materialize the already-authorized canary JSON again. The worker path is
    safe only when checking an exact authorization binding; preparation keeps
    the default full payload validation.
    """
    reference = _artifact(value, "accepted T092 canary")
    if reference["schema_id"] != "t092-paired-semantic-parity-canary-v1":
        raise T092FormalError("accepted T092 canary has an unexpected schema")
    if not validate_payload:
        return _stream_artifact_hash(reference, "accepted T092 canary evidence")
    try:
        raw = Path(reference["path"]).read_bytes()
        evidence = json.loads(raw)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise T092FormalError("accepted T092 canary evidence is unavailable") from exc
    if hashlib.sha256(raw).hexdigest() != reference["sha256"] or len(raw) != reference["size_bytes"] or not isinstance(evidence, Mapping):
        raise T092FormalError("accepted T092 canary evidence hash mismatches")
    try:
        validate_t092_canary_evidence(evidence, split_manifest=split_manifest)
    except (T092CanaryError, TypeError, ValueError) as exc:
        raise T092FormalError("accepted T092 canary evidence is invalid") from exc
    entries = evidence.get("source_execution_entries")
    if not isinstance(entries, Sequence) or any(
        not isinstance(entry, Mapping)
        or not isinstance(entry.get("off"), Mapping)
        or not isinstance(entry.get("on"), Mapping)
        or entry["off"].get("implementation_head") != implementation_head
        or entry["on"].get("implementation_head") != implementation_head
        or not isinstance(entry.get("arm_artifacts"), Mapping)
        or any(
            not isinstance(entry["arm_artifacts"].get(arm), Mapping)
            or entry["arm_artifacts"][arm].get("schema_id") != T092_CANARY_ARM_RECORD_SCHEMA_ID
            for arm in ("OFF", "ON")
        )
        for entry in entries
    ):
        raise T092FormalError(
            "accepted T092 canary is not bound to this exact v2 implementation/geometry identity"
        )
    return reference


def _formal_input_identities(
    value: object, *, validate_payload: bool = True
) -> dict[str, Any]:
    """Bind every accepted upstream fact; no filename/default substitutes."""
    required = {"formal_restore_manifest", "arm_process_specs", "t087_source_cohort",
                "t090_source_ledger", "t091_reference", "task_native_provenance"}
    if not isinstance(value, Mapping) or set(value) != required:
        raise T092FormalError("T092 formal input identities are incomplete")
    result = dict(value)
    for key in ("formal_restore_manifest", "t087_source_cohort", "t090_source_ledger", "t091_reference", "task_native_provenance"):
        artifact = _artifact(result[key], key)
        if not validate_payload:
            _stream_artifact_hash(artifact, key)
            continue
        try:
            raw = Path(artifact["path"]).read_bytes()
        except OSError as exc:
            raise T092FormalError(f"{key} artifact is unavailable") from exc
        if hashlib.sha256(raw).hexdigest() != artifact["sha256"] or len(raw) != artifact["size_bytes"]:
            raise T092FormalError(f"{key} artifact hash mismatches")
        if key == "t091_reference":
            try:
                report = json.loads(raw)
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise T092FormalError("T091 reference artifact is not valid JSON") from exc
            n4 = report.get("leakage_safe_n4_deduplication") if isinstance(report, Mapping) else None
            if (
                not isinstance(report, Mapping)
                or report.get("schema_id") != "t091-battle-teacher-data-surface-report-v1"
                or report.get("schema_version") != 1
                or report.get("task_id") != "T091"
                or not isinstance(n4, Mapping)
                or n4.get("retained_unique_pair_examples") != 3534
                or n4.get("retained_ordered_non_tie_pairs") != 44846
            ):
                raise T092FormalError(
                    "T091 reference lacks the accepted n_min=4 comparison values"
                )
    specs = result["arm_process_specs"]
    if not isinstance(specs, Mapping) or set(specs) != {"ON"} or not isinstance(specs["ON"], Mapping) or specs["ON"].get("native_identity") != T092_NATIVE_IDENTITY:
        raise T092FormalError("T092 formal ON native process identity is invalid")
    return result


def build_t092_formal_authorization_template(*, implementation_head: str, split_manifest: Mapping[str, Any],
                                             root_reference: Mapping[str, Any], canary_evidence: Mapping[str, Any],
                                             input_identities: Mapping[str, Any], output_root: str | Path,
                                             shard_count: int = T092_FORMAL_DEFAULT_SHARDS,
                                             worker_count: int = T092_FORMAL_DEFAULT_WORKERS,
                                             validate_canary_evidence: bool = True,
                                             validate_input_payloads: bool = True) -> dict[str, Any]:
    if not _sha(implementation_head):
        raise T092FormalError("T092 formal implementation/input identity is invalid")
    inputs = _formal_input_identities(
        input_identities, validate_payload=validate_input_payloads
    )
    plan = build_t092_formal_plan(split_manifest, shard_count=shard_count, worker_count=worker_count)
    reference = validate_t092_t090_root_reference(
        root_reference,
        split_manifest=split_manifest,
        require_input_artifacts=True,
        verify_input_artifacts=validate_input_payloads,
    )
    canary_ref = _accepted_canary_reference(
        canary_evidence,
        split_manifest=split_manifest,
        implementation_head=implementation_head,
        validate_payload=validate_canary_evidence,
    )
    identity = {
        "schema_id": T092_FORMAL_AUTHORIZATION_SCHEMA_ID, "task_id": "T092", "authorization_kind": "formal_413_telemetry",
        "implementation_head": implementation_head, "split_manifest_sha256": canonical_sha256(split_manifest),
        "formal_plan_sha256": canonical_sha256(plan), "root_reference_sha256": canonical_sha256(reference),
        "canary_evidence": canary_ref, "input_identities_sha256": canonical_sha256(inputs),
        "native_identity": dict(T092_NATIVE_IDENTITY), "teacher_config": dict(T092_FROZEN_TEACHER_CONFIG),
        "execution_config": dict(T092_CANARY_EXECUTION_CONFIG), "shard_topology": plan["worker_plan"],
        "output_root": str(Path(output_root).resolve()),
    }
    return {"schema_id": "t092-formal-authorization-preparation-v1", "task_id": "T092", "preparation_only": True,
            "formal_plan": plan, "input_identities": inputs, "authorization_identity": identity,
            "authorization_template": {**identity, "authorized": None, "authorization_id": None,
                "maintainer_attestation": {"role": "maintainer", "decision": "FORMAL_AUTHORIZED", "exact_head": implementation_head}}}


def validate_t092_formal_authorization(authorization: Mapping[str, Any] | None, *, implementation_head: str,
                                       split_manifest: Mapping[str, Any], root_reference: Mapping[str, Any],
                                       canary_evidence: Mapping[str, Any], input_identities: Mapping[str, Any],
                                       output_root: str | Path, shard_index: int, shard_count: int, worker_count: int) -> dict[str, Any]:
    if not isinstance(authorization, Mapping):
        raise T092FormalError("explicit T092 Maintainer formal authorization is required")
    # Preparation already performed full payload validation.  This exact
    # authorization identity lets each worker recheck bindings without
    # retaining the large upstream/canary JSON objects in its RSS.
    prepared = build_t092_formal_authorization_template(implementation_head=implementation_head, split_manifest=split_manifest,
        root_reference=root_reference, canary_evidence=canary_evidence, input_identities=input_identities, output_root=output_root,
        shard_count=shard_count,
        worker_count=worker_count,
        validate_canary_evidence=False,
        validate_input_payloads=False,
    )
    identity = prepared["authorization_identity"]
    expected = {**identity, "authorized": True, "authorization_id": authorization.get("authorization_id"),
                "maintainer_attestation": {"role": "maintainer", "decision": "FORMAL_AUTHORIZED", "exact_head": implementation_head}}
    if not isinstance(authorization.get("authorization_id"), str) or not authorization["authorization_id"] or dict(authorization) != expected:
        raise T092FormalError("T092 formal authorization is not an exact approved binding")
    return _topology(shard_index=shard_index, shard_count=shard_count, worker_count=worker_count)


def _formal_arm(record: Mapping[str, Any], source: Mapping[str, Any], worker: Mapping[str, Any], implementation_head: str) -> dict[str, Any]:
    """Accept exactly the reviewed ON arm envelope; retain no OFF surrogate."""
    try:
        from sts_combat_rl.sim.t090_battle_student import T090SplitEntry
        entry = T090SplitEntry(**dict(source))
        _validate_arm_record(record, arm="ON", expected_native_identity=T092_NATIVE_IDENTITY, source=entry)
    except (TypeError, ValueError, T092CanaryError) as exc:
        raise T092FormalError("T092 formal ON arm record is invalid") from exc
    if record.get("schema_id") != T092_CANARY_ARM_RECORD_SCHEMA_ID or not isinstance(record.get("tree_geometry"), Sequence):
        raise T092FormalError("T092 formal ON arm lacks current compact tree geometry retention")
    if record.get("implementation_head") != implementation_head or record.get("worker") != worker:
        raise T092FormalError("T092 formal ON arm provenance mismatches its shard")
    return dict(record)


def execute_t092_authorized_formal_shard(*, authorization: Mapping[str, Any] | None, implementation_head: str,
                                         split_manifest: Mapping[str, Any], root_reference: Mapping[str, Any],
                                         canary_evidence: Mapping[str, Any], input_identities: Mapping[str, Any],
                                         output_root: str | Path, shard_index: int, shard_count: int, worker_count: int,
                                         runner: Callable[[Mapping[str, Any], Mapping[str, Any]], Mapping[str, Any]]) -> dict[str, Any]:
    """Run one all-or-nothing formal shard after offline admission only."""
    topology = validate_t092_formal_authorization(authorization, implementation_head=implementation_head,
        split_manifest=split_manifest, root_reference=root_reference, canary_evidence=canary_evidence,
        input_identities=input_identities, output_root=output_root, shard_index=shard_index,
        shard_count=shard_count, worker_count=worker_count)
    if not callable(runner):
        raise T092FormalError("T092 formal runner is unavailable")
    plan = build_t092_formal_plan(split_manifest, shard_count=shard_count, worker_count=worker_count)
    worker = {"stage_worker_count": worker_count, "worker_index": shard_index, "shard_count": shard_count, "shard_index": shard_index}
    sources = [source for index, source in enumerate(plan["sources"]) if index % shard_count == shard_index]
    source_artifacts: list[dict[str, Any]] = []
    for ordinal, source in enumerate(sources):
        try:
            raw = runner(source, worker)
        except Exception as exc:
            raise T092FormalError("T092 formal runner failed before complete shard retention") from exc
        record = _formal_arm(raw, source, worker, implementation_head)
        source_artifacts.append(write_t092_formal_json(
            Path(output_root) / "source-records" / f"shard-{shard_index:02d}" / f"source-{ordinal:03d}.json",
            record,
            schema_id=T092_CANARY_ARM_RECORD_SCHEMA_ID,
        ))
    if len(source_artifacts) != len(sources):
        raise T092FormalError("T092 formal shard is incomplete")
    return {"schema_id": T092_FORMAL_SHARD_SCHEMA_ID, "schema_version": 1, "task_id": "T092",
            "authorization_id": authorization["authorization_id"], "implementation_head": implementation_head,
            "formal_plan_sha256": canonical_sha256(plan), "topology": topology, "source_artifacts": source_artifacts,
            "source_artifacts_sha256": canonical_sha256(source_artifacts)}


def _root_projection(record: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in record["decision_records"]:
        semantic = item["root_semantics"]
        rows.append({"decision_identity": item["decision_identity"], "ordered_root_actions": [
            {"action_identity": row["action_identity"], "visits": row["visits"], "mean_value": row["mean_value"]}
            for row in semantic["ordered_root_actions"]], "selected_action_identity": semantic["selected_action_identity"]})
    return rows


def _tree_geometry_metrics(
    observations: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Aggregate compact native geometry, or state its exact absence."""

    if not observations:
        raise T092FormalError("T092 formal tree geometry observations are incomplete")
    by_group: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for observation in observations:
        group = observation.get("source_group")
        if group not in {"A", "B", "C"}:
            raise T092FormalError("T092 formal tree geometry source group is invalid")
        by_group[str(group)].append(observation)

    def aggregate(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
        if not rows:
            return {
                "observation_count": 0,
                "unavailable_observation_count": 0,
                "availability": "unavailable",
                "unavailable_reason": "no_observations_for_source_group",
                "expanded_nodes_from_native_telemetry": 0,
                "total_tree_nodes_observed": "UNAVAILABLE_FROM_NATIVE_TREE_GEOMETRY",
                "total_expanded_node_count": "UNAVAILABLE_FROM_NATIVE_TREE_GEOMETRY",
                "total_discovered_child_edge_count": "UNAVAILABLE_FROM_NATIVE_TREE_GEOMETRY",
                "total_visited_child_edge_count": "UNAVAILABLE_FROM_NATIVE_TREE_GEOMETRY",
                "max_expanded_depth": "UNAVAILABLE_FROM_NATIVE_TREE_GEOMETRY",
                "depth_distribution": {},
                "branching_distribution": {},
            }
        unavailable = sum(row.get("availability") != "available" for row in rows)
        expanded_from_native = sum(int(row["expanded_node_count"]) for row in rows)
        depth_counts: Counter[str] = Counter()
        branching_counts: Counter[str] = Counter()
        discovered = visited = expanded = 0
        max_depth = -1
        for row in rows:
            geometry = row.get("geometry")
            if not isinstance(geometry, Mapping):
                continue
            expanded += int(geometry["total_expanded_node_count"])
            discovered += int(geometry["total_discovered_child_edge_count"])
            visited += int(geometry["total_visited_child_edge_count"])
            max_depth = max(max_depth, int(geometry["max_expanded_depth"]))
            for depth_row in geometry["depth_rows"]:
                depth_counts[str(depth_row["depth"])] += int(depth_row["expanded_node_count"])
                for bucket in depth_row["branching_histogram"]:
                    branching_counts[str(bucket["child_count"])] += int(bucket["node_count"])
        result: dict[str, Any] = {
            "observation_count": len(rows),
            "unavailable_observation_count": unavailable,
            "expanded_nodes_from_native_telemetry": expanded_from_native,
            "depth_distribution": dict(sorted(depth_counts.items(), key=lambda item: int(item[0]))),
            "branching_distribution": dict(sorted(branching_counts.items(), key=lambda item: int(item[0]))),
        }
        if unavailable == 0:
            result.update({
                "availability": "available",
                "total_expanded_node_count": expanded,
                "total_discovered_child_edge_count": discovered,
                "total_visited_child_edge_count": visited,
                # A native Search tree has one root plus one node for every
                # discovered child edge.  Expanded nodes are a subset of
                # those tree nodes, not an additional population to add.
                "total_tree_nodes_observed": discovered + sum(
                    isinstance(row.get("geometry"), Mapping) for row in rows
                ),
                "max_expanded_depth": max_depth,
            })
        else:
            result.update({
                "availability": "unavailable" if unavailable == len(rows) else "partial",
                "unavailable_reason": "native_report_omitted_tree_internal_telemetry_tree_geometry",
                "total_expanded_node_count": "UNAVAILABLE_FROM_NATIVE_TREE_GEOMETRY",
                "total_discovered_child_edge_count": "UNAVAILABLE_FROM_NATIVE_TREE_GEOMETRY",
                "total_visited_child_edge_count": "UNAVAILABLE_FROM_NATIVE_TREE_GEOMETRY",
                "total_tree_nodes_observed": "UNAVAILABLE_FROM_NATIVE_TREE_GEOMETRY",
                "max_expanded_depth": "UNAVAILABLE_FROM_NATIVE_TREE_GEOMETRY",
            })
        return result

    result = aggregate(observations)
    result["by_source_group"] = {group: aggregate(by_group.get(group, [])) for group in ("A", "B", "C")}
    return {"schema_id": "t092-formal-tree-geometry-metrics-v1", **result}


def _canonical_root_rows(
    sources: Sequence[Mapping[str, Any]],
    rows_by_source: Mapping[str, Sequence[Mapping[str, Any]]],
) -> list[dict[str, Any]]:
    """Restore source/decision order after canonical-ordinal shard grouping.

    Shards are intentionally assigned by ``global_ordinal % shard_count`` for
    balanced work.  Their completion/manifest order is therefore not the
    accepted T090 source order.  Reconstructing that order explicitly avoids a
    false root-parity failure (or, worse, a positional comparison that happens
    to pass after an accidental source alias).
    """

    expected = [source.get("source_identity") for source in sources]
    if any(not isinstance(identity, str) or not identity for identity in expected):
        raise T092FormalError("T092 canonical root source identity is malformed")
    identities = [str(identity) for identity in expected]
    if len(set(identities)) != len(identities) or set(rows_by_source) != set(identities):
        raise T092FormalError("T092 canonical root source references are duplicate or incomplete")
    result: list[dict[str, Any]] = []
    for identity in identities:
        rows = rows_by_source[identity]
        if not isinstance(rows, Sequence) or isinstance(rows, (str, bytes)):
            raise T092FormalError("T092 canonical root projection is malformed")
        result.extend(dict(row) for row in rows)
    return result


def _depth_bucket(depth: int) -> str:
    return "1" if depth == 1 else "2" if depth == 2 else "3-4" if depth <= 4 else "5-8" if depth <= 8 else "9+"


def _branch_bucket(size: int) -> str:
    return "2" if size == 2 else "3-4" if size <= 4 else "5-8" if size <= 8 else "9-16" if size <= 16 else "17+"


def _classification(
    metrics: Mapping[str, Any], *, root_ok: bool, canary_ok: bool,
    firewall_ok: bool, geometry_ok: bool,
) -> str:
    if not (root_ok and canary_ok):
        return "INTERNAL_TELEMETRY_SEMANTIC_PARITY_INVALID"
    if not firewall_ok:
        return "INTERNAL_SEARCH_INFORMATION_BOUNDARY_INVALID"
    if not geometry_ok:
        # Geometry is required to make the formal internal-surface claim.  A
        # report that only has the expanded-node scalar is explicit evidence
        # of an unavailable required fact, not a usable zero or estimate.
        return "INCOMPLETE"
    primary = metrics["thresholds"]["4"]
    overall_yield = primary["usable_examples_per_1000_search_simulations"]["overall"]
    qualifying_buckets = [
        bucket
        for bucket, count in metrics["raw_multi_action_by_branching_bucket"].items()
        if count >= 10_000
    ]
    common_kinds = {
        kind
        for kind, count in metrics["teacher_searchable_action_kinds"].items()
        if count >= 1_000
    }
    paired_kinds = set(primary["action_kinds_with_retained_pairs"])
    gates = [
        primary["leakage_safe_unique_examples"] >= 35_340,
        primary["retained_ordered_non_tie_pairs"] >= 224_230,
        all(primary["by_source_group"].get(group, 0) >= 5_000 for group in ("A", "B", "C")),
        overall_yield is not None and all(
            value is not None and value >= 0.5 * overall_yield
            for value in primary["usable_examples_per_1000_search_simulations"]["by_source_group"].values()
        ),
        all(primary["by_branching_bucket"].get(bucket, 0) >= 500 for bucket in qualifying_buckets),
        (len(common_kinds & paired_kinds) / len(common_kinds) >= 0.9) if common_kinds else True,
    ]
    return "INTERNAL_SEARCH_SURFACE_DENSE_ENOUGH" if all(gates) else "INTERNAL_SEARCH_SURFACE_TOO_SPARSE_OR_BIASED"


def finalize_t092_formal_shards(*, authorization: Mapping[str, Any] | None, implementation_head: str,
                                split_manifest: Mapping[str, Any], root_reference: Mapping[str, Any],
                                canary_evidence: Mapping[str, Any], input_identities: Mapping[str, Any], output_root: str | Path,
                                shards: Sequence[Mapping[str, Any] | Path]) -> dict[str, Any]:
    """Finalize formal shards with guaranteed cleanup of the spill store."""

    metric_rows = _MetricRowStore(output_root)
    try:
        return _finalize_t092_formal_shards_impl(
            authorization=authorization,
            implementation_head=implementation_head,
            split_manifest=split_manifest,
            root_reference=root_reference,
            canary_evidence=canary_evidence,
            input_identities=input_identities,
            output_root=output_root,
            shards=shards,
            metric_rows=metric_rows,
        )
    finally:
        metric_rows.close()


def _finalize_t092_formal_shards_impl(*, authorization: Mapping[str, Any] | None, implementation_head: str,
                                      split_manifest: Mapping[str, Any], root_reference: Mapping[str, Any],
                                      canary_evidence: Mapping[str, Any], input_identities: Mapping[str, Any], output_root: str | Path,
                                      shards: Sequence[Mapping[str, Any] | Path], metric_rows: _MetricRowStore) -> dict[str, Any]:
    """Offline, fail-closed finalizer. Processes one shard at a time conceptually.

    The retained compact shards, not an in-memory native tree corpus, are the
    unit of aggregation.  The result intentionally contains only reports and
    manifest identities; callers retain original shard payloads separately.
    """
    if not isinstance(authorization, Mapping) or not isinstance(authorization.get("shard_topology"), Mapping):
        raise T092FormalError("T092 formal finalization lacks an exact authorization topology")
    configured = authorization["shard_topology"]
    shard_count, worker_count = configured.get("shard_count"), configured.get("worker_count")
    if (isinstance(shard_count, bool) or not isinstance(shard_count, int)
            or isinstance(worker_count, bool) or not isinstance(worker_count, int)):
        raise T092FormalError("T092 formal finalization topology is invalid")
    plan = build_t092_formal_plan(split_manifest, shard_count=shard_count, worker_count=worker_count)
    if len(shards) != shard_count:
        raise T092FormalError("T092 formal finalization requires every planned shard")
    # Validate the expensive hash-bound root/T091 inputs once.  The shard loop
    # is offline and consumes the same immutable values; re-reading the 560 MB
    # teacher artifact for every shard would turn finalization into an avoidable
    # memory/IO multiplier.
    validate_t092_formal_authorization(
        authorization=authorization,
        implementation_head=implementation_head,
        split_manifest=split_manifest,
        root_reference=root_reference,
        canary_evidence=canary_evidence,
        input_identities=input_identities,
        output_root=output_root,
        shard_index=0,
        shard_count=shard_count,
        worker_count=worker_count,
    )
    reference = dict(root_reference)
    # Never retain public projections, child means, or full occurrence payloads
    # across sources.  The finalizer keeps only these fixed metric summaries.
    observed_roots_by_source: dict[str, list[dict[str, Any]]] = {}
    geometry_observations: list[dict[str, Any]] = []
    ledger: list[dict[str, Any]] = []
    artifacts: list[dict[str, Any]] = []
    for index, shard_input in enumerate(shards):
        if isinstance(shard_input, Path):
            try:
                shard_value = json.loads(shard_input.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                raise T092FormalError("T092 formal shard is unavailable") from exc
            if not isinstance(shard_value, Mapping):
                raise T092FormalError("T092 formal shard is malformed")
            shard: Mapping[str, Any] = shard_value
        else:
            shard = shard_input
        topology = _topology(
            shard_index=index, shard_count=shard_count, worker_count=worker_count
        )
        if not isinstance(shard, Mapping) or set(shard) != {"schema_id", "schema_version", "task_id", "authorization_id", "implementation_head", "formal_plan_sha256", "topology", "source_artifacts", "source_artifacts_sha256"} or shard.get("schema_id") != T092_FORMAL_SHARD_SCHEMA_ID or shard.get("schema_version") != 1 or shard.get("task_id") != "T092" or shard.get("authorization_id") != authorization["authorization_id"] or shard.get("implementation_head") != implementation_head or shard.get("formal_plan_sha256") != canonical_sha256(plan) or shard.get("topology") != topology or not isinstance(shard.get("source_artifacts"), Sequence) or shard.get("source_artifacts_sha256") != canonical_sha256(shard["source_artifacts"]):
            raise T092FormalError("T092 formal shard provenance is invalid")
        expected_sources = [s for ordinal, s in enumerate(plan["sources"]) if ordinal % shard_count == index]
        if len(shard["source_artifacts"]) != len(expected_sources):
            raise T092FormalError("T092 formal shard record count is incomplete")
        worker = {"stage_worker_count": worker_count, "worker_index": index, "shard_count": shard_count, "shard_index": index}
        for record_reference, source in zip(shard["source_artifacts"], expected_sources, strict=True):
            artifact = _artifact(record_reference, "formal source record")
            try:
                encoded = Path(artifact["path"]).read_bytes()
                record = json.loads(encoded)
            except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise T092FormalError("T092 formal source record is unavailable") from exc
            if (hashlib.sha256(encoded).hexdigest() != artifact["sha256"]
                    or len(encoded) != artifact["size_bytes"]
                    or artifact["schema_id"] != T092_CANARY_ARM_RECORD_SCHEMA_ID
                    or not isinstance(record, Mapping)):
                raise T092FormalError("T092 formal source record identity mismatches")
            arm = _formal_arm(record, source, worker, implementation_head)
            source_identity = str(source["source_identity"])
            if source_identity in observed_roots_by_source:
                raise T092FormalError("T092 formal shard source reference is duplicate or aliased")
            observed_roots_by_source[source_identity] = _root_projection(arm)
            for geometry in arm["tree_geometry"]:
                geometry_observations.append({
                    "source_identity": source_identity,
                    "source_group": source["source_group"],
                    **dict(geometry),
                })
            ledger.append({"source_identity": source["source_identity"], "source_group": source["source_group"], "split": source["split"], "canonical_position": source["canonical_position"], "worker": worker, "terminal": arm["terminal"], "cost": arm["cost"]})
            decision_ids = {item["decision_identity"] for item in arm["decision_records"]}
            rows = [validate_retained_occurrence(row, source_identity=source["source_identity"], source_group=source["source_group"], split=source["split"], parent_root_decision_identities=decision_ids) for row in arm["internal_occurrences"]]
            validate_parent_bound_occurrence_identities(rows)
            for row in rows:
                metric_rows.add(_metric_summary(row))
            # The store now owns only the compact scalar/action summaries.
            # Drop the last decoded arm before root comparison and the second
            # metrics pass; otherwise one ~100 MiB source JSON remains live
            # while the finalizer starts its global aggregation.
            del rows, arm, record, encoded
        artifacts.append({"shard_index": index, "source_artifacts": list(shard["source_artifacts"]), "source_artifacts_sha256": shard["source_artifacts_sha256"], "record_count": len(shard["source_artifacts"])})
    expected = list(reference["rows"])
    observed_roots = _canonical_root_rows(plan["sources"], observed_roots_by_source)
    root_ok = observed_roots == expected
    root_reference_sha256 = canonical_sha256(reference)
    if not root_ok:
        raise T092FormalError("INTERNAL_TELEMETRY_SEMANTIC_PARITY_INVALID: formal root reproduction mismatch")
    # Root parity is complete.  Do not carry its 6369-row expected/observed
    # projections into the independent global metric aggregation pass.
    del expected, observed_roots, observed_roots_by_source, reference
    metrics = _metrics(metric_rows, ledger, geometry_observations)
    geometry_report = metrics["node_totals"]["tree_geometry"]
    classification = _classification(
        metrics,
        root_ok=root_ok,
        canary_ok=True,
        firewall_ok=True,
        geometry_ok=geometry_report.get("availability") == "available",
    )
    return {"schema_id": T092_FORMAL_EVIDENCE_SCHEMA_ID, "schema_version": 1, "task_id": "T092",
            "formal_execution_authorized": True, "training_eligible": False,
            "implementation_head": implementation_head, "formal_plan_sha256": canonical_sha256(plan),
            "root_reference_sha256": root_reference_sha256,
            "input_identities_sha256": canonical_sha256(input_identities),
            "native_identity": dict(T092_NATIVE_IDENTITY), "teacher_config": dict(T092_FROZEN_TEACHER_CONFIG),
            "execution_config": dict(T092_CANARY_EXECUTION_CONFIG), "source_worker_ledger": ledger,
            "source_worker_ledger_sha256": canonical_sha256(ledger), "root_reproduction": {"passed": True, "expected_decision_count": 6369, "s0_complete_root_q": 309},
            "internal_shard_manifest": artifacts, "metrics": metrics,
            "terminal_classification": classification,
            "successor_decision": "Planner may consider a separate public-only distillation task" if classification == "INTERNAL_SEARCH_SURFACE_DENSE_ENOUGH" else "Do not weaken T092 thresholds; use the contract-specified successor boundary"}


def _metric_summary(row: T092Occurrence) -> dict[str, Any]:
    """Discard full student-visible payload after boundary validation."""
    searchable = list(row.searchable_actions)
    # Retain one compact value per supported action rather than materializing
    # O(branching^2) pair dictionaries for every occurrence.  The finalizer
    # derives repeated-fingerprint pair signs one fingerprint at a time.
    supported_action_values = tuple(
        (
            json.dumps(item["action"], sort_keys=True, separators=(",", ":")),
            int(item["visits"]),
            float(item["mean_value"]),
        )
        for item in searchable
        if int(item["visits"]) > 0 and _finite(item["mean_value"])
    )
    return {
        "fingerprint": row.fingerprint,
        "split": row.split,
        "source_group": row.source_group,
        "source_identity": row.source_identity,
        "parent": row.parent_root_decision_identity,
        "occurrence": row.occurrence_identity,
        "depth": row.tree_depth,
        "branching": len(row.searchable_actions),
        "searchable_kinds": tuple(item["action"]["kind"] for item in searchable),
        "excluded_kinds": tuple(item["action"]["kind"] for item in row.excluded_actions),
        "supported": {
            str(n): sum(
                item["visits"] >= n and _finite(item["mean_value"])
                for item in row.searchable_actions
            )
            for n in T092_N_MINS
        },
        "pairs": {str(n): len(support_pairs(row, n)) for n in T092_N_MINS},
        "paired_kinds": {
            str(n): tuple(sorted({item["action"]["kind"] for pair in support_pairs(row, n) for item in pair}))
            for n in T092_N_MINS
        },
        "supported_action_values": supported_action_values,
        "telemetry_transitions": row.telemetry_cost["telemetry_extraction_transition_count"],
    }


class _MetricRowStore:
    """Disk-backed compact metric rows for the 413-start finalizer.

    The retained arm artifacts are intentionally large and the formal corpus
    contains more than a million internal occurrences.  Keeping one Python
    mapping per occurrence makes an offline finalizer exceed the same frozen
    2 GiB process-group boundary used by workers.  SQLite is part of the
    Python standard library and gives the finalizer deterministic fingerprint
    ordering while keeping row payloads on the retention filesystem.
    """

    _COLUMNS = (
        "fingerprint", "split", "source_group", "source_identity", "parent",
        "occurrence", "depth", "branching", "searchable_kinds", "excluded_kinds",
        "supported", "pairs", "paired_kinds", "supported_action_values",
        "telemetry_transitions",
    )

    def __init__(self, directory: str | Path | None = None) -> None:
        descriptor, raw_path = tempfile.mkstemp(
            prefix="t092-metrics-",
            suffix=".sqlite3",
            dir=str(directory) if directory is not None else None,
        )
        os.close(descriptor)
        self._path = raw_path
        self._connection = sqlite3.connect(raw_path)
        self._connection.execute(
            """CREATE TABLE metric_rows (
                id INTEGER PRIMARY KEY,
                fingerprint TEXT NOT NULL,
                split TEXT NOT NULL,
                source_group TEXT NOT NULL,
                source_identity TEXT NOT NULL,
                parent TEXT NOT NULL,
                occurrence TEXT NOT NULL,
                depth INTEGER NOT NULL,
                branching INTEGER NOT NULL,
                searchable_kinds TEXT NOT NULL,
                excluded_kinds TEXT NOT NULL,
                supported TEXT NOT NULL,
                pairs TEXT NOT NULL,
                paired_kinds TEXT NOT NULL,
                supported_action_values TEXT NOT NULL,
                telemetry_transitions INTEGER NOT NULL
            )"""
        )
        self._connection.execute(
            "CREATE INDEX metric_rows_fingerprint ON metric_rows(fingerprint)"
        )
        self._pending = 0
        self._count = 0

    @property
    def count(self) -> int:
        return self._count

    def add(self, row: Mapping[str, Any]) -> None:
        encoded = {
            key: json.dumps(row[key], sort_keys=True, separators=(",", ":"))
            for key in (
                "searchable_kinds", "excluded_kinds", "supported", "pairs",
                "paired_kinds", "supported_action_values",
            )
        }
        self._connection.execute(
            """INSERT INTO metric_rows (
                fingerprint, split, source_group, source_identity, parent,
                occurrence, depth, branching, searchable_kinds, excluded_kinds,
                supported, pairs, paired_kinds, supported_action_values,
                telemetry_transitions
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                str(row["fingerprint"]), str(row["split"]), str(row["source_group"]),
                str(row["source_identity"]), str(row["parent"]), str(row["occurrence"]),
                int(row["depth"]), int(row["branching"]), encoded["searchable_kinds"],
                encoded["excluded_kinds"], encoded["supported"], encoded["pairs"],
                encoded["paired_kinds"], encoded["supported_action_values"],
                int(row["telemetry_transitions"]),
            ),
        )
        self._pending += 1
        self._count += 1
        if self._pending >= 10_000:
            self._connection.commit()
            self._pending = 0

    def iter_groups(self):
        self._connection.commit()
        cursor = self._connection.execute(
            "SELECT fingerprint, split, source_group, source_identity, parent, "
            "occurrence, depth, branching, searchable_kinds, excluded_kinds, "
            "supported, pairs, paired_kinds, supported_action_values, "
            "telemetry_transitions FROM metric_rows ORDER BY fingerprint"
        )
        current: list[dict[str, Any]] = []
        current_fingerprint: str | None = None
        for raw in cursor:
            fingerprint = str(raw[0])
            row = {
                "fingerprint": fingerprint,
                "split": str(raw[1]),
                "source_group": str(raw[2]),
                "source_identity": str(raw[3]),
                "parent": str(raw[4]),
                "occurrence": str(raw[5]),
                "depth": int(raw[6]),
                "branching": int(raw[7]),
                "searchable_kinds": tuple(json.loads(raw[8])),
                "excluded_kinds": tuple(json.loads(raw[9])),
                "supported": json.loads(raw[10]),
                "pairs": json.loads(raw[11]),
                "paired_kinds": {
                    str(key): tuple(value)
                    for key, value in json.loads(raw[12]).items()
                },
                "supported_action_values": tuple(
                    tuple(value) for value in json.loads(raw[13])
                ),
                "telemetry_transitions": int(raw[14]),
            }
            if current_fingerprint is not None and fingerprint != current_fingerprint:
                yield current_fingerprint, current
                current = []
            current_fingerprint = fingerprint
            current.append(row)
        if current_fingerprint is not None:
            yield current_fingerprint, current

    def close(self) -> None:
        connection = getattr(self, "_connection", None)
        if connection is None:
            return
        self._connection.commit()
        connection.close()
        self._connection = None
        try:
            os.unlink(self._path)
        except FileNotFoundError:
            pass

    def __del__(self) -> None:  # pragma: no cover - best-effort exceptional cleanup
        try:
            self.close()
        except (OSError, sqlite3.Error):
            pass


def _metrics(
    rows: Sequence[Mapping[str, Any]], ledger: Sequence[Mapping[str, Any]],
    geometry_observations: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Compute every registered report from bounded compact row summaries."""

    if isinstance(rows, _MetricRowStore):
        return _metrics_from_store(rows, ledger, geometry_observations)

    by_fp: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    depth, branching, raw_multi_branching = Counter(), Counter(), Counter()
    excluded, kinds = Counter(), Counter()
    by_group_rows: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    teacher_actions_by_group: Counter[str] = Counter()
    excluded_actions_by_group: Counter[str] = Counter()
    for row in rows:
        by_fp[str(row["fingerprint"])].append(row)
        group = str(row["source_group"])
        by_group_rows[group].append(row)
        teacher_actions_by_group[group] += int(row["branching"])
        excluded_actions_by_group[group] += len(row["excluded_kinds"])
        depth[_depth_bucket(int(row["depth"]))] += 1
        branching[_branch_bucket(int(row["branching"]))] += 1
        if int(row["branching"]) > 1:
            raw_multi_branching[_branch_bucket(int(row["branching"]))] += 1
        kinds.update(row["searchable_kinds"])
        excluded.update(row["excluded_kinds"])
    collisions = {fp for fp, grouped in by_fp.items() if len({r["split"] for r in grouped}) > 1}
    multiplicity = Counter(len(group) for group in by_fp.values())
    within_split = {
        str(split): sum(
            len(group) - 1
            for group in by_fp.values()
            if len({r["split"] for r in group}) == 1
            and group[0]["split"] == split
        )
        for split in {str(r["split"]) for r in rows}
    }
    group_sims: Counter[str] = Counter()
    for item in ledger:
        group_sims[str(item["source_group"])] += int(item["terminal"].get("battle_decision_count", 0)) * 400
    total_sims = sum(group_sims.values())
    thresholds: dict[str, Any] = {}
    disagreement_by_threshold: dict[str, Any] = {}
    for minimum in T092_N_MINS:
        minimum_key = str(minimum)
        eligible = [r for fp, group in by_fp.items() if fp not in collisions for r in group if r["pairs"][minimum_key] > 0]
        canonical: dict[tuple[str, str], Mapping[str, Any]] = {}
        for row in sorted(eligible, key=lambda r: (r["split"], r["source_identity"], r["parent"], r["occurrence"])):
            canonical.setdefault((str(row["split"]), str(row["fingerprint"])), row)
        retained = list(canonical.values())
        pair_kinds = Counter(kind for row in retained for kind in row["paired_kinds"][minimum_key])
        by_group = Counter(str(row["source_group"]) for row in retained)
        pair_count = sum(int(r["pairs"][minimum_key]) for r in retained)
        retained_pairs_by_depth: Counter[str] = Counter()
        retained_pairs_by_branching: Counter[str] = Counter()
        for row in retained:
            pair_count_for_row = int(row["pairs"][minimum_key])
            retained_pairs_by_depth[_depth_bucket(int(row["depth"]))] += pair_count_for_row
            retained_pairs_by_branching[_branch_bucket(int(row["branching"]))] += pair_count_for_row
        raw_supported = [int(row["supported"][minimum_key]) for row in rows]
        fractions = [count / int(row["branching"]) for count, row in zip(raw_supported, rows, strict=True)]
        group_detail: dict[str, Any] = {}
        for group in ("A", "B", "C"):
            group_rows = by_group_rows.get(group, [])
            group_eligible = [r for r in eligible if str(r["source_group"]) == group]
            group_retained = [r for r in retained if str(r["source_group"]) == group]
            group_pairs_by_depth: Counter[str] = Counter()
            group_pairs_by_branching: Counter[str] = Counter()
            for row in group_retained:
                pair_count_for_row = int(row["pairs"][minimum_key])
                group_pairs_by_depth[_depth_bucket(int(row["depth"]))] += pair_count_for_row
                group_pairs_by_branching[_branch_bucket(int(row["branching"]))] += pair_count_for_row
            group_detail[group] = {
                "internal_occurrence_count": len(group_rows),
                "raw_occurrences_with_pairs": len(group_eligible),
                "leakage_safe_unique_examples": len(group_retained),
                "nodes_with_at_least_two_supported_actions": sum(int(r["supported"][minimum_key]) >= 2 for r in group_rows),
                "total_supported_actions": sum(int(r["supported"][minimum_key]) for r in group_rows),
                "retained_ordered_non_tie_pairs": sum(int(r["pairs"][minimum_key]) for r in group_retained),
                "supported_teacher_searchable_fraction": _distribution([int(r["supported"][minimum_key]) / int(r["branching"]) for r in group_rows]),
                "by_depth_bucket": dict(sorted(Counter(_depth_bucket(int(r["depth"])) for r in group_retained).items())),
                "by_branching_bucket": dict(sorted(Counter(_branch_bucket(int(r["branching"])) for r in group_retained).items())),
                "pairs_by_depth_bucket": dict(sorted(group_pairs_by_depth.items())),
                "pairs_by_branching_bucket": dict(sorted(group_pairs_by_branching.items())),
                "usable_examples_per_1000_search_simulations": (len(group_retained) * 1_000 / group_sims[group]) if group_sims[group] else None,
                "usable_pairs_per_1000_search_simulations": (sum(int(r["pairs"][minimum_key]) for r in group_retained) * 1_000 / group_sims[group]) if group_sims[group] else None,
                "usable_examples_per_battle_start": len(group_retained) / len({str(item["source_identity"]) for item in ledger if str(item["source_group"]) == group}) if any(str(item["source_group"]) == group for item in ledger) else None,
                "usable_pairs_per_battle_start": sum(int(r["pairs"][minimum_key]) for r in group_retained) / len({str(item["source_identity"]) for item in ledger if str(item["source_group"]) == group}) if any(str(item["source_group"]) == group for item in ledger) else None,
            }
        repeated = {fp: group for fp, group in by_fp.items() if len(group) > 1}
        best_defined = 0
        best_disagreements = 0
        pair_defined = 0
        pair_conflicts = 0
        groups_with_pair_conflicts = 0
        for group in repeated.values():
            best: set[str] = set()
            for row in group:
                supported = [
                    (action, visits, mean)
                    for action, visits, mean in row.get("supported_action_values", ())
                    if int(visits) >= minimum
                ]
                if supported:
                    best.add(
                        min(
                            supported,
                            key=lambda item: (-float(item[2]), item[0]),
                        )[0]
                    )
            if len(best) >= 2:
                best_disagreements += 1
            if best:
                best_defined += 1
            pair_observations: Counter[str] = Counter()
            preferences: dict[str, set[str]] = defaultdict(set)
            for row in group:
                supported = [
                    (action, visits, mean)
                    for action, visits, mean in row.get("supported_action_values", ())
                    if int(visits) >= minimum
                ]
                for left_index, left in enumerate(supported):
                    for right in supported[left_index + 1:]:
                        delta = float(left[2]) - float(right[2])
                        if abs(delta) <= 1e-9:
                            continue
                        action_a, action_b = sorted((left[0], right[0]))
                        pair_key = f"{action_a}|{action_b}"
                        pair_observations[pair_key] += 1
                        preferences[pair_key].add(left[0] if delta > 0 else right[0])
            group_conflict = False
            for pair_key, signs in preferences.items():
                if pair_observations[pair_key] >= 2:
                    pair_defined += 1
                if pair_observations[pair_key] >= 2 and len(signs) >= 2:
                    pair_conflicts += 1
                    group_conflict = True
            if group_conflict:
                groups_with_pair_conflicts += 1
        disagreement_by_threshold[minimum_key] = {
            "repeated_fingerprint_groups": len(repeated),
            "groups_with_defined_best_supported_action": best_defined,
            "groups_with_best_supported_action_disagreement": best_disagreements,
            "repeated_supported_pair_comparisons": pair_defined,
            "pairwise_mean_sign_conflict_pairs": pair_conflicts,
            "fingerprint_groups_with_pairwise_mean_sign_conflict": groups_with_pair_conflicts,
        }
        thresholds[minimum_key] = {
            "raw_occurrences_with_pairs": len(eligible),
            "leakage_safe_unique_examples": len(retained),
            "nodes_with_at_least_two_supported_actions": sum(count >= 2 for count in raw_supported),
            "total_supported_actions": sum(raw_supported),
            "supported_teacher_searchable_fraction": _distribution(fractions),
            "retained_ordered_non_tie_pairs": pair_count,
            "raw_examples_by_depth_bucket": dict(sorted(Counter(_depth_bucket(int(r["depth"])) for r in eligible).items())),
            "raw_examples_by_branching_bucket": dict(sorted(Counter(_branch_bucket(int(r["branching"])) for r in eligible).items())),
            "by_source_group": dict(sorted(by_group.items())),
            "by_source_group_detail": group_detail,
            "by_depth_bucket": dict(sorted(Counter(_depth_bucket(int(r["depth"])) for r in retained).items())),
            "by_branching_bucket": dict(sorted(Counter(_branch_bucket(int(r["branching"])) for r in retained).items())),
            "pairs_by_depth_bucket": dict(sorted(retained_pairs_by_depth.items())),
            "pairs_by_branching_bucket": dict(sorted(retained_pairs_by_branching.items())),
            "action_kinds_with_retained_pairs": sorted(pair_kinds),
            "usable_examples_per_1000_search_simulations": {
                "overall": (len(retained) * 1_000 / total_sims) if total_sims else None,
                "by_source_group": {group: group_detail[group]["usable_examples_per_1000_search_simulations"] for group in ("A", "B", "C")},
            },
            "usable_pairs_per_1000_search_simulations": {
                "overall": (pair_count * 1_000 / total_sims) if total_sims else None,
                "by_source_group": {group: group_detail[group]["usable_pairs_per_1000_search_simulations"] for group in ("A", "B", "C")},
            },
            "usable_examples_per_battle_start": len(retained) / len(ledger) if ledger else None,
            "usable_pairs_per_battle_start": pair_count / len(ledger) if ledger else None,
            "ambiguity_lower_bound": disagreement_by_threshold[minimum_key],
        }
    search_simulations = total_sims
    starts = len(ledger)
    single = sum(int(row["branching"]) == 1 for row in rows)
    multi = len(rows) - single
    group_node_totals = {
        group: {
            "stable_internal_player_decision_nodes": len(by_group_rows.get(group, [])),
            "stable_internal_single_action_nodes": sum(int(r["branching"]) == 1 for r in by_group_rows.get(group, [])),
            "stable_internal_multi_action_nodes": sum(int(r["branching"]) > 1 for r in by_group_rows.get(group, [])),
        }
        for group in ("A", "B", "C")
    }
    return {
        "schema_id": "t092-internal-search-state-formal-metrics-v3",
        "internal_occurrence_count": len(rows),
        "node_totals": {
            "depth_zero_root_count": 0,
            "stable_internal_player_decision_nodes": len(rows),
            "stable_internal_single_action_nodes": single,
            "stable_internal_multi_action_nodes": multi,
            "by_source_group": group_node_totals,
            "tree_geometry": _tree_geometry_metrics(geometry_observations or []),
        },
        "depth_zero_root_count": 0,
        "depth_distribution": dict(sorted(depth.items())),
        "depth_distribution_by_source_group": {group: dict(sorted(Counter(_depth_bucket(int(r["depth"])) for r in by_group_rows.get(group, [])).items())) for group in ("A", "B", "C")},
        "branching_distribution": dict(sorted(branching.items())),
        "branching_distribution_by_source_group": {group: dict(sorted(Counter(_branch_bucket(int(r["branching"])) for r in by_group_rows.get(group, [])).items())) for group in ("A", "B", "C")},
        "raw_multi_action_by_branching_bucket": dict(sorted(raw_multi_branching.items())),
        "teacher_searchable_action_count": sum(int(row["branching"]) for row in rows),
        "teacher_searchable_action_count_by_source_group": dict(sorted(teacher_actions_by_group.items())),
        "teacher_searchable_action_kinds": dict(sorted(kinds.items())),
        "teacher_searchable_action_kinds_by_source_group": {group: dict(sorted(Counter(kind for r in by_group_rows.get(group, []) for kind in r["searchable_kinds"]).items())) for group in ("A", "B", "C")},
        "teacher_excluded_action_kinds": dict(sorted(excluded.items())),
        "teacher_excluded_action_count": sum(excluded.values()),
        "teacher_excluded_action_count_by_source_group": dict(sorted(excluded_actions_by_group.items())),
        "teacher_excluded_action_kinds_by_source_group": {group: dict(sorted(Counter(kind for r in by_group_rows.get(group, []) for kind in r["excluded_kinds"]).items())) for group in ("A", "B", "C")},
        "public_fingerprint_count": len(by_fp),
        "fingerprint_multiplicity": {
            "by_occurrence_count": dict(sorted(multiplicity.items())),
            "repeated_fingerprint_count": sum(
                count for occurrence_count, count in multiplicity.items() if occurrence_count > 1
            ),
            "repeated_group_count": sum(
                count for occurrence_count, count in multiplicity.items() if occurrence_count > 1
            ),
            "repeated_occurrence_count": sum(
                occurrence_count * count
                for occurrence_count, count in multiplicity.items()
                if occurrence_count > 1
            ),
            "max_multiplicity": max(multiplicity, default=0),
        },
        "within_split_deduplication": {"by_split": dict(sorted(within_split.items())), "total_discarded_duplicate_occurrences": sum(within_split.values())},
        "cross_split_fingerprint_count": len(collisions),
        "ambiguity_lower_bound": {"repeated_public_fingerprint_count": sum(len(group) > 1 for group in by_fp.values()), "cross_split_excluded_count": len(collisions), "by_n_min": disagreement_by_threshold},
        "thresholds": thresholds,
        "cost": {
            "frozen_search_simulations": search_simulations,
            "controller_wall_clock_time_s": sum(
                float(item["cost"]["wall_clock_time_s"]) for item in ledger
            ),
            "telemetry_extraction_transition_count": sum(
                int(r["telemetry_transitions"]) for r in rows
            ),
            "telemetry_extraction_cpu_time_s": "UNAVAILABLE_FROM_RETAINED_T092_ARM_SCHEMA",
            "telemetry_extraction_wall_clock_time_s": "UNAVAILABLE_FROM_RETAINED_T092_ARM_SCHEMA",
            "retained_occurrence_count": len(rows),
            "retained_bytes": "AVAILABLE_FROM_RETENTION_MANIFEST",
            "peak_memory_mib": "AVAILABLE_FROM_DETACHED_STATUS",
        },
        "rates": {"internal_occurrences_per_battle_start": len(rows) / starts if starts else None, "internal_occurrences_per_1000_search_simulations": len(rows) * 1000 / search_simulations if search_simulations else None, "by_n_min": {n: {"usable_examples_per_battle_start": thresholds[n]["usable_examples_per_battle_start"], "usable_pairs_per_battle_start": thresholds[n]["usable_pairs_per_battle_start"], "usable_examples_per_1000_search_simulations": thresholds[n]["usable_examples_per_1000_search_simulations"]["overall"], "usable_pairs_per_1000_search_simulations": thresholds[n]["usable_pairs_per_1000_search_simulations"]["overall"]} for n in thresholds}},
        "t091_primary_reference": {"n_min": 4, "leakage_safe_unique_examples": 3534, "retained_ordered_non_tie_pairs": 44846, "comparison": {"t092_unique_example_multiple": thresholds["4"]["leakage_safe_unique_examples"] / 3534 if 3534 else None, "t092_pair_multiple": thresholds["4"]["retained_ordered_non_tie_pairs"] / 44846 if 44846 else None, "t092_unique_example_delta": thresholds["4"]["leakage_safe_unique_examples"] - 3534, "t092_pair_delta": thresholds["4"]["retained_ordered_non_tie_pairs"] - 44846}},
    }


def _metrics_from_store(
    store: _MetricRowStore,
    ledger: Sequence[Mapping[str, Any]],
    geometry_observations: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Compute the formal report while retaining only one fingerprint group."""

    thresholds: dict[str, Any] = {}
    states: dict[str, dict[str, Any]] = {}
    raw_fractions: dict[str, array] = {}
    group_fractions: dict[tuple[str, str], array] = {}
    for minimum in T092_N_MINS:
        key = str(minimum)
        states[key] = {
            "eligible": 0,
            "retained": 0,
            "supported2": 0,
            "total_supported": 0,
            "pair_count": 0,
            "raw_depth": Counter(),
            "raw_branch": Counter(),
            "ret_depth": Counter(),
            "ret_branch": Counter(),
            "pair_depth": Counter(),
            "pair_branch": Counter(),
            "pair_kinds": Counter(),
            "group": {
                group: {
                    "eligible": 0,
                    "retained": 0,
                    "supported2": 0,
                    "total_supported": 0,
                    "pair_count": 0,
                    "ret_depth": Counter(),
                    "ret_branch": Counter(),
                    "pair_depth": Counter(),
                    "pair_branch": Counter(),
                }
                for group in ("A", "B", "C")
            },
        }
        raw_fractions[key] = array("d")
        for group in ("A", "B", "C"):
            group_fractions[(key, group)] = array("d")

    depth = Counter()
    branching = Counter()
    raw_multi_branching = Counter()
    single_action_by_group: Counter[str] = Counter()
    excluded = Counter()
    kinds = Counter()
    depth_by_group = {group: Counter() for group in ("A", "B", "C")}
    branching_by_group = {group: Counter() for group in ("A", "B", "C")}
    kinds_by_group = {group: Counter() for group in ("A", "B", "C")}
    excluded_by_group = {group: Counter() for group in ("A", "B", "C")}
    teacher_actions_by_group: Counter[str] = Counter()
    excluded_actions_by_group: Counter[str] = Counter()
    group_occurrences: Counter[str] = Counter()
    telemetry_transition_count = 0
    collisions = 0
    repeated_groups = 0
    multiplicity: Counter[int] = Counter()
    within_split: Counter[str] = Counter()
    disagreement: dict[str, dict[str, int]] = {
        str(minimum): {
            "repeated_fingerprint_groups": 0,
            "groups_with_defined_best_supported_action": 0,
            "groups_with_best_supported_action_disagreement": 0,
            "repeated_supported_pair_comparisons": 0,
            "pairwise_mean_sign_conflict_pairs": 0,
            "fingerprint_groups_with_pairwise_mean_sign_conflict": 0,
        }
        for minimum in T092_N_MINS
    }

    for _fingerprint, group in store.iter_groups():
        group.sort(
            key=lambda row: (
                str(row["split"]), str(row["source_identity"]),
                str(row["parent"]), str(row["occurrence"]),
            )
        )
        multiplicity[len(group)] += 1
        if len(group) > 1:
            repeated_groups += 1
        splits = {str(row["split"]) for row in group}
        collision = len(splits) > 1
        if collision:
            collisions += 1
        else:
            within_split[next(iter(splits))] += len(group) - 1

        for row in group:
            group_name = str(row["source_group"])
            telemetry_transition_count += int(row["telemetry_transitions"])
            group_occurrences[group_name] += 1
            depth_key = _depth_bucket(int(row["depth"]))
            branch_key = _branch_bucket(int(row["branching"]))
            depth[depth_key] += 1
            branching[branch_key] += 1
            depth_by_group[group_name][depth_key] += 1
            branching_by_group[group_name][branch_key] += 1
            if int(row["branching"]) == 1:
                single_action_by_group[group_name] += 1
            if int(row["branching"]) > 1:
                raw_multi_branching[branch_key] += 1
            teacher_actions_by_group[group_name] += int(row["branching"])
            excluded_actions_by_group[group_name] += len(row["excluded_kinds"])
            kinds.update(row["searchable_kinds"])
            excluded.update(row["excluded_kinds"])
            kinds_by_group[group_name].update(row["searchable_kinds"])
            excluded_by_group[group_name].update(row["excluded_kinds"])
            for minimum in T092_N_MINS:
                key = str(minimum)
                supported = int(row["supported"][key])
                states[key]["total_supported"] += supported
                states[key]["supported2"] += supported >= 2
                states[key]["group"][group_name]["total_supported"] += supported
                states[key]["group"][group_name]["supported2"] += supported >= 2
                fraction = supported / int(row["branching"])
                raw_fractions[key].append(fraction)
                group_fractions[(key, group_name)].append(fraction)

        for minimum in T092_N_MINS:
            key = str(minimum)
            state = states[key]
            eligible = (
                []
                if collision
                else [row for row in group if int(row["pairs"][key]) > 0]
            )
            state["eligible"] += len(eligible)
            state["raw_depth"].update(_depth_bucket(int(row["depth"])) for row in eligible)
            state["raw_branch"].update(_branch_bucket(int(row["branching"])) for row in eligible)
            for row in eligible:
                state["group"][str(row["source_group"])] ["eligible"] += 1
            retained = [] if collision or not eligible else [eligible[0]]
            state["retained"] += len(retained)
            for row in retained:
                group_name = str(row["source_group"])
                row_depth = _depth_bucket(int(row["depth"]))
                row_branch = _branch_bucket(int(row["branching"]))
                pairs = int(row["pairs"][key])
                state["pair_count"] += pairs
                state["ret_depth"][row_depth] += 1
                state["ret_branch"][row_branch] += 1
                state["pair_depth"][row_depth] += pairs
                state["pair_branch"][row_branch] += pairs
                state["pair_kinds"].update(row["paired_kinds"][key])
                group_state = state["group"][group_name]
                group_state["retained"] += 1
                group_state["pair_count"] += pairs
                group_state["ret_depth"][row_depth] += 1
                group_state["ret_branch"][row_branch] += 1
                group_state["pair_depth"][row_depth] += pairs
                group_state["pair_branch"][row_branch] += pairs

        if len(group) > 1:
            for minimum in T092_N_MINS:
                key = str(minimum)
                report = disagreement[key]
                report["repeated_fingerprint_groups"] += 1
                best: set[str] = set()
                pair_observations: Counter[str] = Counter()
                preferences: dict[str, set[str]] = defaultdict(set)
                for row in group:
                    supported = [
                        (action, visits, mean)
                        for action, visits, mean in row["supported_action_values"]
                        if int(visits) >= minimum
                    ]
                    if supported:
                        best.add(min(supported, key=lambda item: (-float(item[2]), item[0]))[0])
                    for left_index, left in enumerate(supported):
                        for right in supported[left_index + 1:]:
                            delta = float(left[2]) - float(right[2])
                            if abs(delta) <= 1e-9:
                                continue
                            action_a, action_b = sorted((left[0], right[0]))
                            pair_key = f"{action_a}|{action_b}"
                            pair_observations[pair_key] += 1
                            preferences[pair_key].add(left[0] if delta > 0 else right[0])
                if best:
                    report["groups_with_defined_best_supported_action"] += 1
                if len(best) >= 2:
                    report["groups_with_best_supported_action_disagreement"] += 1
                group_conflict = False
                for pair_key, signs in preferences.items():
                    if pair_observations[pair_key] >= 2:
                        report["repeated_supported_pair_comparisons"] += 1
                    if pair_observations[pair_key] >= 2 and len(signs) >= 2:
                        report["pairwise_mean_sign_conflict_pairs"] += 1
                        group_conflict = True
                if group_conflict:
                    report["fingerprint_groups_with_pairwise_mean_sign_conflict"] += 1

    group_sims: Counter[str] = Counter()
    starts_by_group: Counter[str] = Counter()
    for item in ledger:
        group_name = str(item["source_group"])
        group_sims[group_name] += int(item["terminal"].get("battle_decision_count", 0)) * 400
        starts_by_group[group_name] += 1
    total_sims = sum(group_sims.values())
    starts = len(ledger)
    for minimum in T092_N_MINS:
        key = str(minimum)
        state = states[key]
        group_detail: dict[str, Any] = {}
        by_group = Counter()
        for group_name in ("A", "B", "C"):
            gs = state["group"][group_name]
            if gs["retained"]:
                by_group[group_name] = gs["retained"]
            group_detail[group_name] = {
                "internal_occurrence_count": group_occurrences[group_name],
                "raw_occurrences_with_pairs": gs["eligible"],
                "leakage_safe_unique_examples": gs["retained"],
                "nodes_with_at_least_two_supported_actions": gs["supported2"],
                "total_supported_actions": gs["total_supported"],
                "retained_ordered_non_tie_pairs": gs["pair_count"],
                "supported_teacher_searchable_fraction": _distribution(
                    group_fractions[(key, group_name)]
                ),
                "by_depth_bucket": dict(sorted(gs["ret_depth"].items())),
                "by_branching_bucket": dict(sorted(gs["ret_branch"].items())),
                "pairs_by_depth_bucket": dict(sorted(gs["pair_depth"].items())),
                "pairs_by_branching_bucket": dict(sorted(gs["pair_branch"].items())),
                "usable_examples_per_1000_search_simulations": (
                    gs["retained"] * 1_000 / group_sims[group_name]
                    if group_sims[group_name] else None
                ),
                "usable_pairs_per_1000_search_simulations": (
                    gs["pair_count"] * 1_000 / group_sims[group_name]
                    if group_sims[group_name] else None
                ),
                "usable_examples_per_battle_start": (
                    gs["retained"] / starts_by_group[group_name]
                    if starts_by_group[group_name] else None
                ),
                "usable_pairs_per_battle_start": (
                    gs["pair_count"] / starts_by_group[group_name]
                    if starts_by_group[group_name] else None
                ),
            }
        thresholds[key] = {
            "raw_occurrences_with_pairs": state["eligible"],
            "leakage_safe_unique_examples": state["retained"],
            "nodes_with_at_least_two_supported_actions": state["supported2"],
            "total_supported_actions": state["total_supported"],
            "supported_teacher_searchable_fraction": _distribution(raw_fractions[key]),
            "retained_ordered_non_tie_pairs": state["pair_count"],
            "raw_examples_by_depth_bucket": dict(sorted(state["raw_depth"].items())),
            "raw_examples_by_branching_bucket": dict(sorted(state["raw_branch"].items())),
            "by_source_group": dict(sorted(by_group.items())),
            "by_source_group_detail": group_detail,
            "by_depth_bucket": dict(sorted(state["ret_depth"].items())),
            "by_branching_bucket": dict(sorted(state["ret_branch"].items())),
            "pairs_by_depth_bucket": dict(sorted(state["pair_depth"].items())),
            "pairs_by_branching_bucket": dict(sorted(state["pair_branch"].items())),
            "action_kinds_with_retained_pairs": sorted(state["pair_kinds"]),
            "usable_examples_per_1000_search_simulations": {
                "overall": state["retained"] * 1_000 / total_sims if total_sims else None,
                "by_source_group": {
                    group: group_detail[group]["usable_examples_per_1000_search_simulations"]
                    for group in ("A", "B", "C")
                },
            },
            "usable_pairs_per_1000_search_simulations": {
                "overall": state["pair_count"] * 1_000 / total_sims if total_sims else None,
                "by_source_group": {
                    group: group_detail[group]["usable_pairs_per_1000_search_simulations"]
                    for group in ("A", "B", "C")
                },
            },
            "usable_examples_per_battle_start": state["retained"] / starts if starts else None,
            "usable_pairs_per_battle_start": state["pair_count"] / starts if starts else None,
            "ambiguity_lower_bound": disagreement[key],
        }

    single = sum(single_action_by_group.values())
    group_node_totals = {
        group: {
            "stable_internal_player_decision_nodes": group_occurrences[group],
            "stable_internal_single_action_nodes": single_action_by_group[group],
            "stable_internal_multi_action_nodes": group_occurrences[group] - single_action_by_group[group],
        }
        for group in ("A", "B", "C")
    }
    repeated_occurrences = sum(
        occurrence_count * count
        for occurrence_count, count in multiplicity.items()
        if occurrence_count > 1
    )
    repeated_count = sum(
        count for occurrence_count, count in multiplicity.items()
        if occurrence_count > 1
    )
    return {
        "schema_id": "t092-internal-search-state-formal-metrics-v3",
        "internal_occurrence_count": store.count,
        "node_totals": {
            "depth_zero_root_count": 0,
            "stable_internal_player_decision_nodes": store.count,
            "stable_internal_single_action_nodes": single,
            "stable_internal_multi_action_nodes": store.count - single,
            "by_source_group": group_node_totals,
            "tree_geometry": _tree_geometry_metrics(geometry_observations or []),
        },
        "depth_zero_root_count": 0,
        "depth_distribution": dict(sorted(depth.items())),
        "depth_distribution_by_source_group": {
            group: dict(sorted(depth_by_group[group].items())) for group in ("A", "B", "C")
        },
        "branching_distribution": dict(sorted(branching.items())),
        "branching_distribution_by_source_group": {
            group: dict(sorted(branching_by_group[group].items())) for group in ("A", "B", "C")
        },
        "raw_multi_action_by_branching_bucket": dict(sorted(raw_multi_branching.items())),
        "teacher_searchable_action_count": sum(teacher_actions_by_group.values()),
        "teacher_searchable_action_count_by_source_group": dict(sorted(teacher_actions_by_group.items())),
        "teacher_searchable_action_kinds": dict(sorted(kinds.items())),
        "teacher_searchable_action_kinds_by_source_group": {
            group: dict(sorted(kinds_by_group[group].items())) for group in ("A", "B", "C")
        },
        "teacher_excluded_action_kinds": dict(sorted(excluded.items())),
        "teacher_excluded_action_count": sum(excluded.values()),
        "teacher_excluded_action_count_by_source_group": {
            group: excluded_actions_by_group[group]
            for group in sorted(excluded_actions_by_group)
        },
        "teacher_excluded_action_kinds_by_source_group": {
            group: dict(sorted(excluded_by_group[group].items())) for group in ("A", "B", "C")
        },
        "public_fingerprint_count": sum(multiplicity.values()),
        "fingerprint_multiplicity": {
            "by_occurrence_count": dict(sorted(multiplicity.items())),
            "repeated_fingerprint_count": repeated_count,
            "repeated_group_count": repeated_count,
            "repeated_occurrence_count": repeated_occurrences,
            "max_multiplicity": max(multiplicity, default=0),
        },
        "within_split_deduplication": {
            "by_split": dict(sorted(within_split.items())),
            "total_discarded_duplicate_occurrences": sum(within_split.values()),
        },
        "cross_split_fingerprint_count": collisions,
        "ambiguity_lower_bound": {
            "repeated_public_fingerprint_count": repeated_groups,
            "cross_split_excluded_count": collisions,
            "by_n_min": disagreement,
        },
        "thresholds": thresholds,
        "cost": {
            "frozen_search_simulations": total_sims,
            "controller_wall_clock_time_s": sum(float(item["cost"]["wall_clock_time_s"]) for item in ledger),
            "telemetry_extraction_transition_count": telemetry_transition_count,
            "telemetry_extraction_cpu_time_s": "UNAVAILABLE_FROM_RETAINED_T092_ARM_SCHEMA",
            "telemetry_extraction_wall_clock_time_s": "UNAVAILABLE_FROM_RETAINED_T092_ARM_SCHEMA",
            "retained_occurrence_count": store.count,
            "retained_bytes": "AVAILABLE_FROM_RETENTION_MANIFEST",
            "peak_memory_mib": "AVAILABLE_FROM_DETACHED_STATUS",
        },
        "rates": {
            "internal_occurrences_per_battle_start": store.count / starts if starts else None,
            "internal_occurrences_per_1000_search_simulations": store.count * 1000 / total_sims if total_sims else None,
            "by_n_min": {
                key: {
                    "usable_examples_per_battle_start": thresholds[key]["usable_examples_per_battle_start"],
                    "usable_pairs_per_battle_start": thresholds[key]["usable_pairs_per_battle_start"],
                    "usable_examples_per_1000_search_simulations": thresholds[key]["usable_examples_per_1000_search_simulations"]["overall"],
                    "usable_pairs_per_1000_search_simulations": thresholds[key]["usable_pairs_per_1000_search_simulations"]["overall"],
                }
                for key in thresholds
            },
        },
        "t091_primary_reference": {
            "n_min": 4,
            "leakage_safe_unique_examples": 3534,
            "retained_ordered_non_tie_pairs": 44846,
            "comparison": {
                "t092_unique_example_multiple": thresholds["4"]["leakage_safe_unique_examples"] / 3534,
                "t092_pair_multiple": thresholds["4"]["retained_ordered_non_tie_pairs"] / 44846,
                "t092_unique_example_delta": thresholds["4"]["leakage_safe_unique_examples"] - 3534,
                "t092_pair_delta": thresholds["4"]["retained_ordered_non_tie_pairs"] - 44846,
            },
        },
    }


def _distribution(values: Sequence[float]) -> dict[str, float | int | None]:
    if not values:
        return {"count": 0, "min": None, "median": None, "max": None}
    ordered = sorted(values)
    return {"count": len(ordered), "min": ordered[0], "median": ordered[(len(ordered) - 1) // 2], "max": ordered[-1]}


def write_t092_formal_json(path: str | Path, value: Mapping[str, Any], *, schema_id: str) -> dict[str, Any]:
    destination = Path(path).resolve()
    if destination.exists():
        raise T092FormalError("refusing to overwrite retained T092 formal output")
    destination.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(dict(value), sort_keys=True, separators=(",", ":"), allow_nan=False).encode() + b"\n"
    descriptor = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(encoded)
    return {"path": str(destination), "sha256": hashlib.sha256(encoded).hexdigest(), "size_bytes": len(encoded), "schema_id": schema_id}
