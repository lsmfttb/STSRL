#!/usr/bin/env python3
"""Run one paired T069 unprojected/projected 0:16 WSL shard."""

from __future__ import annotations

import argparse
from collections.abc import Mapping
import hashlib
import json
from pathlib import Path
import re
from typing import Any

from sts_combat_rl.commands.model_guided_oracle_search import (
    build_torch_guidance_scorer_from_checkpoint,
)
from sts_combat_rl.commands.t062_battle_search_v2 import (
    run_t062_comparison_from_cohort_path,
    run_t062_input_preflight_from_paths,
    write_t062_comparison_report,
)
from sts_combat_rl.commands.t068_checkout import verify_exact_git_checkout
from sts_combat_rl.sim.action_space import ActionSpaceConfig
from sts_combat_rl.sim.battle_search_v2 import BattleSearchV2Controller
from sts_combat_rl.sim.lightspeed import LightSpeedAdapter
from sts_combat_rl.sim.t069_feature_identity import T069FeatureIdentityRecorder


NATIVE_COMMIT = "3cb9ebecb87c38044b34aa0e013d42b222a04087"
SOURCE_MANIFEST_SHA256 = (
    "2f4bd6710a152b080a2c6e4cfbaf509148ffb27d0139a9250f1a0ee19efd6631"
)
T068_MANIFEST_SHA256 = (
    "bf974134343cea06e9f58e227f4752002ee3cebc14902206991f9fe81752c678"
)
GUIDED_ARMS = ("prior_only", "value_only", "prior_value")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cohort", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--t061-retention-manifest", type=Path, required=True)
    parser.add_argument("--t068-retention-manifest", type=Path, required=True)
    parser.add_argument("--preflight-output", type=Path, required=True)
    parser.add_argument("--unprojected-output", type=Path, required=True)
    parser.add_argument("--projected-output", type=Path, required=True)
    parser.add_argument("--identity-output", type=Path, required=True)
    parser.add_argument("--code-commit", required=True)
    parser.add_argument("--record-range", required=True)
    parser.add_argument("--shard-index", type=int, required=True)
    parser.add_argument("--shard-count", type=int, default=16)
    parser.add_argument("--baseline-budget", type=int, default=100)
    parser.add_argument("--guided-budget", type=int, default=1)
    parser.add_argument("--family", default="wall_clock_normalized")
    args = parser.parse_args()

    if not re.fullmatch(r"[0-9a-f]{40}", args.code_commit):
        raise SystemExit("T069 shard requires an exact code commit")
    if args.shard_count != 16 or args.shard_index not in range(16):
        raise SystemExit("T069 requires 16 explicit one-record shards")
    if args.record_range != f"{args.shard_index}:{args.shard_index + 1}":
        raise SystemExit("T069 record range does not match shard index")
    if args.baseline_budget <= 0 or args.guided_budget <= 0:
        raise SystemExit("T069 budgets must be positive")
    outputs = (
        args.preflight_output,
        args.unprojected_output,
        args.projected_output,
        args.identity_output,
    )
    if any(path.exists() for path in outputs):
        raise SystemExit("T069 shard refuses to overwrite output")
    try:
        verify_exact_git_checkout(Path.cwd(), args.code_commit)
    except ValueError as exc:
        raise SystemExit(f"T069 shard {exc}") from exc
    _verify_sha256(
        Path("docs/sts_lightspeed_source_manifest.json"),
        SOURCE_MANIFEST_SHA256,
    )
    source_manifest = json.loads(
        Path("docs/sts_lightspeed_source_manifest.json").read_text(encoding="utf-8")
    )
    if source_manifest.get("integration", {}).get("commit") != NATIVE_COMMIT:
        raise SystemExit("T069 source manifest native identity changed")
    _verify_sha256(args.t068_retention_manifest, T068_MANIFEST_SHA256)

    preflight = run_t062_input_preflight_from_paths(
        output_path=args.preflight_output,
        t061_retention_manifest_path=args.t061_retention_manifest,
        t052_cohort_path=args.cohort,
        t043_checkpoint_path=args.checkpoint,
    )
    if preflight.get("command_passed") is not True:
        raise SystemExit("T069 input preflight failed")

    unprojected, unprojected_recorders = _run(
        args,
        projected=False,
    )
    projected, projected_recorders = _run(
        args,
        projected=True,
    )
    write_t062_comparison_report(args.unprojected_output, unprojected)
    write_t062_comparison_report(args.projected_output, projected)

    problems: list[str] = []
    unprojected_records = _finish_identity_records(
        unprojected,
        unprojected_recorders,
        problems,
    )
    projected_records = _finish_identity_records(
        projected,
        projected_recorders,
        problems,
    )
    for record in (*unprojected_records, *projected_records):
        record["cohort_index"] = args.shard_index
    payload = {
        "schema_id": "t069-projection-paired-shard-v1",
        "schema_version": 1,
        "task_id": "T069",
        "code_commit": args.code_commit,
        "native_commit": NATIVE_COMMIT,
        "record_range": args.record_range,
        "shard_index": args.shard_index,
        "shard_count": 16,
        "worker_count": 1,
        "stage_worker_count": 16,
        "baseline_budget": args.baseline_budget,
        "guided_budget": args.guided_budget,
        "family": args.family,
        "unprojected_identity_records": unprojected_records,
        "projected_identity_records": projected_records,
        "problems": problems,
        "command_passed": (
            unprojected.get("successful") is True
            and projected.get("successful") is True
            and not problems
        ),
    }
    args.identity_output.parent.mkdir(parents=True, exist_ok=True)
    args.identity_output.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return 0 if payload["command_passed"] else 1


