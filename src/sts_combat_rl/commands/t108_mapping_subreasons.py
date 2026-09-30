"""T108 exact-323 mapping-subreason replay; execution requires exact-head readiness."""

from __future__ import annotations

import argparse
import gc
import hashlib
import importlib.util
import json
import multiprocessing
import os
import shlex
import subprocess
import sys
import threading
import time
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any

from sts_combat_rl.commands import t088_canary, t101_particle_convergence
from sts_combat_rl.commands import t103_particle_diagnostic as t103_command
from sts_combat_rl.commands import t104_bridge_localization as t104_command
from sts_combat_rl.sim.t103_particle_diagnostic import (
    _canonical_json,
    _write_bytes_new,
    t103_record_shard_ranges,
)
from sts_combat_rl.sim.t108_mapping_subreasons import (
    MANIFEST_SCHEMA,
    NATIVE_IDENTITY,
    REPORT_SCHEMA,
    ROW_SCHEMA,
    T106_EXECUTION_SCHEMA,
    T106_IMPLEMENTATION_HEAD,
    T106_MANIFEST_SCHEMA,
    T106_NATIVE_IDENTITY,
    T106_REPORT_SCHEMA,
    T106_ROW_SCHEMA,
    T106_SHA256,
    T108IncompleteError,
    T108NativeRecordRunner,
    aggregate_t108,
    ordered_identity_digest,
    select_t106_root_mapping_failures,
)

T106_PRODUCER = T106_IMPLEMENTATION_HEAD
T106_REFERENCE_KEYS = {
    "rows": ("candidate_stages", T106_ROW_SCHEMA),
    "report": ("aggregate_report", T106_REPORT_SCHEMA),
    "execution": ("execution_record", T106_EXECUTION_SCHEMA),
}
_RUNNER: T108NativeRecordRunner | None = None
_STOP: object | None = None


def _read_json(path: Path, label: str) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise T108IncompleteError(f"{label} must be a JSON object")
    return value


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _verify_reference(
    manifest: dict[str, Any],
    *,
    role: str,
    path: Path,
    document: dict[str, Any],
) -> None:
    reference_name, schema = T106_REFERENCE_KEYS[role]
    references = manifest.get("artifact_references")
    reference = references.get(reference_name) if isinstance(references, dict) else None
    expected_path = path.resolve()
    if (
        not isinstance(reference, dict)
        or reference.get("schema_id") != schema
        or reference.get("sha256") != T106_SHA256[role]
        or reference.get("size_bytes") != path.stat().st_size
        or Path(reference.get("path", "")).resolve() != expected_path
        or document.get("schema_id") != schema
        or document.get("task_id") != "T106"
    ):
        raise T108IncompleteError(f"accepted T106 {role} reference mismatch")


def _validate_t106_report(report: dict[str, Any]) -> None:
    if (
        report.get("schema_id") != T106_REPORT_SCHEMA
        or report.get("task_id") != "T106"
        or report.get("terminal_classification")
        != "PARTICLE_SEARCH_FAILURE_STAGE_CENSUS_ESTABLISHED"
        or report.get("selected_count") != 343
        or report.get("replayed_count") != 343
        or report.get("replayed_failures_with_valid_telemetry") != 343
        or report.get("baseline_contradiction_count") != 0
        or report.get("telemetry_contract_violation_count") != 0
    ):
        raise T108IncompleteError("accepted T106 aggregate terminal is invalid")
    classes = report.get("stage_classes")
    if not isinstance(classes, dict):
        raise T108IncompleteError("accepted T106 stage-class counts are missing")
    expected_classes = {
        "ROOT_OCCURRENCE_MAPPING_FAILURE": 323,
        "PUBLIC_FIDELITY_VALIDATION_FAILURE": 20,
    }
    for name, expected in expected_classes.items():
        record = classes.get(name)
        if not isinstance(record, dict) or record.get("count") != expected:
            raise T108IncompleteError("accepted T106 stage-class counts disagree")
    for stratum, expected in {"A": (84, 5), "B": (174, 15), "C": (65, 0)}.items():
        by_stratum = report.get("by_stratum", {}).get(stratum)
        if not isinstance(by_stratum, dict):
            raise T108IncompleteError("accepted T106 stratum counts are missing")
        root_count = by_stratum.get("ROOT_OCCURRENCE_MAPPING_FAILURE", {}).get("count")
        fidelity_count = by_stratum.get("PUBLIC_FIDELITY_VALIDATION_FAILURE", {}).get(
            "count"
        )
        if (root_count, fidelity_count) != expected:
            raise T108IncompleteError("accepted T106 A/B/C counts disagree")


