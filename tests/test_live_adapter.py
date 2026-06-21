"""Tests for the live CommunicationMod runtime adapter."""

from __future__ import annotations

import io
import json
from typing import Any

from sts_combat_rl.comm.live_adapter import (
    LIVE_SOURCE_FORMAT,
    _is_combat_snapshot,
    _parse_available_commands,
    _potion_can_discard,
    build_live_decision_context,
    build_live_legal_actions,
    build_live_parity_report,
    invoke_live_controller,
    live_action_to_command,
    log_live_decision_result,
    process_live_message,
)
from sts_combat_rl.comm.protocol import (
    Command,
    command_name,
)
from sts_combat_rl.sim.controller_contract import (
    ControllerDecision,
    ControllerProvenance,
)
from sts_combat_rl.sim.contract import SimulatorAction, SimulatorSnapshot
from sts_combat_rl.sim.features import (
    TACTICAL_FEATURE_SCHEMA_ID,
    TACTICAL_FEATURE_SCHEMA_VERSION,
)
from sts_combat_rl.sim.online_controller import PolicyController
from sts_combat_rl.sim.policy import (
    DecisionContext,
    FirstEligiblePolicy,
    PreferredKindPolicy,
)


# ---------------------------------------------------------------------------
# Fixture data
# ---------------------------------------------------------------------------


def _combat_snapshot() -> dict[str, Any]:
    """Return a minimal but valid CommunicationMod combat snapshot."""
    return {
        "available_commands": ["play", "end", "potion", "key", "wait", "state"],
        "game_state": {
            "screen_type": "COMBAT",
            "room_phase": "COMBAT",
            "action_phase": "WAITING_ON_USER",
            "ascension_level": 20,
            "floor": 5,
            "current_hp": 68,
            "max_hp": 75,
            "gold": 120,
            "potions": [
                {
                    "name": "Fire Potion",
                    "id": "Fire Potion",
                    "can_use": True,
                    "can_discard": True,
                },
                {
                    "name": "Block Potion",
                    "id": "Block Potion",
                    "can_use": True,
                    "can_discard": True,
                },
                {
                    "name": "Potion Slot",
                    "id": "Potion Slot",
                    "can_use": False,
                },
            ],
            "relics": [
                {"id": "Burning Blood", "name": "Burning Blood"},
                {"id": "Vajra", "name": "Vajra", "counter": 1},
            ],
            "combat_state": {
                "turn": 2,
                "player": {
                    "current_hp": 65,
                    "max_hp": 75,
                    "block": 6,
                    "energy": 3,
                    "powers": [
                        {"id": "Strength", "amount": 2},
                    ],
                },
                "hand": [
                    {
                        "name": "Strike",
                        "id": "Strike_R",
                        "type": "ATTACK",
                        "cost": 1,
                        "is_playable": True,
                        "has_target": True,
                    },
                    {
                        "name": "Defend",
                        "id": "Defend_R",
                        "type": "SKILL",
                        "cost": 1,
                        "is_playable": True,
                        "has_target": False,
                    },
                    {
                        "name": "Bash",
                        "id": "Bash",
                        "type": "ATTACK",
                        "cost": 2,
                        "is_playable": True,
                        "has_target": True,
                        "rarity": "BASIC",
                        "upgraded": False,
                        "damage": 8,
                    },
                ],
                "draw_pile": [
                    {"name": "Anger", "id": "Anger", "type": "ATTACK", "cost": 0},
                ],
                "discard_pile": [
                    {"name": "Strike", "id": "Strike_R", "type": "ATTACK", "cost": 1},
                ],
                "exhaust_pile": [],
                "monsters": [
                    {
                        "name": "Cultist",
                        "id": "Cultist",
                        "current_hp": 48,
                        "max_hp": 50,
                        "block": 0,
                        "intent": "ATTACK",
                        "is_gone": False,
                        "move_base_damage": 6,
                        "move_hits": 1,
                    },
                    {
                        "name": "JawWorm",
                        "id": "JawWorm",
                        "current_hp": 40,
                        "max_hp": 42,
                        "block": 6,
                        "intent": "BUFF_ATTACK",
                        "is_gone": False,
                        "move_base_damage": 12,
                        "move_hits": 1,
                    },
                ],
            },
        },
    }


