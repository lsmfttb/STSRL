"""Focused contract tests for the T087 repository-owned diagnostic layer."""

from __future__ import annotations

import hashlib

import pytest

from sts_combat_rl.sim.t087_dense_combat_diagnostics import (
    T085_SELECTION_SCHEMA_ID,
    T087_ACTION_SPACE,
    T087_NATIVE_COMMIT,
    T087IncompleteError,
    T087T085InputGate,
    battle_snapshot_evidence,
    build_dense_diagnostic_row,
    build_t087_report,
    canonical_json_bytes,
    hp_rescue_ladder,
    run_t087_hp_rescue,
    run_t087_natural_evaluation,
    select_blind_audit_rows,
    select_hp_rescue_losses,
    selection_digest,
    selection_identity_bytes,
    validate_dense_diagnostic_row,
)
from sts_combat_rl.t085_corrected_leaf_value_search_evaluation import (
    T085BattleStartRecord,
)

SOURCE_MANIFEST = {
    "path": "/stable/t085-native-selection.json",
    "sha256": "d5c335cd6e1f96e72ae3b302eebca17a5f6531fa0aac97ee2febec2c41c2e752",
    "schema_id": T085_SELECTION_SCHEMA_ID,
    "byte_count": 123,
}


def _row(identity: str, cohort: str, *, win: bool, remaining: float = 0.5):
    entry = {
        "player_current_hp": 40,
        "player_max_hp": 80,
        "enemies": [
            {"id": "JawWorm", "current_hp": 20},
            {"id": "Cultist", "current_hp": 20},
        ],
        "battle_start_total_enemy_hp": 40,
        "battle_monster_count": 2,
    }
    terminal = {
        "player_current_hp": 60 if win else 0,
        "player_max_hp": 80,
        "enemies": (
            [{"id": "JawWorm", "current_hp": 0}, {"id": "Cultist", "current_hp": 0}]
            if win
            else [{"id": "JawWorm", "current_hp": 20 * remaining}, {"id": "Cultist", "current_hp": 20 * remaining}]
        ),
        "enemy_occurrences_complete": True,
        "enemy_occurrence_count": 2,
        "enemy_occurrence_identities": ("JawWorm", "Cultist"),
        "raw_snapshot": {
            "cur_hp": 60 if win else 0,
            "max_hp": 80,
            "completed_battle_outcome": "PLAYER_VICTORY" if win else "PLAYER_LOSS",
            "outcome": "UNDECIDED",
            "completed_battle_monster_count": 2,
            "completed_battle_monsters_alive": 0 if win else 2,
            "completed_battle_monsters": (
                [
                    {"id": 1, "id_label": "JawWorm", "name": "Jaw Worm", "current_hp": 0},
                    {"id": 2, "id_label": "Cultist", "name": "Cultist", "current_hp": 0},
                ]
                if win
                else [
                    {
                        "id": 1,
                        "id_label": "JawWorm",
                        "name": "Jaw Worm",
                        "current_hp": 20 * remaining,
                    },
                    {
                        "id": 2,
                        "id_label": "Cultist",
                        "name": "Cultist",
                        "current_hp": 20 * remaining,
                    },
                ]
            ),
        },
    }
    return build_dense_diagnostic_row(
        selection_identity=identity,
        cohort=cohort,
        entry=entry,
        terminal=terminal,
        outcome="PLAYER_VICTORY" if win else "PLAYER_LOSS",
        source_selection_manifest_identity=SOURCE_MANIFEST,
        provenance={
            "task_id": "T087",
            "restore_method": "test_restore",
            "native_commit": T087_NATIVE_COMMIT,
            "search_api": "StepSimulator.battle_search_v2.v1",
            "search_budget": 100,
            "root_selection_rule": "highest_mean",
            "policy_prior_callback": False,
            "learned_leaf_value_callback": False,
            "action_space": T087_ACTION_SPACE,
            "seed": None,
            "max_steps": 200,
            "no_additional_search_seed": True,
            "restore_source_identity": identity,
            "source_selection_manifest_identity": SOURCE_MANIFEST,
        },
    )


