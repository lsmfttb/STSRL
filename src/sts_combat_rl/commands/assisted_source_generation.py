"""T042 assisted complete-run source-generation commands."""

from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
from collections.abc import Mapping
from typing import Any

from sts_combat_rl.sim.battle_start_pool import BattleStartPoolRestoreReport
from sts_combat_rl.sim.a20_battle_start_coverage import A20CoverageCommandConfig
from sts_combat_rl.sim.assisted_source_generation import (
    ASSISTANCE_LEVELS,
    ASSISTANCE_SCHEDULES,
    ASSISTED_RUN_DISTRIBUTION_KIND,
    AssistedCoverageArmReport,
    AssistedSourceCoverageComparisonReport,
    build_assisted_a20_coverage_report,
    dump_assisted_source_coverage_comparison_report_json,
    dump_merged_assisted_source_pool_shards_jsonl,
    format_assisted_a20_coverage_report,
    assistance_schedule_by_level,
    load_assisted_source_pool_jsonl,
    sha256_file,
    verify_assisted_source_pool_restores,
    write_assisted_a20_coverage_report,
    _load_assisted_source_pool_metadata_jsonl,
)
from sts_combat_rl.sim.reachability import (
    ReachabilityArmArtifact,
    ReachabilityArmReport,
    ReachabilityControllerSummary,
)
from sts_combat_rl.sim.lightspeed_source import lightspeed_source_identity_dict


class _CoveragePayload(dict):
    @property
    def command_passed(self) -> bool:
        return self.get("command_passed") is True

    def to_dict(self) -> dict[str, Any]:
        return dict(self)


def run_assisted_a20_coverage_from_paths(
    *,
    pool_path: Path,
    output_path: Path | None,
    adapter_factory,
    restore_limit: int,
    gate_config,
    gate_override: str,
) -> Any:
    """Load one assisted pool, verify restore, and build an A20 coverage report."""

    with pool_path.open("r", encoding="utf-8") as stream:
        artifact = load_assisted_source_pool_jsonl(stream)
    restore = verify_assisted_source_pool_restores(
        adapter_factory,
        artifact,
        limit=restore_limit,
    )
    report = build_assisted_a20_coverage_report(
        artifact,
        restore_report=restore,
        command_config=A20CoverageCommandConfig(
            restore_limit=restore_limit,
            gate_config=gate_config,
            gate_override=gate_override,
        ),
        input_artifacts={
            "natural_pool": {
                "path": str(pool_path),
                "sha256": sha256_file(pool_path),
                "record_count": len(artifact.records),
                "schema_id": artifact.schema_id,
                "format_version": artifact.format_version,
                "distribution_kind": "assisted_run",
                "assistance_level": artifact.assistance_level,
            }
        },
        source_identity=lightspeed_source_identity_dict(),
    )
    if output_path is not None:
        write_assisted_a20_coverage_report(output_path, report)
    return report


def run_assisted_source_coverage_report_from_paths(
    *,
    output_path: Path,
    arm_specs: list[list[str]],
) -> Any:
    """Build the offline T042 comparison report from repeated arm specs."""

    arm_reports = []
    command_problems = []
    levels = []
    for spec_index, spec in enumerate(arm_specs):
        if len(spec) != 3:
            raise ValueError(f"assisted source arm {spec_index} must have 3 values")
        level, pool_raw, coverage_raw = spec
        levels.append(level)
        pool_path = Path(pool_raw)
        coverage_path = Path(coverage_raw)
        metadata = _load_assisted_source_pool_metadata_jsonl(pool_path)
        with coverage_path.open("r", encoding="utf-8") as stream:
            coverage = json.load(stream)
        artifact_identity = {
            "pool_path": str(pool_path),
            "pool_sha256": sha256_file(pool_path),
            "coverage_report_path": str(coverage_path),
            "coverage_report_sha256": sha256_file(coverage_path),
            "pool_record_count": _metadata_int(metadata, "record_count"),
            "coverage_record_count": _coverage_record_count(coverage),
        }
        arm = _assisted_arm_report_from_metadata(
            level=level,
            metadata=metadata,
            coverage=coverage,
            artifact_identity=artifact_identity,
        )
        arm_reports.append(arm)
        command_problems.extend(
            f"{arm.assistance_level}: {problem}" for problem in arm.arm.problems
        )
        command_problems.extend(
            f"{arm.assistance_level}: {problem}" for problem in arm.schedule_problems
        )
    command_problems.extend(_assistance_level_set_problems(levels))
    report = AssistedSourceCoverageComparisonReport(
        arms=tuple(arm_reports),
        source_identity=dict(arm_reports[0].arm.source_identity) if arm_reports else {},
        command_problems=tuple(dict.fromkeys(command_problems)),
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="\n") as stream:
        dump_assisted_source_coverage_comparison_report_json(report, stream)
    return report


