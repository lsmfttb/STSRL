"""Command abstraction and formatting.

The formatter is deliberately small and isolated. Real CommunicationMod command
syntax can be updated here without changing parser or policy code.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal


CommandType = Literal[
    "start",
    "play_card",
    "end_turn",
    "choose",
    "proceed",
    "return",
    "potion",
    "key",
    "click",
    "state",
    "wait",
]
PotionAction = Literal["use", "discard"]
MouseButton = Literal["left", "right"]
READY_SIGNAL = "ready_for_command"
DEFAULT_WAIT_FRAMES = 30


@dataclass(frozen=True)
class Command:
    """A protocol-neutral action selected by policy code."""

    command_type: CommandType
    card_index: int | None = None
    target_index: int | None = None
    choice: int | str | None = None
    player_class: str | None = None
    ascension_level: int | None = None
    seed: str | None = None
    potion_action: PotionAction | None = None
    potion_slot: int | None = None
    key_name: str | None = None
    mouse_button: MouseButton | None = None
    x: int | None = None
    y: int | None = None
    timeout: int | None = None
    wait_frames: int | None = None
    reason: str | None = None

    @classmethod
    def start(
        cls,
        player_class: str,
        ascension_level: int | None = None,
        seed: str | None = None,
        reason: str | None = None,
    ) -> "Command":
        return cls(
            command_type="start",
            player_class=player_class,
            ascension_level=ascension_level,
            seed=seed,
            reason=reason,
        )

    @classmethod
    def play_card(
        cls,
        card_index: int,
        target_index: int | None = None,
        reason: str | None = None,
    ) -> "Command":
        return cls(
            command_type="play_card",
            card_index=card_index,
            target_index=target_index,
            reason=reason,
        )

    @classmethod
    def end_turn(cls, reason: str | None = None) -> "Command":
        return cls(command_type="end_turn", reason=reason)

    @classmethod
    def choose(cls, choice: int | str, reason: str | None = None) -> "Command":
        return cls(command_type="choose", choice=choice, reason=reason)

    @classmethod
    def proceed(cls, reason: str | None = None) -> "Command":
        return cls(command_type="proceed", reason=reason)

    @classmethod
    def return_to_previous(cls, reason: str | None = None) -> "Command":
        return cls(command_type="return", reason=reason)

    @classmethod
    def potion(
        cls,
        action: PotionAction,
        potion_slot: int,
        target_index: int | None = None,
        reason: str | None = None,
    ) -> "Command":
        return cls(
            command_type="potion",
            potion_action=action,
            potion_slot=potion_slot,
            target_index=target_index,
            reason=reason,
        )

    @classmethod
    def key(
        cls,
        key_name: str,
        timeout: int | None = None,
        reason: str | None = None,
    ) -> "Command":
        return cls(
            command_type="key",
            key_name=key_name,
            timeout=timeout,
            reason=reason,
        )

    @classmethod
    def click(
        cls,
        button: MouseButton,
        x: int,
        y: int,
        timeout: int | None = None,
        reason: str | None = None,
    ) -> "Command":
        return cls(
            command_type="click",
            mouse_button=button,
            x=x,
            y=y,
            timeout=timeout,
            reason=reason,
        )

    @classmethod
    def state(cls, reason: str | None = None) -> "Command":
        return cls(command_type="state", reason=reason)

    @classmethod
    def wait(cls, reason: str | None = None) -> "Command":
        return cls(
            command_type="wait",
            wait_frames=DEFAULT_WAIT_FRAMES,
            reason=reason,
        )


def format_command(command: Command) -> str:
    """Format a command for CommunicationMod.

    Card indices are converted from parser/policy zero-based indices to
    CommunicationMod's documented one-based hand indices. Other indices are
    passed through unchanged until calibrated by real command use.
    """

    if command.command_type == "start":
        if command.player_class is None:
            return "state"
        parts = ["start", command.player_class]
        if command.ascension_level is not None:
            parts.append(str(command.ascension_level))
        if command.seed is not None:
            parts.append(command.seed)
        return " ".join(parts)

    if command.command_type == "state":
        return "state"

    if command.command_type == "wait":
        wait_frames = command.wait_frames or DEFAULT_WAIT_FRAMES
        return f"wait {wait_frames}"

    if command.command_type == "end_turn":
        return "end"

    if command.command_type == "choose":
        if command.choice is None:
            return "state"
        return f"choose {command.choice}"

    if command.command_type == "proceed":
        return "proceed"

    if command.command_type == "return":
        return "return"

    if command.command_type == "potion":
        if command.potion_action is None or command.potion_slot is None:
            return "state"
        parts = ["potion", command.potion_action, str(command.potion_slot)]
        if command.target_index is not None:
            parts.append(str(command.target_index))
        return " ".join(parts)

    if command.command_type == "key":
        if command.key_name is None:
            return "state"
        parts = ["key", command.key_name]
        if command.timeout is not None:
            parts.append(str(command.timeout))
        return " ".join(parts)

    if command.command_type == "click":
        if command.mouse_button is None or command.x is None or command.y is None:
            return "state"
        parts = ["click", command.mouse_button, str(command.x), str(command.y)]
        if command.timeout is not None:
            parts.append(str(command.timeout))
        return " ".join(parts)

    if command.command_type == "play_card":
        if command.card_index is None:
            return "end"
        card_index = command.card_index + 1
        if command.target_index is None:
            return f"play {card_index}"
        return f"play {card_index} {command.target_index}"

    return "end"


def command_name(command: Command) -> str:
    """Return the CommunicationMod command verb for availability checks."""

    if command.command_type == "start":
        return "start"
    if command.command_type == "play_card":
        return "play"
    if command.command_type == "end_turn":
        return "end"
    if command.command_type == "choose":
        return "choose"
    if command.command_type == "proceed":
        return "proceed"
    if command.command_type == "return":
        return "return"
    if command.command_type == "potion":
        return "potion"
    if command.command_type == "key":
        return "key"
    if command.command_type == "click":
        return "click"
    if command.command_type == "state":
        return "state"
    if command.command_type == "wait":
        return "wait"
    return "end"


def constrain_to_available_commands(
    command: Command,
    available_commands: Sequence[str],
) -> Command:
    """Return ``command`` if allowed, otherwise a conservative safe command."""

    available = set(available_commands)
    if command_name(command) in available:
        return command

    if "wait" in available:
        return Command.wait("preferred command unavailable")
    if "state" in available:
        return Command.state("preferred command unavailable")
    if "end" in available:
        return Command.end_turn("preferred command unavailable")

    return command


def format_ready_signal() -> str:
    """Format the CommunicationMod startup handshake signal."""

    return READY_SIGNAL
