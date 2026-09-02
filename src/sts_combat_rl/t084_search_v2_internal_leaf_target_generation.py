"""Versioned, fail-closed T084 internal-leaf target-generation audit.

The native collector is deliberately an optional integration surface.  This
module owns the stable evidence contract around that surface: exact inputs,
identity checks, leaf/replicate validation, calibration, quotas, ambiguity,
and the four terminal classifications.  It never reconstructs a hidden state
from a public projection or an ``exactStateDigest``.
"""

from __future__ import annotations

import hashlib
import json
import math
import subprocess
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from statistics import median
from typing import Any

SCHEMA_ID = "t084-search-v2-internal-leaf-target-generation-v1"
COLLECTOR_SCHEMA_ID = "t084-native-internal-leaf-collector-v1"
RETENTION_SCHEMA_ID = "t084-retention-manifest-v1"
EXPECTED_MAIN_COMMIT = "cd2087f2f403d9e16c7e6dde759488e84981582c"
EXPECTED_MAIN_REF = "refs/heads/main"
EXPECTED_NATIVE_COMMIT = "1555348535d66e3035aac80933a60949d4bd850f"
EXPECTED_NATIVE_REF = "refs/heads/stsrl/main"
EXPECTED_T082_REPORT_SHA = (
    "e1435812abed86d9ddb4c857cba1863edf852f1e956db9fc002e043a4eb2febc"
)
EXPECTED_T083_REPORT_SHA = (
    "459216b35ef93c4ca3c5f5183e2af73baf82fd612e4edfb195061f9b0e0d308f"
)
EXPECTED_T064_ARTIFACTS = {
    "t064-curriculum-manifest.json": (
        "a111e082d4bc11e03bc5b785a814c422619404245ddda55c2954be09dded46c7",
        "t064-curriculum-manifest-v1",
    ),
    "t064-training-run-report.json": (
        "3e838bed72f5ca565532d39d77b1991e0d32919dcd9b1d6afe4d2c8f8ecdc38c",
        "t064-training-run-report-v1",
    ),
    "t064-stage-summary.json": (
        "5748e79a23152fa51475f8cb7359c81816d6bbdd26ed2a10d7489f1853b6b880",
        "t064-stage-summary-v1",
    ),
    "t064-transfer-decision.json": (
        "f8407acbc17cb13bba53009c91009fea961e7307071d54b0ff82147ff092603f",
        "t064-transfer-decision-v1",
    ),
}
EXPECTED_T064_TEACHER_SHA = (
    "1352eb301509f258ae92509b804125d59d2da17ef5f7f6e5b81131f11e1d0d72"
)
EXPECTED_T064_TRAINER_SHA = (
    "aae847505ece7c4d535d08cffc9e24bc2aaead334234332f41c69f0b2c99bada"
)
EXPECTED_STATIC_CHECKPOINTS = {
    "prior_only_static_64001": (
        "c0c38c239047f6be67e983768e53bd680007e9cba117e17c7d226583ed751193",
        "static_mixture_v1-64001.pt",
    ),
    "prior_only_static_64002": (
        "32dbf18a187e8b6d465bb026d90643e3dd28624066628019c61455fcd8f5573a",
        "static_mixture_v1-64002.pt",
    ),
}
ARMS = (
    "unguided_search_v2",
    "prior_only_static_64001",
    "prior_only_static_64002",
)
ACT_COUNTS = {1: 256, 2: 204}
ARM_ROW_COUNT = 320
CALIBRATION_COUNT = 96
FORMAL_ROW_COUNT = 960
CALIBRATION_REPLICATES = 256
CANDIDATE_REPETITIONS = (16, 32, 64, 100, 128)
ACTION_CAP = 2048
WORKER_COUNT = 16
FORMAL_ACT_COUNTS = {1: 178, 2: 142}
CLASSIFICATIONS = (
    "LEAF_CONTINUATION_UTILITY_TARGETS_READY",
    "LEAF_TARGET_MONTE_CARLO_UNSTABLE",
    "LEAF_TARGET_SUPPORT_INSUFFICIENT",
    "INCOMPLETE",
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, Mapping):
        raise TypeError(f"{path} is not a JSON object")
    return dict(value)


def _path(value: object) -> Path:
    if not isinstance(value, str) or not value:
        raise ValueError("artifact path is missing")
    return Path(value.replace("D:\\", "/mnt/d/").replace("\\", "/"))


