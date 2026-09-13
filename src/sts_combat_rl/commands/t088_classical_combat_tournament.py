"""T088 controller construction; no canary or formal execution is enabled yet."""

from __future__ import annotations

import math
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

from sts_combat_rl.commands.t085_native_execution import (
    T085UnguidedBattleSearchV2Controller,
)
from sts_combat_rl.sim.action_space import ActionSpaceConfig
from sts_combat_rl.sim.classical_combat_search import (
    BEAM_NAME,
    H1_NAME,
    BeamH1Controller,
    ClassicalSearchUnavailableError,
)
from sts_combat_rl.sim.contract import SimulatorAction, SimulatorSnapshot
from sts_combat_rl.sim.controller_contract import (
    ControllerDecision,
    ControllerProvenance,
    OnlineController,
)
from sts_combat_rl.sim.lightspeed_source import (
    lightspeed_source_identity_dict,
    load_lightspeed_source_manifest,
)
from sts_combat_rl.sim.online_controller import NATIVE_SEARCH_INFORMATION_REGIME
from sts_combat_rl.sim.oracle_search import (
    ORACLE_SEARCH_SCHEMA_ID,
    build_oracle_search_report,
    oracle_search_controller_metadata,
    select_oracle_root_action,
)
from sts_combat_rl.sim.policy_contract import DecisionContext

T088_ARM_ORDER = ("A", "B", "C", "D")
T088_PROGRESSIVE_BIAS_NAME = "progressive_bias_mcts_h1_400_v1"
T088_PROGRESSIVE_BIAS_SIMULATIONS = 400
T088_PROGRESSIVE_BIAS_WEIGHT = 0.50
T088_PROGRESSIVE_BIAS_AUDIT_LIMIT = 256
T088_PROGRESSIVE_BIAS_NATIVE_API = (
    "StepSimulator.battle_search_v2_with_progressive_bias.v1"
)
T088_PROGRESSIVE_BIAS_PATCH_IDENTITY = (
    "sts_lightspeed_battle_search_v2_progressive_bias_h1_v1"
)
T088_PROGRESSIVE_BIAS_TELEMETRY_SCHEMA_ID = (
    "native-battle-search-progressive-bias-h1-v1"
)
T088_WORK_COUNTERS_SCHEMA_ID = "native-battle-search-work-v1"
T088_NATIVE_IDENTITY = {
    "repository": "lsmfttb/sts_lightspeed",
    "ref": "refs/heads/stsrl/main",
    "commit": "20a6c2b3a9cea817c988178b814f083ff889853f",
}


def _non_negative_int(value: object, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ClassicalSearchUnavailableError(f"{label} must be a non-negative integer")
    return value


def _finite_number(value: object, label: str) -> float:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(float(value))
    ):
        raise ClassicalSearchUnavailableError(f"{label} must be finite numeric")
    return float(value)


