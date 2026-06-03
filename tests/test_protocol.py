from __future__ import annotations

import pytest

from sts_combat_rl.comm.protocol import (
    Command,
    command_name,
    constrain_to_available_commands,
    format_command,
)


@pytest.mark.parametrize(
    ("command", "expected"),
    [
        (Command.start("IRONCLAD"), "start IRONCLAD"),
        (Command.start("SILENT", ascension_level=20, seed="ABC123"), "start SILENT 20 ABC123"),
        (Command.play_card(0, 2), "play 1 2"),
        (Command.play_card(1), "play 2"),
        (Command.end_turn(), "end"),
        (Command.choose(0), "choose 0"),
        (Command.choose("card"), "choose card"),
        (Command.proceed(), "proceed"),
        (Command.return_to_previous(), "return"),
        (Command.potion("use", 1), "potion use 1"),
        (Command.potion("discard", 0, target_index=2), "potion discard 0 2"),
        (Command.key("Map"), "key Map"),
        (Command.key("Confirm", timeout=60), "key Confirm 60"),
        (Command.click("left", 100, 200), "click left 100 200"),
        (Command.click("right", 100, 200, timeout=60), "click right 100 200 60"),
        (Command.wait(), "wait 30"),
        (Command.state(), "state"),
    ],
)
def test_format_command_supports_documented_communicationmod_commands(
    command: Command,
    expected: str,
) -> None:
    assert format_command(command) == expected


@pytest.mark.parametrize(
    ("command", "expected"),
    [
        (Command.start("IRONCLAD"), "start"),
        (Command.play_card(0), "play"),
        (Command.end_turn(), "end"),
        (Command.choose(0), "choose"),
        (Command.proceed(), "proceed"),
        (Command.return_to_previous(), "return"),
        (Command.potion("use", 0), "potion"),
        (Command.key("Map"), "key"),
        (Command.click("left", 1, 2), "click"),
        (Command.wait(), "wait"),
        (Command.state(), "state"),
    ],
)
def test_command_name_matches_available_command_verbs(
    command: Command,
    expected: str,
) -> None:
    assert command_name(command) == expected


def test_constrain_to_available_commands_allows_new_documented_verbs() -> None:
    command = Command.choose("card")

    constrained = constrain_to_available_commands(command, ["choose", "state"])

    assert constrained == command


def test_constrain_to_available_commands_still_prefers_wait_then_state() -> None:
    command = Command.proceed()

    constrained = constrain_to_available_commands(command, ["wait", "state"])

    assert constrained.command_type == "wait"
