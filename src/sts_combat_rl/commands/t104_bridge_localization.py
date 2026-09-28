"""Reproducible T104 diagnosis entrypoint; execution requires Maintainer review."""

from __future__ import annotations

import argparse
import gc
import importlib.util
import json
import multiprocessing
import os
import shlex
import sys
import threading
import time
from collections.abc import Mapping
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from sts_combat_rl.commands import t088_canary, t101_particle_convergence
from sts_combat_rl.commands import t103_particle_diagnostic as predecessor
from sts_combat_rl.sim.t103_particle_diagnostic import (
    _canonical_json,
    _write_bytes_new,
    t103_record_shard_ranges,
)
from sts_combat_rl.sim.t104_bridge_localization import (
    T104IncompleteError,
    T104NativeRecordRunner,
    aggregate_localization,
    validate_t103_population,
)

T103_PRODUCER = "ec58e2ad396c149988ca639fd3b22244d331b9d7"
T103_EXECUTION_SHA256 = (
    "171e04a7271707513ae7310a71c9419cf08df3de3490c338610e97a387170d08"
)
T103_MANIFEST_SHA256 = (
    "614cd617e91036e1eaf8126b4930cc1bdc364d43ef1337c7db5b01ca05d5ffcf"
)
T103_REFERENCES = {
    "candidate_diagnostics": (
        "t103-particle-support-diagnostics-v1",
        "e9706fc1fd89c8e511931a79622b89753d29a342746601fdc93e8b8d1932f2ea",
    ),
    "aggregate_report": (
        "t103-particle-support-report-v1",
        "12d05289c30061c605e4b81a213423ae33a77095c330708d230d63a4a811c782",
    ),
}
NATIVE_BINARY_SHA256 = (
    "9eadacf39374d0fe64f407e0b93bbff14764926fcd30c965b7952e44bf64d42e"
)
_FORK_RUNNER: T104NativeRecordRunner | None = None
_FORK_STOP: object | None = None


def load_accepted_t103(
    manifest_path: Path, execution_path: Path
) -> tuple[list[dict], dict]:
    """Qualify exact retained evidence, never audit-only original results."""

    if predecessor._sha256_file(manifest_path) != T103_MANIFEST_SHA256:
        raise T104IncompleteError("accepted T103 retention hash mismatch")
    manifest = predecessor._read_json(manifest_path, label="T103 retention")
    provenance = manifest.get("producer_provenance")
    if (
        manifest.get("schema_id") != "t103-diagnostic-retention-manifest-v1"
        or manifest.get("task_id") != "T103"
        or manifest.get("terminal_classification")
        != "SUPPORT_DOMAIN_FAILURE_TAXONOMY_ESTABLISHED"
        or not isinstance(provenance, Mapping)
        or provenance.get("implementation_head") != T103_PRODUCER
    ):
        raise T104IncompleteError("accepted T103 producer/schema mismatch")
    references = manifest.get("artifact_references")
    if not isinstance(references, Mapping):
        raise T104IncompleteError("accepted T103 artifact bindings missing")
    documents = {}
    for role, (schema, sha) in T103_REFERENCES.items():
        reference = references.get(role)
        if not isinstance(reference, Mapping) or reference.get("sha256") != sha:
            raise T104IncompleteError("accepted T103 artifact hash binding mismatch")
        document, _ = predecessor._read_retained_reference(
            reference, role=role, expected_schema=schema
        )
        if document.get("task_id") != "T103":
            raise T104IncompleteError("accepted T103 artifact task mismatch")
        documents[role] = document
    if (
        documents["aggregate_report"].get("terminal_classification")
        != "SUPPORT_DOMAIN_FAILURE_TAXONOMY_ESTABLISHED"
    ):
        raise T104IncompleteError("accepted T103 report terminal mismatch")
    rows = validate_t103_population(documents["candidate_diagnostics"].get("rows"))
    if predecessor._sha256_file(execution_path) != T103_EXECUTION_SHA256:
        raise T104IncompleteError("accepted T103 execution hash mismatch")
    execution = predecessor._read_json(execution_path, label="T103 execution")
    command = execution.get("command")
    if (
        execution.get("state") != "SUCCEEDED"
        or execution.get("exit_code") != 0
        or not isinstance(command, list)
        or "--implementation-head" not in command
        or command[command.index("--implementation-head") + 1] != T103_PRODUCER
    ):
        raise T104IncompleteError(
            "accepted T103 execution is unavailable or mismatched"
        )
    for row in rows:
        if row.get("current_native_identity") != provenance.get(
            "current_native_identity"
        ):
            raise T104IncompleteError("accepted T103 row native binding mismatch")
    return rows, {
        "manifest": manifest,
        "execution_reference": {
            "path": str(execution_path.resolve()),
            "sha256": predecessor._sha256_file(execution_path),
            "size_bytes": execution_path.stat().st_size,
        },
        "manifest_sha256": T103_MANIFEST_SHA256,
    }


