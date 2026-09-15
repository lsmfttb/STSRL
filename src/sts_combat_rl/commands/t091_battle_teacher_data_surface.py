"""Offline command for the T091 retained-telemetry data-surface audit."""

from __future__ import annotations

import argparse
from pathlib import Path

from sts_combat_rl.sim.t091_battle_teacher_data_surface import write_t091_artifacts


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m sts_combat_rl.commands.t091_battle_teacher_data_surface"
    )
    parser.add_argument(
        "--t090-dir",
        type=Path,
        required=True,
        help="accepted immutable T090 order-repair artifact directory",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        required=True,
        help="ignored/local T091 retention directory",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    write_t091_artifacts(args.t090_dir, args.output_dir)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
