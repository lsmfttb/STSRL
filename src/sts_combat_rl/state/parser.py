"""Fault-tolerant parser for CommunicationMod-style JSON state."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from sts_combat_rl.state.models import Card, GameState, Monster, Player


def parse_game_state(raw: dict[str, Any]) -> GameState:
    """Parse raw JSON state into a conservative ``GameState``.

    Unknown fields remain available through ``GameState.raw`` and each nested
    model's ``raw`` field. Missing fields use safe defaults.
    """

    game_raw = _first_mapping(raw, ("game_state", "gameState")) or raw
    combat_raw = _first_mapping(game_raw, ("combat_state", "combatState"))
    state_raw = combat_raw or game_raw

    screen_type = _first_str(
        game_raw,
        ("screen_type", "screenType", "screen", "screen_name"),
    ) or _first_str(raw, ("screen_type", "screenType", "screen", "screen_name"))
    action_phase = _first_str(game_raw, ("action_phase", "actionPhase"))
    in_combat = _parse_in_combat(game_raw, screen_type, combat_raw)
    turn = _first_int(state_raw, ("turn", "turn_count", "turnCount", "floor_turn"))

    player_raw = _first_mapping(state_raw, ("player", "player_state", "playerState"))
    player = _parse_player(player_raw, state_raw) if player_raw is not None else None

    hand_items = _first_sequence(
        state_raw, ("hand", "cards", "hand_cards", "handCards")
    )
    hand = [_parse_card(item) for item in hand_items if isinstance(item, Mapping)]

    monster_items = _first_sequence(
        state_raw, ("monsters", "monster_list", "monsterList")
    )
    monsters = [
        _parse_monster(item) for item in monster_items if isinstance(item, Mapping)
    ]
    available_commands = _first_str_sequence(
        raw, ("available_commands", "availableCommands")
    )

    return GameState(
        in_combat=in_combat,
        screen_type=screen_type,
        action_phase=action_phase,
        turn=turn,
        player=player,
        hand=hand,
        monsters=monsters,
        available_commands=available_commands,
        raw=raw,
    )


def _parse_player(player_raw: Mapping[str, Any], root_raw: Mapping[str, Any]) -> Player:
    energy = (
        _first_int(player_raw, ("energy", "energy_current", "current_energy"))
        if player_raw
        else None
    )
    if energy is None:
        energy = _first_int(root_raw, ("energy", "energy_current", "current_energy"))

    return Player(
        current_hp=_first_int(
            player_raw, ("current_hp", "currentHp", "hp", "current_health")
        ),
        max_hp=_first_int(player_raw, ("max_hp", "maxHp", "max_health")),
        block=_first_int(player_raw, ("block", "current_block"), default=0) or 0,
        energy=energy,
        raw=dict(player_raw),
    )


def _parse_card(card_raw: Mapping[str, Any]) -> Card:
    name = _first_str(card_raw, ("name", "card_name", "cardName")) or "Unknown Card"
    return Card(
        name=name,
        card_id=_first_str(card_raw, ("card_id", "cardId", "id", "uuid")),
        cost=_first_int(card_raw, ("cost", "cost_for_turn", "costForTurn")),
        type=_first_str(card_raw, ("type", "card_type", "cardType")),
        upgraded=_parse_upgraded(card_raw),
        playable=_first_bool(
            card_raw,
            ("playable", "is_playable", "isPlayable", "can_play", "canPlay"),
            default=False,
        ),
        has_target=_first_bool(
            card_raw, ("has_target", "hasTarget", "requires_target")
        ),
        raw=dict(card_raw),
    )


def _parse_monster(monster_raw: Mapping[str, Any]) -> Monster:
    current_hp = _first_int(
        monster_raw,
        ("current_hp", "currentHp", "hp", "current_health"),
    )
    alive = _parse_alive(monster_raw, current_hp)

    return Monster(
        name=_first_str(monster_raw, ("name", "monster_name", "monsterName"))
        or "Unknown Monster",
        monster_id=_first_str(monster_raw, ("monster_id", "monsterId", "id", "uuid")),
        current_hp=current_hp,
        max_hp=_first_int(monster_raw, ("max_hp", "maxHp", "max_health")),
        block=_first_int(monster_raw, ("block", "current_block"), default=0) or 0,
        intent=_first_str(monster_raw, ("intent", "intent_type", "intentType")),
        alive=alive,
        raw=dict(monster_raw),
    )


def _parse_in_combat(
    raw: Mapping[str, Any],
    screen_type: str | None,
    combat_raw: Mapping[str, Any] | None = None,
) -> bool:
    explicit = _first_bool(raw, ("in_combat", "inCombat", "combat"), default=None)
    if explicit is not None:
        return explicit

    if combat_raw is not None:
        return True

    if screen_type is not None and _normalize(screen_type) in {"combat", "battle"}:
        return True

    room_phase = _first_str(raw, ("room_phase", "roomPhase", "phase"))
    if room_phase is not None and _normalize(room_phase) in {"combat", "battle"}:
        return True

    return False


def _parse_upgraded(card_raw: Mapping[str, Any]) -> bool:
    explicit = _first_bool(
        card_raw, ("upgraded", "is_upgraded", "isUpgraded"), default=None
    )
    if explicit is not None:
        return explicit

    upgrades = _first_int(card_raw, ("upgrades", "upgrade_count", "upgradeCount"))
    if upgrades is not None:
        return upgrades > 0

    return False


def _parse_alive(monster_raw: Mapping[str, Any], current_hp: int | None) -> bool:
    explicit = _first_bool(monster_raw, ("alive", "is_alive", "isAlive"), default=None)
    if explicit is not None:
        return explicit

    is_gone = _first_bool(monster_raw, ("is_gone", "isGone", "gone"), default=None)
    if is_gone is not None:
        return not is_gone

    if current_hp is not None:
        return current_hp > 0

    return True


def _first_mapping(
    data: Mapping[str, Any], keys: Sequence[str]
) -> Mapping[str, Any] | None:
    for key in keys:
        value = data.get(key)
        if isinstance(value, Mapping):
            return value
    return None


def _first_sequence(data: Mapping[str, Any], keys: Sequence[str]) -> list[Any]:
    for key in keys:
        value = data.get(key)
        if isinstance(value, list):
            return value
    return []


def _first_str_sequence(data: Mapping[str, Any], keys: Sequence[str]) -> list[str]:
    for key in keys:
        value = data.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, str)]
    return []


def _first_str(data: Mapping[str, Any], keys: Sequence[str]) -> str | None:
    for key in keys:
        value = data.get(key)
        if value is None:
            continue
        if isinstance(value, str):
            return value
        if isinstance(value, (int, float, bool)):
            return str(value)
    return None


def _first_int(
    data: Mapping[str, Any],
    keys: Sequence[str],
    default: int | None = None,
) -> int | None:
    for key in keys:
        value = data.get(key)
        parsed = _to_int(value)
        if parsed is not None:
            return parsed
    return default


def _first_bool(
    data: Mapping[str, Any],
    keys: Sequence[str],
    default: bool | None = None,
) -> bool | None:
    for key in keys:
        if key not in data:
            continue
        parsed = _to_bool(data.get(key))
        if parsed is not None:
            return parsed
    return default


def _to_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return None
    return None


def _to_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, int) and value in {0, 1}:
        return bool(value)
    if isinstance(value, str):
        normalized = _normalize(value)
        if normalized in {"true", "yes", "1"}:
            return True
        if normalized in {"false", "no", "0"}:
            return False
    return None


def _normalize(value: str) -> str:
    return value.strip().lower()