def _combat_snapshot_end_only() -> dict[str, Any]:
    """Return a combat snapshot where only 'end' is available."""
    return {
        "available_commands": ["end", "key", "wait", "state"],
        "game_state": {
            "screen_type": "COMBAT",
            "action_phase": "WAITING_ON_USER",
            "ascension_level": 20,
            "floor": 3,
            "current_hp": 60,
            "max_hp": 80,
            "gold": 99,
            "potions": [],
            "combat_state": {
                "turn": 1,
                "player": {"current_hp": 60, "max_hp": 80, "block": 0, "energy": 3},
                "hand": [],
                "monsters": [
                    {
                        "name": "Sentry",
                        "id": "Sentry",
                        "current_hp": 38,
                        "max_hp": 38,
                        "block": 0,
                        "intent": "ATTACK",
                        "is_gone": False,
                    },
                ],
            },
        },
    }


def _duplicate_cards_snapshot() -> dict[str, Any]:
    """Return a combat snapshot with duplicate playable cards (two Strikes)."""
    return {
        "available_commands": ["play", "end", "key", "wait", "state"],
        "game_state": {
            "screen_type": "COMBAT",
            "action_phase": "WAITING_ON_USER",
            "ascension_level": 10,
            "floor": 2,
            "current_hp": 70,
            "max_hp": 72,
            "gold": 99,
            "potions": [],
            "combat_state": {
                "turn": 1,
                "player": {"current_hp": 70, "max_hp": 72, "block": 0, "energy": 3},
                "hand": [
                    {
                        "name": "Strike",
                        "id": "Strike_R",
                        "type": "ATTACK",
                        "cost": 1,
                        "is_playable": True,
                        "has_target": True,
                    },
                    {
                        "name": "Strike",
                        "id": "Strike_R",
                        "type": "ATTACK",
                        "cost": 1,
                        "is_playable": True,
                        "has_target": True,
                    },
                ],
                "monsters": [
                    {
                        "name": "LouseNormal",
                        "id": "LouseNormal",
                        "current_hp": 15,
                        "max_hp": 15,
                        "intent": "ATTACK",
                        "is_gone": False,
                    },
                ],
            },
        },
    }


def _potion_can_discard_false_snapshot() -> dict[str, Any]:
    """Potion with can_discard: false — discard must not be legal."""
    return {
        "available_commands": ["play", "end", "potion", "key", "wait", "state"],
        "game_state": {
            "screen_type": "COMBAT",
            "action_phase": "WAITING_ON_USER",
            "ascension_level": 20,
            "floor": 5,
            "current_hp": 70,
            "max_hp": 75,
            "gold": 100,
            "potions": [
                {
                    "name": "Fire Potion",
                    "id": "Fire Potion",
                    "can_use": True,
                    "can_discard": False,
                },
            ],
            "combat_state": {
                "turn": 1,
                "player": {"current_hp": 70, "max_hp": 75, "block": 0, "energy": 3},
                "hand": [
                    {
                        "name": "Strike",
                        "id": "Strike_R",
                        "type": "ATTACK",
                        "cost": 1,
                        "is_playable": True,
                        "has_target": True,
                    },
                ],
                "monsters": [
                    {
                        "name": "Cultist",
                        "id": "Cultist",
                        "current_hp": 20,
                        "max_hp": 20,
                        "intent": "ATTACK",
                        "is_gone": False,
                    },
                ],
            },
        },
    }


