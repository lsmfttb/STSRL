"""T042 assisted complete-run source generation.

Assistance is an explicit data-generation distribution. It mutates the live
simulator only through the accepted native battle-start rebuild surface, keeps
provenance out of normal controller inputs, and records enough information for
portable replay to reapply the same assistance before restored battle starts.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field, replace
import hashlib
import json
import math
from pathlib import Path
from typing import Any, TextIO

from sts_combat_rl.sim.a20_battle_start_coverage import (
    A20CoverageCommandConfig,
    build_a20_battle_start_coverage_report,
    dump_a20_battle_start_coverage_report_json,
    format_a20_battle_start_coverage_report,
)
from sts_combat_rl.sim.action_space import ActionSpaceConfig
from sts_combat_rl.sim.battle_start_pool import (
    ASSISTED_RUN_DISTRIBUTION_KIND,
    BATTLE_START_POOL_FORMAT_VERSION,
    CHECKPOINT_INFORMATION_REGIME,
    BattleStartCheckpointRecord,
    BattleStartPoolCoverageReport,
    BattleStartPoolRestoreReport,
    NaturalBattleStartPool,
    SourceRunSummary,
    _build_source_run_summary,
    _public_context_for_snapshot,
    _snapshot_matches_record,
    _source_run_summaries_from_metadata,
    build_battle_start_pool_coverage_report,
    record_from_manifest,
    record_to_manifest,
)
from sts_combat_rl.sim.checkpoint_verification import is_battle_snapshot
from sts_combat_rl.sim.contract import (
    CheckpointingSimulatorAdapter,
    SimulatorAction,
    SimulatorCheckpoint,
    SimulatorSnapshot,
)
from sts_combat_rl.sim.controlled_run import ControlledRunStep, execute_controlled_run
from sts_combat_rl.sim.decision_record import (
    find_action_index_by_identity,
    source_metadata_from_snapshot,
)
from sts_combat_rl.sim.lightspeed_source import lightspeed_source_identity_dict
from sts_combat_rl.sim.online_controller import RoutedRunController
from sts_combat_rl.sim.public_context_artifacts import (
    PUBLIC_CONTEXT_AVAILABLE,
    sanitize_public_context_artifact,
)
from sts_combat_rl.sim.public_run_context import (
    append_public_history_entry,
    build_public_history_entry,
)
from sts_combat_rl.sim.reachability import (
    ReachabilityArmReport,
    build_reachability_arm_report,
)
from sts_combat_rl.sim.resource_outcome import (
    available_battle_resource_outcome,
    build_battle_resource_outcome,
    is_authoritative_terminal_battle_result,
    unavailable_battle_resource_outcome,
)


ASSISTANCE_SCHEDULE_VERSION = "assisted-run-assistance-schedule-v1"
ASSISTED_SOURCE_POOL_SCHEMA_ID = "assisted-run-source-pool-v1"
ASSISTED_SOURCE_POOL_FORMAT_VERSION = 1
ASSISTED_COVERAGE_COMPARISON_SCHEMA_ID = "assisted-run-source-coverage-comparison-v1"
ASSISTED_COVERAGE_COMPARISON_FORMAT_VERSION = 1
ASSISTED_SOURCE_REQUIRED_TERMINAL_RUNS = 1000

ASSIST_LEVEL_0 = "assist_0"
ASSIST_LEVEL_HP25 = "assist_hp25"
ASSIST_LEVEL_HP50 = "assist_hp50"
ASSIST_LEVEL_HP50_POTION_ELITE_BOSS = "assist_hp50_potion_elite_boss"
ASSIST_LEVEL_HP75_POTION = "assist_hp75_potion"
ASSISTANCE_LEVELS = (
    ASSIST_LEVEL_0,
    ASSIST_LEVEL_HP25,
    ASSIST_LEVEL_HP50,
    ASSIST_LEVEL_HP50_POTION_ELITE_BOSS,
    ASSIST_LEVEL_HP75_POTION,
)


@dataclass(frozen=True)
class AssistanceSchedule:
    """Versioned resource assistance settings for one T042 arm."""

    level: str
    hp_floor_fraction: float
    potion_rule: str = "none"
    coverage_only: bool = False
    version: str = ASSISTANCE_SCHEDULE_VERSION
    distribution_kind: str = ASSISTED_RUN_DISTRIBUTION_KIND
    distribution_tag: str = "resource_assisted_run"

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "level": self.level,
            "distribution_kind": self.distribution_kind,
            "distribution_tag": self.distribution_tag,
            "hp_floor_fraction": self.hp_floor_fraction,
            "potion_rule": self.potion_rule,
            "coverage_only": self.coverage_only,
        }


ASSISTANCE_SCHEDULES: Mapping[str, AssistanceSchedule] = {
    ASSIST_LEVEL_0: AssistanceSchedule(
        level=ASSIST_LEVEL_0,
        hp_floor_fraction=0.0,
        distribution_tag="expert_driver_assisted_run",
    ),
    ASSIST_LEVEL_HP25: AssistanceSchedule(
        level=ASSIST_LEVEL_HP25,
        hp_floor_fraction=0.25,
    ),
    ASSIST_LEVEL_HP50: AssistanceSchedule(
        level=ASSIST_LEVEL_HP50,
        hp_floor_fraction=0.50,
    ),
    ASSIST_LEVEL_HP50_POTION_ELITE_BOSS: AssistanceSchedule(
        level=ASSIST_LEVEL_HP50_POTION_ELITE_BOSS,
        hp_floor_fraction=0.50,
        potion_rule="elite_boss",
    ),
    ASSIST_LEVEL_HP75_POTION: AssistanceSchedule(
        level=ASSIST_LEVEL_HP75_POTION,
        hp_floor_fraction=0.75,
        potion_rule="any_battle",
        coverage_only=True,
    ),
}


@dataclass(frozen=True)
class AssistedSourcePoolArtifact:
    """One assisted complete-run source pool and its schedule provenance."""

    pool: NaturalBattleStartPool
    assistance_level: str
    assistance_schedule: AssistanceSchedule
    policy_seed: int
    assistance_decisions: tuple[dict[str, Any], ...] = ()
    schema_id: str = ASSISTED_SOURCE_POOL_SCHEMA_ID
    format_version: int = ASSISTED_SOURCE_POOL_FORMAT_VERSION
    source_pool_format_version: int = BATTLE_START_POOL_FORMAT_VERSION

    @property
    def records(self) -> list[BattleStartCheckpointRecord]:
        return self.pool.records


@dataclass(frozen=True)
class AssistedCoverageArmReport:
    """One schedule arm in the T042 source-coverage comparison."""

    assistance_level: str
    arm: ReachabilityArmReport
    schedule: AssistanceSchedule
    assistance_decision_counts: Counter[str] = field(default_factory=Counter)
    schedule_problems: tuple[str, ...] = ()

    @property
    def arm_passed(self) -> bool:
        return self.arm.arm_passed and not self.schedule_problems

    def to_dict(self) -> dict[str, Any]:
        payload = self.arm.to_dict()
        payload["assistance_level"] = self.assistance_level
        payload["assistance_schedule"] = self.schedule.to_dict()
        payload["assistance_decision_counts"] = _counter_dict(
            self.assistance_decision_counts
        )
        payload["schedule_problems"] = list(self.schedule_problems)
        payload["arm_passed"] = self.arm_passed
        return payload


@dataclass(frozen=True)
class AssistedSourceCoverageComparisonReport:
    """T042 coverage report comparing all required assistance schedules."""

    arms: tuple[AssistedCoverageArmReport, ...]
    source_identity: dict[str, Any]
    command_problems: tuple[str, ...] = ()
    schema_id: str = ASSISTED_COVERAGE_COMPARISON_SCHEMA_ID
    format_version: int = ASSISTED_COVERAGE_COMPARISON_FORMAT_VERSION

    @property
    def command_passed(self) -> bool:
        return not self.command_problems

    def to_dict(self) -> dict[str, Any]:
        comparison = _assisted_comparison_dict(self.arms)
        return {
            "schema_id": self.schema_id,
            "format_version": self.format_version,
            "source_identity": _json_safe_mapping(self.source_identity),
            "required_schedules": {
                level: schedule.to_dict()
                for level, schedule in ASSISTANCE_SCHEDULES.items()
            },
            "scale_target": {
                "terminal_source_runs_per_arm": ASSISTED_SOURCE_REQUIRED_TERMINAL_RUNS,
                "requires_zero_truncated_runs": True,
            },
            "arms": [arm.to_dict() for arm in self.arms],
            "comparison": comparison,
            "command_passed": self.command_passed,
            "command_problems": list(self.command_problems),
        }


def collect_assisted_battle_start_pool(
    adapter: CheckpointingSimulatorAdapter,
    controller: RoutedRunController,
    *,
    seeds: Iterable[int],
    max_steps: int = 200,
    action_space: ActionSpaceConfig | None = None,
    assistance_level: str,
    policy_seed: int,
) -> tuple[AssistedSourcePoolArtifact, BattleStartPoolCoverageReport]:
    """Collect battle starts while applying one explicit assistance schedule."""

    if max_steps <= 0:
        raise ValueError("assisted battle-start pool max_steps must be positive")
    if not adapter.supports_checkpoint_restore:
        raise ValueError("simulator does not support native checkpoint capture/restore")
    schedule = assistance_schedule_by_level(assistance_level)
    seed_list = [_require_seed(seed, "assisted collection seed") for seed in seeds]
    active_action_space = action_space or ActionSpaceConfig.initial_no_potions()
    records: list[BattleStartCheckpointRecord] = []
    source_run_summaries: list[SourceRunSummary] = []
    problems: list[str] = []
    all_assistance_decisions: list[dict[str, Any]] = []
    terminal_run_count = 0

    for run_index, seed in enumerate(seed_list):
        source_run_id = f"seed-{seed}-run-{run_index}"
        action_trace: list[dict[str, Any]] = []
        assistance_history: list[dict[str, Any]] = []
        active_record_index: int | None = None
        active_battle_started = False
        battle_index = 0
        run_record_start = len(records)
        run_problem_start = len(problems)

        def transform(
            current_adapter: CheckpointingSimulatorAdapter,
            snapshot: SimulatorSnapshot,
            step_index: int,
        ) -> SimulatorSnapshot:
            nonlocal active_battle_started
            if not is_battle_snapshot(snapshot):
                active_battle_started = False
                return snapshot
            if active_battle_started:
                return snapshot
            active_battle_started = True
            decision, transformed = _apply_assistance_schedule(
                current_adapter,
                snapshot,
                schedule=schedule,
                policy_seed=policy_seed,
                source_run_id=source_run_id,
                source_seed=seed,
                source_battle_index=battle_index,
                step_index=step_index,
            )
            assistance_history.append(decision)
            all_assistance_decisions.append(decision)
            return transformed

        def before_decision(
            snapshot: SimulatorSnapshot,
            actions: Sequence[SimulatorAction],
            context: object,
            step_index: int,
        ) -> None:
            del actions, step_index
            nonlocal active_record_index, battle_index
            if not is_battle_snapshot(snapshot) or active_record_index is not None:
                return
            public_run_context = _context_public_run_context(context)
            native_checkpoint = adapter.capture_checkpoint(snapshot)
            if not assistance_history:
                raise ValueError("assisted battle start missing assistance record")
            current_assistance = {
                **assistance_history[-1],
                "source_checkpoint_id": native_checkpoint.checkpoint_id,
                "source_record_index": len(records),
            }
            assistance_history[-1] = current_assistance
            all_assistance_decisions[-1] = current_assistance
            record = _build_assisted_record(
                record_index=len(records),
                source_checkpoint_id=native_checkpoint.checkpoint_id,
                source_run_id=source_run_id,
                source_seed=seed,
                source_battle_index=battle_index,
                snapshot=snapshot,
                action_trace=action_trace,
                controller=controller,
                native_checkpoint=native_checkpoint,
                public_run_context=public_run_context,
                assistance_history=assistance_history,
                schedule=schedule,
            )
            records.append(record)
            active_record_index = record.record_index
            battle_index += 1

        def after_transition(step: ControlledRunStep) -> None:
            nonlocal active_record_index
            action_trace.append(dict(step.chosen_action_identity))
            if active_record_index is None:
                return
            if step.next_battle_active and not step.terminal_after_step:
                return
            record = records[active_record_index]
            if is_authoritative_terminal_battle_result(step.next_battle_outcome):
                outcome_status, outcome_payload = available_battle_resource_outcome(
                    build_battle_resource_outcome(
                        record.snapshot_raw,
                        step.next_snapshot_raw,
                        battle_result=step.next_battle_outcome,
                    )
                )
                records[active_record_index] = replace(
                    record,
                    battle_outcome=step.next_battle_outcome,
                    battle_completed=True,
                    completed_battle_resource_outcome_status=outcome_status,
                    completed_battle_resource_outcome=outcome_payload,
                )
            else:
                unavailable_reason = (
                    "missing_authoritative_battle_outcome"
                    if step.next_battle_outcome is None
                    else "unrecognized_terminal_battle_outcome"
                )
                outcome_status, outcome_payload = unavailable_battle_resource_outcome(
                    unavailable_reason
                )
                records[active_record_index] = replace(
                    record,
                    battle_outcome=step.next_battle_outcome,
                    battle_completed=False,
                    completed_battle_resource_outcome_status=outcome_status,
                    completed_battle_resource_outcome=outcome_payload,
                )
                problems.append(
                    f"{source_run_id}: battle {record.source_battle_index} ended "
                    "without authoritative terminal outcome"
                )
            active_record_index = None

        controlled = execute_controlled_run(
            adapter,
            controller,
            seed=seed,
            max_steps=max_steps,
            action_space=active_action_space,
            before_decision_transform=transform,
            before_decision=before_decision,
            after_transition=after_transition,
        )
        problems.extend(
            f"{source_run_id}: {problem}" for problem in controlled.problems
        )
        if controlled.terminal:
            terminal_run_count += 1
        source_run_summaries.append(
            _build_source_run_summary(
                source_run_id=source_run_id,
                source_seed=seed,
                controlled=controlled,
                records=records[run_record_start:],
                run_problems=problems[run_problem_start:],
            )
        )

    pool = NaturalBattleStartPool(
        source_run_count=len(seed_list),
        terminal_run_count=terminal_run_count,
        truncated_run_count=len(seed_list) - terminal_run_count,
        source_controller_provenance=controller.provenance.to_dict(),
        records=records,
        source_run_summaries=source_run_summaries,
        problems=list(dict.fromkeys(problems)),
    )
    artifact = AssistedSourcePoolArtifact(
        pool=pool,
        assistance_level=assistance_level,
        assistance_schedule=schedule,
        policy_seed=policy_seed,
        assistance_decisions=tuple(all_assistance_decisions),
    )
    artifact_problems = assisted_source_pool_problems(artifact)
    if artifact_problems:
        pool = replace(
            pool, problems=list(dict.fromkeys([*pool.problems, *artifact_problems]))
        )
        artifact = replace(artifact, pool=pool)
    return artifact, build_battle_start_pool_coverage_report(pool)


def assistance_schedule_by_level(level: str) -> AssistanceSchedule:
    """Return the current T042 schedule for ``level``."""

    try:
        return ASSISTANCE_SCHEDULES[level]
    except KeyError as exc:
        raise ValueError(f"unknown assistance level: {level}") from exc


def dump_assisted_source_pool_jsonl(
    artifact: AssistedSourcePoolArtifact,
    stream: TextIO,
) -> None:
    """Write the current assisted source-pool JSONL schema."""

    problems = assisted_source_pool_problems(artifact)
    if problems:
        raise ValueError("invalid assisted source pool: " + "; ".join(problems))
    metadata = {
        "schema_id": artifact.schema_id,
        "format_version": artifact.format_version,
        "source_pool_format_version": artifact.source_pool_format_version,
        "distribution_kind": ASSISTED_RUN_DISTRIBUTION_KIND,
        "assistance_level": artifact.assistance_level,
        "assistance_schedule": artifact.assistance_schedule.to_dict(),
        "policy_seed": artifact.policy_seed,
        "source_run_count": artifact.pool.source_run_count,
        "terminal_run_count": artifact.pool.terminal_run_count,
        "truncated_run_count": artifact.pool.truncated_run_count,
        "source_controller_provenance": artifact.pool.source_controller_provenance,
        "record_count": len(artifact.pool.records),
        "assistance_decision_count": len(artifact.assistance_decisions),
        "assistance_decisions": [
            _json_safe_mapping(decision) for decision in artifact.assistance_decisions
        ],
        "source_run_summaries": [
            summary.to_dict() for summary in artifact.pool.source_run_summaries
        ],
        "migration_report": artifact.pool.migration_report.to_dict(),
        "problems": list(artifact.pool.problems),
    }
    _write_row(stream, {"type": "metadata", "metadata": metadata})
    for record in artifact.pool.records:
        _write_row(stream, {"type": "record", "record": record_to_manifest(record)})


def load_assisted_source_pool_jsonl(stream: TextIO) -> AssistedSourcePoolArtifact:
    """Load a current assisted source-pool JSONL artifact."""

    metadata: dict[str, Any] | None = None
    raw_records: list[dict[str, Any]] = []
    for line_number, raw_line in enumerate(stream, start=1):
        if not raw_line.strip():
            continue
        try:
            row = json.loads(raw_line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"line {line_number}: invalid JSON") from exc
        if not isinstance(row, dict):
            raise ValueError(f"line {line_number}: row must be an object")
        if row.get("type") == "metadata":
            if metadata is not None:
                raise ValueError(f"line {line_number}: duplicate metadata")
            metadata = _require_mapping(row.get("metadata"), "metadata")
        elif row.get("type") == "record":
            raw_records.append(_require_mapping(row.get("record"), "record"))
        else:
            raise ValueError(f"line {line_number}: unknown row type")
    if metadata is None:
        raise ValueError("missing assisted source-pool metadata")
    if metadata.get("schema_id") != ASSISTED_SOURCE_POOL_SCHEMA_ID:
        raise ValueError("assisted source-pool schema_id is unsupported")
    if metadata.get("format_version") != ASSISTED_SOURCE_POOL_FORMAT_VERSION:
        raise ValueError("assisted source-pool format_version is unsupported")
    level = _require_non_empty_string(
        metadata.get("assistance_level"),
        "assistance_level",
    )
    schedule = assistance_schedule_by_level(level)
    if metadata.get("record_count") != len(raw_records):
        raise ValueError("assisted source-pool metadata record_count mismatch")
    records = [
        record_from_manifest(
            raw,
            label=f"record {index}",
            allowed_distribution_kinds=frozenset({ASSISTED_RUN_DISTRIBUTION_KIND}),
            allow_assistance_history=True,
        )
        for index, raw in enumerate(raw_records)
    ]
    if any(record.record_index != index for index, record in enumerate(records)):
        raise ValueError("assisted source-pool record indices must be contiguous")
    source_run_summaries = _source_run_summaries_from_metadata(
        metadata.get("source_run_summaries", []),
        label="source_run_summaries",
    )
    assistance_decisions = tuple(
        _require_mapping(item, f"assistance decision {index}")
        for index, item in enumerate(
            _require_list(
                metadata.get("assistance_decisions", []), "assistance_decisions"
            )
        )
    )
    pool = NaturalBattleStartPool(
        source_run_count=_require_non_negative_int(
            metadata.get("source_run_count"),
            "source_run_count",
        ),
        terminal_run_count=_require_non_negative_int(
            metadata.get("terminal_run_count"),
            "terminal_run_count",
        ),
        truncated_run_count=_require_non_negative_int(
            metadata.get("truncated_run_count"),
            "truncated_run_count",
        ),
        source_controller_provenance=_require_mapping(
            metadata.get("source_controller_provenance"),
            "source_controller_provenance",
        ),
        records=records,
        source_run_summaries=source_run_summaries,
        problems=_require_string_list(metadata.get("problems", []), "problems"),
    )
    artifact = AssistedSourcePoolArtifact(
        pool=pool,
        assistance_level=level,
        assistance_schedule=schedule,
        policy_seed=_require_seed(metadata.get("policy_seed"), "policy_seed"),
        assistance_decisions=assistance_decisions,
    )
    problems = assisted_source_pool_problems(artifact)
    if problems:
        raise ValueError("invalid assisted source pool: " + "; ".join(problems))
    return artifact


def assisted_source_pool_problems(
    artifact: AssistedSourcePoolArtifact,
) -> list[str]:
    """Return structural problems for an assisted source-pool artifact."""

    problems: list[str] = []
    if artifact.schema_id != ASSISTED_SOURCE_POOL_SCHEMA_ID:
        problems.append("assisted source pool schema_id is unsupported")
    if artifact.format_version != ASSISTED_SOURCE_POOL_FORMAT_VERSION:
        problems.append("assisted source pool format_version is unsupported")
    if artifact.source_pool_format_version != BATTLE_START_POOL_FORMAT_VERSION:
        problems.append("assisted source pool source format_version is unsupported")
    if artifact.assistance_schedule.level != artifact.assistance_level:
        problems.append("assistance schedule level does not match artifact level")
    if artifact.assistance_level not in ASSISTANCE_SCHEDULES:
        problems.append("assistance level is not a current T042 schedule")
    if (
        artifact.pool.terminal_run_count + artifact.pool.truncated_run_count
        != artifact.pool.source_run_count
    ):
        problems.append("terminal and truncated run counts do not match source runs")
    if len(artifact.assistance_decisions) < len(artifact.pool.records):
        problems.append("assistance decision count is smaller than record count")
    for index, record in enumerate(artifact.pool.records):
        if record.record_index != index:
            problems.append(f"record {index} index is not contiguous")
        if record.distribution_kind != ASSISTED_RUN_DISTRIBUTION_KIND:
            problems.append(f"record {index} is not tagged assisted_run")
        structural = record.structural_metadata
        if structural.get("source_kind") != ASSISTED_RUN_DISTRIBUTION_KIND:
            problems.append(f"record {index} source_kind is not assisted_run")
        if structural.get("distribution_kind") != ASSISTED_RUN_DISTRIBUTION_KIND:
            problems.append(f"record {index} distribution_kind is not assisted_run")
        if structural.get("assistance_level") != artifact.assistance_level:
            problems.append(f"record {index} assistance level mismatch")
        if not record.assistance_history:
            problems.append(f"record {index} missing assistance history")
        for history_index, decision in enumerate(record.assistance_history):
            problems.extend(
                _assistance_decision_problems(
                    decision,
                    label=f"record {index} assistance {history_index}",
                    expected_level=artifact.assistance_level,
                )
            )
    for index, decision in enumerate(artifact.assistance_decisions):
        problems.extend(
            _assistance_decision_problems(
                decision,
                label=f"assistance decision {index}",
                expected_level=artifact.assistance_level,
            )
        )
    return list(dict.fromkeys([*artifact.pool.problems, *problems]))


def verify_assisted_source_pool_restores(
    adapter_factory: Callable[[], CheckpointingSimulatorAdapter],
    artifact: AssistedSourcePoolArtifact,
    *,
    limit: int = 0,
) -> BattleStartPoolRestoreReport:
    """Verify assisted records by replaying actions and assistance transforms."""

    if limit < 0:
        raise ValueError("assisted source restore limit cannot be negative")
    selected = artifact.pool.records if limit == 0 else artifact.pool.records[:limit]
    restored_count = 0
    replay_count = 0
    context_compared_count = 0
    context_matched_count = 0
    context_legacy_unavailable_count = 0
    context_mismatch_count = 0
    problems: list[str] = []
    for record in selected:
        if record.public_context_status == PUBLIC_CONTEXT_AVAILABLE:
            context_compared_count += 1
        else:
            context_legacy_unavailable_count += 1
        try:
            restored, replayed_context = _restore_assisted_by_seed_action_trace(
                adapter_factory(),
                record,
            )
            if not _snapshot_matches_record(restored, record):
                raise ValueError(
                    f"record {record.record_index}: restored snapshot does not "
                    "match assisted source"
                )
            if record.public_context_status == PUBLIC_CONTEXT_AVAILABLE:
                expected = sanitize_public_context_artifact(
                    record.public_run_context,
                    label=f"record {record.record_index}",
                )
                if expected != replayed_context:
                    raise ValueError(
                        f"record {record.record_index}: public context replay mismatch"
                    )
        except (RuntimeError, ValueError) as exc:
            problems.append(f"record {record.record_index}: {exc}")
            if record.public_context_status == PUBLIC_CONTEXT_AVAILABLE:
                context_mismatch_count += 1
            continue
        restored_count += 1
        replay_count += 1
        if record.public_context_status == PUBLIC_CONTEXT_AVAILABLE:
            context_matched_count += 1
    return BattleStartPoolRestoreReport(
        checkpoint_count=len(artifact.pool.records),
        requested_limit=limit,
        restored_count=restored_count,
        native_restored_count=0,
        replay_restored_count=replay_count,
        context_compared_count=context_compared_count,
        context_matched_count=context_matched_count,
        context_legacy_unavailable_count=context_legacy_unavailable_count,
        context_mismatch_count=context_mismatch_count,
        problems=problems,
    )


def build_assisted_source_coverage_comparison_report(
    arm_inputs: Sequence[
        tuple[str, AssistedSourcePoolArtifact, Mapping[str, Any], Mapping[str, Any]]
    ],
) -> AssistedSourceCoverageComparisonReport:
    """Build the T042 comparison from assisted pools and coverage reports."""

    levels = [level for level, _, _, _ in arm_inputs]
    command_problems = _assistance_level_set_problems(levels)
    arm_reports: list[AssistedCoverageArmReport] = []
    for level, artifact, coverage_report, artifact_identity in arm_inputs:
        reachability_arm = build_reachability_arm_report(
            label=level,
            pool=artifact.pool,
            coverage_report=coverage_report,
            artifact_identity=artifact_identity,
        )
        arm_reports.append(
            AssistedCoverageArmReport(
                assistance_level=level,
                arm=reachability_arm,
                schedule=artifact.assistance_schedule,
                assistance_decision_counts=_assistance_decision_counts(artifact),
                schedule_problems=tuple(_schedule_contract_problems(level, artifact)),
            )
        )
    source_identity = dict(arm_reports[0].arm.source_identity) if arm_reports else {}
    for arm in arm_reports:
        command_problems.extend(
            f"{arm.assistance_level}: {problem}" for problem in arm.arm.problems
        )
        command_problems.extend(
            f"{arm.assistance_level}: {problem}" for problem in arm.schedule_problems
        )
    return AssistedSourceCoverageComparisonReport(
        arms=tuple(arm_reports),
        source_identity=source_identity,
        command_problems=tuple(dict.fromkeys(command_problems)),
    )


def dump_assisted_source_coverage_comparison_report_json(
    report: AssistedSourceCoverageComparisonReport,
    stream: TextIO,
) -> None:
    """Write a deterministic T042 comparison report."""

    json.dump(report.to_dict(), stream, indent=2, sort_keys=True)
    stream.write("\n")


def format_assisted_source_coverage_comparison_report(
    report: AssistedSourceCoverageComparisonReport,
) -> str:
    """Format compact stderr evidence for the T042 comparison report."""

    comparison = _assisted_comparison_dict(report.arms)
    lines = [
        "Assisted complete-run source-coverage comparison",
        f"schema: {report.schema_id} v{report.format_version}",
        f"command passed: {_yes_no(report.command_passed)}",
        "arms:",
    ]
    for arm in report.arms:
        lines.append(f"  {arm.assistance_level}:")
        lines.append(f"    schedule: {arm.schedule.version}")
        lines.append(f"    hp floor fraction: {arm.schedule.hp_floor_fraction}")
        lines.append(f"    potion rule: {arm.schedule.potion_rule}")
        lines.append(f"    coverage only: {_yes_no(arm.schedule.coverage_only)}")
        lines.append(f"    terminal source runs: {arm.arm.terminal_run_count}")
        lines.append(f"    truncated source runs: {arm.arm.truncated_run_count}")
        lines.append(f"    battle starts: {arm.arm.natural_battle_start_count}")
        lines.append(f"    Act 1 Boss starts: {arm.arm.act1_boss_battle_start_count}")
        lines.append(f"    later-act starts: {arm.arm.later_act_battle_start_count}")
        lines.append(
            "    restore ok: "
            f"{arm.arm.restore_verification.get('restore_ok', '(unreported)')}"
        )
        lines.append(
            "    T009 broad training allowed: "
            f"{_nested_get(arm.arm.training_gate_report, 'broad_training_allowed')}"
        )
        _append_counter(
            lines, "    assistance decisions", arm.assistance_decision_counts
        )
        _append_problem_list(lines, "    schedule problems", arm.schedule_problems)
        _append_problem_list(lines, "    arm problems", arm.arm.problems)
    lines.append("comparison:")
    for key, value in comparison.items():
        lines.append(f"  {key}: {value}")
    _append_problem_list(lines, "command problems", report.command_problems)
    return "\n".join(lines)


def build_assisted_a20_coverage_report(
    artifact: AssistedSourcePoolArtifact,
    *,
    restore_report: BattleStartPoolRestoreReport,
    command_config: A20CoverageCommandConfig | None = None,
    input_artifacts: Mapping[str, Any] | None = None,
    source_identity: Mapping[str, Any] | None = None,
):
    """Build an A20 coverage report for an assisted source pool."""

    return build_a20_battle_start_coverage_report(
        artifact.pool,
        restore_report=restore_report,
        command_config=command_config,
        input_artifacts=input_artifacts,
        source_identity=source_identity or lightspeed_source_identity_dict(),
    )


def write_assisted_source_pool(
    path: Path, artifact: AssistedSourcePoolArtifact
) -> None:
    """Write an assisted source-pool artifact to ``path``."""

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as stream:
        dump_assisted_source_pool_jsonl(artifact, stream)


def write_assisted_a20_coverage_report(
    path: Path,
    report: Any,
) -> None:
    """Write an assisted-pool A20 coverage report."""

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as stream:
        dump_a20_battle_start_coverage_report_json(report, stream)


def format_assisted_a20_coverage_report(report: Any) -> str:
    """Format an assisted-pool A20 coverage report."""

    return format_a20_battle_start_coverage_report(report)


def _apply_assistance_schedule(
    adapter: CheckpointingSimulatorAdapter,
    snapshot: SimulatorSnapshot,
    *,
    schedule: AssistanceSchedule,
    policy_seed: int,
    source_run_id: str,
    source_seed: int,
    source_battle_index: int,
    step_index: int,
) -> tuple[dict[str, Any], SimulatorSnapshot]:
    before_resources = _resource_snapshot(snapshot.raw)
    requested = _requested_change(snapshot.raw, schedule)
    base_decision = {
        "schema_id": "assisted-run-assistance-decision-v1",
        "assistance_version": schedule.version,
        "assistance_level": schedule.level,
        "policy_seed": policy_seed,
        "distribution_kind": schedule.distribution_kind,
        "distribution_tag": schedule.distribution_tag,
        "information_regime": CHECKPOINT_INFORMATION_REGIME,
        "source_run_id": source_run_id,
        "source_seed": source_seed,
        "source_battle_index": source_battle_index,
        "step_index": step_index,
        "screen_state": snapshot.raw.get("screen_state"),
        "act": snapshot.raw.get("act"),
        "floor": snapshot.raw.get("floor_num", snapshot.raw.get("floor")),
        "room_type": snapshot.raw.get("room_type"),
        "encounter_id": snapshot.raw.get("encounter_id"),
        "before_resources": before_resources,
        "requested_change": requested,
    }
    if not requested["native_rebuild_requested"]:
        return (
            {
                **base_decision,
                "actual_change": {
                    "applied": False,
                    "reason": requested["reason"],
                    "native_rebuild_called": False,
                },
                "after_resources": before_resources,
                "native_support_status": "not_requested",
                "problems": [],
            },
            snapshot,
        )

    rebuild = getattr(adapter, "rebuild_battle_start", None)
    if not callable(rebuild):
        return (
            {
                **base_decision,
                "actual_change": {
                    "applied": False,
                    "reason": "unsupported_native_operation",
                    "operation": "rebuild_battle_start",
                    "native_rebuild_called": False,
                },
                "after_resources": before_resources,
                "native_support_status": "unsupported",
                "problems": [],
            },
            snapshot,
        )
    try:
        transformed = rebuild(
            snapshot,
            hp_bonus=int(requested["hp_bonus"]),
            add_random_potion=bool(requested["add_random_potion"]),
            encounter_id=None,
        )
    except RuntimeError as exc:
        return (
            {
                **base_decision,
                "actual_change": {
                    "applied": False,
                    "reason": "native_error",
                    "error": str(exc),
                    "native_rebuild_called": False,
                },
                "after_resources": before_resources,
                "native_support_status": "error",
                "problems": [str(exc)],
            },
            snapshot,
        )
    after_resources = _resource_snapshot(transformed.raw)
    actual = _actual_change(before_resources, after_resources)
    actual.update(
        {
            "requested_hp_bonus": requested["hp_bonus"],
            "requested_add_random_potion": requested["add_random_potion"],
            "native_rebuild_called": True,
        }
    )
    return (
        {
            **base_decision,
            "actual_change": actual,
            "after_resources": after_resources,
            "native_support_status": "supported",
            "problems": [],
        },
        transformed,
    )


def _requested_change(
    raw: Mapping[str, Any],
    schedule: AssistanceSchedule,
) -> dict[str, Any]:
    current_hp = _optional_int(_first_value(raw, "cur_hp", "current_hp"))
    max_hp = _optional_int(_first_value(raw, "max_hp", "player_max_hp"))
    hp_floor = 0
    hp_bonus = 0
    if current_hp is not None and max_hp is not None and schedule.hp_floor_fraction > 0:
        hp_floor = min(max_hp, math.ceil(max_hp * schedule.hp_floor_fraction))
        hp_bonus = max(0, hp_floor - current_hp)
    potion_requested = _potion_requested(raw, schedule)
    requested = {
        "hp_floor_fraction": schedule.hp_floor_fraction,
        "hp_floor": hp_floor,
        "hp_bonus": hp_bonus,
        "potion_rule": schedule.potion_rule,
        "add_random_potion": potion_requested,
        "encounter_id": None,
        "native_rebuild_requested": hp_bonus > 0 or potion_requested,
    }
    if schedule.level == ASSIST_LEVEL_0:
        requested["reason"] = "assist_0_no_assistance"
    elif not requested["native_rebuild_requested"]:
        requested["reason"] = "resources_already_satisfy_schedule"
    else:
        requested["reason"] = "schedule_requested_native_rebuild"
    return requested


def _potion_requested(raw: Mapping[str, Any], schedule: AssistanceSchedule) -> bool:
    if schedule.potion_rule == "none":
        return False
    room_type = str(raw.get("room_type", "")).upper()
    if schedule.potion_rule == "elite_boss" and room_type not in {"ELITE", "BOSS"}:
        return False
    if schedule.potion_rule not in {"elite_boss", "any_battle"}:
        return False
    return _potion_count(raw) < _potion_capacity(raw)


def _build_assisted_record(
    *,
    record_index: int,
    source_checkpoint_id: str,
    source_run_id: str,
    source_seed: int,
    source_battle_index: int,
    snapshot: SimulatorSnapshot,
    action_trace: Sequence[Mapping[str, Any]],
    controller: RoutedRunController,
    native_checkpoint: SimulatorCheckpoint,
    public_run_context: Mapping[str, Any],
    assistance_history: Sequence[Mapping[str, Any]],
    schedule: AssistanceSchedule,
) -> BattleStartCheckpointRecord:
    structural = source_metadata_from_snapshot(
        snapshot.raw,
        seed=source_seed,
        source_kind=ASSISTED_RUN_DISTRIBUTION_KIND,
    )
    structural.update(
        {
            "source_run_id": source_run_id,
            "source_battle_index": source_battle_index,
            "assistance_level": schedule.level,
            "assistance_version": schedule.version,
            "distribution_tag": schedule.distribution_tag,
        }
    )
    resource_outcome_status, resource_outcome = unavailable_battle_resource_outcome(
        "battle_not_completed_during_collection"
    )
    return BattleStartCheckpointRecord(
        record_index=record_index,
        source_checkpoint_id=source_checkpoint_id,
        source_run_id=source_run_id,
        source_seed=source_seed,
        source_battle_index=source_battle_index,
        structural_metadata=structural,
        source_controller_provenance=controller.provenance.to_dict(),
        source_battle_controller_provenance=controller.battle.provenance.to_dict(),
        source_non_combat_controller_provenance=(
            controller.non_combat.provenance.to_dict()
        ),
        action_trace=tuple(dict(identity) for identity in action_trace),
        snapshot_observation=tuple(snapshot.observation),
        snapshot_raw=dict(snapshot.raw),
        completed_battle_resource_outcome_status=resource_outcome_status,
        completed_battle_resource_outcome=resource_outcome,
        distribution_kind=ASSISTED_RUN_DISTRIBUTION_KIND,
        public_context_status=PUBLIC_CONTEXT_AVAILABLE,
        public_run_context=sanitize_public_context_artifact(
            public_run_context,
            label=f"assisted record {record_index}",
        ),
        assistance_history=tuple(
            _json_safe_mapping(item) for item in assistance_history
        ),
        native_checkpoint=native_checkpoint,
    )


def _restore_assisted_by_seed_action_trace(
    adapter: CheckpointingSimulatorAdapter,
    record: BattleStartCheckpointRecord,
) -> tuple[SimulatorSnapshot, dict[str, Any]]:
    snapshot = adapter.reset(seed=record.source_seed)
    public_history: list[dict[str, Any]] = []
    active_battle_started = False
    next_battle_index = 0
    assistance_by_battle = _assistance_by_battle_index(record.assistance_history)

    for trace_index, identity in enumerate(record.action_trace):
        if is_battle_snapshot(snapshot):
            if not active_battle_started:
                snapshot = _replay_assistance(
                    adapter,
                    snapshot,
                    assistance_by_battle.get(next_battle_index),
                )
                active_battle_started = True
                next_battle_index += 1
        else:
            active_battle_started = False
        actions = list(adapter.legal_actions(snapshot))
        pre_context = _public_context_for_snapshot(
            adapter,
            snapshot,
            actions,
            history=public_history,
            include_candidates=True,
        )
        action_index = find_action_index_by_identity(actions, identity)
        transition = adapter.step(actions[action_index])
        post_context = _public_context_for_snapshot(
            adapter,
            transition.snapshot,
            (),
            history=public_history,
            include_candidates=False,
        )
        entry = build_public_history_entry(
            history_index=len(public_history),
            step_index=trace_index,
            pre_context=pre_context,
            post_context=post_context,
            selected_action_index=action_index,
        )
        public_history = append_public_history_entry(public_history, entry)
        snapshot = transition.snapshot

    if is_battle_snapshot(snapshot) and not active_battle_started:
        snapshot = _replay_assistance(
            adapter,
            snapshot,
            assistance_by_battle.get(next_battle_index),
        )
    final_context = _public_context_for_snapshot(
        adapter,
        snapshot,
        list(adapter.legal_actions(snapshot)),
        history=public_history,
        include_candidates=True,
    )
    return snapshot, sanitize_public_context_artifact(
        final_context,
        label=f"assisted record {record.record_index} replay context",
    )


def _replay_assistance(
    adapter: CheckpointingSimulatorAdapter,
    snapshot: SimulatorSnapshot,
    decision: Mapping[str, Any] | None,
) -> SimulatorSnapshot:
    if decision is None:
        return snapshot
    actual = _mapping(decision.get("actual_change"), "actual_change")
    if not actual.get("native_rebuild_called"):
        return snapshot
    requested = _mapping(decision.get("requested_change"), "requested_change")
    rebuild = getattr(adapter, "rebuild_battle_start", None)
    if not callable(rebuild):
        raise RuntimeError("rebuild_battle_start unavailable during assisted replay")
    return rebuild(
        snapshot,
        hp_bonus=_require_non_negative_int(requested.get("hp_bonus"), "hp_bonus"),
        add_random_potion=bool(requested.get("add_random_potion")),
        encounter_id=None,
    )


def _resource_snapshot(raw: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "current_hp": _optional_int(_first_value(raw, "cur_hp", "current_hp")),
        "max_hp": _optional_int(_first_value(raw, "max_hp", "player_max_hp")),
        "gold": _optional_int(raw.get("gold")),
        "potion_count": _potion_count(raw),
        "potion_capacity": _potion_capacity(raw),
        "potion_identities": _potion_identities(raw),
        "act": raw.get("act"),
        "floor": raw.get("floor_num", raw.get("floor")),
        "room_type": raw.get("room_type"),
        "encounter_id": raw.get("encounter_id"),
    }


def _actual_change(
    before: Mapping[str, Any],
    after: Mapping[str, Any],
) -> dict[str, Any]:
    before_hp = _optional_int(before.get("current_hp"))
    after_hp = _optional_int(after.get("current_hp"))
    before_potions = _optional_int(before.get("potion_count")) or 0
    after_potions = _optional_int(after.get("potion_count")) or 0
    hp_delta = 0 if before_hp is None or after_hp is None else after_hp - before_hp
    potion_delta = after_potions - before_potions
    return {
        "applied": hp_delta > 0 or potion_delta > 0,
        "reason": "native_rebuild_applied"
        if hp_delta > 0 or potion_delta > 0
        else "native_rebuild_no_visible_change",
        "current_hp_delta": hp_delta,
        "potion_count_delta": potion_delta,
        "before_current_hp": before_hp,
        "after_current_hp": after_hp,
        "before_potion_count": before_potions,
        "after_potion_count": after_potions,
    }


def _assistance_by_battle_index(
    history: Sequence[Mapping[str, Any]],
) -> dict[int, Mapping[str, Any]]:
    result: dict[int, Mapping[str, Any]] = {}
    for decision in history:
        battle_index = decision.get("source_battle_index")
        if isinstance(battle_index, int) and not isinstance(battle_index, bool):
            result[battle_index] = decision
    return result


def _assistance_decision_counts(
    artifact: AssistedSourcePoolArtifact,
) -> Counter[str]:
    counts: Counter[str] = Counter()
    for decision in artifact.assistance_decisions:
        actual = _mapping(decision.get("actual_change"), "actual_change")
        status = str(decision.get("native_support_status", "unknown"))
        reason = str(actual.get("reason", "unknown"))
        counts[f"{status}:{reason}"] += 1
    return counts


def _schedule_contract_problems(
    level: str,
    artifact: AssistedSourcePoolArtifact,
) -> list[str]:
    problems: list[str] = []
    expected = ASSISTANCE_SCHEDULES.get(level)
    if expected is None:
        problems.append("unknown assistance level")
        return problems
    if artifact.assistance_level != level:
        problems.append("artifact assistance level does not match arm level")
    if artifact.assistance_schedule.to_dict() != expected.to_dict():
        problems.append("artifact assistance schedule does not match current contract")
    distributions = {record.distribution_kind for record in artifact.records}
    if distributions != {ASSISTED_RUN_DISTRIBUTION_KIND} and artifact.records:
        problems.append("assisted arm contains non-assisted distribution rows")
    return problems


def _assistance_level_set_problems(levels: Sequence[str]) -> list[str]:
    problems: list[str] = []
    if len(set(levels)) != len(levels):
        problems.append("assisted source coverage assistance levels must be unique")
    expected = set(ASSISTANCE_LEVELS)
    observed = set(levels)
    missing = sorted(expected - observed)
    extra = sorted(observed - expected)
    if missing:
        problems.append(
            "missing required T042 assistance level(s): " + ", ".join(missing)
        )
    if extra:
        problems.append("unknown T042 assistance level(s): " + ", ".join(extra))
    return problems


def _assisted_comparison_dict(
    arms: Sequence[AssistedCoverageArmReport],
) -> dict[str, Any]:
    by_level = {arm.assistance_level: arm for arm in arms}
    baseline = by_level.get(ASSIST_LEVEL_0)
    result: dict[str, Any] = {
        "baseline_level": ASSIST_LEVEL_0,
        "required_levels_present": all(
            level in by_level for level in ASSISTANCE_LEVELS
        ),
    }
    baseline_later = _later_count(baseline)
    baseline_boss = _boss_count(baseline)
    best_later = None
    best_later_level = None
    best_boss = None
    best_boss_level = None
    for arm in arms:
        later = arm.arm.later_act_battle_start_count
        boss = arm.arm.act1_boss_battle_start_count
        if best_later is None or later > best_later:
            best_later = later
            best_later_level = arm.assistance_level
        if best_boss is None or boss > best_boss:
            best_boss = boss
            best_boss_level = arm.assistance_level
        result[f"{arm.assistance_level}_later_act_start_count"] = later
        result[f"{arm.assistance_level}_act1_boss_start_count"] = boss
        result[f"{arm.assistance_level}_scale_target_met"] = (
            arm.arm.terminal_run_count >= ASSISTED_SOURCE_REQUIRED_TERMINAL_RUNS
            and arm.arm.truncated_run_count == 0
        )
    result["best_later_act_level"] = best_later_level
    result["best_later_act_start_count"] = best_later
    result["best_act1_boss_level"] = best_boss_level
    result["best_act1_boss_start_count"] = best_boss
    result["best_later_act_delta_vs_assist_0"] = (
        None
        if baseline_later is None or best_later is None
        else best_later - baseline_later
    )
    result["best_act1_boss_delta_vs_assist_0"] = (
        None
        if baseline_boss is None or best_boss is None
        else best_boss - baseline_boss
    )
    result["assisted_later_act_objective_met"] = (
        baseline_later is not None
        and best_later is not None
        and best_later > baseline_later
    )
    return result


def _later_count(arm: AssistedCoverageArmReport | None) -> int | None:
    return None if arm is None else arm.arm.later_act_battle_start_count


def _boss_count(arm: AssistedCoverageArmReport | None) -> int | None:
    return None if arm is None else arm.arm.act1_boss_battle_start_count


def _assistance_decision_problems(
    decision: Mapping[str, Any],
    *,
    label: str,
    expected_level: str,
) -> list[str]:
    problems: list[str] = []
    required = (
        "assistance_version",
        "assistance_level",
        "policy_seed",
        "distribution_kind",
        "information_regime",
        "source_run_id",
        "source_seed",
        "source_battle_index",
        "before_resources",
        "requested_change",
        "actual_change",
        "after_resources",
        "native_support_status",
    )
    missing = [field for field in required if field not in decision]
    if missing:
        problems.append(f"{label} missing: {', '.join(missing)}")
    if decision.get("assistance_level") != expected_level:
        problems.append(f"{label} assistance level mismatch")
    if decision.get("distribution_kind") != ASSISTED_RUN_DISTRIBUTION_KIND:
        problems.append(f"{label} distribution_kind must be assisted_run")
    if decision.get("information_regime") != CHECKPOINT_INFORMATION_REGIME:
        problems.append(f"{label} information regime mismatch")
    for field_name in (
        "before_resources",
        "requested_change",
        "actual_change",
        "after_resources",
    ):
        if field_name in decision and not isinstance(decision[field_name], Mapping):
            problems.append(f"{label} {field_name} must be an object")
    return problems


def _potion_count(raw: Mapping[str, Any]) -> int:
    explicit = _optional_int(raw.get("potion_count"))
    if explicit is not None:
        return explicit
    return len([identity for identity in _potion_identities(raw) if identity])


def _potion_capacity(raw: Mapping[str, Any]) -> int:
    explicit = _optional_int(raw.get("potion_capacity"))
    if explicit is not None:
        return explicit
    potions = raw.get("potions")
    if isinstance(potions, Sequence) and not isinstance(potions, (str, bytes)):
        return len(potions)
    return 0


def _potion_identities(raw: Mapping[str, Any]) -> list[str | None]:
    potions = raw.get("potions")
    if not isinstance(potions, Sequence) or isinstance(potions, (str, bytes)):
        return []
    identities: list[str | None] = []
    for item in potions:
        if not isinstance(item, Mapping):
            identities.append(None)
            continue
        potion_id = item.get("id", item.get("name", item.get("potion_id")))
        if potion_id in (None, "", "Potion Slot", "EMPTY_POTION_SLOT"):
            identities.append(None)
        else:
            identities.append(str(potion_id))
    return identities


def _context_public_run_context(context: object) -> Mapping[str, Any]:
    value = getattr(context, "public_run_context", None)
    return value if isinstance(value, Mapping) else {}


def _first_value(raw: Mapping[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in raw:
            return raw[key]
    return None


def _optional_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return None


def _require_seed(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{label} must be an integer")
    return value


def _require_non_negative_int(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{label} must be a non-negative integer")
    return value


def _require_non_empty_string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{label} must be a non-empty string")
    return value


def _require_mapping(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} must be an object")
    return dict(value)


def _mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} must be an object")
    return value


def _require_list(value: Any, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise ValueError(f"{label} must be a list")
    return value


def _require_string_list(value: Any, label: str) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError(f"{label} must be a list of strings")
    return list(value)


def _json_safe_mapping(value: Mapping[str, Any]) -> dict[str, Any]:
    return {str(key): _json_safe(value) for key, value in value.items()}


def _json_safe(value: Any) -> Any:
    if isinstance(value, Mapping):
        return _json_safe_mapping(value)
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _counter_dict(counter: Counter[str]) -> dict[str, int]:
    return {str(key): int(value) for key, value in sorted(counter.items())}


def _append_counter(lines: list[str], label: str, counter: Counter[str]) -> None:
    lines.append(f"{label}:")
    if counter:
        for key, value in sorted(counter.items()):
            lines.append(f"      {key}: {value}")
    else:
        lines.append("      (none)")


def _append_problem_list(
    lines: list[str],
    label: str,
    problems: Sequence[str],
) -> None:
    lines.append(f"{label}:")
    if problems:
        lines.extend(f"      - {problem}" for problem in problems)
    else:
        lines.append("      (none)")


def _nested_get(mapping: Mapping[str, Any], key: str) -> Any:
    value = mapping.get(key)
    return value if value is not None else "(missing)"


def _yes_no(value: bool) -> str:
    return "yes" if value else "no"


def _write_row(stream: TextIO, row: Mapping[str, Any]) -> None:
    json.dump(row, stream, sort_keys=True)
    stream.write("\n")


def sha256_file(path: Path) -> str:
    """Return the SHA-256 identity for an artifact file."""

    hasher = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()
