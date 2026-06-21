"""Public run context audit for WSL simulator runs.

Runs N bounded episodes through ``execute_controlled_run``, collects the
``public_run_context`` at every step, and reports screen types, history
lengths, map completeness, boss presence, and forbidden-field leakage.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

from sts_combat_rl.sim.action_space import ActionSpaceConfig
from sts_combat_rl.sim.controlled_run import execute_controlled_run
from sts_combat_rl.sim.lightspeed import LightSpeedAdapter
from sts_combat_rl.sim.online_controller import PolicyController
from sts_combat_rl.sim.policy import PreferredKindPolicy
from sts_combat_rl.sim.public_run_context import (
    PUBLIC_RUN_CONTEXT_SCHEMA_ID,
    PUBLIC_RUN_CONTEXT_SCHEMA_VERSION,
    public_run_context_missing_fields,
    public_run_context_problems,
)


@dataclass(frozen=True)
class PublicRunContextAuditReport:
    """Coverage and problem report from a bounded context audit sweep."""

    episode_count: int
    total_steps: int
    schema_id: str
    schema_version: int
    screen_state_counts: Counter[str] = field(default_factory=Counter)
    history_entry_counts: Counter[str] = field(default_factory=Counter)
    map_populated_count: int = 0
    map_missing_count: int = 0
    boss_populated_count: int = 0
    boss_missing_count: int = 0
    visible_screen_populated_count: int = 0
    visible_screen_missing_count: int = 0
    forbidden_field_problems: list[str] = field(default_factory=list)
    schema_problems: list[str] = field(default_factory=list)
    missing_field_counts: Counter[str] = field(default_factory=Counter)
    problems: list[str] = field(default_factory=list)

    @property
    def audit_ok(self) -> bool:
        return not self.forbidden_field_problems and not self.schema_problems


def run_public_run_context_audit(
    adapter: LightSpeedAdapter,
    *,
    seeds: list[int],
    max_steps: int = 200,
    action_space: ActionSpaceConfig | None = None,
) -> PublicRunContextAuditReport:
    """Run N bounded episodes and audit every public run context snapshot."""

    active_action_space = action_space or ActionSpaceConfig.initial_no_potions()
    controller = PolicyController(PreferredKindPolicy())

    screen_state_counts: Counter[str] = Counter()
    history_entry_counts: Counter[str] = Counter()
    map_populated_count = 0
    map_missing_count = 0
    boss_populated_count = 0
    boss_missing_count = 0
    visible_screen_populated_count = 0
    visible_screen_missing_count = 0
    forbidden_field_problems: list[str] = []
    schema_problems: list[str] = []
    missing_field_counts: Counter[str] = Counter()
    problems: list[str] = []
    total_steps = 0

    for seed in seeds:
        run = execute_controlled_run(
            adapter,
            controller,
            seed=seed,
            max_steps=max_steps,
            action_space=active_action_space,
        )
        problems.extend(f"seed {seed}: {p}" for p in run.problems)
        total_steps += len(run.steps)

        for step in run.steps:
            context = step.public_run_context
            ctx_problems = public_run_context_problems(context)
            if ctx_problems:
                for problem in ctx_problems:
                    if "forbidden field" in problem:
                        forbidden_field_problems.append(
                            f"seed {seed} step {step.step_index}: {problem}"
                        )
                    else:
                        schema_problems.append(
                            f"seed {seed} step {step.step_index}: {problem}"
                        )

            for field_name in public_run_context_missing_fields(context):
                missing_field_counts[field_name] += 1

            screen_state_counts[step.screen_state] += 1

            run_history = context.get("run_history", {})
            entries = run_history.get("entries", [])
            history_entry_counts[str(len(entries))] += 1

            for entry in entries:
                visible_screen = entry.get("before", {}).get("visible_screen", {})
                if visible_screen.get(
                    "missing_fields"
                ) and "public_visible_screen" in visible_screen.get(
                    "missing_fields", ()
                ):
                    visible_screen_missing_count += 1
                elif visible_screen:
                    visible_screen_populated_count += 1

            if context.get("visible_map"):
                map_populated_count += 1
            else:
                map_missing_count += 1

            if context.get("visible_act_boss"):
                boss_populated_count += 1
            else:
                boss_missing_count += 1

    return PublicRunContextAuditReport(
        episode_count=len(seeds),
        total_steps=total_steps,
        schema_id=PUBLIC_RUN_CONTEXT_SCHEMA_ID,
        schema_version=PUBLIC_RUN_CONTEXT_SCHEMA_VERSION,
        screen_state_counts=screen_state_counts,
        history_entry_counts=history_entry_counts,
        map_populated_count=map_populated_count,
        map_missing_count=map_missing_count,
        boss_populated_count=boss_populated_count,
        boss_missing_count=boss_missing_count,
        visible_screen_populated_count=visible_screen_populated_count,
        visible_screen_missing_count=visible_screen_missing_count,
        forbidden_field_problems=forbidden_field_problems,
        schema_problems=schema_problems,
        missing_field_counts=missing_field_counts,
        problems=problems,
    )


def format_public_run_context_audit_report(
    report: PublicRunContextAuditReport,
) -> str:
    """Format the audit report for stderr."""

    lines = [
        "Public run context audit summary",
        f"episodes: {report.episode_count}",
        f"total steps: {report.total_steps}",
        f"schema: {report.schema_id} v{report.schema_version}",
        f"audit ok: {'yes' if report.audit_ok else 'no'}",
        "",
        "Screen states observed:",
    ]
    if report.screen_state_counts:
        for state, count in report.screen_state_counts.most_common():
            lines.append(f"  {state}: {count}")
    else:
        lines.append("  (none)")

    lines.append("")
    lines.append("History entry counts per step:")
    if report.history_entry_counts:
        for length, count in report.history_entry_counts.most_common():
            lines.append(f"  {length} entries: {count} steps")
    else:
        lines.append("  (none)")

    lines.append("")
    lines.append(f"map populated: {report.map_populated_count}")
    lines.append(f"map missing: {report.map_missing_count}")
    lines.append(f"boss populated: {report.boss_populated_count}")
    lines.append(f"boss missing: {report.boss_missing_count}")
    lines.append(f"visible screen populated: {report.visible_screen_populated_count}")
    lines.append(f"visible screen missing: {report.visible_screen_missing_count}")

    lines.append("")
    lines.append("Missing field counts:")
    if report.missing_field_counts:
        for field_name, count in report.missing_field_counts.most_common():
            lines.append(f"  {field_name}: {count}")
    else:
        lines.append("  (none)")

    lines.append("")
    lines.append("Forbidden field problems:")
    if report.forbidden_field_problems:
        lines.extend(f"  {p}" for p in report.forbidden_field_problems)
    else:
        lines.append("  (none)")

    lines.append("")
    lines.append("Schema problems:")
    if report.schema_problems:
        lines.extend(f"  {p}" for p in report.schema_problems)
    else:
        lines.append("  (none)")

    lines.append("")
    lines.append("Run problems:")
    if report.problems:
        lines.extend(f"  {p}" for p in report.problems)
    else:
        lines.append("  (none)")

    return "\n".join(lines)
