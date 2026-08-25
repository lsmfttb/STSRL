from __future__ import annotations

from dataclasses import replace

import pytest

from sts_combat_rl.sim.action_space import ActionSpaceConfig
from sts_combat_rl.sim.search_cost import (
    PublicNodeInferenceCache,
    public_node_cache_key,
)
from sts_combat_rl.sim.contract import SimulatorAction
from sts_combat_rl.sim.controlled_run import build_decision_context
from sts_combat_rl.sim.policy import DecisionContext
from sts_combat_rl.sim.search_guidance_inference import (
    SearchGuidanceActionScore,
    SearchGuidanceCheckpointProvenance,
    SearchGuidanceInferenceResult,
)


def _context() -> DecisionContext:
    raw = {
        "screen_state": "BATTLE",
        "battle_active": True,
        "act": 1,
        "floor_num": 1,
        "ascension": 20,
        "battle_turn": 1,
        "battle_player_hp": 70,
        "battle_player_energy": 3,
        "battle_player_block": 0,
        "battle_hand": [],
        "battle_monsters": [],
    }
    actions = [
        SimulatorAction(
            action_id="battle:11",
            label="Strike",
            kind="card",
            raw={"scope": "battle", "bits": 11, "idx1": 0, "idx2": 0, "idx3": 0},
        ),
        SimulatorAction(
            action_id="battle:22",
            label="Defend",
            kind="card",
            raw={"scope": "battle", "bits": 22, "idx1": 1, "idx2": 0, "idx3": 0},
        ),
    ]
    return build_decision_context(
        raw,
        actions,
        ActionSpaceConfig.initial_no_potions(),
        public_run_context={"visible_history": []},
    )


def _checkpoint() -> SearchGuidanceCheckpointProvenance:
    return SearchGuidanceCheckpointProvenance(
        checkpoint_schema_id="torch-policy-value-checkpoint-v1",
        checkpoint_format_version=1,
        checkpoint_artifact_id="unit-test",
        checkpoint_path="/tmp/unit-test.pt",
        model_class="TinyPolicyValueNet",
        model_config={"hidden_size": 8},
        trainer_input_artifact_id="trainer-input-sha256:abc",
        trainer_input_sha256="abc",
        policy_target_kind="oracle_teacher_action_one_hot",
        policy_target_source="oracle_teacher_row.teacher_action",
    )


def _result(context: DecisionContext, marker: float) -> SearchGuidanceInferenceResult:
    return SearchGuidanceInferenceResult(
        scorer_name="cache-test",
        checkpoint_provenance=_checkpoint(),
        legal_action_count=len(context.legal_action_features),
        eligible_action_count=len(context.eligible_action_indices),
        action_scores=[
            SearchGuidanceActionScore(
                legal_action_index=index,
                action_kind=context.legal_action_kinds[index],
                eligible=index in context.eligible_action_indices,
                policy_logit=marker,
                policy_probability=0.5,
                action_identity=dict(
                    context.tactical_legal_actions[index].get("identity", {})
                ),
            )
            for index in range(len(context.legal_action_features))
        ],
    )


def test_cache_key_is_sensitive_to_every_public_context_field() -> None:
    context = _context()
    original = public_node_cache_key(context)
    assert original is not None
    variants: list[DecisionContext] = [
        replace(context, screen_state="BATTLE_VARIANT"),
        replace(context, snapshot_features=[*context.snapshot_features, 1.0]),
        replace(
            context,
            legal_action_features=[
                [*context.legal_action_features[0], 1.0],
                *context.legal_action_features[1:],
            ],
        ),
        replace(context, legal_action_kinds=["skill", *context.legal_action_kinds[1:]]),
        replace(context, eligible_action_indices=[0]),
        replace(context, snapshot_metadata={"variant": 1}),
        replace(context, legal_action_metadata=[{"variant": 1}, {}]),
        replace(context, tactical_state={"variant": 1}),
        replace(
            context,
            tactical_legal_actions=[
                {
                    **context.tactical_legal_actions[0],
                    "identity": {
                        **context.tactical_legal_actions[0]["identity"],
                        "occurrence": 7,
                    },
                },
                *context.tactical_legal_actions[1:],
            ],
        ),
        replace(context, tactical_feature_schema_id="public-tactical-variant"),
        replace(context, public_run_context={"visible_history": ["variant"]}),
    ]
    assert len(variants) == len(context.__dataclass_fields__)
    for variant in variants:
        key = public_node_cache_key(variant)
        assert key is not None
        assert key != original


def test_cache_key_fails_closed_without_occurrence_safe_actions() -> None:
    context = _context()
    malformed = replace(
        context,
        tactical_legal_actions=[
            {
                **context.tactical_legal_actions[0],
                "identity": {"stable_id": "battle:11"},
            },
            *context.tactical_legal_actions[1:],
        ],
    )
    assert public_node_cache_key(malformed) is None


def test_cache_capacity_evicts_oldest_exact_entry() -> None:
    cache = PublicNodeInferenceCache(capacity=1)
    calls = 0

    def score(context: DecisionContext) -> SearchGuidanceInferenceResult:
        nonlocal calls
        calls += 1
        return _result(context, float(calls))

    first = _context()
    second = replace(first, public_run_context={"visible_history": ["second"]})
    assert cache.score(first, score).cache_hit is False
    assert cache.score(second, score).cache_hit is False
    assert cache.score(second, score).cache_hit is True
    telemetry = cache.telemetry()
    assert telemetry["cache_eviction_count"] == 1.0
    assert telemetry["cache_hit_count"] == 1.0
    assert calls == 2


def test_digest_collision_scores_uncached_and_discards_colliding_entry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _ConstantDigest:
        def hexdigest(self) -> str:
            return "same-digest"

    monkeypatch.setattr(
        "sts_combat_rl.sim.search_cost.hashlib.sha256",
        lambda payload: _ConstantDigest(),
    )
    cache = PublicNodeInferenceCache(capacity=2)
    calls = 0

    def score(context: DecisionContext) -> SearchGuidanceInferenceResult:
        nonlocal calls
        calls += 1
        return _result(context, float(calls))

    first = _context()
    second = replace(first, public_run_context={"visible_history": ["second"]})
    first_score = cache.score(first, score)
    collision_score = cache.score(second, score)
    assert first_score.cache_hit is False
    assert collision_score.cache_hit is False
    assert collision_score.cache_key is None
    assert calls == 2
    assert cache.telemetry()["cache_entry_count"] == 0.0


def test_unsupported_public_value_is_uncacheable_and_always_scored() -> None:
    cache = PublicNodeInferenceCache()
    context = replace(_context(), public_run_context={"unsupported": object()})
    calls = 0

    def score(node: DecisionContext) -> SearchGuidanceInferenceResult:
        nonlocal calls
        calls += 1
        return _result(node, float(calls))

    assert cache.score(context, score).cache_key is None
    assert cache.score(context, score).cache_key is None
    assert calls == 2
    assert cache.telemetry()["cache_uncacheable_count"] == 2.0