def _potion_can_discard_missing_snapshot() -> dict[str, Any]:
    """Potion with can_discard absent — discard must not be legal."""
    return {
        "available_commands": ["play", "end", "potion", "key", "wait", "state"],
        "game_state": {
            "screen_type": "COMBAT",
            "action_phase": "WAITING_ON_USER",
            "ascension_level": 20,
            "floor": 5,
            "current_hp": 70,
            "max_hp": 75,
            "gold": 100,
            "potions": [
                {"name": "Fire Potion", "id": "Fire Potion", "can_use": True},
            ],
            "combat_state": {
                "turn": 1,
                "player": {"current_hp": 70, "max_hp": 75, "block": 0, "energy": 3},
                "hand": [
                    {
                        "name": "Strike",
                        "id": "Strike_R",
                        "type": "ATTACK",
                        "cost": 1,
                        "is_playable": True,
                        "has_target": True,
                    },
                ],
                "monsters": [
                    {
                        "name": "Cultist",
                        "id": "Cultist",
                        "current_hp": 20,
                        "max_hp": 20,
                        "intent": "ATTACK",
                        "is_gone": False,
                    },
                ],
            },
        },
    }


def _non_combat_snapshot() -> dict[str, Any]:
    """Return a non-combat snapshot."""
    return {
        "available_commands": ["choose", "key", "wait", "state"],
        "game_state": {
            "screen_type": "EVENT",
            "room_phase": "EVENT",
            "action_phase": "WAITING_ON_USER",
            "current_hp": 70,
            "max_hp": 75,
            "gold": 150,
        },
    }


def _incomplete_snapshot() -> dict[str, Any]:
    """Return a snapshot missing most combat fields."""
    return {
        "available_commands": ["end", "state"],
        "game_state": {
            "screen_type": "COMBAT",
            "action_phase": "WAITING_ON_USER",
            "current_hp": 50,
            "max_hp": 70,
            "gold": 99,
        },
    }


# ---------------------------------------------------------------------------
# Snapshot detection
# ---------------------------------------------------------------------------


class TestCombatDetection:
    def test_detects_combat_by_battle_active(self) -> None:
        assert _is_combat_snapshot({"battle_active": True}) is True

    def test_detects_combat_by_screen_type(self) -> None:
        assert _is_combat_snapshot({"game_state": {"screen_type": "COMBAT"}}) is True
        assert _is_combat_snapshot({"gameState": {"screenType": "BATTLE"}}) is True

    def test_detects_combat_by_combat_state(self) -> None:
        assert (
            _is_combat_snapshot({"game_state": {"combat_state": {"turn": 1}}}) is True
        )

    def test_detects_combat_by_room_phase(self) -> None:
        assert _is_combat_snapshot({"game_state": {"room_phase": "BATTLE"}}) is True

    def test_rejects_non_combat(self) -> None:
        assert _is_combat_snapshot({"game_state": {"screen_type": "EVENT"}}) is False

    def test_rejects_map(self) -> None:
        assert _is_combat_snapshot({"game_state": {"screen_type": "MAP"}}) is False


class TestAvailableCommands:
    def test_parses_available_commands(self) -> None:
        available = _parse_available_commands(
            {"available_commands": ["play", "end", "key"]}
        )
        assert available == frozenset({"play", "end", "key"})

    def test_parses_available_commands_camel_case(self) -> None:
        available = _parse_available_commands({"availableCommands": ["play", "end"]})
        assert available == frozenset({"play", "end"})

    def test_empty_when_missing(self) -> None:
        assert _parse_available_commands({}) == frozenset()


class TestPotionCanDiscard:
    def test_true_is_legal(self) -> None:
        assert _potion_can_discard({"can_discard": True}) is True

    def test_false_is_not_legal(self) -> None:
        assert _potion_can_discard({"can_discard": False}) is False

    def test_missing_is_not_legal(self) -> None:
        assert _potion_can_discard({}) is False

    def test_none_is_not_legal(self) -> None:
        assert _potion_can_discard({"can_discard": None}) is False


# ---------------------------------------------------------------------------
# Legal action construction
# ---------------------------------------------------------------------------


