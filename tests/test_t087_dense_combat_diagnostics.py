"""Focused contract tests for the T087 repository-owned diagnostic layer."""

from __future__ import annotations

import hashlib

import pytest

import sts_combat_rl.sim.t087_dense_combat_diagnostics as diagnostics
from sts_combat_rl.sim.t087_dense_combat_diagnostics import (
    T085_NATIVE_IDENTITY,
    T085_PAIRED_REPORT_SHA256,
    T085_PAIRED_SCHEMA_ID,
    T085_SELECTION_SCHEMA_ID,
    T087_ACTION_SPACE,
    T087_APPROVED_SPEC,
    T087_NATIVE_COMMIT,
    T087IncompleteError,
    T087T085InputGate,
    battle_snapshot_evidence,
    build_dense_diagnostic_row,
    build_t087_report,
    canonical_json_bytes,
    hp_rescue_ladder,
    load_t087_t085_report_binding,
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
    raw_entry = {
        "battle_player": {"current_hp": 40, "max_hp": 80},
        "battle_monsters": [
            {"id": 1, "id_label": "JawWorm", "name": "Jaw Worm", "current_hp": 20},
            {"id": 2, "id_label": "Cultist", "name": "Cultist", "current_hp": 20},
        ],
        "battle_monster_count": 2,
        "battle_monsters_alive": 2,
    }
    entry = battle_snapshot_evidence(raw_entry)
    terminal = {
        "player_current_hp": 60 if win else 0,
        "player_max_hp": 80,
        "enemies": (
            [{"id": "JawWorm", "current_hp": 0}, {"id": "Cultist", "current_hp": 0}]
            if win
            else [
                {"id": "JawWorm", "current_hp": 20 * remaining},
                {"id": "Cultist", "current_hp": 20 * remaining},
            ]
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
                    {
                        "id": 1,
                        "id_label": "JawWorm",
                        "name": "Jaw Worm",
                        "current_hp": 0,
                    },
                    {
                        "id": 2,
                        "id_label": "Cultist",
                        "name": "Cultist",
                        "current_hp": 0,
                    },
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
    assert (
        selection_digest(identity, domain="hp")
        == hashlib.sha256(b"T087-hp-rescue-v1\n" + identity.encode("utf-8")).hexdigest()
    )
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
            terminal={
                "player_current_hp": 0,
                "enemies": [],
                "enemy_occurrences_complete": True,
            },
            outcome="PLAYER_LOSS",
        )


def test_entry_projection_and_enemy_fractions_use_raw_evidence() -> None:
    row = _row("raw-entry", "A", win=False, remaining=0.25)
    row["entry"] = dict(row["entry"])
    row["entry"]["battle_start_total_enemy_hp"] = 1
    with pytest.raises(T087IncompleteError, match="raw entry snapshot"):
        validate_dense_diagnostic_row(row)

    row = _row("raw-fraction", "A", win=False, remaining=0.25)
    row["entry"] = dict(row["entry"])
    row["terminal"] = dict(row["terminal"])
    row["terminal"]["enemies"] = [
        {"id": "JawWorm", "current_hp": 30},
        {"id": "Cultist", "current_hp": 30},
    ]
    raw_terminal = dict(row["terminal"]["raw_snapshot"])
    raw_terminal["completed_battle_monsters"] = [
        {"id": 1, "id_label": "JawWorm", "name": "Jaw Worm", "current_hp": 30},
        {"id": 2, "id_label": "Cultist", "name": "Cultist", "current_hp": 30},
    ]
    row["terminal"]["raw_snapshot"] = raw_terminal
    row["raw_terminal"] = dict(raw_terminal)
    with pytest.raises(T087IncompleteError, match="enemy_hp_remaining_fraction"):
        validate_dense_diagnostic_row(row)


def test_raw_terminal_outcome_mismatch_fails_row_validation() -> None:
    row = _row("outcome-mismatch", "A", win=True)
    row["terminal"] = dict(row["terminal"])
    row["terminal"]["raw_snapshot"] = dict(row["terminal"]["raw_snapshot"])
    row["terminal"]["raw_snapshot"]["completed_battle_outcome"] = "PLAYER_LOSS"
    row["raw_terminal"] = dict(row["terminal"]["raw_snapshot"])
    with pytest.raises(T087IncompleteError, match="raw terminal outcome"):
        validate_dense_diagnostic_row(row)


def test_terminal_alive_tampering_fails_row_validation() -> None:
    row = _row("terminal-alive-tamper", "A", win=True)
    row["terminal"] = dict(row["terminal"])
    row["terminal"]["enemies"] = [
        {"id": "JawWorm", "current_hp": 0, "alive": True},
        {"id": "Cultist", "current_hp": 0},
    ]
    with pytest.raises(T087IncompleteError, match="alive status"):
        validate_dense_diagnostic_row(row)


def test_entry_alive_tampering_fails_row_validation() -> None:
    row = _row("entry-alive-tamper", "A", win=False)
    row["entry"] = dict(row["entry"])
    row["entry"]["enemies"] = [
        {"id": "JawWorm", "current_hp": 20, "alive": False},
        {"id": "Cultist", "current_hp": 20},
    ]
    with pytest.raises(T087IncompleteError, match="alive status"):
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
    assert not any(
        "four-cohort selection identity order" in problem
        for problem in report["problems"]
    )


def _legacy_t085_paired_report() -> dict[str, object]:
    identity_order = {
        "A": ["A-0"],
        "B": [],
        "C": [],
        "B@400": ["B400-0"],
    }
    return {
        "schema_id": T085_PAIRED_SCHEMA_ID,
        "selection_binding": {
            cohort: {"selected_identity_order": list(identities)}
            for cohort, identities in identity_order.items()
        },
        "outcomes": [
            {
                "task_id": "T085",
                "native_execution_provenance": {
                    "native_identity": dict(T085_NATIVE_IDENTITY),
                    "arm": "baseline",
                },
            }
        ],
    }


def _load_test_paired_report_binding(
    monkeypatch,
    paired: dict[str, object],
    *,
    paired_sha256: str = T085_PAIRED_REPORT_SHA256,
):
    selection_ref = {
        "path": "/stable/t085-selection.json",
        "sha256": "selection-sha",
        "schema_id": T085_SELECTION_SCHEMA_ID,
        "byte_count": 1,
    }
    identity_order = {
        "A": ("A-0",),
        "B": (),
        "C": (),
        "B@400": ("B400-0",),
    }
    restore_ref = {
        "path": "/stable/t085-restore.json",
        "sha256": "restore-sha",
        "schema_id": "t085-native-selection-restore-evidence-v1",
        "byte_count": 1,
    }
    restore = {
        "task_id": "T085",
        "schema_id": "t085-native-selection-restore-evidence-v1",
        "native_identity": dict(T085_NATIVE_IDENTITY),
        "complete": True,
        "partial": False,
        "restore_parity_passed": True,
        "outcome_blind_selection": True,
        "search_invoked": False,
        "selection_artifact": selection_ref,
        "restore_evidence": [{} for _ in range(413)],
    }
    paired_ref = {
        "path": "/stable/t085-paired-report.json",
        "sha256": paired_sha256,
        "schema_id": T085_PAIRED_SCHEMA_ID,
        "byte_count": 1,
    }

    monkeypatch.setattr(
        diagnostics,
        "load_t087_t085_selection_binding",
        lambda _path: (identity_order, selection_ref),
    )

    def read_hash_bound(_path, *, label, **_kwargs):
        if label == "T085 restore evidence":
            return restore, restore_ref
        if label == "T085 paired report":
            return paired, paired_ref
        raise AssertionError(label)

    monkeypatch.setattr(diagnostics, "_read_hash_bound_json", read_hash_bound)
    return load_t087_t085_report_binding(
        selection_artifact_path="/stable/t085-selection.json",
        restore_evidence_path="/stable/t085-restore.json",
        paired_report_path="/stable/t085-paired-report.json",
    )


def test_t087_exact_legacy_paired_report_shape_passes_without_mutation(
    monkeypatch,
) -> None:
    paired = _legacy_t085_paired_report()
    before = repr(paired)
    identity_order, references = _load_test_paired_report_binding(monkeypatch, paired)

    assert identity_order["B@400"] == ("B400-0",)
    assert references["paired"]["sha256"] == T085_PAIRED_REPORT_SHA256
    assert "task_id" not in paired
    assert "native_execution_provenance" not in paired
    assert repr(paired) == before
    assert T087_APPROVED_SPEC == "bc374087c9f4db8972282a3a4c92fa6c027e5f23"


@pytest.mark.parametrize(
    "case",
    (
        "missing_row_task_id",
        "conflicting_row_task_id",
        "missing_row_native_provenance",
        "conflicting_nested_native_commit",
        "conflicting_top_level_task_id",
        "conflicting_top_level_native_provenance",
        "different_sha",
        "missing_selection_binding",
    ),
)
def test_t087_legacy_paired_report_migration_fails_closed(monkeypatch, case) -> None:
    paired = _legacy_t085_paired_report()
    paired_sha256 = T085_PAIRED_REPORT_SHA256
    row = paired["outcomes"][0]
    if case == "missing_row_task_id":
        row.pop("task_id")
    elif case == "conflicting_row_task_id":
        row["task_id"] = "T084"
    elif case == "missing_row_native_provenance":
        row.pop("native_execution_provenance")
    elif case == "conflicting_nested_native_commit":
        row["native_execution_provenance"] = {
            "native_identity": dict(T085_NATIVE_IDENTITY, commit="not-d62")
        }
    elif case == "conflicting_top_level_task_id":
        paired["task_id"] = "T084"
    elif case == "conflicting_top_level_native_provenance":
        paired["native_execution_provenance"] = {
            "native_identity": {
                **T085_NATIVE_IDENTITY,
                "commit": "not-d62",
            }
        }
    elif case == "different_sha":
        paired_sha256 = "0" * 64
    elif case == "missing_selection_binding":
        paired.pop("selection_binding")
    else:  # pragma: no cover - the parameter list is exhaustive
        raise AssertionError(case)

    with pytest.raises(T087IncompleteError):
        _load_test_paired_report_binding(
            monkeypatch,
            paired,
            paired_sha256=paired_sha256,
        )


def test_t087_current_paired_report_provenance_branch_remains_valid(
    monkeypatch,
) -> None:
    paired = _legacy_t085_paired_report()
    paired["task_id"] = "T085"
    paired["native_execution_provenance"] = {
        "native_identity": dict(T085_NATIVE_IDENTITY)
    }

    _load_test_paired_report_binding(monkeypatch, paired)


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
            "battle_monsters_alive": 1,
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
            "battle_monsters_alive": 1,
        }
    )
    assert evidence["enemy_occurrence_identities"] == ("JawWorm",)


