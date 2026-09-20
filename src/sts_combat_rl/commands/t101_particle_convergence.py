"""Path-bound offline routing for the T101 particle-count diagnostic.

Simulator-facing restore and bridge calls are deliberately kept behind the
injected seams in :mod:`sts_combat_rl.sim.t101_particle_convergence`.  This
command creates the immutable non-authorizing formal plan, validates complete
sharded evidence, publishes analysis/cost/final reports, and builds retention
metadata.  It never silently starts a simulator job.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path

from sts_combat_rl.artifact_eligibility import (
    ArtifactQualification,
    EligibilityRequirements,
    Fact,
    Predicate,
)
from sts_combat_rl.commands import t088_canary
from sts_combat_rl.sim.lightspeed_source import load_lightspeed_source_manifest
from sts_combat_rl.sim.t101_particle_convergence import (
    T101_REQUIRED_RETENTION_ROLES,
    T101IncompleteError,
    _canonical_sha256,
    analyze_t101_formal,
    build_t101_formal_plan,
    build_t101_input_admission,
    build_t101_retention_manifest,
    select_t101_cohort,
    validate_t101_canary_evidence,
    validate_t101_formal_rows,
)
from sts_combat_rl.sim.t101_particle_execution import (
    T101NativeRecordRunner,
    execute_t101_canary,
    execute_t101_formal_shard,
)


class T101PathError(ValueError):
    """A path-bound T101 artifact was missing, mutable, or inconsistent."""


def _read_json(path: Path, *, schema_id: str, label: str) -> dict[str, object]:
    try:
        resolved = path.resolve(strict=True)
        value = json.loads(resolved.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise T101PathError(f"cannot read {label} JSON") from exc
    if not isinstance(value, Mapping) or value.get("schema_id") != schema_id:
        raise T101PathError(f"{label} schema is not current")
    return dict(value)


def _artifact_reference(path: Path, *, schema_id: str) -> dict[str, object]:
    resolved = path.resolve(strict=True)
    return {
        "path": str(resolved),
        "schema_id": schema_id,
        "sha256": _sha256_file(resolved),
        "size_bytes": resolved.stat().st_size,
    }


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _normalized_reference(role: str, value: object) -> dict[str, object]:
    if not isinstance(value, Mapping):
        raise T101PathError(f"verified input reference {role} is missing")
    size = value.get("size_bytes", value.get("byte_count"))
    if (
        not isinstance(value.get("path"), str)
        or not value["path"]
        or not isinstance(value.get("schema_id"), str)
        or not value["schema_id"]
        or not isinstance(value.get("sha256"), str)
        or len(value["sha256"]) != 64
        or isinstance(size, bool)
        or not isinstance(size, int)
        or size < 0
    ):
        raise T101PathError(f"verified input reference {role} is malformed")
    return {
        "path": value["path"],
        "schema_id": value["schema_id"],
        "sha256": value["sha256"],
        "size_bytes": size,
    }


def _input_qualification(
    role: str, reference: Mapping[str, object]
) -> tuple[ArtifactQualification, EligibilityRequirements]:
    qualification = ArtifactQualification(
        artifact={
            "id": role,
            "kind": reference["schema_id"],
            "path": reference["path"],
            "size_bytes": reference["size_bytes"],
            "schema_id": reference["schema_id"],
        },
        integrity={"sha256": reference["sha256"]},
        facts={
            "record_count": Fact(413),
            "source.coverage": Fact("accepted_t087_t088_matched_population"),
            "payload_complete": Fact(True),
            "partial": Fact(False),
            "debug_only": Fact(False),
            "superseded_for_t101": Fact(False),
            "override_kind": Fact("none"),
        },
        producer_scope="accepted T087/T088 retained evidence",
    )
    requirements = EligibilityRequirements(
        reuse_mode="scientific_quality_claim",
        claim_boundary=(
            "bounded particle-proxy stability and cost under frozen T101 semantics"
        ),
        predicates=(
            Predicate("record_count", "equals", 413),
            Predicate(
                "source.coverage", "equals", "accepted_t087_t088_matched_population"
            ),
            Predicate("payload_complete", "equals", True),
            Predicate("partial", "equals", False),
            Predicate("debug_only", "equals", False),
            Predicate("superseded_for_t101", "equals", False),
            Predicate("override_kind", "equals", "none"),
        ),
        artifact_id=role,
        artifact_kind=str(reference["schema_id"]),
        sha256=str(reference["sha256"]),
    )
    return qualification, requirements


def _default_adapter_factory() -> object:
    from sts_combat_rl.sim.lightspeed import LightSpeedAdapter

    return LightSpeedAdapter(seed=1, ascension=20, player_class="IRONCLAD")


def _validate_readiness_authorization(
    value: Mapping[str, object],
    *,
    implementation_head: str,
    retained_inputs_sha256: str,
) -> None:
    expected = {
        "schema_id": "t101-maintainer-readiness-authorization-v1",
        "task_id": "T101",
        "authorization_kind": "support_admission",
        "authorized": True,
        "authorization_id": value.get("authorization_id"),
        "implementation_head": implementation_head,
        "retained_inputs_sha256": retained_inputs_sha256,
        "maintainer_attestation": {
            "role": "maintainer",
            "decision": "READINESS_AUTHORIZED",
            "exact_head": implementation_head,
        },
    }
    if (
        dict(value) != expected
        or not isinstance(value.get("authorization_id"), str)
        or not value["authorization_id"]
    ):
        raise T101PathError("readiness authorization is not an exact input binding")


def run_t101_readiness_from_paths(
    *,
    authorization_path: Path | None,
    implementation_head: str,
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
    t088_formal_raw_path: Path,
    t088_final_report_path: Path,
    t088_retention_path: Path,
    artifact_root: Path,
    adapter_factory: object | None = None,
    runner_factory: object = T101NativeRecordRunner,
) -> dict[str, object]:
    """Hash-admit retained inputs, then run the authorized N=2 support gate."""

    formal, gate, inherited = t088_canary._admit_t088_canary_inputs_from_paths(
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
    )
    retention = _read_json(
        t088_retention_path,
        schema_id="t088-retention-manifest-v1",
        label="T088 retention manifest",
    )
    final = _read_json(
        t088_final_report_path,
        schema_id="t088-final-tournament-report-v1",
        label="T088 final report",
    )
    if (
        final.get("task_id") != "T088"
        or final.get("terminal_classification")
        != "STRONGER_NONLEARNED_COMBAT_BASELINE_IDENTIFIED"
        or final.get("selected_challenger") != "B"
        or final.get("baseline_decision")
        != {
            "decision": "promotion_eligible_unique_challenger",
            "selected_arm": "B",
            "selected_controller_configuration": {
                "controller": "Search-v2",
                "simulations": 400,
            },
            "improvement_source": "Search-v2 higher compute",
        }
    ):
        raise T101PathError("T088 final report does not freeze Search-v2@400 Arm B")
    references = retention.get("artifact_references")
    if not isinstance(references, Mapping):
        raise T101PathError("T088 retention artifact references are missing")
    formal_reference = _normalized_reference(
        "t088_formal_raw", references.get("formal_rows")
    )
    final_reference = _normalized_reference(
        "t088_final", references.get("final_report")
    )
    if (
        formal_reference["sha256"]
        != "fe376c3f054c94bf30d368ec544ff85f13f9ac594e7eec4178677e7e5414acea"
        or _sha256_file(t088_formal_raw_path.resolve(strict=True))
        != formal_reference["sha256"]
        or _sha256_file(t088_final_report_path.resolve(strict=True))
        != final_reference["sha256"]
    ):
        raise T101PathError(
            "T088 retained formal/final identity differs from acceptance"
        )
    retained: dict[str, dict[str, object]] = {
        role: _normalized_reference(role, reference)
        for role, reference in inherited.items()
        if role != "t085_canonical"
    }
    canonical = inherited.get("t085_canonical")
    if not isinstance(canonical, Mapping):
        raise T101PathError("T085 canonical artifact references are missing")
    retained.update(
        {
            f"t085_canonical_{stratum.lower()}": _normalized_reference(
                f"t085_canonical_{stratum.lower()}", canonical.get(stratum)
            )
            for stratum in ("A", "B", "C")
        }
    )
    retained.update(
        {
            "t088_formal_raw": {
                **formal_reference,
                "path": str(t088_formal_raw_path.resolve(strict=True)),
            },
            "t088_final_report": {
                **final_reference,
                "path": str(t088_final_report_path.resolve(strict=True)),
            },
            "t088_retention": _artifact_reference(
                t088_retention_path, schema_id="t088-retention-manifest-v1"
            ),
            "native_source_manifest": _artifact_reference(
                Path(__file__).resolve().parents[3]
                / "docs"
                / "sts_lightspeed_source_manifest.json",
                schema_id="sts-lightspeed-source-manifest-v1",
            ),
        }
    )
    retained_sha = _canonical_sha256(retained)
    if authorization_path is None:
        return {
            "schema_id": "t101-readiness-authorization-preparation-v1",
            "task_id": "T101",
            "preparation_only": True,
            "retained_inputs": retained,
            "retained_inputs_sha256": retained_sha,
            "authorization_template": {
                "schema_id": "t101-maintainer-readiness-authorization-v1",
                "task_id": "T101",
                "authorization_kind": "support_admission",
                "authorized": None,
                "authorization_id": None,
                "implementation_head": implementation_head,
                "retained_inputs_sha256": retained_sha,
                "maintainer_attestation": {
                    "role": "maintainer",
                    "decision": "READINESS_AUTHORIZED",
                    "exact_head": implementation_head,
                },
            },
        }
    auth = _read_json(
        authorization_path,
        schema_id="t101-maintainer-readiness-authorization-v1",
        label="T101 readiness authorization",
    )
    _validate_readiness_authorization(
        auth,
        implementation_head=implementation_head,
        retained_inputs_sha256=retained_sha,
    )
    manifest = load_lightspeed_source_manifest()
    repository = manifest.integration.repository_url.rstrip("/").removesuffix(".git")
    native_identity = {
        "repository": repository.removeprefix("https://github.com/"),
        "ref": manifest.integration.ref,
        "commit": manifest.integration.commit,
    }
    factory = adapter_factory or _default_adapter_factory
    if not callable(factory) or not callable(runner_factory):
        raise T101PathError("T101 native factories are invalid")
    audit_adapter = factory()
    audit_call = getattr(audit_adapter, "stsr006_particle_search_audit", None)
    if not callable(audit_call):
        raise T101PathError("T099 bridge audit is unavailable")
    input_admission = build_t101_input_admission(
        {
            role: _input_qualification(role, reference)
            for role, reference in retained.items()
        },
        native_identity=native_identity,
        bridge_audit=audit_call(),
    )
    maps = getattr(gate, "canonical_records_by_cohort", None)
    source_identity = getattr(gate, "source_selection_manifest_identity", None)
    cohorts = getattr(gate, "cohorts", None)
    if not all(
        isinstance(value, Mapping) for value in (maps, source_identity, cohorts)
    ):
        raise T101PathError("admitted T087/T085 gate is malformed")
    source_rows = t088_canary._project_t087_cohort(formal, source_identity, maps)
    selected_records = {
        record.selection_identity: record
        for stratum in ("A", "B", "C")
        for record in cohorts[stratum]
    }
    runner = runner_factory(
        adapter_factory=factory,
        selected_records=selected_records,
        canonical_records_by_stratum=maps,
    )
    cohort_admission = select_t101_cohort(source_rows, admit=runner.admit)
    root = artifact_root.resolve()
    references_out = {
        "input_admission": _write_new(
            root / "t101-input-admission.json", input_admission
        ),
        "cohort_admission": _write_new(
            root / "t101-cohort-admission.json", cohort_admission
        ),
    }
    return {
        "authorization": auth,
        "input_admission": input_admission,
        "cohort_admission": cohort_admission,
        "artifacts": references_out,
    }


def prepare_t101_canary_authorization_from_paths(
    *,
    input_admission_path: Path,
    cohort_admission_path: Path,
    implementation_head: str,
) -> dict[str, object]:
    inputs = _read_json(
        input_admission_path,
        schema_id="t101-input-admission-v1",
        label="T101 input admission",
    )
    cohort = _read_json(
        cohort_admission_path,
        schema_id="t101-cohort-admission-v1",
        label="T101 cohort admission",
    )
    if inputs.get("eligible") is not True or cohort.get("supported") is not True:
        raise T101PathError(
            "canary authorization preparation requires passed readiness"
        )
    return {
        "schema_id": "t101-canary-authorization-preparation-v1",
        "task_id": "T101",
        "preparation_only": True,
        "authorization_template": {
            "schema_id": "t101-maintainer-canary-authorization-v1",
            "task_id": "T101",
            "authorization_kind": "bounded_canary",
            "authorized": None,
            "authorization_id": None,
            "implementation_head": implementation_head,
            "input_admission_sha256": _canonical_sha256(inputs),
            "cohort_admission_sha256": _canonical_sha256(cohort),
            "maintainer_attestation": {
                "role": "maintainer",
                "decision": "CANARY_AUTHORIZED",
                "exact_head": implementation_head,
            },
        },
    }


def _validate_canary_against_plan(
    canary: Mapping[str, object], plan: Mapping[str, object]
) -> None:
    validate_t101_canary_evidence(canary)
    jobs = plan.get("jobs")
    if not isinstance(jobs, Sequence) or isinstance(jobs, (str, bytes)):
        raise T101PathError("formal plan jobs are missing")
    replicate_zero = sorted(
        (
            job
            for job in jobs
            if isinstance(job, Mapping) and job.get("replicate_index") == 0
        ),
        key=lambda job: int(job["state_ordinal"]),
    )
    expected: list[dict[str, object]] = []
    for stratum in ("A", "B", "C"):
        try:
            job = next(row for row in replicate_zero if row.get("stratum") == stratum)
        except StopIteration as exc:
            raise T101PathError("formal plan lacks a canary stratum") from exc
        expected.append(
            {
                "selection_identity": job["selection_identity"],
                "stratum": stratum,
                "replicate_index": 0,
            }
        )
    if canary.get("selected") != expected:
        raise T101PathError("canary is not the first admitted A/B/C state")


def prepare_t101_formal_authorization_from_paths(
    *,
    plan_path: Path,
    canary_evidence_path: Path,
    implementation_head: str,
) -> dict[str, object]:
    plan = _read_json(plan_path, schema_id="t101-formal-plan-v1", label="T101 plan")
    canary = _read_json(
        canary_evidence_path,
        schema_id="t101-canary-evidence-v1",
        label="T101 canary evidence",
    )
    _validate_canary_against_plan(canary, plan)
    if (
        plan.get("formal_authorized") is not False
        or plan.get("implementation_head") != implementation_head
        or canary.get("implementation_head") != implementation_head
    ):
        raise T101PathError("formal authorization preparation inputs are not accepted")
    canary_reference = _artifact_reference(
        canary_evidence_path, schema_id="t101-canary-evidence-v1"
    )
    return {
        "schema_id": "t101-formal-authorization-preparation-v1",
        "task_id": "T101",
        "preparation_only": True,
        "canary_evidence": canary_reference,
        "authorization_template": {
            "schema_id": "t101-maintainer-formal-authorization-v1",
            "task_id": "T101",
            "authorization_kind": "formal_particle_diagnostic",
            "authorized": None,
            "authorization_id": None,
            "implementation_head": implementation_head,
            "formal_plan_sha256": _canonical_sha256(plan),
            "canary_evidence_sha256": canary_reference["sha256"],
            "maintainer_attestation": {
                "role": "maintainer",
                "decision": "FORMAL_AUTHORIZED",
                "exact_head": implementation_head,
            },
        },
    }


def _native_runner_from_paths(
    *,
    implementation_head: str,
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
    adapter_factory: object | None = None,
    runner_factory: object = T101NativeRecordRunner,
) -> object:
    _formal, gate, _inputs = t088_canary._admit_t088_canary_inputs_from_paths(
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
    )
    maps = getattr(gate, "canonical_records_by_cohort", None)
    cohorts = getattr(gate, "cohorts", None)
    if not isinstance(maps, Mapping) or not isinstance(cohorts, Mapping):
        raise T101PathError("admitted T087/T085 execution gate is malformed")
    factory = adapter_factory or _default_adapter_factory
    if not callable(factory) or not callable(runner_factory):
        raise T101PathError("T101 native factories are invalid")
    selected_records = {
        record.selection_identity: record
        for stratum in ("A", "B", "C")
        for record in cohorts[stratum]
    }
    return runner_factory(
        adapter_factory=factory,
        selected_records=selected_records,
        canonical_records_by_stratum=maps,
    )


def run_t101_canary_from_paths(
    *,
    authorization_path: Path,
    input_admission_path: Path,
    cohort_admission_path: Path,
    output_path: Path,
    artifact_root: Path,
    implementation_head: str,
    worker_id: str,
    **runner_paths: object,
) -> dict[str, object]:
    authorization = _read_json(
        authorization_path,
        schema_id="t101-maintainer-canary-authorization-v1",
        label="T101 canary authorization",
    )
    inputs = _read_json(
        input_admission_path,
        schema_id="t101-input-admission-v1",
        label="T101 input admission",
    )
    cohort = _read_json(
        cohort_admission_path,
        schema_id="t101-cohort-admission-v1",
        label="T101 cohort admission",
    )
    destination = output_path.resolve()
    try:
        destination.relative_to(artifact_root.resolve())
    except ValueError as exc:
        raise T101PathError("canary evidence must remain under artifact root") from exc
    runner = _native_runner_from_paths(
        implementation_head=implementation_head,
        **runner_paths,  # type: ignore[arg-type]
    )
    evidence = execute_t101_canary(
        authorization=authorization,
        implementation_head=implementation_head,
        input_admission=inputs,
        cohort_admission=cohort,
        runner=runner,  # type: ignore[arg-type]
        worker_id=worker_id,
    )
    return {"evidence": evidence, "artifact": _write_new(destination, evidence)}


def run_t101_formal_shard_from_paths(
    *,
    authorization_path: Path,
    plan_path: Path,
    canary_evidence_path: Path,
    output_path: Path,
    artifact_root: Path,
    implementation_head: str,
    shard_index: int,
    worker_id: str,
    effective_concurrency: int,
    retry_reason: str | None,
    **runner_paths: object,
) -> dict[str, object]:
    authorization = _read_json(
        authorization_path,
        schema_id="t101-maintainer-formal-authorization-v1",
        label="T101 formal authorization",
    )
    plan = _read_json(plan_path, schema_id="t101-formal-plan-v1", label="T101 plan")
    canary = _read_json(
        canary_evidence_path,
        schema_id="t101-canary-evidence-v1",
        label="T101 canary evidence",
    )
    _validate_canary_against_plan(canary, plan)
    canary_reference = _artifact_reference(
        canary_evidence_path, schema_id="t101-canary-evidence-v1"
    )
    destination = output_path.resolve()
    try:
        destination.relative_to(artifact_root.resolve())
    except ValueError as exc:
        raise T101PathError("formal shard must remain under artifact root") from exc
    runner = _native_runner_from_paths(
        implementation_head=implementation_head,
        **runner_paths,  # type: ignore[arg-type]
    )
    shard = execute_t101_formal_shard(
        authorization=authorization,
        implementation_head=implementation_head,
        plan=plan,
        canary_evidence_reference=canary_reference,
        shard_index=shard_index,
        runner=runner,  # type: ignore[arg-type]
        worker_id=worker_id,
        effective_concurrency=effective_concurrency,
        retry_reason=retry_reason,
    )
    return {"shard": shard, "artifact": _write_new(destination, shard)}


def _write_new(path: Path, value: Mapping[str, object]) -> dict[str, object]:
    destination = path.resolve()
    if destination.exists():
        raise T101PathError("refusing to overwrite retained T101 artifact")
    destination.parent.mkdir(parents=True, exist_ok=True)
    encoded = (
        json.dumps(
            dict(value),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
        + b"\n"
    )
    try:
        descriptor = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(encoded)
    except OSError as exc:
        raise T101PathError("cannot atomically create T101 artifact") from exc
    return {
        "path": str(destination),
        "schema_id": value["schema_id"],
        "sha256": hashlib.sha256(encoded).hexdigest(),
        "size_bytes": len(encoded),
    }


def prepare_t101_formal_plan_from_paths(
    *,
    input_admission_path: Path,
    cohort_admission_path: Path,
    implementation_head: str,
    artifact_root: Path,
    output_path: Path,
    shard_count: int = 16,
    worker_count: int = 16,
) -> dict[str, object]:
    """Write the immutable formal plan with authorization explicitly false."""

    inputs = _read_json(
        input_admission_path,
        schema_id="t101-input-admission-v1",
        label="T101 input admission",
    )
    cohort = _read_json(
        cohort_admission_path,
        schema_id="t101-cohort-admission-v1",
        label="T101 cohort admission",
    )
    root = artifact_root.resolve()
    destination = output_path.resolve()
    try:
        destination.relative_to(root)
    except ValueError as exc:
        raise T101PathError("formal plan must remain under its artifact root") from exc
    plan = build_t101_formal_plan(
        cohort,
        input_admission=inputs,
        implementation_head=implementation_head,
        output_root=str(root),
        shard_count=shard_count,
        worker_count=worker_count,
    )
    return {"plan": plan, "artifact": _write_new(destination, plan)}


def validate_t101_formal_shards_from_paths(
    *,
    plan: Mapping[str, object],
    shard_paths: Sequence[Path],
    canary_evidence_sha256: str,
) -> list[dict[str, object]]:
    topology = plan.get("topology")
    if not isinstance(topology, Mapping):
        raise T101PathError("formal plan topology is missing")
    shard_count = topology.get("shard_count")
    if (
        isinstance(shard_count, bool)
        or not isinstance(shard_count, int)
        or shard_count < 1
    ):
        raise T101PathError("formal plan shard count is invalid")
    if len(shard_paths) != shard_count:
        raise T101PathError("formal evidence does not provide every planned shard")
    plan_sha = _canonical_sha256(plan)
    implementation_head = plan.get("implementation_head")
    worker_count = topology.get("worker_count")
    if (
        not isinstance(canary_evidence_sha256, str)
        or len(canary_evidence_sha256) != 64
        or not isinstance(implementation_head, str)
        or isinstance(worker_count, bool)
        or not isinstance(worker_count, int)
    ):
        raise T101PathError("formal shard provenance binding is invalid")
    by_index: dict[int, dict[str, object]] = {}
    rows: list[dict[str, object]] = []
    authorization_ids: set[str] = set()
    for path in shard_paths:
        shard = _read_json(
            path, schema_id="t101-formal-shard-v1", label="T101 formal shard"
        )
        index = shard.get("shard_index")
        if (
            isinstance(index, bool)
            or not isinstance(index, int)
            or index not in range(shard_count)
            or index in by_index
            or shard.get("formal_plan_sha256") != plan_sha
            or shard.get("implementation_head") != implementation_head
            or shard.get("canary_evidence_sha256") != canary_evidence_sha256
            or shard.get("shard_count") != shard_count
            or shard.get("complete") is not True
        ):
            raise T101PathError("formal shard identity/completion is invalid")
        shard_rows = shard.get("rows")
        if not isinstance(shard_rows, Sequence) or isinstance(shard_rows, (str, bytes)):
            raise T101PathError("formal shard rows are malformed")
        if (
            not isinstance(shard.get("worker_id"), str)
            or not shard["worker_id"]
            or isinstance(shard.get("effective_concurrency"), bool)
            or not isinstance(shard.get("effective_concurrency"), int)
            or shard["effective_concurrency"] < 1
            or shard["effective_concurrency"] > worker_count
            or isinstance(shard.get("wall_clock_time_s"), bool)
            or not isinstance(shard.get("wall_clock_time_s"), (int, float))
            or shard["wall_clock_time_s"] < 0
            or shard.get("job_ordinals")
            != [
                row.get("job_ordinal") for row in shard_rows if isinstance(row, Mapping)
            ]
        ):
            raise T101PathError("formal shard runtime provenance is incomplete")
        authorization_id = shard.get("authorization_id")
        if not isinstance(authorization_id, str) or not authorization_id:
            raise T101PathError("formal shard authorization provenance is missing")
        authorization_ids.add(authorization_id)
        for row in shard_rows:
            if not isinstance(row, Mapping) or row.get("shard_index") != index:
                raise T101PathError("formal shard contains a misplaced row")
            rows.append(dict(row))
        by_index[index] = shard
    if set(by_index) != set(range(shard_count)):
        raise T101PathError("formal shard set is incomplete")
    if len(authorization_ids) != 1:
        raise T101PathError("formal shards use different authorization records")
    return validate_t101_formal_rows(rows, plan)


def analyze_t101_formal_from_paths(
    *,
    plan_path: Path,
    canary_evidence_path: Path,
    shard_paths: Sequence[Path],
    artifact_root: Path,
) -> dict[str, object]:
    """Publish raw-index, analysis, cost, and final reports from complete shards."""

    plan = _read_json(plan_path, schema_id="t101-formal-plan-v1", label="formal plan")
    canary = _read_json(
        canary_evidence_path,
        schema_id="t101-canary-evidence-v1",
        label="T101 canary evidence",
    )
    _validate_canary_against_plan(canary, plan)
    if canary.get("implementation_head") != plan.get("implementation_head"):
        raise T101PathError("analysis requires complete exact-head canary evidence")
    canary_reference = _artifact_reference(
        canary_evidence_path, schema_id="t101-canary-evidence-v1"
    )
    rows = validate_t101_formal_shards_from_paths(
        plan=plan,
        shard_paths=shard_paths,
        canary_evidence_sha256=str(canary_reference["sha256"]),
    )
    analysis = analyze_t101_formal(rows, plan)
    root = artifact_root.resolve()
    root.mkdir(parents=True, exist_ok=True)
    formal_index = {
        "schema_id": "t101-formal-evidence-index-v1",
        "task_id": "T101",
        "formal_plan": _artifact_reference(plan_path, schema_id="t101-formal-plan-v1"),
        "shards": [
            _artifact_reference(path, schema_id="t101-formal-shard-v1")
            for path in sorted(shard_paths)
        ],
        "job_count": len(rows),
        "complete": True,
    }
    cost = dict(analysis["cost_report"])
    ladders = canary.get("ladders")
    if not isinstance(ladders, Sequence) or isinstance(ladders, (str, bytes)):
        raise T101PathError("canary direct wall-clock ladders are missing")
    cost["canary_direct_ladders"] = list(ladders)
    cost["canary_evidence"] = canary_reference
    cost["formal_shards"] = [
        {
            name: shard[name]
            for name in (
                "shard_index",
                "shard_count",
                "worker_id",
                "effective_concurrency",
                "job_ordinals",
                "wall_clock_time_s",
            )
        }
        for shard in (
            _read_json(path, schema_id="t101-formal-shard-v1", label="formal shard")
            for path in sorted(shard_paths)
        )
    ]
    unstable_n32: list[dict[str, object]] = []
    for stability in analysis["across_sampler_replicates"]:
        if stability["all_four_exactly_identical"] is True:
            continue
        identity = stability["selection_identity"]
        replicate_details: list[dict[str, object]] = []
        for state_row in analysis["state_replicate_metrics"]:
            if state_row["selection_identity"] != identity:
                continue
            n32 = next(
                item for item in state_row["metrics"] if item["particle_count"] == 32
            )
            class_values = {
                row["decision_class_id"]: row["strategy_fusion_mean_proxy"]
                for row in n32["decision_classes"]
            }
            best = set(n32["best_decision_class_set"])
            nonbest = [
                float(value)
                for class_id, value in class_values.items()
                if class_id not in best
            ]
            maximum = max(float(value) for value in class_values.values())
            replicate_details.append(
                {
                    "replicate_index": state_row["replicate_index"],
                    "best_decision_class_set": n32["best_decision_class_set"],
                    "n32_decision_class_proxy_values": class_values,
                    "best_to_next_proxy_margin": (
                        maximum - max(nonbest) if nonbest else None
                    ),
                }
            )
        unstable_n32.append({**stability, "n32_replicate_metrics": replicate_details})
    prefix_disagreements: dict[str, list[dict[str, object]]] = {}
    for count in (2, 4, 8, 16, 32):
        disagreements: list[dict[str, object]] = []
        for row in analysis["state_replicate_metrics"]:
            metric = next(
                item for item in row["metrics"] if item["particle_count"] == count
            )
            if metric["best_set_exact_agreement_with_n32"] is not True:
                disagreements.append(
                    {
                        "selection_identity": row["selection_identity"],
                        "stratum": row["stratum"],
                        "replicate_index": row["replicate_index"],
                        "best_decision_class_set": metric["best_decision_class_set"],
                        "n32_reference_proxy_opportunity_gap": metric[
                            "n32_reference_proxy_opportunity_gap"
                        ],
                        "maximum_absolute_class_mean_drift_from_n32": metric[
                            "maximum_absolute_class_mean_drift_from_n32"
                        ],
                    }
                )
        prefix_disagreements[str(count)] = disagreements
    final = {
        "schema_id": "t101-final-report-v1",
        "task_id": "T101",
        "terminal_classification": analysis["terminal_classification"],
        "n32_reference_unanimous_all_states": analysis[
            "n32_reference_unanimous_all_states"
        ],
        "smallest_uniform_prefix_n": analysis["smallest_uniform_prefix_n"],
        "value_semantics": analysis["value_semantics"],
        "information_regime": analysis["information_regime"],
        "semantic_boundary": analysis["semantic_boundary"],
        "unstable_n32_states": unstable_n32,
        "prefix_disagreements": prefix_disagreements,
        "cohort_summaries": analysis["cohort_summaries"],
        "observed_cost": {
            "formal_n32_wall_clock_time_s": cost["formal_n32_wall_clock_time_s"],
            "sum_formal_n32_call_wall_clock_time_s": cost[
                "sum_formal_n32_call_wall_clock_time_s"
            ],
            "n2_to_n32_work_change": cost["n2_to_n32_work_change"],
            "canary_direct_ladders": cost["canary_direct_ladders"],
            "formal_shards": cost["formal_shards"],
        },
        "interpretation": (
            "bounded balanced natural Battle-start cohort diagnostic under the exact "
            "T101 sampler and full-state Search-v2@400 proxy semantics"
        ),
        "nonclaims": [
            "no convergence to a true public-information value",
            "no deployable controller",
            "no normal-information controller improvement",
            "no authorization to execute more than 32 particles",
        ],
    }
    references = {
        "formal_evidence": _write_new(
            root / "t101-formal-evidence-index.json", formal_index
        ),
        "convergence_analysis": _write_new(
            root / "t101-convergence-analysis.json", analysis
        ),
        "cost_report": _write_new(root / "t101-cost-report.json", cost),
        "final_report": _write_new(root / "t101-final-report.json", final),
    }
    return {"analysis": analysis, "final_report": final, "artifacts": references}


def _parse_role_path(spec: str) -> tuple[str, Path]:
    role, separator, path = spec.partition("=")
    if not separator or not role or not path:
        raise T101PathError("artifact must use role=path")
    return role, Path(path)


def build_t101_retention_from_paths(
    *,
    artifact_specs: Sequence[str],
    output_path: Path,
    regeneration_commands: Sequence[str],
    retention_reason: str,
    deletion_condition: str,
) -> dict[str, object]:
    references: dict[str, dict[str, object]] = {}
    for spec in artifact_specs:
        role, path = _parse_role_path(spec)
        if role in references:
            raise T101PathError(f"duplicate retained artifact role: {role}")
        document = _read_json(path, schema_id=_peek_schema(path), label=role)
        references[role] = _artifact_reference(
            path, schema_id=str(document["schema_id"])
        )
    manifest = build_t101_retention_manifest(
        references,
        regeneration_commands=regeneration_commands,
        retention_reason=retention_reason,
        deletion_condition=deletion_condition,
    )
    return {"manifest": manifest, "artifact": _write_new(output_path, manifest)}


def _peek_schema(path: Path) -> str:
    try:
        value = json.loads(path.resolve(strict=True).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise T101PathError("retained artifact is not readable JSON") from exc
    if not isinstance(value, Mapping) or not isinstance(value.get("schema_id"), str):
        raise T101PathError("retained artifact schema_id is missing")
    return str(value["schema_id"])


def build_parser() -> argparse.ArgumentParser:
    def add_runner_paths(command: argparse.ArgumentParser) -> None:
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
            command.add_argument(f"--{name}", type=Path, required=True)

    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_subparsers(dest="mode", required=True)
    readiness = modes.add_parser("readiness")
    readiness.add_argument("--authorization", type=Path)
    readiness.add_argument("--prepare-authorization", action="store_true")
    readiness.add_argument("--implementation-head", required=True)
    add_runner_paths(readiness)
    for name in ("t088-formal-raw", "t088-final-report", "t088-retention"):
        readiness.add_argument(f"--{name}", type=Path, required=True)
    readiness.add_argument("--artifact-root", type=Path, required=True)

    canary = modes.add_parser("canary")
    canary.add_argument("--authorization", type=Path, required=True)
    canary.add_argument("--input-admission", type=Path, required=True)
    canary.add_argument("--cohort-admission", type=Path, required=True)
    canary.add_argument("--implementation-head", required=True)
    canary.add_argument("--worker-id", required=True)
    canary.add_argument("--artifact-root", type=Path, required=True)
    canary.add_argument("--output", type=Path, required=True)
    add_runner_paths(canary)

    canary_auth = modes.add_parser("canary-authorization")
    canary_auth.add_argument("--input-admission", type=Path, required=True)
    canary_auth.add_argument("--cohort-admission", type=Path, required=True)
    canary_auth.add_argument("--implementation-head", required=True)

    plan = modes.add_parser("plan")
    plan.add_argument("--input-admission", type=Path, required=True)
    plan.add_argument("--cohort-admission", type=Path, required=True)
    plan.add_argument("--implementation-head", required=True)
    plan.add_argument("--artifact-root", type=Path, required=True)
    plan.add_argument("--output", type=Path, required=True)
    plan.add_argument("--shard-count", type=int, default=16)
    plan.add_argument("--worker-count", type=int, default=16)

    shard = modes.add_parser("formal-shard")
    shard.add_argument("--authorization", type=Path, required=True)
    shard.add_argument("--plan", type=Path, required=True)
    shard.add_argument("--canary-evidence", type=Path, required=True)
    shard.add_argument("--implementation-head", required=True)
    shard.add_argument("--shard-index", type=int, required=True)
    shard.add_argument("--worker-id", required=True)
    shard.add_argument("--effective-concurrency", type=int, required=True)
    shard.add_argument(
        "--retry-reason", choices=("operational_failure_identical_inputs",)
    )
    shard.add_argument("--artifact-root", type=Path, required=True)
    shard.add_argument("--output", type=Path, required=True)
    add_runner_paths(shard)

    formal_auth = modes.add_parser("formal-authorization")
    formal_auth.add_argument("--plan", type=Path, required=True)
    formal_auth.add_argument("--canary-evidence", type=Path, required=True)
    formal_auth.add_argument("--implementation-head", required=True)

    analyze = modes.add_parser("analyze")
    analyze.add_argument("--plan", type=Path, required=True)
    analyze.add_argument("--canary-evidence", type=Path, required=True)
    analyze.add_argument("--shard", type=Path, action="append", default=[])
    analyze.add_argument("--artifact-root", type=Path, required=True)

    retention = modes.add_parser("retention")
    retention.add_argument("--artifact", action="append", default=[])
    retention.add_argument("--output", type=Path, required=True)
    retention.add_argument("--regeneration-command", action="append", default=[])
    retention.add_argument("--retention-reason", required=True)
    retention.add_argument("--deletion-condition", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.mode == "readiness":
            if args.prepare_authorization == (args.authorization is not None):
                raise T101PathError(
                    "readiness requires exactly one of --prepare-authorization or --authorization"
                )
            result = run_t101_readiness_from_paths(
                authorization_path=args.authorization,
                implementation_head=args.implementation_head,
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
                t088_formal_raw_path=args.t088_formal_raw,
                t088_final_report_path=args.t088_final_report,
                t088_retention_path=args.t088_retention,
                artifact_root=args.artifact_root,
            )
        elif args.mode == "canary-authorization":
            result = prepare_t101_canary_authorization_from_paths(
                input_admission_path=args.input_admission,
                cohort_admission_path=args.cohort_admission,
                implementation_head=args.implementation_head,
            )
        elif args.mode == "canary":
            result = run_t101_canary_from_paths(
                authorization_path=args.authorization,
                input_admission_path=args.input_admission,
                cohort_admission_path=args.cohort_admission,
                output_path=args.output,
                artifact_root=args.artifact_root,
                implementation_head=args.implementation_head,
                worker_id=args.worker_id,
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
            )
        elif args.mode == "plan":
            result = prepare_t101_formal_plan_from_paths(
                input_admission_path=args.input_admission,
                cohort_admission_path=args.cohort_admission,
                implementation_head=args.implementation_head,
                artifact_root=args.artifact_root,
                output_path=args.output,
                shard_count=args.shard_count,
                worker_count=args.worker_count,
            )
        elif args.mode == "formal-shard":
            result = run_t101_formal_shard_from_paths(
                authorization_path=args.authorization,
                plan_path=args.plan,
                canary_evidence_path=args.canary_evidence,
                output_path=args.output,
                artifact_root=args.artifact_root,
                implementation_head=args.implementation_head,
                shard_index=args.shard_index,
                worker_id=args.worker_id,
                effective_concurrency=args.effective_concurrency,
                retry_reason=args.retry_reason,
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
            )
        elif args.mode == "formal-authorization":
            result = prepare_t101_formal_authorization_from_paths(
                plan_path=args.plan,
                canary_evidence_path=args.canary_evidence,
                implementation_head=args.implementation_head,
            )
        elif args.mode == "analyze":
            result = analyze_t101_formal_from_paths(
                plan_path=args.plan,
                canary_evidence_path=args.canary_evidence,
                shard_paths=args.shard,
                artifact_root=args.artifact_root,
            )
        else:
            if {role for role, _ in map(_parse_role_path, args.artifact)} != set(
                T101_REQUIRED_RETENTION_ROLES
            ):
                raise T101PathError("retention command requires every exact T101 role")
            result = build_t101_retention_from_paths(
                artifact_specs=args.artifact,
                output_path=args.output,
                regeneration_commands=args.regeneration_command,
                retention_reason=args.retention_reason,
                deletion_condition=args.deletion_condition,
            )
    except (OSError, T101IncompleteError, T101PathError, ValueError) as exc:
        print(f"T101 command failed: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
