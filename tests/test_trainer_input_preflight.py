from __future__ import annotations

from copy import deepcopy
from dataclasses import replace

from sts_combat_rl.sim.model_input import build_model_input_batch
from sts_combat_rl.sim.public_context_model_input import (
    PUBLIC_CONTEXT_MODEL_INPUT_FEATURE_SIZE,
    PUBLIC_CONTEXT_MODEL_INPUT_SCHEMA_ID,
    PUBLIC_CONTEXT_MODEL_INPUT_SCHEMA_VERSION,
    encode_public_context_model_input,
)
from sts_combat_rl.sim.trainer_input_preflight import (
    build_trainer_input_preflight_report,
    format_trainer_input_preflight_report,
)

from t009_helpers import make_trainer_dataset


def test_public_context_model_input_encodes_v1_feature_groups() -> None:
    dataset = make_trainer_dataset([(20, 1)])
    context = _rich_public_context(dataset.records[0].public_run_context)

    encoded = encode_public_context_model_input(
        public_context_status="available",
        public_run_context=context,
    )
    features = dict(
        zip(
            encoded.public_context_feature_names,
            encoded.public_context_features,
            strict=True,
        )
    )

    assert encoded.public_context_feature_schema_id == (
        PUBLIC_CONTEXT_MODEL_INPUT_SCHEMA_ID
    )
    assert encoded.public_context_feature_schema_version == (
        PUBLIC_CONTEXT_MODEL_INPUT_SCHEMA_VERSION
    )
    assert (
        encoded.public_context_feature_size == PUBLIC_CONTEXT_MODEL_INPUT_FEATURE_SIZE
    )
    assert (
        len(encoded.public_context_features) == PUBLIC_CONTEXT_MODEL_INPUT_FEATURE_SIZE
    )
    assert features["run_position.ascension.available"] == 1.0
    assert features["run_position.ascension"] == 20.0
    assert features["run_position.act"] == 1.0
    assert features["public_resources.current_hp"] == 60.0
    assert features["public_resources.hp_ratio"] == 0.75
    assert features["public_resources.deck_size"] == 4.0
    assert features["public_resources.curse_count"] == 1.0
    assert features["route_context.legal_route_count"] == 3.0
    assert features["route_context.next_room.elite_count"] == 1.0
    assert features["history_counts.card_choice"] == 1.0
    assert features["recent_public_outcomes.current_hp_delta_total"] == -4.0
    assert features["identity_summary_v1.attack_card_count"] == 1.0
    assert features["identity_summary_v1.candidate_card_action_count"] == 1.0
    assert encoded.public_context_missingness_summary["encoded"] is True
    assert encoded.problems == []

    encoded_again = encode_public_context_model_input(
        public_context_status="available",
        public_run_context=deepcopy(context),
    )
    assert encoded_again.public_context_features == encoded.public_context_features


def test_public_context_model_input_hidden_field_firewall_reaches_batch() -> None:
    dataset = make_trainer_dataset([(20, 1)])
    record = dataset.records[0]
    leaked_context = deepcopy(record.public_run_context)
    leaked_context["nested"] = {"hidden_rng_state": 123}

    encoded = encode_public_context_model_input(
        public_context_status="available",
        public_run_context=leaked_context,
    )
    assert encoded.public_context_missingness_summary["encoded"] is False
    assert any("hidden_rng_state" in problem for problem in encoded.problems)

    batch = build_model_input_batch(
        replace(dataset, records=[replace(record, public_run_context=leaked_context)])
    )
    assert any("hidden_rng_state" in problem for problem in batch.problems)


