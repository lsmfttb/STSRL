#!/usr/bin/env python3
"""Merge exactly 16 T067 shards and emit the versioned attribution report."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from sts_combat_rl.commands.t062_battle_search_v2 import (
    merge_t062_comparison_reports_from_paths,
)
from sts_combat_rl.commands.t067_battle_search_v2 import (
    build_t067_cost_attribution_report,
    write_t067_report,
)


EXPECTED_COHORT_SHA256 = (
    "b7f8e9b85b53bbf8e37adfe6cc90d0579937661309b26bce2a8f2921604a8608"
)
EXPECTED_CHECKPOINT_SHA256 = (
    "a2317354b24f93ff48f0408ba3fdc92056701ef16e9b3a1b8b17aa1cce2a56e4"
)
EXPECTED_NATIVE_COMMIT = "3cb9ebecb87c38044b34aa0e013d42b222a04087"
EXPECTED_SOURCE_MANIFEST_SHA256 = (
    "2f4bd6710a152b080a2c6e4cfbaf509148ffb27d0139a9250f1a0ee19efd6631"
)
EXPECTED_VERIFIER_SHA256 = (
    "16fc6ff8049c9c5083260e513e1472d6736e1aac946d27c8ec7b80b64d4dd0a3"
)
EXPECTED_VERIFIER_BYTES = 19872


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--shard", action="append", required=True)
    parser.add_argument("--raw-merged", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--cohort", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--t061-retention-manifest", type=Path, required=True)
    parser.add_argument("--input-preflight-report", type=Path, required=True)
    parser.add_argument(
        "--source-manifest",
        type=Path,
        default=Path("docs/sts_lightspeed_source_manifest.json"),
    )
    parser.add_argument(
        "--verifier", type=Path, default=Path("scripts/verify_lightspeed_source.sh")
    )
    parser.add_argument("--normalization-family", required=True)
    parser.add_argument("--record-range", default="0:16")
    parser.add_argument("--bootstrap-resamples", type=int, default=2000)
    args = parser.parse_args()
    if len(args.shard) != 16:
        raise SystemExit("T067 merge requires exactly 16 shard paths")
    shards = [Path(path) for path in args.shard]
    raw = merge_t062_comparison_reports_from_paths(
        shard_paths=shards,
        output_path=args.raw_merged,
        expected_record_count=16,
        bootstrap_resamples=args.bootstrap_resamples,
    )
    identities = {
        "t052_fixed_cohort": _identity(args.cohort, EXPECTED_COHORT_SHA256),
        "t043_checkpoint": _identity(args.checkpoint, EXPECTED_CHECKPOINT_SHA256),
        "t061_retention_manifest": _identity(args.t061_retention_manifest, None),
        "t062_input_preflight": _identity(args.input_preflight_report, None),
        "sts_lightspeed_source_manifest": _identity(
            args.source_manifest, EXPECTED_SOURCE_MANIFEST_SHA256
        ),
        "sts_lightspeed_source_verifier": _identity(
            args.verifier,
            EXPECTED_VERIFIER_SHA256,
            expected_bytes=EXPECTED_VERIFIER_BYTES,
        ),
    }
    candidate = {}
    provenance = raw.get("controller_provenance", {})
    for label in ("baseline", "prior_only", "value_only", "prior_value"):
        candidate[label] = int(
            provenance[label]["config"]["search_budget"]["simulations"]
        )
    report = build_t067_cost_attribution_report(
        raw,
        input_identities=identities,
        candidate_budget=candidate,
        normalization_family=args.normalization_family,
        worker_count=16,
        shard_count=16,
        record_range=args.record_range,
    )
    report["shards"] = [str(path) for path in shards]
    write_t067_report(args.output, report)
    return 0


def _identity(
    path: Path,
    expected_sha256: str | None,
    *,
    expected_bytes: int | None = None,
) -> dict[str, object]:
    if not path.is_file():
        raise SystemExit(f"missing T067 identity artifact: {path}")
    actual = _sha256(path)
    if expected_sha256 is not None and actual != expected_sha256:
        raise SystemExit(f"hash mismatch for {path}: {actual}")
    size = path.stat().st_size
    if expected_bytes is not None and size != expected_bytes:
        raise SystemExit(f"byte mismatch for {path}: {size}")
    schema = None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(raw, dict):
            schema = raw.get("schema_id")
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        pass
    return {"path": str(path), "bytes": size, "sha256": actual, "schema_id": schema}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


if __name__ == "__main__":
    raise SystemExit(main())
