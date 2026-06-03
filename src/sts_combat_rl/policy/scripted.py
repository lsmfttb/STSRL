"""Minimal scripted combat policy for communication probing."""

from __future__ import annotations

from sts_combat_rl.comm.protocol import Command
from sts_combat_rl.state.models import Card, GameState, Monster


class ScriptedCombatPolicy:
    """Choose stable, explainable actions from parsed combat state."""

    def act(self, state: GameState) -> Command:
        if not state.in_combat:
            return Command.end_turn("not in combat")

        first_alive_monster_index = _first_alive_monster_index(state.monsters)
        if first_alive_monster_index is not None:
            for card_index, card in enumerate(state.hand):
                if _is_playable_attack(card):
                    target_index = (
                        first_alive_monster_index
                        if card.has_target is not False
                        else None
                    )
                    return Command.play_card(
                        card_index=card_index,
                        target_index=target_index,
                        reason="first playable attack into first alive monster",
                    )

        for card_index, card in enumerate(state.hand):
            if _is_playable_defend(card):
                return Command.play_card(
                    card_index=card_index,
                    reason="first playable defend",
                )

        return Command.end_turn("no reliable playable action")


def _first_alive_monster_index(monsters: list[Monster]) -> int | None:
    for index, monster in enumerate(monsters):
        if monster.alive:
            return index
    return None


def _is_playable_attack(card: Card) -> bool:
    if not card.playable:
        return False

    normalized_type = _normalize(card.type)
    if normalized_type == "attack":
        return True

    return _contains_any(card, ("strike", "attack", "攻击"))


def _is_playable_defend(card: Card) -> bool:
    if not card.playable:
        return False

    normalized_type = _normalize(card.type)
    if normalized_type == "defense":
        return True

    return _contains_any(card, ("defend", "defense", "防御"))


def _contains_any(card: Card, needles: tuple[str, ...]) -> bool:
    haystack = " ".join(
        value for value in (card.name, card.card_id or "") if value
    ).lower()
    return any(needle in haystack for needle in needles)


def _normalize(value: str | None) -> str | None:
    return value.strip().lower() if value is not None else None
