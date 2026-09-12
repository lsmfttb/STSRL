"""Independent, non-simulator contract checks for the T088 evidence workflow."""

from __future__ import annotations

import hashlib
import json

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
    validate_t088_t087_cohort_binding,
)


def _cohort() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    source_identity = {
        "path": "/retained/t085-selection.json",
        "sha256": "d5c335cd6e1f96e72ae3b302eebca17a5f6531fa0aac97ee2febec2c41c2e752",
        "schema_id": "t085-native-selection-artifact-v1",
        "byte_count": 1,
    }
    for cohort, count in (("A", 93), ("B", 192), ("C", 128)):
        for index in range(count):
            rows.append(
                {
                    "selection_identity": f"{cohort}:{index}",
                    "cohort": cohort,
                    "source_selection_manifest_identity": source_identity,
                    "provenance": {
                        "native_commit": "96052d24b9c2c16ff25b6f7241edd972613be997"
                    },
                }
            )
    rows[0].update(is_escaping_mugger_case=True, legal_root_action_count=2)
    rows[1].update(is_ordinary_victory=True, legal_root_action_count=2)
    rows[2].update(is_ordinary_loss=True, legal_root_action_count=2)
    rows[93].update(is_later_act_or_boss=True, legal_root_action_count=2)
    rows[94].update(legal_root_action_count=3)
    return rows


def _binding(cohort: list[dict[str, object]]) -> dict[str, object]:
    entries = [
        {"selection_identity": row["selection_identity"], "cohort": row["cohort"]}
        for row in cohort
    ]
    order = json.dumps(entries, sort_keys=True, separators=(",", ":")).encode()
    reference = lambda sha, schema: {
        "path": f"/retained/{schema}.json",
        "sha256": sha,
        "size_bytes": 1,
        "schema_id": schema,
    }
    return {
        "schema_id": "t088-t087-cohort-binding-v1",
        "task_id": "T088",
        "t087_task_id": "T087",
        "t087_native_identity": {
            "repository": "lsmfttb/sts_lightspeed",
            "ref": "refs/heads/stsrl/main",
            "commit": "96052d24b9c2c16ff25b6f7241edd972613be997",
        },
        "source_selection_manifest_identity": {
            "path": "/retained/t085-selection.json",
            "sha256": "d5c335cd6e1f96e72ae3b302eebca17a5f6531fa0aac97ee2febec2c41c2e752",
            "schema_id": "t085-native-selection-artifact-v1",
            "byte_count": 1,
        },
        "t087_artifacts": {
            "formal_natural_evidence": reference(
                "7931a118a4bf921f695db769f05fd77a5ae364484f5646f02d5be05329ad297f",
                "t087-natural-evidence-v1",
            ),
            "final_report": reference(
                "9a0eba7eed03a1ba4801c3019e9d14a2aa61214a76299a63ed9ab5a0192f3ea0",
                "t087-dense-combat-diagnostics-report-v1",
            ),
            "retention_manifest": reference(
                "5afe39476965a192c9bdd8d6bed121cd0169e68925cabfe9b8366ee320938adc",
                "t087-retention-manifest-v1",
            ),
        },
        "ordered_cohort_entries": entries,
        "ordered_cohort_entries_sha256": hashlib.sha256(order).hexdigest(),
    }


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
    binding = _binding(cohort)
    plan = build_t088_formal_plan(cohort, cohort_binding=binding)

    assert plan["execution_authorized"] is False
    assert plan["planned_execution_count"] == T088_FORMAL_EXECUTIONS
    assert [row["arm"] for row in plan["rows"][:413]] == ["A"] * 413
    validate_t088_formal_plan(plan, cohort, cohort_binding=binding)

    plan["rows"] = list(reversed(plan["rows"]))
    with pytest.raises(T088IncompleteError, match="canonical cohort/arm order"):
        validate_t088_formal_plan(plan, cohort, cohort_binding=binding)


def test_canary_selection_is_sha_deterministic_and_never_authorizes_execution() -> None:
    cohort = _cohort()
    binding = _binding(cohort)
    first = select_t088_canary_records(cohort, cohort_binding=binding)
    second = select_t088_canary_records(list(cohort), cohort_binding=binding)

    assert first == second
    assert first["execution_authorized"] is False
    assert {item["role"] for item in first["selected"]} == {
        "escaping_mugger",
        "ordinary_victory",
        "ordinary_loss",
        "later_act_or_boss",
        "multiple_root_actions",
    }


def test_t087_binding_rejects_same_count_substitution_reordering_and_hash_drift() -> (
    None
):
    cohort = _cohort()
    binding = _binding(cohort)
    validate_t088_t087_cohort_binding(binding, cohort)

    substituted = [dict(row) for row in cohort]
    substituted[0]["selection_identity"] = "A:substituted"
    with pytest.raises(T088IncompleteError, match="identity/order binding"):
        validate_t088_t087_cohort_binding(binding, substituted)
    with pytest.raises(T088IncompleteError, match="identity/order binding"):
        validate_t088_t087_cohort_binding(binding, list(reversed(cohort)))

    binding["t087_artifacts"]["formal_natural_evidence"]["sha256"] = "0" * 64
    with pytest.raises(T088IncompleteError, match="formal natural evidence"):
        validate_t088_t087_cohort_binding(binding, cohort)


def test_canary_validation_requires_each_arm_specific_audit() -> None:
    cohort = _cohort()
    binding = _binding(cohort)
    selection = select_t088_canary_records(cohort, cohort_binding=binding)
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
    assert (
        validate_t088_canary_evidence(selection, rows, cohort_binding=binding) == rows
    )
    next(row for row in rows if row["arm"] == "A")["search_v2_parity_verified"] = False
    with pytest.raises(T088IncompleteError, match="Search-v2 parity"):
        validate_t088_canary_evidence(selection, rows, cohort_binding=binding)


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
        cohort = _cohort()
        validate_t088_arm_execution_rows(
            [], cohort, arm="A", cohort_binding=_binding(cohort)
        )
    with pytest.raises(T088IncompleteError, match="cover exactly 413"):
        cohort = _cohort()
        validate_t088_execution_rows([], cohort, cohort_binding=_binding(cohort))


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
