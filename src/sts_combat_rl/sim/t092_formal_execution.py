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
from collections import Counter, defaultdict
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict
from pathlib import Path
from typing import Any

from sts_combat_rl.sim.t090_battle_student import canonical_sha256, validate_t090_split_manifest
from sts_combat_rl.sim.t092_canary import (
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


def validate_t092_t090_root_reference(value: Mapping[str, Any], *, split_manifest: Mapping[str, Any]) -> dict[str, Any]:
    """Require the canonical T090 root comparison table, never inferred rows."""
    required = {"schema_id", "schema_version", "task_id", "split_manifest_sha256", "source_ledger", "rows", "rows_sha256"}
    if not isinstance(value, Mapping) or set(value) != required or value.get("schema_id") != T092_T090_ROOT_REFERENCE_SCHEMA_ID or value.get("schema_version") != 1 or value.get("task_id") != "T092" or value.get("split_manifest_sha256") != canonical_sha256(split_manifest):
        raise T092FormalError("T092 T090 root reference is malformed")
    _artifact(value.get("source_ledger"), "T090 source ledger")
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


def _finite(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))


def _accepted_canary_reference(value: object, *, split_manifest: Mapping[str, Any]) -> dict[str, Any]:
    """Hash-read the retained parity evidence; a filename is never evidence."""
    reference = _artifact(value, "accepted T092 canary")
    if reference["schema_id"] != "t092-paired-semantic-parity-canary-v1":
        raise T092FormalError("accepted T092 canary has an unexpected schema")
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
    return reference


def _formal_input_identities(value: object) -> dict[str, Any]:
    """Bind every accepted upstream fact; no filename/default substitutes."""
    required = {"formal_restore_manifest", "arm_process_specs", "t087_source_cohort",
                "t090_source_ledger", "t091_reference", "task_native_provenance"}
    if not isinstance(value, Mapping) or set(value) != required:
        raise T092FormalError("T092 formal input identities are incomplete")
    result = dict(value)
    for key in ("formal_restore_manifest", "t087_source_cohort", "t090_source_ledger", "t091_reference", "task_native_provenance"):
        _artifact(result[key], key)
    specs = result["arm_process_specs"]
    if not isinstance(specs, Mapping) or set(specs) != {"ON"} or not isinstance(specs["ON"], Mapping) or specs["ON"].get("native_identity") != T092_NATIVE_IDENTITY:
        raise T092FormalError("T092 formal ON native process identity is invalid")
    return result


def build_t092_formal_authorization_template(*, implementation_head: str, split_manifest: Mapping[str, Any],
                                             root_reference: Mapping[str, Any], canary_evidence: Mapping[str, Any],
                                             input_identities: Mapping[str, Any], output_root: str | Path,
                                             shard_count: int = T092_FORMAL_DEFAULT_SHARDS,
                                             worker_count: int = T092_FORMAL_DEFAULT_WORKERS) -> dict[str, Any]:
    if not _sha(implementation_head):
        raise T092FormalError("T092 formal implementation/input identity is invalid")
    inputs = _formal_input_identities(input_identities)
    plan = build_t092_formal_plan(split_manifest, shard_count=shard_count, worker_count=worker_count)
    reference = validate_t092_t090_root_reference(root_reference, split_manifest=split_manifest)
    canary_ref = _accepted_canary_reference(canary_evidence, split_manifest=split_manifest)
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
    prepared = build_t092_formal_authorization_template(implementation_head=implementation_head, split_manifest=split_manifest,
        root_reference=root_reference, canary_evidence=canary_evidence, input_identities=input_identities, output_root=output_root,
        shard_count=shard_count, worker_count=worker_count)
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
    records: list[dict[str, Any]] = []
    for source in sources:
        try:
            raw = runner(source, worker)
        except Exception as exc:
            raise T092FormalError("T092 formal runner failed before complete shard retention") from exc
        records.append(_formal_arm(raw, source, worker, implementation_head))
    if len(records) != len(sources):
        raise T092FormalError("T092 formal shard is incomplete")
    return {"schema_id": T092_FORMAL_SHARD_SCHEMA_ID, "schema_version": 1, "task_id": "T092",
            "authorization_id": authorization["authorization_id"], "implementation_head": implementation_head,
            "formal_plan_sha256": canonical_sha256(plan), "topology": topology, "records": records,
            "records_sha256": canonical_sha256(records)}


