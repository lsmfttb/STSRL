from __future__ import annotations

from types import SimpleNamespace

import pytest

from sts_combat_rl.sim.lightspeed import LightSpeedAdapter
from sts_combat_rl.sim.t099_particle_search_bridge import (
    T099_REQUIRED_AUDIT_PREDICATES,
    T099ParticleSearchBridgeError,
    validate_t099_particle_search_audit,
    validate_t099_particle_search_bridge,
)


def _action(kind: str, idx1: int, label: str) -> dict[str, object]:
    return {
        "scope": "battle",
        "kind": kind,
        "idx1": idx1,
        "idx2": 0,
        "idx3": 0,
        "label": label,
    }


def _projection(actions: list[dict[str, object]]) -> dict[str, object]:
    return {
        "schema_id": "native-battle-public-information-v2",
        "information_regime": "normal_information",
        "screen_identity": "BATTLE",
        "act": 1,
        "floor_num": 1,
        "encounter_id": "JAW_WORM",
        "turn": 0,
        "input_state": "PLAYER_NORMAL",
        "battle_outcome": "UNDECIDED",
        "player": {"current_hp": 80},
        "hand": [],
        "discard_pile": [],
        "exhaust_pile": [],
        "draw_pile_size": 5,
        "monsters": [],
        "persistent_resources": {},
        "information_fidelity": "supported",
        "draw_knowledge_unsupported_reasons": [],
        "visibility": {
            "draw_order": {"classification": "hidden"},
            "enemy_intent": {"classification": "public_exact"},
        },
        "ordered_public_legal_actions": actions,
        "draw_pile_membership": {"classification": "public_constraint"},
    }


def _work_counters() -> dict[str, object]:
    return {
        "schema_id": "native-battle-search-work-v1",
        "action_execution_count": 3,
        "successor_transition_count": 3,
        "tree_and_rollout_action_execution_count": 3,
        "heuristic_successor_transition_count": 0,
        "tree_node_expansion_count": 1,
        "rollout_count": 1,
        "terminal_utility_evaluation_count": 1,
        "policy_prior_calls": 0,
        "leaf_value_calls": 0,
        "model_calls": 0,
    }


def _bridge_report() -> dict[str, object]:
    actions = [
        _action("end_turn", 0, "battle.end_turn"),
        _action("card", 0, "Strike"),
        _action("card", 1, "Strike"),
    ]
    projection = _projection(actions)
    source_actions = [actions[0], actions[1], actions[1]]
    edge_indices = [0, 1, 1]
    modes = [
        "direct_action_bits",
        "direct_action_bits",
        "mechanical_duplicate_card_occurrence",
    ]
    root_rows: list[dict[str, object]] = []
    mappings: list[dict[str, object]] = []
    for ordinal, action in enumerate(actions):
        root_rows.append(
            {
                **action,
                "search_tree_present": True,
                "search_edge_index": edge_indices[ordinal],
                "visits": 1,
                "evaluation_sum": 1.0,
                "mean_value": 1.0,
                "public_action_ordinal": ordinal,
                "search_equivalence_source_edge_index": edge_indices[ordinal],
                "search_equivalence_mapping_mode": modes[ordinal],
            }
        )
        mappings.append(
            {
                "public_action_ordinal": ordinal,
                "public_action": action,
                "search_edge_index": edge_indices[ordinal],
                "mapping_mode": modes[ordinal],
                "source_action": source_actions[ordinal],
                "edge_public_occurrence_count": 1 if ordinal == 0 else 2,
            }
        )
    root_evaluation = {
        "schema_id": "native-battle-search-root-v1",
        "native_api": "StepSimulator.sample_hidden_future_particles_search.v1",
        "patch_identity": "sts_lightspeed_native_particle_search_bridge_v1",
        "information_regime": "full_simulator_state_oracle_like",
        "simulations_requested": 1,
        "root_visits": 2,
        "include_potions": False,
        "native_simulator_steps": 3,
        "model_calls": 0,
        "best_action_value": 1.0,
        "min_action_value": 1.0,
        "outcome_player_hp": 80,
        "root_row_count": 3,
        "search_edge_count": 2,
        "unsearched_legal_action_count": 0,
        "unmapped_search_edge_count": 0,
        "work_counters": _work_counters(),
        "search_v2_configuration": {
            "policy_prior_enabled": False,
            "learned_leaf_value_enabled": False,
            "progressive_bias_enabled": False,
        },
        "root_rows": root_rows,
        "root_action_mapping_schema": ("native-search-root-occurrence-equivalence-v1"),
        "root_action_mapping": mappings,
    }
    particle = {
        "particle_index": 0,
        "sampler_seed": 123,
        "hidden_future_fingerprint": "audit-only-fingerprint",
        "public_information_projection": projection,
        "public_projection_equal": True,
        "ordered_public_legal_actions_equal": True,
        "ordered_public_legal_actions": actions,
        "root_action_mapping_complete": True,
        "root_action_mapping_ambiguous": False,
        "search_value_semantics": "full_state_continuation_strategy_fusion_proxy",
        "root_evaluation": root_evaluation,
        "root_rows": root_rows,
    }
    return {
        "schema_id": "native-battle-public-particle-search-v1",
        "native_api": "StepSimulator.sample_hidden_future_particles_search.v1",
        "sampler_seed_input": 17,
        "particle_start": 0,
        "particle_count": 1,
        "search_simulations": 1,
        "include_potions": False,
        "information_regime": (
            "normal_belief_search_outer_full_simulator_state_oracle_like_continuation"
        ),
        "anchor_public_information_projection": projection,
        "anchor_ordered_public_legal_actions": actions,
        "semantic_boundary": {
            "outer_particle_distribution": (
                "native_public_consistent_hidden_future_sampler"
            ),
            "continuation": "full_state_search_v2_per_particle",
            "aggregation": "not_performed",
            "q_public_claim": False,
            "executable_no_sl_continuation_claim": False,
            "information_set_optimal_claim": False,
        },
        "particles": [particle],
    }


