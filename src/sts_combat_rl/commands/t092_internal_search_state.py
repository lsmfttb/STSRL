"""File-only T092 command harness; registered simulator runs stay unauthorized."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from sts_combat_rl.sim.t092_internal_search_state import (
    parse_native_occurrences,
    select_t092_canary_sources,
    summarize_occurrences,
)


def _read_json(path: str) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _write_json(path: str, payload: object) -> None:
    Path(path).write_text(json.dumps(payload, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m sts_combat_rl.commands.t092_internal_search_state")
    commands = parser.add_subparsers(dest="command", required=True)
    canary = commands.add_parser("canary-select", help="write the deterministic 12-source selection manifest")
    canary.add_argument("--source-ledger", required=True)
    canary.add_argument("--output", required=True)
    validate = commands.add_parser("validate-native", help="validate one already-captured native report only")
    validate.add_argument("--native-report", required=True)
    validate.add_argument("--source-identity", required=True)
    validate.add_argument("--source-group", required=True, choices=("A", "B", "C"))
    validate.add_argument("--split", required=True)
    validate.add_argument("--parent-root-decision-identity", required=True)
    validate.add_argument("--output", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "canary-select":
        rows = _read_json(args.source_ledger)
        if not isinstance(rows, list):
            raise TypeError("T092 source ledger must be a JSON list")
        _write_json(args.output, {"schema_id": "t092-canary-selection-v1", "selected_sources": select_t092_canary_sources(rows)})
        return 0
    rows = parse_native_occurrences(
        _read_json(args.native_report),
        source_identity=args.source_identity,
        source_group=args.source_group,
        split=args.split,
        parent_root_decision_identity=args.parent_root_decision_identity,
    )
    _write_json(args.output, summarize_occurrences(rows))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
