from __future__ import annotations

import hashlib
from types import SimpleNamespace

import pytest

from sts_combat_rl.commands.t096_public_information_sampler import (
    T096_T087_RECORD_COUNT,
    T096_T087_SOURCE_PROVENANCE,
    _mechanics_evidence_gaps,
    run_t096_anchor_audits,
    select_first_four_frozen_t087_anchors,
)
from sts_combat_rl.sim.t096_public_information_sampler import (
    T096SamplerError,
    analytic_next_card_multiset,
    audit_native_particles,
    classify_t096,
    public_visibility_fidelity_gaps,
    total_variation,
    validate_public_information_projection,
)


def _projection() -> dict[str, object]:
    return {
        "schema_id": "native-battle-public-information-v1",
        "information_regime": "normal_information",
        "screen_identity": "BATTLE",
        "act": 1,
        "floor_num": 1,
        "encounter_id": "TEST",
        "turn": 0,
        "input_state": "PLAYER_NORMAL",
        "battle_outcome": "UNDECIDED",
        "player": {"current_hp": 80, "max_hp": 80, "energy": 3},
        "hand": [],
        "discard_pile": [],
        "exhaust_pile": [],
        "draw_pile_size": 3,
        "monsters": [],
        "persistent_resources": {
            "deck": [{"id": 1}, {"id": 2}, {"id": 2}, {"id": 3}],
            "relics": [],
            "potions": [],
            "gold": 99,
            "blue_key": False,
            "green_key": False,
            "red_key": False,
        },
        "visibility": {
            "draw_order": {"classification": "hidden"},
            "enemy_intent": {"classification": "public_exact"},
            "draw_knowledge": {"classification": "unsupported_fidelity"},
            "intent_hidden_mechanics": {"classification": "unsupported_fidelity"},
        },
        "ordered_public_legal_actions": [
            {
                "scope": "battle",
                "kind": "end_turn",
                "idx1": 0,
                "idx2": 0,
                "idx3": 0,
                "label": "end",
            }
        ],
        "draw_pile_membership": {"classification": "public_constraint"},
    }


def test_projection_firewall_rejects_private_rng_or_sampler_fields() -> None:
    value = _projection()
    value["visibility"] = {"draw_order": {"classification": "hidden", "rng_counter": 2}}
    with pytest.raises(T096SamplerError, match="private key"):
        validate_public_information_projection(value)


def test_visibility_aware_v2_projection_accepts_supported_current_information() -> None:
    value = _projection()
    value["schema_id"] = "native-battle-public-information-v2"
    value["information_fidelity"] = "supported"
    value["draw_knowledge_unsupported_reasons"] = []
    value["visibility"] = {
        "draw_order": {
            "classification": "known_prefix",
            "constraint": "public deterministic top-of-draw-pile placement",
        },
        "enemy_intent": {"classification": "public_exact"},
    }

    validated = validate_public_information_projection(value)

    assert validated["schema_id"] == "native-battle-public-information-v2"
    assert public_visibility_fidelity_gaps(validated) == []


def test_analytic_reference_preserves_multiset_partition() -> None:
    raw = {
        "deck": [{"id": 1}, {"id": 2}, {"id": 2}, {"id": 3}],
        "battle_hand": [{"id": 1}],
        "battle_discard_pile": [],
        "battle_exhaust_pile": [],
        "battle_draw_pile_size": 3,
    }
    assert analytic_next_card_multiset(raw) == {2: 2, 3: 1}


def test_total_variation_is_unpooled_and_exact() -> None:
    assert total_variation({1: 50, 2: 50}, {1: 1, 2: 1}) == pytest.approx(0.0)
    assert total_variation({1: 100}, {1: 1, 2: 1}) == pytest.approx(0.5)


