#!/usr/bin/env python3
"""Run one frozen single-arm T070 restored-battle shard."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
import re

from sts_combat_rl.commands.model_guided_oracle_search import (
    build_torch_guidance_scorer_from_checkpoint,
)
from sts_combat_rl.commands.t068_checkout import verify_exact_git_checkout
from sts_combat_rl.commands.t070_search_v2_audit import (
    T043_CHECKPOINT_SHA256,
    run_single_arm_shard,
    validate_t070_frozen_stage,
    validate_t070_preflight,
)
from sts_combat_rl.sim.action_space import ActionSpaceConfig
from sts_combat_rl.sim.battle_search_v2 import BattleSearchV2Controller
from sts_combat_rl.sim.lightspeed import LightSpeedAdapter


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cohort", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--frozen-manifest", type=Path, required=True)
    parser.add_argument("--native-preflight", type=Path, required=True)
    parser.add_argument("--native-checkout", type=Path, required=True)
    parser.add_argument("--native-build-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--code-commit", required=True)
    parser.add_argument("--stage-name", required=True)
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
    source_manifest = Path("docs/sts_lightspeed_source_manifest.json")
    source_verifier = Path("scripts/verify_lightspeed_source.sh")
    preflight = validate_t070_preflight(
        args.native_preflight,
        code_commit=args.code_commit,
        source_manifest_path=source_manifest,
        source_verifier_path=source_verifier,
        native_checkout=args.native_checkout,
        native_build_root=args.native_build_root,
    )
    _, expected_ranges = validate_t070_frozen_stage(
        args.frozen_manifest,
        code_commit=args.code_commit,
        stage_name=args.stage_name,
        arm=args.arm,
        family=args.family,
        budget=args.budget,
        range_kind=args.range_kind,
        tree_geometry=args.tree_geometry,
        cohort_path=args.cohort,
        checkpoint_path=args.checkpoint,
        source_manifest_path=source_manifest,
        source_verifier_path=source_verifier,
    )
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
        stage_name=args.stage_name,
        arm=args.arm,
        family=args.family,
        record_range=args.record_range,
        shard_index=args.shard_index,
        expected_ranges=expected_ranges,
        code_commit=args.code_commit,
        native_runtime_identity=preflight["native_runtime_identity"],
        output_path=args.output,
    )
    return 0 if report["command_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
