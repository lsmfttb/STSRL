"""Fresh-process arm launcher for the authorized-only T092 canary.

This module never imports ``slaythespire``.  The parent validates the complete
arm specification before spawning a child; the child then validates the one
extension it imports before it constructs a simulator.  OFF and ON communicate
only through their immutable arm JSON records.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
from collections.abc import Mapping
from dataclasses import asdict
from pathlib import Path
from typing import Any

from sts_combat_rl.sim.battle_start_pool import (
    BattleStartCheckpointRecord,
    record_to_manifest,
)
from sts_combat_rl.sim.t090_battle_student import T090SplitEntry
from sts_combat_rl.sim.t092_canary import (
    T092_CANARY_ARM_RECORD_SCHEMA_ID,
    T092_PUBLICATION_NATIVE_IDENTITY,
    T092CanaryError,
    _validate_arm_record,
    _validate_pair_record,
    _validate_worker,
)
from sts_combat_rl.sim.t092_internal_search_state import T092_NATIVE_IDENTITY
from sts_combat_rl.t085_corrected_leaf_value_search_evaluation import (
    T085BattleStartRecord,
)

T092_CANARY_ARM_REQUEST_SCHEMA_ID = "t092-paired-canary-arm-request-v1"


class T092CanaryProcessError(T092CanaryError):
    """An arm process is not a valid isolated T092 execution boundary."""


def _child_failure_detail(stderr: str) -> str:
    """Relay only the child's explicit, public-safe failure envelope.

    Native exception text can include simulator representations.  The child
    therefore prints controlled T092 boundary errors only; every other stderr
    shape becomes an unclassified exception type rather than a retained native
    string.
    """

    for line in stderr.splitlines():
        match = re.fullmatch(
            r"T092_CHILD_FAILURE: ([A-Za-z_][A-Za-z0-9_]{0,127}): ([A-Za-z0-9 ._:/-]{1,512})",
            line,
        )
        if match is not None:
            return f"{match.group(1)}: {match.group(2)}"
        match = re.fullmatch(
            r"T092_CHILD_FAILURE: unclassified: ([A-Za-z_][A-Za-z0-9_]{0,127})",
            line,
        )
        if match is not None:
            return f"unclassified: {match.group(1)}"
    return "unclassified: child_stderr_not_safe_for_retention"


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def validate_t092_arm_process_spec(
    spec: Mapping[str, Any], *, arm: str, implementation_head: str | None = None
) -> dict[str, Any]:
    """Validate an arm's pinned interpreter and exactly one extension binary."""

    expected_identity = T092_NATIVE_IDENTITY if arm == "ON" else T092_PUBLICATION_NATIVE_IDENTITY
    required = {
        "python_executable", "extension_path", "extension_sha256",
        "extension_size_bytes", "native_identity", "stsrl_source_root",
    }
    if not isinstance(spec, Mapping) or set(spec) != required:
        raise T092CanaryProcessError("T092 arm process specification is incomplete")
    result = dict(spec)
    executable = Path(str(result["python_executable"])).resolve()
    extension = Path(str(result["extension_path"])).resolve()
    source_root = Path(str(result["stsrl_source_root"])).resolve()
    if (
        not executable.is_file()
        or not os.access(executable, os.X_OK)
        or not extension.is_file()
        or not source_root.joinpath("src/sts_combat_rl").is_dir()
        or result.get("native_identity") != expected_identity
        or not isinstance(result.get("extension_sha256"), str)
        or len(result["extension_sha256"]) != 64
        or isinstance(result.get("extension_size_bytes"), bool)
        or not isinstance(result.get("extension_size_bytes"), int)
        or result["extension_size_bytes"] <= 0
        or extension.stat().st_size != result["extension_size_bytes"]
        or _sha256_file(extension) != result["extension_sha256"]
    ):
        raise T092CanaryProcessError("T092 arm native identity/binary does not match")
    if implementation_head is not None:
        if (
            not isinstance(implementation_head, str)
            or len(implementation_head) != 40
            or any(character not in "0123456789abcdef" for character in implementation_head)
        ):
            raise T092CanaryProcessError("T092 implementation head is invalid")
        try:
            resolved_head = subprocess.run(
                ["git", "-C", str(source_root), "rev-parse", "HEAD"],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
            ).stdout.strip()
        except (OSError, subprocess.SubprocessError) as exc:
            raise T092CanaryProcessError("T092 source root Git identity is unavailable") from exc
        if resolved_head != implementation_head:
            raise T092CanaryProcessError("T092 source root Git head does not match authorization")
    result["python_executable"] = str(executable)
    result["extension_path"] = str(extension)
    result["stsrl_source_root"] = str(source_root)
    return result


def _read_immutable_arm_record(
    path: Path, *, arm: str, source: T090SplitEntry
) -> tuple[dict[str, Any], dict[str, Any]]:
    resolved = path.resolve(strict=True)
    raw = resolved.read_bytes()
    try:
        record = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise T092CanaryProcessError("T092 arm record is not readable JSON") from exc
    if not isinstance(record, Mapping):
        raise T092CanaryProcessError("T092 arm record is not a JSON object")
    expected_native = T092_NATIVE_IDENTITY if arm == "ON" else T092_PUBLICATION_NATIVE_IDENTITY
    try:
        _validate_arm_record(record, arm=arm, expected_native_identity=expected_native, source=source)
    except T092CanaryError as exc:
        raise T092CanaryProcessError("T092 immutable arm record is invalid") from exc
    return dict(record), {
        "path": str(resolved),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "size_bytes": len(raw),
        "schema_id": T092_CANARY_ARM_RECORD_SCHEMA_ID,
    }


