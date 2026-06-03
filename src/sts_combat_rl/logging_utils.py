"""Logging helpers for the communication probe."""

from __future__ import annotations

import json
import logging
from dataclasses import asdict
from pathlib import Path
from typing import Any

from sts_combat_rl.comm.protocol import Command, format_command
from sts_combat_rl.state.models import GameState


DEFAULT_LOG_FILE = Path("logs/sts_combat_rl.log")


def configure_logging(log_file: str | Path | None = DEFAULT_LOG_FILE) -> logging.Logger:
    """Configure and return the package logger."""

    logger = logging.getLogger("sts_combat_rl")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    logger.propagate = False

    if log_file is None:
        handler: logging.Handler = logging.StreamHandler()
    else:
        path = Path(log_file)
        path.parent.mkdir(parents=True, exist_ok=True)
        handler = logging.FileHandler(path, encoding="utf-8")

    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
    )
    logger.addHandler(handler)
    return logger


def log_probe_step(logger: logging.Logger, state: GameState, command: Command) -> None:
    """Log raw input, parsed summary, and selected command."""

    payload: dict[str, Any] = {
        "raw": state.raw,
        "summary": summarize_state(state),
        "command": asdict(command),
        "formatted_command": format_command(command),
    }
    logger.info(json.dumps(payload, ensure_ascii=False, sort_keys=True))


def summarize_state(state: GameState) -> dict[str, Any]:
    """Return a compact parsed-state summary for logs."""

    return {
        "in_combat": state.in_combat,
        "screen_type": state.screen_type,
        "action_phase": state.action_phase,
        "turn": state.turn,
        "available_commands": state.available_commands,
        "player": None
        if state.player is None
        else {
            "current_hp": state.player.current_hp,
            "max_hp": state.player.max_hp,
            "block": state.player.block,
            "energy": state.player.energy,
        },
        "hand": [
            {
                "name": card.name,
                "card_id": card.card_id,
                "cost": card.cost,
                "type": card.type,
                "upgraded": card.upgraded,
                "playable": card.playable,
                "has_target": card.has_target,
            }
            for card in state.hand
        ],
        "monsters": [
            {
                "name": monster.name,
                "monster_id": monster.monster_id,
                "current_hp": monster.current_hp,
                "max_hp": monster.max_hp,
                "block": monster.block,
                "intent": monster.intent,
                "alive": monster.alive,
            }
            for monster in state.monsters
        ],
    }
