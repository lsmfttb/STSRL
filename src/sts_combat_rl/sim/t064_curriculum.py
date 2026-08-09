"""Deterministic T064 curriculum identity, selection, scheduling, and decisions.

This module deliberately contains no simulator, teacher, evaluation, or training
implementation.  It prepares and validates the compact T064 control documents
while those operations continue to use their existing repository contracts.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping, Sequence
import hashlib
import json
import math
from pathlib import Path
import re
from typing import Any, TextIO

from sts_combat_rl.sim.battle_start_pool import BattleStartCheckpointRecord


CURRICULUM_MANIFEST_SCHEMA_ID = "t064-curriculum-manifest-v1"
TRAINING_RUN_REPORT_SCHEMA_ID = "t064-training-run-report-v1"
STAGE_SUMMARY_SCHEMA_ID = "t064-stage-summary-v1"
TRANSFER_DECISION_SCHEMA_ID = "t064-transfer-decision-v1"
T064_FORMAT_VERSION = 1

CURRICULUM_MANIFEST_FILENAME = "t064-curriculum-manifest.json"
TRAINING_RUN_REPORT_FILENAME = "t064-training-run-report.json"
STAGE_SUMMARY_FILENAME = "t064-stage-summary.json"
TRANSFER_DECISION_FILENAME = "t064-transfer-decision.json"
COMPACT_FILENAMES = (
    CURRICULUM_MANIFEST_FILENAME,
    TRAINING_RUN_REPORT_FILENAME,
    STAGE_SUMMARY_FILENAME,
    TRANSFER_DECISION_FILENAME,
)

COMPLETE_SOURCE_IDENTITY_SCHEMA_ID = "t064-complete-source-identity-v1"
BUCKET_STRONG = "strong_later_act"
BUCKET_MEDIUM = "medium_later_act"
BUCKET_ANCHOR = "anchor"
BUCKETS = (BUCKET_STRONG, BUCKET_MEDIUM, BUCKET_ANCHOR)
ARM_STATIC = "static_mixture_v1"
ARM_CURRICULUM = "assistance_annealed_curriculum_v1"
TRAINING_SEEDS = (64001, 64002)
TRAINING_RUN_ORDER = tuple(
    (arm, seed) for seed in TRAINING_SEEDS for arm in (ARM_STATIC, ARM_CURRICULUM)
)
PHASE_TOKEN_PATTERNS = {
    ARM_STATIC: (
        (BUCKET_STRONG, BUCKET_MEDIUM, BUCKET_ANCHOR),
        (BUCKET_STRONG, BUCKET_MEDIUM, BUCKET_ANCHOR),
        (BUCKET_STRONG, BUCKET_MEDIUM, BUCKET_ANCHOR),
    ),
    ARM_CURRICULUM: (
        (BUCKET_STRONG, BUCKET_STRONG, BUCKET_MEDIUM),
        (BUCKET_STRONG, BUCKET_MEDIUM, BUCKET_ANCHOR),
        (BUCKET_MEDIUM, BUCKET_ANCHOR, BUCKET_ANCHOR),
    ),
}
RECOMMENDATION_CASE_A = "T063-oracle-guided-public-battle-learning"
RECOMMENDATION_CASE_B = "T065-learned-non-combat-policy-v1"
_SHA256_RE = re.compile(r"[0-9a-f]{64}")
TRANSFER_GATE_NAMES = (
    "t052_prior_value_aggregate_margin",
    "t052_per_seed_non_regression",
    "t052_subset_non_regression",
    "t044_assist_hp50_model_guided_margin",
    "t044_assist_hp50_raw_policy_non_regression",
    "t044_assist_0_model_guided_non_regression",
)


def canonical_json_bytes(value: Any) -> bytes:
    """Return the exact canonical JSON representation used by T064 hashes."""

    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def action_trace_identity_sha256(record: BattleStartCheckpointRecord) -> str:
    """Reuse occurrence-safe selected action identities for one trace hash."""

    rows: list[dict[str, Any]] = []
    for decision_index, raw in enumerate(record.action_trace):
        if not isinstance(raw, Mapping):
            raise ValueError("action trace identity must be an object")
        stable_id = raw.get("stable_id")
        occurrence = raw.get("occurrence")
        if not isinstance(stable_id, str) or not stable_id:
            raise ValueError("action trace identity is missing stable_id")
        if isinstance(occurrence, bool) or not isinstance(occurrence, int):
            raise ValueError("action trace identity occurrence must be an integer")
        if occurrence < 0:
            raise ValueError("action trace identity occurrence cannot be negative")
        identity = dict(raw)
        if (
            identity.get("stable_id") != stable_id
            or identity.get("occurrence") != occurrence
        ):
            raise ValueError("action trace identity is not occurrence-safe")
        rows.append({"decision_index": decision_index, "selected_action": identity})
    return canonical_sha256(rows)


def complete_source_identity(
    record: Any,
    *,
    source_arm: str | None = None,
) -> dict[str, Any]:
    """Build the frozen complete identity without guessing absent provenance."""

    metadata = getattr(record, "structural_metadata", None)
    if not isinstance(metadata, Mapping):
        raise ValueError("structural_metadata must be an object")
    existing_trace = metadata.get("action_trace_identity")
    if existing_trace is None:
        trace_identity = action_trace_identity_sha256(record)
    elif isinstance(existing_trace, str) and existing_trace:
        trace_identity = existing_trace
    else:
        raise ValueError("existing action_trace_identity must be a non-empty string")
    assistance_level = metadata.get("assistance_level", "")
    if not isinstance(assistance_level, str):
        raise ValueError("assistance_level must be a string when present")
    mapped_source_arm = (
        metadata.get("source_arm", "") if source_arm is None else source_arm
    )
    if not isinstance(mapped_source_arm, str):
        raise ValueError("source_arm must be a string when present")
    identity = {
        "schema_id": COMPLETE_SOURCE_IDENTITY_SCHEMA_ID,
        "source_checkpoint_id": record.source_checkpoint_id,
        "source_seed": record.source_seed,
        "source_run_id": record.source_run_id,
        "source_battle_index": record.source_battle_index,
        "action_trace_identity": trace_identity,
        "distribution_kind": getattr(
            record,
            "distribution_kind",
            getattr(record, "source_distribution_kind", None),
        ),
        "assistance_level": assistance_level,
        "source_arm": mapped_source_arm,
        "checkpoint_information_regime": record.checkpoint_information_regime,
    }
    _validate_complete_identity(identity)
    identity["complete_identity_sha256"] = canonical_sha256(identity)
    return identity


def static_source_exclusion_reasons(record: BattleStartCheckpointRecord) -> list[str]:
    """Return outcome-blind eligibility failures visible in current artifacts."""

    metadata = record.structural_metadata
    reasons: list[str] = []
    if metadata.get("ascension") != 20:
        reasons.append("not_a20")
    if record.checkpoint_information_regime != "full_simulator_state_oracle_like":
        reasons.append("incompatible_information_regime")
    if record.public_context_status != "available" or not record.public_run_context:
        reasons.append("public_context_unavailable")
    if not record.battle_completed:
        reasons.append("structured_outcome_incomplete")
    if record.completed_battle_resource_outcome_status != "available":
        reasons.append("structured_resource_outcome_unavailable")
    for key, provenance in (
        ("source_controller", record.source_controller_provenance),
        ("battle_controller", record.source_battle_controller_provenance),
        ("non_combat_controller", record.source_non_combat_controller_provenance),
    ):
        if not provenance:
            reasons.append(f"{key}_provenance_missing")
    return reasons


def source_descriptor(
    record: BattleStartCheckpointRecord,
    *,
    component: str,
    source_path: str,
) -> dict[str, Any]:
    identity = complete_source_identity(record)
    metadata = record.structural_metadata
    floor_bucket = _floor_bucket(metadata.get("floor"))
    return {
        "component": component,
        "source_path": source_path,
        "source_record_index": record.record_index,
        "complete_identity": identity,
        "complete_identity_sha256": identity["complete_identity_sha256"],
        "act": metadata.get("act"),
        "room_type": metadata.get("room_type"),
        "encounter_id": metadata.get("encounter_id"),
        "floor_bucket": floor_bucket,
        "exclusion_reasons": static_source_exclusion_reasons(record),
        "fresh_restore_status": "pending",
    }


def select_curriculum_buckets(
    descriptors: Sequence[Mapping[str, Any]],
    *,
    holdout_identity_sha256s: Iterable[str],
) -> dict[str, list[dict[str, Any]]]:
    """Select the three frozen disjoint buckets from audited descriptors."""

    holdouts = set(holdout_identity_sha256s)
    eligible: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in descriptors:
        item = dict(raw)
        identity = item.get("complete_identity_sha256")
        if not isinstance(identity, str) or not _SHA256_RE.fullmatch(identity):
            raise ValueError("source descriptor has invalid complete identity")
        reasons = list(item.get("exclusion_reasons", []))
        if identity in holdouts:
            reasons.append("holdout_overlap")
        if identity in seen:
            reasons.append("duplicate_complete_identity")
        seen.add(identity)
        item["exclusion_reasons"] = sorted(set(str(value) for value in reasons))
        if not item["exclusion_reasons"]:
            eligible.append(item)

    def ordered(component: str, *, later: bool = False) -> list[dict[str, Any]]:
        rows = [
            row
            for row in eligible
            if row.get("component") == component
            and (not later or isinstance(row.get("act"), int) and row["act"] >= 2)
        ]
        return sorted(rows, key=lambda row: row["complete_identity_sha256"])

    strong = ordered("assist_hp75_potion", later=True)[:160]
    medium = (
        ordered("assist_hp50", later=True)[:32]
        + ordered("assist_hp50_potion_elite_boss", later=True)[:32]
    )
    anchor_candidates = ordered("assist_0")
    strata: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in anchor_candidates:
        key = canonical_json_bytes(
            [
                row.get("act"),
                row.get("room_type"),
                row.get("encounter_id"),
                row.get("floor_bucket"),
            ]
        ).decode("utf-8")
        strata[key].append(row)
    anchor: list[dict[str, Any]] = []
    offsets = {key: 0 for key in strata}
    while len(anchor) < 256:
        progressed = False
        for key in sorted(strata):
            offset = offsets[key]
            if offset < len(strata[key]):
                anchor.append(strata[key][offset])
                offsets[key] += 1
                progressed = True
                if len(anchor) == 256:
                    break
        if not progressed:
            break
    selected = {BUCKET_STRONG: strong, BUCKET_MEDIUM: medium, BUCKET_ANCHOR: anchor}
    flattened = [
        row["complete_identity_sha256"]
        for bucket in BUCKETS
        for row in selected[bucket]
    ]
    if len(flattened) != len(set(flattened)):
        raise ValueError("selected curriculum buckets are not disjoint")
    return selected


def contiguous_ranges(count: int, shards: int = 16) -> tuple[str, ...]:
    if isinstance(count, bool) or not isinstance(count, int) or count < 0:
        raise ValueError("record count must be a non-negative integer")
    if isinstance(shards, bool) or not isinstance(shards, int) or shards <= 0:
        raise ValueError("shard count must be positive")
    base, remainder = divmod(count, shards)
    ranges: list[str] = []
    start = 0
    for index in range(shards):
        end = start + base + (1 if index < remainder else 0)
        ranges.append(f"{start}:{end}")
        start = end
    return tuple(ranges)


def source_adequacy(
    selected: Mapping[str, Sequence[Mapping[str, Any]]],
    *,
    selected_duplicate_complete_identity_count: int = 0,
    selected_holdout_overlap_count: int = 0,
) -> bool:
    if (
        isinstance(selected_duplicate_complete_identity_count, bool)
        or not isinstance(selected_duplicate_complete_identity_count, int)
        or selected_duplicate_complete_identity_count < 0
        or isinstance(selected_holdout_overlap_count, bool)
        or not isinstance(selected_holdout_overlap_count, int)
        or selected_holdout_overlap_count < 0
    ):
        raise ValueError("T064 source-audit counts must be non-negative integers")
    later = len(selected.get(BUCKET_STRONG, ())) + len(selected.get(BUCKET_MEDIUM, ()))
    anchor = len(selected.get(BUCKET_ANCHOR, ()))
    identities = [
        str(row.get("complete_identity_sha256"))
        for bucket in BUCKETS
        for row in selected.get(bucket, ())
    ]
    return (
        later >= 128
        and anchor == 256
        and len(identities) == len(set(identities))
        and selected_duplicate_complete_identity_count == 0
        and selected_holdout_overlap_count == 0
    )


def build_bucket_exposure_sequence(
    identities: Sequence[str], *, seed: int, bucket: str, draws: int = 9600
) -> tuple[str, ...]:
    if bucket not in BUCKETS or not identities:
        raise ValueError("exposure sequence requires a non-empty known bucket")
    if len(set(identities)) != len(identities):
        raise ValueError("bucket identities must be unique")
    sequence: list[str] = []
    cycle = 0
    while len(sequence) < draws:
        ordered = sorted(
            identities,
            key=lambda identity: hashlib.sha256(
                f"{seed}:{bucket}:{cycle}:{identity}".encode()
            ).hexdigest(),
        )
        sequence.extend(ordered)
        cycle += 1
    return tuple(sequence[:draws])


def build_ordered_batch_plan(
    selected: Mapping[str, Sequence[Mapping[str, Any]]], *, seed: int, arm: str
) -> dict[str, Any]:
    if arm not in PHASE_TOKEN_PATTERNS:
        raise ValueError("unknown curriculum training arm")
    sequences = {
        bucket: build_bucket_exposure_sequence(
            [str(row["complete_identity_sha256"]) for row in selected[bucket]],
            seed=seed,
            bucket=bucket,
        )
        for bucket in BUCKETS
    }
    offsets = {bucket: 0 for bucket in BUCKETS}
    phases: list[list[str]] = []
    for pattern in PHASE_TOKEN_PATTERNS[arm]:
        draws: list[str] = []
        for _ in range(3200):
            for bucket in pattern:
                draws.append(sequences[bucket][offsets[bucket]])
                offsets[bucket] += 1
        if len(draws) != 9600:
            raise AssertionError("T064 phase draw cardinality changed")
        phases.append(draws)
    if offsets != {bucket: 9600 for bucket in BUCKETS}:
        raise ValueError("T064 batch plan did not consume exact bucket exposures")
    batches = [
        phase[start : start + 32]
        for phase in phases
        for start in range(0, len(phase), 32)
    ]
    if len(batches) != 900 or any(len(batch) != 32 for batch in batches):
        raise ValueError("T064 ordered batch plan must contain 900 full batches")
    source_counts = Counter(identity for batch in batches for identity in batch)
    return {
        "arm": arm,
        "seed": seed,
        "phase_hashes": [canonical_sha256(phase) for phase in phases],
        "batch_plan_sha256": canonical_sha256(batches),
        "exposure_sequence_sha256": {
            bucket: canonical_sha256(sequences[bucket]) for bucket in BUCKETS
        },
        "per_source_exposure_counts": dict(sorted(source_counts.items())),
        "ordered_batches": batches,
    }


def validate_exposure_parity(plans: Sequence[Mapping[str, Any]]) -> None:
    grouped: defaultdict[int, dict[str, Mapping[str, Any]]] = defaultdict(dict)
    for plan in plans:
        grouped[int(plan["seed"])][str(plan["arm"])] = plan
    for seed in TRAINING_SEEDS:
        arms = grouped.get(seed, {})
        if set(arms) != {ARM_STATIC, ARM_CURRICULUM}:
            raise ValueError(f"T064 seed {seed} does not have both paired plans")
        left = arms[ARM_STATIC].get("per_source_exposure_counts")
        right = arms[ARM_CURRICULUM].get("per_source_exposure_counts")
        if left != right:
            raise ValueError(f"T064 seed {seed} exposure parity failed")


def build_transfer_decision(
    *,
    source_adequate: bool,
    source_integrity_valid: bool,
    experiment_complete: bool,
    complete_source_audit_status: str | None,
    transfer_gates: Mapping[str, bool | None],
    diagnostics: Mapping[str, Any],
    problems: Sequence[str] = (),
    unmet_acceptance_criteria: Sequence[str] = (),
) -> dict[str, Any]:
    if (
        not isinstance(source_adequate, bool)
        or not isinstance(source_integrity_valid, bool)
        or not isinstance(experiment_complete, bool)
    ):
        raise ValueError("T064 transfer decision status fields must be boolean")
    if set(transfer_gates) != set(TRANSFER_GATE_NAMES):
        raise ValueError("T064 transfer decision requires exactly the six frozen gates")
    if not all(
        value is None or isinstance(value, bool) for value in transfer_gates.values()
    ):
        raise ValueError("T064 transfer gates must be boolean or null")
    if complete_source_audit_status not in {"complete", "pending", "failed", None}:
        raise ValueError("T064 complete source audit status is invalid")
    required_gate_values = tuple(transfer_gates[name] for name in TRANSFER_GATE_NAMES)
    terminal_case = "INCOMPLETE"
    recommendation: str | None = None
    if (
        complete_source_audit_status == "complete"
        and source_integrity_valid
        and not problems
        and not unmet_acceptance_criteria
    ):
        if not source_adequate and not experiment_complete:
            terminal_case = "Case B"
            recommendation = RECOMMENDATION_CASE_B
        elif source_adequate and experiment_complete:
            if all(value is True for value in required_gate_values):
                terminal_case = "Case A"
                recommendation = RECOMMENDATION_CASE_A
            elif all(value is not None for value in required_gate_values):
                terminal_case = "Case B"
                recommendation = RECOMMENDATION_CASE_B
    payload = {
        "schema_id": TRANSFER_DECISION_SCHEMA_ID,
        "format_version": T064_FORMAT_VERSION,
        "source_adequacy": source_adequate,
        "source_integrity_valid": source_integrity_valid,
        "experiment_complete": experiment_complete,
        "complete_source_audit_status": complete_source_audit_status,
        "transfer_gates": dict(transfer_gates),
        "diagnostics": dict(diagnostics),
        "terminal_case": terminal_case,
        "problems": list(problems),
        "unmet_acceptance_criteria": list(unmet_acceptance_criteria),
    }
    if recommendation is not None:
        payload["recommendation"] = recommendation
    return payload


def validate_training_run_report(payload: Mapping[str, Any]) -> dict[str, Any]:
    validated = _validate_document(payload, TRAINING_RUN_REPORT_SCHEMA_ID)
    runs = validated.get("runs")
    if not isinstance(runs, list):
        raise ValueError("T064 training report runs must be a list")
    if not runs:
        if validated.get("not_run_reason") != "source_inadequate":
            raise ValueError("empty T064 training runs require source_inadequate")
        return validated
    if "not_run_reason" in validated:
        raise ValueError("completed T064 training report cannot have not_run_reason")
    order = [
        (run.get("arm"), run.get("seed")) for run in runs if isinstance(run, Mapping)
    ]
    if order != list(TRAINING_RUN_ORDER):
        raise ValueError("T064 training report run order/cardinality is invalid")
    for index, run in enumerate(runs):
        if not isinstance(run, Mapping):
            raise ValueError(f"T064 training run {index} must be an object")
        _require_fields(
            run,
            (
                "arm",
                "seed",
                "initialization_sha256",
                "configuration",
                "trainer_input_sha256",
                "batch_plan_sha256",
                "per_bucket_exposure_counts",
                "per_source_exposure_counts",
                "checkpoint",
                "checkpoint_metadata_linkage",
                "completion_status",
                "problems",
            ),
            f"T064 training run {index}",
        )
        _require_non_empty_string(run["arm"], f"T064 training run {index} arm")
        _require_int(run["seed"], f"T064 training run {index} seed")
        _require_sha256(
            run["initialization_sha256"], f"T064 training run {index} initialization"
        )
        if not isinstance(run["configuration"], Mapping):
            raise ValueError(
                f"T064 training run {index} configuration must be an object"
            )
        _require_sha256(
            run["trainer_input_sha256"], f"T064 training run {index} trainer input"
        )
        _require_sha256(
            run["batch_plan_sha256"], f"T064 training run {index} batch plan"
        )
        if not isinstance(run["per_bucket_exposure_counts"], Mapping) or not isinstance(
            run["per_source_exposure_counts"], Mapping
        ):
            raise ValueError(
                f"T064 training run {index} exposure counts must be objects"
            )
        _validate_file_identity(
            run["checkpoint"], f"T064 training run {index} checkpoint"
        )
        if not isinstance(run["checkpoint_metadata_linkage"], Mapping):
            raise ValueError(
                f"T064 training run {index} checkpoint linkage must be an object"
            )
        _require_non_empty_string(
            run["completion_status"], f"T064 training run {index} completion status"
        )
        _require_string_list(run["problems"], f"T064 training run {index} problems")
    return validated


def validate_compact_document(payload: Mapping[str, Any]) -> dict[str, Any]:
    schema_id = payload.get("schema_id")
    if schema_id == TRAINING_RUN_REPORT_SCHEMA_ID:
        return validate_training_run_report(payload)
    if schema_id not in {
        CURRICULUM_MANIFEST_SCHEMA_ID,
        STAGE_SUMMARY_SCHEMA_ID,
        TRANSFER_DECISION_SCHEMA_ID,
    }:
        raise ValueError("unsupported T064 compact schema_id")
    validated = _validate_document(payload, str(schema_id))
    if schema_id == CURRICULUM_MANIFEST_SCHEMA_ID:
        _validate_curriculum_manifest(validated)
    elif schema_id == STAGE_SUMMARY_SCHEMA_ID:
        _validate_stage_summary(validated)
    if schema_id == TRANSFER_DECISION_SCHEMA_ID:
        _validate_transfer_decision(validated)
        case = validated.get("terminal_case")
        if case not in {"Case A", "Case B", "INCOMPLETE"}:
            raise ValueError("invalid T064 terminal case")
        has_recommendation = "recommendation" in validated
        if has_recommendation != (case in {"Case A", "Case B"}):
            raise ValueError("T064 recommendation cardinality is invalid")
    return validated


def dump_compact_json(payload: Mapping[str, Any], stream: TextIO) -> None:
    validated = validate_compact_document(payload)
    stream.write(canonical_json_bytes(validated).decode("utf-8"))
    stream.write("\n")


def load_compact_json(stream: TextIO) -> dict[str, Any]:
    try:
        payload = json.load(stream)
    except json.JSONDecodeError as exc:
        raise ValueError("invalid T064 compact JSON") from exc
    if not isinstance(payload, Mapping):
        raise ValueError("T064 compact JSON must be an object")
    return validate_compact_document(payload)


def write_compact_json(path: Path, payload: Mapping[str, Any]) -> None:
    if path.name not in COMPACT_FILENAMES:
        raise ValueError("T064 writer only permits the four frozen compact paths")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as stream:
        dump_compact_json(payload, stream)


def independent_rehash(root: Path, referenced_paths: Iterable[Path]) -> dict[str, Any]:
    compact = []
    for filename in COMPACT_FILENAMES:
        path = root / filename
        if not path.is_file():
            raise ValueError(f"missing T064 compact artifact: {path}")
        with path.open("r", encoding="utf-8") as stream:
            load_compact_json(stream)
        compact.append(_file_identity(path))
    references = [_file_identity(path) for path in referenced_paths]
    return {"compact_artifacts": compact, "referenced_artifacts": references}


def _validate_document(payload: Mapping[str, Any], schema_id: str) -> dict[str, Any]:
    result = dict(payload)
    if result.get("schema_id") != schema_id:
        raise ValueError(f"unsupported T064 schema; expected {schema_id}")
    if result.get("format_version") != T064_FORMAT_VERSION:
        raise ValueError("unsupported T064 format_version")
    return result


def _validate_complete_identity(identity: Mapping[str, Any]) -> None:
    _require_fields(
        identity,
        (
            "schema_id",
            "source_checkpoint_id",
            "source_seed",
            "source_run_id",
            "source_battle_index",
            "action_trace_identity",
            "distribution_kind",
            "assistance_level",
            "source_arm",
            "checkpoint_information_regime",
        ),
        "T064 complete source identity",
    )
    if identity["schema_id"] != COMPLETE_SOURCE_IDENTITY_SCHEMA_ID:
        raise ValueError("T064 complete source identity schema is invalid")
    for field in (
        "source_checkpoint_id",
        "source_run_id",
        "action_trace_identity",
        "distribution_kind",
        "assistance_level",
        "source_arm",
        "checkpoint_information_regime",
    ):
        _require_non_empty_string(
            identity[field], f"T064 complete identity {field}"
        ) if field not in {"assistance_level", "source_arm"} else _require_string(
            identity[field], f"T064 complete identity {field}"
        )
    _require_int(identity["source_seed"], "T064 complete identity source_seed")
    _require_int(
        identity["source_battle_index"], "T064 complete identity source_battle_index"
    )


def _floor_bucket(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 56:
        raise ValueError("T064 floor must be a non-Boolean Python integer in 1..56")
    return value


def _validate_curriculum_manifest(payload: Mapping[str, Any]) -> None:
    _require_fields(
        payload,
        (
            "task_id",
            "code_commit",
            "native_commit",
            "input_artifacts",
            "frozen_holdouts",
            "complete_source_audit",
            "selected_buckets",
            "selected_sources",
            "selected_bucket_counts",
            "source_adequacy",
            "teacher_shard_ranges",
            "teacher_worker_count",
            "batch_plans",
            "batch_plan_status",
            "exposure_parity",
            "t070_stage_manifest",
            "problems",
        ),
        "T064 curriculum manifest",
    )
    if payload["task_id"] != "T064":
        raise ValueError("T064 curriculum manifest task_id is invalid")
    _require_git_commit(payload["code_commit"], "T064 curriculum manifest code_commit")
    _require_git_commit(
        payload["native_commit"], "T064 curriculum manifest native_commit"
    )
    if not isinstance(payload["input_artifacts"], Mapping):
        raise ValueError("T064 curriculum manifest input_artifacts must be an object")
    required_inputs = {
        "t042_scale_manifest",
        "initialization_checkpoint",
        "assist_0",
        "assist_hp50",
        "assist_hp50_potion_elite_boss",
        "assist_hp75_potion",
    }
    if not required_inputs.issubset(payload["input_artifacts"]):
        raise ValueError(
            "T064 curriculum manifest required input artifacts are missing"
        )
    for name, identity in payload["input_artifacts"].items():
        _validate_file_identity(identity, f"T064 curriculum input {name}")
    if not isinstance(payload["frozen_holdouts"], list):
        raise ValueError("T064 curriculum manifest frozen_holdouts must be a list")
    for index, holdout in enumerate(payload["frozen_holdouts"]):
        _validate_file_identity(holdout, f"T064 frozen holdout {index}")
        _require_fields(
            holdout,
            ("record_count", "complete_identity_sha256s"),
            f"T064 frozen holdout {index}",
        )
        if _require_non_negative_int(
            holdout["record_count"], f"T064 frozen holdout {index} record count"
        ) != len(holdout["complete_identity_sha256s"]):
            raise ValueError("T064 frozen holdout identity cardinality is invalid")
        _require_sha256_list(
            holdout["complete_identity_sha256s"],
            f"T064 frozen holdout {index} complete identities",
        )
    if not isinstance(payload["complete_source_audit"], Mapping):
        raise ValueError(
            "T064 curriculum manifest complete_source_audit must be an object"
        )
    audit = payload["complete_source_audit"]
    _require_fields(
        audit,
        (
            "status",
            "source_count",
            "sources",
            "candidate_duplicate_complete_identity_count",
            "candidate_holdout_exclusion_count",
            "selected_duplicate_complete_identity_count",
            "selected_holdout_overlap_count",
        ),
        "T064 complete source audit",
    )
    if audit["status"] not in {
        "static_complete_selected_restore_pending",
        "complete",
        "failed",
    }:
        raise ValueError("T064 complete source audit status is invalid")
    _require_non_negative_int(
        audit["candidate_duplicate_complete_identity_count"],
        "T064 candidate source-audit duplicate count",
    )
    _require_non_negative_int(
        audit["candidate_holdout_exclusion_count"],
        "T064 candidate holdout exclusion count",
    )
    _require_non_negative_int(
        audit["selected_duplicate_complete_identity_count"],
        "T064 selected source-audit duplicate count",
    )
    _require_non_negative_int(
        audit["selected_holdout_overlap_count"],
        "T064 selected holdout overlap count",
    )
    if audit["candidate_duplicate_complete_identity_count"]:
        raise ValueError(
            "T064 candidate source audit has duplicate complete identities"
        )
    if audit["selected_duplicate_complete_identity_count"]:
        raise ValueError("T064 selected source audit has duplicate complete identities")
    if audit["selected_holdout_overlap_count"]:
        raise ValueError("T064 selected source audit overlaps frozen holdouts")
    if not isinstance(audit["sources"], list):
        raise ValueError("T064 source audit sources must be a list")
    if _require_non_negative_int(
        audit["source_count"], "T064 source audit count"
    ) != len(audit["sources"]):
        raise ValueError("T064 source audit source cardinality is invalid")
    for index, descriptor in enumerate(audit["sources"]):
        _validate_source_descriptor(descriptor, f"T064 source audit descriptor {index}")
    candidate_hashes = [
        descriptor["complete_identity_sha256"] for descriptor in audit["sources"]
    ]
    candidate_duplicate_count = len(candidate_hashes) - len(set(candidate_hashes))
    if (
        candidate_duplicate_count
        != audit["candidate_duplicate_complete_identity_count"]
    ):
        raise ValueError("T064 candidate source-audit duplicate count is inconsistent")
    if candidate_duplicate_count:
        raise ValueError(
            "T064 candidate source audit has duplicate complete identities"
        )
    if audit["status"] in {"complete", "failed"}:
        _require_fields(
            audit,
            (
                "selected_restore_count",
                "selected_restore_failure_count",
                "selected_restore_failures",
            ),
            "completed T064 source audit",
        )
        _require_non_negative_int(
            audit["selected_restore_count"], "T064 selected restore count"
        )
        _require_non_negative_int(
            audit["selected_restore_failure_count"],
            "T064 selected restore failure count",
        )
        _require_string_list(
            audit["selected_restore_failures"], "T064 selected restore failures"
        )
    if not isinstance(payload["selected_buckets"], Mapping) or set(
        payload["selected_buckets"]
    ) != set(BUCKETS):
        raise ValueError("T064 curriculum manifest selected buckets are invalid")
    if not isinstance(payload["selected_sources"], list):
        raise ValueError("T064 curriculum manifest selected_sources must be a list")
    if not isinstance(payload["selected_bucket_counts"], Mapping) or set(
        payload["selected_bucket_counts"]
    ) != set(BUCKETS):
        raise ValueError("T064 curriculum manifest selected bucket counts are invalid")
    selected_hashes: list[str] = []
    for bucket in BUCKETS:
        rows = payload["selected_buckets"][bucket]
        if not isinstance(rows, list):
            raise ValueError(f"T064 selected bucket {bucket} must be a list")
        if _require_non_negative_int(
            payload["selected_bucket_counts"][bucket],
            f"T064 selected bucket {bucket} count",
        ) != len(rows):
            raise ValueError(f"T064 selected bucket {bucket} count is invalid")
        for index, descriptor in enumerate(rows):
            _validate_source_descriptor(descriptor, f"T064 selected {bucket} {index}")
            selected_hashes.append(descriptor["complete_identity_sha256"])
    for index, descriptor in enumerate(payload["selected_sources"]):
        _validate_source_descriptor(descriptor, f"T064 selected source {index}")
    if selected_hashes != [
        descriptor["complete_identity_sha256"]
        for descriptor in payload["selected_sources"]
    ] or len(selected_hashes) != len(set(selected_hashes)):
        raise ValueError("T064 selected source order or uniqueness is invalid")
    frozen_holdout_hashes = {
        identity
        for holdout in payload["frozen_holdouts"]
        for identity in holdout["complete_identity_sha256s"]
    }
    candidate_holdout_exclusion_count = sum(
        identity in frozen_holdout_hashes for identity in candidate_hashes
    )
    if candidate_holdout_exclusion_count != audit["candidate_holdout_exclusion_count"]:
        raise ValueError("T064 candidate holdout exclusion count is inconsistent")
    selected_duplicate_count = len(selected_hashes) - len(set(selected_hashes))
    if selected_duplicate_count != audit["selected_duplicate_complete_identity_count"]:
        raise ValueError("T064 selected source-audit duplicate count is inconsistent")
    selected_holdout_overlap_count = sum(
        identity in frozen_holdout_hashes for identity in selected_hashes
    )
    if selected_holdout_overlap_count != audit["selected_holdout_overlap_count"]:
        raise ValueError("T064 selected holdout overlap count is inconsistent")
    if not isinstance(payload["source_adequacy"], bool):
        raise ValueError("T064 curriculum manifest source adequacy is invalid")
    if payload["source_adequacy"] != source_adequacy(
        payload["selected_buckets"],
        selected_duplicate_complete_identity_count=(
            audit["selected_duplicate_complete_identity_count"]
        ),
        selected_holdout_overlap_count=audit["selected_holdout_overlap_count"],
    ):
        raise ValueError("T064 curriculum manifest source adequacy is inconsistent")
    if audit["status"] in {"complete", "failed"}:
        if audit["selected_restore_count"] != len(payload["selected_sources"]):
            raise ValueError("T064 source audit restore count is inconsistent")
        failure_count = audit["selected_restore_failure_count"]
        failures = audit["selected_restore_failures"]
        if failure_count != len(failures):
            raise ValueError("T064 source audit failure count is inconsistent")
        selected_statuses = [
            descriptor["fresh_restore_status"]
            for descriptor in payload["selected_sources"]
        ]
        if audit["status"] == "complete" and (
            failure_count != 0
            or any(status != "passed" for status in selected_statuses)
        ):
            raise ValueError("T064 complete source audit has restore failures")
        if audit["status"] == "failed" and (
            failure_count == 0
            or sum(status == "failed" for status in selected_statuses) != failure_count
            or any(status == "pending" for status in selected_statuses)
        ):
            raise ValueError("T064 failed source audit status is inconsistent")
    if tuple(payload["teacher_shard_ranges"]) != contiguous_ranges(
        len(payload["selected_sources"])
    ):
        raise ValueError("T064 curriculum manifest teacher ranges are invalid")
    if payload["teacher_worker_count"] != 16:
        raise ValueError("T064 curriculum manifest teacher worker count is invalid")
    _validate_t070_stage_manifest(payload["t070_stage_manifest"], payload)
    if payload["source_adequacy"]:
        if (
            payload["batch_plan_status"] != "complete"
            or payload["exposure_parity"] is not True
            or not isinstance(payload["batch_plans"], list)
            or len(payload["batch_plans"]) != 4
        ):
            raise ValueError("T064 adequate manifest batch plans are invalid")
    elif (
        payload["batch_plan_status"] != "not_run_source_inadequate"
        or payload["exposure_parity"] is not None
        or payload["batch_plans"] != []
    ):
        raise ValueError("T064 source-inadequate manifest batch plan status is invalid")
    _require_string_list(payload["problems"], "T064 curriculum manifest problems")


def _validate_t070_stage_manifest(value: Any, manifest: Mapping[str, Any]) -> None:
    """Validate the sole in-manifest T070 four-checkpoint selector contract."""

    if value is None:
        return
    if not isinstance(value, Mapping):
        raise ValueError("T064 t070_stage_manifest must be null or an object")
    _require_fields(
        value,
        (
            "frozen_t070_manifest",
            "historical_code_commit",
            "current_code_commit",
            "arm",
            "native_budget",
            "tree_geometry_enabled",
            "projection_mode",
            "shard_ranges",
            "worker_count",
            "checkpoint_selections",
        ),
        "T064 T070 stage manifest",
    )
    _validate_file_identity(value["frozen_t070_manifest"], "T064 frozen T070 manifest")
    _require_git_commit(
        value["historical_code_commit"], "T064 historical T070 code commit"
    )
    _require_git_commit(value["current_code_commit"], "T064 current T070 code commit")
    if (
        value["current_code_commit"] != manifest["code_commit"]
        or value["historical_code_commit"] == manifest["code_commit"]
        or value["arm"] != "prior_value"
        or value["native_budget"] != 100
        or value["tree_geometry_enabled"] is not False
        or value["projection_mode"] != "accepted_t069_search_scope_projection"
        or value["shard_ranges"] != list(contiguous_ranges(93))
        or value["worker_count"] != 16
    ):
        raise ValueError("T064 T070 selector contract is invalid")
    selections = value["checkpoint_selections"]
    expected_keys = {
        "static_mixture_v1:64001",
        "static_mixture_v1:64002",
        "assistance_annealed_curriculum_v1:64001",
        "assistance_annealed_curriculum_v1:64002",
    }
    if not isinstance(selections, Mapping) or set(selections) != expected_keys:
        raise ValueError("T064 T070 selector must contain exactly four checkpoints")
    for key, selection in selections.items():
        if not isinstance(selection, Mapping):
            raise ValueError(f"T064 T070 selection {key} must be an object")
        _validate_file_identity(
            selection.get("checkpoint"), f"T064 T070 selection {key} checkpoint"
        )


def validate_t064_t070_stage_manifest(manifest: Mapping[str, Any]) -> None:
    """Validate the embedded T070 selector before a shard resolves its checkpoint."""

    code_commit = manifest.get("code_commit")
    if not isinstance(code_commit, str):
        raise ValueError("T064 selector manifest lacks code commit")
    _validate_t070_stage_manifest(manifest.get("t070_stage_manifest"), manifest)


def _validate_stage_summary(payload: Mapping[str, Any]) -> None:
    _require_fields(
        payload,
        (
            "reuse_inventory",
            "stages",
            "retention_reason",
            "downstream_consumer",
            "deletion_condition",
            "problems",
        ),
        "T064 stage summary",
    )
    if not isinstance(payload["reuse_inventory"], list) or not isinstance(
        payload["stages"], list
    ):
        raise ValueError("T064 stage summary inventory and stages must be lists")
    for index, stage in enumerate(payload["stages"]):
        if not isinstance(stage, Mapping):
            raise ValueError(f"T064 stage {index} must be an object")
        _require_fields(
            stage,
            (
                "name",
                "status",
                "command",
                "code_commit",
                "native_commit",
                "inputs",
                "outputs",
                "workers",
                "shards",
                "ranges",
                "return_codes",
                "wall_clock_seconds",
                "failure_count",
                "referenced_artifacts",
                "failed_attempts",
                "retained_log_paths",
            ),
            f"T064 stage {index}",
        )
        for field in ("name", "status", "command"):
            _require_non_empty_string(stage[field], f"T064 stage {index} {field}")
        for field in ("code_commit", "native_commit"):
            _require_git_commit(stage[field], f"T064 stage {index} {field}")
        for field in ("inputs", "outputs"):
            if not isinstance(stage[field], Mapping):
                raise ValueError(f"T064 stage {index} {field} must be an object")
            for name, identity in stage[field].items():
                _validate_file_identity(identity, f"T064 stage {index} {field} {name}")
        _require_non_negative_int(stage["workers"], f"T064 stage {index} workers")
        _require_non_negative_int(stage["shards"], f"T064 stage {index} shards")
        _require_string_list(stage["ranges"], f"T064 stage {index} ranges")
        _require_non_negative_int_list(
            stage["return_codes"], f"T064 stage {index} return codes"
        )
        _require_non_negative_number(
            stage["wall_clock_seconds"], f"T064 stage {index} wall clock"
        )
        _require_non_negative_int(
            stage["failure_count"], f"T064 stage {index} failure count"
        )
        if not isinstance(stage["referenced_artifacts"], list):
            raise ValueError(f"T064 stage {index} referenced artifacts must be a list")
        for artifact_index, artifact in enumerate(stage["referenced_artifacts"]):
            _validate_file_identity(
                artifact, f"T064 stage {index} referenced artifact {artifact_index}"
            )
            _require_non_empty_string(
                artifact.get("schema_id"),
                f"T064 stage {index} referenced artifact {artifact_index} schema",
            )
        if not isinstance(stage["failed_attempts"], list):
            raise ValueError(f"T064 stage {index} failed attempts must be a list")
        for attempt_index, attempt in enumerate(stage["failed_attempts"]):
            if not isinstance(attempt, Mapping):
                raise ValueError(
                    f"T064 stage {index} failed attempt {attempt_index} must be an object"
                )
        _require_string_list(
            stage["retained_log_paths"], f"T064 stage {index} retained logs"
        )
    for field in ("retention_reason", "downstream_consumer", "deletion_condition"):
        _require_non_empty_string(payload[field], f"T064 stage summary {field}")
    _require_string_list(payload["problems"], "T064 stage summary problems")


def _validate_transfer_decision(payload: Mapping[str, Any]) -> None:
    _require_fields(
        payload,
        (
            "source_adequacy",
            "source_integrity_valid",
            "experiment_complete",
            "complete_source_audit_status",
            "transfer_gates",
            "diagnostics",
            "terminal_case",
            "problems",
            "unmet_acceptance_criteria",
        ),
        "T064 transfer decision",
    )
    if not all(
        isinstance(payload[name], bool)
        for name in (
            "source_adequacy",
            "source_integrity_valid",
            "experiment_complete",
        )
    ):
        raise ValueError("T064 transfer decision booleans are invalid")
    if payload["complete_source_audit_status"] not in {
        "complete",
        "pending",
        "failed",
        None,
    }:
        raise ValueError("T064 transfer decision source-audit status is invalid")
    gates = payload["transfer_gates"]
    if not isinstance(gates, Mapping) or set(gates) != set(TRANSFER_GATE_NAMES):
        raise ValueError("T064 transfer decision must contain exactly six frozen gates")
    if not all(value is None or isinstance(value, bool) for value in gates.values()):
        raise ValueError("T064 transfer decision gates must be boolean or null")
    if not isinstance(payload["diagnostics"], Mapping):
        raise ValueError("T064 transfer decision diagnostics must be an object")
    _require_string_list(payload["problems"], "T064 transfer decision problems")
    _require_string_list(
        payload["unmet_acceptance_criteria"], "T064 transfer decision unmet criteria"
    )
    expected = build_transfer_decision(
        source_adequate=payload["source_adequacy"],
        source_integrity_valid=payload["source_integrity_valid"],
        experiment_complete=payload["experiment_complete"],
        complete_source_audit_status=payload["complete_source_audit_status"],
        transfer_gates=payload["transfer_gates"],
        diagnostics=payload["diagnostics"],
        problems=payload["problems"],
        unmet_acceptance_criteria=payload["unmet_acceptance_criteria"],
    )
    if payload["terminal_case"] != expected["terminal_case"]:
        raise ValueError(
            "T064 transfer decision terminal case fails the frozen truth table"
        )
    if payload.get("recommendation") != expected.get("recommendation"):
        raise ValueError(
            "T064 transfer decision recommendation fails the frozen truth table"
        )


def _require_fields(
    payload: Mapping[str, Any], fields: Sequence[str], label: str
) -> None:
    missing = [field for field in fields if field not in payload]
    if missing:
        raise ValueError(f"{label} is missing required fields: {', '.join(missing)}")


def _require_string(value: Any, label: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{label} must be a string")
    return value


def _require_non_empty_string(value: Any, label: str) -> str:
    value = _require_string(value, label)
    if not value:
        raise ValueError(f"{label} must be non-empty")
    return value


def _require_int(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{label} must be an integer")
    return value


def _require_non_negative_int(value: Any, label: str) -> int:
    value = _require_int(value, label)
    if value < 0:
        raise ValueError(f"{label} must be non-negative")
    return value


def _require_non_negative_number(value: Any, label: str) -> float:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(float(value))
        or value < 0
    ):
        raise ValueError(f"{label} must be a non-negative number")
    return float(value)


def _require_git_commit(value: Any, label: str) -> str:
    value = _require_non_empty_string(value, label)
    if not re.fullmatch(r"[0-9a-f]{40}", value):
        raise ValueError(f"{label} must be a lowercase 40-hex commit")
    return value


def _require_sha256(value: Any, label: str) -> str:
    value = _require_non_empty_string(value, label)
    if not _SHA256_RE.fullmatch(value):
        raise ValueError(f"{label} must be a SHA-256")
    return value


def _require_string_list(value: Any, label: str) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError(f"{label} must be a list of strings")
    return list(value)


def _require_non_negative_int_list(value: Any, label: str) -> list[int]:
    if not isinstance(value, list):
        raise ValueError(f"{label} must be a list")
    return [
        _require_non_negative_int(item, f"{label} {index}")
        for index, item in enumerate(value)
    ]


def _require_sha256_list(value: Any, label: str) -> list[str]:
    if not isinstance(value, list):
        raise ValueError(f"{label} must be a list")
    result = [
        _require_sha256(item, f"{label} {index}") for index, item in enumerate(value)
    ]
    if len(result) != len(set(result)):
        raise ValueError(f"{label} must be unique")
    return result


def _validate_source_descriptor(value: Any, label: str) -> None:
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} must be an object")
    _require_fields(
        value,
        (
            "component",
            "source_path",
            "source_record_index",
            "complete_identity",
            "complete_identity_sha256",
            "act",
            "room_type",
            "encounter_id",
            "floor_bucket",
            "exclusion_reasons",
            "fresh_restore_status",
        ),
        label,
    )
    _require_non_empty_string(value["component"], f"{label} component")
    _require_non_empty_string(value["source_path"], f"{label} source path")
    _require_non_negative_int(value["source_record_index"], f"{label} source index")
    if not isinstance(value["complete_identity"], Mapping):
        raise ValueError(f"{label} complete identity must be an object")
    identity = dict(value["complete_identity"])
    complete_hash = identity.pop("complete_identity_sha256", None)
    _validate_complete_identity(identity)
    _require_sha256(complete_hash, f"{label} nested complete identity hash")
    expected_hash = canonical_sha256(identity)
    if (
        complete_hash != expected_hash
        or value["complete_identity_sha256"] != expected_hash
    ):
        raise ValueError(f"{label} complete identity hash mismatch")
    _require_sha256(
        value["complete_identity_sha256"], f"{label} complete identity hash"
    )
    _floor_bucket(value["floor_bucket"])
    _require_int(value["act"], f"{label} act")
    _require_non_empty_string(value["room_type"], f"{label} room type")
    _require_non_empty_string(value["encounter_id"], f"{label} encounter id")
    _require_string_list(value["exclusion_reasons"], f"{label} exclusion reasons")
    if value["fresh_restore_status"] not in {"pending", "passed", "failed"}:
        raise ValueError(f"{label} fresh restore status is invalid")


def _validate_file_identity(value: Any, label: str) -> None:
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} must be an object")
    _require_fields(value, ("path", "sha256", "bytes"), label)
    _require_non_empty_string(value["path"], f"{label} path")
    _require_sha256(value["sha256"], f"{label} sha256")
    if _require_int(value["bytes"], f"{label} bytes") < 0:
        raise ValueError(f"{label} bytes must be non-negative")


def _file_identity(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise ValueError(f"referenced artifact is missing: {path}")
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return {
        "path": str(path),
        "sha256": digest.hexdigest(),
        "bytes": path.stat().st_size,
    }
