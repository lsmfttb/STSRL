#!/usr/bin/env python3
"""Run one frozen single-arm T070 restored-battle shard."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re

from sts_combat_rl.commands.model_guided_oracle_search import (
    build_torch_guidance_scorer_from_checkpoint,
)
from sts_combat_rl.commands.t068_checkout import verify_exact_git_checkout
from sts_combat_rl.commands.t070_search_v2_audit import (
    HIGH_BUDGET_RANGES,
    NATIVE_COMMIT,
    PRIMARY_RANGES,
    T043_CHECKPOINT_SHA256,
    run_single_arm_shard,
)
from sts_combat_rl.sim.action_space import ActionSpaceConfig
from sts_combat_rl.sim.battle_search_v2 import BattleSearchV2Controller
from sts_combat_rl.sim.lightspeed import LightSpeedAdapter


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cohort", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--frozen-manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--code-commit", required=True)
    parser.add_argument(
        "--arm",
        choices=("baseline", "prior_only", "value_only", "prior_value"),
        required=True,
    )
    parser.add_argument("--family", required=True)
    parser.add_argument("--budget", type=int, required=True)
    parser.add_argument("--record-range", required=True)
    parser.add_argument("--shard-index", type=int, required=True)
    parser.add_argument(
        "--range-kind", choices=("primary", "high_budget"), required=True
    )
    parser.add_argument("--tree-geometry", action="store_true")
    args = parser.parse_args()
    if not re.fullmatch(r"[0-9a-f]{40}", args.code_commit):
        raise SystemExit("T070 shard requires exact code commit")
    verify_exact_git_checkout(Path.cwd(), args.code_commit)
    if args.output.exists():
        raise SystemExit("T070 shard refuses to overwrite output")
    if (
        hashlib.sha256(args.checkpoint.read_bytes()).hexdigest()
        != T043_CHECKPOINT_SHA256
    ):
        raise SystemExit("T070 checkpoint hash mismatch")
    frozen = json.loads(args.frozen_manifest.read_text(encoding="utf-8"))
    if (
        frozen.get("schema_id") != "t070-frozen-experiment-manifest-v1"
        or frozen.get("command_passed") is not True
        or frozen.get("code_commit") != args.code_commit
        or frozen.get("native_commit") != NATIVE_COMMIT
    ):
        raise SystemExit("T070 frozen manifest is invalid")
    expected_ranges = (
        PRIMARY_RANGES if args.range_kind == "primary" else HIGH_BUDGET_RANGES
    )
    if args.tree_geometry != (
        args.range_kind == "high_budget" and args.arm == "prior_value"
    ):
        raise SystemExit("T070 geometry mode contradicts frozen stage kind/arm")
    scorer = build_torch_guidance_scorer_from_checkpoint(args.checkpoint)
    controller = BattleSearchV2Controller(
        simulations=args.budget,
        scorer=scorer,
        ablation=args.arm,  # type: ignore[arg-type]
        action_space=ActionSpaceConfig.initial_no_potions(),
        inference_cache_enabled=args.arm != "baseline",
        inference_cache_capacity=32768,
        public_context_projection_enabled=args.arm != "baseline",
        tree_geometry_enabled=args.tree_geometry,
    )
    report = run_single_arm_shard(
        cohort_path=args.cohort,
        adapter_factory=lambda: LightSpeedAdapter(seed=1, ascension=20),
        controller=controller,
        arm=args.arm,
        family=args.family,
        record_range=args.record_range,
        shard_index=args.shard_index,
        expected_ranges=expected_ranges,
        code_commit=args.code_commit,
        output_path=args.output,
    )
    return 0 if report["command_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
