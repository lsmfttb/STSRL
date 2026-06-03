"""Fixed-size feature encoders for simulator snapshots and legal actions.

These encoders only transform fields already exposed by a simulator adapter.
They do not implement Slay the Spire mechanics, action masks, Gymnasium spaces,
or any RL algorithm.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from sts_combat_rl.sim.contract import SimulatorAction


MAX_HAND_CARDS = 10
MAX_MONSTERS = 5
MAX_POTIONS = 5

CARD_TYPES = ("ATTACK", "SKILL", "POWER", "CURSE", "STATUS")
ACTION_SCOPES = ("battle", "game")
ACTION_KINDS = (
    "card",
    "end_turn",
    "potion",
    "potion_discard",
    "single_card_select",
    "multi_card_select",
    "event",
    "reward_card",
    "reward_gold",
    "reward_key",
    "reward_potion",
    "reward_relic",
    "card_remove",
    "skip",
    "boss_relic",
    "card_select",
    "map",
    "treasure_open",
    "treasure_leave",
    "rest",
    "shop_reward_card",
    "shop_reward_gold",
    "shop_reward_key",
    "shop_reward_potion",
    "shop_reward_relic",
    "shop_card_remove",
    "shop_skip",
    "game_potion_use",
    "game_potion_discard",
    "game_unknown",
    "battle_unknown",
)


def encode_lightspeed_battle_snapshot(raw: Mapping[str, Any]) -> list[float]:
    """Encode a patched `sts_lightspeed` snapshot into fixed-size features."""

    features: list[float] = [
        _bool(raw.get("battle_active")),
        _number(raw.get("act")),
        _number(raw.get("floor_num")),
        _number(raw.get("cur_hp")),
        _number(raw.get("max_hp")),
        _number(raw.get("gold")),
    ]

    player = _mapping(raw.get("battle_player"))
    features.extend(
        [
            _number(player.get("current_hp")),
            _number(player.get("max_hp")),
            _number(player.get("energy")),
            _number(player.get("energy_per_turn")),
            _number(player.get("block")),
            _number(player.get("strength")),
            _number(player.get("dexterity")),
            _number(player.get("artifact")),
            _number(player.get("focus")),
            _number(player.get("vulnerable")),
            _number(player.get("weak")),
            _number(player.get("frail")),
            _number(player.get("cards_played_this_turn")),
            _number(player.get("attacks_played_this_turn")),
            _number(player.get("skills_played_this_turn")),
            _number(player.get("cards_discarded_this_turn")),
            _number(player.get("times_damaged_this_combat")),
        ]
    )

    features.extend(
        [
            _number(raw.get("battle_turn")),
            _number(raw.get("battle_hand_size")),
            _number(raw.get("battle_draw_pile_size")),
            _number(raw.get("battle_discard_pile_size")),
            _number(raw.get("battle_exhaust_pile_size")),
            _number(raw.get("battle_monster_count")),
            _number(raw.get("battle_monsters_alive")),
            _number(raw.get("battle_potion_count")),
            _number(raw.get("battle_potion_capacity")),
        ]
    )

    hand = _sequence(raw.get("battle_hand"))
    for idx in range(MAX_HAND_CARDS):
        features.extend(_encode_card(_mapping_at(hand, idx)))

    monsters = _sequence(raw.get("battle_monsters"))
    for idx in range(MAX_MONSTERS):
        features.extend(_encode_monster(_mapping_at(monsters, idx)))

    potions = _sequence(raw.get("battle_potions"))
    for idx in range(MAX_POTIONS):
        features.extend(_encode_potion(_mapping_at(potions, idx)))

    return features


def encode_communicationmod_battle_snapshot(raw: Mapping[str, Any]) -> list[float]:
    """Encode a CommunicationMod combat JSON object into the same feature shape."""

    return encode_lightspeed_battle_snapshot(
        normalize_communicationmod_battle_snapshot(raw)
    )


def normalize_communicationmod_battle_snapshot(raw: Mapping[str, Any]) -> dict[str, Any]:
    """Map live CommunicationMod combat fields into the patched simulator shape."""

    game = _mapping(raw.get("game_state")) or _mapping(raw.get("gameState")) or raw
    combat = _mapping(game.get("combat_state")) or _mapping(game.get("combatState"))
    player = _mapping(combat.get("player"))
    hand = _sequence(combat.get("hand"))
    monsters = _sequence(combat.get("monsters"))
    potions = _sequence(game.get("potions"))

    return {
        "battle_active": bool(combat),
        "act": game.get("act"),
        "floor_num": game.get("floor"),
        "cur_hp": game.get("current_hp"),
        "max_hp": game.get("max_hp"),
        "gold": game.get("gold"),
        "battle_player": _normalize_communicationmod_player(player, combat),
        "battle_turn": combat.get("turn"),
        "battle_hand_size": len(hand),
        "battle_draw_pile_size": len(_sequence(combat.get("draw_pile"))),
        "battle_discard_pile_size": len(_sequence(combat.get("discard_pile"))),
        "battle_exhaust_pile_size": len(_sequence(combat.get("exhaust_pile"))),
        "battle_monster_count": len(monsters),
        "battle_monsters_alive": sum(
            1 for monster in monsters if _communicationmod_monster_alive(_mapping(monster))
        ),
        "battle_potion_count": sum(
            1 for potion in potions if _communicationmod_potion_present(_mapping(potion))
        ),
        "battle_potion_capacity": len(potions),
        "battle_hand": [
            _normalize_communicationmod_card(_mapping(card)) for card in hand
        ],
        "battle_monsters": [
            _normalize_communicationmod_monster(_mapping(monster))
            for monster in monsters
        ],
        "battle_potions": [
            _normalize_communicationmod_potion(_mapping(potion))
            for potion in potions
        ],
    }


def lightspeed_battle_feature_size() -> int:
    """Return the stable feature length for `encode_lightspeed_battle_snapshot`."""

    return len(encode_lightspeed_battle_snapshot({}))


def communicationmod_battle_feature_size() -> int:
    """Return the stable feature length for `encode_communicationmod_battle_snapshot`."""

    return len(encode_communicationmod_battle_snapshot({}))


def encode_simulator_action(action: SimulatorAction) -> list[float]:
    """Encode one legal simulator action for variable-action scoring."""

    scope = str(action.raw.get("scope", ""))
    kind = str(action.kind)
    return (
        _one_hot(scope, ACTION_SCOPES)
        + _one_hot(kind, ACTION_KINDS)
        + [
            _number(action.raw.get("idx1")),
            _number(action.raw.get("idx2")),
            _number(action.raw.get("idx3")),
        ]
    )


def encode_simulator_actions(actions: Sequence[SimulatorAction]) -> list[list[float]]:
    """Encode a current legal-action list without creating an action mask."""

    return [encode_simulator_action(action) for action in actions]


def simulator_action_feature_size() -> int:
    """Return the stable feature length for `encode_simulator_action`."""

    return len(
        encode_simulator_action(
            SimulatorAction(action_id="empty", label="", raw={})
        )
    )


def _encode_card(card: Mapping[str, Any]) -> list[float]:
    return [
        _bool(card),
        *_one_hot(str(card.get("type", "")), CARD_TYPES),
        _number(card.get("cost")),
        _number(card.get("cost_for_turn")),
        _bool(card.get("playable")),
        _bool(card.get("requires_target")),
        _bool(card.get("upgraded")),
        _number(card.get("upgrade_count")),
        _bool(card.get("exhausts")),
        _bool(card.get("ethereal")),
    ]


def _encode_monster(monster: Mapping[str, Any]) -> list[float]:
    return [
        _bool(monster),
        _number(monster.get("current_hp")),
        _number(monster.get("max_hp")),
        _number(monster.get("block")),
        _bool(monster.get("alive")),
        _bool(monster.get("targetable")),
        _bool(monster.get("attacking")),
        _number(monster.get("move_base_damage")),
        _number(monster.get("move_hits")),
        _number(monster.get("strength")),
        _number(monster.get("vulnerable")),
        _number(monster.get("weak")),
        _number(monster.get("artifact")),
        _number(monster.get("poison")),
        _number(monster.get("metallicize")),
        _number(monster.get("plated_armor")),
        _number(monster.get("regen")),
        _bool(monster.get("half_dead")),
    ]


def _encode_potion(potion: Mapping[str, Any]) -> list[float]:
    return [
        _bool(potion),
        _number(potion.get("id")),
    ]


def _normalize_communicationmod_player(
    player: Mapping[str, Any],
    combat: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "current_hp": player.get("current_hp"),
        "max_hp": player.get("max_hp"),
        "energy": player.get("energy"),
        "block": player.get("block"),
        "cards_discarded_this_turn": combat.get("cards_discarded_this_turn"),
        "times_damaged_this_combat": combat.get("times_damaged"),
    }


def _normalize_communicationmod_card(card: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "type": card.get("type"),
        "cost": card.get("cost"),
        "cost_for_turn": card.get("cost_for_turn", card.get("cost")),
        "playable": card.get("is_playable", card.get("playable")),
        "requires_target": card.get("has_target", card.get("requires_target")),
        "upgraded": _number(card.get("upgrades")) > 0.0 or bool(card.get("upgraded")),
        "upgrade_count": card.get("upgrades", card.get("upgrade_count")),
        "exhausts": card.get("exhausts"),
        "ethereal": card.get("ethereal"),
    }


def _normalize_communicationmod_monster(monster: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "current_hp": monster.get("current_hp"),
        "max_hp": monster.get("max_hp"),
        "block": monster.get("block"),
        "alive": _communicationmod_monster_alive(monster),
        "targetable": _communicationmod_monster_alive(monster),
        "attacking": _communicationmod_monster_attacking(monster),
        "move_base_damage": monster.get("move_base_damage"),
        "move_hits": monster.get("move_hits"),
        "strength": _communicationmod_power_amount(monster, "Strength"),
        "vulnerable": _communicationmod_power_amount(monster, "Vulnerable"),
        "weak": _communicationmod_power_amount(monster, "Weak"),
        "artifact": _communicationmod_power_amount(monster, "Artifact"),
        "poison": _communicationmod_power_amount(monster, "Poison"),
        "half_dead": monster.get("half_dead"),
    }


def _normalize_communicationmod_potion(potion: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "id": potion.get("numeric_id"),
    }


def _communicationmod_monster_alive(monster: Mapping[str, Any]) -> bool:
    if monster.get("is_gone") is True:
        return False
    return _number(monster.get("current_hp")) > 0.0


def _communicationmod_monster_attacking(monster: Mapping[str, Any]) -> bool:
    intent = str(monster.get("intent", ""))
    return "ATTACK" in intent


def _communicationmod_potion_present(potion: Mapping[str, Any]) -> bool:
    potion_id = str(potion.get("id", potion.get("name", "")))
    return potion_id not in {"", "Potion Slot"}


def _communicationmod_power_amount(monster: Mapping[str, Any], power_id: str) -> int:
    for power in _sequence(monster.get("powers")):
        power_raw = _mapping(power)
        if power_raw.get("id") == power_id or power_raw.get("name") == power_id:
            amount = power_raw.get("amount")
            if isinstance(amount, int):
                return amount
            return 1
    return 0


def _one_hot(value: str, options: Sequence[str]) -> list[float]:
    return [1.0 if value == option else 0.0 for option in options]


def _number(value: Any) -> float:
    if isinstance(value, bool):
        return 1.0 if value else 0.0
    if isinstance(value, (int, float)):
        return float(value)
    return 0.0


def _bool(value: Any) -> float:
    return 1.0 if value else 0.0


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _sequence(value: Any) -> Sequence[Any]:
    return value if isinstance(value, Sequence) and not isinstance(value, str) else ()


def _mapping_at(values: Sequence[Any], idx: int) -> Mapping[str, Any]:
    if idx >= len(values):
        return {}
    return _mapping(values[idx])
