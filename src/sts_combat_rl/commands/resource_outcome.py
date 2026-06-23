"""Focused T012 workflow for structured battle resource outcome auditing."""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

from sts_combat_rl.commands.checkpoint_pool import build_routed_controller
from sts_combat_rl.sim.action_space import ActionSpaceConfig
from sts_combat_rl.sim.battle_start_pool import (
    NaturalBattleStartPool,
    build_battle_start_pool_coverage_report,
    collect_natural_battle_start_pool,
)
from sts_combat_rl.sim.contract import CheckpointingSimulatorAdapter
from sts_combat_rl.sim.policy import DecisionPolicy
from sts_combat_rl.sim.resource_outcome import (
    BATTLE_RESOURCE_OUTCOME_SCHEMA_ID,
    BATTLE_RESOURCE_OUTCOME_SCHEMA_VERSION,
    BattleResourceOutcomeComponentReport,
    build_battle_resource_outcome_component_report,
    format_battle_resource_outcome_component_report,
)


T018_IDENTITY_COMPONENTS = ("potion_slots", "deck", "curses", "relics", "keys")


@dataclass(frozen=True)
class BattleResourceOutcomeAuditReport:
    """Audit result for current structured battle-end resource outcomes."""

    requested_seeds: tuple[int, ...]
    max_steps: int
    source_pool_format_version: int
    source_run_count: int
    natural_battle_start_count: int
    completed_battle_count: int
    completed_battle_outcome_missing_count: int
    source_controller_provenance: dict[str, Any]
    source_distribution_counts: Counter[str] = field(default_factory=Counter)
    terminal_outcome_counts: Counter[str] = field(default_factory=Counter)
    component_report: BattleResourceOutcomeComponentReport = field(
        default_factory=lambda: BattleResourceOutcomeComponentReport(
            source_record_count=0
        )
    )
    identity_component_missing_counts: Counter[str] = field(default_factory=Counter)
    identity_component_problems: tuple[str, ...] = ()
    known_limitations: tuple[str, ...] = ()
    pool_problems: list[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return (
            self.completed_battle_count > 0
            and self.completed_battle_outcome_missing_count == 0
            and not self.pool_problems
            and self.component_report.passed
            and not self.identity_component_problems
        )


def run_battle_resource_outcome_audit(
    adapter: CheckpointingSimulatorAdapter,
    *,
    battle_policy: DecisionPolicy,
    non_combat_policy: DecisionPolicy,
    seeds: Sequence[int],
    max_steps: int,
    action_space: ActionSpaceConfig | None = None,
) -> BattleResourceOutcomeAuditReport:
    """Collect a bounded natural pool and audit structured terminal outcomes."""

    controller = build_routed_controller(battle_policy, non_combat_policy)
    pool = collect_natural_battle_start_pool(
        adapter,
        controller,
        seeds=seeds,
        max_steps=max_steps,
        action_space=action_space,
    )
    return build_battle_resource_outcome_audit_report(
        pool,
        requested_seeds=tuple(seeds),
        max_steps=max_steps,
    )


def build_battle_resource_outcome_audit_report(
    pool: NaturalBattleStartPool,
    *,
    requested_seeds: tuple[int, ...],
    max_steps: int,
) -> BattleResourceOutcomeAuditReport:
    """Build the component report from a current pool artifact."""

    coverage = build_battle_start_pool_coverage_report(pool)
    rows = [
        (
            record.completed_battle_resource_outcome_status,
            record.completed_battle_resource_outcome,
        )
        for record in pool.records
    ]
    component_report = build_battle_resource_outcome_component_report(rows)
    identity_missing_counts = _identity_component_missing_counts(component_report)
    identity_problems = tuple(_identity_component_problems(identity_missing_counts))
    return BattleResourceOutcomeAuditReport(
        requested_seeds=requested_seeds,
        max_steps=max_steps,
        source_pool_format_version=pool.format_version,
        source_run_count=pool.source_run_count,
        natural_battle_start_count=len(pool.records),
        completed_battle_count=coverage.completed_battle_count,
        completed_battle_outcome_missing_count=(
            coverage.completed_battle_outcome_missing_count
        ),
        source_controller_provenance=dict(pool.source_controller_provenance),
        source_distribution_counts=Counter(
            record.distribution_kind for record in pool.records
        ),
        terminal_outcome_counts=coverage.reported_battle_outcome_counts,
        component_report=component_report,
        identity_component_missing_counts=identity_missing_counts,
        identity_component_problems=identity_problems,
        known_limitations=tuple(_known_limitations(component_report)),
        pool_problems=list(coverage.problems),
    )


def format_battle_resource_outcome_audit_report(
    report: BattleResourceOutcomeAuditReport,
) -> str:
    """Format the T012 audit report for stderr and PR reporting."""

    lines = [
        "Battle resource outcome audit",
        f"schema: {BATTLE_RESOURCE_OUTCOME_SCHEMA_ID} v{BATTLE_RESOURCE_OUTCOME_SCHEMA_VERSION}",
        f"requested seeds: {', '.join(str(seed) for seed in report.requested_seeds)}",
        f"max steps per seed: {report.max_steps}",
        f"source pool format version: {report.source_pool_format_version}",
        f"source runs: {report.source_run_count}",
        f"natural battle starts: {report.natural_battle_start_count}",
        f"completed battles: {report.completed_battle_count}",
        (
            "completed battles missing outcome: "
            f"{report.completed_battle_outcome_missing_count}"
        ),
        f"audit passed: {'yes' if report.passed else 'no'}",
        "source controller provenance:",
        f"  name: {report.source_controller_provenance.get('name', '(unknown)')}",
        f"  kind: {report.source_controller_provenance.get('kind', '(unknown)')}",
    ]
    _append_counter(lines, "source distributions", report.source_distribution_counts)
    _append_counter(lines, "terminal outcomes", report.terminal_outcome_counts)
    lines.append("")
    lines.append(
        format_battle_resource_outcome_component_report(report.component_report)
    )
    _append_counter(
        lines,
        "T018 identity missing/unavailable counts",
        report.identity_component_missing_counts,
    )
    lines.append("T018 identity gate problems:")
    if report.identity_component_problems:
        lines.extend(f"  - {problem}" for problem in report.identity_component_problems)
    else:
        lines.append("  (none)")
    lines.append("known limitations:")
    if report.known_limitations:
        lines.extend(f"  - {limitation}" for limitation in report.known_limitations)
    else:
        lines.append("  (none)")
    lines.append("pool problems:")
    if report.pool_problems:
        lines.extend(f"  - {problem}" for problem in report.pool_problems)
    else:
        lines.append("  (none)")
    return "\n".join(lines)


def _append_counter(lines: list[str], title: str, values: Counter[str]) -> None:
    lines.append(f"{title}:")
    if not values:
        lines.append("  (none)")
        return
    for key in sorted(values):
        lines.append(f"  {key}: {values[key]}")


def _known_limitations(
    component_report: BattleResourceOutcomeComponentReport,
) -> list[str]:
    missing_components = [
        name
        for name in T018_IDENTITY_COMPONENTS
        if (
            component_report.component_presence_counts.get(name, Counter()).get(
                "missing", 0
            )
            + component_report.component_presence_counts.get(name, Counter()).get(
                "unavailable", 0
            )
        )
        > 0
    ]
    if not missing_components:
        return []
    return [
        "identity-bearing terminal resource fields remain missing or unavailable "
        f"in this audit: {', '.join(missing_components)}",
        "current audit success means structured plumbing and explicit missingness "
        "are valid; it does not prove full native resource identity coverage",
    ]


def _identity_component_missing_counts(
    component_report: BattleResourceOutcomeComponentReport,
) -> Counter[str]:
    missing_counts: Counter[str] = Counter()
    for name in T018_IDENTITY_COMPONENTS:
        counts = component_report.component_presence_counts.get(name, Counter())
        missing = counts.get("missing", 0) + counts.get("unavailable", 0)
        if missing:
            missing_counts[name] = missing
    return missing_counts


def _identity_component_problems(missing_counts: Counter[str]) -> list[str]:
    return [
        (
            f"T018 identity-bearing component {name} is missing or unavailable "
            f"in {count} terminal outcome(s)"
        )
        for name, count in sorted(missing_counts.items())
    ]
