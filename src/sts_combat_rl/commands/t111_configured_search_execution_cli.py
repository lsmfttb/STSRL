"""Separately authorized T111 N=2 configured-domain execution and finalizer.

The preparation command never imports a native adapter. This command refuses
candidate execution unless an exact-head Maintainer authorization, current
retained-input qualification, exact native binary, and active detached
resource-guard target are all independently verified.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import os
import subprocess
import sys
import time
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path

from sts_combat_rl.commands import (
    t088_canary,
    t103_particle_diagnostic,
)
from sts_combat_rl.commands import (
    t111_configured_search_support as preparation,
)
from sts_combat_rl.commands.t085_native_execution import (
    load_t085_native_evaluation_plan,
)
from sts_combat_rl.commands.t111_configured_search_execution import (
    T111NativeRecordRunner,
)
from sts_combat_rl.sim.t101_particle_convergence import T101_SOURCE_COUNTS
from sts_combat_rl.sim.t111_configured_search_support import (
    T111_NATIVE_COMMIT,
    T111_NATIVE_REF,
    T111ConfiguredSearchError,
    select_t111_configured_search_cohort,
    validate_t111_configured_search_cohort,
)

try:
    import resource
except ImportError:  # pragma: no cover - POSIX-only execution is checked first
    resource = None

T111_EXECUTION_AUTH_SCHEMA = "t111-maintainer-execution-authorization-v1"
T111_EXECUTION_RECORD_SCHEMA = "t111-execution-record-v1"
T111_FINAL_REPORT_SCHEMA = "t111-final-report-v1"
T111_RETENTION_MANIFEST_SCHEMA = "t111-terminal-retention-manifest-v1"
T111_PREP_QUALIFICATION_SCHEMA = preparation.T111_QUALIFICATION_SCHEMA
T111_PREPARATION_SCHEMA = preparation.T111_READINESS_PREPARATION_SCHEMA
_EXPECTED_HEAD_BRANCH = "planner/t111-configured-search-domain-support-reentry"
_EXPECTED_INPUT_ROLES = {
    "t087_formal",
    "t087_report",
    "t087_retention",
    "t085_selection",
    "t085_restore",
    "t085_canonical_a",
    "t085_canonical_b",
    "t085_canonical_c",
    "t088_formal_raw",
    "t088_final_report",
    "t088_retention",
    "native_source_manifest",
}


class T111ExecutionAuthorizationError(ValueError):
    """An execution request is not bound to an exact Maintainer approval."""


def _canonical_json(value: object) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
        + b"\n"
    )


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
        raise T111ExecutionAuthorizationError(f"cannot read {label}") from exc
    if not isinstance(value, Mapping):
        raise T111ExecutionAuthorizationError(f"{label} must be an object")
    return dict(value)


def _write_new_json(path: Path, value: Mapping[str, object]) -> dict[str, object]:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = _canonical_json(value)
    try:
        with path.open("xb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
    except FileExistsError as exc:
        raise T111ExecutionAuthorizationError(
            "refusing to overwrite a retained T111 artifact"
        ) from exc
    return {
        "path": str(path.resolve()),
        "schema_id": value.get("schema_id"),
        "size_bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
    }


def _verify_artifact_reference(
    value: object, *, path: Path | None = None, expected_schema: str
) -> dict[str, object]:
    if not isinstance(value, Mapping):
        raise T111ExecutionAuthorizationError("artifact reference is malformed")
    ref_path = Path(str(value.get("path", "")))
    if path is not None and ref_path.resolve() != path.resolve():
        raise T111ExecutionAuthorizationError(
            "artifact path differs from authorization"
        )
    try:
        stat = ref_path.stat()
        observed_sha = _sha256_file(ref_path)
    except OSError as exc:
        raise T111ExecutionAuthorizationError("bound artifact is unavailable") from exc
    if (
        value.get("schema_id") != expected_schema
        or stat.st_size != value.get("size_bytes")
        or observed_sha != value.get("sha256")
    ):
        raise T111ExecutionAuthorizationError("bound artifact schema/hash changed")
    return {
        "path": str(ref_path.resolve()),
        "schema_id": expected_schema,
        "size_bytes": stat.st_size,
        "sha256": observed_sha,
    }


def _git_state(repo_root: Path) -> tuple[str, str, bool]:
    try:
        head_value = preparation._git_output(repo_root, "rev-parse", "HEAD")
        branch_value = preparation._git_output(repo_root, "branch", "--show-current")
        status_value = preparation._git_output(repo_root, "status", "--porcelain")
        if not all(
            isinstance(value, str) for value in (head_value, branch_value, status_value)
        ):
            raise T111ExecutionAuthorizationError("Git state output is not text")
        head = head_value.strip()
        branch = branch_value.strip()
        dirty = bool(status_value)
    except (
        OSError,
        subprocess.SubprocessError,
        preparation.T111QualificationError,
    ) as exc:
        raise T111ExecutionAuthorizationError(
            "cannot verify exact local Git state"
        ) from exc
    return head, branch, dirty


def _validate_resource_plan(value: object, *, status_path: Path) -> dict[str, object]:
    if not isinstance(value, Mapping):
        raise T111ExecutionAuthorizationError("resource plan is missing")
    worker_count = value.get("effective_worker_count")
    shard_count = value.get("shard_count")
    shard_rows = value.get("shards")
    if (
        isinstance(worker_count, bool)
        or worker_count != 1
        or isinstance(shard_count, bool)
        or shard_count != 1
        or not isinstance(shard_rows, list)
        or len(shard_rows) != 1
        or not isinstance(shard_rows[0], Mapping)
    ):
        raise T111ExecutionAuthorizationError(
            "T111 currently supports only the reviewed single-process serial executor"
        )
    shard = shard_rows[0]
    candidate_range = shard.get("candidate_range")
    stratum_ranges = shard.get("stratum_ranges")
    if (
        shard.get("worker_id") != "worker-0"
        or shard.get("shard_id") != "shard-0"
        or not isinstance(candidate_range, list)
        or len(candidate_range) != 2
        or any(
            isinstance(item, bool) or not isinstance(item, int)
            for item in candidate_range
        )
        or candidate_range != [0, 413]
        or not isinstance(stratum_ranges, Mapping)
        or set(stratum_ranges) != {"A", "B", "C"}
        or any(
            not isinstance(pair, list)
            or len(pair) != 2
            or any(isinstance(item, bool) or not isinstance(item, int) for item in pair)
            for pair in stratum_ranges.values()
        )
        or dict(stratum_ranges) != {"A": [0, 93], "B": [93, 285], "C": [285, 413]}
    ):
        raise T111ExecutionAuthorizationError("T111 shard ranges are not canonical")
    guard = value.get("resource_guard")
    if not isinstance(guard, Mapping):
        raise T111ExecutionAuthorizationError("detached resource guard is missing")
    numeric_positive = (
        "memory_budget_mib",
        "memory_request_mib",
        "runtime_rss_limit_mib",
        "runtime_memavailable_floor_mib",
    )
    for field in numeric_positive:
        item = guard.get(field)
        if isinstance(item, bool) or not isinstance(item, int) or item <= 0:
            raise T111ExecutionAuthorizationError("resource guard threshold is invalid")
    interval = guard.get("runtime_sample_seconds")
    if (
        isinstance(interval, bool)
        or not isinstance(interval, (int, float))
        or not math.isfinite(float(interval))
        or interval <= 0
    ):
        raise T111ExecutionAuthorizationError("resource sample interval is invalid")
    if (
        guard["memory_request_mib"] > guard["memory_budget_mib"]
        or guard["runtime_rss_limit_mib"] > guard["memory_request_mib"]
        or guard.get("status_path") != str(status_path.resolve())
        or not isinstance(guard.get("resource_root"), str)
        or not guard["resource_root"]
        or not isinstance(guard.get("batch_id"), str)
        or not guard["batch_id"]
        or not isinstance(guard.get("job_id"), str)
        or not guard["job_id"]
        or not Path(str(guard["resource_root"])).is_dir()
    ):
        raise T111ExecutionAuthorizationError("resource guard binding is inconsistent")
    return {**dict(value), "resource_guard": dict(guard)}


def validate_t111_execution_authorization(
    value: object,
    *,
    authorization_path: Path,
    qualification_path: Path,
    preparation_path: Path,
    resource_status_path: Path,
    expected_head: str,
    repo_root: Path,
) -> dict[str, object]:
    """Validate the complete Maintainer-owned authorization before adapter import."""

    required = {
        "schema_id",
        "task_id",
        "authorization_id",
        "authorized",
        "decision",
        "implementation_worktree_path",
        "implementation_head",
        "approved_spec_commit",
        "python_runtime",
        "qualification_artifact",
        "preparation_artifact",
        "native_identity",
        "native_binary",
        "resource_plan",
    }
    if not isinstance(value, Mapping) or set(value) != required:
        raise T111ExecutionAuthorizationError("authorization fields are malformed")
    head, branch, dirty = _git_state(repo_root)
    if (
        value.get("schema_id") != T111_EXECUTION_AUTH_SCHEMA
        or value.get("task_id") != "T111"
        or not isinstance(value.get("authorization_id"), str)
        or not value["authorization_id"].strip()
        or value.get("authorized") is not True
        or value.get("decision") != "EXECUTION_AUTHORIZED"
        or value.get("implementation_worktree_path")
        != str(repo_root.resolve(strict=True))
        or value.get("implementation_head") != expected_head
        or value.get("implementation_head") != head
        or branch != _EXPECTED_HEAD_BRANCH
        or dirty
        or value.get("approved_spec_commit") != preparation.T111_APPROVED_SPEC_COMMIT
    ):
        raise T111ExecutionAuthorizationError(
            "authorization does not match the clean current exact-head worktree"
        )
    qualification_ref = _verify_artifact_reference(
        value.get("qualification_artifact"),
        path=qualification_path,
        expected_schema=T111_PREP_QUALIFICATION_SCHEMA,
    )
    preparation_ref = _verify_artifact_reference(
        value.get("preparation_artifact"),
        path=preparation_path,
        expected_schema=T111_PREPARATION_SCHEMA,
    )
    qualification = _read_json(qualification_path, label="T111 qualification")
    readiness = _read_json(preparation_path, label="T111 readiness preparation")
    runtime = preparation._python_runtime_fingerprint()
    if (
        qualification.get("eligible") is not True
        or qualification.get("candidate_execution_started") is not False
        or qualification.get("implementation_head") != head
        or readiness.get("candidate_execution_authorized") is not False
        or readiness.get("candidate_execution_started") is not False
        or readiness.get("implementation_head") != head
        or readiness.get("input_qualification_sha256") != qualification_ref["sha256"]
        or not isinstance(qualification.get("python_runtime"), Mapping)
        or dict(qualification["python_runtime"]) != runtime
        or readiness.get("python_runtime") != runtime
        or value.get("python_runtime") != runtime
        or not isinstance(qualification.get("retained_artifacts"), Mapping)
        or set(qualification["retained_artifacts"]) != _EXPECTED_INPUT_ROLES
    ):
        raise T111ExecutionAuthorizationError(
            "input qualification/readiness does not bind eligible exact-head inputs"
        )
    native = value.get("native_identity")
    if (
        not isinstance(native, Mapping)
        or dict(native)
        != {
            "repository": "lsmfttb/sts_lightspeed",
            "ref": T111_NATIVE_REF,
            "commit": T111_NATIVE_COMMIT,
        }
        or qualification.get("native_identity") != dict(native)
    ):
        raise T111ExecutionAuthorizationError("authorized native identity is not T110")
    binary = value.get("native_binary")
    if (
        not isinstance(binary, Mapping)
        or set(binary) != {"path", "sha256", "size_bytes"}
        or not isinstance(binary.get("path"), str)
        or not isinstance(binary.get("sha256"), str)
        or len(binary["sha256"]) != 64
        or any(char not in "0123456789abcdef" for char in binary["sha256"])
        or isinstance(binary.get("size_bytes"), bool)
        or not isinstance(binary.get("size_bytes"), int)
        or binary["size_bytes"] <= 0
    ):
        raise T111ExecutionAuthorizationError("native binary binding is malformed")
    try:
        binary_path = preparation._validate_native_binary_abi_path(
            Path(str(binary["path"])), runtime
        )
        binary_digest = _sha256_file(binary_path)
        binary_size = binary_path.stat().st_size
    except (OSError, preparation.T111QualificationError) as exc:
        raise T111ExecutionAuthorizationError(
            "native binary is incompatible with the authorized Python ABI"
        ) from exc
    if (
        str(binary_path) != binary["path"]
        or binary_digest != binary["sha256"]
        or binary_size != binary["size_bytes"]
    ):
        raise T111ExecutionAuthorizationError(
            "native binary path/hash/size differs from Maintainer authorization"
        )
    plan = _validate_resource_plan(
        value.get("resource_plan"), status_path=resource_status_path
    )
    return {
        "authorization": dict(value),
        "qualification": qualification,
        "readiness_preparation": readiness,
        "qualification_artifact": qualification_ref,
        "preparation_artifact": preparation_ref,
        "native_binary": dict(binary),
        "resource_plan": plan,
        "local_git_state": {"head": head, "branch": branch, "clean": True},
    }


def _verify_active_resource_guard(
    status_path: Path, *, authorization: Mapping[str, object], target_pid: int
) -> dict[str, object]:
    status = _read_json(status_path, label="active detached resource status")
    plan = authorization["resource_plan"]
    assert isinstance(plan, Mapping)
    resource_plan = plan["resource_guard"]
    assert isinstance(resource_plan, Mapping)
    admission = status.get("resource_admission")
    if (
        status.get("state") != "RUNNING"
        or status.get("target_pid") != target_pid
        or not isinstance(admission, Mapping)
        or admission.get("worker_count") != 1
        or admission.get("shard_count") != 1
        or admission.get("batch_id") != resource_plan["batch_id"]
        or admission.get("job_id") != resource_plan["job_id"]
    ):
        raise T111ExecutionAuthorizationError(
            "candidate execution requires the authorized active detached target"
        )
    guard = admission.get("runtime_guard")
    if (
        not isinstance(guard, Mapping)
        or guard.get("enabled") is not True
        or guard.get("state") not in {"ARMED", "MONITORING"}
        or guard.get("rss_limit_mib") != resource_plan["runtime_rss_limit_mib"]
        or guard.get("memavailable_floor_mib")
        != resource_plan["runtime_memavailable_floor_mib"]
        or guard.get("sample_interval_seconds")
        != resource_plan["runtime_sample_seconds"]
        or admission.get("memory_budget_mib") != resource_plan["memory_budget_mib"]
        or admission.get("memory_request_mib") != resource_plan["memory_request_mib"]
    ):
        raise T111ExecutionAuthorizationError(
            "active detached guard differs from the Maintainer resource plan"
        )
    return {
        "status_path": str(status_path.resolve()),
        "state": guard["state"],
        "target_pid": target_pid,
        "runtime_rss_limit_mib": guard["rss_limit_mib"],
        "runtime_memavailable_floor_mib": guard["memavailable_floor_mib"],
        "sample_interval_seconds": guard["sample_interval_seconds"],
        "batch_id": admission["batch_id"],
        "job_id": admission["job_id"],
    }


def _load_native_module(binary_path: Path, expected_sha256: str) -> object:
    try:
        resolved = preparation._validate_native_binary_abi_path(
            binary_path, preparation._python_runtime_fingerprint()
        )
        digest = _sha256_file(resolved)
    except (OSError, preparation.T111QualificationError) as exc:
        raise T111ExecutionAuthorizationError(
            "authorized native binary is unavailable"
        ) from exc
    if digest != expected_sha256:
        raise T111ExecutionAuthorizationError(
            "authorized native binary SHA-256 changed"
        )
    spec = importlib.util.spec_from_file_location("slaythespire", resolved)
    if spec is None or spec.loader is None:
        raise T111ExecutionAuthorizationError("cannot load the exact native extension")
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except Exception as exc:
        raise T111ExecutionAuthorizationError(
            "exact native extension import failed"
        ) from exc
    if Path(str(getattr(module, "__file__", ""))).resolve() != resolved:
        raise T111ExecutionAuthorizationError(
            "loaded extension path differs from approval"
        )
    return module


def _reload_qualified_inputs(
    *, qualification: Mapping[str, object], t101_manifest_path: Path, head: str
) -> tuple[
    list[dict[str, object]],
    object,
    Mapping[str, Mapping[str, object]],
    Mapping[str, object],
    dict[str, object],
]:
    """Re-hash and reconstruct the retained source gate immediately pre-run."""

    bindings = qualification.get("retained_artifacts")
    if not isinstance(bindings, Mapping):
        raise T111ExecutionAuthorizationError(
            "qualification artifact bindings are missing"
        )
    historical = qualification.get("historical_t101_execution_identity")
    if not isinstance(historical, Mapping):
        raise T111ExecutionAuthorizationError("historical T101 identity is missing")
    producer = historical.get("implementation_head")
    for role, binding in bindings.items():
        if not isinstance(binding, Mapping):
            raise T111ExecutionAuthorizationError("retained input binding is malformed")
        if role == "native_source_manifest":
            preparation._verify_historical_manifest_blob(
                binding,
                producer_commit=str(producer),
                repo_root=preparation._git_repository_root(t101_manifest_path),
            )
        else:
            preparation._verify_file_binding(binding, role=str(role))

    current_manifest = qualification.get("current_source_manifest")
    native_identity = qualification.get("native_identity")
    if not isinstance(current_manifest, Mapping) or not isinstance(
        native_identity, Mapping
    ):
        raise T111ExecutionAuthorizationError(
            "current T110 source manifest binding is missing"
        )
    observed_native, observed_manifest = preparation._source_manifest_identity(
        Path(str(current_manifest.get("path", "")))
    )
    if observed_native != dict(native_identity) or any(
        observed_manifest.get(field) != current_manifest.get(field)
        for field in ("schema_id", "sha256", "size_bytes", "capabilities")
    ):
        raise T111ExecutionAuthorizationError("current T110 source manifest changed")

    _manifest, input_admission, cohort, _historical, old_native = (
        t103_particle_diagnostic._load_t101_terminal_inputs(t101_manifest_path)
    )
    if old_native.get("commit") != "97f59b620efe5ee1571f8da298c99d1e21c1149b":
        raise T111ExecutionAuthorizationError("historical T101 native identity changed")
    refs = t103_particle_diagnostic._t101_input_artifact_bindings(input_admission)
    restore_path = Path(str(refs["t085_restore"]["path"]))
    restore_document = json.loads(restore_path.read_text(encoding="utf-8"))
    b_manifest, c_manifest = preparation._t085_source_manifest_paths(restore_document)
    gate_values = {
        "t087_formal_path": Path(str(refs["t087_formal"]["path"])),
        "t087_report_path": Path(str(refs["t087_report"]["path"])),
        "t087_retention_path": Path(str(refs["t087_retention"]["path"])),
        "t085_selection_path": Path(str(refs["t085_selection"]["path"])),
        "t085_restore_path": restore_path,
        "a_pool_path": Path(str(refs["t085_canonical_a"]["path"])),
        "b_pool_path": Path(str(refs["t085_canonical_b"]["path"])),
        "c_pool_path": Path(str(refs["t085_canonical_c"]["path"])),
        "b_source_manifest_path": b_manifest,
        "c_source_manifest_path": c_manifest,
    }
    formal, gate, gate_inputs = t088_canary._admit_t088_canary_inputs_from_paths(
        implementation_head=head,
        historical_t085_producer_only=True,
        **gate_values,
    )
    canonical = getattr(gate, "canonical_records_by_cohort", None)
    source_identity = getattr(gate, "source_selection_manifest_identity", None)
    if not isinstance(canonical, Mapping) or not isinstance(source_identity, Mapping):
        raise T111ExecutionAuthorizationError("T087/T085 source gate is malformed")
    source_rows = t088_canary._project_t087_cohort(formal, source_identity, canonical)
    attempts = cohort.get("attempted")
    if not isinstance(attempts, Sequence) or isinstance(attempts, (str, bytes)):
        raise T111ExecutionAuthorizationError(
            "T101 full ordered attempt evidence is missing"
        )
    population = preparation._validate_t101_order(attempts, source_rows)
    selection_plan = load_t085_native_evaluation_plan(
        gate_values["t085_selection_path"],
        expected_sha256=str(refs["t085_selection"]["sha256"]),
    )
    selected_records: dict[str, object] = {}
    for stratum in T101_SOURCE_COUNTS:
        for selected_record in selection_plan.cohorts[stratum]:
            selected_records[selected_record.selection_identity] = selected_record
    return (
        source_rows,
        gate,
        canonical,
        selected_records,
        {
            "t101_terminal_manifest_path": str(t101_manifest_path.resolve()),
            "t101_terminal_manifest_sha256": _sha256_file(t101_manifest_path),
            "native_identity": dict(native_identity),
            "historical_t101_native_identity": old_native,
            "source_population": population,
            "t087_t085_gate_inputs": gate_inputs,
            "retained_artifacts": dict(bindings),
        },
    )


def _append_jsonl(path: Path, row: Mapping[str, object]) -> None:
    data = _canonical_json(row)
    with path.open("ab") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())


def _capture_process_peak_rss(
    *, platform_name: str = sys.platform
) -> dict[str, object]:
    """Capture post-selector ru_maxrss with the platform's documented units."""

    if resource is None:
        raise T111ExecutionAuthorizationError(
            "POSIX execution resource telemetry is unavailable"
        )
    raw_value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    if isinstance(raw_value, bool) or not isinstance(raw_value, (int, float)):
        raise T111ExecutionAuthorizationError("ru_maxrss value is malformed")
    if not math.isfinite(float(raw_value)) or raw_value < 0:
        raise T111ExecutionAuthorizationError("ru_maxrss value is invalid")
    if platform_name.startswith("linux"):
        raw_unit = "KiB"
        mib = float(raw_value) / 1024
    elif platform_name == "darwin":
        raw_unit = "bytes"
        mib = float(raw_value) / (1024 * 1024)
    else:
        raise T111ExecutionAuthorizationError(
            "ru_maxrss units are not defined for this execution platform"
        )
    return {
        "process_peak_rss_mib": round(mib, 3),
        "process_peak_rss_raw": raw_value,
        "process_peak_rss_raw_unit": raw_unit,
        "process_peak_rss_sample_phase": "after_selector_completion",
        "process_peak_rss_source": "resource.getrusage(RUSAGE_SELF).ru_maxrss lifetime high-water mark",
    }


