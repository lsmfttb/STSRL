"""Pinned, native-free T092 canary restore-map recipe.

The callable is imported only after a real Maintainer authorization has been
validated by :mod:`t092_canary_execution`.  It admits the existing T087/T085
artifacts through their established verifier, projects the immutable T090
ledger, and returns no adapter or native module object.  Each actual arm is
subsequently created in a fresh child process by the isolated runner.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from sts_combat_rl.commands.t088_canary import _admit_t088_canary_inputs_from_paths
from sts_combat_rl.sim.t090_battle_student import validate_t090_split_manifest
from sts_combat_rl.sim.t092_canary import select_t092_canary_entries
from sts_combat_rl.sim.t092_canary_process import T092CanaryProcessError

T092_SHARED_ARTIFACT_ROOT = Path("/mnt/d/DeadlyCatCoding/STSRL/artifacts")
T092_SPLIT_MANIFEST_PATH = T092_SHARED_ARTIFACT_ROOT / "t090-formal-413-2bfcb27-20260915-retry1/t090-split-manifest.json"
T092_T087_FORMAL_PATH = T092_SHARED_ARTIFACT_ROOT / "t087-formal-natural-413-8d7e44-20260911/t087-formal-natural-evidence.json"
T092_T087_REPORT_PATH = T092_SHARED_ARTIFACT_ROOT / "t087-final-8d7e44-20260911/t087-dense-combat-diagnostics-report.json"
T092_T087_RETENTION_PATH = T092_SHARED_ARTIFACT_ROOT / "t087-final-8d7e44-20260911/t087-retention-manifest.json"
T092_T085_ROOT = T092_SHARED_ARTIFACT_ROOT / "t085-corrected-leaf-value-search-repair"
T092_T085_SELECTION_PATH = T092_T085_ROOT / "selection/t085-native-selection.json"
T092_T085_RESTORE_PATH = T092_T085_ROOT / "selection/t085-native-selection-restore-evidence.json"
T092_A_POOL_PATH = Path("/mnt/d/DeadlyCatCoding/STSRL/artifacts/t052-t051-boss-later-act-fixed-cohort-diagnostic-pr/t052-fixed-cohort.jsonl")
T092_B_ROOT = T092_T085_ROOT / "source/cohort-b-formal-d62ff35579b54d70a7428afdf84743c94df3fe0c"
T092_C_ROOT = T092_T085_ROOT / "source/cohort-c-formal-d62ff35579b54d70a7428afdf84743c94df3fe0c"

T092_CANARY_ARM_PROCESS_SPECS = {
    "OFF": {
        "python_executable": "/usr/bin/python3.14",
        "extension_path": "/home/lsmft/stsrl-spikes/sts_lightspeed-t088-20a6/build-py/slaythespire.cpython-314-x86_64-linux-gnu.so",
        "extension_sha256": "b996f949e77b3d76a3991c4e24977c80722f0e09e1e0f235384a4158ee6351bb",
        "extension_size_bytes": 1632040,
        "native_identity": {
            "repository": "lsmfttb/sts_lightspeed", "ref": "refs/heads/stsrl/main",
            "commit": "20a6c2b3a9cea817c988178b814f083ff889853f",
        },
        "stsrl_source_root": "/mnt/d/DeadlyCatCoding/STSRL-T092/src",
    },
    "ON": {
        "python_executable": "/usr/bin/python3.14",
        "extension_path": "/mnt/d/DeadlyCatCoding/sts_lightspeed-T092/build-t092-py/slaythespire.cpython-314-x86_64-linux-gnu.so",
        "extension_sha256": "0a9ba8127c3970a7b3bf2093f005527f1d567e37d3062fa116d1729be621e7af",
        "extension_size_bytes": 1648424,
        "native_identity": {
            "repository": "lsmfttb/sts_lightspeed", "ref": "refs/heads/planner/t092-internal-search-state-telemetry",
            "commit": "07e1770cf0710d8c26719c153383d09e3bfd7686",
        },
        "stsrl_source_root": "/mnt/d/DeadlyCatCoding/STSRL-T092/src",
    },
}


def t092_canary_runtime_input_identities() -> Mapping[str, Any]:
    """Return the reviewable, canonical identity map without loading a pool."""

    path = Path(__file__).resolve().parents[3] / "docs/t092_canary_runtime_identity_map.json"
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise T092CanaryProcessError("T092 runtime identity map is unavailable") from exc
    if (
        not isinstance(value, Mapping)
        or value.get("schema_id") != "t092-canary-runtime-input-identities-v2"
        or value.get("schema_version") != 2
        or value.get("task_id") != "T092"
        or value.get("execution_authorized") is not False
        or value.get("runtime_factory")
        != "sts_combat_rl.commands.t092_canary_runtime:t092_canary_runtime"
    ):
        raise T092CanaryProcessError("T092 runtime identity map is malformed")
    return dict(value)


def t092_canary_runtime() -> Mapping[str, Any]:
    """Return exactly the admitted restore maps and isolated arm specifications."""

    try:
        split = json.loads(T092_SPLIT_MANIFEST_PATH.read_text(encoding="utf-8"))
        if not isinstance(split, Mapping):
            raise ValueError("split ledger is not an object")
        validate_t090_split_manifest(split)
        _formal, gate, _identities = _admit_t088_canary_inputs_from_paths(
            implementation_head="f" * 40,
            t087_formal_path=T092_T087_FORMAL_PATH,
            t087_report_path=T092_T087_REPORT_PATH,
            t087_retention_path=T092_T087_RETENTION_PATH,
            t085_selection_path=T092_T085_SELECTION_PATH,
            t085_restore_path=T092_T085_RESTORE_PATH,
            a_pool_path=T092_A_POOL_PATH,
            b_pool_path=T092_B_ROOT / "cohort-b-merged.pool.jsonl",
            c_pool_path=T092_C_ROOT / "cohort-c-merged.pool.jsonl",
            b_source_manifest_path=T092_B_ROOT / "cohort-b-source-manifest.json",
            c_source_manifest_path=T092_C_ROOT / "cohort-c-source-manifest.json",
        )
    except (OSError, ValueError) as exc:
        raise T092CanaryProcessError("T092 accepted restore maps are unavailable") from exc
    source_records: dict[str, object] = {}
    canonical_records: dict[str, object] = {}
    for source in select_t092_canary_entries(split):
        cohort = source.source_group
        selected = next(
            (row for row in gate.cohorts[cohort] if row.selection_identity == source.source_identity),
            None,
        )
        canonical = gate.canonical_records_by_cohort[cohort].get(source.source_identity)
        if selected is None or canonical is None:
            raise T092CanaryProcessError("T092 selected source lacks an accepted restore map")
        source_records[source.source_identity] = selected
        canonical_records[source.source_identity] = canonical
    if len(source_records) != 12 or set(source_records) != set(canonical_records):
        raise T092CanaryProcessError("T092 canary restore maps are incomplete")
    return {
        "arm_process_specs": T092_CANARY_ARM_PROCESS_SPECS,
        "source_records": source_records,
        "canonical_records": canonical_records,
    }


__all__ = [
    "T092_CANARY_ARM_PROCESS_SPECS", "t092_canary_runtime",
    "t092_canary_runtime_input_identities",
]
