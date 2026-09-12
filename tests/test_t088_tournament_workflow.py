"""Independent, non-simulator contract checks for the T088 evidence workflow."""

from __future__ import annotations

import hashlib

import pytest

from sts_combat_rl.sim.t088_tournament_workflow import (
    T088_ARMS,
    T088_FORMAL_EXECUTIONS,
    T088IncompleteError,
    build_t088_formal_plan,
    paired_bootstrap,
    paired_t088_comparison,
    select_t088_blind_audit,
    select_t088_canary_records,
    validate_t088_arm_execution_rows,
    validate_t088_canary_evidence,
    validate_t088_execution_rows,
    validate_t088_formal_plan,
    validate_t088_retention_manifest,
)


def _cohort() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for cohort, count in (("A", 93), ("B", 192), ("C", 128)):
        for index in range(count):
            rows.append({"selection_identity": f"{cohort}:{index}", "cohort": cohort})
    rows[0].update(is_escaping_mugger_case=True, legal_root_action_count=2)
    rows[1].update(is_ordinary_victory=True, legal_root_action_count=2)
    rows[2].update(is_ordinary_loss=True, legal_root_action_count=2)
    rows[93].update(is_later_act_or_boss=True, legal_root_action_count=2)
    rows[94].update(legal_root_action_count=3)
    return rows


def _diagnostic(
    identity: str, cohort: str, *, win: bool, value: float
) -> dict[str, object]:
    """Minimal statistics fixture; paired helpers intentionally use only these fields."""

    return {
        "selection_identity": identity,
        "cohort": cohort,
        "outcome": "PLAYER_VICTORY" if win else "PLAYER_LOSS",
        "diagnostics": {
            "enemy_hp_remaining_fraction": value,
            "player_hp_remaining_fraction_of_max": value,
            "combat_terminal_margin_v1": value,
        },
    }


def _paired_rows() -> list[dict[str, object]]:
    values = [
        ("A:0", "A", False, True, 0.9, 0.7),
        ("A:1", "A", False, False, 0.8, 0.4),
        ("B:0", "B", True, True, 0.6, 0.8),
        ("C:0", "C", True, False, 0.6, 0.9),
    ]
    rows: list[dict[str, object]] = []
    for identity, cohort, a_win, b_win, a_value, b_value in values:
        for arm, win, value in (("A", a_win, a_value), ("B", b_win, b_value)):
            rows.append(
                {
                    "arm": arm,
                    "selection_identity": identity,
                    "cohort": cohort,
                    "outcome": "PLAYER_VICTORY" if win else "PLAYER_LOSS",
                    "dense_diagnostic": _diagnostic(
                        identity, cohort, win=win, value=value
                    ),
                    "public_trace": [{"step_index": 0, "chosen_action_kind": "play"}],
                }
            )
    return rows


def test_formal_plan_is_exact_413_by_four_and_rejects_reordering() -> None:
    cohort = _cohort()
    plan = build_t088_formal_plan(cohort)

    assert plan["execution_authorized"] is False
    assert plan["planned_execution_count"] == T088_FORMAL_EXECUTIONS
    assert [row["arm"] for row in plan["rows"][:413]] == ["A"] * 413
    validate_t088_formal_plan(plan, cohort)

    plan["rows"] = list(reversed(plan["rows"]))
    with pytest.raises(T088IncompleteError, match="canonical cohort/arm order"):
        validate_t088_formal_plan(plan, cohort)


def test_canary_selection_is_sha_deterministic_and_never_authorizes_execution() -> None:
    cohort = _cohort()
    first = select_t088_canary_records(cohort)
    second = select_t088_canary_records(reversed(cohort))

    assert first == second
    assert first["execution_authorized"] is False
    assert {item["role"] for item in first["selected"]} == {
        "escaping_mugger",
        "ordinary_victory",
        "ordinary_loss",
        "later_act_or_boss",
        "multiple_root_actions",
    }


