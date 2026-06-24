"""Argument parser construction for the command-line entrypoint."""

from __future__ import annotations

import argparse
from pathlib import Path

from sts_combat_rl.logging_utils import DEFAULT_LOG_FILE
from sts_combat_rl.sim.oracle_search import ORACLE_ROOT_SELECTION_RULES
from sts_combat_rl.sim.reward_design import BATTLE_REWARD_PRESETS
from sts_combat_rl.sim.training_gate import TRAINING_GATE_OVERRIDES


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
        "--lightspeed-tactical-feature-audit",
        action="store_true",
        help=(
            "Audit the versioned public tactical feature contract over bounded "
            "sts_lightspeed snapshots and report schema, coverage, missing "
            "fields, unknown identities, and live parity to stderr."
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
        "--lightspeed-battle-sweep",
        action="store_true",
        help=(
            "Run a battle-agent seed sweep: the selected policy controls only "
            "battle states while a separate driver advances non-combat states."
        ),
    )
    input_group.add_argument(
        "--lightspeed-battle-batch-smoke",
        action="store_true",
        help=(
            "Collect battle-agent rollouts, drop scripted non-combat decisions, "
            "build a battle-only decision batch, and summarize to stderr."
        ),
    )
    input_group.add_argument(
        "--lightspeed-battle-segments-smoke",
        action="store_true",
        help=(
            "Collect battle-agent rollouts, identify contiguous battle segments, "
            "and summarize battle boundary calibration to stderr."
        ),
    )
    input_group.add_argument(
        "--lightspeed-battle-reward-components",
        action="store_true",
        help=(
            "Collect battle-agent rollouts and summarize raw reward-component "
            "candidates to stderr without choosing reward weights."
        ),
    )
    input_group.add_argument(
        "--lightspeed-battle-reward-design",
        action="store_true",
        help=(
            "Collect battle-agent rollouts and score a segment-level reward "
            "draft to stderr without training."
        ),
    )
    input_group.add_argument(
        "--lightspeed-battle-reward-batch-smoke",
        action="store_true",
        help=(
            "Collect battle-agent rollouts, build battle decision examples, "
            "and attach segment reward labels to stderr without training."
        ),
    )
    input_group.add_argument(
        "--lightspeed-battle-trainer-input-contract",
        action="store_true",
        help=(
            "Collect a reward-labeled battle batch and validate future trainer "
            "input fields to stderr without training."
        ),
    )
    input_group.add_argument(
        "--lightspeed-battle-trainer-input-smoke",
        action="store_true",
        help=(
            "Collect a reward-labeled battle batch, package it as a "
            "framework-neutral trainer input dataset, and verify JSONL "
            "serialization to stderr without training."
        ),
    )
    input_group.add_argument(
        "--lightspeed-battle-model-input-smoke",
        action="store_true",
        help=(
            "Collect reward-labeled battle data, package it into flattened "
            "variable-action model input rows, and summarize to stderr "
            "without training."
        ),
    )
    input_group.add_argument(
        "--lightspeed-battle-model-score-smoke",
        action="store_true",
        help=(
            "Collect reward-labeled battle data, pack flattened model input "
            "rows, score every legal action row with a deterministic smoke "
            "scorer, and validate eligible argmax to stderr without training."
        ),
    )
    input_group.add_argument(
        "--lightspeed-battle-training-readiness",
        action="store_true",
        help=(
            "Collect battle-agent rollouts and run the full pre-trainer "
            "readiness checklist to stderr without training."
        ),
    )
    input_group.add_argument(
        "--trainer-input-preflight",
        type=Path,
        metavar="TRAINER_JSONL",
        help=(
            "Load an exported trainer-input JSONL artifact, validate offline "
            "model-input/scoring shape, and report the T009 broad-training gate "
            "without importing PyTorch."
        ),
    )
    input_group.add_argument(
        "--pytorch-search-guidance-train",
        type=Path,
        metavar="TRAINER_JSONL",
        help=(
            "Load trainer-input JSONL, run the T009 broad-training gate, and "
            "train the optional PyTorch policy/value model only if the gate "
            "passes or a named override is supplied."
        ),
    )
    input_group.add_argument(
        "--lightspeed-battle-resource-outcome-audit",
        action="store_true",
        help=(
            "Collect a bounded natural A20 battle-start pool and audit "
            "structured battle-end public resource outcomes to stderr."
        ),
    )
    input_group.add_argument(
        "--lightspeed-constructed-battle-start-audit",
        action="store_true",
        help=(
            "Collect a bounded natural A20 battle-start pool, audit seeded "
            "constructed supplement proposals, and report transform counts, "
            "caps, and unsupported native operations to stderr."
        ),
    )
    input_group.add_argument(
        "--lightspeed-battle-checkpoint-verify",
        action="store_true",
        help=(
            "Capture the first naturally reached battle start, restore its native "
            "checkpoint twice, and verify a deterministic action trace."
        ),
    )
    input_group.add_argument(
        "--lightspeed-battle-start-pool",
        type=Path,
        metavar="PATH",
        help=(
            "Collect natural battle-start checkpoints from the configured seed range, "
            "write a portable JSONL manifest to PATH, and report coverage to stderr."
        ),
    )
    input_group.add_argument(
        "--lightspeed-battle-start-pool-restore",
        type=Path,
        metavar="PATH",
        help=(
            "Load a portable battle-start pool manifest and verify fresh-adapter "
            "seed/action-trace restores."
        ),
    )
    input_group.add_argument(
        "--lightspeed-fixed-battle-evaluation",
        type=Path,
        metavar="POOL_PATH",
        help=(
            "Load a portable battle-start pool, select a fixed structural cohort, "
            "evaluate the named controller on each restored battle start, and write "
            "cohort and evaluation report artifacts."
        ),
    )
    input_group.add_argument(
        "--lightspeed-oracle-search-teacher",
        type=Path,
        metavar="POOL_PATH",
        help=(
            "Load a portable battle-start pool, restore each source checkpoint, "
            "run native hidden-state battle search, and write an Oracle teacher "
            "JSONL artifact."
        ),
    )
    input_group.add_argument(
        "--lightspeed-oracle-fixed-evaluation",
        type=Path,
        metavar="COHORT_PATH",
        help=(
            "Load an immutable fixed battle cohort unchanged and evaluate the "
            "Oracle search controller on the same restored starts."
        ),
    )
    input_group.add_argument(
        "--lightspeed-non-combat-calibration",
        action="store_true",
        help=(
            "Run the versioned stochastic non-combat driver across the named "
            "A20 simulator seed range and require all rare branches."
        ),
    )
    input_group.add_argument(
        "--lightspeed-public-projection-capability-audit",
        action="store_true",
        help=(
            "Audit the versioned raw native public-projection capability, "
            "candidate-action parity, and checkpoint preservation over bounded "
            "sts_lightspeed controlled runs."
        ),
    )
    input_group.add_argument(
        "--lightspeed-public-context-audit",
        action="store_true",
        help=(
            "Audit T016 sanitized public-context artifacts, action-set parity, "
            "portable replay comparison, missingness, and forbidden-field gates "
            "over bounded sts_lightspeed controlled runs."
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
    input_group.add_argument(
        "--audit-tactical-features",
        type=Path,
        nargs="+",
        help=(
            "Audit captured CommunicationMod combat snapshots against the "
            "versioned public tactical feature contract."
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
            "action-kind-prior-scorer",
        ),
        default="preferred-kind",
        help="Policy used by --lightspeed-policy-smoke and policy rollout smoke.",
    )
    parser.add_argument(
        "--sim-non-combat-policy",
        choices=(
            "stochastic-v1",
            "preferred-kind",
            "first-eligible",
            "random-eligible",
        ),
        default="stochastic-v1",
        help=(
            "Non-combat driver policy used by battle-agent smokes. "
            "The default is the seeded hierarchical stochastic driver."
        ),
    )
    parser.add_argument(
        "--reward-detail-limit",
        type=int,
        default=8,
        help=(
            "Maximum highlighted segments shown by "
            "reward component/design reports. Use 0 to hide details."
        ),
    )
    parser.add_argument(
        "--reward-preset",
        choices=BATTLE_REWARD_PRESETS,
        default="battle-v0",
        help="Reward draft preset used by reward design and reward batch smokes.",
    )
    parser.add_argument(
        "--checkpoint-replay-steps",
        type=int,
        default=10,
        help="Maximum battle actions used by --lightspeed-battle-checkpoint-verify.",
    )
    parser.add_argument(
        "--battle-start-restore-limit",
        type=int,
        default=0,
        help="Maximum pool records checked by restore verification; 0 means all.",
    )
    parser.add_argument(
        "--battle-start-sample-count",
        type=int,
        default=0,
        help="Reported seeded optimization draws for a pool; does not add coverage.",
    )
    parser.add_argument(
        "--battle-start-structural-fraction",
        type=float,
        default=0.5,
        help="Fraction of reported pool draws selected by uniform structural stratum.",
    )
    parser.add_argument(
        "--constructed-start-output",
        type=Path,
        metavar="PATH",
        help=(
            "Write --lightspeed-constructed-battle-start-audit JSONL artifact to PATH."
        ),
    )
    parser.add_argument(
        "--constructed-start-pool",
        type=Path,
        metavar="PATH",
        help=(
            "Load an existing portable natural battle-start pool for "
            "--lightspeed-constructed-battle-start-audit instead of collecting "
            "a fresh bounded pool."
        ),
    )
    parser.add_argument(
        "--fixed-evaluation-cohort",
        type=Path,
        metavar="PATH",
        help="Write the selected fixed evaluation cohort to this JSONL path.",
    )
    parser.add_argument(
        "--fixed-evaluation-report",
        type=Path,
        metavar="PATH",
        help="Write the fixed evaluation report to this JSONL path.",
    )
    parser.add_argument(
        "--fixed-evaluation-seed",
        type=int,
        default=1,
        help="Selection seed for the fixed cohort (default: 1).",
    )
    parser.add_argument(
        "--oracle-teacher-output",
        type=Path,
        metavar="PATH",
        help="Write --lightspeed-oracle-search-teacher output to this JSONL path.",
    )
    parser.add_argument(
        "--oracle-search-simulations",
        type=int,
        default=100,
        help="Native BattleScumSearcher2 root playout count for Oracle search.",
    )
    parser.add_argument(
        "--oracle-root-selection",
        choices=ORACLE_ROOT_SELECTION_RULES,
        default="highest_mean",
        help="Oracle root statistic used for teacher/evaluation action selection.",
    )
    parser.add_argument(
        "--pytorch-checkpoint-output",
        type=Path,
        metavar="PATH",
        help="Write --pytorch-search-guidance-train checkpoint to this path.",
    )
    parser.add_argument(
        "--pytorch-gate-override",
        choices=TRAINING_GATE_OVERRIDES,
        default="none",
        help=(
            "Named override for T009 training gate. Overrides allow only smoke "
            "or narrow-curriculum diagnostics, not broad-training evidence."
        ),
    )
    parser.add_argument(
        "--pytorch-gate-required-ascensions",
        type=int,
        nargs="+",
        default=[20],
        help="Ascensions required by the T009 broad-training gate.",
    )
    parser.add_argument(
        "--pytorch-gate-required-acts",
        type=int,
        nargs="+",
        default=[1, 2, 3, 4],
        help="Acts required by the T009 broad-training gate.",
    )
    parser.add_argument(
        "--pytorch-gate-min-records",
        type=int,
        default=100,
        help="Minimum records required per ascension/act for broad training.",
    )
    parser.add_argument(
        "--pytorch-gate-min-sources",
        type=int,
        default=20,
        help="Minimum unique source starts required per ascension/act.",
    )
    parser.add_argument(
        "--pytorch-epochs",
        type=int,
        default=10,
        help="Epoch count for --pytorch-search-guidance-train.",
    )
    parser.add_argument(
        "--pytorch-learning-rate",
        type=float,
        default=0.001,
        help="Learning rate for --pytorch-search-guidance-train.",
    )
    parser.add_argument(
        "--pytorch-hidden-size",
        type=int,
        default=128,
        help="Hidden size for the optional PyTorch policy/value model.",
    )
    parser.add_argument(
        "--pytorch-batch-size",
        type=int,
        default=32,
        help="Batch size for --pytorch-search-guidance-train.",
    )
    return parser
