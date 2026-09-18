"""File-only T093 corpus materialization command.

The command deliberately accepts retained records and writes a derived corpus;
it has no simulator or Search option and cannot recollect teacher data.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from sts_combat_rl.sim.t093_internal_state_student import (
    materialize_t093_from_paths,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m sts_combat_rl.commands.t093_internal_state_student"
    )
    parser.add_argument("--retention-manifest", type=Path, required=True)
    parser.add_argument("--formal-evidence", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    materialize_t093_from_paths(
        retention_manifest_path=args.retention_manifest,
        formal_evidence_path=args.formal_evidence,
        output_path=args.output,
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
