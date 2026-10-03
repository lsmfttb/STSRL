"""Exact-head, separately authorized T113 direct-canary workflow.

The module-level imports are simulator-free.  The native extension is loaded
only after path, qualification, fixed-cohort, resource, and Maintainer gates
have all passed.
"""

from __future__ import annotations

import argparse
import ctypes
import json
import math
import os
import sys
import time
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from pathlib import Path

from sts_combat_rl.commands import t088_canary
from sts_combat_rl.commands.t085_native_execution import (
    T085_SOURCE_MANIFEST_SCHEMA_ID,
    T085NativeExecutionError,
    _t085_validate_path_reference,
    restore_t085_canonical_record,
)
from sts_combat_rl.commands.t113_configured_particle_convergence import (
    T113_BRANCH,
    T113WorkflowError,
    _artifact_reference,
    _current_worktree,
    _read_json,
    _resolve_host_path,
    _sha256_file,
    _verify_reference,
    _write_new_json,
    qualify_t113_inputs,
)
from sts_combat_rl.sim.public_run_context import (
    build_public_run_context,
    read_native_public_projection,
)
from sts_combat_rl.sim.t101_particle_convergence import (
    T101_COUNTS,
    T101_SEARCH_SIMULATIONS,
    T101_SOURCE_COUNTS,
    derive_t101_sampler_seed,
)
from sts_combat_rl.sim.t113_canary_execution import (
    T113_CANARY_AUTHORIZATION_SCHEMA,
    T113_CANARY_CALL_ATTEMPT_SCHEMA,
    T113_CANARY_FAILURE_SCHEMA,
    T113_CANARY_FINALIZATION_SCHEMA,
    T113_CANARY_RAW_STAGE_SCHEMA,
    T113_CANARY_READINESS_SCHEMA,
    T113CanaryAuthorizationError,
    build_t113_canary_readiness,
    canonical_sha256,
    t113_canary_selection,
    validate_t113_canary_authorization,
)
from sts_combat_rl.sim.t113_configured_particle_convergence import (
    T113_APPROVED_SPEC_COMMIT,
    T113_NATIVE_IDENTITY,
    T113_SEARCH_CONFIGURATION,
    T113_STAGE_EXECUTION_ENVELOPE_SCHEMA,
    T113_TASK_ID,
    T113ConvergenceError,
    build_t113_canary_evidence,
    validate_t113_bridge_report,
    validate_t113_fixed_cohort,
)

T113_CANARY_CALL_SCHEMA = "t113-canary-direct-call-v1"
T113_CANARY_STAGE_EXECUTION_SCHEMA = T113_STAGE_EXECUTION_ENVELOPE_SCHEMA
T113_CANARY_WORKER_REASON = "three-state direct prefix canary; serial single worker"


class T113CanaryWorkflowError(ValueError):
    """The path-bound T113 canary was incomplete or failed closed."""


def _utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _require_under(path: Path, root: Path) -> Path:
    resolved = path.resolve(strict=True)
    try:
        resolved.relative_to(root.resolve(strict=True))
    except ValueError as exc:
        raise T113CanaryWorkflowError(
            "T113 canary retained output escaped its artifact root"
        ) from exc
    return resolved


def _verify_path_reference(
    raw: object, *, expected_schema: str | None = None
) -> tuple[dict[str, object], Path]:
    reference, path = _verify_reference(raw, expected_schema=expected_schema)
    return reference, path


def _verify_t085_source_manifest_reference(
    raw: object,
) -> tuple[dict[str, object], Path]:
    """Verify the T085 byte_count reference without widening generic refs."""

    if not isinstance(raw, Mapping):
        raise T113CanaryWorkflowError(
            "retained T085 source manifest reference is malformed"
        )
    raw_path = raw.get("path")
    if not isinstance(raw_path, str) or not raw_path:
        raise T113CanaryWorkflowError("retained T085 source manifest path is missing")
    try:
        resolved = _resolve_host_path(raw_path)
        reference = _t085_validate_path_reference(
            {**raw, "path": str(resolved)},
            "T113 retained T085 source manifest",
            expected_schema_id=T085_SOURCE_MANIFEST_SCHEMA_ID,
        )
    except (OSError, T085NativeExecutionError, T113WorkflowError) as exc:
        raise T113CanaryWorkflowError(
            "retained T085 source manifest schema, byte count, path, or hash changed"
        ) from exc
    path = Path(str(reference["path"]))
    return reference, path


def _resource_state() -> dict[str, float]:
    """Measure current available memory and process RSS without extra packages."""

    if os.name == "nt":

        class MemoryStatusEx(ctypes.Structure):
            _fields_ = [
                ("dwLength", ctypes.c_ulong),
                ("dwMemoryLoad", ctypes.c_ulong),
                ("ullTotalPhys", ctypes.c_ulonglong),
                ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong),
                ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong),
                ("ullAvailVirtual", ctypes.c_ulonglong),
                ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
            ]

        class ProcessMemoryCountersEx(ctypes.Structure):
            _fields_ = [
                ("cb", ctypes.c_ulong),
                ("PageFaultCount", ctypes.c_ulong),
                ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t),
                ("PeakPagefileUsage", ctypes.c_size_t),
                ("PrivateUsage", ctypes.c_size_t),
            ]

        status = MemoryStatusEx()
        status.dwLength = ctypes.sizeof(status)
        if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
            raise T113CanaryWorkflowError("Windows memory measurement failed")
        counters = ProcessMemoryCountersEx()
        counters.cb = ctypes.sizeof(counters)
        if not ctypes.windll.psapi.GetProcessMemoryInfo(
            ctypes.windll.kernel32.GetCurrentProcess(),
            ctypes.byref(counters),
            counters.cb,
        ):
            raise T113CanaryWorkflowError("Windows process RSS measurement failed")
        mib = float(1024 * 1024)
        return {
            "available_memory_mib": status.ullAvailPhys / mib,
            "process_rss_mib": counters.WorkingSetSize / mib,
            "process_peak_rss_mib": counters.PeakWorkingSetSize / mib,
        }

    try:
        meminfo = Path("/proc/meminfo").read_text(encoding="ascii")
        status = Path("/proc/self/status").read_text(encoding="ascii")
    except OSError as exc:
        raise T113CanaryWorkflowError(
            "host resource measurement is unavailable; refusing canary execution"
        ) from exc
    memory: dict[str, float] = {}
    for line in meminfo.splitlines():
        label, separator, rest = line.partition(":")
        if separator and label in {"MemAvailable"}:
            memory[label] = float(rest.strip().split()[0]) / 1024
    process: dict[str, float] = {}
    for line in status.splitlines():
        label, separator, rest = line.partition(":")
        if separator and label in {"VmRSS", "VmHWM"}:
            process[label] = float(rest.strip().split()[0]) / 1024
    if not all(key in memory for key in ("MemAvailable",)) or not all(
        key in process for key in ("VmRSS", "VmHWM")
    ):
        raise T113CanaryWorkflowError("host resource measurement is incomplete")
    return {
        "available_memory_mib": memory["MemAvailable"],
        "process_rss_mib": process["VmRSS"],
        "process_peak_rss_mib": process["VmHWM"],
    }