def test_canary_validation_requires_each_arm_specific_audit() -> None:
    selection = select_t088_canary_records(_cohort())
    rows = []
    for identity in {item["selection_identity"] for item in selection["selected"]}:
        for arm in T088_ARMS:
            row = {
                "arm": arm,
                "selection_identity": identity,
                "restore_public_legal_parity": True,
                "outcome": "PLAYER_VICTORY",
                "controller_definition_verified": True,
                "dense_diagnostic_recomputed": True,
                "native_game_mechanics_parity": True,
                "search_v2_parity_verified": arm in {"A", "B"},
                "beam_deterministic_replay_verified": arm == "C",
                "progressive_bias_depth_gt_zero_verified": arm == "D",
                "wall_clock_time_s": 0.1,
                "work_counters": {
                    "successor_transition_count": 1,
                    "action_execution_count": 1,
                    "model_calls": 0,
                },
            }
            rows.append(row)
    assert validate_t088_canary_evidence(selection, rows) == rows
    next(row for row in rows if row["arm"] == "A")["search_v2_parity_verified"] = False
    with pytest.raises(T088IncompleteError, match="Search-v2 parity"):
        validate_t088_canary_evidence(selection, rows)


def test_paired_statistics_preserve_pairing_and_use_precommitted_bootstrap() -> None:
    comparison = paired_t088_comparison(
        _paired_rows(), candidate_arm="B", reference_arm="A"
    )

    binary = comparison["binary_outcome"]
    assert binary["candidate_win_reference_loss"] == 1
    assert binary["candidate_loss_reference_win"] == 1
    assert binary["win_rate_difference"]["seed"] == 880088
    assert binary["win_rate_difference"]["resample_count"] == 20_000
    assert comparison["outcome_transitions"] == {
        "loss->win": 1,
        "loss->loss": 1,
        "win->win": 1,
        "win->loss": 1,
    }
    assert paired_bootstrap([1.0, -1.0]) == paired_bootstrap([1.0, -1.0])


def test_blind_bundle_uses_disjoint_semantic_strata_and_hides_arm_names() -> None:
    result = select_t088_blind_audit(
        _paired_rows(), candidate_arm="B", reference_arm="A"
    )
    public = result["bundle"]
    hidden = result["hidden_provenance"]

    assert public["schema_id"] == "t088-blind-audit-bundle-v1"
    assert len(public["pairs"]) == 4
    assert {pair["stratum"] for pair in public["pairs"]} == {
        "outcome_discordant",
        "both_loss",
        "both_win",
    }
    assert "A" not in repr(public) and "B" not in repr(public)
    assert {pair["X_arm"] for pair in hidden["pairs"]} <= {"A", "B"}


def test_formal_execution_fails_closed_before_partial_rows_can_be_reported() -> None:
    with pytest.raises(T088IncompleteError, match="formal arm does not cover"):
        validate_t088_arm_execution_rows([], _cohort(), arm="A")
    with pytest.raises(T088IncompleteError, match="cover exactly 413"):
        validate_t088_execution_rows([], _cohort())


def test_retention_requires_every_role_and_real_sha_shape() -> None:
    roles = (
        "specification",
        "controller_definitions",
        "native_verifier",
        "formal_cohort",
        "canary_evidence",
        "formal_rows",
        "cost_rows",
        "statistics_report",
        "blind_bundle",
        "blind_provenance",
        "final_report",
    )
    reference = {
        "path": "/retained/evidence.json",
        "sha256": hashlib.sha256(b"evidence").hexdigest(),
        "size_bytes": 8,
        "schema_id": "fixture-v1",
    }
    manifest = {
        "schema_id": "t088-retention-manifest-v1",
        "task_id": "T088",
        "artifact_references": {role: reference for role in roles},
    }
    validate_t088_retention_manifest(manifest)
    manifest["artifact_references"] = {"formal_rows": reference}
    with pytest.raises(T088IncompleteError, match="artifact roles"):
        validate_t088_retention_manifest(manifest)


def test_arm_set_is_frozen() -> None:
    assert T088_ARMS == ("A", "B", "C", "D")
