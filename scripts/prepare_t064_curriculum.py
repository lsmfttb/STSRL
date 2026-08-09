#!/usr/bin/env python3
"""Verify frozen T064 inputs and prepare the sole curriculum manifest."""

from __future__ import annotations

import argparse
from pathlib import Path

from sts_combat_rl.commands.t064_curriculum import build_curriculum_manifest
from sts_combat_rl.sim.t064_curriculum import CURRICULUM_MANIFEST_FILENAME


POOL_SHA256S = {
    "assist_0": "d124d94a94df534c0bcc32072582a4448746f0a9734a41410e45c51c1b1ff87f",
    "assist_hp50": "1231bcd24309df9fbeb22ec56dfa12b661c38c6f440bdea1850053734cc32d8f",
    "assist_hp50_potion_elite_boss": "642d11d4956316e96f58ddf5fceec94f59a50c3dd051205e2fdfca94485ab201",
    "assist_hp75_potion": "1bbcbfebbde4fd2eec1be249f9843bf25a288abb0672950f47ad540c9bb8f46f",
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-root", type=Path, required=True)
    parser.add_argument("--artifact-root", type=Path, required=True)
    parser.add_argument("--code-commit", required=True)
    args = parser.parse_args()
    t042 = (
        args.input_root
        / "t042-assisted-source-scale-pr39"
        / "runs1000_s20_workers16"
    )
    t044 = args.input_root / "t044-de-assisted-comparison-pr"
    t052 = args.input_root / "t052-t051-boss-later-act-fixed-cohort-diagnostic-pr"
    pool_paths = {
        component: t042 / "merged-pools" / f"{component}.jsonl"
        for component in POOL_SHA256S
    }
    build_curriculum_manifest(
        pool_paths=pool_paths,
        pool_sha256s=POOL_SHA256S,
        scale_manifest_path=t042 / "scale-manifest.json",
        scale_manifest_sha256="25efae30dc9a61c8b97cb09e1844b93b9ffe693bde51c0f494f0f65203a1d327",
        holdouts=(
            {
                "path": t044
                / "runs1000-fixed-cohorts"
                / "assist_0-runs1000-fixed-cohort.jsonl",
                "sha256": "4ee0eb125ac37e870f0f2c950290b131f4693185c60b6c71cd46b5265a4d0037",
                "identity": "a336ffb1fda9ed7e",
                "record_count": 21,
            },
            {
                "path": t044
                / "runs1000-fixed-cohorts"
                / "assist_hp50-runs1000-fixed-cohort.jsonl",
                "sha256": "bc9372a67fe6536b848616e4b700765d6a47f49b4044bd973dbcaff4dd3bba36",
                "identity": "e99a0938307c0e7a",
                "record_count": 38,
            },
            {
                "path": t052 / "t052-fixed-cohort.jsonl",
                "sha256": "b7f8e9b85b53bbf8e37adfe6cc90d0579937661309b26bce2a8f2921604a8608",
                "identity": None,
                "record_count": 93,
            },
        ),
        initialization_checkpoint_path=t044
        / "t043-assist_0-smoke"
        / "t043-assist_0-smoke-checkpoint.pt",
        initialization_checkpoint_sha256="a2317354b24f93ff48f0408ba3fdc92056701ef16e9b3a1b8b17aa1cce2a56e4",
        code_commit=args.code_commit,
        output_path=args.artifact_root / CURRICULUM_MANIFEST_FILENAME,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
