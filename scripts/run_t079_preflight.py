#!/usr/bin/env python3
"""Run the real native T079 parity and restore-fidelity preflight.

This gate deliberately exercises three independent native calls on the frozen
sixteen-record cohort.  A fake adapter is not sufficient evidence: the
telemetry-off, T070 geometry, and T079 state-utilization controllers each
restore and play the records through the configured ``sts_lightspeed`` module.
"""

from __future__ import annotations

import argparse
import importlib
import json
import platform
import subprocess
import sys
import time
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from sts_combat_rl.sim.action_space import ActionSpaceConfig
from sts_combat_rl.sim.battle_search_v2 import BattleSearchV2Controller
from sts_combat_rl.sim.fixed_battle_evaluation import evaluate_fixed_cohort
from sts_combat_rl.sim.fixed_evaluation_set import load_fixed_cohort_jsonl
from sts_combat_rl.sim.lightspeed import LightSpeedAdapter
from sts_combat_rl.sim.lightspeed_source import lightspeed_source_identity_dict
from sts_combat_rl.sim.search_telemetry import iter_search_decision_telemetry_dicts
from sts_combat_rl.sim.t079_state_utilization import sha256_file, write_json

T079_EXPECTED_NATIVE_COMMIT = "1555348535d66e3035aac80933a60949d4bd850f"
T079_RECORD_COUNT = 16
T079_PREFLIGHT_SCHEMA_ID = "t079-preflight-v1"