def test_selection_bytes_and_domains_are_exact() -> None:
    identity = "source/é:3"
    assert selection_identity_bytes(identity) == identity.encode("utf-8")
    assert selection_digest(identity, domain="hp") == hashlib.sha256(
        b"T087-hp-rescue-v1\n" + identity.encode("utf-8")
    ).hexdigest()
    assert canonical_json_bytes({"é": 1, "a": [2, 3]}) == '{"a":[2,3],"é":1}'.encode()
    assert hp_rescue_ladder(73, 80) == (0, 5, 7)


def test_dense_row_recomputes_authoritative_margin() -> None:
    row = _row("record-1", "A", win=False, remaining=0.25)
    assert row["outcome"] == "PLAYER_LOSS"
    assert row["diagnostics"]["enemy_hp_remaining_fraction"] == pytest.approx(0.25)
    assert row["diagnostics"]["enemy_damage_fraction"] == pytest.approx(0.75)
    assert row["diagnostics"]["combat_terminal_margin_v1"] == pytest.approx(-0.25)
    with pytest.raises(T087IncompleteError):
        build_dense_diagnostic_row(
            selection_identity="bad",
            cohort="A",
            entry={"player_current_hp": 40, "player_max_hp": 80, "enemies": []},
            terminal={"player_current_hp": 0, "enemies": [], "enemy_occurrences_complete": True},
            outcome="PLAYER_LOSS",
        )


def test_raw_terminal_outcome_mismatch_fails_row_validation() -> None:
    row = _row("outcome-mismatch", "A", win=True)
    row["terminal"] = dict(row["terminal"])
    row["terminal"]["raw_snapshot"] = dict(row["terminal"]["raw_snapshot"])
    row["terminal"]["raw_snapshot"]["completed_battle_outcome"] = "PLAYER_LOSS"
    with pytest.raises(T087IncompleteError, match="raw terminal outcome"):
        validate_dense_diagnostic_row(row)


def test_action_counts_must_recompute_from_retained_trace() -> None:
    row = _row("trace-counts", "A", win=True)
    row["action_trace"] = [{"kind": "potion"}, {"kind": "attack"}]
    row["action_count"] = 2
    row["potion_action_count"] = 0
    with pytest.raises(T087IncompleteError, match="potion_action_count"):
        validate_dense_diagnostic_row(row)


def test_hp_and_blind_audit_selection_freezes_disjoint_identities() -> None:
    rows = []
    for cohort, count in (("A", 93), ("B", 192), ("C", 128)):
        for index in range(count):
            # Provide enough wins, near losses, and deep losses in every cohort.
            win = index % 5 == 0
            remaining = 0.1 if index % 3 == 0 else 0.9
            rows.append(_row(f"{cohort}-{index}", cohort, win=win, remaining=remaining))
    hp = select_hp_rescue_losses(rows)
    assert len(hp["selected"]) == 24
    audit = select_blind_audit_rows(rows)
    assert len(audit["selected"]) == 24
    assert len({item["selection_identity"] for item in audit["selected"]}) == 24


def test_report_is_incomplete_until_all_formal_surfaces_exist() -> None:
    row = _row("only-one", "A", win=True)
    report = build_t087_report(natural_rows=[row])
    assert report["terminal_classification"] == "INCOMPLETE"
    assert report["problems"]


def test_report_accepts_and_retains_the_four_key_t085_selection_matrix() -> None:
    order = {
        "A": ("only-one",),
        "B": (),
        "C": (),
        "B@400": tuple(f"b400-{index}" for index in range(48)),
    }
    report = build_t087_report(
        natural_rows=[_row("only-one", "A", win=True)],
        t085_selection_identity_order=order,
    )
    assert report["t085_binding"]["selection_identity_order"]["B@400"] == order["B@400"]
    assert not any("four-cohort selection identity order" in problem for problem in report["problems"])