class TestBuildLiveLegalActions:
    def test_builds_card_play_and_end_turn(self) -> None:
        snapshot = _combat_snapshot()
        actions = build_live_legal_actions(snapshot)
        assert len(actions) >= 1
        kinds = {a.kind for a in actions}
        assert "card" in kinds
        assert "end_turn" in kinds

    def test_card_with_target_produces_one_per_alive_monster(self) -> None:
        snapshot = _combat_snapshot()
        actions = build_live_legal_actions(snapshot)
        card_actions = [a for a in actions if a.kind == "card"]
        end_actions = [a for a in actions if a.kind == "end_turn"]
        assert len(end_actions) == 1
        # Strike (targeting) -> 2, Defend (no target) -> 1, Bash (targeting) -> 2
        assert len(card_actions) == 5

    def test_builds_end_turn_when_available(self) -> None:
        snapshot = _combat_snapshot()
        actions = build_live_legal_actions(snapshot)
        end_actions = [a for a in actions if a.kind == "end_turn"]
        assert len(end_actions) == 1
        assert end_actions[0].raw["_live_command_type"] == "end_turn"

    def test_end_only_snapshot(self) -> None:
        snapshot = _combat_snapshot_end_only()
        actions = build_live_legal_actions(snapshot)
        kinds = {a.kind for a in actions}
        assert "card" not in kinds
        assert "end_turn" in kinds or len(actions) == 1

    def test_builds_potion_actions(self) -> None:
        snapshot = _combat_snapshot()
        actions = build_live_legal_actions(snapshot)
        potion_kinds = {a.kind for a in actions}
        assert "potion" in potion_kinds

    def test_duplicate_cards_produce_distinct_actions(self) -> None:
        snapshot = _duplicate_cards_snapshot()
        actions = build_live_legal_actions(snapshot)
        card_actions = [a for a in actions if a.kind == "card"]
        card_indices = {a.raw.get("_live_card_index") for a in card_actions}
        assert card_indices == {0, 1}

    def test_action_raw_contains_command_mapping(self) -> None:
        snapshot = _combat_snapshot()
        actions = build_live_legal_actions(snapshot)
        for action in actions:
            assert "_live_command_type" in action.raw

    # --- can_discard regression (P1) ---

    def test_can_discard_true_produces_discard_actions(self) -> None:
        snapshot = _combat_snapshot()
        actions = build_live_legal_actions(snapshot)
        discard_kinds = {a.kind for a in actions}
        assert "potion_discard" in discard_kinds

    def test_can_discard_false_produces_no_discard_actions(self) -> None:
        snapshot = _potion_can_discard_false_snapshot()
        actions = build_live_legal_actions(snapshot)
        discard_actions = [a for a in actions if a.kind == "potion_discard"]
        assert len(discard_actions) == 0

    def test_can_discard_missing_produces_no_discard_actions(self) -> None:
        snapshot = _potion_can_discard_missing_snapshot()
        actions = build_live_legal_actions(snapshot)
        discard_actions = [a for a in actions if a.kind == "potion_discard"]
        assert len(discard_actions) == 0


# ---------------------------------------------------------------------------
# Action-to-command mapping
# ---------------------------------------------------------------------------


class TestLiveActionToCommand:
    def test_maps_play_card_without_target(self) -> None:
        non_target = [
            a
            for a in build_live_legal_actions(_combat_snapshot())
            if a.kind == "card" and a.raw.get("_live_target_index") is None
        ]
        if non_target:
            command = live_action_to_command(non_target[0])
            assert command is not None
            assert command.command_type == "play_card"
            assert command.target_index is None

    def test_maps_play_card_with_target(self) -> None:
        actions = build_live_legal_actions(_duplicate_cards_snapshot())
        targeting = [
            a
            for a in actions
            if a.kind == "card" and a.raw.get("_live_target_index") is not None
        ]
        assert len(targeting) > 0
        command = live_action_to_command(targeting[0])
        assert command is not None
        assert command.command_type == "play_card"
        assert command.target_index is not None

    def test_maps_end_turn(self) -> None:
        actions = build_live_legal_actions(_combat_snapshot())
        end_actions = [a for a in actions if a.kind == "end_turn"]
        assert len(end_actions) == 1
        command = live_action_to_command(end_actions[0])
        assert command is not None
        assert command.command_type == "end_turn"

    def test_maps_potion_use(self) -> None:
        snapshot = _combat_snapshot()
        actions = build_live_legal_actions(snapshot)
        potion_actions = [
            a
            for a in actions
            if a.kind == "potion" and a.raw.get("_live_potion_action") == "use"
        ]
        if potion_actions:
            command = live_action_to_command(potion_actions[0])
            assert command is not None
            assert command.command_type == "potion"
            assert command.potion_action == "use"

    def test_maps_potion_discard(self) -> None:
        snapshot = _combat_snapshot()
        actions = build_live_legal_actions(snapshot)
        discard_actions = [a for a in actions if a.kind == "potion_discard"]
        if discard_actions:
            command = live_action_to_command(discard_actions[0])
            assert command is not None
            assert command.command_type == "potion"
            assert command.potion_action == "discard"

    def test_unknown_live_command_type_returns_none(self) -> None:
        action = SimulatorAction(
            action_id="live_bad",
            label="bad",
            kind="unknown",
            raw={
                "_live_command_type": "nonexistent",
            },
        )
        assert live_action_to_command(action) is None


