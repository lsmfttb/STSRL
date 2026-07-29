#!/usr/bin/env python3
"""Run one projected T069 cost-calibration shard at explicit arm budgets."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
import re

from sts_combat_rl.commands.model_guided_oracle_search import (
    build_torch_guidance_scorer_from_checkpoint,
)
from sts_combat_rl.commands.t062_battle_search_v2 import (
    parse_t062_arm_budgets,
    run_t062_comparison_from_cohort_path,
    run_t062_input_preflight_from_paths,
    write_t062_comparison_report,
)
from sts_combat_rl.commands.t068_checkout import verify_exact_git_checkout
from sts_combat_rl.sim.action_space import ActionSpaceConfig
from sts_combat_rl.sim.battle_search_v2 import BattleSearchV2Controller
from sts_combat_rl.sim.lightspeed import LightSpeedAdapter


NATIVE_COMMIT = "3cb9ebecb87c38044b34aa0e013d42b222a04087"
SOURCE_MANIFEST_SHA256 = (
    "2f4bd6710a152b080a2c6e4cfbaf509148ffb27d0139a9250f1a0ee19efd6631"
)
T068_MANIFEST_SHA256 = (
    "bf974134343cea06e9f58e227f4752002ee3cebc14902206991f9fe81752c678"
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cohort", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--t061-retention-manifest", type=Path, required=True)
    parser.add_argument("--t068-retention-manifest", type=Path, required=True)
    parser.add_argument("--preflight-output", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--code-commit", required=True)
    parser.add_argument("--record-range", required=True)
    parser.add_argument("--shard-index", type=int, required=True)
    parser.add_argument("--baseline-budget", type=int, default=100)
    parser.add_argument("--arm-budget", action="append", default=[])
    parser.add_argument("--family", required=True)
    args = parser.parse_args()
    if not re.fullmatch(r"[0-9a-f]{40}", args.code_commit):
        raise SystemExit("T069 calibration shard requires exact code commit")
    if args.shard_index not in range(16) or args.record_range != (
        f"{args.shard_index}:{args.shard_index + 1}"
    ):
        raise SystemExit("T069 calibration requires 16 one-record shards")
    if args.output.exists() or args.preflight_output.exists():
        raise SystemExit("T069 calibration shard refuses to overwrite output")
    try:
        verify_exact_git_checkout(Path.cwd(), args.code_commit)
    except ValueError as exc:
        raise SystemExit(f"T069 calibration {exc}") from exc
    _verify_sha256(
        Path("docs/sts_lightspeed_source_manifest.json"),
        SOURCE_MANIFEST_SHA256,
    )
    _verify_sha256(args.t068_retention_manifest, T068_MANIFEST_SHA256)
    preflight = run_t062_input_preflight_from_paths(
        output_path=args.preflight_output,
        t061_retention_manifest_path=args.t061_retention_manifest,
        t052_cohort_path=args.cohort,
        t043_checkpoint_path=args.checkpoint,
    )
    if preflight.get("command_passed") is not True:
        raise SystemExit("T069 calibration preflight failed")
    budgets = parse_t062_arm_budgets(args.arm_budget, args.baseline_budget)
    action_space = ActionSpaceConfig.initial_no_potions()
    arms = []
    for arm in ("baseline", "prior_only", "value_only", "prior_value"):
        scorer = build_torch_guidance_scorer_from_checkpoint(args.checkpoint)
        arms.append(
            (
                arm,
                BattleSearchV2Controller(
                    simulations=budgets[arm],
                    scorer=scorer,
                    ablation=arm,  # type: ignore[arg-type]
                    action_space=action_space,
                    inference_cache_enabled=arm != "baseline",
                    inference_cache_capacity=32768,
                    public_context_projection_enabled=arm != "baseline",
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
    report["t069_projection_mode"] = "projected"
    report["t069_code_commit"] = args.code_commit
    report["t069_native_commit"] = NATIVE_COMMIT
    report["t069_candidate_budget"] = budgets
    write_t062_comparison_report(args.output, report)
    return 0 if report.get("successful") is True else 1


def _verify_sha256(path: Path, expected: str) -> None:
    if not path.is_file():
        raise SystemExit(f"T069 missing input: {path}")
    if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
        raise SystemExit(f"T069 input hash changed: {path}")


if __name__ == "__main__":
    raise SystemExit(main())
