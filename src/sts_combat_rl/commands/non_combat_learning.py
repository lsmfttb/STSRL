"""Neutral command surface for the T065/T075 non-combat workflows.

This module is deliberately not wired into the legacy flat CLI.  Long-running
collection and evaluation are explicit subcommands so their artifact paths,
seed ranges, and stage boundaries remain visible in the command itself.
"""

from __future__ import annotations

import argparse
from collections.abc import Iterator, Sequence
from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
import json
import math
import os
from pathlib import Path
import shlex
import statistics
import sys
import time
from tempfile import TemporaryDirectory
from typing import Any, Mapping

from sts_combat_rl.sim.lightspeed import LightSpeedAdapter
from sts_combat_rl.sim.non_combat_learning import (
    T065_APPROVED_SPEC_COMMIT,
    T065CounterfactualTarget,
    T065_EXPERIMENT_SCHEMA_ID,
    T065_EXPERIMENT_SCHEMA_VERSION,
    T065ExperimentConfig,
    T065_CHECKPOINT_SCHEMA_ID,
    T065_MAX_WORKERS,
    T065_LIGHTSPEED_BUILD_PYTHONPATH,
    T065_MANDATORY_FAMILIES,
    T065_SPLITS,
    T065_SOURCE_SEED_RANGE,
    T065_STAGE6_DRIVER_SEED,
    T065_STAGE6_SEED_RANGE,
    T065_STAGE6_REPORT_SCHEMA_ID,
    T065_STAGE6_SHARD_COUNT,
    T065_MODEL_SEEDS,
    T065SourceState,
    T065HeldoutReport,
    T065HeldoutStateResult,
    T065_STAGE5_REPORT_SCHEMA_ID,
    T065_TRAINING_INTERPRETER,
    T065CaseD,
    ExpertNonCombatDriver,
    StochasticNonCombatDriver,
    T075_APPROVED_SPEC_COMMIT,
    T075_PLANNER_BASELINE,
    T075_REUSE_MANIFEST_SCHEMA_ID,
    T075_RETENTION_MANIFEST_SCHEMA_ID,
    T075_SELECTION_MANIFEST_SCHEMA_ID,
    T075_SELECTION_STRATEGY_ID,
    T075_STAGE3_VALIDATION_SCHEMA_ID,
    T075_TASK_ID,
    T075_TERMINAL_DECISION_SCHEMA_ID,
    build_stage5_report,
    build_t065_preflight_report,
    compute_learned_coverage,
    canonical_source_selection_key,
    collect_source_arm,
    collect_source_arm_sharded_to_path,
    file_sha256,
    frozen_battle_provenance,
    frozen_action_space,
    load_non_combat_checkpoint,
    matched_bootstrap_probability,
    non_combat_model_input_schema,
    read_source_states,
    read_target_table,
    run_stage6_experiment,
    continuation_seeds_for_split,
    select_source_candidates,
    select_t075_source_candidates,
    train_frozen_model_seeds,
    terminal_decision_report,
    validate_t065_preflight,
    write_source_states,
    write_target_table,
    generate_counterfactual_targets,
    generate_counterfactual_targets_sharded,
    generate_counterfactual_targets_process_sharded,
    replay_source_states_process_sharded,
    stage6_shard_ranges,
    target_shard_ranges,
    write_source_selection_manifest,
    write_t065_manifest,
    write_t065_terminal_decision_report,
)
from sts_combat_rl.sim.public_run_context import forbidden_public_context_problems
from sts_combat_rl.sim.lightspeed_source import lightspeed_source_identity_dict

T075_STAGE_ORDER = (
    "stage0-preflight",
    "stage0-reuse",
    "stage1-selection-replay",
    "stage2-target",
    "stage4-train",
    "stage5-gate",
    "stage6-eval",
    "terminal-finalize",
)
T075_STAGE6_SHARD_COUNT = T065_STAGE6_SHARD_COUNT
T075_STAGE6_SEEDS_PER_SHARD = (
    T065_STAGE6_SEED_RANGE[1] - T065_STAGE6_SEED_RANGE[0] + 1
) // T075_STAGE6_SHARD_COUNT
T075_STABLE_ARTIFACT_ROOT = Path(
    "D:/DeadlycatCoding/STSRL/artifacts/t075-leakage-safe-non-combat-cohort-repair"
)

T075_FROZEN_SOURCE_ARTIFACTS = {
    "artifacts/t065-learned-non-combat-policy-v1/source-stochastic-650001-650256-c57b2ee.json": {
        "arm": "stochastic_non_combat_v1",
        "sha256": "40a29e2cc8042efc15a46e9c50f6a50f889c94a1d7def24e91b62718eaaa8f61",
        "size_bytes": 5352891044,
    },
    "artifacts/t065-learned-non-combat-policy-v1/source-expert-650001-650256-deeaa46.json": {
        "arm": "expert_non_combat_v1",
        "sha256": "29d4155e543b024e741230b5bcefad3116c44610b370b666f46a65571348ad4c",
        "size_bytes": 3710180244,
    },
}

T075_ACCEPTED_PREFLIGHT_ALIASES = {
    "artifacts/t065-learned-non-combat-policy-v1/preflight-c57b2ee-20260827.json": "stochastic_non_combat_v1",
    "artifacts/t065-learned-non-combat-policy-v1/preflight-968797e-20260827.json": "expert_non_combat_v1",
}
T075_ACCEPTED_PREFLIGHT_RETENTION_ALIASES = {
    "artifacts/t065-learned-non-combat-policy-v1/preflight-c57b2ee-20260827.retention.json": "stochastic_non_combat_v1",
    "artifacts/t065-learned-non-combat-policy-v1/preflight-968797e-20260827.retention.json": "expert_non_combat_v1",
}
T075_ACCEPTED_T065_CASE_D = {
    "path": "artifacts/t065-learned-non-combat-policy-v1/source-selection-650001-650256-a69972f.t065-terminal-decision-report.json",
    "sha256": "0e6bc4a343c2f543ecb9b5d4dfb23393a980b8243c4eee77ec2d4595b74d9bfc",
    "size_bytes": 198842,
}
T075_ACCEPTED_T065_CASE_D_RETENTION = {
    "path": "artifacts/t065-learned-non-combat-policy-v1/source-selection-650001-650256-a69972f.retention.json",
    "sha256": "fcf24bad8590dc1c74b77c6e3c9a04bdef63611182661153c9c02fc36ccd5faf",
    "size_bytes": 36186,
}


class T075WorkflowError(T065CaseD):
    """Case-D-compatible failure carrying the T075 terminal contract."""

    pass


def _t075_pinned_simulator_identity() -> dict[str, Any]:
    """Return the one simulator identity shared by T075 writers and readers."""

    return dict(lightspeed_source_identity_dict())


def _t075_require_pinned_simulator_identity(
    value: Any, *, label: str
) -> dict[str, Any]:
    identity = _t075_pinned_simulator_identity()
    if value != identity:
        raise ValueError(f"{label} simulator identity is not the pinned identity")
    return identity


def _t075_expected_stage6_driver(
    arm: str, report: Mapping[str, Any]
) -> Mapping[str, Any] | None:
    """Return the exact frozen driver provenance for one Stage-6 arm."""

    if arm == "stochastic":
        driver = StochasticNonCombatDriver(seed=T065_STAGE6_DRIVER_SEED)
    elif arm == "expert":
        driver = ExpertNonCombatDriver(seed=T065_STAGE6_DRIVER_SEED)
    elif arm == "learned":
        raw = report.get("driver_provenance")
        if not isinstance(raw, Mapping):
            return None
        config = raw.get("config")
        if (
            raw.get("name") != "learned_non_combat_v1"
            or raw.get("version") != 1
            or not isinstance(config, Mapping)
            or set(config)
            != {
                "seed",
                "version",
                "supported_screen_families",
                "fallback_policy",
                "fallback_provenance",
                "checkpoint_schema_id",
                "checkpoint_artifact_id",
                "model_seed",
                "model_input_schema",
                "information_regime",
                "expert_action_or_score_is_model_input",
            }
            or config.get("seed") != T065_STAGE6_DRIVER_SEED
            or config.get("version") != 1
            or config.get("supported_screen_families") != list(T065_MANDATORY_FAMILIES)
            or config.get("fallback_policy") != "expert_non_combat_v1"
            or config.get("fallback_provenance")
            != {
                "name": "expert_non_combat_v1",
                "version": 1,
                "seed": T065_STAGE6_DRIVER_SEED,
            }
            or config.get("checkpoint_schema_id") != T065_CHECKPOINT_SCHEMA_ID
            or not isinstance(config.get("checkpoint_artifact_id"), str)
            or len(config["checkpoint_artifact_id"]) != 64
            or any(
                character not in "0123456789abcdef"
                for character in config["checkpoint_artifact_id"].lower()
            )
            or config.get("model_seed") not in (653001, 653002)
            or config.get("model_input_schema") != non_combat_model_input_schema()
            or config.get("information_regime") != "normal_public_policy"
            or config.get("expert_action_or_score_is_model_input") is not False
        ):
            return None
        return dict(raw)
    else:
        return None
    return {
        "name": driver.name,
        "version": driver.version,
        "config": dict(driver.provenance_config),
    }


def _t075_stage6_arm_provenance_is_frozen(arm: str, report: Mapping[str, Any]) -> bool:
    expected_driver = _t075_expected_stage6_driver(arm, report)
    if expected_driver is None or report.get("driver_provenance") != expected_driver:
        return False
    driver_config = expected_driver["config"]
    controller = report.get("controller_provenance")
    if not isinstance(controller, Mapping):
        return False
    expected_battle = frozen_battle_provenance()
    non_combat_name = str(expected_driver["name"])
    policy_class = {
        "stochastic": "StochasticNonCombatDriver",
        "expert": "ExpertNonCombatDriver",
        "learned": "LearnedNonCombatPolicy",
    }[arm]
    expected_non_combat = {
        "kind": "decision_policy",
        "name": non_combat_name,
        "config": {
            **dict(driver_config),
            "policy_class": policy_class,
            "information_regime": "normal_public_policy",
        },
        "schema_version": 1,
    }
    expected_controller = {
        "kind": "routed_run",
        "name": f"{expected_battle['name']}+{non_combat_name}",
        "config": {
            "battle": expected_battle,
            "non_combat": expected_non_combat,
            "reproducible": True,
        },
        "schema_version": 1,
    }
    return controller == expected_controller


def _t075_parse_utc_timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() != timedelta(0):
        return None
    return parsed


def _t075_resolve_identity_path(
    raw_path: str, *, artifact_root: Path | None = None
) -> Path | None:
    try:
        path = _portable_path(raw_path)
    except (OSError, TypeError, ValueError):
        return None
    candidates = [path]
    if not path.is_absolute():
        if artifact_root is not None:
            candidates.append(artifact_root / path)
        candidates.append(_target_src_path().parent / path)
    root = None
    if artifact_root is not None:
        try:
            root = artifact_root.resolve()
        except OSError:
            return None
    for candidate in candidates:
        try:
            resolved = candidate.resolve()
            if root is not None:
                resolved.relative_to(root)
            if resolved.is_file():
                return resolved
        except (OSError, ValueError):
            continue
    return None


def _t075_actual_identity(identity: Any, *, artifact_root: Path | None = None) -> bool:
    if not isinstance(identity, Mapping):
        return False
    raw_path = identity.get("path")
    digest = identity.get("sha256")
    size = identity.get("size_bytes")
    if (
        not isinstance(raw_path, str)
        or not raw_path
        or not isinstance(digest, str)
        or len(digest) != 64
        or any(character not in "0123456789abcdef" for character in digest.lower())
        or isinstance(size, bool)
        or not isinstance(size, int)
        or size < 0
    ):
        return False
    path = _t075_resolve_identity_path(raw_path, artifact_root=artifact_root)
    return (
        path is not None and file_sha256(path) == digest and path.stat().st_size == size
    )


def _t075_validate_process_shards(
    stage: str,
    *,
    shard_count: int,
    worker_count: int,
    per_shard: Any,
    status: str,
    ranges: Any = None,
    allow_partial_failure: bool = False,
) -> None:
    """Validate observed process evidence, including its frozen shard plan.

    Stage-6 retention is one list containing all three arms.  The arm label is
    deliberately retained on every row so a dict keyed by arm cannot be
    mistaken for observed per-shard evidence.
    """

    if shard_count == 0:
        if per_shard != []:
            raise T075WorkflowError(
                "artifact-retention", [f"{stage}: zero-shard evidence is not empty"]
            )
        return
    if stage == "stage6-eval":
        if shard_count != T075_STAGE6_SHARD_COUNT:
            raise T075WorkflowError(
                "artifact-retention", [f"{stage}: shard count is not frozen"]
            )
        expected_count = shard_count * 3
        expected_arms = {"stochastic", "expert", "learned"}
    else:
        if shard_count != T065_MAX_WORKERS:
            raise T075WorkflowError(
                "artifact-retention", [f"{stage}: shard count is not frozen"]
            )
        expected_count = shard_count
        expected_arms = None
    if worker_count != T065_MAX_WORKERS or (
        len(per_shard) != expected_count
        and not (allow_partial_failure and status == "failed")
    ):
        raise T075WorkflowError(
            "artifact-retention",
            [f"{stage}: observed worker/shard count is incomplete"],
        )
    expected_noncombat: dict[int, dict[str, Any]] = {}
    if stage in {"stage1-selection-replay", "stage2-target"}:
        if not isinstance(ranges, list) or (
            len(ranges) != expected_count
            and not (allow_partial_failure and status == "failed")
        ):
            raise T075WorkflowError(
                "artifact-retention",
                [f"{stage}: frozen 16x20 range evidence is incomplete"],
            )
        expected_noncombat = {
            int(spec["shard_index"]): dict(spec)
            for spec in target_shard_ranges(worker_count=T065_MAX_WORKERS)
        }
        seen_noncombat: set[int] = set()
        for range_entry in ranges:
            if not isinstance(range_entry, Mapping):
                raise T075WorkflowError(
                    "artifact-retention", [f"{stage}: range evidence is not an object"]
                )
            index = range_entry.get("shard_index")
            expected = expected_noncombat.get(index)
            if index in seen_noncombat:
                raise T075WorkflowError(
                    "artifact-retention", [f"{stage}: range identity is duplicated"]
                )
            seen_noncombat.add(index)
            if expected is None or any(
                range_entry.get(field) != expected.get(field)
                for field in (
                    "shard_index",
                    "selected_state_start",
                    "selected_state_end",
                    "selected_state_count",
                    "worker_count",
                )
            ):
                raise T075WorkflowError(
                    "artifact-retention",
                    [f"{stage}: range does not match frozen 16x20 plan"],
                )
        if not allow_partial_failure and seen_noncombat != set(expected_noncombat):
            raise T075WorkflowError(
                "artifact-retention", [f"{stage}: frozen 16x20 plan is incomplete"]
            )
    expected_stage6: dict[tuple[str, int], dict[str, Any]] = {}
    if stage == "stage6-eval":
        if not isinstance(ranges, list) or (
            len(ranges) != expected_count
            and not (allow_partial_failure and status == "failed")
        ):
            raise T075WorkflowError(
                "artifact-retention",
                [f"{stage}: frozen range evidence is incomplete"],
            )
        for expected_arm in sorted(expected_arms):
            for spec in stage6_shard_ranges(
                arm=expected_arm, worker_count=T065_MAX_WORKERS
            ):
                expected_stage6[(expected_arm, int(spec["shard_index"]))] = dict(spec)
        seen_ranges: set[tuple[Any, Any]] = set()
        for range_entry in ranges:
            if not isinstance(range_entry, Mapping):
                raise T075WorkflowError(
                    "artifact-retention", [f"{stage}: range evidence is not an object"]
                )
            range_key = (range_entry.get("arm"), range_entry.get("shard_index"))
            if range_key in seen_ranges:
                raise T075WorkflowError(
                    "artifact-retention", [f"{stage}: range identity is duplicated"]
                )
            seen_ranges.add(range_key)
            expected = expected_stage6.get(range_key)
            if expected is None or any(
                range_entry.get(field) != expected.get(field)
                for field in (
                    "arm",
                    "shard_index",
                    "seed_start",
                    "seed_end",
                    "seed_count",
                    "worker_count",
                )
            ):
                raise T075WorkflowError(
                    "artifact-retention",
                    [f"{stage}: range does not match frozen seed plan"],
                )
        if not allow_partial_failure and seen_ranges != set(expected_stage6):
            raise T075WorkflowError(
                "artifact-retention", [f"{stage}: frozen range plan is incomplete"]
            )
    seen: set[tuple[str | None, int]] = set()
    process_ids: set[int] = set()
    process_ids_by_arm: dict[str, set[int]] = {}
    for entry in per_shard:
        if not isinstance(entry, Mapping):
            raise T075WorkflowError(
                "artifact-retention", [f"{stage}: shard evidence is not an object"]
            )
        arm = entry.get("arm")
        if expected_arms is not None and arm not in expected_arms:
            raise T075WorkflowError(
                "artifact-retention", [f"{stage}: shard arm identity is invalid"]
            )
        if expected_arms is None and arm is not None:
            raise T075WorkflowError(
                "artifact-retention", [f"{stage}: unexpected arm identity"]
            )
        index = entry.get("shard_index")
        process_id = entry.get("process_id")
        started = entry.get("started", True)
        if (
            isinstance(index, bool)
            or not isinstance(index, int)
            or not 0 <= index < shard_count
            or not isinstance(started, bool)
            or entry.get("worker_kind") != "spawn-process"
        ):
            raise T075WorkflowError(
                "artifact-retention", [f"{stage}: shard process evidence is invalid"]
            )
        key = (str(arm) if arm is not None else None, index)
        if started:
            if isinstance(process_id, bool) or not isinstance(process_id, int):
                raise T075WorkflowError(
                    "artifact-retention",
                    [f"{stage}: started shard has invalid process identity"],
                )
        elif not (allow_partial_failure and status == "failed" and process_id is None):
            raise T075WorkflowError(
                "artifact-retention", [f"{stage}: unstarted shard evidence is invalid"]
            )
        arm_process_ids = process_ids_by_arm.setdefault(str(arm), set())
        duplicate_process = started and (
            process_id in arm_process_ids
            if expected_arms is not None
            else process_id in process_ids
        )
        if key in seen or duplicate_process:
            raise T075WorkflowError(
                "artifact-retention", [f"{stage}: duplicate shard/process identity"]
            )
        seen.add(key)
        if expected_arms is not None and started:
            arm_process_ids.add(process_id)
        elif started:
            process_ids.add(process_id)
        exit_code = entry.get("exit_code")
        if isinstance(exit_code, bool) or (
            not isinstance(exit_code, int)
            and not (allow_partial_failure and status == "failed" and exit_code is None)
        ):
            raise T075WorkflowError(
                "artifact-retention", [f"{stage}: shard exit evidence is invalid"]
            )
        if status == "completed" and exit_code != 0:
            raise T075WorkflowError(
                "artifact-retention", [f"{stage}: completed shard has nonzero exit"]
            )
        if stage in {"stage1-selection-replay", "stage2-target"} and (
            entry.get("state_count") != 20 or entry.get("selected_state_count") != 20
        ):
            raise T075WorkflowError(
                "artifact-retention", [f"{stage}: shard state count is not frozen"]
            )
        if stage in {"stage1-selection-replay", "stage2-target"}:
            expected = expected_noncombat.get(index)
            if expected is None or any(
                entry.get(field) != expected.get(field)
                for field in (
                    "shard_index",
                    "selected_state_start",
                    "selected_state_end",
                    "selected_state_count",
                    "worker_count",
                )
            ):
                raise T075WorkflowError(
                    "artifact-retention", [f"{stage}: shard range is forged"]
                )
            if status == "completed" and any(
                entry.get(field) != 20
                for field in ("state_count", "selected_state_count")
            ):
                raise T075WorkflowError(
                    "artifact-retention", [f"{stage}: completed shard is partial"]
                )
        if (
            stage == "stage6-eval"
            and entry.get("requested_seed_count") != T075_STAGE6_SEEDS_PER_SHARD
        ):
            raise T075WorkflowError(
                "artifact-retention", [f"{stage}: shard seed range is not frozen"]
            )
        if stage == "stage6-eval":
            expected = expected_stage6.get((str(arm), index))
            requested_seeds = (
                list(range(int(expected["seed_start"]), int(expected["seed_end"]) + 1))
                if expected is not None
                else None
            )
            if (
                expected is None
                or any(
                    entry.get(field) != expected.get(field)
                    for field in (
                        "arm",
                        "shard_index",
                        "seed_start",
                        "seed_end",
                        "seed_count",
                        "worker_count",
                    )
                )
                or entry.get("requested_seeds") != requested_seeds
            ):
                raise T075WorkflowError(
                    "artifact-retention", [f"{stage}: shard seed range is forged"]
                )
            completed_seeds = entry.get("completed_seeds")
            if (
                not isinstance(completed_seeds, list)
                or any(seed not in requested_seeds for seed in completed_seeds)
                or len(set(completed_seeds)) != len(completed_seeds)
            ):
                raise T075WorkflowError(
                    "artifact-retention",
                    [f"{stage}: completed seed evidence is invalid"],
                )
            if status == "completed" and completed_seeds != requested_seeds:
                raise T075WorkflowError(
                    "artifact-retention", [f"{stage}: completed seed range is partial"]
                )
    if expected_arms is not None and not allow_partial_failure:
        counts = {arm: 0 for arm in expected_arms}
        for arm, _index in seen:
            counts[str(arm)] += 1
        if set(counts) != expected_arms or any(
            count != shard_count for count in counts.values()
        ):
            raise T075WorkflowError(
                "artifact-retention", [f"{stage}: per-arm shard plan is incomplete"]
            )


