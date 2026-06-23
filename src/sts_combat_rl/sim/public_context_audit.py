"""WSL-facing public-context artifact, replay, and coverage audit."""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from typing import Any

from sts_combat_rl.sim.action_space import ActionSpaceConfig
from sts_combat_rl.sim.battle_start_pool import (
    CHECKPOINT_INFORMATION_REGIME,
    NATURAL_DISTRIBUTION_KIND,
    BattleStartCheckpointRecord,
    NaturalBattleStartPool,
    verify_battle_start_pool_restores,
)
from sts_combat_rl.sim.contract import (
    CheckpointingSimulatorAdapter,
    SimulatorAction,
    SimulatorSnapshot,
)
from sts_combat_rl.sim.controlled_run import ControlledRunStep, execute_controlled_run
from sts_combat_rl.sim.decision_record import source_metadata_from_snapshot
from sts_combat_rl.sim.native_public_projection import KNOWN_SCREEN_STATES
from sts_combat_rl.sim.online_controller import PolicyController, RoutedRunController
from sts_combat_rl.sim.policy import PreferredKindPolicy, StochasticNonCombatDriver
from sts_combat_rl.sim.lightspeed_source import (
    format_lightspeed_source_identity,
    lightspeed_source_identity_dict,
)
from sts_combat_rl.sim.public_context_artifacts import (
    PUBLIC_CONTEXT_AVAILABLE,
    public_context_artifact_problems,
    public_context_missing_paths,
    sanitize_public_context_artifact,
)
from sts_combat_rl.sim.public_run_context import forbidden_public_context_problems


PUBLIC_CONTEXT_AUDIT_REPORT_SCHEMA_ID = "public-context-artifact-audit-v1"


