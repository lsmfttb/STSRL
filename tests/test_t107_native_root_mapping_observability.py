from __future__ import annotations

from copy import deepcopy

import pytest

from scripts.test_stsr008_root_occurrence_mapping_observability import (
    MAX_BATTLE_ENTRY_ACTIONS,
    _bridge_call_in_active_battle,
)
from sts_combat_rl.sim.t107_native_root_mapping_observability import (
    AUDIT_PREDICATES,
    AUDIT_SCHEMA,
    DIAGNOSTIC_SCHEMA,
    FAILURE_SUBREASONS,
    validate_t107_mapping_audit,
    validate_t107_mapping_diagnostic,
)


def _counts(**overrides: int) -> dict[str, int]:
    counts = {
        "public_legal_occurrence_count": 1,
        "search_root_edge_count": 1,
        "public_occurrences_mapped": 0,
        "search_root_edges_covered": 0,
        "direct_mapping_count": 0,
        "mechanical_duplicate_mapping_count": 0,
    }
    counts.update(overrides)
    return counts


class _BoundedBattleSetup:
    def __init__(self, *, battle_after: int | None) -> None:
        self.battle_after = battle_after
        self.step_count = 0
        self.bridge_calls = 0
        self.snapshot_value = {
            "screen_state": "MAP",
            "battle_active": False,
            "battle_input_state": "NONE",
        }

    def snapshot(self) -> dict[str, object]:
        return dict(self.snapshot_value)

    def legal_actions(self) -> list[str]:
        return ["advance"]

    def step(self, _action: str) -> dict[str, object]:
        self.step_count += 1
        if self.battle_after is not None and self.step_count >= self.battle_after:
            self.snapshot_value = {
                "screen_state": "BATTLE",
                "battle_active": True,
                "battle_input_state": "PLAYER_NORMAL",
            }
        return self.snapshot()

    def bridge(self, *_args: object) -> dict[str, object]:
        assert self.snapshot_value == {
            "screen_state": "BATTLE",
            "battle_active": True,
            "battle_input_state": "PLAYER_NORMAL",
        }
        self.bridge_calls += 1
        return {"accepted": True}


def test_smoke_bridge_requires_active_player_battle_and_obeys_action_bound() -> None:
    assert MAX_BATTLE_ENTRY_ACTIONS == 32

    ready = _BoundedBattleSetup(battle_after=MAX_BATTLE_ENTRY_ACTIONS)
    result = _bridge_call_in_active_battle(
        ready, ready.bridge, max_actions=MAX_BATTLE_ENTRY_ACTIONS
    )
    assert result == {"accepted": True}
    assert ready.step_count == MAX_BATTLE_ENTRY_ACTIONS
    assert ready.bridge_calls == 1

    one_step_too_late = _BoundedBattleSetup(battle_after=MAX_BATTLE_ENTRY_ACTIONS)
    with pytest.raises(
        SystemExit,
        match=f"within {MAX_BATTLE_ENTRY_ACTIONS - 1} legal-action steps",
    ):
        _bridge_call_in_active_battle(
            one_step_too_late,
            one_step_too_late.bridge,
            max_actions=MAX_BATTLE_ENTRY_ACTIONS - 1,
        )
    assert one_step_too_late.step_count == MAX_BATTLE_ENTRY_ACTIONS - 1
    assert one_step_too_late.bridge_calls == 0


def _diagnostic(
    subreason: str,
    *,
    counts: dict[str, int] | None = None,
    occurrence: bool = False,
    representative: str | None = None,
) -> dict[str, object]:
    diagnostic: dict[str, object] = {
        "schema_id": DIAGNOSTIC_SCHEMA,
        "status": "failed",
        "mapping_subreason": subreason,
        **(counts or _counts()),
    }
    if occurrence:
        diagnostic.update(
            public_occurrence_index=diagnostic["public_occurrences_mapped"],
            public_action_kind=(
                "end_turn"
                if subreason == "missing_non_card_direct_search_root_match"
                else "card"
            ),
            direct_match_multiplicity=(
                "multiple"
                if subreason == "multiple_direct_search_root_matches"
                else "zero"
            ),
        )
    if representative is not None:
        diagnostic["representative_match_multiplicity"] = representative
    return diagnostic


