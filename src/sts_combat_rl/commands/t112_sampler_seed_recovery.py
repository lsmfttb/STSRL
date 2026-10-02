"""T112 exact-head qualification, one-call witness, and bounded N=2 recovery.

Preparation is simulator-free. The native witness and candidate selector are
separate commands and require distinct Maintainer approval records plus an
active detached resource guard. T111 validators/order/runner are reused, while
all retained T112 outputs use T112-owned schemas and terminal labels.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import subprocess
import time
from collections import Counter
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from sts_combat_rl.commands import (
    t111_configured_search_execution as t111_runner_module,
)
from sts_combat_rl.commands import (
    t111_configured_search_execution_cli as t111_execution,
)
from sts_combat_rl.commands import (
    t111_configured_search_support as t111_preparation,
)
from sts_combat_rl.sim.t101_particle_convergence import (
    T101_SEARCH_SIMULATIONS,
    T101_SOURCE_COUNTS,
    derive_t101_sampler_seed,
)
from sts_combat_rl.sim.t111_configured_search_support import (
    T111_ADMISSION_SCHEMA,
    T111SupportExclusion,
    select_t111_configured_search_cohort,
    validate_t111_configured_search_cohort,
)
from sts_combat_rl.sim.t112_sampler_seed_recovery import (
    T112_APPROVED_SPEC_COMMIT,
    T112_COHORT_SCHEMA,
    T112_NATIVE_IDENTITY,
    T112_REPAIR_FACTS,
    T112_REPAIR_PROVENANCE_SCHEMA,
    T112_TASK_ID,
    T112_TERMINALS,
    T112_WITNESS_SCHEMA,
    safe_t112_seed_metadata,
    t112_cohort_from_t111,
    validate_t112_cohort,
    validate_t112_safe_seed_metadata,
)

T112_QUALIFICATION_SCHEMA = "t112-input-qualification-v1"
T112_PREPARATION_SCHEMA = "t112-readiness-preparation-v1"
T112_PREPARATION_MANIFEST_SCHEMA = "t112-preparation-retention-manifest-v1"
T112_AUTH_SCHEMA = "t112-maintainer-stage-authorization-v1"
T112_WITNESS_RECORD_SCHEMA = "t112-native-witness-execution-record-v1"
T112_WITNESS_TERMINAL_SCHEMA = "t112-native-witness-terminal-v1"
T112_EXECUTION_RECORD_SCHEMA = "t112-cohort-execution-record-v1"
T112_FINAL_REPORT_SCHEMA = "t112-final-report-v1"
T112_RETENTION_MANIFEST_SCHEMA = "t112-terminal-retention-manifest-v1"
T112_INTERRUPTION_SCHEMA = "t112-execution-interruption-v1"
T112_BRANCH = "planner/t112-sampler-seed-repair-cohort-recovery"
T112_RAW_REPORTS_INELIGIBLE = "T111_RAW_BRIDGE_REPORTS_NOT_RETAINED"
_T111_REFERENCE_SCHEMAS = {
    "input_qualification": "t111-input-qualification-v1",
    "readiness_preparation": "t111-execution-readiness-preparation-v1",
    "candidate_attempts": "t111-candidate-attempts-jsonl-v1",
    "cohort_admission": T111_ADMISSION_SCHEMA,
    "execution_record": "t111-execution-record-v1",
    "detached_resource_status": "stsrl-detached-job-status-v1",
    "final_report": "t111-final-report-v1",
}
_T112_STAGE_DECISIONS = {
    "witness": "N2_NATIVE_WITNESS_AUTHORIZED",
    "cohort": "BOUNDED_COHORT_EXECUTION_AUTHORIZED",
}
_T112_PR_COMMENT_PREFIX = "https://github.com/lsmfttb/STSRL/pull/130#issuecomment-"


class T112WorkflowError(ValueError):
    """A T112 stage is not bound to its approved exact-head evidence."""


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
        raise T112WorkflowError(f"cannot read {label}") from exc
    if not isinstance(value, Mapping):
        raise T112WorkflowError(f"{label} must be an object")
    return dict(value)


def _write_new_json(path: Path, value: Mapping[str, object]) -> dict[str, object]:
    path = path.resolve()
    if path.exists():
        raise T112WorkflowError("refusing to overwrite retained T112 evidence")
    path.parent.mkdir(parents=True, exist_ok=True)
    data = _canonical_json(value)
    with path.open("xb") as stream:
        stream.write(data)
    return {
        "path": str(path),
        "schema_id": value.get("schema_id"),
        "size_bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
    }


def _write_jsonl_new(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb"):
        pass


def _append_jsonl(path: Path, value: Mapping[str, object]) -> None:
    with path.open("ab") as stream:
        stream.write(_canonical_json(value))
        stream.flush()
        os.fsync(stream.fileno())


def _artifact_ref(path: Path, *, schema_id: str | None = None) -> dict[str, object]:
    resolved = path.resolve(strict=True)
    return {
        "path": str(resolved),
        "schema_id": schema_id,
        "size_bytes": resolved.stat().st_size,
        "sha256": _sha256_file(resolved),
    }


def _verify_ref(
    value: object,
    *,
    expected_schema: str,
    expected_path: Path | None = None,
) -> dict[str, object]:
    if not isinstance(value, Mapping):
        raise T112WorkflowError("artifact reference is malformed")
    path = Path(str(value.get("path", "")))
    if expected_path is not None and path.resolve() != expected_path.resolve():
        raise T112WorkflowError("artifact path differs from stage binding")
    try:
        size = path.stat().st_size
        digest = _sha256_file(path)
    except OSError as exc:
        raise T112WorkflowError("bound artifact is unavailable") from exc
    if (
        value.get("schema_id") != expected_schema
        or value.get("size_bytes") != size
        or value.get("sha256") != digest
    ):
        raise T112WorkflowError("bound artifact schema/hash changed")
    return {
        "path": str(path.resolve()),
        "schema_id": expected_schema,
        "size_bytes": size,
        "sha256": digest,
    }


def _verify_repair_provenance(
    qualification: Mapping[str, object],
    readiness: Mapping[str, object],
    *,
    implementation_head: str,
) -> dict[str, object]:
    ref = _verify_ref(
        qualification.get("validator_repair_provenance_artifact"),
        expected_schema=T112_REPAIR_PROVENANCE_SCHEMA,
    )
    if readiness.get("validator_repair_provenance_artifact") != ref:
        raise T112WorkflowError("T112 readiness lost repair provenance binding")
    value = _read_json(Path(str(ref["path"])), label="T112 validator repair provenance")
    expected = {
        "schema_id": T112_REPAIR_PROVENANCE_SCHEMA,
        "task_id": T112_TASK_ID,
        "implementation_head": implementation_head,
        "approved_spec_commit": T112_APPROVED_SPEC_COMMIT,
        "native_identity": dict(T112_NATIVE_IDENTITY),
        **T112_REPAIR_FACTS,
    }
    if value != expected:
        raise T112WorkflowError("T112 validator repair provenance changed")
    return ref


def _git_state(repo_root: Path) -> tuple[str, str, bool]:
    try:
        head = t111_preparation._git_output(repo_root, "rev-parse", "HEAD")
        branch = t111_preparation._git_output(repo_root, "branch", "--show-current")
        dirty = t111_preparation._git_output(repo_root, "status", "--porcelain")
    except (
        OSError,
        subprocess.SubprocessError,
        t111_preparation.T111QualificationError,
    ) as exc:
        raise T112WorkflowError("cannot verify current exact Git state") from exc
    if not all(isinstance(item, str) for item in (head, branch, dirty)):
        raise T112WorkflowError("Git state is not text")
    return head.strip(), branch.strip(), bool(dirty)


def _contract_is_ancestor(repo_root: Path, head: str) -> bool:
    try:
        result = subprocess.run(
            ["git", "merge-base", "--is-ancestor", T112_APPROVED_SPEC_COMMIT, head],
            cwd=repo_root,
            capture_output=True,
            check=False,
            text=True,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise T112WorkflowError(
            "cannot verify approved T112 contract ancestry"
        ) from exc
    return result.returncode == 0


def _verify_current_worktree(repo_root: Path, expected_head: str) -> dict[str, object]:
    head, branch, dirty = _git_state(repo_root)
    if (
        head != expected_head
        or branch != T112_BRANCH
        or dirty
        or not _contract_is_ancestor(repo_root, head)
    ):
        raise T112WorkflowError("T112 stage requires the clean exact approved worktree")
    return {"head": head, "branch": branch, "clean": True}


def _read_jsonl(path: Path, *, label: str) -> list[dict[str, object]]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
        values = [json.loads(line) for line in lines]
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise T112WorkflowError(f"{label} is invalid") from exc
    if any(not isinstance(value, Mapping) for value in values):
        raise T112WorkflowError(f"{label} contains a non-object row")
    return [dict(value) for value in values]


def _verify_t111_terminal_inputs(
    t111_retention_manifest_path: Path,
) -> dict[str, object]:
    """Revalidate immutable T111 terminal outputs; never reuse its labels."""

    manifest = _read_json(
        t111_retention_manifest_path, label="T111 terminal retention manifest"
    )
    if manifest.get("schema_id") != "t111-terminal-retention-manifest-v1":
        raise T112WorkflowError("T111 terminal retention schema mismatch")
    if (
        manifest.get("task_id") != "T111"
        or manifest.get("terminal_classification")
        != "CONFIGURED_SEARCH_DOMAIN_SUPPORT_INSUFFICIENT"
        or manifest.get("candidate_execution_completed") is not True
    ):
        raise T112WorkflowError(
            "retained T111 terminal is not the accepted insufficient result"
        )
    refs = manifest.get("artifact_references")
    if not isinstance(refs, Mapping) or set(refs) != set(_T111_REFERENCE_SCHEMAS):
        raise T112WorkflowError("T111 terminal artifact roles are incomplete")
    verified = {
        role: _verify_ref(ref, expected_schema=schema)
        for role, schema in _T111_REFERENCE_SCHEMAS.items()
        for ref in (refs.get(role),)
    }
    execution = _read_json(
        Path(str(verified["execution_record"]["path"])),
        label="T111 execution record",
    )
    if (
        execution.get("schema_id") != "t111-execution-record-v1"
        or execution.get("task_id") != "T111"
        or execution.get("candidate_execution_completed") is not True
        or execution.get("terminal_classification")
        != "CONFIGURED_SEARCH_DOMAIN_SUPPORT_INSUFFICIENT"
        or execution.get("native_identity") != T112_NATIVE_IDENTITY
    ):
        raise T112WorkflowError("T111 execution record identity/terminal changed")
    cohort = _read_json(
        Path(str(verified["cohort_admission"]["path"])),
        label="T111 cohort admission",
    )
    cohort = validate_t111_configured_search_cohort(cohort)
    attempted = cohort["attempted"]
    if (
        cohort.get("terminal_classification")
        != "CONFIGURED_SEARCH_DOMAIN_SUPPORT_INSUFFICIENT"
        or cohort.get("selected_counts") != {"A": 0, "B": 0, "C": 0}
        or len(attempted) != sum(T101_SOURCE_COUNTS.values())
    ):
        raise T112WorkflowError(
            "T111 retained cohort is not exact 413-row insufficiency"
        )
    raw_report_hashes = [row.get("bridge_report_sha256") for row in attempted]
    if any(value is not None for value in raw_report_hashes):
        raise T112WorkflowError(
            "T111 raw bridge report eligibility differs from the specified null evidence"
        )
    attempt_ref = verified["candidate_attempts"]
    t111_execution._validate_attempt_jsonl_matches_cohort(
        attempts_path=Path(str(attempt_ref["path"])),
        attempt_reference=attempt_ref,
        attempt_rows=attempted,
        execution_record=execution,
    )
    final_report = _read_json(
        Path(str(verified["final_report"]["path"])), label="T111 final report"
    )
    if (
        final_report.get("schema_id") != "t111-final-report-v1"
        or final_report.get("task_id") != "T111"
        or final_report.get("implementation_head")
        != manifest.get("implementation_head")
        or final_report.get("terminal_classification")
        != "CONFIGURED_SEARCH_DOMAIN_SUPPORT_INSUFFICIENT"
    ):
        raise T112WorkflowError("T111 final report identity/terminal changed")
    status_path = Path(str(verified["detached_resource_status"]["path"]))
    status = _read_json(status_path, label="T111 detached resource status")
    _admission, _guard = t111_execution._validate_completed_resource_guard(
        status, execution
    )
    return {
        "retention_manifest": _artifact_ref(
            t111_retention_manifest_path,
            schema_id="t111-terminal-retention-manifest-v1",
        ),
        "implementation_head": manifest.get("implementation_head"),
        "approved_spec_commit": manifest.get("approved_spec_commit"),
        "terminal_classification": manifest.get("terminal_classification"),
        "verified_artifacts": verified,
        "source_counts": dict(T101_SOURCE_COUNTS),
        "attempted_count": len(attempted),
        "selected_counts": dict(cohort["selected_counts"]),
        "raw_bridge_reports": {
            "eligible_for_reuse": False,
            "reason": T112_RAW_REPORTS_INELIGIBLE,
            "candidate_rows_with_null_bridge_report_sha256": sum(
                value is None for value in raw_report_hashes
            ),
            "historical_exclusion_labels_used_for_admission": False,
        },
    }


def prepare_t112_inputs(
    *,
    t101_retention_manifest_path: Path,
    t111_retention_manifest_path: Path,
    current_native_source_manifest_path: Path,
    artifact_root: Path,
    repo_root: Path,
) -> dict[str, object]:
    """Qualify exact T101/T111 sources without loading native code or running a sim."""

    if artifact_root.exists():
        raise T112WorkflowError("refusing to overwrite existing T112 preparation")
    head, branch, dirty = _git_state(repo_root)
    if (
        branch != T112_BRANCH
        or dirty
        or len(head) != 40
        or not _contract_is_ancestor(repo_root, head)
    ):
        raise T112WorkflowError("T112 preparation requires the clean T112 worktree")
    t111_terminal = _verify_t111_terminal_inputs(t111_retention_manifest_path)
    if t111_terminal.get("raw_bridge_reports") != {
        "eligible_for_reuse": False,
        "reason": T112_RAW_REPORTS_INELIGIBLE,
        "candidate_rows_with_null_bridge_report_sha256": 413,
        "historical_exclusion_labels_used_for_admission": False,
    }:
        raise T112WorkflowError(
            "T111 raw bridge report reuse was not rejected explicitly"
        )
    t111_head = t111_terminal.get("implementation_head")
    if not isinstance(t111_head, str) or len(t111_head) != 40:
        raise T112WorkflowError("retained T111 implementation head is malformed")
    source_root = artifact_root / "predecessor-t111-source-qualification"
    prior = t111_preparation.prepare_t111_input_qualification_from_paths(
        implementation_head=t111_head,
        t101_retention_manifest_path=t101_retention_manifest_path,
        artifact_root=source_root,
        source_manifest_path=current_native_source_manifest_path,
    )
    prior_qualification = prior.get("qualification")
    if not isinstance(prior_qualification, Mapping):
        raise T112WorkflowError("T111 source validator did not return qualification")
    prior_ref = prior.get("qualification_artifact")
    prior_ref = _verify_ref(prior_ref, expected_schema="t111-input-qualification-v1")
    current_manifest = prior_qualification.get("current_source_manifest")
    native_identity = prior_qualification.get("native_identity")
    if (
        prior_qualification.get("eligible") is not True
        or prior_qualification.get("candidate_execution_started") is not False
        or prior_qualification.get("implementation_head") != t111_head
        or prior_qualification.get("approved_spec_commit")
        != t111_preparation.T111_APPROVED_SPEC_COMMIT
        or not isinstance(current_manifest, Mapping)
        or not isinstance(native_identity, Mapping)
        or dict(native_identity) != T112_NATIVE_IDENTITY
    ):
        raise T112WorkflowError("T101/T085 source and restore qualification failed")
    current_native, current_manifest_ref = t111_preparation._source_manifest_identity(
        current_native_source_manifest_path
    )
    if current_native != T112_NATIVE_IDENTITY or any(
        current_manifest.get(field) != current_manifest_ref.get(field)
        for field in ("schema_id", "sha256", "size_bytes", "capabilities")
    ):
        raise T112WorkflowError("current native manifest is not the accepted T112 pin")
    t111_preparation_ref = prior.get("readiness_preparation_artifact")
    if t111_preparation_ref is None:
        raise T112WorkflowError("T111 predecessor source readiness is missing")
    t111_preparation_ref = _verify_ref(
        t111_preparation_ref,
        expected_schema="t111-execution-readiness-preparation-v1",
    )
    source_population = prior_qualification.get("source_population")
    if not isinstance(source_population, Mapping) or (
        source_population.get("record_count") != 413
        or source_population.get("source_counts") != T101_SOURCE_COUNTS
        or source_population.get("historical_t101_attempt_order_exact") is not True
    ):
        raise T112WorkflowError("exact T101 source order/population was not proven")
    t101_ref = _artifact_ref(
        t101_retention_manifest_path, schema_id="t101-terminal-retention-manifest-v1"
    )
    predecessor_ref = _artifact_ref(
        t111_retention_manifest_path,
        schema_id="t111-terminal-retention-manifest-v1",
    )
    repair_provenance = {
        "schema_id": T112_REPAIR_PROVENANCE_SCHEMA,
        "task_id": T112_TASK_ID,
        "implementation_head": head,
        "approved_spec_commit": T112_APPROVED_SPEC_COMMIT,
        "native_identity": dict(T112_NATIVE_IDENTITY),
        **T112_REPAIR_FACTS,
    }
    repair_ref = _write_new_json(
        artifact_root / "t112-validator-repair-provenance.json", repair_provenance
    )
    source_qualification = {
        "schema_id": T112_QUALIFICATION_SCHEMA,
        "task_id": T112_TASK_ID,
        "approved_spec_commit": T112_APPROVED_SPEC_COMMIT,
        "implementation_head": head,
        "implementation_worktree_path": str(repo_root.resolve(strict=True)),
        "historical_t111_implementation_head": t111_head,
        "eligible": True,
        "candidate_execution_started": False,
        "native_identity": dict(T112_NATIVE_IDENTITY),
        "validator_repair_provenance_artifact": repair_ref,
        "current_native_source_manifest": current_manifest_ref,
        "t101_terminal_retention_manifest": t101_ref,
        "t111_terminal_evidence": t111_terminal,
        "t111_source_qualification_artifact": prior_ref,
        "t111_readiness_artifact": t111_preparation_ref,
        "source_population": dict(source_population),
        "raw_bridge_reports": dict(t111_terminal["raw_bridge_reports"]),
        "candidate_execution_authorized": False,
        "terminal_classification": None,
    }
    qualification_ref = _write_new_json(
        artifact_root / "t112-input-qualification.json", source_qualification
    )
    readiness = {
        "schema_id": T112_PREPARATION_SCHEMA,
        "task_id": T112_TASK_ID,
        "preparation_only": True,
        "candidate_execution_authorized": False,
        "candidate_execution_started": False,
        "implementation_head": head,
        "approved_spec_commit": T112_APPROVED_SPEC_COMMIT,
        "native_identity": dict(T112_NATIVE_IDENTITY),
        "validator_repair_provenance_artifact": repair_ref,
        "qualification_artifact": qualification_ref,
        "qualification_sha256": qualification_ref["sha256"],
        "witness_status": "NOT_STARTED",
        "candidate_status": "BLOCKED_UNTIL_WITNESS_ACCEPTED",
        "frozen_configuration": {
            "source_counts": dict(T101_SOURCE_COUNTS),
            "particle_start": 0,
            "particle_count": 2,
            "replicate_index": 0,
            "search_simulations_per_particle": T101_SEARCH_SIMULATIONS,
            "include_potions": False,
            "policy_prior": False,
            "learned_leaf_value": False,
            "progressive_bias": False,
            "retry_count": 0,
        },
        "raw_t111_report_reuse": False,
        "next_action": "Maintainer separately authorizes the one-call native witness and its resource guard.",
    }
    readiness_ref = _write_new_json(
        artifact_root / "t112-readiness-preparation.json", readiness
    )
    manifest = {
        "schema_id": T112_PREPARATION_MANIFEST_SCHEMA,
        "task_id": T112_TASK_ID,
        "approved_spec_commit": T112_APPROVED_SPEC_COMMIT,
        "implementation_head": head,
        "terminal_classification": None,
        "candidate_execution_started": False,
        "artifact_references": {
            "qualification": qualification_ref,
            "readiness_preparation": readiness_ref,
            "validator_repair_provenance": repair_ref,
            "t101_retention_manifest": t101_ref,
            "t111_retention_manifest": predecessor_ref,
            "t111_source_qualification": prior_ref,
            "t111_readiness": t111_preparation_ref,
        },
        "retention_reason": "Bind exact T112 source qualification before witness authorization.",
        "deletion_condition": "Retain through T112 terminal review and provenance closeout.",
    }
    manifest_ref = _write_new_json(
        artifact_root / "t112-preparation-retention-manifest.json", manifest
    )
    return {
        "qualification": source_qualification,
        "qualification_artifact": qualification_ref,
        "readiness_preparation": readiness,
        "readiness_artifact": readiness_ref,
        "preparation_manifest_artifact": manifest_ref,
    }


def _validate_resource_plan(
    value: object, *, stage: str, resource_status_path: Path
) -> dict[str, object]:
    if not isinstance(value, Mapping):
        raise T112WorkflowError("T112 resource plan is missing")
    expected_stop = 1 if stage == "witness" else 413
    worker_count = value.get("effective_worker_count")
    shard_count = value.get("shard_count")
    shards = value.get("shards")
    if (
        isinstance(worker_count, bool)
        or worker_count != 1
        or isinstance(shard_count, bool)
        or shard_count != 1
        or not isinstance(shards, list)
        or len(shards) != 1
        or not isinstance(shards[0], Mapping)
    ):
        raise T112WorkflowError("T112 only authorizes one bounded serial target")
    shard = shards[0]
    required_shard_fields = (
        {"worker_id", "shard_id", "candidate_range"}
        if stage == "witness"
        else {"worker_id", "shard_id", "candidate_range", "stratum_ranges"}
    )
    if (
        set(shard) != required_shard_fields
        or shard.get("worker_id") != "worker-0"
        or shard.get("shard_id") != "shard-0"
        or shard.get("candidate_range") != [0, expected_stop]
    ):
        raise T112WorkflowError("T112 stage candidate range is not canonical")
    if stage == "cohort" and shard.get("stratum_ranges") != {
        "A": [0, 93],
        "B": [93, 285],
        "C": [285, 413],
    }:
        raise T112WorkflowError("T112 source stratum ranges are not canonical")
    guard = value.get("resource_guard")
    if not isinstance(guard, Mapping):
        raise T112WorkflowError("T112 detached resource guard is missing")
    for field in (
        "memory_budget_mib",
        "memory_request_mib",
        "runtime_rss_limit_mib",
        "runtime_memavailable_floor_mib",
    ):
        item = guard.get(field)
        if isinstance(item, bool) or not isinstance(item, int) or item <= 0:
            raise T112WorkflowError("T112 resource threshold is invalid")
    interval = guard.get("runtime_sample_seconds")
    if (
        isinstance(interval, bool)
        or not isinstance(interval, (int, float))
        or not math.isfinite(float(interval))
        or interval <= 0
        or guard.get("status_path") != str(resource_status_path.resolve())
        or not isinstance(guard.get("resource_root"), str)
        or not Path(str(guard.get("resource_root"))).is_dir()
        or not isinstance(guard.get("batch_id"), str)
        or not guard["batch_id"]
        or not isinstance(guard.get("job_id"), str)
        or not guard["job_id"]
        or guard["memory_request_mib"] > guard["memory_budget_mib"]
        or guard["runtime_rss_limit_mib"] > guard["memory_request_mib"]
    ):
        raise T112WorkflowError("T112 resource plan binding is inconsistent")
    return {**dict(value), "resource_guard": dict(guard)}


def validate_t112_stage_authorization(
    value: object,
    *,
    authorization_path: Path,
    stage: str,
    qualification_path: Path,
    readiness_path: Path,
    resource_status_path: Path,
    repo_root: Path,
    witness_terminal_path: Path | None = None,
) -> dict[str, object]:
    """Require independent exact-head approval for witness or cohort stage."""

    if stage not in _T112_STAGE_DECISIONS:
        raise T112WorkflowError("unknown T112 authorization stage")
    required = {
        "schema_id",
        "task_id",
        "stage",
        "authorization_id",
        "authorized",
        "decision",
        "approval",
        "implementation_worktree_path",
        "implementation_head",
        "approved_spec_commit",
        "qualification_artifact",
        "readiness_artifact",
        "native_identity",
        "native_source_manifest_artifact",
        "native_binary",
        "resource_plan",
    }
    if stage == "cohort":
        required.add("witness_terminal_artifact")
    if not isinstance(value, Mapping) or set(value) != required:
        raise T112WorkflowError("T112 authorization fields are malformed")
    head = value.get("implementation_head")
    if not isinstance(head, str) or len(head) != 40:
        raise T112WorkflowError("T112 authorization head is malformed")
    git_state = _verify_current_worktree(repo_root, head)
    approval = value.get("approval")
    if (
        value.get("schema_id") != T112_AUTH_SCHEMA
        or value.get("task_id") != T112_TASK_ID
        or value.get("stage") != stage
        or not isinstance(value.get("authorization_id"), str)
        or not value["authorization_id"].strip()
        or value.get("authorized") is not True
        or value.get("decision") != _T112_STAGE_DECISIONS[stage]
        or not isinstance(approval, Mapping)
        or set(approval)
        != {"kind", "reference", "approved_stage", "implementation_head", "decision"}
        or approval.get("kind") != "github_pr_comment"
        or not isinstance(approval.get("reference"), str)
        or not approval["reference"].startswith(_T112_PR_COMMENT_PREFIX)
        or not approval["reference"][len(_T112_PR_COMMENT_PREFIX) :].isdigit()
        or approval.get("approved_stage") != stage
        or approval.get("implementation_head") != head
        or approval.get("decision") != "APPROVED"
        or value.get("implementation_worktree_path")
        != str(repo_root.resolve(strict=True))
        or value.get("approved_spec_commit") != T112_APPROVED_SPEC_COMMIT
        or value.get("native_identity") != T112_NATIVE_IDENTITY
    ):
        raise T112WorkflowError("T112 authorization is not exact-head approved")
    qualification_ref = _verify_ref(
        value.get("qualification_artifact"),
        expected_schema=T112_QUALIFICATION_SCHEMA,
        expected_path=qualification_path,
    )
    readiness_ref = _verify_ref(
        value.get("readiness_artifact"),
        expected_schema=T112_PREPARATION_SCHEMA,
        expected_path=readiness_path,
    )
    qualification = _read_json(qualification_path, label="T112 input qualification")
    readiness = _read_json(readiness_path, label="T112 readiness preparation")
    repair_ref = _verify_repair_provenance(
        qualification, readiness, implementation_head=head
    )
    source_population = qualification.get("source_population")
    if not isinstance(source_population, Mapping):
        raise T112WorkflowError("T112 exact source population is malformed")
    if (
        qualification.get("eligible") is not True
        or qualification.get("candidate_execution_started") is not False
        or qualification.get("implementation_head") != head
        or qualification.get("implementation_worktree_path")
        != str(repo_root.resolve(strict=True))
        or qualification.get("approved_spec_commit") != T112_APPROVED_SPEC_COMMIT
        or qualification.get("native_identity") != T112_NATIVE_IDENTITY
        or source_population.get("record_count") != 413
        or source_population.get("source_counts") != T101_SOURCE_COUNTS
        or source_population.get("historical_t101_attempt_order_exact") is not True
        or qualification.get("raw_bridge_reports")
        != {
            "eligible_for_reuse": False,
            "reason": T112_RAW_REPORTS_INELIGIBLE,
            "candidate_rows_with_null_bridge_report_sha256": 413,
            "historical_exclusion_labels_used_for_admission": False,
        }
        or readiness.get("schema_id") != T112_PREPARATION_SCHEMA
        or readiness.get("task_id") != T112_TASK_ID
        or readiness.get("preparation_only") is not True
        or readiness.get("candidate_execution_started") is not False
        or readiness.get("implementation_head") != head
        or readiness.get("approved_spec_commit") != T112_APPROVED_SPEC_COMMIT
        or readiness.get("qualification_sha256") != qualification_ref["sha256"]
        or readiness.get("validator_repair_provenance_artifact") != repair_ref
        or readiness.get("candidate_execution_authorized") is not False
        or readiness.get("raw_t111_report_reuse") is not False
        or readiness.get("frozen_configuration")
        != {
            "source_counts": dict(T101_SOURCE_COUNTS),
            "particle_start": 0,
            "particle_count": 2,
            "replicate_index": 0,
            "search_simulations_per_particle": T101_SEARCH_SIMULATIONS,
            "include_potions": False,
            "policy_prior": False,
            "learned_leaf_value": False,
            "progressive_bias": False,
            "retry_count": 0,
        }
    ):
        raise T112WorkflowError("T112 qualification/readiness binding is invalid")
    source_ref = _verify_ref(
        value.get("native_source_manifest_artifact"),
        expected_schema="sts-lightspeed-source-manifest-v1",
        expected_path=Path(
            str(qualification["current_native_source_manifest"]["path"])
        ),
    )
    current_source = qualification["current_native_source_manifest"]
    if source_ref["sha256"] != current_source.get("sha256"):
        raise T112WorkflowError("T112 native source manifest binding changed")
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
        raise T112WorkflowError("T112 native binary binding is malformed")
    try:
        runtime = t111_preparation._python_runtime_fingerprint()
        binary_path = t111_preparation._validate_native_binary_abi_path(
            Path(str(binary["path"])), runtime
        )
        binary_sha = _sha256_file(binary_path)
        binary_size = binary_path.stat().st_size
    except (OSError, t111_preparation.T111QualificationError) as exc:
        raise T112WorkflowError("authorized T112 native binary is unavailable") from exc
    if (
        str(binary_path) != binary["path"]
        or binary_sha != binary["sha256"]
        or binary_size != binary["size_bytes"]
    ):
        raise T112WorkflowError("T112 native binary differs from exact approval")
    resource_plan = _validate_resource_plan(
        value.get("resource_plan"),
        stage=stage,
        resource_status_path=resource_status_path,
    )
    witness_terminal: dict[str, object] | None = None
    if stage == "cohort":
        if witness_terminal_path is None:
            raise T112WorkflowError("T112 candidate stage lacks witness binding")
        witness_ref = _verify_ref(
            value.get("witness_terminal_artifact"),
            expected_schema=T112_WITNESS_TERMINAL_SCHEMA,
            expected_path=witness_terminal_path,
        )
        witness_terminal = _read_json(
            witness_terminal_path, label="T112 exact-native witness terminal"
        )
        if (
            witness_terminal.get("witness_status") != "ACCEPTED"
            or witness_terminal.get("terminal_classification") is not None
            or witness_terminal.get("implementation_head") != head
            or witness_terminal.get("approved_spec_commit") != T112_APPROVED_SPEC_COMMIT
            or witness_terminal.get("native_identity") != T112_NATIVE_IDENTITY
            or witness_terminal.get("native_binary") != dict(binary)
            or witness_terminal.get("native_source_manifest_artifact") != source_ref
            or witness_terminal.get("qualification_artifact") != qualification_ref
            or witness_terminal.get("bridge_call_count") != 1
            or witness_terminal.get("retry_count") != 0
            or witness_ref["sha256"] != value["witness_terminal_artifact"].get("sha256")
        ):
            raise T112WorkflowError("T112 exact-native witness gate has not passed")
    return {
        "authorization": dict(value),
        "qualification": qualification,
        "readiness": readiness,
        "qualification_artifact": qualification_ref,
        "readiness_artifact": readiness_ref,
        "native_source_manifest_artifact": source_ref,
        "native_binary": dict(binary),
        "resource_plan": resource_plan,
        "witness_terminal": witness_terminal,
        "local_git_state": git_state,
        "authorization_sha256": _sha256_file(authorization_path),
        "authorization_artifact": _artifact_ref(
            authorization_path, schema_id=T112_AUTH_SCHEMA
        ),
    }


def _source_records_for_run(
    validated: Mapping[str, object], *, t101_manifest_path: Path
) -> tuple[
    list[dict[str, object]],
    Mapping[str, Mapping[str, object]],
    Mapping[str, object],
    dict[str, object],
]:
    qualification = validated["qualification"]
    assert isinstance(qualification, Mapping)
    _verify_ref(
        qualification.get("t101_terminal_retention_manifest"),
        expected_schema="t101-terminal-retention-manifest-v1",
        expected_path=t101_manifest_path,
    )
    historical_terminal = qualification.get("t111_terminal_evidence")
    if not isinstance(historical_terminal, Mapping):
        raise T112WorkflowError("T112 qualification lacks T111 terminal binding")
    t111_terminal_path = Path(str(historical_terminal["retention_manifest"]["path"]))
    if _verify_t111_terminal_inputs(t111_terminal_path) != historical_terminal:
        raise T112WorkflowError("retained T111 terminal inputs changed")
    t111_ref = qualification.get("t111_source_qualification_artifact")
    t111_ref = _verify_ref(t111_ref, expected_schema="t111-input-qualification-v1")
    t111_qualification = _read_json(
        Path(str(t111_ref["path"])), label="revalidated T101/T085 source qualification"
    )
    if (
        t111_qualification.get("eligible") is not True
        or t111_qualification.get("candidate_execution_started") is not False
        or t111_qualification.get("implementation_head")
        != qualification.get("historical_t111_implementation_head")
    ):
        raise T112WorkflowError("T111 source qualification no longer binds inputs")
    rows, _gate, canonical, selected, provenance = (
        t111_execution._reload_qualified_inputs(
            qualification=t111_qualification,
            t101_manifest_path=t101_manifest_path,
            head=str(qualification["historical_t111_implementation_head"]),
        )
    )
    if (
        len(rows) != 413
        or provenance["source_population"] != qualification.get("source_population")
        or provenance["source_population"].get("source_counts") != T101_SOURCE_COUNTS
    ):
        raise T112WorkflowError("reloaded T112 source population is not exact T101")
    return rows, canonical, selected, provenance


def _adapter_factory_for_binary(binary: Mapping[str, object]):
    module = t111_execution._load_native_module(
        Path(str(binary["path"])), str(binary["sha256"])
    )
    from sts_combat_rl.sim.lightspeed import LightSpeedAdapter

    active: list[Any] = []

    def create() -> Any:
        adapter = LightSpeedAdapter(
            seed=1, ascension=20, player_class="IRONCLAD", module=module
        )
        active.append(adapter)
        return adapter

    return create, active


def _runner_for(
    validated: Mapping[str, object],
    *,
    t101_manifest_path: Path,
    bridge_call_counts: dict[str, int],
):
    rows, canonical, selected, provenance = _source_records_for_run(
        validated, t101_manifest_path=t101_manifest_path
    )
    factory, active = _adapter_factory_for_binary(validated["native_binary"])
    runner = t111_runner_module.T111NativeRecordRunner(
        adapter_factory=factory,
        selected_records=selected,
        canonical_records_by_stratum=canonical,
        native_identity=T112_NATIVE_IDENTITY,
        on_bridge_call=lambda identity: bridge_call_counts.__setitem__(
            identity, bridge_call_counts.get(identity, 0) + 1
        ),
    )
    return rows, runner, active, provenance


def _active_guard(
    validated: Mapping[str, object], *, resource_status_path: Path
) -> dict[str, object]:
    return t111_execution._verify_active_resource_guard(
        resource_status_path, authorization=validated, target_pid=os.getpid()
    )


def _base_execution_record(
    *,
    validated: Mapping[str, object],
    stage: str,
    resource_status_path: Path,
    active_guard_snapshot: Mapping[str, object],
) -> dict[str, object]:
    authorization = validated["authorization"]
    resource_plan = validated["resource_plan"]
    assert isinstance(authorization, Mapping) and isinstance(resource_plan, Mapping)
    guard = resource_plan["resource_guard"]
    return {
        "target_pid": os.getpid(),
        "stage": stage,
        "authorization_id": authorization["authorization_id"],
        "authorization_sha256": validated["authorization_sha256"],
        "authorization_artifact": dict(validated["authorization_artifact"]),
        "implementation_head": authorization["implementation_head"],
        "approved_spec_commit": T112_APPROVED_SPEC_COMMIT,
        "native_identity": dict(T112_NATIVE_IDENTITY),
        "native_binary": dict(validated["native_binary"]),
        "native_source_manifest_artifact": dict(
            validated["native_source_manifest_artifact"]
        ),
        "qualification_artifact": dict(validated["qualification_artifact"]),
        "readiness_artifact": dict(validated["readiness_artifact"]),
        "resource_guard_plan": dict(guard),
        "resource_guard_status_path": str(resource_status_path.resolve()),
        "resource_guard_observations": [dict(active_guard_snapshot)],
        "candidate_execution_started": stage == "cohort",
        "candidate_execution_completed": False,
    }


def execute_t112_witness(
    *,
    authorization_path: Path,
    qualification_path: Path,
    readiness_path: Path,
    resource_status_path: Path,
    t101_manifest_path: Path,
    witness_output_root: Path,
    repo_root: Path,
) -> dict[str, object]:
    """Make one deterministic exact-native N=2 call; never invoke selector."""

    if os.name == "nt":
        raise T112WorkflowError("T112 native witness must run under WSL/POSIX guard")
    if witness_output_root.exists():
        raise T112WorkflowError("refusing to overwrite T112 witness outputs")
    auth = _read_json(authorization_path, label="T112 witness authorization")
    validated = validate_t112_stage_authorization(
        auth,
        authorization_path=authorization_path,
        stage="witness",
        qualification_path=qualification_path,
        readiness_path=readiness_path,
        resource_status_path=resource_status_path,
        repo_root=repo_root,
    )
    guard = _active_guard(validated, resource_status_path=resource_status_path)
    bridge_call_counts: dict[str, int] = {}
    rows, runner, active, provenance = _runner_for(
        validated,
        t101_manifest_path=t101_manifest_path,
        bridge_call_counts=bridge_call_counts,
    )
    first_a = min(
        (row for row in rows if row.get("cohort", row.get("stratum")) == "A"),
        key=lambda row: (
            hashlib.sha256(str(row["selection_identity"]).encode("utf-8")).hexdigest(),
            str(row["selection_identity"]),
        ),
    )
    identity = str(first_a["selection_identity"])
    requested_seed = derive_t101_sampler_seed(identity, 0)
    record = _base_execution_record(
        validated=validated,
        stage="witness",
        resource_status_path=resource_status_path,
        active_guard_snapshot=guard,
    )
    started = time.monotonic()
    witness_result: dict[str, object] = {
        "schema_id": T112_WITNESS_SCHEMA,
        "task_id": T112_TASK_ID,
        "implementation_head": validated["authorization"]["implementation_head"],
        "approved_spec_commit": T112_APPROVED_SPEC_COMMIT,
        "authorization_id": validated["authorization"]["authorization_id"],
        "native_identity": dict(T112_NATIVE_IDENTITY),
        "source_identity": {
            "selection_identity": identity,
            "stratum": "A",
            "selection_digest": hashlib.sha256(identity.encode("utf-8")).hexdigest(),
        },
        "frozen_configuration": {
            "particle_start": 0,
            "particle_count": 2,
            "replicate_index": 0,
            "search_simulations_per_particle": 400,
            "include_potions": False,
            "policy_prior": False,
            "learned_leaf_value": False,
            "progressive_bias": False,
        },
        "requested_sampler_seed_input": requested_seed,
        "bridge_call_count": 0,
        "retry_count": 0,
        "witness_status": "REJECTED",
        "validator": "validate_t111_configured_search_report",
        "safe_seed_metadata": None,
        "support_summary": None,
        "bridge_report_sha256": None,
        "failure_type": None,
        "candidate_selector_invoked": False,
        "provenance": provenance,
    }
    try:
        try:
            observed = runner(first_a)
        finally:
            if active:
                active.pop().close()
        report = observed.get("bridge_report")
        summary = observed.get("support_summary")
        if not isinstance(report, Mapping) or not isinstance(summary, Mapping):
            raise T112WorkflowError(
                "corrected T111 validator returned no report summary"
            )
        report_sha = str(summary.get("bridge_report_sha256", ""))
        safe_seed = safe_t112_seed_metadata(
            report,
            expected_sampler_seed=requested_seed,
            bridge_report_sha256=report_sha,
        )
        witness_result.update(
            {
                "witness_status": "ACCEPTED",
                "observed_sampler_seed_input": report["sampler_seed_input"],
                "safe_seed_metadata": safe_seed,
                "support_summary": {
                    "searched_occurrence_count_per_particle": summary[
                        "searched_occurrence_count_per_particle"
                    ],
                    "configuration_excluded_occurrence_count_per_particle": summary[
                        "configuration_excluded_occurrence_count_per_particle"
                    ],
                    "configured_search_decision_class_count": summary[
                        "configured_search_decision_class_count"
                    ],
                    "searched_excluded_classification_and_partition_stable": summary[
                        "searched_excluded_classification_and_partition_stable"
                    ],
                    "all_searched_occurrences_finite_and_visited": summary[
                        "all_searched_occurrences_finite_and_visited"
                    ],
                    "all_search_edges_covered": summary["all_search_edges_covered"],
                },
                "bridge_report_sha256": report_sha,
            }
        )
    except T111SupportExclusion as exc:
        witness_result["failure_type"] = type(exc).__name__
    except Exception as exc:  # noqa: BLE001 - retain only safe type, not payload
        witness_result["failure_type"] = type(exc).__name__[:120]
    witness_result["bridge_call_count"] = bridge_call_counts.get(identity, 0)
    if witness_result["bridge_call_count"] != 1:
        witness_result["witness_status"] = "REJECTED"
        witness_result["safe_seed_metadata"] = None
        witness_result["support_summary"] = None
        witness_result["bridge_report_sha256"] = None
    witness_result["wall_clock_time_s"] = max(0.0, time.monotonic() - started)
    witness_ref = _write_new_json(
        witness_output_root / "t112-native-witness.json", witness_result
    )
    record.update(
        {
            "schema_id": T112_WITNESS_RECORD_SCHEMA,
            "task_id": T112_TASK_ID,
            "candidate_execution_started": False,
            "candidate_execution_completed": False,
            "bridge_call_count": witness_result["bridge_call_count"],
            "retry_count": 0,
            "witness_artifact": witness_ref,
            "witness_status": witness_result["witness_status"],
            "executor": {
                "effective_worker_count": 1,
                "shard_count": 1,
                "shards": [
                    {
                        "worker_id": "worker-0",
                        "shard_id": "shard-0",
                        "candidate_range": [0, 1],
                    }
                ],
            },
            "wall_clock_time_s": witness_result["wall_clock_time_s"],
            "provenance": provenance,
        }
    )
    record_ref = _write_new_json(
        witness_output_root / "t112-witness-execution-record.json", record
    )
    return {"witness_artifact": witness_ref, "witness_execution_record": record_ref}


def _validate_t112_guard_status(
    status_path: Path, *, execution_record: Mapping[str, object]
) -> tuple[Mapping[str, object], Mapping[str, object]]:
    status = _read_json(status_path, label="T112 detached guard status")
    return t111_execution._validate_completed_resource_guard(status, execution_record)


def finalize_t112_witness(
    *, witness_output_root: Path, resource_status_path: Path
) -> dict[str, object]:
    """Close the witness guard before emitting a candidate-stage gate."""

    witness_path = witness_output_root / "t112-native-witness.json"
    record_path = witness_output_root / "t112-witness-execution-record.json"
    witness = _read_json(witness_path, label="T112 native witness")
    record = _read_json(record_path, label="T112 witness execution record")
    witness_ref = _artifact_ref(witness_path, schema_id=T112_WITNESS_SCHEMA)
    if (
        record.get("schema_id") != T112_WITNESS_RECORD_SCHEMA
        or record.get("task_id") != T112_TASK_ID
        or record.get("stage") != "witness"
        or isinstance(record.get("bridge_call_count"), bool)
        or not isinstance(record.get("bridge_call_count"), int)
        or record.get("bridge_call_count") not in {0, 1}
        or isinstance(record.get("retry_count"), bool)
        or not isinstance(record.get("retry_count"), int)
        or record.get("retry_count") != 0
        or record.get("witness_artifact") != witness_ref
        or record.get("resource_guard_status_path")
        != str(resource_status_path.resolve())
        or witness.get("schema_id") != T112_WITNESS_SCHEMA
        or witness.get("candidate_selector_invoked") is not False
        or isinstance(witness.get("bridge_call_count"), bool)
        or not isinstance(witness.get("bridge_call_count"), int)
        or witness.get("bridge_call_count") not in {0, 1}
        or record.get("bridge_call_count") != witness.get("bridge_call_count")
        or isinstance(witness.get("retry_count"), bool)
        or not isinstance(witness.get("retry_count"), int)
        or witness.get("retry_count") != 0
    ):
        raise T112WorkflowError("T112 witness execution record is inconsistent")
    _admission, guard = _validate_t112_guard_status(
        resource_status_path, execution_record=record
    )
    accepted = (
        witness.get("witness_status") == "ACCEPTED"
        and not isinstance(witness.get("bridge_call_count"), bool)
        and isinstance(witness.get("bridge_call_count"), int)
        and witness.get("bridge_call_count") == 1
        and not isinstance(witness.get("requested_sampler_seed_input"), bool)
        and isinstance(witness.get("requested_sampler_seed_input"), int)
        and not isinstance(witness.get("observed_sampler_seed_input"), bool)
        and isinstance(witness.get("observed_sampler_seed_input"), int)
        and witness.get("observed_sampler_seed_input")
        == witness.get("requested_sampler_seed_input")
        and not isinstance(witness.get("retry_count"), bool)
        and isinstance(witness.get("retry_count"), int)
        and witness.get("retry_count") == 0
        and isinstance(witness.get("safe_seed_metadata"), Mapping)
        and guard.get("state") == "COMPLETED"
    )
    authorization_ref = _verify_ref(
        record.get("authorization_artifact"), expected_schema=T112_AUTH_SCHEMA
    )
    authorization = _read_json(
        Path(str(authorization_ref["path"])), label="T112 witness authorization"
    )
    if (
        authorization.get("stage") != "witness"
        or authorization.get("authorization_id") != record.get("authorization_id")
        or authorization_ref.get("sha256") != record.get("authorization_sha256")
        or authorization.get("implementation_head") != record.get("implementation_head")
    ):
        raise T112WorkflowError("T112 witness authorization binding changed")
    terminal = None if accepted else "SAMPLER_SEED_CONTRACT_REPAIR_INVALID"
    terminal_doc = {
        "schema_id": T112_WITNESS_TERMINAL_SCHEMA,
        "task_id": T112_TASK_ID,
        "implementation_head": witness.get("implementation_head"),
        "approved_spec_commit": T112_APPROVED_SPEC_COMMIT,
        "native_identity": dict(T112_NATIVE_IDENTITY),
        "native_binary": record["native_binary"],
        "native_source_manifest_artifact": record["native_source_manifest_artifact"],
        "qualification_artifact": record["qualification_artifact"],
        "readiness_artifact": record["readiness_artifact"],
        "witness_authorization": authorization_ref,
        "witness_artifact": witness_ref,
        "witness_execution_record": _artifact_ref(
            record_path, schema_id=T112_WITNESS_RECORD_SCHEMA
        ),
        "witness_status": "ACCEPTED" if accepted else "REJECTED",
        "terminal_classification": terminal,
        "bridge_call_count": witness.get("bridge_call_count"),
        "retry_count": 0,
        "resource_guard_observation": {
            key: guard.get(key)
            for key in (
                "state",
                "sample_count",
                "peak_rss_mib",
                "lowest_memavailable_mib",
                "rss_limit_mib",
                "memavailable_floor_mib",
                "sample_interval_seconds",
            )
        },
        "candidate_execution_authorized": False,
    }
    terminal_ref = _write_new_json(
        witness_output_root / "t112-witness-terminal.json", terminal_doc
    )
    return {"witness_terminal": terminal_doc, "witness_terminal_artifact": terminal_ref}


def _t112_attempt_row(
    row: Mapping[str, object],
    *,
    seed_metadata_by_identity: Mapping[str, Mapping[str, object]],
    bridge_call_count_by_identity: Mapping[str, int],
    shard: Mapping[str, object],
) -> dict[str, object]:
    copied = dict(row)
    identity = str(copied.pop("selection_identity"))
    copied["selection_identity"] = identity
    copied["task_id"] = T112_TASK_ID
    copied["sampler_seed_input"] = copied.pop("sampler_seed")
    copied["particle_sampler_seed_metadata"] = dict(
        seed_metadata_by_identity.get(
            identity,
            {
                "schema_id": None,
                "bridge_report_sha256": None,
                "sampler_seed_input": None,
                "particles": None,
            },
        )
    )
    copied["native_bridge_call_count"] = bridge_call_count_by_identity.get(identity, 0)
    copied.update(
        {
            "worker_id": shard["worker_id"],
            "shard_id": shard["shard_id"],
            "shard_candidate_range": list(shard["candidate_range"]),
            "executor_attempt_status": (
                "ADMITTED" if row.get("admitted") is True else "EXCLUDED_NO_RETRY"
            ),
            "historical_t111_row_reused": False,
        }
    )
    return copied


def execute_t112_authorized_cohort(
    *,
    authorization_path: Path,
    qualification_path: Path,
    readiness_path: Path,
    witness_terminal_path: Path,
    resource_status_path: Path,
    t101_manifest_path: Path,
    cohort_output_root: Path,
    repo_root: Path,
) -> dict[str, object]:
    """Run the source-order T111 selector only after accepted witness and auth."""

    if os.name == "nt":
        raise T112WorkflowError("T112 cohort execution must run under WSL/POSIX guard")
    if cohort_output_root.exists():
        raise T112WorkflowError("refusing to overwrite T112 cohort outputs")
    auth = _read_json(authorization_path, label="T112 cohort authorization")
    validated = validate_t112_stage_authorization(
        auth,
        authorization_path=authorization_path,
        stage="cohort",
        qualification_path=qualification_path,
        readiness_path=readiness_path,
        resource_status_path=resource_status_path,
        repo_root=repo_root,
        witness_terminal_path=witness_terminal_path,
    )
    guard = _active_guard(validated, resource_status_path=resource_status_path)
    bridge_call_counts: dict[str, int] = {}
    source_rows, runner, active, provenance = _runner_for(
        validated,
        t101_manifest_path=t101_manifest_path,
        bridge_call_counts=bridge_call_counts,
    )
    plan = validated["resource_plan"]
    shard = plan["shards"][0]
    attempts_path = cohort_output_root / "t112-candidate-attempts.jsonl"
    _write_jsonl_new(attempts_path)
    record = _base_execution_record(
        validated=validated,
        stage="cohort",
        resource_status_path=resource_status_path,
        active_guard_snapshot=guard,
    )
    seed_metadata_by_identity: dict[str, Mapping[str, object]] = {}
    active_guard_snapshots = [guard]
    started = time.monotonic()

    def admit_one(source_record: Mapping[str, object]) -> Mapping[str, object]:
        identity = str(source_record.get("selection_identity", ""))
        try:
            result = runner(source_record)
            report = result.get("bridge_report")
            summary = result.get("support_summary")
            expected_seed = derive_t101_sampler_seed(identity, 0)
            if not isinstance(summary, Mapping):
                raise T112WorkflowError(
                    "T112 bridge report lacks strict support summary"
                )
            metadata = safe_t112_seed_metadata(
                report,
                expected_sampler_seed=expected_seed,
                bridge_report_sha256=str(summary.get("bridge_report_sha256", "")),
            )
            seed_metadata_by_identity[identity] = metadata
            return result
        finally:
            if active:
                active.pop().close()

    def retain(row: Mapping[str, object]) -> None:
        if not isinstance(row, Mapping):
            raise T112WorkflowError("T112 selector emitted malformed attempt")
        record_row = _t112_attempt_row(
            row,
            seed_metadata_by_identity=seed_metadata_by_identity,
            bridge_call_count_by_identity=bridge_call_counts,
            shard=shard,
        )
        _append_jsonl(attempts_path, record_row)
        active_guard_snapshots.append(
            _active_guard(validated, resource_status_path=resource_status_path)
        )

    try:
        selector_cohort = select_t111_configured_search_cohort(
            source_rows,
            native_identity=validated["authorization"]["native_identity"],
            admit=admit_one,
            on_attempt=retain,
        )
        selector_cohort = validate_t111_configured_search_cohort(selector_cohort)
        witness_ref = _artifact_ref(
            witness_terminal_path, schema_id=T112_WITNESS_TERMINAL_SCHEMA
        )
        cohort = t112_cohort_from_t111(
            selector_cohort,
            implementation_head=str(validated["authorization"]["implementation_head"]),
            witness_sha256=str(witness_ref["sha256"]),
            seed_metadata_by_identity=seed_metadata_by_identity,
            bridge_call_count_by_identity=bridge_call_counts,
        )
        cohort = validate_t112_cohort(cohort)
        cohort_ref = _write_new_json(
            cohort_output_root / "t112-cohort-admission.json", cohort
        )
        attempts_ref = _artifact_ref(
            attempts_path, schema_id="t112-candidate-attempts-jsonl-v1"
        )
        durations = [float(row["wall_clock_time_s"]) for row in cohort["attempted"]]
        exclusions = Counter(
            str(row["exclusion_reason"])
            for row in cohort["attempted"]
            if row.get("admitted") is False
        )
        record.update(
            {
                "schema_id": T112_EXECUTION_RECORD_SCHEMA,
                "task_id": T112_TASK_ID,
                "witness_terminal_artifact": witness_ref,
                "candidate_execution_started": True,
                "candidate_execution_completed": True,
                "executor": {
                    "effective_worker_count": 1,
                    "shard_count": 1,
                    "shards": [dict(shard)],
                    "attempted_count": len(cohort["attempted"]),
                    "attempted_wall_clock_total_s": sum(durations),
                    "attempted_wall_clock_max_s": max(durations, default=0.0),
                    "attempted_wall_clock_min_s": min(durations, default=0.0),
                    "whole_selector_wall_clock_s": max(0.0, time.monotonic() - started),
                    "no_retry_attempt_count": len(cohort["attempted"]),
                    "exclusion_counts": dict(sorted(exclusions.items())),
                    "resource_guard_observations_during_execution": active_guard_snapshots,
                },
                "resource_guard_plan": dict(plan["resource_guard"]),
                "resource_guard_status_path": str(resource_status_path.resolve()),
                "input_provenance": provenance,
                "t101_source_identity_count": len(source_rows),
                "attempt_artifact": attempts_ref,
                "cohort_admission_artifact": cohort_ref,
                "terminal_classification": cohort["terminal_classification"],
            }
        )
        record_ref = _write_new_json(
            cohort_output_root / "t112-execution-record.json", record
        )
        return {
            "execution_record": record,
            "execution_record_artifact": record_ref,
            "attempt_artifact": attempts_ref,
            "cohort_admission_artifact": cohort_ref,
        }
    except BaseException as exc:  # noqa: BLE001 - retain exact partial evidence
        interruption = {
            "schema_id": T112_INTERRUPTION_SCHEMA,
            "task_id": T112_TASK_ID,
            "implementation_head": validated["authorization"]["implementation_head"],
            "authorization_id": validated["authorization"]["authorization_id"],
            "state": "INCOMPLETE",
            "terminal_classification": None,
            "candidate_execution_started": attempts_path.stat().st_size > 0,
            "exception_type": type(exc).__name__[:120],
            "attempt_artifact": _artifact_ref(
                attempts_path, schema_id="t112-candidate-attempts-jsonl-v1"
            ),
        }
        try:
            _write_new_json(
                cohort_output_root / "t112-execution-interruption.json", interruption
            )
        finally:
            raise


def _verify_jsonl_matches_t112_cohort(
    *,
    attempts_path: Path,
    attempt_ref: Mapping[str, object],
    cohort: Mapping[str, object],
    record: Mapping[str, object],
) -> None:
    verified = _verify_ref(
        attempt_ref,
        expected_schema="t112-candidate-attempts-jsonl-v1",
        expected_path=attempts_path,
    )
    actual = _read_jsonl(attempts_path, label="T112 candidate attempt JSONL")
    executor = record.get("executor")
    shards = executor.get("shards") if isinstance(executor, Mapping) else None
    if (
        not isinstance(shards, list)
        or len(shards) != 1
        or not isinstance(shards[0], Mapping)
    ):
        raise T112WorkflowError("T112 executor shard record is malformed")
    shard = shards[0]
    expected: list[dict[str, object]] = []
    for row in cohort["attempted"]:
        value = dict(row)
        value.update(
            {
                "worker_id": shard["worker_id"],
                "shard_id": shard["shard_id"],
                "shard_candidate_range": list(shard["candidate_range"]),
                "executor_attempt_status": (
                    "ADMITTED" if row.get("admitted") is True else "EXCLUDED_NO_RETRY"
                ),
                "historical_t111_row_reused": False,
            }
        )
        expected.append(value)
    if actual != expected or verified["sha256"] != attempt_ref.get("sha256"):
        raise T112WorkflowError("T112 attempt JSONL and cohort differ")


def finalize_t112_execution(
    *, cohort_output_root: Path, resource_status_path: Path
) -> dict[str, object]:
    """Verify completed cohort, guard, all hashes and write final/retention schemas."""

    record_path = cohort_output_root / "t112-execution-record.json"
    record = _read_json(record_path, label="T112 execution record")
    if (
        record.get("schema_id") != T112_EXECUTION_RECORD_SCHEMA
        or record.get("task_id") != T112_TASK_ID
        or record.get("resource_guard_status_path")
        != str(resource_status_path.resolve())
        or record.get("candidate_execution_completed") is not True
        or record.get("implementation_head") is None
        or record.get("approved_spec_commit") != T112_APPROVED_SPEC_COMMIT
        or record.get("native_identity") != T112_NATIVE_IDENTITY
        or record.get("terminal_classification")
        not in T112_TERMINALS - {"SAMPLER_SEED_CONTRACT_REPAIR_INVALID"}
    ):
        raise T112WorkflowError(
            "T112 execution record is not a valid completed terminal"
        )
    plan = record.get("resource_guard_plan")
    executor = record.get("executor")
    if not isinstance(plan, Mapping) or not isinstance(executor, Mapping):
        raise T112WorkflowError("T112 execution/resource record is incomplete")
    status = _read_json(
        resource_status_path, label="T112 terminal resource guard status"
    )
    admission, guard = t111_execution._validate_completed_resource_guard(status, record)
    qualification_ref = _verify_ref(
        record.get("qualification_artifact"),
        expected_schema=T112_QUALIFICATION_SCHEMA,
    )
    readiness_ref = _verify_ref(
        record.get("readiness_artifact"), expected_schema=T112_PREPARATION_SCHEMA
    )
    qualification = _read_json(
        Path(str(qualification_ref["path"])), label="T112 terminal qualification"
    )
    readiness = _read_json(
        Path(str(readiness_ref["path"])), label="T112 terminal readiness"
    )
    repair_ref = _verify_repair_provenance(
        qualification,
        readiness,
        implementation_head=str(record.get("implementation_head")),
    )
    preparation_manifest_path = (
        Path(str(qualification_ref["path"])).parent
        / "t112-preparation-retention-manifest.json"
    )
    preparation_manifest_ref = _artifact_ref(
        preparation_manifest_path, schema_id=T112_PREPARATION_MANIFEST_SCHEMA
    )
    preparation_manifest = _read_json(
        preparation_manifest_path, label="T112 preparation retention manifest"
    )
    authorization_ref = _verify_ref(
        record.get("authorization_artifact"), expected_schema=T112_AUTH_SCHEMA
    )
    authorization = _read_json(
        Path(str(authorization_ref["path"])), label="T112 cohort authorization"
    )
    preparation_references = preparation_manifest.get("artifact_references")
    if not isinstance(preparation_references, Mapping):
        raise T112WorkflowError("T112 preparation manifest references are missing")
    t111_terminal_evidence = qualification.get("t111_terminal_evidence")
    if not isinstance(t111_terminal_evidence, Mapping):
        raise T112WorkflowError("T112 qualification lost T111 predecessor evidence")
    t111_retention_ref = t111_terminal_evidence.get("retention_manifest")
    if (
        qualification.get("implementation_head") != record.get("implementation_head")
        or qualification.get("approved_spec_commit") != T112_APPROVED_SPEC_COMMIT
        or qualification.get("native_identity") != T112_NATIVE_IDENTITY
        or readiness.get("implementation_head") != record.get("implementation_head")
        or readiness.get("qualification_sha256") != qualification_ref["sha256"]
        or preparation_manifest.get("schema_id") != T112_PREPARATION_MANIFEST_SCHEMA
        or preparation_manifest.get("implementation_head")
        != record.get("implementation_head")
        or preparation_manifest.get("artifact_references", {}).get("qualification")
        != qualification_ref
        or preparation_manifest.get("artifact_references", {}).get(
            "readiness_preparation"
        )
        != readiness_ref
        or preparation_references.get("t101_retention_manifest")
        != qualification.get("t101_terminal_retention_manifest")
        or preparation_references.get("validator_repair_provenance") != repair_ref
        or preparation_references.get("t111_retention_manifest") != t111_retention_ref
        or preparation_references.get("t111_source_qualification")
        != qualification.get("t111_source_qualification_artifact")
        or preparation_references.get("t111_readiness")
        != qualification.get("t111_readiness_artifact")
        or authorization.get("stage") != "cohort"
        or authorization.get("authorization_id") != record.get("authorization_id")
        or authorization.get("implementation_head") != record.get("implementation_head")
        or authorization.get("native_identity") != T112_NATIVE_IDENTITY
        or authorization.get("native_binary") != record.get("native_binary")
        or authorization.get("native_source_manifest_artifact")
        != record.get("native_source_manifest_artifact")
        or authorization.get("qualification_artifact") != qualification_ref
        or authorization.get("readiness_artifact") != readiness_ref
        or not isinstance(authorization.get("resource_plan"), Mapping)
        or authorization["resource_plan"].get("resource_guard")
        != record.get("resource_guard_plan")
    ):
        raise T112WorkflowError("T112 terminal head/authorization binding changed")
    t111_manifest_path = Path(
        str(qualification["t111_terminal_evidence"]["retention_manifest"]["path"])
    )
    t111_terminal = _verify_t111_terminal_inputs(t111_manifest_path)
    if t111_terminal != qualification["t111_terminal_evidence"]:
        raise T112WorkflowError("T111 predecessor evidence changed after qualification")
    attempt_ref = record.get("attempt_artifact")
    cohort_ref = record.get("cohort_admission_artifact")
    witness_ref = record.get("witness_terminal_artifact")
    if (
        not isinstance(attempt_ref, Mapping)
        or not isinstance(cohort_ref, Mapping)
        or not isinstance(witness_ref, Mapping)
    ):
        raise T112WorkflowError("T112 execution record lacks retained output refs")
    witness_ref = _verify_ref(witness_ref, expected_schema=T112_WITNESS_TERMINAL_SCHEMA)
    witness = _read_json(Path(str(witness_ref["path"])), label="T112 witness gate")
    witness_record_ref = _verify_ref(
        witness.get("witness_execution_record"),
        expected_schema=T112_WITNESS_RECORD_SCHEMA,
    )
    witness_record = _read_json(
        Path(str(witness_record_ref["path"])), label="T112 witness execution record"
    )
    witness_artifact_ref = _verify_ref(
        witness.get("witness_artifact"), expected_schema=T112_WITNESS_SCHEMA
    )
    witness_artifact = _read_json(
        Path(str(witness_artifact_ref["path"])), label="T112 native witness"
    )
    witness_authorization_ref = _verify_ref(
        witness.get("witness_authorization"), expected_schema=T112_AUTH_SCHEMA
    )
    witness_authorization = _read_json(
        Path(str(witness_authorization_ref["path"])),
        label="T112 witness authorization",
    )
    if (
        witness.get("witness_status") != "ACCEPTED"
        or isinstance(witness.get("bridge_call_count"), bool)
        or not isinstance(witness.get("bridge_call_count"), int)
        or witness.get("bridge_call_count") != 1
        or isinstance(witness.get("retry_count"), bool)
        or not isinstance(witness.get("retry_count"), int)
        or witness.get("retry_count") != 0
        or witness.get("implementation_head") != record.get("implementation_head")
        or witness.get("native_binary") != record.get("native_binary")
        or witness.get("native_source_manifest_artifact")
        != record.get("native_source_manifest_artifact")
        or authorization.get("witness_terminal_artifact") != witness_ref
        or witness_authorization.get("stage") != "witness"
        or witness_authorization.get("implementation_head")
        != record.get("implementation_head")
        or witness_authorization.get("native_identity") != T112_NATIVE_IDENTITY
        or witness_authorization.get("native_binary") != record.get("native_binary")
        or witness_authorization.get("native_source_manifest_artifact")
        != record.get("native_source_manifest_artifact")
        or witness_authorization.get("qualification_artifact") != qualification_ref
        or witness_authorization.get("readiness_artifact") != readiness_ref
        or witness_record.get("authorization_id")
        != witness_authorization.get("authorization_id")
        or witness_record.get("authorization_sha256")
        != witness_authorization_ref.get("sha256")
        or witness_record.get("witness_artifact") != witness_artifact_ref
        or witness_record.get("witness_status") != "ACCEPTED"
        or witness_artifact.get("witness_status") != "ACCEPTED"
        or witness_artifact.get("bridge_call_count") != 1
        or witness_artifact.get("retry_count") != 0
    ):
        raise T112WorkflowError("T112 witness gate evidence changed")
    cohort_ref = _verify_ref(cohort_ref, expected_schema=T112_COHORT_SCHEMA)
    cohort = validate_t112_cohort(
        _read_json(Path(str(cohort_ref["path"])), label="T112 cohort admission")
    )
    t101_manifest_path = Path(
        str(qualification["t101_terminal_retention_manifest"]["path"])
    )
    source_rows, _canonical, _selected, source_provenance = _source_records_for_run(
        {"qualification": qualification}, t101_manifest_path=t101_manifest_path
    )
    if source_provenance.get("source_population") != qualification.get(
        "source_population"
    ):
        raise T112WorkflowError("T112 source population changed before finalization")
    first_a = min(
        (row for row in source_rows if row.get("cohort", row.get("stratum")) == "A"),
        key=lambda row: (
            hashlib.sha256(str(row["selection_identity"]).encode("utf-8")).hexdigest(),
            str(row["selection_identity"]),
        ),
    )
    witness_identity = witness.get("source_identity")
    expected_witness_identity = str(first_a["selection_identity"])
    expected_witness_seed = derive_t101_sampler_seed(expected_witness_identity, 0)
    safe_witness_metadata = witness.get("safe_seed_metadata")
    if (
        not isinstance(witness_identity, Mapping)
        or witness_identity.get("selection_identity") != expected_witness_identity
        or witness_identity.get("stratum") != "A"
        or witness_identity.get("selection_digest")
        != hashlib.sha256(expected_witness_identity.encode("utf-8")).hexdigest()
        or isinstance(witness.get("requested_sampler_seed_input"), bool)
        or not isinstance(witness.get("requested_sampler_seed_input"), int)
        or witness.get("requested_sampler_seed_input") != expected_witness_seed
        or isinstance(witness.get("observed_sampler_seed_input"), bool)
        or not isinstance(witness.get("observed_sampler_seed_input"), int)
        or witness.get("observed_sampler_seed_input") != expected_witness_seed
        or not isinstance(safe_witness_metadata, Mapping)
    ):
        raise T112WorkflowError("T112 witness is not the deterministic first-A record")
    validate_t112_safe_seed_metadata(
        safe_witness_metadata,
        expected_sampler_seed=expected_witness_seed,
        expected_bridge_report_sha256=str(witness.get("bridge_report_sha256", "")),
    )
    for stratum in T101_SOURCE_COUNTS:
        ordered_identities = sorted(
            (
                str(row["selection_identity"])
                for row in source_rows
                if row.get("cohort", row.get("stratum")) == stratum
            ),
            key=lambda identity: (
                hashlib.sha256(identity.encode("utf-8")).hexdigest(),
                identity,
            ),
        )
        attempted_identities = [
            str(row["selection_identity"])
            for row in cohort["attempted"]
            if row.get("stratum") == stratum
        ]
        if attempted_identities != ordered_identities[: len(attempted_identities)]:
            raise T112WorkflowError(
                "T112 attempts do not match the exact T101 source-order prefix"
            )
    attempts_path = Path(str(attempt_ref.get("path", "")))
    _verify_jsonl_matches_t112_cohort(
        attempts_path=attempts_path,
        attempt_ref=attempt_ref,
        cohort=cohort,
        record=record,
    )
    if (
        len(cohort["attempted"]) != executor.get("attempted_count")
        or cohort["terminal_classification"] != record.get("terminal_classification")
        or record.get("candidate_execution_started") is not True
    ):
        raise T112WorkflowError("T112 execution record and cohort disagree")
    status_ref = _artifact_ref(
        resource_status_path, schema_id="stsrl-detached-job-status-v1"
    )
    t111_verified_artifacts = t111_terminal_evidence.get("verified_artifacts")
    if not isinstance(t111_verified_artifacts, Mapping):
        raise T112WorkflowError("T112 qualification lost T111 retained artifacts")
    native_binary = record.get("native_binary")
    if not isinstance(native_binary, Mapping):
        raise T112WorkflowError("T112 execution record lost native binary identity")
    final = {
        "schema_id": T112_FINAL_REPORT_SCHEMA,
        "task_id": T112_TASK_ID,
        "implementation_head": record["implementation_head"],
        "approved_spec_commit": T112_APPROVED_SPEC_COMMIT,
        "native_identity": T112_NATIVE_IDENTITY,
        "historical_t101_native_identity": record["input_provenance"][
            "historical_t101_native_identity"
        ],
        "authorization_artifact": record["authorization_artifact"],
        "source_counts": dict(T101_SOURCE_COUNTS),
        "attempted_counts": {
            stratum: sum(row.get("stratum") == stratum for row in cohort["attempted"])
            for stratum in T101_SOURCE_COUNTS
        },
        "selected_counts": dict(cohort["selected_counts"]),
        "selected_identities": [
            row["selection_identity"] for row in cohort["selected"]
        ],
        "exhausted_strata": list(cohort["exhausted_strata"]),
        "selection_uses_value_or_outcome": False,
        "historical_failure_label_preselection": False,
        "historical_t111_attempts_used_for_admission": False,
        "frozen_configuration": {
            "particle_start": 0,
            "particle_count": 2,
            "replicate_index": 0,
            "search_simulations_per_particle": 400,
            "include_potions": False,
            "policy_prior": False,
            "learned_leaf_value": False,
            "progressive_bias": False,
        },
        "exclusion_counts": dict(executor["exclusion_counts"]),
        "witness_artifact": witness_ref,
        "attempt_artifact": dict(attempt_ref),
        "cohort_admission_artifact": cohort_ref,
        "terminal_classification": cohort["terminal_classification"],
        "executor": dict(executor),
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
            "target_pid": admission["target_pid"],
            "worker_count": admission["worker_count"],
            "shard_count": admission["shard_count"],
            "memory_budget_mib": admission["memory_budget_mib"],
            "memory_request_mib": admission["memory_request_mib"],
        },
        "candidate_execution_completed": True,
        "no_retry_or_substitution": True,
        "no_n_gt_2_or_convergence_execution": True,
    }
    final_ref = _write_new_json(cohort_output_root / "t112-final-report.json", final)
    record_ref = _artifact_ref(record_path, schema_id=T112_EXECUTION_RECORD_SCHEMA)
    manifest = {
        "schema_id": T112_RETENTION_MANIFEST_SCHEMA,
        "task_id": T112_TASK_ID,
        "implementation_head": record["implementation_head"],
        "approved_spec_commit": T112_APPROVED_SPEC_COMMIT,
        "terminal_classification": cohort["terminal_classification"],
        "artifact_references": {
            "preparation_manifest": preparation_manifest_ref,
            "input_qualification": qualification_ref,
            "readiness_preparation": readiness_ref,
            "validator_repair_provenance": repair_ref,
            "t101_retention_manifest": qualification[
                "t101_terminal_retention_manifest"
            ],
            "t111_retention_manifest": t111_terminal_evidence["retention_manifest"],
            "t111_source_qualification": qualification[
                "t111_source_qualification_artifact"
            ],
            "t111_readiness": qualification["t111_readiness_artifact"],
            "t111_verified_artifacts": dict(t111_verified_artifacts),
            "native_source_manifest": dict(record["native_source_manifest_artifact"]),
            "native_binary": dict(native_binary),
            "witness_authorization": witness_authorization_ref,
            "witness_terminal": witness_ref,
            "witness_execution_record": witness_record_ref,
            "native_witness": witness_artifact_ref,
            "cohort_authorization": authorization_ref,
            "candidate_attempts": dict(attempt_ref),
            "cohort_admission": cohort_ref,
            "execution_record": record_ref,
            "detached_resource_status": status_ref,
            "final_report": final_ref,
        },
        "candidate_execution_started": True,
        "candidate_execution_completed": True,
        "retention_reason": "Retain exact-head T112 seed-contract witness and bounded cohort evidence.",
        "deletion_condition": "Delete only after T112 lifecycle/provenance review has no audit consumers.",
    }
    manifest_ref = _write_new_json(
        cohort_output_root / "t112-terminal-retention-manifest.json", manifest
    )
    return {
        "final_report": final,
        "final_report_artifact": final_ref,
        "manifest_artifact": manifest_ref,
    }


__all__ = [
    "T112_AUTH_SCHEMA",
    "T112_COHORT_SCHEMA",
    "T112_FINAL_REPORT_SCHEMA",
    "T112_PREPARATION_SCHEMA",
    "T112_QUALIFICATION_SCHEMA",
    "T112_RETENTION_MANIFEST_SCHEMA",
    "T112_TERMINALS",
    "T112_WITNESS_SCHEMA",
    "T112WorkflowError",
    "execute_t112_authorized_cohort",
    "execute_t112_witness",
    "finalize_t112_execution",
    "finalize_t112_witness",
    "prepare_t112_inputs",
    "validate_t112_stage_authorization",
]
