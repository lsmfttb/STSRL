from __future__ import annotations

import hashlib
import json
from pathlib import Path

from sts_combat_rl.commands.cli_parser import build_parser
from sts_combat_rl.commands.cli_validation import validate_cli_args
from sts_combat_rl.commands.t062_battle_search_v2 import (
    run_t062_input_preflight_from_paths,
)


def test_t062_input_preflight_verifies_explicit_stable_artifacts(
    tmp_path: Path, monkeypatch
) -> None:
    manifest = tmp_path / "t061-retention-manifest.json"
    cohort = tmp_path / "t052-fixed-cohort.jsonl"
    checkpoint = tmp_path / "t043-checkpoint.pt"
    output = tmp_path / "preflight.json"
    manifest_payload = {
        "schema_id": "t061-retention-manifest-v2",
        "retention_root": "D:/stable/artifacts/t061",
        "raw_artifacts_may_be_deleted_when": "T062 input extraction complete",
        "manifest_identity": {"bytes": 0, "sha256": ""},
    }
    canonical = dict(manifest_payload)
    canonical["manifest_identity"] = {"bytes": None, "sha256": None}
    canonical_sha256 = hashlib.sha256(
        (json.dumps(canonical, indent=2, sort_keys=True) + "\n").encode("utf-8")
    ).hexdigest()
    manifest_payload["manifest_identity"]["sha256"] = canonical_sha256
    for _ in range(3):
        manifest.write_text(
            json.dumps(manifest_payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        manifest_payload["manifest_identity"]["bytes"] = manifest.stat().st_size
    manifest.write_text(
        json.dumps(manifest_payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    cohort.write_bytes(b"cohort")
    checkpoint.write_bytes(b"checkpoint")
    from sts_combat_rl.commands import t062_battle_search_v2 as command

    monkeypatch.setattr(command, "T061_RETENTION_MANIFEST_SHA256", canonical_sha256)
    monkeypatch.setattr(command, "T052_COHORT_SHA256", _sha256(cohort))
    monkeypatch.setattr(command, "T052_COHORT_BYTES", cohort.stat().st_size)
    monkeypatch.setattr(command, "T043_CHECKPOINT_SHA256", _sha256(checkpoint))
    monkeypatch.setattr(command, "T043_CHECKPOINT_BYTES", checkpoint.stat().st_size)

    report = run_t062_input_preflight_from_paths(
        output_path=output,
        t061_retention_manifest_path=manifest,
        t052_cohort_path=cohort,
        t043_checkpoint_path=checkpoint,
    )

    assert report["command_passed"]
    assert json.loads(output.read_text(encoding="utf-8"))["command_passed"]


def test_t062_input_preflight_rejects_missing_explicit_input(tmp_path: Path) -> None:
    report = run_t062_input_preflight_from_paths(
        output_path=tmp_path / "preflight.json",
        t061_retention_manifest_path=tmp_path / "missing-manifest.json",
        t052_cohort_path=tmp_path / "missing-cohort.jsonl",
        t043_checkpoint_path=tmp_path / "missing-checkpoint.pt",
    )

    assert not report["command_passed"]
    assert len(report["problems"]) == 3


def test_t062_cli_requires_all_explicit_input_paths() -> None:
    parser = build_parser()
    args = parser.parse_args(["--t062-input-preflight-report", "preflight.json"])

    assert validate_cli_args(args).startswith("--t062-input-preflight-report requires")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
