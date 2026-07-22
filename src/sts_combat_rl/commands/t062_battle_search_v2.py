"""Input-contract preflight for the T062 Battle Search v2 experiment."""

from __future__ import annotations

import hashlib
import json
import math
import random
from collections import Counter
from collections.abc import Callable, Sequence
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from sts_combat_rl.sim.action_space import ActionSpaceConfig
from sts_combat_rl.sim.contract import CheckpointingSimulatorAdapter
from sts_combat_rl.sim.controller_contract import OnlineController
from sts_combat_rl.sim.fixed_battle_evaluation import (
    FixedEvaluationReport,
    evaluate_fixed_cohort,
)
from sts_combat_rl.sim.fixed_evaluation_set import (
    FixedCohort,
    FixedCohortRecord,
    load_fixed_cohort_jsonl,
)
from sts_combat_rl.sim.model_guided_search_comparison import (
    fixed_report_sequence_source_match_problems,
)


T062_INPUT_PREFLIGHT_SCHEMA_ID = "t062-battle-search-v2-input-preflight-v1"
T061_RETENTION_MANIFEST_SHA256 = (
    "2fb5e329505b52541edbd7aa74b5fa2025e97276523ee341884538a4d7b3ef90"
)
T052_COHORT_SHA256 = "b7f8e9b85b53bbf8e37adfe6cc90d0579937661309b26bce2a8f2921604a8608"
T052_COHORT_BYTES = 161435825
T043_CHECKPOINT_SHA256 = (
    "a2317354b24f93ff48f0408ba3fdc92056701ef16e9b3a1b8b17aa1cce2a56e4"
)
T043_CHECKPOINT_BYTES = 386717
T062_COMPARISON_SCHEMA_ID = "t062-battle-search-v2-comparison-v1"
T062_ARM_LABELS = ("baseline", "prior_only", "value_only", "prior_value")


def run_t062_comparison_from_cohort_path(
    *,
    adapter_factory: Callable[[], CheckpointingSimulatorAdapter],
    cohort_path: Path,
    controller_arms: Sequence[tuple[str, OnlineController]],
    action_space: ActionSpaceConfig,
    max_battle_steps: int,
    family: str,
    worker_count: int = 1,
    shard_count: int = 1,
    record_range: str | None = None,
) -> dict[str, Any]:
    """Evaluate the four fixed T062 arms on an explicit cohort record range.

    The returned object is deliberately JSON-native so every external shard can
    be inspected without importing an experiment-only report class.  A caller
    must merge disjoint ranges before treating the report as primary evidence.
    """

    labels = tuple(label for label, _ in controller_arms)
    if labels != T062_ARM_LABELS:
        raise ValueError(f"T062 controller arms must be exactly {T062_ARM_LABELS!r}")
    if family not in {"nominal", "simulator_step_normalized", "wall_clock_normalized"}:
        raise ValueError(f"unsupported T062 comparison family {family!r}")
    if worker_count < 1 or shard_count < 1:
        raise ValueError("T062 worker and shard counts must be positive")
    with cohort_path.open("r", encoding="utf-8") as stream:
        cohort = load_fixed_cohort_jsonl(stream)
    selected = _select_record_range(cohort.records, record_range)
    if not selected:
        raise ValueError("T062 selected no cohort records")

    reports = {
        label: _evaluate_t062_arm(
            adapter_factory=adapter_factory,
            cohort=cohort,
            records=selected,
            controller=controller,
            action_space=action_space,
            max_battle_steps=max_battle_steps,
            worker_count=worker_count,
            shard_count=shard_count,
        )
        for label, controller in controller_arms
    }
    source_problems = fixed_report_sequence_source_match_problems(
        [(label, reports[label]) for label in T062_ARM_LABELS]
    )
    return {
        "schema_id": T062_COMPARISON_SCHEMA_ID,
        "task_id": "T062",
        "family": family,
        "cohort_path": str(cohort_path),
        "cohort_identity": cohort.identity,
        "cohort_total_record_count": len(cohort.records),
        "record_range": record_range or "all",
        "evaluated_record_count": len(selected),
        "worker_count": worker_count,
        "shard_count": shard_count,
        "action_space": action_space.to_dict(),
        "max_battle_steps": max_battle_steps,
        "controller_provenance": {
            label: controller.provenance.to_dict()
            for label, controller in controller_arms
        },
        "source_match_problems": source_problems,
        "arms": {
            label: _fixed_report_summary(reports[label]) for label in T062_ARM_LABELS
        },
        "successful": not source_problems
        and all(report.evaluation_successful for report in reports.values()),
    }