def _validate_attempt_jsonl_matches_cohort(
    *,
    attempts_path: Path,
    attempt_reference: Mapping[str, object],
    attempt_rows: Sequence[Mapping[str, object]],
    execution_record: Mapping[str, object],
) -> None:
    _verify_artifact_reference(
        attempt_reference,
        path=attempts_path,
        expected_schema="t111-candidate-attempts-jsonl-v1",
    )
    executor = execution_record.get("executor")
    shards = executor.get("shards") if isinstance(executor, Mapping) else None
    if not isinstance(shards, list) or len(shards) != 1:
        raise T111ExecutionAuthorizationError("execution shard record is malformed")
    shard = shards[0]
    if not isinstance(shard, Mapping):
        raise T111ExecutionAuthorizationError("execution shard record is malformed")
    try:
        jsonl_rows = [
            json.loads(line)
            for line in attempts_path.read_text(encoding="utf-8").splitlines()
        ]
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise T111ExecutionAuthorizationError(
            "candidate attempt JSONL is invalid"
        ) from exc
    expected_attempts = []
    for row in attempt_rows:
        expected = dict(row)
        expected.update(
            {
                "worker_id": shard["worker_id"],
                "shard_id": shard["shard_id"],
                "shard_candidate_range": list(shard["candidate_range"]),
                "executor_attempt_status": (
                    "ADMITTED" if row.get("admitted") is True else "EXCLUDED_NO_RETRY"
                ),
            }
        )
        expected_attempts.append(expected)
    if jsonl_rows != expected_attempts:
        raise T111ExecutionAuthorizationError(
            "ordered candidate JSONL and cohort attempt records differ"
        )


