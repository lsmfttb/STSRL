"""Input-contract preflight for the T062 Battle Search v2 experiment."""

from __future__ import annotations

import hashlib
import json
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