def _finite(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    result = float(value)
    return result if math.isfinite(result) else None


def _percentile(values: Sequence[float], fraction: float) -> float | None:
    ordered = sorted(float(value) for value in values if math.isfinite(float(value)))
    if not ordered:
        return None
    if len(ordered) == 1:
        return ordered[0]
    position = fraction * (len(ordered) - 1)
    low = math.floor(position)
    high = math.ceil(position)
    return ordered[low] + (ordered[high] - ordered[low]) * (position - low)


def value_stats(
    values: Iterable[object], *, available_rows: int | None = None
) -> dict[str, Any]:
    finite = [value for raw in values if (value := _finite(raw)) is not None]
    return {
        "available_rows": len(finite) if available_rows is None else available_rows,
        "finite_value_count": len(finite),
        "min": min(finite) if finite else None,
        "median": median(finite) if finite else None,
        "mean": sum(finite) / len(finite) if finite else None,
        "p05": _percentile(finite, 0.05),
        "p95": _percentile(finite, 0.95),
        "max": max(finite) if finite else None,
    }


def derive_replicate_seed(
    native_commit: str,
    source_complete_identity_sha256: str,
    sampling_arm: str,
    exact_leaf_identity: str,
    replicate_index: int,
) -> dict[str, Any]:
    """Derive the frozen uint32 search-action seed and retain its full input."""

    if isinstance(replicate_index, bool) or replicate_index < 1:
        raise ValueError("replicate_index must be a positive integer")
    digest_input = "|".join(
        (
            native_commit,
            source_complete_identity_sha256,
            sampling_arm,
            exact_leaf_identity,
            str(replicate_index),
        )
    )
    digest = hashlib.sha256(digest_input.encode("utf-8")).hexdigest()
    return {
        "digest_input": digest_input,
        "sha256": digest,
        "seed": int(digest[:8], 16),
        "replicate_index": replicate_index,
    }


def _git_ref_commit(repository: Path, ref: str) -> str | None:
    try:
        process = subprocess.run(
            [
                "git",
                "-C",
                str(repository),
                "rev-parse",
                "--verify",
                f"{ref}^{{commit}}",
            ],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return process.stdout.strip()


def _git_show(
    repository: Path, commit: str, relative: str
) -> tuple[str | None, str | None]:
    try:
        process = subprocess.run(
            ["git", "-C", str(repository), "show", f"{commit}:{relative}"],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
    except (OSError, subprocess.CalledProcessError):
        return None, None
    content = process.stdout
    return content, hashlib.sha256(content.encode("utf-8")).hexdigest()


def _file_check(
    path: Path, expected_sha: str, expected_schema: str | None = None
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "path": str(path),
        "expected_sha256": expected_sha,
        "sha256": None,
        "bytes": None,
        "schema_id": None,
        "expected_schema_id": expected_schema,
        "valid": False,
    }
    if not path.exists():
        result["reason"] = "missing artifact"
        return result
    result["bytes"] = path.stat().st_size
    try:
        result["sha256"] = sha256_file(path)
        if expected_schema is not None:
            parsed = _json(path)
            result["schema_id"] = parsed.get("schema_id")
            result["valid"] = (
                result["sha256"] == expected_sha
                and result["schema_id"] == expected_schema
            )
        else:
            result["valid"] = result["sha256"] == expected_sha
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        result["reason"] = str(exc)
    return result


def _accepted_report_check(
    path: Path, expected_sha: str, schema_key: str, expected_schema: str
) -> dict[str, Any]:
    result = _file_check(path, expected_sha)
    if not result["valid"]:
        return result
    try:
        payload = _json(path)
        result["schema_key"] = schema_key
        result["schema_id"] = payload.get(schema_key)
        result["schema_valid"] = result["schema_id"] == expected_schema
        result["classification"] = payload.get("classification")
        result["valid"] = result["schema_valid"]
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        result["valid"] = False
        result["reason"] = str(exc)
    return result


def validate_code_identity(repo_root: Path) -> dict[str, Any]:
    """Resolve main and compare audit source bytes against that resolved ref."""

    resolved = _git_ref_commit(repo_root, EXPECTED_MAIN_REF)
    source_files = (
        "src/sts_combat_rl/sim/battle_search_v2.py",
        "src/sts_combat_rl/sim/torch_policy_value.py",
        "src/sts_combat_rl/sim/oracle_teacher_search_guidance.py",
    )
    files: dict[str, Any] = {}
    source_matches = resolved == EXPECTED_MAIN_COMMIT
    for relative in source_files:
        current = repo_root / relative
        _main_source, main_sha = _git_show(repo_root, EXPECTED_MAIN_REF, relative)
        current_sha = sha256_file(current) if current.exists() else None
        matches = (
            current_sha is not None and main_sha is not None and current_sha == main_sha
        )
        source_matches = source_matches and matches
        files[relative] = {
            "available": current.exists(),
            "sha256": current_sha,
            "main_sha256": main_sha,
            "source_matches_main": matches,
        }
    return {
        "ref": EXPECTED_MAIN_REF,
        "resolved_commit": resolved,
        "expected_commit": EXPECTED_MAIN_COMMIT,
        "ref_identity_valid": resolved == EXPECTED_MAIN_COMMIT,
        "source_matches_main": source_matches,
        "files": files,
    }


def validate_native_identity(
    native_root: Path,
    *,
    runtime_ref: str | None = None,
    runtime_commit: str | None = None,
    build_path: str | None = None,
    abi: str | None = None,
    verifier_result: str | None = None,
) -> dict[str, Any]:
    baseline_resolved = _git_ref_commit(native_root, EXPECTED_NATIVE_REF)
    selected_ref = runtime_ref or EXPECTED_NATIVE_REF
    resolved = _git_ref_commit(native_root, selected_ref)
    expected_runtime = runtime_commit or (
        EXPECTED_NATIVE_COMMIT if runtime_ref is None else resolved
    )
    source_files = (
        "include/sim/search/BattleScumSearcher2.h",
        "src/sim/search/BattleScumSearcher2.cpp",
        "bindings/slaythespire.cpp",
    )
    files: dict[str, Any] = {}
    for relative in source_files:
        content, digest = _git_show(native_root, selected_ref, relative)
        files[relative] = {"available": content is not None, "sha256": digest}
    return {
        "ref": selected_ref,
        "resolved_commit": resolved,
        "expected_commit": expected_runtime,
        "baseline_ref": EXPECTED_NATIVE_REF,
        "baseline_resolved_commit": baseline_resolved,
        "baseline_identity_valid": baseline_resolved == EXPECTED_NATIVE_COMMIT,
        "identity_valid": resolved == expected_runtime
        and all(item["available"] for item in files.values()),
        "files": files,
        "build": {
            "path": build_path,
            "abi": abi,
            "source_verifier_result": verifier_result,
        },
        "collector_api": {
            "required": "StepSimulator.battle_search_v2_with_leaf_collection",
            "accepted_baseline_provides": False,
            "reason": "accepted T079 surface exports exactStateDigest/path metadata but no restorable post-action BattleContext payload",
        },
    }


def validate_native_probe(
    probe: Mapping[str, Any] | None, native: Mapping[str, Any]
) -> dict[str, Any]:
    """Validate runtime/API evidence independently of source path names."""

    required_methods = {
        "battle_search_v2_with_leaf_collection",
        "evaluate_leaf_continuation",
        "capture_checkpoint",
        "restore_checkpoint",
    }
    methods = probe.get("api_methods") if isinstance(probe, Mapping) else None
    method_values = methods if isinstance(methods, Mapping) else {}
    method_valid = all(method_values.get(name) is True for name in required_methods)
    executable = probe.get("python_executable") if isinstance(probe, Mapping) else None
    version = probe.get("python_version") if isinstance(probe, Mapping) else None
    extension = probe.get("extension") if isinstance(probe, Mapping) else None
    runtime_commit = probe.get("native_commit") if isinstance(probe, Mapping) else None
    valid = bool(
        method_valid
        and isinstance(executable, str)
        and executable.endswith("/py313-torch/bin/python")
        and isinstance(version, str)
        and version.startswith("3.13.")
        and isinstance(extension, str)
        and "cpython-313-" in extension
        and runtime_commit == native.get("resolved_commit")
        and native.get("identity_valid") is True
    )
    return {
        "available": isinstance(probe, Mapping),
        "valid": valid,
        "required_methods": sorted(required_methods),
        "api_methods": dict(method_values),
        "python_executable": executable,
        "python_version": version,
        "extension": extension,
        "native_commit": runtime_commit,
        "reason": None
        if valid
        else "missing or conflicting CPython 3.13 runtime/API/source identity evidence",
    }


def _selected_sources(
    manifest: Mapping[str, Any],
) -> tuple[list[Mapping[str, Any]], list[str]]:
    selected = manifest.get("selected_sources")
    problems: list[str] = []
    if not isinstance(selected, list) or len(selected) != 460:
        return [], ["T064 selected_sources is not exactly 460 rows"]
    rows: list[Mapping[str, Any]] = []
    for index, item in enumerate(selected):
        if not isinstance(item, Mapping):
            problems.append(f"T064 selected source {index} is malformed")
            continue
        identity = item.get("complete_identity")
        if not isinstance(identity, Mapping) or item.get(
            "complete_identity_sha256"
        ) != identity.get("complete_identity_sha256"):
            problems.append(f"T064 selected source {index} identity is incomplete")
        rows.append(item)
    identities = [str(item.get("complete_identity_sha256")) for item in rows]
    if len(set(identities)) != len(identities):
        problems.append("T064 selected-source complete identities are not unique")
    if Counter(item.get("act") for item in rows) != Counter(ACT_COUNTS):
        problems.append("T064 Act counts do not match 256/204")
    expected_components = {
        "assist_0": 256,
        "assist_hp50": 12,
        "assist_hp50_potion_elite_boss": 32,
        "assist_hp75_potion": 160,
    }
    if Counter(item.get("component") for item in rows) != Counter(expected_components):
        problems.append("T064 component counts do not match accepted lineage")
    return rows, problems


def validate_t064_inputs(t064_root: Path) -> dict[str, Any]:
    checks = [
        _file_check(t064_root / name, expected_sha, schema)
        for name, (expected_sha, schema) in EXPECTED_T064_ARTIFACTS.items()
    ]
    problems = [
        f"invalid T064 artifact: {item['path']}" for item in checks if not item["valid"]
    ]
    try:
        manifest = _json(t064_root / "t064-curriculum-manifest.json")
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        return {
            "valid": False,
            "problems": problems + [str(exc)],
            "artifact_checks": checks,
            "selected_sources": [],
        }
    selected, selected_problems = _selected_sources(manifest)
    problems.extend(selected_problems)
    transfer_path = t064_root / "t064-transfer-decision.json"
    try:
        transfer = _json(transfer_path)
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        transfer = {}
        problems.append(str(exc))
    if transfer.get("terminal_case") != "Case B" or not all(
        transfer.get(key) is True
        for key in ("experiment_complete", "source_adequacy", "source_integrity_valid")
    ):
        problems.append(
            "T064 transfer decision is not complete/adequate/integrity-valid Case B"
        )
    artifacts = manifest.get("input_artifacts", {})
    pool_checks: list[dict[str, Any]] = []
    if not isinstance(artifacts, Mapping):
        problems.append("T064 input_artifacts is unavailable")
        artifacts = {}
    for component in (
        "assist_0",
        "assist_hp50",
        "assist_hp50_potion_elite_boss",
        "assist_hp75_potion",
    ):
        spec = artifacts.get(component)
        if not isinstance(spec, Mapping):
            problems.append(f"T064 pool identity unavailable: {component}")
            continue
        try:
            path = _path(spec.get("path"))
            present = path.exists() and path.stat().st_size == spec.get("bytes")
        except (OSError, ValueError):
            path, present = Path(str(spec.get("path"))), False
        pool_checks.append(
            {
                "component": component,
                "path": str(path),
                "sha256": spec.get("sha256"),
                "bytes": path.stat().st_size if path.exists() else None,
                "expected_bytes": spec.get("bytes"),
                "schema_id": spec.get("schema_id"),
                "record_count": spec.get("record_count"),
                "hash_verified": False,
                "verification_mode": "accepted_T064_manifest_identity_plus_size",
                "valid": present
                and spec.get("schema_id") == "assisted-run-source-pool-v1"
                and isinstance(spec.get("sha256"), str)
                and len(spec["sha256"]) == 64,
            }
        )
        if not pool_checks[-1]["valid"]:
            problems.append(f"invalid T064 pool identity: {component}")
    static_checkpoints: dict[str, dict[str, Any]] = {}
    for arm, (expected_sha, filename) in EXPECTED_STATIC_CHECKPOINTS.items():
        checkpoint = t064_root / "training" / "checkpoints" / filename
        actual_sha = sha256_file(checkpoint) if checkpoint.exists() else None
        valid = actual_sha == expected_sha
        static_checkpoints[arm] = {
            "expected_sha256": expected_sha,
            "sha256": actual_sha,
            "bytes": checkpoint.stat().st_size if checkpoint.exists() else None,
            "filename": filename,
            "path": str(checkpoint),
            "available": checkpoint.exists(),
            "valid": valid,
        }
        if not valid:
            problems.append(f"invalid T064 static checkpoint identity: {arm}")
    return {
        "valid": not problems,
        "problems": problems,
        "artifact_checks": checks,
        "pool_checks": pool_checks,
        "selected_sources": selected,
        "selected_count": len(selected),
        "act_counts": dict(Counter(item.get("act") for item in selected)),
        "component_counts": dict(Counter(item.get("component") for item in selected)),
        "static_checkpoints": static_checkpoints,
    }


def _required_mapping(row: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    value = row.get(key)
    if not isinstance(value, Mapping):
        raise TypeError(f"leaf row requires mapping {key}")
    return value


def validate_leaf_row(
    row: Mapping[str, Any], *, require_replicates: int | None = None
) -> dict[str, Any]:
    """Validate one collector/formal row without accepting public-only state."""

    required = (
        "sampling_arm",
        "act",
        "root_identity",
        "exact_leaf_identity",
        "exact_hidden_state_payload",
        "exact_state_digest",
        "public_projection",
        "public_model_input",
        "legal_actions",
        "source_complete_identity_sha256",
        "depth",
    )
    missing = [key for key in required if key not in row]
    if missing:
        raise ValueError("leaf row missing: " + ", ".join(missing))
    if row["sampling_arm"] not in ARMS or row["act"] not in ACT_COUNTS:
        raise ValueError("leaf row arm or Act is invalid")
    if not isinstance(row["exact_hidden_state_payload"], Mapping):
        raise TypeError("exact hidden state payload is not restorable structured data")
    if not isinstance(row["exact_state_digest"], str) or not row["exact_state_digest"]:
        raise ValueError("exact state digest is missing")
    if not isinstance(row["public_projection"], Mapping) or not isinstance(
        row["public_model_input"], Sequence
    ):
        raise TypeError("public projection/model input is malformed")
    if not isinstance(row["legal_actions"], Sequence) or not row["legal_actions"]:
        raise ValueError("legal action provenance is missing")
    if (
        not isinstance(row["depth"], int)
        or isinstance(row["depth"], bool)
        or row["depth"] < 1
    ):
        raise ValueError("leaf depth must be a positive integer")
    if require_replicates is not None:
        replicates = row.get("replicates")
        if not isinstance(replicates, list) or len(replicates) != require_replicates:
            raise ValueError(
                f"leaf row must contain exactly {require_replicates} replicates"
            )
    return dict(row)


def validate_replicate(replica: Mapping[str, Any], *, cap: int = ACTION_CAP) -> bool:
    """Return true only for a finite terminal utility below the safety cap."""

    transitions = replica.get("transition_count")
    utility = _finite(replica.get("terminal_evaluate_end_state"))
    return (
        replica.get("terminal") is True
        and isinstance(transitions, int)
        and not isinstance(transitions, bool)
        and 0 <= transitions <= cap
        and utility is not None
        and replica.get("cap_hit") is not True
    )


def validate_replicates(
    row: Mapping[str, Any], count: int
) -> tuple[list[float], list[int], list[str]]:
    replicates = row.get("replicates")
    if not isinstance(replicates, list) or len(replicates) != count:
        return [], [], [f"expected {count} replicates"]
    utilities: list[float] = []
    lengths: list[int] = []
    problems: list[str] = []
    for index, replica in enumerate(replicates, 1):
        if not isinstance(replica, Mapping) or not validate_replicate(replica):
            problems.append(f"replicate {index} is unavailable/non-terminal/cap-hit")
            continue
        utilities.append(float(replica["terminal_evaluate_end_state"]))
        lengths.append(int(replica["transition_count"]))
    if problems:
        return [], lengths, problems
    return utilities, lengths, []


def validate_collector_execution(
    execution: Mapping[str, Any],
    selected_sources: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Validate the complete native 3-arm/460-root collection inventory."""

    problems: list[str] = []
    if execution.get("schema_id") != COLLECTOR_SCHEMA_ID:
        problems.append("collector schema_id mismatch")
    if execution.get("generation_mode") != "native_runtime_collector":
        problems.append("collector generation_mode is not native_runtime_collector")
    if execution.get("search_simulations_per_root") != 100:
        problems.append("collector search_simulations_per_root is not 100")
    if len(selected_sources) != 460:
        problems.append("collector selected T064 root cohort is not exactly 460 roots")
    if (
        execution.get("worker_count") != WORKER_COUNT
        or execution.get("effective_worker_count") != WORKER_COUNT
    ):
        problems.append("collector did not prove 16 configured/effective workers")
    root_by_identity = {
        str(item.get("complete_identity_sha256")): index
        for index, item in enumerate(selected_sources)
    }
    root_runs = execution.get("root_runs")
    if not isinstance(root_runs, list) or len(root_runs) != len(ARMS) * 460:
        problems.append("collector root_runs is not exactly 3x460")
        root_runs = []
    seen_runs: set[tuple[str, str]] = set()
    for run in root_runs:
        if not isinstance(run, Mapping):
            problems.append("collector root-run row is malformed")
            continue
        arm = run.get("sampling_arm")
        root = str(run.get("root_identity"))
        key = (str(arm), root)
        if arm not in ARMS or root not in root_by_identity:
            problems.append("collector root-run has unknown arm/root identity")
        if key in seen_runs:
            problems.append(
                "collector root-run inventory contains a duplicate arm/root"
            )
        seen_runs.add(key)
        if run.get("simulations") != 100 or run.get("status") != "complete":
            problems.append("collector root-run lacks complete 100-simulation evidence")
        if run.get("source_complete_identity_sha256") != root:
            problems.append("collector root-run source/root identity disagrees")
        root_statistics = run.get("native_root_statistics", run.get("root_statistics"))
        if not isinstance(root_statistics, list) or not root_statistics:
            problems.append("collector root-run lacks native root statistics")
    if len(seen_runs) != len(ARMS) * 460:
        problems.append(
            "collector root-run inventory does not cover every arm/root pair"
        )
    arm_configs = execution.get("arm_configs")
    expected_configs = {
        "unguided_search_v2": {
            "policy_prior": False,
            "leaf_value": False,
            "checkpoint_sha256": None,
        },
        "prior_only_static_64001": {
            "policy_prior": True,
            "leaf_value": False,
            "checkpoint_sha256": EXPECTED_STATIC_CHECKPOINTS["prior_only_static_64001"][
                0
            ],
        },
        "prior_only_static_64002": {
            "policy_prior": True,
            "leaf_value": False,
            "checkpoint_sha256": EXPECTED_STATIC_CHECKPOINTS["prior_only_static_64002"][
                0
            ],
        },
    }
    if not isinstance(arm_configs, Mapping):
        problems.append("collector arm_configs is unavailable")
    else:
        for arm, expected in expected_configs.items():
            actual = arm_configs.get(arm)
            if not isinstance(actual, Mapping) or any(
                actual.get(key) != value for key, value in expected.items()
            ):
                problems.append(f"collector configuration mismatch: {arm}")
    parity = execution.get("parity")
    parity_fields = (
        "checked_root_count",
        "arms",
        "acts",
        "worker_count",
        "material_outputs_equal",
        "root_action_equal",
        "root_statistics_equal",
        "rng_semantics_equal",
    )
    if not isinstance(parity, Mapping) or any(
        field not in parity for field in parity_fields
    ):
        problems.append("collector parity evidence is incomplete")
    else:
        if (
            parity.get("checked_root_count") != 16
            or set(parity.get("arms", [])) != set(ARMS)
            or set(parity.get("acts", [])) != {1, 2}
        ):
            problems.append(
                "collector parity does not cover 16 roots, all arms, and both Acts"
            )
        if parity.get("worker_count") != WORKER_COUNT or not all(
            parity.get(field) is True for field in parity_fields[4:]
        ):
            problems.append(
                "collector parity did not prove material Search/RNG equality"
            )
    candidate_rows = execution.get("candidate_rows", [])
    if not isinstance(candidate_rows, list):
        problems.append("collector candidate_rows is malformed")
        candidate_rows = []
    valid_candidates: list[dict[str, Any]] = []
    candidate_identity_digests: dict[str, str] = {}
    candidate_digest_identities: dict[str, str] = {}
    for raw in candidate_rows:
        if not isinstance(raw, Mapping):
            problems.append("collector candidate row is malformed")
            continue
        try:
            row = validate_leaf_row(raw)
        except (TypeError, ValueError) as exc:
            problems.append(str(exc))
            continue
        if (
            row["root_identity"] not in root_by_identity
            or row["source_complete_identity_sha256"] != row["root_identity"]
        ):
            problems.append("candidate leaf is not tied to an exact selected T064 root")
        identity = str(row["exact_leaf_identity"])
        digest = str(row["exact_state_digest"])
        if (
            identity in candidate_identity_digests
            and candidate_identity_digests[identity] != digest
        ):
            problems.append(
                "candidate exact hidden identity maps to conflicting state digests"
            )
        if (
            digest in candidate_digest_identities
            and candidate_digest_identities[digest] != identity
        ):
            problems.append(
                "candidate exact state digest maps to conflicting hidden identities"
            )
        candidate_identity_digests[identity] = digest
        candidate_digest_identities[digest] = identity
        valid_candidates.append(row)
    return {
        "valid": not problems,
        "problems": problems,
        "candidate_rows": valid_candidates,
        "candidate_count": len(valid_candidates),
        "candidate_exact_hidden_identity_count": len(candidate_identity_digests),
        "candidate_exact_state_digest_count": len(candidate_digest_identities),
        "candidate_duplicate_occupancy_count": len(valid_candidates)
        - len(candidate_identity_digests),
        "root_run_count": len(root_runs),
        "parity": parity if isinstance(parity, Mapping) else {},
    }


def validate_target_rows(
    calibration_rows: Sequence[Mapping[str, Any]],
    formal_rows: Sequence[Mapping[str, Any]],
    *,
    native_commit: str,
    selected_repetition_count: int | None,
    candidate_ids: set[str],
) -> dict[str, Any]:
    """Validate exact calibration/formal support and independent seed lineage."""

    problems: list[str] = []
    calibration_ids: set[str] = set()
    formal_ids: set[str] = set()
    formal_digests: set[str] = set()
    calibration_digests: set[str] = set()

    def check_rows(rows: Sequence[Mapping[str, Any]], count: int, label: str) -> None:
        if len(rows) != count:
            problems.append(f"{label} row count is {len(rows)}, expected {count}")
        for raw in rows:
            try:
                row = validate_leaf_row(
                    raw,
                    require_replicates=CALIBRATION_REPLICATES
                    if label == "calibration"
                    else selected_repetition_count,
                )
            except (TypeError, ValueError) as exc:
                problems.append(f"{label} row invalid: {exc}")
                continue
            identity = str(row["exact_leaf_identity"])
            digest = str(row["exact_state_digest"])
            ids = calibration_ids if label == "calibration" else formal_ids
            digests = calibration_digests if label == "calibration" else formal_digests
            if identity in ids or digest in digests:
                problems.append(f"duplicate {label} exact hidden leaf identity")
            ids.add(identity)
            digests.add(digest)
            if identity not in candidate_ids:
                problems.append(f"{label} leaf is absent from candidate pool")
            if label == "formal" and row["sampling_arm"] not in ARMS:
                problems.append("formal row has unknown sampling arm")
            replicate_count = (
                CALIBRATION_REPLICATES
                if label == "calibration"
                else selected_repetition_count
            )
            if replicate_count is None:
                continue
            replicas = row.get("replicates", [])
            utilities, _, replica_problems = validate_replicates(row, replicate_count)
            if replica_problems:
                problems.append(
                    f"{label} leaf {identity} has invalid continuation replicates"
                )
                continue
            if len(utilities) != replicate_count:
                problems.append(
                    f"{label} leaf {identity} does not have all finite terminal utilities"
                )
            for replica_index, replica in enumerate(replicas, 1):
                if not isinstance(replica, Mapping):
                    continue
                expected = derive_replicate_seed(
                    native_commit,
                    str(row["source_complete_identity_sha256"]),
                    str(row["sampling_arm"]),
                    identity,
                    replica_index,
                )
                if replica.get("seed_provenance") != expected:
                    problems.append(
                        f"{label} leaf {identity} replicate {replica_index} seed lineage mismatch"
                    )

    check_rows(calibration_rows, CALIBRATION_COUNT, "calibration")
    check_rows(formal_rows, FORMAL_ROW_COUNT, "formal")
    if calibration_ids & formal_ids or calibration_digests & formal_digests:
        problems.append(
            "calibration and formal hidden leaf identities are not disjoint"
        )
    if len(formal_ids) != len(formal_rows):
        problems.append("formal exact hidden leaf identities are not unique")
    calibration_arm_counts = Counter(
        row.get("sampling_arm") for row in calibration_rows
    )
    formal_arm_counts = Counter(row.get("sampling_arm") for row in formal_rows)
    calibration_cells = Counter(
        (row.get("sampling_arm"), row.get("act")) for row in calibration_rows
    )
    formal_cells = Counter(
        (row.get("sampling_arm"), row.get("act")) for row in formal_rows
    )
    for arm in ARMS:
        if calibration_arm_counts[arm] != 32:
            problems.append(f"calibration arm quota mismatch: {arm}")
        if formal_arm_counts[arm] != ARM_ROW_COUNT:
            problems.append(f"formal arm quota mismatch: {arm}")
        for act, expected in ((1, 18), (2, 14)):
            if calibration_cells[(arm, act)] != expected:
                problems.append(f"calibration Act quota mismatch: {arm}/act{act}")
        for act, expected in FORMAL_ACT_COUNTS.items():
            if formal_cells[(arm, act)] != expected:
                problems.append(f"formal Act quota mismatch: {arm}/act{act}")
    return {
        "valid": not problems,
        "problems": problems,
        "calibration_count": len(calibration_rows),
        "formal_count": len(formal_rows),
        "calibration_hidden_identity_count": len(calibration_ids),
        "formal_hidden_identity_count": len(formal_ids),
        "calibration_formal_disjoint": not bool(
            calibration_ids & formal_ids or calibration_digests & formal_digests
        ),
        "formal_unique": len(formal_ids) == len(formal_rows) == FORMAL_ROW_COUNT,
        "calibration_arm_counts": dict(calibration_arm_counts),
        "formal_arm_counts": dict(formal_arm_counts),
        "formal_cells": {
            f"{arm}/act{act}": formal_cells[(arm, act)]
            for arm in ARMS
            for act in FORMAL_ACT_COUNTS
        },
    }


def _rank(values: Sequence[float]) -> list[float]:
    indexed = sorted(enumerate(values), key=lambda item: item[1])
    ranks = [0.0] * len(values)
    cursor = 0
    while cursor < len(indexed):
        end = cursor + 1
        while end < len(indexed) and indexed[end][1] == indexed[cursor][1]:
            end += 1
        rank = (cursor + end - 1) / 2.0 + 1.0
        for index, _ in indexed[cursor:end]:
            ranks[index] = rank
        cursor = end
    return ranks


def _correlation(left: Sequence[float], right: Sequence[float]) -> float | None:
    if len(left) != len(right) or len(left) < 2:
        return None
    x, y = _rank(left), _rank(right)
    mean_x, mean_y = sum(x) / len(x), sum(y) / len(y)
    numerator = sum((a - mean_x) * (b - mean_y) for a, b in zip(x, y, strict=True))
    denominator = math.sqrt(
        sum((a - mean_x) ** 2 for a in x) * sum((b - mean_y) ** 2 for b in y)
    )
    return numerator / denominator if denominator else None


def calibration_metrics(
    rows: Sequence[Mapping[str, Any]], repetition_count: int
) -> dict[str, Any]:
    if repetition_count not in CANDIDATE_REPETITIONS:
        raise ValueError("unsupported candidate repetition count")
    reference: list[float] = []
    estimates: list[float] = []
    for row in rows:
        utilities, _, problems = validate_replicates(row, CALIBRATION_REPLICATES)
        if problems:
            return {
                "available": False,
                "repetition_count": repetition_count,
                "problems": problems,
            }
        estimates.append(sum(utilities[:repetition_count]) / repetition_count)
        reference.append(sum(utilities[128:]) / 128.0)
    p95 = _percentile(reference, 0.95)
    p05 = _percentile(reference, 0.05)
    scale = (p95 - p05) if p95 is not None and p05 is not None else None
    errors = [
        estimate - truth for estimate, truth in zip(estimates, reference, strict=True)
    ]
    rmse = (
        math.sqrt(sum(error * error for error in errors) / len(errors))
        if errors
        else None
    )
    absolute = [abs(error) for error in errors]
    p95_absolute = _percentile(absolute, 0.95)
    spearman = _correlation(estimates, reference)
    return {
        "available": bool(rows) and scale is not None and scale > 0,
        "leaf_count": len(rows),
        "repetition_count": repetition_count,
        "reference_repetition_count": 128,
        "I90": scale,
        "spearman": spearman,
        "NRMSE": rmse / scale if rmse is not None and scale else None,
        "P95_NAE": (p95_absolute / scale if scale else None),
        "gates": {
            "spearman_ge_0_98": spearman is not None and spearman >= 0.98,
            "NRMSE_le_0_05": rmse is not None
            and scale is not None
            and rmse / scale <= 0.05,
            "P95_NAE_le_0_10": p95_absolute is not None
            and bool(scale)
            and p95_absolute / scale <= 0.10,
        },
    }


def select_repetition_count(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    metrics = [calibration_metrics(rows, count) for count in CANDIDATE_REPETITIONS]
    selected = next(
        (
            item["repetition_count"]
            for item in metrics
            if all(item.get("gates", {}).values())
        ),
        None,
    )
    return {
        "candidate_metrics": metrics,
        "selected_repetition_count": selected,
        "qualified": selected is not None,
    }


def summarize_candidate_pool(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    counts: Counter[tuple[str, int]] = Counter()
    unique: dict[tuple[str, int], set[str]] = defaultdict(set)
    public: dict[str, set[str]] = defaultdict(set)
    roots: Counter[tuple[str, str]] = Counter()
    depths: Counter[tuple[str, int]] = Counter()
    for row in rows:
        arm, act = row.get("sampling_arm"), row.get("act")
        counts[(str(arm), int(act))] += 1
        unique[(str(arm), int(act))].add(str(row.get("exact_leaf_identity")))
        public_key = json.dumps(
            row.get("public_model_input"), sort_keys=True, separators=(",", ":")
        )
        public[public_key].add(str(row.get("exact_leaf_identity")))
        roots[(str(arm), str(row.get("root_identity")))] += 1
        depths[(str(arm), int(row.get("depth", -1)))] += 1
    duplicate_groups = [
        identities for identities in public.values() if len(identities) > 1
    ]
    return {
        "total_rows": len(rows),
        "by_arm_act": {
            f"{arm}/act{act}": counts[(arm, act)] for arm in ARMS for act in ACT_COUNTS
        },
        "unique_hidden_by_arm_act": {
            f"{arm}/act{act}": len(unique[(arm, act)])
            for arm in ARMS
            for act in ACT_COUNTS
        },
        "per_root_counts": {
            f"{arm}/{root}": count for (arm, root), count in sorted(roots.items())
        },
        "depth_counts": {
            f"{arm}/depth{depth}": count
            for (arm, depth), count in sorted(depths.items())
        },
        "public_duplicate_group_count": len(duplicate_groups),
        "public_duplicate_groups": [sorted(group) for group in duplicate_groups],
    }


def ambiguity_diagnostic(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    groups: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        key = json.dumps(
            row.get("public_model_input"), sort_keys=True, separators=(",", ":")
        )
        groups[key].append(row)
    diagnostics = []
    for key, group in groups.items():
        identities = {str(row.get("exact_leaf_identity")) for row in group}
        if len(identities) < 2:
            continue
        means = [_finite(row.get("target_mean")) for row in group]
        values = [value for value in means if value is not None]
        diagnostics.append(
            {
                "public_model_input_sha256": hashlib.sha256(key.encode()).hexdigest(),
                "hidden_leaf_count": len(identities),
                "target_spread": max(values) - min(values) if values else None,
                "target_stats": value_stats(values),
            }
        )
    return {"group_count": len(diagnostics), "groups": diagnostics, "is_blocker": False}


def classify_t084(
    *,
    integrity_valid: bool,
    execution_valid: bool,
    collector_parity: bool,
    calibration: Mapping[str, Any],
    support_sufficient: bool,
    formal_valid: bool,
) -> str:
    """Select one terminal classification from independent evidence dimensions."""

    if not integrity_valid or not execution_valid or not collector_parity:
        return "INCOMPLETE"
    if not support_sufficient or not formal_valid:
        return "LEAF_TARGET_SUPPORT_INSUFFICIENT"
    if not calibration.get("qualified", False):
        return "LEAF_TARGET_MONTE_CARLO_UNSTABLE"
    return "LEAF_CONTINUATION_UTILITY_TARGETS_READY"


def _empty_execution(reason: str) -> dict[str, Any]:
    return {
        "available": False,
        "schema_id": COLLECTOR_SCHEMA_ID,
        "reason": reason,
        "worker_count": WORKER_COUNT,
        "effective_worker_count": 0,
        "shards": [],
        "failures": [reason],
        "candidate_rows": [],
        "calibration_rows": [],
        "formal_rows": [],
        "parity": {"available": False, "passed": False, "reason": reason},
    }


def _load_collector(path: Path | None) -> dict[str, Any]:
    if path is None:
        return _empty_execution(
            "collector artifact not supplied; accepted native surface cannot restore hidden internal leaves"
        )
    try:
        payload = _json(path)
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        return _empty_execution(f"collector artifact invalid: {exc}")
    if payload.get("schema_id") != COLLECTOR_SCHEMA_ID:
        return _empty_execution("collector schema_id mismatch")
    return payload


def audit_t084(
    t064_root: Path,
    t082_report: Path,
    t083_report: Path,
    output: Path,
    *,
    repo_root: Path,
    native_root: Path,
    collector: Path | None = None,
    native_runtime_ref: str | None = None,
    native_runtime_commit: str | None = None,
    native_build: str | None = None,
    native_abi: str | None = None,
    native_verifier_result: str | None = None,
    native_probe: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the formal report, failing closed when the collector is absent."""

    t064 = validate_t064_inputs(t064_root)
    t082 = _accepted_report_check(
        t082_report,
        EXPECTED_T082_REPORT_SHA,
        "schema_version",
        "t082-value-target-semantic-closure-v1",
    )
    t083 = _accepted_report_check(
        t083_report,
        EXPECTED_T083_REPORT_SHA,
        "schema_id",
        "t083-battle-search-v2-leaf-value-target-contract-v1",
    )
    code = validate_code_identity(repo_root)
    native = validate_native_identity(
        native_root,
        runtime_ref=native_runtime_ref,
        runtime_commit=native_runtime_commit,
        build_path=native_build,
        abi=native_abi,
        verifier_result=native_verifier_result,
    )
    probe = validate_native_probe(native_probe, native)
    execution = _load_collector(collector)
    integrity_problems = list(t064["problems"])
    if not t082["valid"]:
        integrity_problems.append("invalid accepted T082 report")
    if not t083["valid"]:
        integrity_problems.append("invalid accepted T083 report")
    if not code["ref_identity_valid"] or not code["source_matches_main"]:
        integrity_problems.append("STSRL main ref/source identity mismatch")
    if not native["identity_valid"]:
        integrity_problems.append("native ref/source identity mismatch")
    if t082.get("classification") != "VALUE_TARGET_SEMANTIC_MISMATCH_CONFIRMED":
        integrity_problems.append("accepted T082 classification mismatch")
    if t083.get("classification") != "NEW_LEAF_CONTINUATION_UTILITY_TARGET_REQUIRED":
        integrity_problems.append("accepted T083 classification mismatch")
    if not probe["valid"]:
        integrity_problems.append("native build/API probe is missing or invalid")
    collector_validation = validate_collector_execution(
        execution, t064["selected_sources"]
    )
    if not collector_validation["valid"]:
        execution.setdefault("failures", []).extend(collector_validation["problems"])
    valid_candidates = collector_validation["candidate_rows"]
    calibration_rows = execution.get("calibration_rows", [])
    formal_rows = execution.get("formal_rows", [])
    if not isinstance(calibration_rows, list) or not isinstance(formal_rows, list):
        execution.setdefault("failures", []).append(
            "collector calibration/formal rows are malformed"
        )
        calibration_rows, formal_rows = [], []
    calibration = (
        select_repetition_count(calibration_rows)
        if len(calibration_rows) == CALIBRATION_COUNT
        else {
            "candidate_metrics": [],
            "selected_repetition_count": None,
            "qualified": False,
            "reason": "exact 96 calibration rows unavailable",
        }
    )
    candidate_ids = {str(row.get("exact_leaf_identity")) for row in valid_candidates}
    target_validation = validate_target_rows(
        calibration_rows,
        formal_rows,
        native_commit=str(native.get("resolved_commit")),
        selected_repetition_count=calibration["selected_repetition_count"],
        candidate_ids=candidate_ids,
    )
    formal_valid = target_validation["valid"]
    support_sufficient = (
        collector_validation["valid"]
        and target_validation["calibration_count"] == CALIBRATION_COUNT
        and target_validation["formal_count"] == FORMAL_ROW_COUNT
        and target_validation["calibration_formal_disjoint"]
        and target_validation["formal_unique"]
    )
    execution_valid = (
        bool(execution.get("available"))
        and not execution.get("failures")
        and collector_validation["valid"]
    )
    parity = collector_validation.get("parity", {})
    parity_passed = (
        collector_validation["valid"] and parity.get("material_outputs_equal") is True
    )
    classification = classify_t084(
        integrity_valid=not integrity_problems,
        execution_valid=execution_valid,
        collector_parity=parity_passed,
        calibration=calibration,
        support_sufficient=support_sufficient,
        formal_valid=formal_valid,
    )
    report: dict[str, Any] = {
        "schema_id": SCHEMA_ID,
        "schema_version": 1,
        "task_id": "T084",
        "identity": {
            "stsr_main_ref": EXPECTED_MAIN_REF,
            "stsr_main_commit": EXPECTED_MAIN_COMMIT,
            "code": code,
            "native": native,
            "native_probe": probe,
        },
        "accepted_inputs": {
            "t082_report": t082,
            "t083_report": t083,
            "t064": t064,
            "static_checkpoint_identities": EXPECTED_STATIC_CHECKPOINTS,
        },
        "integrity": {"valid": not integrity_problems, "problems": integrity_problems},
        "execution": {
            key: execution.get(key)
            for key in (
                "schema_id",
                "available",
                "worker_count",
                "effective_worker_count",
                "shards",
                "failures",
                "parity",
            )
        },
        "candidate_pool": summarize_candidate_pool(valid_candidates),
        "calibration": calibration,
        "target_validation": target_validation,
        "formal_dataset": {
            "row_count": len(formal_rows),
            "expected_row_count": FORMAL_ROW_COUNT,
            "valid": formal_valid,
            "arm_counts": dict(Counter(row.get("sampling_arm") for row in formal_rows)),
            "act_counts": dict(Counter(row.get("act") for row in formal_rows)),
            "transition_cap": ACTION_CAP,
            "all_replicates_valid": target_validation["valid"],
        },
        "ambiguity_diagnostic": ambiguity_diagnostic(formal_rows),
        "classification": classification,
        "recommendation": (
            "propose a separate paired value-target repair/retraining task using V_leaf=E[evaluateEndState | post-action state, pinned playoutRandom]"
            if classification == "LEAF_CONTINUATION_UTILITY_TARGETS_READY"
            else "do not publish a paired repair dataset from this run; preserve the explicit fail-closed evidence boundary"
        ),
        "compatibility_boundary": "Python model-facing callback remains public-only; hidden BattleContext is collector provenance only; T084 does not execute successor training or outcome evaluation",
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return report


__all__ = [
    "ACTION_CAP",
    "ARMS",
    "CANDIDATE_REPETITIONS",
    "CLASSIFICATIONS",
    "COLLECTOR_SCHEMA_ID",
    "EXPECTED_MAIN_COMMIT",
    "EXPECTED_NATIVE_COMMIT",
    "FORMAL_ACT_COUNTS",
    "FORMAL_ROW_COUNT",
    "SCHEMA_ID",
    "audit_t084",
    "calibration_metrics",
    "classify_t084",
    "derive_replicate_seed",
    "select_repetition_count",
    "sha256_file",
    "validate_leaf_row",
    "validate_replicate",
]
