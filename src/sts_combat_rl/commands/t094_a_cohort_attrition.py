"""File-only command for the T094 exact-artifact attrition audit."""

from __future__ import annotations

import argparse
from pathlib import Path

from sts_combat_rl.sim.t094_a_cohort_attrition import write_t094_artifacts


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m sts_combat_rl.commands.t094_a_cohort_attrition"
    )
    parser.add_argument("--t092-retention-manifest", type=Path, required=True)
    parser.add_argument("--t092-formal-evidence", type=Path, required=True)
    parser.add_argument("--t093-retention-manifest", type=Path, required=True)
    parser.add_argument("--t093-corpus", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    write_t094_artifacts(
        t092_retention_manifest_path=args.t092_retention_manifest,
        t092_evidence_path=args.t092_formal_evidence,
        t093_retention_manifest_path=args.t093_retention_manifest,
        t093_corpus_path=args.t093_corpus,
        output_dir=args.output_dir,
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
