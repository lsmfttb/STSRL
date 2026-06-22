from __future__ import annotations

from copy import deepcopy

import pytest

from sts_combat_rl.sim.contract import (
    SimulatorAction,
    SimulatorCheckpoint,
    SimulatorSnapshot,
)
from sts_combat_rl.sim.native_public_projection import (
    NATIVE_PUBLIC_PROJECTION_EXTERNAL_BASE_COMMIT,
    NATIVE_PUBLIC_PROJECTION_PATCH_ID,
    NATIVE_PUBLIC_PROJECTION_SCHEMA_ID,
    NativePublicProjectionAuditCollector,
    parse_native_public_projection,
)
from sts_combat_rl.sim.lightspeed import LightSpeedAdapter


def _available(value: object, source: str = "native::source") -> dict[str, object]:
    return {"availability": "available", "source": source, "value": value}


def _unavailable(reason: str = "not exposed") -> dict[str, object]:
    return {"availability": "unavailable", "reason": reason}


def _candidate(bits: int = 7) -> dict[str, object]:
    return {
        "scope": "battle",
        "bits": bits,
        "kind": "end_turn",
        "label": "end turn",
        "idx1": 0,
        "idx2": 0,
        "idx3": 0,
    }


def _projection_raw(
    *,
    candidate_bits: int = 7,
    current_hp: int = 80,
    max_hp: int = 80,
    gold: int = 99,
    potion_count: int = 1,
    potion_capacity: int = 3,
    resource_sources: dict[str, str] | None = None,
) -> dict[str, object]:
    sources = resource_sources or {}
    resources = {
        "current_hp": _available(
            current_hp, sources.get("current_hp", "GameContext::curHp")
        ),
        "max_hp": _available(max_hp, sources.get("max_hp", "GameContext::maxHp")),
        "gold": _available(gold, sources.get("gold", "GameContext::gold")),
        "potion_count": _available(
            potion_count, sources.get("potion_count", "GameContext::potionCount")
        ),
        "potion_capacity": _available(
            potion_capacity,
            sources.get("potion_capacity", "GameContext::potionCapacity"),
        ),
        "deck": _unavailable(),
        "relics": _unavailable(),
        "potion_identities": _unavailable(),
        "keys": _unavailable(),
    }
    return {
        "schema_id": NATIVE_PUBLIC_PROJECTION_SCHEMA_ID,
        "external_base_commit": NATIVE_PUBLIC_PROJECTION_EXTERNAL_BASE_COMMIT,
        "patch_identity": NATIVE_PUBLIC_PROJECTION_PATCH_ID,
        "screen_identity": _available("BATTLE", "GameContext::screenState"),
        "visible_act_boss": _unavailable(),
        "visible_map_graph": _unavailable(),
        "current_map_node": _unavailable(),
        "immediately_legal_routes": _unavailable(),
        "persistent_resources": _available(resources, "GameContext"),
        "screen_payload": {
            "availability": "unsupported",
            "reason": "not exposed",
        },
        "candidate_actions": _available(
            [_candidate(candidate_bits)], "StepSimulator::legalActions"
        ),
    }


def _battle_snapshot(
    *,
    current_hp: int = 80,
    max_hp: int = 80,
    potion_count: int = 1,
    potion_capacity: int = 3,
) -> SimulatorSnapshot:
    return SimulatorSnapshot(
        observation=[],
        raw={
            "screen_state": "BATTLE",
            "battle_active": True,
            "battle_player_hp": current_hp,
            "battle_player": {
                "current_hp": current_hp,
                "max_hp": max_hp,
            },
            "battle_potion_count": potion_count,
            "battle_potion_capacity": potion_capacity,
            "cur_hp": 999,
            "max_hp": max_hp,
            "potion_count": 0,
            "potion_capacity": 0,
        },
    )