def test_entry_alive_count_is_required_and_consistent() -> None:
    raw = {
        "battle_player": {"current_hp": 40, "max_hp": 80},
        "battle_monsters": [{"id": 1, "id_label": "JawWorm", "current_hp": 20}],
        "battle_monster_count": 1,
    }
    with pytest.raises(T087IncompleteError, match="alive count"):
        battle_snapshot_evidence(raw)
    raw["battle_monsters_alive"] = 0
    with pytest.raises(T087IncompleteError, match="alive count"):
        battle_snapshot_evidence(raw)


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


def test_superficially_matching_fake_gate_cannot_start_natural_or_hp_execution() -> (
    None
):
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
    object.__setattr__(
        malformed_gate, "_validation_token", diagnostics._T087_VERIFIED_GATE_TOKEN
    )
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
    rows = [
        _row(f"{cohort}-{index}", cohort, win=False)
        for cohort in ("A", "B", "C")
        for index in range(8)
    ]
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


def test_report_contains_grouped_margin_and_hp_ladder_outcome_summaries() -> None:
    natural_rows = [
        _row(f"{cohort}-{index}", cohort, win=index % 5 == 0)
        for cohort, count in (("A", 93), ("B", 192), ("C", 128))
        for index in range(count)
    ]
    hp_manifest = select_hp_rescue_losses(natural_rows)
    natural_by_id = {row["selection_identity"]: row for row in natural_rows}
    hp_rows = []
    for selected in hp_manifest["selected"]:
        identity = selected["selection_identity"]
        for extra_hp in hp_rescue_ladder(40, 80):
            row = dict(natural_by_id[identity])
            row["hp_rescue_selection"] = dict(selected)
            row["extra_hp"] = extra_hp
            row["provenance"] = dict(
                row["provenance"],
                natural_selection_identity=identity,
                extra_hp=extra_hp,
                hp_transform="current_hp_addition" if extra_hp else "none",
                add_random_potion=False,
                encounter_id=None,
                intervention_scope="current_hp_only",
            )
            hp_rows.append(row)

    report = build_t087_report(natural_rows=natural_rows, hp_ladder_rows=hp_rows)
    summary = report["diagnostic_summary"]
    margin = summary["combat_terminal_margin_v1"]
    assert set(margin["by_cohort"]) == {"A", "B", "C"}
    assert set(margin["by_outcome"]) == {"PLAYER_VICTORY", "PLAYER_LOSS"}
    assert set(margin["by_cohort_outcome"]["A"]) == {
        "PLAYER_VICTORY",
        "PLAYER_LOSS",
    }
    component_names = {
        "enemy_hp_remaining_fraction",
        "enemy_damage_fraction",
        "player_hp_remaining_fraction_of_max",
        "enemy_kill_fraction",
    }
    assert set(margin["components"]) == component_names
    for component in margin["components"].values():
        assert set(component["by_cohort"]) == {"A", "B", "C"}
        assert set(component["by_outcome"]) == {"PLAYER_VICTORY", "PLAYER_LOSS"}
        assert set(component["by_cohort_outcome"]) == {"A", "B", "C"}
        assert all(
            set(outcomes) == {"PLAYER_VICTORY", "PLAYER_LOSS"}
            for outcomes in component["by_cohort_outcome"].values()
        )
    assert all(
        margin["components"][name]["by_outcome"]["PLAYER_VICTORY"][key] is None
        for name in ("enemy_hp_remaining_fraction", "enemy_damage_fraction")
        for key in ("p25", "p50", "p75")
    )
    assert all(
        margin["components"]["player_hp_remaining_fraction_of_max"]["by_outcome"][
            "PLAYER_LOSS"
        ][key]
        is None
        for key in ("p25", "p50", "p75")
    )
    assert (
        summary["enemy_kill_fraction"]["by_cohort_outcome"]["A"]["PLAYER_VICTORY"][
            "p50"
        ]
        == 1.0
    )
    assert summary["action_count"]["p50"] == 0.0
    assert summary["potion_action_count"]["p50"] == 0.0

    validation = report["hp_rescue"]["validation"]
    assert validation["expected_variant_count"] == 120
    assert validation["observed_variant_count"] == 120
    assert validation["record_count"] == 24
    assert validation["censoring_count"] == 24
    assert len(validation["selection_outcomes"]) == 24
    assert all(
        len(item["outcome_sequence"]) == 5
        and item["min_observed_extra_hp_with_win"] is None
        and item["censored_no_win_at_max_hp"] is True
        for item in validation["selection_outcomes"]
    )
    assert all(
        set(item) == {"extra_hp", "outcome", "terminal_margin"}
        for item in validation["selection_outcomes"][0]["outcome_sequence"]
    )

    tampered_hp_rows = [dict(row) for row in hp_rows]
    tampered_hp_rows[0]["diagnostics"] = dict(
        tampered_hp_rows[0]["diagnostics"],
        combat_terminal_margin_v1=999.0,
    )
    tampered_problems = []
    from sts_combat_rl.sim.t087_dense_combat_diagnostics import _validate_hp_surface

    tampered_validation = _validate_hp_surface(
        hp_manifest,
        tampered_hp_rows,
        natural_by_id,
        tampered_problems,
    )
    assert tampered_validation is not None
    assert tampered_validation["validated_variant_count"] == 119
    assert tampered_validation["record_count"] == 0
    assert tampered_validation["selection_outcomes"] == []
    assert tampered_validation["censoring_count"] is None
    assert tampered_problems


def test_complete_natural_count_is_not_premature_ready() -> None:
    rows = []
    for cohort, count in (("A", 93), ("B", 192), ("C", 128)):
        for index in range(count):
            rows.append(_row(f"{cohort}-{index}", cohort, win=index % 5 == 0))
    report = build_t087_report(natural_rows=rows)
    assert report["natural_execution"]["observed_count"] == 413
    assert report["terminal_classification"] == "INCOMPLETE"
    assert any("artifact references" in problem for problem in report["problems"])