def _score(value: object, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ClassicalSearchUnavailableError(f"{label} must be numeric")
    return float(value)


def _same_score(actual: float, expected: float) -> bool:
    if math.isnan(actual) or math.isnan(expected):
        return math.isnan(actual) and math.isnan(expected)
    if math.isinf(actual) or math.isinf(expected):
        return actual == expected
    return math.isclose(actual, expected, rel_tol=1e-12, abs_tol=1e-12)


def _validated_t088_native_identity() -> dict[str, object]:
    try:
        manifest = load_lightspeed_source_manifest()
    except (OSError, ValueError) as exc:
        raise ClassicalSearchUnavailableError(
            "T088 progressive bias requires a readable pinned source manifest"
        ) from exc
    repository = manifest.integration.repository_url.rstrip("/").removesuffix(".git")
    identity = {
        "repository": repository.removeprefix("https://github.com/"),
        "ref": manifest.integration.ref,
        "commit": manifest.integration.commit,
    }
    if identity != T088_NATIVE_IDENTITY:
        raise ClassicalSearchUnavailableError(
            f"T088 progressive bias requires exact accepted native identity {T088_NATIVE_IDENTITY['commit']}"
        )
    if "native_battle_search_v2_progressive_bias_h1" not in manifest.capability_ids:
        raise ClassicalSearchUnavailableError(
            "T088 progressive bias source manifest lacks its native capability"
        )
    return identity


def _validated_h1(value: object, label: str) -> dict[str, float]:
    if not isinstance(value, Mapping):
        raise ClassicalSearchUnavailableError(f"{label} must be an object")
    h1 = {
        name: _finite_number(value.get(name), f"{label}.{name}")
        for name in (
            "player_hp_fraction",
            "active_enemy_hp_fraction",
            "block_fraction",
            "turn_fraction",
            "h_raw",
            "value",
        )
    }
    expected_raw = (
        2 * h1["player_hp_fraction"]
        - 2 * h1["active_enemy_hp_fraction"]
        + 0.5 * h1["block_fraction"]
        - 0.1 * h1["turn_fraction"]
    )
    if not math.isclose(h1["h_raw"], expected_raw, rel_tol=1e-12, abs_tol=1e-12):
        raise ClassicalSearchUnavailableError(f"{label}.h_raw violates fixed H1")
    if not math.isclose(
        h1["value"], math.tanh(h1["h_raw"]), rel_tol=1e-12, abs_tol=1e-12
    ):
        raise ClassicalSearchUnavailableError(f"{label}.value violates fixed H1")
    return h1


def _validated_native_telemetry(raw: Mapping[str, object]) -> dict[str, object]:
    work = raw.get("work_counters")
    if (
        not isinstance(work, Mapping)
        or work.get("schema_id") != T088_WORK_COUNTERS_SCHEMA_ID
    ):
        raise ClassicalSearchUnavailableError("T088 native work_counters are missing")
    work_values = {
        name: _non_negative_int(work.get(name), f"work_counters.{name}")
        for name in (
            "action_execution_count",
            "successor_transition_count",
            "tree_and_rollout_action_execution_count",
            "heuristic_successor_transition_count",
            "tree_node_expansion_count",
            "rollout_count",
            "terminal_utility_evaluation_count",
            "model_calls",
        )
    }
    if (
        work_values["successor_transition_count"]
        != work_values["action_execution_count"]
        or work_values["tree_and_rollout_action_execution_count"]
        != work_values["action_execution_count"]
        - work_values["heuristic_successor_transition_count"]
    ):
        raise ClassicalSearchUnavailableError(
            "T088 native work counters are inconsistent"
        )
    if work_values["model_calls"] != 0:
        raise ClassicalSearchUnavailableError(
            "T088 progressive bias consumed model calls"
        )
    telemetry = raw.get("progressive_bias_telemetry")
    if (
        not isinstance(telemetry, Mapping)
        or telemetry.get("schema_id") != T088_PROGRESSIVE_BIAS_TELEMETRY_SCHEMA_ID
    ):
        raise ClassicalSearchUnavailableError(
            "T088 native progressive-bias telemetry is missing"
        )
    if (
        telemetry.get("enabled") is not True
        or telemetry.get("heuristic") != H1_NAME
        or _finite_number(telemetry.get("weight"), "progressive_bias.weight")
        != T088_PROGRESSIVE_BIAS_WEIGHT
    ):
        raise ClassicalSearchUnavailableError(
            "T088 progressive-bias configuration drifted"
        )
    audit_limit = _non_negative_int(
        telemetry.get("audit_limit"), "progressive_bias.audit_limit"
    )
    if audit_limit != T088_PROGRESSIVE_BIAS_AUDIT_LIMIT:
        raise ClassicalSearchUnavailableError(
            "T088 progressive-bias audit limit drifted"
        )
    counts = {
        name: _non_negative_int(telemetry.get(name), f"progressive_bias.{name}")
        for name in (
            "heuristic_available_count",
            "heuristic_terminal_unavailable_count",
            "heuristic_invalid_unavailable_count",
            "score_count",
            "audit_dropped_count",
        )
    }
    if (
        counts["heuristic_available_count"]
        + counts["heuristic_terminal_unavailable_count"]
        + counts["heuristic_invalid_unavailable_count"]
        != work_values["heuristic_successor_transition_count"]
    ):
        raise ClassicalSearchUnavailableError(
            "T088 H1 availability counts are inconsistent"
        )
    rows = telemetry.get("audit_rows")
    if (
        not isinstance(rows, Sequence)
        or isinstance(rows, (str, bytes))
        or len(rows) > audit_limit
        or counts["score_count"] < len(rows)
        or counts["audit_dropped_count"] != counts["score_count"] - len(rows)
    ):
        raise ClassicalSearchUnavailableError(
            "T088 progressive-bias audit is malformed"
        )
    parsed_rows: list[dict[str, object]] = []
    for index, value in enumerate(rows):
        if not isinstance(value, Mapping):
            raise ClassicalSearchUnavailableError(
                f"progressive_bias.audit_rows[{index}] is malformed"
            )
        row = {
            name: _non_negative_int(
                value.get(name), f"progressive_bias.audit_rows[{index}].{name}"
            )
            for name in (
                "parent_expansion_ordinal",
                "parent_depth",
                "child_edge_index",
                "child_visit_count",
            )
        }
        available = value.get("h1_available")
        if not isinstance(available, bool):
            raise ClassicalSearchUnavailableError(
                f"progressive_bias.audit_rows[{index}].h1_available is malformed"
            )
        bias = _finite_number(
            value.get("bias_contribution"),
            f"progressive_bias.audit_rows[{index}].bias_contribution",
        )
        base, final = (
            _score(
                value.get("base_score"),
                f"progressive_bias.audit_rows[{index}].base_score",
            ),
            _score(
                value.get("final_score"),
                f"progressive_bias.audit_rows[{index}].final_score",
            ),
        )
        if value.get("base_score_finite") is not math.isfinite(base) or value.get(
            "final_score_finite"
        ) is not math.isfinite(final):
            raise ClassicalSearchUnavailableError(
                f"progressive_bias.audit_rows[{index}] finite flags are invalid"
            )
        if available:
            if value.get("h1_unavailable_reason") is not None:
                raise ClassicalSearchUnavailableError(
                    f"progressive_bias.audit_rows[{index}] has contradictory H1 availability"
                )
            h1 = _validated_h1(
                value.get("child_h1"), f"progressive_bias.audit_rows[{index}].child_h1"
            )
            expected_bias = (
                T088_PROGRESSIVE_BIAS_WEIGHT
                * h1["value"]
                / (1 + row["child_visit_count"])
            )
            if not math.isclose(bias, expected_bias, rel_tol=1e-12, abs_tol=1e-12):
                raise ClassicalSearchUnavailableError(
                    f"progressive_bias.audit_rows[{index}] violates bias decay"
                )
        else:
            if (
                not isinstance(value.get("h1_unavailable_reason"), str)
                or not value.get("h1_unavailable_reason")
                or value.get("child_h1") is not None
                or bias != 0
            ):
                raise ClassicalSearchUnavailableError(
                    f"progressive_bias.audit_rows[{index}] has invalid unavailable H1"
                )
            h1 = None
        if not _same_score(final, base + bias):
            raise ClassicalSearchUnavailableError(
                f"progressive_bias.audit_rows[{index}] final score is inconsistent"
            )
        parsed_rows.append(
            {
                **row,
                "h1_available": available,
                "h1_unavailable_reason": value.get("h1_unavailable_reason"),
                "child_h1": h1,
                "base_score": base,
                "bias_contribution": bias,
                "final_score": final,
                "base_score_finite": math.isfinite(base),
                "final_score_finite": math.isfinite(final),
            }
        )
    return {
        "work_counters": {"schema_id": T088_WORK_COUNTERS_SCHEMA_ID, **work_values},
        "progressive_bias_telemetry": {
            "schema_id": T088_PROGRESSIVE_BIAS_TELEMETRY_SCHEMA_ID,
            "enabled": True,
            "heuristic": H1_NAME,
            "weight": T088_PROGRESSIVE_BIAS_WEIGHT,
            "audit_limit": audit_limit,
            **counts,
            "audit_rows": parsed_rows,
        },
    }


@dataclass(frozen=True)
class ProgressiveBiasMCTSH1Controller:
    """Fixed T088 Arm D, using only the canonical native opt-in API."""

    action_space: ActionSpaceConfig = field(
        default_factory=ActionSpaceConfig.initial_no_potions
    )
    provenance: ControllerProvenance = field(init=False)  # type: ignore[assignment]
    _validated_native_identity: Mapping[str, object] = field(
        init=False, repr=False, compare=False
    )

    def __post_init__(self) -> None:
        if (
            self.action_space.to_dict()
            != ActionSpaceConfig.initial_no_potions().to_dict()
        ):
            raise ClassicalSearchUnavailableError(
                "T088 progressive bias requires initial_no_potions action space"
            )
        native_identity = _validated_t088_native_identity()
        object.__setattr__(self, "_validated_native_identity", native_identity)
        object.__setattr__(
            self,
            "provenance",
            ControllerProvenance(
                kind="classical_battle_search",
                name=T088_PROGRESSIVE_BIAS_NAME,
                config={
                    "task_id": "T088",
                    "information_regime": NATIVE_SEARCH_INFORMATION_REGIME,
                    "native_identity": native_identity,
                    "native_source_identity": lightspeed_source_identity_dict(),
                    "native_search_schema_id": ORACLE_SEARCH_SCHEMA_ID,
                    "native_search_api": T088_PROGRESSIVE_BIAS_NATIVE_API,
                    "native_search_patch_identity": T088_PROGRESSIVE_BIAS_PATCH_IDENTITY,
                    "simulations": T088_PROGRESSIVE_BIAS_SIMULATIONS,
                    "root_selection_rule": "highest_mean",
                    "action_space": self.action_space.to_dict(),
                    "policy_prior_callback": None,
                    "root_action_priors": None,
                    "leaf_value_callback": None,
                    "rollout": "BattleScumSearcher2::playoutRandom",
                    "native_terminal_utility": "BattleScumSearcher2::evaluateEndState",
                    "heuristic": H1_NAME,
                    "progressive_bias": "0.50 * combat_handcrafted_h1(child_state) / (1 + child_visit_count)",
                    "progressive_bias_weight": T088_PROGRESSIVE_BIAS_WEIGHT,
                    "progressive_bias_scope": "all_searchable_tree_nodes",
                    "audit_limit": T088_PROGRESSIVE_BIAS_AUDIT_LIMIT,
                    "work_counters_schema_id": T088_WORK_COUNTERS_SCHEMA_ID,
                    "model_calls_required": 0,
                    "controller_seed": None,
                },
            ),
        )

    def select_action(
        self,
        adapter: object,
        snapshot: SimulatorSnapshot,
        actions: Sequence[SimulatorAction],
        context: DecisionContext,
        step_index: int,
    ) -> ControllerDecision:
        search = getattr(adapter, "battle_search_v2_with_progressive_bias", None)
        if not callable(search):
            raise ClassicalSearchUnavailableError(
                "T088 progressive bias requires the native opt-in adapter API"
            )
        started = time.perf_counter()
        try:
            raw = search(
                snapshot,
                simulations=T088_PROGRESSIVE_BIAS_SIMULATIONS,
                include_potions=False,
                bias_enabled=True,
                audit_limit=T088_PROGRESSIVE_BIAS_AUDIT_LIMIT,
            )
        except (AttributeError, RuntimeError, TypeError, ValueError) as exc:
            raise ClassicalSearchUnavailableError(
                "T088 progressive-bias native search failed"
            ) from exc
        if not isinstance(raw, Mapping):
            raise ClassicalSearchUnavailableError(
                "T088 progressive-bias native search did not return an object"
            )
        try:
            report = build_oracle_search_report(
                raw,
                actions,
                context,
                expected_native_api=T088_PROGRESSIVE_BIAS_NATIVE_API,
                expected_patch_identity=T088_PROGRESSIVE_BIAS_PATCH_IDENTITY,
                wall_clock_time_s=time.perf_counter() - started,
            )
        except (TypeError, ValueError) as exc:
            raise ClassicalSearchUnavailableError(
                "T088 progressive-bias native root report is malformed"
            ) from exc
        if (
            not report.search_ok
            or report.simulations_requested != T088_PROGRESSIVE_BIAS_SIMULATIONS
            or report.include_potions
            or report.model_calls != 0
        ):
            raise ClassicalSearchUnavailableError(
                "T088 progressive-bias native root report violated the fixed controller boundary"
            )
        telemetry = _validated_native_telemetry(raw)
        target = select_oracle_root_action(report, selection_rule="highest_mean")
        metadata = oracle_search_controller_metadata(report, target)
        metadata["t088_progressive_bias"] = {
            "controller_step_index": step_index,
            "native_identity": dict(self._validated_native_identity),
            "callbacks_disabled": True,
            "root_priors_disabled": True,
            "native_work": telemetry,
        }
        return ControllerDecision(
            selected_index=target.legal_action_index,
            provenance=self.provenance,
            reason=f"{T088_PROGRESSIVE_BIAS_NAME}:highest_mean",
            score=target.score,
            metadata=metadata,
        )


def build_t088_controller(arm: str) -> OnlineController:
    """Construct the fixed T088 arms without replacing any unavailable arm."""
    if arm in ("A", "B"):
        return T085UnguidedBattleSearchV2Controller(
            simulations=100 if arm == "A" else 400
        )
    if arm == "C":
        return BeamH1Controller()
    if arm == "D":
        return ProgressiveBiasMCTSH1Controller()
    raise ValueError(f"unknown T088 arm {arm!r}; expected {T088_ARM_ORDER}")


def t088_controller_definitions() -> dict[str, object]:
    """Expose four fixed definitions without claiming tournament readiness."""
    return {
        "task": "T088",
        "schema_id": "t088-controller-definitions-v1",
        "arm_order": list(T088_ARM_ORDER),
        "tournament_execution_ready": False,
        "arms": {
            "A": {"controller": "Search-v2", "simulations": 100},
            "B": {"controller": "Search-v2", "simulations": 400},
            "C": {"controller": BEAM_NAME, "width": 32, "transition_budget": 400},
            "D": {
                "controller": T088_PROGRESSIVE_BIAS_NAME,
                "simulations": T088_PROGRESSIVE_BIAS_SIMULATIONS,
                "progressive_bias_weight": T088_PROGRESSIVE_BIAS_WEIGHT,
                "progressive_bias": "0.50 * combat_handcrafted_h1(child_state) / (1 + child_visit_count)",
                "availability": "canonical_native_opt_in",
                "native_identity": dict(T088_NATIVE_IDENTITY),
            },
        },
    }