class _FakeAdapter:
    def __init__(
        self, projection: dict[str, object], particles: list[dict[str, object]]
    ) -> None:
        self.projection = projection
        self.particles = particles

    def t096_public_information_projection(  # type: ignore[no-untyped-def]
        self, snapshot
    ):
        return self.projection

    def t096_anchor_distribution_metadata(  # type: ignore[no-untyped-def]
        self, snapshot
    ):
        return {
            "schema_id": "native-battle-anchor-distribution-audit-v1",
            "eligible": True,
            "first_ordinary_player_decision": True,
            "draw_order_visibility": "hidden",
            "stronger_draw_constraint": False,
            "draw_knowledge_fidelity": "ordinary-hidden-draw-only",
            "discard_empty": True,
            "exhaust_empty": True,
            "deck_size": 4,
            "hand_size": 1,
            "draw_pile_size": 3,
            "all_cards_persistent_deck_instances": True,
            "no_temporary_generated_inserted_cards": True,
            "multiset_union_exact": True,
            "remaining_unseen_card_counts": {2: 2, 3: 1},
            "remaining_unseen_card_identity_count": 2,
            "remaining_unseen_nonempty": True,
        }

    def sample_hidden_future_particles(  # type: ignore[no-untyped-def]
        self, snapshot, *, sampler_seed, particle_start, particle_count
    ):
        assert sampler_seed == 7
        assert particle_count == len(self.particles)
        assert particle_start == 0
        return self.particles


def test_native_audit_keeps_private_rows_out_of_projection_and_checks_diversity() -> (
    None
):
    projection = _projection()
    particles = [
        {
            "particle_index": 0,
            "sampler_seed": 101,
            "public_information_projection": projection,
            "hidden_future_fingerprint": "a",
            "next_draw_card_id": 2,
        },
        {
            "particle_index": 1,
            "sampler_seed": 102,
            "public_information_projection": projection,
            "hidden_future_fingerprint": "b",
            "next_draw_card_id": 3,
        },
    ]
    raw = {
        "deck": [{"id": 1}, {"id": 2}, {"id": 2}, {"id": 3}],
        "battle_hand": [{"id": 1}],
        "battle_discard_pile": [],
        "battle_exhaust_pile": [],
        "battle_draw_pile_size": 3,
    }
    result = audit_native_particles(
        _FakeAdapter(projection, particles),
        SimpleNamespace(raw=raw),
        sampler_seed=7,
        particle_count=2,
    )
    assert result["public_parity_pass_count"] == 2
    assert result["legal_action_parity_pass_count"] == 2
    assert result["distinct_hidden_future_fingerprint_count"] == 2
    assert result["distribution_pass"] is False
    assert result["visibility_fidelity_gaps"] == [
        "draw_knowledge:unsupported_fidelity",
        "intent_hidden_mechanics:unsupported_fidelity",
    ]


def test_public_action_identity_rejects_native_replay_bits() -> None:
    value = _projection()
    value["ordered_public_legal_actions"][0]["label"] = (
        "end bits=123"
    )  # type: ignore[index]
    with pytest.raises(T096SamplerError, match="replay-only native bits"):
        validate_public_information_projection(value)


def test_classification_fails_closed_for_missing_four_anchor_gate() -> None:
    assert (
        classify_t096([{"particle_count": 8192, "distribution_pass": True}])
        == "INCOMPLETE"
    )


class _SelectionAdapter(_FakeAdapter):
    def __init__(self, eligible: bool) -> None:
        super().__init__(_projection(), [])
        self.eligible = eligible

    def t096_anchor_distribution_metadata(  # type: ignore[no-untyped-def]
        self, snapshot
    ):
        metadata = super().t096_anchor_distribution_metadata(snapshot)
        metadata["eligible"] = self.eligible
        if not self.eligible:
            metadata["remaining_unseen_card_identity_count"] = 1
        return metadata


