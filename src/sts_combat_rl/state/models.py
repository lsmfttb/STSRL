"""Dataclasses for parsed Slay the Spire state."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class Card:
    name: str
    card_id: str | None
    cost: int | None
    type: str | None
    upgraded: bool
    playable: bool
    has_target: bool | None
    raw: dict[str, Any]


@dataclass
class Monster:
    name: str
    monster_id: str | None
    current_hp: int | None
    max_hp: int | None
    block: int
    intent: str | None
    alive: bool
    raw: dict[str, Any]


@dataclass
class Player:
    current_hp: int | None
    max_hp: int | None
    block: int
    energy: int | None
    raw: dict[str, Any]


@dataclass
class GameState:
    in_combat: bool
    screen_type: str | None
    action_phase: str | None
    turn: int | None
    player: Player | None
    hand: list[Card]
    monsters: list[Monster]
    available_commands: list[str]
    raw: dict[str, Any]