def merge_assisted_source_pool_from_paths(
    *,
    output_path: Path,
    shard_paths: list[Path],
) -> Any:
    """Merge repeated T042 assisted source-pool shards into one arm artifact."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="\n") as stream:
        return dump_merged_assisted_source_pool_shards_jsonl(shard_paths, stream)


def merge_assisted_a20_coverage_from_paths(
    *,
    output_path: Path,
    pool_path: Path,
    coverage_shard_paths: list[Path],
    restore_limit: int,
    gate_config,
    gate_override: str,
) -> Any:
    """Build one merged assisted A20 coverage report from shard restore evidence."""

    metadata = _load_assisted_source_pool_metadata_jsonl(pool_path)
    coverage_shards = []
    for shard_path in coverage_shard_paths:
        with shard_path.open("r", encoding="utf-8") as stream:
            coverage_shards.append((shard_path, json.load(stream)))
    restore = _aggregate_restore_reports(coverage_shards)
    record_count = _metadata_int(metadata, "record_count")
    if restore.checkpoint_count != record_count:
        raise ValueError(
            "coverage shard restore counts do not match merged assisted pool "
            f"records: {restore.checkpoint_count} != {record_count}"
        )
    config = A20CoverageCommandConfig(
        restore_limit=restore_limit,
        gate_config=gate_config,
        gate_override=gate_override,
    )
    report = _CoveragePayload(
        _merged_coverage_payload(
            pool_path=pool_path,
            metadata=metadata,
            coverage_shards=coverage_shards,
            restore=restore,
            command_config=config,
        )
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="\n") as stream:
        json.dump(report, stream, indent=2, sort_keys=True)
        stream.write("\n")
    return report


def format_assisted_source_pool_merge_report(artifact: Any) -> str:
    """Format a compact assisted shard-merge summary for stderr."""

    if hasattr(artifact, "pool"):
        source_run_count = artifact.pool.source_run_count
        terminal_run_count = artifact.pool.terminal_run_count
        truncated_run_count = artifact.pool.truncated_run_count
        record_count = len(artifact.records)
        assistance_decision_count = len(artifact.assistance_decisions)
    else:
        source_run_count = artifact.source_run_count
        terminal_run_count = artifact.terminal_run_count
        truncated_run_count = artifact.truncated_run_count
        record_count = artifact.record_count
        assistance_decision_count = artifact.assistance_decision_count
    return "\n".join(
        [
            "Assisted source-pool merge summary",
            f"assistance level: {artifact.assistance_level}",
            f"shards: {len(artifact.source_shards)}",
            f"source runs: {source_run_count}",
            f"terminal source runs: {terminal_run_count}",
            f"truncated source runs: {truncated_run_count}",
            f"records: {record_count}",
            f"assistance decisions: {assistance_decision_count}",
        ]
    )


def format_assisted_coverage_report(report: Any) -> str:
    """Format an assisted A20 coverage report for stderr."""

    if isinstance(report, Mapping):
        natural = _mapping(report.get("natural_coverage"), "natural_coverage")
        restore = _mapping(report.get("restore_verification"), "restore_verification")
        return "\n".join(
            [
                "A20 battle-start coverage report",
                f"command passed: {_yes_no(report.get('command_passed') is True)}",
                f"source runs: {natural.get('source_run_count')}",
                f"terminal source runs: {natural.get('terminal_run_count')}",
                f"truncated source runs: {natural.get('truncated_run_count')}",
                f"natural battle starts: {natural.get('natural_battle_start_count')}",
                f"Act-1 Boss starts: {_counter_value(natural, 'room_type_counts', 'BOSS')}",
                f"later-act starts: {natural.get('later_act_battle_start_count')}",
                f"restore ok: {_yes_no(restore.get('restore_ok') is True)}",
            ]
        )
    return format_assisted_a20_coverage_report(report)


def _assisted_arm_report_from_metadata(
    *,
    level: str,
    metadata: Mapping[str, Any],
    coverage: Mapping[str, Any],
    artifact_identity: Mapping[str, Any],
) -> AssistedCoverageArmReport:
    natural = _mapping(coverage.get("natural_coverage"), "natural_coverage")
    summaries = _summary_rows(metadata)
    training_gate = _mapping(coverage.get("training_gate_report"), "training_gate")
    source_identity = _mapping(coverage.get("source_identity"), "source_identity")
    record_count = _metadata_int(metadata, "record_count")
    coverage_record_count = _coverage_record_count(coverage)
    problems = _metadata_coverage_link_problems(
        label=level,
        metadata=metadata,
        coverage=coverage,
        artifact_identity=artifact_identity,
    )
    arm = ReachabilityArmReport(
        label=level,
        artifact=ReachabilityArmArtifact(
            label=level,
            pool_path=str(artifact_identity.get("pool_path", "")),
            pool_sha256=str(artifact_identity.get("pool_sha256", "")),
            coverage_report_path=str(artifact_identity.get("coverage_report_path", "")),
            coverage_report_sha256=str(
                artifact_identity.get("coverage_report_sha256", "")
            ),
            pool_record_count=record_count,
            coverage_record_count=coverage_record_count,
        ),
        source_identity=dict(source_identity),
        controller=_controller_summary_from_metadata(metadata),
        source_run_count=_metadata_int(metadata, "source_run_count"),
        terminal_run_count=_metadata_int(metadata, "terminal_run_count"),
        truncated_run_count=_metadata_int(metadata, "truncated_run_count"),
        natural_battle_start_count=_natural_int(natural, "natural_battle_start_count"),
        unique_source_start_count=_natural_int(natural, "unique_source_start_count"),
        boss_battle_start_count=_counter_value(natural, "room_type_counts", "BOSS"),
        act1_boss_battle_start_count=_act1_boss_count(natural),
        later_act_battle_start_count=_later_act_start_count(natural),
        boss_source_run_count=_natural_int(natural, "boss_source_run_count", default=0),
        later_act_source_run_count=_natural_int(
            natural,
            "later_act_source_run_count",
        ),
        terminal_floor_counts=_summary_counter(summaries, "final_floor"),
        terminal_act_counts=_summary_counter(summaries, "final_act"),
        battles_per_source_run_counts=Counter(
            str(_int_or_zero(summary.get("captured_battle_start_count")))
            for summary in summaries
        ),
        max_battle_start_floor_counts=_summary_counter(
            summaries,
            "max_battle_start_floor",
        ),
        act_counts=_counter_from_mapping(natural.get("act_counts")),
        room_type_counts=_counter_from_mapping(natural.get("room_type_counts")),
        encounter_id_counts=_counter_from_mapping(natural.get("encounter_id_counts")),
        battle_outcome_counts=_counter_from_mapping(
            natural.get("reported_battle_outcome_counts")
        ),
        public_context_status_counts=_counter_from_mapping(
            training_gate.get("public_context_status_counts")
        ),
        structured_outcome_status_counts=_counter_from_mapping(
            natural.get("structured_resource_outcome_status_counts")
        ),
        run_summary_status_counts=Counter(
            str(summary.get("status", "available")) for summary in summaries
        ),
        sampled_distribution=_mapping(
            coverage.get("sampled_optimization_weight"),
            "sampled_optimization_weight",
        ),
        constructed_distribution=_mapping(
            coverage.get("constructed_coverage"),
            "constructed_coverage",
        ),
        paired_distribution={
            "present": False,
            "reason": "T042 assisted report has no paired-counterfactual input",
        },
        restore_verification=_mapping(
            coverage.get("restore_verification"),
            "restore_verification",
        ),
        training_gate_report=dict(training_gate),
        coverage_command_passed=(
            coverage.get("command_passed")
            if isinstance(coverage.get("command_passed"), bool)
            else None
        ),
        problems=tuple(problems),
    )
    return AssistedCoverageArmReport(
        assistance_level=level,
        arm=arm,
        schedule=assistance_schedule_by_level(level),
        assistance_decision_counts=_assistance_decision_counts_from_metadata(metadata),
        schedule_problems=tuple(_metadata_schedule_problems(level, metadata)),
    )


def _merged_coverage_payload(
    *,
    pool_path: Path,
    metadata: Mapping[str, Any],
    coverage_shards: list[tuple[Path, Any]],
    restore: BattleStartPoolRestoreReport,
    command_config: A20CoverageCommandConfig,
) -> dict[str, Any]:
    natural_payloads = [
        _mapping(payload.get("natural_coverage"), f"{path} natural_coverage")
        for path, payload in coverage_shards
        if isinstance(payload, Mapping)
    ]
    command_problems = []
    for path, payload in coverage_shards:
        if not isinstance(payload, Mapping):
            command_problems.append(f"{path}: coverage shard must be a JSON object")
            continue
        if payload.get("command_passed") is False:
            command_problems.append(f"{path}: coverage shard command did not pass")
        raw_problems = payload.get("command_problems", [])
        if isinstance(raw_problems, list):
            command_problems.extend(f"{path}: {problem}" for problem in raw_problems)
    if not restore.restore_ok:
        command_problems.append("merged restore verification failed")

    source_identity = (
        coverage_shards[0][1].get("source_identity")
        if coverage_shards and isinstance(coverage_shards[0][1], Mapping)
        else lightspeed_source_identity_dict()
    )
    if not isinstance(source_identity, Mapping) or not source_identity:
        source_identity = lightspeed_source_identity_dict()
    natural = _aggregate_natural_coverage(natural_payloads)
    training_row = _aggregate_training_row_coverage(coverage_shards)
    training_gate = _aggregate_training_gate_reports(coverage_shards)
    sampled = _aggregate_sampled_distribution(coverage_shards)
    constructed = _aggregate_constructed_distribution(coverage_shards)
    return {
        "schema_id": "a20-battle-start-coverage-v1",
        "format_version": 1,
        "input_artifacts": {
            "natural_pool": {
                "path": str(pool_path),
                "sha256": sha256_file(pool_path),
                "record_count": _metadata_int(metadata, "record_count"),
                "schema_id": metadata.get("schema_id"),
                "format_version": metadata.get("format_version"),
                "distribution_kind": ASSISTED_RUN_DISTRIBUTION_KIND,
                "assistance_level": metadata.get("assistance_level"),
                "source_shard_count": len(_metadata_list(metadata, "source_shards")),
            },
            "coverage_shards": [
                {
                    "path": str(path),
                    "sha256": sha256_file(path),
                    "record_count": _coverage_record_count(payload),
                    "restore_checkpoint_count": _restore_int(
                        payload,
                        "checkpoint_count",
                    ),
                    "command_passed": payload.get("command_passed")
                    if isinstance(payload, Mapping)
                    else None,
                }
                for path, payload in coverage_shards
            ],
        },
        "source_identity": dict(source_identity),
        "command_config": command_config.to_dict(),
        "natural_coverage": natural,
        "sampled_optimization_weight": sampled,
        "constructed_coverage": constructed,
        "restore_verification": _restore_report_payload(restore),
        "training_row_coverage": training_row,
        "training_gate_report": training_gate,
        "command_passed": not command_problems,
        "command_problems": list(dict.fromkeys(command_problems)),
    }


def _coverage_record_count(coverage: Any) -> int | None:
    if not isinstance(coverage, dict):
        return None
    natural = coverage.get("natural_coverage")
    if not isinstance(natural, dict):
        return None
    value = natural.get("natural_battle_start_count")
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _metadata_int(metadata: Mapping[str, Any], key: str) -> int:
    value = metadata.get(key)
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"assisted source metadata {key} must be a non-negative int")
    return value


def _metadata_list(metadata: Mapping[str, Any], key: str) -> list[Any]:
    value = metadata.get(key, [])
    if not isinstance(value, list):
        raise ValueError(f"assisted source metadata {key} must be a list")
    return value


def _summary_rows(metadata: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    rows = _metadata_list(metadata, "source_run_summaries")
    result = []
    for index, row in enumerate(rows):
        if not isinstance(row, Mapping):
            raise ValueError(f"source_run_summaries {index} must be an object")
        result.append(row)
    return result


def _mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} must be an object")
    return value


def _counter_from_mapping(value: Any) -> Counter[str]:
    if not isinstance(value, Mapping):
        return Counter()
    counter: Counter[str] = Counter()
    for key, raw in value.items():
        if isinstance(raw, bool) or not isinstance(raw, int):
            continue
        counter[str(key)] += raw
    return counter


def _counter_value(mapping: Mapping[str, Any], field: str, key: str) -> int:
    return _counter_from_mapping(mapping.get(field))[key]


def _natural_int(
    natural: Mapping[str, Any],
    key: str,
    *,
    default: int | None = None,
) -> int:
    value = natural.get(key, default)
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"natural_coverage {key} must be an int")
    return value


def _int_or_zero(value: Any) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) else 0


def _summary_counter(
    summaries: list[Mapping[str, Any]],
    key: str,
) -> Counter[str]:
    counter: Counter[str] = Counter()
    for summary in summaries:
        value = summary.get(key)
        counter["(missing)" if value is None else str(value)] += 1
    return counter


def _act1_boss_count(natural: Mapping[str, Any]) -> int:
    room_counts = _counter_from_mapping(natural.get("room_type_counts"))
    act_counts = _counter_from_mapping(natural.get("act_counts"))
    if len(act_counts) == 1 and act_counts.get("1", 0):
        return room_counts["BOSS"]
    return _natural_int(natural, "act1_boss_battle_start_count", default=0)


def _later_act_start_count(natural: Mapping[str, Any]) -> int:
    value = natural.get("later_act_battle_start_count")
    explicit = value if isinstance(value, int) and not isinstance(value, bool) else 0
    derived = 0
    for act, count in _counter_from_mapping(natural.get("act_counts")).items():
        try:
            act_value = int(act)
        except ValueError:
            continue
        if act_value > 1:
            derived += count
    return max(explicit, derived)


def _yes_no(value: bool) -> str:
    return "yes" if value else "no"


def _controller_summary_from_metadata(
    metadata: Mapping[str, Any],
) -> ReachabilityControllerSummary:
    routed = dict(_mapping(metadata.get("source_controller_provenance"), "controller"))
    config = _mapping(routed.get("config", {}), "controller config")
    battle = _mapping(config.get("battle", {}), "battle controller provenance")
    non_combat = _mapping(
        config.get("non_combat", {}),
        "non-combat controller provenance",
    )
    battle_config = _mapping(battle.get("config", {}), "battle controller config")
    return ReachabilityControllerSummary(
        routed_controller=routed,
        battle_controller=dict(battle),
        non_combat_controller=dict(non_combat),
        battle_controller_kind=str(battle.get("kind", "(missing)")),
        battle_controller_name=str(battle.get("name", "(missing)")),
        non_combat_controller_name=str(non_combat.get("name", "(missing)")),
        information_regime=str(battle_config.get("information_regime", "unknown")),
        search_budget=dict(_mapping(battle_config.get("search_budget", {}), "search")),
        root_selection_rule=(
            battle_config.get("root_selection_rule")
            if isinstance(battle_config.get("root_selection_rule"), str)
            else None
        ),
        action_space=dict(_mapping(battle_config.get("action_space", {}), "actions")),
        include_potions=(
            battle_config.get("include_potions")
            if isinstance(battle_config.get("include_potions"), bool)
            else None
        ),
    )


def _assistance_decision_counts_from_metadata(
    metadata: Mapping[str, Any],
) -> Counter[str]:
    counts: Counter[str] = Counter()
    for raw in _metadata_list(metadata, "assistance_decisions"):
        if not isinstance(raw, Mapping):
            continue
        actual = raw.get("actual_change", {})
        reason = (
            actual.get("reason", "unknown")
            if isinstance(actual, Mapping)
            else "unknown"
        )
        status = str(raw.get("native_support_status", "unknown"))
        counts[f"{status}:{reason}"] += 1
    return counts


def _metadata_schedule_problems(
    level: str,
    metadata: Mapping[str, Any],
) -> list[str]:
    problems = []
    expected = ASSISTANCE_SCHEDULES.get(level)
    if expected is None:
        return ["unknown assistance level"]
    if metadata.get("assistance_level") != level:
        problems.append("artifact assistance level does not match arm level")
    if metadata.get("assistance_schedule") != expected.to_dict():
        problems.append("artifact assistance schedule does not match current contract")
    return problems


def _metadata_coverage_link_problems(
    *,
    label: str,
    metadata: Mapping[str, Any],
    coverage: Mapping[str, Any],
    artifact_identity: Mapping[str, Any],
) -> list[str]:
    problems = []
    natural = _mapping(coverage.get("natural_coverage"), "natural_coverage")
    record_count = _metadata_int(metadata, "record_count")
    if natural.get("natural_battle_start_count") != record_count:
        problems.append(f"{label}: coverage natural count does not match pool metadata")
    input_artifacts = coverage.get("input_artifacts")
    coverage_pool = (
        input_artifacts.get("natural_pool")
        if isinstance(input_artifacts, Mapping)
        else None
    )
    if not isinstance(coverage_pool, Mapping):
        problems.append(f"{label}: coverage report is missing natural_pool linkage")
    else:
        if coverage_pool.get("sha256") != artifact_identity.get("pool_sha256"):
            problems.append(f"{label}: coverage natural-pool sha256 does not match")
        if coverage_pool.get("record_count") != record_count:
            problems.append(f"{label}: coverage natural-pool record_count mismatch")
    restore = _mapping(coverage.get("restore_verification"), "restore_verification")
    if restore.get("restore_ok") is False:
        problems.append(f"{label}: restore verification failed")
    if coverage.get("command_passed") is False:
        problems.append(f"{label}: coverage command did not pass")
    for problem in _metadata_list(metadata, "problems"):
        problems.append(f"{label}: pool problem: {problem}")
    return problems


def _assistance_level_set_problems(levels: list[str]) -> list[str]:
    required = set(ASSISTANCE_LEVELS)
    present = set(levels)
    problems = []
    if len(present) != len(levels):
        problems.append("duplicate T042 assistance level in report inputs")
    missing = sorted(required - present)
    extra = sorted(present - required)
    if missing:
        problems.append(
            "missing required T042 assistance level(s): " + ", ".join(missing)
        )
    if extra:
        problems.append("unknown T042 assistance level(s): " + ", ".join(extra))
    return problems


def _aggregate_natural_coverage(payloads: list[Mapping[str, Any]]) -> dict[str, Any]:
    int_keys = (
        "completed_battle_count",
        "completed_battle_outcome_missing_count",
        "later_act_source_run_count",
        "later_act_battle_start_count",
        "natural_battle_start_count",
        "reported_battle_win_count",
        "sampled_draw_count",
        "source_run_count",
        "terminal_run_count",
        "truncated_run_count",
        "unique_source_start_count",
    )
    counter_keys = (
        "act_counts",
        "ascension_counts",
        "encounter_id_counts",
        "missing_metadata_counts",
        "reported_battle_outcome_counts",
        "room_type_counts",
        "sampling_component_counts",
        "structured_resource_outcome_status_counts",
    )
    result: dict[str, Any] = {key: 0 for key in int_keys}
    for payload in payloads:
        for key in int_keys:
            value = payload.get(key, 0)
            if isinstance(value, int) and not isinstance(value, bool):
                result[key] += value
    for key in counter_keys:
        counter: Counter[str] = Counter()
        for payload in payloads:
            counter.update(_counter_from_mapping(payload.get(key)))
        result[key] = dict(sorted(counter.items()))
    result["completed_outcomes_complete"] = all(
        payload.get("completed_outcomes_complete") is not False for payload in payloads
    )
    result["later_act_battle_start_count"] = _later_act_start_count(result)
    problems = []
    for payload in payloads:
        raw = payload.get("problems", [])
        if isinstance(raw, list):
            problems.extend(str(problem) for problem in raw)
    result["problems"] = list(dict.fromkeys(problems))
    return result


def _aggregate_sampled_distribution(
    coverage_shards: list[tuple[Path, Any]],
) -> dict[str, Any]:
    sampled_draw_count = 0
    sampled_unique_source_count = 0
    sampling_component_counts: Counter[str] = Counter()
    for _, payload in coverage_shards:
        if not isinstance(payload, Mapping):
            continue
        sampled = payload.get("sampled_optimization_weight", {})
        if not isinstance(sampled, Mapping):
            continue
        sampled_draw_count += _int_or_zero(sampled.get("sampled_draw_count"))
        sampled_unique_source_count += _int_or_zero(
            sampled.get("sampled_unique_source_count")
        )
        sampling_component_counts.update(
            _counter_from_mapping(sampled.get("sampling_component_counts"))
        )
    return {
        "sampled_draw_count": sampled_draw_count,
        "sampled_unique_source_count": sampled_unique_source_count,
        "sampling_component_counts": dict(sorted(sampling_component_counts.items())),
    }


def _aggregate_constructed_distribution(
    coverage_shards: list[tuple[Path, Any]],
) -> dict[str, Any]:
    for _, payload in coverage_shards:
        if isinstance(payload, Mapping) and isinstance(
            payload.get("constructed_coverage"),
            Mapping,
        ):
            constructed = dict(payload["constructed_coverage"])
            constructed["source_record_count"] = sum(
                _coverage_record_count(shard_payload) or 0
                for _, shard_payload in coverage_shards
            )
            return constructed
    return {"loaded": False, "problems": ["missing constructed coverage summary"]}


def _aggregate_training_row_coverage(
    coverage_shards: list[tuple[Path, Any]],
) -> dict[str, Any]:
    int_keys = ("row_count", "unique_natural_source_count")
    counter_keys = (
        "act_counts",
        "ascension_counts",
        "distribution_kind_counts",
        "encounter_id_counts",
        "missing_metadata_counts",
        "room_type_counts",
    )
    result: dict[str, Any] = {key: 0 for key in int_keys}
    for _, payload in coverage_shards:
        if not isinstance(payload, Mapping):
            continue
        rows = payload.get("training_row_coverage", {})
        if not isinstance(rows, Mapping):
            continue
        for key in int_keys:
            result[key] += _int_or_zero(rows.get(key))
    for key in counter_keys:
        counter: Counter[str] = Counter()
        for _, payload in coverage_shards:
            if isinstance(payload, Mapping) and isinstance(
                payload.get("training_row_coverage"),
                Mapping,
            ):
                counter.update(
                    _counter_from_mapping(payload["training_row_coverage"].get(key))
                )
        result[key] = dict(sorted(counter.items()))
    return result


def _aggregate_training_gate_reports(
    coverage_shards: list[tuple[Path, Any]],
) -> dict[str, Any]:
    gates = [
        payload.get("training_gate_report")
        for _, payload in coverage_shards
        if isinstance(payload, Mapping)
        and isinstance(payload.get("training_gate_report"), Mapping)
    ]
    if not gates:
        return {"training_allowed": False, "problems": ["missing training gate"]}
    first = dict(gates[0])
    first["record_count"] = sum(
        _int_or_zero(gate.get("record_count")) for gate in gates
    )
    for key in (
        "observed_act_counts",
        "observed_ascension_counts",
        "distribution_counts",
        "public_context_status_counts",
        "structured_outcome_status_counts",
    ):
        counter: Counter[str] = Counter()
        for gate in gates:
            counter.update(_counter_from_mapping(gate.get(key)))
        first[key] = dict(sorted(counter.items()))
    problems = []
    for gate in gates:
        raw = gate.get("problems", [])
        if isinstance(raw, list):
            problems.extend(str(problem) for problem in raw)
    first["problems"] = list(dict.fromkeys(problems))
    first["training_allowed"] = all(
        gate.get("training_allowed") is True for gate in gates
    )
    first["gate_passed_without_override"] = all(
        gate.get("gate_passed_without_override") is True for gate in gates
    )
    return first


def _restore_report_payload(report: BattleStartPoolRestoreReport) -> dict[str, Any]:
    return {
        "checkpoint_count": report.checkpoint_count,
        "requested_limit": report.requested_limit,
        "restored_count": report.restored_count,
        "native_restored_count": report.native_restored_count,
        "replay_restored_count": report.replay_restored_count,
        "context_compared_count": report.context_compared_count,
        "context_matched_count": report.context_matched_count,
        "context_legacy_unavailable_count": report.context_legacy_unavailable_count,
        "context_mismatch_count": report.context_mismatch_count,
        "restore_ok": report.restore_ok,
        "problems": list(report.problems),
    }


def _aggregate_restore_reports(
    coverage_shards: list[tuple[Path, Any]],
) -> BattleStartPoolRestoreReport:
    if not coverage_shards:
        raise ValueError("at least one assisted coverage shard is required")
    totals = {
        "checkpoint_count": 0,
        "restored_count": 0,
        "native_restored_count": 0,
        "replay_restored_count": 0,
        "context_compared_count": 0,
        "context_matched_count": 0,
        "context_legacy_unavailable_count": 0,
        "context_mismatch_count": 0,
    }
    problems: list[str] = []
    for path, payload in coverage_shards:
        if not isinstance(payload, dict):
            raise ValueError(f"{path}: coverage shard must be a JSON object")
        restore = payload.get("restore_verification")
        if not isinstance(restore, dict):
            raise ValueError(f"{path}: missing restore_verification")
        for key in totals:
            totals[key] += _restore_int(payload, key)
        if restore.get("restore_ok") is not True:
            problems.append(f"{path}: restore_ok is not true")
        raw_problems = restore.get("problems", [])
        if not isinstance(raw_problems, list):
            raise ValueError(f"{path}: restore problems must be a list")
        problems.extend(f"{path}: {problem}" for problem in raw_problems)
    return BattleStartPoolRestoreReport(
        checkpoint_count=totals["checkpoint_count"],
        requested_limit=0,
        restored_count=totals["restored_count"],
        native_restored_count=totals["native_restored_count"],
        replay_restored_count=totals["replay_restored_count"],
        context_compared_count=totals["context_compared_count"],
        context_matched_count=totals["context_matched_count"],
        context_legacy_unavailable_count=totals["context_legacy_unavailable_count"],
        context_mismatch_count=totals["context_mismatch_count"],
        problems=problems,
    )


def _restore_int(coverage: Any, key: str) -> int:
    if not isinstance(coverage, dict):
        raise ValueError("coverage shard must be a JSON object")
    restore = coverage.get("restore_verification")
    if not isinstance(restore, dict):
        raise ValueError("coverage shard missing restore_verification")
    value = restore.get(key)
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"restore_verification.{key} must be a non-negative integer")
    return value