def _validate_completed_resource_guard(
    status: Mapping[str, object], execution_record: Mapping[str, object]
) -> tuple[Mapping[str, object], Mapping[str, object]]:
    """Verify terminal guard identity, topology, and observed resource bounds."""

    plan = execution_record.get("resource_guard_plan")
    executor = execution_record.get("executor")
    target_pid = execution_record.get("target_pid")
    if (
        not isinstance(plan, Mapping)
        or not isinstance(executor, Mapping)
        or isinstance(target_pid, bool)
        or not isinstance(target_pid, int)
        or target_pid <= 0
    ):
        raise T111ExecutionAuthorizationError("execution guard binding is malformed")
    admission = status.get("resource_admission")
    guard = admission.get("runtime_guard") if isinstance(admission, Mapping) else None
    positive_int_fields = (
        "memory_budget_mib",
        "memory_request_mib",
        "runtime_rss_limit_mib",
        "runtime_memavailable_floor_mib",
    )
    if any(
        isinstance(plan.get(field), bool)
        or not isinstance(plan.get(field), int)
        or plan[field] <= 0
        for field in positive_int_fields
    ):
        raise T111ExecutionAuthorizationError("resource guard plan is malformed")
    sample_seconds = plan.get("runtime_sample_seconds")
    if (
        isinstance(sample_seconds, bool)
        or not isinstance(sample_seconds, (int, float))
        or not math.isfinite(float(sample_seconds))
        or sample_seconds <= 0
    ):
        raise T111ExecutionAuthorizationError("resource sampling plan is malformed")
    if not isinstance(admission, Mapping) or not isinstance(guard, Mapping):
        raise T111ExecutionAuthorizationError("terminal resource guard is missing")
    sample_count = guard.get("sample_count")
    peak_rss = guard.get("peak_rss_mib")
    lowest_memavailable = guard.get("lowest_memavailable_mib")
    if (
        status.get("state") != "SUCCEEDED"
        or status.get("exit_code") != 0
        or guard.get("state") != "COMPLETED"
        or isinstance(sample_count, bool)
        or not isinstance(sample_count, int)
        or sample_count <= 0
        or guard.get("rss_limit_mib") != plan["runtime_rss_limit_mib"]
        or guard.get("memavailable_floor_mib") != plan["runtime_memavailable_floor_mib"]
        or guard.get("sample_interval_seconds") != sample_seconds
        or admission.get("batch_id") != plan.get("batch_id")
        or admission.get("job_id") != plan.get("job_id")
        or admission.get("root") != plan.get("resource_root")
        or admission.get("memory_budget_mib") != plan["memory_budget_mib"]
        or admission.get("memory_request_mib") != plan["memory_request_mib"]
        or status.get("target_pid") != target_pid
        or admission.get("target_pid") != target_pid
        or admission.get("worker_count") != executor.get("effective_worker_count")
        or admission.get("shard_count") != executor.get("shard_count")
        or guard.get("sample_error") is not None
        or guard.get("trigger_reason") is not None
        or isinstance(peak_rss, bool)
        or not isinstance(peak_rss, (int, float))
        or not math.isfinite(float(peak_rss))
        or peak_rss < 0
        or peak_rss > plan["runtime_rss_limit_mib"]
        or isinstance(lowest_memavailable, bool)
        or not isinstance(lowest_memavailable, (int, float))
        or not math.isfinite(float(lowest_memavailable))
        or lowest_memavailable < plan["runtime_memavailable_floor_mib"]
    ):
        raise T111ExecutionAuthorizationError(
            "detached job or resource guard did not complete within its exact plan"
        )
    return admission, guard