def load_t106_inputs(
    *,
    rows_path: Path,
    report_path: Path,
    execution_path: Path,
    manifest_path: Path,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Hash/provenance qualify T106, then return its exact ordered 323 rows."""

    paths = {
        "rows": rows_path,
        "report": report_path,
        "execution": execution_path,
        "manifest": manifest_path,
    }
    for role, path in paths.items():
        if not path.is_file() or _sha256(path) != T106_SHA256[role]:
            raise T108IncompleteError(f"accepted T106 {role} hash mismatch")
    documents = {role: _read_json(path, f"T106 {role}") for role, path in paths.items()}
    manifest = documents["manifest"]
    provenance = manifest.get("producer_provenance")
    if (
        manifest.get("schema_id") != T106_MANIFEST_SCHEMA
        or manifest.get("task_id") != "T106"
        or manifest.get("terminal_classification")
        != "PARTICLE_SEARCH_FAILURE_STAGE_CENSUS_ESTABLISHED"
        or not isinstance(provenance, dict)
        or provenance.get("implementation_head") != T106_PRODUCER
        or provenance.get("current_native_identity") != T106_NATIVE_IDENTITY
    ):
        raise T108IncompleteError("accepted T106 producer/schema provenance mismatch")
    for role in ("rows", "report", "execution"):
        _verify_reference(
            manifest,
            role=role,
            path=paths[role],
            document=documents[role],
        )
    execution = documents["execution"]
    if (
        execution.get("schema_id") != T106_EXECUTION_SCHEMA
        or execution.get("task_id") != "T106"
        or execution.get("candidate_positions") != list(range(343))
    ):
        raise T108IncompleteError("accepted T106 execution coverage is not full")
    _validate_t106_report(documents["report"])
    rows_document = documents["rows"]
    if (
        rows_document.get("schema_id") != T106_ROW_SCHEMA
        or rows_document.get("task_id") != "T106"
    ):
        raise T108IncompleteError("accepted T106 rows schema mismatch")
    rows = rows_document.get("rows")
    selected = select_t106_root_mapping_failures(rows)
    if len(selected) != 323:
        raise T108IncompleteError("T106 filter did not preserve the exact 323 rows")
    return selected, {
        "schema_id": T106_MANIFEST_SCHEMA,
        "producer": T106_PRODUCER,
        "current_native_identity": provenance["current_native_identity"],
        "historical_t101_bindings": provenance.get("historical_t101_bindings"),
        "producer_provenance": provenance,
        "paths": {role: str(path.resolve()) for role, path in paths.items()},
        "sha256": dict(T106_SHA256),
        "selected_count": 323,
        "selected_by_stratum": dict(Counter(row["stratum"] for row in selected)),
        "ordered_identity_digest": ordered_identity_digest(selected),
    }


def _path_from_retained_reference(reference: object, label: str) -> Path:
    if not isinstance(reference, dict) or not isinstance(reference.get("path"), str):
        raise T108IncompleteError(f"T106 retained {label} path is unavailable")
    path = Path(reference["path"])
    if not path.is_file():
        raise T108IncompleteError(f"T106 retained {label} artifact is unavailable")
    return path


def _source_inputs_from_t106_provenance(
    producer_provenance: dict[str, Any],
) -> dict[str, Path]:
    """Resolve replay inputs only through artifacts bound by the T106 manifest."""

    historical = producer_provenance.get("historical_t101_bindings")
    t101_artifacts = (
        historical.get("accepted_t101_source_artifacts")
        if isinstance(historical, dict)
        else None
    )
    accepted_t103 = producer_provenance.get("accepted_t103")
    if not isinstance(t101_artifacts, dict) or not isinstance(accepted_t103, dict):
        raise T108IncompleteError("T106 transitive T101/T103 bindings are unavailable")
    t103_manifest = accepted_t103.get("manifest")
    t103_references = (
        t103_manifest.get("artifact_references")
        if isinstance(t103_manifest, dict)
        else None
    )
    candidate_reference = (
        t103_references.get("candidate_diagnostics")
        if isinstance(t103_references, dict)
        else None
    )
    if not isinstance(candidate_reference, dict) or not isinstance(
        candidate_reference.get("path"), str
    ):
        raise T108IncompleteError("T106 accepted T103 artifact paths are unavailable")
    t103_root = Path(candidate_reference["path"]).parent
    t103_manifest_path = t103_root / "t103-retention-manifest.json"
    if not t103_manifest_path.is_file() or _sha256(
        t103_manifest_path
    ) != accepted_t103.get("manifest_sha256"):
        raise T108IncompleteError("T106-bound T103 retention manifest is unavailable")
    execution_reference = accepted_t103.get("execution_reference")
    t103_execution_path = _path_from_retained_reference(
        execution_reference, "T103 execution"
    )
    if not isinstance(execution_reference, dict) or _sha256(
        t103_execution_path
    ) != execution_reference.get("sha256"):
        raise T108IncompleteError("T106-bound T103 execution record hash mismatch")

    b_pool = _path_from_retained_reference(
        t101_artifacts.get("t085_canonical_b"), "T085 B pool"
    )
    c_pool = _path_from_retained_reference(
        t101_artifacts.get("t085_canonical_c"), "T085 C pool"
    )
    resolved = {
        "t101_retention_manifest": _path_from_retained_reference(
            t101_artifacts.get("t101_terminal_retention_manifest"),
            "T101 terminal retention manifest",
        ),
        "t103_retention_manifest": t103_manifest_path,
        "t103_execution_record": t103_execution_path,
        "t087_formal": _path_from_retained_reference(
            t101_artifacts.get("t087_formal"), "T087 formal evidence"
        ),
        "t087_report": _path_from_retained_reference(
            t101_artifacts.get("t087_report"), "T087 report"
        ),
        "t087_retention": _path_from_retained_reference(
            t101_artifacts.get("t087_retention"), "T087 retention manifest"
        ),
        "t085_selection": _path_from_retained_reference(
            t101_artifacts.get("t085_selection"), "T085 selection"
        ),
        "t085_restore": _path_from_retained_reference(
            t101_artifacts.get("t085_restore"), "T085 restore evidence"
        ),
        "a_pool": _path_from_retained_reference(
            t101_artifacts.get("t085_canonical_a"), "T085 A pool"
        ),
        "b_pool": b_pool,
        "c_pool": c_pool,
        "b_source_manifest": b_pool.parent / "cohort-b-source-manifest.json",
        "c_source_manifest": c_pool.parent / "cohort-c-source-manifest.json",
    }
    if (
        not resolved["b_source_manifest"].is_file()
        or not resolved["c_source_manifest"].is_file()
    ):
        raise T108IncompleteError("T106-bound T085 source manifests are unavailable")
    return resolved


def qualify_inputs_from_paths(args: argparse.Namespace) -> dict[str, Any]:
    """Read-only, non-simulator qualification used before readiness review."""

    selected, provenance = load_t106_inputs(
        rows_path=args.t106_rows,
        report_path=args.t106_report,
        execution_path=args.t106_execution,
        manifest_path=args.t106_manifest,
    )
    native = _native_source_qualified()
    return {
        "task_id": "T108",
        "qualification": "EXACT_T106_323_INPUTS_QUALIFIED",
        "simulator_started": False,
        "selected_count": len(selected),
        "selected_by_stratum": provenance["selected_by_stratum"],
        "ordered_identity_digest": provenance["ordered_identity_digest"],
        "t106_artifact_sha256": provenance["sha256"],
        "t106_producer": provenance["producer"],
        "current_native_identity": native,
    }


def _native_source_qualified() -> dict[str, str]:
    repository_root = Path(__file__).resolve().parents[3]
    manifest = _read_json(
        repository_root / "docs" / "sts_lightspeed_source_manifest.json",
        "canonical native source manifest",
    )
    integration = manifest.get("integration")
    if (
        manifest.get("schema_id") != "sts-lightspeed-source-manifest-v1"
        or not isinstance(integration, dict)
        or integration.get("repository_url")
        != "https://github.com/lsmfttb/sts_lightspeed.git"
        or integration.get("ref") != NATIVE_IDENTITY["ref"]
        or integration.get("commit") != NATIVE_IDENTITY["commit"]
    ):
        raise T108IncompleteError("current native source is not the accepted T107 pin")
    capabilities = manifest.get("supported_native_capabilities")
    capability = next(
        (
            item
            for item in capabilities or []
            if isinstance(item, dict)
            and item.get("id") == "native_stsr008_root_occurrence_mapping_observability"
        ),
        None,
    )
    if (
        not isinstance(capability, dict)
        or "T107" not in capability.get("task_provenance", [])
        or "StepSimulator.last_particle_search_stage_diagnostics.particles.root_occurrence_mapping_diagnostic"
        not in capability.get("required_python_api", [])
    ):
        raise T108IncompleteError("T107 mapping observability capability is not pinned")
    task_contract = (
        repository_root
        / "docs"
        / "tasks"
        / "T107-native-root-mapping-observability-source-acceptance.md"
    )
    execution_evidence = (
        repository_root
        / "docs"
        / "tasks"
        / "support"
        / "T107"
        / "maintainer-execution.md"
    )
    contract_text = task_contract.read_text(encoding="utf-8")
    evidence_text = execution_evidence.read_text(encoding="utf-8")
    if any(
        value not in contract_text
        for value in (
            NATIVE_IDENTITY["commit"],
            "NATIVE_ROOT_OCCURRENCE_MAPPING_OBSERVABILITY_ACCEPTED",
            "native-root-occurrence-mapping-diagnostic-v1",
        )
    ) or any(
        value not in evidence_text
        for value in (
            NATIVE_IDENTITY["commit"],
            "NATIVE_ROOT_OCCURRENCE_MAPPING_OBSERVABILITY_ACCEPTED",
            "STSRL-008",
            "diagnostic schema",
        )
    ):
        raise T108IncompleteError("T107 source-acceptance evidence is unavailable")
    return dict(NATIVE_IDENTITY)


def _readiness_qualified(
    *,
    path: Path | None,
    implementation_head: str,
    positions: list[int],
    full: bool,
    worker_count: int,
    native_binary: Path,
    native_binary_sha256: str,
    resource_status_path: Path,
) -> dict[str, Any]:
    if path is None:
        raise T108IncompleteError(
            "T108 simulator replay requires separate exact-head Maintainer readiness"
        )
    approval = _read_json(path, "T108 Maintainer readiness")
    repository_root = Path(__file__).resolve().parents[3]
    actual_head = subprocess.run(
        ["git", "-C", str(repository_root), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    worktree_status = subprocess.run(
        [
            "git",
            "-C",
            str(repository_root),
            "status",
            "--porcelain=v1",
            "--untracked-files=all",
        ],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    plan = approval.get("resource_plan")
    approved_binary = approval.get("native_binary")
    expected_scope = "full_population" if full else "bounded_canary"
    approved_status_path = (
        Path(plan["status_path"])
        if isinstance(plan, dict) and isinstance(plan.get("status_path"), str)
        else None
    )
    if (
        approval.get("task_id") != "T108"
        or approval.get("implementation_head") != implementation_head
        or actual_head != implementation_head
        or bool(worktree_status)
        or approval.get("execution_authorized") is not True
        or approval.get("execution_scope") != expected_scope
        or approval.get("candidate_positions") != positions
        or (full and approval.get("full_population_authorized") is not True)
        or approval.get("worker_count") != worker_count
        or not isinstance(approval.get("approval_comment_url"), str)
        or "github.com/lsmfttb/STSRL/pull/126#issuecomment-"
        not in approval["approval_comment_url"]
        or not isinstance(approved_binary, dict)
        or approved_binary.get("path") != str(native_binary.resolve())
        or approved_binary.get("sha256") != native_binary_sha256
        or approved_binary.get("source_commit") != NATIVE_IDENTITY["commit"]
        or not isinstance(plan, dict)
        or plan.get("supervision") != "detached_resource_guard"
        or plan.get("summed_rss_limit_mib") != 16384
        or plan.get("mem_available_floor_mib") != 8192
        or plan.get("sample_interval_s") != 1
        or not isinstance(plan.get("status_path"), str)
        or not plan["status_path"]
        or not resource_status_path.is_absolute()
        or approved_status_path is None
        or not approved_status_path.is_absolute()
        or approved_status_path != resource_status_path
        or approved_status_path.resolve() != resource_status_path.resolve()
    ):
        raise T108IncompleteError(
            "T108 readiness does not bind the clean exact head, selection, binary, and resource plan"
        )
    return {
        "path": str(path.resolve()),
        "sha256": _sha256(path),
        "approval_comment_url": approval["approval_comment_url"],
        "resource_status_path": str(resource_status_path),
        "resource_plan": plan,
    }


def _initialize_worker(runner: T108NativeRecordRunner, stop_event: object) -> None:
    global _RUNNER, _STOP
    _RUNNER, _STOP = runner, stop_event


def _run_shard(
    jobs: list[tuple[dict[str, Any], dict[str, Any]]],
    shard: dict[str, Any],
    concurrency: int,
) -> list[dict[str, Any]]:
    import resource  # WSL/Linux execution only

    if _RUNNER is None:
        raise T108IncompleteError("worker restore/source inputs unavailable")
    output = []
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
        output.append(row)
        if (
            row["baseline_contradiction"]
            or row["parent_stage_contract_violation"]
            or row["mapping_telemetry_contract_violation"]
        ):
            if _STOP is not None:
                _STOP.set()
            break
    return output


def _write_outputs(
    *,
    root: Path,
    rows: list[dict[str, Any]],
    report: dict[str, Any],
    execution: dict[str, Any],
    provenance: dict[str, Any],
    command: str,
) -> dict[str, Any]:
    root = root.resolve()
    repository_root = Path(__file__).resolve().parents[3]
    if root.is_relative_to(repository_root):
        raise T108IncompleteError(
            "retained output must be outside the disposable worktree"
        )
    root.mkdir(parents=True, exist_ok=True)
    names = (
        "t108-candidate-mapping-subreasons.json",
        "t108-aggregate-report.json",
        "t108-execution-record.json",
        "t108-retention-manifest.json",
    )
    paths = [root / name for name in names]
    if any(path.exists() for path in paths):
        raise T108IncompleteError("refusing to overwrite retained T108 evidence")
    documents = (
        (
            "candidate_rows",
            {"schema_id": ROW_SCHEMA, "task_id": "T108", "rows": rows},
            ROW_SCHEMA,
        ),
        ("aggregate_report", report, REPORT_SCHEMA),
        ("execution_record", execution, "t108-execution-record-v1"),
    )
    references = {}
    for path, (role, document, schema) in zip(paths[:3], documents, strict=True):
        references[role] = _write_bytes_new(
            path, _canonical_json(document) + b"\n", schema
        )
    manifest = {
        "schema_id": MANIFEST_SCHEMA,
        "task_id": "T108",
        "terminal_classification": report["terminal_classification"],
        "producer_provenance": provenance,
        "artifact_references": references,
        "regeneration_commands": [command],
        "retention_reason": "Exact accepted T106 323-row mapping-subreason diagnostic and successor planning only.",
        "raw_deletion_condition": "Retain until T108 audit and successor observability consumers close.",
    }
    references["retention_manifest"] = _write_bytes_new(
        paths[3], _canonical_json(manifest) + b"\n", MANIFEST_SCHEMA
    )
    return references


def run_from_paths(args: argparse.Namespace) -> dict[str, Any]:
    if len(args.implementation_head) != 40 or any(
        character not in "0123456789abcdef" for character in args.implementation_head
    ):
        raise T108IncompleteError("implementation head must be a full SHA-1")
    selected, t106_provenance = load_t106_inputs(
        rows_path=args.t106_rows,
        report_path=args.t106_report,
        execution_path=args.t106_execution,
        manifest_path=args.t106_manifest,
    )
    positions = (
        list(range(323))
        if args.candidate_positions is None
        else args.candidate_positions
    )
    if (
        not positions
        or positions != sorted(set(positions))
        or any(position < 0 or position >= 323 for position in positions)
    ):
        raise T108IncompleteError(
            "candidate positions must be ascending indexes in exact T106 order"
        )
    full = len(positions) == 323
    native_identity = _native_source_qualified()
    if t103_command._sha256_file(args.native_binary) != args.native_binary_sha256:
        raise T108IncompleteError(
            "native binary hash differs from supplied verified build"
        )
    module = importlib.util.find_spec("slaythespire")
    if (
        module is None
        or module.origin is None
        or Path(module.origin).resolve() != args.native_binary.resolve()
    ):
        raise T108IncompleteError(
            "loaded native module differs from verified T107 build"
        )

    target, worker_count = t104_command.worker_plan(
        args.worker_count, args.lower_worker_reason, len(positions)
    )
    readiness = _readiness_qualified(
        path=args.readiness_approval,
        implementation_head=args.implementation_head,
        positions=positions,
        full=full,
        worker_count=worker_count,
        native_binary=args.native_binary,
        native_binary_sha256=args.native_binary_sha256,
        resource_status_path=args.resource_status_path,
    )

    started = time.perf_counter()
    source_inputs = _source_inputs_from_t106_provenance(
        t106_provenance["producer_provenance"]
    )
    _, _admission, cohort, historical_t101, old_native = (
        t103_command._load_t101_terminal_inputs(
            source_inputs["t101_retention_manifest"]
        )
    )
    if (
        old_native
        != t106_provenance["historical_t101_bindings"]["historical_native_identity"]
        or historical_t101 != t106_provenance["historical_t101_bindings"]
    ):
        raise T108IncompleteError(
            "T101 historical source binding differs from accepted T106"
        )
    accepted_t103, t103_provenance = t104_command.load_accepted_t103(
        source_inputs["t103_retention_manifest"],
        source_inputs["t103_execution_record"],
    )
    formal, gate, _ = t088_canary._admit_t088_canary_inputs_from_paths(
        implementation_head=args.implementation_head,
        **{
            f"{name}_path": source_inputs[name]
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
    attempts_by_identity = {
        row["selection_identity"]: row for row in cohort["attempted"]
    }
    for row in selected:
        accepted_t104_ordinal = row["accepted_t104_row_ordinal"]
        accepted_t103_row = accepted_t103[accepted_t104_ordinal]
        attempt = attempts_by_identity.get(row["selection_identity"])
        if attempt is None:
            raise T108IncompleteError("accepted T101 source identity is unavailable")
        for field in (
            "selection_identity",
            "stratum",
            "source_ordinal",
            "selection_digest",
            "sampler_seed",
        ):
            expected_value = (
                row["sampler_seed"] if field == "sampler_seed" else row[field]
            )
            if accepted_t103_row.get(field) != expected_value:
                raise T108IncompleteError(
                    "T106/T103 identity or replicate-0 seed differs"
                )
            if field != "sampler_seed" and attempt.get(field) != expected_value:
                raise T108IncompleteError("T106/T101 source order differs")
    chosen = [selected[position] for position in positions]
    identities = {row["selection_identity"] for row in chosen}
    selected_records = {
        record.selection_identity: record
        for stratum in ("A", "B", "C")
        for record in gate.cohorts[stratum]
        if record.selection_identity in identities
    }
    compact_maps = {
        stratum: {
            record["selection_identity"]: maps[stratum][record["selection_identity"]]
            for record in chosen
            if record["stratum"] == stratum
        }
        for stratum in ("A", "B", "C")
    }
    del gate, formal, maps
    gc.collect()
    runner = T108NativeRecordRunner(
        adapter_factory=t101_particle_convergence._default_adapter_factory,
        selected_records=selected_records,
        canonical_records_by_stratum=compact_maps,
        native_identity=native_identity,
        historical_bindings=historical_t101,
    )
    input_loading_wall = time.perf_counter() - started
    jobs = [(dict(sources[row["selection_identity"]]), row) for row in chosen]
    ranges = t103_record_shard_ranges(len(jobs), worker_count)
    if threading.active_count() != 1 or "slaythespire" in sys.modules:
        raise T108IncompleteError(
            "Linux fork must precede parent native initialization and thread setup"
        )
    replay_started = time.perf_counter()
    context = multiprocessing.get_context("fork")
    stop = context.Event()
    with ProcessPoolExecutor(
        max_workers=worker_count,
        mp_context=context,
        initializer=_initialize_worker,
        initargs=(runner, stop),
    ) as pool:
        futures = [
            pool.submit(
                _run_shard,
                jobs[shard["start_ordinal_inclusive"] : shard["end_ordinal_exclusive"]],
                shard,
                worker_count,
            )
            for shard in ranges
        ]
        rows = [row for future in futures for row in future.result()]
    replay_wall = time.perf_counter() - replay_started
    selected_by_stratum = Counter(row["stratum"] for row in chosen)
    report = aggregate_t108(
        rows,
        full=full,
        selected_count=len(chosen),
        expected_by_stratum={
            stratum: selected_by_stratum.get(stratum, 0) for stratum in ("A", "B", "C")
        },
        expected_identities=[row["selection_identity"] for row in chosen],
        expected_identity_digest=ordered_identity_digest(chosen),
    )
    execution = {
        "schema_id": "t108-execution-record-v1",
        "task_id": "T108",
        "candidate_positions": positions,
        "worker_target": target,
        "configured_worker_count": worker_count,
        "effective_worker_count": len({row["execution"]["worker_pid"] for row in rows}),
        "observed_worker_pids": sorted(
            {row["execution"]["worker_pid"] for row in rows}
        ),
        "record_shard_ranges": ranges,
        "worker_reduction_reason": args.lower_worker_reason,
        "topology": "linux_fork_selected_restore_maps_copy_on_write",
        "input_loading_wall_clock_time_s": input_loading_wall,
        "replay_wall_clock_time_s": replay_wall,
        "native_bridge_gil_released": False,
        "readiness_approval": readiness,
        "resource_status_path": readiness["resource_status_path"],
        "native_binary": {
            "path": str(args.native_binary.resolve()),
            "sha256": args.native_binary_sha256,
            "python_executable": sys.executable,
            "python_version": sys.version,
        },
    }
    command = shlex.join(
        [
            sys.executable,
            "-m",
            "sts_combat_rl.commands.t108_mapping_subreasons",
            *sys.argv[1:],
        ]
    )
    artifact_refs = _write_outputs(
        root=args.output_root,
        rows=rows,
        report=report,
        execution=execution,
        provenance={
            "implementation_head": args.implementation_head,
            "current_native_identity": native_identity,
            "accepted_t106": t106_provenance,
            "accepted_t103": t103_provenance,
            "historical_t101_bindings": historical_t101,
            "native_binary_sha256": args.native_binary_sha256,
            "readiness_approval": readiness,
        },
        command=command,
    )
    return {"report": report, "artifacts": artifact_refs}


def _add_t106_arguments(parser: argparse.ArgumentParser) -> None:
    for name in ("t106-rows", "t106-report", "t106-execution", "t106-manifest"):
        parser.add_argument(f"--{name}", type=Path, required=True)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    _add_t106_arguments(parser)
    parser.add_argument("--qualify-t106-inputs-only", action="store_true")
    parser.add_argument("--implementation-head")
    parser.add_argument("--output-root", type=Path)
    for name in ("native-binary",):
        parser.add_argument(f"--{name}", type=Path)
    parser.add_argument("--native-binary-sha256")
    parser.add_argument("--readiness-approval", type=Path)
    parser.add_argument("--resource-status-path", type=Path)
    parser.add_argument("--worker-count", type=int)
    parser.add_argument("--lower-worker-reason")
    parser.add_argument("--candidate-positions", type=int, nargs="+")
    return parser


def _require_replay_arguments(args: argparse.Namespace) -> None:
    required = (
        "implementation_head",
        "output_root",
        "native_binary",
        "native_binary_sha256",
        "resource_status_path",
    )
    missing = [name for name in required if getattr(args, name) is None]
    if missing:
        raise T108IncompleteError(
            "replay arguments are required: " + ", ".join(missing)
        )


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.qualify_t106_inputs_only:
            result = qualify_inputs_from_paths(args)
        else:
            _require_replay_arguments(args)
            result = run_from_paths(args)
    except (
        OSError,
        ValueError,
        TypeError,
        KeyError,
        IndexError,
        AttributeError,
        RuntimeError,
        subprocess.SubprocessError,
    ) as exc:
        print(
            f"T108 qualification/replay incomplete: {type(exc).__name__}",
            file=sys.stderr,
        )
        print(json.dumps({"task_id": "T108", "terminal_classification": "INCOMPLETE"}))
        return 2
    print(json.dumps(result, sort_keys=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
