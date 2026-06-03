"""Shared command selection helpers for the probe."""

from __future__ import annotations

from sts_combat_rl.comm.protocol import Command, constrain_to_available_commands
from sts_combat_rl.policy.scripted import ScriptedCombatPolicy
from sts_combat_rl.state.models import GameState


def choose_command_for_state(
    state: GameState,
    policy: ScriptedCombatPolicy,
) -> Command:
    """Choose and protocol-constrain the next command for a parsed state."""

    command = policy.act(state)
    if should_wait_for_stable_combat(state):
        command = Command.wait("combat state is still changing")
    return constrain_to_available_commands(command, state.available_commands)


def choose_manual_poll_command(state: GameState) -> Command:
    """Poll state without taking gameplay actions.

    This is intended for manual capture sessions where the player controls the
    game directly and the probe only records CommunicationMod JSON.
    """

    if "wait" in state.available_commands:
        return Command.wait("manual capture poll")
    return Command.state("manual capture poll")


def should_wait_for_stable_combat(state: GameState) -> bool:
    """Return whether a combat state is not yet ready for player input."""

    if not state.in_combat:
        return False
    if "wait" not in state.available_commands:
        return False
    if state.action_phase is None:
        return False
    return state.action_phase != "WAITING_ON_USER"
