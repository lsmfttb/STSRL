"""T113 artifact qualification and non-authorizing readiness preparation.

This command validates the accepted T112 retention chain, emits a fixed cohort
manifest and the deterministic 24 x 4 formal plan, and records the outstanding
Maintainer gates.  It does not import or call the native simulator bridge.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from sts_combat_rl.sim.t101_particle_convergence import (
    T101_SOURCE_COUNTS,
    validate_t101_input_admission,
)
from sts_combat_rl.sim.t112_sampler_seed_recovery import (
    T112_NATIVE_COMMIT,
    T112_NATIVE_REF,
    T112RecoveryError,
    validate_t112_cohort,
)
from sts_combat_rl.sim.t113_configured_particle_convergence import (
    T113_APPROVED_SPEC_COMMIT,
    T113_EXACT_NATIVE_BINARY_SHA256,
    T113_EXACT_NATIVE_MANIFEST_SHA256,
    T113_EXACT_T112_COHORT_SHA256,
    T113_EXACT_T112_FINAL_REPORT_SHA256,
    T113_EXACT_T112_RETENTION_SHA256,
    T113_INPUT_QUALIFICATION_SCHEMA,
    T113_NATIVE_IDENTITY,
    T113_READINESS_SCHEMA,
    T113_SEARCH_CONFIGURATION,
    T113_T112_COHORT_SCHEMA,
    T113_T112_FINAL_REPORT_SCHEMA,
    T113_T112_RETENTION_SCHEMA,
    T113_TASK_ID,
    T113ConvergenceError,
    build_t113_fixed_cohort,
    build_t113_formal_plan,
    validate_t113_fixed_cohort,
    validate_t113_formal_plan,
)

T113_BRANCH = "planner/t113-configured-particle-convergence"
T113_T101_RETENTION_SCHEMA = "t101-terminal-retention-manifest-v1"
T113_T101_INPUT_SCHEMA = "t101-input-admission-v1"
T113_NATIVE_MANIFEST_SCHEMA = "sts-lightspeed-source-manifest-v1"
T113_PREPARATION_MANIFEST_SCHEMA = "t113-preparation-retention-manifest-v1"


class T113WorkflowError(ValueError):
    """T113 retained inputs cannot be qualified or output would be unsafe."""


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _resolve_host_path(raw_path: object) -> Path:
    if not isinstance(raw_path, str) or not raw_path:
        raise T113WorkflowError("artifact path is missing")
    if os.name == "nt":
        match = re.fullmatch(r"/mnt/([a-zA-Z])/(.*)", raw_path.replace("\\", "/"))
        if match:
            drive, suffix = match.groups()
            return Path(f"{drive.upper()}:\\{suffix.replace('/', chr(92))}")
    return Path(raw_path)


def _read_json(path: Path, *, label: str) -> dict[str, Any]:
    try:
        raw = path.read_bytes()
        value = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise T113WorkflowError(f"{label} is unavailable or invalid JSON") from exc
    if not isinstance(value, Mapping):
        raise T113WorkflowError(f"{label} must be a JSON object")
    return dict(value)


def _artifact_reference(
    path: Path, *, schema_id: str | None = None
) -> dict[str, object]:
    resolved = path.resolve(strict=True)
    return {
        "path": str(resolved),
        "schema_id": schema_id,
        "size_bytes": resolved.stat().st_size,
        "sha256": _sha256_file(resolved),
    }


def _verify_reference(
    value: object,
    *,
    expected_schema: str | None = None,
    expected_sha256: str | None = None,
) -> tuple[dict[str, object], Path]:
    if not isinstance(value, Mapping):
        raise T113WorkflowError("retained artifact reference is malformed")
    path = _resolve_host_path(value.get("path"))
    try:
        resolved = path.resolve(strict=True)
        size = resolved.stat().st_size
        digest = _sha256_file(resolved)
    except OSError as exc:
        raise T113WorkflowError("a required retained artifact is unavailable") from exc
    schema = value.get("schema_id")
    if (
        (expected_schema is not None and schema != expected_schema)
        or (expected_sha256 is not None and digest != expected_sha256)
        or value.get("size_bytes") != size
        or value.get("sha256") != digest
    ):
        raise T113WorkflowError("retained artifact schema, size, or hash changed")
    return (
        {
            "path": str(resolved),
            "schema_id": schema,
            "size_bytes": size,
            "sha256": digest,
        },
        resolved,
    )


def _same_reference(left: object, right: object) -> bool:
    if not isinstance(left, Mapping) or not isinstance(right, Mapping):
        return False
    if any(
        left.get(field) != right.get(field)
        for field in ("schema_id", "size_bytes", "sha256")
    ):
        return False
    try:
        return (
            _resolve_host_path(left.get("path")).resolve()
            == _resolve_host_path(right.get("path")).resolve()
        )
    except (OSError, T113WorkflowError):
        return False


def _verify_nested_references(value: object) -> int:
    """Verify each fully formed path/schema/size/hash reference in a manifest."""

    seen: set[tuple[str, str]] = set()

    def visit(item: object) -> None:
        if isinstance(item, Mapping):
            if {"path", "size_bytes", "sha256"} <= set(item):
                key = (str(item.get("path")), str(item.get("sha256")))
                if key not in seen:
                    _verify_reference(item)
                    seen.add(key)
                return
            for child in item.values():
                visit(child)
        elif isinstance(item, list):
            for child in item:
                visit(child)

    visit(value)
    return len(seen)


def _current_worktree(repo_root: Path) -> dict[str, object]:
    try:
        head = subprocess.run(
            ["git", "-C", str(repo_root), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        branch = subprocess.run(
            ["git", "-C", str(repo_root), "branch", "--show-current"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        status = subprocess.run(
            ["git", "-C", str(repo_root), "status", "--porcelain"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout
        ancestry = subprocess.run(
            [
                "git",
                "-C",
                str(repo_root),
                "merge-base",
                "--is-ancestor",
                T113_APPROVED_SPEC_COMMIT,
                "HEAD",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise T113WorkflowError("cannot verify exact T113 worktree identity") from exc
    if (
        len(head) != 40
        or branch != T113_BRANCH
        or status.strip()
        or ancestry.returncode != 0
    ):
        raise T113WorkflowError(
            "T113 preparation requires the clean approved PR branch/head lineage"
        )
    return {"head": head, "branch": branch, "clean": True}


def _verify_native_manifest(
    path: Path, *, bound_ref: Mapping[str, object]
) -> dict[str, object]:
    current_ref = _artifact_reference(path, schema_id=T113_NATIVE_MANIFEST_SCHEMA)
    if (
        current_ref["sha256"] != T113_EXACT_NATIVE_MANIFEST_SHA256
        or current_ref["sha256"] != bound_ref.get("sha256")
        or current_ref["size_bytes"] != bound_ref.get("size_bytes")
        or current_ref["schema_id"] != bound_ref.get("schema_id")
    ):
        raise T113WorkflowError(
            "current native source manifest is not the retained T112 manifest"
        )
    manifest = _read_json(path, label="current native source manifest")
    integration = manifest.get("integration")
    if (
        manifest.get("schema_id") != T113_NATIVE_MANIFEST_SCHEMA
        or not isinstance(integration, Mapping)
        or integration.get("repository_url")
        != "https://github.com/lsmfttb/sts_lightspeed.git"
        or integration.get("branch") != "stsrl/main"
        or integration.get("ref") != T112_NATIVE_REF
        or integration.get("commit") != T112_NATIVE_COMMIT
    ):
        raise T113WorkflowError("native source manifest identity changed")
    return current_ref


def qualify_t113_inputs(
    *,
    t112_retention_manifest_path: Path,
    current_native_manifest_path: Path,
    repo_root: Path,
) -> dict[str, object]:
    """Revalidate the exact retained T112 chain without importing native code."""

    try:
        worktree = _current_worktree(repo_root)
        retention_path = t112_retention_manifest_path.resolve(strict=True)
        retention_sha = _sha256_file(retention_path)
        if retention_sha != T113_EXACT_T112_RETENTION_SHA256:
            raise T113WorkflowError("T112 terminal retention manifest hash changed")
        retention = _read_json(retention_path, label="T112 terminal retention manifest")
        if (
            retention.get("schema_id") != T113_T112_RETENTION_SCHEMA
            or retention.get("task_id") != "T112"
            or retention.get("terminal_classification")
            != "CONFIGURED_SEARCH_DOMAIN_SUPPORT_RECOVERED"
            or retention.get("candidate_execution_started") is not True
            or retention.get("candidate_execution_completed") is not True
            or retention.get("native_identity") not in (None, T113_NATIVE_IDENTITY)
        ):
            raise T113WorkflowError(
                "T112 retained terminal is not accepted support recovery"
            )
        references = retention.get("artifact_references")
        if not isinstance(references, Mapping):
            raise T113WorkflowError("T112 retention artifact references are missing")
        ref_count = _verify_nested_references(references)
        required_schemas = {
            "cohort_admission": T113_T112_COHORT_SCHEMA,
            "final_report": T113_T112_FINAL_REPORT_SCHEMA,
            "input_qualification": "t112-input-qualification-v1",
            "t101_retention_manifest": T113_T101_RETENTION_SCHEMA,
            "native_source_manifest": T113_NATIVE_MANIFEST_SCHEMA,
        }
        verified_refs: dict[str, dict[str, object]] = {}
        verified_paths: dict[str, Path] = {}
        for role, schema in required_schemas.items():
            ref, path = _verify_reference(references.get(role), expected_schema=schema)
            verified_refs[role] = ref
            verified_paths[role] = path
        if (
            verified_refs["cohort_admission"]["sha256"] != T113_EXACT_T112_COHORT_SHA256
            or verified_refs["final_report"]["sha256"]
            != T113_EXACT_T112_FINAL_REPORT_SHA256
        ):
            raise T113WorkflowError("T112 cohort/final-report identity changed")
        binary = references.get("native_binary")
        if (
            not isinstance(binary, Mapping)
            or binary.get("sha256") != T113_EXACT_NATIVE_BINARY_SHA256
        ):
            raise T113WorkflowError("accepted T112 native binary identity changed")
        _verify_reference(binary, expected_sha256=T113_EXACT_NATIVE_BINARY_SHA256)
        current_manifest_ref = _verify_native_manifest(
            current_native_manifest_path,
            bound_ref=verified_refs["native_source_manifest"],
        )

        t112_cohort = _read_json(
            verified_paths["cohort_admission"], label="T112 cohort admission"
        )
        try:
            checked_t112 = validate_t112_cohort(t112_cohort)
        except T112RecoveryError as exc:
            raise T113WorkflowError(
                "T112 cohort admission failed strict validation"
            ) from exc
        if checked_t112.get("schema_id") != T113_T112_COHORT_SCHEMA:
            raise T113WorkflowError("T112 cohort schema changed")
        final_report = _read_json(
            verified_paths["final_report"], label="T112 final report"
        )
        frozen_configuration = final_report.get("frozen_configuration")
        if (
            final_report.get("schema_id") != T113_T112_FINAL_REPORT_SCHEMA
            or final_report.get("task_id") != "T112"
            or final_report.get("terminal_classification")
            != "CONFIGURED_SEARCH_DOMAIN_SUPPORT_RECOVERED"
            or final_report.get("native_identity") != T113_NATIVE_IDENTITY
            or final_report.get("selected_counts") != {"A": 8, "B": 8, "C": 8}
            or final_report.get("selected_identities")
            != [row["selection_identity"] for row in checked_t112["selected"]]
            or not _same_reference(
                final_report.get("cohort_admission_artifact"),
                verified_refs["cohort_admission"],
            )
            or not isinstance(frozen_configuration, Mapping)
            or frozen_configuration.get("particle_count") != 2
            or frozen_configuration.get("search_simulations_per_particle") != 400
            or frozen_configuration.get("include_potions") is not False
        ):
            raise T113WorkflowError(
                "T112 final report does not bind the accepted cohort/configuration"
            )
        t112_qualification = _read_json(
            verified_paths["input_qualification"], label="T112 input qualification"
        )
        population = t112_qualification.get("source_population")
        if (
            t112_qualification.get("schema_id") != "t112-input-qualification-v1"
            or t112_qualification.get("task_id") != "T112"
            or t112_qualification.get("eligible") is not True
            or t112_qualification.get("candidate_execution_started") is not False
            or t112_qualification.get("candidate_execution_authorized") is not False
            or t112_qualification.get("native_identity") != T113_NATIVE_IDENTITY
            or not _same_reference(
                t112_qualification.get("current_native_source_manifest"),
                verified_refs["native_source_manifest"],
            )
            or not _same_reference(
                t112_qualification.get("t101_terminal_retention_manifest"),
                verified_refs["t101_retention_manifest"],
            )
            or not isinstance(population, Mapping)
            or population.get("record_count") != 413
            or population.get("attempted_count") != 413
            or population.get("source_counts") != T101_SOURCE_COUNTS
            or population.get("historical_t101_attempt_order_exact") is not True
            or population.get("ordered_identity_binding_sha256")
            != "a99fcd38ea6e5c14190b0964c8ec5a04fc40f501d91ab4409c7205bc8b3677bb"
        ):
            raise T113WorkflowError(
                "T112 source population/restore provenance binding is incomplete"
            )

        t101_manifest = _read_json(
            verified_paths["t101_retention_manifest"],
            label="historical T101 terminal retention manifest",
        )
        if (
            t101_manifest.get("schema_id") != T113_T101_RETENTION_SCHEMA
            or t101_manifest.get("task_id") != "T101"
            or t101_manifest.get("terminal_classification")
            != "SUPPORTED_COHORT_INSUFFICIENT"
        ):
            raise T113WorkflowError("historical T101 provenance manifest changed")
        t101_refs = t101_manifest.get("artifact_references")
        if not isinstance(t101_refs, Mapping):
            raise T113WorkflowError("historical T101 artifact references are missing")
        t101_ref_count = _verify_nested_references(t101_refs)
        input_ref, input_path = _verify_reference(
            t101_refs.get("input_admission"), expected_schema=T113_T101_INPUT_SCHEMA
        )
        input_admission = _read_json(
            input_path, label="historical T101 input admission"
        )
        try:
            validate_t101_input_admission(input_admission)
        except Exception as exc:
            raise T113WorkflowError(
                "historical T101 artifact eligibility did not revalidate"
            ) from exc
        if input_admission.get("eligible") is not True:
            raise T113WorkflowError("historical T101 input eligibility is not accepted")

        population_binding = {
            "t101_terminal_retention_manifest_sha256": verified_refs[
                "t101_retention_manifest"
            ]["sha256"],
            "t101_input_admission_sha256": input_ref["sha256"],
            "ordered_identity_binding_sha256": population[
                "ordered_identity_binding_sha256"
            ],
            "record_count": population["record_count"],
            "source_counts": dict(T101_SOURCE_COUNTS),
            "historical_t101_attempt_order_exact": True,
            "t101_retained_reference_count_verified": t101_ref_count,
        }
        t112_binding = {
            "retention_manifest_sha256": retention_sha,
            "cohort_admission": verified_refs["cohort_admission"],
            "final_report": verified_refs["final_report"],
            "input_qualification": verified_refs["input_qualification"],
        }
        cohort = build_t113_fixed_cohort(
            checked_t112,
            source_cohort_sha256=str(verified_refs["cohort_admission"]["sha256"]),
            source_population_binding=population_binding,
            t112_artifact_binding=t112_binding,
        )
        return {
            "schema_id": T113_INPUT_QUALIFICATION_SCHEMA,
            "task_id": T113_TASK_ID,
            "approved_spec_commit": T113_APPROVED_SPEC_COMMIT,
            "implementation_head": worktree["head"],
            "implementation_worktree": str(repo_root.resolve(strict=True)),
            "eligible": True,
            "candidate_execution_started": False,
            "execution_authorized": False,
            "canary_authorized": False,
            "artifact_qualification_status": "QUALIFIED",
            "artifact_reference_count_verified": ref_count,
            "native_identity": dict(T113_NATIVE_IDENTITY),
            "native_source_manifest": current_manifest_ref,
            "native_binary_sha256": T113_EXACT_NATIVE_BINARY_SHA256,
            "t112_terminal_retention_manifest": _artifact_reference(
                retention_path, schema_id=T113_T112_RETENTION_SCHEMA
            ),
            "t112_artifact_references": verified_refs,
            "t112_terminal_classification": final_report["terminal_classification"],
            "source_population_binding": dict(population),
            "source_t101_input_admission": input_ref,
            "fixed_cohort": cohort,
            "frozen_search_configuration": dict(T113_SEARCH_CONFIGURATION),
            "seed_contract": {
                "algorithm": "SHA256(T101-v1 || selection_identity || decimal_replicate)_first_8_bytes_u64be",
                "bridge_seed_field": "sampler_seed_input",
                "particle_seed_field": "native-derived metadata; no equality to bridge input required",
                "python_native_seed_mixing": False,
            },
            "historical_t101_artifacts_rewritten": False,
            "native_simulator_or_bridge_called": False,
        }
    except T113ConvergenceError as exc:
        raise T113WorkflowError(str(exc)) from exc


def _write_new_json(path: Path, value: Mapping[str, object]) -> dict[str, object]:
    if path.exists():
        raise T113WorkflowError(f"refusing to overwrite existing artifact: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    with path.open("xb") as stream:
        stream.write(encoded)
        stream.flush()
        os.fsync(stream.fileno())
    return _artifact_reference(path, schema_id=value.get("schema_id"))


def prepare_t113_from_paths(
    *,
    t112_retention_manifest_path: Path,
    native_manifest_path: Path,
    artifact_root: Path,
    repo_root: Path,
) -> dict[str, object]:
    """Write qualification, fixed cohort, formal plan, and non-authorizing readiness."""

    if artifact_root.exists():
        raise T113WorkflowError(
            "refusing to overwrite an existing T113 preparation root"
        )
    qualification = qualify_t113_inputs(
        t112_retention_manifest_path=t112_retention_manifest_path,
        current_native_manifest_path=native_manifest_path,
        repo_root=repo_root,
    )
    fixed_cohort = qualification.get("fixed_cohort")
    if not isinstance(fixed_cohort, Mapping):
        raise T113WorkflowError("qualified T113 fixed cohort is unavailable")
    fixed_cohort = validate_t113_fixed_cohort(fixed_cohort)
    qualification_ref = _write_new_json(
        artifact_root / "t113-input-qualification.json", qualification
    )
    cohort_ref = _write_new_json(
        artifact_root / "t113-fixed-cohort-manifest.json", fixed_cohort
    )
    plan = build_t113_formal_plan(
        fixed_cohort,
        implementation_head=str(qualification["implementation_head"]),
        input_qualification_sha256=str(qualification_ref["sha256"]),
        fixed_cohort_sha256=str(cohort_ref["sha256"]),
    )
    plan = validate_t113_formal_plan(plan)
    plan_ref = _write_new_json(artifact_root / "t113-formal-execution-plan.json", plan)
    readiness = {
        "schema_id": T113_READINESS_SCHEMA,
        "task_id": T113_TASK_ID,
        "implementation_head": qualification["implementation_head"],
        "approved_spec_commit": T113_APPROVED_SPEC_COMMIT,
        "qualification_artifact": qualification_ref,
        "fixed_cohort_artifact": cohort_ref,
        "formal_plan_artifact": plan_ref,
        "artifact_qualification_status": "QUALIFIED",
        "preparation_only": True,
        "native_simulator_or_bridge_called": False,
        "canary_authorized": False,
        "canary_started": False,
        "formal_execution_authorized": False,
        "formal_execution_started": False,
        "execution_authorization_created": False,
        "frozen_search_configuration": dict(T113_SEARCH_CONFIGURATION),
        "resource_gate": {
            "status": "BLOCKED_UNTIL_MEASURED_CANARY_AND_MAINTAINER_AUTHORIZATION",
            "max_effective_concurrency": 4,
            "aggregate_memory_proof_required": True,
        },
        "next_action": "Maintainer independently reviews exact-head qualification, then separately authorizes the direct canary and resource plan.",
    }
    readiness_ref = _write_new_json(
        artifact_root / "t113-readiness-preparation.json", readiness
    )
    manifest = {
        "schema_id": T113_PREPARATION_MANIFEST_SCHEMA,
        "task_id": T113_TASK_ID,
        "implementation_head": qualification["implementation_head"],
        "approved_spec_commit": T113_APPROVED_SPEC_COMMIT,
        "terminal_classification": None,
        "candidate_execution_started": False,
        "artifact_references": {
            "input_qualification": qualification_ref,
            "fixed_cohort": cohort_ref,
            "formal_plan": plan_ref,
            "readiness_preparation": readiness_ref,
            "t112_terminal_retention_manifest": qualification[
                "t112_terminal_retention_manifest"
            ],
            "native_source_manifest": qualification["native_source_manifest"],
        },
        "retention_reason": "Retain exact T112 cohort/source/native qualification and non-authorizing T113 readiness for Maintainer review.",
        "deletion_condition": "Delete only after T113 artifact and lifecycle review has no audit consumers.",
    }
    manifest_ref = _write_new_json(
        artifact_root / "t113-preparation-retention-manifest.json", manifest
    )
    return {
        "qualification": qualification,
        "qualification_artifact": qualification_ref,
        "fixed_cohort": fixed_cohort,
        "fixed_cohort_artifact": cohort_ref,
        "formal_plan": plan,
        "formal_plan_artifact": plan_ref,
        "readiness": readiness,
        "readiness_artifact": readiness_ref,
        "preparation_manifest_artifact": manifest_ref,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Qualify T113 retained inputs and prepare a non-authorizing formal plan."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    prepare = subparsers.add_parser("prepare")
    prepare.add_argument("--t112-retention-manifest", type=Path, required=True)
    prepare.add_argument("--native-source-manifest", type=Path, required=True)
    prepare.add_argument("--artifact-root", type=Path, required=True)
    prepare.add_argument("--repo-root", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = prepare_t113_from_paths(
            t112_retention_manifest_path=args.t112_retention_manifest,
            native_manifest_path=args.native_source_manifest,
            artifact_root=args.artifact_root,
            repo_root=args.repo_root,
        )
    except (OSError, T113WorkflowError, T113ConvergenceError) as exc:
        print(f"T113 preparation failed closed: {exc}", file=sys.stderr)
        return 2
    output = {
        "state": "PREPARED_NON_AUTHORIZING",
        "qualification_artifact": result["qualification_artifact"],
        "fixed_cohort_artifact": result["fixed_cohort_artifact"],
        "formal_plan_artifact": result["formal_plan_artifact"],
        "readiness_artifact": result["readiness_artifact"],
        "preparation_manifest_artifact": result["preparation_manifest_artifact"],
        "native_simulator_or_bridge_called": False,
        "execution_authorization_created": False,
    }
    print(json.dumps(output, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "T113WorkflowError",
    "main",
    "prepare_t113_from_paths",
    "qualify_t113_inputs",
]
