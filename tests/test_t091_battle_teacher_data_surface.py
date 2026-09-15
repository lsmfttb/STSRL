"""Focused unit coverage for T091's offline telemetry-audit primitives."""

from __future__ import annotations

from pathlib import Path

from sts_combat_rl.sim.t091_battle_teacher_data_surface import (
    T091_N_MINS,
    _iter_json_array,
    _selection_summary,
    _static_internal_audit,
    _Stats,
)


def test_incremental_json_array_reader_handles_chunk_boundaries(tmp_path: Path) -> None:
    path = tmp_path / "rows.json"
    path.write_text('[\n {"row": 1},\n {"row": 2}\n]\n', encoding="utf-8")

    assert list(_iter_json_array(path)) == [{"row": 1}, {"row": 2}]


def test_stats_keep_unvisited_actions_out_of_support() -> None:
    stats = _Stats()
    stats.add(
        legal_count=3,
        s1=2,
        s0=False,
        threshold_rows={minimum: (2, 1) for minimum in T091_N_MINS},
    )
    report = stats.report()

    assert report["s0_complete_root_q"]["count"] == 0
    assert (
        report["s1_visited_action_support"]["supported_legal_fraction"]["median"]
        == 2 / 3
    )
    assert report["s2_partial_pairwise_support"]["4"] == {
        "decisions_with_at_least_two_supported_actions": 1,
        "fraction_of_multi_action_decisions_with_at_least_two_supported_actions": 1.0,
        "total_supported_actions": 2,
        "total_ordered_non_tie_pairs": 1,
        "ordered_pairs_per_multi_action_decision": {
            "count": 1,
            "mean": 1.0,
            "median": 1.0,
            "p75": 1.0,
            "p90": 1.0,
            "p95": 1.0,
            "max": 1,
        },
        "supported_legal_fraction": {
            "count": 1,
            "mean": 2 / 3,
            "median": 2 / 3,
            "p75": 2 / 3,
            "p90": 2 / 3,
            "p95": 2 / 3,
            "max": 2 / 3,
        },
    }


def test_selection_summary_does_not_impute_depth_and_internal_audit_is_bounded() -> (
    None
):
    summary = _selection_summary(
        [
            {
                "legal_count": 2,
                "legal_kinds": ["card", "end_turn"],
                "selected_kind": "card",
                "source_group": "A",
                "terminal_outcome": "PLAYER_VICTORY",
            }
        ]
    )
    audit = _static_internal_audit()

    assert summary["battle_turn_or_decision_depth"].startswith("UNAVAILABLE")
    assert summary["terminal_outcome_source_level_descriptive"] == {"PLAYER_VICTORY": 1}
    assert audit["conclusion"] == "CURRENT_SEARCH_INTERNAL_SURFACE_FEASIBLE"
    assert "does not add" in audit["implementation_boundary"]
