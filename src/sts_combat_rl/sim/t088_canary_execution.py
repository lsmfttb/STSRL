"""Explicitly-authorized, bounded execution seam for the T088 canary.

This module is deliberately *not* a general tournament runner.  It accepts a
single Maintainer authorization record that binds an exact implementation head,
the deterministic five-role canary selection, the accepted T087 cohort, and
the four frozen controller definitions.  Without that record it performs no
restore, controller construction, simulator call, or artifact write.

The actual simulator-facing record runner is injected.  That keeps source
restore and mechanics at the existing authoritative boundaries while this
module owns T088's authorization, all-arm coverage, evidence normalization,
and fail-closed artifact commit.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Protocol

from sts_combat_rl.commands.t085_native_execution import (
    T085NativeExecutionError,
    _validate_t085_native_source_manifest,
    restore_t085_canonical_record,
)
from sts_combat_rl.commands.t088_classical_combat_tournament import (
    T088_ARM_ORDER,
    T088_NATIVE_IDENTITY,
    T088_WORK_COUNTERS_SCHEMA_ID,
    build_t088_controller,
    t088_controller_definitions,
)
from sts_combat_rl.sim.action_space import ActionSpaceConfig
from sts_combat_rl.sim.battle_start_pool import BattleStartCheckpointRecord
from sts_combat_rl.sim.controlled_run import ControlledRun, execute_controlled_run
from sts_combat_rl.sim.decision_record import action_identity_dicts_for_actions
from sts_combat_rl.sim.public_run_context import (
    build_public_run_context,
    read_native_public_projection,
)
from sts_combat_rl.sim.t087_dense_combat_diagnostics import (
    T087IncompleteError,
    _terminal_outcome_from_raw,
    _trace_for_controlled_run,
    battle_snapshot_evidence,
    build_dense_diagnostic_row,
)
from sts_combat_rl.sim.t088_tournament_workflow import (
    T088_ARMS,
    T088_TASK_ID,
    T088IncompleteError,
    _binding_identity,
    _finite,
    select_t088_canary_records,
    validate_t088_canary_evidence,
    validate_t088_t087_cohort_binding,
)
from sts_combat_rl.t085_corrected_leaf_value_search_evaluation import (
    T085BattleStartRecord,
)

T088_CANARY_AUTHORIZATION_SCHEMA_ID = "t088-maintainer-canary-authorization-v1"
T088_CANARY_EVIDENCE_SCHEMA_ID = "t088-canary-evidence-v1"


class T088CanaryExecutionError(T088IncompleteError):
    """The canary is unapproved, incomplete, or unsuitable for retention."""


def _safe_runner_exception_detail(exc: Exception) -> str:
    """Retain actionable repository-bound failures without serializing state.

    Native/runtime exceptions may embed arbitrary simulator representations, so
    their messages are not surfaced.  Repository boundary errors have
    deliberately controlled messages and can be retained in the detached-job
    status without exposing copied simulator state.
    """

    if isinstance(
        exc,
        (T085NativeExecutionError, T087IncompleteError, T088CanaryExecutionError),
    ):
        message = " ".join(str(exc).split())
        if message:
            return f"{type(exc).__name__}: {message[:512]}"
    return type(exc).__name__


class T088CanaryRecordRunner(Protocol):
    """Restore, parity-check, and execute exactly one already-bound record."""

    def __call__(
        self, record: Mapping[str, object], arm: str, controller: object
    ) -> Mapping[str, object]: ...


class _T088CanaryRuntimeAdapter:
    """Additive work-capture proxy over an accepted restored native adapter.

    This intentionally owns no game transition, restore, or action-selection
    semantics.  The two native companion calls are the reviewed T088 additive
    telemetry surfaces; all other methods, including checkpoint operations used
    by Beam, remain the exact wrapped adapter methods.
    """

    def __init__(self, base_adapter: object, restored_snapshot: object) -> None:
        self._base_adapter = base_adapter
        self._restored_snapshot = restored_snapshot
        self._runtime_work_rows: list[dict[str, object]] = []
        self._progressive_bias_rows: list[dict[str, object]] = []

    def __getattr__(self, name: str) -> object:
        return getattr(self._base_adapter, name)

    def reset(self, seed: int | None = None) -> object:
        if seed is not None:
            raise T088CanaryExecutionError("T088 canary must not reseed a restore")
        snapshot = self._restored_snapshot
        self._restored_snapshot = None
        if snapshot is None:
            raise T088CanaryExecutionError("T088 canary restored snapshot was reused")
        return snapshot

    def battle_search_v2(
        self,
        snapshot: object,
        *,
        simulations: int,
        include_potions: bool = False,
        policy_prior_callback: object | None = None,
        leaf_value_callback: object | None = None,
    ) -> Mapping[str, object]:
        """Run A/B through the native additive-counter companion only."""

        if (
            include_potions
            or policy_prior_callback is not None
            or leaf_value_callback is not None
        ):
            raise T088CanaryExecutionError("T088 A/B Search-v2 contract drifted")
        search = getattr(
            self._base_adapter, "battle_search_v2_with_work_counters", None
        )
        if not callable(search):
            raise T088CanaryExecutionError(
                "T088 native Search-v2 work counters are unavailable"
            )
        raw = search(snapshot, simulations=simulations, include_potions=False)
        if not isinstance(raw, Mapping):
            raise T088CanaryExecutionError(
                "T088 native Search-v2 counter report is malformed"
            )
        work = raw.get("work_counters")
        if not isinstance(work, Mapping):
            raise T088CanaryExecutionError(
                "T088 native Search-v2 work counters are missing"
            )
        self._runtime_work_rows.append(dict(work))
        return raw

    def battle_search_v2_with_progressive_bias(
        self,
        snapshot: object,
        *,
        simulations: int,
        include_potions: bool = False,
        bias_enabled: bool = True,
        audit_limit: int = 256,
    ) -> Mapping[str, object]:
        search = getattr(
            self._base_adapter, "battle_search_v2_with_progressive_bias", None
        )
        if not callable(search):
            raise T088CanaryExecutionError(
                "T088 native progressive-bias API is unavailable"
            )
        raw = search(
            snapshot,
            simulations=simulations,
            include_potions=include_potions,
            bias_enabled=bias_enabled,
            audit_limit=audit_limit,
        )
        if not isinstance(raw, Mapping):
            raise T088CanaryExecutionError(
                "T088 native progressive-bias report is malformed"
            )
        self._progressive_bias_rows.append(dict(raw))
        return raw


def _positive_int(value: object, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise T088CanaryExecutionError(f"{label} must be a non-negative integer")
    return value


def _metadata_work_rows(
    controlled: ControlledRun,
    *,
    arm: str,
    adapter: _T088CanaryRuntimeAdapter,
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    """Extract exact per-root counters published by each frozen controller."""

    if arm in {"A", "B"}:
        if len(adapter._runtime_work_rows) != len(controlled.steps):
            raise T088CanaryExecutionError(
                "T088 A/B Search-v2 work rows do not match decisions"
            )
        return list(adapter._runtime_work_rows), []
    if arm == "C":
        rows: list[dict[str, object]] = []
        for step in controlled.steps:
            metadata = step.decision_metadata.get("classical_search")
            if not isinstance(metadata, Mapping):
                raise T088CanaryExecutionError("T088 Beam work metadata is unavailable")
            rows.append(dict(metadata))
        return rows, []
    if arm == "D":
        if len(adapter._progressive_bias_rows) != len(controlled.steps):
            raise T088CanaryExecutionError(
                "T088 progressive-bias rows do not match decisions"
            )
        rows = []
        audits = []
        for raw in adapter._progressive_bias_rows:
            work = raw.get("work_counters")
            telemetry = raw.get("progressive_bias_telemetry")
            if not isinstance(work, Mapping) or not isinstance(telemetry, Mapping):
                raise T088CanaryExecutionError(
                    "T088 progressive-bias telemetry is unavailable"
                )
            rows.append(dict(work))
            audits.append(dict(telemetry))
        return rows, audits
    raise T088CanaryExecutionError(f"unknown T088 arm {arm!r}")


def _aggregate_work(
    rows: Sequence[Mapping[str, object]], *, arm: str, controlled_steps: int
) -> dict[str, object]:
    """Retain per-root exact counters and an all-decision total without aliases."""

    fields = (
        "successor_transition_count",
        "action_execution_count",
        "tree_node_expansion_count",
        "rollout_count",
        "terminal_utility_evaluation_count",
        "model_calls",
    )
    totals = {name: 0 for name in fields}
    retained: list[dict[str, object]] = []
    for index, raw in enumerate(rows):
        if (
            arm in {"A", "B", "D"}
            and raw.get("schema_id") != T088_WORK_COUNTERS_SCHEMA_ID
        ):
            raise T088CanaryExecutionError("T088 native work-counter schema drifted")
        row = {
            name: _positive_int(raw.get(name), f"root[{index}].{name}")
            for name in fields
        }
        if row["model_calls"] != 0:
            raise T088CanaryExecutionError("T088 canary consumed learned model calls")
        retained.append({"root_decision_index": index, **row, "raw": dict(raw)})
        for name, value in row.items():
            if name in totals:
                totals[name] += value
    return {
        **totals,
        "root_decision_count": controlled_steps,
        # The native v2 and Beam surfaces do not expose one cross-algorithm
        # simulator-step definition.  Their directly counted transition work is
        # retained above, rather than inventing a comparable number.
        "native_simulator_step_count": None,
        "native_simulator_step_count_unavailable_reason": (
            "no cross-algorithm native simulator-step counter is exposed"
        ),
        "per_root_decision": retained,
    }


def _validate_runtime_controller(controller: object, arm: str) -> None:
    """Bind the runtime object to the frozen arm definition, not its label."""

    provenance = _controller_provenance(controller)
    config = provenance.get("config")
    if not isinstance(config, Mapping):
        raise T088CanaryExecutionError("T088 controller configuration is unavailable")
    action_space = ActionSpaceConfig.initial_no_potions().to_dict()
    if config.get("action_space") != action_space:
        raise T088CanaryExecutionError("T088 controller action space drifted")
    if arm in {"A", "B"}:
        budget = 100 if arm == "A" else 400
        if (
            provenance.get("name") != f"t085_unguided_search_v2_s{budget}"
            or config.get("search_budget") != budget
            or config.get("root_selection_rule") != "highest_mean"
            or config.get("policy_prior_callback") is not None
            or config.get("leaf_value_callback") is not None
            or config.get("native_identity") != T088_NATIVE_IDENTITY
        ):
            raise T088CanaryExecutionError("T088 A/B Search-v2 controller drifted")
        return
    if arm == "C":
        if (
            provenance.get("name") != "beam_h1_w32_b400_v1"
            or config.get("task_id") != T088_TASK_ID
            or config.get("beam_width") != 32
            or config.get("successor_transition_budget") != 400
            or config.get("policy_prior") is not None
            or config.get("learned_leaf_value") is not None
        ):
            raise T088CanaryExecutionError("T088 Beam controller drifted")
        return
    if arm == "D":
        if (
            provenance.get("name") != "progressive_bias_mcts_h1_400_v1"
            or config.get("task_id") != T088_TASK_ID
            or config.get("simulations") != 400
            or config.get("progressive_bias_weight") != 0.50
            or config.get("policy_prior_callback") is not None
            or config.get("leaf_value_callback") is not None
            or config.get("native_identity") != T088_NATIVE_IDENTITY
        ):
            raise T088CanaryExecutionError("T088 progressive-bias controller drifted")
        return
    raise T088CanaryExecutionError(f"unknown T088 arm {arm!r}")


class T088NativeCanaryRecordRunner:
    """The real one-record T088 canary adapter, with no artifact side effects.

    ``selected_records`` and ``canonical_records_by_cohort`` must be loaded by
    the caller through the retained T087/T085 input gate.  This object accepts
    only those resolved records; it never loads a best-effort cohort or creates
    a replacement restore path.
    """

    def __init__(
        self,
        *,
        adapter_factory: Callable[[], object],
        selected_records: Mapping[str, T085BattleStartRecord],
        canonical_records_by_cohort: Mapping[
            str, Mapping[str, BattleStartCheckpointRecord]
        ],
        worker_count: int = 1,
    ) -> None:
        if not callable(adapter_factory) or not selected_records:
            raise T088CanaryExecutionError(
                "T088 native canary runner inputs are unavailable"
            )
        if (
            isinstance(worker_count, bool)
            or not isinstance(worker_count, int)
            or worker_count <= 0
        ):
            raise T088CanaryExecutionError("T088 canary worker_count must be positive")
        self._adapter_factory = adapter_factory
        self._selected_records = dict(selected_records)
        self._canonical_records_by_cohort = {
            str(cohort): dict(records)
            for cohort, records in canonical_records_by_cohort.items()
        }
        self._worker_count = worker_count

    def __call__(
        self, record: Mapping[str, object], arm: str, controller: object
    ) -> Mapping[str, object]:
        identity = record.get("selection_identity")
        cohort = record.get("cohort")
        if not isinstance(identity, str) or not isinstance(cohort, str):
            raise T088CanaryExecutionError("T088 canary record identity is malformed")
        selected = self._selected_records.get(identity)
        canonical_records = self._canonical_records_by_cohort.get(cohort)
        if (
            selected is None
            or canonical_records is None
            or selected.selection_identity != identity
        ):
            raise T088CanaryExecutionError(
                "T088 canary record is not an accepted T085 restore"
            )
        canonical = canonical_records.get(identity)
        if canonical is None:
            raise T088CanaryExecutionError(
                "T088 canary canonical restore record is unavailable"
            )
        if arm not in T088_ARM_ORDER:
            raise T088CanaryExecutionError("T088 canary arm is invalid")
        _validate_runtime_controller(controller, arm)
        try:
            native_identity = _validate_t085_native_source_manifest(
                "battle_search_v2", expected_native_identity=T088_NATIVE_IDENTITY
            )
            base_adapter = self._adapter_factory()
            restored, restore_method = restore_t085_canonical_record(
                base_adapter, selected, canonical_records
            )
            root_actions = list(base_adapter.legal_actions(restored))
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
                raise T088CanaryExecutionError(
                    "T088 restore public/legal parity failed"
                )
            entry = battle_snapshot_evidence(restored.raw)
            adapter = _T088CanaryRuntimeAdapter(base_adapter, restored)
            started = time.perf_counter()
            controlled = execute_controlled_run(
                adapter,
                controller,  # type: ignore[arg-type]
                seed=None,
                max_steps=200,
                action_space=ActionSpaceConfig.initial_no_potions(),
            )
            wall_clock_time_s = time.perf_counter() - started
        except (T085NativeExecutionError, RuntimeError, TypeError, ValueError) as exc:
            raise T088CanaryExecutionError(
                f"{identity}: T088 native canary execution failed: "
                f"{_safe_runner_exception_detail(exc)}"
            ) from exc
        if not controlled.terminal or controlled.problems:
            raise T088CanaryExecutionError(
                f"{identity}: controlled Battle did not terminate: "
                + "; ".join(controlled.problems)
            )
        terminal_raw = (
            controlled.steps[-1].next_snapshot_raw
            if controlled.steps
            else controlled.final_raw
        )
        terminal = battle_snapshot_evidence(
            terminal_raw, require_positive_enemy_hp=False
        )
        outcome = _terminal_outcome_from_raw(terminal["raw_snapshot"])
        work_rows, progressive_bias = _metadata_work_rows(
            controlled, arm=arm, adapter=adapter
        )
        work = _aggregate_work(
            work_rows, arm=arm, controlled_steps=len(controlled.steps)
        )
        trace = _trace_for_controlled_run(controlled)
        diagnostic = build_dense_diagnostic_row(
            selection_identity=identity,
            cohort=cohort,
            entry=entry,
            terminal=terminal,
            outcome=outcome,
            action_trace=trace,
            provenance={
                "task_id": T088_TASK_ID,
                "restore_method": restore_method,
                "native_commit": native_identity["commit"],
                "search_api": "T088 controller-specific native/search adapter",
                "action_space": ActionSpaceConfig.initial_no_potions().to_dict(),
                "seed": None,
                "max_steps": 200,
                "no_additional_search_seed": True,
                "restore_source_identity": identity,
            },
            source_selection_manifest_identity=record[
                "source_selection_manifest_identity"
            ],  # type: ignore[arg-type]
        )
        beam_rows = [
            step.decision_metadata.get("classical_search")
            for step in controlled.steps
            if isinstance(step.decision_metadata.get("classical_search"), Mapping)
        ]
        return {
            "arm": arm,
            "selection_identity": identity,
            "cohort": cohort,
            "native_identity": native_identity,
            "controller_provenance": _controller_provenance(controller),
            "restore_public_legal_parity": True,
            "restore_provenance": {
                "restore_method": restore_method,
                "selection_identity": identity,
                "root_legal_action_identities": action_identity_dicts_for_actions(
                    root_actions
                ),
            },
            "outcome": outcome,
            "controller_definition_verified": True,
            "dense_diagnostic_recomputed": True,
            "native_game_mechanics_parity": True,
            "search_v2_parity_verified": arm in {"A", "B"},
            "beam_deterministic_replay_verified": (
                arm == "C"
                and len(beam_rows) == len(controlled.steps)
                and all(
                    isinstance(row, Mapping) and row.get("selected_action_indices")
                    for row in beam_rows
                )
            ),
            "progressive_bias_depth_gt_zero_verified": (
                arm == "D"
                and any(
                    isinstance(row, Mapping)
                    and any(
                        isinstance(audit, Mapping) and audit.get("parent_depth", 0) > 0
                        for audit in row.get("audit_rows", [])
                        if isinstance(row.get("audit_rows"), Sequence)
                    )
                    for row in progressive_bias
                )
            ),
            "wall_clock_time_s": wall_clock_time_s,
            "worker": {"stage_worker_count": self._worker_count, "pid": os.getpid()},
            "work_counters": work,
            "controlled_action_trace": trace,
            "dense_diagnostic": diagnostic,
        }


def _canonical_sha256(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()


def _is_sha(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 40
        and all(character in "0123456789abcdef" for character in value)
    )


def _controller_provenance(controller: object) -> Mapping[str, object]:
    provenance = getattr(controller, "provenance", None)
    to_dict = getattr(provenance, "to_dict", None)
    value = to_dict() if callable(to_dict) else provenance
    if not isinstance(value, Mapping):
        raise T088CanaryExecutionError("T088 controller provenance is unavailable")
    return dict(value)


def _selected_records(
    selection: Mapping[str, object], cohort: Sequence[Mapping[str, object]]
) -> list[dict[str, object]]:
    selected = selection.get("selected")
    if not isinstance(selected, Sequence) or isinstance(selected, (str, bytes)):
        raise T088CanaryExecutionError("T088 canary selection is malformed")
    by_identity = {str(record["selection_identity"]): dict(record) for record in cohort}
    result: list[dict[str, object]] = []
    seen: set[str] = set()
    for item in selected:
        if not isinstance(item, Mapping):
            raise T088CanaryExecutionError(
                "T088 canary selection contains a malformed role"
            )
        identity = item.get("selection_identity")
        if not isinstance(identity, str) or identity not in by_identity:
            raise T088CanaryExecutionError(
                "T088 canary selection is outside the bound cohort"
            )
        if identity not in seen:
            seen.add(identity)
            result.append(by_identity[identity])
    if not result or len(result) * len(T088_ARMS) > 20:
        raise T088CanaryExecutionError("T088 canary execution is not bounded")
    return result


def validate_t088_canary_authorization(
    authorization: Mapping[str, object] | None,
    *,
    implementation_head: str,
    selection: Mapping[str, object],
    cohort_binding: Mapping[str, object],
    controller_definitions: Mapping[str, object],
) -> None:
    """Verify the explicit, exact-head Maintainer permission before execution.

    A specification approval, a true-ish flag, or an authorization copied from
    another selection/head is intentionally insufficient.
    """

    if not _is_sha(implementation_head):
        raise T088CanaryExecutionError("T088 implementation head must be a full SHA-1")
    if not isinstance(authorization, Mapping):
        raise T088CanaryExecutionError(
            "explicit T088 Maintainer canary authorization is required"
        )
    required = {
        "schema_id",
        "task_id",
        "authorization_kind",
        "authorized",
        "authorization_id",
        "implementation_head",
        "canary_selection_sha256",
        "t087_cohort_binding",
        "controller_definitions_sha256",
        "maintainer_attestation",
    }
    if set(authorization) != required:
        raise T088CanaryExecutionError(
            "T088 canary authorization has an unexpected shape"
        )
    attestation = authorization.get("maintainer_attestation")
    if (
        authorization.get("schema_id") != T088_CANARY_AUTHORIZATION_SCHEMA_ID
        or authorization.get("task_id") != T088_TASK_ID
        or authorization.get("authorization_kind") != "bounded_canary"
        or authorization.get("authorized") is not True
        or not isinstance(authorization.get("authorization_id"), str)
        or not authorization["authorization_id"]
        or authorization.get("implementation_head") != implementation_head
        or authorization.get("canary_selection_sha256") != _canonical_sha256(selection)
        or authorization.get("t087_cohort_binding") != _binding_identity(cohort_binding)
        or authorization.get("controller_definitions_sha256")
        != _canonical_sha256(controller_definitions)
        or not isinstance(attestation, Mapping)
        or dict(attestation)
        != {
            "role": "maintainer",
            "decision": "CANARY_AUTHORIZED",
            "exact_head": implementation_head,
        }
    ):
        raise T088CanaryExecutionError(
            "T088 canary authorization is not an exact approved binding"
        )


def _validate_amended_dense_diagnostic(
    row: Mapping[str, object],
    *,
    identity: str,
    cohort: str,
    source_identity: Mapping[str, object],
) -> None:
    """Recompute T087's amended vector without its arm-A-only provenance."""

    diagnostic = row.get("dense_diagnostic")
    if not isinstance(diagnostic, Mapping):
        raise T088CanaryExecutionError(
            "canary row lacks an amended dense diagnostic row"
        )
    if (
        diagnostic.get("selection_identity") != identity
        or diagnostic.get("cohort") != cohort
        or diagnostic.get("outcome") != row.get("outcome")
        or diagnostic.get("source_selection_manifest_identity") != source_identity
        or not isinstance(diagnostic.get("entry"), Mapping)
        or not isinstance(diagnostic.get("terminal"), Mapping)
        or not isinstance(diagnostic.get("action_trace"), Sequence)
        or isinstance(diagnostic.get("action_trace"), (str, bytes))
    ):
        raise T088CanaryExecutionError("canary dense diagnostic binding is malformed")
    try:
        rebuilt = build_dense_diagnostic_row(
            selection_identity=identity,
            cohort=cohort,
            entry=diagnostic["entry"],  # type: ignore[arg-type]
            terminal=diagnostic["terminal"],  # type: ignore[arg-type]
            outcome=str(row["outcome"]),
            action_trace=diagnostic["action_trace"],  # type: ignore[arg-type]
            provenance=(
                diagnostic["provenance"]
                if isinstance(diagnostic.get("provenance"), Mapping)
                else None
            ),
            source_selection_manifest_identity=source_identity,
        )
    except (KeyError, T087IncompleteError, TypeError, ValueError) as exc:
        raise T088CanaryExecutionError(
            "canary dense diagnostic does not recompute"
        ) from exc
    if dict(diagnostic) != rebuilt:
        raise T088CanaryExecutionError(
            "canary dense diagnostic has scalar or raw-evidence drift"
        )