def write_t062_comparison_report(path: Path, report: dict[str, Any]) -> None:
    """Write a stable, inspectable T062 shard or merged comparison report."""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def merge_t062_comparison_reports_from_paths(
    *,
    shard_paths: Sequence[Path],
    output_path: Path,
    expected_record_count: int,
    bootstrap_resamples: int = 2_000,
    bootstrap_seed: int = 6201,
) -> dict[str, Any]:
    """Merge disjoint T062 shards and compute deterministic paired statistics."""

    if expected_record_count < 1:
        raise ValueError("expected T062 record count must be positive")
    if bootstrap_resamples < 100:
        raise ValueError("T062 bootstrap resamples must be at least 100")
    reports = [_load_t062_comparison(path) for path in shard_paths]
    if not reports:
        raise ValueError("at least one T062 comparison shard is required")
    first = reports[0]
    compatible_keys = (
        "family",
        "cohort_identity",
        "cohort_total_record_count",
        "action_space",
        "max_battle_steps",
        "controller_provenance",
    )
    problems: list[str] = []
    combined = {label: [] for label in T062_ARM_LABELS}
    for shard_index, report in enumerate(reports):
        for key in compatible_keys:
            if report.get(key) != first.get(key):
                problems.append(f"shard {shard_index}: {key} differs")
        if not report.get("successful"):
            problems.append(f"shard {shard_index}: evaluation was not successful")
        arms = report.get("arms")
        if not isinstance(arms, dict) or set(arms) != set(T062_ARM_LABELS):
            problems.append(f"shard {shard_index}: arms are incomplete")
            continue
        for label in T062_ARM_LABELS:
            rows = arms[label].get("records")
            if not isinstance(rows, list):
                problems.append(f"shard {shard_index}: {label} records are missing")
                continue
            combined[label].extend(row for row in rows if isinstance(row, dict))

    indexed = {
        label: _index_t062_records(combined[label], label, problems)
        for label in T062_ARM_LABELS
    }
    reference_indices = set(indexed["baseline"])
    for label in T062_ARM_LABELS[1:]:
        if set(indexed[label]) != reference_indices:
            problems.append(f"{label}: cohort indices do not match baseline")
        for cohort_index in reference_indices.intersection(indexed[label]):
            if _source_key(indexed[label][cohort_index]) != _source_key(
                indexed["baseline"][cohort_index]
            ):
                problems.append(f"{label}: source identity mismatch at {cohort_index}")
    if len(reference_indices) != expected_record_count:
        problems.append(
            f"expected {expected_record_count} distinct records, found {len(reference_indices)}"
        )
    ordered = sorted(reference_indices)
    arms = {
        label: _merged_arm_summary(
            [
                indexed[label][cohort_index]
                for cohort_index in ordered
                if cohort_index in indexed[label]
            ]
        )
        for label in T062_ARM_LABELS
    }
    paired = {
        label: _paired_t062_summary(
            baseline=arms["baseline"]["records"],
            guided=arms[label]["records"],
            bootstrap_resamples=bootstrap_resamples,
            bootstrap_seed=bootstrap_seed + position,
        )
        for position, label in enumerate(T062_ARM_LABELS[1:], start=1)
    }
    merged = {
        "schema_id": T062_COMPARISON_SCHEMA_ID,
        "format_version": 1,
        "task_id": "T062",
        "report_kind": "merged_comparison",
        "family": first.get("family"),
        "cohort_identity": first.get("cohort_identity"),
        "cohort_total_record_count": first.get("cohort_total_record_count"),
        "evaluated_record_count": len(ordered),
        "expected_record_count": expected_record_count,
        "action_space": first.get("action_space"),
        "max_battle_steps": first.get("max_battle_steps"),
        "controller_provenance": first.get("controller_provenance"),
        "worker_count": len(reports),
        "shard_count": len(reports),
        "shards": [str(path) for path in shard_paths],
        "arms": arms,
        "paired_vs_baseline": paired,
        "problems": list(dict.fromkeys(problems)),
        "command_passed": not problems,
    }
    write_t062_comparison_report(output_path, merged)
    return merged