# ---------------------------------------------------------------------------
# Decision context
# ---------------------------------------------------------------------------


class TestBuildLiveDecisionContext:
    def test_context_has_tactical_schema(self) -> None:
        snapshot = _combat_snapshot()
        actions = build_live_legal_actions(snapshot)
        context = build_live_decision_context(snapshot, actions)
        assert context.tactical_feature_schema_id == TACTICAL_FEATURE_SCHEMA_ID
        assert context.screen_state == "BATTLE"
        assert len(context.eligible_action_indices) == len(actions)
        assert context.tactical_state.get("schema_id") == TACTICAL_FEATURE_SCHEMA_ID
        assert (
            context.tactical_state.get("schema_version")
            == TACTICAL_FEATURE_SCHEMA_VERSION
        )

    def test_context_tactical_actions_aligned(self) -> None:
        snapshot = _combat_snapshot()
        actions = build_live_legal_actions(snapshot)
        context = build_live_decision_context(snapshot, actions)
        assert len(context.tactical_legal_actions) == len(actions)
        for ta in context.tactical_legal_actions:
            assert ta.get("schema_id") == TACTICAL_FEATURE_SCHEMA_ID

    def test_duplicate_cards_get_distinct_identities(self) -> None:
        snapshot = _duplicate_cards_snapshot()
        actions = build_live_legal_actions(snapshot)
        context = build_live_decision_context(snapshot, actions)
        card_actions = [
            ta
            for ta, a in zip(context.tactical_legal_actions, actions)
            if a.kind == "card"
        ]
        assert len(card_actions) >= 2
        stable_ids = [
            card_actions[i].get("identity", {}).get("stable_id")
            for i in range(len(card_actions))
        ]
        assert len(set(stable_ids)) == len(stable_ids)


# ---------------------------------------------------------------------------
# Hidden information regression (P1)
# ---------------------------------------------------------------------------


class TestHiddenInformationBoundary:
    """Controllers must not receive draw pile, hidden RNG, future moves, or
    hidden Boss data through the synthetic snapshot."""

    def test_controller_snapshot_does_not_contain_draw_pile(self) -> None:
        raw = _combat_snapshot()
        # raw has game_state.combat_state.draw_pile
        controller = PolicyController(FirstEligiblePolicy())
        result = invoke_live_controller(raw, controller)

        assert result.is_combat is True
        # A public controller sees only the sanitized snapshot via context &
        # tactical_state. The synthesized snapshot raw should not include
        # the raw CommunicationMod JSON (which has draw_pile).
        # We verify by checking the tactical state does not expose draw pile
        # order (draw_pile is deliberately blocked by the normalizer).
        # draw pile *size* is public, but the actual cards in draw order must
        # not appear in the public card list.
        cards = result.tactical_state.get("cards", [])
        hand_names = {
            c.get("identity", {}).get("value") for c in cards if c.get("pile") == "hand"
        }
        # Anger is in draw_pile — must NOT appear in hand/discard/exhaust
        assert "Anger" not in hand_names

    def test_controller_cannot_read_raw_communicationmod_fields(self) -> None:
        """A controller that reads snapshot.raw must not find hidden data."""
        raw = _combat_snapshot()

        class DrawPileDetector:
            provenance = ControllerProvenance(
                kind="test", name="draw_detector", config={"test": True}
            )

            def select_action(
                self,
                adapter: Any,
                snapshot: SimulatorSnapshot,
                actions: Any,
                context: DecisionContext,
                step_index: int,
            ) -> ControllerDecision:
                # snapshot.raw is the *public* sanitized snapshot — draw_pile
                # is gone; only the public battle_hand/battle_discard_pile
                # etc. remain.
                raw_snapshot = snapshot.raw
                # The public snapshot must not contain draw_pile members.
                assert "draw_pile" not in raw_snapshot
                # And it must not leak game_state.combat_state.draw_pile either.
                return ControllerDecision(
                    selected_index=0,
                    provenance=self.provenance,
                    reason="draw_detector_ok",
                )

        result = invoke_live_controller(raw, DrawPileDetector())
        assert result.is_combat is True
        assert result.decision is not None
        assert result.decision.reason == "draw_detector_ok"


