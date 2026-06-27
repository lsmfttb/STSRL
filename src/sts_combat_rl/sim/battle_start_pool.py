"""Natural battle-start checkpoint pools and structural sampling.

Native checkpoints are retained only in memory and are intentionally omitted
from JSONL.  A portable pool record restores in a fresh adapter by replaying
the source seed and every preceding occurrence-disambiguated action identity.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field, replace
import json
import random
from typing import Any, TextIO

from sts_combat_rl.sim.action_space import ActionSpaceConfig
from sts_combat_rl.sim.artifact_versioning import (
    ArtifactDocument,
    ArtifactMigration,
    ArtifactMigrationReport,
    migrate_artifact_document,
    preserved_migration_report,
)
from sts_combat_rl.sim.checkpoint_verification import (
    freeze_value,
    is_battle_snapshot,
    snapshot_fingerprint,
)
from sts_combat_rl.sim.contract import (
    CheckpointingSimulatorAdapter,
    ObservationValue,
    SimulatorAction,
    SimulatorCheckpoint,
    SimulatorSnapshot,
)
from sts_combat_rl.sim.controlled_run import (
    ControlledRun,
    ControlledRunStep,
    execute_controlled_run,
)
from sts_combat_rl.sim.controller_contract import (
    ControllerProvenance,
    controller_provenance_from_dict,
    legacy_policy_provenance,
)
from sts_combat_rl.sim.decision_record import (
    action_identity_from_dict,
    find_action_index_by_identity,
    source_metadata_from_snapshot,
)
from sts_combat_rl.sim.online_controller import RoutedRunController
from sts_combat_rl.sim.public_context_artifacts import (
    PUBLIC_CONTEXT_AVAILABLE,
    PUBLIC_CONTEXT_LEGACY_LOSS,
    PUBLIC_CONTEXT_LEGACY_UNAVAILABLE,
    public_context_artifact_problems,
    public_context_mismatches,
    sanitize_public_context_artifact,
)
from sts_combat_rl.sim.public_run_context import (
    append_public_history_entry,
    build_public_history_entry,
    build_public_run_context,
    read_native_public_projection,
)
from sts_combat_rl.sim.resource_outcome import (
    BATTLE_RESOURCE_OUTCOME_AVAILABLE,
    BATTLE_RESOURCE_OUTCOME_LEGACY_LOSS,
    battle_resource_outcome_problems,
    available_battle_resource_outcome,
    build_battle_resource_outcome,
    is_authoritative_terminal_battle_result,
    legacy_unavailable_battle_resource_outcome,
    unavailable_battle_resource_outcome,
)


BATTLE_START_POOL_FORMAT_VERSION = 4
"""Current portable JSONL schema version for natural battle-start pools."""

LEGACY_BATTLE_START_POOL_FORMAT_VERSION = 1
PUBLIC_CONTEXT_POOL_FORMAT_VERSION = 3
STRUCTURED_RESOURCE_OUTCOME_POOL_FORMAT_VERSION = 4
NATURAL_DISTRIBUTION_KIND = "natural_run"
NATURAL_SAMPLING_COMPONENT = "natural"
STRUCTURAL_SAMPLING_COMPONENT = "structural_uniform"
CHECKPOINT_INFORMATION_REGIME = "full_simulator_state_oracle_like"
LEGACY_UNKNOWN_INFORMATION_REGIME = "unknown"
PUBLIC_CONTEXT_UNAVAILABLE = PUBLIC_CONTEXT_LEGACY_UNAVAILABLE
SOURCE_RUN_SUMMARY_AVAILABLE = "available"
SOURCE_RUN_SUMMARY_LEGACY_UNAVAILABLE = "legacy_unavailable"

BATTLE_START_POOL_MIGRATIONS = (
    ArtifactMigration(
        source_version=LEGACY_BATTLE_START_POOL_FORMAT_VERSION,
        target_version=2,
        migrate=lambda document: _migrate_pool_v1_to_v2(document),
        losses=(
            "v1 recorded action ids without duplicate occurrence indices; "
            "legacy replay fails closed when an id is duplicated",
            "v1 recorded policy names rather than complete controller configuration",
            "v1 did not declare checkpoint information regime or public context",
            "v1 did not record whether a battle completed before collection ended",
        ),
    ),
    ArtifactMigration(
        source_version=2,
        target_version=PUBLIC_CONTEXT_POOL_FORMAT_VERSION,
        migrate=lambda document: _migrate_pool_v2_to_v3(document),
        losses=(PUBLIC_CONTEXT_LEGACY_LOSS,),
    ),
    ArtifactMigration(
        source_version=PUBLIC_CONTEXT_POOL_FORMAT_VERSION,
        target_version=STRUCTURED_RESOURCE_OUTCOME_POOL_FORMAT_VERSION,
        migrate=lambda document: _migrate_pool_v3_to_v4(document),
        losses=(BATTLE_RESOURCE_OUTCOME_LEGACY_LOSS,),
    ),
)


@dataclass(frozen=True)
class SourceRunSummary:
    """Run-level reachability metadata for one source episode."""

    source_run_id: str
    source_seed: int
    terminal: bool
    outcome: str
    final_floor: float | None
    final_act: int | None
    final_screen_state: str
    final_battle_active: bool
    captured_battle_start_count: int
    completed_battle_count: int
    max_battle_start_floor: float | None
    max_battle_start_act: int | None
    problem_count: int
    problems: tuple[str, ...] = ()
    status: str = SOURCE_RUN_SUMMARY_AVAILABLE

    @classmethod
    def legacy_unavailable(
        cls,
        *,
        source_run_id: str,
        source_seed: int,
        captured_battle_start_count: int,
    ) -> SourceRunSummary:
        """Build an explicit placeholder for migrated legacy pools."""

        return cls(
            source_run_id=source_run_id,
            source_seed=source_seed,
            terminal=False,
            outcome="UNKNOWN",
            final_floor=None,
            final_act=None,
            final_screen_state="(legacy-unavailable)",
            final_battle_active=False,
            captured_battle_start_count=captured_battle_start_count,
            completed_battle_count=0,
            max_battle_start_floor=None,
            max_battle_start_act=None,
            problem_count=0,
            status=SOURCE_RUN_SUMMARY_LEGACY_UNAVAILABLE,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_run_id": self.source_run_id,
            "source_seed": self.source_seed,
            "terminal": self.terminal,
            "outcome": self.outcome,
            "final_floor": self.final_floor,
            "final_act": self.final_act,
            "final_screen_state": self.final_screen_state,
            "final_battle_active": self.final_battle_active,
            "captured_battle_start_count": self.captured_battle_start_count,
            "completed_battle_count": self.completed_battle_count,
            "max_battle_start_floor": self.max_battle_start_floor,
            "max_battle_start_act": self.max_battle_start_act,
            "problem_count": self.problem_count,
            "problems": list(self.problems),
            "status": self.status,
        }


@dataclass(frozen=True)
class BattleStartCheckpointRecord:
    """One naturally reached battle start and its restore provenance."""

    record_index: int
    source_checkpoint_id: str
    source_run_id: str
    source_seed: int
    source_battle_index: int
    structural_metadata: dict[str, Any]
    source_controller_provenance: dict[str, Any]
    source_battle_controller_provenance: dict[str, Any]
    source_non_combat_controller_provenance: dict[str, Any]
    action_trace: tuple[dict[str, Any], ...]
    snapshot_observation: tuple[ObservationValue, ...]
    snapshot_raw: dict[str, Any]
    battle_outcome: str | None = None
    battle_completed: bool = False
    completed_battle_resource_outcome_status: str = "legacy_unavailable"
    completed_battle_resource_outcome: dict[str, Any] = field(default_factory=dict)
    distribution_kind: str = NATURAL_DISTRIBUTION_KIND
    checkpoint_information_regime: str = CHECKPOINT_INFORMATION_REGIME
    public_context_status: str = PUBLIC_CONTEXT_LEGACY_UNAVAILABLE
    public_run_context: dict[str, Any] = field(default_factory=dict)
    native_checkpoint: SimulatorCheckpoint | None = field(
        default=None,
        repr=False,
        compare=False,
    )

    @property
    def structural_stratum(self) -> tuple[Any, Any, Any, Any]:
        """Rule-defined metadata used for structural resampling only."""

        return tuple(
            self.structural_metadata.get(field_name)
            for field_name in ("ascension", "act", "room_type", "encounter_id")
        )  # type: ignore[return-value]


@dataclass(frozen=True)
class NaturalBattleStartPool:
    """Natural battle starts created by one explicit routed controller."""

    source_run_count: int
    terminal_run_count: int
    truncated_run_count: int
    source_controller_provenance: dict[str, Any]
    format_version: int = BATTLE_START_POOL_FORMAT_VERSION
    records: list[BattleStartCheckpointRecord] = field(default_factory=list)
    source_run_summaries: list[SourceRunSummary] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)
    migration_report: ArtifactMigrationReport = field(
        default_factory=lambda: ArtifactMigrationReport(
            source_version=BATTLE_START_POOL_FORMAT_VERSION,
            target_version=BATTLE_START_POOL_FORMAT_VERSION,
        ),
        compare=False,
    )


@dataclass(frozen=True)
class SampledBattleStart:
    """One optimization draw retaining the natural source checkpoint identity."""

    sample_index: int
    source_checkpoint_id: str
    sampling_component: str
    record: BattleStartCheckpointRecord


@dataclass(frozen=True)
class BattleStartPoolCoverageReport:
    """Coverage report that never conflates starts, wins, or sampled weight."""

    natural_battle_start_count: int
    unique_source_start_count: int
    source_run_count: int
    terminal_run_count: int
    truncated_run_count: int
    reported_battle_win_count: int
    completed_battle_count: int = 0
    completed_battle_outcome_missing_count: int = 0
    reported_battle_outcome_counts: Counter[str] = field(default_factory=Counter)
    resource_outcome_status_counts: Counter[str] = field(default_factory=Counter)
    later_act_source_run_count: int = 0
    sampled_draw_count: int = 0
    sampling_component_counts: Counter[str] = field(default_factory=Counter)
    ascension_counts: Counter[str] = field(default_factory=Counter)
    act_counts: Counter[str] = field(default_factory=Counter)
    room_type_counts: Counter[str] = field(default_factory=Counter)
    encounter_id_counts: Counter[str] = field(default_factory=Counter)
    missing_metadata_counts: Counter[str] = field(default_factory=Counter)
    problems: list[str] = field(default_factory=list)

    @property
    def completed_outcomes_complete(self) -> bool:
        """Whether every battle that ended during collection kept its outcome."""

        return self.completed_battle_outcome_missing_count == 0


@dataclass(frozen=True)
class BattleStartPoolRestoreReport:
    """Fresh-adapter portable replay verification results for a pool."""

    checkpoint_count: int
    requested_limit: int
    restored_count: int
    native_restored_count: int
    replay_restored_count: int
    context_compared_count: int = 0
    context_matched_count: int = 0
    context_legacy_unavailable_count: int = 0
    context_mismatch_count: int = 0
    problems: list[str] = field(default_factory=list)

    @property
    def restore_ok(self) -> bool:
        expected = self.checkpoint_count
        if self.requested_limit > 0:
            expected = min(expected, self.requested_limit)
        return expected > 0 and self.restored_count == expected and not self.problems


def collect_natural_battle_start_pool(
    adapter: CheckpointingSimulatorAdapter,
    controller: RoutedRunController,
    *,
    seeds: Iterable[int],
    max_steps: int = 200,
    action_space: ActionSpaceConfig | None = None,
) -> NaturalBattleStartPool:
    """Capture every natural battle start before its battle action is selected."""

    if max_steps <= 0:
        raise ValueError("natural battle-start pool max_steps must be positive")
    if not adapter.supports_checkpoint_restore:
        raise ValueError("simulator does not support native checkpoint capture/restore")
    seed_list = [_require_seed(seed, "collection seed") for seed in seeds]
    active_action_space = action_space or ActionSpaceConfig.initial_no_potions()
    records: list[BattleStartCheckpointRecord] = []
    source_run_summaries: list[SourceRunSummary] = []
    problems: list[str] = []
    terminal_run_count = 0

    for run_index, seed in enumerate(seed_list):
        source_run_id = f"seed-{seed}-run-{run_index}"
        action_trace: list[dict[str, Any]] = []
        active_record_index: int | None = None
        battle_index = 0
        run_record_start = len(records)
        run_problem_start = len(problems)

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
            record = _build_record(
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

    return NaturalBattleStartPool(
        source_run_count=len(seed_list),
        terminal_run_count=terminal_run_count,
        truncated_run_count=len(seed_list) - terminal_run_count,
        source_controller_provenance=controller.provenance.to_dict(),
        records=records,
        source_run_summaries=source_run_summaries,
        problems=list(dict.fromkeys(problems)),
    )


def _build_source_run_summary(
    *,
    source_run_id: str,
    source_seed: int,
    controlled: ControlledRun,
    records: Sequence[BattleStartCheckpointRecord],
    run_problems: Sequence[str],
) -> SourceRunSummary:
    final_raw = (
        controlled.final_raw if isinstance(controlled.final_raw, Mapping) else {}
    )
    final_floor = _optional_number(final_raw.get("floor_num", final_raw.get("floor")))
    final_act = _optional_int(final_raw.get("act"))
    max_floor = _max_optional_number(
        record.structural_metadata.get("floor") for record in records
    )
    max_act = _max_optional_int(
        record.structural_metadata.get("act") for record in records
    )
    return SourceRunSummary(
        source_run_id=source_run_id,
        source_seed=source_seed,
        terminal=controlled.terminal,
        outcome=controlled.outcome,
        final_floor=final_floor,
        final_act=max_act if final_act is None else final_act,
        final_screen_state=str(final_raw.get("screen_state", "(none)")),
        final_battle_active=bool(final_raw.get("battle_active")),
        captured_battle_start_count=len(records),
        completed_battle_count=sum(1 for record in records if record.battle_completed),
        max_battle_start_floor=max_floor,
        max_battle_start_act=max_act,
        problem_count=len(run_problems),
        problems=tuple(dict.fromkeys(run_problems)),
    )


def sample_battle_start_pool(
    pool: NaturalBattleStartPool,
    *,
    sample_count: int,
    seed: int,
    structural_fraction: float = 0.5,
) -> list[SampledBattleStart]:
    """Draw seeded natural/structural samples without creating new sources."""

    if sample_count < 0:
        raise ValueError("battle-start sample count cannot be negative")
    if not 0.0 <= structural_fraction <= 1.0:
        raise ValueError("structural fraction must be between zero and one")
    problems = natural_battle_start_pool_problems(pool)
    if problems:
        raise ValueError("invalid natural battle-start pool: " + "; ".join(problems))
    if sample_count and not pool.records:
        raise ValueError("cannot sample an empty battle-start pool")

    generator = random.Random(seed)
    strata: dict[tuple[Any, Any, Any, Any], list[BattleStartCheckpointRecord]] = (
        defaultdict(list)
    )
    for record in pool.records:
        strata[record.structural_stratum].append(record)
    stratum_keys = sorted(strata, key=repr)
    sampled: list[SampledBattleStart] = []
    for sample_index in range(sample_count):
        use_structural = generator.random() < structural_fraction
        if use_structural:
            source = generator.choice(strata[generator.choice(stratum_keys)])
            component = STRUCTURAL_SAMPLING_COMPONENT
        else:
            source = generator.choice(pool.records)
            component = NATURAL_SAMPLING_COMPONENT
        sampled.append(
            SampledBattleStart(
                sample_index=sample_index,
                source_checkpoint_id=source.source_checkpoint_id,
                sampling_component=component,
                record=source,
            )
        )
    return sampled


def build_battle_start_pool_coverage_report(
    pool: NaturalBattleStartPool,
    *,
    sampled: Sequence[SampledBattleStart] = (),
) -> BattleStartPoolCoverageReport:
    """Report structural start coverage independently from outcomes and draws."""

    ascension_counts: Counter[str] = Counter()
    act_counts: Counter[str] = Counter()
    room_type_counts: Counter[str] = Counter()
    encounter_id_counts: Counter[str] = Counter()
    missing_metadata_counts: Counter[str] = Counter()
    outcome_counts: Counter[str] = Counter()
    resource_outcome_status_counts: Counter[str] = Counter()
    later_act_runs: set[str] = set()
    completed_battle_count = 0
    completed_battle_outcome_missing_count = 0

    for record in pool.records:
        for field_name, counter in (
            ("ascension", ascension_counts),
            ("act", act_counts),
            ("room_type", room_type_counts),
            ("encounter_id", encounter_id_counts),
        ):
            value = record.structural_metadata.get(field_name)
            if value is None or value == "":
                missing_metadata_counts[field_name] += 1
                counter["(missing)"] += 1
            else:
                counter[str(value)] += 1
        act = record.structural_metadata.get("act")
        if isinstance(act, int) and not isinstance(act, bool) and act > 1:
            later_act_runs.add(record.source_run_id)
        if record.battle_completed:
            completed_battle_count += 1
        if record.battle_outcome is None:
            if record.battle_completed:
                completed_battle_outcome_missing_count += 1
                outcome_counts["(completed-outcome-missing)"] += 1
            else:
                outcome_counts["(battle-not-completed)"] += 1
        else:
            outcome_counts[record.battle_outcome] += 1
        resource_outcome_status_counts[
            record.completed_battle_resource_outcome_status
        ] += 1

    component_counts = Counter(sample.sampling_component for sample in sampled)
    sample_problems = [
        f"sample {sample.sample_index} source checkpoint mismatch"
        for sample in sampled
        if sample.source_checkpoint_id != sample.record.source_checkpoint_id
        or sample.sampling_component
        not in {NATURAL_SAMPLING_COMPONENT, STRUCTURAL_SAMPLING_COMPONENT}
    ]
    return BattleStartPoolCoverageReport(
        natural_battle_start_count=len(pool.records),
        unique_source_start_count=len(
            {record.source_checkpoint_id for record in pool.records}
        ),
        source_run_count=pool.source_run_count,
        terminal_run_count=pool.terminal_run_count,
        truncated_run_count=pool.truncated_run_count,
        reported_battle_win_count=outcome_counts["PLAYER_VICTORY"],
        completed_battle_count=completed_battle_count,
        completed_battle_outcome_missing_count=completed_battle_outcome_missing_count,
        reported_battle_outcome_counts=outcome_counts,
        resource_outcome_status_counts=resource_outcome_status_counts,
        later_act_source_run_count=len(later_act_runs),
        sampled_draw_count=len(sampled),
        sampling_component_counts=component_counts,
        ascension_counts=ascension_counts,
        act_counts=act_counts,
        room_type_counts=room_type_counts,
        encounter_id_counts=encounter_id_counts,
        missing_metadata_counts=missing_metadata_counts,
        problems=list(
            dict.fromkeys(
                [
                    *pool.problems,
                    *sample_problems,
                    *(
                        [
                            "completed battle outcomes are missing from "
                            f"{completed_battle_outcome_missing_count} records"
                        ]
                        if completed_battle_outcome_missing_count
                        else []
                    ),
                ]
            )
        ),
    )


def dump_natural_battle_start_pool_jsonl(
    pool: NaturalBattleStartPool,
    stream: TextIO,
) -> None:
    """Write the current JSONL schema without opaque native checkpoint payloads."""

    problems = natural_battle_start_pool_problems(pool)
    if problems:
        raise ValueError("invalid natural battle-start pool: " + "; ".join(problems))
    metadata = {
        "format_version": BATTLE_START_POOL_FORMAT_VERSION,
        "source_run_count": pool.source_run_count,
        "terminal_run_count": pool.terminal_run_count,
        "truncated_run_count": pool.truncated_run_count,
        "source_controller_provenance": pool.source_controller_provenance,
        "record_count": len(pool.records),
        "source_run_summaries": [
            summary.to_dict() for summary in pool.source_run_summaries
        ],
        "migration_report": pool.migration_report.to_dict(),
        "problems": list(pool.problems),
    }
    _write_row(stream, {"type": "metadata", "metadata": metadata})
    for record in pool.records:
        _write_row(stream, {"type": "record", "record": record_to_manifest(record)})


def load_natural_battle_start_pool_jsonl(stream: TextIO) -> NaturalBattleStartPool:
    """Load and sequentially migrate a portable natural battle-start pool."""

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
        raise ValueError("missing battle-start pool metadata")

    migrated = migrate_artifact_document(
        metadata,
        raw_records,
        current_version=BATTLE_START_POOL_FORMAT_VERSION,
        migrations=BATTLE_START_POOL_MIGRATIONS,
        artifact_name="battle-start pool",
    )
    metadata = migrated.document.metadata
    records = [
        record_from_manifest(raw, label=f"record {index}")
        for index, raw in enumerate(migrated.document.records)
    ]
    if metadata.get("record_count") != len(records):
        raise ValueError("battle-start pool metadata record_count mismatch")
    if any(record.record_index != index for index, record in enumerate(records)):
        raise ValueError("battle-start pool record indices must be contiguous")
    problems = _require_string_list(metadata.get("problems", []), "metadata problems")
    source_run_summaries = _source_run_summaries_from_metadata(
        metadata.get("source_run_summaries", []),
        label="source_run_summaries",
    )
    pool = NaturalBattleStartPool(
        source_run_count=_require_non_negative_int(
            metadata.get("source_run_count"), "source_run_count"
        ),
        terminal_run_count=_require_non_negative_int(
            metadata.get("terminal_run_count"), "terminal_run_count"
        ),
        truncated_run_count=_require_non_negative_int(
            metadata.get("truncated_run_count"), "truncated_run_count"
        ),
        source_controller_provenance=_validated_provenance(
            metadata.get("source_controller_provenance"),
            "source controller provenance",
        ),
        records=records,
        source_run_summaries=source_run_summaries,
        problems=problems,
        migration_report=preserved_migration_report(
            metadata,
            migrated.report,
            artifact_name="battle-start pool",
        ),
    )
    pool_problems = natural_battle_start_pool_problems(pool)
    if pool_problems:
        raise ValueError(
            "invalid natural battle-start pool: " + "; ".join(pool_problems)
        )
    return pool


def restore_battle_start_record(
    adapter: CheckpointingSimulatorAdapter,
    record: BattleStartCheckpointRecord,
) -> tuple[SimulatorSnapshot, str]:
    """Restore natively when possible, otherwise replay in a fresh adapter."""

    if record.public_context_status == PUBLIC_CONTEXT_AVAILABLE:
        restored, replayed_context = _restore_by_seed_action_trace(adapter, record)
        method = "seed_action_trace"
        mismatches = public_context_mismatches(
            sanitize_public_context_artifact(
                record.public_run_context,
                label=f"record {record.record_index}",
            ),
            replayed_context,
            label=f"record {record.record_index} public context replay",
        )
        if mismatches:
            raise ValueError("; ".join(mismatches))
    elif (
        record.native_checkpoint is not None
        and record.native_checkpoint.adapter_id == adapter.checkpoint_adapter_id
    ):
        restored = adapter.restore_checkpoint(record.native_checkpoint)
        method = "native_checkpoint"
    else:
        restored, _ = _restore_by_seed_action_trace(adapter, record)
        method = "seed_action_trace"
    if not _snapshot_matches_record(restored, record):
        raise ValueError(
            f"record {record.record_index}: restored snapshot does not match source"
        )
    return restored, method


def verify_battle_start_pool_restores(
    adapter_factory: Callable[[], CheckpointingSimulatorAdapter],
    pool: NaturalBattleStartPool,
    *,
    limit: int = 0,
) -> BattleStartPoolRestoreReport:
    """Verify records with new adapter instances, suitable for a fresh WSL CLI run."""

    if limit < 0:
        raise ValueError("battle-start restore limit cannot be negative")
    selected = pool.records if limit == 0 else pool.records[:limit]
    restored_count = 0
    native_count = 0
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
            _, method = restore_battle_start_record(adapter_factory(), record)
        except (RuntimeError, ValueError) as exc:
            problems.append(f"record {record.record_index}: {exc}")
            if record.public_context_status == PUBLIC_CONTEXT_AVAILABLE:
                context_mismatch_count += 1
            continue
        restored_count += 1
        if record.public_context_status == PUBLIC_CONTEXT_AVAILABLE:
            context_matched_count += 1
        if method == "native_checkpoint":
            native_count += 1
        else:
            replay_count += 1
    return BattleStartPoolRestoreReport(
        checkpoint_count=len(pool.records),
        requested_limit=limit,
        restored_count=restored_count,
        native_restored_count=native_count,
        replay_restored_count=replay_count,
        context_compared_count=context_compared_count,
        context_matched_count=context_matched_count,
        context_legacy_unavailable_count=context_legacy_unavailable_count,
        context_mismatch_count=context_mismatch_count,
        problems=problems,
    )


def record_to_manifest(record: BattleStartCheckpointRecord) -> dict[str, Any]:
    """Serialize portable record fields while deliberately omitting native state."""

    return {
        "record_index": record.record_index,
        "source_checkpoint_id": record.source_checkpoint_id,
        "source_run_id": record.source_run_id,
        "source_seed": record.source_seed,
        "source_battle_index": record.source_battle_index,
        "structural_metadata": _json_safe_mapping(record.structural_metadata),
        "source_controller_provenance": record.source_controller_provenance,
        "source_battle_controller_provenance": record.source_battle_controller_provenance,
        "source_non_combat_controller_provenance": (
            record.source_non_combat_controller_provenance
        ),
        "action_trace": [
            _json_safe_mapping(identity) for identity in record.action_trace
        ],
        "snapshot_observation": list(record.snapshot_observation),
        "snapshot_raw": _json_safe_mapping(record.snapshot_raw),
        "battle_outcome": record.battle_outcome,
        "battle_completed": record.battle_completed,
        "completed_battle_resource_outcome_status": (
            record.completed_battle_resource_outcome_status
        ),
        "completed_battle_resource_outcome": _json_safe_mapping(
            record.completed_battle_resource_outcome
        ),
        "distribution_kind": record.distribution_kind,
        "checkpoint_information_regime": record.checkpoint_information_regime,
        "public_context_status": record.public_context_status,
        "public_run_context": _json_safe_mapping(record.public_run_context),
    }


def record_from_manifest(
    raw: Mapping[str, Any],
    *,
    label: str,
) -> BattleStartCheckpointRecord:
    """Strictly load one current-schema record without guessing missing fields."""

    action_trace_raw = raw.get("action_trace")
    if not isinstance(action_trace_raw, list):
        raise ValueError(f"{label} action_trace must be a list")
    action_trace = tuple(
        _validated_trace_identity(value, f"{label} action trace {index}")
        for index, value in enumerate(action_trace_raw)
    )
    observation = raw.get("snapshot_observation")
    if not isinstance(observation, list) or not all(
        isinstance(value, (bool, int, float)) for value in observation
    ):
        raise ValueError(f"{label} snapshot_observation must contain scalar values")
    battle_outcome = raw.get("battle_outcome")
    if battle_outcome is not None and not isinstance(battle_outcome, str):
        raise ValueError(f"{label} battle_outcome must be a string or null")
    battle_completed = raw.get("battle_completed")
    if not isinstance(battle_completed, bool):
        raise ValueError(f"{label} battle_completed must be a boolean")
    resource_outcome_status = _resource_outcome_status(
        raw.get("completed_battle_resource_outcome_status"),
        f"{label} completed battle resource outcome status",
    )
    resource_outcome = _resource_outcome_payload(
        raw.get("completed_battle_resource_outcome"),
        status=resource_outcome_status,
        label=f"{label} completed battle resource outcome",
    )
    distribution_kind = raw.get("distribution_kind")
    if distribution_kind != NATURAL_DISTRIBUTION_KIND:
        raise ValueError(f"{label} must retain natural_run distribution_kind")
    checkpoint_information_regime = _information_regime(
        raw.get("checkpoint_information_regime"),
        f"{label} checkpoint information regime",
    )
    public_context_status = _public_context_status(
        raw.get("public_context_status"),
        f"{label} public context status",
    )
    public_run_context = _public_run_context(
        raw.get("public_run_context"),
        public_context_status=public_context_status,
        label=label,
    )
    return BattleStartCheckpointRecord(
        record_index=_require_non_negative_int(
            raw.get("record_index"), f"{label} index"
        ),
        source_checkpoint_id=_require_non_empty_string(
            raw.get("source_checkpoint_id"), f"{label} source checkpoint id"
        ),
        source_run_id=_require_non_empty_string(
            raw.get("source_run_id"), f"{label} source run id"
        ),
        source_seed=_require_seed(raw.get("source_seed"), f"{label} source seed"),
        source_battle_index=_require_non_negative_int(
            raw.get("source_battle_index"), f"{label} source battle index"
        ),
        structural_metadata=_validated_structural_metadata(
            raw.get("structural_metadata"), label
        ),
        source_controller_provenance=_validated_provenance(
            raw.get("source_controller_provenance"), f"{label} controller provenance"
        ),
        source_battle_controller_provenance=_validated_provenance(
            raw.get("source_battle_controller_provenance"),
            f"{label} battle controller provenance",
        ),
        source_non_combat_controller_provenance=_validated_provenance(
            raw.get("source_non_combat_controller_provenance"),
            f"{label} non-combat controller provenance",
        ),
        action_trace=action_trace,
        snapshot_observation=tuple(observation),
        snapshot_raw=_require_mapping(raw.get("snapshot_raw"), f"{label} snapshot raw"),
        battle_outcome=battle_outcome,
        battle_completed=battle_completed,
        completed_battle_resource_outcome_status=resource_outcome_status,
        completed_battle_resource_outcome=resource_outcome,
        distribution_kind=distribution_kind,
        checkpoint_information_regime=checkpoint_information_regime,
        public_context_status=public_context_status,
        public_run_context=public_run_context,
    )


def natural_battle_start_pool_problems(pool: NaturalBattleStartPool) -> list[str]:
    """Return structural failures; optional simulator metadata remains explicit."""

    problems: list[str] = []
    if pool.format_version != BATTLE_START_POOL_FORMAT_VERSION:
        problems.append("pool has an unsupported format version")
    if pool.terminal_run_count + pool.truncated_run_count != pool.source_run_count:
        problems.append(
            "pool terminal and truncated run counts do not match source runs"
        )
    if pool.source_run_summaries:
        if len(pool.source_run_summaries) != pool.source_run_count:
            problems.append(
                "pool source_run_summaries count does not match source runs"
            )
        summary_run_ids: set[str] = set()
        terminal_summary_count = 0
        for index, summary in enumerate(pool.source_run_summaries):
            try:
                _validated_source_run_summary(summary.to_dict(), f"run summary {index}")
            except ValueError as exc:
                problems.append(str(exc))
            if summary.source_run_id in summary_run_ids:
                problems.append(
                    f"duplicate source_run_summaries id {summary.source_run_id}"
                )
            summary_run_ids.add(summary.source_run_id)
            if summary.terminal:
                terminal_summary_count += 1
        if terminal_summary_count != pool.terminal_run_count:
            problems.append(
                "pool source_run_summaries terminal count does not match metadata"
            )
    try:
        _validated_provenance(pool.source_controller_provenance, "pool controller")
    except ValueError as exc:
        problems.append(str(exc))
    checkpoint_ids: set[str] = set()
    for index, record in enumerate(pool.records):
        if record.record_index != index:
            problems.append(f"record {index} index is not contiguous")
        if record.source_checkpoint_id in checkpoint_ids:
            problems.append(
                f"duplicate source checkpoint id {record.source_checkpoint_id}"
            )
        checkpoint_ids.add(record.source_checkpoint_id)
        if record.distribution_kind != NATURAL_DISTRIBUTION_KIND:
            problems.append(f"record {index} is not tagged as a natural source")
        if record.checkpoint_information_regime not in {
            CHECKPOINT_INFORMATION_REGIME,
            LEGACY_UNKNOWN_INFORMATION_REGIME,
        }:
            problems.append(
                f"record {index} has an invalid checkpoint information regime"
            )
        problems.extend(
            public_context_artifact_problems(
                status=record.public_context_status,
                context=record.public_run_context,
                label=f"record {index}",
                require_candidate_actions=(
                    record.public_context_status == PUBLIC_CONTEXT_AVAILABLE
                ),
            )
        )
        problems.extend(
            battle_resource_outcome_problems(
                record.completed_battle_resource_outcome_status,
                record.completed_battle_resource_outcome,
                label=f"record {index} completed battle resource outcome",
                require_available=record.battle_completed,
            )
        )
        for provenance_name, provenance in (
            ("controller", record.source_controller_provenance),
            ("battle controller", record.source_battle_controller_provenance),
            ("non-combat controller", record.source_non_combat_controller_provenance),
        ):
            try:
                _validated_provenance(provenance, f"record {index} {provenance_name}")
            except ValueError as exc:
                problems.append(str(exc))
        try:
            _validated_structural_metadata(
                record.structural_metadata, f"record {index}"
            )
        except ValueError as exc:
            problems.append(str(exc))
    return list(dict.fromkeys([*pool.problems, *problems]))


def format_battle_start_pool_coverage_report(
    report: BattleStartPoolCoverageReport,
) -> str:
    """Format coverage with clear natural/source/weight separation."""

    lines = ["Natural battle-start checkpoint pool coverage"]
    lines.append(f"natural battle starts: {report.natural_battle_start_count}")
    lines.append(f"unique source starts: {report.unique_source_start_count}")
    lines.append(f"source runs: {report.source_run_count}")
    lines.append(f"terminal source runs: {report.terminal_run_count}")
    lines.append(f"truncated source runs: {report.truncated_run_count}")
    lines.append(f"reported battle wins: {report.reported_battle_win_count}")
    lines.append(f"completed battles: {report.completed_battle_count}")
    lines.append(
        "completed battles missing outcome: "
        f"{report.completed_battle_outcome_missing_count}"
    )
    lines.append(
        f"source runs with later-act starts: {report.later_act_source_run_count}"
    )
    lines.append(f"sampled optimization draws: {report.sampled_draw_count}")
    lines.append("sampling components (weight only; not unique coverage):")
    _append_counter(lines, report.sampling_component_counts)
    lines.append("ascension battle starts:")
    _append_counter(lines, report.ascension_counts)
    lines.append("act battle starts:")
    _append_counter(lines, report.act_counts)
    lines.append("room type battle starts:")
    _append_counter(lines, report.room_type_counts)
    lines.append("encounter battle starts:")
    _append_counter(lines, report.encounter_id_counts)
    lines.append("reported battle outcomes:")
    _append_counter(lines, report.reported_battle_outcome_counts)
    lines.append("structured resource outcome statuses:")
    _append_counter(lines, report.resource_outcome_status_counts)
    lines.append("missing structural metadata:")
    _append_counter(lines, report.missing_metadata_counts)
    lines.append("problems:")
    if report.problems:
        lines.extend(f"  - {problem}" for problem in report.problems)
    else:
        lines.append("  (none)")
    return "\n".join(lines)


def format_battle_start_pool_restore_report(
    report: BattleStartPoolRestoreReport,
) -> str:
    """Format fresh-adapter replay results for stderr-only command output."""

    lines = ["Battle-start pool fresh-adapter restore summary"]
    lines.append(f"checkpoint records: {report.checkpoint_count}")
    lines.append(f"requested limit: {report.requested_limit or '(all)'}")
    lines.append(f"restored records: {report.restored_count}")
    lines.append(f"native restores: {report.native_restored_count}")
    lines.append(f"seed/action-trace restores: {report.replay_restored_count}")
    lines.append(f"public-context comparisons: {report.context_compared_count}")
    lines.append(f"public-context matches: {report.context_matched_count}")
    lines.append(
        f"public-context legacy losses: {report.context_legacy_unavailable_count}"
    )
    lines.append(f"public-context mismatches: {report.context_mismatch_count}")
    lines.append(f"restore ok: {'yes' if report.restore_ok else 'no'}")
    lines.append("problems:")
    if report.problems:
        lines.extend(f"  - {problem}" for problem in report.problems)
    else:
        lines.append("  (none)")
    return "\n".join(lines)


def _build_record(
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
) -> BattleStartCheckpointRecord:
    structural = source_metadata_from_snapshot(
        snapshot.raw,
        seed=source_seed,
        source_kind=NATURAL_DISTRIBUTION_KIND,
    )
    structural.update(
        {
            "source_run_id": source_run_id,
            "source_battle_index": source_battle_index,
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
        public_context_status=PUBLIC_CONTEXT_AVAILABLE,
        public_run_context=sanitize_public_context_artifact(
            public_run_context,
            label=f"record {record_index}",
        ),
        native_checkpoint=native_checkpoint,
    )


def _restore_by_seed_action_trace(
    adapter: CheckpointingSimulatorAdapter,
    record: BattleStartCheckpointRecord,
) -> tuple[SimulatorSnapshot, dict[str, Any]]:
    snapshot = adapter.reset(seed=record.source_seed)
    public_history: list[dict[str, Any]] = []
    for trace_index, identity in enumerate(record.action_trace):
        actions = list(adapter.legal_actions(snapshot))
        pre_context = _public_context_for_snapshot(
            adapter,
            snapshot,
            actions,
            history=public_history,
        )
        index = _trace_action_index(actions, identity, trace_index)
        transition = adapter.step(actions[index])
        post_context = _public_context_for_snapshot(
            adapter,
            transition.snapshot,
            (),
            history=public_history,
            include_candidates=False,
        )
        history_entry = build_public_history_entry(
            history_index=len(public_history),
            step_index=trace_index,
            pre_context=pre_context,
            post_context=post_context,
            selected_action_index=index,
        )
        public_history = append_public_history_entry(public_history, history_entry)
        snapshot = transition.snapshot
    final_context = _public_context_for_snapshot(
        adapter,
        snapshot,
        list(adapter.legal_actions(snapshot)),
        history=public_history,
    )
    return snapshot, final_context


def _public_context_for_snapshot(
    adapter: CheckpointingSimulatorAdapter,
    snapshot: SimulatorSnapshot,
    actions: Sequence[SimulatorAction],
    *,
    history: Sequence[Mapping[str, Any]],
    include_candidates: bool = True,
) -> dict[str, Any]:
    projection = read_native_public_projection(adapter, snapshot)
    return build_public_run_context(
        snapshot.raw,
        actions,
        projection=projection,
        history=history,
        include_candidates=include_candidates,
    )


def _context_public_run_context(context: object) -> dict[str, Any]:
    value = getattr(context, "public_run_context", None)
    if not isinstance(value, Mapping):
        raise ValueError("decision context public_run_context is missing")
    return sanitize_public_context_artifact(value, label="decision context")


def _trace_action_index(
    actions: Sequence[SimulatorAction],
    identity: Mapping[str, Any],
    trace_index: int,
) -> int:
    occurrence = identity.get("occurrence")
    if occurrence is not None:
        return find_action_index_by_identity(actions, identity)
    action_id = identity.get("action_id")
    matches = [
        index for index, action in enumerate(actions) if action.action_id == action_id
    ]
    if len(matches) != 1:
        raise ValueError(
            f"legacy action trace {trace_index} matched {len(matches)} legal actions; "
            "v1 omitted duplicate occurrence information"
        )
    return matches[0]


def _snapshot_matches_record(
    snapshot: SimulatorSnapshot,
    record: BattleStartCheckpointRecord,
) -> bool:
    expected = freeze_value((record.snapshot_observation, record.snapshot_raw))
    return snapshot_fingerprint(snapshot) == expected


def _validated_structural_metadata(value: Any, label: str) -> dict[str, Any]:
    metadata = _require_mapping(value, f"{label} structural metadata")
    required = (
        "ascension",
        "act",
        "floor",
        "room_type",
        "encounter_id",
        "seed",
        "source_kind",
        "distribution_kind",
        "source_run_id",
        "source_battle_index",
    )
    missing = [field_name for field_name in required if field_name not in metadata]
    if missing:
        raise ValueError(f"{label} structural metadata missing: {', '.join(missing)}")
    if metadata["source_kind"] != NATURAL_DISTRIBUTION_KIND:
        raise ValueError(f"{label} structural metadata source_kind must be natural_run")
    if metadata["distribution_kind"] != NATURAL_DISTRIBUTION_KIND:
        raise ValueError(
            f"{label} structural metadata distribution_kind must be natural_run"
        )
    return metadata


def _validated_provenance(value: Any, label: str) -> dict[str, Any]:
    try:
        return controller_provenance_from_dict(_require_mapping(value, label)).to_dict()
    except ValueError as exc:
        raise ValueError(f"{label}: {exc}") from exc


def _validated_trace_identity(value: Any, label: str) -> dict[str, Any]:
    identity = _require_mapping(value, label)
    if identity.get("occurrence") is None:
        action_id = identity.get("action_id")
        if isinstance(action_id, bool) or not isinstance(action_id, (int, str)):
            raise ValueError(f"{label} legacy action_id must be an integer or string")
        if set(identity) - {"action_id", "occurrence"}:
            raise ValueError(f"{label} legacy action trace has unsupported fields")
        return {"action_id": action_id, "occurrence": None}
    try:
        return action_identity_from_dict(identity).to_dict()
    except ValueError as exc:
        raise ValueError(f"{label}: {exc}") from exc


def _information_regime(value: Any, label: str) -> str:
    if value not in {CHECKPOINT_INFORMATION_REGIME, LEGACY_UNKNOWN_INFORMATION_REGIME}:
        raise ValueError(
            f"{label} must be {CHECKPOINT_INFORMATION_REGIME!r} or "
            f"{LEGACY_UNKNOWN_INFORMATION_REGIME!r}"
        )
    return str(value)


def _public_context_status(value: Any, label: str) -> str:
    if value == "unavailable":
        return PUBLIC_CONTEXT_LEGACY_UNAVAILABLE
    if value not in {PUBLIC_CONTEXT_AVAILABLE, PUBLIC_CONTEXT_LEGACY_UNAVAILABLE}:
        raise ValueError(
            f"{label} must be {PUBLIC_CONTEXT_AVAILABLE!r} or "
            f"{PUBLIC_CONTEXT_LEGACY_UNAVAILABLE!r}"
        )
    return str(value)


def _resource_outcome_status(value: Any, label: str) -> str:
    from sts_combat_rl.sim.resource_outcome import BATTLE_RESOURCE_OUTCOME_STATUSES

    if value not in BATTLE_RESOURCE_OUTCOME_STATUSES:
        raise ValueError(f"{label} has invalid value {value!r}")
    return str(value)


def _resource_outcome_payload(
    value: Any,
    *,
    status: str,
    label: str,
) -> dict[str, Any]:
    payload = _require_mapping(value, label)
    problems = battle_resource_outcome_problems(
        status,
        payload,
        label=label,
        require_available=status == BATTLE_RESOURCE_OUTCOME_AVAILABLE,
    )
    if problems:
        raise ValueError("; ".join(problems))
    return payload


def _source_run_summaries_from_metadata(
    value: Any,
    *,
    label: str,
) -> list[SourceRunSummary]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError(f"{label} must be a list")
    return [
        SourceRunSummary(**_validated_source_run_summary(item, f"{label} {index}"))
        for index, item in enumerate(value)
    ]


def _validated_source_run_summary(value: Any, label: str) -> dict[str, Any]:
    summary = _require_mapping(value, label)
    status = summary.get("status", SOURCE_RUN_SUMMARY_AVAILABLE)
    if status not in {
        SOURCE_RUN_SUMMARY_AVAILABLE,
        SOURCE_RUN_SUMMARY_LEGACY_UNAVAILABLE,
    }:
        raise ValueError(f"{label} has invalid source run summary status")
    problems = summary.get("problems", [])
    if not isinstance(problems, list) or not all(
        isinstance(problem, str) for problem in problems
    ):
        raise ValueError(f"{label} problems must be a string list")
    return {
        "source_run_id": _require_non_empty_string(
            summary.get("source_run_id"), f"{label} source_run_id"
        ),
        "source_seed": _require_seed(
            summary.get("source_seed"), f"{label} source_seed"
        ),
        "terminal": _require_bool(summary.get("terminal"), f"{label} terminal"),
        "outcome": _require_non_empty_string(
            summary.get("outcome"), f"{label} outcome"
        ),
        "final_floor": _optional_number(summary.get("final_floor")),
        "final_act": _optional_int(summary.get("final_act")),
        "final_screen_state": _require_non_empty_string(
            summary.get("final_screen_state"), f"{label} final_screen_state"
        ),
        "final_battle_active": _require_bool(
            summary.get("final_battle_active"), f"{label} final_battle_active"
        ),
        "captured_battle_start_count": _require_non_negative_int(
            summary.get("captured_battle_start_count"),
            f"{label} captured_battle_start_count",
        ),
        "completed_battle_count": _require_non_negative_int(
            summary.get("completed_battle_count"), f"{label} completed_battle_count"
        ),
        "max_battle_start_floor": _optional_number(
            summary.get("max_battle_start_floor")
        ),
        "max_battle_start_act": _optional_int(summary.get("max_battle_start_act")),
        "problem_count": _require_non_negative_int(
            summary.get("problem_count"), f"{label} problem_count"
        ),
        "problems": tuple(problems),
        "status": str(status),
    }


def _public_run_context(
    value: Any,
    *,
    public_context_status: str,
    label: str,
) -> dict[str, Any]:
    if public_context_status == PUBLIC_CONTEXT_LEGACY_UNAVAILABLE:
        if value not in (None, {}):
            raise ValueError(f"{label} legacy public context must be empty")
        return {}
    return sanitize_public_context_artifact(value, label=label)


def _migrate_pool_v1_to_v2(document: ArtifactDocument) -> ArtifactDocument:
    metadata = dict(document.metadata)
    metadata_non_combat_policy = metadata.pop("source_non_combat_policy", "(missing)")
    metadata_battle_policy = metadata.pop("source_battle_policy", "(missing)")
    non_combat = _legacy_provenance(metadata_non_combat_policy, "non-combat")
    battle = _legacy_provenance(metadata_battle_policy, "battle")
    metadata["source_controller_provenance"] = _legacy_routed_provenance(
        battle, non_combat
    )
    metadata["format_version"] = 2
    migrated_records: list[dict[str, Any]] = []
    for index, source in enumerate(document.records):
        raw = dict(source)
        record_non_combat = _legacy_provenance(
            raw.pop(
                "source_non_combat_policy",
                metadata_non_combat_policy,
            ),
            "non-combat",
        )
        record_battle = _legacy_provenance(
            raw.pop(
                "source_battle_policy",
                metadata_battle_policy,
            ),
            "battle",
        )
        trace = raw.get("action_trace", [])
        if not isinstance(trace, list):
            raise ValueError(f"v1 record {index} action_trace must be a list")
        raw["action_trace"] = [
            {"action_id": action_id, "occurrence": None} for action_id in trace
        ]
        raw["source_checkpoint_id"] = raw.pop("checkpoint_id", None)
        raw["source_seed"] = raw.pop("seed", None)
        raw["source_battle_index"] = raw.pop("battle_index", None)
        raw["structural_metadata"] = {
            "ascension": raw.pop("ascension", None),
            "act": raw.pop("act", None),
            "floor": raw.pop("floor", None),
            "room_type": raw.pop("room_type", None),
            "encounter_id": raw.pop("encounter_id", None),
            "seed": raw.get("source_seed"),
            "source_kind": NATURAL_DISTRIBUTION_KIND,
            "distribution_kind": NATURAL_DISTRIBUTION_KIND,
            "source_run_id": raw.get("source_run_id"),
            "source_battle_index": raw.get("source_battle_index"),
        }
        raw["snapshot_observation"] = raw.pop("observation", None)
        raw["snapshot_raw"] = raw.pop("raw_snapshot", None)
        raw["source_battle_controller_provenance"] = record_battle
        raw["source_non_combat_controller_provenance"] = record_non_combat
        raw["source_controller_provenance"] = _legacy_routed_provenance(
            record_battle, record_non_combat
        )
        raw["battle_outcome"] = None
        raw["battle_completed"] = False
        raw["distribution_kind"] = NATURAL_DISTRIBUTION_KIND
        raw["checkpoint_information_regime"] = LEGACY_UNKNOWN_INFORMATION_REGIME
        raw["public_context_status"] = PUBLIC_CONTEXT_LEGACY_UNAVAILABLE
        migrated_records.append(raw)
    return ArtifactDocument(metadata=metadata, records=migrated_records)


def _migrate_pool_v2_to_v3(document: ArtifactDocument) -> ArtifactDocument:
    metadata = dict(document.metadata)
    metadata["format_version"] = PUBLIC_CONTEXT_POOL_FORMAT_VERSION
    migrated_records: list[dict[str, Any]] = []
    for source in document.records:
        raw = dict(source)
        status = raw.get("public_context_status")
        if status in (None, "unavailable"):
            raw["public_context_status"] = PUBLIC_CONTEXT_LEGACY_UNAVAILABLE
        raw["public_run_context"] = {}
        migrated_records.append(raw)
    return ArtifactDocument(metadata=metadata, records=migrated_records)


def _migrate_pool_v3_to_v4(document: ArtifactDocument) -> ArtifactDocument:
    metadata = dict(document.metadata)
    metadata["format_version"] = STRUCTURED_RESOURCE_OUTCOME_POOL_FORMAT_VERSION
    status, payload = legacy_unavailable_battle_resource_outcome()
    migrated_records: list[dict[str, Any]] = []
    for source in document.records:
        raw = dict(source)
        raw["completed_battle_resource_outcome_status"] = status
        raw["completed_battle_resource_outcome"] = payload
        migrated_records.append(raw)
    return ArtifactDocument(metadata=metadata, records=migrated_records)


def _legacy_provenance(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, str) or not value:
        raise ValueError(f"v1 {label} policy name is missing")
    return legacy_policy_provenance(value).to_dict()


def _legacy_routed_provenance(
    battle: Mapping[str, Any],
    non_combat: Mapping[str, Any],
) -> dict[str, Any]:
    provenance = ControllerProvenance(
        kind="routed_run",
        name=f"{battle['name']}+{non_combat['name']}",
        config={
            "battle": dict(battle),
            "non_combat": dict(non_combat),
            "reproducible": False,
        },
    )
    return provenance.to_dict()


def _write_row(stream: TextIO, row: Mapping[str, Any]) -> None:
    stream.write(json.dumps(row, sort_keys=True, allow_nan=False))
    stream.write("\n")


def _json_safe_mapping(value: Mapping[str, Any]) -> dict[str, Any]:
    return {str(key): _json_safe_value(item) for key, item in value.items()}


def _json_safe_value(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Mapping):
        return _json_safe_mapping(value)
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return [_json_safe_value(item) for item in value]
    raise ValueError(f"artifact value is not JSON-safe: {type(value).__name__}")


def _require_mapping(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} must be an object")
    return {str(key): item for key, item in value.items()}


def _require_non_empty_string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{label} must be a non-empty string")
    return value


def _require_non_negative_int(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{label} must be a non-negative integer")
    return value


def _require_bool(value: Any, label: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{label} must be a boolean")
    return value


def _require_seed(value: Any, label: str) -> int:
    return _require_non_negative_int(value, label)


def _require_string_list(value: Any, label: str) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError(f"{label} must be a string list")
    return list(value)


def _optional_int(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    raise ValueError("optional integer field must be an integer or null")


def _optional_number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    raise ValueError("optional numeric field must be numeric or null")


def _max_optional_number(values: Iterable[Any]) -> float | None:
    converted = [_optional_number(value) for value in values]
    present = [value for value in converted if value is not None]
    return max(present) if present else None


def _max_optional_int(values: Iterable[Any]) -> int | None:
    converted = [_optional_int(value) for value in values]
    present = [value for value in converted if value is not None]
    return max(present) if present else None


def _append_counter(lines: list[str], counter: Counter[str]) -> None:
    if not counter:
        lines.append("  (none)")
        return
    for key, count in counter.most_common():
        lines.append(f"  {key}: {count}")