def execute_t111_authorized_population(
    *,
    authorization_path: Path,
    qualification_path: Path,
    preparation_path: Path,
    resource_status_path: Path,
    t101_manifest_path: Path,
    output_root: Path,
) -> dict[str, object]:
    """Execute only after strict authorization and active guard verification."""

    if os.name == "nt":
        raise T111ExecutionAuthorizationError(
            "T111 candidate execution must run under the approved WSL/POSIX guard"
        )
    if resource is None:
        raise T111ExecutionAuthorizationError(
            "POSIX execution resource telemetry is unavailable"
        )
    auth = _read_json(authorization_path, label="Maintainer execution authorization")
    expected_head = str(auth.get("implementation_head", ""))
    validated = validate_t111_execution_authorization(
        auth,
        authorization_path=authorization_path,
        qualification_path=qualification_path,
        preparation_path=preparation_path,
        resource_status_path=resource_status_path,
        expected_head=expected_head,
        repo_root=preparation._git_repository_root(Path(__file__)),
    )
    active_guard = _verify_active_resource_guard(
        resource_status_path, authorization=validated, target_pid=os.getpid()
    )
    binary = validated["native_binary"]
    assert isinstance(binary, Mapping)
    source_rows, _gate, canonical, selected_records, provenance = (
        _reload_qualified_inputs(
            qualification=validated["qualification"],
            t101_manifest_path=t101_manifest_path,
            head=expected_head,
        )
    )
    module = _load_native_module(Path(str(binary["path"])), str(binary["sha256"]))
    if output_root.exists():
        raise T111ExecutionAuthorizationError(
            "refusing to overwrite T111 execution outputs"
        )
    output_root.mkdir(parents=True, exist_ok=False)
    attempts_path = output_root / "t111-candidate-attempts.jsonl"
    with attempts_path.open("xb"):
        pass

    plan = validated["resource_plan"]
    assert isinstance(plan, Mapping)
    shard = plan["shards"][0]
    assert isinstance(shard, Mapping)
    from sts_combat_rl.sim.lightspeed import LightSpeedAdapter

    active_adapters: list[LightSpeedAdapter] = []

    def adapter_factory() -> LightSpeedAdapter:
        adapter = LightSpeedAdapter(
            seed=1, ascension=20, player_class="IRONCLAD", module=module
        )
        active_adapters.append(adapter)
        return adapter

    runner = T111NativeRecordRunner(
        adapter_factory=adapter_factory,
        selected_records=selected_records,
        canonical_records_by_stratum=canonical,
        native_identity=validated["authorization"]["native_identity"],
    )
    started = time.monotonic()
    guard_snapshots = [active_guard]

    def retain_attempt(row: Mapping[str, object]) -> None:
        if not isinstance(row, dict):
            raise T111ExecutionAuthorizationError(
                "selector emitted a non-mutable attempt row"
            )
        enriched = row
        enriched["worker_id"] = shard["worker_id"]
        enriched["shard_id"] = shard["shard_id"]
        enriched["shard_candidate_range"] = list(shard["candidate_range"])
        enriched["executor_attempt_status"] = (
            "ADMITTED" if row.get("admitted") is True else "EXCLUDED_NO_RETRY"
        )
        _append_jsonl(attempts_path, enriched)
        guard_snapshots.append(
            _verify_active_resource_guard(
                resource_status_path,
                authorization=validated,
                target_pid=os.getpid(),
            )
        )

    def admit_one(record: Mapping[str, object]) -> Mapping[str, object]:
        try:
            return runner(record)
        finally:
            if active_adapters:
                adapter = active_adapters.pop()
                adapter.close()

    try:
        cohort = select_t111_configured_search_cohort(
            source_rows,
            native_identity=validated["authorization"]["native_identity"],
            admit=admit_one,
            on_attempt=retain_attempt,
        )
        cohort = validate_t111_configured_search_cohort(cohort)
        # Sample the process high-water mark only after selector completion.
        process_peak_rss = _capture_process_peak_rss()
        cohort_ref = _write_new_json(output_root / "t111-cohort-admission.json", cohort)
        attempt_ref = {
            "path": str(attempts_path.resolve()),
            "schema_id": "t111-candidate-attempts-jsonl-v1",
            "size_bytes": attempts_path.stat().st_size,
            "sha256": _sha256_file(attempts_path),
        }
        elapsed = max(0.0, time.monotonic() - started)
        attempt_rows = cohort["attempted"]
        assert isinstance(attempt_rows, list)
        durations = [float(row["wall_clock_time_s"]) for row in attempt_rows]
        excluded_counts = Counter(
            str(row["exclusion_reason"])
            for row in attempt_rows
            if row["admitted"] is False
        )
        execution_record = {
            "schema_id": T111_EXECUTION_RECORD_SCHEMA,
            "task_id": "T111",
            "implementation_head": expected_head,
            "target_pid": os.getpid(),
            "approved_spec_commit": preparation.T111_APPROVED_SPEC_COMMIT,
            "authorization_id": validated["authorization"]["authorization_id"],
            "authorization_sha256": _sha256_file(authorization_path),
            "candidate_execution_authorized": True,
            "candidate_execution_started": True,
            "candidate_execution_completed": True,
            "native_identity": validated["authorization"]["native_identity"],
            "native_binary": dict(binary),
            "python_runtime": dict(validated["authorization"]["python_runtime"]),
            "historical_t101_identity": provenance["historical_t101_native_identity"],
            "input_provenance": provenance,
            "input_qualification_artifact": validated["qualification_artifact"],
            "readiness_preparation_artifact": validated["preparation_artifact"],
            "executor": {
                "effective_worker_count": 1,
                "shard_count": 1,
                "shards": [dict(shard)],
                "attempted_count": len(attempt_rows),
                "attempted_wall_clock_total_s": sum(durations),
                "attempted_wall_clock_max_s": max(durations, default=0.0),
                "attempted_wall_clock_min_s": min(durations, default=0.0),
                "whole_selector_wall_clock_s": elapsed,
                **process_peak_rss,
                "no_retry_attempt_count": sum(
                    row.get("failure_retry_status")
                    in {"failed_no_retry", "success_no_retry"}
                    for row in attempt_rows
                ),
                "exclusion_counts": dict(sorted(excluded_counts.items())),
            },
            "resource_guard_plan": dict(plan["resource_guard"]),
            "resource_guard_status_path": str(resource_status_path.resolve()),
            "resource_guard_observations_during_execution": guard_snapshots,
            "attempt_artifact": attempt_ref,
            "cohort_admission_artifact": cohort_ref,
            "terminal_classification": cohort["terminal_classification"],
        }
        execution_ref = _write_new_json(
            output_root / "t111-execution-record.json", execution_record
        )
        return {
            "execution_record": execution_record,
            "execution_record_artifact": execution_ref,
            "attempt_artifact": attempt_ref,
            "cohort_admission_artifact": cohort_ref,
        }
    except BaseException as exc:  # noqa: BLE001 - preserve interrupted job evidence
        # The attempt JSONL is append-only and may contain scientifically useful
        # partial rows. Preserve only the exception type and never invent a
        # terminal classification from an interrupted run.
        failure = {
            "schema_id": "t111-execution-interruption-v1",
            "task_id": "T111",
            "implementation_head": expected_head,
            "authorization_id": validated["authorization"]["authorization_id"],
            "state": "INCOMPLETE",
            "candidate_execution_started": attempts_path.stat().st_size > 0,
            "exception_type": type(exc).__name__[:120],
            "attempt_artifact": {
                "path": str(attempts_path.resolve()),
                "schema_id": "t111-candidate-attempts-jsonl-v1",
                "size_bytes": attempts_path.stat().st_size,
                "sha256": _sha256_file(attempts_path),
            },
        }
        try:
            _write_new_json(output_root / "t111-execution-interruption.json", failure)
        finally:
            raise


