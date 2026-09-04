"""Offline T085 source/restore/evaluation/retention command routing.

Native source generation, checkpoint restore, and Search execution remain owned
by the pinned simulator.  This command consumes their explicit JSON artifacts,
revalidates the selection gate, aggregates paired outcomes, and writes a
stable-root report.  It intentionally contains no simulator mechanics.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping
from pathlib import Path

from sts_combat_rl.t085_corrected_leaf_value_search_evaluation import (
    T085BattleStartRecord,
    build_t085_paired_evaluation_report,
    validate_t085_evaluation_selection_evidence,
    validate_t085_retention_manifest,
    write_t085_json_artifact,
)


def _read_json(path: Path) -> Mapping[str, object]:
    document = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(document, Mapping):
        raise ValueError(f"{path} must contain a JSON object")
    return document


def run_t085_paired_evaluation_report_from_paths(
    *,
    outcomes_path: Path,
    selection_evidence_path: Path,
    output_path: Path,
) -> dict[str, object]:
    """Aggregate explicit native outcome rows after selection-gate validation."""

    selection_document = _read_json(selection_evidence_path)
    raw_cohorts = selection_document.get("cohorts")
    raw_evidence = selection_document.get("selection_evidence")
    if not isinstance(raw_cohorts, Mapping) or not isinstance(raw_evidence, Mapping):
        raise ValueError(
            "selection evidence document requires cohorts and selection_evidence"
        )
    cohorts: dict[str, tuple[T085BattleStartRecord, ...]] = {}
    for name, raw_records in raw_cohorts.items():
        if not isinstance(raw_records, list):
            raise ValueError(f"selection evidence cohort {name} must be a list")
        cohorts[str(name)] = tuple(
            record
            if isinstance(record, T085BattleStartRecord)
            else T085BattleStartRecord.from_mapping(record)
            for record in raw_records
        )
    validate_t085_evaluation_selection_evidence(cohorts, raw_evidence)
    outcomes_document = json.loads(outcomes_path.read_text(encoding="utf-8"))
    if isinstance(outcomes_document, list):
        raw_outcomes = outcomes_document
    elif isinstance(outcomes_document, Mapping):
        raw_outcomes = outcomes_document.get("outcomes")
    else:
        raw_outcomes = None
    if not isinstance(raw_outcomes, list):
        raise ValueError("outcomes artifact must be a JSON list or an outcomes object")
    report = build_t085_paired_evaluation_report(
        raw_outcomes,
        cohort_b_record_count=len(cohorts["B"]),
        cohort_c_record_count=len(cohorts["C"]),
        selection_cohorts=cohorts,
        selection_evidence=raw_evidence,
    )
    reference = write_t085_json_artifact(
        output_path,
        report,
        schema_id="t085-paired-evaluation-report-v1",
    )
    return {"report": report, "artifact": reference}


def run_t085_retention_validation_from_path(path: Path) -> dict[str, object]:
    """Validate a previously written T085 retention manifest."""

    return validate_t085_retention_manifest(_read_json(path))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--outcomes",
        type=Path,
        help="Explicit native evaluation outcomes JSON/list artifact.",
    )
    parser.add_argument(
        "--selection-evidence",
        type=Path,
        help="Explicit A/B/C/Search@400 selection-gate JSON artifact.",
    )
    parser.add_argument(
        "--report",
        type=Path,
        help="Stable-root T085 paired report output path.",
    )
    parser.add_argument(
        "--validate-retention",
        type=Path,
        help="Validate an explicit T085 retention manifest and exit.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.validate_retention is not None:
            if any(
                value is not None
                for value in (args.outcomes, args.selection_evidence, args.report)
            ):
                raise ValueError(
                    "--validate-retention cannot be combined with aggregation inputs"
                )
            result = run_t085_retention_validation_from_path(args.validate_retention)
        else:
            if (
                args.outcomes is None
                or args.selection_evidence is None
                or args.report is None
            ):
                raise ValueError(
                    "aggregation requires --outcomes, --selection-evidence, and --report"
                )
            result = run_t085_paired_evaluation_report_from_paths(
                outcomes_path=args.outcomes,
                selection_evidence_path=args.selection_evidence,
                output_path=args.report,
            )
    except (OSError, UnicodeDecodeError, ValueError, json.JSONDecodeError) as exc:
        print(f"T085 command failed: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, sort_keys=True, default=str), file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "build_parser",
    "main",
    "run_t085_paired_evaluation_report_from_paths",
    "run_t085_retention_validation_from_path",
]
