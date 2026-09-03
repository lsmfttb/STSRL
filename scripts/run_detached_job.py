#!/usr/bin/env python3
"""Start and inspect one small detached local job."""

from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
import time
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

STATES = {"RUNNING", "SUCCEEDED", "FAILED"}


def _timestamp() -> str:
    return datetime.now(UTC).isoformat()


def _atomic_write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    for attempt in range(50):
        try:
            os.replace(temporary, path)
            break
        except PermissionError:
            if attempt == 49:
                raise
            time.sleep(0.01)


def _status_payload(
    *,
    command: Sequence[str],
    cwd: Path,
    pid: int,
    started_at: str,
    expected_seconds: float | None,
    stdout_path: Path,
    stderr_path: Path,
    state: str,
    finished_at: str | None = None,
    exit_code: int | None = None,
    startup_error: str | None = None,
) -> dict[str, Any]:
    if state not in STATES:
        raise ValueError(f"invalid detached-job state: {state}")
    estimated = None
    if expected_seconds is not None:
        start = datetime.fromisoformat(started_at)
        estimated = (start + timedelta(seconds=expected_seconds)).isoformat()
    return {
        "command": list(command),
        "cwd": str(cwd),
        "pid": pid,
        "state": state,
        "started_at": started_at,
        "finished_at": finished_at,
        "exit_code": exit_code,
        "expected_seconds": expected_seconds,
        "estimated_finish_at": estimated,
        "stdout_path": str(stdout_path),
        "stderr_path": str(stderr_path),
        "startup_error": startup_error,
    }


def _creation_flags() -> int:
    if os.name != "nt":
        return 0
    return (
        subprocess.DETACHED_PROCESS
        | subprocess.CREATE_NEW_PROCESS_GROUP
        | subprocess.CREATE_NO_WINDOW
    )


def _terminate_target_group(target: subprocess.Popen[bytes]) -> None:
    """Terminate the detached target and all POSIX children in its process group."""

    if os.name == "nt":
        target.terminate()
        return
    os.killpg(target.pid, signal.SIGTERM)


def _supervise(
    *,
    status_path: Path,
    stdout_path: Path,
    stderr_path: Path,
    cwd: Path,
    command: Sequence[str],
    expected_seconds: float | None,
) -> int:
    pid = os.getpid()
    started_at = _timestamp()
    common = {
        "command": command,
        "cwd": cwd,
        "pid": pid,
        "started_at": started_at,
        "expected_seconds": expected_seconds,
        "stdout_path": stdout_path,
        "stderr_path": stderr_path,
    }
    try:
        stdout_path.parent.mkdir(parents=True, exist_ok=True)
        stderr_path.parent.mkdir(parents=True, exist_ok=True)
        with stdout_path.open("ab") as stdout, stderr_path.open("ab") as stderr:
            try:
                target = subprocess.Popen(
                    list(command),
                    cwd=str(cwd),
                    stdin=subprocess.DEVNULL,
                    stdout=stdout,
                    stderr=stderr,
                    env=None,
                    creationflags=_creation_flags(),
                    start_new_session=os.name != "nt",
                )
            except OSError as exc:
                _atomic_write(
                    status_path,
                    _status_payload(
                        **common,
                        state="FAILED",
                        finished_at=_timestamp(),
                        exit_code=getattr(exc, "errno", None) or 1,
                        startup_error=str(exc)[:500],
                    ),
                )
                return 1
            _atomic_write(status_path, _status_payload(**common, state="RUNNING"))

            def handle_supervisor_signal(signum: int, _frame: object) -> None:
                """Terminate the child and leave a terminal status on supervisor kill."""

                if target.poll() is None:
                    _terminate_target_group(target)
                try:
                    target.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    if os.name == "nt":
                        target.kill()
                    else:
                        os.killpg(target.pid, signal.SIGKILL)
                    target.wait()
                _atomic_write(
                    status_path,
                    _status_payload(
                        **common,
                        state="FAILED",
                        finished_at=_timestamp(),
                        exit_code=128 + signum,
                        startup_error=(
                            f"detached supervisor terminated by signal {signum}"
                        ),
                    ),
                )
                raise SystemExit(128 + signum)

            signal.signal(signal.SIGTERM, handle_supervisor_signal)
            exit_code = target.wait()
        _atomic_write(
            status_path,
            _status_payload(
                **common,
                state="SUCCEEDED" if exit_code == 0 else "FAILED",
                finished_at=_timestamp(),
                exit_code=exit_code,
            ),
        )
        return exit_code
    except BaseException as exc:  # noqa: BLE001 - supervisor must record all failures
        _atomic_write(
            status_path,
            _status_payload(
                **common,
                state="FAILED",
                finished_at=_timestamp(),
                exit_code=1,
                startup_error=str(exc)[:500],
            ),
        )
        return 1


def _start(args: argparse.Namespace) -> int:
    if not args.command:
        raise SystemExit("start requires a command after --")
    status_path = args.status.resolve()
    stdout_path = args.stdout.resolve()
    stderr_path = args.stderr.resolve()
    cwd = (args.cwd or Path.cwd()).resolve()
    if not cwd.is_dir():
        raise SystemExit(f"--cwd is not a directory: {cwd}")
    command = args.command[1:] if args.command[:1] == ["--"] else list(args.command)
    supervisor_args = [
        sys.executable,
        str(Path(__file__).resolve()),
        "--supervise",
        "--status",
        str(status_path),
        "--stdout",
        str(stdout_path),
        "--stderr",
        str(stderr_path),
        "--cwd",
        str(cwd),
    ]
    if args.expected_seconds is not None:
        supervisor_args.extend(["--expected-seconds", str(args.expected_seconds)])
    supervisor_args.append("--")
    supervisor_args.extend(command)
    supervisor = subprocess.Popen(
        supervisor_args,
        cwd=str(cwd),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        env=None,
        creationflags=_creation_flags(),
        start_new_session=os.name != "nt",
    )
    deadline = time.monotonic() + 2.0
    while not status_path.exists() and time.monotonic() < deadline:
        time.sleep(0.01)
    if supervisor.poll() is not None and not status_path.exists():
        raise SystemExit("detached supervisor exited before writing status")
    return 0


def _supervisor_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--status", type=Path, required=True)
    parser.add_argument("--stdout", type=Path, required=True)
    parser.add_argument("--stderr", type=Path, required=True)
    parser.add_argument("--cwd", type=Path, required=True)
    parser.add_argument("--expected-seconds", type=float, default=None)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    return parser


def _start_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--status", type=Path, required=True)
    parser.add_argument("--stdout", type=Path, required=True)
    parser.add_argument("--stderr", type=Path, required=True)
    parser.add_argument("--cwd", type=Path)
    parser.add_argument("--expected-seconds", type=float, default=None)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    values = list(sys.argv[1:] if argv is None else argv)
    if not values:
        raise SystemExit("expected start or status")
    mode, values = values[0], values[1:]
    if mode == "--supervise":
        args = _supervisor_parser().parse_args(values)
        command = args.command[1:] if args.command[:1] == ["--"] else args.command
        return _supervise(
            status_path=args.status,
            stdout_path=args.stdout,
            stderr_path=args.stderr,
            cwd=args.cwd,
            command=command,
            expected_seconds=args.expected_seconds,
        )
    if mode == "start":
        return _start(_start_parser().parse_args(values))
    if mode != "status":
        raise SystemExit(f"unknown command: {mode}")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--status", type=Path, required=True)
    args = parser.parse_args(values)
    payload = json.loads(args.status.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("state") not in STATES:
        raise SystemExit("status file is not a detached-job status document")
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