def _enforce_live_resource_policy(
    observation: Mapping[str, object], policy: Mapping[str, object]
) -> dict[str, object]:
    available = observation.get("available_memory_mib")
    process_rss = observation.get("process_rss_mib")
    peak_rss = observation.get("process_peak_rss_mib")
    request = policy.get("memory_request_mib")
    rss_limit = policy.get("runtime_rss_limit_mib")
    if any(
        isinstance(number, bool)
        or not isinstance(number, (int, float))
        or not math.isfinite(float(number))
        or float(number) < 0
        for number in (available, process_rss, peak_rss, request, rss_limit)
    ):
        raise T113CanaryWorkflowError("measured canary resource values are malformed")
    if (
        float(available) < float(request)
        or float(process_rss) > float(rss_limit)
        or float(peak_rss) > float(rss_limit)
    ):
        raise T113CanaryWorkflowError(
            "measured live resources violate the authorized canary guard"
        )
    return {
        "available_memory_mib": float(available),
        "process_rss_mib": float(process_rss),
        "process_peak_rss_mib": float(peak_rss),
        "measured_at_utc": _utc_now(),
        "guard_status": "PASS",
    }


def _current_t113_native_identity() -> dict[str, object]:
    from sts_combat_rl.sim.lightspeed_source import load_lightspeed_source_manifest

    manifest = load_lightspeed_source_manifest()
    repository = manifest.integration.repository_url.rstrip("/").removesuffix(".git")
    identity = {
        "repository": repository.removeprefix("https://github.com/"),
        "ref": manifest.integration.ref,
        "commit": manifest.integration.commit,
    }
    capabilities = set(manifest.capability_ids)
    if (
        identity != T113_NATIVE_IDENTITY
        or not {
            "native_t096_public_information_hidden_future_sampler",
            "native_stsr006_particle_search_bridge",
            "native_stsr009_configuration_aware_root_mapping",
        }
        <= capabilities
    ):
        raise T113CanaryWorkflowError(
            "current native source identity/capabilities differ from T113 qualification"
        )
    return identity


def _authorized_adapter_factory(
    binary: Mapping[str, object],
    *,
    native_manifest_path: Path,
    expected_native_manifest_sha256: str,
) -> Callable[[], object]:
    """Load only the exact hash-bound extension, after authorization validation."""

    from sts_combat_rl.commands import t111_configured_search_execution_cli
    from sts_combat_rl.sim.lightspeed import LightSpeedAdapter

    manifest_path = native_manifest_path.resolve(strict=True)
    if _sha256_file(manifest_path) != expected_native_manifest_sha256:
        raise T113CanaryWorkflowError(
            "authorized native source manifest changed before module load"
        )
    _current_t113_native_identity()
    binary_path = _resolve_host_path(binary.get("path")).resolve(strict=True)
    binary_sha = binary.get("sha256")
    if not isinstance(binary_sha, str) or _sha256_file(binary_path) != binary_sha:
        raise T113CanaryWorkflowError("authorized native binary changed before load")
    module = t111_configured_search_execution_cli._load_native_module(
        binary_path, binary_sha
    )

    def create() -> object:
        return LightSpeedAdapter(
            seed=1,
            ascension=20,
            player_class="IRONCLAD",
            module=module,
        )

    return create


class T113DirectCanaryRunner:
    """Restore exact retained states and make only the five direct T113 calls."""

    def __init__(
        self,
        *,
        adapter_factory: Callable[[], object],
        selected_records: Mapping[str, object],
        canonical_records_by_stratum: Mapping[str, Mapping[str, object]],
        restore_record: Callable[
            [str, str, Mapping[str, object], Mapping[str, object]],
            tuple[object, object, str],
        ]
        | None = None,
        resource_probe: Callable[[], Mapping[str, object]] = _resource_state,
    ) -> None:
        if not callable(adapter_factory) or not callable(resource_probe):
            raise T113CanaryWorkflowError("T113 canary runtime factories are invalid")
        self._adapter_factory = adapter_factory
        self._selected_records = dict(selected_records)
        self._canonical_records_by_stratum = {
            str(key): dict(value) for key, value in canonical_records_by_stratum.items()
        }
        self._restore_record = restore_record
        self._resource_probe = resource_probe

    def _restore(self, state: Mapping[str, object]) -> tuple[object, object, str]:
        identity = state.get("selection_identity")
        stratum = state.get("stratum")
        if not isinstance(identity, str) or stratum not in T101_SOURCE_COUNTS:
            raise T113CanaryWorkflowError("T113 selected canary state is malformed")
        selected = self._selected_records.get(identity)
        canonical_map = self._canonical_records_by_stratum.get(str(stratum))
        if selected is None or canonical_map is None or identity not in canonical_map:
            raise T113CanaryWorkflowError(
                "T113 canary state has no exact accepted T085 restore record"
            )
        if self._restore_record is not None:
            return self._restore_record(identity, str(stratum), selected, canonical_map)
        adapter = self._adapter_factory()
        try:
            restored, method = restore_t085_canonical_record(
                adapter,
                selected,
                canonical_map,  # type: ignore[arg-type]
            )
            actions = list(adapter.legal_actions(restored))  # type: ignore[attr-defined]
            canonical = canonical_map[identity]
            expected = getattr(canonical, "public_run_context", None)
            actual = build_public_run_context(
                restored.raw,
                actions,
                projection=read_native_public_projection(adapter, restored),
                history=(
                    expected.get("history", []) if isinstance(expected, Mapping) else []
                ),
            )
        except (T085NativeExecutionError, RuntimeError, TypeError, ValueError) as exc:
            raise T113CanaryWorkflowError(
                f"{identity}: exact accepted T085 restore failed"
            ) from exc
        if not isinstance(expected, Mapping) or actual != expected:
            raise T113CanaryWorkflowError(
                f"{identity}: restored T096 projection/legal-action parity changed"
            )
        return adapter, restored, str(method)

    def run_ladder(
        self,
        state: Mapping[str, object],
        *,
        worker_id: str,
        resource_policy: Mapping[str, object],
        call_observer: Callable[[Mapping[str, object]], None],
        call_start_observer: Callable[[Mapping[str, object]], Mapping[str, object]],
    ) -> dict[str, object]:
        if not isinstance(worker_id, str) or not worker_id:
            raise T113CanaryWorkflowError("single-worker identity is required")
        if not callable(call_observer):
            raise T113CanaryWorkflowError("durable T113 per-call sink is required")
        if not callable(call_start_observer):
            raise T113CanaryWorkflowError("durable T113 call-attempt sink is required")
        identity = state.get("selection_identity")
        stratum = state.get("stratum")
        if not isinstance(identity, str) or stratum not in T101_SOURCE_COUNTS:
            raise T113CanaryWorkflowError("T113 selected state is malformed")
        seed = derive_t101_sampler_seed(identity, 0)
        adapter, restored, restore_method = self._restore(state)
        bridge = getattr(adapter, "sample_hidden_future_particles_search", None)
        if not callable(bridge):
            raise T113CanaryWorkflowError("validated T099 direct bridge is unavailable")
        calls: dict[str, object] = {}
        for count in T101_COUNTS:
            before = _enforce_live_resource_policy(
                self._resource_probe(), resource_policy
            )
            started = time.perf_counter()
            attempt = {
                "schema_id": T113_CANARY_CALL_ATTEMPT_SCHEMA,
                "task_id": T113_TASK_ID,
                "selection_identity": identity,
                "stratum": stratum,
                "replicate_index": 0,
                "sampler_seed_input": seed,
                "particle_start": 0,
                "particle_count": count,
                "search_simulations_per_particle": T101_SEARCH_SIMULATIONS,
                "include_potions": False,
                "worker_id": worker_id,
                "shard_index": 0,
                "effective_concurrency": 1,
                "failure_retry_status": "started_no_retry",
                "bridge_invocation_status": "STARTED",
                "native_identity": dict(T113_NATIVE_IDENTITY),
                "frozen_search_configuration": dict(T113_SEARCH_CONFIGURATION),
                "started_at_utc": _utc_now(),
                "resource_guard_observation": before,
            }
            attempt_ref = call_start_observer(attempt)
            try:
                report = bridge(
                    restored,
                    sampler_seed=seed,
                    particle_start=0,
                    particle_count=count,
                    search_simulations=T101_SEARCH_SIMULATIONS,
                    include_potions=False,
                )
            except (
                OSError,
                RuntimeError,
                TypeError,
                ValueError,
                T113CanaryWorkflowError,
            ) as exc:
                # Operational retries are deliberately absent at this boundary.
                raise T113CanaryWorkflowError(
                    f"{identity}: direct canary N={count} failed; no retry was attempted"
                ) from exc
            elapsed = time.perf_counter() - started
            after_raw: dict[str, object] = {}
            try:
                after_raw = dict(self._resource_probe())
                after = _enforce_live_resource_policy(after_raw, resource_policy)
            except (OSError, TypeError, ValueError, T113CanaryWorkflowError) as exc:
                after = {
                    **after_raw,
                    "measured_at_utc": _utc_now(),
                    "guard_status": "FAIL",
                    "measurement_error_type": type(exc).__name__,
                }
            call = {
                "schema_id": T113_CANARY_CALL_SCHEMA,
                "task_id": T113_TASK_ID,
                "selection_identity": identity,
                "stratum": stratum,
                "replicate_index": 0,
                "sampler_seed_input": seed,
                "particle_start": 0,
                "particle_count": count,
                "search_simulations_per_particle": T101_SEARCH_SIMULATIONS,
                "include_potions": False,
                "bridge_report": report,
                "wall_clock_time_s": elapsed,
                "started_at_utc": attempt["started_at_utc"],
                "finished_at_utc": _utc_now(),
                "attempt_artifact": dict(attempt_ref),
                "worker_id": worker_id,
                "shard_index": 0,
                "effective_concurrency": 1,
                "failure_retry_status": "success_no_retry",
                "retry_reason": None,
                "single_worker_reason": T113_CANARY_WORKER_REASON,
                "restore_method": restore_method,
                "native_identity": dict(T113_NATIVE_IDENTITY),
                "frozen_search_configuration": dict(T113_SEARCH_CONFIGURATION),
                "resource_guard_observation": {"before": before, "after": after},
            }
            call_observer(call)
            if after.get("guard_status") != "PASS":
                raise T113CanaryWorkflowError(
                    f"{identity}: post-call resource guard failed; no retry was attempted"
                )
            if elapsed <= 0:
                raise T113CanaryWorkflowError(
                    f"{identity}: direct canary N={count} elapsed time is not positive"
                )
            # Fail on invalid reports before making the next direct call.
            validate_t113_bridge_report(
                report, particle_count=count, expected_sampler_seed=seed
            )
            calls[str(count)] = call
        return {
            "selection_identity": identity,
            "stratum": stratum,
            "replicate_index": 0,
            "sampler_seed_input": seed,
            "restore_method": restore_method,
            "calls": calls,
        }


