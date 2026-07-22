"""Argument parser construction for the command-line entrypoint."""

from __future__ import annotations

import argparse
from pathlib import Path

from sts_combat_rl.logging_utils import DEFAULT_LOG_FILE
from sts_combat_rl.sim.assisted_source_generation import ASSISTANCE_LEVELS
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
from sts_combat_rl.commands.search_battle_controller import (
    SEARCH_BATTLE_CONTROLLER_CHOICES,
    SEARCH_BATTLE_CONTROLLER_ORACLE,
)


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
    input_group.add_argument(
        "--post-t044-failure-analysis-report",
        type=Path,
        metavar="OUTPUT_JSON",
        help=(
            "Build the offline T045 post-T044 failure analysis JSON report from "
            "one or more explicit --post-t044-comparison T044 artifacts."
        ),
    )
    input_group.add_argument(
        "--t053-root-prior-allocation-failure-analysis-report",
        type=Path,
        metavar="OUTPUT_JSON",
        help=(
            "Build the offline T053 root-prior allocation failure analysis "
            "JSON report from explicit retained T052 artifacts."
        ),
    )
    input_group.add_argument(
        "--t054-guardrailed-root-prior-repair-report",
        type=Path,
        metavar="OUTPUT_JSON",
        help=(
            "Build the offline T054 guardrailed root-prior repair JSON report "
            "from explicit retained T052/T053 artifacts and a generated T054 "
            "four-arm comparison."
        ),
    )
    input_group.add_argument(
        "--t055-guardrailed-root-prior-scale-validation-report",
        type=Path,
        metavar="OUTPUT_JSON",
        help=(
            "Build the offline T055 guardrailed root-prior scale-validation "
            "JSON report from explicit T048/T054 inputs and generated T055 "
            "four-arm comparisons."
        ),
    )
    input_group.add_argument(
        "--t056-post-t055-root-prior-path-selection-report",
        type=Path,
        metavar="OUTPUT_JSON",
        help=(
            "Build the offline T056 post-T055 root-prior path-selection JSON "
            "report from explicit retained T048/T050/T051/T052/T053/T054/T055 "
            "artifacts."
        ),
    )
    input_group.add_argument(
        "--t057-existing-root-prior-telemetry-diagnostic-report",
        type=Path,
        metavar="OUTPUT_JSON",
        help=(
            "Build the offline T057 existing-root-prior allocation telemetry "
            "diagnostic JSON report from explicit retained T048/T052/T053/"
            "T055/T056 artifacts."
        ),
    )
    input_group.add_argument(
        "--t058-root-prior-selected-action-telemetry-report",
        type=Path,
        metavar="OUTPUT_JSON",
        help=(
            "Build the offline T058 root-prior selected-action telemetry "
            "diagnostic JSON report from T057, retained cohorts/checkpoints, "
            "and instrumented T058 replay comparison artifacts."
        ),
    )
    input_group.add_argument(
        "--t059-root-prior-allocation-repair-report",
        type=Path,
        metavar="OUTPUT_JSON",
        help=(
            "Build the offline T059 root-prior allocation repair JSON report "
            "from T058 evidence, retained cohorts/checkpoints, retained T058 "
            "comparison artifacts, and generated T059 repair comparisons."
        ),
    )
    input_group.add_argument(
        "--t052-t051-boss-later-act-fixed-cohort",
        type=Path,
        metavar="OUTPUT_JSONL",
        help=(
            "Build the T052 fixed diagnostic cohort from retained T051 Boss and "
            "later-act natural source-pool starts."
        ),
    )
    input_group.add_argument(
        "--t052-retention-manifest",
        type=Path,
        metavar="OUTPUT_JSON",
        help=(
            "Build the T052 retention manifest from already generated cohort, "
            "comparison, log, and summary artifacts."
        ),
    )
    input_group.add_argument(
        "--t054-retention-manifest",
        type=Path,
        metavar="OUTPUT_JSON",
        help=(
            "Build the T054 retention manifest from already generated "
            "comparison, report, log, and summary artifacts."
        ),
    )
    input_group.add_argument(
        "--t055-retention-manifest",
        type=Path,
        metavar="OUTPUT_JSON",
        help=(
            "Build the T055 retention manifest from already generated "
            "comparison, report, log, wrapper, and summary artifacts."
        ),
    )
    input_group.add_argument(
        "--t059-retention-manifest",
        type=Path,
        metavar="OUTPUT_JSON",
        help=(
            "Build the T059 retention manifest from already generated "
            "comparison, report, log, wrapper, and summary artifacts."
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
    parser.add_argument(
        "--post-t044-comparison",
        type=Path,
        action="append",
        default=[],
        metavar="T044_JSONL",
        help=(
            "One T044 de-assisted fixed-cohort comparison JSONL artifact for "
            "--post-t044-failure-analysis-report. Repeat for multiple cohorts."
        ),
    )
    parser.add_argument(
        "--post-t044-linked-artifact",
        nargs=2,
        action="append",
        default=[],
        metavar=("ROLE", "PATH"),
        help=(
            "Optional linked T043/T044 artifact identity for the T045 report, "
            "for example calibration REPORT_JSON. Repeat as needed."
        ),
    )
    parser.add_argument(
        "--t053-t052-artifact",
        nargs=3,
        action="append",
        default=[],
        metavar=("ROLE", "PATH", "SHA256"),
        help=(
            "One retained T052 artifact for "
            "--t053-root-prior-allocation-failure-analysis-report. Required "
            "roles are retention_manifest, fixed_cohort, "
            "root_prior_guided_comparison, and result_summary."
        ),
    )
    parser.add_argument(
        "--t054-input-artifact",
        nargs=3,
        action="append",
        default=[],
        metavar=("ROLE", "PATH", "SHA256"),
        help=(
            "One retained or generated artifact for "
            "--t054-guardrailed-root-prior-repair-report. Required roles are "
            "t052_retention_manifest, t052_fixed_cohort, "
            "t052_root_prior_guided_comparison, t052_result_summary, "
            "t053_failure_analysis, and t054_guardrailed_comparison."
        ),
    )
    parser.add_argument(
        "--t055-input-artifact",
        nargs=3,
        action="append",
        default=[],
        metavar=("ROLE", "PATH", "SHA256"),
        help=(
            "One retained or generated artifact for "
            "--t055-guardrailed-root-prior-scale-validation-report. Required "
            "roles include T054 report/comparison/manifest, two T048 reference "
            "comparisons, two retained cohorts, two checkpoints, and two T055 "
            "guardrailed comparisons."
        ),
    )
    parser.add_argument(
        "--t056-input-artifact",
        nargs=3,
        action="append",
        default=[],
        metavar=("ROLE", "PATH", "SHA256"),
        help=(
            "One retained artifact for "
            "--t056-post-t055-root-prior-path-selection-report. Required "
            "roles cover T048 comparisons, T050/T051 reachability reports and "
            "retention manifests, T052/T053/T054 reports, and T055 report, "
            "manifest, and comparisons."
        ),
    )
    parser.add_argument(
        "--t057-input-artifact",
        nargs=3,
        action="append",
        default=[],
        metavar=("ROLE", "PATH", "SHA256"),
        help=(
            "One retained artifact for "
            "--t057-existing-root-prior-telemetry-diagnostic-report. Required "
            "roles cover the T056 path-selection report, T048/T052/T055 "
            "comparison artifacts, the T052 result summary, T053 failure "
            "analysis report, and T055 scale-validation report."
        ),
    )
    parser.add_argument(
        "--t058-input-artifact",
        nargs=3,
        action="append",
        default=[],
        metavar=("ROLE", "PATH", "SHA256"),
        help=(
            "One retained or generated artifact for "
            "--t058-root-prior-selected-action-telemetry-report. Required "
            "roles cover the T057 report, three retained fixed cohorts, two "
            "T043 checkpoints, and three instrumented T058 replay comparisons."
        ),
    )
    parser.add_argument(
        "--t059-input-artifact",
        nargs=3,
        action="append",
        default=[],
        metavar=("ROLE", "PATH", "SHA256"),
        help=(
            "One retained or generated artifact for "
            "--t059-root-prior-allocation-repair-report. Required roles cover "
            "the T058 report/manifest, retained T058 comparisons, three fixed "
            "cohorts, two T043 checkpoints, and three generated T059 repair "
            "comparisons."
        ),
    )
    parser.add_argument(
        "--t052-source-arm",
        nargs=4,
        action="append",
        default=[],
        metavar=("ROLE", "LABEL", "POOL_JSONL", "SHA256"),
        help=(
            "One T052 source arm for cohort extraction. Required roles are "
            "baseline, post_search, and root_prior. Repeat exactly three times."
        ),
    )
    parser.add_argument(
        "--t052-verify-artifact",
        nargs=3,
        action="append",
        default=[],
        metavar=("ROLE", "PATH", "SHA256"),
        help=(
            "Additional T052 input artifact to hash-check before cohort "
            "extraction, such as the T051 manifest, reachability report, or "
            "checkpoint."
        ),
    )
    parser.add_argument(
        "--t052-cohort-summary",
        type=Path,
        metavar="OUTPUT_JSON",
        help="Write the T052 cohort extraction summary JSON artifact.",
    )
    parser.add_argument(
        "--t052-retained-artifact",
        nargs=3,
        action="append",
        default=[],
        metavar=("ROLE", "PATH", "SCHEMA_ID"),
        help=(
            "One generated artifact to include in --t052-retention-manifest. "
            "Repeat for cohort, summary, comparison, logs, and reports."
        ),
    )
    parser.add_argument(
        "--t052-retention-command",
        nargs=2,
        action="append",
        default=[],
        metavar=("ROLE", "COMMAND"),
        help="One reproduction command recorded in the T052 retention manifest.",
    )
    parser.add_argument(
        "--t052-retention-stage",
        nargs=5,
        action="append",
        default=[],
        metavar=("ROLE", "WORKERS", "SHARDS", "RECORD_RANGE", "SECONDS"),
        help=(
            "One runtime stage recorded in the T052 retention manifest, including "
            "worker count, shard count, cohort record range, and wall-clock seconds."
        ),
    )
    parser.add_argument(
        "--t052-retention-note",
        nargs=2,
        action="append",
        default=[],
        metavar=("KEY", "VALUE"),
        help="Free-form key/value note recorded in the T052 retention manifest.",
    )
    parser.add_argument(
        "--t054-retained-artifact",
        nargs=3,
        action="append",
        default=[],
        metavar=("ROLE", "PATH", "SCHEMA_ID"),
        help=(
            "One generated artifact to include in --t054-retention-manifest. "
            "Repeat for comparison, report, logs, and manifests."
        ),
    )
    parser.add_argument(
        "--t054-retention-command",
        nargs=2,
        action="append",
        default=[],
        metavar=("ROLE", "COMMAND"),
        help="One reproduction command recorded in the T054 retention manifest.",
    )
    parser.add_argument(
        "--t054-retention-stage",
        nargs=5,
        action="append",
        default=[],
        metavar=("ROLE", "WORKERS", "SHARDS", "RECORD_RANGE", "SECONDS"),
        help=(
            "One runtime stage recorded in the T054 retention manifest, including "
            "worker count, shard count, cohort record range, and wall-clock seconds."
        ),
    )
    parser.add_argument(
        "--t054-retention-note",
        nargs=2,
        action="append",
        default=[],
        metavar=("KEY", "VALUE"),
        help="Free-form key/value note recorded in the T054 retention manifest.",
    )
    parser.add_argument(
        "--t055-retained-artifact",
        nargs=3,
        action="append",
        default=[],
        metavar=("ROLE", "PATH", "SCHEMA_ID"),
        help=(
            "One generated artifact to include in --t055-retention-manifest. "
            "Repeat for comparisons, report, logs, wrappers, and manifests."
        ),
    )
    parser.add_argument(
        "--t055-retention-command",
        nargs=2,
        action="append",
        default=[],
        metavar=("ROLE", "COMMAND"),
        help="One reproduction command recorded in the T055 retention manifest.",
    )
    parser.add_argument(
        "--t055-retention-stage",
        nargs=5,
        action="append",
        default=[],
        metavar=("ROLE", "WORKERS", "SHARDS", "RECORD_RANGE", "SECONDS"),
        help=(
            "One runtime stage recorded in the T055 retention manifest, including "
            "worker count, shard count, cohort record range, and wall-clock seconds."
        ),
    )
    parser.add_argument(
        "--t055-retention-note",
        nargs=2,
        action="append",
        default=[],
        metavar=("KEY", "VALUE"),
        help="Free-form key/value note recorded in the T055 retention manifest.",
    )
    parser.add_argument(
        "--t059-retained-artifact",
        nargs=3,
        action="append",
        default=[],
        metavar=("ROLE", "PATH", "SCHEMA_ID"),
        help=(
            "One generated artifact to include in --t059-retention-manifest. "
            "Repeat for comparisons, report, logs, wrappers, and manifests."
        ),
    )
    parser.add_argument(
        "--t059-retention-command",
        nargs=2,
        action="append",
        default=[],
        metavar=("ROLE", "COMMAND"),
        help="One reproduction command recorded in the T059 retention manifest.",
    )
    parser.add_argument(
        "--t059-retention-stage",
        nargs=5,
        action="append",
        default=[],
        metavar=("ROLE", "WORKERS", "SHARDS", "RECORD_RANGE", "SECONDS"),
        help=(
            "One runtime stage recorded in the T059 retention manifest, including "
            "worker count, shard count, cohort record range, and wall-clock seconds."
        ),
    )
    parser.add_argument(
        "--t059-retention-note",
        nargs=2,
        action="append",
        default=[],
        metavar=("KEY", "VALUE"),
        help="Free-form key/value note recorded in the T059 retention manifest.",
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
        "--lightspeed-native-root-prior-allocation-smoke",
        action="store_true",
        help=(
            "Run a T046 diagnostic smoke comparing baseline native battle_search "
            "with uniform and one-hot root-prior allocation searches."
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
            "whose battle child is a search controller and whose non-combat child "
            "is the separately named stochastic driver."
        ),
    )
    input_group.add_argument(
        "--lightspeed-assisted-battle-start-pool",
        type=Path,
        metavar="PATH",
        help=(
            "Collect T042 assisted complete-run battle-start checkpoints for "
            "one --assistance-level and write an assisted-run JSONL artifact."
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
        "--lightspeed-assisted-a20-battle-start-coverage",
        type=Path,
        metavar="ASSISTED_POOL_PATH",
        help=(
            "Load a T042 assisted source pool, verify assisted replay restores, "
            "and report A20 coverage plus T009 broad-training gate status."
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
        "--merge-battle-start-pool-shards",
        type=Path,
        metavar="OUTPUT_JSONL",
        help=(
            "Merge repeated --battle-start-pool-shard natural source-pool JSONL "
            "artifacts into one current-schema natural battle-start pool."
        ),
    )
    input_group.add_argument(
        "--merge-a20-battle-start-coverage",
        type=Path,
        metavar="OUTPUT_JSON",
        help=(
            "Build one merged A20 coverage report from --merged-battle-start-pool "
            "and repeated shard-level --battle-start-coverage-shard reports."
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
        "--assisted-source-coverage-report",
        type=Path,
        metavar="OUTPUT_JSON",
        help=(
            "Build an offline T042 assisted source-coverage comparison from "
            "repeated --assisted-source-arm LEVEL POOL_JSONL COVERAGE_JSON inputs."
        ),
    )
    parser.add_argument(
        "--t061-bottleneck-report",
        type=Path,
        metavar="OUTPUT_JSON",
        help=(
            "Build T061 restored-battle budget, complete-run factorial, and "
            "single-recommendation reports from --t061-budget-arm and "
            "--t061-factorial-arm inputs."
        ),
    )
    parser.add_argument(
        "--t061-budget-curve-report",
        type=Path,
        metavar="OUTPUT_JSON",
        help="Write the T061 restored-battle budget-curve report.",
    )
    parser.add_argument(
        "--t061-factorial-report",
        type=Path,
        metavar="OUTPUT_JSON",
        help="Write the T061 complete-run factorial report.",
    )
    parser.add_argument(
        "--t061-budget-arm",
        nargs=2,
        action="append",
        default=[],
        metavar=("BUDGET", "JSON_PATH"),
        help="One T061 restored-battle budget arm; repeat for 20, 100, and 300.",
    )
    parser.add_argument(
        "--t061-factorial-arm",
        nargs=3,
        action="append",
        default=[],
        metavar=("DRIVER", "BUDGET", "JSON_PATH"),
        help=(
            "One T061 complete-run factorial arm; repeat for both drivers and "
            "budgets 20, 100, and 300."
        ),
    )
    parser.add_argument(
        "--t061-expected-run-count",
        type=int,
        default=256,
        help="Expected runs per T061 factorial arm (default: 256).",
    )
    parser.add_argument(
        "--t061-bootstrap-resamples",
        type=int,
        default=2000,
        help="Bootstrap resamples for T061 paired intervals (default: 2000).",
    )
    parser.add_argument(
        "--t062-input-preflight-report",
        type=Path,
        metavar="OUTPUT_JSON",
        help=(
            "Verify the published T061 retention manifest, T052 93-record "
            "cohort, and T043 diagnostic checkpoint identities before T062 "
            "calibration or model inference."
        ),
    )
    parser.add_argument(
        "--t062-t061-retention-manifest",
        type=Path,
        metavar="MANIFEST_JSON",
        help="Published T061 retention manifest required by T062.",
    )
    parser.add_argument(
        "--t062-fixed-cohort",
        type=Path,
        metavar="COHORT_JSONL",
        help="Published 93-record T052 fixed cohort required by T062.",
    )
    parser.add_argument(
        "--t062-checkpoint",
        type=Path,
        metavar="CHECKPOINT_PT",
        help="Published T043 diagnostic policy/value checkpoint required by T062.",
    )
    parser.add_argument(
        "--merge-t062-comparison",
        type=Path,
        metavar="OUTPUT_JSON",
        help="Merge explicit T062 comparison shards and compute paired statistics.",
    )
    parser.add_argument(
        "--t062-comparison-shard",
        type=Path,
        action="append",
        default=[],
        metavar="SHARD_JSON",
        help="One T062 comparison shard used by --merge-t062-comparison.",
    )
    parser.add_argument(
        "--t062-expected-record-count",
        type=int,
        default=93,
        help="Required distinct record count for a merged T062 report.",
    )
    parser.add_argument(
        "--t062-decision-report",
        type=Path,
        metavar="OUTPUT_JSON",
        help="Apply T062's predeclared promotion gate to three merged reports.",
    )
    parser.add_argument(
        "--t062-nominal-comparison",
        type=Path,
        metavar="REPORT_JSON",
        help="Merged equal-nominal-budget T062 comparison report.",
    )
    parser.add_argument(
        "--t062-simulator-step-comparison",
        type=Path,
        metavar="REPORT_JSON",
        help="Merged simulator-step-normalized T062 comparison report.",
    )
    parser.add_argument(
        "--t062-wall-clock-comparison",
        type=Path,
        metavar="REPORT_JSON",
        help="Merged wall-clock-normalized T062 comparison report.",
    )
    input_group.add_argument(
        "--merge-assisted-source-pool",
        type=Path,
        metavar="OUTPUT_JSONL",
        help=(
            "Merge repeated --assisted-source-shard JSONL artifacts for one T042 "
            "assistance level into a single assisted source-pool artifact."
        ),
    )
    input_group.add_argument(
        "--merge-assisted-a20-coverage",
        type=Path,
        metavar="OUTPUT_JSON",
        help=(
            "Build a merged T042 assisted A20 coverage report from one "
            "--merged-assisted-source-pool and repeated --assisted-coverage-shard "
            "JSON reports."
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
        "--lightspeed-a20-assisted-oracle-teacher-scaleup",
        type=Path,
        metavar="ASSISTED_POOL_PATH",
        help=(
            "Load one T042 A20 assisted battle-start pool, select a fixed "
            "source set, collect Oracle-like teacher datasets for multiple "
            "native-search budgets, write T022 reports, and emit a T043 "
            "assisted scale-up manifest."
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
        "--lightspeed-de-assisted-fixed-cohort-comparison",
        type=Path,
        metavar="COHORT_PATH",
        help=(
            "Load an immutable fixed battle cohort from unassisted or assisted "
            "source starts and run the T044 de-assisted comparison across "
            "baseline Oracle search, T043 v2 guided search, raw checkpoint "
            "policy, and scripted policy arms."
        ),
    )
    input_group.add_argument(
        "--lightspeed-root-prior-guided-search-comparison",
        type=Path,
        metavar="COHORT_PATH",
        help=(
            "Load an immutable fixed battle cohort unchanged and run the T047 "
            "comparison across baseline Oracle search, post-search v2 "
            "model-guided search, and native root-prior guided search."
        ),
    )
    input_group.add_argument(
        "--lightspeed-t054-guardrailed-root-prior-repair-comparison",
        type=Path,
        metavar="COHORT_PATH",
        help=(
            "Load the retained T052 fixed cohort unchanged and run the T054 "
            "four-arm comparison across baseline Oracle search, post-search v2 "
            "model-guided search, existing root-prior guided search, and the "
            "new guardrailed root-prior variant."
        ),
    )
    input_group.add_argument(
        "--lightspeed-t055-guardrailed-root-prior-scale-comparison",
        type=Path,
        metavar="COHORT_PATH",
        help=(
            "Load one retained T048 fixed cohort unchanged and run the T055 "
            "four-arm scale-validation comparison across baseline Oracle search, "
            "post-search v2 model-guided search, existing root-prior guided "
            "search, and the T054 guardrailed root-prior variant."
        ),
    )
    input_group.add_argument(
        "--lightspeed-t059-root-prior-allocation-repair-comparison",
        type=Path,
        metavar="COHORT_PATH",
        help=(
            "Load one retained T048/T052 fixed cohort unchanged and run the "
            "T059 four-arm comparison across baseline Oracle search, post-search "
            "v2 model-guided search, existing root-prior guided search, and the "
            "T059 allocation repair variant."
        ),
    )
    input_group.add_argument(
        "--lightspeed-t062-battle-search-v2-comparison",
        type=Path,
        metavar="COHORT_PATH",
        help=(
            "Load an immutable fixed battle cohort unchanged and evaluate the "
            "four T062 tree-internal policy/value search ablations."
        ),
    )
    input_group.add_argument(
        "--merge-root-prior-guided-search-comparison",
        type=Path,
        metavar="OUTPUT_JSONL",
        help=(
            "Merge current-schema root-prior guided comparison shard reports "
            "written with --record-range into one comparison JSONL artifact."
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
        "--sim-non-combat-seed",
        type=int,
        default=None,
        help=(
            "Seed for seeded non-combat drivers. Defaults to --sim-seed; set this "
            "for sharded source-generation when source seed ranges differ."
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
        "--assistance-level",
        choices=ASSISTANCE_LEVELS,
        default="assist_0",
        help=(
            "T042 assistance schedule used by --lightspeed-assisted-battle-start-pool."
        ),
    )
    parser.add_argument(
        "--assistance-policy-seed",
        type=int,
        default=None,
        help="Seed recorded in T042 assistance provenance. Defaults to --sim-seed.",
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
        "--stream-reachability-pools",
        action="store_true",
        help=(
            "Stream current-schema --a20-reachability-report pool records instead "
            "of loading all arm pools into memory."
        ),
    )
    parser.add_argument(
        "--battle-start-pool-shard",
        type=Path,
        action="append",
        default=[],
        metavar="POOL_JSONL",
        help=(
            "One natural battle-start source-pool shard for "
            "--merge-battle-start-pool-shards. Repeat for every generated shard."
        ),
    )
    parser.add_argument(
        "--battle-start-pool-shard-merge-manifest",
        type=Path,
        metavar="MANIFEST_JSON",
        help=(
            "Optional T050 manifest written by --merge-battle-start-pool-shards "
            "with shard paths, hashes, counts, and merged output identity."
        ),
    )
    parser.add_argument(
        "--merged-battle-start-pool",
        type=Path,
        metavar="POOL_JSONL",
        help=(
            "Merged natural battle-start pool used by "
            "--merge-a20-battle-start-coverage."
        ),
    )
    parser.add_argument(
        "--battle-start-coverage-shard",
        type=Path,
        action="append",
        default=[],
        metavar="COVERAGE_JSON",
        help=(
            "One shard-level A20 coverage report for --merge-a20-battle-start-coverage."
        ),
    )
    parser.add_argument(
        "--search-battle-controller",
        choices=SEARCH_BATTLE_CONTROLLER_CHOICES,
        default=SEARCH_BATTLE_CONTROLLER_ORACLE,
        help=(
            "Battle child used by --lightspeed-search-battle-start-pool. "
            "The default preserves the T036/T037 Oracle-search source path; "
            "T049 may select post-search model-guided or root-prior guided search."
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
        "--assisted-source-arm",
        nargs=3,
        action="append",
        default=[],
        metavar=("LEVEL", "POOL_JSONL", "COVERAGE_JSON"),
        help=(
            "One T042 source-coverage arm. Required levels are assist_0, "
            "assist_hp25, assist_hp50, assist_hp50_potion_elite_boss, and "
            "assist_hp75_potion."
        ),
    )
    parser.add_argument(
        "--assisted-source-shard",
        type=Path,
        action="append",
        default=[],
        metavar="POOL_JSONL",
        help=(
            "One T042 assisted source-pool shard for --merge-assisted-source-pool. "
            "Repeat for every generated shard."
        ),
    )
    parser.add_argument(
        "--merged-assisted-source-pool",
        type=Path,
        metavar="POOL_JSONL",
        help=(
            "Merged T042 assisted source pool used by --merge-assisted-a20-coverage."
        ),
    )
    parser.add_argument(
        "--assisted-coverage-shard",
        type=Path,
        action="append",
        default=[],
        metavar="COVERAGE_JSON",
        help=(
            "One shard-level assisted A20 coverage report for "
            "--merge-assisted-a20-coverage. Repeat for every shard."
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
            "Write Oracle teacher scale-up teacher JSONL, T022 reports, and "
            "manifest artifacts under DIR."
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
        help="Seeded maximum number of source starts selected for scale-up.",
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
        "--search-budget",
        type=int,
        default=None,
        help=(
            "Native root playout budget for T046 root-prior allocation smoke. "
            "Defaults to --oracle-search-simulations when omitted."
        ),
    )
    parser.add_argument(
        "--root-prior-temperature",
        type=float,
        default=1.0,
        help="Prior temperature for --lightspeed-native-root-prior-allocation-smoke.",
    )
    parser.add_argument(
        "--root-prior-min-visits",
        type=int,
        default=1,
        help=(
            "Minimum root visits per eligible action for "
            "--lightspeed-native-root-prior-allocation-smoke."
        ),
    )
    parser.add_argument(
        "--root-prior-allocation-weight",
        type=float,
        default=1.0,
        help=(
            "Mixture weight for supplied priors in T046 root-prior allocation; "
            "0 is uniform and 1 is pure supplied-prior allocation after min visits."
        ),
    )
    parser.add_argument(
        "--root-prior-guardrail-uniform-blend-weight",
        type=float,
        default=0.35,
        help=(
            "T054 guardrail weight for mixing checkpoint priors with a uniform "
            "eligible-action prior before native root allocation."
        ),
    )
    parser.add_argument(
        "--root-prior-guardrail-max-prior-probability",
        type=float,
        default=0.65,
        help=(
            "T054 guardrail cap for any one eligible action's supplied root "
            "prior probability before native allocation."
        ),
    )
    parser.add_argument(
        "--root-prior-allocation-report",
        type=Path,
        metavar="PATH",
        help="Write the T046 native-root-prior-allocation-report-v1 JSON artifact.",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=1,
        help=(
            "Worker count for T047 root-prior guided fixed-cohort comparison. "
            "Use 1 for smoke/debug runs; scale evidence should report the "
            "chosen host-worker count."
        ),
    )
    parser.add_argument(
        "--shards",
        type=int,
        default=1,
        help=(
            "Cohort shard count for T047 root-prior guided fixed-cohort "
            "comparison. Defaults to a single shard for smoke/debug runs."
        ),
    )
    parser.add_argument(
        "--record-range",
        default=None,
        metavar="START:END",
        help=(
            "Optional zero-based end-exclusive cohort record range for a T047 "
            "comparison shard, for example 0:64. Omit to evaluate all records."
        ),
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
            "--lightspeed-model-guided-search-fixed-comparison or "
            "--lightspeed-model-guided-search-v2-fixed-comparison or "
            "--lightspeed-de-assisted-fixed-cohort-comparison or "
            "--lightspeed-root-prior-guided-search-comparison or "
            "--lightspeed-t055-guardrailed-root-prior-scale-comparison or "
            "--lightspeed-t059-root-prior-allocation-repair-comparison, or by "
            "--lightspeed-search-battle-start-pool when --search-battle-controller "
            "selects a checkpoint-guided controller."
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
        "--de-assisted-fixed-cohort-comparison-report",
        type=Path,
        metavar="PATH",
        help="Write the T044 de-assisted fixed-cohort comparison JSONL report.",
    )
    parser.add_argument(
        "--de-assisted-fixed-cohort-comparison-scale",
        choices=("smoke", "fixed"),
        default="smoke",
        help=(
            "Scale label recorded in the T044 comparison report. The default "
            "marks the run as smoke-scale evidence."
        ),
    )
    parser.add_argument(
        "--root-prior-guided-search-comparison-report",
        type=Path,
        metavar="PATH",
        help="Write the T047 root-prior guided search comparison JSONL report.",
    )
    parser.add_argument(
        "--t054-guardrailed-root-prior-comparison-report",
        type=Path,
        metavar="PATH",
        help="Write the T054 four-arm root-prior repair comparison JSONL report.",
    )
    parser.add_argument(
        "--t055-guardrailed-root-prior-comparison-report",
        type=Path,
        metavar="PATH",
        help="Write one T055 four-arm root-prior scale comparison JSONL report.",
    )
    parser.add_argument(
        "--t059-root-prior-allocation-repair-comparison-report",
        type=Path,
        metavar="PATH",
        help="Write one T059 four-arm root-prior repair comparison JSONL report.",
    )
    parser.add_argument(
        "--t062-battle-search-v2-comparison-report",
        type=Path,
        metavar="PATH",
        help="Write one T062 four-arm comparison JSON report.",
    )
    parser.add_argument(
        "--t062-battle-search-v2-family",
        choices=("nominal", "simulator_step_normalized", "wall_clock_normalized"),
        default="nominal",
        help="Compute-matching family recorded in a T062 comparison report.",
    )
    parser.add_argument(
        "--t062-arm-budget",
        action="append",
        default=[],
        metavar="ARM=PLAYOUTS",
        help=(
            "Override one T062 arm's native playout budget; repeat for baseline, "
            "prior_only, value_only, and/or prior_value."
        ),
    )
    parser.add_argument(
        "--t054-guardrailed-root-prior-repair-scale",
        choices=("smoke", "fixed"),
        default="smoke",
        help=(
            "Scale label recorded in the T054 guardrailed repair comparison. "
            "The default marks the run as smoke-scale evidence."
        ),
    )
    parser.add_argument(
        "--t055-guardrailed-root-prior-scale",
        choices=("smoke", "fixed"),
        default="smoke",
        help=(
            "Scale label recorded in a T055 guardrailed scale comparison. "
            "The default marks the run as smoke-scale evidence."
        ),
    )
    parser.add_argument(
        "--t059-root-prior-allocation-repair-scale",
        choices=("smoke", "fixed"),
        default="fixed",
        help=(
            "Scale label recorded in a T059 repair comparison. The default "
            "marks retained-cohort T059 evidence as fixed-scale."
        ),
    )
    parser.add_argument(
        "--t059-root-prior-repair-entropy-temperature",
        type=float,
        default=2.0,
        help=(
            "Fixed entropy temperature used by the T059 allocation repair prior "
            "transform before native root allocation."
        ),
    )
    parser.add_argument(
        "--root-prior-guided-search-comparison-scale",
        choices=("smoke", "fixed"),
        default="smoke",
        help=(
            "Scale label recorded in the T047 comparison report. The default "
            "marks the run as smoke-scale evidence."
        ),
    )
    parser.add_argument(
        "--root-prior-guided-search-comparison-task-id",
        default="T047",
        help=(
            "Task id recorded in the root-prior guided comparison config. "
            "Defaults to T047, which introduced the artifact schema."
        ),
    )
    parser.add_argument(
        "--root-prior-guided-search-comparison-shard",
        type=Path,
        action="append",
        default=[],
        metavar="JSONL",
        help=(
            "Input shard report for --merge-root-prior-guided-search-comparison. "
            "Repeat once per record-range shard."
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
