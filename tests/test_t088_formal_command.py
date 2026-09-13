"""Fake-only parser/routing checks for the T088 formal command."""

from __future__ import annotations

import json

from sts_combat_rl.commands import t088_formal as command


def test_parser_defaults_to_the_required_sixteen_shard_topology() -> None:
    parser = command.build_parser()
    args = parser.parse_args(
        [
            "--canary-evidence",
            "canary.json",
            "--implementation-head",
            "a" * 40,
            "--t087-formal",
            "formal.json",
            "--t087-report",
            "report.json",
            "--t087-retention",
            "retention.json",
            "--t085-selection",
            "selection.json",
            "--t085-restore",
            "restore.json",
            "--a-pool",
            "a.jsonl",
            "--b-pool",
            "b.jsonl",
            "--c-pool",
            "c.jsonl",
            "--b-source-manifest",
            "b-manifest.json",
            "--c-source-manifest",
            "c-manifest.json",
        ]
    )
    assert args.shard_count == 16
    assert args.worker_count == 16


def test_cli_routes_only_explicit_formal_shard_paths(
    monkeypatch, capsys, tmp_path
) -> None:
    observed = {}

    def fake_run(**kwargs):
        observed.update(kwargs)
        return {
            "artifact": {
                "path": str(tmp_path / "out.json"),
                "sha256": "a" * 64,
                "size_bytes": 1,
                "schema_id": "t088-formal-execution-shard-v1",
            }
        }

    monkeypatch.setattr(
        command, "run_t088_authorized_formal_shard_from_paths", fake_run
    )
    paths = [
        "--authorization",
        "authorization.json",
        "--canary-evidence",
        "canary.json",
        "--implementation-head",
        "a" * 40,
        "--t087-formal",
        "formal.json",
        "--t087-report",
        "report.json",
        "--t087-retention",
        "retention.json",
        "--t085-selection",
        "selection.json",
        "--t085-restore",
        "restore.json",
        "--a-pool",
        "a.jsonl",
        "--b-pool",
        "b.jsonl",
        "--c-pool",
        "c.jsonl",
        "--b-source-manifest",
        "b-manifest.json",
        "--c-source-manifest",
        "c-manifest.json",
        "--output",
        "out.json",
        "--artifact-root",
        "retained",
        "--shard-index",
        "3",
    ]
    assert command.main(paths) == 0
    assert observed["shard_index"] == 3
    assert observed["shard_count"] == 16
    assert (
        json.loads(capsys.readouterr().out)["schema_id"]
        == "t088-formal-command-result-v1"
    )
