"""T103's bounded replay, aggregate report, and retention command."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shlex
import sys
import time
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path

from sts_combat_rl.commands import t088_canary, t101_particle_convergence
from sts_combat_rl.sim.lightspeed_source import load_lightspeed_source_manifest
from sts_combat_rl.sim.t101_particle_convergence import (
    T101_NATIVE_COMMIT,
    T101_NATIVE_REF,
    T101_SOURCE_COUNTS,
    T101IncompleteError,
    validate_t101_input_admission,
    validate_t101_insufficient_cohort,
)
from sts_combat_rl.sim.t103_particle_diagnostic import (
    T103_T101_RETENTION_SHA256,
    T103DiagnosticError,
    T103NativeRecordRunner,
    aggregate_t103_diagnostics,
    replay_t103_candidates,
    t103_record_shard_ranges,
    write_t103_retained_artifacts,
)


class T103PathError(ValueError):
    """A retained T103 input or output path is invalid."""


_T101_ROLE_SCHEMAS = {
    "input_admission": "t101-input-admission-v1",
    "cohort_admission": "t101-cohort-admission-v1",
    "cost_report": "t101-cost-report-v1",
    "final_report": "t101-final-report-v1",
}


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _read_json(path: Path, *, label: str) -> dict[str, object]:
    try:
        value = json.loads(path.resolve(strict=True).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise T103PathError(f"cannot read {label}") from exc
    if not isinstance(value, Mapping):
        raise T103PathError(f"{label} is not a JSON object")
    return dict(value)


def _read_retained_reference(
    reference: object, *, role: str, expected_schema: str
) -> tuple[dict[str, object], dict[str, object]]:
    if not isinstance(reference, Mapping):
        raise T103PathError(f"T101 retained reference {role} is missing")
    path_value = reference.get("path")
    sha = reference.get("sha256")
    size = reference.get("size_bytes")
    if (
        not isinstance(path_value, str)
        or not path_value
        or reference.get("schema_id") != expected_schema
        or not isinstance(sha, str)
        or len(sha) != 64
        or any(char not in "0123456789abcdef" for char in sha)
        or isinstance(size, bool)
        or not isinstance(size, int)
        or size < 0
    ):
        raise T103PathError(f"T101 retained reference {role} is malformed")
    path = Path(path_value)
    try:
        resolved = path.resolve(strict=True)
        stat = resolved.stat()
    except OSError as exc:
        raise T103PathError(f"T101 retained artifact {role} is unavailable") from exc
    if stat.st_size != size or _sha256_file(resolved) != sha:
        raise T103PathError(f"T101 retained artifact {role} hash/size mismatch")
    document = _read_json(resolved, label=f"T101 {role}")
    if document.get("schema_id") != expected_schema:
        raise T103PathError(f"T101 retained artifact {role} schema mismatch")
    return document, {
        "path": str(resolved),
        "schema_id": expected_schema,
        "sha256": sha,
        "size_bytes": size,
    }


def _t101_input_artifact_bindings(
    input_admission: Mapping[str, object],
) -> dict[str, dict[str, object]]:
    artifacts = input_admission.get("artifacts")
    if not isinstance(artifacts, Mapping):
        raise T103PathError("T101 input artifact bindings are missing")
    result: dict[str, dict[str, object]] = {}
    for role, eligibility in artifacts.items():
        if not isinstance(role, str) or not isinstance(eligibility, Mapping):
            raise T103PathError("T101 input artifact binding is malformed")
        artifact = eligibility.get("artifact")
        integrity = eligibility.get("integrity")
        if not isinstance(artifact, Mapping) or not isinstance(integrity, Mapping):
            raise T103PathError(f"T101 input artifact binding {role} is incomplete")
        path = artifact.get("path")
        schema = artifact.get("schema_id")
        size = artifact.get("size_bytes")
        sha = integrity.get("sha256")
        if (
            not isinstance(path, str)
            or not path
            or not isinstance(schema, str)
            or not schema
            or isinstance(size, bool)
            or not isinstance(size, int)
            or size < 0
            or not isinstance(sha, str)
            or len(sha) != 64
        ):
            raise T103PathError(f"T101 input artifact binding {role} is malformed")
        result[role] = {
            "path": path,
            "schema_id": schema,
            "sha256": sha,
            "size_bytes": size,
        }
    return result


def _load_t101_terminal_inputs(
    manifest_path: Path,
) -> tuple[
    dict[str, object],
    dict[str, object],
    dict[str, object],
    dict[str, object],
    dict[str, object],
]:
    try:
        resolved = manifest_path.resolve(strict=True)
    except OSError as exc:
        raise T103PathError("accepted T101 terminal manifest is unavailable") from exc
    manifest_sha = _sha256_file(resolved)
    if manifest_sha != T103_T101_RETENTION_SHA256:
        raise T103PathError("accepted T101 terminal manifest SHA-256 mismatch")
    manifest = _read_json(resolved, label="accepted T101 terminal manifest")
    if (
        manifest.get("schema_id") != "t101-terminal-retention-manifest-v1"
        or manifest.get("task_id") != "T101"
        or manifest.get("terminal_classification") != "SUPPORTED_COHORT_INSUFFICIENT"
    ):
        raise T103PathError("accepted T101 terminal manifest identity mismatch")
    refs = manifest.get("artifact_references")
    if not isinstance(refs, Mapping):
        raise T103PathError("accepted T101 artifact references are missing")

    input_admission, input_ref = _read_retained_reference(
        refs.get("input_admission"),
        role="input_admission",
        expected_schema=_T101_ROLE_SCHEMAS["input_admission"],
    )
    cohort, cohort_ref = _read_retained_reference(
        refs.get("cohort_admission"),
        role="cohort_admission",
        expected_schema=_T101_ROLE_SCHEMAS["cohort_admission"],
    )
    cost, cost_ref = _read_retained_reference(
        refs.get("cost_report"),
        role="cost_report",
        expected_schema=_T101_ROLE_SCHEMAS["cost_report"],
    )
    final, final_ref = _read_retained_reference(
        refs.get("final_report"),
        role="final_report",
        expected_schema=_T101_ROLE_SCHEMAS["final_report"],
    )
    try:
        validate_t101_input_admission(input_admission)
        validate_t101_insufficient_cohort(cohort)
    except T101IncompleteError as exc:
        raise T103PathError(
            "accepted T101 admission evidence failed validation"
        ) from exc

    attempts = cohort.get("attempted")
    selected = cohort.get("selected")
    if (
        not isinstance(attempts, Sequence)
        or isinstance(attempts, (str, bytes))
        or len(attempts) != sum(T101_SOURCE_COUNTS.values())
        or not isinstance(selected, Sequence)
        or isinstance(selected, (str, bytes))
        or len(selected) != 0
        or any(
            not isinstance(row, Mapping) or row.get("admitted") is not False
            for row in attempts
        )
        or cohort.get("exhausted_strata") != ["A", "B", "C"]
    ):
        raise T103PathError(
            "T101 retained evidence does not show 413 attempts and zero admissions"
        )

    provenance = manifest.get("producer_provenance")
    if not isinstance(provenance, Mapping):
        raise T103PathError("T101 terminal producer provenance is missing")
    native_identity = input_admission.get("native_identity")
    if (
        provenance.get("input_admission_artifact_sha256") != input_ref["sha256"]
        or provenance.get("cohort_admission_artifact_sha256") != cohort_ref["sha256"]
        or not isinstance(native_identity, Mapping)
        or dict(provenance.get("native_identity", {})) != dict(native_identity)
    ):
        raise T103PathError("T101 terminal evidence bindings do not agree")
    if (
        final.get("terminal_classification") != "SUPPORTED_COHORT_INSUFFICIENT"
        or final.get("support_admission_summary")
        != {
            "source_counts": dict(T101_SOURCE_COUNTS),
            "attempted_counts": dict(T101_SOURCE_COUNTS),
            "selected_counts": {},
            "exhausted_strata": ["A", "B", "C"],
        }
        or cost.get("terminal_classification") != "SUPPORTED_COHORT_INSUFFICIENT"
    ):
        raise T103PathError(
            "T101 final report/cost report does not preserve zero admission"
        )
    final_cohort_ref = final.get("cohort_admission")
    final_input_ref = final.get("input_admission")
    if (
        not isinstance(final_cohort_ref, Mapping)
        or final_cohort_ref.get("sha256") != cohort_ref["sha256"]
        or not isinstance(final_input_ref, Mapping)
        or final_input_ref.get("sha256") != input_ref["sha256"]
    ):
        raise T103PathError(
            "T101 final report references differ from terminal manifest"
        )

    binding = {
        "t101_terminal_retention_manifest": {
            "path": str(resolved),
            "schema_id": manifest["schema_id"],
            "sha256": manifest_sha,
            "size_bytes": resolved.stat().st_size,
        },
        "t101_input_admission": input_ref,
        "t101_cohort_admission": cohort_ref,
        "t101_final_report": final_ref,
        "t101_cost_report": cost_ref,
        # Preserve the historical producer's exact execution identity separately
        # from the current-native identity used by T103.
        "retained_t101_execution_identity": dict(provenance),
        "accepted_t101_source_artifacts": _t101_input_artifact_bindings(
            input_admission
        ),
        "historical_native_identity": dict(native_identity),
    }
    return manifest, input_admission, cohort, binding, dict(native_identity)


def _current_native_identity(
    input_admission: Mapping[str, object],
) -> dict[str, object]:
    try:
        manifest = load_lightspeed_source_manifest()
    except (OSError, ValueError) as exc:
        raise T103PathError("current native source manifest is unavailable") from exc
    repository = manifest.integration.repository_url.rstrip("/").removesuffix(".git")
    identity = {
        "repository": repository.removeprefix("https://github.com/"),
        "ref": manifest.integration.ref,
        "commit": manifest.integration.commit,
    }
    if identity != {
        "repository": "lsmfttb/sts_lightspeed",
        "ref": T101_NATIVE_REF,
        "commit": T101_NATIVE_COMMIT,
    }:
        raise T103PathError("current native identity differs from accepted T101/T099")
    if not {
        "native_t096_public_information_hidden_future_sampler",
        "native_stsr006_particle_search_bridge",
    }.issubset(manifest.capability_ids):
        raise T103PathError(
            "current native manifest lacks accepted T098/T099 capabilities"
        )
    artifacts = input_admission.get("artifacts")
    manifest_qualification = (
        artifacts.get("native_source_manifest")
        if isinstance(artifacts, Mapping)
        else None
    )
    artifact = (
        manifest_qualification.get("artifact")
        if isinstance(manifest_qualification, Mapping)
        else None
    )
    integrity = (
        manifest_qualification.get("integrity")
        if isinstance(manifest_qualification, Mapping)
        else None
    )
    if not isinstance(artifact, Mapping) or not isinstance(integrity, Mapping):
        raise T103PathError("T101 input admission lacks its source-manifest binding")
    current_manifest_path = Path(manifest.path).resolve(strict=True)
    if (
        integrity.get("sha256") != _sha256_file(current_manifest_path)
        or artifact.get("size_bytes") != current_manifest_path.stat().st_size
        or artifact.get("schema_id") != "sts-lightspeed-source-manifest-v1"
    ):
        raise T103PathError(
            "current native manifest differs from retained T101 input binding"
        )
    return identity


def _source_records(
    source_rows: Sequence[Mapping[str, object]],
    attempts: Sequence[Mapping[str, object]],
) -> dict[str, Mapping[str, object]]:
    records: dict[str, Mapping[str, object]] = {}
    for row in source_rows:
        identity = row.get("selection_identity")
        stratum = row.get("cohort", row.get("stratum"))
        if not isinstance(identity, str) or stratum not in T101_SOURCE_COUNTS:
            raise T103PathError("accepted T087/T085 source row is malformed")
        if identity in records:
            raise T103PathError(
                "accepted T087/T085 source set contains duplicate identity"
            )
        records[identity] = row
    attempt_ids = [row.get("selection_identity") for row in attempts]
    if (
        len(records) != sum(T101_SOURCE_COUNTS.values())
        or len(set(attempt_ids)) != len(attempts)
        or set(records) != set(attempt_ids)
    ):
        raise T103PathError(
            "current source records do not match exact T101 identity coverage"
        )
    observed_counts = Counter(
        str(row.get("cohort", row.get("stratum"))) for row in source_rows
    )
    if observed_counts != Counter(T101_SOURCE_COUNTS):
        raise T103PathError("current source record A/B/C counts differ from T101")
    return records


def run_t103_diagnostics_from_paths(
    *,
    t101_retention_manifest_path: Path,
    implementation_head: str,
    output_root: Path,
    t087_formal_path: Path,
    t087_report_path: Path,
    t087_retention_path: Path,
    t085_selection_path: Path,
    t085_restore_path: Path,
    a_pool_path: Path,
    b_pool_path: Path,
    c_pool_path: Path,
    b_source_manifest_path: Path,
    c_source_manifest_path: Path,
    worker_count: int | None = None,
    lower_worker_reason: str | None = None,
    adapter_factory: object | None = None,
    retention_reason: str = (
        "Retain the exact T103 support-domain diagnosis for audit and "
        "successor planning."
    ),
    deletion_condition: str = (
        "Delete raw T103 diagnostics only after all T103 audit and "
        "successor-planning consumers have closed."
    ),
) -> dict[str, object]:
    """Revalidate T101 evidence, load source pools once, then replay all 413."""

    if (
        not isinstance(implementation_head, str)
        or len(implementation_head) != 40
        or any(char not in "0123456789abcdef" for char in implementation_head)
    ):
        raise T103PathError("T103 implementation head must be a full SHA-1")
    host_workers = max(1, os.cpu_count() or 1)
    target_workers = min(host_workers, sum(T101_SOURCE_COUNTS.values()))
    effective_workers = target_workers if worker_count is None else worker_count
    if (
        isinstance(effective_workers, bool)
        or not isinstance(effective_workers, int)
        or not 1 <= effective_workers <= target_workers
    ):
        raise T103PathError("T103 worker count must be between one and the host target")
    if effective_workers < target_workers and not (
        isinstance(lower_worker_reason, str) and lower_worker_reason.strip()
    ):
        raise T103PathError("a documented lower-worker reason is required")
    if effective_workers == target_workers and lower_worker_reason is not None:
        raise T103PathError("lower-worker reason is only valid below the host target")

    start_load = time.perf_counter()
    _t101_manifest, input_admission, cohort, historical_bindings, accepted_native = (
        _load_t101_terminal_inputs(t101_retention_manifest_path)
    )
    current_native = _current_native_identity(input_admission)
    if current_native != accepted_native:
        raise T103PathError(
            "current native identity differs from retained T101 identity"
        )

    formal, gate, _inherited = t088_canary._admit_t088_canary_inputs_from_paths(
        implementation_head=implementation_head,
        t087_formal_path=t087_formal_path,
        t087_report_path=t087_report_path,
        t087_retention_path=t087_retention_path,
        t085_selection_path=t085_selection_path,
        t085_restore_path=t085_restore_path,
        a_pool_path=a_pool_path,
        b_pool_path=b_pool_path,
        c_pool_path=c_pool_path,
        b_source_manifest_path=b_source_manifest_path,
        c_source_manifest_path=c_source_manifest_path,
        historical_t085_producer_only=True,
    )
    maps = getattr(gate, "canonical_records_by_cohort", None)
    cohorts = getattr(gate, "cohorts", None)
    source_identity = getattr(gate, "source_selection_manifest_identity", None)
    if (
        not isinstance(maps, Mapping)
        or not isinstance(cohorts, Mapping)
        or not isinstance(source_identity, Mapping)
    ):
        raise T103PathError("admitted T087/T085 execution gate is malformed")
    source_rows = t088_canary._project_t087_cohort(formal, source_identity, maps)
    attempts = cohort.get("attempted")
    if not isinstance(attempts, Sequence) or isinstance(attempts, (str, bytes)):
        raise T103PathError("accepted T101 ordered attempts are unavailable")
    source_by_identity = _source_records(source_rows, attempts)

    selected_records = {
        record.selection_identity: record
        for stratum in ("A", "B", "C")
        for record in cohorts[stratum]
    }
    runner = T103NativeRecordRunner(
        adapter_factory=(
            adapter_factory or t101_particle_convergence._default_adapter_factory
        ),
        selected_records=selected_records,
        canonical_records_by_stratum=maps,
        native_identity=current_native,
        historical_bindings=historical_bindings,
    )
    input_loading_wall = time.perf_counter() - start_load
    replay_started = time.perf_counter()
    rows = replay_t103_candidates(
        runner=runner,
        source_records_by_identity=source_by_identity,
        attempts=attempts,
        worker_count=effective_workers,
    )
    replay_wall = time.perf_counter() - replay_started
    report = aggregate_t103_diagnostics(
        rows,
        source_counts=T101_SOURCE_COUNTS,
        t101_input_bindings=historical_bindings,
        native_identity=current_native,
    )
    report["execution"] = {
        "input_loading_wall_clock_time_s": input_loading_wall,
        "replay_wall_clock_time_s": replay_wall,
        "worker_target": target_workers,
        "effective_worker_count": effective_workers,
        "worker_reduction_reason": lower_worker_reason,
        "shard_count": effective_workers,
        "sharding_policy": "contiguous_t101_order_balanced_ranges_v1",
        "record_shard_ranges": t103_record_shard_ranges(len(rows), effective_workers),
        "source_pool_loading": "one_process_shared_canonical_maps",
        "candidate_calls": len(rows),
    }
    regeneration = shlex.join(
        [
            sys.executable,
            "-m",
            "sts_combat_rl.commands.t103_particle_diagnostic",
            *sys.argv[1:],
        ]
    )
    artifacts = write_t103_retained_artifacts(
        artifact_root=output_root,
        rows=rows,
        report=report,
        producer_provenance={
            "implementation_head": implementation_head,
            "current_native_identity": current_native,
            "historical_t101_bindings": historical_bindings,
            "effective_worker_count": effective_workers,
            "worker_reduction_reason": lower_worker_reason,
        },
        regeneration_command=regeneration,
        retention_reason=retention_reason,
        deletion_condition=deletion_condition,
    )
    return {
        "report": report,
        "artifacts": artifacts,
        "source_population": {
            "total": len(rows),
            "by_stratum": dict(T101_SOURCE_COUNTS),
        },
        "admitted_candidates": sum(row.get("admitted") is True for row in rows),
        "worker_count": effective_workers,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--t101-retention-manifest", type=Path, required=True)
    parser.add_argument("--implementation-head", required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    for name in (
        "t087-formal",
        "t087-report",
        "t087-retention",
        "t085-selection",
        "t085-restore",
        "a-pool",
        "b-pool",
        "c-pool",
        "b-source-manifest",
        "c-source-manifest",
    ):
        parser.add_argument(f"--{name}", type=Path, required=True)
    parser.add_argument("--worker-count", type=int)
    parser.add_argument("--lower-worker-reason")
    parser.add_argument(
        "--retention-reason",
        default=(
            "Retain the exact T103 support-domain diagnosis for audit and "
            "successor planning."
        ),
    )
    parser.add_argument(
        "--deletion-condition",
        default=(
            "Delete raw T103 diagnostics only after all T103 audit and "
            "successor-planning consumers have closed."
        ),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = run_t103_diagnostics_from_paths(
            t101_retention_manifest_path=args.t101_retention_manifest,
            implementation_head=args.implementation_head,
            output_root=args.output_root,
            t087_formal_path=args.t087_formal,
            t087_report_path=args.t087_report,
            t087_retention_path=args.t087_retention,
            t085_selection_path=args.t085_selection,
            t085_restore_path=args.t085_restore,
            a_pool_path=args.a_pool,
            b_pool_path=args.b_pool,
            c_pool_path=args.c_pool,
            b_source_manifest_path=args.b_source_manifest,
            c_source_manifest_path=args.c_source_manifest,
            worker_count=args.worker_count,
            lower_worker_reason=args.lower_worker_reason,
            retention_reason=args.retention_reason,
            deletion_condition=args.deletion_condition,
        )
    except (
        OSError,
        T101IncompleteError,
        T103DiagnosticError,
        T103PathError,
        ValueError,
    ) as exc:
        print(f"T103 diagnostic command failed: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
