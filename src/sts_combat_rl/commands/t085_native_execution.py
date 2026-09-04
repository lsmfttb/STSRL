"""Bounded native execution seam for the T085 paired evaluation.

Source generation and battle mechanics remain owned by the pinned
``sts_lightspeed`` simulator.  This module composes the existing T085 source
and restore/parity validators, wraps an existing simulator adapter, and
retains a terminal label only when the selected action's *pre-action* native
search root edge proves the transition terminal.  The retained utility is the
native root-edge mean verbatim; this module never reimplements
``evaluateEndState`` or computes a game-mechanics formula in Python.

The paired runner owns restore/controller stepping.  The adapter exposes the
repository's accepted restore helper through ``restore_t085_battle_start_record``;
the runner performs search before every in-battle ``step`` and derives survival
from the simulator's authoritative terminal transition.  Caller-supplied
survival, utility, cohort, arm, budget, or provenance fields are not accepted.
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
    restore_assisted_battle_start_record,
)
from sts_combat_rl.sim.battle_start_pool import (
    BattleStartCheckpointRecord,
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
from sts_combat_rl.sim.online_controller import NATIVE_SEARCH_INFORMATION_REGIME
from sts_combat_rl.sim.oracle_search import (
    ORACLE_SEARCH_NATIVE_API,
    ORACLE_SEARCH_PATCH_IDENTITY,
    ORACLE_SEARCH_SCHEMA_ID,
    OracleSearchReport,
    build_oracle_search_report,
    oracle_search_controller_metadata,
    select_oracle_root_action,
)
from sts_combat_rl.t085_corrected_leaf_value_search_evaluation import (
    T085_NATIVE_IDENTITY,
    T085_SEARCH_400_ARMS,
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
    write_t085_json_artifact,
)

T085_NATIVE_V2_API = "StepSimulator.battle_search_v2.v1"
T085_NATIVE_V2_PATCH = "sts_lightspeed_battle_search_v2_tree_internal_v1"
T085_NATIVE_TERMINAL_LABEL_SCHEMA_ID = "t085-native-terminal-root-label-v1"
T085_NATIVE_SELECTION_SCHEMA_ID = "t085-native-selection-artifact-v1"
T085_NATIVE_OUTCOMES_SCHEMA_ID = "t085-native-outcome-records-v1"
T085_NATIVE_EXECUTION_VERSION = "t085-native-execution-v1"
T085_NATIVE_SEARCH_BACKENDS = ("battle_search", "battle_search_v2")
T085NativeSearchBackend = Literal["battle_search", "battle_search_v2"]

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


def resolve_t085_canonical_records(
    path: str | Path = T085_T052_COHORT_PATH,
    *,
    expected_sha256: str = T085_T052_COHORT_SHA256,
) -> dict[str, BattleStartCheckpointRecord]:
    """Load full fixed-cohort records and bind them by exact checkpoint identity."""
    resolved = Path(path).resolve(strict=True)
    digest = sha256_file(resolved)
    if digest != expected_sha256:
        raise T085NativeExecutionError(
            "T085 canonical cohort bytes do not match the accepted SHA-256"
        )
    with resolved.open(encoding="utf-8") as stream:
        cohort = load_fixed_cohort_jsonl(stream)
    records: dict[str, BattleStartCheckpointRecord] = {}
    for index, full in enumerate(cohort.records):
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
                or self.target_kind != "battle_survival_probability"
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
            "battle_survival_probability",
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
            "battle_survival_probability",
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
        raw = search(
            snapshot,
            simulations=self.simulations,
            include_potions=False,
            policy_prior_callback=self.arm.policy_prior_callback,
            leaf_value_callback=self.arm.leaf_value_callback,
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
    if canonical_records_by_cohort is None:
        canonical_records_by_cohort = {
            "A": resolve_t085_canonical_records(canonical_records_path)
        }
    required_record_maps = {"A", "B", "C", "B@400"}
    if not required_record_maps.issubset(canonical_records_by_cohort):
        raise T085NativeExecutionError(
            "T085 paired evaluation requires separately verified full-record maps for A/T052, B, and C"
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
        adapter = T085NativeTerminalSearchAdapter(
            base_adapter,
            search_simulations=budget,
            search_backend=search_backend,
            policy_prior_callback=selected_arm.policy_prior_callback,
            leaf_value_callback=selected_arm.leaf_value_callback,
        )
        cohort = _cohort_for_record(plan, record, arm)
        restored = restore_t085_canonical_record(
            adapter, record, canonical_records_by_cohort[cohort]
        )
        if isinstance(restored, tuple):
            snapshot = restored[0]
        else:
            snapshot = restored
        if not isinstance(snapshot, SimulatorSnapshot):
            raise T085NativeExecutionError(
                "T085 restore did not return a SimulatorSnapshot"
            )
        adapter._current_snapshot = snapshot
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
        row_payload["native_terminal_utility_provenance"] = label.to_dict()
        retained_rows.append(row_payload)
        retained_labels.append(label.to_dict())
        return row

    report = run_t085_paired_evaluation(
        plan.cohorts,
        evaluate_record=evaluate_record,
        selection_evidence=plan.selection_evidence,
    )
    report_payload = dict(report)
    report_payload["task_id"] = "T085"
    report_payload["selection_artifact"] = selection_reference
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
        "native_identity": native_identity,
        "selection_artifact": selection_reference,
        "paired_report_artifact": report_reference,
        "selection_binding": report.get("selection_binding"),
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
        "status": "verified",
        "task_id": "T085",
        "selection_artifact": selection_reference,
        "paired_report_artifact": report_reference,
        "outcomes_artifact": outcomes_reference,
        "report": report,
    }


__all__ = [
    "T085NativeArm",
    "T085NativeArmController",
    "T085NativeEvaluationPlan",
    "T085NativeExecutionError",
    "T085NativeRootEdgeLabel",
    "T085NativeSearchBackend",
    "T085NativeTerminalSearchAdapter",
    "T085UnguidedBattleSearchV2Controller",
    "build_t085_native_arms",
    "build_t085_native_evaluation_plan",
    "finalize_t085_native_root_edge_label",
    "prepare_t085_native_root_edge_label",
    "run_t085_native_paired_evaluation",
    "write_t085_native_selection_artifact",
]
