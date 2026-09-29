"""T106 structured failure-stage replay; full execution needs Maintainer readiness."""

from __future__ import annotations

import argparse
import gc
import importlib.util
import json
import multiprocessing
import os
import shlex
import subprocess
import sys
import threading
import time
from collections.abc import Mapping
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from sts_combat_rl.commands import t088_canary, t101_particle_convergence
from sts_combat_rl.commands import t103_particle_diagnostic as t103_command
from sts_combat_rl.commands import t104_bridge_localization as t104_command
from sts_combat_rl.sim.t103_particle_diagnostic import (
    _canonical_json,
    _write_bytes_new,
    t103_record_shard_ranges,
)
from sts_combat_rl.sim.t106_failure_stages import (
    MANIFEST_SCHEMA,
    NATIVE_IDENTITY,
    REPORT_SCHEMA,
    ROW_SCHEMA,
    T106IncompleteError,
    T106NativeRecordRunner,
    aggregate,
    select_t104_part_b,
)

T104_PRODUCER = "90cbe6c5020f2fb360503e7731c9a892afc6447a"
T104_SHA = {
    "rows": "3232719325d790dcc84f7e91f907d12b56da37c7557edc8848a5f38fe530dd41",
    "report": "d59e5c9c09dd780a522b018be045dc0656d1e0fe4f78f6406a204684a54ef0ff",
    "manifest": "e1d380177f3f68484809b6bac99f7d3477c3ad29e16229f08e70aa46d52da7ba",
    "execution": "b3d1e3d4b0e0e753614c0d38eecb8b35e05a844ea09559f5d3bc3b4413df5295",
}
_RUNNER: T106NativeRecordRunner | None = None
_STOP: object | None = None


def load_t104(
    rows_path: Path, report_path: Path, manifest_path: Path, execution_path: Path
) -> tuple[list[dict], dict]:
    paths = {
        "rows": rows_path,
        "report": report_path,
        "manifest": manifest_path,
        "execution": execution_path,
    }
    for role, path in paths.items():
        if t103_command._sha256_file(path) != T104_SHA[role]:
            raise T106IncompleteError(f"accepted T104 {role} hash mismatch")
    docs = {
        role: t103_command._read_json(path, label=f"T104 {role}")
        for role, path in paths.items()
    }
    manifest = docs["manifest"]
    provenance = manifest.get("producer_provenance")
    refs = manifest.get("artifact_references")
    if (
        manifest.get("schema_id") != "t104-localization-retention-manifest-v1"
        or manifest.get("task_id") != "T104"
        or manifest.get("terminal_classification") != "NATIVE_OBSERVABILITY_REQUIRED"
        or not isinstance(provenance, Mapping)
        or provenance.get("implementation_head") != T104_PRODUCER
        or provenance.get("current_native_identity", {}).get("commit")
        != "97f59b620efe5ee1571f8da298c99d1e21c1149b"
        or not isinstance(refs, Mapping)
    ):
        raise T106IncompleteError("T104 manifest producer or schema mismatch")
    for role, ref_name, schema in (
        ("rows", "candidate_localization", "t104-bridge-localization-rows-v1"),
        ("report", "aggregate_report", "t104-bridge-localization-report-v1"),
    ):
        ref = refs.get(ref_name)
        if (
            not isinstance(ref, Mapping)
            or ref.get("schema_id") != schema
            or ref.get("sha256") != T104_SHA[role]
            or ref.get("size_bytes") != paths[role].stat().st_size
            or Path(ref.get("path", "")).resolve() != paths[role].resolve()
            or docs[role].get("schema_id") != schema
            or docs[role].get("task_id") != "T104"
        ):
            raise T106IncompleteError(f"T104 {role} reference mismatch")
    report = docs["report"]
    execution = docs["execution"]
    if (
        report.get("terminal_classification") != "NATIVE_OBSERVABILITY_REQUIRED"
        or execution.get("state") != "SUCCEEDED"
        or execution.get("exit_code") != 0
    ):
        raise T106IncompleteError("T104 execution/report terminal mismatch")
    rows = docs["rows"].get("rows")
    selected = select_t104_part_b(rows)
    for ordinal, row in enumerate(rows):
        row["t104_row_ordinal"] = ordinal
    return selected, {
        "producer": T104_PRODUCER,
        "historical_native_identity": provenance["current_native_identity"],
        "hashes": T104_SHA,
        "paths": {role: str(path.resolve()) for role, path in paths.items()},
        "historical_t101_bindings": provenance["historical_t101_bindings"],
    }