def _reference_from_input_admission(
    input_admission: Mapping[str, object], role: str
) -> tuple[dict[str, object], Path]:
    artifacts = input_admission.get("artifacts")
    report = artifacts.get(role) if isinstance(artifacts, Mapping) else None
    qualified = report.get("artifact") if isinstance(report, Mapping) else None
    identity = qualified.get("artifact") if isinstance(qualified, Mapping) else None
    integrity = qualified.get("integrity") if isinstance(qualified, Mapping) else None
    if not isinstance(identity, Mapping) or not isinstance(integrity, Mapping):
        raise T113CanaryWorkflowError(f"retained T101 role {role} is malformed")
    ref = {
        "path": identity.get("path"),
        "schema_id": identity.get("schema_id"),
        "size_bytes": identity.get("size_bytes"),
        "sha256": integrity.get("sha256"),
    }
    return _verify_reference(ref, expected_schema=str(identity.get("schema_id")))


def _load_t101_restore_inputs(
    qualification: Mapping[str, object],
    *,
    implementation_head: str,
) -> tuple[object, dict[str, object], dict[str, object]]:
    source_refs = qualification.get("t112_artifact_references")
    t101_retention_ref = (
        source_refs.get("t101_retention_manifest")
        if isinstance(source_refs, Mapping)
        else None
    )
    _, retention_path = _verify_path_reference(
        t101_retention_ref, expected_schema="t101-terminal-retention-manifest-v1"
    )
    retention = _read_json(retention_path, label="historical T101 retention manifest")
    artifact_refs = retention.get("artifact_references")
    input_ref = (
        artifact_refs.get("input_admission")
        if isinstance(artifact_refs, Mapping)
        else None
    )
    _, input_path = _verify_path_reference(
        input_ref, expected_schema="t101-input-admission-v1"
    )
    input_admission = _read_json(input_path, label="historical T101 input admission")
    if input_admission.get("eligible") is not True:
        raise T113CanaryWorkflowError("historical T101 restore inputs are not eligible")
    roles = {
        role: _reference_from_input_admission(input_admission, role)
        for role in (
            "t087_formal",
            "t087_report",
            "t087_retention",
            "t085_selection",
            "t085_restore",
            "t085_canonical_a",
            "t085_canonical_b",
            "t085_canonical_c",
        )
    }
    _, restore_path = roles["t085_restore"]
    restore_document = _read_json(restore_path, label="accepted T085 restore evidence")
    sources = restore_document.get("source_bindings")
    if not isinstance(sources, Mapping):
        raise T113CanaryWorkflowError("accepted T085 source bindings are missing")
    source_manifests: dict[str, Path] = {}
    for stratum in ("B", "C"):
        source = sources.get(stratum)
        reference = (
            source.get("source_manifest") if isinstance(source, Mapping) else None
        )
        _, source_manifests[stratum] = _verify_t085_source_manifest_reference(reference)
    formal, gate, _provenance = t088_canary._admit_t088_canary_inputs_from_paths(
        implementation_head=implementation_head,
        t087_formal_path=roles["t087_formal"][1],
        t087_report_path=roles["t087_report"][1],
        t087_retention_path=roles["t087_retention"][1],
        t085_selection_path=roles["t085_selection"][1],
        t085_restore_path=restore_path,
        a_pool_path=roles["t085_canonical_a"][1],
        b_pool_path=roles["t085_canonical_b"][1],
        c_pool_path=roles["t085_canonical_c"][1],
        b_source_manifest_path=source_manifests["B"],
        c_source_manifest_path=source_manifests["C"],
        historical_t085_producer_only=True,
    )
    maps = getattr(gate, "canonical_records_by_cohort", None)
    cohorts = getattr(gate, "cohorts", None)
    if not isinstance(maps, Mapping) or not isinstance(cohorts, Mapping):
        raise T113CanaryWorkflowError(
            "accepted T085 canonical restore gate is malformed"
        )
    selected_records = {
        record.selection_identity: record
        for stratum in T101_SOURCE_COUNTS
        for record in cohorts.get(stratum, ())
    }
    return formal, selected_records, {"maps": maps, "input_admission": input_admission}


