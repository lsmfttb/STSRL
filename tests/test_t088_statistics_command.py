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


def test_statistics_validates_against_authorized_formal_root_not_its_own_root(
    tmp_path,
) -> None:
    formal_root = tmp_path / "t088-formal-accepted"
    statistics_root = tmp_path / "t088-statistics-new"

    assert command._formal_output_root_for_statistics(
        {"output_root": str(formal_root)}, statistics_root=statistics_root
    ) == str(formal_root.resolve())
    assert not statistics_root.exists()

    with pytest.raises(command.T088StatisticsPathError, match="independent"):
        command._formal_output_root_for_statistics(
            {"output_root": str(statistics_root)}, statistics_root=statistics_root
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


def test_auxiliary_fallback_keeps_full_tie_set_for_pairwise_cycle() -> None:
    pairs = [
        {
            "candidate_arm": candidate,
            "reference_arm": reference,
            "binary_outcome": {"classification": classification},
            "dense_diagnostics": {"classification": "DENSE_MIXED"},
        }
        for candidate, reference, classification in (
            ("B", "C", "CLEAR_OUTCOME_SUPERIORITY"),
            ("C", "D", "CLEAR_OUTCOME_SUPERIORITY"),
            ("B", "D", "CLEAR_OUTCOME_HARM"),
        )
    ]
    costs = {
        arm: {"successor_transition_count": 1, "wall_clock_time_s": 1}
        for arm in ("B", "C", "D")
    }

    selected, tie_set = command._auxiliary_challenger(pairs, costs)

    assert tie_set == ["B", "C", "D"]
    assert selected in tie_set
    assert (selected, tie_set) == command._auxiliary_challenger(pairs, costs)


def test_final_report_maps_unique_preparation_to_terminal_with_exact_arm() -> None:
    final = command._final_tournament_report(
        selection={
            "terminal_classification": "ANALYSIS_PREPARATION_READY",
            "selected_challenger": "B",
            "eligible_challengers": ["B"],
            "tie_set": [],
        },
        comparisons=[],
        blind_audit_challenger="B",
    )

    assert (
        final["terminal_classification"]
        == "STRONGER_NONLEARNED_COMBAT_BASELINE_IDENTIFIED"
    )
    assert final["selected_challenger"] == "B"
    assert final["blind_audit_challenger"] == "B"
    assert final["baseline_decision"] == {
        "decision": "promotion_eligible_unique_challenger",
        "selected_arm": "B",
        "selected_controller_configuration": {
            "controller": "Search-v2",
            "simulations": 400,
        },
        "improvement_source": "Search-v2 higher compute",
    }


@pytest.mark.parametrize(
    ("selection", "blind", "terminal"),
    [
        (
            {
                "terminal_classification": "NO_CHALLENGER_CLEARS_PROMOTION_GATE",
                "selected_challenger": None,
                "eligible_challengers": [],
                "tie_set": [],
            },
            "C",
            "NO_CHALLENGER_CLEARS_PROMOTION_GATE",
        ),
        (
            {
                "terminal_classification": "TOURNAMENT_TIE_REQUIRES_PLANNER_DECISION",
                "selected_challenger": None,
                "eligible_challengers": ["B", "C"],
                "tie_set": ["B", "C"],
            },
            "B",
            "TOURNAMENT_TIE_REQUIRES_PLANNER_DECISION",
        ),
    ],
)
def test_final_report_keeps_auxiliary_blind_choice_out_of_formal_selection(
    selection, blind, terminal
) -> None:
    final = command._final_tournament_report(
        selection=selection, comparisons=[], blind_audit_challenger=blind
    )

    assert final["terminal_classification"] == terminal
    assert final["selected_challenger"] is None
    assert final["blind_audit_challenger"] == blind
    assert final["selection_provenance"]["selected_challenger"] is None


def test_final_validation_raw_iterator_closes_reader_on_early_exit(
    monkeypatch, tmp_path
) -> None:
    closed = False

    class FakeReader:
        def __init__(self, _path):
            pass

        def rows(self):
            yield {"row": 1}
            yield {"row": 2}

        def close(self):
            nonlocal closed
            closed = True

    monkeypatch.setattr(command, "_StreamingShardJson", FakeReader)
    raw_path = tmp_path / "raw.json"
    raw_path.write_text("{}", encoding="utf-8")
    rows = command._iter_full_formal_rows_for_final_validation(raw_path)
    assert next(rows) == {"row": 1}
    rows.close()
    assert closed is True


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


def test_staged_publication_cleans_private_stage_on_injected_write_failure(
    monkeypatch, tmp_path
) -> None:
    root = tmp_path / "published"
    real_write = command._write_new
    calls = 0

    def fail_second_write(path, document):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise command.T088StatisticsPathError(
                "injected manifest/closure write failure"
            )
        return real_write(path, document)

    monkeypatch.setattr(command, "_write_new", fail_second_write)

    def writer(stage):
        command._write_new(stage / "first.json", {"schema_id": "fixture-v1"})
        command._write_new(stage / "manifest.json", {"schema_id": "fixture-v1"})
        raise AssertionError("injected write failure must stop before closure")

    with pytest.raises(command.T088StatisticsPathError, match="injected"):
        command._publish_private_stage(root_path=root, writer=writer)

    assert not root.exists()
    assert list(tmp_path.glob(".t088-statistics-*")) == []