class FakeProjectionAdapter:
    def __init__(self, *, restored_current_hp: int | None = None) -> None:
        self._raw = _projection_raw()
        self._restored_current_hp = restored_current_hp
        self._was_restored = False

    @property
    def checkpoint_adapter_id(self) -> str:
        return "fake-public-projection"

    @property
    def supports_checkpoint_restore(self) -> bool:
        return True

    def public_projection(self, snapshot: SimulatorSnapshot):  # type: ignore[no-untyped-def]
        del snapshot
        raw = deepcopy(self._raw)
        if self._was_restored and self._restored_current_hp is not None:
            resources = raw["persistent_resources"]["value"]  # type: ignore[index]
            resources["current_hp"]["value"] = self._restored_current_hp  # type: ignore[index]
        return parse_native_public_projection(raw)

    def capture_checkpoint(self, snapshot: SimulatorSnapshot) -> SimulatorCheckpoint:
        del snapshot
        return SimulatorCheckpoint(
            adapter_id=self.checkpoint_adapter_id,
            checkpoint_id="checkpoint-1",
            payload="opaque",
        )

    def restore_checkpoint(self, checkpoint: SimulatorCheckpoint) -> SimulatorSnapshot:
        assert checkpoint.adapter_id == self.checkpoint_adapter_id
        self._was_restored = True
        return SimulatorSnapshot(observation=[], raw={"screen_state": "BATTLE"})


class _ProjectionCharacterClass:
    IRONCLAD = "IRONCLAD"


class _ProjectionStepSimulator:
    def __init__(self, character_class: str, seed: int, ascension: int) -> None:
        self.seed = seed

    def reset(self, character_class: str, seed: int, ascension: int) -> None:
        self.seed = seed

    def snapshot(self) -> dict[str, object]:
        return {"screen_state": "BATTLE", "outcome": "UNDECIDED", "seed": self.seed}

    def observation(self) -> list[int]:
        return [self.seed]

    def public_projection(self) -> dict[str, object]:
        return _projection_raw()


class _ProjectionModule:
    CharacterClass = _ProjectionCharacterClass
    StepSimulator = _ProjectionStepSimulator


def _actions() -> list[SimulatorAction]:
    return [
        SimulatorAction(
            action_id="battle:7",
            label="end turn",
            kind="end_turn",
            raw={"scope": "battle", "bits": 7},
        )
    ]


def test_parser_retains_only_typed_audit_view_and_duplicate_safe_candidates() -> None:
    raw = _projection_raw()
    raw["candidate_actions"]["value"].append(_candidate())  # type: ignore[index]

    projection = parse_native_public_projection(raw)

    assert projection.screen_identity == "BATTLE"
    assert projection.fields["visible_map_graph"].availability == "unavailable"
    assert projection.resource_fields["current_hp"].source == "GameContext::curHp"
    assert projection.resource_values["current_hp"] == 80
    assert [
        identity["occurrence"] for identity in projection.candidate_action_identities()
    ] == [
        0,
        1,
    ]
    assert "current_hp" in projection.canonical_payload
    assert not hasattr(projection, "raw")


def test_parser_rejects_undeclared_or_malformed_raw_fields() -> None:
    raw = _projection_raw()
    del raw["candidate_actions"]

    with pytest.raises(ValueError, match="candidate_actions must be an object"):
        parse_native_public_projection(raw)


def test_parser_keeps_persistent_resource_unavailability_explicit() -> None:
    raw = _projection_raw()
    raw["persistent_resources"] = _unavailable("native resources not exposed")

    projection = parse_native_public_projection(raw)

    assert projection.fields["persistent_resources"].availability == "unavailable"
    assert projection.resource_fields["deck"].availability == "unavailable"
    assert projection.resource_fields["deck"].reason == "native resources not exposed"