def _t075_terminal_decision_is_valid(
    value: Any,
    *,
    artifact_root: Path | None = None,
    retention_path: Path | None = None,
) -> bool:
    """Return whether a terminal report is complete enough to win first-valid."""

    # A terminal report is only authoritative in the stable artifact root;
    # accepting an arbitrary absolute path here would let a source/current
    # worktree file impersonate a retained T075 parent.
    if artifact_root is None:
        return False
    if retention_path is None or not isinstance(retention_path, Path):
        return False
    required = (
        "schema_id",
        "schema_version",
        "task_id",
        "approved_t075_spec_commit",
        "planner_baseline",
        "code_head",
        "terminal_case",
        "terminal_stage",
        "reason_code",
        "summary",
        "reached_stages",
        "skipped_stages",
        "parent_artifact_identities",
        "stage3_validation_status",
        "stage5_gate_status",
        "stage6_status",
        "recommendation",
        "problems",
    )
    if (
        not isinstance(value, Mapping)
        or any(key not in value for key in required)
        or value.get("schema_id") != T075_TERMINAL_DECISION_SCHEMA_ID
        or value.get("schema_version") != 1
        or value.get("task_id") != T075_TASK_ID
        or value.get("approved_t075_spec_commit") != T075_APPROVED_SPEC_COMMIT
        or value.get("planner_baseline") != T075_PLANNER_BASELINE
        or value.get("code_head") != _code_head_for_artifact_root(argparse.Namespace())
        or not isinstance(value.get("code_head"), str)
        or not value.get("code_head")
        or value.get("terminal_case") not in {"A", "B", "C", "D"}
        or not isinstance(value.get("parent_artifact_identities"), Mapping)
        or not value.get("parent_artifact_identities")
        or not isinstance(value.get("problems"), list)
    ):
        return False
    if any(
        not _t075_actual_identity(identity, artifact_root=artifact_root)
        for identity in value["parent_artifact_identities"].values()
    ):
        return False
    execution_stages = T075_STAGE_ORDER[:-1]
    reached = value.get("reached_stages")
    skipped = value.get("skipped_stages")
    terminal_stage = value.get("terminal_stage")
    if (
        not isinstance(reached, list)
        or not isinstance(skipped, list)
        or terminal_stage not in execution_stages
        or reached
        != list(execution_stages[: execution_stages.index(terminal_stage) + 1])
        or skipped
        != list(execution_stages[execution_stages.index(terminal_stage) + 1 :])
    ):
        return False
    skipped_commands = value.get("skipped_stage_commands")
    skipped_evidence = value.get("skipped_stage_evidence")
    if not isinstance(skipped_commands, Mapping) or not isinstance(
        skipped_evidence, Mapping
    ):
        return False
    for stage in skipped:
        command = skipped_commands.get(stage)
        evidence = skipped_evidence.get(stage)
        if (
            not isinstance(command, str)
            or not command.strip()
            or not isinstance(evidence, Mapping)
            or evidence.get("command") != command
            or not _t075_command_matches_contract(command, stage, skipped=True)
            or evidence.get("executed") is not False
            or evidence.get("status") != "skipped"
            or evidence.get("code_head") != value.get("code_head")
            or evidence.get("exit_code") is not None
            or evidence.get("terminal") is not False
            or not isinstance(evidence.get("skip_reason"), str)
            or not evidence["skip_reason"].strip()
            or _t075_parse_utc_timestamp(evidence.get("start_time_utc")) is None
            or _t075_parse_utc_timestamp(evidence.get("end_time_utc")) is None
            or _t075_parse_utc_timestamp(evidence["start_time_utc"])
            > _t075_parse_utc_timestamp(evidence["end_time_utc"])
        ):
            return False
    stage6_identity = value.get("stage6_report_identity")
    stage6_report: Mapping[str, Any] | None = None
    if stage6_identity is not None and not _t075_actual_identity(
        stage6_identity, artifact_root=artifact_root
    ):
        return False
    if stage6_identity is not None:
        stage6_path = _t075_resolve_identity_path(
            str(stage6_identity.get("path", "")), artifact_root=artifact_root
        )
        if stage6_path is None or not _t075_stage6_report_is_valid(
            stage6_path, artifact_root=artifact_root
        ):
            return False
        try:
            loaded_stage6 = json.loads(stage6_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return False
        if not isinstance(loaded_stage6, Mapping):
            return False
        stage6_report = loaded_stage6
    failure_stage = value.get("failure_stage")
    failure_stage_map = {
        "source-input-reuse": "stage0-reuse",
        "cohort-ownership": "stage1-selection-replay",
        "replay": "stage1-selection-replay",
        "target-sharding": "stage2-target",
        "stage3-model-input-lineage-firewall": "stage2-target",
        "stage6": "stage6-eval",
    }
    if value["terminal_case"] == "D":
        if not isinstance(failure_stage, str):
            return False
        if (
            failure_stage not in failure_stage_map
            and failure_stage not in execution_stages
        ) or failure_stage_map.get(failure_stage, failure_stage) != terminal_stage:
            return False
    if not retention_path.is_file():
        return False
    try:
        _commands, retained_evidence, _reused = _t075_stage_retention_records(
            retention_path.parent, value
        )
    except (OSError, ValueError, T075WorkflowError):
        return False
    retained_outputs = [
        entry
        for stage_value in retained_evidence.values()
        for entry in stage_value.get("output_identities", [])
        if isinstance(entry, Mapping)
    ]
    for identity in value["parent_artifact_identities"].values():
        if not any(
            entry.get("path") == identity.get("path")
            and entry.get("sha256") == identity.get("sha256")
            and entry.get("size_bytes") == identity.get("size_bytes")
            for entry in retained_outputs
        ):
            return False
    if value["terminal_case"] in {"A", "B"} or (
        value["terminal_case"] == "D" and value.get("terminal_stage") == "stage6-eval"
    ):
        stage6_identity = value.get("stage6_report_identity")
        if not isinstance(stage6_identity, Mapping) or not any(
            entry.get("path") == stage6_identity.get("path")
            and entry.get("sha256") == stage6_identity.get("sha256")
            and entry.get("size_bytes") == stage6_identity.get("size_bytes")
            for entry in retained_outputs
        ):
            return False
    case = value["terminal_case"]
    if case in {"A", "B"}:
        if (
            not isinstance(stage6_report, Mapping)
            or stage6_report.get("valid") is not True
        ):
            return False
        if case == "A" and stage6_report.get("passed") is not True:
            return False
        if case == "B" and stage6_report.get("passed") is not False:
            return False
    if case == "D" and terminal_stage == "stage6-eval":
        if (
            not isinstance(stage6_report, Mapping)
            or stage6_report.get("valid") is not False
            or stage6_report.get("passed") is not False
            or not isinstance(stage6_report.get("problems"), list)
            or not stage6_report["problems"]
            or stage6_report.get("execution_evidence", {}).get("status") != "failed"
        ):
            return False
    if case == "D":
        failure_ids = value.get("failure_ids")
        failure_counts = value.get("failure_counts")
        failure_details = value.get("failure_details")
        if (
            not isinstance(failure_ids, list)
            or not failure_ids
            or any(
                not isinstance(item, str) or not item.strip() for item in failure_ids
            )
            or len(set(failure_ids)) != len(failure_ids)
            or not isinstance(failure_counts, Mapping)
            or any(
                isinstance(count, bool) or not isinstance(count, int) or count < 0
                for count in failure_counts.values()
            )
            or not isinstance(failure_details, list)
        ):
            return False
        declared_failure_count = failure_counts.get("failure_count")
        if declared_failure_count is not None and declared_failure_count != len(
            failure_ids
        ):
            return False
        for detail in failure_details:
            if isinstance(detail, Mapping) and "failure_id" in detail:
                if detail["failure_id"] not in failure_ids:
                    return False
        return (
            bool(value["problems"])
            and isinstance(value.get("failure_stage"), str)
            and bool(value["failure_stage"])
            and (
                value.get("stage6_status") == "failed"
                if terminal_stage == "stage6-eval"
                else value.get("stage6_status") == "not_reached"
            )
        )
    if case == "C":
        return (
            terminal_stage == "stage5-gate"
            and value.get("stage5_gate_status") == "failed"
            and value.get("stage6_status") == "skipped"
        )
    return (
        terminal_stage == "stage6-eval"
        and value.get("stage5_gate_status") == "passed"
        and value.get("stage6_status") == "completed"
    )


def _t075_has_terminal_decision(args: argparse.Namespace) -> bool:
    path = getattr(args, "decision_report", None)
    if not isinstance(path, Path) or not path.is_file():
        return False
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    return _t075_terminal_decision_is_valid(
        value,
        artifact_root=path.parent,
        retention_path=getattr(args, "retention_manifest", None),
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m sts_combat_rl.commands.non_combat_learning",
        description="T065 learned public non-combat policy workflow",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    preflight = subparsers.add_parser(
        "preflight", help="run cheap schema readiness checks"
    )
    preflight.add_argument("--output", type=Path, required=True)
    preflight.add_argument("--decision-report", type=Path)
    preflight.add_argument("--retention-manifest", type=Path)
    preflight.add_argument(
        "--simulator-runtime",
        action="store_true",
        help="explicitly probe the WSL-provided simulator runtime",
    )
    preflight.add_argument(
        "--torch-runtime",
        action="store_true",
        help="explicitly probe the optional PyTorch runtime",
    )
    preflight.add_argument("--sim-seed", type=int, default=1)
    preflight.add_argument("--ascension", type=int, default=20)

    reuse = subparsers.add_parser(
        "validate-reuse", help="validate the two retained T065 source arms"
    )
    reuse.add_argument("--source", type=Path, action="append", required=True)
    reuse.add_argument("--accepted-preflight-content-sha256", required=True)
    reuse.add_argument("--source-preflight-alias", type=Path, action="append")
    reuse.add_argument("--source-preflight-retention-alias", type=Path, action="append")
    reuse.add_argument("--accepted-case-d", type=Path, required=True)
    reuse.add_argument("--accepted-case-d-retention", type=Path, required=True)
    reuse.add_argument("--output", type=Path, required=True)
    reuse.add_argument("--retention-manifest", type=Path, required=True)
    reuse.add_argument("--decision-report", type=Path)

    collect = subparsers.add_parser(
        "collect", help="collect one fixed source behavior arm"
    )
    collect.add_argument(
        "--arm",
        choices=("stochastic_non_combat_v1", "expert_non_combat_v1"),
        required=True,
    )
    collect.add_argument("--output", type=Path, required=True)
    collect.add_argument("--seed-start", type=int, default=T065_SOURCE_SEED_RANGE[0])
    collect.add_argument("--seed-end", type=int, default=T065_SOURCE_SEED_RANGE[1])
    collect.add_argument("--sim-seed", type=int, default=1)
    collect.add_argument("--ascension", type=int, default=20)
    collect.add_argument("--decision-report", type=Path)
    collect.add_argument("--preflight", type=Path, required=True)
    collect.add_argument("--preceding-manifest", type=Path, action="append")
    collect.add_argument("--retention-manifest", type=Path)

    select = subparsers.add_parser(
        "select", help="deduplicate and select the frozen cohort"
    )
    select.add_argument("--input", type=Path, action="append", required=True)
    select.add_argument("--output", type=Path, required=True)
    select.add_argument("--manifest", type=Path)
    select.add_argument("--decision-report", type=Path)
    select.add_argument("--preflight", type=Path, required=True)
    select.add_argument("--preceding-manifest", type=Path, action="append")
    select.add_argument("--retention-manifest", type=Path)
    select.add_argument("--reuse-manifest", type=Path)
    select.add_argument("--ownership-audit", type=Path)
    select.add_argument("--replay-verify", action="store_true")
    select.add_argument("--replay-shard-count", type=int, default=16)
    select.add_argument("--replay-worker-count", type=int, default=16)
    select.add_argument("--selection-strategy", default=T075_SELECTION_STRATEGY_ID)

    target = subparsers.add_parser(
        "target", help="generate all-action counterfactual targets"
    )
    target.add_argument("--states", type=Path, required=True)
    target.add_argument("--output", type=Path, required=True)
    target.add_argument("--sim-seed", type=int, default=1)
    target.add_argument("--ascension", type=int, default=20)
    target.add_argument("--decision-report", type=Path)
    target.add_argument("--preflight", type=Path, required=True)
    target.add_argument("--preceding-manifest", type=Path, action="append")
    target.add_argument("--retention-manifest", type=Path)
    target.add_argument("--selection-manifest", type=Path)
    target.add_argument("--validation-report", type=Path)
    target.add_argument("--shard-count", type=int, default=16)
    target.add_argument("--worker-count", type=int, default=16)

    train = subparsers.add_parser("train", help="train the two frozen model seeds")
    train.add_argument("--target-table", type=Path, required=True)
    train.add_argument("--checkpoint-directory", type=Path, required=True)
    train.add_argument("--output", type=Path, required=True)
    train.add_argument("--preflight", type=Path, required=True)
    train.add_argument("--preceding-manifest", type=Path, action="append")
    train.add_argument("--decision-report", type=Path)
    train.add_argument("--retention-manifest", type=Path)
    train.add_argument("--target-validation", type=Path)

    evaluate = subparsers.add_parser(
        "evaluate", help="run held-out gate and conditional Stage 6"
    )
    evaluate.add_argument("--target-table", type=Path, required=True)
    evaluate.add_argument("--checkpoint-directory", type=Path, required=True)
    evaluate.add_argument("--output", type=Path, required=True)
    evaluate.add_argument("--run-stage6", action="store_true")
    evaluate.add_argument("--sim-seed", type=int, default=1)
    evaluate.add_argument("--ascension", type=int, default=20)
    evaluate.add_argument("--preflight", type=Path, required=True)
    evaluate.add_argument("--preceding-manifest", type=Path, action="append")
    evaluate.add_argument("--decision-report", type=Path)
    evaluate.add_argument("--retention-manifest", type=Path)
    evaluate.add_argument("--stage5-report", type=Path)
    evaluate.add_argument("--stage6-shard-count", type=int, default=16)
    evaluate.add_argument("--stage6-worker-count", type=int, default=16)

    finalize = subparsers.add_parser(
        "finalize", help="validate and retain the terminal T075 decision"
    )
    finalize.add_argument("--artifact-root", type=Path, required=True)
    finalize.add_argument("--decision-report", type=Path, required=True)
    finalize.add_argument("--retention-manifest", type=Path, required=True)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    args._command_argv = tuple(argv if argv is not None else sys.argv[1:])
    args._t075_execution_start_monotonic = time.perf_counter()
    args._t075_execution_start_utc = datetime.now(timezone.utc).isoformat()
    try:
        if args.command == "preflight":
            return (
                _run_t075_preflight(args)
                if _is_t075_invocation(args)
                else _run_preflight(args)
            )
        if args.command == "validate-reuse":
            return _run_t075_validate_reuse(args)
        if args.command == "collect":
            return _run_collect(args)
        if args.command == "select":
            return (
                _run_t075_select(args)
                if _is_t075_invocation(args)
                else _run_select(args)
            )
        if args.command == "target":
            return (
                _run_t075_target(args)
                if _is_t075_invocation(args)
                else _run_target(args)
            )
        if args.command == "train":
            return (
                _run_t075_train(args) if _is_t075_invocation(args) else _run_train(args)
            )
        if args.command == "evaluate":
            return (
                _run_t075_evaluate(args)
                if _is_t075_invocation(args)
                else _run_evaluate(args)
            )
        if args.command == "finalize":
            return _run_t075_finalize(args)
    except T075WorkflowError as exc:
        if args.command == "finalize":
            print(f"T075 finalization failed: {exc}", file=sys.stderr)
            return 1
        try:
            _handle_t075_case_d(args, exc)
        except Exception as materialization_error:
            print(
                "T075 Case D retention materialization failed: "
                f"{type(materialization_error).__name__}: {materialization_error}",
                file=sys.stderr,
            )
        print(f"T075 command failed: {exc}", file=sys.stderr)
        return 1
    except T065CaseD as exc:
        if _is_t075_invocation(args):
            if args.command == "finalize":
                print(f"T075 finalization failed: {exc}", file=sys.stderr)
                return 1
            failure = T075WorkflowError(
                exc.stage,
                list(exc.problems),
                failure_ids=exc.failure_ids,
                failure_counts=exc.failure_counts,
                failure_details=exc.failure_details,
                failure_detail_counts=exc.failure_detail_counts,
                simulator_identity=exc.simulator_identity,
                execution_evidence=exc.execution_evidence,
            )
            try:
                _handle_t075_case_d(args, failure)
            except Exception as materialization_error:
                print(
                    "T075 Case D retention materialization failed: "
                    f"{type(materialization_error).__name__}: {materialization_error}",
                    file=sys.stderr,
                )
            print(f"T075 command failed: {exc}", file=sys.stderr)
            return 1
        _handle_case_d(args, exc)
        print(f"T065 command failed: {exc}", file=sys.stderr)
        return 1
    except (OSError, RuntimeError, ValueError) as exc:
        failure_class = T075WorkflowError if _is_t075_invocation(args) else T065CaseD
        failure = failure_class(
            _stage_name(args.command),
            [str(exc)],
            failure_ids=(f"command:{args.command}",),
            failure_counts={"failure_count": 1},
            simulator_identity=lightspeed_source_identity_dict(),
        )
        if isinstance(failure, T075WorkflowError):
            if args.command == "finalize":
                print(f"T075 finalization failed: {failure}", file=sys.stderr)
                return 1
            try:
                _handle_t075_case_d(args, failure)
            except Exception as materialization_error:
                print(
                    "T075 Case D retention materialization failed: "
                    f"{type(materialization_error).__name__}: {materialization_error}",
                    file=sys.stderr,
                )
            print(f"T075 command failed: {exc}", file=sys.stderr)
        else:
            _handle_case_d(args, failure)
            print(f"T065 command failed: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        # Process-pool failures and malformed worker payloads are not all
        # subclasses of ValueError.  T075 must still materialize its own
        # terminal schema instead of falling through to the legacy handler.
        if not _is_t075_invocation(args):
            raise
        failure = T075WorkflowError(
            _stage_name(args.command),
            [f"{type(exc).__name__}: {exc}"],
            failure_ids=(f"command:{args.command}",),
            failure_counts={"failure_count": 1},
            simulator_identity=_t075_pinned_simulator_identity(),
        )
        if args.command == "finalize":
            print(f"T075 finalization failed: {failure}", file=sys.stderr)
            return 1
        try:
            _handle_t075_case_d(args, failure)
        except Exception as materialization_error:
            print(
                "T075 Case D retention materialization failed: "
                f"{type(materialization_error).__name__}: {materialization_error}",
                file=sys.stderr,
            )
        print(f"T075 command failed: {failure}", file=sys.stderr)
        return 1
    return 2


def _is_t075_invocation(args: argparse.Namespace) -> bool:
    """Identify T075 commands without adding a legacy-CLI flag."""

    if args.command in {"validate-reuse", "finalize"}:
        return True
    if args.command == "preflight":
        return bool(
            getattr(args, "decision_report", None)
            or getattr(args, "retention_manifest", None)
        )
    if args.command in {"select", "target", "train"}:
        return bool(
            getattr(args, "reuse_manifest", None)
            or getattr(args, "selection_manifest", None)
            or getattr(args, "target_validation", None)
            or getattr(args, "retention_manifest", None)
        )
    if args.command == "evaluate":
        # This command surface is T075-only.  In particular, missing or
        # corrupt preceding retention is an input failure, never a routing
        # signal that may fall through to the legacy T065 handler.
        return True
    return False


def _validate_t075_preflight(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise T075WorkflowError(
            "stage0-preflight", [f"preflight cannot be read: {exc}"]
        ) from exc
    if not isinstance(value, Mapping):
        raise T075WorkflowError("stage0-preflight", ["preflight root is not an object"])
    if value.get("schema_id") != "t065-readiness-preflight-v1":
        raise T075WorkflowError("stage0-preflight", ["preflight schema is unsupported"])
    if value.get("schema_version") != 1:
        raise T075WorkflowError(
            "stage0-preflight", ["preflight schema version is unsupported"]
        )
    if value.get("approved_spec_commit") != T075_APPROVED_SPEC_COMMIT:
        raise T075WorkflowError(
            "stage0-preflight", ["preflight is not tied to approved T075 spec"]
        )
    legacy_value = dict(value)
    legacy_value["approved_spec_commit"] = T065_APPROVED_SPEC_COMMIT
    legacy_path = path.with_name(f".{path.name}.t065-validation")
    try:
        legacy_path.write_text(json.dumps(legacy_value), encoding="utf-8")
        try:
            validate_t065_preflight(legacy_path)
        except T065CaseD as exc:
            raise T075WorkflowError("stage0-preflight", list(exc.problems)) from exc
    finally:
        legacy_path.unlink(missing_ok=True)
    if value.get("passed") is not True:
        raise T075WorkflowError(
            "stage0-preflight", ["fresh T075 preflight did not pass"]
        )
    return dict(value)


def _run_t075_preflight(args: argparse.Namespace) -> int:
    _require_frozen_simulator_args(args)
    factory = None
    if args.simulator_runtime:
        factory = lambda: LightSpeedAdapter(  # noqa: E731
            seed=args.sim_seed,
            ascension=args.ascension,
            player_class="IRONCLAD",
        )
    report = build_t065_preflight_report(
        adapter_factory=factory,
        check_simulator_runtime=args.simulator_runtime,
        check_torch_runtime=args.torch_runtime,
    ).to_dict()
    report["approved_spec_commit"] = T075_APPROVED_SPEC_COMMIT
    report["task_id"] = T075_TASK_ID
    _write_canonical_json(args.output, report)
    if report.get("passed") is not True:
        failed = [
            str(name)
            for section in ("capability_checks", "runtime_checks")
            for name, check in report.get(section, {}).items()
            if not isinstance(check, Mapping) or check.get("status") != "passed"
        ]
        raise T075WorkflowError(
            "stage0-preflight",
            tuple(report.get("problems", ())) or ("preflight did not pass",),
            failure_ids=tuple(f"preflight-check:{name}" for name in failed),
            failure_counts={"failed_checks": len(failed)},
            simulator_identity=report.get("simulator_identity", {}),
        )
    _write_t075_stage_retention(
        args,
        stage="stage0-preflight",
        artifacts={"current_output": args.output},
        evidence={
            **_t075_execution_evidence(
                args, status="completed", terminal=True, exit_code=0, executed=True
            ),
            "passed": True,
            "shard_count": 0,
            "worker_count": 0,
            "ranges": [],
            "per_shard": [],
            "parent_identities": {},
        },
    )
    print(f"T075 preflight passed: {args.output}", file=sys.stderr)
    return 0


def _run_preflight(args: argparse.Namespace) -> int:
    _require_frozen_simulator_args(args)
    factory = None
    if args.simulator_runtime:
        factory = lambda: LightSpeedAdapter(  # noqa: E731
            seed=args.sim_seed,
            ascension=args.ascension,
            player_class="IRONCLAD",
        )
    report = build_t065_preflight_report(
        adapter_factory=factory,
        check_simulator_runtime=args.simulator_runtime,
        check_torch_runtime=args.torch_runtime,
    ).to_dict()
    _write_json(args.output, report)
    print(json.dumps(report, indent=2, sort_keys=True), file=sys.stderr)
    if not report["passed"]:
        failed_checks = tuple(
            name
            for section in ("capability_checks", "runtime_checks")
            for name, check in report.get(section, {}).items()
            if not isinstance(check, Mapping) or check.get("status") != "passed"
        )
        raise T065CaseD(
            "stage0-preflight",
            tuple(report.get("problems", ())) or ("preflight did not pass",),
            failure_ids=tuple(f"preflight-check:{name}" for name in failed_checks),
            failure_counts={"failed_checks": len(failed_checks)},
            simulator_identity=report.get("simulator_identity", {}),
        )
    _write_workflow_manifest(args, stage="stage0-preflight")
    return 0


def _write_canonical_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    try:
        temporary.write_text(
            json.dumps(
                value,
                ensure_ascii=False,
                allow_nan=False,
                sort_keys=True,
                separators=(",", ":"),
            )
            + "\n",
            encoding="utf-8",
        )
        os.replace(temporary, path)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def _t075_finite_number(value: Any) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
    )


def _t075_stage5_state_result(value: Any, *, model_seed: int) -> T065HeldoutStateResult:
    if not isinstance(value, Mapping):
        raise ValueError("Stage-5 state result is not an object")

    def integer(name: str, *, allow_none: bool = False) -> int | None:
        item = value.get(name)
        if allow_none and item is None:
            return None
        if isinstance(item, bool) or not isinstance(item, int):
            raise ValueError(f"Stage-5 state result {name} is not an integer")
        return item

    def finite(name: str, *, allow_none: bool = False) -> float | None:
        item = value.get(name)
        if allow_none and item is None:
            return None
        if not _t075_finite_number(item):
            raise ValueError(f"Stage-5 state result {name} is not finite")
        return float(item)

    required_strings = (
        "family",
        "split",
        "source_behavior",
        "screen_state",
        "public_state_identity",
    )
    if any(not isinstance(value.get(name), str) for name in required_strings):
        raise ValueError("Stage-5 state result has invalid identity text")
    if integer("selected_state_index") is None or integer("model_seed") != model_seed:
        raise ValueError("Stage-5 state result has invalid seed identity")
    for name in (
        "source_behavior_action_identity",
        "model_action_identity",
        "expert_action_identity",
        "predicted_action_values",
        "empirical_action_values",
    ):
        if not isinstance(value.get(name), Mapping):
            raise ValueError(f"Stage-5 state result {name} is not an object")
    empirical_best = value.get("empirical_best_action_indices")
    if not isinstance(empirical_best, list) or any(
        isinstance(item, bool) or not isinstance(item, int) for item in empirical_best
    ):
        raise ValueError("Stage-5 state result best actions are malformed")
    predicted_values = value["predicted_action_values"]
    empirical_values = value["empirical_action_values"]
    if any(not _t075_finite_number(item) for item in predicted_values.values()) or any(
        not _t075_finite_number(item) for item in empirical_values.values()
    ):
        raise ValueError("Stage-5 state result action values are not finite")
    rank_correlation = finite("rank_correlation", allow_none=True)
    return T065HeldoutStateResult(
        selected_state_index=integer("selected_state_index"),
        family=value["family"],
        split=value["split"],
        source_behavior=value["source_behavior"],
        screen_state=value["screen_state"],
        source_act=finite("source_act", allow_none=True),
        source_floor=finite("source_floor", allow_none=True),
        public_state_identity=value["public_state_identity"],
        source_behavior_action_index=integer(
            "source_behavior_action_index", allow_none=True
        ),
        source_behavior_action_identity=dict(value["source_behavior_action_identity"]),
        model_seed=model_seed,
        model_action_index=integer("model_action_index"),
        model_action_identity=dict(value["model_action_identity"]),
        expert_action_index=integer("expert_action_index"),
        expert_action_identity=dict(value["expert_action_identity"]),
        model_q_floor=finite("model_q_floor"),
        expert_q_floor=finite("expert_q_floor"),
        delta=finite("delta"),
        predicted_action_values={
            str(key): float(item) for key, item in predicted_values.items()
        },
        empirical_best_action_indices=tuple(empirical_best),
        empirical_action_values={
            str(key): float(item) for key, item in empirical_values.items()
        },
        rank_correlation=rank_correlation,
    )


def _read_t075_stage5_gate_report(
    path: Path, *, target_table_path: Path
) -> T065HeldoutReport:
    """Load the frozen Stage-5 parent without rebuilding or rewriting it."""

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise T075WorkflowError(
            "stage5-gate", [f"supplied Stage-5 report is unreadable: {exc}"]
        ) from exc
    if not isinstance(payload, Mapping):
        raise T075WorkflowError(
            "stage5-gate", ["supplied Stage-5 report is not an object"]
        )
    if (
        payload.get("schema_id") != "t075-stage5-gate-report-v1"
        or payload.get("schema_version") != 1
        or payload.get("task_id") != T075_TASK_ID
        or payload.get("approved_t075_spec_commit") != T075_APPROVED_SPEC_COMMIT
    ):
        raise T075WorkflowError(
            "stage5-gate", ["supplied Stage-5 report wrapper is not frozen"]
        )
    if payload.get("parent_target_table_sha256") != file_sha256(target_table_path):
        raise T075WorkflowError(
            "stage5-gate", ["supplied Stage-5 report target parent does not match"]
        )
    wrapper_passed = payload.get("passed")
    wrapper_problems = payload.get("problems")
    nested = payload.get("stage5")
    if (
        not isinstance(wrapper_passed, bool)
        or not isinstance(wrapper_problems, list)
        or any(not isinstance(problem, str) for problem in wrapper_problems)
        or not isinstance(nested, Mapping)
        or nested.get("schema_id") != T065_STAGE5_REPORT_SCHEMA_ID
        or nested.get("schema_version") != 1
    ):
        raise T075WorkflowError(
            "stage5-gate", ["supplied Stage-5 report shape is incomplete"]
        )
    selected_seed = nested.get("selected_model_seed")
    model_results = nested.get("model_results")
    family_means = nested.get("family_mean_deltas")
    nested_problems = nested.get("problems")
    expected_model_keys = {str(seed) for seed in T065_MODEL_SEEDS}
    if (
        isinstance(selected_seed, bool)
        or not isinstance(selected_seed, int)
        or selected_seed not in T065_MODEL_SEEDS
        or not isinstance(model_results, Mapping)
        or set(model_results) != expected_model_keys
        or not isinstance(family_means, Mapping)
        or set(family_means) != set(T065_MANDATORY_FAMILIES)
        or any(not _t075_finite_number(value) for value in family_means.values())
        or not isinstance(nested_problems, list)
        or any(not isinstance(problem, str) for problem in nested_problems)
    ):
        raise T075WorkflowError(
            "stage5-gate", ["supplied Stage-5 report nested evidence is incomplete"]
        )
    parsed_model_results: dict[str, tuple[T065HeldoutStateResult, ...]] = {}
    try:
        for seed, results in model_results.items():
            model_seed = int(seed)
            if (
                not isinstance(seed, str)
                or isinstance(results, (str, bytes))
                or not isinstance(results, list)
            ):
                raise ValueError("model result collection is malformed")
            parsed_model_results[seed] = tuple(
                _t075_stage5_state_result(result, model_seed=model_seed)
                for result in results
            )
            parsed = parsed_model_results[seed]
            if len(parsed) != 64:
                raise ValueError("each Stage-5 model must contain 64 held-out states")
            family_counts = {
                family: sum(result.family == family for result in parsed)
                for family in T065_MANDATORY_FAMILIES
            }
            if (
                any(result.split != "heldout" for result in parsed)
                or any(count != 16 for count in family_counts.values())
                or any(
                    result.family not in T065_MANDATORY_FAMILIES for result in parsed
                )
            ):
                raise ValueError(
                    "Stage-5 held-out model results have invalid family/split coverage"
                )
    except (TypeError, ValueError) as exc:
        raise T075WorkflowError(
            "stage5-gate", [f"supplied Stage-5 model results are malformed: {exc}"]
        ) from exc
    numeric_fields = (
        "selected_validation_mae",
        "aggregate_mean_delta",
        "median_delta",
        "p_positive",
        "non_selected_model_mean_delta",
    )
    if any(not _t075_finite_number(nested.get(field)) for field in numeric_fields):
        raise T075WorkflowError(
            "stage5-gate", ["supplied Stage-5 metrics are not finite"]
        )
    nested_passed = nested.get("passed")
    if (
        not isinstance(nested_passed, bool)
        or nested_passed != wrapper_passed
        or nested_problems != wrapper_problems
    ):
        raise T075WorkflowError(
            "stage5-gate", ["supplied Stage-5 pass status is inconsistent"]
        )
    return T065HeldoutReport(
        selected_model_seed=selected_seed,
        selected_validation_mae=float(nested["selected_validation_mae"]),
        model_results=parsed_model_results,
        aggregate_mean_delta=float(nested["aggregate_mean_delta"]),
        median_delta=float(nested["median_delta"]),
        family_mean_deltas={
            str(key): float(value) for key, value in family_means.items()
        },
        p_positive=float(nested["p_positive"]),
        non_selected_model_mean_delta=float(nested["non_selected_model_mean_delta"]),
        passed=wrapper_passed,
        problems=tuple(nested_problems),
    )


def _t075_command_string(
    args: argparse.Namespace, *, command_argv: Sequence[str] | None = None
) -> str:
    tokens = [
        str(token)
        for token in (
            getattr(args, "_command_argv", ()) if command_argv is None else command_argv
        )
    ]
    rendered = []
    for token in tokens:
        if "\\" in token or (len(token) > 1 and token[1] == ":"):
            rendered.append(_wsl_path(Path(token)))
        else:
            rendered.append(token)
    return "wsl.exe -d Ubuntu -e bash -lc " + shlex.quote(
        "set -euo pipefail; "
        f"cd {shlex.quote(_wsl_path(_target_src_path().parent))}; "
        f"export PYTHONPATH={shlex.quote(T065_LIGHTSPEED_BUILD_PYTHONPATH + ':' + _wsl_path(_target_src_path()))}; "
        f"{shlex.quote(T065_TRAINING_INTERPRETER)} -m "
        f"sts_combat_rl.commands.non_combat_learning {shlex.join(rendered)}"
    )


def _t075_standalone_stage6_argv(args: argparse.Namespace) -> tuple[str, ...]:
    """Build the frozen independent Stage-6 command from observed paths."""

    output = getattr(args, "output", None)
    retention = getattr(args, "retention_manifest", None)
    if not isinstance(output, Path) or not isinstance(retention, Path):
        raise T075WorkflowError(
            "stage6-eval", ["independent Stage-6 command lacks output/retention paths"]
        )
    run_stage6 = bool(getattr(args, "run_stage6", False))
    stage5_report = getattr(args, "stage5_report", None) or output
    stage5_parent = getattr(args, "preceding_manifest", None)
    if not run_stage6:
        stage5_parent = retention
    if not isinstance(stage5_report, Path) or not isinstance(stage5_parent, Path):
        raise T075WorkflowError(
            "stage6-eval", ["independent Stage-6 command lacks Stage-5 parent paths"]
        )
    stage6_output = (
        output if run_stage6 else output.with_name("stage6-complete-run-report.json")
    )
    stage6_retention = (
        retention if run_stage6 else retention.with_name("stage6.retention.json")
    )
    preflight = getattr(args, "preflight", None)
    decision_report = getattr(args, "decision_report", None)
    if not isinstance(preflight, Path) or not isinstance(decision_report, Path):
        raise T075WorkflowError(
            "stage6-eval",
            ["independent Stage-6 command lacks preflight/decision paths"],
        )
    return (
        "evaluate",
        "--target-table",
        str(args.target_table),
        "--checkpoint-directory",
        str(args.checkpoint_directory),
        "--stage5-report",
        str(stage5_report),
        "--output",
        str(stage6_output),
        "--run-stage6",
        "--stage6-shard-count",
        str(T075_STAGE6_SHARD_COUNT),
        "--stage6-worker-count",
        str(T065_MAX_WORKERS),
        "--preflight",
        str(preflight),
        "--preceding-manifest",
        str(stage5_parent),
        "--retention-manifest",
        str(stage6_retention),
        "--decision-report",
        str(decision_report),
    )


def _t075_frozen_stage_argv(args: argparse.Namespace, stage: str) -> tuple[str, ...]:
    """Build the exact argv prescribed for a stage, including skipped stages."""

    root = T075_STABLE_ARTIFACT_ROOT
    t065 = Path("D:/DeadlycatCoding/STSRL/artifacts/t065-learned-non-combat-policy-v1")
    if stage == "stage0-preflight":
        return (
            "preflight",
            "--output",
            str(root / "stage0-preflight.json"),
            "--simulator-runtime",
            "--torch-runtime",
            "--sim-seed",
            "1",
            "--ascension",
            "20",
            "--retention-manifest",
            str(root / "stage0-preflight.retention.json"),
            "--decision-report",
            str(root / "terminal-decision-report.json"),
        )
    if stage == "stage0-reuse":
        return (
            "validate-reuse",
            "--source",
            str(t065 / "source-stochastic-650001-650256-c57b2ee.json"),
            "--source",
            str(t065 / "source-expert-650001-650256-deeaa46.json"),
            "--accepted-preflight-content-sha256",
            "a89560d037ea4555922d0e1282edb8e328ce75ab6e1d720fd05f86022b56c334",
            "--source-preflight-alias",
            str(t065 / "preflight-c57b2ee-20260827.json"),
            "--source-preflight-alias",
            str(t065 / "preflight-968797e-20260827.json"),
            "--source-preflight-retention-alias",
            str(t065 / "preflight-c57b2ee-20260827.retention.json"),
            "--source-preflight-retention-alias",
            str(t065 / "preflight-968797e-20260827.retention.json"),
            "--accepted-case-d",
            str(
                t065
                / "source-selection-650001-650256-a69972f.t065-terminal-decision-report.json"
            ),
            "--accepted-case-d-retention",
            str(t065 / "source-selection-650001-650256-a69972f.retention.json"),
            "--output",
            str(root / "stage0-retained-source-reuse.json"),
            "--retention-manifest",
            str(root / "stage0-retained-source-reuse.retention.json"),
            "--decision-report",
            str(root / "terminal-decision-report.json"),
        )
    if stage == "stage1-selection-replay":
        return (
            "select",
            "--input",
            str(t065 / "source-stochastic-650001-650256-c57b2ee.json"),
            "--input",
            str(t065 / "source-expert-650001-650256-deeaa46.json"),
            "--selection-strategy",
            T075_SELECTION_STRATEGY_ID,
            "--reuse-manifest",
            str(root / "stage0-retained-source-reuse.json"),
            "--preflight",
            str(root / "stage0-preflight.json"),
            "--output",
            str(root / "stage1-selected-states.json"),
            "--ownership-audit",
            str(root / "stage1-replay-group-ownership-audit.json"),
            "--manifest",
            str(root / "stage1-selection-manifest.json"),
            "--replay-verify",
            "--replay-shard-count",
            "16",
            "--replay-worker-count",
            "16",
            "--retention-manifest",
            str(root / "stage1-selection.retention.json"),
            "--decision-report",
            str(root / "terminal-decision-report.json"),
        )
    if stage == "stage2-target":
        return (
            "target",
            "--states",
            str(root / "stage1-selected-states.json"),
            "--selection-manifest",
            str(root / "stage1-selection-manifest.json"),
            "--output",
            str(root / "stage2-target-table.json"),
            "--validation-report",
            str(root / "stage2-target-validation.json"),
            "--shard-count",
            "16",
            "--worker-count",
            "16",
            "--preflight",
            str(root / "stage0-preflight.json"),
            "--preceding-manifest",
            str(root / "stage1-selection.retention.json"),
            "--retention-manifest",
            str(root / "stage2-target-table.retention.json"),
            "--decision-report",
            str(root / "terminal-decision-report.json"),
        )
    if stage == "stage4-train":
        return (
            "train",
            "--target-table",
            str(root / "stage2-target-table.json"),
            "--target-validation",
            str(root / "stage2-target-validation.json"),
            "--checkpoint-directory",
            str(root / "stage4-checkpoints"),
            "--output",
            str(root / "stage4-training-report.json"),
            "--preflight",
            str(root / "stage0-preflight.json"),
            "--preceding-manifest",
            str(root / "stage2-target-table.retention.json"),
            "--retention-manifest",
            str(root / "stage4-training.retention.json"),
            "--decision-report",
            str(root / "terminal-decision-report.json"),
        )
    if stage == "stage5-gate":
        return (
            "evaluate",
            "--target-table",
            str(root / "stage2-target-table.json"),
            "--checkpoint-directory",
            str(root / "stage4-checkpoints"),
            "--output",
            str(root / "stage5-heldout-report.json"),
            "--preflight",
            str(root / "stage0-preflight.json"),
            "--preceding-manifest",
            str(root / "stage4-training.retention.json"),
            "--retention-manifest",
            str(root / "stage5.retention.json"),
            "--decision-report",
            str(root / "terminal-decision-report.json"),
        )
    if stage == "stage6-eval":
        return (
            "evaluate",
            "--target-table",
            str(root / "stage2-target-table.json"),
            "--checkpoint-directory",
            str(root / "stage4-checkpoints"),
            "--stage5-report",
            str(root / "stage5-heldout-report.json"),
            "--output",
            str(root / "stage6-complete-run-report.json"),
            "--run-stage6",
            "--stage6-shard-count",
            "16",
            "--stage6-worker-count",
            "16",
            "--preflight",
            str(root / "stage0-preflight.json"),
            "--preceding-manifest",
            str(root / "stage5.retention.json"),
            "--retention-manifest",
            str(root / "stage6.retention.json"),
            "--decision-report",
            str(root / "terminal-decision-report.json"),
        )
    raise T075WorkflowError(stage, ["no frozen argv is defined"])


def _t075_command_tokens_match_frozen(
    stage: str, command_tokens: Sequence[str]
) -> bool:
    """Compare argv token-by-token after canonical artifact-path normalization."""

    root = T075_STABLE_ARTIFACT_ROOT
    expected = _t075_frozen_stage_argv(
        argparse.Namespace(decision_report=root / "terminal-decision-report.json"),
        stage,
    )
    if len(command_tokens) != len(expected) + 1 or command_tokens[1:] == ():
        return False
    for actual, wanted in zip(command_tokens[1:], expected, strict=True):
        if "/" in wanted or "\\" in wanted or len(wanted) > 1 and wanted[1] == ":":
            try:
                if _t075_normalize_artifact_path(
                    actual
                ) != _t075_normalize_artifact_path(wanted):
                    return False
            except (OSError, TypeError, ValueError):
                return False
        elif actual != wanted:
            return False
    return True


def _t075_command_matches_contract(
    command: Any, stage: str, *, skipped: bool = False
) -> bool:
    del skipped
    if not isinstance(command, str) or not command.strip():
        return False
    if stage == "terminal-finalize":
        return command == _t075_terminal_finalize_command()
    if stage not in T075_STAGE_ORDER[:-1]:
        return False
    stable_root = T075_STABLE_ARTIFACT_ROOT
    expected_args = argparse.Namespace(
        decision_report=stable_root / "terminal-decision-report.json"
    )
    expected = _t075_command_string(
        expected_args,
        command_argv=_t075_frozen_stage_argv(expected_args, stage),
    )
    # The outer WSL launcher, shell preamble, checkout, PYTHONPATH, pinned
    # interpreter, module, and argv are all part of the frozen evidence.
    return command == expected


def _t075_terminal_finalize_argv() -> tuple[str, ...]:
    root = T075_STABLE_ARTIFACT_ROOT
    return (
        "finalize",
        "--artifact-root",
        str(root),
        "--decision-report",
        str(root / "terminal-decision-report.json"),
        "--retention-manifest",
        str(root / "t075-retention-manifest.json"),
    )


def _t075_terminal_finalize_command() -> str:
    return _t075_command_string(
        argparse.Namespace(), command_argv=_t075_terminal_finalize_argv()
    )


def _t075_cli_argv_matches(actual: Any, expected: Sequence[str]) -> bool:
    if not isinstance(actual, (tuple, list)) or len(actual) != len(expected):
        return False
    for observed, wanted in zip(actual, expected, strict=True):
        if not isinstance(observed, str):
            return False
        if "/" in wanted or "\\" in wanted or (len(wanted) > 1 and wanted[1] == ":"):
            try:
                if _t075_normalize_artifact_path(
                    observed
                ) != _t075_normalize_artifact_path(wanted):
                    return False
            except (OSError, TypeError, ValueError):
                return False
        elif observed != wanted:
            return False
    return True


def _t075_execution_evidence(
    args: argparse.Namespace,
    *,
    status: str,
    terminal: bool,
    exit_code: int | None,
    executed: bool,
) -> dict[str, Any]:
    """Build explicit execution fields at the command boundary.

    The retention writer deliberately refuses to invent these values.  The
    command entry point records the start; the caller supplies the observed
    exit/status at the stage boundary.
    """

    start_time = getattr(args, "_t075_execution_start_utc", None)
    if not isinstance(start_time, str) or not start_time:
        raise T075WorkflowError(
            "artifact-retention", ["T075 command has no execution start evidence"]
        )
    start_monotonic = getattr(args, "_t075_execution_start_monotonic", None)
    if (
        isinstance(start_monotonic, bool)
        or not isinstance(start_monotonic, (int, float))
        or not math.isfinite(float(start_monotonic))
    ):
        # Direct library-level callers do not pass through main; capture a
        # local bounded interval for those calls instead of inventing zero.
        start_monotonic = time.perf_counter()
    elapsed = max(0.0, time.perf_counter() - float(start_monotonic))
    return {
        "command": _t075_command_string(args),
        "executed": executed,
        "start_time_utc": start_time,
        "end_time_utc": datetime.now(timezone.utc).isoformat(),
        "exit_code": exit_code,
        "status": status,
        "terminal": terminal,
        "wall_clock_seconds": elapsed,
    }


def _t075_skipped_stage_contract(
    args: argparse.Namespace, stages: Sequence[str], reason: str
) -> tuple[dict[str, str], dict[str, dict[str, Any]]]:
    """Capture exact skipped-stage command/evidence before finalization."""

    contracts: dict[str, dict[str, Any]] = {}
    for stage in stages:
        command_argv = _t075_frozen_stage_argv(args, stage)
        command = _t075_command_string(args, command_argv=command_argv)
        contracts[stage] = {
            **_t075_execution_evidence(
                args, status="skipped", terminal=False, exit_code=None, executed=False
            ),
            "skip_reason": reason,
            "code_head": _code_head_for_artifact_root(args),
            "wall_clock_seconds": 0.0,
            "shard_count": 0,
            "worker_count": 0,
            "ranges": [],
            "per_shard": [],
            "parent_identities": {},
            "output_identities": [],
            "counts": {},
            "problems": [],
        }
        contracts[stage]["command"] = command
    return (
        {stage: str(value["command"]) for stage, value in contracts.items()},
        contracts,
    )


def _t075_artifact_identity(path: Path, *, role: str) -> dict[str, Any]:
    if not path.is_file():
        raise T075WorkflowError("artifact-retention", [f"artifact is missing: {path}"])
    return {
        "role": role,
        "path": str(path),
        "sha256": file_sha256(path),
        "size_bytes": path.stat().st_size,
    }


def _t075_path_matches(left: str | Path, right: str | Path) -> bool:
    try:
        return _t075_normalize_artifact_path(
            str(left)
        ) == _t075_normalize_artifact_path(str(right))
    except (OSError, ValueError, TypeError):
        return False


def _t075_stage_retention_records(
    artifact_root: Path, decision: Mapping[str, Any]
) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    """Read every completed stage retention without basename-based lookup."""

    def validate_stage_entry(
        path: Path, stage: str, command: Mapping[str, Any], evidence: Mapping[str, Any]
    ) -> None:
        required = (
            "command",
            "executed",
            "status",
            "code_head",
            "start_time_utc",
            "end_time_utc",
            "exit_code",
            "terminal",
            "wall_clock_seconds",
            "shard_count",
            "worker_count",
            "ranges",
            "parent_identities",
            "output_identities",
        )
        if any(key not in command for key in required) or any(
            key not in evidence for key in required
        ):
            raise T075WorkflowError(
                "terminal-finalize", [f"retention for {stage} is incomplete: {path}"]
            )
        if command.get("code_head") != evidence.get("code_head"):
            raise T075WorkflowError(
                "terminal-finalize",
                [f"retention for {stage} code head diverges: {path}"],
            )
        current_code_head = _code_head_for_artifact_root(argparse.Namespace())
        if command.get("code_head") != current_code_head:
            raise T075WorkflowError(
                "terminal-finalize",
                [f"retention for {stage} is from a different code head: {path}"],
            )
        if (
            not isinstance(command.get("command"), str)
            or not command["command"].strip()
            or command.get("command") != evidence.get("command")
            or not isinstance(command.get("start_time_utc"), str)
            or not command["start_time_utc"].strip()
            or command.get("start_time_utc") != evidence.get("start_time_utc")
            or not isinstance(command.get("end_time_utc"), str)
            or not command["end_time_utc"].strip()
            or command.get("end_time_utc") != evidence.get("end_time_utc")
            or command.get("exit_code") != evidence.get("exit_code")
        ):
            raise T075WorkflowError(
                "terminal-finalize",
                [f"retention execution evidence diverges: {path}"],
            )
        if not _t075_command_matches_contract(
            command["command"], stage, skipped=command.get("status") == "skipped"
        ):
            raise T075WorkflowError(
                "terminal-finalize",
                [f"retention command is not the frozen runtime command: {path}"],
            )
        start = _t075_parse_utc_timestamp(command["start_time_utc"])
        end = _t075_parse_utc_timestamp(command["end_time_utc"])
        if start is None or end is None or start > end:
            raise T075WorkflowError(
                "terminal-finalize",
                [f"retention execution bounds are invalid: {path}"],
            )
        if command.get("exit_code") is not None and (
            isinstance(command.get("exit_code"), bool)
            or not isinstance(command.get("exit_code"), int)
        ):
            raise T075WorkflowError(
                "terminal-finalize", [f"retention exit code is invalid: {path}"]
            )
        if command.get("status") == "completed" and command.get("exit_code") != 0:
            raise T075WorkflowError(
                "terminal-finalize", [f"completed retention has nonzero exit: {path}"]
            )
        if command.get("status") == "failed" and command.get("exit_code") == 0:
            raise T075WorkflowError(
                "terminal-finalize", [f"failed retention has zero exit: {path}"]
            )
        if command.get("status") != evidence.get("status") or command.get(
            "terminal"
        ) != evidence.get("terminal"):
            raise T075WorkflowError(
                "terminal-finalize", [f"retention for {stage} status diverges: {path}"]
            )
        if command.get("status") not in {"completed", "pending", "failed", "skipped"}:
            raise T075WorkflowError(
                "terminal-finalize",
                [f"retention for {stage} status is invalid: {path}"],
            )
        if not isinstance(command.get("executed"), bool) or not isinstance(
            command.get("terminal"), bool
        ):
            raise T075WorkflowError(
                "terminal-finalize",
                [f"retention for {stage} flags are invalid: {path}"],
            )
        if command.get("status") == "completed" and command.get("terminal") is not True:
            raise T075WorkflowError(
                "terminal-finalize", [f"completed retention is not terminal: {path}"]
            )
        if command.get("status") == "skipped" and not evidence.get("skip_reason"):
            raise T075WorkflowError(
                "terminal-finalize", [f"skipped retention has no reason: {path}"]
            )
        if stage in {"stage1-selection-replay", "stage2-target", "stage6-eval"}:
            _t075_validate_process_shards(
                stage,
                shard_count=evidence["shard_count"],
                worker_count=evidence["worker_count"],
                per_shard=evidence.get("per_shard"),
                status=str(evidence.get("status")),
                ranges=evidence.get("ranges"),
                allow_partial_failure=evidence.get("partial_spawn_failure") is True,
            )
        outputs = evidence.get("output_identities")
        command_outputs = command.get("output_identities")
        if not isinstance(outputs, list) or command_outputs != outputs:
            raise T075WorkflowError(
                "terminal-finalize", [f"retention outputs diverge: {path}"]
            )
        roles: list[str] = []
        for entry in outputs:
            if not isinstance(entry, Mapping) or not isinstance(entry.get("role"), str):
                raise T075WorkflowError(
                    "terminal-finalize", [f"retention output role is invalid: {path}"]
                )
            role = str(entry["role"])
            if role in roles:
                raise T075WorkflowError(
                    "terminal-finalize",
                    [f"retention output role is duplicated: {path}"],
                )
            raw_path = entry.get("path")
            if not isinstance(raw_path, str):
                raise T075WorkflowError(
                    "terminal-finalize", [f"retention output path is invalid: {path}"]
                )
            output_path = _portable_path(raw_path)
            if not output_path.is_file() and not Path(raw_path).is_absolute():
                output_path = artifact_root / raw_path
            if not _t075_identity_matches(entry, output_path, expected_role=role):
                raise T075WorkflowError(
                    "terminal-finalize",
                    [f"retention output identity is invalid: {path}"],
                )
            roles.append(role)
        referenced_roles = evidence.get("artifact_roles")
        if not isinstance(referenced_roles, list) or referenced_roles != roles:
            raise T075WorkflowError(
                "terminal-finalize", [f"retention artifact roles diverge: {path}"]
            )
        parent_identities = evidence.get("parent_identities")
        if not isinstance(parent_identities, Mapping):
            raise T075WorkflowError(
                "terminal-finalize",
                [f"retention parent identities are invalid: {path}"],
            )
        for parent_role, identity in parent_identities.items():
            if not isinstance(identity, Mapping) or not isinstance(
                identity.get("path"), str
            ):
                raise T075WorkflowError(
                    "terminal-finalize",
                    [f"retention parent identity is invalid: {path}"],
                )
            parent_path = _portable_path(identity["path"])
            if not parent_path.is_file() and not Path(identity["path"]).is_absolute():
                parent_path = artifact_root / identity["path"]
            if not _t075_identity_matches(identity, parent_path):
                raise T075WorkflowError(
                    "terminal-finalize",
                    [f"retention parent {parent_role!r} is invalid: {path}"],
                )

    commands: dict[str, Any] = {}
    evidence: dict[str, Any] = {}
    reused: list[dict[str, Any]] = []
    for path in sorted(artifact_root.rglob("*.retention.json")):
        if path == artifact_root / "t075-retention-manifest.json":
            continue
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise T075WorkflowError(
                "terminal-finalize", [f"retention is unreadable: {path}: {exc}"]
            ) from exc
        if not isinstance(value, Mapping):
            raise T075WorkflowError(
                "terminal-finalize", [f"retention is not an object: {path}"]
            )
        if value.get("schema_id") != T075_RETENTION_MANIFEST_SCHEMA_ID:
            continue
        if (
            value.get("schema_version") != 1
            or value.get("task_id") != T075_TASK_ID
            or value.get("approved_t075_spec_commit") != T075_APPROVED_SPEC_COMMIT
            or value.get("planner_baseline") != T075_PLANNER_BASELINE
        ):
            raise T075WorkflowError(
                "terminal-finalize", [f"retention identity is invalid: {path}"]
            )
        raw_commands = value.get("stage_commands")
        raw_evidence = value.get("stage_evidence")
        if not isinstance(raw_commands, Mapping) or not isinstance(
            raw_evidence, Mapping
        ):
            raise T075WorkflowError(
                "terminal-finalize", [f"retention has incomplete stage lineage: {path}"]
            )
        for stage, command in raw_commands.items():
            if stage not in T075_STAGE_ORDER[:-1] or stage in commands:
                raise T075WorkflowError(
                    "terminal-finalize",
                    [f"duplicate/unknown stage command {stage!r}: {path}"],
                )
            if not isinstance(command, Mapping):
                raise T075WorkflowError(
                    "terminal-finalize", [f"stage command is not an object: {path}"]
                )
            stage_name = str(stage)
            stage_evidence = raw_evidence.get(stage_name)
            if not isinstance(stage_evidence, Mapping):
                raise T075WorkflowError(
                    "terminal-finalize", [f"stage evidence is missing: {path}"]
                )
            validate_stage_entry(path, stage_name, command, stage_evidence)
            commands[stage_name] = dict(command)
        for stage, stage_value in raw_evidence.items():
            if stage not in T075_STAGE_ORDER[:-1] or stage in evidence:
                raise T075WorkflowError(
                    "terminal-finalize",
                    [f"duplicate/unknown stage evidence {stage!r}: {path}"],
                )
            if not isinstance(stage_value, Mapping):
                raise T075WorkflowError(
                    "terminal-finalize", [f"stage evidence is not an object: {path}"]
                )
            evidence[str(stage)] = dict(stage_value)
        for entry in value.get("reused_artifacts", ()):
            if isinstance(entry, Mapping):
                reused.append(dict(entry))

    skipped_stages = decision.get("skipped_stages", ())
    if not isinstance(skipped_stages, list):
        raise T075WorkflowError(
            "terminal-finalize", ["decision skipped stages are not a list"]
        )
    stale_skipped = sorted(
        stage for stage in skipped_stages if stage in commands or stage in evidence
    )
    if stale_skipped:
        raise T075WorkflowError(
            "terminal-finalize",
            [
                "retention exists for decision-skipped stage(s): "
                + ", ".join(stale_skipped)
            ],
        )

    reached = tuple(decision.get("reached_stages", ()))
    terminal_stage = decision.get("terminal_stage")
    for stage in reached:
        if stage not in T075_STAGE_ORDER[:-1]:
            raise T075WorkflowError(
                "terminal-finalize", [f"decision reached unknown stage {stage!r}"]
            )
        command = commands.get(stage)
        stage_value = evidence.get(stage)
        if not isinstance(command, Mapping) or not isinstance(stage_value, Mapping):
            raise T075WorkflowError(
                "terminal-finalize", [f"completed retention for {stage} is missing"]
            )
        failed_terminal_stage = (
            decision.get("terminal_case") == "D"
            and stage == terminal_stage
            and command.get("status") == "failed"
            and stage_value.get("status") == "failed"
        )
        if (
            decision.get("terminal_case") == "D"
            and stage == terminal_stage
            and not (
                failed_terminal_stage
                and command.get("terminal") is False
                and stage_value.get("terminal") is False
                and command.get("exit_code") not in (None, 0)
            )
        ):
            raise T075WorkflowError(
                "terminal-finalize",
                [f"Case D terminal retention is not a failed stage: {path}"],
            )
        if (
            command.get("executed") is not True
            or stage_value.get("executed") is not True
        ):
            raise T075WorkflowError(
                "terminal-finalize", [f"retention for {stage} is not executed"]
            )
        if not failed_terminal_stage and (
            command.get("status") != "completed"
            or stage_value.get("status") != "completed"
        ):
            raise T075WorkflowError(
                "terminal-finalize", [f"retention for {stage} is not completed"]
            )
        if not failed_terminal_stage and (
            command.get("terminal") is not True
            or stage_value.get("terminal") is not True
        ):
            raise T075WorkflowError(
                "terminal-finalize", [f"retention for {stage} is not terminal"]
            )
        if not command.get("output_identities") or not stage_value.get(
            "output_identities"
        ):
            raise T075WorkflowError(
                "terminal-finalize", [f"retention for {stage} has no outputs"]
            )
    return commands, evidence, reused


def _t075_require_parent_retention(
    path: Path, *, stage: str, required_paths: Mapping[str, Path]
) -> dict[str, Any]:
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise T075WorkflowError(
            "lineage", [f"parent retention is unreadable: {path}: {exc}"]
        ) from exc
    if (
        not isinstance(manifest, Mapping)
        or manifest.get("schema_id") != T075_RETENTION_MANIFEST_SCHEMA_ID
        or manifest.get("schema_version") != 1
        or manifest.get("task_id") != T075_TASK_ID
        or manifest.get("approved_t075_spec_commit") != T075_APPROVED_SPEC_COMMIT
        or manifest.get("planner_baseline") != T075_PLANNER_BASELINE
    ):
        raise T075WorkflowError(
            "lineage", [f"parent retention schema is invalid: {path}"]
        )
    evidence = manifest.get("stage_evidence", {}).get(stage)
    if (
        not isinstance(evidence, Mapping)
        or evidence.get("status") != "completed"
        or evidence.get("terminal") is not True
    ):
        raise T075WorkflowError(
            "lineage", [f"parent retention does not contain completed {stage}: {path}"]
        )
    if (
        not _t075_command_matches_contract(evidence.get("command"), stage)
        or evidence.get("executed") is not True
        or evidence.get("exit_code") != 0
        or evidence.get("code_head")
        != _code_head_for_artifact_root(argparse.Namespace())
    ):
        raise T075WorkflowError(
            "lineage", [f"parent retention execution evidence is invalid: {path}"]
        )
    start = _t075_parse_utc_timestamp(evidence.get("start_time_utc"))
    end = _t075_parse_utc_timestamp(evidence.get("end_time_utc"))
    if start is None or end is None or start > end:
        raise T075WorkflowError(
            "lineage", [f"parent retention execution bounds are invalid: {path}"]
        )
    shard_count = evidence.get("shard_count")
    worker_count = evidence.get("worker_count")
    per_shard = evidence.get("per_shard")
    if (
        isinstance(shard_count, bool)
        or not isinstance(shard_count, int)
        or shard_count < 0
        or isinstance(worker_count, bool)
        or not isinstance(worker_count, int)
        or worker_count < 0
        or not isinstance(per_shard, list)
    ):
        raise T075WorkflowError(
            "lineage", [f"parent retention execution counts are invalid: {path}"]
        )
    if shard_count > 0:
        process_ids = []
        for shard in per_shard:
            if (
                not isinstance(shard, Mapping)
                or isinstance(shard.get("process_id"), bool)
                or not isinstance(shard.get("process_id"), int)
                or shard.get("worker_kind") != "spawn-process"
            ):
                raise T075WorkflowError(
                    "lineage", [f"parent retention process evidence is invalid: {path}"]
                )
            process_ids.append(shard["process_id"])
        if len(per_shard) != shard_count or len(set(process_ids)) != len(process_ids):
            raise T075WorkflowError(
                "lineage", [f"parent retention shard evidence is incomplete: {path}"]
            )
    if stage in {"stage1-selection-replay", "stage2-target", "stage6-eval"}:
        _t075_validate_process_shards(
            stage,
            shard_count=shard_count,
            worker_count=worker_count,
            per_shard=per_shard,
            status="completed",
            ranges=evidence.get("ranges"),
        )
    outputs = evidence.get("output_identities", ())
    if not isinstance(outputs, list):
        raise T075WorkflowError(
            "lineage", [f"parent retention outputs are invalid: {path}"]
        )
    for role, required_path in required_paths.items():
        matching = [
            entry
            for entry in outputs
            if isinstance(entry, Mapping)
            and entry.get("role") == role
            and _t075_path_matches(entry.get("path", ""), required_path)
        ]
        if len(matching) != 1 or not _t075_identity_matches(
            matching[0], required_path, expected_role=role
        ):
            raise T075WorkflowError(
                "lineage", [f"parent retention lacks exact {role} identity: {path}"]
            )
    for output in outputs:
        if not isinstance(output, Mapping) or not isinstance(output.get("role"), str):
            raise T075WorkflowError(
                "lineage", [f"parent retention output role is invalid: {path}"]
            )
        output_path = _t075_resolve_lineage_identity_path(
            output, artifact_root=path.parent
        )
        if output_path is None:
            raise T075WorkflowError(
                "lineage", [f"parent retention output identity is invalid: {path}"]
            )
    parent_identities = evidence.get("parent_identities", {})
    if not isinstance(parent_identities, Mapping):
        raise T075WorkflowError(
            "lineage", [f"parent retention parent identities are invalid: {path}"]
        )
    for role, identity in parent_identities.items():
        if not isinstance(identity, Mapping):
            raise T075WorkflowError(
                "lineage", [f"parent identity {role!r} is invalid: {path}"]
            )
        try:
            identity_path = _t075_resolve_lineage_identity_path(
                identity, artifact_root=path.parent
            )
            if identity_path is None:
                raise ValueError("path/hash/size mismatch")
        except (KeyError, OSError, ValueError) as exc:
            raise T075WorkflowError(
                "lineage", [f"parent identity {role!r} is invalid: {path}"]
            ) from exc
    return dict(manifest)


def _write_t075_stage_retention(
    args: argparse.Namespace,
    *,
    stage: str,
    artifacts: Mapping[str, Path],
    evidence: Mapping[str, Any],
    terminal_case: str | None = None,
) -> dict[str, Any]:
    entries = [
        _t075_artifact_identity(path, role=role)
        for role, path in sorted(artifacts.items())
    ]
    if "status" not in evidence or "terminal" not in evidence:
        raise T075WorkflowError(
            "artifact-retention", [f"{stage}: explicit status is required"]
        )
    status = str(evidence["status"])
    if status not in {"completed", "pending", "failed", "skipped"}:
        raise T075WorkflowError(
            "artifact-retention", [f"{stage}: invalid execution status {status!r}"]
        )
    if status in {"completed", "failed"} and not entries:
        raise T075WorkflowError(
            "artifact-retention", [f"{stage}: terminal evidence has no outputs"]
        )
    raw_terminal = evidence["terminal"]
    if not isinstance(raw_terminal, bool):
        raise T075WorkflowError(
            "artifact-retention", [f"{stage}: terminal status is not boolean"]
        )
    terminal = raw_terminal
    problems = list(evidence.get("problems", ()))
    execution_keys = (
        "command",
        "executed",
        "start_time_utc",
        "end_time_utc",
        "exit_code",
        "wall_clock_seconds",
        "shard_count",
        "worker_count",
        "ranges",
        "per_shard",
        "parent_identities",
    )
    if any(key not in evidence for key in execution_keys):
        raise T075WorkflowError(
            "artifact-retention",
            [f"{stage}: caller must provide complete execution evidence"],
        )
    if not isinstance(evidence["command"], str) or not evidence["command"].strip():
        raise T075WorkflowError(
            "artifact-retention", [f"{stage}: exact command is missing"]
        )
    if evidence["command"] != _t075_command_string(args):
        raise T075WorkflowError(
            "artifact-retention", [f"{stage}: command is not the frozen invocation"]
        )
    if not _t075_command_matches_contract(
        evidence["command"], stage, skipped=status == "skipped"
    ):
        raise T075WorkflowError(
            "artifact-retention", [f"{stage}: command does not match frozen argv"]
        )
    if not isinstance(evidence["executed"], bool):
        raise T075WorkflowError(
            "artifact-retention", [f"{stage}: executed flag is invalid"]
        )
    start_time = evidence["start_time_utc"]
    end_time = evidence["end_time_utc"]
    if (
        not isinstance(start_time, str)
        or not start_time.strip()
        or not isinstance(end_time, str)
        or not end_time.strip()
    ):
        raise T075WorkflowError(
            "artifact-retention", [f"{stage}: execution bounds are missing"]
        )
    parsed_start = _t075_parse_utc_timestamp(start_time)
    parsed_end = _t075_parse_utc_timestamp(end_time)
    if parsed_start is None or parsed_end is None or parsed_start > parsed_end:
        raise T075WorkflowError(
            "artifact-retention",
            [f"{stage}: execution bounds must be ordered ISO-UTC timestamps"],
        )
    executed = evidence["executed"]
    raw_exit_code = evidence["exit_code"]
    if (status == "skipped" and executed) or (
        status in {"completed", "failed"} and not executed
    ):
        raise T075WorkflowError(
            "artifact-retention",
            [f"{stage}: execution flag contradicts status"],
        )
    if raw_exit_code is not None and (
        isinstance(raw_exit_code, bool) or not isinstance(raw_exit_code, int)
    ):
        raise T075WorkflowError(
            "artifact-retention", [f"{stage}: exit code is invalid"]
        )
    wall_clock_seconds = evidence["wall_clock_seconds"]
    if (
        isinstance(wall_clock_seconds, bool)
        or not isinstance(wall_clock_seconds, (int, float))
        or not math.isfinite(float(wall_clock_seconds))
        or wall_clock_seconds < 0
    ):
        raise T075WorkflowError(
            "artifact-retention", [f"{stage}: wall-clock evidence is invalid"]
        )
    for field in ("shard_count", "worker_count"):
        value = evidence[field]
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise T075WorkflowError(
                "artifact-retention", [f"{stage}: {field} evidence is invalid"]
            )
    if not isinstance(evidence["ranges"], list) or not isinstance(
        evidence["per_shard"], list
    ):
        raise T075WorkflowError(
            "artifact-retention", [f"{stage}: shard evidence is invalid"]
        )
    if stage in {"stage1-selection-replay", "stage2-target", "stage6-eval"}:
        _t075_validate_process_shards(
            stage,
            shard_count=evidence["shard_count"],
            worker_count=evidence["worker_count"],
            per_shard=evidence["per_shard"],
            status=status,
            ranges=evidence["ranges"],
            allow_partial_failure=evidence.get("partial_spawn_failure") is True,
        )
    if not isinstance(evidence["parent_identities"], Mapping):
        raise T075WorkflowError(
            "artifact-retention", [f"{stage}: parent evidence is invalid"]
        )
    if status == "completed" and not terminal:
        status = "pending"
    if status != "completed":
        terminal = False
    manifest = {
        "schema_id": T075_RETENTION_MANIFEST_SCHEMA_ID,
        "schema_version": 1,
        "task_id": T075_TASK_ID,
        "approved_t075_spec_commit": T075_APPROVED_SPEC_COMMIT,
        "planner_baseline": T075_PLANNER_BASELINE,
        "terminal_case": terminal_case,
        "retention_owner": T075_TASK_ID,
        "retention_reason": "T075 exact stage-local evidence and retained T065 source reuse",
        "reused_artifacts": [
            entry for entry in entries if entry["role"].startswith("source_")
        ],
        "produced_artifacts": entries,
        "stage_commands": {
            stage: {
                "command": evidence["command"],
                "executed": executed,
                "status": status,
                "skip_reason": evidence.get("skip_reason"),
                "code_head": _code_head_for_artifact_root(args),
                "start_time_utc": start_time,
                "end_time_utc": end_time,
                "exit_code": raw_exit_code,
                "terminal": terminal,
                "wall_clock_seconds": float(wall_clock_seconds),
                "shard_count": evidence["shard_count"],
                "worker_count": evidence["worker_count"],
                "ranges": evidence["ranges"],
                "parent_identities": evidence["parent_identities"],
                "output_identities": entries,
            }
        },
        "stage_evidence": {
            stage: {
                **dict(evidence),
                "command": evidence["command"],
                "executed": executed,
                "status": status,
                "terminal": terminal,
                "code_head": _code_head_for_artifact_root(args),
                "start_time_utc": start_time,
                "end_time_utc": end_time,
                "exit_code": raw_exit_code,
                "shard_count": evidence["shard_count"],
                "worker_count": evidence["worker_count"],
                "ranges": evidence["ranges"],
                "per_shard": evidence["per_shard"],
                "artifact_roles": [entry["role"] for entry in entries],
                "output_identities": entries,
                "parent_identities": evidence.get("parent_identities", {}),
                "counts": evidence.get("counts", {}),
                "problems": problems,
            }
        },
        "downstream_consumers": evidence.get("downstream_consumers", []),
        "deletion_condition": "merged T075 terminal report and no open consumer requires retained inputs",
        "problems": problems,
    }
    _write_canonical_json(args.retention_manifest, manifest)
    return manifest


def _code_head_for_artifact_root(args: argparse.Namespace) -> str:
    import subprocess

    worktree = _target_src_path().parent
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], text=True, cwd=worktree
        ).strip()
    except (OSError, subprocess.SubprocessError):
        # A Windows-created linked worktree stores a Windows absolute path in
        # its .git pointer.  WSL's git cannot follow that pointer, so retry
        # read-only with the pointer translated to the mounted path.
        git_pointer = worktree / ".git"
        try:
            pointer = git_pointer.read_text(encoding="utf-8").strip()
            prefix = "gitdir:"
            if not pointer.lower().startswith(prefix):
                return "unknown"
            gitdir_text = pointer[len(prefix) :].strip()
            if not gitdir_text:
                return "unknown"
            gitdir = _wsl_path(Path(gitdir_text))
            worktree_path = _wsl_path(worktree)
            return subprocess.check_output(
                [
                    "git",
                    "--git-dir",
                    gitdir,
                    "--work-tree",
                    worktree_path,
                    "rev-parse",
                    "HEAD",
                ],
                text=True,
            ).strip()
        except (OSError, subprocess.SubprocessError, ValueError):
            return "unknown"


def _portable_path(value: str | Path) -> Path:
    text = str(value).replace("\\", "/")
    if any(part == ".." for part in text.split("/")):
        raise ValueError(f"artifact path contains ..: {value}")
    path = Path(value)
    if path.is_file() or path.exists():
        return path
    if (
        len(text) >= 7
        and text.startswith("/mnt/")
        and text[5].isalpha()
        and text[6] == "/"
    ):
        return Path(text[5].upper() + ":" + text[6:])
    return path


def _t075_normalize_artifact_path(value: str) -> str:
    text = str(value).replace("\\", "/")
    frozen_root_prefix = (
        str(T075_STABLE_ARTIFACT_ROOT).replace("\\", "/").rstrip("/") + "/"
    )
    frozen_root = frozen_root_prefix.rstrip("/")
    if text == frozen_root:
        text = "artifacts/t075-leakage-safe-non-combat-cohort-repair"
    elif text.startswith(frozen_root_prefix):
        text = (
            "artifacts/t075-leakage-safe-non-combat-cohort-repair/"
            + text[len(frozen_root_prefix) :]
        )
    for prefix in (
        "D:/DeadlycatCoding/STSRL/",
        "/mnt/d/DeadlycatCoding/STSRL/",
    ):
        if text.startswith(prefix):
            text = text[len(prefix) :]
            break
    if text.startswith("./"):
        text = text[2:]
    parts = []
    for part in text.split("/"):
        if part in {"", "."}:
            continue
        if part == "..":
            raise ValueError(f"artifact path contains ..: {value}")
        parts.append(part)
    normalized = "/".join(parts)
    if not normalized.startswith("artifacts/"):
        raise ValueError(f"artifact path is not under artifacts/: {value}")
    return normalized


def _t075_artifact_root_matches(path: Any) -> bool:
    if not isinstance(path, Path):
        return False
    try:
        return _t075_normalize_artifact_path(
            str(path)
        ) == _t075_normalize_artifact_path(str(T075_STABLE_ARTIFACT_ROOT))
    except (OSError, TypeError, ValueError):
        return False


def _t075_identity_matches(
    identity: Mapping[str, Any], path: Path, *, expected_role: str | None = None
) -> bool:
    try:
        return (
            (expected_role is None or identity.get("role") == expected_role)
            and _t075_path_matches(str(identity["path"]), path)
            and identity.get("sha256") == file_sha256(path)
            and identity.get("size_bytes") == path.stat().st_size
        )
    except (KeyError, OSError, ValueError):
        return False


def _t075_resolve_lineage_identity_path(
    identity: Mapping[str, Any], *, artifact_root: Path
) -> Path | None:
    """Resolve local outputs or the two explicitly frozen T065 source inputs.

    A T075 retention file is rooted in the T075 stable directory, while its
    Stage-1 output identities legitimately include the retained T065 source
    files from the sibling T065 artifact directory.  The external exception
    is deliberately keyed by the frozen normalized path and frozen digest/
    size; it is not a general external-artifact escape hatch.
    """

    raw_path = identity.get("path")
    if not isinstance(raw_path, str) or not raw_path:
        return None
    local = _t075_resolve_identity_path(raw_path, artifact_root=artifact_root)
    if local is not None and _t075_identity_matches(identity, local):
        return local
    try:
        normalized = _t075_normalize_artifact_path(raw_path)
    except (OSError, TypeError, ValueError):
        return None
    frozen = T075_FROZEN_SOURCE_ARTIFACTS.get(normalized)
    if not isinstance(frozen, Mapping):
        return None
    expected_role = {
        "stochastic_non_combat_v1": "source_stochastic",
        "expert_non_combat_v1": "source_expert",
    }.get(str(frozen.get("arm")))
    if identity.get("role") != expected_role:
        return None
    if identity.get("sha256") != frozen.get("sha256") or identity.get(
        "size_bytes"
    ) != frozen.get("size_bytes"):
        return None
    # The optional actual_path exists only for bounded fixture tests.  The
    # production mapping resolves to the immutable stable artifact location.
    actual_path_value = frozen.get("actual_path")
    actual_path = (
        Path(actual_path_value)
        if isinstance(actual_path_value, str)
        else _portable_path(f"/mnt/d/DeadlycatCoding/STSRL/{normalized}")
    )
    try:
        if (
            not actual_path.is_file()
            or file_sha256(actual_path) != frozen.get("sha256")
            or actual_path.stat().st_size != frozen.get("size_bytes")
        ):
            return None
    except OSError:
        return None
    return actual_path


def _t075_find_source_retention(source_path: Path) -> tuple[Path, dict[str, Any]]:
    matches: list[tuple[Path, dict[str, Any]]] = []
    for manifest_path in sorted(source_path.parent.glob("*.retention.json")):
        try:
            manifest = _read_retention_manifest(manifest_path)
        except ValueError:
            continue
        artifacts = manifest.get("artifacts", [])
        current = [
            entry
            for entry in artifacts
            if isinstance(entry, Mapping) and entry.get("role") == "current_output"
        ]
        if len(current) == 1 and _t075_identity_matches(
            current[0], source_path, expected_role="current_output"
        ):
            matches.append((manifest_path, manifest))
    if len(matches) != 1:
        raise T075WorkflowError(
            "source-input-reuse",
            [
                f"{source_path}: expected exactly one direct source retention root, "
                f"found {len(matches)}"
            ],
        )
    return matches[0]


def _t075_validate_accepted_case_d_files(
    decision_path: Path, retention_path: Path
) -> None:
    """Revalidate the immutable T065 Case-D pair before reuse is accepted."""

    if (
        _t075_normalize_artifact_path(str(decision_path))
        != T075_ACCEPTED_T065_CASE_D["path"]
        or _t075_normalize_artifact_path(str(retention_path))
        != T075_ACCEPTED_T065_CASE_D_RETENTION["path"]
        or not decision_path.is_file()
        or not retention_path.is_file()
        or decision_path.stat().st_size != T075_ACCEPTED_T065_CASE_D["size_bytes"]
        or retention_path.stat().st_size
        != T075_ACCEPTED_T065_CASE_D_RETENTION["size_bytes"]
        or file_sha256(decision_path) != T075_ACCEPTED_T065_CASE_D["sha256"]
        or file_sha256(retention_path) != T075_ACCEPTED_T065_CASE_D_RETENTION["sha256"]
    ):
        raise T075WorkflowError(
            "source-input-reuse", ["accepted T065 Case-D files are stale or missing"]
        )
    try:
        decision = json.loads(decision_path.read_text(encoding="utf-8"))
        retention = json.loads(retention_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise T075WorkflowError(
            "source-input-reuse",
            [f"accepted T065 Case-D evidence is unreadable: {exc}"],
        ) from exc
    if (
        not isinstance(decision, Mapping)
        or decision.get("schema_id") != "t065-terminal-decision-report-v1"
        or decision.get("schema_version") != 1
        or decision.get("task_id") != "T065"
        or decision.get("approved_spec_commit") != T065_APPROVED_SPEC_COMMIT
        or decision.get("case") != "D"
        or decision.get("stage") != "source-selection"
        or not isinstance(retention, Mapping)
        or retention.get("schema_id") != "t065-retention-manifest-v1"
        or retention.get("schema_version") != 1
        or retention.get("task_id") != "T065"
        or retention.get("approved_spec_commit") != T065_APPROVED_SPEC_COMMIT
        or retention.get("experiment_schema_id") != T065_EXPERIMENT_SCHEMA_ID
        or retention.get("frozen_config") != T065ExperimentConfig().to_dict()
        or retention.get("simulator_identity") != lightspeed_source_identity_dict()
    ):
        raise T075WorkflowError(
            "source-input-reuse", ["accepted T065 Case-D content is not frozen"]
        )
    artifacts = retention.get("artifacts")
    matching = (
        [
            entry
            for entry in artifacts
            if isinstance(entry, Mapping)
            and entry.get("role") == "terminal_decision_report"
        ]
        if isinstance(artifacts, list)
        else []
    )
    if len(matching) != 1 or not _t075_identity_matches(
        matching[0], decision_path, expected_role="terminal_decision_report"
    ):
        raise T075WorkflowError(
            "source-input-reuse", ["accepted T065 retention lacks the Case-D output"]
        )
    evidence = retention.get("stage_evidence", {}).get("source-selection")
    if (
        not isinstance(evidence, Mapping)
        or evidence.get("stage") != "source-selection"
        or evidence.get("status") != "case_d"
        or evidence.get("terminal") is not True
        or evidence.get("terminal_case") != "D"
    ):
        raise T075WorkflowError(
            "source-input-reuse", ["accepted T065 retention Case-D evidence is invalid"]
        )


def _t075_validate_source_retention(
    source_path: Path,
    *,
    expected_arm: str,
    preflight_retention: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    try:
        frozen_identity = T075_FROZEN_SOURCE_ARTIFACTS[
            _t075_normalize_artifact_path(str(source_path))
        ]
    except (KeyError, ValueError) as exc:
        raise T075WorkflowError(
            "source-input-reuse",
            [f"source path is not a frozen T065 input: {source_path}"],
        ) from exc
    if (
        frozen_identity["arm"] != expected_arm
        or not source_path.is_file()
        or file_sha256(source_path) != frozen_identity["sha256"]
        or source_path.stat().st_size != frozen_identity["size_bytes"]
    ):
        raise T075WorkflowError(
            "source-input-reuse",
            [f"source identity is not the frozen T065 input: {source_path}"],
        )
    retention_path, retention = _t075_find_source_retention(source_path)
    evidence = retention.get("stage_evidence", {}).get("stage1-source-collection")
    if (
        not isinstance(evidence, Mapping)
        or evidence.get("stage") != "stage1-source-collection"
        or evidence.get("status") != "completed"
        or evidence.get("terminal") is not False
        or "current_output" not in evidence.get("artifact_roles", [])
    ):
        raise T075WorkflowError(
            "source-input-reuse", [f"{retention_path}: Stage 1 evidence is invalid"]
        )
    preceding = evidence.get("preceding_stage_manifests")
    preflight_descriptor = (
        preceding.get("stage0_preflight") if isinstance(preceding, Mapping) else None
    )
    preflight_manifest = _read_retention_manifest(preflight_retention)
    if not isinstance(preflight_descriptor, Mapping):
        raise T075WorkflowError(
            "source-input-reuse",
            [f"{retention_path}: source preflight lineage is missing"],
        )
    if (
        _t075_normalize_artifact_path(str(preflight_descriptor.get("path", "")))
        != _t075_normalize_artifact_path(str(preflight_retention))
        or preflight_descriptor.get("sha256") != file_sha256(preflight_retention)
        or preflight_descriptor.get("size_bytes") != preflight_retention.stat().st_size
    ):
        raise T075WorkflowError(
            "source-input-reuse",
            [f"{retention_path}: source preflight lineage does not match alias"],
        )
    commands = retention.get("regeneration_commands")
    if (
        not isinstance(commands, list)
        or len(commands) != 1
        or not isinstance(commands[0], str)
        or not commands[0].strip()
        or commands[0] != evidence.get("command")
    ):
        raise T075WorkflowError(
            "source-input-reuse",
            [f"{retention_path}: regeneration command lineage is invalid"],
        )
    if (
        retention.get("frozen_config") != T065ExperimentConfig().to_dict()
        or retention.get("simulator_identity") != lightspeed_source_identity_dict()
    ):
        raise T075WorkflowError(
            "source-input-reuse",
            [f"{retention_path}: retained T065 identity is not frozen"],
        )
    reader = _SourceArmArtifactReader(source_path)
    for _state in reader.iter_states():
        pass
    actual_arm = _validate_source_arm_metadata(
        reader.metadata, source_path, record_count=reader.record_count
    )
    if actual_arm != expected_arm:
        raise T075WorkflowError(
            "source-input-reuse",
            [f"{source_path}: expected {expected_arm}, got {actual_arm}"],
        )
    return (
        {
            "arm": actual_arm,
            "path": str(source_path),
            "sha256": file_sha256(source_path),
            "size_bytes": source_path.stat().st_size,
            "record_count": reader.record_count,
            "retention_manifest": {
                "path": str(retention_path),
                "sha256": file_sha256(retention_path),
                "size_bytes": retention_path.stat().st_size,
            },
            "raw_metadata": {
                "schema_id": reader.metadata.get("schema_id"),
                "schema_version": reader.metadata.get("schema_version"),
                "arm": actual_arm,
                "selected_candidate_count": reader.record_count,
                "terminal_run_count": reader.metadata.get("terminal_run_count"),
            },
            "stage1_evidence": dict(evidence),
            "preflight_retention": {
                "path": str(preflight_retention),
                "sha256": file_sha256(preflight_retention),
                "size_bytes": preflight_retention.stat().st_size,
            },
            "regeneration_command": commands[0],
        },
        {
            "path": str(retention_path),
            "manifest": retention,
            "preflight": preflight_manifest,
        },
    )


def _t075_validate_preflight_alias(path: Path, expected_sha256: str) -> dict[str, Any]:
    if not path.is_file() or file_sha256(path) != expected_sha256:
        raise T075WorkflowError(
            "source-input-reuse",
            [f"preflight alias is missing or hash-invalid: {path}"],
        )
    try:
        return validate_t065_preflight(path)
    except T065CaseD as exc:
        raise T075WorkflowError("source-input-reuse", list(exc.problems)) from exc


def _t075_validate_alias_retention(path: Path, raw_path: Path) -> dict[str, Any]:
    manifest = _read_retention_manifest(path)
    artifacts = manifest.get("artifacts", [])
    if not any(
        isinstance(entry, Mapping)
        and entry.get("role") == "current_output"
        and _t075_identity_matches(entry, raw_path, expected_role="current_output")
        for entry in artifacts
    ):
        raise T075WorkflowError(
            "source-input-reuse",
            [f"{path}: retention does not reference raw preflight alias"],
        )
    return manifest


def _t075_resolve_reuse_manifest(
    path: Path, source_paths: Sequence[Path]
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Re-resolve the frozen source roots instead of trusting a JSON copy."""

    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise T075WorkflowError(
            "source-input-reuse", [f"reuse manifest is unreadable: {path}: {exc}"]
        ) from exc
    required = (
        "schema_id",
        "schema_version",
        "task_id",
        "approved_t075_spec_commit",
        "planner_baseline",
        "code_head",
        "pinned_simulator_identity",
        "accepted_t065_preflight_content_sha256",
        "accepted_t065_case_d",
        "sources",
        "validation",
        "original_regeneration_commands",
        "problems",
    )
    if (
        not isinstance(value, Mapping)
        or any(key not in value for key in required)
        or value.get("schema_id") != T075_REUSE_MANIFEST_SCHEMA_ID
        or value.get("schema_version") != 1
        or value.get("task_id") != T075_TASK_ID
        or value.get("approved_t075_spec_commit") != T075_APPROVED_SPEC_COMMIT
        or value.get("planner_baseline") != T075_PLANNER_BASELINE
        or value.get("code_head") != _code_head_for_artifact_root(argparse.Namespace())
        or value.get("pinned_simulator_identity") != lightspeed_source_identity_dict()
        or value.get("accepted_t065_preflight_content_sha256")
        != "a89560d037ea4555922d0e1282edb8e328ce75ab6e1d720fd05f86022b56c334"
        or value.get("problems") != []
    ):
        raise T075WorkflowError(
            "source-input-reuse", [f"reuse manifest is not the frozen schema: {path}"]
        )
    accepted_case_d = value["accepted_t065_case_d"]
    if (
        not isinstance(accepted_case_d, Mapping)
        or _t075_normalize_artifact_path(str(accepted_case_d.get("path", "")))
        != T075_ACCEPTED_T065_CASE_D["path"]
        or accepted_case_d.get("sha256") != T075_ACCEPTED_T065_CASE_D["sha256"]
        or accepted_case_d.get("size_bytes") != T075_ACCEPTED_T065_CASE_D["size_bytes"]
    ):
        raise T075WorkflowError(
            "source-input-reuse",
            [f"reuse accepted Case-D identity is not frozen: {path}"],
        )
    accepted_case_d_path = _t075_resolve_identity_path(str(accepted_case_d["path"]))
    if accepted_case_d_path is None:
        raise T075WorkflowError(
            "source-input-reuse", ["accepted T065 Case-D decision is missing"]
        )
    accepted_retention_name = Path(
        _portable_path(T075_ACCEPTED_T065_CASE_D_RETENTION["path"])
    ).name
    accepted_retention_path = accepted_case_d_path.parent / accepted_retention_name
    _t075_validate_accepted_case_d_files(accepted_case_d_path, accepted_retention_path)
    validation = value["validation"]
    if (
        not isinstance(validation, Mapping)
        or validation.get("status") != "passed"
        or validation.get("raw_metadata_validated") is not True
        or validation.get("source_count") != 2
        or validation.get("source_arms")
        != ["stochastic_non_combat_v1", "expert_non_combat_v1"]
        or validation.get("source_recollection_prohibited") is not True
    ):
        raise T075WorkflowError(
            "source-input-reuse", [f"reuse validation gate is not strict: {path}"]
        )
    if len(source_paths) != 2:
        raise T075WorkflowError(
            "source-input-reuse", ["T075 selection requires exactly two sources"]
        )
    source_by_normalized = {}
    for source_path in source_paths:
        try:
            normalized = _t075_normalize_artifact_path(str(source_path))
            identity = T075_FROZEN_SOURCE_ARTIFACTS[normalized]
        except (KeyError, ValueError) as exc:
            raise T075WorkflowError(
                "source-input-reuse",
                [f"source is not an exact frozen input: {source_path}"],
            ) from exc
        if normalized in source_by_normalized:
            raise T075WorkflowError(
                "source-input-reuse", [f"duplicate frozen source: {source_path}"]
            )
        source_by_normalized[normalized] = (source_path, identity)
    sources = value["sources"]
    expected_order = tuple(
        sorted(
            T075_FROZEN_SOURCE_ARTIFACTS,
            key=lambda item: ("stochastic" not in item, item),
        )
    )
    if not isinstance(sources, list) or len(sources) != 2:
        raise T075WorkflowError(
            "source-input-reuse", [f"reuse source list is incomplete: {path}"]
        )
    resolved_entries: list[dict[str, Any]] = []
    for entry, normalized in zip(sources, expected_order, strict=True):
        source_path, frozen_identity = source_by_normalized.get(
            normalized, (None, None)
        )
        if source_path is None or not isinstance(entry, Mapping):
            raise T075WorkflowError(
                "source-input-reuse",
                [f"reuse source order/identity is invalid: {path}"],
            )
        expected_arm = str(frozen_identity["arm"])
        if (
            _t075_normalize_artifact_path(str(entry.get("path", ""))) != normalized
            or entry.get("arm") != expected_arm
            or entry.get("sha256") != frozen_identity["sha256"]
            or entry.get("size_bytes") != frozen_identity["size_bytes"]
            or not source_path.is_file()
            or file_sha256(source_path) != frozen_identity["sha256"]
            or source_path.stat().st_size != frozen_identity["size_bytes"]
        ):
            raise T075WorkflowError(
                "source-input-reuse", [f"reuse source identity is stale: {source_path}"]
            )
        raw_preflight = entry.get("preflight_raw")
        retention_preflight = entry.get("preflight_retention")
        if not isinstance(raw_preflight, Mapping) or not isinstance(
            retention_preflight, Mapping
        ):
            raise T075WorkflowError(
                "source-input-reuse",
                [f"reuse preflight lineage is incomplete: {source_path}"],
            )
        try:
            raw_path = _portable_path(str(raw_preflight["path"]))
            retention_path = _portable_path(str(retention_preflight["path"]))
            raw_key = _t075_normalize_artifact_path(str(raw_path))
            retention_key = _t075_normalize_artifact_path(str(retention_path))
        except (KeyError, OSError, ValueError) as exc:
            raise T075WorkflowError(
                "source-input-reuse",
                [f"reuse preflight path is invalid: {source_path}"],
            ) from exc
        if (
            T075_ACCEPTED_PREFLIGHT_ALIASES.get(raw_key) != expected_arm
            or T075_ACCEPTED_PREFLIGHT_RETENTION_ALIASES.get(retention_key)
            != expected_arm
            or raw_preflight.get("sha256")
            != "a89560d037ea4555922d0e1282edb8e328ce75ab6e1d720fd05f86022b56c334"
            or raw_preflight.get("sha256") != file_sha256(raw_path)
            or raw_preflight.get("size_bytes") != raw_path.stat().st_size
            or retention_preflight.get("sha256") != file_sha256(retention_path)
            or retention_preflight.get("size_bytes") != retention_path.stat().st_size
        ):
            raise T075WorkflowError(
                "source-input-reuse",
                [f"reuse preflight identity is stale: {source_path}"],
            )
        preflight_report = _t075_validate_preflight_alias(
            raw_path,
            "a89560d037ea4555922d0e1282edb8e328ce75ab6e1d720fd05f86022b56c334",
        )
        if (
            preflight_report.get("simulator_identity")
            != lightspeed_source_identity_dict()
            or preflight_report.get("action_space") != frozen_action_space().to_dict()
            or preflight_report.get("battle_controller_name")
            != frozen_battle_provenance()["name"]
        ):
            raise T075WorkflowError(
                "source-input-reuse",
                [f"reuse preflight identity is not frozen: {raw_path}"],
            )
        _t075_validate_alias_retention(retention_path, raw_path)
        resolved, context = _t075_validate_source_retention(
            source_path,
            expected_arm=expected_arm,
            preflight_retention=retention_path,
        )
        entry_retention = entry.get("retention_manifest")
        if not isinstance(entry_retention, Mapping) or (
            _t075_normalize_artifact_path(str(entry_retention.get("path", "")))
            != _t075_normalize_artifact_path(str(context["path"]))
            or entry_retention.get("sha256") != file_sha256(Path(context["path"]))
            or entry_retention.get("size_bytes") != Path(context["path"]).stat().st_size
        ):
            raise T075WorkflowError(
                "source-input-reuse",
                [f"reuse source retention identity is stale: {source_path}"],
            )
        if any(
            entry.get(key) != resolved.get(key)
            for key in (
                "arm",
                "path",
                "sha256",
                "size_bytes",
                "record_count",
                "raw_metadata",
                "stage1_evidence",
                "regeneration_command",
            )
        ):
            raise T075WorkflowError(
                "source-input-reuse", [f"reuse source evidence is stale: {source_path}"]
            )
        resolved_entries.append(dict(entry))
    commands = value["original_regeneration_commands"]
    if (
        not isinstance(commands, list)
        or len(commands) != 2
        or commands != [entry.get("regeneration_command") for entry in resolved_entries]
        or any(
            not isinstance(command, str) or not command.strip() for command in commands
        )
    ):
        raise T075WorkflowError(
            "source-input-reuse", [f"reuse regeneration prohibition is invalid: {path}"]
        )
    return dict(value), resolved_entries


def _run_t075_validate_reuse(args: argparse.Namespace) -> int:
    if (
        args.accepted_preflight_content_sha256
        != "a89560d037ea4555922d0e1282edb8e328ce75ab6e1d720fd05f86022b56c334"
    ):
        raise T075WorkflowError(
            "source-input-reuse", ["accepted T065 preflight content hash is not frozen"]
        )
    sources = tuple(_portable_path(path) for path in (args.source or ()))
    if len(sources) != 2:
        raise T075WorkflowError(
            "source-input-reuse", ["T075 requires exactly two retained source arms"]
        )
    raw_aliases = tuple(
        _portable_path(path) for path in (args.source_preflight_alias or ())
    )
    retention_aliases = tuple(
        _portable_path(path) for path in (args.source_preflight_retention_alias or ())
    )
    if len(raw_aliases) != 2 or len(retention_aliases) != 2:
        raise T075WorkflowError(
            "source-input-reuse",
            ["T075 requires two source-specific preflight aliases and retentions"],
        )
    raw_alias_by_arm: dict[str, Path] = {}
    for path in raw_aliases:
        try:
            arm = T075_ACCEPTED_PREFLIGHT_ALIASES[
                _t075_normalize_artifact_path(str(path))
            ]
        except (KeyError, ValueError) as exc:
            raise T075WorkflowError(
                "source-input-reuse", [f"preflight alias is not frozen: {path}"]
            ) from exc
        if arm in raw_alias_by_arm:
            raise T075WorkflowError(
                "source-input-reuse", [f"duplicate preflight alias for {arm}"]
            )
        raw_alias_by_arm[arm] = path
    retention_alias_by_arm: dict[str, Path] = {}
    for path in retention_aliases:
        try:
            arm = T075_ACCEPTED_PREFLIGHT_RETENTION_ALIASES[
                _t075_normalize_artifact_path(str(path))
            ]
        except (KeyError, ValueError) as exc:
            raise T075WorkflowError(
                "source-input-reuse",
                [f"preflight retention alias is not frozen: {path}"],
            ) from exc
        if arm in retention_alias_by_arm:
            raise T075WorkflowError(
                "source-input-reuse", [f"duplicate preflight retention for {arm}"]
            )
        retention_alias_by_arm[arm] = path
    source_entries: list[dict[str, Any]] = []
    for source in sources:
        try:
            frozen_identity = T075_FROZEN_SOURCE_ARTIFACTS[
                _t075_normalize_artifact_path(str(source))
            ]
        except (KeyError, ValueError) as exc:
            raise T075WorkflowError(
                "source-input-reuse", [f"source is not an exact frozen input: {source}"]
            ) from exc
        expected_arm = str(frozen_identity["arm"])
        preflight = raw_alias_by_arm.get(expected_arm)
        preflight_retention = retention_alias_by_arm.get(expected_arm)
        if preflight is None or preflight_retention is None:
            raise T075WorkflowError(
                "source-input-reuse", [f"missing preflight alias for {expected_arm}"]
            )
        preflight_report = _t075_validate_preflight_alias(
            preflight,
            "a89560d037ea4555922d0e1282edb8e328ce75ab6e1d720fd05f86022b56c334",
        )
        if (
            preflight_report.get("simulator_identity")
            != lightspeed_source_identity_dict()
            or preflight_report.get("action_space") != frozen_action_space().to_dict()
            or preflight_report.get("battle_controller_name")
            != frozen_battle_provenance()["name"]
        ):
            raise T075WorkflowError(
                "source-input-reuse",
                [f"preflight alias identity is not frozen: {preflight}"],
            )
        _t075_validate_alias_retention(preflight_retention, preflight)
        entry, retention_context = _t075_validate_source_retention(
            source, expected_arm=expected_arm, preflight_retention=preflight_retention
        )
        entry["preflight_raw"] = {
            "path": str(preflight),
            "sha256": file_sha256(preflight),
            "size_bytes": preflight.stat().st_size,
        }
        entry["preflight_retention"] = {
            "path": str(preflight_retention),
            "sha256": file_sha256(preflight_retention),
            "size_bytes": preflight_retention.stat().st_size,
        }
        entry["retention_validation"] = {
            "schema_id": retention_context["manifest"].get("schema_id"),
            "stage": "stage1-source-collection",
            "status": "completed",
            "terminal": False,
        }
        source_entries.append(entry)
    source_entries.sort(
        key=lambda entry: ("stochastic" not in entry["arm"], entry["arm"])
    )
    case_d_path = _portable_path(args.accepted_case_d)
    case_d_retention_path = _portable_path(args.accepted_case_d_retention)
    if (
        _t075_normalize_artifact_path(str(case_d_path))
        != T075_ACCEPTED_T065_CASE_D["path"]
        or _t075_normalize_artifact_path(str(case_d_retention_path))
        != T075_ACCEPTED_T065_CASE_D_RETENTION["path"]
        or not case_d_path.is_file()
        or not case_d_retention_path.is_file()
        or case_d_path.stat().st_size != T075_ACCEPTED_T065_CASE_D["size_bytes"]
        or case_d_retention_path.stat().st_size
        != T075_ACCEPTED_T065_CASE_D_RETENTION["size_bytes"]
    ):
        raise T075WorkflowError(
            "source-input-reuse", ["accepted T065 Case-D evidence is missing"]
        )
    if file_sha256(case_d_path) != T075_ACCEPTED_T065_CASE_D["sha256"]:
        raise T075WorkflowError(
            "source-input-reuse", ["accepted T065 Case-D decision hash is invalid"]
        )
    if (
        file_sha256(case_d_retention_path)
        != T075_ACCEPTED_T065_CASE_D_RETENTION["sha256"]
    ):
        raise T075WorkflowError(
            "source-input-reuse", ["accepted T065 Case-D retention hash is invalid"]
        )
    _t075_validate_accepted_case_d_files(case_d_path, case_d_retention_path)
    decision = json.loads(case_d_path.read_text(encoding="utf-8"))
    try:
        case_d_retention = json.loads(case_d_retention_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise T075WorkflowError(
            "source-input-reuse", ["accepted T065 retention is unreadable"]
        ) from exc
    if (
        not isinstance(decision, Mapping)
        or decision.get("case") != "D"
        or not isinstance(case_d_retention, Mapping)
        or case_d_retention.get("schema_id") != "t065-retention-manifest-v1"
        or case_d_retention.get("task_id") != "T065"
    ):
        raise T075WorkflowError(
            "source-input-reuse", ["accepted T065 evidence is not Case D"]
        )
    reuse = {
        "schema_id": T075_REUSE_MANIFEST_SCHEMA_ID,
        "schema_version": 1,
        "task_id": T075_TASK_ID,
        "approved_t075_spec_commit": T075_APPROVED_SPEC_COMMIT,
        "planner_baseline": T075_PLANNER_BASELINE,
        "code_head": _code_head_for_artifact_root(args),
        "pinned_simulator_identity": lightspeed_source_identity_dict(),
        "accepted_t065_preflight_content_sha256": args.accepted_preflight_content_sha256,
        "accepted_t065_case_d": {
            "path": str(case_d_path),
            "sha256": file_sha256(case_d_path),
            "size_bytes": case_d_path.stat().st_size,
        },
        "sources": source_entries,
        "validation": {
            "status": "passed",
            "raw_metadata_validated": True,
            "source_count": len(source_entries),
            "source_arms": [entry["arm"] for entry in source_entries],
            "source_recollection_prohibited": True,
        },
        "original_regeneration_commands": [
            entry["regeneration_command"] for entry in source_entries
        ],
        "problems": [],
    }
    _write_canonical_json(args.output, reuse)
    args.retention_manifest = _portable_path(args.retention_manifest)
    _write_t075_stage_retention(
        args,
        stage="stage0-reuse",
        artifacts={
            "reuse_manifest": args.output,
            "source_stochastic": _portable_path(source_entries[0]["path"]),
            "source_expert": _portable_path(source_entries[1]["path"]),
        },
        evidence={
            **_t075_execution_evidence(
                args, status="completed", terminal=True, exit_code=0, executed=True
            ),
            "status": "completed",
            "terminal": True,
            "counts": {"sources": 2},
            "shard_count": 0,
            "worker_count": 0,
            "ranges": [],
            "per_shard": [],
            "parent_identities": {},
        },
    )
    print(f"T075 retained-source reuse passed: {args.output}", file=sys.stderr)
    return 0


def _t075_parent_identity(path: Path) -> dict[str, Any]:
    return {
        "path": str(path),
        "sha256": file_sha256(path),
        "size_bytes": path.stat().st_size,
    }


def _t075_optional_file_sha256(path: Path) -> str | None:
    return file_sha256(path) if path.is_file() else None


def _t075_preceding_manifest_path(args: argparse.Namespace, *, stage: str) -> Path:
    """Normalize the repeatable CLI option to one T075 parent manifest."""
    raw = getattr(args, "preceding_manifest", None)
    paths = (raw,) if isinstance(raw, (Path, str)) else tuple(raw or ())
    if len(paths) != 1 or not isinstance(paths[0], (Path, str)):
        raise T075WorkflowError(
            stage, ["T075 requires exactly one --preceding-manifest path"]
        )
    return Path(paths[0])


def _run_t075_select(args: argparse.Namespace) -> int:
    """Run T075 ownership, quota selection, and the mandatory replay gate."""

    if _t075_has_terminal_decision(args):
        print(
            "T075 terminal decision already exists; selection is skipped",
            file=sys.stderr,
        )
        return 0
    if args.selection_strategy != T075_SELECTION_STRATEGY_ID:
        raise T075WorkflowError(
            "stage1-selection-replay", ["selection strategy is not frozen"]
        )
    if (
        not args.replay_verify
        or args.replay_shard_count != 16
        or args.replay_worker_count != 16
    ):
        raise T075WorkflowError(
            "stage1-selection-replay",
            ["T075 replay verification requires the frozen 16 shards and workers"],
        )
    if not args.replay_verify:
        raise T075WorkflowError(
            "stage1-selection-replay", ["T075 replay verification is mandatory"]
        )
    reuse_manifest = getattr(args, "reuse_manifest", None)
    if not isinstance(reuse_manifest, Path):
        raise T075WorkflowError(
            "stage0-reuse", ["T075 selection requires the strict reuse resolver"]
        )
    _validate_t075_preflight(args.preflight)
    reuse, source_entries = _t075_resolve_reuse_manifest(reuse_manifest, args.input)
    expected_by_path = {
        _t075_normalize_artifact_path(str(entry.get("path"))): entry
        for entry in source_entries
        if isinstance(entry, Mapping)
    }
    source_artifacts: list[dict[str, Any]] = []
    observed_arms: set[str] = set()

    def candidate_stream() -> Iterator[_SourceSelectionLocator]:
        for source_index, path in enumerate(args.input):
            if not path.is_file():
                raise T075WorkflowError(
                    "stage1-selection-replay", [f"source is missing: {path}"]
                )
            entry = expected_by_path.get(_t075_normalize_artifact_path(str(path)))
            if (
                not isinstance(entry, Mapping)
                or entry.get("sha256") != file_sha256(path)
                or entry.get("size_bytes") != path.stat().st_size
            ):
                raise T075WorkflowError(
                    "stage1-selection-replay",
                    [f"source identity does not match reuse manifest: {path}"],
                )
            reader = _SourceArmArtifactReader(path)
            for record_index, state in enumerate(reader.iter_states()):
                yield _SourceSelectionLocator.from_state(
                    state, source_index=source_index, record_index=record_index
                )
            arm = _validate_source_arm_metadata(
                reader.metadata, path, record_count=reader.record_count
            )
            if arm in observed_arms:
                raise T075WorkflowError(
                    "stage1-selection-replay", [f"duplicate source arm: {arm}"]
                )
            observed_arms.add(arm)
            source_artifacts.append(
                {
                    "arm": arm,
                    "path": str(path),
                    "sha256": file_sha256(path),
                    "size_bytes": path.stat().st_size,
                    "record_count": reader.record_count,
                    "retention_manifest": dict(entry["retention_manifest"]),
                }
            )

    try:
        selected_locators, audit = select_t075_source_candidates(candidate_stream())
    except T065CaseD as exc:
        raise T075WorkflowError(
            "stage1-selection-replay",
            list(exc.problems),
            failure_ids=exc.failure_ids,
            failure_counts=exc.failure_counts,
            failure_details=exc.failure_details,
            failure_detail_counts=exc.failure_detail_counts,
        ) from exc
    if observed_arms != {"stochastic_non_combat_v1", "expert_non_combat_v1"}:
        raise T075WorkflowError(
            "stage1-selection-replay", ["both retained source arms are required"]
        )
    audit.update(
        {
            "approved_t075_spec_commit": T075_APPROVED_SPEC_COMMIT,
            "code_head": _code_head_for_artifact_root(args),
            "selection_domain": "T065-source-selection-v1",
            "parent_reuse_manifest_sha256": file_sha256(args.reuse_manifest),
            "parent_current_preflight_sha256": file_sha256(args.preflight),
        }
    )
    _write_canonical_json(args.ownership_audit, audit)
    desired = {
        (candidate.source_index, candidate.record_index): (digest, payload)
        for candidate, digest, payload in selected_locators
    }
    selected_states: dict[tuple[int, int], T065SourceState] = {}
    for source_index, path in enumerate(args.input):
        reader = _SourceArmArtifactReader(path)
        for record_index, state in enumerate(reader.iter_states()):
            wanted = desired.get((source_index, record_index))
            if wanted is not None:
                digest, payload = wanted
                selected_states[(source_index, record_index)] = replace(
                    state,
                    selected_state_index=-1,
                    selection_digest=digest,
                    selection_canonical_json=payload.decode("utf-8"),
                )
        if (
            file_sha256(path) != source_artifacts[source_index]["sha256"]
            or path.stat().st_size != source_artifacts[source_index]["size_bytes"]
        ):
            raise T075WorkflowError(
                "stage1-selection-replay", [f"source changed during selection: {path}"]
            )
    if len(selected_states) != 320:
        raise T075WorkflowError(
            "stage1-selection-replay",
            [
                f"ownership selection produced {len(selected_states)} states, expected 320"
            ],
        )
    selected = tuple(
        replace(
            selected_states[(candidate.source_index, candidate.record_index)],
            selected_state_index=index,
        )
        for index, (candidate, _digest, _payload) in enumerate(selected_locators)
    )
    selected_locator_keys = {
        (
            int(getattr(candidate, "source_index", -1)),
            int(getattr(candidate, "record_index", -1)),
        )
        for candidate, _digest, _payload in selected_locators
    }
    selected_replay_identity_digests = sorted(
        str(group["group_digest"])
        for group in audit["groups"]
        if isinstance(group.get("owner"), Mapping)
        and (
            int(group["owner"].get("source_index", -1)),
            int(group["owner"].get("record_index", -1)),
        )
        in selected_locator_keys
    )
    if len(selected_replay_identity_digests) != len(selected):
        raise T075WorkflowError(
            "stage1-selection-replay",
            ["selected replay identity coverage is not exactly 320 states"],
        )
    selected_sha = write_source_states(args.output, selected)
    replay = {
        "attempted": 0,
        "restored": 0,
        "mismatches": 0,
        "replacements": 0,
        "selected_duplicate": 0,
        "cross_split_overlap": 0,
        "status": "passed",
    }
    if args.replay_verify:
        replay = replay_source_states_process_sharded(
            selected,
            shard_specs=target_shard_ranges(worker_count=16),
            worker_count=16,
            simulator_seed=1,
            ascension=20,
            player_class="IRONCLAD",
            require_frozen_shards=True,
        )
    manifest = {
        "schema_id": T075_SELECTION_MANIFEST_SCHEMA_ID,
        "schema_version": 1,
        "task_id": T075_TASK_ID,
        "approved_t075_spec_commit": T075_APPROVED_SPEC_COMMIT,
        "code_head": _code_head_for_artifact_root(args),
        "selection_strategy_id": T075_SELECTION_STRATEGY_ID,
        "parent_reuse_manifest_sha256": file_sha256(args.reuse_manifest),
        "parent_current_preflight_sha256": file_sha256(args.preflight),
        "parent_ownership_audit_sha256": file_sha256(args.ownership_audit),
        "selected_states_path": str(args.output),
        "selected_states_sha256": selected_sha,
        "selected_state_schema_id": "t065-source-state-v1",
        "selected_state_file_format": "t065-source-state-jsonl-v1",
        "family_order": list(T065_MANDATORY_FAMILIES),
        "split_order": list(T065_SPLITS),
        "quotas": {"train": 48, "validation": 16, "heldout": 16},
        "post_owner_available_counts": audit["owner_counts_by_family_split"],
        "selected_counts": {
            family: {
                split: sum(
                    1
                    for state in selected
                    if state.family == family and state.split == split
                )
                for split in T065_SPLITS
            }
            for family in T065_MANDATORY_FAMILIES
        },
        "simulator_identity": _t075_pinned_simulator_identity(),
        "source_artifacts": source_artifacts,
        "selected_replay_identity_digests": selected_replay_identity_digests,
        "replay_verification": replay,
        "problems": [],
    }
    _write_canonical_json(args.manifest, manifest)
    _write_t075_stage_retention(
        args,
        stage="stage1-selection-replay",
        artifacts={
            "selected_states": args.output,
            "ownership_audit": args.ownership_audit,
            "selection_manifest": args.manifest,
            "source_stochastic": Path(
                next(
                    entry["path"]
                    for entry in source_entries
                    if entry["arm"].startswith("stochastic")
                )
            ),
            "source_expert": Path(
                next(
                    entry["path"]
                    for entry in source_entries
                    if entry["arm"].startswith("expert")
                )
            ),
        },
        evidence={
            **_t075_execution_evidence(
                args, status="completed", terminal=True, exit_code=0, executed=True
            ),
            "status": "completed",
            "terminal": True,
            "shard_count": replay["shard_count"],
            "worker_count": replay["worker_count"],
            "ranges": replay["shards"],
            "per_shard": replay["shards"],
            "processes": replay["processes"],
            "counts": manifest["selected_counts"],
            "replay_counts": {
                "attempted": replay["attempted"],
                "restored": replay["restored"],
                "process_count": replay["process_count"],
                "wall_clock_seconds": replay["wall_clock_seconds"],
            },
            "parent_identities": {
                "reuse": _t075_parent_identity(args.reuse_manifest),
                "preflight": _t075_parent_identity(args.preflight),
            },
        },
    )
    print(f"T075 selection passed: states=320 output={args.output}", file=sys.stderr)
    return 0


def _t075_target_row_completeness(
    states: Sequence[T065SourceState],
    targets: Sequence[T065CounterfactualTarget],
) -> dict[str, Any]:
    """Compare target rows with the exact eligible-action key set."""
    expected_row_count = sum(len(state.eligible_action_indices) for state in states)
    expected_rows = {
        (state.selected_state_index, action_index)
        for state in states
        for action_index in state.eligible_action_indices
    }
    actual_row_list = [
        (row.selected_state_index, row.legal_action_index) for row in targets
    ]
    actual_rows = set(actual_row_list)
    duplicate_row_count = len(actual_row_list) - len(actual_rows)
    missing_row_count = len(expected_rows - actual_rows)
    unexpected_row_count = len(actual_rows - expected_rows)
    return {
        "expected_row_count": expected_row_count,
        "actual_row_count": len(actual_row_list),
        "missing_row_count": missing_row_count,
        "duplicate_row_count": duplicate_row_count,
        "unexpected_row_count": unexpected_row_count,
        "complete": (
            len(actual_row_list) == expected_row_count
            and actual_rows == expected_rows
            and duplicate_row_count == 0
        ),
    }


def _t075_write_stage3_report(
    args: argparse.Namespace, table_path: Path, states_path: Path, selection_path: Path
) -> dict[str, Any]:
    preceding_manifest = _t075_preceding_manifest_path(args, stage="stage2-target")
    problems: list[str] = []
    violations = {
        "missing_target_rows": 0,
        "duplicate_target_rows": 0,
        "nonfinite_targets": 0,
        "model_input_mismatches": 0,
        "lineage_mismatches": 0,
        "legal_action_mismatches": 0,
        "continuation_seed_mismatches": 0,
        "firewall_violations": 0,
    }
    strict_status = "passed"
    try:
        table = read_target_table(table_path)
        table.validate_complete()
        states = table.states
    except (OSError, ValueError, T065CaseD) as exc:
        strict_status = "failed"
        states = ()
        problems.append(f"strict target reader: {exc}")
        violations["missing_target_rows"] += 1
        table = None
    raw_table: Mapping[str, Any] = {}
    try:
        raw_value = json.loads(table_path.read_text(encoding="utf-8"))
        if isinstance(raw_value, Mapping):
            raw_table = raw_value
    except (OSError, json.JSONDecodeError) as exc:
        problems.append(f"target table metadata is unreadable: {exc}")
        violations["lineage_mismatches"] += 1

    selected_state_lineage = {
        "status": "failed",
        "path": str(states_path),
        "sha256": file_sha256(states_path) if states_path.is_file() else None,
        "size_bytes": states_path.stat().st_size if states_path.is_file() else None,
        "record_count": len(states),
        "content_match": False,
    }
    source_identity = raw_table.get("source_artifact_identity")
    if strict_status == "passed":
        try:
            persisted_states = read_source_states(states_path)
            content_match = tuple(
                state.to_dict() for state in persisted_states
            ) == tuple(state.to_dict() for state in states)
        except (OSError, ValueError) as exc:
            content_match = False
            problems.append(f"selected-state content is unreadable: {exc}")
        if (
            states_path.is_file()
            and isinstance(source_identity, Mapping)
            and _t075_path_matches(source_identity.get("path", ""), states_path)
            and source_identity.get("sha256") == file_sha256(states_path)
            and source_identity.get("size_bytes") == states_path.stat().st_size
            and source_identity.get("record_count") == len(states)
            and content_match
        ):
            selected_state_lineage["status"] = "passed"
            selected_state_lineage["content_match"] = True
        else:
            problems.append("selected-state lineage or content does not match")
            violations["lineage_mismatches"] += 1
    else:
        problems.append("selected-state lineage was not checked after reader failure")
        violations["lineage_mismatches"] += 1

    lineage_ok = strict_status == "passed"
    try:
        selection = json.loads(selection_path.read_text(encoding="utf-8"))
        if not isinstance(selection, Mapping):
            raise ValueError("selection manifest is not an object")
        if selection.get("schema_id") != T075_SELECTION_MANIFEST_SCHEMA_ID:
            raise ValueError("selection manifest schema is invalid")
        if (
            selection.get("schema_version") != 1
            or selection.get("task_id") != T075_TASK_ID
            or selection.get("approved_t075_spec_commit") != T075_APPROVED_SPEC_COMMIT
        ):
            raise ValueError("selection manifest T075 identity is invalid")
        if (
            raw_table.get("task_id") != T075_TASK_ID
            or raw_table.get("approved_spec_commit") != T075_APPROVED_SPEC_COMMIT
            or raw_table.get("t075_parent_selection_manifest_sha256")
            != file_sha256(selection_path)
            or raw_table.get("t075_parent_preflight_sha256")
            != file_sha256(args.preflight)
        ):
            raise ValueError("target table T075 parent lineage is invalid")
        if selection.get("selected_states_sha256") != file_sha256(states_path):
            raise ValueError("selection manifest selected-state hash is invalid")
        if selection.get("parent_current_preflight_sha256") != file_sha256(
            args.preflight
        ):
            raise ValueError("selection manifest preflight parent is invalid")
        if not preceding_manifest.is_file():
            raise ValueError("Stage-1 retention parent is missing")
        if selection.get("parent_reuse_manifest_sha256") is None:
            raise ValueError("selection reuse parent is missing")
        if selection.get("approved_t075_spec_commit") != T075_APPROVED_SPEC_COMMIT:
            raise ValueError("selection approved spec is invalid")
        if selection.get("selection_strategy_id") != T075_SELECTION_STRATEGY_ID:
            raise ValueError("selection strategy identity is invalid")
        if selection.get("code_head") != _code_head_for_artifact_root(args):
            raise ValueError("selection code head is not the executing checkout")
        _t075_require_pinned_simulator_identity(
            selection.get("simulator_identity"), label="selection"
        )
        selected_digests = selection.get("selected_replay_identity_digests")
        if (
            not isinstance(selected_digests, list)
            or len(selected_digests) != 320
            or len(set(selected_digests)) != 320
            or any(
                not isinstance(digest, str) or len(digest) != 64
                for digest in selected_digests
            )
        ):
            raise ValueError("selection replay digest coverage is invalid")
        expected_counts = {
            family: {split: (48 if split == "train" else 16) for split in T065_SPLITS}
            for family in T065_MANDATORY_FAMILIES
        }
        if selection.get("selected_counts") != expected_counts:
            raise ValueError("selection counts are not the frozen quotas")
        replay = selection.get("replay_verification")
        if (
            not isinstance(replay, Mapping)
            or replay.get("status") != "passed"
            or replay.get("attempted") != 320
            or replay.get("restored") != 320
            or any(
                replay.get(key) != 0
                for key in (
                    "mismatches",
                    "replacements",
                    "selected_duplicate",
                    "cross_split_overlap",
                )
            )
            or replay.get("worker_count") != T065_MAX_WORKERS
            or replay.get("shard_count") != T065_MAX_WORKERS
            or replay.get("process_count") != T065_MAX_WORKERS
        ):
            raise ValueError("selection replay verification is incomplete")
        ownership_path = (
            args.ownership_audit
            if hasattr(args, "ownership_audit")
            else selection_path.parent / "stage1-replay-group-ownership-audit.json"
        )
        if not ownership_path.is_file() or selection.get(
            "parent_ownership_audit_sha256"
        ) != file_sha256(ownership_path):
            raise ValueError("selection ownership audit parent is invalid")
        source_artifacts = selection.get("source_artifacts")
        if (
            not isinstance(source_artifacts, list)
            or len(source_artifacts) != 2
            or {
                item.get("arm")
                for item in source_artifacts
                if isinstance(item, Mapping)
            }
            != {"stochastic_non_combat_v1", "expert_non_combat_v1"}
        ):
            raise ValueError("selection source lineage is incomplete")
        for source in source_artifacts:
            if not isinstance(source, Mapping):
                raise ValueError("selection source lineage entry is invalid")
            source_path = _portable_path(str(source.get("path", "")))
            normalized_source = _t075_normalize_artifact_path(str(source_path))
            frozen_source = T075_FROZEN_SOURCE_ARTIFACTS.get(normalized_source)
            if (
                not isinstance(frozen_source, Mapping)
                or source.get("arm") != frozen_source.get("arm")
                or source.get("sha256") != frozen_source.get("sha256")
                or source.get("size_bytes") != frozen_source.get("size_bytes")
                or not _t075_identity_matches(source, source_path)
            ):
                raise ValueError("selection source artifact identity is invalid")
            retention_identity = source.get("retention_manifest")
            if not isinstance(retention_identity, Mapping):
                raise ValueError("selection source retention identity is missing")
            retention_path, _retention = _t075_find_source_retention(source_path)
            if (
                not _t075_path_matches(
                    retention_identity.get("path", ""), retention_path
                )
                or retention_identity.get("sha256") != file_sha256(retention_path)
                or retention_identity.get("size_bytes") != retention_path.stat().st_size
            ):
                raise ValueError("selection source retention identity is invalid")
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        lineage_ok = False
        problems.append(f"selection/source lineage: {exc}")
        violations["lineage_mismatches"] += 1
    try:
        _t075_require_parent_retention(
            preceding_manifest,
            stage="stage1-selection-replay",
            required_paths={
                "selected_states": states_path,
                "ownership_audit": args.ownership_audit
                if hasattr(args, "ownership_audit")
                else selection_path.parent / "stage1-replay-group-ownership-audit.json",
                "selection_manifest": selection_path,
            },
        )
    except (OSError, ValueError, T075WorkflowError) as exc:
        lineage_ok = False
        problems.append(f"Stage-1 retention lineage: {exc}")
        violations["lineage_mismatches"] += 1

    simulator_ok: bool | None = (
        bool(table is not None) if strict_status == "passed" else None
    )
    if (
        simulator_ok
        and dict(table.simulator_identity) != _t075_pinned_simulator_identity()
    ):
        simulator_ok = False
        problems.append("target simulator identity is not the pinned identity")
        violations["lineage_mismatches"] += 1
    preflight_ok: bool | None = None
    try:
        if strict_status != "passed":
            raise ValueError(
                "strict target reader failed; preflight lineage not executed"
            )
        preflight = _validate_t075_preflight(args.preflight)
        preflight_ok = preflight.get("passed") is True
        if preflight.get("simulator_identity") != _t075_pinned_simulator_identity():
            raise ValueError("preflight simulator identity is invalid")
        if not preflight_ok:
            raise ValueError("preflight is not passed")
    except (OSError, ValueError, T065CaseD) as exc:
        preflight_ok = False
        problems.append(f"preflight lineage: {exc}")
        violations["lineage_mismatches"] += 1

    counts = {
        family: {
            split: sum(
                1 for state in states if state.family == family and state.split == split
            )
            for split in T065_SPLITS
        }
        for family in T065_MANDATORY_FAMILIES
    }
    expected = {
        family: {split: (48 if split == "train" else 16) for split in T065_SPLITS}
        for family in T065_MANDATORY_FAMILIES
    }
    cohort_ok = (
        len(states) == 320
        and counts == expected
        and all(state.selected_state_index == i for i, state in enumerate(states))
    )
    if not cohort_ok:
        problems.append("target cohort does not satisfy exact T075 counts")
    row_completeness = _t075_target_row_completeness(
        states, table.targets if table is not None else ()
    )
    completeness_ok = False
    schema_ok: bool | None = True if strict_status == "passed" else None
    schema = raw_table.get("model_input_schema")
    if (
        not isinstance(schema, Mapping)
        or schema.get("state_feature_size") != 4737
        or schema.get("action_feature_size") != 92
    ):
        schema_ok = False if strict_status == "passed" else None
        if strict_status == "passed":
            problems.append("model-input schema is not the frozen 4737/92 schema")
            violations["model_input_mismatches"] += 1
    finite_ok: bool | None = True if strict_status == "passed" else None
    legal_ok: bool | None = True if strict_status == "passed" else None
    seed_ok: bool | None = True if strict_status == "passed" else None
    firewall_ok: bool | None = True if strict_status == "passed" else None
    if table is not None:
        violations["missing_target_rows"] += row_completeness["missing_row_count"]
        violations["duplicate_target_rows"] += (
            row_completeness["duplicate_row_count"]
            + row_completeness["unexpected_row_count"]
        )
        for state in states:
            if (
                len(state.state_features) != 4737
                or len(state.public_context_features) != 103
                or len(state.snapshot_features) != 4634
            ):
                schema_ok = False
                violations["model_input_mismatches"] += 1
            if any(not math.isfinite(float(value)) for value in state.state_features):
                finite_ok = False
                violations["nonfinite_targets"] += 1
            if forbidden_public_context_problems(state.public_run_context):
                firewall_ok = False
                violations["firewall_violations"] += 1
            observed = tuple(
                row.legal_action_index
                for row in table.rows_for_state(state.selected_state_index)
            )
            expected_actions = tuple(state.eligible_action_indices)
            if observed != expected_actions or any(
                row.legal_action_identity
                != state.legal_action_identities[row.legal_action_index]
                for row in table.rows_for_state(state.selected_state_index)
                if row.legal_action_index in state.eligible_action_indices
            ):
                legal_ok = False
                violations["legal_action_mismatches"] += 1
            expected_seeds = continuation_seeds_for_split(state.split)
            for row in table.rows_for_state(state.selected_state_index):
                if row.continuation_seeds != expected_seeds:
                    seed_ok = False
                    violations["continuation_seed_mismatches"] += 1
                values = (*row.terminal_floors, row.q_floor)
                if any(not math.isfinite(float(value)) for value in values):
                    finite_ok = False
                    violations["nonfinite_targets"] += 1
        completeness_ok = cohort_ok and row_completeness["complete"]
    else:
        # The reader failure is already the observed failure.  Checks whose
        # inputs were not readable remain not_run; inventing one violation per
        # check would turn missing evidence into fabricated measurements.
        pass

    def check_status(value: bool | None) -> str:
        if value is None:
            return "not_run"
        return "passed" if value else "failed"

    checks = {
        "strict_target_reader": {"status": strict_status},
        "target_completeness": {
            "status": check_status(completeness_ok),
            "state_count": len(states),
            "target_row_count": len(table.targets) if table is not None else 0,
        },
        "selected_state_lineage": selected_state_lineage,
        "simulator_and_preflight_lineage": {
            "status": (
                "passed"
                if simulator_ok is True and preflight_ok is True and lineage_ok
                else "failed"
            ),
            "simulator_identity": dict(table.simulator_identity)
            if table is not None
            else {},
            "preflight_sha256": _t075_optional_file_sha256(args.preflight),
        },
        "model_input_schema": {
            "status": check_status(schema_ok),
            "state_feature_size": 4737,
            "action_feature_size": 92,
        },
        "state_action_dimensions": {"status": check_status(schema_ok)},
        "finite_numeric_values": {
            "status": check_status(finite_ok),
            "violations": violations["nonfinite_targets"],
        },
        "legal_action_order": {
            "status": check_status(legal_ok),
            "violations": violations["legal_action_mismatches"],
        },
        "continuation_seed_contract": {
            "status": check_status(seed_ok),
            "violations": violations["continuation_seed_mismatches"],
        },
        "public_input_firewall": {
            "status": check_status(firewall_ok),
            "violations": violations["firewall_violations"],
        },
    }
    passed = cohort_ok and all(check["status"] == "passed" for check in checks.values())
    if not passed and not problems:
        problems.append("one or more mandatory Stage-3 validation checks failed")
    report = {
        "schema_id": T075_STAGE3_VALIDATION_SCHEMA_ID,
        "schema_version": 1,
        "task_id": T075_TASK_ID,
        "approved_t075_spec_commit": T075_APPROVED_SPEC_COMMIT,
        "code_head": _code_head_for_artifact_root(args),
        "execution_stage": "stage2-target",
        "logical_stage": "stage3-model-input-lineage-firewall",
        "parent_target_table_sha256": _t075_optional_file_sha256(table_path),
        "parent_selected_states_sha256": _t075_optional_file_sha256(states_path),
        "parent_selection_manifest_sha256": _t075_optional_file_sha256(selection_path),
        "parent_current_preflight_sha256": _t075_optional_file_sha256(args.preflight),
        "selected_state_count": len(states),
        "target_row_count": len(table.targets) if table is not None else 0,
        "eligible_action_count": sum(
            len(state.eligible_action_indices) for state in states
        ),
        "family_split_state_counts": counts,
        "continuation_replication_counts_by_split": {
            split: len(continuation_seeds_for_split(split)) for split in T065_SPLITS
        },
        "checks": checks,
        "violation_counts": violations,
        "passed": passed,
        "problems": [] if passed else problems,
    }
    _write_canonical_json(args.validation_report, report)
    if not passed:
        raise T075WorkflowError(
            "stage2-target",
            report["problems"],
            failure_ids=("stage3-validation-failed",),
            failure_counts=dict(violations),
        )
    return report


def _run_t075_target(args: argparse.Namespace) -> int:
    if _t075_has_terminal_decision(args):
        print(
            "T075 terminal decision already exists; target is skipped", file=sys.stderr
        )
        return 0
    if args.shard_count != 16 or args.worker_count != 16:
        raise T075WorkflowError(
            "stage2-target",
            ["T075 target generation requires 16 shards and 16 workers"],
        )
    _validate_t075_preflight(args.preflight)
    preceding_manifest = _t075_preceding_manifest_path(args, stage="stage2-target")
    states = read_source_states(args.states)
    if len(states) != 320:
        raise T075WorkflowError(
            "stage2-target", [f"selected state count is {len(states)}, expected 320"]
        )
    selection_manifest = json.loads(args.selection_manifest.read_text(encoding="utf-8"))
    if selection_manifest.get(
        "schema_id"
    ) != T075_SELECTION_MANIFEST_SCHEMA_ID or selection_manifest.get(
        "selected_states_sha256"
    ) != file_sha256(args.states):
        raise T075WorkflowError(
            "stage2-target", ["selection manifest does not match selected states"]
        )
    _t075_require_parent_retention(
        preceding_manifest,
        stage="stage1-selection-replay",
        required_paths={
            "selected_states": args.states,
            "ownership_audit": args.selection_manifest.parent
            / "stage1-replay-group-ownership-audit.json",
            "selection_manifest": args.selection_manifest,
        },
    )
    source_identity = {
        "path": str(args.states),
        "sha256": file_sha256(args.states),
        "size_bytes": args.states.stat().st_size,
        "record_count": len(states),
    }
    shard_specs = target_shard_ranges(worker_count=16)
    with TemporaryDirectory(
        prefix="t075-stage2-target-shards-", dir=args.output.parent
    ) as shard_directory:
        table = generate_counterfactual_targets_process_sharded(
            states,
            shard_specs=shard_specs,
            worker_count=16,
            output_directory=Path(shard_directory),
            simulator_seed=1,
            ascension=20,
            player_class="IRONCLAD",
            source_artifact_identity=source_identity,
            simulator_identity=lightspeed_source_identity_dict(),
            require_frozen_shards=True,
        )
    write_target_table(args.output, table)
    raw = json.loads(args.output.read_text(encoding="utf-8"))
    raw.update(
        {
            "task_id": T075_TASK_ID,
            "approved_spec_commit": T075_APPROVED_SPEC_COMMIT,
            "t075_parent_selection_manifest_sha256": file_sha256(
                args.selection_manifest
            ),
            "t075_parent_preflight_sha256": file_sha256(args.preflight),
        }
    )
    _write_canonical_json(args.output, raw)
    validation = _t075_write_stage3_report(
        args, args.output, args.states, args.selection_manifest
    )
    target_ranges = table.execution_evidence.get("shards", [])
    target_wall_clock = table.execution_evidence.get("wall_clock_seconds", 0.0)
    target_processes = table.execution_evidence.get("processes", [])
    process_by_index = {
        int(process["shard_index"]): dict(process)
        for process in target_processes
        if isinstance(process, Mapping) and "shard_index" in process
    }
    target_per_shard = [
        {
            **dict(range_spec),
            **process_by_index.get(int(range_spec["shard_index"]), {}),
        }
        for range_spec in target_ranges
        if isinstance(range_spec, Mapping) and "shard_index" in range_spec
    ]
    _write_t075_stage_retention(
        args,
        stage="stage2-target",
        artifacts={
            "target_table": args.output,
            "target_validation": args.validation_report,
        },
        evidence={
            **_t075_execution_evidence(
                args, status="completed", terminal=True, exit_code=0, executed=True
            ),
            "status": "completed",
            "terminal": True,
            "shard_count": 16,
            "worker_count": 16,
            "ranges": target_ranges,
            "per_shard": target_per_shard,
            "processes": target_processes,
            "subphase_wall_clock_seconds": {
                "target_generation": target_wall_clock,
            },
            "stage3_validation_status": "passed",
            "counts": validation["family_split_state_counts"],
            "parent_identities": {
                "selection": _t075_parent_identity(args.selection_manifest),
                "preflight": _t075_parent_identity(args.preflight),
            },
        },
    )
    print(
        f"T075 target and mandatory Stage-3 validation passed: {args.output}",
        file=sys.stderr,
    )
    return 0


def _run_t075_train(args: argparse.Namespace) -> int:
    if _t075_has_terminal_decision(args):
        print(
            "T075 terminal decision already exists; training is skipped",
            file=sys.stderr,
        )
        return 0
    preceding_manifest = _t075_preceding_manifest_path(args, stage="stage4-train")
    validation = json.loads(args.target_validation.read_text(encoding="utf-8"))
    if (
        validation.get("schema_id") != T075_STAGE3_VALIDATION_SCHEMA_ID
        or validation.get("passed") is not True
    ):
        raise T075WorkflowError(
            "stage4-train", ["Stage-3 validation is absent or failed"]
        )
    if validation.get("parent_target_table_sha256") != file_sha256(args.target_table):
        raise T075WorkflowError(
            "stage4-train", ["Stage-3 target parent hash does not match"]
        )
    if validation.get("parent_selected_states_sha256") != file_sha256(
        args.target_table.parent / "stage1-selected-states.json"
    ):
        raise T075WorkflowError(
            "stage4-train", ["Stage-3 selected-state parent hash does not match"]
        )
    _t075_require_parent_retention(
        preceding_manifest,
        stage="stage2-target",
        required_paths={
            "target_table": args.target_table,
            "target_validation": args.target_validation,
        },
    )
    table = read_target_table(args.target_table)
    table.validate_complete()
    args.checkpoint_directory.mkdir(parents=True, exist_ok=True)
    training_started = time.perf_counter()
    runs = train_frozen_model_seeds(
        states=table.states,
        targets=table.targets,
        source_artifact_identity=table.source_artifact_identity,
        target_artifact_identity={
            "path": str(args.target_table),
            "sha256": file_sha256(args.target_table),
            "size_bytes": args.target_table.stat().st_size,
            "record_count": len(table.targets),
        },
        checkpoint_directory=args.checkpoint_directory,
    )
    payload = {
        "schema_id": "t075-training-report-v1",
        "schema_version": 1,
        "task_id": T075_TASK_ID,
        "approved_t075_spec_commit": T075_APPROVED_SPEC_COMMIT,
        "planner_baseline": T075_PLANNER_BASELINE,
        "code_head": _code_head_for_artifact_root(args),
        "parent_target_validation_sha256": file_sha256(args.target_validation),
        "models": [
            {
                "model_seed": run.model_seed,
                "validation_q_floor_mae": run.validation_mae,
                "checkpoint_path": run.checkpoint_path,
                "checkpoint_sha256": file_sha256(Path(run.checkpoint_path))
                if run.checkpoint_path
                else None,
                "metadata": dict(run.metadata),
            }
            for run in runs
        ],
        "problems": [],
    }
    _write_canonical_json(args.output, payload)
    training_wall_clock = time.perf_counter() - training_started
    _write_t075_stage_retention(
        args,
        stage="stage4-train",
        artifacts={
            "training_report": args.output,
            "checkpoint_653001": args.checkpoint_directory / "model-653001.pt",
            "checkpoint_653002": args.checkpoint_directory / "model-653002.pt",
        },
        evidence={
            **_t075_execution_evidence(
                args, status="completed", terminal=True, exit_code=0, executed=True
            ),
            "status": "completed",
            "terminal": True,
            "parent_identities": {
                "target_validation": _t075_parent_identity(args.target_validation)
            },
            "subphase_wall_clock_seconds": {
                "training": training_wall_clock,
            },
            "shard_count": 1,
            "worker_count": 2,
            "ranges": [],
            "per_shard": [],
        },
    )
    print(f"T075 training passed: {args.output}", file=sys.stderr)
    return 0


def _run_t075_evaluate(args: argparse.Namespace) -> int:
    if _t075_has_terminal_decision(args):
        print(
            "T075 terminal decision already exists; evaluation is skipped",
            file=sys.stderr,
        )
        return 0
    preceding_manifest = _t075_preceding_manifest_path(args, stage="stage5-gate")
    parent_stage = "stage5-gate" if args.stage5_report else "stage4-train"
    parent_artifacts = (
        {"stage5_report": args.stage5_report}
        if args.stage5_report
        else {
            "training_report": args.checkpoint_directory.parent
            / "stage4-training-report.json"
        }
    )
    parent_artifacts.update(
        {
            "checkpoint_653001": args.checkpoint_directory / "model-653001.pt",
            "checkpoint_653002": args.checkpoint_directory / "model-653002.pt",
        }
    )
    _t075_require_parent_retention(
        preceding_manifest,
        stage=parent_stage,
        required_paths=parent_artifacts,
    )
    table = read_target_table(args.target_table)
    stage5_started = time.perf_counter()
    stage5_path = args.stage5_report or args.output
    if args.run_stage6 and args.stage5_report:
        stage5 = _read_t075_stage5_gate_report(
            args.stage5_report, target_table_path=args.target_table
        )
        model_runs = tuple(
            load_non_combat_checkpoint(args.checkpoint_directory / f"model-{seed}.pt")
            for seed in (653001, 653002)
        )
    else:
        model_runs = tuple(
            load_non_combat_checkpoint(args.checkpoint_directory / f"model-{seed}.pt")
            for seed in (653001, 653002)
        )
        stage5 = build_stage5_report(model_runs, table)
        stage5_payload = {
            "schema_id": "t075-stage5-gate-report-v1",
            "schema_version": 1,
            "task_id": T075_TASK_ID,
            "approved_t075_spec_commit": T075_APPROVED_SPEC_COMMIT,
            "parent_target_table_sha256": file_sha256(args.target_table),
            "stage5": stage5.to_dict(),
            "passed": stage5.passed,
            "problems": list(stage5.problems),
        }
        _write_canonical_json(stage5_path, stage5_payload)
    stage5_wall_clock = time.perf_counter() - stage5_started
    stage5_evidence = {
        **_t075_execution_evidence(
            args, status="completed", terminal=True, exit_code=0, executed=True
        ),
        "status": "completed",
        "terminal": True,
        "counts": {
            "passed": stage5.passed,
            "problems": len(stage5.problems),
        },
        "parent_identities": {
            "target_table": _t075_parent_identity(args.target_table),
        },
        "subphase_wall_clock_seconds": {
            "stage5": stage5_wall_clock,
        },
        "shard_count": 0,
        "worker_count": 0,
        "ranges": [],
        "per_shard": [],
        "problems": list(stage5.problems),
    }
    stage5_artifacts = {
        "stage5_report": stage5_path,
        "checkpoint_653001": args.checkpoint_directory / "model-653001.pt",
        "checkpoint_653002": args.checkpoint_directory / "model-653002.pt",
    }
    stage5_evidence["parent_identities"] = {
        "target_table": _t075_parent_identity(args.target_table),
        "checkpoint_653001": _t075_parent_identity(
            args.checkpoint_directory / "model-653001.pt"
        ),
        "checkpoint_653002": _t075_parent_identity(
            args.checkpoint_directory / "model-653002.pt"
        ),
    }
    if not stage5.passed:
        skipped_commands, skipped_evidence = _t075_skipped_stage_contract(
            args, ("stage6-eval",), "Stage 5 gate failed"
        )
        decision = {
            "schema_id": T075_TERMINAL_DECISION_SCHEMA_ID,
            "schema_version": 1,
            "task_id": T075_TASK_ID,
            "approved_t075_spec_commit": T075_APPROVED_SPEC_COMMIT,
            "planner_baseline": T075_PLANNER_BASELINE,
            "code_head": _code_head_for_artifact_root(args),
            "terminal_case": "C",
            "terminal_stage": "stage5-gate",
            "reason_code": "stage5-gate-failed",
            "summary": "T075 held-out Stage 5 gate failed",
            "reached_stages": [
                "stage0-preflight",
                "stage0-reuse",
                "stage1-selection-replay",
                "stage2-target",
                "stage4-train",
                "stage5-gate",
            ],
            "skipped_stages": ["stage6-eval"],
            "parent_artifact_identities": {
                "target_table": _t075_parent_identity(args.target_table),
                "stage5_report": _t075_parent_identity(stage5_path),
            },
            "stage3_validation_status": "passed",
            "stage5_gate_status": "failed",
            "stage6_status": "skipped",
            "skipped_stage_commands": skipped_commands,
            "skipped_stage_evidence": skipped_evidence,
            "recommendation": "close this T075 target/model formulation",
            "problems": list(stage5.problems) or ["Stage 5 gate failed"],
        }
        _write_canonical_json(args.decision_report, decision)
        _write_t075_stage_retention(
            args,
            stage="stage5-gate",
            artifacts={
                **stage5_artifacts,
                "terminal_decision_report": args.decision_report,
            },
            evidence=stage5_evidence,
            terminal_case="C",
        )
        return 0
    if not args.run_stage6:
        # Stage 5 is an independently completed gate.  Stage 6 is a separate
        # frozen command, so its absence must not downgrade the completed
        # Stage-5 parent to pending (which would make standalone Stage 6
        # impossible to validate).
        completed_stage5_evidence = dict(stage5_evidence)
        _write_t075_stage_retention(
            args,
            stage="stage5-gate",
            artifacts=stage5_artifacts,
            evidence=completed_stage5_evidence,
        )
        print(
            "T075 Stage 5 passed; Stage 6 remains an independent command",
            file=sys.stderr,
        )
        return 0
    if (
        args.stage6_shard_count != T075_STAGE6_SHARD_COUNT
        or args.stage6_worker_count != T065_MAX_WORKERS
    ):
        raise T075WorkflowError(
            "stage6-eval", ["T075 Stage 6 requires the frozen 16x16 worker plan"]
        )
    selected = next(
        run for run in model_runs if run.model_seed == stage5.selected_model_seed
    )
    _stochastic, _expert, _learned, stage6 = run_stage6_experiment(
        lambda: LightSpeedAdapter(seed=1, ascension=20, player_class="IRONCLAD"),
        stage5=stage5,
        selected_model=selected,
        worker_count=args.stage6_worker_count,
    )
    stage6_execution = stage6.execution_evidence
    arm_execution = stage6_execution.get("arms")
    if not isinstance(arm_execution, Mapping) or set(arm_execution) != {
        "stochastic",
        "expert",
        "learned",
    }:
        raise T075WorkflowError(
            "stage6-eval", ["Stage 6 execution evidence does not contain three arms"]
        )
    actual_worker_counts = {
        arm_value.get("worker_count")
        for arm_value in arm_execution.values()
        if isinstance(arm_value, Mapping)
    }
    actual_shard_counts = {
        arm_value.get("shard_count")
        for arm_value in arm_execution.values()
        if isinstance(arm_value, Mapping)
    }
    if len(actual_worker_counts) != 1 or len(actual_shard_counts) != 1:
        raise T075WorkflowError(
            "stage6-eval", ["Stage 6 arm worker/shard evidence diverges"]
        )
    actual_worker_count = next(iter(actual_worker_counts))
    actual_shard_count = next(iter(actual_shard_counts))
    if actual_worker_count != T065_MAX_WORKERS or actual_shard_count != 16:
        raise T075WorkflowError(
            "stage6-eval", ["Stage 6 execution did not use the frozen worker plan"]
        )
    actual_ranges: list[dict[str, Any]] = []
    actual_per_shard: list[dict[str, Any]] = []
    actual_processes: dict[str, list[dict[str, Any]]] = {}
    for arm in sorted(arm_execution):
        arm_value = arm_execution[arm]
        shard_specs = (
            arm_value.get("shard_specs") if isinstance(arm_value, Mapping) else None
        )
        if isinstance(shard_specs, list):
            ordered_specs = sorted(
                shard_specs, key=lambda item: item.get("shard_index", -1)
            )
            actual_ranges.extend({"arm": arm, **dict(shard)} for shard in ordered_specs)
            actual_per_shard.extend(
                {"arm": arm, **dict(shard)} for shard in ordered_specs
            )
            actual_processes[arm] = [
                {
                    "process_id": shard.get("process_id"),
                    "worker_kind": shard.get("worker_kind"),
                    "exit_code": shard.get("exit_code"),
                    "shard_index": shard.get("shard_index"),
                }
                for shard in ordered_specs
            ]
    for arm, arm_value in arm_execution.items():
        shard_specs = (
            arm_value.get("shard_specs") if isinstance(arm_value, Mapping) else None
        )
        if (
            not isinstance(shard_specs, list)
            or len(shard_specs) != 16
            or any(
                not isinstance(shard, Mapping)
                or isinstance(shard.get("process_id"), bool)
                or not isinstance(shard.get("process_id"), int)
                or shard.get("worker_kind") != "spawn-process"
                or shard.get("exit_code") != 0
                for shard in shard_specs
            )
        ):
            raise T075WorkflowError(
                "stage6-eval",
                [f"Stage 6 {arm} arm lacks complete process/shard evidence"],
            )
    _t075_validate_process_shards(
        "stage6-eval",
        shard_count=actual_shard_count,
        worker_count=actual_worker_count,
        per_shard=actual_per_shard,
        status="completed" if stage6.valid else "failed",
        ranges=actual_ranges,
    )
    stage6_problems = list(stage6.problems)
    if not stage6.valid and not stage6_problems:
        stage6_problems = ["Stage 6 validation failed"]
    stage6_failure_ids = [] if stage6.valid else ["stage6:validation-failed"]
    stage6_failure_details = (
        []
        if stage6.valid
        else [
            {
                "failure_id": "stage6:validation-failed",
                "stage": "stage6-eval",
                "messages": stage6_problems,
            }
        ]
    )
    stage6_failure_counts = (
        {}
        if stage6.valid
        else {
            "failure_count": len(stage6_failure_ids),
            "problem_count": len(stage6_problems),
        }
    )
    stage6_report = stage6.to_dict()
    if not stage6.valid:
        failure_execution = dict(stage6_report["execution_evidence"])
        failure_execution.update(
            {
                "status": "failed",
                "terminal": False,
                "failure_stage": "stage6-eval",
                "failure_ids": stage6_failure_ids,
                "failure_counts": stage6_failure_counts,
                "failure_details": stage6_failure_details,
            }
        )
        stage6_report.update(
            {
                "failure_ids": stage6_failure_ids,
                "failure_counts": stage6_failure_counts,
                "failure_details": stage6_failure_details,
                "execution_evidence": failure_execution,
            }
        )
    _write_canonical_json(args.output, stage6_report)
    stage6_identity = _t075_parent_identity(args.output)
    payload = {
        "schema_id": T075_TERMINAL_DECISION_SCHEMA_ID,
        "schema_version": 1,
        "task_id": T075_TASK_ID,
        "approved_t075_spec_commit": T075_APPROVED_SPEC_COMMIT,
        "planner_baseline": T075_PLANNER_BASELINE,
        "code_head": _code_head_for_artifact_root(args),
        "terminal_case": "A" if stage6.passed else "B" if stage6.valid else "D",
        "terminal_stage": "stage6-eval",
        "reason_code": "stage6-completed"
        if stage6.valid
        else "stage6-validation-failed",
        "summary": "T075 Stage 6 completed"
        if stage6.valid
        else "T075 Stage 6 validation failed",
        "reached_stages": [
            "stage0-preflight",
            "stage0-reuse",
            "stage1-selection-replay",
            "stage2-target",
            "stage4-train",
            "stage5-gate",
            "stage6-eval",
        ],
        "skipped_stages": [],
        "parent_artifact_identities": {
            "target_table": _t075_parent_identity(args.target_table),
            "stage5_report": _t075_parent_identity(stage5_path),
            "stage6_report": stage6_identity,
        },
        "stage3_validation_status": "passed",
        "stage5_gate_status": "passed",
        "stage6_status": "completed" if stage6.valid else "failed",
        "recommendation": "accept experimental fallback controller"
        if stage6.valid
        else "do not promote",
        "problems": stage6_problems,
        "stage6_report_identity": stage6_identity,
        "stage6_arm_reports": dict(stage6_execution.get("arms", {})),
        "stage6_paired_rows": list(stage6_execution.get("paired_rows", [])),
        "stage6_execution_evidence": dict(stage6_execution),
        "failure_stage": "stage6" if not stage6.valid else None,
        "failure_ids": stage6_failure_ids,
        "failure_counts": stage6_failure_counts,
        "failure_details": stage6_failure_details,
    }
    _write_canonical_json(args.decision_report, payload)
    _write_t075_stage_retention(
        args,
        stage="stage6-eval",
        artifacts={
            "stage6_report": args.output,
            "terminal_decision_report": args.decision_report,
            "stage5_report": stage5_path,
        },
        evidence={
            **_t075_execution_evidence(
                args,
                status="completed" if stage6.valid else "failed",
                terminal=stage6.valid,
                exit_code=0 if stage6.valid else 1,
                executed=True,
            ),
            "shard_count": actual_shard_count,
            "worker_count": actual_worker_count,
            "ranges": actual_ranges,
            "per_shard": actual_per_shard,
            "processes": actual_processes,
            "execution_evidence": dict(stage6_execution),
            "status": "completed" if stage6.valid else "failed",
            "terminal": stage6.valid,
            "counts": {"valid": stage6.valid, "passed": stage6.passed},
            "problems": stage6_problems,
            "parent_identities": {
                "target_table": _t075_parent_identity(args.target_table)
            },
        },
        terminal_case=payload["terminal_case"],
    )
    return 0 if stage6.valid else 1


def _run_t075_finalize(args: argparse.Namespace) -> int:
    expected_root = T075_STABLE_ARTIFACT_ROOT
    if not _t075_artifact_root_matches(getattr(args, "artifact_root", None)):
        raise T075WorkflowError(
            "terminal-finalize",
            ["finalizer artifact root is not the frozen stable root"],
        )
    expected_paths = {
        "decision_report": expected_root / "terminal-decision-report.json",
        "retention_manifest": expected_root / "t075-retention-manifest.json",
    }
    for name, expected_path in expected_paths.items():
        supplied = getattr(args, name, None)
        if not isinstance(supplied, Path) or not _t075_path_matches(
            supplied, expected_path
        ):
            raise T075WorkflowError(
                "terminal-finalize", [f"finalizer {name} is not the frozen path"]
            )
    supplied_argv = getattr(args, "_command_argv", ())
    if supplied_argv and not _t075_cli_argv_matches(
        supplied_argv, _t075_terminal_finalize_argv()
    ):
        raise T075WorkflowError(
            "terminal-finalize", ["finalizer argv is not the frozen command"]
        )
    try:
        decision = json.loads(args.decision_report.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise T075WorkflowError(
            "terminal-finalize", [f"terminal decision is unreadable: {exc}"]
        ) from exc
    required = (
        "schema_id",
        "schema_version",
        "task_id",
        "approved_t075_spec_commit",
        "planner_baseline",
        "code_head",
        "terminal_case",
        "terminal_stage",
        "reason_code",
        "summary",
        "reached_stages",
        "skipped_stages",
        "parent_artifact_identities",
        "stage3_validation_status",
        "stage5_gate_status",
        "stage6_status",
        "recommendation",
        "problems",
    )
    if (
        not isinstance(decision, Mapping)
        or any(key not in decision for key in required)
        or decision.get("schema_id") != T075_TERMINAL_DECISION_SCHEMA_ID
        or decision.get("schema_version") != 1
        or decision.get("task_id") != T075_TASK_ID
        or decision.get("approved_t075_spec_commit") != T075_APPROVED_SPEC_COMMIT
        or decision.get("planner_baseline") != T075_PLANNER_BASELINE
        or not isinstance(decision.get("code_head"), str)
        or not decision.get("code_head")
        or decision.get("terminal_case") not in {"A", "B", "C", "D"}
    ):
        raise T075WorkflowError(
            "terminal-finalize", ["terminal decision does not satisfy T075 schema"]
        )
    validation_retention_path = args.retention_manifest
    if not _t075_terminal_decision_is_valid(
        decision,
        artifact_root=args.artifact_root,
        retention_path=validation_retention_path,
    ):
        raise T075WorkflowError(
            "terminal-finalize",
            ["terminal decision is not a complete first-valid report"],
        )
    actual_code_head = _code_head_for_artifact_root(args)
    if decision["code_head"] != actual_code_head:
        raise T075WorkflowError(
            "terminal-finalize",
            [
                "terminal decision code_head does not match the executing checkout: "
                f"{decision['code_head']} != {actual_code_head}"
            ],
        )
    execution_stages = T075_STAGE_ORDER[:-1]
    reached = decision.get("reached_stages")
    skipped = decision.get("skipped_stages")
    if (
        not isinstance(reached, list)
        or not isinstance(skipped, list)
        or len(set(reached)) != len(reached)
        or len(set(skipped)) != len(skipped)
        or any(stage not in execution_stages for stage in (*reached, *skipped))
        or set(reached).intersection(skipped)
        or set(reached).union(skipped) != set(execution_stages)
        or tuple(reached)
        != tuple(stage for stage in execution_stages if stage in reached)
        or tuple(skipped)
        != tuple(stage for stage in execution_stages if stage in skipped)
    ):
        raise T075WorkflowError(
            "terminal-finalize", ["terminal decision stage reachability is invalid"]
        )
    terminal_stage = decision.get("terminal_stage")
    if terminal_stage not in execution_stages:
        raise T075WorkflowError(
            "terminal-finalize", ["terminal decision terminal_stage is invalid"]
        )
    terminal_index = execution_stages.index(terminal_stage)
    if reached != list(execution_stages[: terminal_index + 1]) or skipped != list(
        execution_stages[terminal_index + 1 :]
    ):
        raise T075WorkflowError(
            "terminal-finalize",
            ["terminal decision reached/skipped stages are not a terminal prefix"],
        )
    if not decision.get("parent_artifact_identities"):
        raise T075WorkflowError(
            "terminal-finalize", ["terminal decision has no parent identities"]
        )
    if decision["terminal_case"] == "D" and not decision.get("problems"):
        raise T075WorkflowError("terminal-finalize", ["Case D has no failure problems"])
    if decision["terminal_case"] == "C" and (
        decision.get("terminal_stage") != "stage5-gate"
        or decision.get("stage5_gate_status") != "failed"
        or decision.get("stage6_status") != "skipped"
    ):
        raise T075WorkflowError(
            "terminal-finalize", ["Case C terminal semantics are invalid"]
        )
    if decision["terminal_case"] in {"A", "B"} and (
        decision.get("terminal_stage") != "stage6-eval"
        or decision.get("stage5_gate_status") != "passed"
        or decision.get("stage6_status") != "completed"
    ):
        raise T075WorkflowError(
            "terminal-finalize", ["Case A/B terminal semantics are invalid"]
        )
    if decision["terminal_case"] == "D":
        if decision.get("stage6_status") not in {"not_reached", "failed"}:
            raise T075WorkflowError(
                "terminal-finalize", ["Case D Stage 6 status is invalid"]
            )
        if (
            terminal_stage == "stage6-eval"
            and decision.get("stage6_status") != "failed"
        ):
            raise T075WorkflowError(
                "terminal-finalize", ["Stage-6 Case D must record failed execution"]
            )
        if (
            terminal_stage != "stage6-eval"
            and decision.get("stage6_status") != "not_reached"
        ):
            raise T075WorkflowError(
                "terminal-finalize", ["Case D skipped Stage 6 must be not_reached"]
            )
    parent_identities = decision.get("parent_artifact_identities")
    if not isinstance(parent_identities, Mapping):
        raise T075WorkflowError(
            "terminal-finalize", ["terminal decision parent identities are invalid"]
        )
    for role, identity in parent_identities.items():
        if not isinstance(identity, Mapping) or not isinstance(
            identity.get("path"), str
        ):
            raise T075WorkflowError(
                "terminal-finalize", [f"terminal parent {role!r} is invalid"]
            )
        if not _t075_actual_identity(identity, artifact_root=args.artifact_root):
            raise T075WorkflowError(
                "terminal-finalize", [f"terminal parent {role!r} is not current"]
            )
    args.artifact_root.mkdir(parents=True, exist_ok=True)
    stage_commands, stage_evidence, reused = _t075_stage_retention_records(
        args.artifact_root, decision
    )
    stage_outputs = [
        entry
        for stage_value in stage_evidence.values()
        for entry in stage_value.get("output_identities", [])
        if isinstance(entry, Mapping)
    ]
    for parent_role, identity in parent_identities.items():
        if not any(
            entry.get("path") == identity.get("path")
            and entry.get("sha256") == identity.get("sha256")
            and entry.get("size_bytes") == identity.get("size_bytes")
            for entry in stage_outputs
        ):
            raise T075WorkflowError(
                "terminal-finalize",
                [f"terminal parent {parent_role!r} is absent from stage outputs"],
            )
    produced: list[dict[str, Any]] = []
    seen_paths: set[str] = set()
    for path in sorted(args.artifact_root.rglob("*")):
        if path.is_file() and path != args.retention_manifest:
            normalized = str(path.resolve()).replace("\\", "/")
            if normalized in seen_paths:
                raise T075WorkflowError(
                    "terminal-finalize", [f"duplicate artifact path: {path}"]
                )
            seen_paths.add(normalized)
            relative_role = path.relative_to(args.artifact_root).as_posix()
            produced.append(_t075_artifact_identity(path, role=relative_role))
    terminal_output_identities = [
        entry
        for entry in produced
        if isinstance(entry.get("path"), str)
        and Path(entry["path"]).resolve() == args.decision_report.resolve()
    ]
    if len(terminal_output_identities) != 1 or not _t075_actual_identity(
        terminal_output_identities[0], artifact_root=args.artifact_root
    ):
        raise T075WorkflowError(
            "terminal-finalize",
            ["terminal decision output identity is missing or stale"],
        )
    skipped_stage_commands = decision.get("skipped_stage_commands")
    skipped_stage_evidence = decision.get("skipped_stage_evidence")
    skipped = {}
    all_evidence = {}
    for stage in execution_stages:
        if stage in decision.get("reached_stages", ()):
            continue
        if (
            not isinstance(skipped_stage_commands, Mapping)
            or not isinstance(skipped_stage_evidence, Mapping)
            or not isinstance(skipped_stage_commands.get(stage), str)
            or not skipped_stage_commands[stage].strip()
            or not isinstance(skipped_stage_evidence.get(stage), Mapping)
        ):
            raise T075WorkflowError(
                "terminal-finalize",
                [f"missing exact skipped evidence for {stage}"],
            )
        evidence = dict(skipped_stage_evidence[stage])
        required_skipped_fields = {
            "command",
            "executed",
            "status",
            "code_head",
            "start_time_utc",
            "end_time_utc",
            "exit_code",
            "terminal",
            "wall_clock_seconds",
            "shard_count",
            "worker_count",
            "ranges",
            "parent_identities",
            "output_identities",
        }
        if (
            not required_skipped_fields.issubset(evidence)
            or evidence.get("command") != skipped_stage_commands[stage]
            or evidence.get("executed") is not False
            or evidence.get("status") != "skipped"
            or evidence.get("code_head") != actual_code_head
            or not isinstance(evidence.get("start_time_utc"), str)
            or not evidence["start_time_utc"].strip()
            or not isinstance(evidence.get("end_time_utc"), str)
            or not evidence["end_time_utc"].strip()
            or evidence.get("exit_code") is not None
            or evidence.get("terminal") is not False
            or not isinstance(evidence.get("skip_reason"), str)
            or not evidence["skip_reason"].strip()
            or isinstance(evidence.get("wall_clock_seconds"), bool)
            or not isinstance(evidence.get("wall_clock_seconds"), (int, float))
            or evidence.get("wall_clock_seconds") < 0
            or evidence.get("shard_count") != 0
            or evidence.get("worker_count") != 0
            or evidence.get("ranges") != []
            or evidence.get("parent_identities") != {}
            or evidence.get("output_identities") != []
        ):
            raise T075WorkflowError(
                "terminal-finalize",
                [f"skipped evidence for {stage} is not exact and non-executed"],
            )
        skipped[stage] = evidence
        all_evidence[stage] = evidence
    all_commands = {**skipped, **stage_commands}
    all_evidence.update(stage_evidence)
    # The final entry is intentionally terminal only after this manifest is
    # atomically written; its output identity is the terminal decision.
    all_commands["terminal-finalize"] = {
        "command": _t075_terminal_finalize_command(),
        "executed": True,
        "status": "completed",
        "code_head": _code_head_for_artifact_root(args),
        "start_time_utc": datetime.now(timezone.utc).isoformat(),
        "end_time_utc": datetime.now(timezone.utc).isoformat(),
        "exit_code": 0,
        "terminal": True,
        "wall_clock_seconds": 0.0,
        "shard_count": 1,
        "worker_count": 1,
        "ranges": [],
        "parent_identities": dict(decision["parent_artifact_identities"]),
        "output_identities": terminal_output_identities,
    }
    all_evidence["terminal-finalize"] = {
        "command": all_commands["terminal-finalize"]["command"],
        "executed": True,
        "status": "completed",
        "code_head": _code_head_for_artifact_root(args),
        "start_time_utc": all_commands["terminal-finalize"]["start_time_utc"],
        "end_time_utc": all_commands["terminal-finalize"]["end_time_utc"],
        "exit_code": 0,
        "terminal": True,
        "shard_count": 1,
        "worker_count": 1,
        "ranges": [],
        "per_shard": [],
        "output_identities": all_commands["terminal-finalize"]["output_identities"],
        "parent_identities": dict(decision["parent_artifact_identities"]),
        "counts": {},
        "problems": [],
    }
    manifest = {
        "schema_id": T075_RETENTION_MANIFEST_SCHEMA_ID,
        "schema_version": 1,
        "task_id": T075_TASK_ID,
        "approved_t075_spec_commit": T075_APPROVED_SPEC_COMMIT,
        "planner_baseline": T075_PLANNER_BASELINE,
        "code_head": decision["code_head"],
        "terminal_case": decision["terminal_case"],
        "retention_owner": T075_TASK_ID,
        "retention_reason": "T075 final terminal evidence",
        "reused_artifacts": reused,
        "produced_artifacts": produced,
        "stage_commands": {stage: all_commands[stage] for stage in T075_STAGE_ORDER},
        "stage_evidence": {stage: all_evidence[stage] for stage in T075_STAGE_ORDER},
        "downstream_consumers": [],
        "deletion_condition": "merged terminal T075 report and no open consumer requires retained inputs",
        "problems": [],
    }
    _write_canonical_json(args.retention_manifest, manifest)
    print(
        f"T075 final retention materialized: {args.retention_manifest}", file=sys.stderr
    )
    return 0


def _run_collect(args: argparse.Namespace) -> int:
    _require_preflight(args)
    _require_preceding_manifests(args)
    _require_frozen_simulator_args(args)
    seeds = tuple(range(args.seed_start, args.seed_end + 1))
    factory = lambda: LightSpeedAdapter(  # noqa: E731 - explicit per-worker factory
        seed=args.sim_seed,
        ascension=args.ascension,
        player_class="IRONCLAD",
    )
    if (args.seed_start, args.seed_end) == T065_SOURCE_SEED_RANGE:
        report = collect_source_arm_sharded_to_path(
            factory,
            args.output,
            source_arm=args.arm,
            worker_count=16,
        )
    else:
        report = collect_source_arm(factory, source_arm=args.arm, seeds=seeds)
        _write_json(args.output, report.to_dict())
    print(
        f"T065 collected arm={args.arm} seeds={len(seeds)} "
        f"candidates={report.selected_candidate_count} "
        f"terminal={report.terminal_run_count} "
        f"truncated={report.truncated_run_count}",
        file=sys.stderr,
    )
    if not _source_report_is_complete(report):
        failed_ids = tuple(
            f"simulator_seed:{summary.get('simulator_seed')}"
            for summary in report.run_summaries
            if not summary.get("terminal") or summary.get("problems")
        )
        raise T065CaseD(
            "source-collection",
            report.problems
            or ("one or more frozen Stage 1 source runs did not complete",),
            failure_ids=failed_ids,
            failure_counts={
                "requested_runs": report.requested_seed_count,
                "terminal_runs": report.terminal_run_count,
                "truncated_runs": report.truncated_run_count,
                "failed_runs": report.failed_run_count,
            },
            simulator_identity=report.simulator_identity,
        )
    _write_workflow_manifest(args, stage="stage1-source-collection")
    return 0


def _run_select(args: argparse.Namespace) -> int:
    _require_preflight(args)
    _require_preceding_manifests(args)
    if len(args.input) != 2:
        raise ValueError("T065 selection requires exactly two source-arm artifacts")
    source_artifacts = []
    observed_arms = set()
    simulator_identity: Mapping[str, Any] | None = None

    def candidate_stream() -> Iterator["_SourceSelectionLocator"]:
        nonlocal simulator_identity
        for source_index, path in enumerate(args.input):
            reader = _SourceArmArtifactReader(path)
            for record_index, state in enumerate(reader.iter_states()):
                yield _SourceSelectionLocator.from_state(
                    state, source_index=source_index, record_index=record_index
                )
            arm = _validate_source_arm_metadata(
                reader.metadata, path, record_count=reader.record_count
            )
            if arm in observed_arms:
                raise ValueError(f"duplicate T065 source arm artifact: {arm}")
            observed_arms.add(arm)
            artifact_simulator_identity = reader.metadata.get("simulator_identity")
            if not isinstance(artifact_simulator_identity, Mapping):
                raise T065CaseD(
                    "source-selection", [f"{path}: simulator identity is missing"]
                )
            expected_simulator_identity = lightspeed_source_identity_dict()
            if dict(artifact_simulator_identity) != expected_simulator_identity:
                raise T065CaseD(
                    "source-selection",
                    [f"{path}: simulator identity does not match the pinned manifest"],
                )
            if simulator_identity is None:
                simulator_identity = dict(artifact_simulator_identity)
            elif dict(artifact_simulator_identity) != dict(simulator_identity):
                raise T065CaseD(
                    "source-selection", [f"{path}: simulator identities do not match"]
                )
            source_artifacts.append(
                {
                    "arm": arm,
                    "path": str(path),
                    "sha256": file_sha256(path),
                    "size_bytes": path.stat().st_size,
                    "record_count": reader.record_count,
                }
            )

    selected_locators = select_source_candidates(candidate_stream())
    if observed_arms != {
        "stochastic_non_combat_v1",
        "expert_non_combat_v1",
    }:
        raise ValueError("T065 selection requires stochastic and expert source arms")
    desired = {
        (candidate.source_index, candidate.record_index): (digest, payload)
        for candidate, digest, payload in selected_locators
    }
    selected_states_by_locator: dict[tuple[int, int], T065SourceState] = {}
    for source_index, path in enumerate(args.input):
        reader = _SourceArmArtifactReader(path)
        for record_index, state in enumerate(reader.iter_states()):
            key = (source_index, record_index)
            expected = desired.get(key)
            if expected is not None:
                actual = canonical_source_selection_key(state)
                if actual != expected:
                    raise T065CaseD(
                        "source-selection",
                        [f"{path}: selected source record changed during selection"],
                    )
                selected_states_by_locator[key] = state
    for source_index, path in enumerate(args.input):
        expected_artifact = source_artifacts[source_index]
        try:
            actual_size = path.stat().st_size
            actual_sha256 = file_sha256(path)
        except OSError as exc:
            raise T065CaseD(
                "source-selection",
                [f"{path}: source artifact disappeared during selection"],
            ) from exc
        if (
            actual_size != expected_artifact["size_bytes"]
            or actual_sha256 != expected_artifact["sha256"]
        ):
            raise T065CaseD(
                "source-selection",
                [f"{path}: source artifact changed between selection passes"],
            )
    if len(selected_states_by_locator) != len(selected_locators):
        raise T065CaseD(
            "source-selection", ["selected source record locator is missing"]
        )
    selected = tuple(
        replace(
            selected_states_by_locator[
                (candidate.source_index, candidate.record_index)
            ],
            selected_state_index=index,
            selection_digest=digest,
            selection_canonical_json=payload.decode("utf-8"),
        )
        for index, (candidate, digest, payload) in enumerate(selected_locators)
    )
    digest = write_source_states(args.output, selected)
    manifest_path = args.manifest or Path(f"{args.output}.manifest.json")
    write_source_selection_manifest(
        manifest_path,
        selected_states=selected,
        selected_artifact_identity={
            "path": str(args.output),
            "sha256": digest,
            "record_count": len(selected),
        },
        source_artifacts=source_artifacts,
        simulator_identity=simulator_identity or {},
        approved_spec_commit=T065_APPROVED_SPEC_COMMIT,
    )
    print(
        f"T065 selected states={len(selected)} sha256={digest} "
        f"manifest={manifest_path}",
        file=sys.stderr,
    )
    _write_workflow_manifest(args, stage="stage1-source-selection")
    return 0


def _run_target(args: argparse.Namespace) -> int:
    _require_preflight(args)
    _require_preceding_manifests(args)
    _require_frozen_simulator_args(args)
    states = read_source_states(args.states)
    if len(states) != 320:
        raise T065CaseD(
            "counterfactual-targets",
            [f"selected state count {len(states)} does not match frozen 320"],
            failure_ids=(f"selected_state_count:{len(states)}",),
            failure_counts={"selected_states": len(states), "required_states": 320},
            simulator_identity=lightspeed_source_identity_dict(),
        )
    source_artifact_identity = {
        "path": str(args.states),
        "sha256": file_sha256(args.states),
        "size_bytes": args.states.stat().st_size,
        "record_count": len(states),
    }
    simulator_identity = lightspeed_source_identity_dict()
    factory = lambda: LightSpeedAdapter(  # noqa: E731 - explicit per-worker factory
        seed=args.sim_seed,
        ascension=args.ascension,
        player_class="IRONCLAD",
    )
    table = (
        generate_counterfactual_targets_sharded(
            factory,
            states,
            worker_count=16,
            source_artifact_identity=source_artifact_identity,
            simulator_identity=simulator_identity,
        )
        if len(states) == 320
        else generate_counterfactual_targets(
            factory,
            states,
            source_artifact_identity=source_artifact_identity,
            simulator_identity=simulator_identity,
        )
    )
    digest = write_target_table(args.output, table)
    print(
        f"T065 target table rows={len(table.targets)} sha256={digest}", file=sys.stderr
    )
    _write_workflow_manifest(args, stage="stage2-counterfactual-targets")
    return 0


def _run_train(args: argparse.Namespace) -> int:
    _require_preflight(args)
    _require_preceding_manifests(args)
    table = read_target_table(args.target_table)
    args.checkpoint_directory.mkdir(parents=True, exist_ok=True)
    runs = train_frozen_model_seeds(
        states=table.states,
        targets=table.targets,
        source_artifact_identity=table.source_artifact_identity,
        target_artifact_identity={
            "path": str(args.target_table),
            "sha256": file_sha256(args.target_table),
            "size_bytes": args.target_table.stat().st_size,
            "record_count": len(table.targets),
        },
        checkpoint_directory=args.checkpoint_directory,
    )
    _write_json(
        args.output,
        {
            "schema_id": "t065-training-report-v1",
            "schema_version": 1,
            "approved_spec_commit": T065_APPROVED_SPEC_COMMIT,
            "simulator_identity": dict(table.simulator_identity),
            "source_artifact_identity": dict(table.source_artifact_identity),
            "target_artifact_identity": {
                "path": str(args.target_table),
                "sha256": file_sha256(args.target_table),
                "size_bytes": args.target_table.stat().st_size,
                "record_count": len(table.targets),
            },
            "model_input_schema": table.to_dict()["model_input_schema"],
            "models": [
                {
                    "model_seed": run.model_seed,
                    "validation_q_floor_mae": run.validation_mae,
                    "checkpoint_path": run.checkpoint_path,
                    "checkpoint_sha256": file_sha256(Path(run.checkpoint_path))
                    if run.checkpoint_path
                    else None,
                    "metadata": dict(run.metadata),
                }
                for run in runs
            ],
        },
    )
    print(f"T065 trained models={len(runs)}", file=sys.stderr)
    _write_workflow_manifest(args, stage="stage4-training")
    return 0


def _run_evaluate(args: argparse.Namespace) -> int:
    _require_preflight(args)
    _require_preceding_manifests(args)
    _require_frozen_simulator_args(args)
    table = read_target_table(args.target_table)
    model_runs = tuple(
        load_non_combat_checkpoint(args.checkpoint_directory / f"model-{seed}.pt")
        for seed in (653001, 653002)
    )
    stage5 = build_stage5_report(model_runs, table)
    payload: dict[str, Any] = {
        "approved_spec_commit": T065_APPROVED_SPEC_COMMIT,
        "simulator_identity": dict(table.simulator_identity),
        "target_artifact_identity": {
            "path": str(args.target_table),
            "sha256": file_sha256(args.target_table),
        },
        "model_input_schema": table.to_dict()["model_input_schema"],
        "stage5": stage5.to_dict(),
    }
    if stage5.passed and args.run_stage6:
        selected = next(
            run for run in model_runs if run.model_seed == stage5.selected_model_seed
        )
        stochastic, expert, learned, stage6 = run_stage6_experiment(
            lambda: LightSpeedAdapter(
                seed=args.sim_seed,
                ascension=args.ascension,
                player_class="IRONCLAD",
            ),
            stage5=stage5,
            selected_model=selected,
        )
        payload["stage6_arms"] = {
            "stochastic": stochastic.to_dict(),
            "expert": expert.to_dict(),
            "learned": learned.to_dict(),
        }
        payload["stage6"] = stage6.to_dict()
        if not stage6.valid:
            _write_json(args.output, payload)
            raise T065CaseD(
                "stage6",
                stage6.problems or ("Stage 6 reducer rejected the cohort",),
                failure_ids=tuple(
                    f"stage6-problem:{index}"
                    for index, _problem in enumerate(stage6.problems)
                ),
                failure_counts={
                    "paired_rows": len(stage6.paired_terminal_floor_deltas),
                    "controller_errors": stage6.controller_error_count,
                    "truncations": stage6.truncation_count,
                },
                simulator_identity=table.simulator_identity,
            )
        payload["decision"] = terminal_decision_report(
            stage5=stage5,
            stage6=stage6,
            simulator_identity=table.simulator_identity,
            preceding_stage_manifests=_preceding_manifest_identities(args),
        )
    else:
        if stage5.passed:
            payload["decision_status"] = "incomplete"
            payload["incomplete"] = True
            payload["decision_pending"] = (
                "Stage 6 was not requested; rerun with --run-stage6 before "
                "writing the terminal Case A/B decision"
            )
        else:
            payload["decision"] = terminal_decision_report(
                stage5=stage5,
                simulator_identity=table.simulator_identity,
                preceding_stage_manifests=_preceding_manifest_identities(args),
            )
    _write_json(args.output, payload)
    decision_path: Path | None = None
    if "decision" in payload:
        decision_path = _decision_report_path(args)
        _write_json(decision_path, payload["decision"])
    print(json.dumps(payload, indent=2, sort_keys=True), file=sys.stderr)
    if "decision_pending" in payload:
        _write_workflow_manifest(args, stage="stage5-heldout-pending-stage6")
        return 1
    _write_workflow_manifest(
        args,
        stage="stage5-stage6-evaluation",
        decision_path=decision_path,
        terminal=True,
        terminal_case=payload["decision"]["case"],
    )
    return 0 if payload["decision"]["case"] in {"A", "B", "C", "D"} else 1


def read_source_states_from_objects(rows: list[Any], path: Path) -> list[Any]:
    result = []
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            raise ValueError(f"{path}: source row {index} is not an object")
        # Reuse the strict current-schema reader without inventing a second
        # deserialization path.
        from sts_combat_rl.sim.non_combat_learning import T065SourceState

        result.append(T065SourceState.from_dict(row))
    return result


class _StreamingJsonReader:
    """Decode one JSON value at a time from a bounded text buffer."""

    _CHUNK_SIZE = 1024 * 1024

    def __init__(self, stream: Any) -> None:
        self._stream = stream
        self._decoder = json.JSONDecoder()
        self._buffer = ""
        self._eof = False

    def _read_more(self) -> bool:
        if self._eof:
            return False
        chunk = self._stream.read(self._CHUNK_SIZE)
        if chunk == "":
            self._eof = True
            return False
        self._buffer += chunk
        return True

    def _skip_whitespace(self) -> None:
        while True:
            self._buffer = self._buffer.lstrip()
            if self._buffer or self._eof:
                return
            self._read_more()

    def _consume(self, expected: str) -> None:
        self._skip_whitespace()
        while len(self._buffer) < len(expected) and self._read_more():
            pass
        if not self._buffer.startswith(expected):
            raise ValueError(f"expected JSON token {expected!r}")
        self._buffer = self._buffer[len(expected) :]

    def _consume_if(self, token: str) -> bool:
        self._skip_whitespace()
        while len(self._buffer) < len(token) and self._read_more():
            pass
        if not self._buffer.startswith(token):
            return False
        self._buffer = self._buffer[len(token) :]
        return True

    def value(self) -> Any:
        self._skip_whitespace()
        while True:
            try:
                value, end = self._decoder.raw_decode(self._buffer)
            except json.JSONDecodeError:
                if not self._read_more():
                    raise
                continue
            if end == len(self._buffer) and not self._eof:
                self._read_more()
                continue
            self._buffer = self._buffer[end:]
            return value

    def array_values(self) -> Iterator[Any]:
        self._consume("[")
        if self._consume_if("]"):
            return
        while True:
            yield self.value()
            if self._consume_if("]"):
                return
            self._consume(",")

    def ensure_end(self) -> None:
        self._skip_whitespace()
        if self._buffer:
            raise ValueError("unexpected trailing JSON data")


@dataclass(frozen=True)
class _SourceSelectionLocator:
    """Compact first-pass candidate retained until full-state reread."""

    source_index: int
    record_index: int
    family: str
    split: str
    simulator_seed: int
    source_arm: str
    source_run_id: str
    source_step_index: int
    public_state_identity: str
    legal_action_identities: tuple[Mapping[str, Any], ...]
    action_trace: tuple[Mapping[str, Any], ...]
    terminal: bool

    @classmethod
    def from_state(
        cls, state: T065SourceState, *, source_index: int, record_index: int
    ) -> "_SourceSelectionLocator":
        return cls(
            source_index=source_index,
            record_index=record_index,
            family=state.family,
            split=state.split,
            simulator_seed=state.simulator_seed,
            source_arm=state.source_arm,
            source_run_id=state.source_run_id,
            source_step_index=state.source_step_index,
            public_state_identity=state.public_state_identity,
            legal_action_identities=tuple(
                dict(identity) for identity in state.legal_action_identities
            ),
            action_trace=tuple(dict(item) for item in state.action_trace),
            terminal=state.terminal,
        )


class _SourceArmArtifactReader:
    """Stream source records while retaining only small source metadata."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.metadata: dict[str, Any] = {}
        self.record_count = 0

    def iter_states(self) -> Iterator[T065SourceState]:
        first_record_arm: str | None = None
        for row in self:
            if not isinstance(row, dict):
                raise ValueError(f"{self.path}: source row is not an object")
            state = T065SourceState.from_dict(row)
            if first_record_arm is None:
                first_record_arm = state.source_arm
            elif state.source_arm != first_record_arm:
                raise ValueError(f"{self.path}: source record arms are inconsistent")
            yield state
        if first_record_arm != self.metadata.get("arm"):
            raise ValueError(
                f"{self.path}: source record arm does not match artifact arm"
            )

    def __iter__(self) -> Iterator[Any]:
        seen_keys: set[str] = set()
        saw_records = False
        try:
            with self.path.open("r", encoding="utf-8") as stream:
                reader = _StreamingJsonReader(stream)
                reader._consume("{")
                if reader._consume_if("}"):
                    raise ValueError("source artifact object is empty")
                while True:
                    key = reader.value()
                    if not isinstance(key, str):
                        raise ValueError("source artifact key is not a string")
                    if key in seen_keys:
                        raise ValueError(f"duplicate source artifact key {key!r}")
                    seen_keys.add(key)
                    reader._consume(":")
                    if key == "records":
                        saw_records = True
                        for row in reader.array_values():
                            self.record_count += 1
                            yield row
                    else:
                        self.metadata[key] = reader.value()
                    if reader._consume_if("}"):
                        break
                    reader._consume(",")
                reader.ensure_end()
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError(
                f"{self.path}: invalid source artifact JSON: {exc}"
            ) from exc
        if not saw_records:
            raise ValueError(f"{self.path}: source records are missing")
        _validate_source_arm_metadata(
            self.metadata, self.path, record_count=self.record_count
        )


def _iter_source_arm_states(path: Path) -> Iterator[T065SourceState]:
    reader = _SourceArmArtifactReader(path)
    yield from reader.iter_states()


def _validate_source_arm_metadata(
    value: Mapping[str, Any], path: Path, *, record_count: int
) -> str:
    expected_seeds = set(range(650001, 650257))
    if value.get("schema_id") != "t065-learned-non-combat-policy-v1":
        raise T065CaseD("source-collection", [f"{path}: source schema is unsupported"])
    if value.get("schema_version") != T065_EXPERIMENT_SCHEMA_VERSION:
        raise T065CaseD(
            "source-collection", [f"{path}: source schema version is unsupported"]
        )
    if value.get("frozen_config") != T065ExperimentConfig().to_dict():
        raise T065CaseD(
            "source-collection", [f"{path}: source frozen config is not frozen"]
        )
    arm = value.get("arm")
    if not isinstance(arm, str) or arm not in {
        "stochastic_non_combat_v1",
        "expert_non_combat_v1",
    }:
        raise T065CaseD("source-collection", [f"{path}: source arm is invalid"])
    if value.get("approved_spec_commit") != T065_APPROVED_SPEC_COMMIT:
        raise T065CaseD(
            "source-collection", [f"{path}: approved T065 spec commit is invalid"]
        )
    if value.get("driver_seed") != 654001:
        raise T065CaseD("source-collection", [f"{path}: source driver seed is invalid"])
    if value.get("requested_seed_count") != 256:
        raise T065CaseD("source-collection", [f"{path}: source seed count is not 256"])
    if value.get("terminal_run_count") != 256:
        raise T065CaseD(
            "source-collection", [f"{path}: not all source runs are terminal"]
        )
    if value.get("truncated_run_count") != 0 or value.get("failed_run_count") != 0:
        raise T065CaseD(
            "source-collection", [f"{path}: source run truncation/failure reported"]
        )
    if value.get("selected_candidate_count") != record_count:
        raise T065CaseD(
            "source-collection",
            [f"{path}: source candidate count does not match records"],
        )
    if value.get("problems") != []:
        raise T065CaseD(
            "source-collection", [f"{path}: source artifact contains problems"]
        )
    if value.get("worker_count") != 16:
        raise T065CaseD("source-collection", [f"{path}: source worker count is not 16"])
    if value.get("action_space") != frozen_action_space().to_dict():
        raise T065CaseD("source-collection", [f"{path}: action space is not frozen"])
    battle_provenance = value.get("battle_controller_provenance")
    if battle_provenance != frozen_battle_provenance():
        raise T065CaseD(
            "source-collection", [f"{path}: battle provenance is not frozen"]
        )
    if value.get("simulator_identity") != lightspeed_source_identity_dict():
        raise T065CaseD(
            "source-collection", [f"{path}: simulator identity is not pinned"]
        )
    shard_specs = value.get("shard_specs")
    if value.get("shard_count") != 16 or not isinstance(shard_specs, list):
        raise T065CaseD(
            "source-collection", [f"{path}: source shard evidence is incomplete"]
        )
    if len(shard_specs) != 16 or any(
        not isinstance(spec, Mapping)
        or spec.get("shard_index") != index
        or spec.get("seed_start") != 650001 + 16 * index
        or spec.get("seed_end") != 650016 + 16 * index
        or spec.get("seed_count") != 16
        or spec.get("worker_count") != 16
        or spec.get("requested_seed_count") != 16
        or spec.get("terminal_run_count") != 16
        or spec.get("truncated_run_count") != 0
        or spec.get("failed_run_count") != 0
        or spec.get("problems")
        for index, spec in enumerate(shard_specs)
    ):
        raise T065CaseD(
            "source-collection", [f"{path}: source shard ranges/evidence are invalid"]
        )
    summaries = value.get("run_summaries")
    if not isinstance(summaries, list):
        raise T065CaseD("source-collection", [f"{path}: source summaries are missing"])
    if len(summaries) != 256:
        raise T065CaseD(
            "source-collection", [f"{path}: source run summaries are incomplete"]
        )
    summary_seeds = set()
    for summary in summaries:
        if not isinstance(summary, Mapping):
            raise T065CaseD(
                "source-collection", [f"{path}: source summary is malformed"]
            )
        seed = summary.get("simulator_seed")
        if isinstance(seed, bool) or not isinstance(seed, int):
            raise T065CaseD(
                "source-collection", [f"{path}: source summary seed is invalid"]
            )
        summary_seeds.add(seed)
        if (
            summary.get("source_arm") != arm
            or summary.get("source_run_id") != f"{arm}:{seed}"
            or not isinstance(summary.get("terminal"), bool)
            or summary.get("terminal") is not True
            or summary.get("problems")
        ):
            raise T065CaseD(
                "source-collection", [f"{path}: source summary is not valid"]
            )
    if summary_seeds != expected_seeds:
        raise T065CaseD(
            "source-collection", [f"{path}: source summary seed set is incomplete"]
        )
    return str(arm)


def _validate_source_arm_artifact(value: Mapping[str, Any], path: Path) -> str:
    rows = value.get("records")
    if not isinstance(rows, list):
        raise T065CaseD("source-collection", [f"{path}: source records are missing"])
    arm = _validate_source_arm_metadata(value, path, record_count=len(rows))
    for row in rows:
        if not isinstance(row, Mapping) or row.get("source_arm") != arm:
            raise T065CaseD(
                "source-collection", [f"{path}: source record arm is invalid"]
            )
    return arm


def _source_report_is_complete(report: Any) -> bool:
    return bool(
        not report.problems
        and report.requested_seed_count > 0
        and report.terminal_run_count == report.requested_seed_count
        and report.truncated_run_count == 0
        and report.failed_run_count == 0
    )


def _stage_name(command: str) -> str:
    return {
        "preflight": "stage0-preflight",
        "collect": "stage1-source-collection",
        "select": "stage1-source-selection",
        "target": "stage2-counterfactual-targets",
        "train": "stage4-training",
        "evaluate": "stage5",
    }.get(command, command)


def _decision_report_path(args: argparse.Namespace) -> Path:
    report_path = getattr(args, "decision_report", None)
    if isinstance(report_path, Path):
        return report_path
    output_path = getattr(args, "output", None)
    if isinstance(output_path, Path):
        return output_path.with_name(
            f"{output_path.stem}.t065-terminal-decision-report.json"
        )
    raise ValueError("T065 Case D requires an explicit output or decision-report path")


def _retention_manifest_path(args: argparse.Namespace) -> Path:
    manifest_path = getattr(args, "retention_manifest", None)
    if isinstance(manifest_path, Path):
        return manifest_path
    output_path = getattr(args, "output", None)
    if isinstance(output_path, Path):
        return output_path.with_name(f"{output_path.stem}.t065-retention-manifest.json")
    raise ValueError("T065 retention manifest requires an explicit output path")


def _file_identity(path: Path) -> dict[str, Any]:
    return {
        "path": str(path),
        "sha256": file_sha256(path),
        "size_bytes": path.stat().st_size,
    }


def _preceding_artifact_paths(args: argparse.Namespace) -> dict[str, Path]:
    """Return ordinary input/current artifact paths, never manifest lineage."""

    paths: dict[str, Path] = {}

    def add(role: str, path: Any) -> None:
        if isinstance(path, Path) and path.is_file():
            paths.setdefault(role, path)

    if args.command == "preflight":
        add("stage0_preflight", getattr(args, "output", None))
    else:
        add("stage0_preflight", getattr(args, "preflight", None))
    if args.command == "select":
        for index, path in enumerate(args.input):
            add(f"source_arm_{index}", path)
    elif args.command == "target":
        add("selected_states", args.states)
    elif args.command in {"train", "evaluate"}:
        add("target_table", args.target_table)
    if args.command == "evaluate":
        for model_seed in (653001, 653002):
            add(
                f"checkpoint_{model_seed}",
                args.checkpoint_directory / f"model-{model_seed}.pt",
            )
    return paths


def _artifact_identities(paths: Mapping[str, Path]) -> dict[str, Any]:
    """Return identities only for artifacts that actually exist."""

    return {
        role: _file_identity(path) for role, path in paths.items() if path.is_file()
    }


def _expected_preceding_stages(args: argparse.Namespace) -> tuple[str, ...]:
    return {
        "collect": ("stage0-preflight",),
        "select": (
            "stage0-preflight",
            "stage1-source-collection",
            "stage1-source-collection",
        ),
        "target": ("stage0-preflight", "stage1-source-selection"),
        "train": ("stage0-preflight", "stage2-counterfactual-targets"),
        "evaluate": (
            "stage0-preflight",
            "stage2-counterfactual-targets",
            "stage4-training",
        ),
    }[args.command]


def _read_retention_manifest(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"{path}: retention manifest cannot be read: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{path}: retention manifest root must be an object")
    if value.get("schema_id") != "t065-retention-manifest-v1":
        raise ValueError(f"{path}: retention manifest schema is unsupported")
    if value.get("schema_version") != 1:
        raise ValueError(f"{path}: retention manifest schema version is unsupported")
    if value.get("task_id") != "T065":
        raise ValueError(f"{path}: retention manifest task id is invalid")
    if value.get("approved_spec_commit") != T065_APPROVED_SPEC_COMMIT:
        raise ValueError(f"{path}: retention manifest approved spec is invalid")
    artifacts = value.get("artifacts")
    evidence = value.get("stage_evidence")
    if not isinstance(artifacts, list) or not isinstance(evidence, Mapping):
        raise ValueError(f"{path}: retention manifest lineage fields are missing")
    if not evidence or any(not isinstance(item, Mapping) for item in evidence.values()):
        raise ValueError(f"{path}: retention manifest stage evidence is invalid")

    def validate_identity(role: str, identity: Mapping[str, Any]) -> None:
        artifact_path = identity.get("path")
        digest = identity.get("sha256")
        size = identity.get("size_bytes")
        if not isinstance(artifact_path, str) or not artifact_path:
            raise ValueError(f"{path}: artifact {role} has an invalid path")
        if (
            not isinstance(digest, str)
            or len(digest) != 64
            or any(character not in "0123456789abcdef" for character in digest)
        ):
            raise ValueError(f"{path}: artifact {role} has an invalid sha256")
        if isinstance(size, bool) or not isinstance(size, int) or size < 0:
            raise ValueError(f"{path}: artifact {role} has an invalid size_bytes")
        actual_path = Path(artifact_path)
        if not actual_path.is_file():
            raise ValueError(f"{path}: artifact {role} is missing: {artifact_path}")
        if file_sha256(actual_path) != digest:
            raise ValueError(f"{path}: artifact {role} sha256 does not match")
        if actual_path.stat().st_size != size:
            raise ValueError(f"{path}: artifact {role} size_bytes does not match")

    roles: set[str] = set()
    for index, artifact in enumerate(artifacts):
        if not isinstance(artifact, Mapping):
            raise ValueError(f"{path}: artifact entry {index} is not an object")
        role = artifact.get("role")
        if not isinstance(role, str) or not role or role in roles:
            raise ValueError(f"{path}: artifact entry {index} has an invalid role")
        validate_identity(role, artifact)
        if role.startswith("checkpoint_"):
            expected_seed = role.removeprefix("checkpoint_")
            identity = artifact.get("identity")
            if (
                not expected_seed.isdigit()
                or not isinstance(identity, Mapping)
                or identity.get("model_seed") != int(expected_seed)
            ):
                raise ValueError(f"{path}: artifact {role} seed identity is invalid")
        roles.add(role)
    for section_name in ("preceding_stage_manifests", "failed_stage_artifacts"):
        identities = value.get(section_name, {})
        if not isinstance(identities, Mapping):
            raise ValueError(f"{path}: {section_name} must be an object")
        for role, identity in identities.items():
            if (
                not isinstance(role, str)
                or not role
                or not isinstance(identity, Mapping)
            ):
                raise ValueError(f"{path}: {section_name} contains an invalid entry")
            validate_identity(role, identity)
    for stage, stage_value in evidence.items():
        if not isinstance(stage, str) or not stage:
            raise ValueError(f"{path}: stage evidence has an invalid stage")
        referenced_roles = stage_value.get("artifact_roles")
        if not isinstance(referenced_roles, list) or any(
            not isinstance(role, str) or role not in roles for role in referenced_roles
        ):
            raise ValueError(
                f"{path}: stage evidence {stage} references unknown artifact roles"
            )
    return value


def _manifest_contains_artifact(
    manifest: Mapping[str, Any],
    path: Path,
    *,
    expected_role: str | None = None,
    expected_seed: int | None = None,
) -> bool:
    if not path.is_file():
        return False
    expected_path = path.resolve()
    expected_hash = file_sha256(path)
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, list):
        return False
    for artifact in artifacts:
        if not isinstance(artifact, Mapping):
            continue
        try:
            artifact_path = Path(str(artifact["path"])).resolve()
        except (KeyError, OSError, ValueError):
            continue
        if (
            artifact_path == expected_path
            and artifact.get("sha256") == expected_hash
            and artifact.get("schema_id") in {None, "t065-retention-manifest-v1"}
            and (expected_role is None or artifact.get("role") == expected_role)
        ):
            if expected_seed is not None:
                identity = artifact.get("identity")
                if (
                    artifact.get("role") != f"checkpoint_{expected_seed}"
                    or not isinstance(identity, Mapping)
                    or identity.get("model_seed") != expected_seed
                ):
                    continue
            return True
    return False


def _manifest_descriptor(path: Path, manifest: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "path": str(path),
        "sha256": file_sha256(path),
        "size_bytes": path.stat().st_size,
        "schema_id": manifest["schema_id"],
        "schema_version": manifest["schema_version"],
        "completed_stages": sorted(str(stage) for stage in manifest["stage_evidence"]),
    }


def _require_preceding_manifests(args: argparse.Namespace) -> None:
    expected_stages = _expected_preceding_stages(args)
    supplied = tuple(getattr(args, "preceding_manifest", None) or ())
    if len(supplied) != len(expected_stages):
        raise T065CaseD(
            _stage_name(args.command),
            [
                f"expected {len(expected_stages)} explicit preceding retention "
                f"manifests, received {len(supplied)}"
            ],
            failure_ids=(f"preceding-manifest-count:{len(supplied)}",),
            failure_counts={
                "required_manifests": len(expected_stages),
                "supplied_manifests": len(supplied),
            },
        )
    manifests: list[tuple[Path, Mapping[str, Any], str]] = []
    problems: list[str] = []
    for index, (path, expected_stage) in enumerate(zip(supplied, expected_stages)):
        try:
            manifest = _read_retention_manifest(path)
            evidence = manifest["stage_evidence"]
            stage_evidence = evidence.get(expected_stage)
            if (
                not isinstance(stage_evidence, Mapping)
                or stage_evidence.get("status") != "completed"
            ):
                raise ValueError(
                    f"{path}: completed evidence for {expected_stage} is missing"
                )
            manifests.append((path, manifest, expected_stage))
        except (OSError, ValueError, KeyError, TypeError) as exc:
            problems.append(f"preceding manifest {index}: {exc}")
    if problems:
        args._preceding_manifest_paths = tuple(
            path for path, _manifest, _stage in manifests
        )
        args._preceding_manifest_identities = {
            (
                "stage1_source_collection_" + str(index - 1)
                if stage == "stage1-source-collection"
                else stage.replace("-", "_")
            ): _manifest_descriptor(path, manifest)
            for index, (path, manifest, stage) in enumerate(manifests)
        }
        raise T065CaseD(
            _stage_name(args.command),
            problems,
            failure_ids=tuple(
                f"preceding-manifest:{index}" for index in range(len(problems))
            ),
            failure_counts={"invalid_preceding_manifests": len(problems)},
        )

    relation_paths: list[Path | tuple[Path, ...] | None] = [None] * len(manifests)
    if args.command == "collect":
        relation_paths[0] = args.preflight
    elif args.command == "select":
        relation_paths[0] = args.preflight
        relation_paths[1:] = list(args.input)
    elif args.command == "target":
        relation_paths[0] = args.preflight
        relation_paths[1] = args.states
    elif args.command == "train":
        relation_paths[0] = args.preflight
        relation_paths[1] = args.target_table
    elif args.command == "evaluate":
        relation_paths[0] = args.preflight
        relation_paths[1] = args.target_table
        relation_paths[2] = tuple(
            args.checkpoint_directory / f"model-{seed}.pt" for seed in (653001, 653002)
        )
    relation_problems = []
    for index, ((path, manifest, _stage), relation_path) in enumerate(
        zip(manifests, relation_paths)
    ):
        paths = (
            relation_path
            if isinstance(relation_path, tuple)
            else (relation_path,)
            if relation_path is not None
            else ()
        )
        for required_path in paths:
            expected_seed = (
                int(required_path.stem.removeprefix("model-"))
                if args.command == "evaluate"
                and required_path.name.startswith("model-")
                else None
            )
            if not _manifest_contains_artifact(
                manifest,
                required_path,
                expected_role=(
                    f"checkpoint_{expected_seed}" if expected_seed is not None else None
                ),
                expected_seed=expected_seed,
            ):
                relation_problems.append(
                    f"preceding manifest {index} does not contain the exact "
                    f"path/hash/size/seed identity for {required_path}"
                )
    if relation_problems:
        raise T065CaseD(
            _stage_name(args.command),
            relation_problems,
            failure_ids=tuple(
                f"preceding-manifest-artifact:{index}"
                for index in range(len(relation_problems))
            ),
            failure_counts={"manifest_artifact_mismatches": len(relation_problems)},
        )

    args._preceding_manifest_paths = tuple(
        path for path, _manifest, _stage in manifests
    )
    args._preceding_manifest_identities = {
        (
            "stage1_source_collection_" + str(index - 1)
            if stage == "stage1-source-collection"
            else stage.replace("-", "_")
        ): _manifest_descriptor(path, manifest)
        for index, (path, manifest, stage) in enumerate(manifests)
    }


def _preceding_manifest_identities(args: argparse.Namespace) -> dict[str, Any]:
    return dict(getattr(args, "_preceding_manifest_identities", {}))


def _t075_write_stage6_failure_report(path: Path, failure: T075WorkflowError) -> None:
    """Materialize an auditable non-scientific T065 Stage-6 failure report."""

    failure_ids = list(failure.failure_ids or failure.problems)
    if not failure_ids:
        failure_ids = ["stage6:worker-failure"]
    problems = list(failure.problems) or ["Stage 6 did not complete"]
    failure_details = [dict(detail) for detail in failure.failure_details]
    if not failure_details:
        failure_details = [
            {
                "failure_id": identifier,
                "stage": failure.stage,
                "messages": list(problems),
            }
            for identifier in failure_ids
        ]
    failure_counts = {
        **dict(failure.failure_counts),
        "failure_count": len(failure_ids),
    }
    execution_evidence = {
        **dict(getattr(failure, "execution_evidence", {})),
        "status": "failed",
        "terminal": False,
        "failure_stage": failure.stage,
        "failure_ids": failure_ids,
        "failure_counts": failure_counts,
        "failure_details": failure_details,
    }
    _write_canonical_json(
        path,
        {
            "schema_id": T065_STAGE6_REPORT_SCHEMA_ID,
            "schema_version": 1,
            "paired_terminal_floor_deltas": [],
            "learned_terminal_floor_mean": 0.0,
            "expert_terminal_floor_mean": 0.0,
            "mean_terminal_floor_delta": 0.0,
            "p_positive": 0.0,
            "coverage": {
                "D": 0,
                "L": 0,
                "M": 0,
                "F": 0,
                "learned_coverage": 0.0,
                "mandatory_failure_rate": 0.0,
                "passed": False,
            },
            "learned_act2_entry_count": 0,
            "expert_act2_entry_count": 0,
            "controller_error_count": 0,
            "truncation_count": 0,
            "valid": False,
            "passed": False,
            "problems": problems,
            "failure_ids": failure_ids,
            "failure_counts": failure_counts,
            "failure_details": failure_details,
            "execution_evidence": execution_evidence,
        },
    )


def _t075_stage6_report_is_valid(path: Path, *, artifact_root: Path) -> bool:
    """Validate the content contract for a retained Stage-6 report."""

    if not _t075_actual_identity(
        {
            "path": str(path),
            "sha256": file_sha256(path) if path.is_file() else "",
            "size_bytes": path.stat().st_size if path.is_file() else -1,
        },
        artifact_root=artifact_root,
    ):
        return False
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    required = {
        "schema_id",
        "schema_version",
        "paired_terminal_floor_deltas",
        "learned_terminal_floor_mean",
        "expert_terminal_floor_mean",
        "mean_terminal_floor_delta",
        "p_positive",
        "coverage",
        "learned_act2_entry_count",
        "expert_act2_entry_count",
        "controller_error_count",
        "truncation_count",
        "valid",
        "passed",
        "problems",
        "execution_evidence",
    }
    if (
        not isinstance(value, Mapping)
        or not required.issubset(value)
        or value.get("schema_id") != T065_STAGE6_REPORT_SCHEMA_ID
        or value.get("schema_version") != 1
        or not isinstance(value.get("valid"), bool)
        or not isinstance(value.get("passed"), bool)
        or not isinstance(value.get("problems"), list)
        or not isinstance(value.get("execution_evidence"), Mapping)
    ):
        return False

    def finite_number(item: Any) -> bool:
        return (
            isinstance(item, (int, float))
            and not isinstance(item, bool)
            and math.isfinite(float(item))
        )

    deltas = value["paired_terminal_floor_deltas"]
    if not isinstance(deltas, list) or any(not finite_number(item) for item in deltas):
        return False
    if (
        any(
            not finite_number(value[field])
            for field in (
                "learned_terminal_floor_mean",
                "expert_terminal_floor_mean",
                "mean_terminal_floor_delta",
                "p_positive",
            )
        )
        or not 0.0 <= float(value["p_positive"]) <= 1.0
    ):
        return False
    if any(
        isinstance(value[field], bool)
        or not isinstance(value[field], int)
        or value[field] < 0
        for field in (
            "learned_act2_entry_count",
            "expert_act2_entry_count",
            "controller_error_count",
            "truncation_count",
        )
    ):
        return False

    coverage = value["coverage"]
    coverage_fields = {
        "D",
        "L",
        "M",
        "F",
        "learned_coverage",
        "mandatory_failure_rate",
        "passed",
    }
    if not isinstance(coverage, Mapping) or set(coverage) != coverage_fields:
        return False
    if any(
        isinstance(coverage[field], bool)
        or not isinstance(coverage[field], int)
        or coverage[field] < 0
        for field in ("D", "L", "M", "F")
    ) or any(
        not finite_number(coverage[field])
        for field in ("learned_coverage", "mandatory_failure_rate")
    ):
        return False
    expected_learned_coverage = coverage["L"] / coverage["D"] if coverage["D"] else 0.0
    expected_failure_rate = coverage["F"] / coverage["M"] if coverage["M"] else 0.0
    expected_coverage_passed = (
        coverage["D"] > 0
        and coverage["M"] > 0
        and expected_learned_coverage >= 0.60
        and expected_failure_rate <= 0.01
    )
    if (
        not math.isclose(float(coverage["learned_coverage"]), expected_learned_coverage)
        or not math.isclose(
            float(coverage["mandatory_failure_rate"]), expected_failure_rate
        )
        or coverage["passed"] is not expected_coverage_passed
    ):
        return False
    if value["valid"] and (coverage["D"] == 0 or coverage["M"] == 0):
        return False

    execution = value["execution_evidence"]
    if not value["valid"]:
        top_failure_ids = value.get("failure_ids")
        top_failure_counts = value.get("failure_counts")
        top_failure_details = value.get("failure_details")
        failure_ids = execution.get("failure_ids")
        failure_counts = execution.get("failure_counts")
        return (
            value["passed"] is False
            and bool(value["problems"])
            and execution.get("status") == "failed"
            and execution.get("terminal") is False
            and isinstance(execution.get("failure_stage"), str)
            and bool(execution["failure_stage"])
            and isinstance(failure_ids, list)
            and bool(failure_ids)
            and all(isinstance(item, str) and item for item in failure_ids)
            and isinstance(failure_counts, Mapping)
            and all(
                isinstance(item, int) and not isinstance(item, bool) and item >= 0
                for item in failure_counts.values()
            )
            and failure_counts.get("failure_count") == len(failure_ids)
            and top_failure_ids == failure_ids
            and isinstance(top_failure_counts, Mapping)
            and top_failure_counts == failure_counts
            and isinstance(top_failure_details, list)
            and len(top_failure_details) == len(failure_ids)
            and all(
                isinstance(detail, Mapping)
                and detail.get("failure_id") in failure_ids
                and isinstance(detail.get("stage"), str)
                and isinstance(detail.get("messages"), list)
                and bool(detail.get("messages"))
                for detail in top_failure_details
            )
            and execution.get("failure_details") == top_failure_details
        )

    if (
        not isinstance(execution, Mapping)
        or execution.get("worker_count") != T065_MAX_WORKERS
        or execution.get("shard_count_per_arm") != T075_STAGE6_SHARD_COUNT
        or not isinstance(execution.get("arms"), Mapping)
        or set(execution["arms"]) != {"stochastic", "expert", "learned"}
        or not isinstance(execution.get("paired_rows"), list)
        or len(execution["paired_rows"]) != 256
        or len(deltas) != 256
    ):
        return False

    arm_reports: dict[str, Mapping[str, Any]] = {}
    arm_rows_by_seed: dict[str, dict[int, Mapping[str, Any]]] = {}
    for arm in ("stochastic", "expert", "learned"):
        arm_execution = execution["arms"].get(arm)
        if not isinstance(arm_execution, Mapping):
            return False
        if (
            arm_execution.get("requested_seed_count") != 256
            or arm_execution.get("completed_row_count") != 256
            or arm_execution.get("worker_count") != T065_MAX_WORKERS
            or arm_execution.get("shard_count") != T075_STAGE6_SHARD_COUNT
            or arm_execution.get("problems") != []
            or not finite_number(arm_execution.get("wall_clock_seconds"))
        ):
            return False
        report = arm_execution.get("report")
        if not isinstance(report, Mapping):
            return False
        required_report = {
            "schema_id",
            "schema_version",
            "arm",
            "driver_seed",
            "requested_seeds",
            "rows",
            "decision_events",
            "worker_count",
            "shard_count",
            "shard_specs",
            "simulator_identity",
            "action_space",
            "controller_provenance",
            "driver_provenance",
        }
        if (
            not required_report.issubset(report)
            or report.get("schema_id") != T065_STAGE6_REPORT_SCHEMA_ID
            or report.get("schema_version") != 1
            or report.get("arm") != arm
            or report.get("worker_count") != T065_MAX_WORKERS
            or report.get("shard_count") != T075_STAGE6_SHARD_COUNT
            or report.get("driver_seed") != T065_STAGE6_DRIVER_SEED
            or not isinstance(report.get("requested_seeds"), list)
            or not isinstance(report.get("problems"), list)
            or report.get("problems") != []
        ):
            return False
        decision_count = arm_execution.get("decision_count")
        problem_count = arm_execution.get("problem_count")
        if (
            isinstance(decision_count, bool)
            or not isinstance(decision_count, int)
            or decision_count != len(report["decision_events"])
            or isinstance(problem_count, bool)
            or not isinstance(problem_count, int)
            or problem_count != 0
        ):
            return False
        # The explicit list comparison avoids accepting a report whose range
        # is merely the right length.
        if report["requested_seeds"] != list(
            range(T065_STAGE6_SEED_RANGE[0], T065_STAGE6_SEED_RANGE[1] + 1)
        ):
            return False
        rows = report.get("rows")
        specs = report.get("shard_specs")
        if (
            not isinstance(rows, list)
            or len(rows) != 256
            or not isinstance(specs, list)
            or not isinstance(report.get("decision_events"), list)
            or any(
                not isinstance(event, Mapping) for event in report["decision_events"]
            )
        ):
            return False
        if [
            row.get("simulator_seed") for row in rows if isinstance(row, Mapping)
        ] != list(range(T065_STAGE6_SEED_RANGE[0], T065_STAGE6_SEED_RANGE[1] + 1)):
            return False
        if any(
            not isinstance(row, Mapping)
            or not finite_number(row.get("terminal_floor"))
            or not isinstance(row.get("terminal"), bool)
            or row.get("terminal") is not True
            or row.get("truncated") is not False
            or row.get("controller_error") is not False
            or not isinstance(row.get("act2_entry"), bool)
            or not isinstance(row.get("problems"), list)
            or row.get("problems") != []
            for row in rows
        ):
            return False
        expected_specs = stage6_shard_ranges(arm=arm, worker_count=T065_MAX_WORKERS)
        if len(specs) != len(expected_specs):
            return False
        pids: set[int] = set()
        for expected, observed in zip(expected_specs, specs, strict=True):
            if not isinstance(observed, Mapping) or any(
                observed.get(field) != expected.get(field)
                for field in (
                    "arm",
                    "shard_index",
                    "seed_start",
                    "seed_end",
                    "seed_count",
                    "worker_count",
                )
            ):
                return False
            if (
                observed.get("requested_seeds")
                != list(range(expected["seed_start"], expected["seed_end"] + 1))
                or observed.get("completed_seeds") != observed.get("requested_seeds")
                or observed.get("requested_seed_count") != 16
                or observed.get("completed_row_count") != 16
                or observed.get("worker_kind") != "spawn-process"
                or observed.get("exit_code") != 0
                or not isinstance(observed.get("process_id"), int)
                or isinstance(observed.get("process_id"), bool)
            ):
                return False
            pids.add(observed["process_id"])
        if len(pids) != 16:
            return False
        if arm_execution.get("shard_specs") != specs:
            return False
        if report.get("simulator_identity") != _t075_pinned_simulator_identity():
            return False
        if report.get("action_space") != frozen_action_space().to_dict():
            return False
        if not _t075_stage6_arm_provenance_is_frozen(arm, report):
            return False
        arm_reports[arm] = report
        arm_rows_by_seed[arm] = {
            int(row["simulator_seed"]): row for row in rows if isinstance(row, Mapping)
        }
        events = report["decision_events"]
        if arm != "learned" and events:
            return False
        event_counts: dict[int, dict[str, int]] = {}
        for event in events:
            event_seed = event.get("simulator_seed")
            family = event.get("screen_family")
            mandatory = event.get("mandatory")
            status = event.get("status")
            expected_mandatory = family in T065_MANDATORY_FAMILIES
            if (
                isinstance(event_seed, bool)
                or not isinstance(event_seed, int)
                or event_seed not in arm_rows_by_seed[arm]
                or not isinstance(family, str)
                or not family
                or not isinstance(mandatory, bool)
                or not isinstance(status, str)
                or not status
                or mandatory != expected_mandatory
            ):
                return False
            if mandatory and status not in {"learned_success", "learned_failure"}:
                return False
            if not mandatory and status != "unsupported_fallback":
                return False
            if status == "learned_success":
                action_index = event.get("action_index")
                if (
                    isinstance(action_index, bool)
                    or not isinstance(action_index, int)
                    or action_index < 0
                    or not finite_number(event.get("score"))
                ):
                    return False
            elif status == "learned_failure":
                if (
                    not isinstance(event.get("error"), str)
                    or not event["error"].strip()
                ):
                    return False
            else:
                action_index = event.get("action_index")
                if (
                    isinstance(action_index, bool)
                    or not isinstance(action_index, int)
                    or action_index < 0
                    or not isinstance(event.get("reason"), str)
                    or not event["reason"].strip()
                ):
                    return False
            if event.get("battle") is not None and event.get("battle") is not False:
                return False
            counts = event_counts.setdefault(
                event_seed,
                {
                    "learned_decision_count": 0,
                    "intentional_unsupported_fallback_count": 0,
                    "supported_failure_count": 0,
                },
            )
            if status in {"learned_success", "learned_failure"}:
                counts["learned_decision_count"] += 1
            elif status == "unsupported_fallback":
                counts["intentional_unsupported_fallback_count"] += 1
            if status == "learned_failure":
                counts["supported_failure_count"] += 1
        if arm == "learned":
            for event_seed, row in arm_rows_by_seed[arm].items():
                row_counts = {}
                for field in (
                    "learned_decision_count",
                    "intentional_unsupported_fallback_count",
                    "supported_failure_count",
                ):
                    count = row.get(field)
                    if (
                        isinstance(count, bool)
                        or not isinstance(count, int)
                        or count < 0
                    ):
                        return False
                    row_counts[field] = count
                if row_counts != event_counts.get(
                    event_seed,
                    {
                        "learned_decision_count": 0,
                        "intentional_unsupported_fallback_count": 0,
                        "supported_failure_count": 0,
                    },
                ):
                    return False

    paired_rows = execution["paired_rows"]
    if [
        row.get("simulator_seed") for row in paired_rows if isinstance(row, Mapping)
    ] != list(range(T065_STAGE6_SEED_RANGE[0], T065_STAGE6_SEED_RANGE[1] + 1)) or any(
        not isinstance(row, Mapping)
        or not finite_number(row.get("learned_terminal_floor"))
        or not finite_number(row.get("expert_terminal_floor"))
        for row in paired_rows
    ):
        return False
    expected_deltas: list[float] = []
    for row in paired_rows:
        seed = int(row["simulator_seed"])
        learned_row = arm_rows_by_seed["learned"].get(seed)
        expert_row = arm_rows_by_seed["expert"].get(seed)
        if learned_row is None or expert_row is None:
            return False
        if (
            row.get("learned_terminal") is not learned_row.get("terminal")
            or row.get("expert_terminal") is not expert_row.get("terminal")
            or row.get("learned_act2_entry") is not learned_row.get("act2_entry")
            or row.get("expert_act2_entry") is not expert_row.get("act2_entry")
            or row.get("truncated")
            is not (learned_row.get("truncated") or expert_row.get("truncated"))
            or row.get("controller_error")
            is not (
                learned_row.get("controller_error")
                or expert_row.get("controller_error")
            )
            or row.get("learned_terminal_floor") != learned_row.get("terminal_floor")
            or row.get("expert_terminal_floor") != expert_row.get("terminal_floor")
        ):
            return False
        expected_deltas.append(
            float(learned_row["terminal_floor"] - expert_row["terminal_floor"])
        )
    if any(
        not math.isclose(float(actual), expected)
        for actual, expected in zip(deltas, expected_deltas, strict=True)
    ):
        return False
    expected_learned_mean = statistics.fmean(
        arm_rows_by_seed["learned"][seed]["terminal_floor"]
        for seed in sorted(arm_rows_by_seed["learned"])
    )
    expected_expert_mean = statistics.fmean(
        arm_rows_by_seed["expert"][seed]["terminal_floor"]
        for seed in sorted(arm_rows_by_seed["expert"])
    )
    expected_delta_mean = statistics.fmean(expected_deltas)
    expected_p_positive = matched_bootstrap_probability(
        expected_deltas, replicates=10000, seed=655002
    )
    if any(
        not math.isclose(float(value[field]), expected, rel_tol=0.0, abs_tol=1e-12)
        for field, expected in (
            ("learned_terminal_floor_mean", expected_learned_mean),
            ("expert_terminal_floor_mean", expected_expert_mean),
            ("mean_terminal_floor_delta", expected_delta_mean),
            ("p_positive", expected_p_positive),
        )
    ):
        return False
    expected_learned_act2 = sum(
        row["act2_entry"] for row in arm_rows_by_seed["learned"].values()
    )
    expected_expert_act2 = sum(
        row["act2_entry"] for row in arm_rows_by_seed["expert"].values()
    )
    expected_errors = sum(
        row["controller_error"] or arm_rows_by_seed["expert"][seed]["controller_error"]
        for seed, row in arm_rows_by_seed["learned"].items()
    )
    expected_truncation = sum(
        row["truncated"] or arm_rows_by_seed["expert"][seed]["truncated"]
        for seed, row in arm_rows_by_seed["learned"].items()
    )
    if (
        value["learned_act2_entry_count"] != expected_learned_act2
        or value["expert_act2_entry_count"] != expected_expert_act2
        or value["controller_error_count"] != expected_errors
        or value["truncation_count"] != expected_truncation
    ):
        return False
    learned_coverage = compute_learned_coverage(
        arm_reports["learned"]["decision_events"]
    ).to_dict()
    if any(
        coverage[field] != learned_coverage[field]
        for field in ("D", "L", "M", "F", "passed")
    ):
        return False
    if any(
        not math.isclose(float(coverage[field]), float(learned_coverage[field]))
        for field in ("learned_coverage", "mandatory_failure_rate")
    ):
        return False
    expected_passed = (
        float(value["mean_terminal_floor_delta"]) > 0.0
        and float(value["p_positive"]) >= 0.80
        and value["learned_act2_entry_count"] >= value["expert_act2_entry_count"]
        and value["controller_error_count"] == 0
        and value["truncation_count"] == 0
        and coverage["passed"]
        and (
            value["learned_act2_entry_count"] > value["expert_act2_entry_count"]
            or float(value["p_positive"]) >= 0.95
        )
    )
    return value["passed"] is expected_passed


def _failed_stage_artifact_paths(
    args: argparse.Namespace, failure: T065CaseD
) -> dict[str, Path]:
    paths: dict[str, Path] = {}
    if failure.stage == "stage0-preflight":
        candidate = (
            args.output
            if args.command == "preflight"
            else getattr(args, "preflight", None)
        )
        if isinstance(candidate, Path) and candidate.is_file():
            paths["failed_preflight_artifact"] = candidate
    output_path = getattr(args, "output", None)
    if isinstance(output_path, Path) and output_path.is_file():
        paths["failed_current_artifact"] = output_path
    if failure.stage == "stage2-target":
        validation_path = getattr(args, "validation_report", None)
        if isinstance(validation_path, Path) and validation_path.is_file():
            paths["failed_stage3_validation"] = validation_path
    return paths


def _target_src_path() -> Path:
    return Path(__file__).resolve().parents[2]


def _wsl_path(path: Path) -> str:
    raw_value = str(path).replace("\\", "/")
    if raw_value.startswith("/"):
        return raw_value
    if (
        len(raw_value) >= 3
        and raw_value[0].isalpha()
        and raw_value[1] == ":"
        and raw_value[2] == "/"
    ):
        return f"/mnt/{raw_value[0].lower()}{raw_value[2:]}"
    value = str(path.resolve()).replace("\\", "/")
    if len(value) >= 3 and value[1] == ":" and value[2] == "/":
        return f"/mnt/{value[0].lower()}{value[2:]}"
    return value


def _manifest_artifact_paths(
    args: argparse.Namespace,
    *,
    decision_path: Path | None = None,
    case_d: bool = False,
    failure: T065CaseD | None = None,
) -> dict[str, Path]:
    if case_d:
        paths = _failed_stage_artifact_paths(args, failure or T065CaseD("unknown", ()))
    else:
        paths = _preceding_artifact_paths(args)
        output_path = getattr(args, "output", None)
        if isinstance(output_path, Path) and output_path.is_file():
            paths["current_output"] = output_path
        if args.command == "select":
            selection_path = args.manifest or Path(f"{args.output}.manifest.json")
            if selection_path.is_file():
                paths["source_selection_manifest"] = selection_path
        if args.command == "train":
            for model_seed in (653001, 653002):
                checkpoint = args.checkpoint_directory / f"model-{model_seed}.pt"
                if checkpoint.is_file():
                    paths[f"checkpoint_{model_seed}"] = checkpoint
    if decision_path is not None and decision_path.is_file():
        paths["terminal_decision_report"] = decision_path
    return paths


def _regeneration_command(args: argparse.Namespace) -> str:
    command_args = _canonical_command_args(args)
    rendered: list[str] = []
    for token in command_args:
        if isinstance(token, str) and ("\\" in token or ":" in token):
            rendered.append(_wsl_path(Path(token)))
        else:
            rendered.append(str(token))
    shard_count = {
        "collect": 16,
        "select": 0,
        "target": 16,
        "train": 0,
        "evaluate": 16,
        "preflight": 1,
    }[args.command]
    worker_count = 16 if shard_count else 1
    seed_range = {
        "collect": f"{getattr(args, 'seed_start', T065_SOURCE_SEED_RANGE[0])}.."
        f"{getattr(args, 'seed_end', T065_SOURCE_SEED_RANGE[1])}",
        "select": "source-artifacts-from-collect",
        "target": "selected-state-index=0..319",
        "train": "model-seeds=653001,653002",
        "evaluate": "stage6-seeds=651001..651256",
        "preflight": "simulator-seed=1;model-seed=653001",
    }[args.command]
    metadata = (
        f"# frozen_shards={shard_count} frozen_worker_count={worker_count} "
        f"frozen_seed_range={seed_range} pinned_simulator=sts_lightspeed"
    )
    pythonpath = f"{T065_LIGHTSPEED_BUILD_PYTHONPATH}:{_wsl_path(_target_src_path())}"
    return "wsl.exe -d Ubuntu -e bash -lc " + shlex.quote(
        "set -euo pipefail; "
        f"export PYTHONPATH={shlex.quote(pythonpath)}; "
        f"{T065_TRAINING_INTERPRETER} -m "
        f"sts_combat_rl.commands.non_combat_learning {shlex.join(rendered)}; "
        + metadata
    )


def _canonical_command_args(args: argparse.Namespace) -> list[str]:
    """Render every relevant frozen/default argument into the replay command."""

    tokens = [args.command]

    def add(flag: str, value: Any) -> None:
        if value is None:
            return
        tokens.extend((flag, str(value)))

    add("--output", getattr(args, "output", None))
    if args.command == "preflight":
        if args.simulator_runtime:
            tokens.append("--simulator-runtime")
        if args.torch_runtime:
            tokens.append("--torch-runtime")
        add("--sim-seed", args.sim_seed)
        add("--ascension", args.ascension)
    elif args.command == "collect":
        add("--arm", args.arm)
        add("--seed-start", args.seed_start)
        add("--seed-end", args.seed_end)
        add("--sim-seed", args.sim_seed)
        add("--ascension", args.ascension)
        add("--preflight", args.preflight)
    elif args.command == "select":
        for path in args.input:
            add("--input", path)
        add("--manifest", args.manifest or Path(f"{args.output}.manifest.json"))
        add("--preflight", args.preflight)
    elif args.command == "target":
        add("--states", args.states)
        add("--sim-seed", args.sim_seed)
        add("--ascension", args.ascension)
        add("--preflight", args.preflight)
    elif args.command == "train":
        add("--target-table", args.target_table)
        add("--checkpoint-directory", args.checkpoint_directory)
        add("--preflight", args.preflight)
    elif args.command == "evaluate":
        add("--target-table", args.target_table)
        add("--checkpoint-directory", args.checkpoint_directory)
        if args.run_stage6:
            tokens.append("--run-stage6")
        add("--sim-seed", args.sim_seed)
        add("--ascension", args.ascension)
        add("--preflight", args.preflight)
    else:  # pragma: no cover - parser restricts the command set
        raise ValueError(f"unsupported T065 command {args.command!r}")

    for path in getattr(args, "preceding_manifest", None) or ():
        add("--preceding-manifest", path)
    add("--decision-report", _decision_report_path(args))
    add("--retention-manifest", _retention_manifest_path(args))
    return tokens


def _write_workflow_manifest(
    args: argparse.Namespace,
    *,
    stage: str,
    decision_path: Path | None = None,
    case_d: bool = False,
    failure: T065CaseD | None = None,
    terminal: bool = False,
    terminal_case: str | None = None,
) -> dict[str, Any]:
    artifacts = _manifest_artifact_paths(
        args, decision_path=decision_path, case_d=case_d, failure=failure
    )
    evidence: dict[str, Any] = {
        "status": "case_d" if case_d else "completed",
        "stage": stage,
        "command": _regeneration_command(args),
        "artifact_roles": sorted(artifacts),
        "preceding_stage_manifests": _preceding_manifest_identities(args),
        "terminal": terminal,
    }
    if terminal_case is not None:
        evidence["terminal_case"] = terminal_case
    if failure is not None:
        evidence.update(
            {
                "failure_ids": list(failure.failure_ids or failure.problems),
                "failure_counts": dict(failure.failure_counts),
                "downstream_skipped": failure.to_decision_report()[
                    "downstream_skipped"
                ],
                "no_replacement": True,
                "failed_stage_artifacts": dict(failure.failed_stage_artifacts),
            }
        )
    manifest = write_t065_manifest(
        _retention_manifest_path(args),
        approved_spec_commit=T065_APPROVED_SPEC_COMMIT,
        simulator_identity=(
            failure.simulator_identity
            if failure is not None and failure.simulator_identity
            else lightspeed_source_identity_dict()
        ),
        artifacts=artifacts,
        regeneration_commands=(_regeneration_command(args),),
        stage_evidence={stage: evidence},
        preceding_stage_manifests=_preceding_manifest_identities(args),
        failed_stage_artifacts=(
            dict(failure.failed_stage_artifacts) if failure is not None else {}
        ),
    )
    print(f"T065 retention manifest: {_retention_manifest_path(args)}", file=sys.stderr)
    return manifest


def _handle_case_d(args: argparse.Namespace, failure: T065CaseD) -> None:
    failure.preceding_stage_manifests.update(_preceding_manifest_identities(args))
    failure.failed_stage_artifacts.update(
        _artifact_identities(_failed_stage_artifact_paths(args, failure))
    )
    decision_path = _decision_report_path(args)
    write_t065_terminal_decision_report(
        decision_path,
        failure,
        simulator_identity=(
            failure.simulator_identity or lightspeed_source_identity_dict()
        ),
    )
    _write_workflow_manifest(
        args,
        stage=failure.stage,
        decision_path=decision_path,
        case_d=True,
        failure=failure,
        terminal=True,
        terminal_case="D",
    )
    print(f"T065 Case D decision report: {decision_path}", file=sys.stderr)


def _t075_failure_terminal_stage(args: argparse.Namespace, failure_stage: str) -> str:
    if failure_stage in T075_STAGE_ORDER[:-1]:
        return failure_stage
    mapped = {
        "source-input-reuse": "stage0-reuse",
        "cohort-ownership": "stage1-selection-replay",
        "replay": "stage1-selection-replay",
        "target-sharding": "stage2-target",
        "stage3-model-input-lineage-firewall": "stage2-target",
        "stage6": "stage6-eval",
    }.get(failure_stage)
    if mapped is not None:
        return mapped
    command_boundary = {
        "preflight": "stage0-preflight",
        "validate-reuse": "stage0-reuse",
        "select": "stage1-selection-replay",
        "target": "stage2-target",
        "train": "stage4-train",
        "evaluate": (
            "stage6-eval" if getattr(args, "run_stage6", False) else "stage5-gate"
        ),
    }.get(getattr(args, "command", ""))
    if command_boundary is None:
        raise T075WorkflowError(
            "terminal-finalize", [f"unknown T075 failure stage: {failure_stage}"]
        )
    return command_boundary


def _handle_t075_case_d(args: argparse.Namespace, failure: T075WorkflowError) -> None:
    """Materialize the single canonical T075 terminal Case-D report."""

    decision_path = getattr(args, "decision_report", None) or _decision_report_path(
        args
    )
    if decision_path.is_file():
        try:
            existing = json.loads(decision_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            existing = None
        existing_retention = getattr(args, "retention_manifest", None)
        if _t075_terminal_decision_is_valid(
            existing,
            artifact_root=decision_path.parent,
            retention_path=(
                existing_retention if isinstance(existing_retention, Path) else None
            ),
        ):
            print(
                f"T075 terminal decision already exists: {decision_path}",
                file=sys.stderr,
            )
            return
    terminal_stage = _t075_failure_terminal_stage(args, failure.stage)
    stage6_report_path: Path | None = None
    if terminal_stage == "stage6-eval":
        candidate = getattr(args, "output", None)
        stage6_report_path = (
            candidate
            if isinstance(candidate, Path) and candidate != decision_path
            else decision_path.with_name("stage6-complete-run-report.json")
        )
        _t075_write_stage6_failure_report(stage6_report_path, failure)

    failure_evidence_path = decision_path.with_name(
        f".{decision_path.stem}.failure-evidence.json"
    )
    failure_ids = list(failure.failure_ids or failure.problems)
    if not failure_ids:
        failure_ids = (
            ["stage6:worker-failure"]
            if terminal_stage == "stage6-eval"
            else ["workflow:failure"]
        )
    problems = list(failure.problems) or ["T075 workflow failed"]
    failure_counts = {
        **dict(failure.failure_counts),
        "failure_count": len(failure_ids),
    }
    failure_details = list(failure.failure_details)
    if not failure_details:
        failure_details = [
            {
                "failure_id": failure_ids[0],
                "stage": terminal_stage,
                "messages": problems,
            }
        ]
    _write_canonical_json(
        failure_evidence_path,
        {
            "schema_id": "t075-failure-evidence-v1",
            "schema_version": 1,
            "task_id": T075_TASK_ID,
            "approved_t075_spec_commit": T075_APPROVED_SPEC_COMMIT,
            "code_head": _code_head_for_artifact_root(args),
            "failure_stage": failure.stage,
            "problems": problems,
            "failure_ids": failure_ids,
            "failure_counts": failure_counts,
        },
    )
    failed_artifacts = _failed_stage_artifact_paths(args, failure)
    if terminal_stage == "stage6-eval":
        # The output is a real, content-validated failed Stage-6 report rather
        # than a terminal-decision payload.  Keep one stable role for it.
        failed_artifacts.pop("failed_current_artifact", None)
        assert stage6_report_path is not None
        failed_artifacts["stage6_report"] = stage6_report_path
    failed_artifacts["failure_evidence"] = failure_evidence_path
    parent_identities = _artifact_identities(failed_artifacts)
    parent_identities.update(_preceding_manifest_identities(args))
    # A Case-D retention must retain the exact inputs which made the failure
    # auditable.  Listing them only as decision parents is insufficient: the
    # finalizer also requires every parent identity to occur in stage output
    # identities.  Add the same files as stage-local outputs, preserving their
    # content identity rather than inventing a placeholder artifact.
    retention_artifacts = dict(failed_artifacts)
    for role, identity in parent_identities.items():
        if not isinstance(identity, Mapping) or not isinstance(
            identity.get("path"), str
        ):
            continue
        parent_path = _t075_resolve_identity_path(
            identity["path"], artifact_root=decision_path.parent
        )
        if parent_path is not None and parent_path not in retention_artifacts.values():
            retention_artifacts[f"parent_{role}"] = parent_path
    execution_stages = T075_STAGE_ORDER[:-1]
    terminal_index = execution_stages.index(terminal_stage)
    reached_stages = list(execution_stages[: terminal_index + 1])
    skipped_stages = list(execution_stages[terminal_index + 1 :])
    skipped_commands, skipped_evidence = _t075_skipped_stage_contract(
        args, skipped_stages, "not reached by terminal decision"
    )
    report = {
        "schema_id": T075_TERMINAL_DECISION_SCHEMA_ID,
        "schema_version": 1,
        "task_id": T075_TASK_ID,
        "approved_t075_spec_commit": T075_APPROVED_SPEC_COMMIT,
        "planner_baseline": T075_PLANNER_BASELINE,
        "code_head": _code_head_for_artifact_root(args),
        "terminal_case": "D",
        "terminal_stage": terminal_stage,
        "failure_stage": (
            failure.stage
            if failure.stage
            in {
                "source-input-reuse",
                "cohort-ownership",
                "replay",
                "target-sharding",
                "stage3-model-input-lineage-firewall",
                "stage6",
                *execution_stages,
            }
            else terminal_stage
        ),
        "reason_code": (
            "stage3-validation-failed"
            if "stage3-validation-failed" in failure.failure_ids
            else "frozen-contract-failure"
        ),
        "summary": "; ".join(problems),
        "reached_stages": reached_stages,
        "skipped_stages": skipped_stages,
        "skipped_stage_commands": skipped_commands,
        "skipped_stage_evidence": skipped_evidence,
        "parent_artifact_identities": parent_identities,
        "stage3_validation_status": (
            "failed"
            if "stage3-validation-failed" in failure.failure_ids
            else "not_reached"
        ),
        "stage5_gate_status": "not_reached",
        "stage6_status": (
            "failed" if terminal_stage == "stage6-eval" else "not_reached"
        ),
        "stage6_report_identity": (
            parent_identities.get("stage6_report")
            if terminal_stage == "stage6-eval"
            else None
        ),
        "recommendation": "repair the frozen T075 contract failure and rerun",
        "failure_ids": failure_ids,
        "failure_counts": failure_counts,
        "failure_details": failure_details,
        "problems": problems,
    }
    _write_canonical_json(decision_path, report)
    retention_path = getattr(args, "retention_manifest", None)
    if isinstance(retention_path, Path):
        partial_execution = dict(getattr(failure, "execution_evidence", {}))
        stage6_partial = partial_execution if terminal_stage == "stage6-eval" else {}
        _write_t075_stage_retention(
            args,
            stage=terminal_stage,
            artifacts=retention_artifacts,
            evidence={
                **_t075_execution_evidence(
                    args, status="failed", terminal=False, exit_code=1, executed=True
                ),
                "executed": True,
                "status": "failed",
                "terminal": False,
                "exit_code": 1,
                "counts": failure_counts,
                "problems": problems,
                "parent_identities": _preceding_manifest_identities(args),
                "shard_count": stage6_partial.get("shard_count", 0),
                "worker_count": stage6_partial.get("worker_count", 0),
                "ranges": stage6_partial.get("ranges", []),
                "per_shard": stage6_partial.get("per_shard", []),
                "partial_spawn_failure": stage6_partial.get(
                    "partial_spawn_failure", False
                ),
            },
            terminal_case="D",
        )


def _require_preflight(args: argparse.Namespace) -> dict[str, Any]:
    path = getattr(args, "preflight", None)
    if not isinstance(path, Path):
        raise T065CaseD(
            "stage0-preflight",
            ["workflow command did not receive an explicit --preflight artifact"],
            failure_ids=("preflight:missing-argument",),
            failure_counts={"missing_preflight": 1},
        )
    return validate_t065_preflight(path)


def _require_frozen_simulator_args(args: argparse.Namespace) -> None:
    if args.sim_seed != 1 or args.ascension != 20:
        raise ValueError("T065 simulator configuration is frozen at seed=1, A20")


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":  # pragma: no cover - exercised by command smoke
    raise SystemExit(main())
