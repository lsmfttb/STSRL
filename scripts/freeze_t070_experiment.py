#!/usr/bin/env python3
"""Verify T070 inputs and freeze experiment plus outcome-blind subset manifests."""

from __future__ import annotations

import argparse
from pathlib import Path

from sts_combat_rl.commands.t070_search_v2_audit import build_frozen_manifests


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-root", type=Path, required=True)
    parser.add_argument("--artifact-root", type=Path, required=True)
    parser.add_argument("--code-commit", required=True)
    args = parser.parse_args()
    root = args.input_root.resolve()
    output = args.artifact_root.resolve()
    build_frozen_manifests(
        cohort_path=root
        / "t052-t051-boss-later-act-fixed-cohort-diagnostic-pr"
        / "t052-fixed-cohort.jsonl",
        checkpoint_path=root
        / "t044-de-assisted-comparison-pr"
        / "t043-assist_0-smoke"
        / "t043-assist_0-smoke-checkpoint.pt",
        t068_retention_path=root
        / "t068-native-boundary-batched-inference-feasibility"
        / "reproduction-3dd14e3"
        / "t068-retention-manifest.json",
        t069_retention_path=root
        / "t069-public-node-feature-encoding-projection-feasibility"
        / "reproduction-46a5695"
        / "t069-retention-manifest.json",
        source_manifest_path=Path("docs/sts_lightspeed_source_manifest.json"),
        source_verifier_path=Path("scripts/verify_lightspeed_source.sh"),
        code_commit=args.code_commit,
        frozen_output_path=output / "frozen-manifest" / "t070-frozen-manifest.json",
        subset_output_path=output
        / "budget-subset"
        / "t070-budget-subset-manifest.json",
        subset_cohort_output_path=output
        / "budget-subset"
        / "t070-budget-subset-cohort.jsonl",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
