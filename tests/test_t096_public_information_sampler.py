from __future__ import annotations

from types import SimpleNamespace

import pytest

from sts_combat_rl.sim.t096_public_information_sampler import (
    T096SamplerError,
    analytic_next_card_multiset,
    audit_native_particles,
    classify_t096,
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

    def t096_public_information_projection(self, snapshot):  # type: ignore[no-untyped-def]
        return self.projection

    def sample_hidden_future_particles(self, snapshot, *, sampler_seed, particle_count):  # type: ignore[no-untyped-def]
        assert sampler_seed == 7
        assert particle_count == len(self.particles)
        return self.particles


def test_native_audit_keeps_private_rows_out_of_projection_and_checks_diversity() -> (
    None
):
    projection = _projection()
    particles = [
        {
            "public_information_projection": projection,
            "hidden_future_fingerprint": "a",
            "next_draw_card_id": 2,
        },
        {
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


def test_classification_fails_closed_for_missing_four_anchor_gate() -> None:
    assert (
        classify_t096([{"particle_count": 8192, "distribution_pass": True}])
        == "INCOMPLETE"
    )