def worker_plan(
    requested: int | None, reason: str | None, record_count: int = 413
) -> tuple[int, int]:
    target = min(os.cpu_count() or 1, record_count)
    count = target if requested is None else requested
    if (
        isinstance(count, bool)
        or not isinstance(count, int)
        or not 1 <= count <= target
    ):
        raise T104IncompleteError(
            "worker count must be positive and no greater than host target"
        )
    if count < target and (not isinstance(reason, str) or not reason.strip()):
        raise T104IncompleteError(
            "lower process concurrency requires a documented resource/tooling reason"
        )
    if "fork" not in multiprocessing.get_all_start_methods():
        raise T104IncompleteError(
            "T104 parallel native execution requires the WSL/Linux fork runtime"
        )
    return target, count


def candidate_positions(value: list[int] | None) -> list[int]:
    positions = list(range(413)) if value is None else value
    if (
        not positions
        or any(
            isinstance(p, bool) or not isinstance(p, int) or not 0 <= p < 413
            for p in positions
        )
        or positions != sorted(set(positions))
    ):
        raise T104IncompleteError(
            "candidate positions must be unique ascending frozen population indexes"
        )
    return positions


def _initialize_worker(
    runner: T104NativeRecordRunner, stop_event: object | None = None
) -> None:
    global _FORK_RUNNER, _FORK_STOP
    _FORK_RUNNER = runner
    _FORK_STOP = stop_event


def _run_shard(
    jobs: list[tuple[dict, dict]], shard: dict, concurrency: int
) -> list[dict]:
    import resource  # WSL/Linux-only worker; the command itself remains importable.

    if _FORK_RUNNER is None:
        raise T104IncompleteError("worker restore inputs unavailable")
    rows = []
    for source, accepted in jobs:
        if _FORK_STOP is not None and _FORK_STOP.is_set():
            break
        row = _FORK_RUNNER.diagnose(
            source,
            accepted=accepted,
            source_ordinal=accepted["source_ordinal"],
            selection_digest=accepted["selection_digest"],
        )
        row["execution"] = {
            "worker_pid": os.getpid(),
            "configured_concurrency": concurrency,
            "worker_peak_rss_mib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
            / 1024,
            "shard": shard,
            "failure_retry_status": "no_retry",
        }
        rows.append(row)
        if not row["baseline_reproduced"]:
            if _FORK_STOP is not None:
                _FORK_STOP.set()
            break
    return rows


def write_artifacts(
    root: Path, rows: list[dict], report: dict, provenance: dict, regeneration: str
) -> dict:
    root = root.resolve()
    root.mkdir(parents=True, exist_ok=True)
    paths = [
        root / name
        for name in (
            "t104-candidate-localization.json",
            "t104-aggregate-report.json",
            "t104-retention-manifest.json",
        )
    ]
    if any(path.exists() for path in paths):
        raise T104IncompleteError("refusing to overwrite retained T104 evidence")
    refs = {}
    for role, path, document in (
        (
            "candidate_localization",
            paths[0],
            {
                "schema_id": "t104-bridge-localization-rows-v1",
                "task_id": "T104",
                "rows": rows,
            },
        ),
        ("aggregate_report", paths[1], report),
    ):
        refs[role] = _write_bytes_new(
            path, _canonical_json(document) + b"\n", document["schema_id"]
        )
    manifest = {
        "schema_id": "t104-localization-retention-manifest-v1",
        "task_id": "T104",
        "terminal_classification": report["terminal_classification"],
        "producer_provenance": provenance,
        "artifact_references": refs,
        "regeneration_commands": [regeneration],
        "retention_reason": "Frozen T103 failure localization and future observability planning; no repair/convergence reuse.",
        "raw_deletion_condition": "Delete only after T104 audit and successor observability consumers close.",
    }
    refs["retention_manifest"] = _write_bytes_new(
        paths[2], _canonical_json(manifest) + b"\n", manifest["schema_id"]
    )
    return refs