def _validate_execution_row(
    row: Mapping[str, object],
    *,
    record: Mapping[str, object],
    arm: str,
    controller: object,
    cohort_binding: Mapping[str, object],
) -> dict[str, object]:
    """Reject a runner result unless all T088 runtime facts remain bound."""

    identity = record["selection_identity"]
    cohort = record["cohort"]
    if not isinstance(identity, str) or not isinstance(cohort, str):
        raise T088CanaryExecutionError("bound canary record lacks identity/cohort")
    result = dict(row)
    if (
        result.get("arm") != arm
        or result.get("selection_identity") != identity
        or result.get("cohort") != cohort
        or result.get("native_identity") != T088_NATIVE_IDENTITY
        or result.get("controller_provenance") != _controller_provenance(controller)
    ):
        raise T088CanaryExecutionError(
            "canary runner result is substituted or lacks provenance"
        )
    if result.get("formal_execution_authorized") not in (None, False):
        raise T088CanaryExecutionError("canary row must not authorize formal execution")
    source_identity = cohort_binding.get("source_selection_manifest_identity")
    if not isinstance(source_identity, Mapping):
        raise T088CanaryExecutionError("T088 bound source identity is unavailable")
    _validate_amended_dense_diagnostic(
        result,
        identity=identity,
        cohort=cohort,
        source_identity=source_identity,
    )
    counters = result.get("work_counters")
    if not isinstance(counters, Mapping):
        raise T088CanaryExecutionError("canary row work counters are missing")
    for name in (
        "successor_transition_count",
        "action_execution_count",
        "model_calls",
        "root_decision_count",
        "tree_node_expansion_count",
        "rollout_count",
        "terminal_utility_evaluation_count",
    ):
        value = counters.get(name)
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise T088CanaryExecutionError(f"canary work counter {name} is invalid")
    if counters["model_calls"] != 0:
        raise T088CanaryExecutionError("T088 canary consumed learned model calls")
    native_steps = counters.get("native_simulator_step_count")
    if native_steps is None:
        reason = counters.get("native_simulator_step_count_unavailable_reason")
        if not isinstance(reason, str) or not reason:
            raise T088CanaryExecutionError(
                "canary native simulator steps are unavailable without a reason"
            )
    elif (
        isinstance(native_steps, bool)
        or not isinstance(native_steps, int)
        or native_steps < 0
    ):
        raise T088CanaryExecutionError(
            "canary native simulator step counter is invalid"
        )
    _finite(result.get("wall_clock_time_s"), "wall_clock_time_s")
    return result


