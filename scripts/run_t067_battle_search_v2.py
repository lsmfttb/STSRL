#!/usr/bin/env python3
"""Run one explicit T067 repaired four-arm calibration shard in WSL.

The script intentionally emits a T062-shaped shard so the existing streaming
merge validator remains authoritative.  ``merge_t067_battle_search_v2.py``
wraps the merged result in the versioned T067 attribution schema.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

from sts_combat_rl.commands.model_guided_oracle_search import (
    build_torch_guidance_scorer_from_checkpoint,
)
from sts_combat_rl.commands.t062_battle_search_v2 import (
    parse_t062_arm_budgets,
    run_t062_comparison_from_cohort_path,
    run_t062_input_preflight_from_paths,
    write_t062_comparison_report,
)
from sts_combat_rl.sim.action_space import ActionSpaceConfig
from sts_combat_rl.sim.battle_search_v2 import BattleSearchV2Controller
from sts_combat_rl.sim.lightspeed import LightSpeedAdapter


EXPECTED_NATIVE_COMMIT = "3cb9ebecb87c38044b34aa0e013d42b222a04087"
EXPECTED_SOURCE_MANIFEST_SHA256 = (
    "2f4bd6710a152b080a2c6e4cfbaf509148ffb27d0139a9250f1a0ee19efd6631"
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cohort", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--t061-retention-manifest", type=Path, required=True)
    parser.add_argument("--input-preflight-report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--record-range", required=True)
    parser.add_argument("--workers", type=int, default=16)
    parser.add_argument("--shards", type=int, default=16)
    parser.add_argument("--sim-seed", type=int, default=1)
    parser.add_argument("--sim-ascension", type=int, default=20)
    parser.add_argument("--sim-steps", type=int, default=200)
    parser.add_argument("--baseline-budget", type=int, default=100)
    parser.add_argument("--arm-budget", action="append", default=[])
    parser.add_argument("--family", default="nominal")
    parser.add_argument("--cache-capacity", type=int, default=4096)
    args = parser.parse_args()

    if args.workers != 16 or args.shards != 16 or args.record_range.count(":") != 1:
        raise SystemExit("T067 requires 16 workers, 16 shards, and an explicit range")
    _verify_source_manifest(Path("docs/sts_lightspeed_source_manifest.json"))
    preflight = run_t062_input_preflight_from_paths(
        output_path=args.input_preflight_report,
        t061_retention_manifest_path=args.t061_retention_manifest,
        t052_cohort_path=args.cohort,
        t043_checkpoint_path=args.checkpoint,
    )
    if not preflight["command_passed"]:
        raise SystemExit(
            "T067 input preflight failed: " + "; ".join(preflight["problems"])
        )

    scorer = build_torch_guidance_scorer_from_checkpoint(args.checkpoint)
    budgets = parse_t062_arm_budgets(
        args.arm_budget,
        args.baseline_budget,
    )
    action_space = ActionSpaceConfig.initial_no_potions()
    baseline = BattleSearchV2Controller(
        simulations=budgets["baseline"],
        scorer=scorer,
        ablation="baseline",
        action_space=action_space,
    )
    arms = [
        ("baseline", baseline),
        *[
            (
                label,
                BattleSearchV2Controller(
                    simulations=budgets[label],
                    scorer=scorer,
                    ablation=label,  # type: ignore[arg-type]
                    action_space=action_space,
                    inference_cache_enabled=True,
                    inference_cache_capacity=args.cache_capacity,
                ),
            )
            for label in ("prior_only", "value_only", "prior_value")
        ],
    ]
    report = run_t062_comparison_from_cohort_path(
        adapter_factory=lambda: LightSpeedAdapter(
            seed=args.sim_seed,
            ascension=args.sim_ascension,
        ),
        cohort_path=args.cohort,
        controller_arms=arms,
        action_space=action_space,
        max_battle_steps=args.sim_steps,
        family=args.family,
        worker_count=args.workers,
        shard_count=args.shards,
        record_range=args.record_range,
    )
    report["t067_repair_identity"] = "exact-public-node-inference-cache-v1"
    report["t067_native_commit"] = EXPECTED_NATIVE_COMMIT
    report["t067_candidate_budget"] = budgets
    write_t062_comparison_report(args.output, report)
    print(
        f"T067 shard: range={args.record_range}, family={args.family}, "
        f"successful={'yes' if report['successful'] else 'no'}",
        file=sys.stderr,
    )
    return 0 if report["successful"] else 1


def _verify_source_manifest(path: Path) -> None:
    import hashlib
    import json

    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual != EXPECTED_SOURCE_MANIFEST_SHA256:
        raise SystemExit("T067 source manifest hash does not match T062 identity")
    raw = json.loads(path.read_text(encoding="utf-8"))
    integration = raw.get("integration", {})
    if integration.get("commit") != EXPECTED_NATIVE_COMMIT:
        raise SystemExit(
            "T067 source manifest native commit does not match T062 identity"
        )


if __name__ == "__main__":
    raise SystemExit(main())
