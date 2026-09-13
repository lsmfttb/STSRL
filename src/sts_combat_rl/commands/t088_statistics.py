"""Path-bound, non-simulator T088 statistical publication command."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path

from sts_combat_rl.commands import t088_canary as canary_paths
from sts_combat_rl.commands import t088_formal
from sts_combat_rl.commands.t088_classical_combat_tournament import (
    t088_controller_definitions,
)
from sts_combat_rl.sim.t088_formal_execution import (
    T088_FORMAL_RAW_EVIDENCE_SCHEMA_ID,
    _canonical_sha256,
    _StreamingShardJson,
    validate_t088_formal_authorization,
)
from sts_combat_rl.sim.t088_tournament_workflow import (
    T088_ARMS,
    T088_FORMAL_EXECUTIONS,
    T088IncompleteError,
    build_t088_formal_plan,
    paired_t088_comparison,
    select_t088_challenger,
)


class T088StatisticsPathError(ValueError):
    """A retained T088 input or publication boundary failed closed."""


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _reference(path: Path, schema_id: str) -> dict[str, object]:
    resolved = path.resolve(strict=True)
    return {
        "path": str(resolved),
        "sha256": _sha256_file(resolved),
        "size_bytes": resolved.stat().st_size,
        "schema_id": schema_id,
    }


def _write_new(path: Path, document: Mapping[str, object]) -> dict[str, object]:
    destination = path.resolve()
    if destination.exists():
        raise T088StatisticsPathError("refusing to overwrite retained artifact")
    destination.parent.mkdir(parents=True, exist_ok=True)
    encoded = (
        json.dumps(
            dict(document),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode()
        + b"\n"
    )
    try:
        descriptor = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(encoded)
    except OSError as exc:
        raise T088StatisticsPathError(
            "cannot atomically create retained artifact"
        ) from exc
    return {
        "path": str(destination),
        "sha256": hashlib.sha256(encoded).hexdigest(),
        "size_bytes": len(encoded),
        "schema_id": document["schema_id"],
    }


def _stream_compact_rows(
    path: Path,
    *,
    authorization: Mapping[str, object],
    implementation_head: str,
    inputs: Mapping[str, object],
    cohort: Sequence[Mapping[str, object]],
    binding: Mapping[str, object],
    canary_reference: Mapping[str, object],
) -> list[dict[str, object]]:
    """Decode raw rows one at a time; retain only paired-analysis fields."""

    reader = _StreamingShardJson(path.resolve(strict=True))
    plan = build_t088_formal_plan(cohort, cohort_binding=binding)
    expected = plan["rows"]
    if not isinstance(expected, Sequence):
        raise T088StatisticsPathError("formal plan rows are unavailable")
    compact: list[dict[str, object]] = []
    try:
        for ordinal, row in enumerate(reader.rows()):
            if ordinal >= len(expected) or not isinstance(expected[ordinal], Mapping):
                raise T088StatisticsPathError("raw evidence rows exceed canonical plan")
            planned = expected[ordinal]
            if row.get("arm") != planned.get("arm") or row.get(
                "selection_identity"
            ) != planned.get("selection_identity"):
                raise T088StatisticsPathError(
                    "raw evidence is not in canonical cohort order"
                )
            for key in (
                "cohort",
                "outcome",
                "dense_diagnostic",
                "work_counters",
                "wall_clock_time_s",
            ):
                if key not in row:
                    raise T088StatisticsPathError(
                        "raw evidence row lacks required analysis field"
                    )
            compact.append(
                {
                    key: row[key]
                    for key in (
                        "arm",
                        "selection_identity",
                        "cohort",
                        "outcome",
                        "dense_diagnostic",
                        "work_counters",
                        "wall_clock_time_s",
                    )
                }
            )
        metadata = reader.metadata
    finally:
        reader.close()
    if len(compact) != T088_FORMAL_EXECUTIONS:
        raise T088StatisticsPathError("raw evidence is incomplete")
    expected_metadata = {
        "schema_id": T088_FORMAL_RAW_EVIDENCE_SCHEMA_ID,
        "task_id": "T088",
        "formal_execution_authorized": True,
        "implementation_head": implementation_head,
        "authorization": dict(authorization),
        "input_identities_sha256": _canonical_sha256(inputs),
        "canary_evidence": dict(canary_reference),
        "t087_cohort_binding": binding.get("ordered_cohort_entries_sha256"),
        "controller_definitions": t088_controller_definitions(),
        "formal_plan_sha256": _canonical_sha256(plan),
    }
    for key, value in expected_metadata.items():
        if metadata.get(key) != value:
            raise T088StatisticsPathError(
                f"raw evidence {key} identity is not accepted"
            )
    if metadata.get("execution_count") != T088_FORMAL_EXECUTIONS:
        raise T088StatisticsPathError("raw evidence count is incomplete")
    return compact


def run_t088_statistics_from_paths(
    *,
    authorization_path: Path,
    canary_evidence_path: Path,
    raw_evidence_path: Path,
    artifact_root: Path,
    **paths: object,
) -> dict[str, object]:
    """Validate then publish all current T088 analysis artifacts; never simulates."""

    cohort, binding, _gate, inputs = t088_formal._admit_formal_context(**paths)  # type: ignore[arg-type]
    authorization, _ = canary_paths._read_exact_json(
        authorization_path,
        expected_sha256=None,
        schema_id="t088-maintainer-formal-authorization-v1",
        label="T088 formal authorization",
    )
    canary, canary_reference = t088_formal._canary_reference(canary_evidence_path)
    root = str(artifact_root.resolve())
    try:
        validate_t088_formal_authorization(
            authorization,
            implementation_head=str(paths["implementation_head"]),
            input_identities=inputs,
            canary_evidence_reference=canary_reference,
            canary_evidence=canary,
            cohort_rows=cohort,
            cohort_binding=binding,
            shard_index=0,
            shard_count=16,
            worker_count=16,
            output_root=root,
        )
    except (T088IncompleteError, TypeError, ValueError) as exc:
        raise T088StatisticsPathError("formal authorization is not accepted") from exc
    raw_reference = _reference(raw_evidence_path, T088_FORMAL_RAW_EVIDENCE_SCHEMA_ID)
    rows = _stream_compact_rows(
        raw_evidence_path,
        authorization=authorization,
        implementation_head=str(paths["implementation_head"]),
        inputs=inputs,
        cohort=cohort,
        binding=binding,
        canary_reference=canary_reference,
    )
    pairs = (("B", "A"), ("C", "A"), ("D", "A"), ("B", "C"), ("B", "D"), ("C", "D"))
    comparisons = [
        paired_t088_comparison(rows, candidate_arm=a, reference_arm=b) for a, b in pairs
    ]
    costs = {
        arm: {
            "successor_transition_count": sum(
                int(row["work_counters"]["successor_transition_count"])
                for row in rows
                if row["arm"] == arm
            )
            / 413,
            "wall_clock_time_s": sum(
                float(row["wall_clock_time_s"]) for row in rows if row["arm"] == arm
            )
            / 413,
        }
        for arm in T088_ARMS
    }
    selection = select_t088_challenger(comparisons, cost_by_arm=costs)
    report = {
        "schema_id": "t088-statistics-report-v1",
        "task_id": "T088",
        "formal_raw_evidence": raw_reference,
        "paired_comparisons": comparisons,
        "selection": selection,
    }
    # Validate everything before the first publication.  These schemas retain an
    # explicit empty blind bundle when no unique challenger is available.
    selected = selection["selected_challenger"]
    blind = {
        "schema_id": "t088-blind-audit-bundle-v1",
        "pairs": [],
        "selected_challenger": selected,
    }
    hidden = {"schema_id": "t088-blind-audit-hidden-provenance-v1", "pairs": []}
    final = {
        "schema_id": "t088-final-tournament-report-v1",
        "task_id": "T088",
        "terminal_classification": selection["terminal_classification"],
        "selected_challenger": selected,
        "paired_comparisons": comparisons,
    }
    root_path = artifact_root.resolve()
    references = {
        "statistics_report": _write_new(
            root_path / "t088-statistics-report.json", report
        ),
        "blind_bundle": _write_new(root_path / "t088-blind-audit-bundle.json", blind),
        "blind_provenance": _write_new(
            root_path / "t088-blind-audit-hidden-provenance.json", hidden
        ),
        "final_report": _write_new(root_path / "t088-final-report.json", final),
    }
    manifest = {
        "schema_id": "t088-retention-manifest-v1",
        "task_id": "T088",
        "formal_raw_evidence": raw_reference,
        "artifacts": references,
    }
    references["retention_manifest"] = _write_new(
        root_path / "t088-retention-manifest.json", manifest
    )
    return {
        "schema_id": "t088-statistics-command-result-v1",
        "task_id": "T088",
        "artifacts": references,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--authorization", type=Path, required=True)
    parser.add_argument("--canary-evidence", type=Path, required=True)
    parser.add_argument("--raw-evidence", type=Path, required=True)
    parser.add_argument("--artifact-root", type=Path, required=True)
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
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = run_t088_statistics_from_paths(
            authorization_path=args.authorization,
            canary_evidence_path=args.canary_evidence,
            raw_evidence_path=args.raw_evidence,
            artifact_root=args.artifact_root,
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
        )
    except (OSError, TypeError, ValueError) as exc:
        print(f"T088 statistics command failed: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, sort_keys=True, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