def _root_projection(record: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in record["decision_records"]:
        semantic = item["root_semantics"]
        rows.append({"decision_identity": item["decision_identity"], "ordered_root_actions": [
            {"action_identity": row["action_identity"], "visits": row["visits"], "mean_value": row["mean_value"]}
            for row in semantic["ordered_root_actions"]], "selected_action_identity": semantic["selected_action_identity"]})
    return rows


def _depth_bucket(depth: int) -> str:
    return "1" if depth == 1 else "2" if depth == 2 else "3-4" if depth <= 4 else "5-8" if depth <= 8 else "9+"


def _branch_bucket(size: int) -> str:
    return "2" if size == 2 else "3-4" if size <= 4 else "5-8" if size <= 8 else "9-16" if size <= 16 else "17+"


def _classification(metrics: Mapping[str, Any], *, root_ok: bool, canary_ok: bool, firewall_ok: bool) -> str:
    if not (root_ok and canary_ok):
        return "INTERNAL_TELEMETRY_SEMANTIC_PARITY_INVALID"
    if not firewall_ok:
        return "INTERNAL_SEARCH_INFORMATION_BOUNDARY_INVALID"
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
                                shards: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
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
    reference = validate_t092_t090_root_reference(root_reference, split_manifest=split_manifest)
    all_occurrences: list[T092Occurrence] = []
    observed_roots: list[dict[str, Any]] = []
    ledger: list[dict[str, Any]] = []
    artifacts: list[dict[str, Any]] = []
    for index, shard in enumerate(shards):
        topology = validate_t092_formal_authorization(authorization, implementation_head=implementation_head,
            split_manifest=split_manifest, root_reference=reference, canary_evidence=canary_evidence,
            input_identities=input_identities, output_root=output_root, shard_index=index,
            shard_count=shard_count, worker_count=worker_count)
        if not isinstance(shard, Mapping) or set(shard) != {"schema_id", "schema_version", "task_id", "authorization_id", "implementation_head", "formal_plan_sha256", "topology", "records", "records_sha256"} or shard.get("schema_id") != T092_FORMAL_SHARD_SCHEMA_ID or shard.get("schema_version") != 1 or shard.get("task_id") != "T092" or shard.get("authorization_id") != authorization["authorization_id"] or shard.get("implementation_head") != implementation_head or shard.get("formal_plan_sha256") != canonical_sha256(plan) or shard.get("topology") != topology or not isinstance(shard.get("records"), Sequence) or shard.get("records_sha256") != canonical_sha256(shard["records"]):
            raise T092FormalError("T092 formal shard provenance is invalid")
        expected_sources = [s for ordinal, s in enumerate(plan["sources"]) if ordinal % shard_count == index]
        if len(shard["records"]) != len(expected_sources):
            raise T092FormalError("T092 formal shard record count is incomplete")
        worker = {"stage_worker_count": worker_count, "worker_index": index, "shard_count": shard_count, "shard_index": index}
        for record, source in zip(shard["records"], expected_sources, strict=True):
            arm = _formal_arm(record, source, worker, implementation_head)
            observed_roots.extend(_root_projection(arm))
            ledger.append({"source_identity": source["source_identity"], "source_group": source["source_group"], "split": source["split"], "canonical_position": source["canonical_position"], "worker": worker, "terminal": arm["terminal"], "cost": arm["cost"]})
            decision_ids = {item["decision_identity"] for item in arm["decision_records"]}
            rows = [validate_retained_occurrence(row, source_identity=source["source_identity"], source_group=source["source_group"], split=source["split"], parent_root_decision_identities=decision_ids) for row in arm["internal_occurrences"]]
            validate_parent_bound_occurrence_identities(rows)
            all_occurrences.extend(rows)
        artifacts.append({"shard_index": index, "records_sha256": shard["records_sha256"], "record_count": len(shard["records"])})
    expected = list(reference["rows"])
    root_ok = observed_roots == expected
    if not root_ok:
        raise T092FormalError("INTERNAL_TELEMETRY_SEMANTIC_PARITY_INVALID: formal root reproduction mismatch")
    metrics = _metrics(all_occurrences, ledger)
    classification = _classification(metrics, root_ok=root_ok, canary_ok=True, firewall_ok=True)
    return {"schema_id": T092_FORMAL_EVIDENCE_SCHEMA_ID, "schema_version": 1, "task_id": "T092",
            "formal_execution_authorized": True, "training_eligible": False,
            "implementation_head": implementation_head, "formal_plan_sha256": canonical_sha256(plan),
            "native_identity": dict(T092_NATIVE_IDENTITY), "teacher_config": dict(T092_FROZEN_TEACHER_CONFIG),
            "execution_config": dict(T092_CANARY_EXECUTION_CONFIG), "source_worker_ledger": ledger,
            "source_worker_ledger_sha256": canonical_sha256(ledger), "root_reproduction": {"passed": True, "expected_decision_count": 6369, "s0_complete_root_q": 309},
            "internal_shard_manifest": artifacts, "metrics": metrics,
            "terminal_classification": classification,
            "successor_decision": "Planner may consider a separate public-only distillation task" if classification == "INTERNAL_SEARCH_SURFACE_DENSE_ENOUGH" else "Do not weaken T092 thresholds; use the contract-specified successor boundary"}


def _metrics(rows: Sequence[T092Occurrence], ledger: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Compute deterministic formal reports; candidates are depth>=1 by validator."""
    by_fp: dict[str, list[T092Occurrence]] = defaultdict(list)
    depth, branching, raw_multi_branching = Counter(), Counter(), Counter()
    excluded, kinds = Counter(), Counter()
    for row in rows:
        by_fp[row.fingerprint].append(row)
        depth[_depth_bucket(row.tree_depth)] += 1
        branching[_branch_bucket(len(row.searchable_actions))] += 1
        if len(row.searchable_actions) > 1:
            raw_multi_branching[_branch_bucket(len(row.searchable_actions))] += 1
        kinds.update(action["action"]["kind"] for action in row.searchable_actions)
        excluded.update(action["action"]["kind"] for action in row.excluded_actions)
    collisions = {fp for fp, grouped in by_fp.items() if len({r.split for r in grouped}) > 1}
    thresholds: dict[str, Any] = {}
    for minimum in T092_N_MINS:
        eligible = [r for fp, group in by_fp.items() if fp not in collisions for r in group if support_pairs(r, minimum)]
        canonical: dict[tuple[str, str], T092Occurrence] = {}
        for row in sorted(eligible, key=lambda r: (r.split, r.source_identity, r.parent_root_decision_identity, r.occurrence_identity)):
            canonical.setdefault((row.split, row.fingerprint), row)
        retained = list(canonical.values())
        pair_kinds = Counter(
            action["action"]["kind"]
            for row in retained
            for pair in support_pairs(row, minimum)
            for action in pair
        )
        group_sims: Counter[str] = Counter()
        for item in ledger:
            group_sims[str(item["source_group"])] += (
                int(item["terminal"].get("battle_decision_count", 0)) * 400
            )
        total_sims = sum(group_sims.values())
        by_group = Counter(row.source_group for row in retained)
        thresholds[str(minimum)] = {"raw_occurrences_with_pairs": len(eligible), "leakage_safe_unique_examples": len(retained),
            "retained_ordered_non_tie_pairs": sum(len(support_pairs(r, minimum)) for r in retained),
            "by_source_group": dict(sorted(by_group.items())),
            "by_depth_bucket": dict(sorted(Counter(_depth_bucket(r.tree_depth) for r in retained).items())),
            "by_branching_bucket": dict(sorted(Counter(_branch_bucket(len(r.searchable_actions)) for r in retained).items())),
            "action_kinds_with_retained_pairs": sorted(pair_kinds),
            "usable_examples_per_1000_search_simulations": {
                "overall": (len(retained) * 1_000 / total_sims) if total_sims else None,
                "by_source_group": {
                    group: (by_group[group] * 1_000 / group_sims[group]) if group_sims[group] else None
                    for group in ("A", "B", "C")
                },
            },
        }
    search_simulations = sum(int(item["terminal"].get("battle_decision_count", 0)) * 400 for item in ledger)
    return {"schema_id": "t092-internal-search-state-formal-metrics-v1", "internal_occurrence_count": len(rows),
            "depth_zero_root_count": 0, "depth_distribution": dict(sorted(depth.items())), "branching_distribution": dict(sorted(branching.items())),
            "raw_multi_action_by_branching_bucket": dict(sorted(raw_multi_branching.items())),
            "teacher_searchable_action_kinds": dict(sorted(kinds.items())), "teacher_excluded_action_kinds": dict(sorted(excluded.items())),
            "public_fingerprint_count": len(by_fp), "cross_split_fingerprint_count": len(collisions),
            "thresholds": thresholds, "cost": {"frozen_search_simulations": search_simulations,
                "controller_wall_clock_time_s": sum(float(item["cost"]["wall_clock_time_s"]) for item in ledger),
                "telemetry_extraction_transition_count": sum(r.telemetry_cost["telemetry_extraction_transition_count"] for r in rows),
                "retained_occurrence_count": len(rows)},
            "ambiguity_lower_bound": {"repeated_public_fingerprint_count": sum(len(group) > 1 for group in by_fp.values()), "cross_split_excluded_count": len(collisions)},
            "t091_primary_reference": {"n_min": 4, "leakage_safe_unique_examples": 3534, "retained_ordered_non_tie_pairs": 44846}}


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