def prepare_t113_canary_readiness_from_paths(
    *,
    t112_retention_manifest_path: Path,
    native_manifest_path: Path,
    artifact_root: Path,
    repo_root: Path,
) -> dict[str, object]:
    """Write a fresh, non-authorizing canary readiness bundle."""

    if artifact_root.exists():
        raise T113CanaryWorkflowError("refusing to overwrite T113 canary readiness")
    qualification = qualify_t113_inputs(
        t112_retention_manifest_path=t112_retention_manifest_path,
        current_native_manifest_path=native_manifest_path,
        repo_root=repo_root,
    )
    cohort = validate_t113_fixed_cohort(qualification["fixed_cohort"])
    qualification_ref = _write_new_json(
        artifact_root / "t113-canary-input-qualification.json", qualification
    )
    cohort_ref = _write_new_json(
        artifact_root / "t113-canary-fixed-cohort.json", cohort
    )
    readiness = build_t113_canary_readiness(
        qualification=qualification,
        fixed_cohort=cohort,
        implementation_head=str(qualification["implementation_head"]),
        qualification_artifact_sha256=str(qualification_ref["sha256"]),
        fixed_cohort_artifact_sha256=str(cohort_ref["sha256"]),
        native_manifest_sha256=str(qualification["native_source_manifest"]["sha256"]),
        native_binary_sha256=str(qualification["native_binary_sha256"]),
    )
    readiness_ref = _write_new_json(
        artifact_root / "t113-canary-readiness.json", readiness
    )
    return {
        "qualification_artifact": qualification_ref,
        "fixed_cohort_artifact": cohort_ref,
        "readiness_artifact": readiness_ref,
        "canary_authorized": False,
        "canary_started": False,
        "native_simulator_or_bridge_called": False,
        "execution_authorization_created": False,
    }


