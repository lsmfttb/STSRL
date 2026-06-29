"""T040 expert non-combat source-coverage comparison reports.

This module is offline: it compares already-generated natural battle-start
pools and T021 coverage reports. It does not run the simulator, train models,
or promote the heuristic non-combat driver as a final controller.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import json
from typing import Any, TextIO

from sts_combat_rl.sim.battle_start_pool import NaturalBattleStartPool
from sts_combat_rl.sim.online_controller import NATIVE_SEARCH_INFORMATION_REGIME
from sts_combat_rl.sim.reachability import (
    ReachabilityArmReport,
    build_reachability_arm_report,
)


EXPERT_SOURCE_COVERAGE_SCHEMA_ID = "expert-non-combat-source-coverage-comparison-v1"
EXPERT_SOURCE_COVERAGE_FORMAT_VERSION = 1
EXPERT_SOURCE_COVERAGE_REQUIRED_TERMINAL_RUNS = 1000
EXPERT_SOURCE_COVERAGE_ARM_STOCHASTIC_S20 = "stochastic_s20"
EXPERT_SOURCE_COVERAGE_ARM_EXPERT_S20 = "expert_s20"
EXPERT_SOURCE_COVERAGE_ARM_EXPERT_S100 = "expert_s100"
EXPERT_SOURCE_COVERAGE_ARM_ROLES = (
    EXPERT_SOURCE_COVERAGE_ARM_STOCHASTIC_S20,
    EXPERT_SOURCE_COVERAGE_ARM_EXPERT_S20,
    EXPERT_SOURCE_COVERAGE_ARM_EXPERT_S100,
)


@dataclass(frozen=True)
class ExpertSourceArmContract:
    """Expected T040 behavior-changing settings for one comparison arm."""

    role: str
    non_combat_controller_name: str
    oracle_search_simulations: int
    root_selection_rule: str = "highest_mean"

    def to_dict(self) -> dict[str, Any]:
        return {
            "role": self.role,
            "non_combat_controller_name": self.non_combat_controller_name,
            "oracle_search_simulations": self.oracle_search_simulations,
            "root_selection_rule": self.root_selection_rule,
        }


EXPERT_SOURCE_COVERAGE_ARM_CONTRACTS: Mapping[str, ExpertSourceArmContract] = {
    EXPERT_SOURCE_COVERAGE_ARM_STOCHASTIC_S20: ExpertSourceArmContract(
        role=EXPERT_SOURCE_COVERAGE_ARM_STOCHASTIC_S20,
        non_combat_controller_name="stochastic_non_combat_v1",
        oracle_search_simulations=20,
    ),
    EXPERT_SOURCE_COVERAGE_ARM_EXPERT_S20: ExpertSourceArmContract(
        role=EXPERT_SOURCE_COVERAGE_ARM_EXPERT_S20,
        non_combat_controller_name="expert_non_combat_v1",
        oracle_search_simulations=20,
    ),
    EXPERT_SOURCE_COVERAGE_ARM_EXPERT_S100: ExpertSourceArmContract(
        role=EXPERT_SOURCE_COVERAGE_ARM_EXPERT_S100,
        non_combat_controller_name="expert_non_combat_v1",
        oracle_search_simulations=100,
    ),
}


@dataclass(frozen=True)
class ExpertSourceCoverageArmReport:
    """One role-labeled arm in the T040 comparison."""

    role: str
    arm: ReachabilityArmReport
    contract: ExpertSourceArmContract
    contract_problems: tuple[str, ...] = ()

    @property
    def arm_passed(self) -> bool:
        return self.arm.arm_passed and not self.contract_problems

    def to_dict(self) -> dict[str, Any]:
        payload = self.arm.to_dict()
        payload["role"] = self.role
        payload["contract"] = self.contract.to_dict()
        payload["contract_passed"] = not self.contract_problems
        payload["contract_problems"] = list(self.contract_problems)
        payload["arm_passed"] = self.arm_passed
        return payload


@dataclass(frozen=True)
class ExpertSourceCoverageComparisonReport:
    """T040 three-arm source-coverage comparison."""

    arms: tuple[ExpertSourceCoverageArmReport, ...]
    source_identity: dict[str, Any]
    command_problems: tuple[str, ...] = ()
    schema_id: str = EXPERT_SOURCE_COVERAGE_SCHEMA_ID
    format_version: int = EXPERT_SOURCE_COVERAGE_FORMAT_VERSION

    @property
    def command_passed(self) -> bool:
        return not self.command_problems

    def to_dict(self) -> dict[str, Any]:
        comparison = _expert_comparison_dict(self.arms)
        return {
            "schema_id": self.schema_id,
            "format_version": self.format_version,
            "source_identity": _json_safe_mapping(self.source_identity),
            "required_arms": {
                role: contract.to_dict()
                for role, contract in EXPERT_SOURCE_COVERAGE_ARM_CONTRACTS.items()
            },
            "scale_target": {
                "terminal_source_runs_per_arm": (
                    EXPERT_SOURCE_COVERAGE_REQUIRED_TERMINAL_RUNS
                ),
                "requires_zero_truncated_runs": True,
            },
            "arms": [arm.to_dict() for arm in self.arms],
            "comparison": comparison,
            "command_passed": self.command_passed,
            "command_problems": list(self.command_problems),
        }


def build_expert_source_coverage_comparison_report(
    arm_inputs: Sequence[
        tuple[str, NaturalBattleStartPool, Mapping[str, Any], Mapping[str, Any]]
    ],
) -> ExpertSourceCoverageComparisonReport:
    """Build the T040 report from role-labeled pool/coverage artifacts.

    Inputs are ``(role, pool, coverage_report, artifact_identity)``. The role
    set must be the three required T040 arms.
    """

    roles = [role for role, _, _, _ in arm_inputs]
    role_problems = _role_set_problems(roles)
    arm_reports = []
    for role, pool, coverage_report, artifact_identity in arm_inputs:
        contract = EXPERT_SOURCE_COVERAGE_ARM_CONTRACTS.get(
            role,
            ExpertSourceArmContract(
                role=role,
                non_combat_controller_name="(unknown)",
                oracle_search_simulations=-1,
            ),
        )
        reachability_arm = build_reachability_arm_report(
            label=role,
            pool=pool,
            coverage_report=coverage_report,
            artifact_identity=artifact_identity,
        )
        arm_reports.append(
            ExpertSourceCoverageArmReport(
                role=role,
                arm=reachability_arm,
                contract=contract,
                contract_problems=tuple(
                    _arm_contract_problems(reachability_arm, contract)
                ),
            )
        )

    source_identity = dict(arm_reports[0].arm.source_identity) if arm_reports else {}
    command_problems = [
        *role_problems,
        *_common_source_identity_problems(arm_reports),
    ]
    for arm in arm_reports:
        command_problems.extend(
            f"{arm.role}: {problem}" for problem in arm.arm.problems
        )
        command_problems.extend(
            f"{arm.role}: {problem}" for problem in arm.contract_problems
        )
    return ExpertSourceCoverageComparisonReport(
        arms=tuple(arm_reports),
        source_identity=source_identity,
        command_problems=tuple(dict.fromkeys(command_problems)),
    )


def dump_expert_source_coverage_comparison_report_json(
    report: ExpertSourceCoverageComparisonReport,
    stream: TextIO,
) -> None:
    """Write a deterministic JSON report."""

    json.dump(report.to_dict(), stream, indent=2, sort_keys=True)
    stream.write("\n")


def format_expert_source_coverage_comparison_report(
    report: ExpertSourceCoverageComparisonReport,
) -> str:
    """Format compact stderr evidence for the T040 report."""

    comparison = _expert_comparison_dict(report.arms)
    lines = [
        "Expert non-combat source-coverage comparison",
        f"schema: {report.schema_id} v{report.format_version}",
        f"command passed: {_yes_no(report.command_passed)}",
        "arms:",
    ]
    for arm in report.arms:
        lines.append(f"  {arm.role}:")
        lines.append(
            f"    non-combat driver: {arm.arm.controller.non_combat_controller_name}"
        )
        lines.append(
            f"    battle controller: {arm.arm.controller.battle_controller_name}"
        )
        lines.append(
            "    oracle search simulations: "
            f"{_search_simulations(arm.arm.controller.search_budget)}"
        )
        lines.append(f"    terminal source runs: {arm.arm.terminal_run_count}")
        lines.append(f"    truncated source runs: {arm.arm.truncated_run_count}")
        lines.append(f"    battle starts: {arm.arm.natural_battle_start_count}")
        lines.append(f"    Act 1 Boss starts: {arm.arm.act1_boss_battle_start_count}")
        lines.append(f"    later-act starts: {arm.arm.later_act_battle_start_count}")
        lines.append(
            "    T009 broad training allowed: "
            f"{_nested_get(arm.arm.training_gate_report, 'broad_training_allowed')}"
        )
        _append_problem_list(lines, "    contract problems", arm.contract_problems)
        _append_problem_list(lines, "    arm problems", arm.arm.problems)
    lines.append("comparison:")
    for key, value in comparison.items():
        lines.append(f"  {key}: {value}")
    _append_problem_list(lines, "command problems", report.command_problems)
    return "\n".join(lines)


def _role_set_problems(roles: Sequence[str]) -> list[str]:
    problems: list[str] = []
    if len(set(roles)) != len(roles):
        problems.append("expert source coverage arm roles must be unique")
    expected = set(EXPERT_SOURCE_COVERAGE_ARM_ROLES)
    observed = set(roles)
    missing = sorted(expected - observed)
    extra = sorted(observed - expected)
    if missing:
        problems.append("missing required T040 arm role(s): " + ", ".join(missing))
    if extra:
        problems.append("unknown T040 arm role(s): " + ", ".join(extra))
    return problems


def _arm_contract_problems(
    arm: ReachabilityArmReport,
    contract: ExpertSourceArmContract,
) -> list[str]:
    problems: list[str] = []
    controller = arm.controller
    if controller.information_regime != NATIVE_SEARCH_INFORMATION_REGIME:
        problems.append(
            "battle controller information regime is not "
            f"{NATIVE_SEARCH_INFORMATION_REGIME}"
        )
    if controller.non_combat_controller_name != contract.non_combat_controller_name:
        problems.append(
            "non-combat controller name "
            f"{controller.non_combat_controller_name!r} does not match "
            f"{contract.non_combat_controller_name!r}"
        )
    observed_simulations = _search_simulations(controller.search_budget)
    if observed_simulations != contract.oracle_search_simulations:
        problems.append(
            "oracle search simulations "
            f"{observed_simulations!r} does not match "
            f"{contract.oracle_search_simulations!r}"
        )
    if controller.root_selection_rule != contract.root_selection_rule:
        problems.append(
            "root selection rule "
            f"{controller.root_selection_rule!r} does not match "
            f"{contract.root_selection_rule!r}"
        )
    return problems


def _common_source_identity_problems(
    arms: Sequence[ExpertSourceCoverageArmReport],
) -> list[str]:
    commits = {
        str(arm.arm.source_identity.get("integration_commit", ""))
        for arm in arms
        if arm.arm.source_identity
    }
    if len(commits) > 1:
        return ["expert source coverage arms use different sts_lightspeed commits"]
    return []


def _expert_comparison_dict(
    arms: Sequence[ExpertSourceCoverageArmReport],
) -> dict[str, Any]:
    by_role = {arm.role: arm.arm for arm in arms}
    stochastic = by_role.get(EXPERT_SOURCE_COVERAGE_ARM_STOCHASTIC_S20)
    expert_s20 = by_role.get(EXPERT_SOURCE_COVERAGE_ARM_EXPERT_S20)
    expert_s100 = by_role.get(EXPERT_SOURCE_COVERAGE_ARM_EXPERT_S100)
    scale_target_met = all(
        arm.arm.terminal_run_count >= EXPERT_SOURCE_COVERAGE_REQUIRED_TERMINAL_RUNS
        and arm.arm.truncated_run_count == 0
        for arm in arms
    )
    expert_s20_boss_delta = _delta(
        expert_s20,
        stochastic,
        "act1_boss_battle_start_count",
    )
    expert_s20_later_delta = _delta(
        expert_s20,
        stochastic,
        "later_act_battle_start_count",
    )
    return {
        "scale_target_met": scale_target_met,
        "all_contracts_passed": all(arm.arm_passed for arm in arms),
        "stochastic_s20_act1_boss_start_count": _count(
            stochastic, "act1_boss_battle_start_count"
        ),
        "expert_s20_act1_boss_start_count": _count(
            expert_s20, "act1_boss_battle_start_count"
        ),
        "expert_s100_act1_boss_start_count": _count(
            expert_s100, "act1_boss_battle_start_count"
        ),
        "stochastic_s20_later_act_start_count": _count(
            stochastic, "later_act_battle_start_count"
        ),
        "expert_s20_later_act_start_count": _count(
            expert_s20, "later_act_battle_start_count"
        ),
        "expert_s100_later_act_start_count": _count(
            expert_s100, "later_act_battle_start_count"
        ),
        "expert_s20_act1_boss_delta_vs_stochastic_s20": expert_s20_boss_delta,
        "expert_s20_later_act_delta_vs_stochastic_s20": expert_s20_later_delta,
        "expert_s20_improves_act1_boss_reachability": (
            expert_s20_boss_delta is not None and expert_s20_boss_delta > 0
        ),
        "expert_s20_improves_later_act_reachability": (
            expert_s20_later_delta is not None and expert_s20_later_delta > 0
        ),
        "expert_s20_reachability_gate_met": (
            expert_s20_boss_delta is not None
            and expert_s20_later_delta is not None
            and expert_s20_boss_delta > 0
            and expert_s20_later_delta > 0
        ),
        "broad_training_allowed_any_arm": any(
            _nested_get(arm.arm.training_gate_report, "broad_training_allowed") is True
            for arm in arms
        ),
    }


def _search_simulations(search_budget: Mapping[str, Any]) -> int | None:
    value = search_budget.get("simulations")
    if isinstance(value, bool):
        return None
    return value if isinstance(value, int) else None


def _count(arm: ReachabilityArmReport | None, field_name: str) -> int | None:
    if arm is None:
        return None
    value = getattr(arm, field_name)
    return value if isinstance(value, int) else None


def _delta(
    left: ReachabilityArmReport | None,
    right: ReachabilityArmReport | None,
    field_name: str,
) -> int | None:
    left_value = _count(left, field_name)
    right_value = _count(right, field_name)
    if left_value is None or right_value is None:
        return None
    return left_value - right_value


def _nested_get(value: Mapping[str, Any], *keys: str) -> Any:
    current: Any = value
    for key in keys:
        if not isinstance(current, Mapping):
            return None
        current = current.get(key)
    return current


def _json_safe_mapping(values: Mapping[str, Any]) -> dict[str, Any]:
    return {str(key): _json_safe_value(value) for key, value in values.items()}


def _json_safe_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return _json_safe_mapping(value)
    if isinstance(value, (list, tuple)):
        return [_json_safe_value(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _append_problem_list(
    lines: list[str],
    title: str,
    problems: Sequence[str],
) -> None:
    lines.append(title + ":")
    prefix = title[: len(title) - len(title.lstrip(" "))]
    if problems:
        lines.extend(f"{prefix}  - {problem}" for problem in problems)
    else:
        lines.append(f"{prefix}  (none)")


def _yes_no(value: bool) -> str:
    return "yes" if value else "no"