def _native_source_qualified() -> None:
    manifest_path = (
        Path(__file__).resolve().parents[3]
        / "docs"
        / "sts_lightspeed_source_manifest.json"
    )
    native = t103_command._read_json(manifest_path, label="canonical native source")
    integration = native.get("integration")
    if (
        native.get("schema_id") != "sts-lightspeed-source-manifest-v1"
        or not isinstance(integration, Mapping)
        or integration.get("repository_url")
        != "https://github.com/lsmfttb/sts_lightspeed.git"
        or integration.get("ref") != NATIVE_IDENTITY["ref"]
        or integration.get("commit") != NATIVE_IDENTITY["commit"]
    ):
        raise T106IncompleteError("current native source is not the T105 pin")
    t105_doc = (
        Path(__file__).resolve().parents[3]
        / "docs"
        / "tasks"
        / "support"
        / "T105"
        / "maintainer-execution.md"
    )
    contents = t105_doc.read_text(encoding="utf-8")
    if (
        NATIVE_IDENTITY["commit"] not in contents
        or "NATIVE_PARTICLE_SEARCH_STAGE_OBSERVABILITY_ACCEPTED" not in contents
    ):
        raise T106IncompleteError("T105 source acceptance evidence is unavailable")


def _readiness_qualified(
    path: Path | None, implementation_head: str, worker_count: int
) -> None:
    if path is None:
        raise T106IncompleteError(
            "full 343-row execution requires separate Maintainer readiness"
        )
    approval = t103_command._read_json(path, label="T106 Maintainer readiness")
    repository_root = Path(__file__).resolve().parents[3]
    actual_head = subprocess.run(
        ["git", "-C", str(repository_root), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    plan = approval.get("resource_plan")
    if (
        approval.get("task_id") != "T106"
        or approval.get("implementation_head") != implementation_head
        or actual_head != implementation_head
        or approval.get("full_execution_authorized") is not True
        or approval.get("worker_count") != worker_count
        or not isinstance(approval.get("approval_comment_url"), str)
        or "github.com/lsmfttb/STSRL/pull/122#issuecomment-"
        not in approval["approval_comment_url"]
        or not isinstance(plan, Mapping)
        or plan.get("supervision") != "detached_resource_guard"
        or plan.get("summed_rss_limit_mib") != 16384
        or plan.get("mem_available_floor_mib") != 8192
        or plan.get("sample_interval_s") != 1
        or not isinstance(plan.get("status_path"), str)
        or not plan["status_path"]
    ):
        raise T106IncompleteError(
            "full execution readiness does not bind this head and resource plan"
        )


def _initialize_worker(runner: T106NativeRecordRunner, stop_event: object) -> None:
    global _RUNNER, _STOP
    _RUNNER, _STOP = runner, stop_event


def _run_shard(
    jobs: list[tuple[dict, dict]], shard: dict, concurrency: int
) -> list[dict]:
    import resource  # WSL/Linux only

    if _RUNNER is None:
        raise T106IncompleteError("worker restore inputs unavailable")
    rows = []
    for source, accepted in jobs:
        if _STOP is not None and _STOP.is_set():
            break
        row = _RUNNER.diagnose(source, accepted)
        row["execution"] = {
            "worker_pid": os.getpid(),
            "configured_concurrency": concurrency,
            "worker_peak_rss_mib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
            / 1024,
            "shard": shard,
            "failure_retry_status": "no_retry",
        }
        rows.append(row)
        if row["baseline_contradiction"] or row["telemetry_contract_violation"]:
            if _STOP is not None:
                _STOP.set()
            break
    return rows


def _write_outputs(
    root: Path, rows: list[dict], report: dict, provenance: dict, command: str
) -> dict:
    root = root.resolve()
    root.mkdir(parents=True, exist_ok=True)
    names = (
        "t106-candidate-stages.json",
        "t106-aggregate-report.json",
        "t106-execution-record.json",
        "t106-retention-manifest.json",
    )
    paths = [root / name for name in names]
    if any(path.exists() for path in paths):
        raise T106IncompleteError("refusing to overwrite retained T106 evidence")
    execution = report.pop("execution")
    documents = (
        (
            "candidate_stages",
            {"schema_id": ROW_SCHEMA, "task_id": "T106", "rows": rows},
            ROW_SCHEMA,
        ),
        ("aggregate_report", report, REPORT_SCHEMA),
        ("execution_record", execution, "t106-execution-record-v1"),
    )
    refs = {}
    for path, (role, document, schema) in zip(paths[:3], documents, strict=True):
        refs[role] = _write_bytes_new(path, _canonical_json(document) + b"\n", schema)
    manifest = {
        "schema_id": MANIFEST_SCHEMA,
        "task_id": "T106",
        "terminal_classification": report["terminal_classification"],
        "producer_provenance": provenance,
        "artifact_references": refs,
        "regeneration_commands": [command],
        "retention_reason": "T106 frozen 343-row structured failure-stage audit and successor planning only.",
        "raw_deletion_condition": "Delete after T106 audit and successor observability consumers close.",
    }
    refs["retention_manifest"] = _write_bytes_new(
        paths[3], _canonical_json(manifest) + b"\n", MANIFEST_SCHEMA
    )
    return refs


def run_from_paths(args: argparse.Namespace) -> dict:
    if len(args.implementation_head) != 40 or any(
        c not in "0123456789abcdef" for c in args.implementation_head
    ):
        raise T106IncompleteError("implementation head must be a full SHA-1")
    if args.output_root.resolve().is_relative_to(Path(__file__).resolve().parents[3]):
        raise T106IncompleteError("retained output must be outside disposable worktree")
    selected, retained = load_t104(
        args.t104_rows, args.t104_report, args.t104_manifest, args.t104_execution
    )
    positions = (
        list(range(343))
        if args.candidate_positions is None
        else args.candidate_positions
    )
    if (
        not positions
        or positions != sorted(set(positions))
        or any(p < 0 or p >= 343 for p in positions)
    ):
        raise T106IncompleteError(
            "canary positions must be unique ascending indexes in the frozen Part-B order"
        )
    target, count = t104_command.worker_plan(
        args.worker_count, args.lower_worker_reason, len(positions)
    )
    full = len(positions) == 343
    if full:
        _readiness_qualified(
            args.full_readiness_approval, args.implementation_head, count
        )
    _native_source_qualified()
    if t103_command._sha256_file(args.native_binary) != args.native_binary_sha256:
        raise T106IncompleteError(
            "native binary hash differs from supplied verified build"
        )
    module = importlib.util.find_spec("slaythespire")
    if (
        module is None
        or module.origin is None
        or Path(module.origin).resolve() != args.native_binary.resolve()
    ):
        raise T106IncompleteError("loaded native module differs from verified build")
    started = time.perf_counter()
    _, _admission, cohort, historical, old_native = (
        t103_command._load_t101_terminal_inputs(args.t101_retention_manifest)
    )
    if (
        old_native != retained["historical_native_identity"]
        or historical != retained["historical_t101_bindings"]
    ):
        raise T106IncompleteError("T101 historical source identity changed")
    accepted_t103, t103_retained = t104_command.load_accepted_t103(
        args.t103_retention_manifest, args.t103_execution_record
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
    sources = t103_command._source_records(
        t088_canary._project_t087_cohort(
            formal, gate.source_selection_manifest_identity, maps
        ),
        cohort["attempted"],
    )
    attempts = cohort["attempted"]
    old_rows = [accepted_t103[r["t104_row_ordinal"]] for r in selected]
    for t104, t103 in zip(selected, old_rows, strict=True):
        for key in (
            "selection_identity",
            "stratum",
            "source_ordinal",
            "selection_digest",
            "sampler_seed",
        ):
            if t104[key] != t103[key]:
                raise T106IncompleteError(
                    "T104/T103 identity or replicate-0 seed differs"
                )
        attempt = attempts[t104["t104_row_ordinal"]]
        for key in (
            "selection_identity",
            "stratum",
            "source_ordinal",
            "selection_digest",
        ):
            if t104[key] != attempt[key]:
                raise T106IncompleteError("T104/T101 frozen ordering differs")
    selected = [selected[p] for p in positions]
    ids = {r["selection_identity"] for r in selected}
    selected_records = {
        r.selection_identity: r
        for s in ("A", "B", "C")
        for r in gate.cohorts[s]
        if r.selection_identity in ids
    }
    compact_maps = {
        s: {
            r["selection_identity"]: maps[s][r["selection_identity"]]
            for r in selected
            if r["stratum"] == s
        }
        for s in ("A", "B", "C")
    }
    del gate, formal, maps
    gc.collect()
    runner = T106NativeRecordRunner(
        adapter_factory=t101_particle_convergence._default_adapter_factory,
        selected_records=selected_records,
        canonical_records_by_stratum=compact_maps,
        native_identity=NATIVE_IDENTITY,
        historical_bindings=historical,
    )
    loading_wall = time.perf_counter() - started
    jobs = [(dict(sources[r["selection_identity"]]), r) for r in selected]
    ranges = t103_record_shard_ranges(len(jobs), count)
    if threading.active_count() != 1 or "slaythespire" in sys.modules:
        raise T106IncompleteError(
            "fork must precede parent native initialization and thread setup"
        )
    replay_started = time.perf_counter()
    context = multiprocessing.get_context("fork")
    stop = context.Event()
    with ProcessPoolExecutor(
        max_workers=count,
        mp_context=context,
        initializer=_initialize_worker,
        initargs=(runner, stop),
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
    report = aggregate(rows, full=full)
    report["execution"] = {
        "schema_id": "t106-execution-record-v1",
        "task_id": "T106",
        "candidate_positions": positions,
        "worker_target": target,
        "configured_worker_count": count,
        "effective_worker_count": len({r["execution"]["worker_pid"] for r in rows}),
        "observed_worker_pids": sorted({r["execution"]["worker_pid"] for r in rows}),
        "record_shard_ranges": ranges,
        "worker_reduction_reason": args.lower_worker_reason,
        "topology": "linux_fork_selected_restore_maps_copy_on_write",
        "input_loading_wall_clock_time_s": loading_wall,
        "replay_wall_clock_time_s": replay_wall,
        "native_bridge_gil_released": False,
        "full_readiness_approval": str(args.full_readiness_approval.resolve())
        if full
        else None,
    }
    command = shlex.join(
        [
            sys.executable,
            "-m",
            "sts_combat_rl.commands.t106_failure_stages",
            *sys.argv[1:],
        ]
    )
    refs = _write_outputs(
        args.output_root,
        rows,
        report,
        {
            "implementation_head": args.implementation_head,
            "current_native_identity": NATIVE_IDENTITY,
            "historical_t104": retained,
            "accepted_t103": t103_retained,
            "historical_t101_bindings": historical,
            "native_binary": {
                "path": str(args.native_binary.resolve()),
                "sha256": args.native_binary_sha256,
                "python_executable": sys.executable,
                "python_version": sys.version,
            },
        },
        command,
    )
    return {"report": report, "artifacts": refs}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--implementation-head", required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    for name in (
        "t104-rows",
        "t104-report",
        "t104-manifest",
        "t104-execution",
        "t103-retention-manifest",
        "t103-execution-record",
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
        "native-binary",
    ):
        parser.add_argument(f"--{name}", type=Path, required=True)
    parser.add_argument("--native-binary-sha256", required=True)
    parser.add_argument("--worker-count", type=int)
    parser.add_argument("--lower-worker-reason")
    parser.add_argument("--candidate-positions", type=int, nargs="+")
    parser.add_argument("--full-readiness-approval", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = run_from_paths(args)
    except (OSError, ValueError, TypeError, KeyError, IndexError, RuntimeError) as exc:
        print(
            f"T106 qualification/execution incomplete: {type(exc).__name__}",
            file=sys.stderr,
        )
        print(json.dumps({"task_id": "T106", "terminal_classification": "INCOMPLETE"}))
        return 2
    print(json.dumps(result, sort_keys=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