@pytest.mark.parametrize(
    ("diagnostic", "expected_stage"),
    [
        (
            _diagnostic(
                "no_public_legal_action_surface",
                counts=_counts(
                    public_legal_occurrence_count=0,
                    search_root_edge_count=1,
                ),
            ),
            "failed",
        ),
        (
            _diagnostic(
                "multiple_direct_search_root_matches",
                occurrence=True,
            ),
            "failed",
        ),
        (
            _diagnostic(
                "missing_non_card_direct_search_root_match",
                occurrence=True,
            ),
            "failed",
        ),
        (
            _diagnostic(
                "card_not_adjacent_mechanical_duplicate",
                occurrence=True,
            ),
            "failed",
        ),
        (
            _diagnostic(
                "representative_search_root_match_zero",
                occurrence=True,
                representative="zero",
            ),
            "failed",
        ),
        (
            _diagnostic(
                "representative_search_root_match_multiple",
                occurrence=True,
                representative="multiple",
            ),
            "failed",
        ),
        (
            _diagnostic(
                "uncovered_search_root_edge",
                counts=_counts(
                    search_root_edge_count=2,
                    public_occurrences_mapped=1,
                    search_root_edges_covered=1,
                    direct_mapping_count=1,
                ),
            ),
            "failed",
        ),
    ],
)
def test_all_seven_native_mapping_failure_subreasons_are_structured(
    diagnostic: dict[str, object], expected_stage: str
) -> None:
    assert diagnostic["mapping_subreason"] in FAILURE_SUBREASONS
    assert (
        validate_t107_mapping_diagnostic(
            diagnostic, mapping_stage_status=expected_stage
        )
        == diagnostic
    )


def test_entered_mapping_diagnostic_is_bounded_and_stage_consistent() -> None:
    entered = {
        "schema_id": DIAGNOSTIC_SCHEMA,
        "status": "entered",
        "mapping_subreason": None,
    }
    assert (
        validate_t107_mapping_diagnostic(entered, mapping_stage_status="entered")
        == entered
    )
    with pytest.raises(ValueError, match="disagrees"):
        validate_t107_mapping_diagnostic(entered, mapping_stage_status="completed")


def test_none_is_only_valid_before_mapping_was_reached() -> None:
    assert (
        validate_t107_mapping_diagnostic(None, mapping_stage_status="not_reached")
        is None
    )
    with pytest.raises(ValueError, match="absent after mapping"):
        validate_t107_mapping_diagnostic(None, mapping_stage_status="entered")
    with pytest.raises(ValueError, match="exists before mapping"):
        validate_t107_mapping_diagnostic(
            {
                "schema_id": DIAGNOSTIC_SCHEMA,
                "status": "entered",
                "mapping_subreason": None,
            },
            mapping_stage_status="not_reached",
        )


def test_success_requires_complete_mapping_and_coverage_counts() -> None:
    completed = {
        "schema_id": DIAGNOSTIC_SCHEMA,
        "status": "completed",
        "mapping_subreason": "mapping_completed",
        **_counts(
            public_occurrences_mapped=1,
            search_root_edges_covered=1,
            direct_mapping_count=1,
        ),
    }
    assert (
        validate_t107_mapping_diagnostic(completed, mapping_stage_status="completed")
        == completed
    )
    invalid = deepcopy(completed)
    invalid["root_state"] = "must never cross the native boundary"
    with pytest.raises(ValueError, match="non-whitelisted"):
        validate_t107_mapping_diagnostic(invalid, mapping_stage_status="completed")


def test_mapping_failure_vocabulary_is_closed_and_native_audit_is_exact() -> None:
    audit = {"schema_id": AUDIT_SCHEMA, **dict.fromkeys(AUDIT_PREDICATES, True)}
    assert validate_t107_mapping_audit(audit) == audit
    audit["unlisted_condition"] = True
    with pytest.raises(ValueError, match="exactly"):
        validate_t107_mapping_audit(audit)
