"""Offline routing and artifact finalization for T087 diagnostics.

Formal simulator execution is intentionally injected by the caller through
``run_t087_native_record``.  This command consumes only explicit current-schema
evidence and writes the report/retention surfaces; it never silently starts a
large simulator job.
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from sts_combat_rl.sim.t087_dense_combat_diagnostics import (
    T087_APPROVED_SPEC,
    T087_TASK_ID,
    build_t087_report,
    load_t087_t085_selection_binding,
    write_t087_json_artifact,
)


def _read_document(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read current-schema JSON artifact {path}: {exc}") from exc


def _rows(document: Any, label: str) -> list[Mapping[str, object]]:
    raw = document.get("rows") if isinstance(document, Mapping) else document
    if not isinstance(raw, list) or any(not isinstance(row, Mapping) for row in raw):
        raise ValueError(f"{label} must be a JSON list of row objects")
    return [dict(row) for row in raw]


def run_t087_report_from_paths(
    *,
    natural_path: Path,
    hp_ladder_path: Path,
    audit_trace_path: Path,
    t085_selection_path: Path,
    output_path: Path,
    artifact_root: Path,
) -> dict[str, object]:
    """Finalize explicit T087 rows and all current-schema report artifacts."""

    natural_rows = _rows(_read_document(natural_path), "natural evidence")
    hp_rows = _rows(_read_document(hp_ladder_path), "HP ladder evidence")
    audit_rows = _rows(_read_document(audit_trace_path), "blind audit evidence")
    t085_identity_order, t085_selection_reference = load_t087_t085_selection_binding(
        t085_selection_path
    )
    artifact_root.mkdir(parents=True, exist_ok=True)
    retention_inputs = {
        "stable_root": str(artifact_root.resolve()),
        "regeneration_command": "python -m sts_combat_rl.commands.t087_dense_combat_diagnostics",
        "raw_deletion_condition": "retain while T087 or its successor relies on the diagnostic claim",
    }

    report = build_t087_report(
        natural_rows=natural_rows,
        hp_ladder_rows=hp_rows,
        audit_traces=audit_rows,
        retention_inputs=retention_inputs,
        t085_selection_identity_order=t085_identity_order,
    )
    references: dict[str, Mapping[str, object]] = {}
    references["t085_selection"] = t085_selection_reference
    references["natural_evidence"] = write_t087_json_artifact(
        artifact_root / "t087-natural-evidence.json",
        {"task_id": T087_TASK_ID, "rows": natural_rows},
        schema_id="t087-natural-evidence-v1",
    )
    references["dense_diagnostic_table"] = write_t087_json_artifact(
        artifact_root / "t087-dense-diagnostic-table.json",
        {"task_id": T087_TASK_ID, "rows": natural_rows},
        schema_id="t087-dense-diagnostic-table-v1",
    )
    references["hp_rescue_selection"] = write_t087_json_artifact(
        artifact_root / "t087-hp-rescue-selection.json",
        {"selection_manifest": report["hp_rescue"]["selection_manifest"]},  # type: ignore[index]
        schema_id="t087-hp-rescue-selection-v1",
    )
    references["hp_rescue_ladder"] = write_t087_json_artifact(
        artifact_root / "t087-hp-rescue-ladder.json",
        {"rows": hp_rows},
        schema_id="t087-hp-rescue-ladder-v1",
    )
    references["blind_audit_selection"] = write_t087_json_artifact(
        artifact_root / "t087-blind-audit-selection.json",
        {"selection_manifest": report["blind_human_audit"]["selection_manifest"]},  # type: ignore[index]
        schema_id="t087-blind-audit-selection-v1",
    )
    references["blind_audit_bundle"] = write_t087_json_artifact(
        artifact_root / "t087-blind-audit-bundle.json",
        report["blind_human_audit"]["bundle"]  # type: ignore[index]
        if isinstance(report["blind_human_audit"]["bundle"], Mapping)  # type: ignore[index]
        else {"traces": []},
        schema_id="t087-blind-audit-bundle-v1",
    )
    references["blind_audit_hidden_provenance"] = write_t087_json_artifact(
        artifact_root / "t087-blind-audit-hidden-provenance.json",
        report["blind_human_audit"]["hidden_provenance"]  # type: ignore[index]
        if isinstance(report["blind_human_audit"]["hidden_provenance"], Mapping)  # type: ignore[index]
        else {"trace_map": []},
        schema_id="t087-blind-audit-hidden-provenance-v1",
    )
    references["human_review_rubric"] = write_t087_json_artifact(
        artifact_root / "t087-human-review-rubric.json",
        report["human_review_rubric"],  # type: ignore[arg-type]
        schema_id="t087-human-review-rubric-v1",
    )
    report = build_t087_report(
        natural_rows=natural_rows,
        hp_ladder_rows=hp_rows,
        audit_traces=audit_rows,
        artifact_references=references,
        retention_inputs=retention_inputs,
        t085_selection_identity_order=t085_identity_order,
    )
    report_reference = write_t087_json_artifact(
        output_path,
        report,
        schema_id="t087-dense-combat-diagnostics-report-v1",
    )
    references["final_report"] = report_reference
    retention = {
        "schema_id": "t087-retention-manifest-v1",
        "task_id": T087_TASK_ID,
        "approved_spec": T087_APPROVED_SPEC,
        "terminal_classification": report["terminal_classification"],
        "artifact_references": references,
        "stable_root": str(artifact_root.resolve()),
        "regeneration_command": retention_inputs["regeneration_command"],
        "raw_deletion_condition": retention_inputs["raw_deletion_condition"],
    }
    retention_reference = write_t087_json_artifact(
        artifact_root / "t087-retention-manifest.json",
        retention,
        schema_id="t087-retention-manifest-v1",
    )
    result = dict(report)
    result["report_artifact"] = report_reference
    result["retention_manifest"] = retention_reference
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--natural", type=Path, required=True)
    parser.add_argument("--hp-ladder", type=Path, required=True)
    parser.add_argument("--audit-traces", type=Path, required=True)
    parser.add_argument("--t085-selection", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--artifact-root", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = run_t087_report_from_paths(
            natural_path=args.natural,
            hp_ladder_path=args.hp_ladder,
            audit_trace_path=args.audit_traces,
            t085_selection_path=args.t085_selection,
            output_path=args.report,
            artifact_root=args.artifact_root,
        )
    except (OSError, UnicodeDecodeError, ValueError, TypeError, json.JSONDecodeError) as exc:
        print(f"T087 command failed: {exc}")
        return 2
    print(json.dumps(result, sort_keys=True, ensure_ascii=False))
    return 0 if result["terminal_classification"] == "DENSE_COMBAT_DIAGNOSTICS_READY" else 1


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["build_parser", "main", "run_t087_report_from_paths"]
