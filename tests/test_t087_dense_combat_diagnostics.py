"""Focused contract tests for the T087 repository-owned diagnostic layer."""

from __future__ import annotations

import hashlib

import pytest

from sts_combat_rl.sim.t087_dense_combat_diagnostics import (
    T087IncompleteError,
    build_dense_diagnostic_row,
    build_t087_report,
    canonical_json_bytes,
    hp_rescue_ladder,
    select_blind_audit_rows,
    select_hp_rescue_losses,
    selection_digest,
    selection_identity_bytes,
)


def _row(identity: str, cohort: str, *, win: bool, remaining: float = 0.5):
    entry = {
        "player_current_hp": 40,
        "player_max_hp": 80,
        "enemies": [
            {"id": "JawWorm", "current_hp": 20},
            {"id": "Cultist", "current_hp": 20},
        ],
        "battle_start_total_enemy_hp": 40,
        "enemy_occurrences_complete": True,
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
    }
    return build_dense_diagnostic_row(
        selection_identity=identity,
        cohort=cohort,
        entry=entry,
        terminal=terminal,
        outcome="PLAYER_VICTORY" if win else "PLAYER_LOSS",
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
