"""Small file-based command surface for offline T090 materialization.

The command intentionally has no simulator adapter option.  It can build a
frozen split manifest and validate/reduce already materialized teacher rows,
but target collection, canaries, and formal execution remain explicit
Maintainer-authorized Python workflows.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from sts_combat_rl.sim.t090_battle_student import (
    build_t090_split_manifest,
    materialize_t090_targets,
)


def _read(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m sts_combat_rl.commands.t090_battle_student"
    )
    operations = parser.add_subparsers(dest="operation", required=True)
    split = operations.add_parser(
        "split", help="materialize the frozen T090 source split"
    )
    split.add_argument("--records", type=Path, required=True)
    split.add_argument("--output", type=Path, required=True)
    targets = operations.add_parser(
        "targets", help="validate/reduce existing teacher rows"
    )
    targets.add_argument("--rows", type=Path, required=True)
    targets.add_argument("--split-manifest", type=Path, required=True)
    targets.add_argument("--output", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.operation == "split":
        records = _read(args.records)
        if not isinstance(records, list):
            raise TypeError("T090 split records must be a JSON list")
        _write(args.output, build_t090_split_manifest(records))
        return 0
    if args.operation == "targets":
        rows = _read(args.rows)
        manifest = _read(args.split_manifest)
        if not isinstance(rows, list) or not isinstance(manifest, dict):
            raise TypeError(
                "T090 target inputs must be a rows list and split manifest mapping"
            )
        _write(args.output, materialize_t090_targets(rows, manifest))
        return 0
    raise AssertionError(f"unknown T090 operation {args.operation!r}")


if __name__ == "__main__":  # pragma: no cover - module execution only
    raise SystemExit(main())
