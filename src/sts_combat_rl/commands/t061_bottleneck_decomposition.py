"""CLI helpers for T061 offline bottleneck decomposition reports."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from sts_combat_rl.sim.t061_bottleneck_decomposition import (
    build_t061_budget_curve_report,
    build_t061_bottleneck_report,
    build_t061_factorial_report,
    load_json_object,
)


def run_t061_bottleneck_decomposition_from_paths(
    *,
    budget_curve_output: Path,
    factorial_output: Path,
    bottleneck_output: Path,
    budget_arm_specs: list[list[str]],
    factorial_arm_specs: list[list[str]],
    expected_run_count: int = 256,
    bootstrap_resamples: int = 2000,
) -> dict[str, Any]:
    """Load six factorial and three budget manifests and write all reports."""

    budget_arms = [
        (values[0], load_json_object(values[1]))
        for values in budget_arm_specs
        if len(values) == 2
    ]
    if len(budget_arms) != len(budget_arm_specs):
        raise ValueError("T061 budget arm specs must contain LABEL and JSON_PATH")
    factorial_arms = [
        (values[0], values[1], load_json_object(values[2]))
        for values in factorial_arm_specs
        if len(values) == 3
    ]
    if len(factorial_arms) != len(factorial_arm_specs):
        raise ValueError(
            "T061 factorial arm specs must contain DRIVER, BUDGET, and JSON_PATH"
        )
    budget_report = build_t061_budget_curve_report(budget_arms)
    factorial_report = build_t061_factorial_report(
        factorial_arms,
        expected_run_count=expected_run_count,
        bootstrap_resamples=bootstrap_resamples,
    )
    report = build_t061_bottleneck_report(budget_report, factorial_report)
    for path, payload in (
        (budget_curve_output, budget_report),
        (factorial_output, factorial_report),
        (bottleneck_output, report),
    ):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    return report


def format_t061_bottleneck_report(report: dict[str, Any]) -> str:
    decision = report.get("decision", {})
    factorial = report.get("complete_run_factorial", {})
    return "\n".join(
        (
            "T061 A20 reachability bottleneck decomposition",
            f"command passed: {'yes' if report.get('command_passed') else 'no'}",
            f"budget curve runs: {report.get('restored_battle_budget_curve', {}).get('cohort', {}).get('record_count', 0)}",
            f"factorial runs: {factorial.get('total_run_count', 0)}",
            f"recommended next task: {decision.get('recommended_next_task', '(missing)')}",
            f"rationale: {decision.get('rationale', '(missing)')}",
        )
    )