T070_GEOMETRY_FIELDS = (
    "native_geometry",
    "root_actions",
    "root_visits",
    "root_legal_action_count",
    "selected_action_identity",
    "selected_legal_action_index",
    "native_simulator_steps",
    "model_calls",
)
SEARCH_PARITY_FIELDS = (
    "selected_action_identity",
    "selected_legal_action_index",
    "selected_visits",
    "selected_mean_value",
    "selection_rule",
    "root_visits",
    "root_actions",
    "soft_visit_target",
    "soft_visit_denominator",
    "root_row_count",
    "search_edge_count",
    "unsearched_legal_action_count",
    "unmapped_search_edge_count",
    "native_simulator_steps",
    "model_calls",
    "legal_action_count",
    "eligible_action_count",
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cohort", type=Path, required=True)
    parser.add_argument("--subset-manifest", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--native-build",
        type=Path,
        required=True,
        help="build directory containing the exact active sts_lightspeed module",
    )
    parser.add_argument("--max-battle-steps", type=int, default=200)
    parser.add_argument("--sim-seed", type=int, default=1)
    args = parser.parse_args()

    args.output.parent.mkdir(parents=True, exist_ok=True)
    artifact: dict[str, Any] = {
        "schema_id": T079_PREFLIGHT_SCHEMA_ID,
        "task_id": "T079",
        "passed": False,
        "parity": {"passed": False},
        "t078_restore_fidelity": {"passed": False},
    }
    try:
        cohort, source_identity = _validate_inputs(args)
        artifact.update(
            {
                "code_identity": _code_identity(),
                "native_runtime_identity": _native_runtime_identity(args.native_build),
                "native_source_identity": source_identity,
                "inputs": {
                    "subset_manifest": {
                        "path": str(args.subset_manifest.resolve()),
                        "sha256": sha256_file(args.subset_manifest),
                    },
                    "subset_cohort": {
                        "path": str(args.cohort.resolve()),
                        "sha256": sha256_file(args.cohort),
                    },
                    "checkpoint": {
                        "path": str(args.checkpoint.resolve()),
                        "sha256": sha256_file(args.checkpoint),
                    },
                    "cohort_identity": cohort.identity,
                    "record_indices": [r.cohort_index for r in cohort.records],
                },
                "configuration": {
                    "sim_seed": args.sim_seed,
                    "ascension": 20,
                    "max_battle_steps": args.max_battle_steps,
                    "simulations": 100,
                    "ablation": "prior_value",
                    "root_selection_rule": "highest_mean",
                    "action_space": ActionSpaceConfig.initial_no_potions().to_dict(),
                    "inference_cache_enabled": True,
                    "public_context_projection_enabled": True,
                },
            }
        )
        _require_active_native_identity(source_identity)
        started = time.monotonic()
        reports = _run_real_modes(args, cohort, source_identity)
        artifact["wall_clock_seconds"] = time.monotonic() - started
        artifact["real_mode_diagnostics"] = {
            name: [_result_diagnostic(result) for result in report.battle_results]
            for name, report in reports.items()
        }
        artifact["t078_restore_fidelity"] = _restore_fidelity_report(
            cohort, reports["telemetry_off"]
        )
        artifact["parity"] = _parity_report(reports)
        if not artifact["t078_restore_fidelity"]["passed"]:
            raise RuntimeError("T079 preflight T078 restore-fidelity check failed")
        if not artifact["parity"]["passed"]:
            raise RuntimeError("T079 native deterministic parity check failed")
        artifact["passed"] = True
    except Exception as exc:  # noqa: BLE001
        artifact["failure"] = f"{type(exc).__name__}: {exc}"
        write_json(args.output, artifact)
        print(json.dumps(artifact, indent=2, sort_keys=True))
        return 1

    write_json(args.output, artifact)
    print(json.dumps(artifact, indent=2, sort_keys=True))
    return 0


def _validate_inputs(args: argparse.Namespace) -> tuple[Any, dict[str, Any]]:
    expected = {
        "subset_manifest": (
            args.subset_manifest,
            "ec9201b87abb9921decdc337689b7a08e84899d4f01fd8b04172d21c9db8207c",
        ),
        "subset_cohort": (
            args.cohort,
            "2d21a79dcbb393e4691e5aaf15f66c87fa20ba3e274bfa19baa30693cb2f029d",
        ),
        "checkpoint": (
            args.checkpoint,
            "a2317354b24f93ff48f0408ba3fdc92056701ef16e9b3a1b8b17aa1cce2a56e4",
        ),
    }
    for label, (path, digest) in expected.items():
        actual = sha256_file(path)
        if actual != digest:
            raise RuntimeError(f"frozen {label} hash mismatch: {actual}")
    with args.cohort.open("r", encoding="utf-8") as stream:
        cohort = load_fixed_cohort_jsonl(stream)
    if len(cohort.records) != T079_RECORD_COUNT:
        raise RuntimeError("T079 preflight requires exactly 16 cohort records")
    if [r.cohort_index for r in cohort.records] != list(range(T079_RECORD_COUNT)):
        raise RuntimeError("T079 cohort indices are not the exact ordered 16 records")
    return cohort, lightspeed_source_identity_dict()


def _require_active_native_identity(identity: Mapping[str, Any]) -> None:
    if identity.get("integration_branch") != "stsrl/main":
        raise RuntimeError("native input branch is not active stsrl/main")
    if identity.get("integration_ref") != "refs/heads/stsrl/main":
        raise RuntimeError("native input ref is not refs/heads/stsrl/main")
    if identity.get("integration_commit") != T079_EXPECTED_NATIVE_COMMIT:
        raise RuntimeError(
            "native active commit mismatch: "
            f"{identity.get('integration_commit')} != {T079_EXPECTED_NATIVE_COMMIT}"
        )
    required = "native_battle_search_v2_state_utilization"
    if required not in identity.get("native_capabilities", []):
        raise RuntimeError(f"native capability missing: {required}")


def _code_identity() -> dict[str, Any]:
    root = Path(__file__).resolve().parents[1]
    head = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    status = subprocess.run(
        ["git", "-C", str(root), "status", "--porcelain"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()
    return {
        "repository": "STSRL",
        "head": head,
        "worktree_clean": not status,
        "status_lines": status,
        "script": str(Path(__file__).resolve()),
        "script_sha256": sha256_file(Path(__file__)),
    }


def _native_runtime_identity(native_build: Path) -> dict[str, Any]:
    native_build = native_build.resolve()
    if not native_build.is_dir():
        raise RuntimeError(f"native build directory is unavailable: {native_build}")
    candidates = sorted(native_build.glob("slaythespire*.so"))
    if len(candidates) != 1:
        raise RuntimeError(
            "native build must contain exactly one slaythespire*.so module: "
            f"{[str(path) for path in candidates]}"
        )
    if str(native_build) not in sys.path:
        sys.path.insert(0, str(native_build))
    module = importlib.import_module("slaythespire")
    module_path = Path(str(module.__file__)).resolve()
    if module_path != candidates[0].resolve():
        raise RuntimeError(
            f"imported native module is not from --native-build: {module_path}"
        )
    return {
        "python_executable": sys.executable,
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "module": "slaythespire",
        "native_build_directory": str(native_build),
        "module_file": str(module_path),
        "module_sha256": sha256_file(module_path),
        "step_simulator": getattr(module, "StepSimulator", None).__name__,
    }


def _run_real_modes(
    args: argparse.Namespace, cohort: Any, identity: Mapping[str, Any]
) -> dict[str, Any]:
    action_space = ActionSpaceConfig.initial_no_potions()

    def adapter_factory() -> LightSpeedAdapter:
        return LightSpeedAdapter(seed=args.sim_seed, ascension=20)

    def run_mode(name: str, *, geometry: bool, state: bool) -> Any:
        from sts_combat_rl.sim.torch_policy_value import TorchPolicyValueGuidanceScorer

        scorer = TorchPolicyValueGuidanceScorer.from_checkpoint_path(args.checkpoint)
        controller = BattleSearchV2Controller(
            simulations=100,
            scorer=scorer,
            ablation="prior_value",
            root_selection_rule="highest_mean",
            action_space=action_space,
            inference_cache_enabled=True,
            public_context_projection_enabled=True,
            tree_geometry_enabled=geometry,
            state_utilization_enabled=state,
            native_source_identity=identity,
        )
        report = evaluate_fixed_cohort(
            adapter_factory=adapter_factory,
            cohort_records=cohort.records,
            controller=controller,
            cohort_identity=cohort.identity,
            source_pool_format_version=cohort.source_pool_format_version,
            selection_config=cohort.selection_config.to_dict(),
            action_space=action_space,
            max_battle_steps=args.max_battle_steps,
        )
        if len(report.battle_results) != T079_RECORD_COUNT:
            raise RuntimeError(f"{name} returned the wrong record count")
        return report

    return {
        "telemetry_off": run_mode("telemetry_off", geometry=False, state=False),
        "t070_geometry": run_mode("t070_geometry", geometry=True, state=False),
        "t079_state_utilization": run_mode(
            "t079_state_utilization", geometry=False, state=True
        ),
    }


def _restore_fidelity_report(cohort: Any, report: Any) -> dict[str, Any]:
    rows = []
    for result in report.battle_results:
        restore_problem = [
            problem
            for problem in result.problems
            if "restore" in problem.lower() or "fingerprint" in problem.lower()
        ]
        rows.append(
            {
                "record_index": result.cohort_index,
                "restoration_method": result.restoration_method,
                "restore_problems": restore_problem,
                "fingerprint_checked_by_fixed_evaluation": True,
            }
        )
    passed = (
        len(rows) == T079_RECORD_COUNT
        and all(row["restoration_method"] != "failed" for row in rows)
        and all(not row["restore_problems"] for row in rows)
    )
    return {
        "kind": "T078_exact_fixed_cohort_restore_boundary",
        "cohort_identity": cohort.identity,
        "record_count": len(rows),
        "passed": passed,
        "records": rows,
    }


def _parity_report(reports: Mapping[str, Any]) -> dict[str, Any]:
    off = reports["telemetry_off"]
    geometry = reports["t070_geometry"]
    state = reports["t079_state_utilization"]
    rows: list[dict[str, Any]] = []
    for index in range(T079_RECORD_COUNT):
        off_result = off.battle_results[index]
        geometry_result = geometry.battle_results[index]
        state_result = state.battle_results[index]
        mismatches: list[str] = []
        off_search, off_search_problem = _safe_search_rows(off_result, "telemetry_off")
        state_search, state_search_problem = _safe_search_rows(
            state_result, "state_utilization"
        )
        if off_search_problem is not None:
            mismatches.append(off_search_problem)
        if state_search_problem is not None:
            mismatches.append(state_search_problem)
        if (
            off_search_problem is None
            and state_search_problem is None
            and off_search != state_search
        ):
            mismatches.append("selected action/root stats/search status")
        off_eval = _evaluation_signature(off_result)
        state_eval = _evaluation_signature(state_result)
        if off_eval != state_eval:
            mismatches.append("terminal/evaluation/simulator steps")
        off_callbacks, off_callback_problem = _safe_callback_signature(
            off_result, "telemetry_off"
        )
        state_callbacks, state_callback_problem = _safe_callback_signature(
            state_result, "state_utilization"
        )
        if off_callback_problem is not None:
            mismatches.append(off_callback_problem)
        if state_callback_problem is not None:
            mismatches.append(state_callback_problem)
        if (
            off_callback_problem is None
            and state_callback_problem is None
            and off_callbacks != state_callbacks
        ):
            mismatches.append("policy/value callback counts")
        geometry_rows, geometry_problem = _safe_geometry_rows(
            geometry_result, "t070_geometry"
        )
        state_geometry_rows, state_geometry_problem = _safe_state_geometry_rows(
            state_result, "state_utilization"
        )
        if geometry_problem is not None:
            mismatches.append(geometry_problem)
        if state_geometry_problem is not None:
            mismatches.append(state_geometry_problem)
        if (
            geometry_problem is None
            and state_geometry_problem is None
            and geometry_rows != state_geometry_rows
        ):
            mismatches.append("T070 geometry")
        rows.append(
            {
                "record_index": index,
                "passed": not mismatches,
                "mismatches": mismatches,
                "telemetry_off": {
                    "search": off_search,
                    "evaluation": off_eval,
                    "callbacks": off_callbacks,
                },
                "state_utilization_on": {
                    "search": state_search,
                    "evaluation": state_eval,
                    "callbacks": state_callbacks,
                },
                "t070_geometry_matches_state_on": not ("T070 geometry" in mismatches),
            }
        )
    return {
        "kind": "real_native_deterministic_telemetry_off_vs_state_utilization_on",
        "record_count": len(rows),
        "passed": len(rows) == T079_RECORD_COUNT and all(row["passed"] for row in rows),
        "compared": [
            "selected action",
            "root stats/evaluation",
            "T070 geometry",
            "policy/value callback counts",
            "terminal/search status",
            "simulator steps",
        ],
        "records": rows,
    }


def _result_diagnostic(result: Any) -> dict[str, Any]:
    """Retain the failure boundary when a real result has no telemetry.

    A missing telemetry mapping is not a valid parity result and must never be
    converted into a pass by this diagnostic path.  Keeping the result shape
    and fixed-evaluation problems in the artifact makes native fail-closed
    identity failures actionable instead of hiding them behind a generic
    extraction exception.
    """

    telemetry = result.controller_compute_telemetry
    return {
        "record_index": result.cohort_index,
        "restoration_method": result.restoration_method,
        "termination_status": result.termination_status,
        "decision_count": result.decision_count,
        "simulator_step_count": result.simulator_step_count,
        "problems": list(result.problems),
        "controller_telemetry_type": type(telemetry).__name__,
        "controller_telemetry_present": telemetry is not None,
        "controller_telemetry_keys": (
            sorted(telemetry) if isinstance(telemetry, Mapping) else []
        ),
    }


def _safe_search_rows(
    result: Any, mode: str
) -> tuple[list[dict[str, Any]], str | None]:
    try:
        return _search_rows(result), None
    except (TypeError, RuntimeError, ValueError) as exc:
        return (
            [],
            f"{mode} record {result.cohort_index}: search telemetry invalid: {exc}",
        )


def _safe_callback_signature(
    result: Any, mode: str
) -> tuple[dict[str, Any], str | None]:
    try:
        return _callback_signature(result), None
    except (TypeError, RuntimeError, ValueError) as exc:
        return (
            {},
            f"{mode} record {result.cohort_index}: callback telemetry invalid: {exc}",
        )


def _safe_geometry_rows(
    result: Any, mode: str
) -> tuple[list[dict[str, Any]], str | None]:
    try:
        return _geometry_rows(result), None
    except (TypeError, RuntimeError, ValueError) as exc:
        return (
            [],
            f"{mode} record {result.cohort_index}: geometry telemetry invalid: {exc}",
        )


def _safe_state_geometry_rows(
    result: Any, mode: str
) -> tuple[list[dict[str, Any]], str | None]:
    try:
        return _state_geometry_rows(result), None
    except (TypeError, RuntimeError, ValueError) as exc:
        return (
            [],
            f"{mode} record {result.cohort_index}: geometry telemetry invalid: {exc}",
        )


def _search_rows(result: Any) -> list[dict[str, Any]]:
    telemetry = result.controller_compute_telemetry
    if not isinstance(telemetry, Mapping):
        raise TypeError("real parity result has no controller telemetry")
    search = iter_search_decision_telemetry_dicts(telemetry)
    reports = _selected_search_reports(telemetry)
    if len(search) != result.decision_count or len(reports) != result.decision_count:
        raise RuntimeError(
            "real parity search telemetry count does not match decisions"
        )
    output = []
    for telemetry_row, report in zip(search, reports):
        row = {
            key: telemetry_row.get(key)
            for key in SEARCH_PARITY_FIELDS
            if key != "root_actions"
        }
        row["root_actions"] = report.get("root_actions")
        row["selected_action_identity"] = report.get("selected_action_identity")
        output.append(row)
    return output


def _selected_search_reports(telemetry: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    found: list[Mapping[str, Any]] = []

    def visit(value: Any) -> None:
        if isinstance(value, Mapping):
            if "root_actions" in value and "selected_action_identity" in value:
                found.append(value)
                return
            for nested in value.values():
                visit(nested)
        elif isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
            for nested in value:
                visit(nested)

    visit(telemetry.get("oracle_search_decision_reports"))
    return found


def _evaluation_signature(result: Any) -> dict[str, Any]:
    return {
        "restoration_method": result.restoration_method,
        "termination_status": result.termination_status,
        "terminal_absolute_hp": result.terminal_absolute_hp,
        "hp_loss": result.hp_loss,
        "decision_count": result.decision_count,
        "simulator_step_count": result.simulator_step_count,
        "structured_battle_outcome_status": result.structured_battle_outcome_status,
        "structured_battle_outcome": result.structured_battle_outcome,
        "problems": result.problems,
    }


def _callback_signature(result: Any) -> dict[str, Any]:
    telemetry = result.controller_compute_telemetry
    if not isinstance(telemetry, Mapping):
        raise TypeError("real parity result has no callback telemetry")
    costs = telemetry.get("t067_cost_attribution")
    if not isinstance(costs, Mapping):
        raise TypeError("real parity result has no T067 callback attribution")
    return {
        key: costs.get(key)
        for key in ("policy_callback_count", "value_callback_count", "model_call_count")
    }


def _geometry_rows(result: Any) -> list[dict[str, Any]]:
    telemetry = result.controller_compute_telemetry
    if not isinstance(telemetry, Mapping):
        raise TypeError("T070 geometry result has no telemetry")
    rows = _find_records(telemetry.get("t070_tree_geometry_records"))
    return [{key: row.get(key) for key in T070_GEOMETRY_FIELDS} for row in rows]


def _state_geometry_rows(result: Any) -> list[dict[str, Any]]:
    telemetry = result.controller_compute_telemetry
    if not isinstance(telemetry, Mapping):
        raise TypeError("T079 state result has no telemetry")
    rows = _find_records(telemetry.get("t079_state_utilization_records"))
    output = []
    for row in rows:
        native_geometry = row.get("native_geometry")
        output.append(
            {
                "native_geometry": native_geometry,
                "root_actions": row.get("root_actions"),
                "root_visits": row.get("root_visits"),
                "root_legal_action_count": row.get("root_legal_action_count"),
                "selected_action_identity": row.get("selected_action_identity"),
                "selected_legal_action_index": row.get("selected_legal_action_index"),
                "native_simulator_steps": row.get("native_simulator_steps"),
                "model_calls": row.get("model_calls"),
            }
        )
    # T079 stores selected index in the native geometry payload; retain the
    # exact geometry dict as the comparison authority when present.
    return output


def _find_records(value: Any) -> list[Mapping[str, Any]]:
    found: list[Mapping[str, Any]] = []

    def visit(item: Any) -> None:
        if isinstance(item, Mapping):
            if "decision_step_index" in item and (
                "native_geometry" in item or "native_state_utilization" in item
            ):
                found.append(item)
                return
            for nested in item.values():
                visit(nested)
        elif isinstance(item, Sequence) and not isinstance(item, (str, bytes)):
            for nested in item:
                visit(nested)

    visit(value)
    return found


if __name__ == "__main__":
    sys.exit(main())
