"""Fake-only routing checks for the non-simulator T088 statistics command."""

from __future__ import annotations

import json

import pytest

from sts_combat_rl.commands import t088_statistics as command
from sts_combat_rl.sim.t088_tournament_workflow import (
    T088_REQUIRED_ARTIFACT_ROLES,
    T088_RETENTION_MANIFEST_EXTERNAL_ROLES,
)


def _paths() -> list[str]:
    return [
        "--authorization",
        "authorization.json",
        "--canary-evidence",
        "canary.json",
        "--raw-evidence",
        "raw.json",
        "--artifact-root",
        "retained",
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


def test_cli_routes_explicit_non_simulator_paths(monkeypatch, capsys) -> None:
    observed = {}

    def fake_run(**kwargs):
        observed.update(kwargs)
        return {
            "schema_id": "t088-statistics-command-result-v1",
            "task_id": "T088",
            "artifacts": {},
        }

    monkeypatch.setattr(command, "run_t088_statistics_from_paths", fake_run)
    assert command.main(_paths()) == 0
    assert observed["raw_evidence_path"].name == "raw.json"
    assert json.loads(capsys.readouterr().out)["task_id"] == "T088"


def test_raw_stream_failure_prevents_publication(monkeypatch, tmp_path) -> None:
    raw = tmp_path / "raw.json"
    raw.write_text(
        '{"schema_id":"t088-formal-raw-evidence-v1","rows":[]}', encoding="utf-8"
    )
    monkeypatch.setattr(
        command, "build_t088_formal_plan", lambda *_args, **_kwargs: {"rows": []}
    )
    with pytest.raises(command.T088StatisticsPathError, match="incomplete"):
        command._stream_compact_rows(
            raw,
            authorization={},
            implementation_head="a" * 40,
            inputs={},
            cohort=[],
            binding={},
            canary_reference={},
        )


def test_auxiliary_fallback_prefers_pairwise_quality_over_cost() -> None:
    pairs = []
    for candidate, reference in (
        ("B", "A"),
        ("C", "A"),
        ("D", "A"),
        ("B", "C"),
        ("B", "D"),
        ("C", "D"),
    ):
        pairs.append(
            {
                "candidate_arm": candidate,
                "reference_arm": reference,
                "binary_outcome": {
                    "classification": "CLEAR_OUTCOME_SUPERIORITY"
                    if (candidate, reference) in {("B", "C"), ("B", "D")}
                    else "OUTCOME_INCONCLUSIVE"
                },
                "dense_diagnostics": {"classification": "DENSE_MIXED"},
            }
        )
    costs = {
        arm: {"successor_transition_count": value, "wall_clock_time_s": value}
        for arm, value in {"B": 9, "C": 1, "D": 2}.items()
    }
    assert command._auxiliary_challenger(pairs, costs)[0] == "B"


def test_retention_closure_has_external_manifest_roles_plus_self() -> None:
    assert T088_RETENTION_MANIFEST_EXTERNAL_ROLES == T088_REQUIRED_ARTIFACT_ROLES - {
        "retention_manifest"
    }
    assert len(T088_RETENTION_MANIFEST_EXTERNAL_ROLES) == 11
    assert len(T088_REQUIRED_ARTIFACT_ROLES) == 12


def test_private_stage_cleanup_never_creates_final_root(tmp_path) -> None:
    stage = tmp_path / ".stage"
    stage.mkdir()
    (stage / "partial.json").write_text("{}", encoding="utf-8")
    command._cleanup_stage(stage)
    assert not stage.exists()
    assert not (tmp_path / "published").exists()