def _native_audit() -> dict[str, object]:
    return {
        "schema_id": "native-stsr006-particle-search-audit-v1",
        **{predicate: True for predicate in T099_REQUIRED_AUDIT_PREDICATES},
    }


def test_bridge_accepts_occurrence_equivalent_duplicate_cards() -> None:
    report = validate_t099_particle_search_bridge(_bridge_report())

    particle = report["particles"][0]
    root = particle["root_evaluation"]
    mappings = root["root_action_mapping"]
    assert mappings[1]["search_edge_index"] == mappings[2]["search_edge_index"]
    assert mappings[2]["mapping_mode"] == "mechanical_duplicate_card_occurrence"
    assert mappings[2]["edge_public_occurrence_count"] == 2
    assert all("bits" not in row for row in particle["root_rows"])


def test_bridge_accepts_sanitized_unvisited_root_rows() -> None:
    report = _bridge_report()
    row = report["particles"][0]["root_rows"][2]
    row["visits"] = 0
    row["evaluation_sum"] = 0.0
    row["mean_value"] = None

    validate_t099_particle_search_bridge(report)


@pytest.mark.parametrize(
    ("path", "value", "match"),
    [
        (("particles", 0, "root_action_mapping_complete"), False, "incomplete"),
        (("particles", 0, "root_action_mapping_ambiguous"), True, "ambiguous"),
        (
            (
                "particles",
                0,
                "root_evaluation",
                "root_action_mapping",
                2,
                "edge_public_occurrence_count",
            ),
            1,
            "count disagrees",
        ),
        (
            ("semantic_boundary", "q_public_claim"),
            True,
            "mixed information-regime semantics",
        ),
    ],
)
def test_bridge_fails_closed_on_invalid_contract(path, value, match) -> None:
    report = _bridge_report()
    target = report
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value

    with pytest.raises(T099ParticleSearchBridgeError, match=match):
        validate_t099_particle_search_bridge(report)


def test_bridge_rejects_replay_only_bits_from_public_identity() -> None:
    report = _bridge_report()
    row = report["particles"][0]["root_rows"][0]
    row["bits"] = 123

    with pytest.raises(T099ParticleSearchBridgeError, match="keys mismatch"):
        validate_t099_particle_search_bridge(report)


def test_native_audit_requires_every_predicate_true() -> None:
    assert validate_t099_particle_search_audit(_native_audit()) == _native_audit()
    audit = _native_audit()
    audit["known_draw_constraint_preserved"] = False

    with pytest.raises(T099ParticleSearchBridgeError, match="known_draw"):
        validate_t099_particle_search_audit(audit)


class _FakeStepSimulator:
    def __init__(self, character_class, seed, ascension) -> None:
        self.seed = seed
        self.ascension = ascension
        self.bridge_calls: list[tuple[object, ...]] = []

    def snapshot(self):  # type: ignore[no-untyped-def]
        return {"screen_state": "BATTLE", "outcome": "UNDECIDED"}

    def observation(self):  # type: ignore[no-untyped-def]
        return [self.seed, self.ascension]

    def sample_hidden_future_particles_search(self, *args):  # type: ignore[no-untyped-def]
        self.bridge_calls.append(args)
        return _bridge_report()

    def stsr006_particle_search_audit(self):  # type: ignore[no-untyped-def]
        return _native_audit()


def test_adapter_exposes_only_bounded_validated_bridge_surface() -> None:
    module = SimpleNamespace(
        CharacterClass=SimpleNamespace(IRONCLAD="IRONCLAD"),
        StepSimulator=_FakeStepSimulator,
    )
    adapter = LightSpeedAdapter(seed=1, ascension=20, module=module)
    snapshot = adapter._snapshot()

    report = adapter.sample_hidden_future_particles_search(
        snapshot,
        sampler_seed=17,
        particle_count=1,
        search_simulations=1,
    )

    assert report["schema_id"] == "native-battle-public-particle-search-v1"
    assert adapter._sim.bridge_calls == [(17, 0, 1, 1, False)]
    assert adapter.stsr006_particle_search_audit() == _native_audit()


@pytest.mark.parametrize("particle_count", [0, 65, True])
def test_adapter_rejects_invalid_particle_count_before_native_call(
    particle_count,
) -> None:
    module = SimpleNamespace(
        CharacterClass=SimpleNamespace(IRONCLAD="IRONCLAD"),
        StepSimulator=_FakeStepSimulator,
    )
    adapter = LightSpeedAdapter(seed=1, ascension=20, module=module)

    with pytest.raises((TypeError, ValueError), match="particle_count"):
        adapter.sample_hidden_future_particles_search(
            adapter._snapshot(),
            sampler_seed=17,
            particle_count=particle_count,
            search_simulations=1,
        )

    assert adapter._sim.bridge_calls == []