def finalize_t111_execution(
    *, output_root: Path, resource_status_path: Path
) -> dict[str, object]:
    """Bind a completed external detached-job guard to retained final outputs."""

    record_path = output_root / "t111-execution-record.json"
    record = _read_json(record_path, label="T111 execution record")
    if record.get("resource_guard_status_path") != str(resource_status_path.resolve()):
        raise T111ExecutionAuthorizationError("resource status path is not bound")
    status = _read_json(resource_status_path, label="terminal detached resource status")
    admission, guard = _validate_completed_resource_guard(status, record)
    executor = record["executor"]
    attempt_ref = record.get("attempt_artifact")
    cohort_ref = record.get("cohort_admission_artifact")
    if not isinstance(attempt_ref, Mapping) or not isinstance(cohort_ref, Mapping):
        raise T111ExecutionAuthorizationError(
            "execution record lacks output references"
        )
    cohort_artifact = _verify_artifact_reference(
        cohort_ref,
        expected_schema="t111-configured-search-cohort-admission-v1",
    )
    cohort = _read_json(
        Path(str(cohort_artifact["path"])), label="T111 cohort admission"
    )
    cohort = validate_t111_configured_search_cohort(cohort)
    attempt_rows = cohort["attempted"]
    assert isinstance(attempt_rows, list)
    _validate_attempt_jsonl_matches_cohort(
        attempts_path=Path(str(attempt_ref["path"])),
        attempt_reference=attempt_ref,
        attempt_rows=attempt_rows,
        execution_record=record,
    )
    if (
        len(attempt_rows) != executor.get("attempted_count")
        or record.get("candidate_execution_completed") is not True
    ):
        raise T111ExecutionAuthorizationError("execution record and cohort disagree")
    status_ref = {
        "path": str(resource_status_path.resolve()),
        "schema_id": "stsrl-detached-job-status-v1",
        "size_bytes": resource_status_path.stat().st_size,
        "sha256": _sha256_file(resource_status_path),
    }
    report = {
        "schema_id": T111_FINAL_REPORT_SCHEMA,
        "task_id": "T111",
        "implementation_head": record["implementation_head"],
        "approved_spec_commit": record["approved_spec_commit"],
        "native_identity": record["native_identity"],
        "historical_t101_identity": record["historical_t101_identity"],
        "source_counts": dict(T101_SOURCE_COUNTS),
        "attempted_counts": {
            stratum: sum(row.get("stratum") == stratum for row in attempt_rows)
            for stratum in T101_SOURCE_COUNTS
        },
        "selected_counts": dict(cohort["selected_counts"]),
        "selected_identities": list(cohort["selected"]),
        "exhausted_strata": list(cohort["exhausted_strata"]),
        "selection_uses_value_or_outcome": False,
        "historical_failure_label_preselection": False,
        "frozen_configuration": {
            "particle_start": 0,
            "particle_count": 2,
            "replicate_index": 0,
            "search_simulations_per_particle": 400,
            "include_potions": False,
        },
        "exclusion_counts": dict(record["executor"]["exclusion_counts"]),
        "admitted_configuration_excluded_occurrence_counts": [
            row["support_summary"][
                "configuration_excluded_occurrence_count_per_particle"
            ]
            for row in attempt_rows
            if row.get("admitted") is True
        ],
        "admitted_configured_search_decision_class_counts": [
            row["support_summary"]["configured_search_decision_class_count"]
            for row in attempt_rows
            if row.get("admitted") is True
        ],
        "terminal_classification": cohort["terminal_classification"],
        "executor": record["executor"],
        "resource_guard_observation": {
            "status_path": status_ref["path"],
            "state": guard["state"],
            "sample_count": guard["sample_count"],
            "peak_rss_mib": guard["peak_rss_mib"],
            "lowest_memavailable_mib": guard["lowest_memavailable_mib"],
            "rss_limit_mib": guard["rss_limit_mib"],
            "memavailable_floor_mib": guard["memavailable_floor_mib"],
            "sample_interval_seconds": guard["sample_interval_seconds"],
            "batch_id": admission["batch_id"],
            "job_id": admission["job_id"],
            "lease_id": admission.get("lease_id"),
            "target_pid": admission["target_pid"],
            "worker_count": admission["worker_count"],
            "shard_count": admission["shard_count"],
            "memory_budget_mib": admission["memory_budget_mib"],
            "memory_request_mib": admission["memory_request_mib"],
        },
        "candidate_execution_completed": True,
        "no_n_gt_2_or_convergence_execution": True,
    }
    report_ref = _write_new_json(output_root / "t111-final-report.json", report)
    record_ref = {
        "path": str(record_path.resolve()),
        "schema_id": T111_EXECUTION_RECORD_SCHEMA,
        "size_bytes": record_path.stat().st_size,
        "sha256": _sha256_file(record_path),
    }
    manifest = {
        "schema_id": T111_RETENTION_MANIFEST_SCHEMA,
        "task_id": "T111",
        "implementation_head": record["implementation_head"],
        "approved_spec_commit": record["approved_spec_commit"],
        "terminal_classification": cohort["terminal_classification"],
        "artifact_references": {
            "input_qualification": record.get("input_qualification_artifact"),
            "readiness_preparation": record.get("readiness_preparation_artifact"),
            "candidate_attempts": attempt_ref,
            "cohort_admission": cohort_ref,
            "execution_record": record_ref,
            "detached_resource_status": status_ref,
            "final_report": report_ref,
        },
        "candidate_execution_started": True,
        "candidate_execution_completed": True,
        "retention_reason": "Retain exact-head T111 configured-domain support evidence.",
        "deletion_condition": "Delete only after lifecycle and provenance review has no remaining audit consumers.",
    }
    manifest_ref = _write_new_json(
        output_root / "t111-terminal-retention-manifest.json", manifest
    )
    return {
        "final_report": report,
        "final_report_artifact": report_ref,
        "manifest_artifact": manifest_ref,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    execute = subparsers.add_parser("execute")
    execute.add_argument("--authorization", type=Path, required=True)
    execute.add_argument("--qualification", type=Path, required=True)
    execute.add_argument("--preparation", type=Path, required=True)
    execute.add_argument("--resource-status", type=Path, required=True)
    execute.add_argument("--t101-retention-manifest", type=Path, required=True)
    execute.add_argument("--output-root", type=Path, required=True)
    finalize = subparsers.add_parser("finalize")
    finalize.add_argument("--output-root", type=Path, required=True)
    finalize.add_argument("--resource-status", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "execute":
            result = execute_t111_authorized_population(
                authorization_path=args.authorization,
                qualification_path=args.qualification,
                preparation_path=args.preparation,
                resource_status_path=args.resource_status,
                t101_manifest_path=args.t101_retention_manifest,
                output_root=args.output_root,
            )
            print(
                json.dumps({"status": "EXECUTION_COMPLETE", **result}, sort_keys=True)
            )
        else:
            result = finalize_t111_execution(
                output_root=args.output_root,
                resource_status_path=args.resource_status,
            )
            print(json.dumps({"status": "FINALIZED", **result}, sort_keys=True))
    except (
        OSError,
        T111ConfiguredSearchError,
        T111ExecutionAuthorizationError,
        ValueError,
    ) as exc:
        print(
            json.dumps(
                {"status": "INCOMPLETE", "error_type": type(exc).__name__},
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "T111ExecutionAuthorizationError",
    "execute_t111_authorized_population",
    "finalize_t111_execution",
    "main",
    "validate_t111_execution_authorization",
]
