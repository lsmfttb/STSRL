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
    tmp_path: Path,
    command: list[str],
    *,
    expected_seconds: int | None = None,
    env=None,
    resource_args: list[str] | None = None,
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
    if resource_args is not None:
        args.extend(resource_args)
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


def _resource_args(
    root: Path,
    *,
    batch_id: str,
    job_id: str,
    budget_mib: int = 100,
    request_mib: int = 100,
    wait_seconds: float = 0,
    worker_count: int | None = None,
    shard_count: int | None = None,
) -> list[str]:
    args = [
        "--resource-root",
        str(root),
        "--resource-memory-budget-mib",
        str(budget_mib),
        "--resource-memory-request-mib",
        str(request_mib),
        "--resource-batch-id",
        batch_id,
        "--resource-job-id",
        job_id,
        "--resource-wait-seconds",
        str(wait_seconds),
        "--resource-stage",
        "test-stage",
    ]
    if worker_count is not None and shard_count is not None:
        args.extend(
            [
                "--resource-worker-count",
                str(worker_count),
                "--resource-shard-count",
                str(shard_count),
            ]
        )
    return args


def _wait_for_target(status: Path) -> dict[str, object]:
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        if status.is_file():
            payload = json.loads(status.read_text(encoding="utf-8"))
            if payload["state"] == "RUNNING" and payload.get("target_pid"):
                return payload
        time.sleep(0.02)
    raise AssertionError(f"target did not start: {status}")


def _wait_for_resource_state(status: Path, expected: str) -> dict[str, object]:
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        if status.is_file():
            payload = json.loads(status.read_text(encoding="utf-8"))
            resource = payload.get("resource_admission")
            if isinstance(resource, dict) and resource.get("state") == expected:
                return payload
        time.sleep(0.02)
    raise AssertionError(f"resource state {expected!r} not observed: {status}")


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
    sys.platform == "win32", reason="resource admission uses POSIX file locking"
)
def test_resource_admission_waits_and_records_bounded_concurrency(
    tmp_path: Path,
) -> None:
    resource_root = tmp_path / "resource-admission"
    status_one, started_one = _start(
        tmp_path / "job-one",
        [sys.executable, "-c", "import time; time.sleep(1.2)"],
        resource_args=_resource_args(
            resource_root,
            batch_id="batch",
            job_id="shard-00",
            worker_count=16,
            shard_count=16,
        ),
    )
    assert started_one.returncode == 0, started_one.stderr
    running_one = _wait_for_target(status_one)

    status_two, started_two = _start(
        tmp_path / "job-two",
        [sys.executable, "-c", "pass"],
        resource_args=_resource_args(
            resource_root,
            batch_id="batch",
            job_id="shard-01",
            wait_seconds=3,
        ),
    )
    assert started_two.returncode == 0, started_two.stderr
    waiting_two = _wait_for_resource_state(status_two, "WAITING")
    assert waiting_two["resource_admission"]["state"] == "WAITING"
    first = _wait_for_terminal(status_one)
    second = _wait_for_terminal(status_two)

    assert first["state"] == "SUCCEEDED"
    assert second["state"] == "SUCCEEDED"
    admission = second["resource_admission"]
    assert admission["state"] == "RELEASED"
    assert admission["memory_budget_mib"] == 100
    assert admission["memory_request_mib"] == 100
    assert admission["admitted_concurrency"] == 1
    assert admission["worker_count"] is None
    assert admission["shard_count"] is None
    assert not list(resource_root.glob("lease-*.json"))
    assert running_one["resource_admission"]["worker_count"] == 16


@pytest.mark.skipif(
    sys.platform == "win32", reason="resource admission uses POSIX file locking"
)
def test_resource_admission_rejects_duplicate_active_batch_job(
    tmp_path: Path,
) -> None:
    resource_root = tmp_path / "resource-admission"
    resource = _resource_args(
        resource_root,
        batch_id="batch",
        job_id="shard-00",
        wait_seconds=2,
    )
    status_one, started_one = _start(
        tmp_path / "job-one",
        [sys.executable, "-c", "import time; time.sleep(1.2)"],
        resource_args=resource,
    )
    assert started_one.returncode == 0, started_one.stderr
    _wait_for_target(status_one)

    status_duplicate, started_duplicate = _start(
        tmp_path / "job-duplicate",
        [sys.executable, "-c", "raise SystemExit(99)"],
        resource_args=resource,
    )
    assert started_duplicate.returncode == 0, started_duplicate.stderr
    duplicate = _wait_for_terminal(status_duplicate)
    first = _wait_for_terminal(status_one)

    assert duplicate["state"] == "FAILED"
    assert duplicate["exit_code"] == 1
    assert duplicate["resource_admission"]["state"] == "REJECTED"
    assert "duplicate batch/job" in str(duplicate["startup_error"])
    assert first["state"] == "SUCCEEDED"
    assert not list(resource_root.glob("lease-*.json"))


