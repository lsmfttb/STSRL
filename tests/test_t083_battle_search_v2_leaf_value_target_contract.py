from __future__ import annotations

import json
from pathlib import Path

import sts_combat_rl.t083_battle_search_v2_leaf_value_target_contract as module


def _row(index: int, *, value: float = 5.0) -> dict:
    actions = [
        {
            "eligible": True,
            "mean_value": value,
            "visit_probability": 1.0,
            "action_identity": {"stable_id": f"card:{index}", "occurrence": 0},
        }
    ]
    return {
        "row_index": index,
        "source_checkpoint_id": "checkpoint",
        "source_run_id": "run",
        "source_seed": 1,
        "source_battle_index": index,
        "source_pool_record_index": index,
        "root_statistics": actions,
        "teacher_action": {
            "mean_value": value,
            "score": value,
            "action_identity": actions[0]["action_identity"],
        },
        "native_search_report": {"best_action_value": value + 1.0},
    }


def _envelope(path: Path, metadata: dict, rows: list[dict]) -> None:
    path.write_text(
        "\n".join(
            [json.dumps({"type": "metadata", "metadata": metadata})]
            + [json.dumps({"type": "record", "record": row}) for row in rows]
        )
        + "\n",
        encoding="utf-8",
    )


def test_stats_reject_non_finite_values_and_preserve_quantiles() -> None:
    stats = module._stats([1.0, float("nan"), 3.0], available_rows=3)
    assert stats["finite_value_count"] == 2
    assert stats["min"] == 1.0
    assert stats["max"] == 3.0


def test_teacher_inventory_distinguishes_action_value_and_root_mixture(
    tmp_path: Path,
) -> None:
    path = tmp_path / "teacher.jsonl"
    _envelope(
        path,
        {
            "artifact_schema_id": "oracle-search-teacher-v1",
            "record_count": 1,
            "controller_provenance": {
                "config": {
                    "information_regime": "full_simulator_state_oracle_like",
                    "search_budget": {"simulations": 100},
                    "root_selection_rule": "highest_mean",
                    "include_potions": False,
                }
            },
        },
        [_row(0)],
    )
    inventory, problems = module._teacher_inventory(
        path,
        [
            {
                "complete_identity": {
                    "source_checkpoint_id": "checkpoint",
                    "source_run_id": "run",
                    "source_seed": 1,
                    "source_battle_index": 0,
                },
                "source_record_index": 0,
            }
        ],
        1,
    )
    assert not problems
    assert (
        inventory["candidates"]["selected_teacher_action_mean_value"]["value_kind"]
        == "action-value conditional"
    )
    assert (
        inventory["candidates"]["soft_visit_weighted_root_mean"]["statistics"]["mean"]
        == 5.0
    )


def test_native_unit_mismatch_is_explicit() -> None:
    table = module._candidate_table({"reason": "not reconstructable"}, True)
    current = next(
        item
        for item in table
        if item["candidate"] == "current_battle_survival_probability"
    )
    assert current["gates"]["utility_gate"] is False
    assert (
        current["rejection_or_limit"]
        == "direct [0,1] probability is not native utility"
    )


def test_missing_identity_is_incomplete(tmp_path: Path, monkeypatch) -> None:
    report_path = tmp_path / "report.json"
    t064 = tmp_path / "t064"
    t064.mkdir()
    t082 = tmp_path / "t082.json"
    t082.write_text(
        json.dumps({"schema_id": "wrong", "classification": "wrong"}), encoding="utf-8"
    )
    monkeypatch.setattr(
        module, "_artifact_check", lambda *args, **kwargs: {"valid": False}
    )
    result = module.audit_t083(
        t064, t082, report_path, repo_root=tmp_path, native_root=tmp_path
    )
    assert result["classification"] == "INCOMPLETE"


def test_native_ref_identity_is_fail_closed(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(module, "_git_ref_commit", lambda *_: None)
    evidence = module.native_evidence(tmp_path)
    assert evidence["ref"] == module.EXPECTED_NATIVE_REF
    assert evidence["resolved_commit"] is None
    assert evidence["identity_valid"] is False


def test_code_evidence_requires_main_ref_and_matching_sources(tmp_path: Path) -> None:
    evidence = module.code_evidence(tmp_path, module.EXPECTED_MAIN_COMMIT)
    assert evidence["main_ref"] == module.EXPECTED_MAIN_REF
    assert evidence["source_matches_main"] is False


def test_terminal_classification_is_single_and_recommendation_is_bounded() -> None:
    support = {
        "reason": "missing terminal state",
        "reconstructed_exact_native_utility_rows": 0,
    }
    table = module._candidate_table(support, True)
    assert len({"NEW_LEAF_CONTINUATION_UTILITY_TARGET_REQUIRED"}) == 1
    assert all("gates" in row and len(row["gates"]) == 6 for row in table)
