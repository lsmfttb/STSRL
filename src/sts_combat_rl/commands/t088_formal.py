"""Explicit path-bound T088 formal shard and raw-evidence finalizer command."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path

from sts_combat_rl.commands import t088_canary as canary_paths
from sts_combat_rl.commands.t088_classical_combat_tournament import (
    t088_controller_definitions,
)
from sts_combat_rl.sim.t088_canary_execution import T088NativeCanaryRecordRunner
from sts_combat_rl.sim.t088_formal_execution import (
    T088_FORMAL_AUTHORIZATION_SCHEMA_ID,
    T088_FORMAL_DEFAULT_SHARD_COUNT,
    T088_FORMAL_SHARD_ASSIGNMENT,
    T088_FORMAL_SHARD_SCHEMA_ID,
    _canonical_sha256,
    execute_t088_authorized_formal_shard,
    merge_t088_authorized_formal_shards,
    validate_t088_accepted_canary_evidence,
    validate_t088_formal_authorization,
    write_t088_formal_raw_evidence,
    write_t088_formal_shard,
)
from sts_combat_rl.sim.t088_tournament_workflow import (
    _binding_identity,
    build_t088_formal_plan,
)


class T088FormalPathError(ValueError):
    """A retained formal input, authorization, or output boundary failed."""


def _canary_reference(path: Path) -> tuple[dict[str, object], dict[str, object]]:
    document, identity = canary_paths._read_exact_json(
        path,
        expected_sha256=None,
        schema_id="t088-canary-evidence-v1",
        label="T088 accepted canary evidence",
    )
    return document, {
        "path": identity["path"],
        "sha256": identity["sha256"],
        "size_bytes": identity["byte_count"],
        "schema_id": identity["schema_id"],
    }


def _admit_formal_context(
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
) -> tuple[list[dict[str, object]], dict[str, object], object, dict[str, object]]:
    formal, gate, inputs = canary_paths._admit_t088_canary_inputs_from_paths(
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
    source = getattr(gate, "source_selection_manifest_identity", None)
    if not isinstance(maps, Mapping) or not isinstance(source, Mapping):
        raise T088FormalPathError("admitted T087/T085 input gate is malformed")
    references = (
        inputs["t087_formal"],
        inputs["t087_report"],
        inputs["t087_retention"],
    )
    if not all(isinstance(value, Mapping) for value in references):
        raise T088FormalPathError("admitted T087 references are malformed")
    cohort = canary_paths._project_t087_cohort(formal, source, maps)
    binding = canary_paths._build_t087_cohort_binding(
        cohort,
        source_identity=source,
        formal_reference=references[0],
        report_reference=references[1],
        retention_reference=references[2],
    )
    return cohort, binding, gate, inputs


def prepare_t088_formal_authorization_from_paths(
    *,
    canary_evidence_path: Path,
    artifact_root: Path,
    shard_count: int = 16,
    worker_count: int = 16,
    **paths: object,
) -> dict[str, object]:
    """Emit a non-authorizing exact formal-authorization template."""

    cohort, binding, _gate, inputs = _admit_formal_context(**paths)  # type: ignore[arg-type]
    evidence, reference = _canary_reference(canary_evidence_path)
    validate_t088_accepted_canary_evidence(evidence, cohort_binding=binding)
    root = str(artifact_root.resolve())
    plan = build_t088_formal_plan(cohort, cohort_binding=binding)
    topology = {
        "shard_count": shard_count,
        "worker_count": worker_count,
        "assignment": T088_FORMAL_SHARD_ASSIGNMENT,
    }
    identity = {
        "schema_id": T088_FORMAL_AUTHORIZATION_SCHEMA_ID,
        "task_id": "T088",
        "authorization_kind": "formal_tournament",
        "implementation_head": paths["implementation_head"],
        "input_identities_sha256": _canonical_sha256(inputs),
        "canary_evidence": reference,
        "t087_cohort_binding": _binding_identity(binding),
        "controller_definitions_sha256": _canonical_sha256(
            t088_controller_definitions()
        ),
        "formal_plan_sha256": _canonical_sha256(plan),
        "shard_topology": topology,
        "output_root": root,
    }
    # Full validation deliberately remains in the execution path; preparation
    # must never construct an adapter or authorize a run.
    return {
        "schema_id": "t088-formal-authorization-preparation-v1",
        "task_id": "T088",
        "preparation_only": True,
        "inputs": inputs,
        "canary_evidence": reference,
        "authorization_identity": identity,
        "authorization_template": {
            **identity,
            "authorized": None,
            "authorization_id": None,
            "maintainer_attestation": {
                "role": "maintainer",
                "decision": "FORMAL_AUTHORIZED",
                "exact_head": paths["implementation_head"],
            },
        },
        "canary_evidence_schema": evidence.get("schema_id"),
    }


def _output_path(path: Path, root: Path, label: str) -> tuple[Path, str]:
    resolved, root_resolved = path.resolve(), root.resolve()
    try:
        resolved.relative_to(root_resolved)
    except ValueError as exc:
        raise T088FormalPathError(
            f"{label} must remain under its retention root"
        ) from exc
    if resolved.exists():
        raise T088FormalPathError(f"refusing to overwrite retained {label}")
    return resolved, str(root_resolved)


def run_t088_authorized_formal_shard_from_paths(
    *,
    authorization_path: Path,
    canary_evidence_path: Path,
    output_path: Path,
    artifact_root: Path,
    shard_index: int,
    shard_count: int = 16,
    worker_count: int = 16,
    adapter_factory: Callable[[], object] | None = None,
    runner_factory: Callable[..., object] = T088NativeCanaryRecordRunner,
    **paths: object,
) -> dict[str, object]:
    """Run exactly one complete formal shard after all offline gates pass."""

    cohort, binding, gate, inputs = _admit_formal_context(**paths)  # type: ignore[arg-type]
    authorization, _ = canary_paths._read_exact_json(
        authorization_path,
        expected_sha256=None,
        schema_id=T088_FORMAL_AUTHORIZATION_SCHEMA_ID,
        label="T088 formal authorization",
    )
    canary_evidence, canary_reference = _canary_reference(canary_evidence_path)
    destination, root = _output_path(output_path, artifact_root, "formal shard")
    validate_t088_formal_authorization(
        authorization,
        implementation_head=paths["implementation_head"],  # type: ignore[arg-type]
        input_identities=inputs,
        canary_evidence_reference=canary_reference,
        canary_evidence=canary_evidence,
        cohort_rows=cohort,
        cohort_binding=binding,
        shard_index=shard_index,
        shard_count=shard_count,
        worker_count=worker_count,
        output_root=root,
    )
    if adapter_factory is None:
        adapter_factory = canary_paths._default_adapter_factory
    maps = getattr(gate, "canonical_records_by_cohort", None)
    if not isinstance(maps, Mapping):
        raise T088FormalPathError("admitted canonical record maps are unavailable")
    selected = {
        record.selection_identity: record
        for cohort_name in ("A", "B", "C")
        for record in gate.cohorts[cohort_name]
    }
    runner = runner_factory(
        adapter_factory=adapter_factory,
        selected_records=selected,
        canonical_records_by_cohort=maps,
        worker_count=worker_count,
    )
    shard = execute_t088_authorized_formal_shard(
        authorization=authorization,
        implementation_head=paths["implementation_head"],  # type: ignore[arg-type]
        input_identities=inputs,
        canary_evidence_reference=canary_reference,
        canary_evidence=canary_evidence,
        cohort_rows=cohort,
        cohort_binding=binding,
        shard_index=shard_index,
        shard_count=shard_count,
        worker_count=worker_count,
        output_root=root,
        runner=runner,  # type: ignore[arg-type]
    )
    return {"artifact": write_t088_formal_shard(destination, shard), "shard": shard}


def finalize_t088_formal_from_paths(
    *,
    authorization_path: Path,
    canary_evidence_path: Path,
    shard_paths: Sequence[Path],
    output_path: Path,
    artifact_root: Path,
    **paths: object,
) -> dict[str, object]:
    """Read complete retained shards and atomically write the one raw matrix."""

    cohort, binding, _gate, inputs = _admit_formal_context(**paths)  # type: ignore[arg-type]
    authorization, _ = canary_paths._read_exact_json(
        authorization_path,
        expected_sha256=None,
        schema_id=T088_FORMAL_AUTHORIZATION_SCHEMA_ID,
        label="T088 formal authorization",
    )
    canary_evidence, canary_reference = _canary_reference(canary_evidence_path)
    destination, root = _output_path(output_path, artifact_root, "formal raw evidence")
    shards = [
        canary_paths._read_exact_json(
            path,
            expected_sha256=None,
            schema_id=T088_FORMAL_SHARD_SCHEMA_ID,
            label="T088 formal shard",
        )[0]
        for path in shard_paths
    ]
    evidence = merge_t088_authorized_formal_shards(
        authorization=authorization,
        implementation_head=paths["implementation_head"],  # type: ignore[arg-type]
        input_identities=inputs,
        canary_evidence_reference=canary_reference,
        canary_evidence=canary_evidence,
        cohort_rows=cohort,
        cohort_binding=binding,
        output_root=root,
        shards=shards,
    )
    return {
        "artifact": write_t088_formal_raw_evidence(destination, evidence),
        "evidence": evidence,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--prepare-authorization", action="store_true")
    modes.add_argument("--finalize", action="store_true")
    parser.add_argument("--authorization", type=Path)
    parser.add_argument("--canary-evidence", type=Path, required=True)
    parser.add_argument("--implementation-head", required=True)
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
    parser.add_argument("--output", type=Path)
    parser.add_argument("--artifact-root", type=Path)
    parser.add_argument("--shard-index", type=int, default=0)
    parser.add_argument(
        "--shard-count", type=int, default=T088_FORMAL_DEFAULT_SHARD_COUNT
    )
    parser.add_argument(
        "--worker-count", type=int, default=T088_FORMAL_DEFAULT_SHARD_COUNT
    )
    parser.add_argument("--shard-evidence", type=Path, action="append", default=[])
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    common = {
        "implementation_head": args.implementation_head,
        "t087_formal_path": args.t087_formal,
        "t087_report_path": args.t087_report,
        "t087_retention_path": args.t087_retention,
        "t085_selection_path": args.t085_selection,
        "t085_restore_path": args.t085_restore,
        "a_pool_path": args.a_pool,
        "b_pool_path": args.b_pool,
        "c_pool_path": args.c_pool,
        "b_source_manifest_path": args.b_source_manifest,
        "c_source_manifest_path": args.c_source_manifest,
    }
    try:
        if args.prepare_authorization:
            if args.artifact_root is None:
                raise T088FormalPathError(
                    "artifact root is required for authorization preparation"
                )
            result = prepare_t088_formal_authorization_from_paths(
                canary_evidence_path=args.canary_evidence,
                artifact_root=args.artifact_root,
                shard_count=args.shard_count,
                worker_count=args.worker_count,
                **common,
            )
            print(json.dumps(result, sort_keys=True, ensure_ascii=False))
            return 0
        if (
            args.authorization is None
            or args.output is None
            or args.artifact_root is None
        ):
            raise T088FormalPathError(
                "authorization, output, and artifact root are required"
            )
        if args.finalize:
            result = finalize_t088_formal_from_paths(
                authorization_path=args.authorization,
                canary_evidence_path=args.canary_evidence,
                shard_paths=args.shard_evidence,
                output_path=args.output,
                artifact_root=args.artifact_root,
                **common,
            )
        else:
            result = run_t088_authorized_formal_shard_from_paths(
                authorization_path=args.authorization,
                canary_evidence_path=args.canary_evidence,
                output_path=args.output,
                artifact_root=args.artifact_root,
                shard_index=args.shard_index,
                shard_count=args.shard_count,
                worker_count=args.worker_count,
                **common,
            )
    except (OSError, TypeError, ValueError) as exc:
        print(f"T088 formal command failed: {exc}", file=sys.stderr)
        return 2
    artifact = result.get("artifact")
    if not isinstance(artifact, Mapping):
        print(
            "T088 formal command failed: retained artifact reference is missing",
            file=sys.stderr,
        )
        return 2
    print(
        json.dumps(
            {
                "schema_id": "t088-formal-command-result-v1",
                "task_id": "T088",
                "artifact": dict(artifact),
            },
            sort_keys=True,
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "T088FormalPathError",
    "build_parser",
    "finalize_t088_formal_from_paths",
    "main",
    "prepare_t088_formal_authorization_from_paths",
    "run_t088_authorized_formal_shard_from_paths",
]
