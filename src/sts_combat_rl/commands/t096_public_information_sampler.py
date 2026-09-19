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
    canonical_sha256,
    classify_t096,
    validate_anchor_distribution_metadata,
    validate_public_information_projection,
)

T096_ANCHOR_SELECTION_SCHEMA_ID = "t096-frozen-t087-anchor-selection-v1"


def select_first_four_frozen_t087_anchors(
    *,
    ordered_rows: Sequence[Mapping[str, Any]],
    anchor_loader: Callable[[Mapping[str, Any]], tuple[Any, Any]],
    required_count: int = 4,
) -> dict[str, Any]:
    """Select the first eligible rows in the accepted T087 canonical order.

    Selection only reads native current-state visibility/partition evidence.  It
    never reads sampler rows, outcomes, diversity, or distribution statistics.
    """

    scanned: list[dict[str, Any]] = []
    selected: list[dict[str, Any]] = []
    for position, candidate in enumerate(ordered_rows):
        evidence: dict[str, Any] = {
            "canonical_position": position,
            "eligible": False,
        }
        adapter = None
        try:
            if not isinstance(candidate, Mapping):
                raise ValueError("canonical row is not a mapping")
            identity = candidate.get("selection_identity")
            if not isinstance(identity, str) or not identity:
                raise ValueError("canonical row lacks explicit selection_identity")
            evidence["selection_identity"] = identity
            adapter, snapshot = anchor_loader(candidate)
            projection = validate_public_information_projection(
                adapter.t096_public_information_projection(snapshot)
            )
            metadata = validate_anchor_distribution_metadata(
                adapter.t096_anchor_distribution_metadata(snapshot)
            )
            evidence["projection_sha256"] = canonical_sha256(projection)
            evidence["native_metadata"] = metadata
            evidence["eligible"] = True
            if len(selected) < required_count:
                selected.append(
                    {
                        "canonical_position": position,
                        "selection_identity": identity,
                        "source_record": dict(candidate),
                        "selection_evidence": evidence,
                    }
                )
        except Exception as exc:  # noqa: BLE001 - selection is fail-closed
            evidence["reason"] = str(exc)
        finally:
            close = getattr(adapter, "close", None)
            if callable(close):
                close()
        scanned.append(evidence)
    complete = len(selected) == required_count
    return {
        "schema_id": T096_ANCHOR_SELECTION_SCHEMA_ID,
        "source": "accepted T087 413-record canonical order",
        "required_count": required_count,
        "scanned_count": len(scanned),
        "eligible_count": sum(1 for row in scanned if row.get("eligible") is True),
        "selected_anchors": selected,
        "scanned": scanned,
        "selection_complete": complete,
        "status": "COMPLETE" if complete else "INCOMPLETE",
        "terminal_classification": "COMPLETE" if complete else "INCOMPLETE",
    }


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run_t096_anchor_audits(
    *,
    anchor_loader: Callable[[Mapping[str, Any]], tuple[Any, Any]],
    anchors: Sequence[Mapping[str, Any]] = (),
    sampler_seed: int,
    particle_count: int = T096_PARTICLES_PER_ANCHOR,
    fidelity_gaps: Sequence[str] = (),
    anchor_selection: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Run explicit anchor audits using native adapter/restore callbacks.

    ``anchor_loader`` returns ``(adapter, snapshot)``.  It is deliberately
    supplied by the caller so the task's accepted checkpoint/restore lineage
    remains explicit and cannot be guessed from filenames.
    """

    selection = dict(anchor_selection) if anchor_selection is not None else None
    selected_anchors: Sequence[Mapping[str, Any]] = anchors
    if selection is not None:
        selected_value = selection.get("selected_anchors")
        selected_anchors = (
            selected_value if isinstance(selected_value, Sequence) else ()
        )
    if len(selected_anchors) != 4 or (
        selection is not None and selection.get("selection_complete") is not True
    ):
        return {
            "schema_id": "t096-public-information-sampler-report-v1",
            "task_id": T096_TASK_ID,
            "sampler_schema_id": T096_SAMPLER_SCHEMA_ID,
            "sampler_configuration": {
                "seed_domain": "native sampler seed + anchor index",
                "base_seed": sampler_seed,
                "particle_count_per_anchor": particle_count,
                "accepted_particle_definition": (
                    "native row with exact public and ordered legal-action parity"
                ),
            },
            "anchor_count": 0,
            "anchors": [],
            "anchor_selection": selection,
            "selection_complete": False,
            "fidelity_gaps": list(fidelity_gaps),
            "terminal_classification": "INCOMPLETE",
            "private_audit_firewall": {
                "hidden_future_fingerprint_used_for": "diversity evidence only",
                "next_draw_card_id_used_for": "distribution statistic only",
                "controller_model_input": "not constructed by this workflow",
            },
        }
    rows: list[dict[str, Any]] = []
    for index, anchor in enumerate(selected_anchors):
        row: dict[str, Any]
        adapter = None
        try:
            if not isinstance(anchor, Mapping):
                raise TypeError(f"T096 anchor {index} is not a mapping")
            if (
                not isinstance(anchor.get("selection_identity"), str)
                or not isinstance(anchor.get("canonical_position"), int)
                or not isinstance(anchor.get("selection_evidence"), Mapping)
            ):
                raise ValueError("T096 anchor lacks frozen selection provenance")
            source = anchor.get("source_record", anchor)
            if not isinstance(source, Mapping):
                raise ValueError("T096 anchor source_record is malformed")
            adapter, snapshot = anchor_loader(source)
            row = audit_native_particles(
                adapter,
                snapshot,
                sampler_seed=sampler_seed + index,
                particle_count=particle_count,
            )
        except Exception as exc:  # noqa: BLE001 - report all failures deterministically
            row = {
                "schema_id": T096_SAMPLER_SCHEMA_ID,
                "status": "INCOMPLETE",
                "terminal_hint": "INCOMPLETE",
                "failure_code": "anchor_audit_exception",
                "failure_message": str(exc),
                "particle_count": particle_count,
                "public_parity_pass_count": 0,
                "legal_action_parity_pass_count": 0,
                "distribution_pass": None,
            }
        finally:
            close = getattr(adapter, "close", None)
            if callable(close):
                close()
        row["anchor_index"] = index
        row["anchor_identity"] = dict(anchor) if isinstance(anchor, Mapping) else {}
        rows.append(row)
    return {
        "schema_id": "t096-public-information-sampler-report-v1",
        "task_id": T096_TASK_ID,
        "sampler_schema_id": T096_SAMPLER_SCHEMA_ID,
        "sampler_configuration": {
            "seed_domain": "native sampler seed + anchor index",
            "base_seed": sampler_seed,
            "particle_count_per_anchor": particle_count,
            "accepted_particle_definition": (
                "native row with exact public and ordered legal-action parity"
            ),
        },
        "anchor_count": len(rows),
        "anchors": rows,
        "anchor_selection": selection,
        "selection_complete": True,
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
