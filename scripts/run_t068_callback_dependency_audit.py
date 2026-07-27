#!/usr/bin/env python3
"""Record one T068 callback-dependency audit shard in the pinned WSL ABI."""

from __future__ import annotations

import argparse
from collections.abc import Mapping
import hashlib
import json
import math
from pathlib import Path
import re
import subprocess
from typing import Any

from sts_combat_rl.commands.model_guided_oracle_search import (
    build_torch_guidance_scorer_from_checkpoint,
)
from sts_combat_rl.commands.t062_battle_search_v2 import (
    run_t062_comparison_from_cohort_path,
    run_t062_input_preflight_from_paths,
)
from sts_combat_rl.sim.action_space import ActionSpaceConfig
from sts_combat_rl.sim.battle_search_v2 import BattleSearchV2Controller
from sts_combat_rl.sim.lightspeed import LightSpeedAdapter


EXPECTED_NATIVE_COMMIT = "3cb9ebecb87c38044b34aa0e013d42b222a04087"
EXPECTED_SOURCE_MANIFEST_SHA256 = (
    "2f4bd6710a152b080a2c6e4cfbaf509148ffb27d0139a9250f1a0ee19efd6631"
)
GUIDED_ARMS = ("prior_only", "value_only", "prior_value")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cohort", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--t061-retention-manifest", type=Path, required=True)
    parser.add_argument("--preflight-output", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--code-commit", required=True)
    parser.add_argument("--record-range", required=True)
    parser.add_argument("--shard-index", type=int, required=True)
    parser.add_argument("--shard-count", type=int, default=16)
    args = parser.parse_args()
    if not re.fullmatch(r"[0-9a-f]{40}", args.code_commit):
        raise SystemExit("T068 audit requires an exact 40-character code commit")
    if args.shard_count != 16 or args.shard_index not in range(16):
        raise SystemExit("T068 audit requires 16 explicit one-record shards")
    if args.record_range != f"{args.shard_index}:{args.shard_index + 1}":
        raise SystemExit("T068 shard range does not match its explicit shard index")
    _verify_code_commit(Path.cwd(), args.code_commit)
    _verify_source_manifest(Path("docs/sts_lightspeed_source_manifest.json"))
    preflight = run_t062_input_preflight_from_paths(
        output_path=args.preflight_output,
        t061_retention_manifest_path=args.t061_retention_manifest,
        t052_cohort_path=args.cohort,
        t043_checkpoint_path=args.checkpoint,
    )
    if not preflight["command_passed"]:
        raise SystemExit(
            "T068 input preflight failed: " + "; ".join(preflight["problems"])
        )
    scorer = build_torch_guidance_scorer_from_checkpoint(args.checkpoint)
    action_space = ActionSpaceConfig.initial_no_potions()
    arms = _build_arms(scorer, action_space)
    try:
        comparison = run_t062_comparison_from_cohort_path(
            adapter_factory=lambda: LightSpeedAdapter(seed=1, ascension=20),
            cohort_path=args.cohort,
            controller_arms=arms,
            action_space=action_space,
            max_battle_steps=200,
            # T062's existing runner owns the accepted comparison-family enum.
            # This trace is not a cost comparison, so retain its neutral nominal
            # family while T068 stamps the audit-specific stage schema separately.
            family="nominal",
            worker_count=1,
            shard_count=args.shard_count,
            record_range=args.record_range,
        )
    except BaseException as exc:
        _write_failure_output(args, stage="comparison", error=repr(exc))
        raise
    try:
        traces = {
            label: _extract_requests(comparison["arms"][label]) for label in GUIDED_ARMS
        }
        comparison_problems = _comparison_problems(comparison)
        cost_summaries = {
            label: _arm_cost_summary(comparison["arms"][label]) for label in GUIDED_ARMS
        }
    except BaseException as exc:
        _write_failure_output(
            args,
            stage="trace_extraction",
            error=repr(exc),
            comparison=comparison,
        )
        raise
    for label, requests in traces.items():
        if not requests:
            _write_failure_output(
                args,
                stage="trace_extraction",
                error=f"{label} produced no callback requests",
                comparison=comparison,
            )
            raise SystemExit(f"T068 {label} shard produced no callback requests")
        for ordinal, request in enumerate(requests):
            request["request_id"] = f"shard-{args.shard_index:02d}-{ordinal:06d}"
    output = {
        "schema_id": "t068-native-callback-dependency-shard-v1",
        "schema_version": 1,
        "task_id": "T068",
        "code_commit": args.code_commit,
        "native_commit": EXPECTED_NATIVE_COMMIT,
        "record_range": args.record_range,
        "shard_index": args.shard_index,
        "shard_count": args.shard_count,
        "worker_count": 1,
        "stage_worker_count": 16,
        "stage_classification": "one_record_component_of_16_worker_audit",
        "input_preflight": preflight,
        "arms": traces,
        "arm_cost_summaries": cost_summaries,
        "comparison_successful": comparison["successful"],
        "comparison_problems": comparison_problems,
        "command_passed": comparison["successful"],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if args.output.exists():
        raise SystemExit(f"T068 refuses to overwrite shard output: {args.output}")
    args.output.write_text(
        json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return 0 if output["command_passed"] else 1


def _build_arms(
    scorer: Any, action_space: ActionSpaceConfig
) -> list[tuple[str, BattleSearchV2Controller]]:
    """Build the exact T062 arm set; only guided arms enable T068 tracing."""

    return [
        (
            "baseline",
            BattleSearchV2Controller(
                simulations=1,
                scorer=scorer,
                ablation="baseline",
                action_space=action_space,
            ),
        ),
        *[
            (
                label,
                BattleSearchV2Controller(
                    simulations=1,
                    scorer=scorer,
                    ablation=label,  # type: ignore[arg-type]
                    action_space=action_space,
                    inference_cache_enabled=True,
                    callback_dependency_trace_enabled=True,
                ),
            )
            for label in GUIDED_ARMS
        ],
    ]


def _extract_requests(value: Any) -> list[dict[str, Any]]:
    requests: list[dict[str, Any]] = []
    if isinstance(value, Mapping):
        if value.get(
            "schema_id"
        ) == "t068-native-callback-request-trace-v1" and isinstance(
            value.get("requests"), list
        ):
            requests.extend(
                dict(item) for item in value["requests"] if isinstance(item, Mapping)
            )
        for child in value.values():
            requests.extend(_extract_requests(child))
    elif isinstance(value, list):
        for child in value:
            requests.extend(_extract_requests(child))
    return requests


def _comparison_problems(comparison: Mapping[str, Any]) -> list[str]:
    """Read the accepted T062 shard problem fields without inventing one."""

    problems = [
        str(problem)
        for problem in comparison.get("source_match_problems", [])
        if isinstance(problem, str)
    ]
    arms = comparison.get("arms", {})
    if not isinstance(arms, Mapping):
        return [*problems, "T062 arms mapping is missing"]
    for label, arm in arms.items():
        if not isinstance(arm, Mapping):
            problems.append(f"{label}: arm summary is malformed")
            continue
        for problem in arm.get("evaluation_problems", []):
            if isinstance(problem, str):
                problems.append(f"{label}: {problem}")
        for record in arm.get("records", []):
            if not isinstance(record, Mapping):
                continue
            for problem in record.get("problems", []):
                if isinstance(problem, str):
                    problems.append(f"{label}: {problem}")
    return problems


def _arm_cost_summary(arm: Mapping[str, Any]) -> dict[str, Any]:
    """Keep the required T068 component costs beside compact request traces."""

    fields = (
        "python_callback_total_ms",
        "checkpoint_feature_encoding_ms",
        "tensor_construction_ms",
        "policy_value_forward_pass_ms",
    )
    totals = {field: 0.0 for field in fields}
    model_call_count = 0
    outer_steps = 0
    record_wall_seconds = 0.0
    native_search_steps = 0
    search_wall_seconds = 0.0
    failures: list[str] = []
    records = arm.get("records", [])
    if not isinstance(records, list):
        raise ValueError("T068 arm records are missing")
    for record in records:
        if not isinstance(record, Mapping):
            raise ValueError("T068 arm record is malformed")
        telemetry = record.get("controller_compute_telemetry", {})
        cost = (
            telemetry.get("t067_cost_attribution", {})
            if isinstance(telemetry, Mapping)
            else {}
        )
        if not isinstance(cost, Mapping):
            raise ValueError("T068 guided arm lacks T067 cost telemetry")
        for field in fields:
            value = cost.get(field)
            if _finite_nonnegative(value):
                totals[field] += float(value)
            else:
                raise ValueError(f"T068 guided arm lacks finite nonnegative {field}")
        calls = cost.get("model_call_count")
        if not _nonnegative_integer(calls):
            raise ValueError(
                "T068 guided arm lacks nonnegative integer model_call_count"
            )
        model_call_count += int(calls)
        for field, target in (
            ("outer_simulator_steps", "outer"),
            ("wall_clock_seconds", "record_wall"),
        ):
            value = record.get(field)
            valid = (
                _nonnegative_integer(value)
                if target == "outer"
                else _finite_nonnegative(value)
            )
            if not valid:
                raise ValueError(f"T068 guided arm lacks finite nonnegative {field}")
            if target == "outer":
                outer_steps += int(value)
            else:
                record_wall_seconds += float(value)
        search_summary = telemetry.get("search_telemetry_summary", {})
        if not isinstance(search_summary, Mapping):
            raise ValueError("T068 guided arm lacks search telemetry summary")
        for field, target in (
            ("native_simulator_steps", "native_search"),
            ("wall_clock_time_s", "search_wall"),
        ):
            value = search_summary.get(field, {})
            total = value.get("total") if isinstance(value, Mapping) else None
            valid = (
                _nonnegative_integer(total)
                if target == "native_search"
                else _finite_nonnegative(total)
            )
            if not valid:
                raise ValueError(
                    f"T068 guided arm lacks finite nonnegative search {field}.total"
                )
            if target == "native_search":
                native_search_steps += int(total)
            else:
                search_wall_seconds += float(total)
        failures.extend(
            str(problem)
            for problem in record.get("problems", [])
            if isinstance(problem, str)
        )
    return {
        "record_count": len(records),
        "component_cost_ms": totals,
        "model_call_count": model_call_count,
        "outer_simulator_steps": outer_steps,
        "record_wall_clock_seconds": record_wall_seconds,
        "native_search_simulator_steps": native_search_steps,
        "search_wall_clock_seconds": search_wall_seconds,
        "failures": failures,
    }


def _finite_nonnegative(value: Any) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
        and value >= 0
    )


def _nonnegative_integer(value: Any) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
        and value >= 0
        and float(value).is_integer()
    )


def _write_failure_output(
    args: argparse.Namespace,
    *,
    stage: str,
    error: str,
    comparison: Mapping[str, Any] | None = None,
) -> None:
    """Persist a fresh fail-closed shard diagnostic before surfacing an error."""

    if args.output.exists():
        return
    payload: dict[str, Any] = {
        "schema_id": "t068-native-callback-dependency-shard-v1",
        "schema_version": 1,
        "task_id": "T068",
        "code_commit": args.code_commit,
        "record_range": args.record_range,
        "shard_index": args.shard_index,
        "shard_count": args.shard_count,
        "failure_stage": stage,
        "failure": error,
        "command_passed": False,
    }
    if comparison is not None:
        payload["comparison_successful"] = comparison.get("successful")
        payload["comparison_problems"] = comparison.get("source_match_problems")
        payload["observed_arm_record_counts"] = {
            label: len(arm.get("records", []))
            for label, arm in comparison.get("arms", {}).items()
            if isinstance(arm, Mapping)
        }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def _verify_code_commit(repo_root: Path, code_commit: str) -> None:
    actual = _git_output(repo_root, "rev-parse", "HEAD")
    if actual != code_commit:
        raise SystemExit(
            "T068 source checkout HEAD differs: "
            f"{actual} != {code_commit}; {_git_diagnostic(repo_root)}"
        )
    status = _git_output(repo_root, "status", "--porcelain", "--untracked-files=no")
    if status is None or status:
        raise SystemExit(
            "T068 source checkout has tracked or staged changes; "
            + _git_diagnostic(repo_root)
        )


def _git_output(repo_root: Path, *arguments: str) -> str | None:
    safe_directory = f"safe.directory={repo_root}"
    commands = [
        [
            "git",
            "-c",
            safe_directory,
            "-C",
            str(repo_root),
            "-c",
            "core.autocrlf=true",
            *arguments,
        ]
    ]
    dot_git = repo_root / ".git"
    if dot_git.is_file():
        marker = dot_git.read_text(encoding="utf-8").strip()
        if marker.startswith("gitdir:"):
            git_dir = marker.removeprefix("gitdir:").strip()
            match = re.fullmatch(r"([A-Za-z]):[/\\](.*)", git_dir)
            if match is not None:
                git_dir = (
                    f"/mnt/{match.group(1).lower()}/"
                    f"{match.group(2).replace(chr(92), '/')}"
                )
            commands.append(
                [
                    "git",
                    "-c",
                    safe_directory,
                    "--git-dir",
                    git_dir,
                    "--work-tree",
                    str(repo_root),
                    "-c",
                    "core.autocrlf=true",
                    *arguments,
                ]
            )
    for command in commands:
        result = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    return None


def _git_diagnostic(repo_root: Path) -> str:
    result = subprocess.run(
        [
            "git",
            "-c",
            f"safe.directory={repo_root}",
            "-C",
            str(repo_root),
            "rev-parse",
            "HEAD",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    message = (result.stderr or result.stdout).strip().replace("\n", " ")
    return message or f"git exit={result.returncode} without diagnostic"


def _verify_source_manifest(path: Path) -> None:
    if hashlib.sha256(path.read_bytes()).hexdigest() != EXPECTED_SOURCE_MANIFEST_SHA256:
        raise SystemExit("T068 source manifest does not match accepted T067 ABI")
    raw = json.loads(path.read_text(encoding="utf-8"))
    if raw.get("integration", {}).get("commit") != EXPECTED_NATIVE_COMMIT:
        raise SystemExit("T068 native source manifest identity is wrong")


if __name__ == "__main__":
    raise SystemExit(main())
