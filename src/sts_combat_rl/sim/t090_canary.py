"""Bounded, non-authoritative T090 canary workflow plumbing.

The default workflow stays injectable, and ``T090NativeCanaryRunner`` binds
the existing T085 restore/native adapter/controlled-run seams for an approved
real canary.  This module owns no simulator, restore path, or local Battle
transition.
"""

from __future__ import annotations

import math
import sys
import time
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from typing import Protocol

from sts_combat_rl.commands.t085_native_execution import (
    T085NativeTerminalSearchAdapter,
    T085UnguidedBattleSearchV2Controller,
    _validate_t085_native_source_manifest,
    restore_t085_canonical_record,
)
from sts_combat_rl.sim.action_space import ActionSpaceConfig
from sts_combat_rl.sim.battle_start_pool import BattleStartCheckpointRecord
from sts_combat_rl.sim.controlled_run import execute_controlled_run
from sts_combat_rl.sim.features import (
    TACTICAL_FEATURE_SCHEMA_ID,
    TACTICAL_FEATURE_SCHEMA_VERSION,
)
from sts_combat_rl.sim.public_run_context import (
    build_public_run_context,
    read_native_public_projection,
)
from sts_combat_rl.sim.t090_battle_student import (
    T090_NATIVE_IDENTITY,
    T090_TASK_ID,
    T090_TEACHER_CONFIG,
    T090SplitEntry,
    build_t090_target_provenance,
    canonical_sha256,
    materialize_t090_decision,
    validate_t090_split_manifest,
)
from sts_combat_rl.t085_corrected_leaf_value_search_evaluation import (
    T085BattleStartRecord,
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


def _native_search_provenance() -> dict[str, object]:
    return {
        "native_identity": dict(T090_NATIVE_IDENTITY),
        "native_api": "StepSimulator.battle_search_v2.v1",
        "simulations": T090_TEACHER_CONFIG["simulations"],
        "include_potions": False,
        "policy_prior_callback": None,
        "leaf_value_callback": None,
    }


def _teacher_rows_from_controlled_run(
    source: T090SplitEntry, controlled: object
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    """Extract current public/teacher records from shared executor steps."""

    steps = getattr(controlled, "steps", None)
    if not isinstance(steps, Sequence):
        raise T090CanaryError("T090 native canary did not return controlled steps")
    rows: list[dict[str, object]] = []
    decisions: list[dict[str, object]] = []
    for step in steps:
        if getattr(step, "battle_active", False) is not True:
            continue
        if getattr(step, "feature_schema_id", None) != TACTICAL_FEATURE_SCHEMA_ID:
            raise T090CanaryError("T090 native canary public feature schema drifted")
        metadata = getattr(step, "decision_metadata", None)
        report_rows = (
            metadata.get("oracle_search_decision_reports")
            if isinstance(metadata, Mapping)
            else None
        )
        reports = _sequence(report_rows, "native search decision reports")
        if len(reports) != 1:
            raise T090CanaryError(
                "T090 native canary lacks one search report per decision"
            )
        report = _mapping(reports[0], "native search decision report")
        if (
            report.get("native_api") != "StepSimulator.battle_search_v2.v1"
            or report.get("simulations_requested") != T090_TEACHER_CONFIG["simulations"]
            or report.get("include_potions") is not False
            or report.get("selection_rule") != "highest_mean"
        ):
            raise T090CanaryError("T090 native canary Search-v2@400 provenance drifted")
        root_stats = _sequence(report.get("root_actions"), "native root actions")
        root_by_index: dict[int, Mapping[str, object]] = {}
        for raw_root in root_stats:
            root = _mapping(raw_root, "native root action")
            index = root.get("legal_action_index")
            if (
                isinstance(index, bool)
                or not isinstance(index, int)
                or index in root_by_index
            ):
                raise T090CanaryError(
                    "T090 native canary root action indices are invalid"
                )
            root_by_index[index] = root
        identities = getattr(step, "legal_action_identities", None)
        action_features = getattr(step, "legal_action_features", None)
        action_kinds = getattr(step, "legal_action_kinds", None)
        state_features = getattr(step, "snapshot_features", None)
        if not (
            isinstance(identities, Sequence)
            and isinstance(action_features, Sequence)
            and isinstance(action_kinds, Sequence)
            and isinstance(state_features, Sequence)
        ):
            raise T090CanaryError(
                "T090 native canary controlled step lacks public input"
            )
        root_rows: list[dict[str, object]] = []
        for index, identity_raw in enumerate(identities):
            identity = _mapping(identity_raw, "public legal action identity")
            root = root_by_index.get(index)
            if root is None or root.get("action_identity") != dict(identity):
                raise T090CanaryError(
                    "T090 native canary root action map is incomplete"
                )
            root_rows.append(
                {
                    "legal_action_identity": dict(identity),
                    "visits": root.get("visits"),
                    "mean_value": root.get("mean_value"),
                }
            )
        step_index = getattr(step, "step_index", None)
        if isinstance(step_index, bool) or not isinstance(step_index, int):
            raise T090CanaryError("T090 native canary step index is invalid")
        decision_identity = f"{source.source_identity}:battle-decision:{step_index}"
        selected = _mapping(
            report.get("selected_action_identity"), "native selected action identity"
        )
        rows.append(
            {
                "source_identity": source.source_identity,
                "source_group": source.source_group,
                "decision_identity": decision_identity,
                "public_input": {
                    "schema_id": TACTICAL_FEATURE_SCHEMA_ID,
                    "schema_version": TACTICAL_FEATURE_SCHEMA_VERSION,
                    "state_features": list(state_features),
                    "legal_action_features": [list(item) for item in action_features],
                    "legal_action_identities": [
                        dict(_mapping(item, "action identity")) for item in identities
                    ],
                    "legal_action_kinds": list(action_kinds),
                },
                "root_rows": root_rows,
            }
        )
        decisions.append(
            {
                "decision_identity": decision_identity,
                "selected_action_identity": dict(selected),
                "selection_rule": "highest_mean",
                "native_search": _native_search_provenance(),
            }
        )
    return rows, decisions


class T090NativeCanaryRunner:
    """Production runner using T085 restore and shared native execution only.

    ``adapter_factory`` supplies the repository's current ``LightSpeedAdapter``
    in production; tests may inject a narrow fake.  No adapter method is
    reimplemented here.
    """

    def __init__(
        self,
        *,
        adapter_factory: Callable[[], object],
        source_records: Mapping[str, T085BattleStartRecord],
        canonical_records: Mapping[str, BattleStartCheckpointRecord],
        worker: Mapping[str, object],
    ) -> None:
        if not callable(adapter_factory):
            raise T090CanaryError("T090 native canary adapter factory is unavailable")
        _validate_worker(worker)
        self._adapter_factory = adapter_factory
        self._source_records = dict(source_records)
        self._canonical_records = dict(canonical_records)
        self._worker = dict(worker)

    def __call__(self, source: T090SplitEntry) -> Mapping[str, object]:
        base_adapter = self._adapter_factory()
        try:
            return self._run_source(source, base_adapter)
        finally:
            close = getattr(base_adapter, "close", None)
            if callable(close):
                try:
                    close()
                except BaseException:
                    # Do not replace the restore/Search/controlled-run failure
                    # that caused this cleanup.  On a successful run, however,
                    # a failed close remains a fail-closed runner failure.
                    if sys.exc_info()[0] is None:
                        raise

    def _run_source(
        self, source: T090SplitEntry, base_adapter: object
    ) -> Mapping[str, object]:
        selected = self._source_records.get(source.source_identity)
        canonical = self._canonical_records.get(source.source_identity)
        if selected is None or canonical is None:
            raise T090CanaryError(
                "T090 native canary source restore binding is missing"
            )
        native_identity = _validate_t085_native_source_manifest(
            "battle_search_v2", expected_native_identity=T090_NATIVE_IDENTITY
        )
        restored, restore_method = restore_t085_canonical_record(
            base_adapter,
            selected,
            {selected.selection_identity: canonical},
        )
        legal_actions = getattr(base_adapter, "legal_actions", None)
        if not callable(legal_actions):
            raise T090CanaryError("T090 native canary adapter lacks legal_actions")
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
        if (
            not isinstance(expected_context, Mapping)
            or actual_context != expected_context
        ):
            raise T090CanaryError(
                "T090 native canary restore public/legal parity failed"
            )
        adapter = T085NativeTerminalSearchAdapter(
            base_adapter,
            search_simulations=T090_TEACHER_CONFIG["simulations"],
            search_backend="battle_search_v2",
            policy_prior_callback=None,
            leaf_value_callback=None,
            expected_native_identity=T090_NATIVE_IDENTITY,
        )
        adapter.prime_restored_snapshot(restored)
        controller = T085UnguidedBattleSearchV2Controller(
            simulations=T090_TEACHER_CONFIG["simulations"],
            action_space=ActionSpaceConfig.initial_no_potions(),
            expected_native_identity=T090_NATIVE_IDENTITY,
        )
        started = time.perf_counter()
        controlled = execute_controlled_run(
            adapter,
            controller,
            seed=None,
            max_steps=200,
            action_space=ActionSpaceConfig.initial_no_potions(),
        )
        wall_clock = time.perf_counter() - started
        rows, decisions = _teacher_rows_from_controlled_run(source, controlled)
        labels = adapter.native_terminal_labels
        final_step = controlled.steps[-1] if controlled.steps else None
        outcome = (
            final_step.next_battle_outcome
            if final_step is not None
            else controlled.final_raw.get("completed_battle_outcome")
        )
        if (
            not controlled.terminal
            or controlled.problems
            or not isinstance(outcome, str)
            or not outcome
            or len(labels) != 1
            or labels[0].terminal_outcome != outcome
        ):
            raise T090CanaryError("T090 native canary did not prove a battle terminal")
        return {
            "source_identity": source.source_identity,
            "source_group": source.source_group,
            "split": source.split,
            "canonical_position": source.canonical_position,
            "native_identity": native_identity,
            "teacher_config": T090_TEACHER_CONFIG,
            "restore_public_legal_parity": True,
            "completed": True,
            "terminal_reached": True,
            "terminal_evidence": {
                "outcome": outcome,
                "restore_method": restore_method,
                "terminal_current_hp": (
                    final_step.next_player_hp if final_step is not None else None
                ),
                "native_terminal_label_proven": True,
            },
            "worker": dict(self._worker),
            "cost": {
                "wall_clock_time_s": wall_clock,
                "root_decision_count": len(rows),
                "search_simulation_count": len(rows)
                * T090_TEACHER_CONFIG["simulations"],
            },
            "teacher_rows": rows,
            "decision_provenance": decisions,
        }


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
    if result["root_decision_count"] == 0:
        raise T090CanaryError("T090 completed canary start requires a root decision")
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


def _validate_decision_provenance(
    value: object, *, teacher_rows: Sequence[Mapping[str, object]]
) -> list[dict[str, object]]:
    records = _sequence(value, "canary decision provenance")
    if len(records) != len(teacher_rows):
        raise T090CanaryError(
            "T090 canary decision provenance does not cover captured teacher rows"
        )
    retained: list[dict[str, object]] = []
    for teacher, raw in zip(teacher_rows, records, strict=True):
        record = _mapping(raw, "canary decision provenance record")
        required = {
            "decision_identity",
            "selected_action_identity",
            "selection_rule",
            "native_search",
        }
        if set(record) != required or record.get("decision_identity") != teacher.get(
            "decision_identity"
        ):
            raise T090CanaryError("T090 canary decision provenance is unbound")
        if record.get("selection_rule") != "highest_mean":
            raise T090CanaryError("T090 canary did not select highest_mean")
        if (
            _mapping(record.get("native_search"), "native search provenance")
            != _native_search_provenance()
        ):
            raise T090CanaryError("T090 canary native Search-v2 provenance drifted")
        selected = _mapping(
            record.get("selected_action_identity"), "selected action identity"
        )
        root_rows = _sequence(teacher.get("root_rows"), "canary root rows")
        public_input = _mapping(teacher.get("public_input"), "canary public input")
        legal_identities = _sequence(
            public_input.get("legal_action_identities"),
            "public legal action identities",
        )
        roots_by_identity: dict[str, Mapping[str, object]] = {}
        for root_raw in root_rows:
            root = _mapping(root_raw, "canary root row")
            identity = _mapping(root.get("legal_action_identity"), "root identity")
            identity_key = canonical_sha256(identity)
            if identity_key in roots_by_identity:
                raise T090CanaryError(
                    "T090 canary root action identities are duplicated"
                )
            roots_by_identity[identity_key] = root
        ranked: list[tuple[float, int, int, Mapping[str, object]]] = []
        for legal_index, identity_raw in enumerate(legal_identities):
            identity = _mapping(identity_raw, "public legal action identity")
            root = roots_by_identity.get(canonical_sha256(identity))
            if root is None:
                raise T090CanaryError("T090 canary root action map is incomplete")
            visits = root.get("visits")
            mean = root.get("mean_value")
            if (
                isinstance(visits, int)
                and not isinstance(visits, bool)
                and visits > 0
                and isinstance(mean, (int, float))
                and not isinstance(mean, bool)
                and math.isfinite(float(mean))
            ):
                ranked.append(
                    (
                        float(mean),
                        visits,
                        legal_index,
                        identity,
                    )
                )
        if not ranked:
            raise T090CanaryError("T090 canary cannot prove highest_mean selection")
        _, _, _, expected_selected = max(
            ranked, key=lambda item: (item[0], item[1], -item[2])
        )
        if selected != expected_selected:
            raise T090CanaryError("T090 canary selected action is not highest_mean")
        retained.append(dict(record))
    return retained


def _validate_runner_record(
    value: Mapping[str, object], *, source: T090SplitEntry
) -> tuple[dict[str, object], list[dict[str, object]], list[dict[str, object]]]:
    required = {
        "source_identity",
        "source_group",
        "split",
        "canonical_position",
        "native_identity",
        "teacher_config",
        "restore_public_legal_parity",
        "completed",
        "terminal_reached",
        "terminal_evidence",
        "worker",
        "cost",
        "teacher_rows",
        "decision_provenance",
    }
    if set(value) != required:
        raise T090CanaryError("T090 canary runner record has an unexpected shape")
    if (
        value.get("source_identity") != source.source_identity
        or value.get("source_group") != source.source_group
        or value.get("split") != source.split
        or value.get("canonical_position") != source.canonical_position
        or value.get("native_identity") != T090_NATIVE_IDENTITY
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
    decision_provenance = _validate_decision_provenance(
        value.get("decision_provenance"), teacher_rows=teacher_rows
    )
    cost = _validate_cost(value.get("cost"))
    if cost["root_decision_count"] != len(teacher_rows):
        raise T090CanaryError(
            "T090 canary root decision count does not match captured teacher rows"
        )
    entry = {
        "source_identity": source.source_identity,
        "source_group": source.source_group,
        "split": source.split,
        "canonical_position": source.canonical_position,
        "native_identity": dict(T090_NATIVE_IDENTITY),
        "restore_public_legal_parity": True,
        "completed": True,
        "terminal_reached": True,
        "status": "COMPLETED_VALID",
        "terminal_evidence": dict(terminal),
        "worker": _validate_worker(value.get("worker")),
        "cost": cost,
    }
    return entry, teacher_rows, decision_provenance


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
            "native_identity",
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
            or entry.get("native_identity") != T090_NATIVE_IDENTITY
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
    decision_provenance: list[dict[str, object]] = []
    for source in selected:
        raw = runner(source)
        if not isinstance(raw, Mapping):
            raise T090CanaryError("T090 canary runner did not return a mapping")
        entry, rows, decisions = _validate_runner_record(raw, source=source)
        entries.append(entry)
        teacher_rows.extend(rows)
        decision_provenance.extend(decisions)
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
        "decision_provenance": decision_provenance,
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
    validated_rows: list[dict[str, object]] = []
    for raw in rows:
        row = _mapping(raw, "canary teacher row")
        identity = row.get("source_identity")
        if not isinstance(identity, str) or identity not in by_source:
            raise T090CanaryError("T090 canary teacher row is outside selected sources")
        validated_rows.extend(_validate_teacher_rows([row], source=by_source[identity]))
        _, observed = materialize_t090_decision(row, split_entry=by_source[identity])
        key = (identity, observed.decision_identity)
        if key in seen:
            raise T090CanaryError("T090 canary teacher rows duplicate a decision")
        seen.add(key)
    _validate_decision_provenance(
        value.get("decision_provenance"), teacher_rows=validated_rows
    )
    rows_by_source = Counter(str(row["source_identity"]) for row in validated_rows)
    for entry in entries:
        source_identity = str(entry["source_identity"])
        if (
            rows_by_source[source_identity]
            != _mapping(entry["cost"], "canary cost")["root_decision_count"]
        ):
            raise T090CanaryError(
                "T090 canary root decision count does not match captured teacher rows"
            )


__all__ = [
    "T090_CANARY_CLASSIFICATION",
    "T090_CANARY_EVIDENCE_SCHEMA_ID",
    "T090_CANARY_SOURCE_EXECUTION_SCHEMA_ID",
    "T090_CANARY_START_COUNT",
    "T090CanaryError",
    "T090CanaryStartRunner",
    "T090NativeCanaryRunner",
    "build_t090_canary_evidence_from_records",
    "execute_t090_canary",
    "select_t090_canary_sources",
    "validate_t090_canary_evidence",
    "validate_t090_canary_source_execution_ledger",
]
