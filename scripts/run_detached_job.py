#!/usr/bin/env python3
"""Start and inspect one small detached local job."""

from __future__ import annotations

import argparse
import errno
import json
import math
import os
import signal
import subprocess
import sys
import time
from collections.abc import Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import uuid4

try:
    import fcntl
except ImportError:  # pragma: no cover - exercised only on Windows
    fcntl = None

STATES = {"RUNNING", "SUCCEEDED", "FAILED"}
_RESOURCE_POLL_SECONDS = 0.2
_RESOURCE_LEASE_SCHEMA_ID = "stsrl-detached-resource-lease-v1"
_RUNTIME_GUARD_EXIT_CODE = 1
_TARGET_TERMINATION_GRACE_SECONDS = 1.0
_NON_RESIDENT_PROCESS_STATES = frozenset({"Z", "X"})


class ResourceAdmissionError(RuntimeError):
    """A requested detached-job resource lease could not be admitted."""

    def __init__(
        self,
        message: str,
        *,
        status: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.status = status


@dataclass(frozen=True)
class ResourceAdmissionConfig:
    """Explicit resource reservation and duplicate-job identity."""

    root: Path
    memory_budget_mib: int
    memory_request_mib: int
    batch_id: str
    job_id: str
    runtime_rss_limit_mib: int | None = None
    runtime_memavailable_floor_mib: int | None = None
    runtime_sample_seconds: float = _RESOURCE_POLL_SECONDS
    wait_seconds: float = 0.0
    stage: str | None = None
    worker_count: int | None = None
    shard_count: int | None = None

    def __post_init__(self) -> None:
        if fcntl is None:
            raise ValueError("resource admission requires POSIX file locking")
        if (
            isinstance(self.memory_budget_mib, bool)
            or not isinstance(self.memory_budget_mib, int)
            or self.memory_budget_mib <= 0
        ):
            raise ValueError("resource memory budget must be positive")
        if (
            isinstance(self.memory_request_mib, bool)
            or not isinstance(self.memory_request_mib, int)
            or self.memory_request_mib <= 0
        ):
            raise ValueError("resource memory request must be positive")
        if self.memory_request_mib > self.memory_budget_mib:
            raise ValueError("resource memory request cannot exceed its budget")
        if (
            isinstance(self.runtime_rss_limit_mib, bool)
            or not isinstance(self.runtime_rss_limit_mib, int)
            or self.runtime_rss_limit_mib <= 0
        ):
            raise ValueError("resource admission requires a positive runtime RSS limit")
        if self.runtime_memavailable_floor_mib is not None and (
            isinstance(self.runtime_memavailable_floor_mib, bool)
            or not isinstance(self.runtime_memavailable_floor_mib, int)
            or self.runtime_memavailable_floor_mib <= 0
        ):
            raise ValueError("runtime MemAvailable floor must be positive")
        if not self.batch_id:
            raise ValueError("resource batch id must be non-empty")
        if not self.job_id:
            raise ValueError("resource job id must be non-empty")
        if not math.isfinite(self.wait_seconds) or self.wait_seconds < 0:
            raise ValueError("resource wait seconds must be finite and non-negative")
        if (
            not isinstance(self.runtime_sample_seconds, (int, float))
            or isinstance(self.runtime_sample_seconds, bool)
            or not math.isfinite(self.runtime_sample_seconds)
            or self.runtime_sample_seconds <= 0
        ):
            raise ValueError("runtime sample seconds must be finite and positive")
        if (self.worker_count is None) != (self.shard_count is None):
            raise ValueError(
                "resource worker and shard counts must be supplied together"
            )
        if self.worker_count is not None and (
            self.worker_count <= 0 or self.shard_count is None or self.shard_count <= 0
        ):
            raise ValueError("resource worker and shard counts must be positive")

    def to_status(
        self,
        *,
        state: str,
        reason: str,
        active_memory_mib: int = 0,
        active_lease_count: int = 0,
        lease_id: str | None = None,
        target_pid: int | None = None,
        admitted_concurrency: int | None = None,
        released_at: str | None = None,
        runtime_guard: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if runtime_guard is None:
            runtime_guard = {
                "enabled": True,
                "state": "ARMED",
                "reason": "runtime tripwire armed",
                "rss_limit_mib": self.runtime_rss_limit_mib,
                "memavailable_floor_mib": self.runtime_memavailable_floor_mib,
                "sample_interval_seconds": self.runtime_sample_seconds,
                "observed_rss_mib": None,
                "peak_rss_mib": None,
                "observed_memavailable_mib": None,
                "lowest_memavailable_mib": None,
                "sample_count": 0,
                "last_sample_at": None,
                "trigger_reason": None,
                "triggered_at": None,
                "sample_error": None,
            }
        return {
            "enabled": True,
            "state": state,
            "reason": reason,
            "root": str(self.root),
            "batch_id": self.batch_id,
            "job_id": self.job_id,
            "stage": self.stage,
            "memory_budget_mib": self.memory_budget_mib,
            "memory_request_mib": self.memory_request_mib,
            "projected_memory_mib": active_memory_mib + self.memory_request_mib,
            "active_memory_mib": active_memory_mib,
            "active_lease_count": active_lease_count,
            "admitted_concurrency": admitted_concurrency,
            "worker_count": self.worker_count,
            "shard_count": self.shard_count,
            "lease_id": lease_id,
            "target_pid": target_pid,
            "released_at": released_at,
            "runtime_guard": runtime_guard,
        }


class RuntimeGuardObservationError(RuntimeError):
    """The configured runtime guard cannot obtain a trustworthy observation."""


@dataclass
class _RuntimeGuard:
    config: ResourceAdmissionConfig
    state: str = "ARMED"
    state_reason: str = "runtime tripwire armed"
    observed_rss_mib: int | None = None
    peak_rss_mib: int | None = None
    observed_memavailable_mib: int | None = None
    lowest_memavailable_mib: int | None = None
    sample_count: int = 0
    last_sample_at: str | None = None
    trigger_reason: str | None = None
    triggered_at: str | None = None
    sample_error: str | None = None

    def to_status(self) -> dict[str, Any]:
        return {
            "enabled": True,
            "state": self.state,
            "reason": self.state_reason,
            "rss_limit_mib": self.config.runtime_rss_limit_mib,
            "memavailable_floor_mib": self.config.runtime_memavailable_floor_mib,
            "sample_interval_seconds": self.config.runtime_sample_seconds,
            "observed_rss_mib": self.observed_rss_mib,
            "peak_rss_mib": self.peak_rss_mib,
            "observed_memavailable_mib": self.observed_memavailable_mib,
            "lowest_memavailable_mib": self.lowest_memavailable_mib,
            "sample_count": self.sample_count,
            "last_sample_at": self.last_sample_at,
            "trigger_reason": self.trigger_reason,
            "triggered_at": self.triggered_at,
            "sample_error": self.sample_error,
        }

    def observe(self, target_pid: int) -> bool:
        sampled_at = _timestamp()
        self.last_sample_at = sampled_at
        self.sample_count += 1
        try:
            rss_mib = _read_process_group_rss_mib(target_pid)
            memavailable_mib = (
                _read_memavailable_mib()
                if self.config.runtime_memavailable_floor_mib is not None
                else None
            )
        except RuntimeGuardObservationError as exc:
            self.sample_error = str(exc)[:500]
            self._trip(f"runtime guard observation failed closed: {self.sample_error}")
            return True

        self.observed_rss_mib = rss_mib
        self.peak_rss_mib = (
            rss_mib if self.peak_rss_mib is None else max(self.peak_rss_mib, rss_mib)
        )
        if memavailable_mib is not None:
            self.observed_memavailable_mib = memavailable_mib
            self.lowest_memavailable_mib = (
                memavailable_mib
                if self.lowest_memavailable_mib is None
                else min(self.lowest_memavailable_mib, memavailable_mib)
            )

        if rss_mib > self.config.runtime_rss_limit_mib:
            self._trip(
                "target process-group RSS "
                f"{rss_mib} MiB exceeded runtime limit "
                f"{self.config.runtime_rss_limit_mib} MiB"
            )
            return True
        floor = self.config.runtime_memavailable_floor_mib
        if floor is not None and memavailable_mib < floor:
            self._trip(
                "WSL MemAvailable "
                f"{memavailable_mib} MiB fell below runtime floor {floor} MiB"
            )
            return True
        self.state = "MONITORING"
        self.state_reason = "runtime tripwire monitoring target process group"
        return False

    def mark_completed(self) -> None:
        if self.state != "TRIGGERED":
            self.state = "COMPLETED"
            self.state_reason = "target completed without a runtime tripwire"

    def mark_cancelled(self) -> None:
        if self.state != "TRIGGERED":
            self.state = "CANCELLED"
            self.state_reason = "runtime tripwire cancelled by supervisor signal"

    def mark_not_admitted(self) -> None:
        if self.state != "TRIGGERED":
            self.state = "NOT_ADMITTED"
            self.state_reason = (
                "runtime tripwire was not armed because admission failed"
            )

    def mark_failed(self) -> None:
        if self.state in {"ARMED", "MONITORING"}:
            self.state = "SUPERVISOR_FAILED"
            self.state_reason = "supervisor or target failure before runtime completion"

    def _trip(self, reason: str) -> None:
        self.state = "TRIGGERED"
        self.state_reason = reason
        self.trigger_reason = reason
        self.triggered_at = _timestamp()


@dataclass
class _ResourceLease:
    config: ResourceAdmissionConfig
    lease_id: str
    path: Path
    file: Any
    active_memory_mib_at_admission: int
    active_lease_count_at_admission: int
    admitted_at: str
    target_pid: int | None = None
    released_at: str | None = None
    released: bool = False

    @property
    def admitted_concurrency(self) -> int:
        return self.active_lease_count_at_admission + 1

    def status(
        self,
        *,
        state: str,
        reason: str,
        runtime_guard: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return self.config.to_status(
            state=state,
            reason=reason,
            active_memory_mib=self.active_memory_mib_at_admission,
            active_lease_count=self.active_lease_count_at_admission,
            lease_id=self.lease_id,
            target_pid=self.target_pid,
            admitted_concurrency=self.admitted_concurrency,
            released_at=self.released_at,
            runtime_guard=runtime_guard,
        ) | {"admitted_at": self.admitted_at, "released": self.released}

    def update_target_pid(self, target_pid: int) -> None:
        self.target_pid = target_pid
        self.file.seek(0)
        self.file.truncate()
        self.file.write(
            json.dumps(
                {
                    "schema_id": _RESOURCE_LEASE_SCHEMA_ID,
                    "lease_id": self.lease_id,
                    "owner_pid": os.getpid(),
                    "target_pid": target_pid,
                    "batch_id": self.config.batch_id,
                    "job_id": self.config.job_id,
                    "stage": self.config.stage,
                    "memory_budget_mib": self.config.memory_budget_mib,
                    "memory_request_mib": self.config.memory_request_mib,
                    "runtime_rss_limit_mib": self.config.runtime_rss_limit_mib,
                    "runtime_memavailable_floor_mib": (
                        self.config.runtime_memavailable_floor_mib
                    ),
                    "runtime_sample_seconds": self.config.runtime_sample_seconds,
                    "worker_count": self.config.worker_count,
                    "shard_count": self.config.shard_count,
                    "admitted_at": self.admitted_at,
                },
                sort_keys=True,
            )
            + "\n"
        )
        self.file.flush()
        os.fsync(self.file.fileno())

    def release(self) -> str | None:
        """Drop the lease lock and file, retaining stale-file recovery."""

        if self.released:
            return None
        release_error: str | None = None
        self.released_at = _timestamp()
        try:
            with _resource_registry_lock(self.config.root):
                try:
                    self.path.unlink(missing_ok=True)
                except OSError as exc:
                    release_error = str(exc)[:500]
        except OSError as exc:
            release_error = str(exc)[:500]
        finally:
            try:
                fcntl.flock(self.file.fileno(), fcntl.LOCK_UN)
            except OSError as exc:
                if release_error is None:
                    release_error = str(exc)[:500]
            try:
                self.file.close()
            except OSError as exc:
                if release_error is None:
                    release_error = str(exc)[:500]
            self.released = True
        return release_error


def _timestamp() -> str:
    return datetime.now(UTC).isoformat()


def _proc_stat_process_group_id(stat_path: Path) -> int:
    try:
        contents = stat_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise RuntimeGuardObservationError(
            f"cannot read process-group stat {stat_path}: {exc}"
        ) from exc
    closing_paren = contents.rfind(")")
    if closing_paren < 0:
        raise RuntimeGuardObservationError(f"malformed process-group stat {stat_path}")
    fields = contents[closing_paren + 2 :].split()
    if len(fields) < 3:
        raise RuntimeGuardObservationError(f"malformed process-group stat {stat_path}")
    try:
        return int(fields[2])
    except ValueError as exc:
        raise RuntimeGuardObservationError(
            f"invalid process-group id in {stat_path}"
        ) from exc


def _proc_stat_process_state(stat_path: Path) -> str:
    try:
        contents = stat_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise RuntimeGuardObservationError(
            f"cannot read process state {stat_path}: {exc}"
        ) from exc
    closing_paren = contents.rfind(")")
    if closing_paren < 0:
        raise RuntimeGuardObservationError(f"malformed process state {stat_path}")
    fields = contents[closing_paren + 2 :].split()
    if not fields:
        raise RuntimeGuardObservationError(f"malformed process state {stat_path}")
    return fields[0]


def _proc_status_rss_kib(status_path: Path) -> int:
    try:
        lines = status_path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise RuntimeGuardObservationError(
            f"cannot read process memory status {status_path}: {exc}"
        ) from exc
    for line in lines:
        if line.startswith("VmRSS:"):
            fields = line.split()
            if len(fields) >= 2:
                try:
                    return int(fields[1])
                except ValueError as exc:
                    raise RuntimeGuardObservationError(
                        f"invalid VmRSS value in {status_path}"
                    ) from exc
    raise RuntimeGuardObservationError(f"VmRSS is missing from {status_path}")


def _read_process_group_rss_mib(target_pid: int) -> int:
    """Return the target process group's aggregate resident memory in MiB."""

    proc_root = Path("/proc")
    if proc_root.is_dir():
        target_stat = proc_root / str(target_pid) / "stat"
        try:
            process_group_id = _proc_stat_process_group_id(target_stat)
        except RuntimeGuardObservationError:
            if not target_stat.exists():
                return 0
            raise
        total_kib = 0
        members = 0
        for stat_path in proc_root.glob("[0-9]*/stat"):
            try:
                if _proc_stat_process_group_id(stat_path) != process_group_id:
                    continue
                total_kib += _proc_status_rss_kib(stat_path.with_name("status"))
                members += 1
            except RuntimeGuardObservationError:
                status_path = stat_path.with_name("status")
                if not stat_path.exists() or not status_path.exists():
                    continue
                try:
                    process_state = _proc_stat_process_state(stat_path)
                except RuntimeGuardObservationError:
                    if not stat_path.exists():
                        continue
                    raise
                if process_state in _NON_RESIDENT_PROCESS_STATES:
                    continue
                raise
        if members == 0:
            return 0
        return math.ceil(total_kib / 1024)

    try:
        result = subprocess.run(
            ["ps", "-axo", "pid=,pgid=,rss="],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as exc:
        raise RuntimeGuardObservationError(
            f"cannot execute ps for process-group RSS: {exc}"
        ) from exc
    if result.returncode != 0:
        raise RuntimeGuardObservationError(
            f"ps failed while reading process-group RSS: {result.stderr.strip()}"
        )
    rows: list[tuple[int, int, int]] = []
    for line in result.stdout.splitlines():
        fields = line.split()
        if len(fields) != 3:
            continue
        try:
            rows.append(tuple(int(field) for field in fields))
        except ValueError:
            continue
    target_row = next((row for row in rows if row[0] == target_pid), None)
    if target_row is None:
        return 0
    process_group_id = target_row[1]
    total_kib = sum(row[2] for row in rows if row[1] == process_group_id)
    return math.ceil(total_kib / 1024)


def _read_memavailable_mib() -> int:
    """Read Linux/WSL's available-memory estimate in MiB."""

    meminfo_path = Path("/proc/meminfo")
    try:
        lines = meminfo_path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise RuntimeGuardObservationError(
            f"cannot read MemAvailable from {meminfo_path}: {exc}"
        ) from exc
    for line in lines:
        if line.startswith("MemAvailable:"):
            fields = line.split()
            if len(fields) >= 2:
                try:
                    return math.ceil(int(fields[1]) / 1024)
                except ValueError as exc:
                    raise RuntimeGuardObservationError(
                        "invalid MemAvailable value in /proc/meminfo"
                    ) from exc
    raise RuntimeGuardObservationError("MemAvailable is missing from /proc/meminfo")


@contextmanager
def _resource_registry_lock(root: Path):
    """Serialize resource-lease inspection and creation for one root."""

    if fcntl is None:  # pragma: no cover - guarded by ResourceAdmissionConfig
        raise OSError("resource admission requires POSIX file locking")
    root.mkdir(parents=True, exist_ok=True)
    with (root / ".stsrl-resource-admission.lock").open("a+", encoding="utf-8") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock.fileno(), fcntl.LOCK_UN)


def _read_active_resource_leases(root: Path) -> list[dict[str, Any]]:
    """Read live leases and remove files whose kernel lock is no longer held."""

    if fcntl is None:  # pragma: no cover - guarded by ResourceAdmissionConfig
        raise OSError("resource admission requires POSIX file locking")
    active: list[dict[str, Any]] = []
    for path in sorted(root.glob("lease-*.json")):
        try:
            with path.open("r+", encoding="utf-8") as lease_file:
                try:
                    fcntl.flock(lease_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                except OSError as exc:
                    if exc.errno not in (errno.EACCES, errno.EAGAIN):
                        raise
                    lease_file.seek(0)
                    try:
                        metadata = json.load(lease_file)
                    except (json.JSONDecodeError, OSError) as parse_exc:
                        raise ResourceAdmissionError(
                            f"active resource lease is unreadable: {path}",
                        ) from parse_exc
                    if not isinstance(metadata, dict):
                        raise ResourceAdmissionError(
                            f"active resource lease is malformed: {path}"
                        )
                    active.append(metadata)
                else:
                    fcntl.flock(lease_file.fileno(), fcntl.LOCK_UN)
                    path.unlink(missing_ok=True)
        except FileNotFoundError:
            continue
    return active


def _resource_active_memory(leases: Sequence[dict[str, Any]]) -> int:
    total = 0
    for lease in leases:
        request = lease.get("memory_request_mib")
        if isinstance(request, bool) or not isinstance(request, int) or request <= 0:
            raise ResourceAdmissionError(
                "active resource lease has invalid memory request"
            )
        total += request
    return total


def _resource_wait_status(
    config: ResourceAdmissionConfig,
    *,
    reason: str,
    active_leases: Sequence[dict[str, Any]],
    state: str = "WAITING",
) -> dict[str, Any]:
    active_memory = _resource_active_memory(active_leases)
    return config.to_status(
        state=state,
        reason=reason,
        active_memory_mib=active_memory,
        active_lease_count=len(active_leases),
        admitted_concurrency=len(active_leases),
    )


def _acquire_resource_lease(
    config: ResourceAdmissionConfig,
    *,
    command: Sequence[str],
    cwd: Path,
    status_path: Path,
    on_wait: Any,
    cancelled: Any,
) -> _ResourceLease:
    """Admit one explicit reservation, waiting only up to its configured limit."""

    deadline = time.monotonic() + config.wait_seconds
    while True:
        if cancelled():
            raise ResourceAdmissionError(
                "resource admission cancelled by supervisor signal",
            )
        with _resource_registry_lock(config.root):
            active = _read_active_resource_leases(config.root)
            duplicate = next(
                (
                    lease
                    for lease in active
                    if lease.get("batch_id") == config.batch_id
                    and lease.get("job_id") == config.job_id
                ),
                None,
            )
            active_memory = _resource_active_memory(active)
            if duplicate is not None:
                status = _resource_wait_status(
                    config,
                    reason=(
                        "duplicate batch/job is already admitted: "
                        f"{config.batch_id}/{config.job_id}"
                    ),
                    active_leases=active,
                    state="REJECTED",
                )
                raise ResourceAdmissionError(status["reason"], status=status)
            if active_memory + config.memory_request_mib <= config.memory_budget_mib:
                lease_id = uuid4().hex
                lease_path = config.root / f"lease-{lease_id}.json"
                lease_file = lease_path.open("x+", encoding="utf-8")
                try:
                    fcntl.flock(lease_file.fileno(), fcntl.LOCK_EX)
                    admitted_at = _timestamp()
                    metadata = {
                        "schema_id": _RESOURCE_LEASE_SCHEMA_ID,
                        "lease_id": lease_id,
                        "owner_pid": os.getpid(),
                        "target_pid": None,
                        "batch_id": config.batch_id,
                        "job_id": config.job_id,
                        "stage": config.stage,
                        "memory_budget_mib": config.memory_budget_mib,
                        "memory_request_mib": config.memory_request_mib,
                        "runtime_rss_limit_mib": config.runtime_rss_limit_mib,
                        "runtime_memavailable_floor_mib": (
                            config.runtime_memavailable_floor_mib
                        ),
                        "runtime_sample_seconds": config.runtime_sample_seconds,
                        "worker_count": config.worker_count,
                        "shard_count": config.shard_count,
                        "command": list(command),
                        "cwd": str(cwd),
                        "status_path": str(status_path),
                        "admitted_at": admitted_at,
                    }
                    lease_file.write(json.dumps(metadata, sort_keys=True) + "\n")
                    lease_file.flush()
                    os.fsync(lease_file.fileno())
                except BaseException:
                    try:
                        fcntl.flock(lease_file.fileno(), fcntl.LOCK_UN)
                    finally:
                        lease_file.close()
                        lease_path.unlink(missing_ok=True)
                    raise
                return _ResourceLease(
                    config=config,
                    lease_id=lease_id,
                    path=lease_path,
                    file=lease_file,
                    active_memory_mib_at_admission=active_memory,
                    active_lease_count_at_admission=len(active),
                    admitted_at=admitted_at,
                )
            status = _resource_wait_status(
                config,
                reason=(
                    "resource memory budget exhausted: "
                    f"{active_memory}+{config.memory_request_mib} > "
                    f"{config.memory_budget_mib} MiB"
                ),
                active_leases=active,
            )
        on_wait(status)
        if config.wait_seconds == 0 or time.monotonic() >= deadline:
            status["state"] = "REJECTED"
            status["reason"] = (
                f"{status['reason']}; admission wait limit "
                f"{config.wait_seconds:g}s expired"
            )
            raise ResourceAdmissionError(status["reason"], status=status)
        time.sleep(min(_RESOURCE_POLL_SECONDS, max(0.0, deadline - time.monotonic())))


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
    target_pid: int | None = None,
    resource_admission: dict[str, Any] | None = None,
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
        "target_pid": target_pid,
        "state": state,
        "started_at": started_at,
        "finished_at": finished_at,
        "exit_code": exit_code,
        "expected_seconds": expected_seconds,
        "estimated_finish_at": estimated,
        "stdout_path": str(stdout_path),
        "stderr_path": str(stderr_path),
        "startup_error": startup_error,
        "resource_admission": resource_admission,
    }


def _creation_flags() -> int:
    if os.name != "nt":
        return 0
    return (
        subprocess.DETACHED_PROCESS
        | subprocess.CREATE_NEW_PROCESS_GROUP
        | subprocess.CREATE_NO_WINDOW
    )


def _terminate_target_group(
    target: subprocess.Popen[bytes], signum: int = signal.SIGTERM
) -> None:
    """Terminate the detached target and all POSIX children in its process group."""

    if os.name == "nt":
        if signum == signal.SIGKILL:
            target.kill()
        else:
            target.terminate()
        return
    os.killpg(target.pid, signum)


def _terminate_and_reap_target_group(target: subprocess.Popen[bytes]) -> int:
    """Reap a terminated target, escalating once if it ignores SIGTERM.

    This is called only from the supervisor's outer wait path. Signal handlers
    and runtime observations may request group termination, but never reap the
    target themselves.
    """

    try:
        return target.wait(timeout=_TARGET_TERMINATION_GRACE_SECONDS)
    except subprocess.TimeoutExpired:
        try:
            _terminate_target_group(target, signal.SIGKILL)
        except (ProcessLookupError, OSError):
            pass
        return target.wait()


def _wait_for_target_with_runtime_guard(
    target: subprocess.Popen[bytes],
    runtime_guard: _RuntimeGuard | None,
    *,
    cancelled: Any,
) -> tuple[int, bool]:
    """Wait for a target and trip the guard without reentrant signal handling."""

    if runtime_guard is None:
        return target.wait(), False
    while True:
        if cancelled():
            runtime_guard.mark_cancelled()
            return _terminate_and_reap_target_group(target), False
        try:
            exit_code = target.wait(timeout=runtime_guard.config.runtime_sample_seconds)
        except subprocess.TimeoutExpired:
            if cancelled():
                runtime_guard.mark_cancelled()
                return _terminate_and_reap_target_group(target), False
            if not runtime_guard.observe(target.pid):
                continue
            try:
                _terminate_target_group(target)
            except (ProcessLookupError, OSError):
                # The target may have exited between observation and cleanup;
                # this outer wait path still owns the single reap.
                pass
            return _terminate_and_reap_target_group(target), True
        except InterruptedError:
            continue
        else:
            if cancelled():
                runtime_guard.mark_cancelled()
            else:
                runtime_guard.mark_completed()
            return exit_code, False


def _supervise(
    *,
    status_path: Path,
    stdout_path: Path,
    stderr_path: Path,
    cwd: Path,
    command: Sequence[str],
    expected_seconds: float | None,
    resource_config: ResourceAdmissionConfig | None = None,
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
    target: subprocess.Popen[bytes] | None = None
    target_reaped = False
    lease: _ResourceLease | None = None
    supervisor_signal: int | None = None
    runtime_guard = (
        _RuntimeGuard(resource_config) if resource_config is not None else None
    )
    resource_status = (
        {
            "enabled": False,
            "state": "DISABLED",
            "reason": "resource admission was not requested",
        }
        if resource_config is None
        else resource_config.to_status(
            state="WAITING",
            reason="awaiting explicit resource admission",
            runtime_guard=runtime_guard.to_status(),
        )
    )
    terminal_state = "FAILED"
    terminal_exit_code = 1
    terminal_error: str | None = None

    def handle_supervisor_signal(signum: int, _frame: object) -> None:
        """Record the signal and best-effort terminate the target group."""

        nonlocal supervisor_signal
        supervisor_signal = signum
        if target is not None:
            try:
                _terminate_target_group(target)
            except (ProcessLookupError, OSError):
                # The outer wait owns child reaping.  The target may have
                # exited between signal delivery and this best-effort group
                # termination.
                pass

    try:
        stdout_path.parent.mkdir(parents=True, exist_ok=True)
        stderr_path.parent.mkdir(parents=True, exist_ok=True)
        signal.signal(signal.SIGTERM, handle_supervisor_signal)
        _atomic_write(
            status_path,
            _status_payload(
                **common,
                state="RUNNING",
                target_pid=None,
                resource_admission=resource_status,
            ),
        )
        with stdout_path.open("ab") as stdout, stderr_path.open("ab") as stderr:
            if resource_config is not None:
                try:
                    lease = _acquire_resource_lease(
                        resource_config,
                        command=command,
                        cwd=cwd,
                        status_path=status_path,
                        on_wait=lambda status: _atomic_write(
                            status_path,
                            _status_payload(
                                **common,
                                state="RUNNING",
                                target_pid=None,
                                resource_admission=status,
                            ),
                        ),
                        cancelled=lambda: supervisor_signal is not None,
                    )
                except ResourceAdmissionError as exc:
                    resource_status = exc.status or resource_status
                    raise
                resource_status = lease.status(
                    state="ADMITTED",
                    reason="resource reservation admitted",
                    runtime_guard=runtime_guard.to_status(),
                )
                _atomic_write(
                    status_path,
                    _status_payload(
                        **common,
                        state="RUNNING",
                        target_pid=None,
                        resource_admission=resource_status,
                    ),
                )
            if supervisor_signal is not None:
                terminal_exit_code = 128 + supervisor_signal
                terminal_error = (
                    f"detached supervisor terminated by signal {supervisor_signal}"
                )
                if runtime_guard is not None:
                    runtime_guard.mark_cancelled()
            else:
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
                    terminal_exit_code = getattr(exc, "errno", None) or 1
                    terminal_error = str(exc)[:500]
                    if runtime_guard is not None:
                        runtime_guard.mark_failed()
                else:
                    if lease is not None:
                        lease.update_target_pid(target.pid)
                        resource_status = lease.status(
                            state="ADMITTED",
                            reason="target started under resource reservation",
                            runtime_guard=runtime_guard.to_status(),
                        )
                    _atomic_write(
                        status_path,
                        _status_payload(
                            **common,
                            state="RUNNING",
                            target_pid=target.pid,
                            resource_admission=resource_status,
                        ),
                    )
                    exit_code, runtime_tripped = _wait_for_target_with_runtime_guard(
                        target,
                        runtime_guard,
                        cancelled=lambda: supervisor_signal is not None,
                    )
                    target_reaped = True
                    terminal_exit_code = exit_code
                    if runtime_tripped:
                        terminal_state = "FAILED"
                        terminal_exit_code = (
                            128 + supervisor_signal
                            if supervisor_signal is not None
                            else _RUNTIME_GUARD_EXIT_CODE
                        )
                        terminal_error = (
                            "runtime resource guard tripped: "
                            f"{runtime_guard.trigger_reason}"
                        )
                    elif supervisor_signal is not None:
                        terminal_state = "FAILED"
                        terminal_exit_code = 128 + supervisor_signal
                        terminal_error = f"detached supervisor terminated by signal {supervisor_signal}"
                    else:
                        terminal_state = "SUCCEEDED" if exit_code == 0 else "FAILED"
        if lease is None and resource_config is not None:
            resource_status = resource_config.to_status(
                state="CANCELLED" if supervisor_signal is not None else "REJECTED",
                reason=(
                    "resource admission cancelled by supervisor signal"
                    if supervisor_signal is not None
                    else "resource admission was not granted"
                ),
            ) | {"released": False}
    except ResourceAdmissionError as exc:
        terminal_state = "FAILED"
        terminal_exit_code = (
            128 + supervisor_signal if supervisor_signal is not None else 1
        )
        terminal_error = str(exc)[:500]
        if runtime_guard is not None:
            runtime_guard.mark_not_admitted()
            resource_status = dict(resource_status)
            resource_status["runtime_guard"] = runtime_guard.to_status()
    except BaseException as exc:  # noqa: BLE001 - supervisor must record all failures
        terminal_state = "FAILED"
        terminal_exit_code = (
            128 + supervisor_signal if supervisor_signal is not None else 1
        )
        terminal_error = str(exc)[:500]
        if runtime_guard is not None:
            runtime_guard.mark_failed()
    finally:
        if target is not None and not target_reaped:
            try:
                _terminate_target_group(target)
            except (ProcessLookupError, OSError):
                pass
            try:
                _terminate_and_reap_target_group(target)
            except (OSError, subprocess.SubprocessError):
                pass
            target_reaped = True
        if runtime_guard is not None and lease is not None:
            if supervisor_signal is not None and runtime_guard.state != "TRIGGERED":
                runtime_guard.mark_cancelled()
            elif runtime_guard.state in {"ARMED", "MONITORING"}:
                runtime_guard.mark_failed()
        if lease is not None:
            release_error = lease.release()
            resource_status = lease.status(
                state="RELEASED",
                reason=(
                    "lease released after runtime resource guard"
                    if runtime_guard is not None and runtime_guard.state == "TRIGGERED"
                    else "lease released after supervisor signal"
                    if supervisor_signal is not None
                    else "lease released after supervisor or target failure"
                    if runtime_guard is not None
                    and runtime_guard.state == "SUPERVISOR_FAILED"
                    else "lease released after target completion"
                ),
                runtime_guard=(
                    runtime_guard.to_status() if runtime_guard is not None else None
                ),
            )
            if release_error is not None:
                resource_status["release_error"] = release_error
        elif resource_config is not None and resource_status.get("state") in {
            "WAITING",
            "REJECTED",
        }:
            if runtime_guard is not None:
                runtime_guard.mark_not_admitted()
            resource_status = dict(resource_status)
            if supervisor_signal is not None:
                resource_status["state"] = "CANCELLED"
                resource_status["reason"] = (
                    "resource admission cancelled by supervisor signal"
                )
            elif resource_status.get("state") == "WAITING":
                resource_status["state"] = "REJECTED"
                resource_status["reason"] = terminal_error or (
                    "resource admission was not granted"
                )
            resource_status["runtime_guard"] = (
                runtime_guard.to_status() if runtime_guard is not None else None
            )
            resource_status["released"] = False
        try:
            _atomic_write(
                status_path,
                _status_payload(
                    **common,
                    state=terminal_state,
                    target_pid=target.pid if target is not None else None,
                    finished_at=_timestamp(),
                    exit_code=terminal_exit_code,
                    startup_error=terminal_error,
                    resource_admission=resource_status,
                ),
            )
        except BaseException:  # noqa: BLE001 - preserve the supervisor result
            terminal_error = terminal_error or "terminal status write failed"
    return terminal_exit_code


def _add_resource_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--resource-root",
        type=Path,
        help="Shared POSIX lease root; required to enable resource admission.",
    )
    parser.add_argument(
        "--resource-memory-budget-mib",
        type=int,
        help="Aggregate memory reservation budget for this lease root.",
    )
    parser.add_argument(
        "--resource-memory-request-mib",
        type=int,
        help="Memory reservation requested by this job.",
    )
    parser.add_argument(
        "--resource-runtime-rss-limit-mib",
        type=int,
        help="Required runtime process-group RSS limit for an admitted job.",
    )
    parser.add_argument(
        "--resource-runtime-memavailable-floor-mib",
        type=int,
        help="Optional runtime WSL/Linux MemAvailable floor.",
    )
    parser.add_argument(
        "--resource-runtime-sample-seconds",
        type=float,
        help="Runtime guard sampling interval; defaults to 0.2 seconds.",
    )
    parser.add_argument(
        "--resource-batch-id",
        help="Stable batch identity used for duplicate active-job detection.",
    )
    parser.add_argument(
        "--resource-job-id",
        help="Stable job/shard identity within the batch.",
    )
    parser.add_argument(
        "--resource-wait-seconds",
        type=float,
        help="Maximum admission wait; zero rejects immediately when unavailable.",
    )
    parser.add_argument(
        "--resource-stage",
        help="Optional auditable stage name, such as t085-cohort-b-source.",
    )
    parser.add_argument(
        "--resource-worker-count",
        type=int,
        help="Optional effective worker count recorded with the lease.",
    )
    parser.add_argument(
        "--resource-shard-count",
        type=int,
        help="Optional total shard count recorded with the lease.",
    )


def _resource_config_from_args(
    args: argparse.Namespace,
) -> ResourceAdmissionConfig | None:
    names = (
        "resource_root",
        "resource_memory_budget_mib",
        "resource_memory_request_mib",
        "resource_runtime_rss_limit_mib",
        "resource_runtime_memavailable_floor_mib",
        "resource_runtime_sample_seconds",
        "resource_batch_id",
        "resource_job_id",
        "resource_wait_seconds",
        "resource_stage",
        "resource_worker_count",
        "resource_shard_count",
    )
    if not any(getattr(args, name) is not None for name in names):
        return None
    required = (
        "resource_root",
        "resource_memory_budget_mib",
        "resource_memory_request_mib",
        "resource_runtime_rss_limit_mib",
        "resource_batch_id",
        "resource_job_id",
    )
    missing = [name for name in required if getattr(args, name) is None]
    if missing:
        raise SystemExit(
            "resource admission requires --resource-root, "
            "--resource-memory-budget-mib, --resource-memory-request-mib, "
            "--resource-runtime-rss-limit-mib, --resource-batch-id, and "
            "--resource-job-id"
        )
    return ResourceAdmissionConfig(
        root=args.resource_root.resolve(),
        memory_budget_mib=args.resource_memory_budget_mib,
        memory_request_mib=args.resource_memory_request_mib,
        batch_id=args.resource_batch_id,
        job_id=args.resource_job_id,
        runtime_rss_limit_mib=args.resource_runtime_rss_limit_mib,
        runtime_memavailable_floor_mib=args.resource_runtime_memavailable_floor_mib,
        runtime_sample_seconds=(
            _RESOURCE_POLL_SECONDS
            if args.resource_runtime_sample_seconds is None
            else args.resource_runtime_sample_seconds
        ),
        wait_seconds=(
            0.0 if args.resource_wait_seconds is None else args.resource_wait_seconds
        ),
        stage=args.resource_stage,
        worker_count=args.resource_worker_count,
        shard_count=args.resource_shard_count,
    )


def _resource_config_args(config: ResourceAdmissionConfig) -> list[str]:
    args = [
        "--resource-root",
        str(config.root),
        "--resource-memory-budget-mib",
        str(config.memory_budget_mib),
        "--resource-memory-request-mib",
        str(config.memory_request_mib),
        "--resource-runtime-rss-limit-mib",
        str(config.runtime_rss_limit_mib),
        "--resource-batch-id",
        config.batch_id,
        "--resource-job-id",
        config.job_id,
        "--resource-wait-seconds",
        str(config.wait_seconds),
    ]
    if config.runtime_memavailable_floor_mib is not None:
        args.extend(
            [
                "--resource-runtime-memavailable-floor-mib",
                str(config.runtime_memavailable_floor_mib),
            ]
        )
    if config.runtime_sample_seconds != _RESOURCE_POLL_SECONDS:
        args.extend(
            [
                "--resource-runtime-sample-seconds",
                str(config.runtime_sample_seconds),
            ]
        )
    if config.stage is not None:
        args.extend(["--resource-stage", config.stage])
    if config.worker_count is not None and config.shard_count is not None:
        args.extend(
            [
                "--resource-worker-count",
                str(config.worker_count),
                "--resource-shard-count",
                str(config.shard_count),
            ]
        )
    return args


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
    resource_config = _resource_config_from_args(args)
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
    if resource_config is not None:
        supervisor_args.extend(_resource_config_args(resource_config))
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
    _add_resource_arguments(parser)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    return parser


def _start_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--status", type=Path, required=True)
    parser.add_argument("--stdout", type=Path, required=True)
    parser.add_argument("--stderr", type=Path, required=True)
    parser.add_argument("--cwd", type=Path)
    parser.add_argument("--expected-seconds", type=float, default=None)
    _add_resource_arguments(parser)
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
        resource_config = _resource_config_from_args(args)
        return _supervise(
            status_path=args.status,
            stdout_path=args.stdout,
            stderr_path=args.stderr,
            cwd=args.cwd,
            command=command,
            expected_seconds=args.expected_seconds,
            resource_config=resource_config,
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
