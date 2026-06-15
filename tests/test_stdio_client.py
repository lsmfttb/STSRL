from __future__ import annotations

import io
import logging
from pathlib import Path

from sts_combat_rl.comm.stdio_client import StdioClient
from sts_combat_rl.policy.scripted import ScriptedCombatPolicy


def test_stdio_client_reads_json_lines_and_writes_commands() -> None:
    client = StdioClient(
        policy=ScriptedCombatPolicy(),
        logger=logging.getLogger("test_stdio_client"),
    )
    input_stream = io.StringIO(
        '{"screen_type":"COMBAT","hand":[{"name":"Strike","type":"ATTACK",'
        '"playable":true}],"monsters":[{"name":"Cultist","hp":10}]}\n'
    )
    output_stream = io.StringIO()

    client.run(input_stream, output_stream)

    assert output_stream.getvalue() == "play 1 0\n"


def test_stdio_client_can_capture_raw_json_lines(tmp_path: Path) -> None:
    capture_file = tmp_path / "real_samples" / "captured.jsonl"
    client = StdioClient(
        policy=ScriptedCombatPolicy(),
        logger=logging.getLogger("test_stdio_client_capture"),
        sample_capture_file=capture_file,
    )
    input_stream = io.StringIO('  {"screen_type":"EVENT"}  \n\n{not valid json}\n')
    output_stream = io.StringIO()

    client.run(input_stream, output_stream)

    assert output_stream.getvalue() == "end\nend\n"
    assert capture_file.read_text(encoding="utf-8").splitlines() == [
        '  {"screen_type":"EVENT"}  ',
        "{not valid json}",
    ]


def test_stdio_client_respects_available_commands() -> None:
    client = StdioClient(
        policy=ScriptedCombatPolicy(),
        logger=logging.getLogger("test_stdio_client_available_commands"),
    )
    input_stream = io.StringIO(
        '{"available_commands":["choose","key","click","wait","state"],'
        '"game_state":{"screen_type":"EVENT"}}\n'
        '{"error":"Invalid command: end. Possible commands: [start, state]",'
        '"ready_for_command":true}\n'
    )
    output_stream = io.StringIO()

    client.run(input_stream, output_stream)

    assert output_stream.getvalue() == "wait 30\nstate\n"


def test_stdio_client_plays_nested_communication_mod_combat_state() -> None:
    client = StdioClient(
        policy=ScriptedCombatPolicy(),
        logger=logging.getLogger("test_stdio_client_nested_combat"),
        idle_poll_delay_seconds=0,
    )
    input_stream = io.StringIO(
        '{"available_commands":["play","end","key","click","wait","state"],'
        '"game_state":{"room_phase":"COMBAT","combat_state":{"turn":1,'
        '"player":{"current_hp":68,"max_hp":75,"block":0,"energy":3},'
        '"hand":[{"name":"Strike","id":"Strike_R","type":"ATTACK",'
        '"is_playable":true,"cost":1}],'
        '"monsters":[{"name":"Cultist","id":"Cultist","current_hp":20,'
        '"max_hp":20,"is_gone":false}]}}}\n'
    )
    output_stream = io.StringIO()

    client.run(input_stream, output_stream)

    assert output_stream.getvalue() == "play 1 0\n"


def test_stdio_client_waits_for_changing_combat_state() -> None:
    client = StdioClient(
        policy=ScriptedCombatPolicy(),
        logger=logging.getLogger("test_stdio_client_changing_combat"),
        idle_poll_delay_seconds=0,
    )
    input_stream = io.StringIO(
        '{"available_commands":["end","key","click","wait","state"],'
        '"game_state":{"room_phase":"COMBAT","action_phase":"EXECUTING_ACTIONS",'
        '"combat_state":{"turn":1,"hand":[],"monsters":[{"name":"Cultist",'
        '"current_hp":20}]}}}\n'
    )
    output_stream = io.StringIO()

    client.run(input_stream, output_stream)

    assert output_stream.getvalue() == "wait 30\n"


def test_stdio_client_manual_mode_polls_without_gameplay_actions() -> None:
    client = StdioClient(
        policy=ScriptedCombatPolicy(),
        logger=logging.getLogger("test_stdio_client_manual"),
        manual_mode=True,
        idle_poll_delay_seconds=0,
    )
    input_stream = io.StringIO(
        '{"available_commands":["play","end","key","click","wait","state"],'
        '"game_state":{"room_phase":"COMBAT","action_phase":"WAITING_ON_USER",'
        '"combat_state":{"turn":1,'
        '"hand":[{"name":"Strike","id":"Strike_R","type":"ATTACK",'
        '"is_playable":true,"cost":1}],'
        '"monsters":[{"name":"Cultist","id":"Cultist","current_hp":20,'
        '"max_hp":20,"is_gone":false}]}}}\n'
    )
    output_stream = io.StringIO()

    client.run(input_stream, output_stream)

    assert output_stream.getvalue() == "wait 30\n"


def test_stdio_client_manual_mode_uses_state_when_wait_is_unavailable() -> None:
    client = StdioClient(
        policy=ScriptedCombatPolicy(),
        logger=logging.getLogger("test_stdio_client_manual_state"),
        manual_mode=True,
        idle_poll_delay_seconds=0,
    )
    input_stream = io.StringIO(
        '{"available_commands":["start","state"],"ready_for_command":true,'
        '"in_game":false}\n'
    )
    output_stream = io.StringIO()

    client.run(input_stream, output_stream)

    assert output_stream.getvalue() == "state\n"
