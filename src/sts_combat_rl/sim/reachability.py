"""A20 reachability comparison reports for T036.

This module is intentionally offline: it compares current-schema natural
battle-start pools and their T021 coverage reports. It does not run the
simulator, train models, or reinterpret Oracle-like search as normal play.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
import json
from typing import Any, TextIO

from sts_combat_rl.sim.a20_battle_start_coverage import (
    A20_BATTLE_START_COVERAGE_FORMAT_VERSION,
    A20_BATTLE_START_COVERAGE_SCHEMA_ID,
)
from sts_combat_rl.sim.battle_start_pool import (
    SOURCE_RUN_SUMMARY_AVAILABLE,
    NaturalBattleStartPool,
    build_battle_start_pool_coverage_report,
)
from sts_combat_rl.sim.lightspeed_source import format_lightspeed_source_identity


A20_REACHABILITY_REPORT_SCHEMA_ID = "a20-search-controlled-reachability-report-v1"
A20_REACHABILITY_REPORT_FORMAT_VERSION = 1


@dataclass(frozen=True)
class ReachabilityArmArtifact:
    """Artifact identity for one compared source distribution."""

    label: str
    pool_path: str
    pool_sha256: str
    coverage_report_path: str
    coverage_report_sha256: str
    pool_record_count: int
    coverage_record_count: int | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "label": self.label,
            "pool_path": self.pool_path,
            "pool_sha256": self.pool_sha256,
            "coverage_report_path": self.coverage_report_path,
            "coverage_report_sha256": self.coverage_report_sha256,
            "pool_record_count": self.pool_record_count,
            "coverage_record_count": self.coverage_record_count,
        }


@dataclass(frozen=True)
class ReachabilityControllerSummary:
    """Controller provenance flattened for reachability comparison."""

    routed_controller: dict[str, Any]
    battle_controller: dict[str, Any]
    non_combat_controller: dict[str, Any]
    battle_controller_kind: str
    battle_controller_name: str
    non_combat_controller_name: str
    information_regime: str
    search_budget: dict[str, Any] = field(default_factory=dict)
    root_selection_rule: str | None = None
    action_space: dict[str, Any] = field(default_factory=dict)
    include_potions: bool | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "routed_controller": _json_safe_mapping(self.routed_controller),
            "battle_controller": _json_safe_mapping(self.battle_controller),
            "non_combat_controller": _json_safe_mapping(self.non_combat_controller),
            "battle_controller_kind": self.battle_controller_kind,
            "battle_controller_name": self.battle_controller_name,
            "non_combat_controller_name": self.non_combat_controller_name,
            "information_regime": self.information_regime,
            "search_budget": _json_safe_mapping(self.search_budget),
            "root_selection_rule": self.root_selection_rule,
            "action_space": _json_safe_mapping(self.action_space),
            "include_potions": self.include_potions,
        }


@dataclass(frozen=True)
class ReachabilityArmReport:
    """Reachability and artifact status for one source-generation arm."""

    label: str
    artifact: ReachabilityArmArtifact
    source_identity: dict[str, Any]
    controller: ReachabilityControllerSummary
    source_run_count: int
    terminal_run_count: int
    truncated_run_count: int
    natural_battle_start_count: int
    unique_source_start_count: int
    boss_battle_start_count: int
    act1_boss_battle_start_count: int
    later_act_battle_start_count: int
    boss_source_run_count: int
    later_act_source_run_count: int
    terminal_floor_counts: Counter[str]
    terminal_act_counts: Counter[str]
    battles_per_source_run_counts: Counter[str]
    max_battle_start_floor_counts: Counter[str]
    act_counts: Counter[str]
    room_type_counts: Counter[str]
    encounter_id_counts: Counter[str]
    battle_outcome_counts: Counter[str]
    public_context_status_counts: Counter[str]
    structured_outcome_status_counts: Counter[str]
    run_summary_status_counts: Counter[str]
    sampled_distribution: dict[str, Any]
    constructed_distribution: dict[str, Any]
    paired_distribution: dict[str, Any]
    restore_verification: dict[str, Any]
    training_gate_report: dict[str, Any]
    coverage_command_passed: bool | None
    problems: tuple[str, ...] = ()

    @property
    def arm_passed(self) -> bool:
        return not self.problems

    def to_dict(self) -> dict[str, Any]:
        return {
            "label": self.label,
            "artifact": self.artifact.to_dict(),
            "source_identity": _json_safe_mapping(self.source_identity),
            "controller": self.controller.to_dict(),
            "source_run_count": self.source_run_count,
            "terminal_run_count": self.terminal_run_count,
            "truncated_run_count": self.truncated_run_count,
            "natural_battle_start_count": self.natural_battle_start_count,
            "unique_source_start_count": self.unique_source_start_count,
            "boss_battle_start_count": self.boss_battle_start_count,
            "act1_boss_battle_start_count": self.act1_boss_battle_start_count,
            "later_act_battle_start_count": self.later_act_battle_start_count,
            "boss_source_run_count": self.boss_source_run_count,
            "later_act_source_run_count": self.later_act_source_run_count,
            "terminal_floor_counts": _counter_dict(self.terminal_floor_counts),
            "terminal_act_counts": _counter_dict(self.terminal_act_counts),
            "battles_per_source_run_counts": _counter_dict(
                self.battles_per_source_run_counts
            ),
            "max_battle_start_floor_counts": _counter_dict(
                self.max_battle_start_floor_counts
            ),
            "act_counts": _counter_dict(self.act_counts),
            "room_type_counts": _counter_dict(self.room_type_counts),
            "encounter_id_counts": _counter_dict(self.encounter_id_counts),
            "battle_outcome_counts": _counter_dict(self.battle_outcome_counts),
            "public_context_status_counts": _counter_dict(
                self.public_context_status_counts
            ),
            "structured_outcome_status_counts": _counter_dict(
                self.structured_outcome_status_counts
            ),
            "run_summary_status_counts": _counter_dict(self.run_summary_status_counts),
            "sampled_distribution": _json_safe_mapping(self.sampled_distribution),
            "constructed_distribution": _json_safe_mapping(
                self.constructed_distribution
            ),
            "paired_distribution": _json_safe_mapping(self.paired_distribution),
            "restore_verification": _json_safe_mapping(self.restore_verification),
            "training_gate_report": _json_safe_mapping(self.training_gate_report),
            "coverage_command_passed": self.coverage_command_passed,
            "arm_passed": self.arm_passed,
            "problems": list(self.problems),
        }


@dataclass(frozen=True)
class A20ReachabilityComparisonReport:
    """Comparison report for default and search-controlled source arms."""

    arms: tuple[ReachabilityArmReport, ...]
    source_identity: dict[str, Any]
    historical_reference: dict[str, Any]
    followup_hint: str
    command_problems: tuple[str, ...] = ()
    schema_id: str = A20_REACHABILITY_REPORT_SCHEMA_ID
    format_version: int = A20_REACHABILITY_REPORT_FORMAT_VERSION

    @property
    def command_passed(self) -> bool:
        return not self.command_problems

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "format_version": self.format_version,
            "source_identity": _json_safe_mapping(self.source_identity),
            "historical_reference": _json_safe_mapping(self.historical_reference),
            "arms": [arm.to_dict() for arm in self.arms],
            "comparison": _comparison_dict(self.arms),
            "followup_hint": self.followup_hint,
            "command_passed": self.command_passed,
            "command_problems": list(self.command_problems),
        }


def build_a20_reachability_comparison_report(
    arm_inputs: Sequence[
        tuple[str, NaturalBattleStartPool, Mapping[str, Any], Mapping[str, Any]]
    ],
) -> A20ReachabilityComparisonReport:
    """Build the T036 comparison report from loaded arm artifacts.

    ``arm_inputs`` entries are ``(label, pool, coverage_report, artifact_identity)``.
    """

    if len(arm_inputs) < 2:
        raise ValueError("reachability comparison requires at least two arms")
    labels = [label for label, _, _, _ in arm_inputs]
    if len(set(labels)) != len(labels):
        raise ValueError("reachability arm labels must be unique")

    arms = tuple(
        build_reachability_arm_report(
            label=label,
            pool=pool,
            coverage_report=coverage,
            artifact_identity=artifact_identity,
        )
        for label, pool, coverage, artifact_identity in arm_inputs
    )
    source_identity = _common_source_identity(arms)
    problems = _comparison_problems(arms)
    return A20ReachabilityComparisonReport(
        arms=arms,
        source_identity=source_identity,
        historical_reference=_historical_reference(),
        followup_hint=_followup_hint(arms),
        command_problems=tuple(dict.fromkeys(problems)),
    )


def build_reachability_arm_report(
    *,
    label: str,
    pool: NaturalBattleStartPool,
    coverage_report: Mapping[str, Any],
    artifact_identity: Mapping[str, Any],
) -> ReachabilityArmReport:
    """Summarize one pool and its T021 coverage report."""

    coverage = build_battle_start_pool_coverage_report(pool)
    source_identity = _mapping(
        (
            coverage_report.get("source_identity")
            if isinstance(coverage_report.get("source_identity"), Mapping)
            else {}
        ),
        f"{label} coverage source_identity",
    )
    problems = _coverage_link_problems(
        label=label,
        pool=pool,
        coverage_report=coverage_report,
        artifact_identity=artifact_identity,
    )
    run_summary_counts = Counter(
        summary.status for summary in pool.source_run_summaries
    )
    if not pool.source_run_summaries:
        run_summary_counts["legacy_unavailable"] = pool.source_run_count
    battle_counts = _battle_counts_by_run(pool)
    terminal_floor_counts, terminal_act_counts = _terminal_counters(pool)
    boss_count, act1_boss_count, boss_runs = _boss_reachability(pool)
    later_count, later_runs = _later_act_reachability(pool)
    return ReachabilityArmReport(
        label=label,
        artifact=_artifact_from_identity(label, artifact_identity, pool),
        source_identity=dict(source_identity),
        controller=_controller_summary(pool),
        source_run_count=pool.source_run_count,
        terminal_run_count=pool.terminal_run_count,
        truncated_run_count=pool.truncated_run_count,
        natural_battle_start_count=coverage.natural_battle_start_count,
        unique_source_start_count=coverage.unique_source_start_count,
        boss_battle_start_count=boss_count,
        act1_boss_battle_start_count=act1_boss_count,
        later_act_battle_start_count=later_count,
        boss_source_run_count=len(boss_runs),
        later_act_source_run_count=len(later_runs),
        terminal_floor_counts=terminal_floor_counts,
        terminal_act_counts=terminal_act_counts,
        battles_per_source_run_counts=Counter(str(value) for value in battle_counts),
        max_battle_start_floor_counts=_max_battle_start_floor_counts(pool),
        act_counts=coverage.act_counts,
        room_type_counts=coverage.room_type_counts,
        encounter_id_counts=coverage.encounter_id_counts,
        battle_outcome_counts=coverage.reported_battle_outcome_counts,
        public_context_status_counts=Counter(
            record.public_context_status for record in pool.records
        ),
        structured_outcome_status_counts=coverage.resource_outcome_status_counts,
        run_summary_status_counts=run_summary_counts,
        sampled_distribution=_mapping(
            coverage_report.get("sampled_optimization_weight", {}),
            f"{label} sampled optimization weight",
        ),
        constructed_distribution=_mapping(
            coverage_report.get("constructed_coverage", {}),
            f"{label} constructed coverage",
        ),
        paired_distribution={
            "present": False,
            "reason": "T036 reachability report has no paired-counterfactual input",
        },
        restore_verification=_mapping(
            coverage_report.get("restore_verification", {}),
            f"{label} restore verification",
        ),
        training_gate_report=_mapping(
            coverage_report.get("training_gate_report", {}),
            f"{label} training gate report",
        ),
        coverage_command_passed=_optional_bool(coverage_report.get("command_passed")),
        problems=tuple(dict.fromkeys(problems)),
    )


def dump_a20_reachability_comparison_report_json(
    report: A20ReachabilityComparisonReport,
    stream: TextIO,
) -> None:
    """Write a deterministic JSON report."""

    json.dump(report.to_dict(), stream, indent=2, sort_keys=True)
    stream.write("\n")


def format_a20_reachability_comparison_report(
    report: A20ReachabilityComparisonReport,
) -> str:
    """Format the comparison for stderr and PR evidence."""

    lines = [
        "A20 search-controlled reachability report",
        f"schema: {report.schema_id} v{report.format_version}",
        f"command passed: {_yes_no(report.command_passed)}",
        "",
        format_lightspeed_source_identity(report.source_identity),
        "",
        "historical 2026-06-14 reference:",
    ]
    for key, value in report.historical_reference.items():
        lines.append(f"  {key}: {value}")
    lines.append("")
    lines.append("arms:")
    for arm in report.arms:
        lines.append(f"  {arm.label}:")
        lines.append(f"    controller: {arm.controller.battle_controller_name}")
        lines.append(f"    information regime: {arm.controller.information_regime}")
        lines.append(f"    include potions: {arm.controller.include_potions}")
        lines.append(f"    source runs: {arm.source_run_count}")
        lines.append(f"    terminal source runs: {arm.terminal_run_count}")
        lines.append(f"    truncated source runs: {arm.truncated_run_count}")
        lines.append(f"    battle starts: {arm.natural_battle_start_count}")
        lines.append(f"    Act 1 Boss starts: {arm.act1_boss_battle_start_count}")
        lines.append(f"    later-act starts: {arm.later_act_battle_start_count}")
        lines.append(f"    later-act source runs: {arm.later_act_source_run_count}")
        _append_counter(lines, "    terminal floors", arm.terminal_floor_counts)
        _append_counter(lines, "    starts by act", arm.act_counts)
        _append_counter(lines, "    starts by room type", arm.room_type_counts)
        _append_counter(lines, "    battle outcomes", arm.battle_outcome_counts)
        _append_counter(
            lines,
            "    public-context statuses",
            arm.public_context_status_counts,
        )
        _append_counter(
            lines,
            "    structured-outcome statuses",
            arm.structured_outcome_status_counts,
        )
        lines.append(
            "    restore ok: "
            f"{arm.restore_verification.get('restore_ok', '(unreported)')}"
        )
        lines.append(
            "    T009 broad training allowed: "
            f"{_nested_get(arm.training_gate_report, 'broad_training_allowed')}"
        )
        _append_problem_list(lines, "    arm problems", arm.problems)
    lines.append("")
    lines.append("comparison:")
    for key, value in _comparison_dict(report.arms).items():
        lines.append(f"  {key}: {value}")
    lines.append(f"follow-up hint: {report.followup_hint}")
    _append_problem_list(lines, "command problems", report.command_problems)
    return "\n".join(lines)


def _coverage_link_problems(
    *,
    label: str,
    pool: NaturalBattleStartPool,
    coverage_report: Mapping[str, Any],
    artifact_identity: Mapping[str, Any],
) -> list[str]:
    problems: list[str] = []
    if coverage_report.get("schema_id") != A20_BATTLE_START_COVERAGE_SCHEMA_ID:
        problems.append(f"{label}: coverage report schema_id is not T021")
    if (
        coverage_report.get("format_version")
        != A20_BATTLE_START_COVERAGE_FORMAT_VERSION
    ):
        problems.append(f"{label}: coverage report format_version is unsupported")
    natural = _mapping(coverage_report.get("natural_coverage", {}), "natural coverage")
    if natural.get("natural_battle_start_count") != len(pool.records):
        problems.append(
            f"{label}: coverage natural count does not match pool record count"
        )
    input_artifacts = coverage_report.get("input_artifacts")
    if not isinstance(input_artifacts, Mapping):
        problems.append(f"{label}: coverage report is missing input_artifacts")
        coverage_pool_map: Mapping[str, Any] = {}
    else:
        coverage_pool = input_artifacts.get("natural_pool")
        if not isinstance(coverage_pool, Mapping):
            problems.append(
                f"{label}: coverage report is missing natural_pool artifact linkage"
            )
            coverage_pool_map = {}
        else:
            coverage_pool_map = coverage_pool
    expected_sha = artifact_identity.get("pool_sha256")
    if coverage_pool_map.get("sha256") is None:
        problems.append(f"{label}: coverage natural-pool sha256 is missing")
    elif coverage_pool_map.get("sha256") != expected_sha:
        problems.append(f"{label}: coverage natural-pool sha256 does not match")
    pool_path = coverage_pool_map.get("path")
    if not isinstance(pool_path, str) or not pool_path:
        problems.append(f"{label}: coverage natural-pool path is missing")
    record_count = coverage_pool_map.get("record_count")
    if isinstance(record_count, bool) or not isinstance(record_count, int):
        problems.append(f"{label}: coverage natural-pool record_count is missing")
    elif record_count != len(pool.records):
        problems.append(f"{label}: coverage natural-pool record_count does not match")
    source_identity = coverage_report.get("source_identity")
    if not isinstance(source_identity, Mapping) or not source_identity:
        problems.append(f"{label}: coverage report is missing source_identity")
    else:
        problems.extend(_source_identity_problems(label, source_identity))
    restore = _mapping(
        coverage_report.get("restore_verification", {}),
        f"{label} restore verification",
    )
    if restore.get("restore_ok") is False:
        problems.append(f"{label}: restore verification failed")
    if coverage_report.get("command_passed") is False:
        problems.append(f"{label}: coverage command did not pass")
    if pool.problems:
        problems.extend(
            f"{label}: pool problem: {problem}" for problem in pool.problems
        )
    return problems


def _source_identity_problems(
    label: str,
    source_identity: Mapping[str, Any],
) -> list[str]:
    problems: list[str] = []
    required_strings = (
        "manifest_schema_id",
        "manifest_path",
        "upstream_repository_url",
        "upstream_base_commit",
        "integration_repository_url",
        "integration_branch",
        "integration_ref",
        "integration_commit",
        "python_module",
        "simulator_class",
        "legacy_patch_stack_status",
        "canonical_verifier",
    )
    for field_name in required_strings:
        if (
            not isinstance(source_identity.get(field_name), str)
            or not source_identity[field_name]
        ):
            problems.append(f"{label}: coverage source_identity missing {field_name}")
    manifest_version = source_identity.get("manifest_version")
    if isinstance(manifest_version, bool) or not isinstance(manifest_version, int):
        problems.append(f"{label}: coverage source_identity missing manifest_version")
    capabilities = source_identity.get("native_capabilities")
    if (
        not isinstance(capabilities, Sequence)
        or isinstance(capabilities, (str, bytes))
        or not capabilities
        or not all(isinstance(item, str) and item for item in capabilities)
    ):
        problems.append(
            f"{label}: coverage source_identity missing native_capabilities"
        )
    return problems


def _artifact_from_identity(
    label: str,
    artifact_identity: Mapping[str, Any],
    pool: NaturalBattleStartPool,
) -> ReachabilityArmArtifact:
    return ReachabilityArmArtifact(
        label=label,
        pool_path=str(artifact_identity.get("pool_path", "")),
        pool_sha256=str(artifact_identity.get("pool_sha256", "")),
        coverage_report_path=str(artifact_identity.get("coverage_report_path", "")),
        coverage_report_sha256=str(artifact_identity.get("coverage_report_sha256", "")),
        pool_record_count=len(pool.records),
        coverage_record_count=_optional_int(
            artifact_identity.get("coverage_record_count")
        ),
    )


def _controller_summary(pool: NaturalBattleStartPool) -> ReachabilityControllerSummary:
    routed = dict(pool.source_controller_provenance)
    config = _mapping(routed.get("config", {}), "routed controller config")
    battle = _mapping(config.get("battle", {}), "battle controller provenance")
    non_combat = _mapping(
        config.get("non_combat", {}),
        "non-combat controller provenance",
    )
    battle_config = _mapping(battle.get("config", {}), "battle controller config")
    non_combat_name = str(non_combat.get("name", "(missing)"))
    return ReachabilityControllerSummary(
        routed_controller=routed,
        battle_controller=dict(battle),
        non_combat_controller=dict(non_combat),
        battle_controller_kind=str(battle.get("kind", "(missing)")),
        battle_controller_name=str(battle.get("name", "(missing)")),
        non_combat_controller_name=non_combat_name,
        information_regime=str(battle_config.get("information_regime", "unknown")),
        search_budget=_mapping(battle_config.get("search_budget", {}), "search budget"),
        root_selection_rule=_optional_string(battle_config.get("root_selection_rule")),
        action_space=_mapping(battle_config.get("action_space", {}), "action space"),
        include_potions=_optional_bool(battle_config.get("include_potions")),
    )


def _battle_counts_by_run(pool: NaturalBattleStartPool) -> list[int]:
    if pool.source_run_summaries:
        return [
            summary.captured_battle_start_count for summary in pool.source_run_summaries
        ]
    by_run: defaultdict[str, int] = defaultdict(int)
    for record in pool.records:
        by_run[record.source_run_id] += 1
    return list(by_run.values())


def _terminal_counters(
    pool: NaturalBattleStartPool,
) -> tuple[Counter[str], Counter[str]]:
    floor_counts: Counter[str] = Counter()
    act_counts: Counter[str] = Counter()
    if not pool.source_run_summaries:
        floor_counts["(legacy-unavailable)"] = pool.source_run_count
        act_counts["(legacy-unavailable)"] = pool.source_run_count
        return floor_counts, act_counts
    for summary in pool.source_run_summaries:
        if summary.status != SOURCE_RUN_SUMMARY_AVAILABLE:
            floor_counts["(legacy-unavailable)"] += 1
            act_counts["(legacy-unavailable)"] += 1
            continue
        floor_counts[_value_key(summary.final_floor)] += 1
        act_counts[_value_key(summary.final_act)] += 1
    return floor_counts, act_counts


def _boss_reachability(
    pool: NaturalBattleStartPool,
) -> tuple[int, int, set[str]]:
    count = 0
    act1_count = 0
    runs: set[str] = set()
    for record in pool.records:
        room_type = str(record.structural_metadata.get("room_type", "")).lower()
        if "boss" not in room_type:
            continue
        count += 1
        runs.add(record.source_run_id)
        if _optional_int(record.structural_metadata.get("act")) == 1:
            act1_count += 1
    return count, act1_count, runs


def _later_act_reachability(
    pool: NaturalBattleStartPool,
) -> tuple[int, set[str]]:
    count = 0
    runs: set[str] = set()
    for record in pool.records:
        act = _optional_int(record.structural_metadata.get("act"))
        if act is None or act <= 1:
            continue
        count += 1
        runs.add(record.source_run_id)
    return count, runs


def _max_battle_start_floor_counts(pool: NaturalBattleStartPool) -> Counter[str]:
    if pool.source_run_summaries:
        return Counter(
            _value_key(summary.max_battle_start_floor)
            for summary in pool.source_run_summaries
        )
    by_run: defaultdict[str, list[float]] = defaultdict(list)
    for record in pool.records:
        floor = _optional_number(record.structural_metadata.get("floor"))
        if floor is not None:
            by_run[record.source_run_id].append(floor)
    return Counter(
        _value_key(max(values) if values else None) for values in by_run.values()
    )


def _comparison_dict(arms: Sequence[ReachabilityArmReport]) -> dict[str, Any]:
    best_boss = max(arms, key=lambda arm: arm.act1_boss_battle_start_count)
    best_later = max(arms, key=lambda arm: arm.later_act_battle_start_count)
    best_boss_label = (
        best_boss.label if best_boss.act1_boss_battle_start_count > 0 else None
    )
    best_later_label = (
        best_later.label if best_later.later_act_battle_start_count > 0 else None
    )
    return {
        "arm_count": len(arms),
        "best_act1_boss_arm": best_boss_label,
        "best_act1_boss_start_count": best_boss.act1_boss_battle_start_count,
        "best_later_act_arm": best_later_label,
        "best_later_act_start_count": best_later.later_act_battle_start_count,
        "any_boss_reached": any(arm.boss_battle_start_count > 0 for arm in arms),
        "any_later_act_reached": any(
            arm.later_act_battle_start_count > 0 for arm in arms
        ),
        "broad_training_allowed_any_arm": any(
            _nested_get(arm.training_gate_report, "broad_training_allowed") is True
            for arm in arms
        ),
    }


def _common_source_identity(arms: Sequence[ReachabilityArmReport]) -> dict[str, Any]:
    if not arms:
        return {}
    return dict(arms[0].source_identity)


def _comparison_problems(arms: Sequence[ReachabilityArmReport]) -> list[str]:
    problems: list[str] = []
    commits = {
        str(arm.source_identity.get("integration_commit", ""))
        for arm in arms
        if arm.source_identity
    }
    if len(commits) > 1:
        problems.append("reachability arms use different sts_lightspeed commits")
    for arm in arms:
        problems.extend(f"{arm.label}: {problem}" for problem in arm.problems)
    return problems


def _followup_hint(arms: Sequence[ReachabilityArmReport]) -> str:
    if any(arm.later_act_battle_start_count > 0 for arm in arms):
        return "broader_search_controlled_source_collection"
    if any(arm.boss_battle_start_count > 0 for arm in arms):
        return "broader_search_controlled_source_collection_before_t032"
    return "keep_t032_blocked_or_use_explicit_act1_only_refresh_boundary"


def _historical_reference() -> dict[str, Any]:
    return {
        "date": "2026-06-14",
        "source_runs": 1000,
        "battle_controller": "20-simulation no-potion Oracle-like search",
        "act1_boss_starts": 35,
        "act2_battle_starts": 1,
        "normal_battle_starts": 3888,
        "elite_battle_starts": 755,
        "event_battle_starts": 18,
        "comparison_note": (
            "Scale differences matter: small T036 smoke runs can validate current "
            "schemas and direction, but should not be read as a 1,000-run "
            "reachability replication."
        ),
    }


def _mapping(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} must be an object")
    return {str(key): item for key, item in value.items()}


def _nested_get(value: Mapping[str, Any], *keys: str) -> Any:
    current: Any = value
    for key in keys:
        if not isinstance(current, Mapping):
            return None
        current = current.get(key)
    return current


def _optional_string(value: Any) -> str | None:
    return value if isinstance(value, str) else None


def _optional_bool(value: Any) -> bool | None:
    return value if isinstance(value, bool) else None


def _optional_int(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return None


def _optional_number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _value_key(value: Any) -> str:
    if value is None:
        return "(unavailable)"
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def _counter_dict(values: Mapping[Any, int]) -> dict[str, int]:
    return {str(key): values[key] for key in sorted(values, key=lambda item: str(item))}


def _json_safe_mapping(values: Mapping[str, Any]) -> dict[str, Any]:
    return {str(key): _json_safe_value(value) for key, value in values.items()}


def _json_safe_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return _json_safe_mapping(value)
    if isinstance(value, Counter):
        return _counter_dict(value)
    if isinstance(value, (list, tuple)):
        return [_json_safe_value(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _append_counter(
    lines: list[str],
    title: str,
    values: Mapping[Any, int],
) -> None:
    lines.append(f"{title}:")
    if not values:
        lines.append("      (none)")
        return
    for key in sorted(values, key=lambda item: str(item)):
        lines.append(f"      {key}: {values[key]}")


def _append_problem_list(
    lines: list[str],
    title: str,
    problems: Sequence[str],
) -> None:
    lines.append(f"{title}:")
    if problems:
        lines.extend(f"  - {problem}" for problem in problems)
    else:
        lines.append("  (none)")


def _yes_no(value: bool) -> str:
    return "yes" if value else "no"