def execute_t092_isolated_arm(
    *,
    arm: str,
    spec: Mapping[str, Any],
    source: T090SplitEntry,
    selected: T085BattleStartRecord,
    canonical: BattleStartCheckpointRecord,
    worker: Mapping[str, Any],
    implementation_head: str,
    output_path: str | Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Spawn one fresh interpreter and return its independently checked record."""

    if arm not in {"OFF", "ON"}:
        raise T092CanaryProcessError("T092 process arm must be OFF or ON")
    validated_spec = validate_t092_arm_process_spec(
        spec, arm=arm, implementation_head=implementation_head
    )
    worker_identity = _validate_worker(worker)
    destination = Path(output_path).resolve()
    if destination.exists():
        raise T092CanaryProcessError("refusing to overwrite a T092 arm record")
    request = {
        "schema_id": T092_CANARY_ARM_REQUEST_SCHEMA_ID,
        "schema_version": 1,
        "task_id": "T092",
        "arm": arm,
        "implementation_head": implementation_head,
        "worker": worker_identity,
        "spec": validated_spec,
        "source": asdict(source),
        "selected": asdict(selected),
        "canonical": record_to_manifest(canonical),
    }
    environment = {
        "PATH": os.environ.get("PATH", ""),
        "PYTHONPATH": f"{Path(validated_spec['extension_path']).parent}:{Path(validated_spec['stsrl_source_root']) / 'src'}",
        "PYTHONNOUSERSITE": "1",
    }
    completed = subprocess.run(
        [
            validated_spec["python_executable"], "-m",
            "sts_combat_rl.commands.t092_canary_arm", "--output", str(destination),
        ],
        input=json.dumps(request, sort_keys=True, separators=(",", ":"), allow_nan=False),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=environment,
        check=False,
    )
    if completed.returncode != 0:
        detail = _child_failure_detail(completed.stderr)
        raise T092CanaryProcessError(
            f"T092 isolated arm process failed before retention ({detail})"
        )
    record, artifact = _read_immutable_arm_record(destination, arm=arm, source=source)
    expected_binary = {
        "path": validated_spec["extension_path"],
        "sha256": validated_spec["extension_sha256"],
        "size_bytes": validated_spec["extension_size_bytes"],
    }
    if (
        record.get("native_binary") != expected_binary
        or record.get("native_identity") != validated_spec["native_identity"]
        or record.get("process_identity", {}).get("python_executable")
        != validated_spec["python_executable"]
    ):
        raise T092CanaryProcessError("T092 retained arm binary provenance mismatches")
    return record, artifact


class T092IsolatedCanaryRunner:
    """Pair two separately spawned arm processes through immutable JSON only."""

    def __init__(
        self,
        *,
        arm_process_specs: Mapping[str, Mapping[str, Any]],
        source_records: Mapping[str, T085BattleStartRecord],
        canonical_records: Mapping[str, BattleStartCheckpointRecord],
        worker: Mapping[str, Any],
        implementation_head: str,
        output_root: str | Path,
    ) -> None:
        if not isinstance(arm_process_specs, Mapping) or set(arm_process_specs) != {"OFF", "ON"}:
            raise T092CanaryProcessError("T092 isolated runner requires both arm specifications")
        self._specs = {
            arm: validate_t092_arm_process_spec(
                arm_process_specs[arm], arm=arm, implementation_head=implementation_head
            )
            for arm in ("OFF", "ON")
        }
        self._source_records = dict(source_records)
        self._canonical_records = dict(canonical_records)
        self._worker = _validate_worker(worker)
        self._implementation_head = implementation_head
        self._output_root = Path(output_root).resolve()

    def __call__(self, source: T090SplitEntry) -> Mapping[str, Any]:
        selected = self._source_records.get(source.source_identity)
        canonical = self._canonical_records.get(source.source_identity)
        if selected is None or canonical is None:
            raise T092CanaryProcessError("T092 canary source restore binding is missing")
        records: dict[str, dict[str, Any]] = {}
        artifacts: dict[str, dict[str, Any]] = {}
        for arm in ("OFF", "ON"):
            record, artifact = execute_t092_isolated_arm(
                arm=arm,
                spec=self._specs[arm],
                source=source,
                selected=selected,
                canonical=canonical,
                worker=self._worker,
                implementation_head=self._implementation_head,
                output_path=self._output_root / "arms" / (
                    f"t092-canary-shard-{self._worker['shard_index']}-{arm.lower()}.json"
                ),
            )
            records[arm] = record
            artifacts[arm] = artifact
        pair = {
            "source_identity": source.source_identity,
            "source_group": source.source_group,
            "split": source.split,
            "canonical_position": source.canonical_position,
            "arm_native_identities": {"OFF": dict(T092_PUBLICATION_NATIVE_IDENTITY), "ON": dict(T092_NATIVE_IDENTITY)},
            "teacher_config": records["OFF"]["teacher_config"],
            "worker": dict(self._worker),
            "arm_artifacts": artifacts,
            "off": records["OFF"],
            "on": records["ON"],
        }
        try:
            return _validate_pair_record(pair, source)
        except T092CanaryError as exc:
            raise T092CanaryProcessError("T092 isolated arm pair is incomplete") from exc


__all__ = [
    "T092_CANARY_ARM_REQUEST_SCHEMA_ID",
    "T092CanaryProcessError",
    "T092IsolatedCanaryRunner",
    "_child_failure_detail",
    "execute_t092_isolated_arm",
    "validate_t092_arm_process_spec",
]
