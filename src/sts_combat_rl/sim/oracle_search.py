"""Oracle-like native battle search controller and root-stat mapping."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
import math
import time
from typing import Any

from sts_combat_rl.sim.action_space import ActionSpaceConfig, POTION_ACTION_KINDS
from sts_combat_rl.sim.contract import (
    SimulatorAction,
    SimulatorAdapter,
    SimulatorSnapshot,
)
from sts_combat_rl.sim.controller_contract import (
    ControllerDecision,
    ControllerProvenance,
    json_safe_mapping,
)
from sts_combat_rl.sim.decision_record import (
    action_identity_dicts_for_actions,
)
from sts_combat_rl.sim.lightspeed_source import lightspeed_source_identity_dict
from sts_combat_rl.sim.online_controller import NATIVE_SEARCH_INFORMATION_REGIME
from sts_combat_rl.sim.policy import DecisionContext
from sts_combat_rl.sim.search_telemetry import (
    SEARCH_DECISION_TELEMETRY_SCHEMA_ID,
    SEARCH_DECISION_TELEMETRY_SCHEMA_VERSION,
    SearchDecisionTelemetry,
)


ORACLE_SEARCH_SCHEMA_ID = "native-battle-search-root-v1"
ORACLE_SEARCH_NATIVE_API = "StepSimulator.battle_search.v1"
ORACLE_SEARCH_PATCH_IDENTITY = "sts_lightspeed_battle_search_root_v1"
ORACLE_SEARCH_CONTROLLER_VERSION = "oracle-search-controller-v1"
ORACLE_ROOT_SELECTION_RULES = ("highest_mean", "most_visits")


@dataclass(frozen=True)
class OracleRootActionStatistics:
    """One native root-stat row mapped to a current legal action occurrence."""

    legal_action_index: int
    action_identity: dict[str, Any]
    action_id: int | str | None
    kind: str
    label: str
    eligible: bool
    visits: int
    evaluation_sum: float | None
    mean_value: float | None
    visit_probability: float
    search_tree_present: bool
    native_action: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "legal_action_index": self.legal_action_index,
            "action_identity": dict(self.action_identity),
            "action_id": self.action_id,
            "kind": self.kind,
            "label": self.label,
            "eligible": self.eligible,
            "visits": self.visits,
            "evaluation_sum": self.evaluation_sum,
            "mean_value": self.mean_value,
            "visit_probability": self.visit_probability,
            "search_tree_present": self.search_tree_present,
            "native_action": dict(self.native_action),
        }


@dataclass(frozen=True)
class OracleSearchTarget:
    """Selected teacher action under one named root-selection rule."""

    selection_rule: str
    legal_action_index: int
    action_identity: dict[str, Any]
    visits: int
    mean_value: float | None
    score: float | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "selection_rule": self.selection_rule,
            "legal_action_index": self.legal_action_index,
            "action_identity": dict(self.action_identity),
            "visits": self.visits,
            "mean_value": self.mean_value,
            "score": self.score,
        }


@dataclass(frozen=True)
class OracleSearchReport:
    """Validated root search result for one pre-decision state."""

    schema_id: str
    native_api: str
    patch_identity: str
    information_regime: str
    simulations_requested: int
    root_visits: int
    include_potions: bool
    native_simulator_steps: int | None
    model_calls: int | None
    best_action_value: float | None
    min_action_value: float | None
    outcome_player_hp: int | None
    legal_action_count: int
    eligible_action_count: int
    root_actions: tuple[OracleRootActionStatistics, ...]
    soft_visit_target: tuple[float, ...]
    soft_visit_denominator: int
    root_row_count: int
    search_edge_count: int | None
    unsearched_legal_action_count: int | None
    unmapped_search_edge_count: int | None
    wall_clock_time_s: float | None
    problems: tuple[str, ...] = ()

    @property
    def search_ok(self) -> bool:
        return bool(self.root_actions) and not self.problems

    @property
    def unmapped_root_row_count(self) -> int:
        return sum(
            1 for action in self.root_actions if not action.search_tree_present
        ) + len(self.problems)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "native_api": self.native_api,
            "patch_identity": self.patch_identity,
            "information_regime": self.information_regime,
            "simulations_requested": self.simulations_requested,
            "root_visits": self.root_visits,
            "include_potions": self.include_potions,
            "native_simulator_steps": self.native_simulator_steps,
            "model_calls": self.model_calls,
            "best_action_value": self.best_action_value,
            "min_action_value": self.min_action_value,
            "outcome_player_hp": self.outcome_player_hp,
            "legal_action_count": self.legal_action_count,
            "eligible_action_count": self.eligible_action_count,
            "root_actions": [action.to_dict() for action in self.root_actions],
            "soft_visit_target": list(self.soft_visit_target),
            "soft_visit_denominator": self.soft_visit_denominator,
            "root_row_count": self.root_row_count,
            "search_edge_count": self.search_edge_count,
            "unsearched_legal_action_count": self.unsearched_legal_action_count,
            "unmapped_search_edge_count": self.unmapped_search_edge_count,
            "wall_clock_time_s": self.wall_clock_time_s,
            "decision_telemetry": oracle_search_decision_telemetry(self).to_dict(),
            "problems": list(self.problems),
        }


@dataclass(frozen=True)
class OracleSearchController:
    """OnlineController wrapper around hidden-state native battle search."""

    simulations: int
    root_selection_rule: str = "highest_mean"
    action_space: ActionSpaceConfig = field(
        default_factory=ActionSpaceConfig.initial_no_potions
    )
    native_source_identity: Mapping[str, Any] | None = None
    provenance: ControllerProvenance = field(init=False)  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.simulations <= 0:
            raise ValueError("oracle search simulations must be positive")
        validate_oracle_root_selection_rule(self.root_selection_rule)
        source_identity = (
            dict(self.native_source_identity)
            if self.native_source_identity is not None
            else lightspeed_source_identity_dict()
        )
        object.__setattr__(
            self,
            "provenance",
            ControllerProvenance(
                kind="oracle_battle_search",
                name=f"oracle_search_v1_{self.root_selection_rule}_s{self.simulations}",
                config={
                    "controller_version": ORACLE_SEARCH_CONTROLLER_VERSION,
                    "information_regime": NATIVE_SEARCH_INFORMATION_REGIME,
                    "native_search_schema_id": ORACLE_SEARCH_SCHEMA_ID,
                    "native_search_api": ORACLE_SEARCH_NATIVE_API,
                    "native_search_patch_identity": ORACLE_SEARCH_PATCH_IDENTITY,
                    "native_source_identity": source_identity,
                    "search_budget": {
                        "simulations": self.simulations,
                        "budget_unit": "native_random_terminal_playouts",
                    },
                    "rollout_configuration": {
                        "rollout_policy": "BattleScumSearcher2::playoutRandom",
                        "leaf_value": "BattleScumSearcher2::evaluateEndState",
                        "model_calls": 0,
                    },
                    "search_telemetry": {
                        "schema_id": SEARCH_DECISION_TELEMETRY_SCHEMA_ID,
                        "schema_version": SEARCH_DECISION_TELEMETRY_SCHEMA_VERSION,
                        "model_calls_for_native_baseline": 0,
                        "unavailable_native_fields": {
                            "tree_depth": "native battle_search does not expose tree depth",
                            "value_uncertainty": (
                                "native battle_search does not expose uncertainty"
                            ),
                        },
                    },
                    "root_selection_rule": self.root_selection_rule,
                    "action_space": self.action_space.to_dict(),
                    "include_potions": _include_potions_for_battle_search(
                        self.action_space
                    ),
                    "reproducibility": {
                        "deterministic_given_restored_checkpoint": True,
                        "native_rng_seed_source": "BattleContext.seed+floorNum",
                        "python_rng_seed": None,
                    },
                    "root_mapping": "occurrence_safe_action_identity_v1",
                },
            ),
        )

    def select_action(
        self,
        adapter: SimulatorAdapter,
        snapshot: SimulatorSnapshot,
        actions: Sequence[SimulatorAction],
        context: DecisionContext,
        step_index: int,
    ) -> ControllerDecision:
        del step_index
        if not hasattr(adapter, "battle_search"):
            raise ValueError("oracle search controller requires battle_search adapter")

        search_fn = getattr(adapter, "battle_search")
        start = time.perf_counter()
        raw_search = search_fn(
            snapshot,
            simulations=self.simulations,
            include_potions=_include_potions_for_battle_search(self.action_space),
        )
        elapsed = time.perf_counter() - start
        report = build_oracle_search_report(
            raw_search,
            actions,
            context,
            wall_clock_time_s=elapsed,
        )
        if not report.search_ok:
            raise ValueError(
                "oracle root mapping failed: " + "; ".join(report.problems)
            )
        target = select_oracle_root_action(
            report,
            selection_rule=self.root_selection_rule,
        )
        return ControllerDecision(
            selected_index=target.legal_action_index,
            provenance=self.provenance,
            reason=f"oracle_search:{self.root_selection_rule}",
            score=target.score,
            metadata=oracle_search_controller_metadata(report, target),
        )


def validate_oracle_root_selection_rule(selection_rule: str) -> None:
    """Validate the named root-selection rule."""

    if selection_rule not in ORACLE_ROOT_SELECTION_RULES:
        raise ValueError(f"unknown oracle root selection rule: {selection_rule}")


def build_oracle_search_report(
    raw_search: Mapping[str, Any],
    actions: Sequence[SimulatorAction],
    context: DecisionContext,
    *,
    wall_clock_time_s: float | None = None,
) -> OracleSearchReport:
    """Validate native root rows and align them to current legal actions."""

    raw = _require_mapping(raw_search, "native oracle search result")
    problems: list[str] = []
    schema_id = str(raw.get("schema_id", ""))
    if schema_id != ORACLE_SEARCH_SCHEMA_ID:
        problems.append(f"unsupported native search schema_id {schema_id!r}")
    native_api = str(raw.get("native_api", ""))
    if native_api != ORACLE_SEARCH_NATIVE_API:
        problems.append(f"unsupported native search api {native_api!r}")
    patch_identity = str(raw.get("patch_identity", ""))
    if patch_identity != ORACLE_SEARCH_PATCH_IDENTITY:
        problems.append(f"unsupported native search patch identity {patch_identity!r}")
    information_regime = str(raw.get("information_regime", ""))
    if information_regime != NATIVE_SEARCH_INFORMATION_REGIME:
        problems.append(
            f"native search information regime must be "
            f"{NATIVE_SEARCH_INFORMATION_REGIME!r}"
        )

    legal_identities = action_identity_dicts_for_actions(actions)
    legal_by_stable = {
        str(identity["stable_id"]): index
        for index, identity in enumerate(legal_identities)
    }
    if len(legal_by_stable) != len(legal_identities):
        problems.append("current legal actions have ambiguous occurrence identities")

    rows = raw.get("root_rows")
    if not isinstance(rows, Sequence) or isinstance(rows, (str, bytes)):
        raise ValueError("native oracle search root_rows must be a list")

    row_actions: list[SimulatorAction] = []
    parsed_rows: list[dict[str, Any]] = []
    for row_index, value in enumerate(rows):
        row = _require_mapping(value, f"root row {row_index}")
        scope = _required_string(row.get("scope"), f"root row {row_index} scope")
        bits = _non_negative_int(row.get("bits"), f"root row {row_index} bits")
        kind = _required_string(row.get("kind"), f"root row {row_index} kind")
        label = str(row.get("label", ""))
        action_id = f"{scope}:{bits}"
        row_actions.append(
            SimulatorAction(
                action_id=action_id,
                label=label,
                kind=kind,
                raw={
                    "scope": scope,
                    "bits": bits,
                    "idx1": _optional_int(row.get("idx1")),
                    "idx2": _optional_int(row.get("idx2")),
                    "idx3": _optional_int(row.get("idx3")),
                },
            )
        )
        parsed_rows.append(row)

    row_identities = action_identity_dicts_for_actions(row_actions)
    row_by_stable: dict[str, int] = {}
    duplicate_rows: set[str] = set()
    for index, identity in enumerate(row_identities):
        stable_id = str(identity["stable_id"])
        if stable_id in row_by_stable:
            duplicate_rows.add(stable_id)
        row_by_stable[stable_id] = index
    if duplicate_rows:
        problems.append(
            "native root rows contain duplicate action identities: "
            + ", ".join(sorted(duplicate_rows))
        )

    missing = sorted(set(legal_by_stable) - set(row_by_stable))
    unexpected = sorted(set(row_by_stable) - set(legal_by_stable))
    if missing:
        problems.append(
            "native root rows omitted current legal actions: " + ", ".join(missing)
        )
    if unexpected:
        problems.append(
            "native root rows returned unknown legal actions: " + ", ".join(unexpected)
        )

    simulations_requested = _non_negative_int(
        raw.get("simulations_requested"), "simulations_requested"
    )
    root_visits = _non_negative_int(raw.get("root_visits"), "root_visits")
    if simulations_requested <= 0:
        problems.append("oracle search simulations_requested must be positive")
    if root_visits <= 0:
        problems.append("oracle search root_visits must be positive")

    stats: list[OracleRootActionStatistics] = []
    total_row_visits = 0
    for stable_id, legal_index in legal_by_stable.items():
        row_index = row_by_stable.get(stable_id)
        if row_index is None:
            continue
        row = parsed_rows[row_index]
        identity = legal_identities[legal_index]
        visits = _non_negative_int(row.get("visits"), f"root row {row_index} visits")
        total_row_visits += visits
        evaluation_sum = _optional_finite_float(
            row.get("evaluation_sum"), f"root row {row_index} evaluation_sum"
        )
        mean_value = _optional_finite_float(
            row.get("mean_value"), f"root row {row_index} mean_value"
        )
        if visits > 0 and mean_value is None and evaluation_sum is not None:
            mean_value = evaluation_sum / visits
        if visits > 0 and mean_value is None:
            problems.append(f"root row {row_index} has visits but no mean_value")
        if visits == 0 and mean_value is not None:
            problems.append(f"root row {row_index} has mean_value without visits")
        stats.append(
            OracleRootActionStatistics(
                legal_action_index=legal_index,
                action_identity=dict(identity),
                action_id=identity.get("action_id"),
                kind=str(identity.get("kind", "")),
                label=str(identity.get("label", "")),
                eligible=legal_index in context.eligible_action_indices,
                visits=visits,
                evaluation_sum=evaluation_sum,
                mean_value=mean_value,
                visit_probability=0.0,
                search_tree_present=bool(row.get("search_tree_present", True)),
                native_action={
                    "scope": row.get("scope"),
                    "bits": row.get("bits"),
                    "idx1": row.get("idx1"),
                    "idx2": row.get("idx2"),
                    "idx3": row.get("idx3"),
                    "search_edge_index": row.get("search_edge_index"),
                },
            )
        )

    if stats and total_row_visits != root_visits:
        problems.append(
            "native root visits do not equal summed root-row visits: "
            f"{root_visits} != {total_row_visits}"
        )

    eligible_visit_sum = sum(stat.visits for stat in stats if stat.eligible)
    if stats and eligible_visit_sum <= 0:
        problems.append("oracle search has no visited eligible root action")
    stats = [
        OracleRootActionStatistics(
            legal_action_index=stat.legal_action_index,
            action_identity=stat.action_identity,
            action_id=stat.action_id,
            kind=stat.kind,
            label=stat.label,
            eligible=stat.eligible,
            visits=stat.visits,
            evaluation_sum=stat.evaluation_sum,
            mean_value=stat.mean_value,
            visit_probability=(
                stat.visits / eligible_visit_sum
                if stat.eligible and eligible_visit_sum > 0
                else 0.0
            ),
            search_tree_present=stat.search_tree_present,
            native_action=stat.native_action,
        )
        for stat in sorted(stats, key=lambda item: item.legal_action_index)
    ]
    soft_visit_target = tuple(stat.visit_probability for stat in stats)

    return OracleSearchReport(
        schema_id=schema_id,
        native_api=native_api,
        patch_identity=patch_identity,
        information_regime=information_regime,
        simulations_requested=simulations_requested,
        root_visits=root_visits,
        include_potions=bool(raw.get("include_potions", False)),
        native_simulator_steps=_optional_non_negative_int(
            raw.get("native_simulator_steps"), "native_simulator_steps"
        ),
        model_calls=_optional_non_negative_int(raw.get("model_calls"), "model_calls"),
        best_action_value=_optional_finite_float(
            raw.get("best_action_value"), "best_action_value"
        ),
        min_action_value=_optional_finite_float(
            raw.get("min_action_value"), "min_action_value"
        ),
        outcome_player_hp=_optional_int(raw.get("outcome_player_hp")),
        legal_action_count=len(actions),
        eligible_action_count=len(context.eligible_action_indices),
        root_actions=tuple(stats),
        soft_visit_target=soft_visit_target,
        soft_visit_denominator=eligible_visit_sum,
        root_row_count=_non_negative_int(raw.get("root_row_count"), "root_row_count"),
        search_edge_count=_optional_non_negative_int(
            raw.get("search_edge_count"), "search_edge_count"
        ),
        unsearched_legal_action_count=_optional_non_negative_int(
            raw.get("unsearched_legal_action_count"),
            "unsearched_legal_action_count",
        ),
        unmapped_search_edge_count=_optional_non_negative_int(
            raw.get("unmapped_search_edge_count"), "unmapped_search_edge_count"
        ),
        wall_clock_time_s=wall_clock_time_s,
        problems=tuple(dict.fromkeys(problems)),
    )


def select_oracle_root_action(
    report: OracleSearchReport,
    *,
    selection_rule: str,
) -> OracleSearchTarget:
    """Select one eligible root action under a named rule."""

    if not report.search_ok:
        raise ValueError("cannot select from invalid oracle search report")
    validate_oracle_root_selection_rule(selection_rule)
    candidates = [
        action
        for action in report.root_actions
        if action.eligible and action.visits > 0
    ]
    if selection_rule == "highest_mean":
        candidates = [action for action in candidates if action.mean_value is not None]
        if not candidates:
            raise ValueError("oracle search has no eligible action with a mean value")
        selected = max(
            candidates,
            key=lambda action: (
                float(action.mean_value),
                action.visits,
                -action.legal_action_index,
            ),
        )
        score = selected.mean_value
    else:
        selected = max(
            candidates,
            key=lambda action: (
                action.visits,
                float(action.mean_value)
                if action.mean_value is not None
                else -math.inf,
                -action.legal_action_index,
            ),
        )
        score = float(selected.visits)
    return OracleSearchTarget(
        selection_rule=selection_rule,
        legal_action_index=selected.legal_action_index,
        action_identity=dict(selected.action_identity),
        visits=selected.visits,
        mean_value=selected.mean_value,
        score=score,
    )


def oracle_search_controller_metadata(
    report: OracleSearchReport,
    target: OracleSearchTarget,
) -> dict[str, Any]:
    """Return JSON-safe per-decision telemetry for evaluation aggregation."""

    telemetry = oracle_search_decision_telemetry(report, target=target)
    return json_safe_mapping(
        {
            "oracle_search_decision_count": 1,
            "oracle_search_simulations": report.simulations_requested,
            "oracle_search_root_visits": report.root_visits,
            "oracle_search_native_simulator_steps": report.native_simulator_steps,
            "oracle_search_model_calls": telemetry.model_calls,
            "oracle_search_wall_clock_time_s": report.wall_clock_time_s,
            "oracle_search_root_row_count": report.root_row_count,
            "oracle_search_unmapped_root_rows": report.unmapped_root_row_count,
            "oracle_search_unsearched_legal_actions": (
                report.unsearched_legal_action_count
            ),
            "oracle_search_unmapped_search_edges": report.unmapped_search_edge_count,
            "oracle_search_root_mapping_failures": len(report.problems),
            "oracle_search_selected_rule": target.selection_rule,
            "oracle_search_selected_index": target.legal_action_index,
            "oracle_search_selected_visits": target.visits,
            "oracle_search_selected_mean_value": target.mean_value,
            "search_decision_telemetry_schema_id": (
                SEARCH_DECISION_TELEMETRY_SCHEMA_ID
            ),
            "search_decision_telemetry": [telemetry.to_dict()],
            "oracle_search_decision_reports": [report.to_dict()],
        }
    )


def oracle_search_decision_telemetry(
    report: OracleSearchReport,
    *,
    target: OracleSearchTarget | None = None,
) -> SearchDecisionTelemetry:
    """Build current-schema telemetry for one Oracle-like native search."""

    eligible_values = [
        action.mean_value
        for action in report.root_actions
        if action.eligible and action.visits > 0 and action.mean_value is not None
    ]
    sorted_values = sorted((float(value) for value in eligible_values), reverse=True)
    root_value_max = sorted_values[0] if sorted_values else None
    root_value_min = sorted_values[-1] if sorted_values else None
    root_value_spread = (
        root_value_max - root_value_min
        if root_value_max is not None and root_value_min is not None
        else None
    )
    root_decision_gap = (
        sorted_values[0] - sorted_values[1] if len(sorted_values) >= 2 else None
    )
    unavailable = {
        "tree_depth": "native battle_search does not expose tree depth",
        "value_uncertainty": "native battle_search does not expose uncertainty",
    }
    if report.native_simulator_steps is None:
        unavailable["native_simulator_steps"] = (
            "native search result did not expose native_simulator_steps"
        )
    if report.search_edge_count is None:
        unavailable["search_edge_count"] = (
            "native search result did not expose search_edge_count"
        )
    if report.unsearched_legal_action_count is None:
        unavailable["unsearched_legal_action_count"] = (
            "native search result did not expose unsearched_legal_action_count"
        )
    if report.unmapped_search_edge_count is None:
        unavailable["unmapped_search_edge_count"] = (
            "native search result did not expose unmapped_search_edge_count"
        )
    if root_value_spread is None:
        unavailable["root_value_spread"] = (
            "no visited eligible root action mean values were available"
        )
    if root_decision_gap is None:
        unavailable["root_decision_gap"] = (
            "fewer than two visited eligible root actions had mean values"
        )

    return SearchDecisionTelemetry(
        information_regime=report.information_regime,
        controller_kind="oracle_battle_search",
        search_kind="native_random_terminal_playout",
        search_backend={
            "native_api": report.native_api,
            "patch_identity": report.patch_identity,
            "schema_id": report.schema_id,
        },
        requested_budget={
            "unit": "native_random_terminal_playouts",
            "amount": report.simulations_requested,
        },
        simulations_requested=report.simulations_requested,
        root_visits=report.root_visits,
        root_action_count=len(report.root_actions),
        legal_action_count=report.legal_action_count,
        eligible_action_count=report.eligible_action_count,
        visited_action_count=sum(
            1 for action in report.root_actions if action.visits > 0
        ),
        visited_eligible_action_count=sum(
            1 for action in report.root_actions if action.eligible and action.visits > 0
        ),
        native_simulator_steps=report.native_simulator_steps,
        model_calls=0 if report.model_calls is None else report.model_calls,
        wall_clock_time_s=report.wall_clock_time_s,
        root_value_min=root_value_min,
        root_value_max=root_value_max,
        root_value_spread=root_value_spread,
        root_decision_gap=root_decision_gap,
        unsearched_legal_action_count=report.unsearched_legal_action_count,
        unmapped_search_edge_count=report.unmapped_search_edge_count,
        unmapped_root_row_count=report.unmapped_root_row_count,
        root_mapping_failure_count=len(report.problems),
        selection_rule=None if target is None else target.selection_rule,
        selected_legal_action_index=(
            None if target is None else target.legal_action_index
        ),
        selected_visits=None if target is None else target.visits,
        selected_mean_value=None if target is None else target.mean_value,
        unavailable_fields=unavailable,
        problems=report.problems,
    )


def oracle_visit_target_dict(report: OracleSearchReport) -> dict[str, Any]:
    """Serialize the soft root-visit target separately from teacher action."""

    return {
        "target_kind": "root_visit_distribution",
        "probabilities": list(report.soft_visit_target),
        "denominator": report.soft_visit_denominator,
    }


def _include_potions_for_battle_search(action_space: ActionSpaceConfig) -> bool:
    return not bool(action_space.excluded_kinds.intersection(POTION_ACTION_KINDS))


def _require_mapping(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} must be an object")
    return {str(key): item for key, item in value.items()}


def _required_string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{label} must be a non-empty string")
    return value


def _non_negative_int(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{label} must be a non-negative integer")
    return value


def _optional_non_negative_int(value: Any, label: str) -> int | None:
    if value is None:
        return None
    return _non_negative_int(value, label)


def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError("optional integer field must be an integer or null")
    return value


def _optional_finite_float(value: Any, label: str) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} must be numeric or null")
    converted = float(value)
    if not math.isfinite(converted):
        raise ValueError(f"{label} must be finite")
    return converted
