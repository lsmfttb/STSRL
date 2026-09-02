from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parents[1] / "scripts" / "run_detached_job.py"


def _start(
    tmp_path: Path, command: list[str], *, expected_seconds: int | None = None, env=None
) -> tuple[Path, subprocess.CompletedProcess[str]]:
    status = tmp_path / "job" / "status.json"
    stdout = tmp_path / "job" / "stdout.log"
    stderr = tmp_path / "job" / "stderr.log"
    args = [
        sys.executable,
        str(SCRIPT),
        "start",
        "--status",
        str(status),
        "--stdout",
        str(stdout),
        "--stderr",
        str(stderr),
    ]
    if expected_seconds is not None:
        args.extend(["--expected-seconds", str(expected_seconds)])
    args.extend(["--", *command])
    result = subprocess.run(args, capture_output=True, text=True, env=env, check=False)
    return status, result


def _wait_for_terminal(status: Path) -> dict[str, object]:
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        if status.is_file():
            payload = json.loads(status.read_text(encoding="utf-8"))
            if payload["state"] in {"SUCCEEDED", "FAILED"}:
                return payload
        time.sleep(0.02)
    raise AssertionError(f"job did not finish: {status}")


def test_start_status_success_logs_pid_cwd_and_environment(tmp_path: Path) -> None:
    env = dict(os.environ, STSRL_DETACHED_MARKER="inherited")
    command = [
        sys.executable,
        "-c",
        (
            "import os,sys; print(os.environ['STSRL_DETACHED_MARKER']); "
            "print('stderr-line', file=sys.stderr)"
        ),
    ]
    status, started = _start(tmp_path, command, expected_seconds=4, env=env)
    assert started.returncode == 0, started.stderr
    payload = _wait_for_terminal(status)
    assert payload["state"] == "SUCCEEDED"
    assert payload["exit_code"] == 0
    assert payload["pid"] > 0
    assert payload["cwd"] == str(Path.cwd().resolve())
    assert payload["command"] == command
    assert payload["startup_error"] is None
    assert payload["expected_seconds"] == 4.0
    datetime.fromisoformat(str(payload["started_at"]))
    datetime.fromisoformat(str(payload["estimated_finish_at"]))
    assert (
        Path(str(payload["stdout_path"])).read_text(encoding="utf-8").strip()
        == "inherited"
    )
    assert (
        Path(str(payload["stderr_path"])).read_text(encoding="utf-8").strip()
        == "stderr-line"
    )

    inspected = subprocess.run(
        [sys.executable, str(SCRIPT), "status", "--status", str(status)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert inspected.returncode == 0
    assert json.loads(inspected.stdout) == payload


def test_nonzero_exit_is_failed_and_omitted_expected_fields_are_null(
    tmp_path: Path,
) -> None:
    status, started = _start(tmp_path, [sys.executable, "-c", "raise SystemExit(7)"])
    assert started.returncode == 0, started.stderr
    payload = _wait_for_terminal(status)
    assert payload["state"] == "FAILED"
    assert payload["exit_code"] == 7
    assert payload["expected_seconds"] is None
    assert payload["estimated_finish_at"] is None
    assert payload["startup_error"] is None


def test_startup_failure_is_recorded_without_losing_atomic_status(
    tmp_path: Path,
) -> None:
    status, started = _start(tmp_path, [str(tmp_path / "does-not-exist.exe")])
    assert started.returncode == 0, started.stderr
    payload = _wait_for_terminal(status)
    assert payload["state"] == "FAILED"
    assert payload["exit_code"] != 0
    assert payload["startup_error"]
    assert not list(status.parent.glob(".*.tmp"))


@pytest.mark.skipif(
    sys.platform == "win32", reason="supervisor signal delivery is WSL/Unix-only"
)
def test_supervisor_signal_records_terminal_failed_status(tmp_path: Path) -> None:
    status, started = _start(
        tmp_path,
        [sys.executable, "-c", "import time; time.sleep(30)"],
    )
    assert started.returncode == 0, started.stderr
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        if status.is_file() and json.loads(status.read_text())["state"] == "RUNNING":
            break
        time.sleep(0.02)
    running = json.loads(status.read_text(encoding="utf-8"))
    os.kill(int(running["pid"]), signal.SIGTERM)
    payload = _wait_for_terminal(status)
    assert payload["state"] == "FAILED"
    assert payload["exit_code"] == 143
    assert "terminated by signal" in str(payload["startup_error"])


@pytest.mark.skipif(
    sys.platform == "win32", reason="process-group verification is POSIX-only"
)
def test_supervisor_signal_terminates_target_process_group(tmp_path: Path) -> None:
    command = [
        sys.executable,
        "-c",
        "import subprocess,sys,time; subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)']); time.sleep(30)",
    ]
    status, started = _start(tmp_path, command)
    assert started.returncode == 0, started.stderr
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        if status.is_file() and json.loads(status.read_text())["state"] == "RUNNING":
            break
        time.sleep(0.02)
    running = json.loads(status.read_text(encoding="utf-8"))
    target_deadline = time.monotonic() + 10
    target_pid = None
    while time.monotonic() < target_deadline:
        children = subprocess.run(
            ["ps", "--ppid", str(running["pid"]), "-o", "pid="],
            capture_output=True,
            text=True,
            check=False,
        ).stdout.split()
        if children:
            target_pid = int(children[0])
            break
        time.sleep(0.02)
    assert target_pid is not None
    os.kill(int(running["pid"]), signal.SIGTERM)
    payload = _wait_for_terminal(status)
    assert payload["state"] == "FAILED"
    time.sleep(0.1)
    remaining = subprocess.run(
        ["ps", "-g", str(target_pid), "-o", "pid="],
        capture_output=True,
        text=True,
        check=False,
    ).stdout.split()
    assert not remaining