@dataclass(frozen=True)
class PublicContextArtifactAuditReport:
    """Focused T016 audit report for persisted public context readiness."""

    report_schema_id: str = PUBLIC_CONTEXT_AUDIT_REPORT_SCHEMA_ID
    source_identity: dict[str, Any] = field(
        default_factory=lightspeed_source_identity_dict
    )
    requested_episodes: int = 0
    completed_episodes: int = 0
    max_steps: int = 0
    decisions_observed: int = 0
    screen_counts: Counter[str] = field(default_factory=Counter)
    coverage_gaps: list[str] = field(default_factory=list)
    candidate_parity_passes: int = 0
    candidate_parity_failures: int = 0
    context_available_count: int = 0
    context_schema_failures: int = 0
    forbidden_field_failures: int = 0
    missing_path_counts: Counter[str] = field(default_factory=Counter)
    replay_checked_count: int = 0
    replay_matched_count: int = 0
    replay_mismatch_count: int = 0
    replay_legacy_loss_count: int = 0
    run_failure_count: int = 0
    battle_start_record_count: int = 0
    problems: list[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return (
            self.decisions_observed > 0
            and self.candidate_parity_failures == 0
            and self.context_schema_failures == 0
            and self.forbidden_field_failures == 0
            and self.replay_mismatch_count == 0
            and self.run_failure_count == 0
            and not self.problems
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "report_schema_id": self.report_schema_id,
            "source_identity": dict(self.source_identity),
            "requested_episodes": self.requested_episodes,
            "completed_episodes": self.completed_episodes,
            "max_steps": self.max_steps,
            "decisions_observed": self.decisions_observed,
            "screen_counts": dict(sorted(self.screen_counts.items())),
            "coverage_gaps": list(self.coverage_gaps),
            "candidate_parity_passes": self.candidate_parity_passes,
            "candidate_parity_failures": self.candidate_parity_failures,
            "context_available_count": self.context_available_count,
            "context_schema_failures": self.context_schema_failures,
            "forbidden_field_failures": self.forbidden_field_failures,
            "missing_path_counts": dict(sorted(self.missing_path_counts.items())),
            "replay_checked_count": self.replay_checked_count,
            "replay_matched_count": self.replay_matched_count,
            "replay_mismatch_count": self.replay_mismatch_count,
            "replay_legacy_loss_count": self.replay_legacy_loss_count,
            "run_failure_count": self.run_failure_count,
            "battle_start_record_count": self.battle_start_record_count,
            "problems": list(self.problems),
            "passed": self.passed,
        }


def run_public_context_artifact_audit(
    adapter_factory: Callable[[], CheckpointingSimulatorAdapter],
    *,
    seed: int,
    episodes: int,
    max_steps: int,
    action_space: ActionSpaceConfig | None = None,
) -> PublicContextArtifactAuditReport:
    """Audit current public context artifacts and portable replay comparison."""

    if episodes <= 0:
        raise ValueError("public-context audit episodes must be positive")
    if max_steps <= 0:
        raise ValueError("public-context audit max_steps must be positive")

    active_action_space = action_space or ActionSpaceConfig.initial_no_potions()
    problems: list[str] = []
    screen_counts: Counter[str] = Counter()
    missing_path_counts: Counter[str] = Counter()
    candidate_parity_passes = 0
    candidate_parity_failures = 0
    context_available_count = 0
    context_schema_failures = 0
    forbidden_field_failures = 0
    run_failure_count = 0
    decisions_observed = 0
    completed_episodes = 0
    records: list[BattleStartCheckpointRecord] = []
    terminal_run_count = 0
    truncated_run_count = 0
    controller_provenance: dict[str, Any] = {}

    for offset in range(episodes):
        run_seed = seed + offset
        adapter = adapter_factory()
        controller = _audit_controller(run_seed)
        controller_provenance = controller.provenance.to_dict()
        action_trace: list[dict[str, Any]] = []
        active_record_index: int | None = None
        battle_index = 0
        source_run_id = f"seed-{run_seed}-audit-run-{offset}"

        def before_decision(
            snapshot: SimulatorSnapshot,
            actions: Sequence[SimulatorAction],
            context: object,
            step_index: int,
        ) -> None:
            nonlocal active_record_index, battle_index
            nonlocal decisions_observed, candidate_parity_passes
            nonlocal candidate_parity_failures, context_available_count
            nonlocal context_schema_failures, forbidden_field_failures

            public_context = getattr(context, "public_run_context", {})
            label = f"seed {run_seed} step {step_index}"
            decisions_observed += 1
            screen = _context_screen(public_context, snapshot)
            screen_counts[screen] += 1
            context_available_count += 1
            schema_problems = public_context_artifact_problems(
                status=PUBLIC_CONTEXT_AVAILABLE,
                context=public_context,
                label=label,
                require_available=True,
                require_candidate_actions=True,
            )
            forbidden = forbidden_public_context_problems(public_context)
            if schema_problems:
                context_schema_failures += 1
                problems.extend(schema_problems)
            if forbidden:
                forbidden_field_failures += 1
                problems.extend(f"{label}: {problem}" for problem in forbidden)
            try:
                sanitized = sanitize_public_context_artifact(
                    public_context,
                    label=label,
                )
                missing_path_counts.update(public_context_missing_paths(sanitized))
                if _candidate_parity_ok(sanitized, actions):
                    candidate_parity_passes += 1
                else:
                    candidate_parity_failures += 1
                    problems.append(f"{label}: candidate action-set parity mismatch")
            except ValueError as exc:
                context_schema_failures += 1
                problems.append(f"{label}: {exc}")
                return

            if not _is_battle_snapshot(snapshot) or active_record_index is not None:
                return
            native_checkpoint = adapter.capture_checkpoint(snapshot)
            structural = source_metadata_from_snapshot(
                snapshot.raw,
                seed=run_seed,
                source_kind=NATURAL_DISTRIBUTION_KIND,
            )
            structural.update(
                {
                    "source_run_id": source_run_id,
                    "source_battle_index": battle_index,
                }
            )
            records.append(
                BattleStartCheckpointRecord(
                    record_index=len(records),
                    source_checkpoint_id=native_checkpoint.checkpoint_id,
                    source_run_id=source_run_id,
                    source_seed=run_seed,
                    source_battle_index=battle_index,
                    structural_metadata=structural,
                    source_controller_provenance=controller.provenance.to_dict(),
                    source_battle_controller_provenance=(
                        controller.battle.provenance.to_dict()
                    ),
                    source_non_combat_controller_provenance=(
                        controller.non_combat.provenance.to_dict()
                    ),
                    action_trace=tuple(dict(identity) for identity in action_trace),
                    snapshot_observation=tuple(snapshot.observation),
                    snapshot_raw=dict(snapshot.raw),
                    distribution_kind=NATURAL_DISTRIBUTION_KIND,
                    checkpoint_information_regime=CHECKPOINT_INFORMATION_REGIME,
                    public_context_status=PUBLIC_CONTEXT_AVAILABLE,
                    public_run_context=sanitized,
                    native_checkpoint=native_checkpoint,
                )
            )
            active_record_index = len(records) - 1
            battle_index += 1

        def after_transition(step: ControlledRunStep) -> None:
            nonlocal active_record_index
            action_trace.append(dict(step.chosen_action_identity))
            if active_record_index is None:
                return
            if step.next_battle_active and not step.terminal_after_step:
                return
            records[active_record_index] = replace(
                records[active_record_index],
                battle_outcome=step.next_battle_outcome,
                battle_completed=True,
            )
            active_record_index = None

        run = execute_controlled_run(
            adapter,
            controller,
            seed=run_seed,
            max_steps=max_steps,
            action_space=active_action_space,
            before_decision=before_decision,
            after_transition=after_transition,
        )
        completed_episodes += 1
        if run.terminal:
            terminal_run_count += 1
        else:
            truncated_run_count += 1
        if run.problems:
            run_failure_count += len(run.problems)
            problems.extend(f"seed {run_seed}: run error: {p}" for p in run.problems)

    pool = NaturalBattleStartPool(
        source_run_count=episodes,
        terminal_run_count=terminal_run_count,
        truncated_run_count=truncated_run_count,
        source_controller_provenance=controller_provenance,
        records=records,
    )
    restore_report = verify_battle_start_pool_restores(adapter_factory, pool)
    problems.extend(restore_report.problems)
    coverage_gaps = sorted(KNOWN_SCREEN_STATES.difference(screen_counts))
    return PublicContextArtifactAuditReport(
        requested_episodes=episodes,
        completed_episodes=completed_episodes,
        max_steps=max_steps,
        decisions_observed=decisions_observed,
        screen_counts=screen_counts,
        coverage_gaps=coverage_gaps,
        candidate_parity_passes=candidate_parity_passes,
        candidate_parity_failures=candidate_parity_failures,
        context_available_count=context_available_count,
        context_schema_failures=context_schema_failures,
        forbidden_field_failures=forbidden_field_failures,
        missing_path_counts=missing_path_counts,
        replay_checked_count=restore_report.context_compared_count,
        replay_matched_count=restore_report.context_matched_count,
        replay_mismatch_count=restore_report.context_mismatch_count,
        replay_legacy_loss_count=restore_report.context_legacy_unavailable_count,
        run_failure_count=run_failure_count,
        battle_start_record_count=len(records),
        problems=list(dict.fromkeys(problems)),
    )


def format_public_context_artifact_audit_report(
    report: PublicContextArtifactAuditReport,
) -> str:
    """Format the T016 WSL audit evidence for stderr and PR reporting."""

    lines = [
        "Public-context artifact replay audit",
        f"report schema: {report.report_schema_id}",
        format_lightspeed_source_identity(report.source_identity),
        f"episodes: {report.completed_episodes}/{report.requested_episodes}",
        f"max steps per episode: {report.max_steps}",
        f"current decision screens observed: {report.decisions_observed}",
        f"candidate-action parity passes: {report.candidate_parity_passes}",
        f"candidate-action parity failures: {report.candidate_parity_failures}",
        f"context schema failures: {report.context_schema_failures}",
        f"forbidden-field failures: {report.forbidden_field_failures}",
        f"battle-start records: {report.battle_start_record_count}",
        f"replay checked: {report.replay_checked_count}",
        f"replay matched: {report.replay_matched_count}",
        f"replay mismatches: {report.replay_mismatch_count}",
        f"legacy context losses: {report.replay_legacy_loss_count}",
        f"run failures: {report.run_failure_count}",
        f"audit passed: {'yes' if report.passed else 'no'}",
    ]
    _append_counter(lines, "observed screen counts", report.screen_counts)
    _append_counter(lines, "context missing paths", report.missing_path_counts)
    _append_values(lines, "coverage gaps", report.coverage_gaps)
    _append_values(lines, "problems", report.problems)
    return "\n".join(lines)


def _audit_controller(seed: int) -> RoutedRunController:
    return RoutedRunController(
        battle=PolicyController(PreferredKindPolicy()),
        non_combat=PolicyController(StochasticNonCombatDriver(seed=seed)),
    )


def _context_screen(context: object, snapshot: SimulatorSnapshot) -> str:
    if isinstance(context, Mapping):
        current = context.get("current")
        if isinstance(current, Mapping):
            screen = current.get("screen")
            if (
                isinstance(screen, Mapping)
                and screen.get("availability") == "available"
            ):
                return str(screen.get("value"))
    return str(snapshot.raw.get("screen_state", "(unknown)"))


def _candidate_parity_ok(
    context: Mapping[str, Any],
    actions: Sequence[SimulatorAction],
) -> bool:
    candidates = context.get("candidate_actions")
    if (
        not isinstance(candidates, Mapping)
        or candidates.get("availability") != "available"
    ):
        return False
    items = candidates.get("items")
    if not isinstance(items, list) or len(items) != len(actions):
        return False
    for index, (item, action) in enumerate(zip(items, actions)):
        if not isinstance(item, Mapping):
            return False
        identity = item.get("identity")
        if item.get("index") != index:
            return False
        if item.get("kind") != action.kind or item.get("label") != action.label:
            return False
        if not isinstance(identity, Mapping):
            return False
        if identity.get("occurrence") is None or "stable_id" not in identity:
            return False
    return True


def _is_battle_snapshot(snapshot: SimulatorSnapshot) -> bool:
    return bool(snapshot.raw.get("battle_active")) or (
        str(snapshot.raw.get("screen_state", "")) == "BATTLE"
    )


def _append_counter(lines: list[str], title: str, values: Counter[str]) -> None:
    lines.append(f"{title}:")
    if not values:
        lines.append("  (none)")
        return
    for key, value in values.most_common():
        lines.append(f"  {key}: {value}")


def _append_values(lines: list[str], title: str, values: Sequence[str]) -> None:
    lines.append(f"{title}:")
    if not values:
        lines.append("  (none)")
        return
    lines.extend(f"  - {value}" for value in values)
