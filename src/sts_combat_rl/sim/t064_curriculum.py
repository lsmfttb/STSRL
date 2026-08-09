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
    (arm, seed)
    for seed in TRAINING_SEEDS
    for arm in (ARM_STATIC, ARM_CURRICULUM)
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
        if identity.get("stable_id") != stable_id or identity.get("occurrence") != occurrence:
            raise ValueError("action trace identity is not occurrence-safe")
        rows.append({"decision_index": decision_index, "selected_action": identity})
    return canonical_sha256(rows)


def complete_source_identity(
    record: Any,
    *,
    source_arm: str | None = None,
) -> dict[str, Any]:
    """Build the frozen complete identity without guessing absent provenance."""

    metadata = record.structural_metadata
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
    mapped_source_arm = metadata.get("source_arm", "") if source_arm is None else source_arm
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
            record, "distribution_kind", getattr(record, "source_distribution_kind", None)
        ),
        "assistance_level": assistance_level,
        "source_arm": mapped_source_arm,
        "checkpoint_information_regime": record.checkpoint_information_regime,
    }
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
    floor = metadata.get("floor")
    floor_bucket = int(floor) // 5 if isinstance(floor, int) and not isinstance(floor, bool) else None
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
            [row.get("act"), row.get("room_type"), row.get("encounter_id"), row.get("floor_bucket")]
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
    flattened = [row["complete_identity_sha256"] for bucket in BUCKETS for row in selected[bucket]]
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


def source_adequacy(selected: Mapping[str, Sequence[Mapping[str, Any]]]) -> bool:
    later = len(selected.get(BUCKET_STRONG, ())) + len(selected.get(BUCKET_MEDIUM, ()))
    anchor = len(selected.get(BUCKET_ANCHOR, ()))
    identities = [
        str(row.get("complete_identity_sha256"))
        for bucket in BUCKETS
        for row in selected.get(bucket, ())
    ]
    return later >= 128 and anchor == 256 and len(identities) == len(set(identities))


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
    experiment_complete: bool,
    transfer_gates: Mapping[str, bool | None],
    diagnostics: Mapping[str, Any],
    problems: Sequence[str] = (),
    unmet_acceptance_criteria: Sequence[str] = (),
) -> dict[str, Any]:
    required_gate_values = tuple(transfer_gates.values())
    if not source_adequate and not problems:
        terminal_case = "Case B"
        recommendation: str | None = RECOMMENDATION_CASE_B
    elif experiment_complete and all(value is True for value in required_gate_values):
        terminal_case = "Case A"
        recommendation = RECOMMENDATION_CASE_A
    elif experiment_complete and all(value is not None for value in required_gate_values):
        terminal_case = "Case B"
        recommendation = RECOMMENDATION_CASE_B
    else:
        terminal_case = "INCOMPLETE"
        recommendation = None
    payload = {
        "schema_id": TRANSFER_DECISION_SCHEMA_ID,
        "format_version": T064_FORMAT_VERSION,
        "source_adequacy": source_adequate,
        "experiment_complete": experiment_complete,
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
    order = [(run.get("arm"), run.get("seed")) for run in runs if isinstance(run, Mapping)]
    if order != list(TRAINING_RUN_ORDER):
        raise ValueError("T064 training report run order/cardinality is invalid")
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
    if schema_id == TRANSFER_DECISION_SCHEMA_ID:
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


def _file_identity(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise ValueError(f"referenced artifact is missing: {path}")
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return {"path": str(path), "sha256": digest.hexdigest(), "bytes": path.stat().st_size}