def _run(
    args: argparse.Namespace,
    *,
    projected: bool,
) -> tuple[dict[str, Any], dict[str, T069FeatureIdentityRecorder]]:
    action_space = ActionSpaceConfig.initial_no_potions()
    recorders: dict[str, T069FeatureIdentityRecorder] = {}
    arms: list[tuple[str, BattleSearchV2Controller]] = []
    for arm in ("baseline", *GUIDED_ARMS):
        scorer = build_torch_guidance_scorer_from_checkpoint(args.checkpoint)
        recorder = T069FeatureIdentityRecorder(arm=arm, projected=projected)
        if arm != "baseline":
            scorer.set_t069_input_observer(recorder)
            recorders[arm] = recorder
        arms.append(
            (
                arm,
                BattleSearchV2Controller(
                    simulations=(
                        args.baseline_budget
                        if arm == "baseline"
                        else args.guided_budget
                    ),
                    scorer=scorer,
                    ablation=arm,  # type: ignore[arg-type]
                    action_space=action_space,
                    inference_cache_enabled=arm != "baseline",
                    inference_cache_capacity=32768,
                    public_context_projection_enabled=projected and arm != "baseline",
                    callback_dependency_trace_enabled=arm != "baseline",
                    feature_identity_trace_enabled=arm != "baseline",
                ),
            )
        )
    report = run_t062_comparison_from_cohort_path(
        adapter_factory=lambda: LightSpeedAdapter(seed=1, ascension=20),
        cohort_path=args.cohort,
        controller_arms=arms,
        action_space=action_space,
        max_battle_steps=200,
        family=args.family,
        worker_count=16,
        shard_count=16,
        record_range=args.record_range,
    )
    report["t069_projection_mode"] = "projected" if projected else "unprojected"
    report["t069_code_commit"] = args.code_commit
    report["t069_native_commit"] = NATIVE_COMMIT
    return report, recorders


def _finish_identity_records(
    comparison: Mapping[str, Any],
    recorders: Mapping[str, T069FeatureIdentityRecorder],
    problems: list[str],
) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    arms = comparison.get("arms", {})
    for arm in GUIDED_ARMS:
        recorder = recorders[arm]
        problems.extend(f"{arm}: {problem}" for problem in recorder.problems)
        requests = _extract_trace_requests(arms.get(arm))
        if len(requests) != len(recorder.records):
            problems.append(
                f"{arm}: trace/feature request count differs "
                f"{len(requests)} != {len(recorder.records)}"
            )
            continue
        for record, request in zip(recorder.records, requests, strict=True):
            if request.get("response_count") != 1:
                problems.append(f"{arm}: callback lacks exactly one response")
            record["callback_kind"] = request.get("callback_kind")
            record["native_public_input_identity"] = request.get(
                "public_input_identity"
            )
            record["native_request_sequence"] = request.get("request_sequence")
            output.append(record)
    return output


def _extract_trace_requests(value: Any) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    if isinstance(value, Mapping):
        if value.get(
            "schema_id"
        ) == "t068-native-callback-request-trace-v1" and isinstance(
            value.get("requests"), list
        ):
            found.extend(
                dict(item) for item in value["requests"] if isinstance(item, Mapping)
            )
        for child in value.values():
            found.extend(_extract_trace_requests(child))
    elif isinstance(value, list):
        for child in value:
            found.extend(_extract_trace_requests(child))
    return found


def _verify_sha256(path: Path, expected: str) -> None:
    if not path.is_file():
        raise SystemExit(f"T069 missing input: {path}")
    if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
        raise SystemExit(f"T069 input hash changed: {path}")


if __name__ == "__main__":
    raise SystemExit(main())