def test_frozen_selector_uses_first_four_eligible_canonical_rows(
    monkeypatch,
) -> None:  # type: ignore[no-untyped-def]
    rows = [
        {
            "selection_identity": f"row-{index}",
            "cohort": "A" if index < 93 else "B" if index < 285 else "C",
        }
        for index in range(T096_T087_RECORD_COUNT)
    ]

    def loader(row):  # type: ignore[no-untyped-def]
        return _SelectionAdapter(row["selection_identity"] != "row-1"), object()

    for cohort, ids in {
        cohort: [row["selection_identity"] for row in rows if row["cohort"] == cohort]
        for cohort in ("A", "B", "C")
    }.items():
        monkeypatch.setitem(
            T096_T087_SOURCE_PROVENANCE["selection_identity_orders_sha256"],
            cohort,
            hashlib.sha256("\n".join(ids).encode()).hexdigest(),
        )

    selection = select_first_four_frozen_t087_anchors(
        ordered_rows=rows,
        anchor_loader=loader,
        source_provenance=T096_T087_SOURCE_PROVENANCE,
    )
    assert selection["selection_complete"] is True
    assert [row["canonical_position"] for row in selection["selected_anchors"]] == [
        0,
        2,
        3,
        4,
    ]


def test_frozen_selector_rejects_identity_order_digest_mismatch() -> None:
    rows = [
        {
            "selection_identity": f"row-{index}",
            "cohort": "A" if index < 93 else "B" if index < 285 else "C",
        }
        for index in range(T096_T087_RECORD_COUNT)
    ]
    selection = select_first_four_frozen_t087_anchors(
        ordered_rows=rows,
        anchor_loader=lambda row: (_SelectionAdapter(True), object()),
        source_provenance=T096_T087_SOURCE_PROVENANCE,
    )
    assert selection["terminal_classification"] == "INCOMPLETE"
    assert selection["failure_reason"] == (
        "T096 T087 selection identity order digest mismatch"
    )


def test_frozen_selector_rejects_short_or_duplicate_unprovenanced_cohorts() -> None:
    short_rows = [{"selection_identity": f"row-{index}"} for index in range(4)]
    short = select_first_four_frozen_t087_anchors(
        ordered_rows=short_rows,
        anchor_loader=lambda row: (_SelectionAdapter(True), object()),
        source_provenance=T096_T087_SOURCE_PROVENANCE,
    )
    assert short["terminal_classification"] == "INCOMPLETE"
    assert short["failure_code"] == "invalid_t087_canonical_input"

    duplicate_rows = [
        {
            "selection_identity": f"row-{index}",
            "cohort": "A" if index < 93 else "B" if index < 285 else "C",
        }
        for index in range(T096_T087_RECORD_COUNT)
    ]
    duplicate_rows[-1]["selection_identity"] = duplicate_rows[0]["selection_identity"]
    duplicate = select_first_four_frozen_t087_anchors(
        ordered_rows=duplicate_rows,
        anchor_loader=lambda row: (_SelectionAdapter(True), object()),
        source_provenance=T096_T087_SOURCE_PROVENANCE,
    )
    assert duplicate["terminal_classification"] == "INCOMPLETE"
    assert duplicate["failure_code"] == "invalid_t087_canonical_input"

    unprovenanced = select_first_four_frozen_t087_anchors(
        ordered_rows=[
            {
                "selection_identity": f"row-{index}",
                "cohort": "A" if index < 93 else "B" if index < 285 else "C",
            }
            for index in range(T096_T087_RECORD_COUNT)
        ],
        anchor_loader=lambda row: (_SelectionAdapter(True), object()),
    )
    assert unprovenanced["terminal_classification"] == "INCOMPLETE"


def test_audit_workflow_is_incomplete_without_four_frozen_anchors() -> None:
    selection = select_first_four_frozen_t087_anchors(
        ordered_rows=[{"selection_identity": "only"}],
        anchor_loader=lambda row: (_SelectionAdapter(True), object()),
    )
    report = run_t096_anchor_audits(
        anchor_loader=lambda row: (_SelectionAdapter(True), object()),
        anchor_selection=selection,
        sampler_seed=7,
        particle_count=2,
    )
    assert report["terminal_classification"] == "INCOMPLETE"


def test_mechanics_evidence_cannot_default_to_ready() -> None:
    assert _mechanics_evidence_gaps([], set()) == {
        "missing_mechanics_case_evidence"
    }
    assert _mechanics_evidence_gaps(
        [{"case": "draw_knowledge", "status": "supported"}], set()
    ) == {"intent_visibility:missing_evidence"}