def load_t062_comparison_report(path: Path) -> dict[str, Any]:
    """Load one current-schema T062 shard or merged comparison report."""

    return _load_t062_comparison(path)


def build_t062_decision_report(
    *,
    nominal_report: dict[str, Any],
    simulator_step_report: dict[str, Any],
    wall_clock_report: dict[str, Any],
) -> dict[str, Any]:
    """Apply the predeclared T062 gate to the three separate families."""

    reports = {
        "nominal": nominal_report,
        "simulator_step_normalized": simulator_step_report,
        "wall_clock_normalized": wall_clock_report,
    }
    failed_families = [
        name for name, report in reports.items() if not report.get("command_passed")
    ]
    nominal = _prior_value_pair(nominal_report)
    steps = _prior_value_pair(simulator_step_report)
    wall = _prior_value_pair(wall_clock_report)
    equal_budget = (
        _positive_delta(nominal, "overall")
        and _ci_lower_nonnegative(nominal, "overall")
        and all(
            _nonnegative_delta(nominal, name) for name in ("boss_only", "act2_plus")
        )
    )
    normalized = all(
        _nonnegative_delta(pair, name)
        for pair in (steps, wall)
        for name in ("overall", "boss_only", "act2_plus")
    ) and (_positive_delta(steps, "overall") or _positive_delta(wall, "overall"))
    tied_hp = all(
        _nonnegative_tied_hp(pair, name)
        for pair in (nominal, steps, wall)
        for name in ("overall", "boss_only", "act2_plus")
    )
    cost = _cost_within(steps, "native_simulator_steps", 0.05) and _cost_within(
        wall, "wall_clock_seconds", 0.10
    )
    promote = not failed_families and equal_budget and normalized and tied_hp and cost
    return {
        "schema_id": "t062-battle-search-v2-decision-report-v1",
        "task_id": "T062",
        "predeclared_candidate": "prior_value",
        "promotion_gates": {
            "zero_failures": not failed_families,
            "equal_budget_prior_value": equal_budget,
            "compute_normalized_prior_value": normalized,
            "tied_terminal_hp": tied_hp,
            "matched_cost": cost,
        },
        "failed_families": failed_families,
        "recommendation": (
            "T062-search-v2-complete-run-evaluation"
            if promote
            else "T062-tree-internal-search-repair-or-closure"
        ),
        "command_passed": not failed_families,
    }


