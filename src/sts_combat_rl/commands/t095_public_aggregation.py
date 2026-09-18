"""File-only command for the T095 exact-artifact aggregation audit."""

from __future__ import annotations

import argparse
from pathlib import Path

from sts_combat_rl.sim.t095_public_aggregation import write_t095_artifacts


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m sts_combat_rl.commands.t095_public_aggregation"
    )
    parser.add_argument("--t092-retention-manifest", type=Path, required=True)
    parser.add_argument("--t092-formal-evidence", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    write_t095_artifacts(
        t092_retention_manifest_path=args.t092_retention_manifest,
        t092_evidence_path=args.t092_formal_evidence,
        output_dir=args.output_dir,
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