def run_t113_canary_from_paths(
    *,
    qualification_path: Path,
    fixed_cohort_path: Path,
    readiness_path: Path,
    authorization_path: Path,
    t112_retention_manifest_path: Path,
    native_manifest_path: Path,
    artifact_root: Path,
    repo_root: Path,
    worker_id: str,
    adapter_factory: Callable[[], object] | None = None,
    runner_factory: Callable[..., T113DirectCanaryRunner] = T113DirectCanaryRunner,
    resource_probe: Callable[[], Mapping[str, object]] = _resource_state,
) -> dict[str, object]:
    """Run exactly 15 direct calls after all exact-head and resource gates pass."""

    worktree = _current_worktree(repo_root)
    if worktree["branch"] != T113_BRANCH:
        raise T113CanaryWorkflowError(
            "T113 canary must run on the authorized PR branch"
        )
    if artifact_root.exists():
        raise T113CanaryWorkflowError("refusing to overwrite T113 canary stage output")
    qualification = _read_json(
        qualification_path, label="T113 canary input qualification"
    )
    fixed_cohort = _read_json(fixed_cohort_path, label="T113 canary fixed cohort")
    readiness = _read_json(readiness_path, label="T113 canary readiness")
    authorization = _read_json(
        authorization_path, label="distinct T113 Maintainer canary authorization"
    )
    qualification_ref = _artifact_reference(
        qualification_path, schema_id="t113-input-qualification-v1"
    )
    cohort_ref = _artifact_reference(
        fixed_cohort_path, schema_id="t113-fixed-cohort-manifest-v1"
    )
    fresh_qualification = qualify_t113_inputs(
        t112_retention_manifest_path=t112_retention_manifest_path,
        current_native_manifest_path=native_manifest_path,
        repo_root=repo_root,
    )
    checked_cohort = validate_t113_fixed_cohort(fixed_cohort)
    if (
        qualification != fresh_qualification
        or checked_cohort
        != validate_t113_fixed_cohort(fresh_qualification["fixed_cohort"])
        or qualification.get("implementation_head") != worktree["head"]
    ):
        raise T113CanaryWorkflowError(
            "T113 qualification/cohort changed or is not for the current exact head"
        )
    manifest_sha = str(fresh_qualification["native_source_manifest"]["sha256"])
    binary_sha = str(fresh_qualification["native_binary_sha256"])
    readiness_expected = build_t113_canary_readiness(
        qualification=qualification,
        fixed_cohort=checked_cohort,
        implementation_head=str(worktree["head"]),
        qualification_artifact_sha256=str(qualification_ref["sha256"]),
        fixed_cohort_artifact_sha256=str(cohort_ref["sha256"]),
        native_manifest_sha256=manifest_sha,
        native_binary_sha256=binary_sha,
    )
    if readiness != readiness_expected:
        raise T113CanaryWorkflowError(
            "T113 canary readiness does not match current files"
        )
    checked_authorization = validate_t113_canary_authorization(
        authorization,
        readiness=readiness,
        qualification=qualification,
        fixed_cohort=checked_cohort,
        implementation_head=str(worktree["head"]),
        qualification_artifact_sha256=str(qualification_ref["sha256"]),
        fixed_cohort_artifact_sha256=str(cohort_ref["sha256"]),
        native_manifest_sha256=manifest_sha,
        native_binary_sha256=binary_sha,
    )
    _current_t113_native_identity()
    binary_reference = fresh_qualification.get("t112_artifact_references", {}).get(
        "native_binary"
    )
    if not isinstance(binary_reference, Mapping):
        # T113 qualification binds the hash; the original T112 retention binds path.
        t112_ref = fresh_qualification.get("t112_terminal_retention_manifest")
        _, retention_path = _verify_path_reference(
            t112_ref, expected_schema="t112-terminal-retention-manifest-v1"
        )
        retention_doc = _read_json(retention_path, label="T112 terminal retention")
        refs = retention_doc.get("artifact_references")
        binary_reference = (
            refs.get("native_binary") if isinstance(refs, Mapping) else None
        )
    binary, binary_path = _verify_path_reference(binary_reference)
    if binary.get("sha256") != binary_sha:
        raise T113CanaryWorkflowError("T113 exact native binary binding changed")

    formal, selected_records, restore_inputs = _load_t101_restore_inputs(
        qualification, implementation_head=str(worktree["head"])
    )
    del formal
    maps = restore_inputs["maps"]
    if not isinstance(maps, Mapping):
        raise T113CanaryWorkflowError("accepted T085 restore maps are malformed")
    selected = t113_canary_selection(checked_cohort)
    for row in selected:
        if row["selection_identity"] not in selected_records:
            raise T113CanaryWorkflowError(
                "fixed T113 canary state is absent from accepted T101 source population"
            )

    readiness_ref = _artifact_reference(
        readiness_path, schema_id=T113_CANARY_READINESS_SCHEMA
    )
    authorization_ref = _artifact_reference(
        authorization_path, schema_id=T113_CANARY_AUTHORIZATION_SCHEMA
    )
    # Recheck every moving approval boundary after retained-pool admission, which
    # may take a long time, and immediately before any lazy native module load.
    latest_worktree = _current_worktree(repo_root)
    if latest_worktree != worktree:
        raise T113CanaryWorkflowError(
            "T113 implementation head/worktree changed before canary execution"
        )
    if (
        _artifact_reference(qualification_path, schema_id="t113-input-qualification-v1")
        != qualification_ref
        or _artifact_reference(
            fixed_cohort_path, schema_id="t113-fixed-cohort-manifest-v1"
        )
        != cohort_ref
        or _artifact_reference(readiness_path, schema_id=T113_CANARY_READINESS_SCHEMA)
        != readiness_ref
        or _artifact_reference(
            authorization_path, schema_id=T113_CANARY_AUTHORIZATION_SCHEMA
        )
        != authorization_ref
        or _read_json(readiness_path, label="T113 canary readiness") != readiness
        or _read_json(authorization_path, label="distinct T113 canary authorization")
        != authorization
        or _sha256_file(native_manifest_path.resolve(strict=True)) != manifest_sha
        or _sha256_file(binary_path) != binary_sha
    ):
        raise T113CanaryWorkflowError(
            "T113 canary approval/input/native identity changed before execution"
        )
    checked_authorization = validate_t113_canary_authorization(
        authorization,
        readiness=readiness,
        qualification=qualification,
        fixed_cohort=checked_cohort,
        implementation_head=str(worktree["head"]),
        qualification_artifact_sha256=str(qualification_ref["sha256"]),
        fixed_cohort_artifact_sha256=str(cohort_ref["sha256"]),
        native_manifest_sha256=manifest_sha,
        native_binary_sha256=binary_sha,
    )
    _current_t113_native_identity()

    artifact_root.mkdir(parents=True, exist_ok=False)
    started_at = _utc_now()
    call_refs: list[dict[str, object]] = []
    attempt_refs: list[dict[str, object]] = []
    resource_policy = checked_authorization["resource_guard_policy"]
    if not isinstance(resource_policy, Mapping):
        raise T113CanaryWorkflowError("authorized T113 resource guard is missing")

    def retain_call(call: Mapping[str, object]) -> None:
        name = f"call-{call['stratum']}-n{call['particle_count']}.json"
        reference = _write_new_json(artifact_root / name, call)
        call_refs.append(reference)

    def retain_attempt(attempt: Mapping[str, object]) -> Mapping[str, object]:
        name = f"attempt-{attempt['stratum']}-n{attempt['particle_count']}.json"
        reference = _write_new_json(artifact_root / name, attempt)
        attempt_refs.append(reference)
        return reference

    stage_start = {
        "schema_id": "t113-canary-stage-start-v1",
        "task_id": T113_TASK_ID,
        "implementation_head": worktree["head"],
        "approved_spec_commit": T113_APPROVED_SPEC_COMMIT,
        "authorization_artifact": authorization_ref,
        "qualification_artifact": qualification_ref,
        "fixed_cohort_artifact": cohort_ref,
        "readiness_artifact": readiness_ref,
        "fixed_cohort_semantic_sha256": canonical_sha256(checked_cohort),
        "native_identity": dict(T113_NATIVE_IDENTITY),
        "native_manifest_sha256": manifest_sha,
        "native_binary_sha256": binary_sha,
        "frozen_search_configuration": dict(T113_SEARCH_CONFIGURATION),
        "canary_selection_sha256": canonical_sha256(selected),
        "planned_bridge_call_count": 15,
        "started_at_utc": started_at,
        "effective_concurrency": 1,
        "worker_count": 1,
        "retry_count": 0,
        "terminal_status": "STARTED",
    }
    stage_start_ref = _write_new_json(
        artifact_root / "t113-canary-stage-start.json", stage_start
    )
    try:
        # Native loading is intentionally below every authorization and retained-input gate.
        native_factory = adapter_factory or _authorized_adapter_factory(
            binary,
            native_manifest_path=native_manifest_path,
            expected_native_manifest_sha256=manifest_sha,
        )
        runner = runner_factory(
            adapter_factory=native_factory,
            selected_records=selected_records,
            canonical_records_by_stratum=maps,
            resource_probe=resource_probe,
        )
        for state in selected:
            runner.run_ladder(
                state,
                worker_id=worker_id,
                resource_policy=resource_policy,
                call_observer=retain_call,
                call_start_observer=retain_attempt,
            )
        finished_at = _utc_now()
        raw_stage = {
            "schema_id": T113_CANARY_RAW_STAGE_SCHEMA,
            "task_id": T113_TASK_ID,
            "implementation_head": worktree["head"],
            "approved_spec_commit": T113_APPROVED_SPEC_COMMIT,
            "authorization_artifact": authorization_ref,
            "qualification_artifact": qualification_ref,
            "fixed_cohort_artifact": cohort_ref,
            "readiness_artifact": readiness_ref,
            "stage_start_artifact": stage_start_ref,
            "fixed_cohort_semantic_sha256": canonical_sha256(checked_cohort),
            "native_identity": dict(T113_NATIVE_IDENTITY),
            "native_manifest_sha256": manifest_sha,
            "native_binary_sha256": binary_sha,
            "frozen_search_configuration": dict(T113_SEARCH_CONFIGURATION),
            "canary_selection_sha256": canonical_sha256(selected),
            "attempt_references": attempt_refs,
            "call_references": call_refs,
            "bridge_call_count": len(call_refs),
            "started_at_utc": started_at,
            "finished_at_utc": finished_at,
            "terminal_status": "SUCCEEDED_UNFINALIZED",
            "effective_concurrency": 1,
            "worker_count": 1,
            "retry_count": 0,
        }
        raw_ref = _write_new_json(
            artifact_root / "t113-canary-raw-stage-manifest.json", raw_stage
        )
        return {
            "raw_stage_manifest": raw_ref,
            "bridge_call_count": len(call_refs),
            "state": "SUCCEEDED_UNFINALIZED",
            "canary_authorized": True,
            "canary_started": True,
            "native_simulator_or_bridge_called": True,
            "formal_execution_authorized": False,
            "formal_execution_started": False,
        }
    except Exception as exc:
        failure = {
            "schema_id": T113_CANARY_FAILURE_SCHEMA,
            "task_id": T113_TASK_ID,
            "implementation_head": worktree["head"],
            "approved_spec_commit": T113_APPROVED_SPEC_COMMIT,
            "stage_start_artifact": stage_start_ref,
            "authorization_artifact": authorization_ref,
            "qualification_artifact": qualification_ref,
            "fixed_cohort_artifact": cohort_ref,
            "readiness_artifact": readiness_ref,
            "attempt_references": attempt_refs,
            "completed_call_references": call_refs,
            "started_at_utc": started_at,
            "finished_at_utc": _utc_now(),
            "terminal_status": "FAILED_NO_RETRY",
            "terminal_classification": "INCOMPLETE",
            "failure_type": type(exc).__name__,
            "bridge_call_may_have_started": bool(attempt_refs),
            "effective_concurrency": 1,
            "worker_count": 1,
            "retry_count": 0,
            "formal_execution_authorized": False,
            "formal_execution_started": False,
        }
        failure_ref = _write_new_json(
            artifact_root / "t113-canary-stage-failure.json", failure
        )
        raise T113CanaryWorkflowError(
            f"T113 canary failed without retry; partial evidence retained at {failure_ref['path']}"
        ) from exc