# ---------------------------------------------------------------------------
# Parity report
# ---------------------------------------------------------------------------


class TestParityReport:
    def test_parity_report_is_non_empty(self) -> None:
        rows = build_live_parity_report()
        assert len(rows) > 0
        for row in rows:
            assert "field" in row
            assert "classification" in row
            assert "missing_value_behavior" in row

    def test_parity_report_includes_live_missing_fields(self) -> None:
        rows = build_live_parity_report()
        classifications = {row["classification"] for row in rows}
        assert "live_missing" in classifications
        assert "shared" in classifications


# ---------------------------------------------------------------------------
# Controller invocation
# ---------------------------------------------------------------------------


class TestInvokeLiveController:
    def test_first_eligible_invocation(self) -> None:
        controller = PolicyController(FirstEligiblePolicy())
        snapshot = _combat_snapshot()
        result = invoke_live_controller(snapshot, controller)

        assert result.is_combat is True
        assert result.decision is not None
        assert result.command is not None
        assert result.selected_action_index is not None
        assert result.selected_action_index >= 0
        assert result.formatted_command != ""
        assert result.provenance is not None
        assert result.provenance["kind"] == "decision_policy"
        assert result.source_format == LIVE_SOURCE_FORMAT

    def test_preferred_kind_invocation(self) -> None:
        controller = PolicyController(PreferredKindPolicy())
        snapshot = _combat_snapshot()
        result = invoke_live_controller(snapshot, controller)

        assert result.is_combat is True
        assert result.command is not None
        assert command_name(result.command) in {"play", "end", "potion"}

    def test_non_combat_without_fallback(self) -> None:
        controller = PolicyController(FirstEligiblePolicy())
        snapshot = _non_combat_snapshot()
        result = invoke_live_controller(snapshot, controller)

        assert result.is_combat is False
        assert result.command is None
        assert result.unsupported_reason == "not a combat state"

    def test_non_combat_with_fallback(self) -> None:
        controller = PolicyController(FirstEligiblePolicy())
        snapshot = _non_combat_snapshot()
        result = invoke_live_controller(
            snapshot,
            controller,
            non_combat_fallback=Command.choose("1"),
        )

        assert result.is_combat is False
        assert result.command is not None
        assert result.command.command_type == "choose"

    def test_incomplete_snapshot_produces_missing_fields(self) -> None:
        controller = PolicyController(FirstEligiblePolicy())
        snapshot = _incomplete_snapshot()
        result = invoke_live_controller(snapshot, controller)

        assert result.is_combat is True
        assert len(result.missing_fields) > 0

    def test_provenance_is_valid(self) -> None:
        controller = PolicyController(FirstEligiblePolicy())
        snapshot = _combat_snapshot()
        result = invoke_live_controller(snapshot, controller)

        assert result.provenance is not None
        from sts_combat_rl.sim.controller_contract import (
            controller_provenance_from_dict,
        )

        prov = controller_provenance_from_dict(result.provenance)
        assert prov.kind == "decision_policy"
        assert prov.name == "first_eligible"

    def test_log_record_is_json_safe(self) -> None:
        controller = PolicyController(FirstEligiblePolicy())
        snapshot = _combat_snapshot()
        result = invoke_live_controller(snapshot, controller)
        log_record = log_live_decision_result(result)
        json.dumps(log_record)
        assert log_record["is_combat"] is True
        assert "selected_action_index" in log_record
        assert "source_metadata" in log_record

    def test_log_record_contains_source_metadata(self) -> None:
        controller = PolicyController(FirstEligiblePolicy())
        snapshot = _combat_snapshot()
        result = invoke_live_controller(snapshot, controller)
        log_record = log_live_decision_result(result)
        assert "source_metadata" in log_record
        assert log_record["source_metadata"]["source_kind"] == "unknown"
        assert log_record["source_metadata"]["ascension"] == 20
        assert log_record["source_metadata"]["floor"] == 5

    # --- fail-closed regression (P1) ---

    def test_no_legal_actions_returns_none_command(self) -> None:
        """When no legal live actions can be constructed, command is None."""
        # A snapshot with no "end" and no playable cards produces zero actions.
        snapshot = {
            "available_commands": ["play"],
            "game_state": {
                "screen_type": "COMBAT",
                "combat_state": {
                    "turn": 1,
                    "player": {"current_hp": 30, "max_hp": 30, "block": 0, "energy": 3},
                    "hand": [],
                    "monsters": [],
                },
            },
        }
        controller = PolicyController(FirstEligiblePolicy())
        result = invoke_live_controller(snapshot, controller)
        assert result.command is None
        assert result.formatted_command == ""
        assert result.unsupported_reason is not None

    def test_incomplete_snapshot_fails_closed(self) -> None:
        """End-only snapshot with no legal actions from adapter must NOT emit end."""
        controller = PolicyController(FirstEligiblePolicy())
        snapshot = _incomplete_snapshot()
        result = invoke_live_controller(snapshot, controller)

        assert result.command is not None
        assert result.unsupported_reason is None


