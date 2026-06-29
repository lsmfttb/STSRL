"""Argument parser construction for the command-line entrypoint."""

from __future__ import annotations

import argparse
from pathlib import Path

from sts_combat_rl.logging_utils import DEFAULT_LOG_FILE
from sts_combat_rl.sim.model_guided_oracle_search import (
    MODEL_GUIDED_ORACLE_DEFAULT_POLICY_PROBABILITY_WEIGHT,
)
from sts_combat_rl.sim.oracle_search import ORACLE_ROOT_SELECTION_RULES
from sts_combat_rl.sim.oracle_teacher_scaleup import (
    ORACLE_TEACHER_SCALEUP_SOURCE_SELECTION_MODES,
    T032_T039_BACKGROUND_SOURCE_COUNT,
)
from sts_combat_rl.sim.oracle_teacher_search_guidance import (
    ORACLE_TEACHER_SEARCH_GUIDANCE_STABILITY_FILTERS,
    ORACLE_TEACHER_SEARCH_GUIDANCE_TARGETS,
)
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
        "--pytorch-search-guidance-infer",
        type=Path,
        metavar="CHECKPOINT",
        help=(
            "Load a T009/T024 PyTorch policy/value checkpoint and score one "
            "public decision context without running a simulator or choosing "
            "an action."
        ),
    )
    input_group.add_argument(
        "--teacher-guidance-calibration-report",
        type=Path,
        metavar="TRAINER_JSONL",
        help=(
            "Load a T024 teacher-targeted trainer-input artifact and compare "
            "one or more compatible checkpoints against its explicit teacher "
            "policy targets without running a simulator or controller."
        ),
    )
    parser.add_argument(
        "--pytorch-search-guidance-infer-trainer-input",
        type=Path,
        metavar="TRAINER_JSONL",
        help=(
            "Trainer-input JSONL artifact used to rebuild the public decision "
            "context for --pytorch-search-guidance-infer."
        ),
    )
    parser.add_argument(
        "--pytorch-search-guidance-infer-example-index",
        type=int,
        default=None,
        help=(
            "Example index from --pytorch-search-guidance-infer-trainer-input to score."
        ),
    )
    parser.add_argument(
        "--teacher-guidance-calibration-checkpoint",
        type=Path,
        action="append",
        default=[],
        metavar="CHECKPOINT",
        help=(
            "Checkpoint to include in --teacher-guidance-calibration-report. "
            "Repeat for multiple compatible checkpoints."
        ),
    )
    parser.add_argument(
        "--teacher-guidance-calibration-output",
        type=Path,
        metavar="REPORT_JSON",
        help="Write the T027 teacher-guidance calibration report JSON.",
    )
    parser.add_argument(
        "--teacher-guidance-calibration-top-k",
        type=int,
        default=3,
        help="Top-k agreement cutoff for --teacher-guidance-calibration-report.",
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
        "--lightspeed-search-battle-start-pool",
        type=Path,
        metavar="PATH",
        help=(
            "Collect natural battle-start checkpoints from complete controlled runs "
            "whose battle child is OracleSearchController and whose non-combat "
            "child is the separately named stochastic driver."
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
        "--lightspeed-a20-battle-start-coverage",
        type=Path,
        metavar="POOL_PATH",
        help=(
            "Load a portable A20 natural battle-start pool, optionally combine "
            "constructed supplements and sampled training weight, verify restores, "
            "and report T009 broad-training gate gaps."
        ),
    )
    input_group.add_argument(
        "--a20-reachability-report",
        type=Path,
        metavar="OUTPUT_JSON",
        help=(
            "Build an offline T036 reachability comparison report from repeated "
            "--reachability-arm LABEL POOL_JSONL COVERAGE_JSON inputs."
        ),
    )
    input_group.add_argument(
        "--expert-source-coverage-report",
        type=Path,
        metavar="OUTPUT_JSON",
        help=(
            "Build an offline T040 expert non-combat source-coverage comparison "
            "from repeated --expert-source-arm ROLE POOL_JSONL COVERAGE_JSON "
            "inputs."
        ),
    )
    input_group.add_argument(
        "--lightspeed-a20-oracle-teacher-scaleup",
        type=Path,
        metavar="POOL_PATH",
        help=(
            "Load one A20 natural battle-start pool, select a fixed source set, "
            "collect Oracle-like teacher datasets for multiple native-search "
            "budgets, write T022 reports, and emit a scale-up manifest."
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
        "--lightspeed-oracle-potion-fixed-comparison",
        type=Path,
        metavar="COHORT_PATH",
        help=(
            "Load an immutable fixed battle cohort unchanged and compare "
            "no-potion Oracle search against potion-enabled Oracle search on "
            "the same restored starts."
        ),
    )
    input_group.add_argument(
        "--lightspeed-model-guided-oracle-fixed-evaluation",
        type=Path,
        metavar="COHORT_PATH",
        help=(
            "Load an immutable fixed battle cohort unchanged and run a T028 "
            "model-guided Oracle-like search smoke evaluation using a checkpoint."
        ),
    )
    input_group.add_argument(
        "--lightspeed-model-guided-search-fixed-comparison",
        type=Path,
        metavar="COHORT_PATH",
        help=(
            "Load an immutable fixed battle cohort unchanged and compare baseline "
            "Oracle search against the T028 model-guided Oracle-like controller "
            "using the same restored starts."
        ),
    )
    input_group.add_argument(
        "--lightspeed-model-guided-search-v2-fixed-comparison",
        type=Path,
        metavar="COHORT_PATH",
        help=(
            "Load an immutable fixed battle cohort unchanged and compare baseline "
            "Oracle search, the T028 model-guided Oracle-like controller, and "
            "the T035 v2 model-guided Oracle-like controller on the same "
            "restored starts."
        ),
    )
    input_group.add_argument(
        "--oracle-teacher-dataset-report",
        type=Path,
        metavar="TEACHER_JSONL",
        help=(
            "Load a saved Oracle teacher JSONL artifact and report teacher "
            "coverage, source linkage, search statistics, and T021 gate gaps."
        ),
    )
    input_group.add_argument(
        "--oracle-teacher-search-guidance-input",
        type=Path,
        metavar="SCALEUP_MANIFEST_JSON",
        help=(
            "Load a T023 Oracle teacher scale-up manifest, select one budget, "
            "and convert it to explicit teacher-targeted trainer input."
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
            "expert-v1",
            "expert_non_combat_v1",
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
        "--a20-coverage-constructed-artifact",
        type=Path,
        metavar="PATH",
        help=(
            "Load a constructed battle-start supplement artifact for "
            "--lightspeed-a20-battle-start-coverage."
        ),
    )
    parser.add_argument(
        "--a20-coverage-output",
        type=Path,
        metavar="PATH",
        help=("Write the --lightspeed-a20-battle-start-coverage JSON report to PATH."),
    )
    parser.add_argument(
        "--reachability-arm",
        nargs=3,
        action="append",
        default=[],
        metavar=("LABEL", "POOL_JSONL", "COVERAGE_JSON"),
        help=(
            "One arm for --a20-reachability-report. Repeat for default, "
            "Oracle no-potion, potion-enabled, or other explicitly labeled arms."
        ),
    )
    parser.add_argument(
        "--expert-source-arm",
        nargs=3,
        action="append",
        default=[],
        metavar=("ROLE", "POOL_JSONL", "COVERAGE_JSON"),
        help=(
            "One T040 source-coverage arm. Required roles are stochastic_s20, "
            "expert_s20, and expert_s100."
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
        "--oracle-teacher-source-pool",
        type=Path,
        metavar="POOL_PATH",
        help=(
            "Optional natural battle-start source pool for "
            "--oracle-teacher-dataset-report linkage checks."
        ),
    )
    parser.add_argument(
        "--oracle-teacher-coverage-report",
        type=Path,
        metavar="COVERAGE_JSON",
        help=(
            "Optional T021 A20 coverage report for "
            "--oracle-teacher-dataset-report linkage checks."
        ),
    )
    parser.add_argument(
        "--oracle-teacher-report-output",
        type=Path,
        metavar="PATH",
        help="Write --oracle-teacher-dataset-report JSON output to PATH.",
    )
    parser.add_argument(
        "--oracle-teacher-scaleup-output-dir",
        type=Path,
        metavar="DIR",
        help=(
            "Write --lightspeed-a20-oracle-teacher-scaleup teacher JSONL, "
            "T022 reports, and manifest artifacts under DIR."
        ),
    )
    parser.add_argument(
        "--oracle-teacher-scaleup-budgets",
        type=int,
        nargs="+",
        default=[20, 50, 100],
        metavar="N",
        help="Native search budgets for A20 Oracle teacher scale-up.",
    )
    parser.add_argument(
        "--oracle-teacher-scaleup-source-limit",
        type=int,
        metavar="N",
        help="Seeded maximum number of natural source starts selected for scale-up.",
    )
    parser.add_argument(
        "--oracle-teacher-scaleup-source-selection",
        choices=ORACLE_TEACHER_SCALEUP_SOURCE_SELECTION_MODES,
        default="seeded_uniform",
        help=(
            "Source-selection contract for A20 Oracle teacher scale-up. "
            "Use t032_t039_narrow for the T032 rare-source diagnostic set."
        ),
    )
    parser.add_argument(
        "--oracle-teacher-scaleup-background-count",
        type=int,
        default=T032_T039_BACKGROUND_SOURCE_COUNT,
        metavar="N",
        help=(
            "Act 1 non-Boss background source count for "
            "--oracle-teacher-scaleup-source-selection t032_t039_narrow."
        ),
    )
    parser.add_argument(
        "--oracle-teacher-scaleup-seed",
        type=int,
        default=1,
        help="Seed used for deterministic source limiting in teacher scale-up.",
    )
    parser.add_argument(
        "--oracle-teacher-scaleup-coverage-report",
        type=Path,
        metavar="COVERAGE_JSON",
        help=(
            "Optional T021 A20 coverage report linked to every generated T022 "
            "teacher report."
        ),
    )
    parser.add_argument(
        "--oracle-teacher-scaleup-root-selection",
        choices=ORACLE_ROOT_SELECTION_RULES,
        default="highest_mean",
        help="Oracle root statistic used for scale-up teacher labels.",
    )
    parser.add_argument(
        "--oracle-teacher-search-guidance-budget",
        type=int,
        default=100,
        metavar="N",
        help="T023 generated teacher budget to convert for search guidance.",
    )
    parser.add_argument(
        "--oracle-teacher-search-guidance-output",
        type=Path,
        metavar="TRAINER_JSONL",
        help="Write the T024 teacher-targeted trainer JSONL artifact to PATH.",
    )
    parser.add_argument(
        "--oracle-teacher-search-guidance-target",
        choices=ORACLE_TEACHER_SEARCH_GUIDANCE_TARGETS,
        default="teacher_action_one_hot",
        help="Teacher-derived policy target to write into the trainer artifact.",
    )
    parser.add_argument(
        "--oracle-teacher-search-guidance-stability-filter",
        choices=ORACLE_TEACHER_SEARCH_GUIDANCE_STABILITY_FILTERS,
        default="none",
        help="Optional T023 stability filter for selected teacher rows.",
    )
    parser.add_argument(
        "--oracle-teacher-search-guidance-report-output",
        type=Path,
        metavar="REPORT_JSON",
        help="Write the T024 bridge report JSON to PATH.",
    )
    parser.add_argument(
        "--oracle-teacher-search-guidance-checkpoint-output",
        type=Path,
        metavar="CHECKPOINT_PATH",
        help=(
            "Optionally train and write one diagnostic T009-style PyTorch "
            "checkpoint from the generated teacher-targeted trainer artifact."
        ),
    )
    parser.add_argument(
        "--oracle-teacher-search-guidance-epochs",
        type=int,
        help=(
            "Epoch count for the optional T024 diagnostic checkpoint. Defaults "
            "to --pytorch-epochs when omitted."
        ),
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
        "--model-guided-oracle-checkpoint",
        type=Path,
        metavar="CHECKPOINT_PATH",
        help=(
            "T026-compatible PyTorch policy/value checkpoint used by "
            "--lightspeed-model-guided-oracle-fixed-evaluation or "
            "--lightspeed-model-guided-search-fixed-comparison."
        ),
    )
    parser.add_argument(
        "--model-guided-search-comparison-report",
        type=Path,
        metavar="PATH",
        help=(
            "Write the T029 or T035 model-guided search comparison JSONL report "
            "to PATH."
        ),
    )
    parser.add_argument(
        "--model-guided-search-comparison-scale",
        choices=("smoke", "fixed"),
        default="smoke",
        help=(
            "Scale label recorded in the T029 comparison report. The default "
            "marks the run as smoke-scale evidence."
        ),
    )
    parser.add_argument(
        "--oracle-potion-comparison-report",
        type=Path,
        metavar="PATH",
        help="Write the T041 no-potion vs potion-enabled comparison JSONL report.",
    )
    parser.add_argument(
        "--oracle-potion-comparison-scale",
        choices=("smoke", "fixed"),
        default="smoke",
        help=(
            "Scale label recorded in the T041 potion comparison report. The "
            "default marks the run as smoke-scale evidence."
        ),
    )
    parser.add_argument(
        "--model-guided-oracle-policy-probability-weight",
        type=float,
        default=MODEL_GUIDED_ORACLE_DEFAULT_POLICY_PROBABILITY_WEIGHT,
        metavar="WEIGHT",
        help=(
            "Weight for T028 root selection: native_mean_value + WEIGHT * "
            "model_policy_probability."
        ),
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
