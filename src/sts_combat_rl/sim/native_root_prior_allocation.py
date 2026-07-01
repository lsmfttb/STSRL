"""Diagnostic native root-prior allocation smoke reports."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import json
import math
import time
from pathlib import Path
from typing import Any

from sts_combat_rl.sim.action_space import (
    ActionSpaceConfig,
    action_space_for_screen,
    choose_deterministic_action,
)
from sts_combat_rl.sim.contract import (
    SimulatorAction,
    SimulatorAdapter,
    SimulatorSnapshot,
)
from sts_combat_rl.sim.controlled_run import build_decision_context
from sts_combat_rl.sim.decision_record import (
    action_identity_dicts_for_actions,
    stable_action_identity_id,
)
from sts_combat_rl.sim.lightspeed_source import lightspeed_source_identity_dict
from sts_combat_rl.sim.online_controller import NATIVE_SEARCH_INFORMATION_REGIME
from sts_combat_rl.sim.oracle_search import (
    ORACLE_SEARCH_NATIVE_API,
    ORACLE_SEARCH_PATCH_IDENTITY,
    OracleSearchReport,
    build_oracle_search_report,
)
from sts_combat_rl.sim.policy import DecisionContext


NATIVE_ROOT_PRIOR_ALLOCATION_REPORT_SCHEMA_ID = "native-root-prior-allocation-report-v1"
NATIVE_ROOT_PRIOR_ALLOCATION_REPORT_SCHEMA_VERSION = 1
NATIVE_ROOT_PRIOR_SEARCH_NATIVE_API = "StepSimulator.battle_search_with_root_priors.v1"
NATIVE_ROOT_PRIOR_SEARCH_PATCH_IDENTITY = "sts_lightspeed_root_prior_allocation_v1"
NATIVE_ROOT_PRIOR_ALLOCATION_METADATA_SCHEMA_ID = (
    "native-root-prior-allocation-metadata-v1"
)
NATIVE_ROOT_PRIOR_ALLOCATION_STRATEGY = "root_prior_mixture_v1"
ROOT_PRIOR_ALLOCATION_CLAIM_BOUNDARY = (
    "diagnostic full_simulator_state_oracle_like smoke only; no "
    "normal-information, live-game, broad-training, controller-promotion, "
    "or A20 performance claim"
)


PriorItems = Mapping[str, float] | Sequence[tuple[str, float]]


@dataclass(frozen=True)
class NativeRootPriorArmReport:
    """One baseline or root-prior native search arm."""

    label: str
    prior_kind: str
    search_report: OracleSearchReport
    allocation_metadata: Mapping[str, Any] | None
    allocation_rows: tuple[Mapping[str, Any], ...]
    wall_clock_time_s: float | None
    preferred_action_identity: Mapping[str, Any] | None = None

    @property
    def root_mapping_failure_count(self) -> int:
        return len(self.search_report.problems)

    @property
    def visited_root_action_count(self) -> int:
        return sum(1 for action in self.search_report.root_actions if action.visits > 0)

    def to_dict(self) -> dict[str, Any]:
        report = self.search_report
        return {
            "label": self.label,
            "prior_kind": self.prior_kind,
            "native_api": report.native_api,
            "patch_identity": report.patch_identity,
            "information_regime": report.information_regime,
            "simulations_requested": report.simulations_requested,
            "root_visits": report.root_visits,
            "include_potions": report.include_potions,
            "legal_action_count": report.legal_action_count,
            "eligible_action_count": report.eligible_action_count,
            "visited_root_action_count": self.visited_root_action_count,
            "unsearched_legal_action_count": report.unsearched_legal_action_count,
            "unmapped_search_edge_count": report.unmapped_search_edge_count,
            "native_simulator_steps": report.native_simulator_steps,
            "model_calls": 0 if report.model_calls is None else report.model_calls,
            "root_mapping_failure_count": self.root_mapping_failure_count,
            "root_actions": [action.to_dict() for action in report.root_actions],
            "allocation_metadata": (
                None
                if self.allocation_metadata is None
                else dict(self.allocation_metadata)
            ),
            "allocation_rows": [dict(row) for row in self.allocation_rows],
            "preferred_action_identity": (
                None
                if self.preferred_action_identity is None
                else dict(self.preferred_action_identity)
            ),
            "wall_clock_time_s": self.wall_clock_time_s,
            "problems": list(report.problems),
        }


@dataclass(frozen=True)
class NativeRootPriorAllocationReport:
    """Versioned T046 diagnostic report."""

    native_source_identity: Mapping[str, Any]
    source_state: Mapping[str, Any]
    configuration: Mapping[str, Any]
    arms: tuple[NativeRootPriorArmReport, ...]
    allocation_checks: Mapping[str, Any]
    problems: tuple[str, ...]
    claim_boundary: str = ROOT_PRIOR_ALLOCATION_CLAIM_BOUNDARY
    schema_id: str = NATIVE_ROOT_PRIOR_ALLOCATION_REPORT_SCHEMA_ID
    schema_version: int = NATIVE_ROOT_PRIOR_ALLOCATION_REPORT_SCHEMA_VERSION

    @property
    def passed(self) -> bool:
        return not self.problems

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "schema_version": self.schema_version,
            "native_source_identity": dict(self.native_source_identity),
            "source_state": dict(self.source_state),
            "configuration": dict(self.configuration),
            "arms": [arm.to_dict() for arm in self.arms],
            "allocation_checks": dict(self.allocation_checks),
            "claim_boundary": self.claim_boundary,
            "passed": self.passed,
            "problems": list(self.problems),
        }


def build_root_action_prior_vector(
    actions: Sequence[SimulatorAction],
    context: DecisionContext,
    root_action_priors: PriorItems,
) -> list[float]:
    """Validate occurrence-safe prior keys and return native legal-order priors."""

    identities = action_identity_dicts_for_actions(actions)
    legal_by_stable = {
        str(identity["stable_id"]): index for index, identity in enumerate(identities)
    }
    if len(legal_by_stable) != len(identities):
        raise ValueError("current legal actions have ambiguous occurrence identities")

    eligible = set(context.eligible_action_indices)
    prior_vector = [0.0 for _ in actions]
    seen: set[str] = set()
    for key, raw_value in _prior_items(root_action_priors):
        stable_id = _validate_prior_stable_id(key)
        if stable_id in seen:
            raise ValueError(f"duplicate root prior action identity: {stable_id}")
        seen.add(stable_id)
        index = legal_by_stable.get(stable_id)
        if index is None:
            raise ValueError(f"unknown root prior action identity: {stable_id}")
        if index not in eligible:
            raise ValueError(f"illegal root prior action identity: {stable_id}")
        value = _finite_non_negative_float(raw_value, "root prior value")
        prior_vector[index] = value
    return prior_vector


def run_native_root_prior_allocation_smoke(
    adapter: SimulatorAdapter,
    *,
    seed: int,
    max_steps: int,
    simulations: int,
    action_space: ActionSpaceConfig,
    include_potions: bool,
    prior_temperature: float,
    min_visits_per_legal_action: int,
    prior_allocation_weight: float,
    native_source_identity: Mapping[str, Any] | None = None,
) -> NativeRootPriorAllocationReport:
    """Run baseline, uniform-prior, and one-hot-prior native root searches."""

    _validate_smoke_config(
        simulations=simulations,
        prior_temperature=prior_temperature,
        min_visits_per_legal_action=min_visits_per_legal_action,
        prior_allocation_weight=prior_allocation_weight,
    )
    snapshot, step_index = _reach_battle(
        adapter,
        seed=seed,
        max_steps=max_steps,
        action_space=action_space,
    )
    actions = list(adapter.legal_actions(snapshot))
    context = build_decision_context(snapshot.raw, actions, action_space)
    if not context.eligible_action_indices:
        raise ValueError("root-prior smoke reached a battle with no eligible actions")

    identities = action_identity_dicts_for_actions(actions)
    preferred_index = context.eligible_action_indices[0]
    uniform_priors = {
        str(identities[index]["stable_id"]): 1.0
        for index in context.eligible_action_indices
    }
    one_hot_priors = {str(identities[preferred_index]["stable_id"]): 1.0}

    baseline = _run_arm(
        adapter,
        snapshot,
        actions,
        context,
        label="baseline",
        prior_kind="none",
        simulations=simulations,
        include_potions=include_potions,
    )
    uniform = _run_arm(
        adapter,
        snapshot,
        actions,
        context,
        label="uniform_root_prior",
        prior_kind="uniform",
        simulations=simulations,
        include_potions=include_potions,
        root_action_priors=uniform_priors,
        prior_temperature=prior_temperature,
        min_visits_per_legal_action=min_visits_per_legal_action,
        prior_allocation_weight=prior_allocation_weight,
    )
    one_hot = _run_arm(
        adapter,
        snapshot,
        actions,
        context,
        label="one_hot_root_prior",
        prior_kind="one_hot",
        simulations=simulations,
        include_potions=include_potions,
        root_action_priors=one_hot_priors,
        prior_temperature=prior_temperature,
        min_visits_per_legal_action=min_visits_per_legal_action,
        prior_allocation_weight=prior_allocation_weight,
        preferred_action_identity=identities[preferred_index],
    )

    allocation_checks = _allocation_checks(
        uniform,
        one_hot,
        preferred_index=preferred_index,
        eligible_indices=context.eligible_action_indices,
    )
    problems: list[str] = []
    for arm in (baseline, uniform, one_hot):
        problems.extend(
            f"{arm.label}: {problem}" for problem in arm.search_report.problems
        )
        if arm.search_report.information_regime != NATIVE_SEARCH_INFORMATION_REGIME:
            problems.append(f"{arm.label}: unexpected information regime")
    if not bool(allocation_checks.get("one_hot_preferred_strictly_more")):
        problems.append(
            "one-hot root prior did not dominate non-preferred root actions"
        )

    source_state = {
        "seed": seed,
        "ascension": snapshot.raw.get("ascension"),
        "step_index": step_index,
        "screen_state": snapshot.raw.get("screen_state"),
        "act": snapshot.raw.get("act"),
        "floor_num": snapshot.raw.get("floor_num"),
        "room_type": snapshot.raw.get("room_type"),
        "encounter_id": snapshot.raw.get("encounter_id"),
        "legal_action_count": len(actions),
        "eligible_action_count": len(context.eligible_action_indices),
    }
    configuration = {
        "simulations": simulations,
        "include_potions": include_potions,
        "prior_temperature": prior_temperature,
        "min_visits_per_legal_action": min_visits_per_legal_action,
        "prior_allocation_weight": prior_allocation_weight,
        "action_space": action_space.to_dict(),
        "model_calls": 0,
    }
    return NativeRootPriorAllocationReport(
        native_source_identity=(
            dict(native_source_identity)
            if native_source_identity is not None
            else lightspeed_source_identity_dict()
        ),
        source_state=source_state,
        configuration=configuration,
        arms=(baseline, uniform, one_hot),
        allocation_checks=allocation_checks,
        problems=tuple(dict.fromkeys(problems)),
    )


def native_root_prior_allocation_report_problems(
    raw: Mapping[str, Any],
) -> list[str]:
    """Return schema/claim-boundary problems for a serialized report."""

    problems: list[str] = []
    if raw.get("schema_id") != NATIVE_ROOT_PRIOR_ALLOCATION_REPORT_SCHEMA_ID:
        problems.append("unsupported native root-prior allocation report schema_id")
    if raw.get("schema_version") != NATIVE_ROOT_PRIOR_ALLOCATION_REPORT_SCHEMA_VERSION:
        problems.append(
            "unsupported native root-prior allocation report schema_version"
        )
    arms = raw.get("arms")
    if not isinstance(arms, list) or len(arms) != 3:
        problems.append("report must contain baseline, uniform, and one-hot arms")
    else:
        labels = {str(arm.get("label")) for arm in arms if isinstance(arm, Mapping)}
        for required in ("baseline", "uniform_root_prior", "one_hot_root_prior"):
            if required not in labels:
                problems.append(f"report missing arm {required!r}")
        for index, arm in enumerate(arms):
            if not isinstance(arm, Mapping):
                problems.append(f"arm {index} must be an object")
                continue
            if arm.get("information_regime") != NATIVE_SEARCH_INFORMATION_REGIME:
                problems.append(f"arm {index} has wrong information regime")
            if arm.get("model_calls") != 0:
                problems.append(f"arm {index} must report zero model calls")
            if arm.get("root_mapping_failure_count") is None:
                problems.append(f"arm {index} missing root mapping failures")
    boundary = str(raw.get("claim_boundary", ""))
    for forbidden_claim in (
        "normal-information",
        "live-game",
        "broad-training",
        "controller-promotion",
        "A20 performance",
    ):
        if forbidden_claim not in boundary:
            problems.append(f"claim boundary missing {forbidden_claim}")
    return problems


def write_native_root_prior_allocation_report(
    path: str | Path,
    report: NativeRootPriorAllocationReport,
) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(
        json.dumps(report.to_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def root_prior_allocation_metadata(raw: Mapping[str, Any]) -> dict[str, Any]:
    """Return validated T046 allocation metadata from a native search result."""

    return dict(_allocation_metadata(raw))


def root_prior_allocation_rows(raw: Mapping[str, Any]) -> tuple[dict[str, Any], ...]:
    """Return JSON-safe allocation rows from a native root-prior search result."""

    return tuple(dict(row) for row in _allocation_rows(raw))


def format_native_root_prior_allocation_report(
    report: NativeRootPriorAllocationReport,
) -> str:
    lines = [
        "Native root-prior allocation smoke",
        f"schema: {report.schema_id} v{report.schema_version}",
        f"passed: {'yes' if report.passed else 'no'}",
        f"information regime: {NATIVE_SEARCH_INFORMATION_REGIME}",
        f"claim boundary: {report.claim_boundary}",
        (
            "source: "
            f"seed={report.source_state.get('seed')} "
            f"ascension={report.source_state.get('ascension')} "
            f"step={report.source_state.get('step_index')} "
            f"encounter={report.source_state.get('encounter_id')}"
        ),
        (
            "configuration: "
            f"simulations={report.configuration.get('simulations')} "
            f"temperature={report.configuration.get('prior_temperature')} "
            f"min_visits={report.configuration.get('min_visits_per_legal_action')} "
            f"allocation_weight={report.configuration.get('prior_allocation_weight')}"
        ),
        "arms:",
    ]
    for arm in report.arms:
        search = arm.search_report
        lines.append(
            "  "
            f"{arm.label}: visits={search.root_visits}, "
            f"visited_actions={arm.visited_root_action_count}, "
            f"unsearched_legal={search.unsearched_legal_action_count}, "
            f"native_steps={search.native_simulator_steps}, "
            f"model_calls={0 if search.model_calls is None else search.model_calls}, "
            f"mapping_failures={arm.root_mapping_failure_count}"
        )
    lines.append("allocation checks:")
    lines.append(
        "  uniform allocated visits: "
        + ", ".join(
            str(item)
            for item in report.allocation_checks.get("uniform_allocations", [])
        )
    )
    lines.append(
        "  one-hot allocated visits: "
        + ", ".join(
            str(item)
            for item in report.allocation_checks.get("one_hot_allocations", [])
        )
    )
    lines.append(
        "  one-hot preferred strictly more: "
        + (
            "yes"
            if report.allocation_checks.get("one_hot_preferred_strictly_more")
            else "no"
        )
    )
    if report.problems:
        lines.append("problems:")
        lines.extend(f"  {problem}" for problem in report.problems)
    return "\n".join(lines)


def _run_arm(
    adapter: SimulatorAdapter,
    snapshot: SimulatorSnapshot,
    actions: Sequence[SimulatorAction],
    context: DecisionContext,
    *,
    label: str,
    prior_kind: str,
    simulations: int,
    include_potions: bool,
    root_action_priors: PriorItems | None = None,
    prior_temperature: float | None = None,
    min_visits_per_legal_action: int | None = None,
    prior_allocation_weight: float | None = None,
    preferred_action_identity: Mapping[str, Any] | None = None,
) -> NativeRootPriorArmReport:
    start = time.perf_counter()
    if root_action_priors is None:
        raw = adapter.battle_search(  # type: ignore[attr-defined]
            snapshot,
            simulations=simulations,
            include_potions=include_potions,
        )
        expected_api = ORACLE_SEARCH_NATIVE_API
        expected_patch = ORACLE_SEARCH_PATCH_IDENTITY
    else:
        raw = adapter.battle_search_with_root_priors(  # type: ignore[attr-defined]
            snapshot,
            actions=actions,
            context=context,
            simulations=simulations,
            include_potions=include_potions,
            root_action_priors=root_action_priors,
            prior_temperature=prior_temperature,
            min_visits_per_legal_action=min_visits_per_legal_action,
            prior_allocation_weight=prior_allocation_weight,
        )
        expected_api = NATIVE_ROOT_PRIOR_SEARCH_NATIVE_API
        expected_patch = NATIVE_ROOT_PRIOR_SEARCH_PATCH_IDENTITY
    elapsed = time.perf_counter() - start
    report = build_oracle_search_report(
        raw,
        actions,
        context,
        expected_native_api=expected_api,
        expected_patch_identity=expected_patch,
        wall_clock_time_s=elapsed,
    )
    allocation_metadata = (
        _allocation_metadata(raw) if root_action_priors is not None else None
    )
    return NativeRootPriorArmReport(
        label=label,
        prior_kind=prior_kind,
        search_report=report,
        allocation_metadata=allocation_metadata,
        allocation_rows=tuple(_allocation_rows(raw)),
        wall_clock_time_s=elapsed,
        preferred_action_identity=preferred_action_identity,
    )


def _allocation_metadata(raw: Mapping[str, Any]) -> Mapping[str, Any]:
    metadata = raw.get("allocation_metadata")
    if not isinstance(metadata, Mapping):
        raise ValueError("root-prior native search did not return allocation_metadata")
    if metadata.get("schema_id") != NATIVE_ROOT_PRIOR_ALLOCATION_METADATA_SCHEMA_ID:
        raise ValueError("unsupported root-prior allocation metadata schema")
    if metadata.get("allocation_strategy") != NATIVE_ROOT_PRIOR_ALLOCATION_STRATEGY:
        raise ValueError("unsupported root-prior allocation strategy")
    return {str(key): value for key, value in metadata.items()}


def _allocation_rows(raw: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    rows = raw.get("root_rows")
    if not isinstance(rows, Sequence) or isinstance(rows, (str, bytes)):
        return []
    return [
        {str(key): value for key, value in row.items()}
        for row in rows
        if isinstance(row, Mapping)
    ]


def _allocation_checks(
    uniform: NativeRootPriorArmReport,
    one_hot: NativeRootPriorArmReport,
    *,
    preferred_index: int,
    eligible_indices: Sequence[int],
) -> dict[str, Any]:
    uniform_allocations = _eligible_allocations(uniform, eligible_indices)
    one_hot_allocations = _eligible_allocations(one_hot, eligible_indices)
    preferred_allocated = _allocated_visit_at(one_hot, preferred_index)
    competitor_allocations = [
        _allocated_visit_at(one_hot, index)
        for index in eligible_indices
        if index != preferred_index and _search_tree_present_at(one_hot, index)
    ]
    return {
        "uniform_allocations": uniform_allocations,
        "one_hot_allocations": one_hot_allocations,
        "one_hot_preferred_index": preferred_index,
        "one_hot_preferred_allocated_visits": preferred_allocated,
        "one_hot_non_preferred_max_allocated_visits": (
            max(competitor_allocations) if competitor_allocations else None
        ),
        "one_hot_preferred_strictly_more": all(
            preferred_allocated > value for value in competitor_allocations
        ),
    }


def _eligible_allocations(
    arm: NativeRootPriorArmReport,
    eligible_indices: Sequence[int],
) -> list[int]:
    return [
        _allocated_visit_at(arm, index)
        for index in eligible_indices
        if _search_tree_present_at(arm, index)
    ]


def _allocated_visit_at(arm: NativeRootPriorArmReport, index: int) -> int:
    if index < 0 or index >= len(arm.allocation_rows):
        return 0
    value = arm.allocation_rows[index].get("allocated_root_visits")
    return int(value) if isinstance(value, int) and not isinstance(value, bool) else 0


def _search_tree_present_at(arm: NativeRootPriorArmReport, index: int) -> bool:
    if index < 0 or index >= len(arm.allocation_rows):
        return False
    return bool(arm.allocation_rows[index].get("search_tree_present"))


def _reach_battle(
    adapter: SimulatorAdapter,
    *,
    seed: int,
    max_steps: int,
    action_space: ActionSpaceConfig,
) -> tuple[SimulatorSnapshot, int]:
    snapshot = adapter.reset(seed=seed)
    for step_index in range(max_steps + 1):
        if str(snapshot.raw.get("screen_state")) == "BATTLE" and bool(
            snapshot.raw.get("battle_active")
        ):
            return snapshot, step_index
        if step_index == max_steps:
            break
        actions = list(adapter.legal_actions(snapshot))
        if not actions:
            break
        effective_action_space = action_space_for_screen(
            action_space,
            screen_state=str(snapshot.raw.get("screen_state", "(none)")),
            battle_active=bool(snapshot.raw.get("battle_active")),
        )
        transition = adapter.step(
            choose_deterministic_action(actions, effective_action_space)
        )
        snapshot = transition.snapshot
        if transition.terminal:
            break
    raise ValueError("could not reach an active battle for root-prior smoke")


def _prior_items(root_action_priors: PriorItems) -> list[tuple[str, float]]:
    if isinstance(root_action_priors, Mapping):
        return [(str(key), value) for key, value in root_action_priors.items()]
    if isinstance(root_action_priors, Sequence) and not isinstance(
        root_action_priors, (str, bytes)
    ):
        items: list[tuple[str, float]] = []
        for index, item in enumerate(root_action_priors):
            if (
                not isinstance(item, Sequence)
                or isinstance(item, (str, bytes))
                or len(item) != 2
            ):
                raise ValueError(f"root prior item {index} must be a key/value pair")
            key, value = item
            items.append((str(key), value))
        return items
    raise ValueError("root action priors must be a mapping or key/value sequence")


def _validate_prior_stable_id(value: object) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError("root prior action identity must be a non-empty string")
    try:
        raw = json.loads(value)
    except json.JSONDecodeError as exc:
        raise ValueError("malformed root prior action identity") from exc
    if not isinstance(raw, Mapping):
        raise ValueError("malformed root prior action identity")
    action_id = raw.get("action_id")
    if action_id is not None and not isinstance(action_id, (int, str)):
        raise ValueError("malformed root prior action identity")
    occurrence = raw.get("occurrence")
    if (
        isinstance(occurrence, bool)
        or not isinstance(occurrence, int)
        or occurrence < 0
    ):
        raise ValueError("malformed root prior action identity")
    kind = raw.get("kind")
    if not isinstance(kind, str) or not kind:
        raise ValueError("malformed root prior action identity")
    expected = stable_action_identity_id(
        action_id=action_id,
        occurrence=occurrence,
        kind=kind,
    )
    if value != expected:
        raise ValueError("malformed root prior action identity")
    return value


def _finite_non_negative_float(value: object, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} must be numeric")
    converted = float(value)
    if not math.isfinite(converted) or converted < 0.0:
        raise ValueError(f"{label} must be finite and non-negative")
    return converted


def _validate_smoke_config(
    *,
    simulations: int,
    prior_temperature: float,
    min_visits_per_legal_action: int,
    prior_allocation_weight: float,
) -> None:
    if simulations <= 0:
        raise ValueError("root-prior smoke simulations must be positive")
    if not math.isfinite(prior_temperature) or prior_temperature <= 0.0:
        raise ValueError("root-prior temperature must be finite and positive")
    if min_visits_per_legal_action < 0:
        raise ValueError("root-prior min visits must be non-negative")
    if (
        not math.isfinite(prior_allocation_weight)
        or prior_allocation_weight < 0.0
        or prior_allocation_weight > 1.0
    ):
        raise ValueError("root-prior allocation weight must be between zero and one")
