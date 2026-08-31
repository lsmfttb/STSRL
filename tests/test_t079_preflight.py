from __future__ import annotations

import pytest

from scripts.run_t079_preflight import _validate_preflight_worker_evidence


def _worker_rows() -> list[dict[str, object]]:
    return [
        {
            "record_index": index,
            "worker_pid": 1000 + index,
            "spawned_process_pid": 1000 + index,
            "worker_started_monotonic": 0.0,
            "worker_finished_monotonic": 10.0,
            "worker_logical_cpu_count": 16,
            "worker_cpu_affinity": list(range(16)),
            "worker_exit_code": 0,
        }
        for index in range(16)
    ]


def test_preflight_worker_evidence_proves_sixteen_effective_workers() -> None:
    evidence = _validate_preflight_worker_evidence(_worker_rows())

    assert evidence["worker_count"] == 16
    assert evidence["shard_count"] == 16
    assert evidence["effective_worker_count"] == 16
    assert evidence["observed_peak_concurrency"] == 16
    assert len(evidence["worker_pid_map"]) == 16


@pytest.mark.parametrize(
    "mutation",
    [
        lambda rows: rows[0].update(spawned_process_pid=9999),
        lambda rows: rows[1].update(worker_exit_code=7),
        lambda rows: rows[2].update(worker_pid=1001),
    ],
)
def test_preflight_worker_evidence_rejects_unproven_topology(mutation) -> None:
    rows = _worker_rows()
    mutation(rows)

    with pytest.raises(ValueError, match="worker|exit code"):
        _validate_preflight_worker_evidence(rows)
