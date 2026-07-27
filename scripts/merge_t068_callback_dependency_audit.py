#!/usr/bin/env python3
"""Merge 16 exact T068 callback traces and emit a fail-closed decision."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from sts_combat_rl.commands.t068_native_boundary_batching import (
    T068_GUIDED_ARMS,
    build_t068_callback_dependency_audit,
    build_t068_decision_report,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--shard", action="append", type=Path, required=True)
    parser.add_argument("--input-manifest", type=Path, required=True)
    parser.add_argument("--native-source-audit", type=Path, required=True)
    parser.add_argument("--code-commit", required=True)
    parser.add_argument("--audit-output", type=Path, required=True)
    parser.add_argument("--decision-output", type=Path, required=True)
    args = parser.parse_args()
    if len(args.shard) != 16:
        raise SystemExit("T068 merge requires exactly 16 shards")
    shards = [
        _load_shard(path, expected_index=index) for index, path in enumerate(args.shard)
    ]
    manifest = _load_json(args.input_manifest)
    source_audit = _load_json(args.native_source_audit)
    input_identities = {
        "t067_retention_manifest": {
            "path": str(args.input_manifest),
            "sha256": _sha256(args.input_manifest),
            "schema_id": manifest.get("schema_id"),
            "artifact_count": manifest.get("artifact_count"),
            "artifact_total_bytes": manifest.get("artifact_total_bytes"),
        }
    }
    audit = build_t068_callback_dependency_audit(
        shard_traces=shards,
        input_identities=input_identities,
        native_source_audit=source_audit,
        code_commit=args.code_commit,
    )
    decision = build_t068_decision_report(audit)
    _write_fresh(args.audit_output, audit)
    _write_fresh(args.decision_output, decision)
    print(
        "T068 audit: "
        + ", ".join(
            f"{arm}={audit['arms'][arm]['request_count']} singleton requests"
            for arm in T068_GUIDED_ARMS
        )
    )
    return 0


def _load_shard(path: Path, *, expected_index: int) -> dict[str, Any]:
    raw = _load_json(path)
    if raw.get("schema_id") != "t068-native-callback-dependency-shard-v1":
        raise SystemExit(f"T068 wrong shard schema: {path}")
    if (
        raw.get("shard_index") != expected_index
        or raw.get("record_range") != f"{expected_index}:{expected_index + 1}"
    ):
        raise SystemExit(f"T068 shard identity mismatch: {path}")
    if raw.get("command_passed") is not True:
        raise SystemExit(f"T068 shard failed: {path}")
    return raw


def _load_json(path: Path) -> dict[str, Any]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"T068 cannot load JSON {path}: {exc}") from exc
    if not isinstance(raw, dict):
        raise SystemExit(f"T068 JSON must be an object: {path}")
    return raw


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_fresh(path: Path, payload: dict[str, Any]) -> None:
    if path.exists():
        raise SystemExit(f"T068 refuses to overwrite output: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    raise SystemExit(main())