def test_sequence_alone_cannot_claim_enemy_occurrence_completeness() -> None:
    with pytest.raises(T087IncompleteError):
        battle_snapshot_evidence(
            {
                "current_hp": 40,
                "max_hp": 80,
                "battle_monsters": [{"id": "JawWorm", "current_hp": 20}],
            }
        )


def test_native_count_and_ordered_monster_identities_prove_completeness() -> None:
    evidence = battle_snapshot_evidence(
        {
            "battle_player": {"current_hp": 40, "max_hp": 80},
            "battle_monsters": [{"id": "JawWorm", "current_hp": 20}],
            "battle_monster_count": 1,
        }
    )
    assert evidence["enemy_occurrences_complete"] is True
    assert evidence["enemy_occurrence_identities"] == ("JawWorm",)


def test_native_integer_id_uses_existing_string_id_label() -> None:
    evidence = battle_snapshot_evidence(
        {
            "battle_player": {"current_hp": 40, "max_hp": 80},
            "battle_monsters": [
                {
                    "id": 1,
                    "id_label": "JawWorm",
                    "name": "Jaw Worm",
                    "current_hp": 20,
                }
            ],
            "battle_monster_count": 1,
        }
    )
    assert evidence["enemy_occurrence_identities"] == ("JawWorm",)


def test_terminal_snapshot_requires_post_action_monster_telemetry() -> None:
    with pytest.raises(T087IncompleteError, match="post-action monster telemetry"):
        battle_snapshot_evidence(
            {
                "cur_hp": 0,
                "max_hp": 80,
                "completed_battle_outcome": "PLAYER_LOSS",
            },
            require_positive_enemy_hp=False,
        )


def test_superficially_matching_fake_gate_cannot_start_natural_or_hp_execution() -> None:
    fake_gate = T087T085InputGate(
        cohorts={"A": (), "B": (), "C": (), "B@400": ()},
        canonical_records_by_cohort={"A": {}, "B": {}, "C": {}},
        artifact_references={},
        source_selection_manifest_identity=SOURCE_MANIFEST,
        canonical_artifact_references={},
    )
    with pytest.raises(T087IncompleteError):
        run_t087_natural_evaluation(
            records_by_cohort={"A": (), "B": (), "C": ()},
            canonical_records_by_cohort={"A": {}, "B": {}, "C": {}},
            adapter_factory=lambda: None,
            t085_input_gate=fake_gate,
        )
    with pytest.raises(T087IncompleteError):
        run_t087_hp_rescue(
            natural_rows=(),
            records_by_identity={},
            canonical_records_by_cohort={"A": {}, "B": {}, "C": {}},
            adapter_factory=lambda: None,
            t085_input_gate=fake_gate,
        )


def test_token_matched_malformed_gate_fails_closed_as_t087_error() -> None:
    from sts_combat_rl.sim import t087_dense_combat_diagnostics as diagnostics

    malformed_gate = T087T085InputGate(
        cohorts={"A": (), "B": (), "C": (), "B@400": ()},
        canonical_records_by_cohort={"A": {}, "B": {}, "C": {}},
        artifact_references=[],  # type: ignore[arg-type]
        source_selection_manifest_identity=SOURCE_MANIFEST,
        canonical_artifact_references={"A": {}, "B": {}, "C": {}},
    )
    object.__setattr__(malformed_gate, "_validation_token", diagnostics._T087_VERIFIED_GATE_TOKEN)
    with pytest.raises(T087IncompleteError):
        run_t087_natural_evaluation(
            records_by_cohort={"A": (), "B": (), "C": ()},
            canonical_records_by_cohort={"A": {}, "B": {}, "C": {}},
            adapter_factory=lambda: None,
            t085_input_gate=malformed_gate,
        )


def test_non_integral_hp_gap_fails_closed() -> None:
    with pytest.raises(T087IncompleteError):
        hp_rescue_ladder(73.5, 80)