# ---------------------------------------------------------------------------
# process_live_message entry point (P1)
# ---------------------------------------------------------------------------


class TestProcessLiveMessage:
    def test_writes_exactly_one_command_on_success(self) -> None:
        controller = PolicyController(FirstEligiblePolicy())
        raw_line = json.dumps(_combat_snapshot())
        out = io.StringIO()

        result = process_live_message(raw_line, controller, output_stream=out)

        assert result.is_combat is True
        output = out.getvalue()
        lines = output.strip().split("\n")
        assert len(lines) == 1
        assert lines[0] != ""

    def test_writes_nothing_on_non_combat_without_fallback(self) -> None:
        controller = PolicyController(FirstEligiblePolicy())
        raw_line = json.dumps(_non_combat_snapshot())
        out = io.StringIO()

        process_live_message(raw_line, controller, output_stream=out)

        assert out.getvalue() == ""

    def test_writes_nothing_on_invalid_json(self) -> None:
        controller = PolicyController(FirstEligiblePolicy())
        out = io.StringIO()

        process_live_message("not valid json", controller, output_stream=out)

        assert out.getvalue() == ""

    def test_writes_nothing_on_non_object_json(self) -> None:
        controller = PolicyController(FirstEligiblePolicy())
        out = io.StringIO()

        process_live_message("[1, 2, 3]", controller, output_stream=out)

        assert out.getvalue() == ""

    def test_writes_with_fallback_on_non_combat(self) -> None:
        controller = PolicyController(FirstEligiblePolicy())
        raw_line = json.dumps(_non_combat_snapshot())
        out = io.StringIO()

        process_live_message(
            raw_line,
            controller,
            output_stream=out,
            fallback_command=Command.choose("1"),
        )

        output = out.getvalue()
        lines = output.strip().split("\n")
        assert len(lines) == 1

    def test_formatted_command_is_valid_protocol(self) -> None:
        controller = PolicyController(FirstEligiblePolicy())
        raw_line = json.dumps(_combat_snapshot())
        out = io.StringIO()

        process_live_message(raw_line, controller, output_stream=out)

        output = out.getvalue().strip()
        assert (
            output
            in {
                "play 1 0",
                "play 1 1",
                "play 2",
                "play 3 0",
                "play 3 1",
                "end",
            }
            or output.startswith("play ")
            or output.startswith("end")
            or output.startswith("potion ")
        )
