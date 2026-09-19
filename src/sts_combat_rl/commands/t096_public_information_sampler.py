"""T096 sampler pilot workflow.

The workflow accepts an already-authorized native anchor loader.  It never
constructs hidden simulator state in Python; its role is validation, report
assembly, and retention metadata around :mod:`sim.t096_public_information_sampler`.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

from sts_combat_rl.sim.t096_public_information_sampler import (
    T096_PARTICLES_PER_ANCHOR,
    T096_SAMPLER_SCHEMA_ID,
    T096_TASK_ID,
    audit_native_particles,
    canonical_json,
    classify_t096,
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run_t096_anchor_audits(
    *,
    anchor_loader: Callable[[Mapping[str, Any]], tuple[Any, Any]],
    anchors: Sequence[Mapping[str, Any]],
    sampler_seed: int,
    particle_count: int = T096_PARTICLES_PER_ANCHOR,
    fidelity_gaps: Sequence[str] = (),
) -> dict[str, Any]:
    """Run explicit anchor audits using native adapter/restore callbacks.

    ``anchor_loader`` returns ``(adapter, snapshot)``.  It is deliberately
    supplied by the caller so the task's accepted checkpoint/restore lineage
    remains explicit and cannot be guessed from filenames.
    """

    if not anchors:
        raise ValueError("T096 requires at least one explicit anchor")
    rows: list[dict[str, Any]] = []
    for index, anchor in enumerate(anchors):
        if not isinstance(anchor, Mapping):
            raise TypeError(f"T096 anchor {index} is not a mapping")
        adapter, snapshot = anchor_loader(anchor)
        row = audit_native_particles(
            adapter,
            snapshot,
            sampler_seed=sampler_seed + index,
            particle_count=particle_count,
        )
        row["anchor_index"] = index
        row["anchor_identity"] = dict(anchor)
        rows.append(row)
        close = getattr(adapter, "close", None)
        if callable(close):
            close()
    return {
        "schema_id": "t096-public-information-sampler-report-v1",
        "task_id": T096_TASK_ID,
        "sampler_schema_id": T096_SAMPLER_SCHEMA_ID,
        "sampler_configuration": {
            "seed_domain": "native sampler seed + anchor index",
            "base_seed": sampler_seed,
            "particle_count_per_anchor": particle_count,
            "accepted_particle_definition": "native row with exact public and ordered legal-action parity",
        },
        "anchor_count": len(rows),
        "anchors": rows,
        "fidelity_gaps": list(fidelity_gaps),
        "terminal_classification": classify_t096(rows, fidelity_gaps=fidelity_gaps),
        "private_audit_firewall": {
            "hidden_future_fingerprint_used_for": "diversity evidence only",
            "next_draw_card_id_used_for": "distribution statistic only",
            "controller_model_input": "not constructed by this workflow",
        },
    }


def write_t096_report(
    report: Mapping[str, Any],
    *,
    report_path: Path,
    artifact_root: Path,
    input_references: Mapping[str, Any],
    implementation_head: str,
    native_identity: Mapping[str, Any],
) -> dict[str, Any]:
    """Write current-schema report and retention manifest atomically enough for audit."""

    artifact_root.mkdir(parents=True, exist_ok=True)
    report_payload = dict(report)
    report_payload["implementation_head"] = implementation_head
    report_payload["native_identity"] = dict(native_identity)
    report_payload["input_references"] = dict(input_references)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(canonical_json(report_payload) + "\n", encoding="utf-8")
    report_ref = {
        "path": str(report_path.resolve()),
        "schema_id": "t096-public-information-sampler-report-v1",
        "sha256": sha256_file(report_path),
        "byte_count": report_path.stat().st_size,
    }
    manifest = {
        "schema_id": "t096-public-information-sampler-retention-v1",
        "task_id": T096_TASK_ID,
        "terminal_classification": report_payload["terminal_classification"],
        "implementation_head": implementation_head,
        "native_identity": dict(native_identity),
        "input_references": dict(input_references),
        "artifact_references": {"report": report_ref},
        "raw_deletion_condition": "retain while T096 or its successor relies on the pilot claim",
    }
    manifest_path = artifact_root / "t096-retention-manifest.json"
    manifest_path.write_text(canonical_json(manifest) + "\n", encoding="utf-8")
    return {
        "report": report_ref,
        "manifest": {
            "path": str(manifest_path.resolve()),
            "schema_id": manifest["schema_id"],
            "sha256": sha256_file(manifest_path),
            "byte_count": manifest_path.stat().st_size,
        },
        "terminal_classification": report_payload["terminal_classification"],
    }