def execute_t088_canary(
    *,
    authorization: Mapping[str, object] | None,
    implementation_head: str,
    cohort_rows: Sequence[Mapping[str, object]],
    cohort_binding: Mapping[str, object],
    runner: T088CanaryRecordRunner,
    selection: Mapping[str, object] | None = None,
    controller_factory: Callable[[str], object] = build_t088_controller,
) -> dict[str, object]:
    """Execute exactly the selected canary rows after exact authorization.

    No partial evidence is returned: a runner failure or any validation failure
    raises before callers receive a serializable evidence document.
    """

    if not callable(runner) or not callable(controller_factory):
        raise T088CanaryExecutionError(
            "T088 canary requires callable runner/controller factory"
        )
    cohort = validate_t088_t087_cohort_binding(cohort_binding, cohort_rows)
    canonical_selection = select_t088_canary_records(
        cohort, cohort_binding=cohort_binding
    )
    if selection is None:
        raise T088CanaryExecutionError(
            "explicit deterministic canary selection is required"
        )
    if dict(selection) != canonical_selection:
        raise T088CanaryExecutionError(
            "T088 canary selection differs from its bound cohort"
        )
    definitions = t088_controller_definitions()
    validate_t088_canary_authorization(
        authorization,
        implementation_head=implementation_head,
        selection=selection,
        cohort_binding=cohort_binding,
        controller_definitions=definitions,
    )
    records = _selected_records(selection, cohort)
    rows: list[dict[str, object]] = []
    for arm in T088_ARM_ORDER:
        if arm not in T088_ARMS:
            raise T088CanaryExecutionError("T088 controller order drifted")
        controller = controller_factory(arm)
        for record in records:
            try:
                raw = runner(record, arm, controller)
            except Exception as exc:
                raise T088CanaryExecutionError(
                    "T088 canary runner failed for "
                    f"{record['selection_identity']} arm {arm}: "
                    f"{_safe_runner_exception_detail(exc)}"
                ) from exc
            if not isinstance(raw, Mapping):
                raise T088CanaryExecutionError(
                    "T088 canary runner did not return a row object"
                )
            rows.append(
                _validate_execution_row(
                    raw,
                    record=record,
                    arm=arm,
                    controller=controller,
                    cohort_binding=cohort_binding,
                )
            )
    try:
        validate_t088_canary_evidence(selection, rows, cohort_binding=cohort_binding)
    except T088IncompleteError as exc:
        raise T088CanaryExecutionError("T088 canary evidence is incomplete") from exc
    return {
        "schema_id": T088_CANARY_EVIDENCE_SCHEMA_ID,
        "task_id": T088_TASK_ID,
        "formal_execution_authorized": False,
        "implementation_head": implementation_head,
        "authorization": dict(authorization),
        "t087_cohort_binding": _binding_identity(cohort_binding),
        "canary_selection": dict(selection),
        "controller_definitions": definitions,
        "execution_count": len(rows),
        "rows": rows,
    }


