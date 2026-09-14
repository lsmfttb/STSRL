"""Bounded, non-authoritative T090 canary workflow plumbing.

The real restore/Search/controlled-run implementation is deliberately injected
through :class:`T090CanaryStartRunner`.  This module owns the exact twelve-start
selection and fail-closed evidence shape; it does not implement a simulator,
restore path, or local Battle transition.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import Protocol

from sts_combat_rl.sim.t090_battle_student import (
    T090_TASK_ID,
    T090_TEACHER_CONFIG,
    T090SplitEntry,
    build_t090_target_provenance,
    canonical_sha256,
    materialize_t090_decision,
    validate_t090_split_manifest,
)

T090_CANARY_EVIDENCE_SCHEMA_ID = "t090-bounded-canary-evidence-v1"
T090_CANARY_SOURCE_EXECUTION_SCHEMA_ID = "t090-canary-source-execution-ledger-v1"
T090_CANARY_START_COUNT = 12
T090_CANARY_CLASSIFICATION = "MECHANICS_COVERAGE_ONLY_NONAUTHORITATIVE"


class T090CanaryError(ValueError):
    """A bounded canary input or execution record is incomplete."""


class T090CanaryStartRunner(Protocol):
    """Restore and execute one selected start through existing native seams.

    A production runner must use the accepted T085 restore boundary and
    ``execute_controlled_run`` with frozen native Search-v2@400.  It returns
    data only; this layer performs no simulator calls or artifact writes.
    """

    def __call__(self, source: T090SplitEntry) -> Mapping[str, object]: ...


def _mapping(value: object, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise T090CanaryError(f"{label} must be a mapping")
    return value


def _sequence(value: object, label: str) -> Sequence[object]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise T090CanaryError(f"{label} must be a sequence")
    return value


def _non_negative_int(value: object, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise T090CanaryError(f"{label} must be a non-negative integer")
    return value


def _positive_int(value: object, label: str) -> int:
    result = _non_negative_int(value, label)
    if result == 0:
        raise T090CanaryError(f"{label} must be positive")
    return result


def _finite_non_negative(value: object, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise T090CanaryError(f"{label} must be a finite non-negative number")
    result = float(value)
    if result < 0.0 or not math.isfinite(result):
        raise T090CanaryError(f"{label} must be a finite non-negative number")
    return result


def select_t090_canary_sources(
    split_manifest: Mapping[str, object], *, start_offset: int, start_count: int = 12
) -> tuple[T090SplitEntry, ...]:
    """Select one exact canonical twelve-start window from the frozen cohort."""

    if (
        isinstance(start_offset, bool)
        or not isinstance(start_offset, int)
        or start_offset < 0
    ):
        raise T090CanaryError("T090 canary start_offset must be non-negative")
    if start_count != T090_CANARY_START_COUNT:
        raise T090CanaryError("T090 canary must contain exactly 12 starts")
    entries = validate_t090_split_manifest(split_manifest)
    selected = entries[start_offset : start_offset + start_count]
    if len(selected) != T090_CANARY_START_COUNT:
        raise T090CanaryError("T090 canary range is outside the exact 413-start cohort")
    return selected


def _validate_worker(value: object) -> dict[str, int]:
    worker = _mapping(value, "canary worker")
    required = {"stage_worker_count", "worker_index", "shard_count", "shard_index"}
    if set(worker) != required:
        raise T090CanaryError("T090 canary worker fields are incomplete")
    result = {
        "stage_worker_count": _positive_int(
            worker["stage_worker_count"], "worker.stage_worker_count"
        ),
        "worker_index": _non_negative_int(
            worker["worker_index"], "worker.worker_index"
        ),
        "shard_count": _positive_int(worker["shard_count"], "worker.shard_count"),
        "shard_index": _non_negative_int(worker["shard_index"], "worker.shard_index"),
    }
    if result["worker_index"] >= result["stage_worker_count"]:
        raise T090CanaryError("T090 canary worker index is outside worker count")
    if result["shard_index"] >= result["shard_count"]:
        raise T090CanaryError("T090 canary shard index is outside shard count")
    return result


def _validate_cost(value: object) -> dict[str, object]:
    cost = _mapping(value, "canary cost")
    required = {"wall_clock_time_s", "root_decision_count", "search_simulation_count"}
    if set(cost) != required:
        raise T090CanaryError("T090 canary cost fields are incomplete")
    result = {
        "wall_clock_time_s": _finite_non_negative(
            cost["wall_clock_time_s"], "cost.wall_clock_time_s"
        ),
        "root_decision_count": _non_negative_int(
            cost["root_decision_count"], "cost.root_decision_count"
        ),
        "search_simulation_count": _non_negative_int(
            cost["search_simulation_count"], "cost.search_simulation_count"
        ),
    }
    if result["search_simulation_count"] != (
        result["root_decision_count"] * T090_TEACHER_CONFIG["simulations"]
    ):
        raise T090CanaryError(
            "T090 canary search cost does not bind Search-v2@400 per root decision"
        )
    return result


def _validate_teacher_rows(
    value: object, *, source: T090SplitEntry
) -> list[dict[str, object]]:
    rows = _sequence(value, "canary teacher rows")
    retained: list[dict[str, object]] = []
    seen: set[str] = set()
    allowed = {
        "source_identity",
        "source_group",
        "decision_identity",
        "public_input",
        "root_rows",
    }
    for raw in rows:
        row = _mapping(raw, "canary teacher row")
        if set(row) != allowed:
            raise T090CanaryError("T090 canary teacher row has unexpected provenance")
        example, observed = materialize_t090_decision(row, split_entry=source)
        if observed.decision_identity in seen:
            raise T090CanaryError(
                "T090 canary source has duplicate decision identities"
            )
        seen.add(observed.decision_identity)
        # Both eligible and ineligible teacher decisions are retained for this
        # mechanics/coverage-only artifact.  The formal target gate remains
        # exclusively in materialize_t090_targets with its 413-start ledger.
        del example
        retained.append(dict(row))
    return retained


def _validate_runner_record(
    value: Mapping[str, object], *, source: T090SplitEntry
) -> tuple[dict[str, object], list[dict[str, object]]]:
    required = {
        "source_identity",
        "source_group",
        "split",
        "canonical_position",
        "teacher_config",
        "restore_public_legal_parity",
        "completed",
        "terminal_reached",
        "terminal_evidence",
        "worker",
        "cost",
        "teacher_rows",
    }
    if set(value) != required:
        raise T090CanaryError("T090 canary runner record has an unexpected shape")
    if (
        value.get("source_identity") != source.source_identity
        or value.get("source_group") != source.source_group
        or value.get("split") != source.split
        or value.get("canonical_position") != source.canonical_position
        or value.get("teacher_config") != T090_TEACHER_CONFIG
        or value.get("restore_public_legal_parity") is not True
        or value.get("completed") is not True
        or value.get("terminal_reached") is not True
    ):
        raise T090CanaryError("T090 canary runner record drifted from frozen inputs")
    terminal = _mapping(value.get("terminal_evidence"), "terminal evidence")
    if (
        not terminal
        or not isinstance(terminal.get("outcome"), str)
        or not terminal["outcome"]
    ):
        raise T090CanaryError("T090 canary terminal evidence is incomplete")
    teacher_rows = _validate_teacher_rows(value.get("teacher_rows"), source=source)
    entry = {
        "source_identity": source.source_identity,
        "source_group": source.source_group,
        "split": source.split,
        "canonical_position": source.canonical_position,
        "restore_public_legal_parity": True,
        "completed": True,
        "terminal_reached": True,
        "status": "COMPLETED_VALID",
        "terminal_evidence": dict(terminal),
        "worker": _validate_worker(value.get("worker")),
        "cost": _validate_cost(value.get("cost")),
    }
    return entry, teacher_rows


def validate_t090_canary_source_execution_ledger(
    value: Mapping[str, object],
    *,
    split_manifest: Mapping[str, object],
    start_offset: int,
) -> tuple[T090SplitEntry, ...]:
    """Validate a selected-only ledger without accepting it as the formal one."""

    selected = select_t090_canary_sources(split_manifest, start_offset=start_offset)
    if (
        value.get("schema_id") != T090_CANARY_SOURCE_EXECUTION_SCHEMA_ID
        or value.get("schema_version") != 1
        or value.get("task_id") != T090_TASK_ID
        or value.get("scope") != "bounded_canary"
        or value.get("formal_execution_authorized") is not False
        or value.get("selected_start_offset") != start_offset
        or value.get("selected_start_count") != T090_CANARY_START_COUNT
    ):
        raise T090CanaryError("T090 canary source execution ledger schema is invalid")
    rows = _sequence(value.get("entries"), "canary source execution entries")
    if value.get("entries_sha256") != canonical_sha256(rows):
        raise T090CanaryError("T090 canary source execution ledger hash mismatches")
    if len(rows) != T090_CANARY_START_COUNT:
        raise T090CanaryError("T090 canary source execution ledger is not 12 starts")
    seen: set[str] = set()
    for expected, raw in zip(selected, rows, strict=True):
        entry = _mapping(raw, "canary source execution entry")
        if entry.get("source_identity") in seen:
            raise T090CanaryError(
                "T090 canary source execution ledger duplicates a start"
            )
        seen.add(str(entry.get("source_identity")))
        required = {
            "source_identity",
            "source_group",
            "split",
            "canonical_position",
            "restore_public_legal_parity",
            "completed",
            "terminal_reached",
            "status",
            "terminal_evidence",
            "worker",
            "cost",
        }
        if (
            set(entry) != required
            or entry.get("source_identity") != expected.source_identity
            or entry.get("source_group") != expected.source_group
            or entry.get("split") != expected.split
            or entry.get("canonical_position") != expected.canonical_position
            or entry.get("restore_public_legal_parity") is not True
            or entry.get("completed") is not True
            or entry.get("terminal_reached") is not True
            or entry.get("status") != "COMPLETED_VALID"
        ):
            raise T090CanaryError("T090 canary source execution entry is invalid")
        terminal = _mapping(entry.get("terminal_evidence"), "terminal evidence")
        if not terminal or not isinstance(terminal.get("outcome"), str):
            raise T090CanaryError("T090 canary terminal evidence is incomplete")
        _validate_worker(entry.get("worker"))
        _validate_cost(entry.get("cost"))
    return selected


def _source_execution_summary(
    entries: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    return {
        "selected_start_count": len(entries),
        "completed_start_count": sum(item["completed"] is True for item in entries),
        "terminal_reached_count": sum(
            item["terminal_reached"] is True for item in entries
        ),
        "restore_public_legal_parity_count": sum(
            item["restore_public_legal_parity"] is True for item in entries
        ),
        "total_wall_clock_time_s": sum(
            float(_mapping(item["cost"], "canary cost")["wall_clock_time_s"])
            for item in entries
        ),
        "total_root_decision_count": sum(
            int(_mapping(item["cost"], "canary cost")["root_decision_count"])
            for item in entries
        ),
        "total_search_simulation_count": sum(
            int(_mapping(item["cost"], "canary cost")["search_simulation_count"])
            for item in entries
        ),
    }


def execute_t090_canary(
    *,
    split_manifest: Mapping[str, object],
    native_source_manifest: Mapping[str, object],
    start_offset: int,
    runner: T090CanaryStartRunner,
) -> dict[str, object]:
    """Run an injected bounded canary workflow; never a formal T090 run."""

    if not callable(runner):
        raise T090CanaryError("T090 canary runner must be callable")
    selected = select_t090_canary_sources(split_manifest, start_offset=start_offset)
    target_provenance = build_t090_target_provenance(
        split_manifest, native_source_manifest=native_source_manifest
    )
    entries: list[dict[str, object]] = []
    teacher_rows: list[dict[str, object]] = []
    for source in selected:
        raw = runner(source)
        if not isinstance(raw, Mapping):
            raise T090CanaryError("T090 canary runner did not return a mapping")
        entry, rows = _validate_runner_record(raw, source=source)
        entries.append(entry)
        teacher_rows.extend(rows)
    ledger = {
        "schema_id": T090_CANARY_SOURCE_EXECUTION_SCHEMA_ID,
        "schema_version": 1,
        "task_id": T090_TASK_ID,
        "scope": "bounded_canary",
        "formal_execution_authorized": False,
        "selected_start_offset": start_offset,
        "selected_start_count": T090_CANARY_START_COUNT,
        "entries": entries,
        "entries_sha256": canonical_sha256(entries),
    }
    evidence = {
        "schema_id": T090_CANARY_EVIDENCE_SCHEMA_ID,
        "schema_version": 1,
        "task_id": T090_TASK_ID,
        "classification": T090_CANARY_CLASSIFICATION,
        "formal_execution_authorized": False,
        "training_eligible": False,
        "target_provenance": target_provenance,
        "split_manifest_sha256": canonical_sha256(split_manifest),
        "selected_start_offset": start_offset,
        "selected_start_count": T090_CANARY_START_COUNT,
        "source_execution_ledger": ledger,
        "source_execution_summary": _source_execution_summary(entries),
        "teacher_rows": teacher_rows,
    }
    validate_t090_canary_evidence(
        evidence,
        split_manifest=split_manifest,
        native_source_manifest=native_source_manifest,
    )
    return evidence


def build_t090_canary_evidence_from_records(
    *,
    split_manifest: Mapping[str, object],
    native_source_manifest: Mapping[str, object],
    start_offset: int,
    execution_records: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    """Route already-produced records into the bounded evidence validator.

    This is the file-command seam.  It does not instantiate an adapter or run
    a simulator; callers that perform native work use ``execute_t090_canary``.
    """

    selected = select_t090_canary_sources(split_manifest, start_offset=start_offset)
    by_source: dict[str, Mapping[str, object]] = {}
    for raw in execution_records:
        record = _mapping(raw, "canary execution record")
        identity = record.get("source_identity")
        if not isinstance(identity, str) or identity in by_source:
            raise T090CanaryError("T090 canary execution records duplicate a source")
        by_source[identity] = record
    expected_ids = {item.source_identity for item in selected}
    if set(by_source) != expected_ids:
        raise T090CanaryError(
            "T090 canary execution records differ from selected range"
        )
    return execute_t090_canary(
        split_manifest=split_manifest,
        native_source_manifest=native_source_manifest,
        start_offset=start_offset,
        runner=lambda source: by_source[source.source_identity],
    )


def validate_t090_canary_evidence(
    value: Mapping[str, object],
    *,
    split_manifest: Mapping[str, object],
    native_source_manifest: Mapping[str, object],
) -> None:
    """Validate mechanics/coverage-only evidence without promoting it."""

    if (
        value.get("schema_id") != T090_CANARY_EVIDENCE_SCHEMA_ID
        or value.get("schema_version") != 1
        or value.get("task_id") != T090_TASK_ID
        or value.get("classification") != T090_CANARY_CLASSIFICATION
        or value.get("formal_execution_authorized") is not False
        or value.get("training_eligible") is not False
        or value.get("split_manifest_sha256") != canonical_sha256(split_manifest)
    ):
        raise T090CanaryError("T090 canary evidence is not non-authoritative")
    expected_provenance = build_t090_target_provenance(
        split_manifest, native_source_manifest=native_source_manifest
    )
    if value.get("target_provenance") != expected_provenance:
        raise T090CanaryError("T090 canary target provenance is invalid")
    offset = value.get("selected_start_offset")
    if isinstance(offset, bool) or not isinstance(offset, int):
        raise T090CanaryError("T090 canary start offset is invalid")
    if value.get("selected_start_count") != T090_CANARY_START_COUNT:
        raise T090CanaryError("T090 canary start count is invalid")
    ledger = _mapping(value.get("source_execution_ledger"), "canary source ledger")
    selected = validate_t090_canary_source_execution_ledger(
        ledger, split_manifest=split_manifest, start_offset=offset
    )
    summary = _mapping(value.get("source_execution_summary"), "canary source summary")
    entries = [
        _mapping(item, "canary source execution entry")
        for item in _sequence(ledger.get("entries"), "canary source execution entries")
    ]
    if dict(summary) != _source_execution_summary(entries):
        raise T090CanaryError("T090 canary source execution summary is inconsistent")
    rows = _sequence(value.get("teacher_rows"), "canary teacher rows")
    by_source = {source.source_identity: source for source in selected}
    seen: set[tuple[str, str]] = set()
    for raw in rows:
        row = _mapping(raw, "canary teacher row")
        identity = row.get("source_identity")
        if not isinstance(identity, str) or identity not in by_source:
            raise T090CanaryError("T090 canary teacher row is outside selected sources")
        _validate_teacher_rows([row], source=by_source[identity])
        _, observed = materialize_t090_decision(row, split_entry=by_source[identity])
        key = (identity, observed.decision_identity)
        if key in seen:
            raise T090CanaryError("T090 canary teacher rows duplicate a decision")
        seen.add(key)


__all__ = [
    "T090_CANARY_CLASSIFICATION",
    "T090_CANARY_EVIDENCE_SCHEMA_ID",
    "T090_CANARY_SOURCE_EXECUTION_SCHEMA_ID",
    "T090_CANARY_START_COUNT",
    "T090CanaryError",
    "T090CanaryStartRunner",
    "build_t090_canary_evidence_from_records",
    "execute_t090_canary",
    "select_t090_canary_sources",
    "validate_t090_canary_evidence",
    "validate_t090_canary_source_execution_ledger",
]