@pytest.mark.skipif(
    sys.platform == "win32", reason="resource admission uses POSIX file locking"
)
def test_waiting_resource_admission_signal_is_cancelled(tmp_path: Path) -> None:
    resource_root = tmp_path / "resource-admission"
    holder_status, holder_started = _start(
        tmp_path / "job-holder",
        [sys.executable, "-c", "import time; time.sleep(1.2)"],
        resource_args=_resource_args(
            resource_root,
            batch_id="batch",
            job_id="holder",
        ),
    )
    assert holder_started.returncode == 0, holder_started.stderr
    _wait_for_target(holder_status)

    waiting_status, waiting_started = _start(
        tmp_path / "job-waiting",
        [sys.executable, "-c", "pass"],
        resource_args=_resource_args(
            resource_root,
            batch_id="batch",
            job_id="waiting",
            wait_seconds=5,
        ),
    )
    assert waiting_started.returncode == 0, waiting_started.stderr
    waiting = _wait_for_resource_state(waiting_status, "WAITING")
    os.kill(int(waiting["pid"]), signal.SIGTERM)

    cancelled = _wait_for_terminal(waiting_status)
    holder = _wait_for_terminal(holder_status)
    assert holder["state"] == "SUCCEEDED"
    assert cancelled["state"] == "FAILED"
    assert cancelled["exit_code"] == 143
    assert cancelled["resource_admission"]["state"] == "CANCELLED"
    assert "supervisor signal" in cancelled["resource_admission"]["reason"]
    assert not list(resource_root.glob("lease-*.json"))


@pytest.mark.skipif(
    sys.platform == "win32", reason="resource admission uses POSIX file locking"
)
def test_resource_lease_releases_after_failure_and_signal(
    tmp_path: Path,
) -> None:
    resource_root = tmp_path / "resource-admission"
    failed_status, failed_started = _start(
        tmp_path / "job-failed",
        [sys.executable, "-c", "raise SystemExit(7)"],
        resource_args=_resource_args(
            resource_root,
            batch_id="batch",
            job_id="failed",
        ),
    )
    assert failed_started.returncode == 0, failed_started.stderr
    failed = _wait_for_terminal(failed_status)
    assert failed["state"] == "FAILED"
    assert failed["exit_code"] == 7
    assert failed["resource_admission"]["state"] == "RELEASED"
    assert not list(resource_root.glob("lease-*.json"))

    signal_status, signal_started = _start(
        tmp_path / "job-signal",
        [sys.executable, "-c", "import time; time.sleep(30)"],
        resource_args=_resource_args(
            resource_root,
            batch_id="batch",
            job_id="signal",
        ),
    )
    assert signal_started.returncode == 0, signal_started.stderr
    running = _wait_for_target(signal_status)
    os.kill(int(running["pid"]), signal.SIGTERM)
    signaled = _wait_for_terminal(signal_status)
    assert signaled["state"] == "FAILED"
    assert signaled["exit_code"] == 143
    assert signaled["resource_admission"]["state"] == "RELEASED"
    assert "supervisor signal" in signaled["resource_admission"]["reason"]
    assert not list(resource_root.glob("lease-*.json"))

    successor_status, successor_started = _start(
        tmp_path / "job-successor",
        [sys.executable, "-c", "pass"],
        resource_args=_resource_args(
            resource_root,
            batch_id="batch",
            job_id="successor",
        ),
    )
    assert successor_started.returncode == 0, successor_started.stderr
    successor = _wait_for_terminal(successor_status)
    assert successor["state"] == "SUCCEEDED"
    assert not list(resource_root.glob("lease-*.json"))


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