def write_t088_canary_evidence(
    path: str | Path, evidence: Mapping[str, object]
) -> dict[str, object]:
    """Atomically create a validated canary artifact without overwriting evidence."""

    if (
        evidence.get("schema_id") != T088_CANARY_EVIDENCE_SCHEMA_ID
        or evidence.get("task_id") != T088_TASK_ID
    ):
        raise T088CanaryExecutionError("T088 canary evidence schema/task is invalid")
    destination = Path(path).resolve()
    if destination.exists():
        raise T088CanaryExecutionError("refusing to overwrite retained canary evidence")
    destination.parent.mkdir(parents=True, exist_ok=True)
    encoded = (
        json.dumps(
            dict(evidence),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
        + b"\n"
    )
    try:
        descriptor = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(encoded)
    except OSError as exc:
        raise T088CanaryExecutionError(
            "cannot create T088 canary evidence artifact"
        ) from exc
    return {
        "path": str(destination),
        "sha256": hashlib.sha256(encoded).hexdigest(),
        "size_bytes": len(encoded),
        "schema_id": T088_CANARY_EVIDENCE_SCHEMA_ID,
    }


__all__ = [
    "T088_CANARY_AUTHORIZATION_SCHEMA_ID",
    "T088_CANARY_EVIDENCE_SCHEMA_ID",
    "T088CanaryExecutionError",
    "T088NativeCanaryRecordRunner",
    "execute_t088_canary",
    "validate_t088_canary_authorization",
    "write_t088_canary_evidence",
]