def _evaluate_t062_arm(
    *,
    adapter_factory: Callable[[], CheckpointingSimulatorAdapter],
    cohort: FixedCohort,
    records: Sequence[FixedCohortRecord],
    controller: OnlineController,
    action_space: ActionSpaceConfig,
    max_battle_steps: int,
    worker_count: int,
    shard_count: int,
) -> FixedEvaluationReport:
    chunks = _chunks(records, shard_count)

    def evaluate(chunk: Sequence[FixedCohortRecord]) -> FixedEvaluationReport:
        return evaluate_fixed_cohort(
            adapter_factory=adapter_factory,
            cohort_records=chunk,
            controller=controller,
            cohort_identity=cohort.identity,
            source_pool_format_version=cohort.source_pool_format_version,
            selection_config=cohort.selection_config.to_dict(),
            action_space=action_space,
            max_battle_steps=max_battle_steps,
        )

    if len(chunks) == 1:
        partials = [evaluate(chunks[0])]
    else:
        with ThreadPoolExecutor(max_workers=min(worker_count, len(chunks))) as executor:
            partials = list(executor.map(evaluate, chunks))
    first = partials[0]
    problems = [problem for partial in partials for problem in partial.problems]
    results = sorted(
        [result for partial in partials for result in partial.battle_results],
        key=lambda result: result.cohort_index,
    )
    counts = Counter(
        "/".join(str(value) for value in record.structural_stratum)
        for record in records
    )
    return FixedEvaluationReport(
        cohort_identity=first.cohort_identity,
        controller_provenance=first.controller_provenance,
        information_regime=first.information_regime,
        action_space_config=first.action_space_config,
        max_battle_steps=first.max_battle_steps,
        source_pool_format_version=first.source_pool_format_version,
        selection_config=first.selection_config,
        per_stratum_source_counts=dict(counts),
        battle_results=results,
        problems=problems,
    )


def _fixed_report_summary(report: FixedEvaluationReport) -> dict[str, Any]:
    """Keep per-record outcomes plus aggregate compute visible in every shard."""

    results = []
    for result in report.battle_results:
        telemetry = result.controller_compute_telemetry or {}
        results.append(
            {
                "cohort_index": result.cohort_index,
                "source_checkpoint_id": result.source_checkpoint_id,
                "structural_metadata": result.structural_metadata,
                "termination_status": result.termination_status,
                "terminal_absolute_hp": result.terminal_absolute_hp,
                "structured_battle_outcome": result.structured_battle_outcome,
                "decision_count": result.decision_count,
                "outer_simulator_steps": result.simulator_step_count,
                "wall_clock_seconds": result.wall_clock_time_s,
                "controller_compute_telemetry": telemetry,
                "problems": result.problems,
            }
        )
    return {
        "controller_provenance": report.controller_provenance,
        "total_battles": report.total_battles,
        "wins": report.authoritative_wins,
        "losses": report.losses,
        "truncations": report.truncations,
        "errors": report.errors,
        "evaluation_problems": report.problems,
        "records": results,
    }


