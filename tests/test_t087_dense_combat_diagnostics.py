"""Focused contract tests for the T087 repository-owned diagnostic layer."""

from __future__ import annotations

import hashlib
import inspect
from types import SimpleNamespace

import pytest

import sts_combat_rl.sim.t087_dense_combat_diagnostics as diagnostics
from sts_combat_rl.sim.t087_dense_combat_diagnostics import (
    T085_SELECTION_SCHEMA_ID,
    T087_ACTION_SPACE,
    T087_APPROVED_SPEC,
    T087_NATIVE_COMMIT,
    T087_NATIVE_IDENTITY,
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
            [
                {
                    "id": "JawWorm",
                    "current_hp": 0,
                    "max_hp": 20,
                    "alive": False,
                    "targetable": False,
                    "half_dead": False,
                },
                {
                    "id": "Cultist",
                    "current_hp": 0,
                    "max_hp": 20,
                    "alive": False,
                    "targetable": False,
                    "half_dead": False,
                },
            ]
            if win
            else [
                {
                    "id": "JawWorm",
                    "current_hp": 20 * remaining,
                    "max_hp": 20,
                    "alive": True,
                    "targetable": True,
                    "half_dead": False,
                },
                {
                    "id": "Cultist",
                    "current_hp": 20 * remaining,
                    "max_hp": 20,
                    "alive": True,
                    "targetable": True,
                    "half_dead": False,
                },
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
                        "max_hp": 20,
                        "alive": False,
                        "targetable": False,
                        "half_dead": False,
                    },
                    {
                        "id": 2,
                        "id_label": "Cultist",
                        "name": "Cultist",
                        "current_hp": 0,
                        "max_hp": 20,
                        "alive": False,
                        "targetable": False,
                        "half_dead": False,
                    },
                ]
                if win
                else [
                    {
                        "id": 1,
                        "id_label": "JawWorm",
                        "name": "Jaw Worm",
                        "current_hp": 20 * remaining,
                        "max_hp": 20,
                        "alive": True,
                        "targetable": True,
                        "half_dead": False,
                    },
                    {
                        "id": 2,
                        "id_label": "Cultist",
                        "name": "Cultist",
                        "current_hp": 20 * remaining,
                        "max_hp": 20,
                        "alive": True,
                        "targetable": True,
                        "half_dead": False,
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


def _custom_terminal_row(
    identity: str,
    *,
    outcome: str,
    terminal_enemies: list[dict[str, object]],
    entry_hp: float = 20,
    entry_enemy_ids: list[str] | None = None,
) -> dict[str, object]:
    entry_ids = entry_enemy_ids or [str(enemy["id"]) for enemy in terminal_enemies]
    entry_enemies = [
        {
            "id": index + 1,
            "id_label": enemy_id,
            "name": enemy_id,
            "current_hp": entry_hp,
            "max_hp": entry_hp,
        }
        for index, enemy_id in enumerate(entry_ids)
    ]
    raw_entry = {
        "battle_player": {"current_hp": 40, "max_hp": 80},
        "battle_monsters": entry_enemies,
        "battle_monster_count": len(entry_enemies),
        "battle_monsters_alive": len(entry_enemies),
    }
    entry = battle_snapshot_evidence(raw_entry)
    raw_terminal_enemies = [dict(enemy) for enemy in terminal_enemies]
    raw_terminal = {
        "cur_hp": 0 if outcome == "PLAYER_LOSS" else 60,
        "max_hp": 80,
        "completed_battle_outcome": outcome,
        "outcome": "UNDECIDED",
        "completed_battle_monster_count": len(raw_terminal_enemies),
        "completed_battle_monsters_alive": sum(
            enemy["targetable"] is True for enemy in raw_terminal_enemies
        ),
        "completed_battle_monsters": raw_terminal_enemies,
    }
    terminal = {
        "player_current_hp": 0 if outcome == "PLAYER_LOSS" else 60,
        "player_max_hp": 80,
        "enemies": [dict(enemy) for enemy in terminal_enemies],
        "enemy_occurrences_complete": True,
        "enemy_occurrence_count": len(terminal_enemies),
        "enemy_occurrence_identities": tuple(
            str(enemy["id"]) for enemy in terminal_enemies
        ),
        "raw_snapshot": raw_terminal,
    }
    provenance = dict(_row("provenance", "A", win=True)["provenance"])
    provenance["restore_source_identity"] = identity
    return build_dense_diagnostic_row(
        selection_identity=identity,
        cohort="A",
        entry=entry,
        terminal=terminal,
        outcome=outcome,
        source_selection_manifest_identity=SOURCE_MANIFEST,
        provenance=provenance,
    )


def _escaped_mugger_row(*, outcome: str = "PLAYER_VICTORY") -> dict[str, object]:
    return _custom_terminal_row(
        "escaped-mugger",
        outcome=outcome,
        terminal_enemies=[
            {
                "id": "LOOTER",
                "current_hp": 0,
                "max_hp": 30,
                "alive": False,
                "targetable": False,
                "half_dead": False,
            },
            {
                "id": "MUGGER",
                "current_hp": 29,
                "max_hp": 40,
                "alive": True,
                "targetable": False,
                "half_dead": False,
            },
        ],
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
    assert row["diagnostics"]["enemy_hp_progress_fraction_v1"] == pytest.approx(0.75)
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


def test_escaped_mugger_native_shape_accepts_hp_alive_distinct_from_active() -> None:
    row = _escaped_mugger_row()

    validate_dense_diagnostic_row(row)
    diagnostics_row = row["diagnostics"]
    assert diagnostics_row["enemy_occurrence_count_terminal"] == 2
    assert diagnostics_row["enemy_count_active_terminal"] == 0
    assert diagnostics_row["enemy_count_hp_alive_terminal"] == 1
    assert diagnostics_row["enemy_count_non_targetable_hp_alive_terminal"] == 1
    assert diagnostics_row["terminal_total_enemy_hp_all_occurrences"] == pytest.approx(
        29
    )
    assert diagnostics_row["terminal_total_enemy_hp_active"] == pytest.approx(0)
    assert diagnostics_row["combat_terminal_margin_v1"] == pytest.approx(0.75)


@pytest.mark.parametrize(
    ("identity", "entry_enemy_ids", "terminal_enemies"),
    [
        (
            "slime-boss-split",
            ["SLIME_BOSS"],
            [
                {
                    "id": "SPIKE_SLIME_L",
                    "monster_index": 0,
                    "current_hp": 35,
                    "max_hp": 35,
                    "alive": True,
                    "targetable": True,
                    "half_dead": False,
                },
                {
                    "id": "SLIME_BOSS_SPLIT_RETAINED",
                    "monster_index": 1,
                    "current_hp": 0,
                    "max_hp": 1,
                    "alive": False,
                    "targetable": False,
                    "half_dead": False,
                },
                {
                    "id": "ACID_SLIME_L",
                    "monster_index": 2,
                    "current_hp": 35,
                    "max_hp": 35,
                    "alive": True,
                    "targetable": True,
                    "half_dead": False,
                },
            ],
        ),
        (
            "large-slime-split",
            ["ACID_SLIME_L"],
            [
                {
                    "id": "ACID_SLIME_M",
                    "monster_index": 0,
                    "current_hp": 20,
                    "max_hp": 20,
                    "alive": True,
                    "targetable": True,
                    "half_dead": False,
                },
                {
                    "id": "ACID_SLIME_M",
                    "monster_index": 1,
                    "current_hp": 20,
                    "max_hp": 20,
                    "alive": True,
                    "targetable": True,
                    "half_dead": False,
                },
            ],
        ),
    ],
)
def test_dynamic_terminal_occurrences_may_replace_or_add_entry_monsters(
    identity: str,
    entry_enemy_ids: list[str],
    terminal_enemies: list[dict[str, object]],
) -> None:
    row = _custom_terminal_row(
        identity,
        outcome="PLAYER_VICTORY",
        entry_enemy_ids=entry_enemy_ids,
        terminal_enemies=terminal_enemies,
    )

    validate_dense_diagnostic_row(row)
    diagnostics_row = row["diagnostics"]
    assert diagnostics_row["enemy_count_initial"] == len(entry_enemy_ids)
    assert diagnostics_row["enemy_occurrence_count_terminal"] == len(terminal_enemies)


def test_terminal_active_scalar_must_match_targetable_rows() -> None:
    raw = dict(_escaped_mugger_row()["raw_terminal"])
    raw["completed_battle_monsters_alive"] = 1
    with pytest.raises(T087IncompleteError, match="active count"):
        battle_snapshot_evidence(raw, require_positive_enemy_hp=False)


def test_targetable_false_alive_row_is_rejected() -> None:
    raw = dict(_escaped_mugger_row()["raw_terminal"])
    monsters = [dict(monster) for monster in raw["completed_battle_monsters"]]
    monsters[1]["targetable"] = True
    monsters[1]["alive"] = False
    raw["completed_battle_monsters"] = monsters
    with pytest.raises(T087IncompleteError, match="targetable requires alive"):
        battle_snapshot_evidence(raw, require_positive_enemy_hp=False)


def test_terminal_monster_count_must_match_occurrence_list() -> None:
    raw = dict(_escaped_mugger_row()["raw_terminal"])
    raw["completed_battle_monster_count"] = 1
    with pytest.raises(T087IncompleteError, match="occurrence count"):
        battle_snapshot_evidence(raw, require_positive_enemy_hp=False)


@pytest.mark.parametrize("field", ("alive", "targetable", "half_dead"))
@pytest.mark.parametrize("mode", ("missing", "non_boolean"))
def test_terminal_monster_state_fields_are_required_and_boolean(
    field: str, mode: str
) -> None:
    raw = dict(_escaped_mugger_row()["raw_terminal"])
    monsters = [dict(monster) for monster in raw["completed_battle_monsters"]]
    if mode == "missing":
        monsters[0].pop(field)
    else:
        monsters[0][field] = "true"
    raw["completed_battle_monsters"] = monsters
    with pytest.raises(T087IncompleteError, match=field):
        battle_snapshot_evidence(raw, require_positive_enemy_hp=False)


def test_zero_enemy_max_hp_is_retained_when_native_snapshot_reports_it() -> None:
    entry_raw = {
        "battle_player": {"current_hp": 40, "max_hp": 80},
        "battle_monsters": [
            {
                "id": 1,
                "id_label": "ZERO_MAX",
                "name": "Zero Max",
                "current_hp": 5,
                "max_hp": 0,
            }
        ],
        "battle_monster_count": 1,
        "battle_monsters_alive": 1,
    }
    entry = battle_snapshot_evidence(entry_raw)
    assert entry["enemies"][0]["max_hp"] == pytest.approx(0)
    assert entry["battle_start_total_enemy_hp"] == pytest.approx(5)

    terminal_raw = {
        "cur_hp": 0,
        "max_hp": 80,
        "completed_battle_outcome": "PLAYER_LOSS",
        "completed_battle_monster_count": 1,
        "completed_battle_monsters_alive": 1,
        "completed_battle_monsters": [
            {
                "id": 1,
                "id_label": "ZERO_MAX",
                "name": "Zero Max",
                "current_hp": 5,
                "max_hp": 0,
                "alive": True,
                "targetable": True,
                "half_dead": False,
            }
        ],
    }
    terminal = battle_snapshot_evidence(
        terminal_raw, require_positive_enemy_hp=False
    )
    assert terminal["enemies"][0]["max_hp"] == pytest.approx(0)


def test_loss_hp_metrics_separate_active_and_all_occurrence_totals() -> None:
    row = _custom_terminal_row(
        "loss-escaped",
        outcome="PLAYER_LOSS",
        terminal_enemies=[
            {
                "id": "ACTIVE",
                "current_hp": 10,
                "max_hp": 20,
                "alive": True,
                "targetable": True,
                "half_dead": False,
            },
            {
                "id": "ESCAPED",
                "current_hp": 29,
                "max_hp": 40,
                "alive": True,
                "targetable": False,
                "half_dead": False,
            },
        ],
    )
    validate_dense_diagnostic_row(row)
    diagnostics_row = row["diagnostics"]
    assert diagnostics_row["terminal_total_enemy_hp_all_occurrences"] == pytest.approx(
        39
    )
    assert diagnostics_row["terminal_total_enemy_hp_active"] == pytest.approx(10)
    assert diagnostics_row["enemy_hp_remaining_fraction"] == pytest.approx(0.25)
    assert diagnostics_row["combat_terminal_margin_v1"] == pytest.approx(-0.25)


def test_loss_hp_remaining_fraction_above_one_is_not_clipped() -> None:
    row = _custom_terminal_row(
        "loss-healed",
        outcome="PLAYER_LOSS",
        entry_hp=20,
        terminal_enemies=[
            {
                "id": "HEALED",
                "current_hp": 30,
                "max_hp": 30,
                "alive": True,
                "targetable": True,
                "half_dead": False,
            }
        ],
    )
    assert row["diagnostics"]["enemy_hp_remaining_fraction"] == pytest.approx(1.5)
    assert row["diagnostics"]["enemy_hp_progress_fraction_v1"] == pytest.approx(-0.5)
    assert row["diagnostics"]["combat_terminal_margin_v1"] == pytest.approx(-1.5)
    validate_dense_diagnostic_row(row)


def test_removed_kill_fields_cannot_satisfy_current_row_schema() -> None:
    row = _row("old-fields", "A", win=False)
    tampered = dict(row)
    tampered["diagnostics"] = dict(row["diagnostics"])
    tampered["diagnostics"]["enemy_count_killed"] = 1
    tampered["diagnostics"]["enemy_kill_fraction"] = 0.5
    with pytest.raises(T087IncompleteError, match="diagnostics"):
        validate_dense_diagnostic_row(tampered)


def test_blind_audit_thresholds_use_active_unresolved_hp() -> None:
    rows = [
        _custom_terminal_row(
            f"win-{index}",
            outcome="PLAYER_VICTORY",
            terminal_enemies=[
                {
                    "id": "DEAD",
                    "current_hp": 0,
                    "max_hp": 20,
                    "alive": False,
                    "targetable": False,
                    "half_dead": False,
                }
            ],
        )
        for index in range(8)
    ]
    rows.extend(
        _custom_terminal_row(
            f"near-{index}",
            outcome="PLAYER_LOSS",
            terminal_enemies=[
                {
                    "id": "ACTIVE",
                    "current_hp": 4,
                    "max_hp": 20,
                    "alive": True,
                    "targetable": True,
                    "half_dead": False,
                },
                {
                    "id": "ESCAPED",
                    "current_hp": 30,
                    "max_hp": 40,
                    "alive": True,
                    "targetable": False,
                    "half_dead": False,
                },
            ],
        )
        for index in range(8)
    )
    rows.extend(
        _custom_terminal_row(
            f"deep-{index}",
            outcome="PLAYER_LOSS",
            terminal_enemies=[
                {
                    "id": "ACTIVE",
                    "current_hp": 36,
                    "max_hp": 40,
                    "alive": True,
                    "targetable": True,
                    "half_dead": False,
                }
            ],
        )
        for index in range(8)
    )
    audit = select_blind_audit_rows(rows)
    near = [
        item
        for item in audit["selected"]
        if item["audit_stratum"] == "near_boundary_losses"
    ]
    deep = [
        item for item in audit["selected"] if item["audit_stratum"] == "deep_losses"
    ]
    assert {item["threshold"] for item in near} == {0.25}
    assert {item["threshold"] for item in deep} == {0.75}


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
    with pytest.raises(T087IncompleteError, match="max_hp"):
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
        {
            "id": "JawWorm",
            "current_hp": 0,
            "max_hp": 20,
            "alive": True,
            "targetable": False,
            "half_dead": False,
        },
        {
            "id": "Cultist",
            "current_hp": 0,
            "max_hp": 20,
            "alive": False,
            "targetable": False,
            "half_dead": False,
        },
    ]
    with pytest.raises(T087IncompleteError, match="alive/targetable"):
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


def test_t087_direct_input_binding_has_no_paired_dependency(monkeypatch) -> None:
    selection_ref = {
        "path": "/stable/t085-selection.json",
        "sha256": "selection-sha",
        "schema_id": T085_SELECTION_SCHEMA_ID,
        "byte_count": 1,
    }
    restore_ref = {
        "path": "/stable/t085-restore.json",
        "sha256": "restore-sha",
        "schema_id": "t085-native-selection-restore-evidence-v1",
        "byte_count": 1,
    }
    documents = {
        "T085 selection artifact": ({}, selection_ref),
        "T085 restore evidence": ({}, restore_ref),
    }
    labels: list[str] = []

    def read_hash_bound(_path, *, label, **_kwargs):
        labels.append(label)
        return documents[label]

    def direct_chain(**kwargs):
        assert set(kwargs["artifact_references"]) == {"selection", "restore"}
        cohorts = {
            cohort: (SimpleNamespace(selection_identity=cohort),)
            for cohort in ("A", "B", "C", "B@400")
        }
        return (
            cohorts,
            {},
            {"A": {}, "B": {}, "C": {}},
            {"B": {}, "C": {}},
            selection_ref,
        )

    monkeypatch.setattr(diagnostics, "_read_hash_bound_json", read_hash_bound)
    monkeypatch.setattr(diagnostics, "_validate_t085_document_chain", direct_chain)
    identity_order, references = load_t087_t085_report_binding(
        selection_artifact_path="/stable/t085-selection.json",
        restore_evidence_path="/stable/t085-restore.json",
    )

    assert labels == ["T085 selection artifact", "T085 restore evidence"]
    assert set(identity_order) == {"A", "B", "C", "B@400"}
    assert set(references) == {"selection", "restore", "canonical", "source_manifests"}
    assert "paired" not in references
    assert (
        "paired_report_path"
        not in inspect.signature(load_t087_t085_report_binding).parameters
    )


def test_t087_direct_chain_rejects_withdrawn_paired_reference() -> None:
    with pytest.raises(T087IncompleteError):
        diagnostics._validate_t085_document_chain(
            selection_document={},
            restore_document={},
            artifact_references={
                "selection": {},
                "restore": {},
                "paired": {},
            },
        )


def test_t087_command_has_no_paired_option() -> None:
    from sts_combat_rl.commands.t087_dense_combat_diagnostics import build_parser

    assert T087_APPROVED_SPEC == "81509bd426c9d0980e9a60ad28e9abb0ee0444e4"
    option_strings = {
        option for action in build_parser()._actions for option in action.option_strings
    }
    assert "--t085-paired" not in option_strings


def test_t087_evaluator_contract_rejects_search_drift() -> None:
    adapter = SimpleNamespace(
        _search_simulations=100,
        _search_backend="battle_search_v2",
        _policy_prior_callback=None,
        _leaf_value_callback=None,
        _expected_native_identity=dict(T087_NATIVE_IDENTITY),
    )
    config = {
        "search_budget": 100,
        "root_selection_rule": "highest_mean",
        "policy_prior_callback": None,
        "leaf_value_callback": None,
        "native_identity": dict(T087_NATIVE_IDENTITY),
    }
    controller = SimpleNamespace(
        simulations=100,
        action_space=diagnostics.ActionSpaceConfig.initial_no_potions(),
        provenance=SimpleNamespace(to_dict=lambda: {"config": config}),
    )
    diagnostics._validate_t087_evaluator_contract(
        adapter=adapter,
        controller=controller,
        seed=None,
        max_steps=200,
        action_space=diagnostics.ActionSpaceConfig.initial_no_potions(),
    )
    adapter._search_simulations = 99
    with pytest.raises(T087IncompleteError):
        diagnostics._validate_t087_evaluator_contract(
            adapter=adapter,
            controller=controller,
            seed=None,
            max_steps=200,
            action_space=diagnostics.ActionSpaceConfig.initial_no_potions(),
        )


def test_t087_current_native_lineage_verification_is_fail_closed(monkeypatch) -> None:
    monkeypatch.setattr(
        diagnostics,
        "_validate_t085_native_source_manifest",
        lambda *_args, **_kwargs: dict(T087_NATIVE_IDENTITY, commit="wrong"),
    )
    with pytest.raises(T087IncompleteError, match="current-native"):
        diagnostics._validate_t087_current_native_identity()


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
    with pytest.raises(T087IncompleteError, match="active count"):
        battle_snapshot_evidence(raw)
    raw["battle_monsters_alive"] = 0
    with pytest.raises(T087IncompleteError, match="active count"):
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
        "enemy_occurrence_count_terminal",
        "enemy_count_active_terminal",
        "enemy_count_hp_alive_terminal",
        "enemy_count_non_targetable_hp_alive_terminal",
        "terminal_total_enemy_hp_all_occurrences",
        "terminal_total_enemy_hp_active",
        "enemy_hp_remaining_fraction",
        "enemy_hp_progress_fraction_v1",
        "player_hp_remaining_fraction_of_max",
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
        for name in ("enemy_hp_remaining_fraction", "enemy_hp_progress_fraction_v1")
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
        margin["components"]["enemy_count_active_terminal"]["by_cohort_outcome"]["A"][
            "PLAYER_VICTORY"
        ]["p50"]
        == 0.0
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
