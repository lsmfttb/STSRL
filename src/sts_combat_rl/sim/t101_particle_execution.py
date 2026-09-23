"""Explicit native execution seams for the frozen T101 workflow.

Nothing in this module grants execution authority.  Canary and formal entry
points require exact Maintainer authorization records.  Native restores reuse
the accepted T085/T087 helpers, and every particle call goes through the
validated T099 bridge adapter.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Mapping, Sequence

from sts_combat_rl.commands.t085_native_execution import (
    T085NativeExecutionError,
    restore_t085_canonical_record,
)
from sts_combat_rl.sim.lightspeed_source import load_lightspeed_source_manifest
from sts_combat_rl.sim.public_run_context import (
    build_public_run_context,
    read_native_public_projection,
)
from sts_combat_rl.sim.t101_particle_convergence import (
    T101_COUNTS,
    T101_NATIVE_COMMIT,
    T101_NATIVE_REF,
    T101_SEARCH_SIMULATIONS,
    T101AdmissionExclusion,
    T101IncompleteError,
    _canonical_sha256,
    call_t101_bridge,
    derive_t101_sampler_seed,
    validate_t101_canary_ladder,
    validate_t101_formal_plan,
    validate_t101_input_admission,
    validate_t101_selected_cohort,
)


class T101ExecutionError(T101IncompleteError):
    """A T101 restore, authorization, or native execution boundary failed."""


def _current_native_identity() -> dict[str, object]:
    try:
        manifest = load_lightspeed_source_manifest()
    except (OSError, ValueError) as exc:
        raise T101ExecutionError(
            "current native source manifest is unavailable"
        ) from exc
    repository = manifest.integration.repository_url.rstrip("/").removesuffix(".git")
    identity = {
        "repository": repository.removeprefix("https://github.com/"),
        "ref": manifest.integration.ref,
        "commit": manifest.integration.commit,
    }
    if identity != {
        "repository": "lsmfttb/sts_lightspeed",
        "ref": T101_NATIVE_REF,
        "commit": T101_NATIVE_COMMIT,
    }:
        raise T101ExecutionError("current native identity differs from T101")
    if (
        "native_t096_public_information_hidden_future_sampler"
        not in (manifest.capability_ids)
        or "native_stsr006_particle_search_bridge" not in manifest.capability_ids
    ):
        raise T101ExecutionError("current manifest lacks T098/T099 capabilities")
    return identity


class T101NativeRecordRunner:
    """Restore only accepted records and call only the sanitized T099 bridge."""

    def __init__(
        self,
        *,
        adapter_factory: Callable[[], object],
        selected_records: Mapping[str, object],
        canonical_records_by_stratum: Mapping[str, Mapping[str, object]],
    ) -> None:
        if not callable(adapter_factory) or not selected_records:
            raise T101ExecutionError("native record runner inputs are unavailable")
        self._adapter_factory = adapter_factory
        self._selected_records = dict(selected_records)
        self._canonical_records_by_stratum = {
            str(name): dict(records)
            for name, records in canonical_records_by_stratum.items()
        }

    def _restore(self, record: Mapping[str, object]) -> tuple[object, object, str]:
        identity = record.get("selection_identity")
        stratum = record.get("cohort", record.get("stratum"))
        if not isinstance(identity, str) or stratum not in {"A", "B", "C"}:
            raise T101ExecutionError("T101 record identity/stratum is malformed")
        selected = self._selected_records.get(identity)
        canonical_map = self._canonical_records_by_stratum.get(str(stratum))
        if selected is None or canonical_map is None or identity not in canonical_map:
            raise T101ExecutionError("record is not an accepted retained restore")
        _current_native_identity()
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
            raise T101ExecutionError(
                f"{identity}: current-native restore failed"
            ) from exc
        if not isinstance(expected, Mapping) or actual != expected:
            raise T101ExecutionError(
                f"{identity}: restored public projection/legal actions changed"
            )
        return adapter, restored, method

    def admit(
        self,
        record: Mapping[str, object],
        *,
        worker_id: str,
        single_worker_reason: str,
    ) -> dict[str, object]:
        if (
            not isinstance(worker_id, str)
            or not worker_id
            or not isinstance(single_worker_reason, str)
            or not single_worker_reason
        ):
            raise T101ExecutionError(
                "support-admission worker identity/reason is missing"
            )
        adapter, restored, method = self._restore(record)
        seed = derive_t101_sampler_seed(str(record["selection_identity"]), 0)
        started = time.perf_counter()
        try:
            report = call_t101_bridge(
                adapter, restored, sampler_seed=seed, particle_count=2
            )
        except (RuntimeError, TypeError, ValueError) as exc:
            raise T101AdmissionExclusion(
                f"{record['selection_identity']}: bounded admission bridge failed",
                bridge_call_runtime={
                    "wall_clock_time_s": time.perf_counter() - started,
                    "particle_count": 2,
                    "search_simulations_per_particle": T101_SEARCH_SIMULATIONS,
                    "worker_id": worker_id,
                    "shard_index": 0,
                    "effective_concurrency": 1,
                    "failure_retry_status": "failed_no_retry",
                    "retry_reason": None,
                    "single_worker_reason": single_worker_reason,
                },
            ) from exc
        return {
            "restore_exact_accepted_state": True,
            "public_projection_parity": True,
            "ordered_legal_action_parity": True,
            "occurrence_mapping_complete": True,
            "search_configuration_unchanged": True,
            "restore_method": method,
            "bridge_report": report,
            "bridge_call_runtime": {
                "wall_clock_time_s": time.perf_counter() - started,
                "particle_count": 2,
                "search_simulations_per_particle": T101_SEARCH_SIMULATIONS,
                "worker_id": worker_id,
                "shard_index": 0,
                "effective_concurrency": 1,
                "failure_retry_status": "success_no_retry",
                "retry_reason": None,
                "single_worker_reason": single_worker_reason,
            },
        }

    def canary_ladder(self, record: Mapping[str, object]) -> dict[str, object]:
        adapter, restored, method = self._restore(record)
        identity = str(record["selection_identity"])
        seed = derive_t101_sampler_seed(identity, 0)
        calls: dict[str, object] = {}
        for count in T101_COUNTS:
            started = time.perf_counter()
            try:
                report = call_t101_bridge(
                    adapter, restored, sampler_seed=seed, particle_count=count
                )
            except (RuntimeError, TypeError, ValueError) as exc:
                raise T101ExecutionError(
                    f"{identity}: direct canary N={count} bridge failed"
                ) from exc
            calls[str(count)] = {
                "wall_clock_time_s": time.perf_counter() - started,
                "bridge_report": report,
            }
        return {
            "selection_identity": identity,
            "stratum": record.get("stratum", record.get("cohort")),
            "replicate_index": 0,
            "sampler_seed": seed,
            "restore_method": method,
            "calls": calls,
        }

    def formal_job(self, job: Mapping[str, object]) -> dict[str, object]:
        adapter, restored, method = self._restore(job)
        seed = job.get("sampler_seed")
        if isinstance(seed, bool) or not isinstance(seed, int):
            raise T101ExecutionError("formal job sampler seed is invalid")
        started = time.perf_counter()
        try:
            report = call_t101_bridge(
                adapter, restored, sampler_seed=seed, particle_count=32
            )
        except (RuntimeError, TypeError, ValueError) as exc:
            raise T101ExecutionError(
                f"{job['selection_identity']}: formal N=32 bridge failed"
            ) from exc
        return {
            "job_ordinal": job["job_ordinal"],
            "shard_index": job["shard_index"],
            "selection_identity": job["selection_identity"],
            "stratum": job["stratum"],
            "replicate_index": job["replicate_index"],
            "sampler_seed": seed,
            "bridge_report": report,
            "wall_clock_time_s": time.perf_counter() - started,
            "restore_method": method,
            "retry_reason": None,
            "failure_retry_status": "success_no_retry",
        }


def _authorization(
    value: object,
    *,
    schema_id: str,
    kind: str,
    implementation_head: str,
    bindings: Mapping[str, str],
) -> dict[str, object]:
    if (
        not isinstance(implementation_head, str)
        or len(implementation_head) != 40
        or any(character not in "0123456789abcdef" for character in implementation_head)
    ):
        raise T101ExecutionError(f"{kind} implementation head is invalid")
    if not isinstance(value, Mapping):
        raise T101ExecutionError(f"{kind} authorization is missing")
    required = {
        "schema_id",
        "task_id",
        "authorization_kind",
        "authorized",
        "authorization_id",
        "implementation_head",
        *bindings,
        "maintainer_attestation",
    }
    if (
        set(value) != required
        or value.get("schema_id") != schema_id
        or value.get("task_id") != "T101"
        or value.get("authorization_kind") != kind
        or value.get("authorized") is not True
        or not isinstance(value.get("authorization_id"), str)
        or not value["authorization_id"]
        or value.get("implementation_head") != implementation_head
        or any(value.get(name) != digest for name, digest in bindings.items())
    ):
        raise T101ExecutionError(f"{kind} authorization binding is invalid")
    attestation = value.get("maintainer_attestation")
    if not isinstance(attestation, Mapping) or dict(attestation) != {
        "role": "maintainer",
        "decision": (
            "CANARY_AUTHORIZED" if kind == "bounded_canary" else "FORMAL_AUTHORIZED"
        ),
        "exact_head": implementation_head,
    }:
        raise T101ExecutionError(f"{kind} Maintainer attestation is invalid")
    return dict(value)


def execute_t101_canary(
    *,
    authorization: object,
    implementation_head: str,
    input_admission: Mapping[str, object],
    cohort_admission: Mapping[str, object],
    runner: T101NativeRecordRunner,
    worker_id: str,
) -> dict[str, object]:
    if not isinstance(worker_id, str) or not worker_id:
        raise T101ExecutionError("canary worker identity is missing")
    validate_t101_input_admission(input_admission)
    cohort = validate_t101_selected_cohort(cohort_admission)
    bindings = {
        "input_admission_sha256": _canonical_sha256(input_admission),
        "cohort_admission_sha256": _canonical_sha256(cohort_admission),
    }
    auth = _authorization(
        authorization,
        schema_id="t101-maintainer-canary-authorization-v1",
        kind="bounded_canary",
        implementation_head=implementation_head,
        bindings=bindings,
    )
    selected = [
        next(row for row in cohort if row["stratum"] == name)
        for name in ("A", "B", "C")
    ]
    ladders: list[dict[str, object]] = []
    for row in selected:
        raw = runner.canary_ladder(row)
        calls = raw.get("calls") if isinstance(raw, Mapping) else None
        if not isinstance(calls, Mapping):
            raise T101ExecutionError("canary runner returned malformed calls")
        annotated = dict(raw)
        annotated["calls"] = {
            str(count): {
                **dict(calls[str(count)]),
                "worker_id": worker_id,
                "shard_index": 0,
                "effective_concurrency": 1,
                "failure_retry_status": "success_no_retry",
                "single_worker_reason": "bounded three-state direct-ladder canary",
            }
            for count in T101_COUNTS
            if isinstance(calls.get(str(count)), Mapping)
        }
        ladders.append(validate_t101_canary_ladder(annotated))
    return {
        "schema_id": "t101-canary-evidence-v1",
        "task_id": "T101",
        "implementation_head": implementation_head,
        "authorization": auth,
        "selected": [
            {
                "selection_identity": row["selection_identity"],
                "stratum": row["stratum"],
                "replicate_index": 0,
            }
            for row in selected
        ],
        "ladders": ladders,
        "direct_prefix_equivalence": True,
        "complete": True,
    }


def execute_t101_formal_shard(
    *,
    authorization: object,
    implementation_head: str,
    plan: Mapping[str, object],
    canary_evidence_reference: Mapping[str, object],
    shard_index: int,
    runner: T101NativeRecordRunner,
    worker_id: str,
    effective_concurrency: int,
    retry_reason: str | None = None,
) -> dict[str, object]:
    plan = validate_t101_formal_plan(plan)
    topology = plan["topology"]
    jobs = plan["jobs"]
    assert isinstance(topology, Mapping)
    assert isinstance(jobs, Sequence) and not isinstance(jobs, (str, bytes))
    shard_count = topology.get("shard_count")
    if (
        isinstance(shard_count, bool)
        or not isinstance(shard_count, int)
        or shard_index not in range(shard_count)
    ):
        raise T101ExecutionError("formal shard index is invalid")
    canary_sha = canary_evidence_reference.get("sha256")
    if not isinstance(canary_sha, str) or len(canary_sha) != 64:
        raise T101ExecutionError("accepted canary reference is invalid")
    auth = _authorization(
        authorization,
        schema_id="t101-maintainer-formal-authorization-v1",
        kind="formal_particle_diagnostic",
        implementation_head=implementation_head,
        bindings={
            "formal_plan_sha256": _canonical_sha256(plan),
            "canary_evidence_sha256": canary_sha,
        },
    )
    if (
        not worker_id
        or isinstance(effective_concurrency, bool)
        or not isinstance(effective_concurrency, int)
        or effective_concurrency < 1
        or effective_concurrency > int(topology["worker_count"])
    ):
        raise T101ExecutionError("formal worker identity/concurrency is invalid")
    if retry_reason not in {None, "operational_failure_identical_inputs"}:
        raise T101ExecutionError("formal retry reason is not operational")
    assigned = [
        job
        for job in jobs
        if isinstance(job, Mapping) and job.get("shard_index") == shard_index
    ]
    rows: list[dict[str, object]] = []
    started = time.perf_counter()
    for job in assigned:
        row = runner.formal_job(job)
        row["worker_id"] = worker_id
        row["effective_concurrency"] = effective_concurrency
        row["retry_reason"] = retry_reason
        row["failure_retry_status"] = (
            "success_after_operational_retry"
            if retry_reason is not None
            else "success_no_retry"
        )
        rows.append(row)
    shard_wall_clock_time_s = time.perf_counter() - started
    return {
        "schema_id": "t101-formal-shard-v1",
        "task_id": "T101",
        "implementation_head": implementation_head,
        "authorization_id": auth["authorization_id"],
        "formal_plan_sha256": _canonical_sha256(plan),
        "canary_evidence_sha256": canary_sha,
        "shard_index": shard_index,
        "shard_count": shard_count,
        "worker_id": worker_id,
        "effective_concurrency": effective_concurrency,
        "job_ordinals": [job["job_ordinal"] for job in assigned],
        "wall_clock_time_s": shard_wall_clock_time_s,
        "rows": rows,
        "complete": len(rows) == len(assigned),
    }


__all__ = [
    "T101ExecutionError",
    "T101NativeRecordRunner",
    "execute_t101_canary",
    "execute_t101_formal_shard",
]
