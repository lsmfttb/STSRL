"""Command-line entrypoint for the communication probe."""

from __future__ import annotations

import argparse
from datetime import datetime
import json
import os
import sys
from pathlib import Path

from sts_combat_rl.comm.protocol import format_command, format_ready_signal
from sts_combat_rl.comm.stdio_client import StdioClient
from sts_combat_rl.logging_utils import DEFAULT_LOG_FILE, configure_logging
from sts_combat_rl.policy.scripted import ScriptedCombatPolicy
from sts_combat_rl.samples import analyze_sample_paths, format_sample_analysis
from sts_combat_rl.sim.action_space import ActionSpaceConfig
from sts_combat_rl.sim.batching import build_decision_batch, format_decision_batch_report
from sts_combat_rl.sim.calibration import (
    format_communicationmod_feature_calibration_report,
    format_simulator_calibration_report,
    run_communicationmod_feature_calibration,
    run_simulator_calibration,
)
from sts_combat_rl.sim.evaluation import (
    format_policy_episode_evaluation_report,
    run_policy_episode_evaluation,
)
from sts_combat_rl.sim.lightspeed import LightSpeedAdapter
from sts_combat_rl.sim.policy import (
    FirstEligiblePolicy,
    PreferredKindPolicy,
    RandomEligiblePolicy,
    ReplayChosenPolicy,
    evaluate_decision_policy,
    format_policy_evaluation_report,
)
from sts_combat_rl.sim.policy_rollout import collect_policy_simulator_rollout
from sts_combat_rl.sim.rollout import collect_simulator_rollout, format_rollout_batch


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Minimal Slay the Spire CommunicationMod-style probe."
    )
    input_group = parser.add_mutually_exclusive_group()
    input_group.add_argument(
        "--mock",
        type=Path,
        help="Read one local JSON fixture and print one policy command.",
    )
    input_group.add_argument(
        "--analyze-samples",
        type=Path,
        nargs="+",
        help=(
            "Replay captured JSONL sample files or directories offline and "
            "summarize to stderr."
        ),
    )
    input_group.add_argument(
        "--lightspeed-smoke",
        action="store_true",
        help=(
            "Run a bounded smoke calibration against a patched external "
            "slaythespire.StepSimulator and summarize to stderr."
        ),
    )
    input_group.add_argument(
        "--lightspeed-rollout-smoke",
        action="store_true",
        help=(
            "Collect a bounded rollout-data smoke from a patched external "
            "slaythespire.StepSimulator and summarize to stderr."
        ),
    )
    input_group.add_argument(
        "--lightspeed-batch-smoke",
        action="store_true",
        help=(
            "Collect several bounded simulator rollouts, build a framework-neutral "
            "decision batch, and summarize to stderr."
        ),
    )
    input_group.add_argument(
        "--lightspeed-policy-smoke",
        action="store_true",
        help=(
            "Collect simulator rollouts, build a decision batch, run a "
            "framework-neutral policy-selection smoke, and summarize to stderr."
        ),
    )
    input_group.add_argument(
        "--lightspeed-policy-rollout-smoke",
        action="store_true",
        help=(
            "Run one bounded simulator rollout whose actions are selected by "
            "the framework-neutral policy interface, and summarize to stderr."
        ),
    )
    input_group.add_argument(
        "--lightspeed-episode-eval",
        action="store_true",
        help=(
            "Run several bounded simulator episodes through the policy interface "
            "and summarize pre-training outcome statistics to stderr."
        ),
    )
    input_group.add_argument(
        "--calibrate-combat-features",
        type=Path,
        nargs="+",
        help=(
            "Summarize live CommunicationMod combat sample readiness for the "
            "fixed-size pre-RL feature encoder."
        ),
    )
    parser.add_argument(
        "--log-file",
        type=Path,
        help=(
            "Path for debug logs. Use '-' to log to stderr. "
            f"Defaults to {DEFAULT_LOG_FILE}."
        ),
    )
    parser.add_argument(
        "--log-dir",
        type=Path,
        help="Create a fresh timestamped debug log file in this directory.",
    )
    capture_group = parser.add_mutually_exclusive_group()
    capture_group.add_argument(
        "--capture-file",
        type=Path,
        help="Append non-empty stdin JSON lines to this local JSONL file.",
    )
    capture_group.add_argument(
        "--capture-dir",
        type=Path,
        help="Create a fresh timestamped JSONL capture file in this directory.",
    )
    parser.add_argument(
        "--manual",
        action="store_true",
        help=(
            "Capture/log states but never emit gameplay actions. "
            "Use wait/state polling so the player can control the game manually."
        ),
    )
    parser.add_argument(
        "--sim-seed",
        type=int,
        default=1,
        help="Seed for --lightspeed-smoke.",
    )
    parser.add_argument(
        "--sim-ascension",
        type=int,
        default=0,
        help="Ascension level for --lightspeed-smoke.",
    )
    parser.add_argument(
        "--sim-steps",
        type=int,
        default=200,
        help="Maximum simulator steps for --lightspeed-smoke.",
    )
    parser.add_argument(
        "--sim-rollouts",
        type=int,
        default=3,
        help="Number of rollouts for --lightspeed-batch-smoke.",
    )
    parser.add_argument(
        "--sim-episodes",
        type=int,
        default=10,
        help="Number of episodes for --lightspeed-episode-eval.",
    )
    parser.add_argument(
        "--include-potions",
        action="store_true",
        help=(
            "Include potion-related actions in --lightspeed-smoke action "
            "selection. The default first-pass action space excludes them."
        ),
    )
    parser.add_argument(
        "--sim-policy",
        choices=(
            "preferred-kind",
            "first-eligible",
            "replay-chosen",
            "random-eligible",
        ),
        default="preferred-kind",
        help="Policy used by --lightspeed-policy-smoke and policy rollout smoke.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.log_file is not None and args.log_dir is not None:
        print("use either --log-file or --log-dir, not both", file=sys.stderr)
        return 2

    capture_file = args.capture_file
    if args.capture_dir is not None:
        capture_file = _timestamped_path(args.capture_dir, "capture", ".jsonl")

    log_file_arg = args.log_file
    if args.log_dir is not None:
        log_file_arg = _timestamped_path(args.log_dir, "communicationmod", ".log")
    elif log_file_arg is None:
        log_file_arg = DEFAULT_LOG_FILE

    log_file = None if str(log_file_arg) == "-" else log_file_arg
    logger = configure_logging(log_file)
    if capture_file is not None:
        logger.info("capturing raw samples to %s", capture_file)
    if log_file is not None:
        logger.info("writing debug log to %s", log_file)
    if args.manual:
        logger.info("manual capture mode enabled; emitting only wait/state poll commands")
    if args.sim_steps < 0:
        print("--sim-steps must be non-negative", file=sys.stderr)
        return 2
    if args.sim_rollouts < 1:
        print("--sim-rollouts must be positive", file=sys.stderr)
        return 2
    if args.sim_episodes < 1:
        print("--sim-episodes must be positive", file=sys.stderr)
        return 2

    policy = ScriptedCombatPolicy()
    client = StdioClient(
        policy=policy,
        logger=logger,
        sample_capture_file=capture_file,
        manual_mode=args.manual,
    )

    if args.analyze_samples is not None:
        try:
            analysis = analyze_sample_paths(args.analyze_samples, policy=policy)
        except OSError as exc:
            print(f"failed to read sample files: {exc}", file=sys.stderr)
            return 2

        print(format_sample_analysis(analysis), file=sys.stderr)
        return 0

    if (
        args.lightspeed_smoke
        or args.lightspeed_rollout_smoke
        or args.lightspeed_batch_smoke
        or args.lightspeed_policy_smoke
        or args.lightspeed_policy_rollout_smoke
        or args.lightspeed_episode_eval
    ):
        try:
            adapter = LightSpeedAdapter(seed=args.sim_seed, ascension=args.sim_ascension)
            action_space = (
                ActionSpaceConfig.include_all()
                if args.include_potions
                else ActionSpaceConfig.initial_no_potions()
            )
            if args.lightspeed_smoke:
                report = run_simulator_calibration(
                    adapter,
                    seed=args.sim_seed,
                    max_steps=args.sim_steps,
                    action_space=action_space,
                )
                print(format_simulator_calibration_report(report), file=sys.stderr)
            else:
                if args.lightspeed_rollout_smoke:
                    batch = collect_simulator_rollout(
                        adapter,
                        seed=args.sim_seed,
                        max_steps=args.sim_steps,
                        action_space=action_space,
                    )
                    print(format_rollout_batch(batch), file=sys.stderr)
                elif args.lightspeed_policy_rollout_smoke:
                    batch = collect_policy_simulator_rollout(
                        adapter,
                        _build_online_sim_policy(args.sim_policy, args.sim_seed),
                        seed=args.sim_seed,
                        max_steps=args.sim_steps,
                        action_space=action_space,
                    )
                    print(format_rollout_batch(batch), file=sys.stderr)
                elif args.lightspeed_episode_eval:
                    episode_report = run_policy_episode_evaluation(
                        adapter,
                        _build_online_sim_policy(args.sim_policy, args.sim_seed),
                        seeds=[
                            args.sim_seed + offset
                            for offset in range(args.sim_episodes)
                        ],
                        max_steps=args.sim_steps,
                        action_space=action_space,
                    )
                    print(
                        format_policy_episode_evaluation_report(episode_report),
                        file=sys.stderr,
                    )
                else:
                    rollouts = [
                        collect_simulator_rollout(
                            adapter,
                            seed=args.sim_seed + offset,
                            max_steps=args.sim_steps,
                            action_space=action_space,
                        )
                        for offset in range(args.sim_rollouts)
                    ]
                    decision_batch = build_decision_batch(rollouts)
                    if args.lightspeed_batch_smoke:
                        print(
                            format_decision_batch_report(decision_batch),
                            file=sys.stderr,
                        )
                    else:
                        policy_evaluation = evaluate_decision_policy(
                            decision_batch,
                            _build_sim_policy(args.sim_policy, args.sim_seed),
                        )
                        print(
                            format_decision_batch_report(decision_batch),
                            file=sys.stderr,
                        )
                        print(file=sys.stderr)
                        print(
                            format_policy_evaluation_report(policy_evaluation),
                            file=sys.stderr,
                        )
        except (RuntimeError, ValueError) as exc:
            print(f"failed to run lightspeed simulator smoke: {exc}", file=sys.stderr)
            return 2
        return 0

    if args.calibrate_combat_features is not None:
        try:
            report = run_communicationmod_feature_calibration(
                args.calibrate_combat_features
            )
        except OSError as exc:
            print(f"failed to calibrate combat features: {exc}", file=sys.stderr)
            return 2

        print(
            format_communicationmod_feature_calibration_report(report),
            file=sys.stderr,
        )
        return 0

    if args.mock is not None:
        try:
            with args.mock.open("r", encoding="utf-8") as file:
                raw = json.load(file)
        except OSError as exc:
            print(f"failed to read mock file: {exc}", file=sys.stderr)
            return 2
        except json.JSONDecodeError as exc:
            print(f"failed to parse mock JSON: {exc}", file=sys.stderr)
            return 2

        if not isinstance(raw, dict):
            print("mock JSON must be an object", file=sys.stderr)
            return 2

        command = client.act_from_raw(raw)
        print(format_command(command))
        return 0

    print(format_ready_signal(), flush=True)
    client.run(sys.stdin, sys.stdout)
    return 0


def _timestamped_path(directory: Path, prefix: str, suffix: str) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base_name = f"{prefix}_{timestamp}_{os.getpid()}"
    candidate = directory / f"{base_name}{suffix}"
    counter = 1
    while candidate.exists():
        candidate = directory / f"{base_name}_{counter}{suffix}"
        counter += 1
    return candidate


def _build_sim_policy(
    policy_name: str,
    seed: int,
) -> FirstEligiblePolicy | PreferredKindPolicy | ReplayChosenPolicy | RandomEligiblePolicy:
    if policy_name == "preferred-kind":
        return PreferredKindPolicy()
    if policy_name == "first-eligible":
        return FirstEligiblePolicy()
    if policy_name == "replay-chosen":
        return ReplayChosenPolicy()
    if policy_name == "random-eligible":
        return RandomEligiblePolicy(seed=seed)
    raise ValueError(f"unknown simulator policy: {policy_name}")


def _build_online_sim_policy(
    policy_name: str,
    seed: int,
) -> FirstEligiblePolicy | PreferredKindPolicy | RandomEligiblePolicy:
    if policy_name == "replay-chosen":
        raise ValueError(
            "replay-chosen is only valid for --lightspeed-policy-smoke, "
            "because online rollouts do not have recorded chosen labels"
        )
    policy = _build_sim_policy(policy_name, seed)
    if isinstance(policy, ReplayChosenPolicy):
        raise ValueError("replay-chosen is not valid for online policy rollouts")
    return policy


if __name__ == "__main__":
    raise SystemExit(main())
