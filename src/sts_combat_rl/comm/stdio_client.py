"""stdin/stdout JSON line client."""

from __future__ import annotations

import json
import logging
from pathlib import Path
import time
from typing import Any
from typing import TextIO

from sts_combat_rl.comm.protocol import (
    Command,
    format_command,
)
from sts_combat_rl.decision import choose_command_for_state, choose_manual_poll_command
from sts_combat_rl.logging_utils import log_probe_step
from sts_combat_rl.policy.scripted import ScriptedCombatPolicy
from sts_combat_rl.state.parser import parse_game_state


class StdioClient:
    """Read JSON states from stdin and write formatted commands to stdout."""

    def __init__(
        self,
        policy: ScriptedCombatPolicy,
        logger: logging.Logger,
        sample_capture_file: Path | None = None,
        idle_poll_delay_seconds: float = 0.5,
        manual_mode: bool = False,
    ) -> None:
        self._policy = policy
        self._logger = logger
        self._sample_capture_file = sample_capture_file
        self._idle_poll_delay_seconds = idle_poll_delay_seconds
        self._manual_mode = manual_mode

    def run(
        self,
        input_stream: TextIO,
        output_stream: TextIO,
    ) -> None:
        for line in input_stream:
            raw_line = line.rstrip("\r\n")
            if not raw_line.strip():
                continue

            self._capture_raw_line(raw_line)
            command = self.act_from_json_line(raw_line)
            output_stream.write(format_command(command) + "\n")
            output_stream.flush()

    def _capture_raw_line(self, raw_line: str) -> None:
        if self._sample_capture_file is None:
            return

        try:
            self._sample_capture_file.parent.mkdir(parents=True, exist_ok=True)
            with self._sample_capture_file.open("a", encoding="utf-8") as file:
                file.write(raw_line)
                file.write("\n")
        except OSError:
            self._logger.exception("failed to append raw sample")

    def act_from_json_line(self, raw_line: str) -> Command:
        try:
            raw = json.loads(raw_line)
        except json.JSONDecodeError:
            self._logger.exception("invalid JSON line")
            return Command.end_turn("invalid json")

        if not isinstance(raw, dict):
            self._logger.error("state JSON must be an object")
            return Command.end_turn("state json was not an object")

        return self.act_from_raw(raw)

    def act_from_raw(self, raw: dict[str, Any]) -> Command:
        try:
            if "error" in raw:
                self._logger.error("CommunicationMod error: %s", raw["error"])
                return Command.state("recover from CommunicationMod error")

            state = parse_game_state(raw)
            if self._manual_mode:
                command = choose_manual_poll_command(state)
            else:
                command = choose_command_for_state(state, self._policy)
            if command.command_type == "state" and raw.get("in_game") is False:
                time.sleep(self._idle_poll_delay_seconds)
            log_probe_step(self._logger, state, command)
            return command
        except Exception:
            self._logger.exception("failed to parse state or select action")
            return Command.end_turn("parser or policy failure")