def test_public_context_model_input_blocks_assistance_leakage_but_ignores_metadata() -> (
    None
):
    dataset = make_trainer_dataset([(20, 1)])
    record = dataset.records[0]
    assisted_metadata_record = replace(
        record,
        source_metadata={
            **record.source_metadata,
            "distribution_kind": "assisted_run",
            "assistance_schedule": "assist_hp50",
            "requested_assistance_changes": {"current_hp": 50},
        },
    )
    batch = build_model_input_batch(
        replace(dataset, records=[assisted_metadata_record])
    )

    assert batch.problems == []
    assert not any("assist" in name for name in batch.public_context_feature_names)
    assert "assistance_schedule" not in str(batch.public_run_contexts[0])
    assert batch.public_context_features[0]

    leaked_context = deepcopy(record.public_run_context)
    leaked_context["assistance_schedule"] = "assist_hp50"
    leaked_batch = build_model_input_batch(
        replace(dataset, records=[replace(record, public_run_context=leaked_context)])
    )
    assert any("assistance-only" in problem for problem in leaked_batch.problems)


def test_trainer_input_preflight_reports_public_context_schema() -> None:
    dataset = make_trainer_dataset([(20, 1), (20, 1)])

    report = build_trainer_input_preflight_report(dataset)
    text = format_trainer_input_preflight_report(report, detail_limit=1)

    assert report.model_input_report is not None
    assert report.model_input_report.public_context_feature_schema_id == (
        PUBLIC_CONTEXT_MODEL_INPUT_SCHEMA_ID
    )
    assert report.model_input_report.public_context_feature_schema_version == (
        PUBLIC_CONTEXT_MODEL_INPUT_SCHEMA_VERSION
    )
    assert report.model_input_report.public_context_feature_size == (
        PUBLIC_CONTEXT_MODEL_INPUT_FEATURE_SIZE
    )
    assert (
        report.model_input_report.public_context_missingness_summary["encoded_count"]
        == 2
    )
    assert "public context feature schema: public-context-model-input-v1 v1" in text
    assert "public context encoded examples: 2/2" in text


def _rich_public_context(base_context: dict[str, object]) -> dict[str, object]:
    context = deepcopy(base_context)
    current = context["current"]  # type: ignore[index]
    location = current["location"]  # type: ignore[index]
    location["ascension"] = _available(20)  # type: ignore[index]
    context["visible_act_boss"] = _available("Hexaghost")
    context["map"] = {
        "visible_map_graph": _available({"nodes": []}),
        "current_node": _available({"x": 1, "y": 2}),
        "immediately_legal_routes": _available(
            [
                {"room_type": "MONSTER"},
                {"room_type": "ELITE"},
                {"room_type": "SHOP"},
            ]
        ),
    }
    context["persistent_resources"] = {
        "schema_id": "public-persistent-resources-v1",
        "fields": {
            "current_hp": _available(60),
            "max_hp": _available(80),
            "gold": _available(123),
            "potion_count": _available(1),
            "potion_capacity": _available(2),
            "deck": _available(
                [
                    {"id": "Strike_R", "type": "ATTACK"},
                    {"id": "Defend_R", "type": "SKILL"},
                    {"id": "Inflame", "type": "POWER"},
                    {"id": "Injury", "type": "CURSE"},
                ]
            ),
            "relics": _available([{"id": "Burning Blood"}]),
            "potion_identities": _available([{"id": "Weak Potion"}]),
            "keys": _available(
                {"blue_key": True, "green_key": False, "red_key": False}
            ),
        },
    }
    context["history"] = [
        {
            "schema_id": "public-run-history-entry-v1",
            "schema_version": 1,
            "history_index": 0,
            "step_index": 0,
            "pre_decision": {
                "screen": _available("BATTLE"),
                "candidate_actions": [],
            },
            "selected_action": {
                "index": 0,
                "candidate": {"kind": "card", "label": "Strike"},
                "identity": {"kind": "card", "label": "Strike"},
            },
            "post_decision": {
                "screen": _available("REWARDS"),
                "location": {"room_type": _available("MONSTER")},
                "result": {"battle_outcome": _available("PLAYER_VICTORY")},
            },
            "resource_change": {
                "current_hp": {"availability": "available", "delta": -4},
                "max_hp": {"availability": "available", "delta": 0},
                "gold": {"availability": "available", "delta": 12},
                "potion_count": {"availability": "available", "delta": -1},
            },
        }
    ]
    context["missing_fields"] = []
    return context


def _available(value: object) -> dict[str, object]:
    return {"availability": "available", "value": value}
