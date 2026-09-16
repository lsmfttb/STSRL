"""Focused T092 firewall, support, and deterministic-harness contracts."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict

import pytest

from sts_combat_rl.sim.t092_internal_search_state import (
    T092_FROZEN_TEACHER_CONFIG,
    T092Incomplete,
    T092_NATIVE_IDENTITY,
    compare_semantic_parity,
    parse_native_occurrences,
    select_t092_canary_sources,
    summarize_occurrences,
    support_pairs,
    validate_retained_occurrence,
)


def _action(bits: int, kind: str = "card") -> dict[str, object]:
    return {"scope": "battle", "bits": bits, "kind": kind, "idx1": 0, "idx2": 0, "idx3": 0, "label": str(bits)}


def _report() -> dict[str, object]:
    return {
        "schema_id": "native-battle-search-root-v1",
        "native_api": "StepSimulator.battle_search_v2_with_internal_teacher_telemetry.v1",
        "patch_identity": "sts_lightspeed_battle_search_v2_internal_teacher_telemetry_v1",
        "information_regime": "full_simulator_state_oracle_like",
        "root_visits": 400,
        "native_simulator_steps": 1200,
        "simulations_requested": 400,
        "include_potions": False,
        "teacher_config": dict(T092_FROZEN_TEACHER_CONFIG),
        "tree_internal_telemetry": {
            "internal_teacher_telemetry": {
                "schema_id": "native-battle-search-v2-internal-teacher-telemetry-v1",
                "schema_version": 1,
                "collection_phase": "post_search_private_state_replay",
                "search_rng_or_counter_mutated": False,
                "raw_private_state_exported": False,
                "telemetry_extraction_transition_count": 4,
                "candidate_count": 1,
                "rows": [{
                    "occurrence_identity": "root.0",
                    "tree_depth": 1,
                    "expansion_ordinal": 2,
                    "input_state": "PLAYER_NORMAL",
                    "public_battle_projection": {"battle_player_hp": 70, "battle_hand": []},
                    "teacher_searchable_actions": [
                        {"action": _action(1), "visits": 4, "mean_value": 0.8},
                        {"action": _action(2, "end_turn"), "visits": 4, "mean_value": 0.3},
                        {"action": _action(3), "visits": 0, "mean_value": None},
                    ],
                    "public_teacher_excluded_actions": [{
                        "action": _action(4, "potion"),
                        "exclusion_reason": "frozen_no_potion_teacher_configuration",
                    }],
                }],
            }
        },
    }


def _parse(report: dict[str, object] | None = None):
    return parse_native_occurrences(report or _report(), source_identity="source-1", source_group="A", split="train", parent_root_decision_identity="root-1", native_identity=T092_NATIVE_IDENTITY)


def test_zero_visit_child_remains_unknown_and_excluded_potions_are_separate() -> None:
    row = _parse()[0]
    assert len(support_pairs(row, 4)) == 1
    report = summarize_occurrences([row])
    assert report["thresholds"]["4"]["retained_ordered_non_tie_pairs"] == 1
    assert report["teacher_excluded_action_kinds"] == {"potion": 1}


def test_hidden_fields_are_rejected_before_candidate_materialization() -> None:
    report = _report()
    telemetry = report["tree_internal_telemetry"]
    assert isinstance(telemetry, dict)
    native = telemetry["internal_teacher_telemetry"]
    assert isinstance(native, dict)
    rows = native["rows"]
    assert isinstance(rows, list)
    rows[0]["public_battle_projection"]["rng_state"] = "forbidden"
    with pytest.raises(T092Incomplete, match="forbidden private field"):
        _parse(report)


def test_report_teacher_envelope_and_task_scoped_native_identity_fail_closed() -> None:
    report = _report()
    report["simulations_requested"] = 399
    with pytest.raises(T092Incomplete, match="frozen Search-v2@400"):
        _parse(report)

    report = _report()
    report["teacher_config"]["root_selection"] = "most_visits"
    with pytest.raises(T092Incomplete, match="teacher configuration"):
        _parse(report)

    with pytest.raises(T092Incomplete, match="native identity"):
        parse_native_occurrences(_report(), source_identity="source-1", source_group="A", split="train", parent_root_decision_identity="root-1", native_identity={})
    with pytest.raises(T092Incomplete, match="native identity"):
        parse_native_occurrences(
            _report(),
            source_identity="source-1",
            source_group="A",
            split="train",
            parent_root_decision_identity="root-1",
        )


def test_depth_zero_root_is_not_an_internal_occurrence() -> None:
    report = _report()
    native = report["tree_internal_telemetry"]["internal_teacher_telemetry"]
    native["rows"][0]["tree_depth"] = 0
    with pytest.raises(T092Incomplete, match="tree metadata"):
        _parse(report)


def test_retained_occurrence_revalidates_metadata_depth_and_public_firewall() -> None:
    row = _parse()[0]
    payload = asdict(row)
    payload["tree_depth"] = 0
    with pytest.raises(T092Incomplete, match="tree metadata"):
        validate_retained_occurrence(payload)

    payload = asdict(row)
    payload["native_identity"]["commit"] = "0" * 40
    with pytest.raises(T092Incomplete, match="native identity"):
        validate_retained_occurrence(payload)

    payload = asdict(row)
    payload["schema_version"] = 2
    with pytest.raises(T092Incomplete, match="schema"):
        validate_retained_occurrence(payload)

    payload = asdict(row)
    payload["input_state"] = "ENEMY_TURN"
    with pytest.raises(T092Incomplete, match="input state"):
        validate_retained_occurrence(payload)

    payload = asdict(row)
    payload["public_battle_projection"]["hidden_draw_order"] = [1]
    with pytest.raises(T092Incomplete, match="forbidden private field"):
        validate_retained_occurrence(payload)

    payload = asdict(row)
    payload["searchable_actions"][0]["action"]["bits"] = "one"
    with pytest.raises(T092Incomplete, match="invalid bits"):
        validate_retained_occurrence(payload)


def test_cross_split_fingerprint_excludes_every_occurrence() -> None:
    train = _parse()[0]
    heldout = _parse()[0]
    heldout = heldout.__class__(**{**heldout.__dict__, "split": "heldout"})
    report = summarize_occurrences([train, heldout])
    assert report["cross_split_fingerprint_count"] == 1
    assert report["thresholds"]["4"]["leakage_safe_unique_examples"] == 0


def test_canary_selection_is_exactly_four_per_group_and_deterministic() -> None:
    ledger = [{"source_group": group, "source_identity": f"{group}-{index}"} for group in "ABC" for index in range(6)]
    first = select_t092_canary_sources(ledger)
    assert first == select_t092_canary_sources(list(reversed(ledger)))
    assert len(first) == 12
    assert {group: sum(row["source_group"] == group for row in first) for group in "ABC"} == {"A": 4, "B": 4, "C": 4}


def test_parity_comparison_ignores_telemetry_only_fields_but_not_root_semantics() -> None:
    off = _report()
    on = deepcopy(off)
    assert compare_semantic_parity(off, on) == []
    on["root_visits"] = 399
    assert compare_semantic_parity(off, on) == ["root_visits"]