def run_from_paths(args: argparse.Namespace) -> dict:
    """Qualify once; fork only compact selected restore maps into native workers."""

    if len(args.implementation_head) != 40 or any(
        c not in "0123456789abcdef" for c in args.implementation_head
    ):
        raise T104IncompleteError("implementation head must be a full SHA-1")
    positions = candidate_positions(args.candidate_positions)
    target, count = worker_plan(
        args.worker_count, args.lower_worker_reason, len(positions)
    )
    accepted, retained = load_accepted_t103(
        args.t103_retention_manifest, args.t103_execution_record
    )
    if predecessor._sha256_file(args.native_binary) != NATIVE_BINARY_SHA256:
        raise T104IncompleteError("accepted native binary hash mismatch")
    module = importlib.util.find_spec("slaythespire")
    if (
        module is None
        or module.origin is None
        or Path(module.origin).resolve() != args.native_binary.resolve()
        or sys.version_info[:3] != (3, 13, 13)
    ):
        raise T104IncompleteError(
            "loaded native module or Python runtime differs from accepted binding"
        )
    started = time.perf_counter()
    _, admission, cohort, historical, native = predecessor._load_t101_terminal_inputs(
        args.t101_retention_manifest
    )
    current = predecessor._current_native_identity(admission)
    provenance = retained["manifest"]["producer_provenance"]
    if (
        current != native
        or current != provenance["current_native_identity"]
        or historical != provenance["historical_t101_bindings"]
    ):
        raise T104IncompleteError(
            "accepted T101/T103 producer inputs or current consumer changed"
        )
    formal, gate, _ = t088_canary._admit_t088_canary_inputs_from_paths(
        implementation_head=args.implementation_head,
        **{
            f"{name}_path": getattr(args, name)
            for name in (
                "t087_formal",
                "t087_report",
                "t087_retention",
                "t085_selection",
                "t085_restore",
                "a_pool",
                "b_pool",
                "c_pool",
                "b_source_manifest",
                "c_source_manifest",
            )
        },
        historical_t085_producer_only=True,
    )
    maps = gate.canonical_records_by_cohort
    sources = predecessor._source_records(
        t088_canary._project_t087_cohort(
            formal, gate.source_selection_manifest_identity, maps
        ),
        cohort["attempted"],
    )
    attempts = cohort["attempted"]
    if any(
        {
            key: row.get(key)
            for key in (
                "selection_identity",
                "stratum",
                "source_ordinal",
                "selection_digest",
            )
        }
        != {
            key: attempt.get(key)
            for key in (
                "selection_identity",
                "stratum",
                "source_ordinal",
                "selection_digest",
            )
        }
        for row, attempt in zip(accepted, attempts, strict=True)
    ):
        raise T104IncompleteError(
            "T103 identities/order/source ordinals differ from accepted T101"
        )
    selected_accepted = [accepted[index] for index in positions]
    selected_ids = {row["selection_identity"] for row in selected_accepted}
    selected = {
        r.selection_identity: r
        for s in ("A", "B", "C")
        for r in gate.cohorts[s]
        if r.selection_identity in selected_ids
    }
    # Drop unselected source records before forking. Each worker shares the
    # immutable qualified selected maps through OS copy-on-write, and touches
    # only the identities in its contiguous shard. No worker reloads a pool.
    compact_maps = {
        s: {
            r["selection_identity"]: maps[s][r["selection_identity"]]
            for r in selected_accepted
            if r["stratum"] == s
        }
        for s in ("A", "B", "C")
    }
    del gate, formal, maps
    gc.collect()
    runner = T104NativeRecordRunner(
        adapter_factory=t101_particle_convergence._default_adapter_factory,
        selected_records=selected,
        canonical_records_by_stratum=compact_maps,
        native_identity=current,
        historical_bindings=historical,
    )
    loading_wall = time.perf_counter() - started
    ranges = t103_record_shard_ranges(len(selected_accepted), count)
    jobs = [(dict(sources[r["selection_identity"]]), r) for r in selected_accepted]
    replay_started = time.perf_counter()
    if threading.active_count() != 1 or "slaythespire" in sys.modules:
        raise T104IncompleteError(
            "fork must precede parent native initialization and thread setup"
        )
    fork_context = multiprocessing.get_context("fork")
    stop_event = fork_context.Event()
    with ProcessPoolExecutor(
        max_workers=count,
        mp_context=fork_context,
        initializer=_initialize_worker,
        initargs=(runner, stop_event),
    ) as pool:
        futures = [
            pool.submit(
                _run_shard,
                jobs[shard["start_ordinal_inclusive"] : shard["end_ordinal_exclusive"]],
                shard,
                count,
            )
            for shard in ranges
        ]
        rows = [row for future in futures for row in future.result()]
    replay_wall = time.perf_counter() - replay_started
    if any(r["baseline_reproduced"] is not True for r in rows):
        report = {
            "schema_id": "t104-bridge-localization-report-v1",
            "task_id": "T104",
            "terminal_classification": "T103_SUPPORT_RESULT_NOT_REPRODUCED",
            "baseline_contradictions": [
                r["selection_identity"] for r in rows if not r["baseline_reproduced"]
            ],
            "rows_completed_before_shard_short_circuit": len(rows),
        }
    elif len(positions) != 413:
        report = {
            "schema_id": "t104-bridge-localization-report-v1",
            "task_id": "T104",
            "terminal_classification": "INCOMPLETE",
            "execution_scope": "canary",
            "canary_baselines_reproduced": len(rows) == len(positions)
            and all(r["baseline_reproduced"] for r in rows),
            "canary_diagnostic_evidence_complete": all(
                r["diagnostic_evidence_complete"] for r in rows
            ),
            "missing_full_census_count": 413 - len(rows),
            "candidate_positions": positions,
            "reason": "bounded canary does not complete the frozen 413-record diagnostic census",
        }
    else:
        report = aggregate_localization(rows)
    report["execution"] = {
        "worker_target": target,
        "effective_worker_count": len({r["execution"]["worker_pid"] for r in rows}),
        "configured_worker_count": count,
        "observed_worker_pids": sorted({r["execution"]["worker_pid"] for r in rows}),
        "candidate_positions": positions,
        "shard_count": count,
        "record_shard_ranges": ranges,
        "worker_reduction_reason": args.lower_worker_reason,
        "native_bridge_gil_released": False,
        "topology": "linux_fork_selected_restore_maps_copy_on_write",
        "input_loading_wall_clock_time_s": loading_wall,
        "replay_wall_clock_time_s": replay_wall,
    }
    regeneration = shlex.join(
        [
            sys.executable,
            "-m",
            "sts_combat_rl.commands.t104_bridge_localization",
            *sys.argv[1:],
        ]
    )
    refs = write_artifacts(
        args.output_root,
        rows,
        report,
        {
            "implementation_head": args.implementation_head,
            "current_native_identity": current,
            "accepted_t103": retained,
            "native_binary": {
                "path": str(args.native_binary.resolve()),
                "sha256": NATIVE_BINARY_SHA256,
                "python_version": sys.version,
                "python_executable": sys.executable,
            },
            "historical_t101_bindings": historical,
        },
        regeneration,
    )
    return {"report": report, "artifacts": refs}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--implementation-head", required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    for name in (
        "t101-retention-manifest",
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
    parser.add_argument("--t103-retention-manifest", type=Path, required=True)
    parser.add_argument("--t103-execution-record", type=Path, required=True)
    parser.add_argument("--native-binary", type=Path, required=True)
    parser.add_argument(
        "--candidate-positions",
        type=int,
        nargs="+",
        help="Ascending frozen population positions for bounded canary only; partial evidence remains INCOMPLETE",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = run_from_paths(args)
    except (OSError, ValueError, TypeError, KeyError, IndexError, RuntimeError) as exc:
        print(
            f"T104 qualification/execution incomplete: {type(exc).__name__}",
            file=sys.stderr,
        )
        print(json.dumps({"task_id": "T104", "terminal_classification": "INCOMPLETE"}))
        return 2
    print(json.dumps(result, sort_keys=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
