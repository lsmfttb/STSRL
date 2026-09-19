from __future__ import annotations

import json
import sys
from types import ModuleType, SimpleNamespace

import pytest

from sts_combat_rl.commands.t098_public_information_fidelity import (
    T098_NATIVE_AUDIT_SCHEMA_ID,
    T098_PARTICLE_COUNT,
    audit_t098_supported_witness,
    build_t098_report,
    classify_t098,
    generate_t098_report_from_portable_pool,
    main,
    validate_t098_native_visibility_audit,
    validate_t098_report,
)
from sts_combat_rl.sim.t096_public_information_sampler import T096SamplerError


def _monster(*, hidden_intent: bool = False) -> dict[str, object]:
    row: dict[str, object] = {
        "id": 1,
        "last_move_id": 2,
        "public_statuses": [],
        "information_fidelity": "supported",
    }
    if not hidden_intent:
        row.update(
            {
                "attacking": True,
                "intent_category": "ATTACK",
                "current_move": "TEST",
                "move_id": 3,
                "move_base_damage": 6,
                "move_hits": 1,
            }
        )
    return row


def _projection(
    *, draw: str = "hidden", intent: str = "public_exact"
) -> dict[str, object]:
    draw_order: dict[str, object] = {
        "classification": draw,
        "fidelity": "native-current-information-v2",
    }
    if draw == "known_prefix":
        draw_order["known_top_prefix"] = [{"id": 17, "name": "Headbutt"}]
    elif draw == "full_public_exact":
        draw_order["visible_order_from_top"] = [
            {"id": 17, "name": "Headbutt"},
            {"id": 1, "name": "Strike"},
        ]
    return {
        "schema_id": "native-battle-public-information-v2",
        "information_regime": "normal_information",
        "screen_identity": "BATTLE",
        "act": 1,
        "floor_num": 1,
        "encounter_id": "TEST",
        "turn": 1,
        "input_state": "PLAYER_NORMAL",
        "battle_outcome": "UNDECIDED",
        "player": {"current_hp": 80},
        "hand": [],
        "discard_pile": [],
        "exhaust_pile": [],
        "draw_pile_size": 2,
        "monsters": [_monster(hidden_intent=intent == "hidden")],
        "persistent_resources": {
            "deck": [],
            "relics": [],
            "potions": [],
            "gold": 99,
            "blue_key": False,
            "green_key": False,
            "red_key": False,
        },
        "information_fidelity": "supported",
        "draw_knowledge_unsupported_reasons": [],
        "visibility": {
            "draw_order": draw_order,
            "enemy_intent": {
                "classification": intent,
                "fidelity": "native-current-information-v2",
            },
            "information_fidelity": "supported",
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


class _Adapter:
    def __init__(self, projection: dict[str, object], *, diverse: bool = True) -> None:
        self.projection = projection
        self.diverse = diverse

    def t096_public_information_projection(self, snapshot):  # type: ignore[no-untyped-def]
        return self.projection

    def sample_hidden_future_particles(  # type: ignore[no-untyped-def]
        self, snapshot, *, sampler_seed, particle_start, particle_count
    ):
        assert particle_count == T098_PARTICLE_COUNT
        assert particle_start == 0
        return [
            {
                "particle_index": index,
                "sampler_seed": sampler_seed + index,
                "public_information_projection": self.projection,
                "hidden_future_fingerprint": (
                    f"hidden-{index}" if self.diverse else "same"
                ),
                "next_draw_card_id": 1 + index % 2,
            }
            for index in range(particle_count)
        ]


def _native_audit() -> dict[str, object]:
    return {
        "schema_id": T098_NATIVE_AUDIT_SCHEMA_ID,
        "headbutt_known_prefix": True,
        "native_snapshot_contract": True,
        "checkpoint_preserves_known_prefix": True,
        "sampler_preserves_known_prefix": True,
        "sampler_public_information_invariant": True,
        "sampler_private_remainder_diverse": True,
        "havoc_consumes_top_preserves_suffix": True,
        "rebound_establishes_known_top": True,
        "forethought_known_position_preserved": True,
        "subset_reveal_fails_closed": True,
        "subset_reveal_shuffle_stays_unsupported": True,
        "subset_reveal_sampler_fails_closed": True,
        "draw_knowledge_reason_typed": True,
        "frozen_eye_full_order": True,
        "frozen_eye_sampler_preserves_order": True,
        "runic_dome_hides_current_intent": True,
        "runic_dome_preserves_previous_move": True,
        "runic_dome_sanitizes_roll_misc": True,
        "runic_dome_hidden_counter_timing_invariant": True,
        "runic_dome_mixed_counter_sampler_fails_closed": True,
        "runic_dome_hides_louse_misc": True,
        "private_hidden_state_projection_invariant": True,
        "runic_dome_looter_public_counter_preserved": True,
        "runic_dome_looter_misc_fails_closed": True,
        "private_hidden_misc_sampler_supported": True,
        "runic_dome_retains_visible_power": True,
        "runic_dome_direct_misc_fail_closed": True,
    }


def test_supported_known_prefix_witness_calls_projection_and_n32_sampler() -> None:
    row = audit_t098_supported_witness(
        _Adapter(_projection(draw="known_prefix")),
        SimpleNamespace(),
        family="supported_draw_knowledge",
        witness_provenance={"source_checkpoint_id": "test"},
        sampler_seed=17,
        expected_draw_classification="known_prefix",
        expected_intent_classification="public_exact",
        diversity_expected=True,
    )

    assert row["particle_count"] == 32
    assert row["public_projection_parity_pass_count"] == 32
    assert row["ordered_public_legal_action_parity_pass_count"] == 32
    assert row["distinct_hidden_future_fingerprint_count"] == 32
    assert row["preserved_public_facts"]["known_top_prefix"][0]["id"] == 17


def test_frozen_eye_witness_preserves_order_without_diversity_claim() -> None:
    row = audit_t098_supported_witness(
        _Adapter(_projection(draw="full_public_exact"), diverse=False),
        SimpleNamespace(),
        family="frozen_eye_exact_order",
        witness_provenance={"source_checkpoint_id": "frozen"},
        sampler_seed=18,
        expected_draw_classification="full_public_exact",
        expected_intent_classification="public_exact",
        diversity_expected=False,
    )

    assert row["hidden_diversity_expected"] is False
    assert row["hidden_diversity_pass"] is None
    assert row["distinct_hidden_future_fingerprint_count"] == 1


def test_runic_dome_witness_requires_history_and_omits_current_intent() -> None:
    row = audit_t098_supported_witness(
        _Adapter(_projection(intent="hidden")),
        SimpleNamespace(),
        family="runic_dome_hidden_intent",
        witness_provenance={"source_checkpoint_id": "dome"},
        sampler_seed=19,
        expected_draw_classification="hidden",
        expected_intent_classification="hidden",
        diversity_expected=True,
    )

    assert row["preserved_public_facts"]["monster_last_move_ids"] == [2]
    assert row["enemy_intent_classification"] == "hidden"


def test_native_visibility_audit_rejects_missing_or_non_boolean_fields() -> None:
    audit = _native_audit()
    audit.pop("frozen_eye_full_order")
    with pytest.raises(T096SamplerError, match="keys mismatch"):
        validate_t098_native_visibility_audit(audit)

    audit = _native_audit()
    audit["frozen_eye_full_order"] = "yes"
    with pytest.raises(T096SamplerError, match="not boolean"):
        validate_t098_native_visibility_audit(audit)


def test_report_reaches_ready_only_with_all_four_and_fail_closed() -> None:
    witnesses = [
        {"family": "ordinary_hidden_draw_visible_intent", "status": "PASS"},
        {"family": "supported_draw_knowledge", "status": "PASS"},
        {"family": "frozen_eye_exact_order", "status": "PASS"},
        {"family": "runic_dome_hidden_intent", "status": "PASS"},
    ]
    report = build_t098_report(
        implementation_head="evidence-head",
        native_identity={
            "repository": "lsmfttb/sts_lightspeed",
            "ref": "refs/heads/stsrl/main",
            "commit": "d309170198e21e57041a84dcfdbc255cdda4052e",
        },
        native_audit=_native_audit(),
        witnesses=witnesses,
        input_references={},
    )

    assert (
        report["terminal_classification"]
        == "PUBLIC_HIDDEN_FUTURE_SAMPLER_FIDELITY_READY"
    )
    assert report["private_field_leak_detected"] is False
    unsupported = report["intentional_unsupported_witness"]
    assert unsupported["witness_provenance"]["native_api"] == (
        "StepSimulator.t096_visibility_audit"
    )
    assert unsupported["witness_provenance"]["witness_kind"] == (
        "native_owned_actual_witness"
    )
    assert (
        unsupported["native_audit_evidence"][
            "runic_dome_mixed_counter_sampler_fails_closed"
        ]
        is True
    )
    assert unsupported["sampler_evidence"] == {
        "rejected": True,
        "accepted_particle_count": 0,
    }
    assert validate_t098_report(report) == report
    assert classify_t098(witnesses[:3], report["intentional_unsupported_witness"]) == (
        "INTENT_VISIBILITY_FIDELITY_INSUFFICIENT"
    )


def test_generation_entrypoint_wraps_explicit_pool_and_report_workflow(
    tmp_path, monkeypatch
) -> None:
    pool = tmp_path / "pool.jsonl"
    pool.write_text("{}\n", encoding="utf-8")
    output = tmp_path / "report.json"
    records = {index: object() for index in (0, 73, 475, 828)}
    observed: dict[str, object] = {}

    def fake_load(stream, *, record_indices):
        observed["indices"] = record_indices
        return records

    def fake_run(**kwargs):
        observed["run"] = kwargs
        return {"schema_id": "t098-public-information-fidelity-reentry-v1"}

    def fake_write(report, path):
        observed["write"] = (report, path)
        return {}

    monkeypatch.setattr(
        "sts_combat_rl.commands.t098_public_information_fidelity.load_portable_battle_start_records",
        fake_load,
    )
    monkeypatch.setattr(
        "sts_combat_rl.commands.t098_public_information_fidelity.run_t098_fidelity_reentry",
        fake_run,
    )
    monkeypatch.setattr(
        "sts_combat_rl.commands.t098_public_information_fidelity.write_t098_report",
        fake_write,
    )
    report = generate_t098_report_from_portable_pool(
        portable_pool_path=pool,
        output_path=output,
        record_indices={
            "ordinary": 0,
            "headbutt": 73,
            "frozen_eye": 828,
            "runic_dome": 475,
        },
        adapter_factory=lambda: object(),
        implementation_head="a" * 40,
    )

    assert report["schema_id"] == "t098-public-information-fidelity-reentry-v1"
    assert observed["indices"] == [0, 73, 828, 475]
    assert observed["write"][1] == output


def test_generation_cli_reports_output_path_without_input_report(
    monkeypatch, tmp_path, capsys
) -> None:
    fake_native = ModuleType("sts_combat_rl.sim.lightspeed")
    fake_native.LightSpeedAdapter = object  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "sts_combat_rl.sim.lightspeed", fake_native)
    report = {
        "schema_id": "t098-public-information-fidelity-reentry-v1",
        "native_identity": {"commit": "d309170198e21e57041a84dcfdbc255cdda4052e"},
        "terminal_classification": "PUBLIC_HIDDEN_FUTURE_SAMPLER_FIDELITY_READY",
    }
    monkeypatch.setattr(
        "sts_combat_rl.commands.t098_public_information_fidelity.generate_t098_report_from_portable_pool",
        lambda **kwargs: report,
    )
    output = tmp_path / "generated.json"
    assert (
        main(
            [
                "--portable-pool",
                str(tmp_path / "pool.jsonl"),
                "--output-report",
                str(output),
                "--implementation-head",
                "a" * 40,
                "--ordinary-record-index",
                "0",
                "--headbutt-record-index",
                "73",
                "--frozen-eye-record-index",
                "828",
                "--runic-dome-record-index",
                "475",
            ]
        )
        == 0
    )
    assert json.loads(capsys.readouterr().out)["path"] == str(output.resolve())