def _load_t062_comparison(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read T062 comparison {path}: {exc}") from exc
    if (
        not isinstance(value, dict)
        or value.get("schema_id") != T062_COMPARISON_SCHEMA_ID
    ):
        raise ValueError(f"{path}: unsupported T062 comparison schema")
    return value


def _index_t062_records(
    rows: Sequence[dict[str, Any]], label: str, problems: list[str]
) -> dict[int, dict[str, Any]]:
    indexed: dict[int, dict[str, Any]] = {}
    for row in rows:
        cohort_index = row.get("cohort_index")
        if not isinstance(cohort_index, int) or isinstance(cohort_index, bool):
            problems.append(f"{label}: record without integer cohort_index")
            continue
        if cohort_index in indexed:
            problems.append(f"{label}: duplicate cohort_index {cohort_index}")
            continue
        indexed[cohort_index] = row
    return indexed


def _source_key(row: dict[str, Any]) -> tuple[Any, ...]:
    metadata = row.get("structural_metadata")
    if not isinstance(metadata, dict):
        metadata = {}
    return (
        row.get("cohort_index"),
        row.get("source_checkpoint_id"),
        metadata.get("source_run_id"),
        metadata.get("source_battle_index"),
    )


def _merged_arm_summary(rows: Sequence[dict[str, Any]]) -> dict[str, Any]:
    rows = list(rows)
    return {
        "record_count": len(rows),
        "wins": sum(row.get("termination_status") == "win" for row in rows),
        "losses": sum(row.get("termination_status") == "loss" for row in rows),
        "truncations": sum(
            row.get("termination_status") == "truncated" for row in rows
        ),
        "errors": sum(row.get("termination_status") == "error" for row in rows),
        "outer_simulator_steps": sum(
            _number(row.get("outer_simulator_steps")) for row in rows
        ),
        "wall_clock_seconds": sum(
            _number(row.get("wall_clock_seconds")) for row in rows
        ),
        "native_simulator_steps": sum(
            _telemetry_number(row, "native_simulator_steps") for row in rows
        ),
        "model_calls": sum(_telemetry_number(row, "model_calls") for row in rows),
        "records": rows,
    }


def _paired_t062_summary(
    *,
    baseline: Sequence[dict[str, Any]],
    guided: Sequence[dict[str, Any]],
    bootstrap_resamples: int,
    bootstrap_seed: int,
) -> dict[str, Any]:
    left = {int(row["cohort_index"]): row for row in baseline}
    right = {int(row["cohort_index"]): row for row in guided}
    return {
        name: _paired_t062_stratum(
            [index for index in sorted(left) if predicate(left[index])],
            left,
            right,
            bootstrap_resamples,
            bootstrap_seed + offset,
        )
        for offset, (name, predicate) in enumerate(
            (
                ("overall", lambda row: True),
                (
                    "boss_only",
                    lambda row: (
                        row.get("structural_metadata", {}).get("room_type") == "BOSS"
                    ),
                ),
                (
                    "act2_plus",
                    lambda row: (
                        _number(row.get("structural_metadata", {}).get("act")) >= 2
                    ),
                ),
            )
        )
    }


def _paired_t062_stratum(
    indices: Sequence[int],
    baseline: dict[int, dict[str, Any]],
    guided: dict[int, dict[str, Any]],
    resamples: int,
    seed: int,
) -> dict[str, Any]:
    win_deltas = [
        int(guided[index].get("termination_status") == "win")
        - int(baseline[index].get("termination_status") == "win")
        for index in indices
    ]
    tied_hp = [
        _number(guided[index].get("terminal_absolute_hp"))
        - _number(baseline[index].get("terminal_absolute_hp"))
        for index in indices
        if guided[index].get("termination_status")
        == baseline[index].get("termination_status")
        and guided[index].get("terminal_absolute_hp") is not None
        and baseline[index].get("terminal_absolute_hp") is not None
    ]
    cost = {
        metric: _ratio(
            sum(_telemetry_number(guided[index], metric) for index in indices),
            sum(_telemetry_number(baseline[index], metric) for index in indices),
        )
        for metric in ("native_simulator_steps", "wall_clock_seconds")
    }
    return {
        "record_count": len(indices),
        "paired_win_delta": sum(win_deltas),
        "paired_win_delta_mean": _mean(win_deltas),
        "paired_win_delta_bootstrap_95ci": _bootstrap_ci(win_deltas, resamples, seed),
        "mean_terminal_hp_delta_among_outcome_ties": _mean(tied_hp),
        "cost_ratio_guided_over_baseline": cost,
    }


def _telemetry_number(row: dict[str, Any], metric: str) -> float:
    if metric == "wall_clock_seconds":
        return _number(row.get("wall_clock_seconds"))
    telemetry = row.get("controller_compute_telemetry")
    if not isinstance(telemetry, dict):
        return 0.0
    return _number(telemetry.get(f"oracle_search_{metric}"))


def _number(value: Any) -> float:
    return (
        float(value)
        if isinstance(value, (int, float)) and not isinstance(value, bool)
        else 0.0
    )


def _mean(values: Sequence[float]) -> float | None:
    return None if not values else sum(values) / len(values)


def _ratio(numerator: float, denominator: float) -> float | None:
    return None if denominator <= 0.0 else numerator / denominator


def _bootstrap_ci(
    values: Sequence[float], resamples: int, seed: int
) -> list[float | None]:
    if not values:
        return [None, None]
    rng = random.Random(seed)
    size = len(values)
    means = sorted(
        sum(values[rng.randrange(size)] for _ in range(size)) / size
        for _ in range(resamples)
    )
    return [means[int(0.025 * (resamples - 1))], means[int(0.975 * (resamples - 1))]]


def _prior_value_pair(report: dict[str, Any]) -> dict[str, Any]:
    paired = report.get("paired_vs_baseline")
    return paired.get("prior_value", {}) if isinstance(paired, dict) else {}


def _positive_delta(pair: dict[str, Any], stratum: str) -> bool:
    return _number(pair.get(stratum, {}).get("paired_win_delta")) > 0.0


def _nonnegative_delta(pair: dict[str, Any], stratum: str) -> bool:
    return _number(pair.get(stratum, {}).get("paired_win_delta")) >= 0.0


def _ci_lower_nonnegative(pair: dict[str, Any], stratum: str) -> bool:
    values = pair.get(stratum, {}).get("paired_win_delta_bootstrap_95ci")
    return (
        isinstance(values, list)
        and len(values) == 2
        and values[0] is not None
        and _number(values[0]) >= 0.0
    )


def _nonnegative_tied_hp(pair: dict[str, Any], stratum: str) -> bool:
    value = pair.get(stratum, {}).get("mean_terminal_hp_delta_among_outcome_ties")
    return value is not None and _number(value) >= 0.0


def _cost_within(pair: dict[str, Any], metric: str, tolerance: float) -> bool:
    ratio = (
        pair.get("overall", {}).get("cost_ratio_guided_over_baseline", {}).get(metric)
    )
    return (
        ratio is not None
        and math.isfinite(_number(ratio))
        and abs(_number(ratio) - 1.0) <= tolerance
    )


def _select_record_range(
    records: Sequence[FixedCohortRecord], record_range: str | None
) -> Sequence[FixedCohortRecord]:
    if record_range is None:
        return records
    try:
        start_text, end_text = record_range.split(":", 1)
        start, end = int(start_text), int(end_text)
    except ValueError as exc:
        raise ValueError("record_range must be START:END") from exc
    if start < 0 or end <= start or end > len(records):
        raise ValueError("record_range is outside the fixed cohort")
    return records[start:end]


def _chunks(
    records: Sequence[FixedCohortRecord], shard_count: int
) -> list[Sequence[FixedCohortRecord]]:
    width = max(1, (len(records) + shard_count - 1) // shard_count)
    return [records[index : index + width] for index in range(0, len(records), width)]


def run_t062_input_preflight_from_paths(
    *,
    output_path: Path,
    t061_retention_manifest_path: Path,
    t052_cohort_path: Path,
    t043_checkpoint_path: Path,
) -> dict[str, Any]:
    """Verify all immutable T062 input identities before any model call."""

    artifacts = {
        "t061_retention_manifest": _verify_t061_retention_manifest(
            t061_retention_manifest_path
        ),
        "t052_fixed_cohort": _verify_file(
            t052_cohort_path,
            expected_sha256=T052_COHORT_SHA256,
            expected_bytes=T052_COHORT_BYTES,
        ),
        "t043_checkpoint": _verify_file(
            t043_checkpoint_path,
            expected_sha256=T043_CHECKPOINT_SHA256,
            expected_bytes=T043_CHECKPOINT_BYTES,
        ),
    }
    problems = [
        f"{label}: {problem}"
        for label, identity in artifacts.items()
        for problem in identity["problems"]
    ]
    manifest_payload: dict[str, Any] | None = None
    if not artifacts["t061_retention_manifest"]["problems"]:
        try:
            raw = json.loads(t061_retention_manifest_path.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                raise ValueError("must be a JSON object")
            if raw.get("schema_id") != "t061-retention-manifest-v2":
                raise ValueError("has an unsupported schema_id")
            retention_root = raw.get("retention_root")
            if not isinstance(retention_root, str) or not retention_root:
                raise ValueError("omits retention_root")
            manifest_payload = {
                "schema_id": raw["schema_id"],
                "retention_root": retention_root,
                "raw_artifacts_may_be_deleted_when": raw.get(
                    "raw_artifacts_may_be_deleted_when"
                ),
            }
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            problems.append(f"t061_retention_manifest: invalid manifest: {exc}")

    report = {
        "schema_id": T062_INPUT_PREFLIGHT_SCHEMA_ID,
        "task_id": "T062",
        "input_artifacts": artifacts,
        "t061_retention_contract": manifest_payload,
        "command_passed": not problems,
        "problems": problems,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return report


def format_t062_input_preflight_report(report: dict[str, Any]) -> str:
    """Format the fail-closed input-contract preflight for stderr."""

    lines = [
        "T062 Battle Search v2 input preflight",
        f"command passed: {'yes' if report.get('command_passed') else 'no'}",
    ]
    for label, identity in report.get("input_artifacts", {}).items():
        lines.append(
            f"{label}: sha256={identity.get('sha256', '(missing)')}, "
            f"bytes={identity.get('bytes', '(missing)')}"
        )
    if report.get("problems"):
        lines.append("problems:")
        lines.extend(f"  {problem}" for problem in report["problems"])
    return "\n".join(lines)


def _verify_file(
    path: Path,
    *,
    expected_sha256: str,
    expected_bytes: int | None = None,
) -> dict[str, Any]:
    problems: list[str] = []
    if not path.is_file():
        problems.append("required file does not exist")
        return {
            "path": str(path),
            "expected_sha256": expected_sha256,
            "expected_bytes": expected_bytes,
            "sha256": None,
            "bytes": None,
            "problems": problems,
        }
    byte_count = path.stat().st_size
    actual = _sha256_file(path)
    if actual != expected_sha256:
        problems.append("sha256 does not match the published T062 contract")
    if expected_bytes is not None and byte_count != expected_bytes:
        problems.append("byte count does not match the published T062 contract")
    return {
        "path": str(path),
        "expected_sha256": expected_sha256,
        "expected_bytes": expected_bytes,
        "sha256": actual,
        "bytes": byte_count,
        "problems": problems,
    }


def _verify_t061_retention_manifest(path: Path) -> dict[str, Any]:
    """Verify T061's documented canonical self-hash, not its raw file hash."""

    identity = _verify_file(path, expected_sha256="")
    identity["expected_sha256"] = T061_RETENTION_MANIFEST_SHA256
    if not path.is_file():
        return identity
    identity["problems"] = []
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError("must be a JSON object")
        manifest_identity = raw.get("manifest_identity")
        if not isinstance(manifest_identity, dict):
            raise ValueError("omits manifest_identity")
        if manifest_identity.get("sha256") != T061_RETENTION_MANIFEST_SHA256:
            identity["problems"].append(
                "manifest_identity.sha256 does not match the published T062 contract"
            )
        if manifest_identity.get("bytes") != path.stat().st_size:
            identity["problems"].append(
                "manifest_identity.bytes does not match the on-disk file"
            )
        canonical = dict(raw)
        canonical_identity = dict(manifest_identity)
        canonical_identity["bytes"] = None
        canonical_identity["sha256"] = None
        canonical["manifest_identity"] = canonical_identity
        canonical_bytes = (
            json.dumps(canonical, indent=2, sort_keys=True) + "\n"
        ).encode("utf-8")
        canonical_sha256 = hashlib.sha256(canonical_bytes).hexdigest()
        identity["canonical_sha256"] = canonical_sha256
        if canonical_sha256 != T061_RETENTION_MANIFEST_SHA256:
            identity["problems"].append(
                "canonical retention-manifest self-hash does not match the published T062 contract"
            )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        identity["problems"].append(f"invalid retention manifest: {exc}")
    return identity


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()
