"""File-only T093 corpus materialization command.

The command deliberately accepts retained records and writes a derived corpus;
it has no simulator or Search option and cannot recollect teacher data.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from sts_combat_rl.sim.t093_internal_state_student import (
    T093_EXACT_T092_EVIDENCE_SHA256,
    T093_EXACT_T092_RETENTION_SHA256,
    T093Error,
    materialize_t093_corpus,
)


def _read(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _retained_record_paths(manifest: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for shard in manifest.get("source_shards", []):
        for artifact in shard.get("source_artifacts", []):
            if not isinstance(artifact, dict) or not isinstance(artifact.get("path"), str):
                raise T093Error("T092 retention source artifact is malformed")
            rows[str(Path(artifact["path"]).resolve())] = artifact
    return rows


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m sts_combat_rl.commands.t093_internal_state_student"
    )
    parser.add_argument("--retention-manifest", type=Path, required=True)
    parser.add_argument("--formal-evidence", type=Path, required=True)
    parser.add_argument(
        "--source-record", type=Path, action="append", required=True,
        help="One or more exact T092 source-record paths from the retention manifest.",
    )
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if _sha(args.retention_manifest) != T093_EXACT_T092_RETENTION_SHA256:
        raise T093Error("retention manifest is not the accepted T092 identity")
    if _sha(args.formal_evidence) != T093_EXACT_T092_EVIDENCE_SHA256:
        raise T093Error("formal evidence is not the accepted T092 identity")
    manifest = _read(args.retention_manifest)
    evidence = _read(args.formal_evidence)
    if not isinstance(manifest, dict) or not isinstance(evidence, dict):
        raise T093Error("T092 evidence and retention manifest must be objects")
    retained = _retained_record_paths(manifest)
    occurrences: list[dict[str, Any]] = []
    for path in args.source_record:
        resolved = str(path.resolve(strict=True))
        identity = retained.get(resolved)
        if identity is None or _sha(path) != identity.get("sha256"):
            raise T093Error("source record is absent from or mismatches T092 retention")
        record = _read(path)
        if not isinstance(record, dict) or not isinstance(record.get("internal_occurrences"), list):
            raise T093Error("T092 source record has no retained internal occurrences")
        occurrences.extend(record["internal_occurrences"])
    materialized = materialize_t093_corpus(
        occurrences, t092_evidence=evidence, t092_retention_manifest=manifest
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(materialized, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
