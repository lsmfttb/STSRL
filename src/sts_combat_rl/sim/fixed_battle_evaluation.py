"""Restored-battle controller evaluation and versioned result reports.

Evaluates one cohort by restoring each portable record in a fresh adapter,
playing one bounded battle with an explicit ``OnlineController``, and producing
a versioned evaluation report with per-battle and aggregate results.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
import json
import time
from typing import Any, TextIO

from sts_combat_rl.sim.action_space import (
    ActionSpaceConfig,
)
from sts_combat_rl.sim.artifact_versioning import (
    ArtifactMigration,
    ArtifactMigrationReport,
    migrate_artifact_document,
    preserved_migration_report,
)
from sts_combat_rl.sim.contract import (
    CheckpointingSimulatorAdapter,
    SimulatorSnapshot,
)
from sts_combat_rl.sim.controller_contract import (
    ControllerDecision,
    OnlineController,
    selected_index_problem,
)
from sts_combat_rl.sim.controlled_run import build_decision_context
from sts_combat_rl.sim.decision_record import find_action_index_by_identity
from sts_combat_rl.sim.fixed_evaluation_set import (
    FixedCohortRecord,
)


FIXED_EVALUATION_REPORT_FORMAT_VERSION = 1
"""Current schema version for the fixed evaluation report."""

FIXED_EVALUATION_REPORT_MIGRATIONS: tuple[ArtifactMigration, ...] = ()
"""Sequential migrations; empty for version 1."""


@dataclass(frozen=True)
class SingleBattleEvaluationResult:
    """Per-battle evaluation result for one restored cohort record."""

    cohort_index: int
    source_checkpoint_id: str
    source_seed: int
    source_run_id: str
    source_battle_index: int
    structural_stratum: tuple[Any, ...]
    structural_metadata: dict[str, Any]
    restoration_method: str
    controller_provenance: dict[str, Any]
    information_regime: str
    action_space_config: dict[str, Any]
    termination_status: str  # "win", "loss", "truncated", "error"
    terminal_absolute_hp: int | None
    hp_loss: int | None
    decision_count: int
    simulator_step_count: int
    wall_clock_time_s: float
    controller_compute_telemetry: dict[str, Any] | None = None
    battle_initial_hp: int | None = None
    battle_initial_max_hp: int | None = None
    problems: list[str] = field(default_factory=list)

    @property
    def is_authoritative_win(self) -> bool:
        return self.termination_status == "win"

    @property
    def is_error(self) -> bool:
        return self.termination_status == "error"

    @property
    def is_truncated(self) -> bool:
        return self.termination_status == "truncated"


@dataclass(frozen=True)
class FixedEvaluationReport:
    """Versioned fixed evaluation report with per-battle and aggregate results."""

    cohort_identity: str
    controller_provenance: dict[str, Any]
    information_regime: str
    action_space_config: dict[str, Any]
    max_battle_steps: int
    source_pool_format_version: int
    selection_config: dict[str, Any]
    format_version: int = FIXED_EVALUATION_REPORT_FORMAT_VERSION
    battle_results: list[SingleBattleEvaluationResult] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)
    migration_report: ArtifactMigrationReport = field(
        default_factory=lambda: ArtifactMigrationReport(
            source_version=FIXED_EVALUATION_REPORT_FORMAT_VERSION,
            target_version=FIXED_EVALUATION_REPORT_FORMAT_VERSION,
        ),
        compare=False,
    )

    @property
    def total_battles(self) -> int:
        return len(self.battle_results)

    @property
    def authoritative_wins(self) -> int:
        return sum(1 for r in self.battle_results if r.is_authoritative_win)

    @property
    def losses(self) -> int:
        return sum(1 for r in self.battle_results if r.termination_status == "loss")

    @property
    def truncations(self) -> int:
        return sum(1 for r in self.battle_results if r.is_truncated)

    @property
    def errors(self) -> int:
        return sum(1 for r in self.battle_results if r.is_error)

    @property
    def evaluation_successful(self) -> bool:
        return self.truncations == 0 and self.errors == 0 and not self.problems


@dataclass(frozen=True)
class FixedEvaluationAggregate:
    """Aggregate statistics sliced four ways."""

    natural_weighted: AggregateSlice
    encounter_macro: dict[str, AggregateSlice]
    room_type_macro: dict[str, AggregateSlice]
    per_stratum: dict[tuple[Any, ...], AggregateSlice]


@dataclass(frozen=True)
class AggregateSlice:
    """One aggregate view of evaluation results."""

    battle_count: int = 0
    win_count: int = 0
    loss_count: int = 0
    truncated_count: int = 0
    error_count: int = 0
    total_hp_loss: int | None = None
    total_decision_count: int = 0
    total_wall_clock_time_s: float = 0.0
    result_indices: list[int] = field(default_factory=list)

    @property
    def win_rate(self) -> float | None:
        resolvable = self.win_count + self.loss_count
        if resolvable == 0:
            return None
        return self.win_count / resolvable

    @property
    def mean_hp_loss(self) -> float | None:
        if self.total_hp_loss is None:
            return None
        resolvable = self.win_count + self.loss_count
        if resolvable == 0:
            return None
        return self.total_hp_loss / resolvable


def evaluate_fixed_cohort(
    adapter_factory: Callable[[], CheckpointingSimulatorAdapter],
    cohort_records: Sequence[FixedCohortRecord],
    controller: OnlineController,
    *,
    cohort_identity: str,
    source_pool_format_version: int,
    selection_config: dict[str, Any],
    action_space: ActionSpaceConfig | None = None,
    max_battle_steps: int = 200,
) -> FixedEvaluationReport:
    """Restore each cohort record in a fresh adapter and play one bounded battle.

    Every battle starts from a fresh adapter instance so an in-memory checkpoint
    cannot accidentally substitute for replay restore.

    Returns a versioned evaluation report.  Truncations, restore failures, and
    errors are recorded but also reported as report-level problems.
    """

    if max_battle_steps < 1:
        raise ValueError("max_battle_steps must be positive")

    active_action_space = action_space or ActionSpaceConfig.initial_no_potions()
    controller_provenance = controller.provenance.to_dict()
    information_regime = str(
        controller.provenance.config.get("information_regime", "normal_public_policy")
    )
    battle_results: list[SingleBattleEvaluationResult] = []
    report_problems: list[str] = []

    for cohort_record in cohort_records:
        t_start = time.perf_counter()
        result = _evaluate_one_battle(
            adapter_factory=adapter_factory,
            cohort_record=cohort_record,
            controller=controller,
            active_action_space=active_action_space,
            max_battle_steps=max_battle_steps,
        )
        t_end = time.perf_counter()
        result = SingleBattleEvaluationResult(
            cohort_index=result.cohort_index,
            source_checkpoint_id=result.source_checkpoint_id,
            source_seed=result.source_seed,
            source_run_id=result.source_run_id,
            source_battle_index=result.source_battle_index,
            structural_stratum=result.structural_stratum,
            structural_metadata=result.structural_metadata,
            restoration_method=result.restoration_method,
            controller_provenance=controller_provenance,
            information_regime=information_regime,
            action_space_config=active_action_space.to_dict(),
            termination_status=result.termination_status,
            terminal_absolute_hp=result.terminal_absolute_hp,
            hp_loss=result.hp_loss,
            decision_count=result.decision_count,
            simulator_step_count=result.simulator_step_count,
            wall_clock_time_s=t_end - t_start,
            controller_compute_telemetry=result.controller_compute_telemetry,
            battle_initial_hp=result.battle_initial_hp,
            battle_initial_max_hp=result.battle_initial_max_hp,
            problems=result.problems,
        )
        battle_results.append(result)

        if result.is_truncated:
            report_problems.append(
                f"cohort index {result.cohort_index}: battle truncated at "
                f"{max_battle_steps} steps"
            )
        if result.is_error:
            report_problems.append(
                f"cohort index {result.cohort_index}: evaluation error — "
                + "; ".join(result.problems)
            )

    return FixedEvaluationReport(
        cohort_identity=cohort_identity,
        controller_provenance=controller_provenance,
        information_regime=information_regime,
        action_space_config=active_action_space.to_dict(),
        max_battle_steps=max_battle_steps,
        source_pool_format_version=source_pool_format_version,
        selection_config=selection_config,
        battle_results=battle_results,
        problems=report_problems,
    )


def _evaluate_one_battle(
    *,
    adapter_factory: Callable[[], CheckpointingSimulatorAdapter],
    cohort_record: FixedCohortRecord,
    controller: OnlineController,
    active_action_space: ActionSpaceConfig,
    max_battle_steps: int,
) -> SingleBattleEvaluationResult:
    """Restore one record and play one bounded battle with the controller."""

    problems: list[str] = []

    # Fresh adapter per record.
    adapter = adapter_factory()

    # Restore the battle start.
    try:
        snapshot, restoration_method = _restore_cohort_record(adapter, cohort_record)
    except (RuntimeError, ValueError) as exc:
        return SingleBattleEvaluationResult(
            cohort_index=cohort_record.cohort_index,
            source_checkpoint_id=cohort_record.source_checkpoint_id,
            source_seed=cohort_record.source_seed,
            source_run_id=cohort_record.source_run_id,
            source_battle_index=cohort_record.source_battle_index,
            structural_stratum=cohort_record.structural_stratum,
            structural_metadata=cohort_record.structural_metadata,
            restoration_method="failed",
            controller_provenance={},
            information_regime="",
            action_space_config=active_action_space.to_dict(),
            termination_status="error",
            terminal_absolute_hp=None,
            hp_loss=None,
            decision_count=0,
            simulator_step_count=0,
            wall_clock_time_s=0.0,
            problems=[f"restore failed: {exc}"],
        )

    # Record initial HP.
    initial_hp = _player_hp(snapshot.raw)
    initial_max_hp = _player_max_hp(snapshot.raw)

    # Play battle actions.
    decision_count = 0
    simulator_step_count = 0
    termination_status = "error"
    current = snapshot

    for step_index in range(max_battle_steps):
        simulator_step_count += 1
        actions = list(adapter.legal_actions(current))
        if not actions:
            # No legal actions — check if battle is over.
            outcome = _battle_outcome(current.raw)
            if outcome == "PLAYER_VICTORY":
                termination_status = "win"
            elif outcome == "PLAYER_LOSS" or outcome is not None:
                termination_status = "loss"
            else:
                problems.append("no legal actions without terminal outcome")
                termination_status = "error"
            break

        context = build_decision_context(current.raw, actions, active_action_space)

        try:
            decision = controller.select_action(
                adapter, current, actions, context, step_index
            )
        except (RuntimeError, ValueError) as exc:
            problems.append(f"controller error at step {step_index}: {exc}")
            termination_status = "error"
            break

        controller_label = _controller_label(decision)
        validation_problem = selected_index_problem(
            decision.selected_index,
            len(actions),
            context.eligible_action_indices,
            controller_label,
        )
        if validation_problem is not None:
            problems.append(validation_problem)
            termination_status = "error"
            break

        decision_count += 1
        chosen_action = actions[decision.selected_index]
        transition = adapter.step(chosen_action)
        current = transition.snapshot

        if transition.terminal or not _is_battle_state(current):
            outcome = _battle_outcome(current.raw)
            if outcome == "PLAYER_VICTORY":
                termination_status = "win"
            elif outcome == "PLAYER_LOSS" or outcome is not None:
                termination_status = "loss"
            else:
                # Battle ended but outcome unclear — check HP.
                final_hp = _player_hp(current.raw)
                if final_hp is not None and final_hp <= 0:
                    termination_status = "loss"
                else:
                    termination_status = "loss"  # conservative
            break
    else:
        termination_status = "truncated"
        problems.append(f"battle did not finish within {max_battle_steps} steps")

    # Compute terminal HP and HP loss.
    terminal_hp = _player_hp(current.raw)
    hp_loss: int | None = None
    if initial_hp is not None and terminal_hp is not None:
        hp_loss = initial_hp - terminal_hp

    return SingleBattleEvaluationResult(
        cohort_index=cohort_record.cohort_index,
        source_checkpoint_id=cohort_record.source_checkpoint_id,
        source_seed=cohort_record.source_seed,
        source_run_id=cohort_record.source_run_id,
        source_battle_index=cohort_record.source_battle_index,
        structural_stratum=cohort_record.structural_stratum,
        structural_metadata=cohort_record.structural_metadata,
        restoration_method=restoration_method,
        controller_provenance={},  # filled in by caller
        information_regime="",  # filled in by caller
        action_space_config=active_action_space.to_dict(),
        termination_status=termination_status,
        terminal_absolute_hp=int(terminal_hp) if terminal_hp is not None else None,
        hp_loss=int(hp_loss) if hp_loss is not None else None,
        decision_count=decision_count,
        simulator_step_count=simulator_step_count,
        wall_clock_time_s=0.0,  # filled in by caller
        battle_initial_hp=int(initial_hp) if initial_hp is not None else None,
        battle_initial_max_hp=int(initial_max_hp)
        if initial_max_hp is not None
        else None,
        problems=problems,
    )


def build_evaluation_aggregates(
    report: FixedEvaluationReport,
) -> FixedEvaluationAggregate:
    """Compute natural-weighted, encounter-macro, room-type-macro, per-stratum."""

    resolved = [r for r in report.battle_results if not r.is_error]

    # Natural-weighted: all successfully evaluated battles.
    natural_weighted = _build_aggregate_slice(resolved)

    # Encounter-macro: average over encounter identity groups.
    encounter_groups: dict[str, list[SingleBattleEvaluationResult]] = {}
    for r in resolved:
        encounter_id = (
            r.structural_stratum[3] if len(r.structural_stratum) > 3 else "unknown"
        )
        key = str(encounter_id)
        encounter_groups.setdefault(key, []).append(r)

    encounter_macro: dict[str, AggregateSlice] = {}
    for enc_id, results in encounter_groups.items():
        encounter_macro[enc_id] = _build_aggregate_slice(results)

    # Room-type-macro: average over room_type groups.
    room_groups: dict[str, list[SingleBattleEvaluationResult]] = {}
    for r in resolved:
        room_type = (
            r.structural_stratum[2] if len(r.structural_stratum) > 2 else "unknown"
        )
        key = str(room_type)
        room_groups.setdefault(key, []).append(r)

    room_type_macro: dict[str, AggregateSlice] = {}
    for rt, results in room_groups.items():
        room_type_macro[rt] = _build_aggregate_slice(results)

    # Per-stratum: one slice per exact stratum.
    stratum_groups: dict[tuple[Any, ...], list[SingleBattleEvaluationResult]] = {}
    for r in resolved:
        stratum = r.structural_stratum
        stratum_groups.setdefault(stratum, []).append(r)

    per_stratum: dict[tuple[Any, ...], AggregateSlice] = {}
    for stratum, results in stratum_groups.items():
        per_stratum[stratum] = _build_aggregate_slice(results)

    return FixedEvaluationAggregate(
        natural_weighted=natural_weighted,
        encounter_macro=encounter_macro,
        room_type_macro=room_type_macro,
        per_stratum=per_stratum,
    )


def _build_aggregate_slice(
    results: list[SingleBattleEvaluationResult],
) -> AggregateSlice:
    indices = [r.cohort_index for r in results]
    win_count = sum(1 for r in results if r.is_authoritative_win)
    loss_count = sum(1 for r in results if r.termination_status == "loss")
    truncated_count = sum(1 for r in results if r.is_truncated)
    error_count = sum(1 for r in results if r.is_error)

    hp_losses = [r.hp_loss for r in results if r.hp_loss is not None]
    total_hp_loss = sum(hp_losses) if hp_losses else None

    return AggregateSlice(
        battle_count=len(results),
        win_count=win_count,
        loss_count=loss_count,
        truncated_count=truncated_count,
        error_count=error_count,
        total_hp_loss=total_hp_loss,
        total_decision_count=sum(r.decision_count for r in results),
        total_wall_clock_time_s=sum(r.wall_clock_time_s for r in results),
        result_indices=indices,
    )


def dump_fixed_evaluation_report_jsonl(
    report: FixedEvaluationReport,
    stream: TextIO,
) -> None:
    """Write a current-schema evaluation report to a portable JSONL stream."""

    metadata: dict[str, Any] = {
        "format_version": FIXED_EVALUATION_REPORT_FORMAT_VERSION,
        "cohort_identity": report.cohort_identity,
        "controller_provenance": report.controller_provenance,
        "information_regime": report.information_regime,
        "action_space_config": report.action_space_config,
        "max_battle_steps": report.max_battle_steps,
        "source_pool_format_version": report.source_pool_format_version,
        "selection_config": report.selection_config,
        "battle_count": len(report.battle_results),
        "authoritative_wins": report.authoritative_wins,
        "losses": report.losses,
        "truncations": report.truncations,
        "errors": report.errors,
        "evaluation_successful": report.evaluation_successful,
        "migration_report": report.migration_report.to_dict(),
        "problems": list(report.problems),
    }
    _write_row(stream, {"type": "metadata", "metadata": metadata})
    for result in report.battle_results:
        _write_row(
            stream,
            {"type": "result", "result": _eval_result_to_manifest(result)},
        )


def load_fixed_evaluation_report_jsonl(
    stream: TextIO,
) -> FixedEvaluationReport:
    """Load and migrate a portable fixed evaluation report."""

    metadata: dict[str, Any] | None = None
    raw_results: list[dict[str, Any]] = []
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
        elif row.get("type") == "result":
            raw_results.append(_require_mapping(row.get("result"), "result"))
        else:
            raise ValueError(f"line {line_number}: unknown row type")
    if metadata is None:
        raise ValueError("missing evaluation report metadata")

    migrated = migrate_artifact_document(
        metadata,
        raw_results,
        current_version=FIXED_EVALUATION_REPORT_FORMAT_VERSION,
        migrations=FIXED_EVALUATION_REPORT_MIGRATIONS,
        artifact_name="fixed evaluation report",
    )
    metadata = migrated.document.metadata

    battle_results = [
        _eval_result_from_manifest(raw, label=f"result {index}")
        for index, raw in enumerate(migrated.document.records)
    ]

    report = FixedEvaluationReport(
        cohort_identity=_require_non_empty_string(
            metadata.get("cohort_identity"), "cohort_identity"
        ),
        controller_provenance=_require_mapping(
            metadata.get("controller_provenance"), "controller_provenance"
        ),
        information_regime=_require_non_empty_string(
            metadata.get("information_regime"), "information_regime"
        ),
        action_space_config=_require_mapping(
            metadata.get("action_space_config"), "action_space_config"
        ),
        max_battle_steps=_require_non_negative_int(
            metadata.get("max_battle_steps"), "max_battle_steps"
        ),
        source_pool_format_version=_require_non_negative_int(
            metadata.get("source_pool_format_version"), "source_pool_format_version"
        ),
        selection_config=_require_mapping(
            metadata.get("selection_config"), "selection_config"
        ),
        battle_results=battle_results,
        problems=_require_string_list(
            metadata.get("problems", []), "metadata problems"
        ),
        migration_report=preserved_migration_report(
            metadata,
            migrated.report,
            artifact_name="fixed evaluation report",
        ),
    )
    return report


def format_fixed_evaluation_report(report: FixedEvaluationReport) -> str:
    """Format a fixed evaluation report for stderr output."""

    aggregates = build_evaluation_aggregates(report)

    lines = ["Fixed battle evaluation report"]
    lines.append(f"cohort identity: {report.cohort_identity}")
    lines.append(f"controller: {report.controller_provenance.get('name', '(unknown)')}")
    lines.append(f"information regime: {report.information_regime}")
    lines.append(f"max battle steps: {report.max_battle_steps}")
    lines.append(f"total battles: {report.total_battles}")
    lines.append(f"authoritative wins: {report.authoritative_wins}")
    lines.append(f"losses: {report.losses}")
    lines.append(f"truncations: {report.truncations}")
    lines.append(f"errors: {report.errors}")
    lines.append(
        f"evaluation successful: {'yes' if report.evaluation_successful else 'no'}"
    )

    # Natural-weighted.
    nw = aggregates.natural_weighted
    lines.append("")
    lines.append("── natural-weighted aggregate ──")
    lines.append(f"  battles: {nw.battle_count}")
    lines.append(f"  wins: {nw.win_count}  losses: {nw.loss_count}")
    wr = nw.win_rate
    lines.append(
        f"  win rate (wins/(wins+losses)): {wr:.4f}"
        if wr is not None
        else "  win rate: N/A"
    )
    mhl = nw.mean_hp_loss
    lines.append(
        f"  mean HP loss: {mhl:.1f}" if mhl is not None else "  mean HP loss: N/A"
    )
    lines.append(f"  total decisions: {nw.total_decision_count}")
    lines.append(f"  truncations: {nw.truncated_count}  errors: {nw.error_count}")

    # Encounter-macro.
    lines.append("")
    lines.append(
        f"── encounter-macro ({len(aggregates.encounter_macro)} encounters) ──"
    )
    for enc_id, slc in sorted(aggregates.encounter_macro.items()):
        wr_str = (
            f"  win rate: {slc.win_rate:.4f}"
            if slc.win_rate is not None
            else "  win rate: N/A"
        )
        lines.append(
            f"  {enc_id}: {slc.battle_count} battles, {slc.win_count}W/{slc.loss_count}L, {wr_str}"
        )

    # Room-type-macro.
    lines.append("")
    lines.append(f"── room-type-macro ({len(aggregates.room_type_macro)} types) ──")
    for rt, slc in sorted(aggregates.room_type_macro.items()):
        wr_str = (
            f"  win rate: {slc.win_rate:.4f}"
            if slc.win_rate is not None
            else "  win rate: N/A"
        )
        lines.append(
            f"  {rt}: {slc.battle_count} battles, {slc.win_count}W/{slc.loss_count}L, {wr_str}"
        )

    # Per-stratum.
    lines.append("")
    lines.append(f"── per-stratum ({len(aggregates.per_stratum)} strata) ──")
    for stratum, slc in sorted(
        aggregates.per_stratum.items(), key=lambda x: repr(x[0])
    ):
        wr_str = (
            f"  win rate: {slc.win_rate:.4f}"
            if slc.win_rate is not None
            else "  win rate: N/A"
        )
        stratum_str = "/".join(str(v) for v in stratum)
        lines.append(
            f"  [{stratum_str}]: {slc.battle_count} battles, {slc.win_count}W/{slc.loss_count}L, {wr_str}"
        )

    lines.append("")
    lines.append("problems:")
    if report.problems:
        lines.extend(f"  - {p}" for p in report.problems)
    else:
        lines.append("  (none)")

    return "\n".join(lines)


def _restore_cohort_record(
    adapter: CheckpointingSimulatorAdapter,
    cohort_record: FixedCohortRecord,
) -> tuple[SimulatorSnapshot, str]:
    """Restore a cohort record by replaying seed + action trace in a fresh adapter.

    This deliberately does NOT use restore_battle_start_record because cohort
    records do not carry snapshot_observation/snapshot_raw needed for fingerprint
    matching.  Instead it performs the seed/action-trace replay directly.
    """

    snapshot = adapter.reset(seed=cohort_record.source_seed)
    for trace_index, identity in enumerate(cohort_record.action_trace):
        actions = list(adapter.legal_actions(snapshot))
        index = find_action_index_by_identity(actions, identity)
        snapshot = adapter.step(actions[index]).snapshot
    return snapshot, "seed_action_trace"


# ── Battle-state helpers ────────────────────────────────────────────────────


def _is_battle_state(snapshot: SimulatorSnapshot) -> bool:
    raw = snapshot.raw
    return (
        bool(raw.get("battle_active")) or str(raw.get("screen_state", "")) == "BATTLE"
    )


def _player_hp(data: Mapping[str, Any]) -> int | None:
    for key in ("cur_hp", "current_hp"):
        value = data.get(key)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return int(value)
    battle_player = data.get("battle_player")
    if isinstance(battle_player, Mapping):
        for key in ("current_hp", "cur_hp"):
            value = battle_player.get(key)
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                return int(value)
    player = data.get("player")
    if isinstance(player, Mapping):
        for key in ("current_hp", "cur_hp"):
            value = player.get(key)
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                return int(value)
    return None


def _player_max_hp(data: Mapping[str, Any]) -> int | None:
    for key in ("max_hp", "maxHp"):
        value = data.get(key)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return int(value)
    battle_player = data.get("battle_player")
    if isinstance(battle_player, Mapping):
        for key in ("max_hp", "maxHp"):
            value = battle_player.get(key)
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                return int(value)
    player = data.get("player")
    if isinstance(player, Mapping):
        for key in ("max_hp", "maxHp"):
            value = player.get(key)
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                return int(value)
    return None


def _battle_outcome(data: Mapping[str, Any]) -> str | None:
    for field_name in ("completed_battle_outcome", "battle_outcome"):
        value = data.get(field_name)
        if isinstance(value, str) and value and value != "UNDECIDED":
            return value
    value = data.get("outcome")
    if isinstance(value, str) and value and value != "UNDECIDED":
        return value
    return None


def _controller_label(decision: ControllerDecision) -> str:
    return str(decision.metadata.get("controller_role", decision.provenance.identity))


# ── Serialization helpers ───────────────────────────────────────────────────


def _eval_result_to_manifest(result: SingleBattleEvaluationResult) -> dict[str, Any]:
    return {
        "cohort_index": result.cohort_index,
        "source_checkpoint_id": result.source_checkpoint_id,
        "source_seed": result.source_seed,
        "source_run_id": result.source_run_id,
        "source_battle_index": result.source_battle_index,
        "structural_stratum": list(result.structural_stratum),
        "structural_metadata": _json_safe_mapping(result.structural_metadata),
        "restoration_method": result.restoration_method,
        "controller_provenance": result.controller_provenance,
        "information_regime": result.information_regime,
        "action_space_config": result.action_space_config,
        "termination_status": result.termination_status,
        "terminal_absolute_hp": result.terminal_absolute_hp,
        "hp_loss": result.hp_loss,
        "decision_count": result.decision_count,
        "simulator_step_count": result.simulator_step_count,
        "wall_clock_time_s": result.wall_clock_time_s,
        "controller_compute_telemetry": result.controller_compute_telemetry,
        "battle_initial_hp": result.battle_initial_hp,
        "battle_initial_max_hp": result.battle_initial_max_hp,
        "problems": list(result.problems),
    }


def _eval_result_from_manifest(
    raw: Mapping[str, Any],
    *,
    label: str,
) -> SingleBattleEvaluationResult:
    stratum_raw = raw.get("structural_stratum")
    if not isinstance(stratum_raw, list):
        raise ValueError(f"{label} structural_stratum must be a list")

    return SingleBattleEvaluationResult(
        cohort_index=_require_non_negative_int(
            raw.get("cohort_index"), f"{label} cohort_index"
        ),
        source_checkpoint_id=_require_non_empty_string(
            raw.get("source_checkpoint_id"), f"{label} source_checkpoint_id"
        ),
        source_seed=_require_seed(raw.get("source_seed"), f"{label} source_seed"),
        source_run_id=_require_non_empty_string(
            raw.get("source_run_id"), f"{label} source_run_id"
        ),
        source_battle_index=_require_non_negative_int(
            raw.get("source_battle_index"), f"{label} source_battle_index"
        ),
        structural_stratum=tuple(stratum_raw),
        structural_metadata=_require_mapping(
            raw.get("structural_metadata"), f"{label} structural_metadata"
        ),
        restoration_method=_require_non_empty_string(
            raw.get("restoration_method"), f"{label} restoration_method"
        ),
        controller_provenance=_require_mapping(
            raw.get("controller_provenance"), f"{label} controller_provenance"
        ),
        information_regime=_require_non_empty_string(
            raw.get("information_regime"), f"{label} information_regime"
        ),
        action_space_config=_require_mapping(
            raw.get("action_space_config"), f"{label} action_space_config"
        ),
        termination_status=_require_non_empty_string(
            raw.get("termination_status"), f"{label} termination_status"
        ),
        terminal_absolute_hp=_optional_int(
            raw.get("terminal_absolute_hp"), f"{label} terminal_absolute_hp"
        ),
        hp_loss=_optional_int(raw.get("hp_loss"), f"{label} hp_loss"),
        decision_count=_require_non_negative_int(
            raw.get("decision_count"), f"{label} decision_count"
        ),
        simulator_step_count=_require_non_negative_int(
            raw.get("simulator_step_count"), f"{label} simulator_step_count"
        ),
        wall_clock_time_s=_optional_float(
            raw.get("wall_clock_time_s"), f"{label} wall_clock_time_s"
        ),
        controller_compute_telemetry=_optional_mapping(
            raw.get("controller_compute_telemetry")
        ),
        battle_initial_hp=_optional_int(
            raw.get("battle_initial_hp"), f"{label} battle_initial_hp"
        ),
        battle_initial_max_hp=_optional_int(
            raw.get("battle_initial_max_hp"), f"{label} battle_initial_max_hp"
        ),
        problems=_require_string_list(raw.get("problems", []), f"{label} problems"),
    )


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


def _require_seed(value: Any, label: str) -> int:
    return _require_non_negative_int(value, label)


def _require_string_list(value: Any, label: str) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError(f"{label} must be a string list")
    return list(value)


def _optional_int(value: Any, label: str) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{label} must be an integer or null")
    return value


def _optional_float(value: Any, label: str) -> float:
    if value is None:
        return 0.0
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} must be a number or null")
    return float(value)


def _optional_mapping(value: Any) -> dict[str, Any] | None:
    if value is None:
        return None
    if not isinstance(value, Mapping):
        raise ValueError("controller compute telemetry must be an object or null")
    return {str(key): item for key, item in value.items()}