def test_lightspeed_adapter_reads_parsed_native_projection_only_from_current_state() -> (
    None
):
    adapter = LightSpeedAdapter(seed=3, ascension=20, module=_ProjectionModule)
    snapshot = adapter.reset(seed=9)

    projection = adapter.public_projection(snapshot)

    assert projection.screen_identity == "BATTLE"
    assert projection.candidate_source == "StepSimulator::legalActions"


def test_audit_records_one_current_screen_and_accepts_native_parity_checkpoint() -> (
    None
):
    adapter = FakeProjectionAdapter()
    adapter._raw = _projection_raw(
        resource_sources={
            "current_hp": "BattleContext::player.curHp",
            "max_hp": "BattleContext::player.maxHp",
            "potion_count": "BattleContext::potionCount",
            "potion_capacity": "BattleContext::potionCapacity",
        }
    )
    collector = NativePublicProjectionAuditCollector(adapter)
    snapshot = _battle_snapshot()

    collector.observe_decision(snapshot, _actions(), seed=5, step_index=2)
    report = collector.finalize(
        requested_episodes=1,
        completed_episodes=1,
        max_steps=10,
    )

    assert report.passed is True
    assert report.decisions_observed == 1
    assert report.screen_counts == {"BATTLE": 1}
    assert report.resource_snapshot_comparisons == 4
    assert report.resource_snapshot_mismatches == 0
    assert report.candidate_parity_passes == 1
    assert report.checkpoint_passes == 1
    assert "SHOP_ROOM" in report.coverage_gaps
    assert report.to_dict()["field_availability_counts"]["candidate_actions"] == {
        "available": 1
    }
    assert report.to_dict()["screen_capability_matrix"]["BATTLE"][
        "candidate_actions"
    ] == {"available": 1}
    assert report.to_dict()["resource_source_counts"]["current_hp"] == {
        "BattleContext::player.curHp": 1
    }
    assert report.to_dict()["field_source_counts"]["candidate_actions"] == {
        "StepSimulator::legalActions": 1
    }


def test_audit_fails_when_projected_battle_resource_is_stale() -> None:
    adapter = FakeProjectionAdapter()
    adapter._raw = _projection_raw(current_hp=68)
    collector = NativePublicProjectionAuditCollector(adapter)

    collector.observe_decision(
        _battle_snapshot(current_hp=62),
        _actions(),
        seed=1,
        step_index=15,
    )
    report = collector.finalize(
        requested_episodes=1,
        completed_episodes=1,
        max_steps=20,
    )

    assert report.passed is False
    assert report.resource_snapshot_mismatches == 1
    assert any(
        "persistent_resources.current_hp mismatch" in problem
        and "battle_player_hp=62" in problem
        for problem in report.problems
    )


def test_audit_fails_on_occurrence_safe_candidate_action_mismatch() -> None:
    adapter = FakeProjectionAdapter()
    adapter._raw = _projection_raw(candidate_bits=8)
    collector = NativePublicProjectionAuditCollector(adapter)

    collector.observe_decision(
        SimulatorSnapshot(observation=[], raw={"screen_state": "BATTLE"}),
        _actions(),
        seed=5,
        step_index=2,
    )
    report = collector.finalize(
        requested_episodes=1,
        completed_episodes=1,
        max_steps=10,
    )

    assert report.passed is False
    assert any(
        "candidate-action parity mismatch" in problem for problem in report.problems
    )


def test_audit_fails_when_checkpoint_changes_raw_projection() -> None:
    adapter = FakeProjectionAdapter(restored_current_hp=79)
    collector = NativePublicProjectionAuditCollector(adapter)

    collector.observe_decision(
        SimulatorSnapshot(observation=[], raw={"screen_state": "BATTLE"}),
        _actions(),
        seed=5,
        step_index=2,
    )
    report = collector.finalize(
        requested_episodes=1,
        completed_episodes=1,
        max_steps=10,
    )

    assert report.passed is False
    assert report.checkpoint_failures == 1
    assert any(
        "checkpoint projection mismatch" in problem for problem in report.problems
    )