def finalize_t113_canary_from_paths(
    *,
    raw_stage_manifest_path: Path,
    qualification_path: Path,
    fixed_cohort_path: Path,
    readiness_path: Path,
    authorization_path: Path,
    t112_retention_manifest_path: Path,
    native_manifest_path: Path,
    repo_root: Path,
) -> dict[str, object]:
    """Prove all three exact nested-prefix ladders and retain terminal outputs."""

    worktree = _current_worktree(repo_root)
    qualification = _read_json(
        qualification_path, label="T113 canary input qualification"
    )
    cohort = validate_t113_fixed_cohort(
        _read_json(fixed_cohort_path, label="T113 canary fixed cohort")
    )
    readiness = _read_json(readiness_path, label="T113 canary readiness")
    authorization = _read_json(
        authorization_path, label="distinct T113 Maintainer canary authorization"
    )
    qualification_ref = _artifact_reference(
        qualification_path, schema_id="t113-input-qualification-v1"
    )
    cohort_ref = _artifact_reference(
        fixed_cohort_path, schema_id="t113-fixed-cohort-manifest-v1"
    )
    fresh = qualify_t113_inputs(
        t112_retention_manifest_path=t112_retention_manifest_path,
        current_native_manifest_path=native_manifest_path,
        repo_root=repo_root,
    )
    manifest_sha = str(fresh["native_source_manifest"]["sha256"])
    binary_sha = str(fresh["native_binary_sha256"])
    readiness_expected = build_t113_canary_readiness(
        qualification=qualification,
        fixed_cohort=cohort,
        implementation_head=str(worktree["head"]),
        qualification_artifact_sha256=str(qualification_ref["sha256"]),
        fixed_cohort_artifact_sha256=str(cohort_ref["sha256"]),
        native_manifest_sha256=manifest_sha,
        native_binary_sha256=binary_sha,
    )
    if qualification != fresh or readiness != readiness_expected:
        raise T113CanaryWorkflowError("T113 finalizer input qualification changed")
    authorization = validate_t113_canary_authorization(
        authorization,
        readiness=readiness,
        qualification=qualification,
        fixed_cohort=cohort,
        implementation_head=str(worktree["head"]),
        qualification_artifact_sha256=str(qualification_ref["sha256"]),
        fixed_cohort_artifact_sha256=str(cohort_ref["sha256"]),
        native_manifest_sha256=manifest_sha,
        native_binary_sha256=binary_sha,
    )
    raw_ref = _artifact_reference(
        raw_stage_manifest_path, schema_id=T113_CANARY_RAW_STAGE_SCHEMA
    )
    root = raw_stage_manifest_path.parent.resolve(strict=True)
    raw_stage = _read_json(
        raw_stage_manifest_path, label="T113 canary raw-stage manifest"
    )
    auth_ref, _ = _verify_reference(
        raw_stage.get("authorization_artifact"),
        expected_schema=T113_CANARY_AUTHORIZATION_SCHEMA,
    )
    readiness_ref = _artifact_reference(
        readiness_path, schema_id=T113_CANARY_READINESS_SCHEMA
    )
    stage_start_ref, stage_start_path = _verify_reference(
        raw_stage.get("stage_start_artifact"),
        expected_schema="t113-canary-stage-start-v1",
    )
    _require_under(stage_start_path, root)
    stage_start = _read_json(stage_start_path, label="T113 canary stage-start receipt")
    if (
        raw_stage.get("schema_id") != T113_CANARY_RAW_STAGE_SCHEMA
        or raw_stage.get("task_id") != T113_TASK_ID
        or raw_stage.get("implementation_head") != worktree["head"]
        or raw_stage.get("approved_spec_commit") != T113_APPROVED_SPEC_COMMIT
        or raw_stage.get("authorization_artifact") != auth_ref
        or auth_ref["sha256"] != _sha256_file(authorization_path.resolve(strict=True))
        or raw_stage.get("qualification_artifact") != qualification_ref
        or raw_stage.get("fixed_cohort_artifact") != cohort_ref
        or raw_stage.get("readiness_artifact") != readiness_ref
        or raw_stage.get("fixed_cohort_semantic_sha256") != canonical_sha256(cohort)
        or raw_stage.get("native_identity") != T113_NATIVE_IDENTITY
        or raw_stage.get("native_manifest_sha256") != manifest_sha
        or raw_stage.get("native_binary_sha256") != binary_sha
        or raw_stage.get("frozen_search_configuration") != T113_SEARCH_CONFIGURATION
        or raw_stage.get("canary_selection_sha256")
        != readiness["canary_selection_sha256"]
        or raw_stage.get("bridge_call_count") != 15
        or raw_stage.get("terminal_status") != "SUCCEEDED_UNFINALIZED"
        or raw_stage.get("effective_concurrency") != 1
        or raw_stage.get("worker_count") != 1
        or raw_stage.get("retry_count") != 0
        or stage_start.get("schema_id") != "t113-canary-stage-start-v1"
        or stage_start.get("task_id") != T113_TASK_ID
        or stage_start.get("implementation_head") != worktree["head"]
        or stage_start.get("approved_spec_commit") != T113_APPROVED_SPEC_COMMIT
        or stage_start.get("authorization_artifact") != auth_ref
        or stage_start.get("qualification_artifact") != qualification_ref
        or stage_start.get("fixed_cohort_artifact") != cohort_ref
        or stage_start.get("readiness_artifact") != readiness_ref
        or stage_start.get("fixed_cohort_semantic_sha256") != canonical_sha256(cohort)
        or stage_start.get("native_identity") != T113_NATIVE_IDENTITY
        or stage_start.get("native_manifest_sha256") != manifest_sha
        or stage_start.get("native_binary_sha256") != binary_sha
        or stage_start.get("frozen_search_configuration") != T113_SEARCH_CONFIGURATION
        or stage_start.get("canary_selection_sha256")
        != readiness["canary_selection_sha256"]
        or stage_start.get("planned_bridge_call_count") != 15
        or stage_start.get("started_at_utc") != raw_stage.get("started_at_utc")
        or stage_start.get("terminal_status") != "STARTED"
        or stage_start.get("effective_concurrency") != 1
        or stage_start.get("worker_count") != 1
        or stage_start.get("retry_count") != 0
        or raw_stage.get("stage_start_artifact") != stage_start_ref
    ):
        raise T113CanaryWorkflowError("T113 raw-stage provenance is invalid")
    call_refs = raw_stage.get("call_references")
    attempt_refs = raw_stage.get("attempt_references")
    if (
        not isinstance(call_refs, list)
        or len(call_refs) != 15
        or not isinstance(attempt_refs, list)
        or len(attempt_refs) != 15
    ):
        raise T113CanaryWorkflowError("T113 raw-stage must retain exactly 15 calls")
    expected_order = [
        (str(row["stratum"]), count)
        for row in readiness["canary_selection"]
        for count in T101_COUNTS
    ]
    expected_keys = set(expected_order)
    try:
        stage_started = datetime.fromisoformat(str(raw_stage.get("started_at_utc")))
        stage_finished = datetime.fromisoformat(str(raw_stage.get("finished_at_utc")))
    except ValueError as exc:
        raise T113CanaryWorkflowError(
            "T113 raw-stage timestamps are malformed"
        ) from exc
    if (
        stage_started.utcoffset() != UTC.utcoffset(stage_started)
        or stage_finished.utcoffset() != UTC.utcoffset(stage_finished)
        or (stage_finished - stage_started).total_seconds() <= 0
    ):
        raise T113CanaryWorkflowError(
            "T113 durable canary stage interval must be positive UTC elapsed time"
        )
    calls_by_key: dict[tuple[str, int], dict[str, object]] = {}
    attempt_by_key: dict[tuple[str, int], dict[str, object]] = {}
    previous_call_finished = stage_started
    worker_identity: str | None = None
    for attempt_ref, expected_key in zip(attempt_refs, expected_order, strict=True):
        attempt_reference, attempt_path = _verify_reference(
            attempt_ref, expected_schema=T113_CANARY_CALL_ATTEMPT_SCHEMA
        )
        _require_under(attempt_path, root)
        attempt = _read_json(attempt_path, label="T113 direct canary call attempt")
        attempt_resource = attempt.get("resource_guard_observation")
        if not isinstance(attempt_resource, Mapping) or (
            attempt_resource.get("guard_status") != "PASS"
        ):
            raise T113CanaryWorkflowError(
                "T113 canary attempt lacks passing measured resources"
            )
        if (
            attempt.get("schema_id") != T113_CANARY_CALL_ATTEMPT_SCHEMA
            or attempt.get("task_id") != T113_TASK_ID
            or (attempt.get("stratum"), attempt.get("particle_count")) != expected_key
            or attempt.get("selection_identity")
            != next(
                row["selection_identity"]
                for row in readiness["canary_selection"]
                if row["stratum"] == expected_key[0]
            )
            or attempt.get("sampler_seed_input")
            != derive_t101_sampler_seed(str(attempt.get("selection_identity")), 0)
            or attempt.get("particle_start") != 0
            or attempt.get("search_simulations_per_particle") != T101_SEARCH_SIMULATIONS
            or attempt.get("include_potions") is not False
            or attempt.get("worker_id") is None
            or attempt.get("shard_index") != 0
            or attempt.get("effective_concurrency") != 1
            or attempt.get("failure_retry_status") != "started_no_retry"
            or attempt.get("bridge_invocation_status") != "STARTED"
            or attempt.get("native_identity") != T113_NATIVE_IDENTITY
            or attempt.get("frozen_search_configuration") != T113_SEARCH_CONFIGURATION
            or expected_key in attempt_by_key
        ):
            raise T113CanaryWorkflowError("T113 canary attempt sequence is invalid")
        if not isinstance(attempt.get("worker_id"), str) or not attempt["worker_id"]:
            raise T113CanaryWorkflowError("T113 canary worker identity is invalid")
        attempt_by_key[expected_key] = {
            **attempt,
            "_artifact_reference": attempt_reference,
        }
    for call_ref, expected_key in zip(call_refs, expected_order, strict=True):
        _verified_ref, call_path = _verify_reference(
            call_ref, expected_schema=T113_CANARY_CALL_SCHEMA
        )
        _require_under(call_path, root)
        call = _read_json(call_path, label="T113 direct canary call")
        count = call.get("particle_count")
        stratum = call.get("stratum")
        key = (str(stratum), int(count) if isinstance(count, int) else -1)
        call_guard = call.get("resource_guard_observation")
        if not isinstance(call_guard, Mapping):
            raise T113CanaryWorkflowError(
                "T113 direct canary resource evidence is malformed"
            )
        if (
            key not in expected_keys
            or key in calls_by_key
            or call.get("schema_id") != T113_CANARY_CALL_SCHEMA
            or call.get("task_id") != T113_TASK_ID
            or call.get("particle_count") != key[1]
            or call.get("particle_start") != 0
            or call.get("search_simulations_per_particle") != T101_SEARCH_SIMULATIONS
            or call.get("include_potions") is not False
            or call.get("replicate_index") != 0
            or call.get("selection_identity")
            != next(
                row["selection_identity"]
                for row in readiness["canary_selection"]
                if row["stratum"] == key[0]
            )
            or call.get("sampler_seed_input")
            != derive_t101_sampler_seed(str(call.get("selection_identity")), 0)
            or not isinstance(call.get("worker_id"), str)
            or not call.get("worker_id")
            or call.get("shard_index") != 0
            or call.get("effective_concurrency") != 1
            or call.get("failure_retry_status") != "success_no_retry"
            or call.get("retry_reason") is not None
            or call.get("single_worker_reason") != T113_CANARY_WORKER_REASON
            or call.get("native_identity") != T113_NATIVE_IDENTITY
            or call.get("frozen_search_configuration") != T113_SEARCH_CONFIGURATION
            or call.get("attempt_artifact")
            != attempt_by_key.get(key, {}).get("_artifact_reference")
            or call.get("worker_id") != attempt_by_key.get(key, {}).get("worker_id")
            or call_guard.get("before")
            != attempt_by_key.get(key, {}).get("resource_guard_observation")
            or call.get("started_at_utc")
            != attempt_by_key.get(key, {}).get("started_at_utc")
            or call.get("finished_at_utc") is None
            or call.get("started_at_utc") is None
        ):
            raise T113CanaryWorkflowError(
                "T113 direct canary call provenance is invalid"
            )
        try:
            attempt_started = datetime.fromisoformat(
                str(attempt_by_key[key]["started_at_utc"])
            )
            call_finished = datetime.fromisoformat(str(call.get("finished_at_utc")))
        except ValueError as exc:
            raise T113CanaryWorkflowError(
                "T113 direct-call UTC timestamps are malformed"
            ) from exc
        if (
            attempt_started.utcoffset() != UTC.utcoffset(attempt_started)
            or call_finished.utcoffset() != UTC.utcoffset(call_finished)
            or attempt_started < previous_call_finished
            or call_finished <= attempt_started
            or call_finished > stage_finished
        ):
            raise T113CanaryWorkflowError(
                "T113 canary calls are not a sequential measured stage"
            )
        previous_call_finished = call_finished
        if worker_identity is None:
            worker_identity = str(call["worker_id"])
        elif call["worker_id"] != worker_identity:
            raise T113CanaryWorkflowError(
                "T113 canary must use one stable worker identity"
            )
        guard_observation = call_guard
        policy = authorization["resource_guard_policy"]
        if not isinstance(guard_observation, Mapping) or not isinstance(
            policy, Mapping
        ):
            raise T113CanaryWorkflowError(
                "T113 per-call resource guard evidence is missing"
            )
        if any(
            not isinstance(guard_observation.get(label), Mapping)
            or guard_observation[label].get("guard_status") != "PASS"
            for label in ("before", "after")
        ):
            raise T113CanaryWorkflowError("T113 per-call resource guard did not pass")
        _enforce_live_resource_policy(guard_observation.get("before", {}), policy)
        _enforce_live_resource_policy(guard_observation.get("after", {}), policy)
        calls_by_key[key] = call
    if set(calls_by_key) != expected_keys:
        raise T113CanaryWorkflowError("T113 raw-stage call set is incomplete")
    ladders: list[dict[str, object]] = []
    for selected in readiness["canary_selection"]:
        stratum = str(selected["stratum"])
        calls = {str(count): calls_by_key[(stratum, count)] for count in T101_COUNTS}
        ladders.append(
            {
                "selection_identity": selected["selection_identity"],
                "stratum": stratum,
                "replicate_index": 0,
                "calls": calls,
            }
        )
    try:
        evidence = build_t113_canary_evidence(
            ladders,
            cohort_manifest=cohort,
            implementation_head=str(worktree["head"]),
        )
    except T113ConvergenceError as exc:
        message = str(exc)
        nested_invalid = (
            "prefix" in message
            or "configured decision domain drifted" in message
            or "differs on" in message
        )
        classification = (
            "NESTED_PREFIX_CONTRACT_INVALID" if nested_invalid else "INCOMPLETE"
        )
        failed_envelope = {
            "schema_id": T113_CANARY_STAGE_EXECUTION_SCHEMA,
            "task_id": T113_TASK_ID,
            "stage_name": "direct_canary_ladder",
            "implementation_head": worktree["head"],
            "input_binding_sha256": canonical_sha256(cohort),
            "bridge_call_count": 15,
            "terminal_status": "FAILED",
            "started_at_utc": raw_stage.get("started_at_utc"),
            "finished_at_utc": raw_stage.get("finished_at_utc"),
        }
        failed_envelope_ref = _write_new_json(
            root / "t113-canary-stage-execution-envelope.json", failed_envelope
        )
        failed_finalization = {
            "schema_id": T113_CANARY_FINALIZATION_SCHEMA,
            "task_id": T113_TASK_ID,
            "implementation_head": worktree["head"],
            "approved_spec_commit": T113_APPROVED_SPEC_COMMIT,
            "terminal_classification": classification,
            "complete": False,
            "direct_prefix_equivalence": False,
            "cohort_manifest_sha256": canonical_sha256(cohort),
            "authorization_artifact": _artifact_reference(
                authorization_path, schema_id=T113_CANARY_AUTHORIZATION_SCHEMA
            ),
            "qualification_artifact": qualification_ref,
            "fixed_cohort_artifact": cohort_ref,
            "readiness_artifact": readiness_ref,
            "raw_stage_manifest_artifact": raw_ref,
            "stage_execution_envelope_artifact": failed_envelope_ref,
            "failure_reason": message,
            "native_identity": dict(T113_NATIVE_IDENTITY),
            "native_manifest_sha256": manifest_sha,
            "native_binary_sha256": binary_sha,
            "frozen_search_configuration": dict(T113_SEARCH_CONFIGURATION),
            "canary_authorized": True,
            "canary_started": True,
            "formal_execution_authorized": False,
            "formal_execution_started": False,
            "execution_authorization_created": False,
            "native_simulator_or_bridge_called": True,
        }
        failed_final_ref = _write_new_json(
            root / "t113-canary-finalization.json", failed_finalization
        )
        return {
            "finalization_artifact": failed_final_ref,
            "stage_execution_envelope_artifact": failed_envelope_ref,
            "terminal_classification": classification,
        }
    evidence_ref = _write_new_json(root / "t113-canary-evidence.json", evidence)
    stage_envelope = {
        "schema_id": T113_CANARY_STAGE_EXECUTION_SCHEMA,
        "task_id": T113_TASK_ID,
        "stage_name": "direct_canary_ladder",
        "implementation_head": worktree["head"],
        "input_binding_sha256": canonical_sha256(cohort),
        "bridge_call_count": 15,
        "terminal_status": "SUCCEEDED",
        "started_at_utc": raw_stage.get("started_at_utc"),
        "finished_at_utc": raw_stage.get("finished_at_utc"),
    }
    envelope_ref = _write_new_json(
        root / "t113-canary-stage-execution-envelope.json", stage_envelope
    )
    finalization = {
        "schema_id": T113_CANARY_FINALIZATION_SCHEMA,
        "task_id": T113_TASK_ID,
        "implementation_head": worktree["head"],
        "approved_spec_commit": T113_APPROVED_SPEC_COMMIT,
        "terminal_classification": "CANARY_PREFIX_PARITY_VALID",
        "complete": True,
        "direct_prefix_equivalence": True,
        "cohort_manifest_sha256": canonical_sha256(cohort),
        "authorization_artifact": _artifact_reference(
            authorization_path, schema_id=T113_CANARY_AUTHORIZATION_SCHEMA
        ),
        "qualification_artifact": qualification_ref,
        "fixed_cohort_artifact": cohort_ref,
        "readiness_artifact": readiness_ref,
        "raw_stage_manifest_artifact": raw_ref,
        "canary_evidence_artifact": evidence_ref,
        "stage_execution_envelope_artifact": envelope_ref,
        "native_identity": dict(T113_NATIVE_IDENTITY),
        "native_manifest_sha256": manifest_sha,
        "native_binary_sha256": binary_sha,
        "frozen_search_configuration": dict(T113_SEARCH_CONFIGURATION),
        "canary_authorized": True,
        "canary_started": True,
        "formal_execution_authorized": False,
        "formal_execution_started": False,
        "execution_authorization_created": False,
        "native_simulator_or_bridge_called": True,
        "next_action": "Maintainer independently reviews exact-head canary evidence and separately authorizes the formal stage if justified.",
    }
    final_ref = _write_new_json(root / "t113-canary-finalization.json", finalization)
    return {
        "finalization_artifact": final_ref,
        "canary_evidence_artifact": evidence_ref,
        "stage_execution_envelope_artifact": envelope_ref,
        "terminal_classification": finalization["terminal_classification"],
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="T113 separately authorized direct-canary readiness, execution, and finalization."
    )
    sub = parser.add_subparsers(dest="command", required=True)
    prep = sub.add_parser("prepare-readiness")
    prep.add_argument("--t112-retention-manifest", type=Path, required=True)
    prep.add_argument("--native-source-manifest", type=Path, required=True)
    prep.add_argument("--artifact-root", type=Path, required=True)
    prep.add_argument("--repo-root", type=Path, required=True)
    run = sub.add_parser("run")
    for arg in (
        "qualification",
        "fixed-cohort",
        "readiness",
        "authorization",
        "t112-retention-manifest",
        "native-source-manifest",
        "artifact-root",
        "repo-root",
    ):
        run.add_argument(f"--{arg}", type=Path, required=True)
    run.add_argument("--worker-id", required=True)
    finalize = sub.add_parser("finalize")
    for arg in (
        "raw-stage-manifest",
        "qualification",
        "fixed-cohort",
        "readiness",
        "authorization",
        "t112-retention-manifest",
        "native-source-manifest",
        "repo-root",
    ):
        finalize.add_argument(f"--{arg}", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "prepare-readiness":
            result = prepare_t113_canary_readiness_from_paths(
                t112_retention_manifest_path=args.t112_retention_manifest,
                native_manifest_path=args.native_source_manifest,
                artifact_root=args.artifact_root,
                repo_root=args.repo_root,
            )
        elif args.command == "run":
            result = run_t113_canary_from_paths(
                qualification_path=args.qualification,
                fixed_cohort_path=args.fixed_cohort,
                readiness_path=args.readiness,
                authorization_path=args.authorization,
                t112_retention_manifest_path=args.t112_retention_manifest,
                native_manifest_path=args.native_source_manifest,
                artifact_root=args.artifact_root,
                repo_root=args.repo_root,
                worker_id=args.worker_id,
            )
        else:
            result = finalize_t113_canary_from_paths(
                raw_stage_manifest_path=args.raw_stage_manifest,
                qualification_path=args.qualification,
                fixed_cohort_path=args.fixed_cohort,
                readiness_path=args.readiness,
                authorization_path=args.authorization,
                t112_retention_manifest_path=args.t112_retention_manifest,
                native_manifest_path=args.native_source_manifest,
                repo_root=args.repo_root,
            )
    except (
        OSError,
        T113WorkflowError,
        T113ConvergenceError,
        T113CanaryAuthorizationError,
        T113CanaryWorkflowError,
        T085NativeExecutionError,
    ) as exc:
        print(f"T113 canary failed closed: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "T113CanaryWorkflowError",
    "T113DirectCanaryRunner",
    "finalize_t113_canary_from_paths",
    "main",
    "prepare_t113_canary_readiness_from_paths",
    "run_t113_canary_from_paths",
]