def test_missing_source_manifest_identity_fails_selection() -> None:
    rows = [_row(f"{cohort}-{index}", cohort, win=False) for cohort in ("A", "B", "C") for index in range(8)]
    rows[0].pop("source_selection_manifest_identity")
    with pytest.raises(T087IncompleteError):
        select_hp_rescue_losses(rows)


def test_substituted_t085_canonical_identity_fails_closed() -> None:
    from sts_combat_rl.sim.t087_dense_combat_diagnostics import (
        _validate_canonical_binding,
    )

    record = T085BattleStartRecord(
        source_run_seed=1,
        source_run_identity="seed-1-run-1",
        complete_source_identity="checkpoint-1",
        battle_identity="seed-1-run-1:3",
        act=1,
        room_type="ELITE",
        source_artifact_record_identity="checkpoint-1",
    )
    canonical = {
        "checkpoint-1": {
            "source_checkpoint_id": "substituted",
            "source_run_id": "seed-1-run-1",
            "source_seed": 1,
            "source_battle_index": 3,
            "structural_metadata": {"act": 1, "room_type": "ELITE"},
        }
    }
    restore = {
        "checkpoint-1": {
            "selection_identity": "checkpoint-1",
            "source_run_identity": "seed-1-run-1",
            "source_run_seed": 1,
            "restore_ok": True,
            "public_context_match": True,
        }
    }
    with pytest.raises(T087IncompleteError):
        _validate_canonical_binding(
            cohort="A", selected=[record], canonical=canonical, restore_rows=restore
        )


def test_invalid_provenance_and_invalid_hp_rows_cannot_be_ready() -> None:
    rows = []
    for cohort, count in (("A", 93), ("B", 192), ("C", 128)):
        for index in range(count):
            rows.append(_row(f"{cohort}-{index}", cohort, win=index % 5 == 0))
    invalid = dict(rows[0])
    invalid["provenance"] = dict(invalid["provenance"], native_commit="wrong")
    with pytest.raises(T087IncompleteError):
        validate_dense_diagnostic_row(invalid)
    report = build_t087_report(
        natural_rows=rows,
        hp_ladder_rows=[invalid for _ in range(24)],
        audit_traces=[],
    )
    assert report["terminal_classification"] == "INCOMPLETE"
    assert report["problems"]


def test_hp_surface_rejects_unauthorized_transform_provenance() -> None:
    from sts_combat_rl.sim.t087_dense_combat_diagnostics import _validate_hp_surface

    natural_rows = [
        _row(f"{cohort}-{index}", cohort, win=False)
        for cohort, count in (("A", 93), ("B", 192), ("C", 128))
        for index in range(count)
    ]
    manifest = select_hp_rescue_losses(natural_rows)
    natural_by_id = {row["selection_identity"]: row for row in natural_rows}
    ladder_rows = []
    for selected in manifest["selected"]:
        identity = selected["selection_identity"]
        for extra_hp in hp_rescue_ladder(40, 80):
            row = dict(natural_by_id[identity])
            row["hp_rescue_selection"] = dict(selected)
            row["extra_hp"] = extra_hp
            row["provenance"] = dict(
                row["provenance"],
                natural_selection_identity=identity,
                extra_hp=extra_hp,
                hp_transform="UNAUTHORIZED",
                add_random_potion=False,
                encounter_id=None,
                intervention_scope="current_hp_only",
            )
            ladder_rows.append(row)
    problems = []
    _validate_hp_surface(manifest, ladder_rows, natural_by_id, problems)
    assert any("invalid execution provenance" in problem for problem in problems)


def test_complete_natural_count_is_not_premature_ready() -> None:
    rows = []
    for cohort, count in (("A", 93), ("B", 192), ("C", 128)):
        for index in range(count):
            rows.append(_row(f"{cohort}-{index}", cohort, win=index % 5 == 0))
    report = build_t087_report(natural_rows=rows)
    assert report["natural_execution"]["observed_count"] == 413
    assert report["terminal_classification"] == "INCOMPLETE"
    assert any("artifact references" in problem for problem in report["problems"])
