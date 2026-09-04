"""T085 paired cohort evaluation and retained-artifact contract.

This module deliberately has no simulator dependency.  The pinned simulator
source/evaluation commands produce JSON records, and this module validates and
aggregates those records without changing Search topology or simulator
semantics.  A missing, malformed, or incomplete record is an integrity failure;
the caller must not backfill it after looking at outcomes.
"""

from __future__ import annotations

import hashlib
import json
import math
import random
from collections import Counter, defaultdict
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path

T085_ARTIFACT_ROOT = Path(
    "/mnt/d/DeadlyCatCoding/STSRL/artifacts/t085-corrected-leaf-value-search-repair"
)
T085_T052_COHORT_PATH = Path(
    "/mnt/d/DeadlyCatCoding/STSRL/artifacts/"
    "t052-t051-boss-later-act-fixed-cohort-diagnostic-pr/t052-fixed-cohort.jsonl"
)
T085_T052_COHORT_BYTE_COUNT = 161_435_825
T085_T052_COHORT_SCHEMA_ID = "fixed-cohort-v3-jsonl"
T085_SOURCE_MANIFEST_SCHEMA_ID = "t085-source-generation-manifest-v1"
T085_SELECTION_EVIDENCE_SCHEMA_ID = "t085-selection-gate-evidence-v1"
T085_T052_COHORT_SHA256 = (
    "b7f8e9b85b53bbf8e37adfe6cc90d0579937661309b26bce2a8f2921604a8608"
)
T085_COHORT_B_SEED_START = 851001
T085_COHORT_B_SEED_END = 852024
T085_COHORT_B_RUN_COUNT = 1024
T085_COHORT_B_SELECTED_COUNT = 192
T085_COHORT_C_SEED_START = 850001
T085_COHORT_C_SEED_END = 850128
T085_COHORT_C_RUN_COUNT = 128
T085_COHORT_C_MIN_SELECTED_COUNT = 96
T085_SEARCH_400_SELECTED_COUNT = 48
T085_BOOTSTRAP_COUNT = 10_000
T085_BOOTSTRAP_SEED = 85085
T085_T042_SCALE_MANIFEST_SHA256 = (
    "25efae30dc9a61c8b97cb09e1844b93bffe693bde51c0f494f0f65203a1d327"
)

T085_PRIMARY_ARMS = (
    "baseline",
    "old_value_64001",
    "corrected_value_85001",
    "old_value_64002",
    "corrected_value_85002",
)
T085_SECONDARY_ARMS = (
    "prior_only_64001",
    "prior_corrected_85001",
    "prior_only_64002",
    "prior_corrected_85002",
)
T085_SEARCH_400_ARMS = (
    "baseline@400",
    "corrected_value_85001@400",
    "corrected_value_85002@400",
)
T085_SEARCH_BUDGET = 100
T085_SEARCH_400_BUDGET = 400
T085_TERMINAL_CLASSIFICATIONS = (
    "CORRECTED_VALUE_SEARCH_IMPROVEMENT_ESTABLISHED",
    "CORRECTED_VALUE_SEARCH_HARM_CONFIRMED",
    "CORRECTED_VALUE_SEARCH_IMPROVEMENT_NOT_ESTABLISHED",
    "VALUE_REPAIR_EVAL_SUPPORT_INSUFFICIENT",
    "INCOMPLETE",
)
T085_REQUIRED_RETENTION_OUTPUT_ROLES = (
    "input_eligibility_manifest",
    "repaired_checkpoint_85001",
    "repaired_checkpoint_85002",
    "training_report_85001",
    "training_report_85002",
    "cohort_a_manifest",
    "cohort_b_source_manifest",
    "cohort_b_selected_manifest",
    "cohort_b_overlap_audit",
    "cohort_c_source_manifest",
    "cohort_c_selected_manifest",
    "search_400_manifest",
    "paired_evaluation_report",
    "terminal_classification_report",
)
T085_SOURCE_INVENTORY_KEYS = (
    "source_run_seed_inventory",
    "source_run_identity_inventory",
    "complete_source_identity_inventory",
)


class T085EvaluationIntegrityError(ValueError):
    """Raised when a source/evaluation artifact cannot support a claim."""


def _required_string(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise T085EvaluationIntegrityError(f"{label} must be a non-empty string")
    return value


def _required_int(value: object, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise T085EvaluationIntegrityError(f"{label} must be an integer")
    return value


def _required_finite(value: object, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise T085EvaluationIntegrityError(f"{label} must be numeric")
    result = float(value)
    if not math.isfinite(result):
        raise T085EvaluationIntegrityError(f"{label} must be finite")
    return result


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _sha256_json(value: object) -> str:
    return _sha256_text(json.dumps(value, sort_keys=True, separators=(",", ":")))


def _is_sha256(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdefABCDEF" for character in value)
    )


def _seed_domain(start: int, end: int) -> set[int]:
    return set(range(start, end + 1))


@dataclass(frozen=True)
class T085SourceRunRecord:
    """One complete source run in a frozen cohort source manifest."""

    source_run_seed: int
    source_run_identity: str
    complete_source_identity: str
    source_valid: bool = True
    failure_reason: str | None = None

    @classmethod
    def from_mapping(cls, value: Mapping[str, object]) -> T085SourceRunRecord:
        return cls(
            source_run_seed=_required_int(
                value.get("source_run_seed"), "source_run_seed"
            ),
            source_run_identity=_required_string(
                value.get("source_run_identity"), "source_run_identity"
            ),
            complete_source_identity=_required_string(
                value.get("complete_source_identity"), "complete_source_identity"
            ),
            source_valid=value.get("source_valid") is True,
            failure_reason=(
                str(value["failure_reason"])
                if value.get("failure_reason") is not None
                else None
            ),
        )


@dataclass(frozen=True)
class T085BattleStartRecord:
    """Public, outcome-blind identity used for cohort selection."""

    source_run_seed: int
    source_run_identity: str
    complete_source_identity: str
    battle_identity: str
    act: int
    room_type: str
    restore_ok: bool = True
    public_context_match: bool = True
    source_valid: bool = True
    failure_reason: str | None = None
    source_artifact_record_identity: str | None = None

    @classmethod
    def from_mapping(cls, value: Mapping[str, object]) -> T085BattleStartRecord:
        act = _required_int(value.get("act"), "act")
        if act <= 0:
            raise T085EvaluationIntegrityError("act must be positive")
        room_type = _required_string(value.get("room_type"), "room_type").upper()
        return cls(
            source_run_seed=_required_int(
                value.get("source_run_seed"), "source_run_seed"
            ),
            source_run_identity=_required_string(
                value.get("source_run_identity"), "source_run_identity"
            ),
            complete_source_identity=_required_string(
                value.get("complete_source_identity"), "complete_source_identity"
            ),
            battle_identity=_required_string(
                value.get("battle_identity"), "battle_identity"
            ),
            act=act,
            room_type=room_type,
            restore_ok=value.get("restore_ok") is True,
            public_context_match=value.get("public_context_match") is True,
            source_valid=value.get("source_valid") is True,
            failure_reason=(
                str(value["failure_reason"])
                if value.get("failure_reason") is not None
                else None
            ),
            source_artifact_record_identity=(
                str(
                    value.get(
                        "source_artifact_record_identity",
                        value.get("source_checkpoint_id"),
                    )
                )
                if value.get(
                    "source_artifact_record_identity",
                    value.get("source_checkpoint_id"),
                )
                is not None
                else None
            ),
        )

    @property
    def selection_identity(self) -> str:
        if self.source_artifact_record_identity is not None:
            return self.source_artifact_record_identity
        return f"{self.source_run_identity}:{self.battle_identity}"


@dataclass(frozen=True)
class T085OutcomeRecord:
    """One completed restored battle observation for one evaluation arm."""

    cohort: str
    record_identity: str
    arm: str
    battle_survived: bool
    terminal_native_utility: float
    terminal_current_hp: float | None = None
    turn_count: int | None = None
    selected_root_action_identity: str | None = None
    simulator_steps: int | None = None
    search_steps: int | None = None
    learned_value_callback_count: int | None = None
    wall_clock_seconds: float | None = None
    failure_reason: str | None = None
    source_run_identity: str | None = None
    search_budget: int | None = None

    @classmethod
    def from_mapping(cls, value: Mapping[str, object]) -> T085OutcomeRecord:
        return cls(
            cohort=_required_string(value.get("cohort"), "cohort"),
            record_identity=_required_string(
                value.get("record_identity"), "record_identity"
            ),
            arm=_required_string(value.get("arm"), "arm"),
            battle_survived=value.get("battle_survived") is True,
            terminal_native_utility=_required_finite(
                value.get("terminal_native_utility"), "terminal_native_utility"
            ),
            terminal_current_hp=(
                _required_finite(value["terminal_current_hp"], "terminal_current_hp")
                if value.get("terminal_current_hp") is not None
                else None
            ),
            turn_count=(
                _required_int(value["turn_count"], "turn_count")
                if value.get("turn_count") is not None
                else None
            ),
            selected_root_action_identity=(
                str(value["selected_root_action_identity"])
                if value.get("selected_root_action_identity") is not None
                else None
            ),
            simulator_steps=(
                _required_int(value["simulator_steps"], "simulator_steps")
                if value.get("simulator_steps") is not None
                else None
            ),
            search_steps=(
                _required_int(value["search_steps"], "search_steps")
                if value.get("search_steps") is not None
                else None
            ),
            learned_value_callback_count=(
                _required_int(
                    value["learned_value_callback_count"],
                    "learned_value_callback_count",
                )
                if value.get("learned_value_callback_count") is not None
                else None
            ),
            wall_clock_seconds=(
                _required_finite(value["wall_clock_seconds"], "wall_clock_seconds")
                if value.get("wall_clock_seconds") is not None
                else None
            ),
            failure_reason=(
                str(value["failure_reason"])
                if value.get("failure_reason") is not None
                else None
            ),
            source_run_identity=(
                str(value["source_run_identity"])
                if value.get("source_run_identity") is not None
                else None
            ),
            search_budget=(
                _required_int(value["search_budget"], "search_budget")
                if value.get("search_budget") is not None
                else None
            ),
        )


def _coerce_source_runs(
    records: Iterable[
        T085SourceRunRecord | T085BattleStartRecord | Mapping[str, object]
    ],
) -> tuple[T085SourceRunRecord, ...]:
    return tuple(
        record
        if isinstance(record, T085SourceRunRecord)
        else T085SourceRunRecord(
            source_run_seed=record.source_run_seed,
            source_run_identity=record.source_run_identity,
            complete_source_identity=record.complete_source_identity,
            source_valid=record.source_valid,
            failure_reason=record.failure_reason,
        )
        if isinstance(record, T085BattleStartRecord)
        else T085SourceRunRecord.from_mapping(record)
        for record in records
    )


def _coerce_battle_starts(
    records: Iterable[T085BattleStartRecord | Mapping[str, object]],
) -> tuple[T085BattleStartRecord, ...]:
    return tuple(
        record
        if isinstance(record, T085BattleStartRecord)
        else T085BattleStartRecord.from_mapping(record)
        for record in records
    )


@dataclass(frozen=True)
class _T085T052ArtifactIdentity:
    path: Path
    sha256: str
    byte_count: int
    record_identities: tuple[str, ...]
    records: tuple[Mapping[str, object], ...]


def _load_t085_t052_artifact(
    path: str | Path = T085_T052_COHORT_PATH,
) -> _T085T052ArtifactIdentity:
    """Verify and index the exact retained T052 JSONL, without trusting flags."""

    try:
        resolved = Path(path).resolve(strict=True)
    except FileNotFoundError as exc:
        raise T085EvaluationIntegrityError(
            "accepted T052 fixed-cohort artifact is unavailable"
        ) from exc
    if resolved != T085_T052_COHORT_PATH.resolve():
        raise T085EvaluationIntegrityError(
            "T052 Cohort A must use the exact retained fixed-cohort path"
        )
    byte_count = resolved.stat().st_size
    if byte_count != T085_T052_COHORT_BYTE_COUNT:
        raise T085EvaluationIntegrityError(
            "T052 fixed-cohort byte count does not match the accepted artifact"
        )
    digest = sha256_file(resolved)
    if digest != T085_T052_COHORT_SHA256:
        raise T085EvaluationIntegrityError(
            "T052 fixed-cohort bytes do not match the accepted SHA-256"
        )
    metadata: Mapping[str, object] | None = None
    records: list[Mapping[str, object]] = []
    with resolved.open(encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, start=1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise T085EvaluationIntegrityError(
                    f"T052 fixed-cohort line {line_number} is not JSON"
                ) from exc
            if not isinstance(row, Mapping):
                raise T085EvaluationIntegrityError(
                    f"T052 fixed-cohort line {line_number} is not an object"
                )
            row_type = row.get("type")
            if row_type == "metadata":
                if metadata is not None:
                    raise T085EvaluationIntegrityError(
                        "T052 fixed-cohort contains duplicate metadata"
                    )
                metadata = _required_mapping(row.get("metadata"), "T052 metadata")
            elif row_type == "record":
                records.append(_required_mapping(row.get("record"), "T052 record"))
            else:
                raise T085EvaluationIntegrityError(
                    f"T052 fixed-cohort line {line_number} has unknown row type"
                )
    if metadata is None:
        raise T085EvaluationIntegrityError("T052 fixed-cohort metadata is missing")
    if (
        metadata.get("format_version") != 3
        or metadata.get("record_count") != 93
        or metadata.get("problems") != []
    ):
        raise T085EvaluationIntegrityError(
            "T052 fixed-cohort metadata is not the accepted 93-record schema"
        )
    identities = tuple(
        _required_string(
            record.get("source_checkpoint_id"), "T052 source_checkpoint_id"
        )
        for record in records
    )
    if len(records) != 93 or len(set(identities)) != 93:
        raise T085EvaluationIntegrityError(
            "T052 fixed-cohort record identities are not exactly 93 unique checkpoints"
        )
    return _T085T052ArtifactIdentity(
        path=resolved,
        sha256=digest,
        byte_count=byte_count,
        record_identities=identities,
        records=tuple(records),
    )


def load_t085_t052_cohort_records(
    path: str | Path = T085_T052_COHORT_PATH,
) -> tuple[T085BattleStartRecord, ...]:
    """Load exact T052 identities into the T085 battle-start representation."""

    artifact = _load_t085_t052_artifact(path)
    loaded: list[T085BattleStartRecord] = []
    for raw in artifact.records:
        structural = _required_mapping(
            raw.get("structural_metadata"), "T052 structural_metadata"
        )
        source_run_id = _required_string(raw.get("source_run_id"), "T052 source_run_id")
        checkpoint_id = _required_string(
            raw.get("source_checkpoint_id"), "T052 source_checkpoint_id"
        )
        source_battle_index = _required_int(
            raw.get("source_battle_index"), "T052 source_battle_index"
        )
        public_context_available = raw.get("public_context_status") == "available"
        loaded.append(
            T085BattleStartRecord(
                source_run_seed=_required_int(
                    raw.get("source_seed"), "T052 source_seed"
                ),
                source_run_identity=source_run_id,
                complete_source_identity=checkpoint_id,
                battle_identity=f"{source_run_id}:{source_battle_index}",
                act=_required_int(structural.get("act"), "T052 act"),
                room_type=_required_string(
                    structural.get("room_type"), "T052 room_type"
                ),
                restore_ok=True,
                public_context_match=public_context_available,
                source_valid=True,
                source_artifact_record_identity=checkpoint_id,
            )
        )
    return tuple(loaded)


def _validate_source_domain(
    source_runs: Sequence[T085SourceRunRecord],
    expected_seeds: set[int],
    expected_count: int,
    label: str,
) -> dict[str, object]:
    if len(source_runs) != expected_count:
        raise T085EvaluationIntegrityError(
            f"{label} requires exactly {expected_count} source runs"
        )
    seeds = [run.source_run_seed for run in source_runs]
    if set(seeds) != expected_seeds or len(set(seeds)) != len(seeds):
        raise T085EvaluationIntegrityError(f"{label} source seed domain is invalid")
    identities = [run.complete_source_identity for run in source_runs]
    if len(set(identities)) != len(identities):
        raise T085EvaluationIntegrityError(
            f"{label} contains duplicate complete_source_identity values"
        )
    bad = [run for run in source_runs if not run.source_valid]
    if bad:
        raise T085EvaluationIntegrityError(
            f"{label} source run validity gate failed for {len(bad)} runs"
        )
    return {
        "run_count": len(source_runs),
        "source_run_seed_start": min(seeds),
        "source_run_seed_end": max(seeds),
        "complete_source_identity_count": len(set(identities)),
    }


def _eligible_battle_starts(
    source_runs: Sequence[T085SourceRunRecord],
    battle_starts: Sequence[T085BattleStartRecord],
    *,
    label: str,
) -> tuple[T085BattleStartRecord, ...]:
    source_by_identity = {run.source_run_identity: run for run in source_runs}
    source_by_seed = {run.source_run_seed: run for run in source_runs}
    eligible: list[T085BattleStartRecord] = []
    for record in battle_starts:
        source = source_by_seed.get(record.source_run_seed)
        if source is None or source.source_run_identity != record.source_run_identity:
            raise T085EvaluationIntegrityError(
                f"{label} battle start is not bound to the frozen source run"
            )
        if source.complete_source_identity != record.complete_source_identity:
            raise T085EvaluationIntegrityError(
                f"{label} complete source identity does not match source manifest"
            )
        if (
            record.source_run_identity not in source_by_identity
            or not record.restore_ok
            or not record.public_context_match
            or not record.source_valid
            or record.failure_reason is not None
        ):
            continue
        eligible.append(record)
    if len({record.selection_identity for record in eligible}) != len(eligible):
        raise T085EvaluationIntegrityError(f"{label} has duplicate battle identities")
    return tuple(eligible)


def validate_cohort_a(
    records: Sequence[T085BattleStartRecord | Mapping[str, object]],
    *,
    artifact_path: str | Path = T085_T052_COHORT_PATH,
    artifact_sha256: str | None = None,
) -> dict[str, object]:
    """Validate the unchanged 93-record T052 stress boundary."""

    if artifact_sha256 is not None and artifact_sha256 != T085_T052_COHORT_SHA256:
        raise T085EvaluationIntegrityError("Cohort A is not the accepted T052 artifact")
    artifact = _load_t085_t052_artifact(artifact_path)
    if artifact_sha256 is not None and artifact_sha256 != artifact.sha256:
        raise T085EvaluationIntegrityError(
            "Cohort A caller SHA-256 does not match the T052 file bytes"
        )
    normalized = _coerce_battle_starts(records)
    if len(normalized) != 93:
        raise T085EvaluationIntegrityError("Cohort A requires exactly 93 records")
    supplied_ids = tuple(
        record.source_artifact_record_identity for record in normalized
    )
    if any(identity is None for identity in supplied_ids):
        raise T085EvaluationIntegrityError(
            "Cohort A records must carry their retained T052 artifact identities"
        )
    if supplied_ids != artifact.record_identities:
        raise T085EvaluationIntegrityError(
            "Cohort A records do not match the exact retained T052 record identities"
        )
    if any(
        record.complete_source_identity != record.source_artifact_record_identity
        for record in normalized
    ):
        raise T085EvaluationIntegrityError(
            "Cohort A complete source identities are not bound to T052 records"
        )
    if len({record.selection_identity for record in normalized}) != 93:
        raise T085EvaluationIntegrityError("Cohort A record identities are not unique")
    if any(
        not record.restore_ok
        or not record.public_context_match
        or not record.source_valid
        or record.failure_reason is not None
        for record in normalized
    ):
        raise T085EvaluationIntegrityError(
            "Cohort A restore/public-context gate failed"
        )
    return {
        "cohort": "A",
        "artifact_path": str(artifact.path),
        "artifact_sha256": artifact.sha256,
        "artifact_byte_count": artifact.byte_count,
        "artifact_record_identity_sha256": _sha256_json(
            list(artifact.record_identities)
        ),
        "record_count": len(normalized),
        "record_identity_order": [record.selection_identity for record in normalized],
        "selected_records": _selection_record_manifest(normalized),
        "room_type_counts": dict(Counter(record.room_type for record in normalized)),
    }


def audit_cohort_b_source_overlap(
    cohort_b_records: Sequence[T085SourceRunRecord | Mapping[str, object]],
    *,
    t084_complete_source_identities: Iterable[str],
    t052_complete_source_identities: Iterable[str],
) -> dict[str, object]:
    """Prove fresh Cohort-B complete sources are disjoint from prior roots."""

    source_records = _coerce_source_runs(cohort_b_records)
    if len(source_records) != T085_COHORT_B_RUN_COUNT:
        raise T085EvaluationIntegrityError(
            "Cohort B overlap audit requires the complete 1024-run source pool"
        )
    seeds = [record.source_run_seed for record in source_records]
    if set(seeds) != _seed_domain(T085_COHORT_B_SEED_START, T085_COHORT_B_SEED_END):
        raise T085EvaluationIntegrityError(
            "Cohort B overlap audit source seed domain is invalid"
        )
    if len(set(seeds)) != len(seeds):
        raise T085EvaluationIntegrityError(
            "Cohort B overlap audit source seeds are duplicated"
        )
    source_run_ids = [record.source_run_identity for record in source_records]
    if len(set(source_run_ids)) != len(source_run_ids):
        raise T085EvaluationIntegrityError(
            "Cohort B overlap audit source run identities are not unique"
        )
    b_identities = [record.complete_source_identity for record in source_records]
    if len(set(b_identities)) != len(b_identities):
        raise T085EvaluationIntegrityError(
            "Cohort B complete_source_identity values are not unique"
        )
    t084 = set(t084_complete_source_identities)
    t052 = set(t052_complete_source_identities)
    if not t084 or not t052:
        raise T085EvaluationIntegrityError(
            "Cohort B overlap audit requires non-empty T084 and T052 identity inventories"
        )
    overlap_t084 = sorted(set(b_identities) & t084)
    overlap_t052 = sorted(set(b_identities) & t052)
    if overlap_t084 or overlap_t052:
        raise T085EvaluationIntegrityError(
            "Cohort B has forbidden complete-source overlap with T084/T052"
        )
    return {
        "schema_id": "t085-cohort-b-complete-source-overlap-audit-v1",
        "cohort_b_identity_count": len(set(b_identities)),
        "t084_identity_count": len(t084),
        "t052_identity_count": len(t052),
        "overlap_t084_count": len(overlap_t084),
        "overlap_t052_count": len(overlap_t052),
        "zero_overlap": True,
    }


def validate_t085_source_generation_contract(
    manifest: Mapping[str, object],
    *,
    cohort: str,
) -> dict[str, object]:
    """Validate frozen source-generation fields before cohort selection."""

    if cohort not in {"B", "C"}:
        raise T085EvaluationIntegrityError("source generation cohort must be B or C")
    required_common = {
        "schema_id": T085_SOURCE_MANIFEST_SCHEMA_ID,
        "ascension": 20,
        "max_outer_steps": 500,
        "action_space": "initial_no_potions",
        "non_combat_controller": "expert_non_combat_v1",
        "non_combat_policy_seed": 42042,
        "source_outcome_independent": True,
        "repaired_checkpoint_used": False,
        "source_manifest_frozen": True,
    }
    for key, expected in required_common.items():
        if manifest.get(key) != expected:
            raise T085EvaluationIntegrityError(
                f"Cohort {cohort} source-generation field {key} is not frozen"
            )
    if cohort == "B":
        expected = {
            "source_run_count": T085_COHORT_B_RUN_COUNT,
            "source_run_seeds": list(
                range(T085_COHORT_B_SEED_START, T085_COHORT_B_SEED_END + 1)
            ),
            "battle_controller": "oracle_search",
            "battle_simulations": 20,
            "root_selection": "highest_mean",
            "assistance_level": "assist_hp75_potion",
            "assistance_policy_seed": 42042,
            "t042_scale_manifest_sha256": T085_T042_SCALE_MANIFEST_SHA256,
        }
    else:
        expected = {
            "source_run_count": T085_COHORT_C_RUN_COUNT,
            "source_run_seeds": list(
                range(T085_COHORT_C_SEED_START, T085_COHORT_C_SEED_END + 1)
            ),
            "battle_controller": "unguided_search_v2",
            "battle_simulations": 100,
            "root_selection": "highest_mean",
            "assistance_level": "assist_0",
            "assistance_policy_seed": None,
        }
    for key, expected_value in expected.items():
        if manifest.get(key) != expected_value:
            raise T085EvaluationIntegrityError(
                f"Cohort {cohort} source-generation field {key} does not match contract"
            )
    if manifest.get("source_run_seed_inventory") != expected["source_run_seeds"]:
        raise T085EvaluationIntegrityError(
            f"Cohort {cohort} source_run_seed_inventory does not match contract"
        )
    for key in (
        "source_run_identity_inventory",
        "complete_source_identity_inventory",
    ):
        inventory = manifest.get(key)
        if (
            not isinstance(inventory, list)
            or len(inventory) != expected["source_run_count"]
        ):
            raise T085EvaluationIntegrityError(
                f"Cohort {cohort} {key} must contain the complete source pool"
            )
        if any(not isinstance(value, str) or not value for value in inventory):
            raise T085EvaluationIntegrityError(
                f"Cohort {cohort} {key} contains an invalid identity"
            )
        if len(set(inventory)) != len(inventory):
            raise T085EvaluationIntegrityError(
                f"Cohort {cohort} {key} contains duplicate identities"
            )
    source_manifest_path = _required_string(
        manifest.get("source_manifest_path"),
        f"Cohort {cohort} source_manifest_path",
    )
    if not Path(source_manifest_path).is_absolute():
        raise T085EvaluationIntegrityError(
            f"Cohort {cohort} source_manifest_path must be absolute"
        )
    source_manifest_sha256 = _required_string(
        manifest.get("source_manifest_sha256"),
        f"Cohort {cohort} source_manifest_sha256",
    )
    if not _is_sha256(source_manifest_sha256):
        raise T085EvaluationIntegrityError(
            f"Cohort {cohort} source_manifest_sha256 is not a SHA-256 digest"
        )
    source_manifest_byte_count = _required_int(
        manifest.get("source_manifest_byte_count"),
        f"Cohort {cohort} source_manifest_byte_count",
    )
    if source_manifest_byte_count <= 0:
        raise T085EvaluationIntegrityError(
            f"Cohort {cohort} source_manifest_byte_count must be positive"
        )
    return {
        "cohort": cohort,
        "validated": True,
        "source_run_count": expected["source_run_count"],
        "source_run_seed_range": {
            "start": expected["source_run_seeds"][0],
            "end": expected["source_run_seeds"][-1],
        },
        "source_manifest": {
            "path": source_manifest_path,
            "sha256": source_manifest_sha256,
            "byte_count": source_manifest_byte_count,
            "frozen": True,
        },
        "source_inventory": {
            key: list(manifest[key]) for key in T085_SOURCE_INVENTORY_KEYS
        },
        "frozen_fields": dict(required_common) | dict(expected),
    }


def _verify_t085_source_manifest_artifact(
    manifest: Mapping[str, object],
    *,
    contract: Mapping[str, object],
) -> dict[str, object]:
    """Bind the frozen config to the actual retained source manifest bytes."""

    source = _required_mapping(contract.get("source_manifest"), "source_manifest")
    path = Path(_required_string(source.get("path"), "source_manifest.path")).resolve()
    _require_t085_output_path(path)
    if not path.is_file():
        raise T085EvaluationIntegrityError(
            "frozen T085 source-generation manifest is unavailable"
        )
    if sha256_file(path) != source.get("sha256"):
        raise T085EvaluationIntegrityError(
            "frozen T085 source-generation manifest hash changed"
        )
    if path.stat().st_size != source.get("byte_count"):
        raise T085EvaluationIntegrityError(
            "frozen T085 source-generation manifest size changed"
        )
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise T085EvaluationIntegrityError(
            "frozen T085 source-generation manifest is unreadable"
        ) from exc
    if not isinstance(document, Mapping):
        raise T085EvaluationIntegrityError(
            "frozen T085 source-generation manifest is not an object"
        )
    for key, value in manifest.items():
        if key in {
            "source_manifest_path",
            "source_manifest_sha256",
            "source_manifest_byte_count",
        }:
            continue
        if document.get(key) != value:
            raise T085EvaluationIntegrityError(
                f"source-generation manifest file disagrees on {key}"
            )
    return {
        "path": str(path),
        "schema_id": document.get("schema_id"),
        "sha256": source.get("sha256"),
        "byte_count": source.get("byte_count"),
        "frozen": True,
        **{key: list(document[key]) for key in T085_SOURCE_INVENTORY_KEYS},
    }


def _validate_t085_source_inventory(
    source_runs: Sequence[T085SourceRunRecord],
    source_manifest: Mapping[str, object],
    *,
    cohort: str,
) -> None:
    """Bind selected source-run objects to the frozen manifest inventory."""

    actual = {
        "source_run_seed_inventory": [run.source_run_seed for run in source_runs],
        "source_run_identity_inventory": [
            run.source_run_identity for run in source_runs
        ],
        "complete_source_identity_inventory": [
            run.complete_source_identity for run in source_runs
        ],
    }
    for key, values in actual.items():
        if source_manifest.get(key) != values:
            raise T085EvaluationIntegrityError(
                f"Cohort {cohort} source records do not match frozen {key}"
            )


def _selection_identity_sha256(
    records: Sequence[T085BattleStartRecord],
) -> str:
    return _sha256_json([record.selection_identity for record in records])


def _selection_record_manifest(
    records: Sequence[T085BattleStartRecord],
) -> list[dict[str, object]]:
    return [
        {
            "source_run_seed": record.source_run_seed,
            "source_run_identity": record.source_run_identity,
            "complete_source_identity": record.complete_source_identity,
            "battle_identity": record.battle_identity,
            "selection_identity": record.selection_identity,
            "act": record.act,
            "room_type": record.room_type,
            "restore_ok": record.restore_ok,
            "public_context_match": record.public_context_match,
            "source_valid": record.source_valid,
            "failure_reason": record.failure_reason,
            "source_artifact_record_identity": record.source_artifact_record_identity,
        }
        for record in records
    ]


def build_t085_cohort_selection(
    *,
    cohort: str,
    source_manifest: Mapping[str, object],
    source_runs: Sequence[T085SourceRunRecord | Mapping[str, object]],
    battle_starts: Sequence[T085BattleStartRecord | Mapping[str, object]],
    restore_results: Mapping[str, Mapping[str, object]],
    t084_complete_source_identities: Iterable[str] | None = None,
    t052_complete_source_identities: Iterable[str] | None = None,
) -> tuple[tuple[T085BattleStartRecord, ...], dict[str, object]]:
    """Run the source-freeze, overlap, selection, and restore gates together.

    The lower-level selectors remain useful for deterministic unit diagnostics,
    but an evaluation claim must consume this composition result.  Every
    source manifest is hashed from its stable artifact path before records are
    selected, and every returned selection is paired with fresh restore/parity
    evidence.
    """

    contract = validate_t085_source_generation_contract(
        source_manifest,
        cohort=cohort,
    )
    source_reference = _verify_t085_source_manifest_artifact(
        source_manifest,
        contract=contract,
    )
    runs = _coerce_source_runs(source_runs)
    _validate_t085_source_inventory(runs, source_manifest, cohort=cohort)
    if cohort == "B":
        if not t084_complete_source_identities or not t052_complete_source_identities:
            raise T085EvaluationIntegrityError(
                "Cohort B selection requires explicit non-empty T084/T052 identities"
            )
        overlap = audit_cohort_b_source_overlap(
            runs,
            t084_complete_source_identities=t084_complete_source_identities,
            t052_complete_source_identities=t052_complete_source_identities,
        )
        selected, selection_summary = select_cohort_b(runs, battle_starts)
        selected_400, search_400_summary = select_search_400_subset(selected)
        parity = validate_t085_restore_parity(selected, restore_results)
        search_400_restore = {
            identity: restore_results[identity]
            for identity in (record.selection_identity for record in selected_400)
        }
        search_400_parity = validate_t085_restore_parity(
            selected_400,
            search_400_restore,
        )
        return selected, {
            "schema_id": T085_SELECTION_EVIDENCE_SCHEMA_ID,
            "cohort": "B",
            "selected_count": len(selected),
            "selected_identity_order": [
                record.selection_identity for record in selected
            ],
            "selected_records": _selection_record_manifest(selected),
            "selected_identity_sha256": _selection_identity_sha256(selected),
            "source_run_count": T085_COHORT_B_RUN_COUNT,
            "source_run_seed_inventory": [run.source_run_seed for run in runs],
            "source_run_identity_inventory": [run.source_run_identity for run in runs],
            "complete_source_identity_inventory": [
                run.complete_source_identity for run in runs
            ],
            "source_generation_valid": True,
            "source_manifest": source_reference,
            "source_manifest_sha256": source_reference["sha256"],
            "source_frozen": True,
            "selection_summary": selection_summary,
            "overlap_audit": overlap,
            "zero_overlap": overlap["zero_overlap"],
            "restore_parity": parity,
            "restore_parity_passed": parity["passed"],
            "search_400": {
                "selected_count": len(selected_400),
                "selected_identity_order": [
                    record.selection_identity for record in selected_400
                ],
                "selected_records": _selection_record_manifest(selected_400),
                "selected_identity_sha256": _selection_identity_sha256(selected_400),
                "selection_summary": search_400_summary,
                "restore_parity": search_400_parity,
                "restore_parity_passed": search_400_parity["passed"],
                "source_manifest": source_reference,
                "source_manifest_sha256": source_reference["sha256"],
                "source_frozen": True,
            },
        }
    if cohort == "C":
        selected, selection_summary = select_cohort_c(runs, battle_starts)
        parity = validate_t085_restore_parity(selected, restore_results)
        return selected, {
            "schema_id": T085_SELECTION_EVIDENCE_SCHEMA_ID,
            "cohort": "C",
            "selected_count": len(selected),
            "selected_identity_order": [
                record.selection_identity for record in selected
            ],
            "selected_records": _selection_record_manifest(selected),
            "selected_identity_sha256": _selection_identity_sha256(selected),
            "source_run_count": T085_COHORT_C_RUN_COUNT,
            "source_run_seed_inventory": [run.source_run_seed for run in runs],
            "source_run_identity_inventory": [run.source_run_identity for run in runs],
            "complete_source_identity_inventory": [
                run.complete_source_identity for run in runs
            ],
            "source_generation_valid": True,
            "source_manifest": source_reference,
            "source_manifest_sha256": source_reference["sha256"],
            "source_frozen": True,
            "selection_summary": selection_summary,
            "restore_parity": parity,
            "restore_parity_passed": parity["passed"],
        }
    raise T085EvaluationIntegrityError("T085 composition cohort must be B or C")


def build_t085_evaluation_selection_evidence(
    *,
    cohort_a_records: Sequence[T085BattleStartRecord],
    cohort_a_restore_results: Mapping[str, Mapping[str, object]],
    cohort_b_records: Sequence[T085BattleStartRecord],
    cohort_b_selection_evidence: Mapping[str, object],
    cohort_c_records: Sequence[T085BattleStartRecord],
    cohort_c_selection_evidence: Mapping[str, object],
    search_400_records: Sequence[T085BattleStartRecord],
) -> dict[str, Mapping[str, object]]:
    """Compose A/B/C and Search@400 gates into the evaluation input contract."""

    a_summary = validate_cohort_a(cohort_a_records)
    a_parity = validate_t085_restore_parity(
        cohort_a_records,
        cohort_a_restore_results,
    )
    b_evidence = _required_mapping(
        cohort_b_selection_evidence,
        "cohort_b_selection_evidence",
    )
    c_evidence = _required_mapping(
        cohort_c_selection_evidence,
        "cohort_c_selection_evidence",
    )
    if b_evidence.get("cohort") != "B" or c_evidence.get("cohort") != "C":
        raise T085EvaluationIntegrityError(
            "B/C selection evidence is bound to the wrong cohort"
        )
    b_ids = [record.selection_identity for record in cohort_b_records]
    c_ids = [record.selection_identity for record in cohort_c_records]
    search_ids = [record.selection_identity for record in search_400_records]
    if (
        b_evidence.get("selected_count") != len(b_ids)
        or b_evidence.get("selected_identity_order") != b_ids
        or b_evidence.get("selected_records")
        != _selection_record_manifest(cohort_b_records)
        or b_evidence.get("selected_identity_sha256") != _sha256_json(b_ids)
    ):
        raise T085EvaluationIntegrityError(
            "Cohort B selection evidence does not match selected records"
        )
    if (
        c_evidence.get("selected_count") != len(c_ids)
        or c_evidence.get("selected_identity_order") != c_ids
        or c_evidence.get("selected_records")
        != _selection_record_manifest(cohort_c_records)
        or c_evidence.get("selected_identity_sha256") != _sha256_json(c_ids)
    ):
        raise T085EvaluationIntegrityError(
            "Cohort C selection evidence does not match selected records"
        )
    b_search = _required_mapping(b_evidence.get("search_400"), "B.search_400")
    if (
        b_search.get("selected_count") != len(search_ids)
        or b_search.get("selected_identity_order") != search_ids
        or b_search.get("selected_records")
        != _selection_record_manifest(search_400_records)
        or b_search.get("selected_identity_sha256") != _sha256_json(search_ids)
    ):
        raise T085EvaluationIntegrityError(
            "Search@400 selection evidence does not match selected records"
        )
    if not set(search_ids).issubset(set(b_ids)):
        raise T085EvaluationIntegrityError(
            "Search@400 selected records are not a subset of Cohort B"
        )
    a_evidence = {
        "schema_id": T085_SELECTION_EVIDENCE_SCHEMA_ID,
        "cohort": "A",
        "selected_count": len(cohort_a_records),
        "selected_identity_order": [
            record.selection_identity for record in cohort_a_records
        ],
        "selected_records": _selection_record_manifest(cohort_a_records),
        "selected_identity_sha256": _selection_identity_sha256(cohort_a_records),
        "artifact": {
            "path": a_summary["artifact_path"],
            "schema_id": T085_T052_COHORT_SCHEMA_ID,
            "sha256": a_summary["artifact_sha256"],
            "byte_count": a_summary["artifact_byte_count"],
        },
        "artifact_validated": True,
        "source_generation_valid": True,
        "source_frozen": True,
        "restore_parity": a_parity,
        "restore_parity_passed": a_parity["passed"],
    }
    search_evidence = {
        "schema_id": T085_SELECTION_EVIDENCE_SCHEMA_ID,
        "cohort": "B@400",
        "selected_count": len(search_400_records),
        "selected_identity_order": search_ids,
        "selected_records": _selection_record_manifest(search_400_records),
        "selected_identity_sha256": _selection_identity_sha256(search_400_records),
        "parent_selected_identity_sha256": _sha256_json(b_ids),
        "source_run_count": T085_COHORT_B_RUN_COUNT,
        "source_run_seed_inventory": b_evidence["source_run_seed_inventory"],
        "source_run_identity_inventory": b_evidence["source_run_identity_inventory"],
        "complete_source_identity_inventory": b_evidence[
            "complete_source_identity_inventory"
        ],
        "source_generation_valid": b_evidence["source_generation_valid"],
        "source_frozen": b_evidence["source_frozen"],
        "source_manifest": b_evidence["source_manifest"],
        "restore_parity": b_search["restore_parity"],
        "restore_parity_passed": b_search["restore_parity_passed"],
    }
    combined = {
        "A": a_evidence,
        "B": b_evidence,
        "C": c_evidence,
        "B@400": search_evidence,
    }
    validate_t085_evaluation_selection_evidence(
        {
            "A": cohort_a_records,
            "B": cohort_b_records,
            "C": cohort_c_records,
            "B@400": search_400_records,
        },
        combined,
    )
    return combined


def select_cohort_b(
    source_runs: Sequence[T085SourceRunRecord | Mapping[str, object]],
    battle_starts: Sequence[T085BattleStartRecord | Mapping[str, object]],
) -> tuple[tuple[T085BattleStartRecord, ...], dict[str, object]]:
    """Select the fixed 96/96 holdout without reading outcome fields."""

    runs = _coerce_source_runs(source_runs)
    starts = _coerce_battle_starts(battle_starts)
    source_summary = _validate_source_domain(
        runs,
        _seed_domain(T085_COHORT_B_SEED_START, T085_COHORT_B_SEED_END),
        T085_COHORT_B_RUN_COUNT,
        "Cohort B",
    )
    eligible = _eligible_battle_starts(runs, starts, label="Cohort B")
    by_act: dict[str, list[T085BattleStartRecord]] = {"act1": [], "act2_plus": []}
    for record in eligible:
        by_act["act1" if record.act == 1 else "act2_plus"].append(record)
    for cell, values in by_act.items():
        values.sort(
            key=lambda record: (
                _sha256_text(record.complete_source_identity),
                record.selection_identity,
            )
        )
        if len(values) < 96:
            raise T085EvaluationIntegrityError(
                f"Cohort B {cell} cannot satisfy the fixed 96-record quota"
            )
    selected = tuple(by_act["act1"][:96] + by_act["act2_plus"][:96])
    if len(selected) != T085_COHORT_B_SELECTED_COUNT:
        raise T085EvaluationIntegrityError("Cohort B selection count is not 192")
    summary = {
        "cohort": "B",
        "source": source_summary,
        "eligibility_count": len(eligible),
        "selected_count": len(selected),
        "selected_act_counts": dict(
            Counter("1" if record.act == 1 else "2+" for record in selected)
        ),
        "selected_room_type_counts": dict(
            Counter(record.room_type for record in selected)
        ),
        "selection_rule": "sha256(complete_source_identity), then source_run_identity:battle_identity",
        "outcome_blind": True,
    }
    return selected, summary


def select_cohort_c(
    source_runs: Sequence[T085SourceRunRecord | Mapping[str, object]],
    battle_starts: Sequence[T085BattleStartRecord | Mapping[str, object]],
) -> tuple[tuple[T085BattleStartRecord, ...], dict[str, object]]:
    """Select one valid battle start per exact current-policy source run."""

    runs = _coerce_source_runs(source_runs)
    starts = _coerce_battle_starts(battle_starts)
    source_summary = _validate_source_domain(
        runs,
        _seed_domain(T085_COHORT_C_SEED_START, T085_COHORT_C_SEED_END),
        T085_COHORT_C_RUN_COUNT,
        "Cohort C",
    )
    eligible = _eligible_battle_starts(runs, starts, label="Cohort C")
    by_run: dict[str, list[T085BattleStartRecord]] = defaultdict(list)
    for record in eligible:
        by_run[record.source_run_identity].append(record)
    selected: list[T085BattleStartRecord] = []
    for run in runs:
        candidates = by_run.get(run.source_run_identity, [])
        if candidates:
            selected.append(
                min(
                    candidates,
                    key=lambda record: _sha256_text(record.selection_identity),
                )
            )
    if len(selected) < T085_COHORT_C_MIN_SELECTED_COUNT:
        raise T085EvaluationIntegrityError(
            "Cohort C cannot satisfy the minimum 96 selected records"
        )
    summary = {
        "cohort": "C",
        "source": source_summary,
        "eligibility_count": len(eligible),
        "selected_count": len(selected),
        "selected_act_counts": dict(Counter(str(record.act) for record in selected)),
        "selected_room_type_counts": dict(
            Counter(record.room_type for record in selected)
        ),
        "selection_rule": "sha256(source_run_identity:battle_identity) per source run",
        "one_record_per_source_run": True,
        "outcome_blind": True,
    }
    return tuple(selected), summary


def select_search_400_subset(
    cohort_b_records: Sequence[T085BattleStartRecord],
) -> tuple[tuple[T085BattleStartRecord, ...], dict[str, object]]:
    """Select the frozen 24/24 Search@400 guard before any outcome is read."""

    cells: dict[str, list[T085BattleStartRecord]] = {"act1": [], "act2_plus": []}
    for record in cohort_b_records:
        cells["act1" if record.act == 1 else "act2_plus"].append(record)
    for values in cells.values():
        values.sort(key=lambda record: _sha256_text(record.selection_identity))
        if len(values) < 24:
            raise T085EvaluationIntegrityError(
                "Search@400 cell cannot satisfy 24 records"
            )
    selected = tuple(cells["act1"][:24] + cells["act2_plus"][:24])
    return selected, {
        "cohort": "B",
        "budget": 400,
        "selected_count": len(selected),
        "selected_act_counts": {"1": 24, "2+": 24},
        "selection_rule": "sha256(source_run_identity:battle_identity)",
        "outcome_blind": True,
    }


def validate_t085_restore_parity(
    records: Sequence[T085BattleStartRecord],
    restore_results: Mapping[str, Mapping[str, object]],
) -> dict[str, object]:
    """Require fresh native restore and public-context parity per selected row."""

    expected = {record.selection_identity for record in records}
    if set(restore_results) != expected:
        missing = sorted(expected - set(restore_results))
        extra = sorted(set(restore_results) - expected)
        raise T085EvaluationIntegrityError(
            f"restore/parity identity mismatch; missing={missing}, extra={extra}"
        )
    for identity, result in restore_results.items():
        if result.get("restore_ok") is not True:
            raise T085EvaluationIntegrityError(f"restore failed for {identity}")
        if result.get("public_context_match") is not True:
            raise T085EvaluationIntegrityError(
                f"public-context parity failed for {identity}"
            )
    return {
        "schema_id": "t085-restore-public-context-parity-v1",
        "record_count": len(records),
        "restored_count": len(restore_results),
        "public_context_matched_count": len(restore_results),
        "passed": True,
    }


def _validated_outcomes(
    records: Iterable[T085OutcomeRecord | Mapping[str, object]],
) -> tuple[T085OutcomeRecord, ...]:
    normalized = tuple(
        record
        if isinstance(record, T085OutcomeRecord)
        else T085OutcomeRecord.from_mapping(record)
        for record in records
    )
    for record in normalized:
        if record.failure_reason is not None:
            raise T085EvaluationIntegrityError(
                f"evaluation row {record.record_identity}/{record.arm} failed: "
                + record.failure_reason
            )
    return normalized


def _validate_outcomes_against_selection(
    outcomes: Sequence[T085OutcomeRecord],
    selection_cohorts: Mapping[
        str,
        Sequence[T085BattleStartRecord | Mapping[str, object]],
    ],
) -> dict[str, tuple[T085BattleStartRecord, ...]]:
    """Bind every retained outcome to the frozen record, arm, and budget."""

    required_cohorts = {"A", "B", "C", "B@400"}
    if set(selection_cohorts) != required_cohorts:
        raise T085EvaluationIntegrityError(
            "outcome binding requires exactly A, B, C, and B@400 selections"
        )
    normalized = {
        cohort: _coerce_battle_starts(selection_cohorts[cohort])
        for cohort in required_cohorts
    }
    plan_arms = {
        "A": set(T085_PRIMARY_ARMS),
        "B": set(T085_PRIMARY_ARMS + T085_SECONDARY_ARMS),
        "C": set(T085_PRIMARY_ARMS),
        "B@400": set(T085_SEARCH_400_ARMS),
    }
    plan_budgets = {
        "A": T085_SEARCH_BUDGET,
        "B": T085_SEARCH_BUDGET,
        "C": T085_SEARCH_BUDGET,
        "B@400": T085_SEARCH_400_BUDGET,
    }
    for cohort in ("A", "B", "C", "B@400"):
        records = normalized[cohort]
        expected_by_id = {record.selection_identity: record for record in records}
        if len(expected_by_id) != len(records):
            raise T085EvaluationIntegrityError(
                f"selection cohort {cohort} contains duplicate identities"
            )
        cohort_outcomes = [row for row in outcomes if row.cohort == cohort]
        actual_ids = {row.record_identity for row in cohort_outcomes}
        expected_ids = set(expected_by_id)
        if actual_ids != expected_ids:
            missing = sorted(expected_ids - actual_ids)
            extra = sorted(actual_ids - expected_ids)
            raise T085EvaluationIntegrityError(
                f"outcomes for Cohort {cohort} do not match frozen records; "
                f"missing={missing}, extra={extra}"
            )
        for row in cohort_outcomes:
            expected = expected_by_id.get(row.record_identity)
            if expected is None:
                raise T085EvaluationIntegrityError(
                    f"outcome {row.record_identity} is not in frozen Cohort {cohort}"
                )
            if row.arm not in plan_arms[cohort]:
                raise T085EvaluationIntegrityError(
                    f"outcome {row.record_identity}/{row.arm} has an unknown arm"
                )
            if row.search_budget != plan_budgets[cohort]:
                raise T085EvaluationIntegrityError(
                    f"outcome {row.record_identity}/{row.arm} has an invalid "
                    "search budget"
                )
            if row.source_run_identity != expected.source_run_identity:
                raise T085EvaluationIntegrityError(
                    f"outcome {row.record_identity}/{row.arm} is not bound to "
                    "the frozen source run"
                )
    return normalized


def _selection_binding(
    selection_cohorts: Mapping[str, Sequence[T085BattleStartRecord]],
) -> dict[str, object]:
    arms = {
        "A": list(T085_PRIMARY_ARMS),
        "B": list(T085_PRIMARY_ARMS + T085_SECONDARY_ARMS),
        "C": list(T085_PRIMARY_ARMS),
        "B@400": list(T085_SEARCH_400_ARMS),
    }
    budgets = {
        "A": T085_SEARCH_BUDGET,
        "B": T085_SEARCH_BUDGET,
        "C": T085_SEARCH_BUDGET,
        "B@400": T085_SEARCH_400_BUDGET,
    }
    return {
        cohort: {
            "selected_identity_order": [
                record.selection_identity for record in selection_cohorts[cohort]
            ],
            "selected_identity_sha256": _selection_identity_sha256(
                selection_cohorts[cohort]
            ),
            "selected_records": _selection_record_manifest(selection_cohorts[cohort]),
            "arms": arms[cohort],
            "search_budget": budgets[cohort],
        }
        for cohort in ("A", "B", "C", "B@400")
    }


def _validate_outcomes_against_selection_binding(
    outcomes: Sequence[T085OutcomeRecord],
    binding: Mapping[str, object],
) -> None:
    """Recheck a serialized report's outcome rows against its binding."""

    required_cohorts = ("A", "B", "C", "B@400")
    if set(binding) != set(required_cohorts):
        raise T085EvaluationIntegrityError(
            "paired report selection binding must cover exactly A, B, C, and B@400"
        )
    for cohort in required_cohorts:
        value = _required_mapping(binding.get(cohort), f"selection_binding.{cohort}")
        raw_records = value.get("selected_records")
        if not isinstance(raw_records, list):
            raise T085EvaluationIntegrityError(
                f"selection_binding.{cohort}.selected_records is missing"
            )
        expected_ids = [
            _required_string(
                _required_mapping(record, "selection binding record").get(
                    "selection_identity"
                ),
                "selection binding record.selection_identity",
            )
            for record in raw_records
        ]
        if value.get("selected_identity_order") != expected_ids:
            raise T085EvaluationIntegrityError(
                f"selection_binding.{cohort} identity order is inconsistent"
            )
        if value.get("selected_identity_sha256") != _sha256_json(expected_ids):
            raise T085EvaluationIntegrityError(
                f"selection_binding.{cohort} identity digest is inconsistent"
            )
        expected_by_id = {
            record["selection_identity"]: record
            for record in raw_records
            if isinstance(record, Mapping)
        }
        expected_arms = value.get("arms")
        budget = value.get("search_budget")
        if not isinstance(expected_arms, list) or not isinstance(budget, int):
            raise T085EvaluationIntegrityError(
                f"selection_binding.{cohort} arm/budget binding is invalid"
            )
        rows = [row for row in outcomes if row.cohort == cohort]
        if {row.record_identity for row in rows} != set(expected_by_id):
            raise T085EvaluationIntegrityError(
                f"paired report outcomes do not match selection_binding.{cohort}"
            )
        for row in rows:
            expected = expected_by_id.get(row.record_identity)
            if expected is None:
                raise T085EvaluationIntegrityError(
                    f"paired report contains an unknown {cohort} record"
                )
            if row.arm not in expected_arms or row.search_budget != budget:
                raise T085EvaluationIntegrityError(
                    f"paired report {cohort} outcome arm/budget is not bound"
                )
            if row.source_run_identity != expected.get("source_run_identity"):
                raise T085EvaluationIntegrityError(
                    f"paired report {cohort} outcome source is not bound"
                )


def aggregate_paired_outcomes(
    records: Iterable[T085OutcomeRecord | Mapping[str, object]],
    *,
    comparator_arm: str,
    reference_arm: str,
) -> dict[str, object]:
    """Aggregate a paired battle comparison at record, not callback, level."""

    normalized = _validated_outcomes(records)
    accepted_arms = {comparator_arm, reference_arm}
    unknown_arms = {record.arm for record in normalized} - accepted_arms
    if unknown_arms:
        raise T085EvaluationIntegrityError(
            "paired comparison contains unknown arms: "
            + ", ".join(sorted(unknown_arms))
        )
    grouped: dict[str, dict[str, T085OutcomeRecord]] = defaultdict(dict)
    for record in normalized:
        if record.arm in (comparator_arm, reference_arm):
            if record.arm in grouped[record.record_identity]:
                raise T085EvaluationIntegrityError("duplicate paired evaluation row")
            grouped[record.record_identity][record.arm] = record
    pairs = []
    for identity, arms in grouped.items():
        if set(arms) != {comparator_arm, reference_arm}:
            raise T085EvaluationIntegrityError(
                f"paired record {identity} is missing one comparison arm"
            )
        comparator = arms[comparator_arm]
        reference = arms[reference_arm]
        pairs.append((comparator, reference))
    if not pairs:
        raise T085EvaluationIntegrityError("paired comparison has no records")
    comparator_only_wins = sum(
        comparator.battle_survived and not reference.battle_survived
        for comparator, reference in pairs
    )
    reference_only_wins = sum(
        reference.battle_survived and not comparator.battle_survived
        for comparator, reference in pairs
    )
    deltas = [
        comparator.terminal_native_utility - reference.terminal_native_utility
        for comparator, reference in pairs
    ]
    return {
        "comparator_arm": comparator_arm,
        "reference_arm": reference_arm,
        "record_count": len(pairs),
        "comparator_wins": comparator_only_wins,
        "reference_wins": reference_only_wins,
        "paired_win_delta": comparator_only_wins - reference_only_wins,
        "utility_deltas": deltas,
        "mean_utility_delta": sum(deltas) / len(deltas),
        "median_utility_delta": _median(deltas),
        "record_identities": sorted(identity for identity in grouped),
    }


def _median(values: Sequence[float]) -> float:
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return float(ordered[middle])
    return (float(ordered[middle - 1]) + float(ordered[middle])) / 2.0


def bootstrap_mean_percentile(
    values: Sequence[float],
    *,
    seed: int = T085_BOOTSTRAP_SEED,
    resample_count: int = T085_BOOTSTRAP_COUNT,
) -> dict[str, object]:
    """Run the fixed battle-record bootstrap and return percentile bounds."""

    if not values:
        raise T085EvaluationIntegrityError("bootstrap requires at least one record")
    if resample_count != T085_BOOTSTRAP_COUNT:
        raise T085EvaluationIntegrityError("T085 bootstrap count must be exactly 10000")
    if seed != T085_BOOTSTRAP_SEED:
        raise T085EvaluationIntegrityError("T085 bootstrap seed must be exactly 85085")
    clean = [_required_finite(value, "bootstrap value") for value in values]
    rng = random.Random(seed)
    means: list[float] = []
    for _ in range(resample_count):
        total = sum(clean[rng.randrange(len(clean))] for _ in clean)
        means.append(total / len(clean))
    means.sort()
    return {
        "sampling_unit": "battle_record",
        "seed": seed,
        "resample_count": resample_count,
        "observed_mean": sum(clean) / len(clean),
        "percentile_2_5": _percentile(means, 0.025),
        "percentile_97_5": _percentile(means, 0.975),
    }


def _percentile(sorted_values: Sequence[float], quantile: float) -> float:
    position = (len(sorted_values) - 1) * quantile
    low = math.floor(position)
    high = math.ceil(position)
    if low == high:
        return float(sorted_values[low])
    fraction = position - low
    return float(sorted_values[low]) + fraction * (
        float(sorted_values[high]) - float(sorted_values[low])
    )


def _cohort_primary_reports(
    records: Sequence[T085OutcomeRecord],
    cohort: str,
) -> dict[str, object]:
    cohort_rows = [record for record in records if record.cohort == cohort]
    required = set(T085_PRIMARY_ARMS)
    present = {record.arm for record in cohort_rows}
    if not required.issubset(present):
        raise T085EvaluationIntegrityError(
            f"Cohort {cohort} is missing primary arms: {sorted(required - present)}"
        )

    def pair(comparator_arm: str, reference_arm: str) -> dict[str, object]:
        return aggregate_paired_outcomes(
            [
                record
                for record in cohort_rows
                if record.arm in {comparator_arm, reference_arm}
            ],
            comparator_arm=comparator_arm,
            reference_arm=reference_arm,
        )

    reports = {
        "corrected_85001_vs_baseline": pair("corrected_value_85001", "baseline"),
        "corrected_85002_vs_baseline": pair("corrected_value_85002", "baseline"),
        "corrected_85001_vs_old": pair("corrected_value_85001", "old_value_64001"),
        "corrected_85002_vs_old": pair("corrected_value_85002", "old_value_64002"),
    }
    return {"cohort": cohort, "arms": sorted(present), "comparisons": reports}


def build_t085_paired_evaluation_report(
    records: Iterable[T085OutcomeRecord | Mapping[str, object]],
    *,
    cohort_b_record_count: int,
    cohort_c_record_count: int,
    selection_cohorts: Mapping[
        str,
        Sequence[T085BattleStartRecord | Mapping[str, object]],
    ]
    | None = None,
    selection_evidence: Mapping[str, Mapping[str, object]] | None = None,
) -> dict[str, object]:
    """Build primary, secondary, guard, and fixed-bootstrap reports."""

    normalized = _validated_outcomes(records)
    normalized_selection: dict[str, tuple[T085BattleStartRecord, ...]] | None = None
    if (selection_cohorts is None) != (selection_evidence is None):
        raise T085EvaluationIntegrityError(
            "paired report selection cohorts and evidence must be supplied together"
        )
    if selection_cohorts is not None and selection_evidence is not None:
        validate_t085_evaluation_selection_evidence(
            selection_cohorts,
            selection_evidence,
        )
        normalized_selection = _validate_outcomes_against_selection(
            normalized,
            selection_cohorts,
        )
    expected_arms_by_cohort = {
        "A": set(T085_PRIMARY_ARMS),
        "B": set(T085_PRIMARY_ARMS + T085_SECONDARY_ARMS),
        "C": set(T085_PRIMARY_ARMS),
        "B@400": set(T085_SEARCH_400_ARMS),
    }
    rows_by_cohort: dict[str, list[T085OutcomeRecord]] = defaultdict(list)
    for record in normalized:
        if record.cohort not in expected_arms_by_cohort:
            raise T085EvaluationIntegrityError(
                f"unknown T085 evaluation cohort {record.cohort!r}"
            )
        rows_by_cohort[record.cohort].append(record)
    for cohort, cohort_rows in rows_by_cohort.items():
        expected_arms = expected_arms_by_cohort[cohort]
        actual_arms = {record.arm for record in cohort_rows}
        if actual_arms != expected_arms:
            missing = sorted(expected_arms - actual_arms)
            unknown = sorted(actual_arms - expected_arms)
            raise T085EvaluationIntegrityError(
                f"Cohort {cohort} arm matrix mismatch; missing={missing}, unknown={unknown}"
            )
        seen: set[tuple[str, str]] = set()
        for record in cohort_rows:
            identity = (record.record_identity, record.arm)
            if identity in seen:
                raise T085EvaluationIntegrityError(
                    f"duplicate T085 evaluation row {record.record_identity}/{record.arm}"
                )
            seen.add(identity)
        record_ids = {record.record_identity for record in cohort_rows}
        for record_id in record_ids:
            present = {
                record.arm
                for record in cohort_rows
                if record.record_identity == record_id
            }
            if present != expected_arms:
                raise T085EvaluationIntegrityError(
                    f"Cohort {cohort} record {record_id} has an incomplete arm matrix"
                )
    primary = {
        cohort: _cohort_primary_reports(normalized, cohort)
        for cohort in ("A", "B", "C")
    }
    b_rows = [record for record in normalized if record.cohort == "B"]
    c_rows = [record for record in normalized if record.cohort == "C"]
    a_rows = [record for record in normalized if record.cohort == "A"]
    guard_rows = [record for record in normalized if record.cohort == "B@400"]
    actual_a_record_count = len({record.record_identity for record in a_rows})
    actual_b_record_count = len({record.record_identity for record in b_rows})
    actual_c_record_count = len({record.record_identity for record in c_rows})
    actual_search_400_record_count = len(
        {record.record_identity for record in guard_rows}
    )
    if actual_b_record_count != cohort_b_record_count:
        raise T085EvaluationIntegrityError(
            "Cohort B outcome record count is incomplete"
        )
    if actual_c_record_count != cohort_c_record_count:
        raise T085EvaluationIntegrityError(
            "Cohort C outcome record count is incomplete"
        )
    b_by_identity: dict[str, dict[str, T085OutcomeRecord]] = defaultdict(dict)
    for row in b_rows:
        if row.arm in T085_PRIMARY_ARMS:
            b_by_identity[row.record_identity][row.arm] = row
    deltas_old: list[float] = []
    deltas_base: list[float] = []
    for identity, arms in b_by_identity.items():
        if not set(T085_PRIMARY_ARMS).issubset(arms):
            raise T085EvaluationIntegrityError(
                f"Cohort B paired aggregation missing arm for {identity}"
            )
        corrected_mean = (
            arms["corrected_value_85001"].terminal_native_utility
            + arms["corrected_value_85002"].terminal_native_utility
        ) / 2.0
        old_mean = (
            arms["old_value_64001"].terminal_native_utility
            + arms["old_value_64002"].terminal_native_utility
        ) / 2.0
        deltas_old.append(corrected_mean - old_mean)
        deltas_base.append(corrected_mean - arms["baseline"].terminal_native_utility)
    secondary_rows = [record for record in normalized if record.cohort == "B"]
    secondary = {
        "prior_corrected_85001_vs_prior_only": aggregate_paired_outcomes(
            [
                record
                for record in secondary_rows
                if record.arm in {"prior_corrected_85001", "prior_only_64001"}
            ],
            comparator_arm="prior_corrected_85001",
            reference_arm="prior_only_64001",
        ),
        "prior_corrected_85002_vs_prior_only": aggregate_paired_outcomes(
            [
                record
                for record in secondary_rows
                if record.arm in {"prior_corrected_85002", "prior_only_64002"}
            ],
            comparator_arm="prior_corrected_85002",
            reference_arm="prior_only_64002",
        ),
    }
    guard = {
        "corrected_85001_vs_baseline": aggregate_paired_outcomes(
            [
                record
                for record in guard_rows
                if record.arm in {"corrected_value_85001@400", "baseline@400"}
            ],
            comparator_arm="corrected_value_85001@400",
            reference_arm="baseline@400",
        ),
        "corrected_85002_vs_baseline": aggregate_paired_outcomes(
            [
                record
                for record in guard_rows
                if record.arm in {"corrected_value_85002@400", "baseline@400"}
            ],
            comparator_arm="corrected_value_85002@400",
            reference_arm="baseline@400",
        ),
    }
    report: dict[str, object] = {
        "schema_id": "t085-paired-evaluation-report-v1",
        "outcomes": [asdict(record) for record in normalized],
        "primary": primary,
        "secondary": secondary,
        "search_400": guard,
        "cohort_b": {
            "record_count": cohort_b_record_count,
            "delta_old": bootstrap_mean_percentile(deltas_old),
            "delta_base": bootstrap_mean_percentile(deltas_base),
            "paired_delta_old_values": deltas_old,
            "paired_delta_base_values": deltas_base,
        },
        "support": {
            "cohort_a_record_count": actual_a_record_count,
            "cohort_b_record_count": actual_b_record_count,
            "cohort_c_record_count": actual_c_record_count,
            "search_400_record_count": actual_search_400_record_count,
            "cohort_a_exact": actual_a_record_count == 93,
            "cohort_b_exact": actual_b_record_count == T085_COHORT_B_SELECTED_COUNT,
            "cohort_c_minimum": actual_c_record_count
            >= T085_COHORT_C_MIN_SELECTED_COUNT,
            "search_400_exact": actual_search_400_record_count
            == T085_SEARCH_400_SELECTED_COUNT,
        },
        "outcome_record_count": len(normalized),
    }
    if normalized_selection is not None:
        report["selection_binding"] = _selection_binding(normalized_selection)
    return report


def _verify_t085_artifact_reference(
    reference_value: object,
    label: str,
    *,
    exact_path: Path | None = None,
    require_t085_root: bool = False,
) -> dict[str, object]:
    reference = _required_mapping(reference_value, label)
    path = Path(_required_string(reference.get("path"), f"{label}.path")).resolve()
    if exact_path is not None and path != exact_path.resolve():
        raise T085EvaluationIntegrityError(
            f"{label} is not bound to its accepted artifact path"
        )
    if require_t085_root:
        _require_t085_output_path(path)
    if not path.is_file():
        raise T085EvaluationIntegrityError(f"{label} artifact is unavailable")
    digest = sha256_file(path)
    if digest != reference.get("sha256"):
        raise T085EvaluationIntegrityError(f"{label} artifact hash changed")
    byte_count = reference.get("byte_count")
    if path.stat().st_size != byte_count:
        raise T085EvaluationIntegrityError(f"{label} artifact size changed")
    return {
        "path": str(path),
        "schema_id": _required_string(reference.get("schema_id"), f"{label}.schema_id"),
        "sha256": digest,
        "byte_count": byte_count,
    }


def _verify_t085_source_manifest_reference(
    reference_value: object,
    label: str,
    *,
    cohort: str,
) -> dict[str, object]:
    """Verify a source-manifest reference and its frozen JSON contents."""

    artifact = _verify_t085_artifact_reference(
        reference_value,
        label,
        require_t085_root=True,
    )
    path = Path(artifact["path"])
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise T085EvaluationIntegrityError(
            f"{label} source manifest is unreadable"
        ) from exc
    if not isinstance(document, Mapping):
        raise T085EvaluationIntegrityError(f"{label} source manifest is not an object")
    manifest = dict(document)
    manifest.update(
        {
            "source_manifest_path": artifact["path"],
            "source_manifest_sha256": artifact["sha256"],
            "source_manifest_byte_count": artifact["byte_count"],
        }
    )
    contract = validate_t085_source_generation_contract(manifest, cohort=cohort)
    return _verify_t085_source_manifest_artifact(manifest, contract=contract)


def validate_t085_evaluation_selection_evidence(
    cohorts: Mapping[
        str,
        Sequence[T085BattleStartRecord | Mapping[str, object]],
    ],
    selection_evidence: Mapping[str, Mapping[str, object]],
) -> dict[str, object]:
    """Validate frozen selection evidence against the records about to run."""

    required_cohorts = {"A", "B", "C", "B@400"}
    if set(cohorts) != required_cohorts:
        raise T085EvaluationIntegrityError(
            "evaluation cohorts must cover exactly A, B, C, and B@400"
        )
    if set(selection_evidence) != required_cohorts:
        raise T085EvaluationIntegrityError(
            "selection evidence must cover exactly A, B, C, and B@400"
        )
    normalized_cohorts = {
        cohort: _coerce_battle_starts(cohorts[cohort]) for cohort in required_cohorts
    }
    actual_ids = {
        cohort: [record.selection_identity for record in normalized_cohorts[cohort]]
        for cohort in required_cohorts
    }
    expected_counts = {"A": 93, "B": 192, "C": 96, "B@400": 48}
    source_counts = {"A": None, "B": 1024, "C": 128, "B@400": 1024}
    validated: dict[str, object] = {}
    for cohort in ("A", "B", "C", "B@400"):
        evidence = _required_mapping(
            selection_evidence.get(cohort), f"selection_evidence.{cohort}"
        )
        if evidence.get("schema_id") != T085_SELECTION_EVIDENCE_SCHEMA_ID:
            raise T085EvaluationIntegrityError(
                f"selection evidence {cohort} schema is not current"
            )
        actual_count = len(actual_ids[cohort])
        if cohort == "C":
            if actual_count < T085_COHORT_C_MIN_SELECTED_COUNT:
                raise T085EvaluationIntegrityError(
                    "Cohort C selection evidence cannot support the 96-record gate"
                )
        elif actual_count != expected_counts[cohort]:
            raise T085EvaluationIntegrityError(
                f"selection evidence {cohort} record count is not exact"
            )
        if evidence.get("selected_count") != actual_count:
            raise T085EvaluationIntegrityError(
                f"selection evidence {cohort} count does not match records"
            )
        if evidence.get("selected_identity_order") != actual_ids[cohort]:
            raise T085EvaluationIntegrityError(
                f"selection evidence {cohort} identity order does not match records"
            )
        if evidence.get("selected_records") != _selection_record_manifest(
            normalized_cohorts[cohort]
        ):
            raise T085EvaluationIntegrityError(
                f"selection evidence {cohort} selected records do not match"
            )
        if evidence.get("selected_identity_sha256") != _sha256_json(actual_ids[cohort]):
            raise T085EvaluationIntegrityError(
                f"selection evidence {cohort} identity digest does not match records"
            )
        if evidence.get("source_generation_valid") is not True:
            raise T085EvaluationIntegrityError(
                f"selection evidence {cohort} lacks source-generation validation"
            )
        if evidence.get("source_frozen") is not True:
            raise T085EvaluationIntegrityError(
                f"selection evidence {cohort} lacks source-freeze validation"
            )
        if evidence.get("restore_parity_passed") is not True:
            raise T085EvaluationIntegrityError(
                f"selection evidence {cohort} lacks restore/public-context parity"
            )
        if (
            source_counts[cohort] is not None
            and evidence.get("source_run_count") != source_counts[cohort]
        ):
            raise T085EvaluationIntegrityError(
                f"selection evidence {cohort} source pool count is invalid"
            )
        if cohort == "A":
            artifact = _verify_t085_artifact_reference(
                evidence.get("artifact"),
                "selection_evidence.A.artifact",
                exact_path=T085_T052_COHORT_PATH,
            )
            a_summary = validate_cohort_a(
                normalized_cohorts[cohort],
                artifact_path=artifact["path"],
                artifact_sha256=artifact["sha256"],
            )
            if a_summary.get("selected_records") != evidence.get("selected_records"):
                raise T085EvaluationIntegrityError(
                    "selection evidence A is not bound to the actual T052 records"
                )
        else:
            source_cohort = "B" if cohort == "B@400" else cohort
            artifact = _verify_t085_source_manifest_reference(
                evidence.get("source_manifest"),
                f"selection_evidence.{cohort}.source_manifest",
                cohort=source_cohort,
            )
            for key in T085_SOURCE_INVENTORY_KEYS:
                if evidence.get(key) != artifact.get(key):
                    raise T085EvaluationIntegrityError(
                        f"selection evidence {cohort} {key} does not match "
                        "the complete frozen source inventory"
                    )
            seeds = evidence["source_run_seed_inventory"]
            run_ids = evidence["source_run_identity_inventory"]
            complete_ids = evidence["complete_source_identity_inventory"]
            by_seed = dict(zip(seeds, zip(run_ids, complete_ids), strict=True))
            for record in normalized_cohorts[cohort]:
                source_binding = by_seed.get(record.source_run_seed)
                if source_binding != (
                    record.source_run_identity,
                    record.complete_source_identity,
                ):
                    raise T085EvaluationIntegrityError(
                        f"selection evidence {cohort} record is not bound to "
                        "the frozen source inventory"
                    )
        if cohort == "B" and evidence.get("zero_overlap") is not True:
            raise T085EvaluationIntegrityError(
                "selection evidence B lacks the zero-overlap audit"
            )
        if cohort == "B@400":
            parent_ids = set(actual_ids["B"])
            if not set(actual_ids[cohort]).issubset(parent_ids):
                raise T085EvaluationIntegrityError(
                    "Search@400 selection is not a subset of frozen Cohort B"
                )
            if evidence.get("parent_selected_identity_sha256") != _sha256_json(
                actual_ids["B"]
            ):
                raise T085EvaluationIntegrityError(
                    "Search@400 evidence is not bound to Cohort B selection"
                )
        validated[cohort] = {
            "selected_count": actual_count,
            "selected_identity_order": actual_ids[cohort],
            "selected_records": _selection_record_manifest(normalized_cohorts[cohort]),
            "selected_identity_sha256": _sha256_json(actual_ids[cohort]),
            "artifact": artifact,
        }
    return {
        "schema_id": T085_SELECTION_EVIDENCE_SCHEMA_ID,
        "validated": True,
        "cohort_counts": {
            cohort: len(actual_ids[cohort]) for cohort in ("A", "B", "C", "B@400")
        },
        "cohorts": validated,
    }


def run_t085_paired_evaluation(
    cohorts: Mapping[str, Sequence[T085BattleStartRecord]],
    *,
    evaluate_record: Callable[
        [T085BattleStartRecord, str, int], T085OutcomeRecord | Mapping[str, object]
    ],
    selection_evidence: Mapping[str, Mapping[str, object]] | None = None,
) -> dict[str, object]:
    """Execute the complete T085 arm matrix through an injected evaluator.

    The evaluator owns native restore and Search execution.  Its inputs are
    explicit frozen records, an arm label, and a nominal budget; it must return
    the retained telemetry fields represented by :class:`T085OutcomeRecord`.
    This keeps the workflow executable with the pinned simulator while keeping
    simulator mechanics outside the STSRL Python boundary.
    """

    required_cohorts = {"A", "B", "C", "B@400"}
    if set(cohorts) != required_cohorts:
        raise T085EvaluationIntegrityError(
            "T085 evaluation requires exactly cohorts A, B, C, and B@400"
        )
    if selection_evidence is None:
        raise T085EvaluationIntegrityError(
            "T085 evaluation requires validated source/selection/parity evidence"
        )
    validate_t085_evaluation_selection_evidence(cohorts, selection_evidence)
    rows: list[T085OutcomeRecord] = []
    plans = {
        "A": (T085_PRIMARY_ARMS, T085_SEARCH_BUDGET),
        "B": (T085_PRIMARY_ARMS + T085_SECONDARY_ARMS, T085_SEARCH_BUDGET),
        "C": (T085_PRIMARY_ARMS, T085_SEARCH_BUDGET),
        "B@400": (T085_SEARCH_400_ARMS, T085_SEARCH_400_BUDGET),
    }
    for cohort, records in cohorts.items():
        if not records:
            raise T085EvaluationIntegrityError(f"T085 cohort {cohort} is empty")
        for record in records:
            for arm in plans[cohort][0]:
                returned = evaluate_record(record, arm, plans[cohort][1])
                row = (
                    returned
                    if isinstance(returned, T085OutcomeRecord)
                    else T085OutcomeRecord.from_mapping(returned)
                )
                if (
                    row.cohort != cohort
                    or row.record_identity != record.selection_identity
                    or row.arm != arm
                    or row.source_run_identity != record.source_run_identity
                    or row.search_budget != plans[cohort][1]
                ):
                    raise T085EvaluationIntegrityError(
                        "evaluator returned a row not bound to its requested "
                        "cohort, record, arm, source, and budget"
                    )
                rows.append(row)
    return build_t085_paired_evaluation_report(
        rows,
        cohort_b_record_count=len(cohorts["B"]),
        cohort_c_record_count=len(cohorts["C"]),
        selection_cohorts=cohorts,
        selection_evidence=selection_evidence,
    )


def _required_comparison(
    report: Mapping[str, object],
    key: str,
) -> Mapping[str, object]:
    value = report.get(key)
    if not isinstance(value, Mapping):
        raise T085EvaluationIntegrityError(f"classification report missing {key}")
    return value


def _all_nonnegative_utility(report: Mapping[str, object]) -> bool:
    return (
        _required_finite(report.get("mean_utility_delta"), "mean_utility_delta") >= 0.0
    )


def _at_most_one_win_loss(
    report: Mapping[str, object],
) -> bool:
    return _required_int(
        report.get("comparator_wins"), "comparator_wins"
    ) + 1 >= _required_int(report.get("reference_wins"), "reference_wins")


def classify_t085_terminal(
    evaluation_report: Mapping[str, object],
    *,
    gates: Mapping[str, bool],
    cohort_b_supported: bool,
    cohort_c_supported: bool,
    gate_evidence: Mapping[str, object] | None = None,
) -> str:
    """Apply the published T085 terminal classification exactly once."""

    required_gates = (
        "artifact",
        "policy_invariance",
        "checkpoint",
        "source_cohort",
        "restore_parity",
        "execution",
        "retention",
    )
    if any(gates.get(name) is not True for name in required_gates):
        return "INCOMPLETE"
    try:
        _validate_gate_evidence(gate_evidence)
        counts = _verify_paired_report_reproducible(evaluation_report)
    except T085EvaluationIntegrityError:
        return "INCOMPLETE"
    try:
        selection = _required_mapping(
            gate_evidence.get("selection") if gate_evidence else None,
            "gate_evidence.selection",
        )
        expected_selection_counts = {
            "cohort_a_selected_count": counts["A"],
            "cohort_b_selected_count": counts["B"],
            "cohort_c_selected_count": counts["C"],
            "search_400_selected_count": counts["B@400"],
        }
        for key, actual in expected_selection_counts.items():
            if selection.get(key) != actual:
                return "INCOMPLETE"
        actual_support = (
            counts["A"] == 93
            and counts["B"] == T085_COHORT_B_SELECTED_COUNT
            and counts["C"] >= T085_COHORT_C_MIN_SELECTED_COUNT
            and counts["B@400"] == T085_SEARCH_400_SELECTED_COUNT
        )
        expected_support_status = "supported" if actual_support else "insufficient"
        if selection.get("support_status") != expected_support_status:
            return "INCOMPLETE"
        if cohort_b_supported is not (
            counts["B"] == T085_COHORT_B_SELECTED_COUNT
        ) or cohort_c_supported is not (
            counts["C"] >= T085_COHORT_C_MIN_SELECTED_COUNT
        ):
            return "INCOMPLETE"
        if not actual_support:
            return "VALUE_REPAIR_EVAL_SUPPORT_INSUFFICIENT"
        b = _required_mapping(evaluation_report.get("cohort_b"), "cohort_b")
        primary = _required_mapping(evaluation_report.get("primary"), "primary")
        search_400 = _required_mapping(
            evaluation_report.get("search_400"), "search_400"
        )
        delta_old = _required_mapping(b.get("delta_old"), "delta_old")
        delta_base = _required_mapping(b.get("delta_base"), "delta_base")
        b_primary = _required_mapping(primary.get("B"), "primary.B")
        a_primary = _required_mapping(primary.get("A"), "primary.A")
        c_primary = _required_mapping(primary.get("C"), "primary.C")
        b_comparisons = _required_mapping(
            b_primary.get("comparisons"), "primary.B.comparisons"
        )
        a_comparisons = _required_mapping(
            a_primary.get("comparisons"), "primary.A.comparisons"
        )
        c_comparisons = _required_mapping(
            c_primary.get("comparisons"), "primary.C.comparisons"
        )
        guard_85001 = _required_comparison(search_400, "corrected_85001_vs_baseline")
        guard_85002 = _required_comparison(search_400, "corrected_85002_vs_baseline")
        established = (
            _required_finite(delta_old.get("percentile_2_5"), "delta_old lower") > 0.0
            and _required_finite(delta_base.get("percentile_2_5"), "delta_base lower")
            > 0.0
            and _required_comparison(b_comparisons, "corrected_85001_vs_baseline").get(
                "comparator_wins", -1
            )
            >= _required_comparison(b_comparisons, "corrected_85001_vs_baseline").get(
                "reference_wins", 0
            )
            and _required_comparison(b_comparisons, "corrected_85002_vs_baseline").get(
                "comparator_wins", -1
            )
            >= _required_comparison(b_comparisons, "corrected_85002_vs_baseline").get(
                "reference_wins", 0
            )
            and _required_comparison(b_comparisons, "corrected_85001_vs_old").get(
                "comparator_wins", -1
            )
            >= _required_comparison(b_comparisons, "corrected_85001_vs_old").get(
                "reference_wins", 0
            )
            and _required_comparison(b_comparisons, "corrected_85002_vs_old").get(
                "comparator_wins", -1
            )
            >= _required_comparison(b_comparisons, "corrected_85002_vs_old").get(
                "reference_wins", 0
            )
            and _at_most_one_win_loss(
                _required_comparison(a_comparisons, "corrected_85001_vs_baseline")
            )
            and _at_most_one_win_loss(
                _required_comparison(a_comparisons, "corrected_85002_vs_baseline")
            )
            and _all_nonnegative_utility(
                _required_comparison(a_comparisons, "corrected_85001_vs_baseline")
            )
            and _all_nonnegative_utility(
                _required_comparison(a_comparisons, "corrected_85002_vs_baseline")
            )
            and _at_most_one_win_loss(
                _required_comparison(c_comparisons, "corrected_85001_vs_baseline")
            )
            and _at_most_one_win_loss(
                _required_comparison(c_comparisons, "corrected_85002_vs_baseline")
            )
            and _all_nonnegative_utility(
                _required_comparison(c_comparisons, "corrected_85001_vs_baseline")
            )
            and _all_nonnegative_utility(
                _required_comparison(c_comparisons, "corrected_85002_vs_baseline")
            )
            and _at_most_one_win_loss(guard_85001)
            and _at_most_one_win_loss(guard_85002)
            and _all_nonnegative_utility(guard_85001)
            and _all_nonnegative_utility(guard_85002)
        )
        if established:
            return "CORRECTED_VALUE_SEARCH_IMPROVEMENT_ESTABLISHED"
        harmful = (
            _required_finite(delta_base.get("percentile_97_5"), "delta_base upper")
            < 0.0
            and _required_comparison(b_comparisons, "corrected_85001_vs_baseline").get(
                "comparator_wins", 0
            )
            < _required_comparison(b_comparisons, "corrected_85001_vs_baseline").get(
                "reference_wins", 0
            )
            and _required_comparison(b_comparisons, "corrected_85002_vs_baseline").get(
                "comparator_wins", 0
            )
            < _required_comparison(b_comparisons, "corrected_85002_vs_baseline").get(
                "reference_wins", 0
            )
        )
        if harmful:
            return "CORRECTED_VALUE_SEARCH_HARM_CONFIRMED"
        return "CORRECTED_VALUE_SEARCH_IMPROVEMENT_NOT_ESTABLISHED"
    except (KeyError, TypeError, ValueError, T085EvaluationIntegrityError):
        return "INCOMPLETE"


def _validate_gate_evidence(value: Mapping[str, object] | None) -> None:
    if not isinstance(value, Mapping):
        raise T085EvaluationIntegrityError(
            "terminal classification requires concrete gate evidence"
        )
    required = (
        "artifact",
        "policy_invariance",
        "checkpoint",
        "source_cohort",
        "restore_parity",
        "execution",
        "retention",
    )
    for name in required:
        evidence = _required_mapping(value.get(name), f"gate_evidence.{name}")
        if evidence.get("passed") is not True:
            raise T085EvaluationIntegrityError(
                f"gate evidence {name} is not marked passed"
            )
        _required_string(
            evidence.get("evidence_id"), f"gate_evidence.{name}.evidence_id"
        )
    selection = _required_mapping(value.get("selection"), "gate_evidence.selection")
    _required_string(
        selection.get("evidence_id"), "gate_evidence.selection.evidence_id"
    )
    if selection.get("passed") is not True:
        raise T085EvaluationIntegrityError(
            "gate evidence selection is not marked passed"
        )
    for key in (
        "cohort_a_selected_count",
        "cohort_b_selected_count",
        "cohort_c_selected_count",
        "search_400_selected_count",
    ):
        count = _required_int(selection.get(key), f"gate_evidence.selection.{key}")
        if count < 0:
            raise T085EvaluationIntegrityError(
                f"gate evidence selection {key} must be non-negative"
            )
    if selection.get("support_status") not in {"supported", "insufficient"}:
        raise T085EvaluationIntegrityError(
            "gate evidence selection support_status is invalid"
        )
    if selection.get("source_generation_valid") is not True:
        raise T085EvaluationIntegrityError(
            "gate evidence selection lacks source-generation validation"
        )
    if selection.get("source_frozen") is not True:
        raise T085EvaluationIntegrityError(
            "gate evidence selection lacks source-freeze validation"
        )
    if selection.get("restore_parity_passed") is not True:
        raise T085EvaluationIntegrityError(
            "gate evidence selection lacks restore/public-context parity"
        )
    if selection.get("zero_overlap") is not True:
        raise T085EvaluationIntegrityError(
            "gate evidence selection lacks Cohort-B zero-overlap validation"
        )
    _verify_t085_artifact_reference(
        selection.get("cohort_a_artifact"),
        "gate_evidence.selection.cohort_a_artifact",
        exact_path=T085_T052_COHORT_PATH,
    )
    for key in ("cohort_b_source_manifest", "cohort_c_source_manifest"):
        _verify_t085_source_manifest_reference(
            selection.get(key),
            f"gate_evidence.selection.{key}",
            cohort="B" if key == "cohort_b_source_manifest" else "C",
        )
    retention = _required_mapping(
        value.get("retention_manifest"), "gate_evidence.retention_manifest"
    )
    validate_t085_retention_manifest(retention)
    outputs = _required_mapping(retention.get("outputs"), "retention.outputs")
    missing_roles = sorted(set(T085_REQUIRED_RETENTION_OUTPUT_ROLES) - set(outputs))
    if missing_roles:
        raise T085EvaluationIntegrityError(
            "gate evidence retention manifest is missing required output roles: "
            + ", ".join(missing_roles)
        )


def _verify_paired_report_reproducible(
    report: Mapping[str, object],
) -> dict[str, int]:
    """Reject a terminal claim assembled from caller-supplied summary flags."""

    if report.get("schema_id") != "t085-paired-evaluation-report-v1":
        raise T085EvaluationIntegrityError("T085 paired report schema is not current")
    raw_outcomes = report.get("outcomes")
    if not isinstance(raw_outcomes, list) or not raw_outcomes:
        raise T085EvaluationIntegrityError(
            "T085 terminal classification requires retained outcome rows"
        )
    outcomes = tuple(
        row
        if isinstance(row, T085OutcomeRecord)
        else T085OutcomeRecord.from_mapping(row)
        for row in raw_outcomes
        if isinstance(row, (Mapping, T085OutcomeRecord))
    )
    if len(outcomes) != len(raw_outcomes):
        raise T085EvaluationIntegrityError("T085 outcome rows are malformed")
    selection_binding = _required_mapping(
        report.get("selection_binding"), "selection_binding"
    )
    _validate_outcomes_against_selection_binding(outcomes, selection_binding)
    b_count = len({row.record_identity for row in outcomes if row.cohort == "B"})
    c_count = len({row.record_identity for row in outcomes if row.cohort == "C"})
    rebuilt = build_t085_paired_evaluation_report(
        outcomes,
        cohort_b_record_count=b_count,
        cohort_c_record_count=c_count,
    )
    for key in (
        "primary",
        "secondary",
        "search_400",
        "cohort_b",
        "support",
        "outcome_record_count",
    ):
        if report.get(key) != rebuilt.get(key):
            raise T085EvaluationIntegrityError(
                f"T085 paired report {key} does not match retained outcome rows"
            )
    return {
        "A": len({row.record_identity for row in outcomes if row.cohort == "A"}),
        "B": b_count,
        "C": c_count,
        "B@400": len(
            {row.record_identity for row in outcomes if row.cohort == "B@400"}
        ),
    }


def build_t085_terminal_report(
    classification: str | None = None,
    *,
    gates: Mapping[str, bool],
    evaluation_report: Mapping[str, object] | None = None,
    cohort_b_supported: bool | None = None,
    cohort_c_supported: bool | None = None,
    gate_evidence: Mapping[str, object] | None = None,
) -> dict[str, object]:
    if (
        evaluation_report is None
        or cohort_b_supported is None
        or cohort_c_supported is None
    ):
        computed_classification = "INCOMPLETE"
    else:
        computed_classification = classify_t085_terminal(
            evaluation_report,
            gates=gates,
            cohort_b_supported=cohort_b_supported,
            cohort_c_supported=cohort_c_supported,
            gate_evidence=gate_evidence,
        )
    if classification is not None and classification != computed_classification:
        raise T085EvaluationIntegrityError(
            "caller T085 classification does not match the validated evaluation report"
        )
    classification = computed_classification
    return {
        "schema_id": "t085-terminal-classification-report-v1",
        "task_id": "T085",
        "classification": classification,
        "allowed_classifications": list(T085_TERMINAL_CLASSIFICATIONS),
        "gates": dict(gates),
        "gate_evidence": dict(gate_evidence or {}),
        "support": {
            "cohort_b_supported": cohort_b_supported,
            "cohort_c_supported": cohort_c_supported,
        },
        "evaluation_report_schema_id": (
            evaluation_report.get("schema_id")
            if isinstance(evaluation_report, Mapping)
            else None
        ),
    }


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def artifact_reference(path: str | Path, *, schema_id: str) -> dict[str, object]:
    resolved = Path(path).resolve(strict=True)
    return {
        "path": str(resolved),
        "schema_id": schema_id,
        "sha256": sha256_file(resolved),
        "byte_count": resolved.stat().st_size,
    }


def write_t085_json_artifact(
    path: str | Path,
    payload: Mapping[str, object],
    *,
    schema_id: str,
) -> dict[str, object]:
    """Write a deterministic current-schema artifact and return its reference."""

    target = Path(path).resolve()
    _require_t085_output_path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    body = dict(payload)
    body.setdefault("schema_id", schema_id)
    target.write_text(
        json.dumps(body, sort_keys=True, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return artifact_reference(target, schema_id=schema_id)


def validate_t085_retention_manifest(
    manifest: Mapping[str, object],
    *,
    verify_files: bool = True,
) -> dict[str, object]:
    """Revalidate a retention manifest before it can support a claim."""

    if manifest.get("schema_id") != "t085-retention-manifest-v1":
        raise T085EvaluationIntegrityError("unsupported T085 retention schema")
    if manifest.get("task_id") != "T085":
        raise T085EvaluationIntegrityError(
            "retention manifest task identity is invalid"
        )
    if (
        Path(_required_string(manifest.get("artifact_root"), "artifact_root")).resolve()
        != T085_ARTIFACT_ROOT.resolve()
    ):
        raise T085EvaluationIntegrityError("T085 retention root is not stable")
    outputs = _required_mapping(manifest.get("outputs"), "outputs")
    verified: dict[str, object] = {"output_count": len(outputs), "verified": True}
    for name, raw_reference in outputs.items():
        reference = _required_mapping(raw_reference, f"outputs.{name}")
        path = Path(
            _required_string(reference.get("path"), f"outputs.{name}.path")
        ).resolve()
        _require_t085_output_path(path)
        if verify_files:
            if not path.is_file():
                raise T085EvaluationIntegrityError(
                    f"retained T085 output {name} is unavailable"
                )
            if sha256_file(path) != reference.get("sha256"):
                raise T085EvaluationIntegrityError(
                    f"retained T085 output {name} hash changed"
                )
            if path.stat().st_size != reference.get("byte_count"):
                raise T085EvaluationIntegrityError(
                    f"retained T085 output {name} size changed"
                )
    return verified


def _require_t085_output_path(path: Path) -> None:
    try:
        path.relative_to(T085_ARTIFACT_ROOT.resolve())
    except ValueError as exc:
        raise T085EvaluationIntegrityError(
            "T085 retention outputs must be under the stable ignored T085 root"
        ) from exc


def build_t085_retention_manifest(
    *,
    inputs: Mapping[str, Mapping[str, object]],
    outputs: Mapping[str, Mapping[str, object]],
    stages: Sequence[Mapping[str, object]],
    code_identity: Mapping[str, object],
    native_identity: Mapping[str, object],
    terminal_classification: str,
    regeneration_commands: Sequence[str],
    retention_reason: str,
    deletion_conditions: Sequence[str],
) -> dict[str, object]:
    """Build the stable-root manifest required for later reproducibility."""

    if terminal_classification not in T085_TERMINAL_CLASSIFICATIONS:
        raise T085EvaluationIntegrityError("unknown terminal classification")
    for label, refs in (("inputs", inputs), ("outputs", outputs)):
        for name, reference in refs.items():
            for key in ("path", "schema_id", "sha256", "byte_count"):
                if key not in reference:
                    raise T085EvaluationIntegrityError(
                        f"{label}.{name} is missing artifact field {key}"
                    )
            if label == "outputs":
                _require_t085_output_path(
                    Path(
                        _required_string(reference["path"], f"outputs.{name}.path")
                    ).resolve()
                )
    worker_counts = []
    for stage in stages:
        worker_counts.append(stage.get("effective_worker_count"))
        if (
            stage.get("stage")
            in {
                "source_generation",
                "restore_parity",
                "teacher_collection",
                "evaluation",
                "comparison",
            }
            and stage.get("effective_worker_count") != 16
        ):
            raise T085EvaluationIntegrityError(
                f"{stage.get('stage')} must record the default 16-worker gate"
            )
    return {
        "schema_id": "t085-retention-manifest-v1",
        "task_id": "T085",
        "artifact_root": str(T085_ARTIFACT_ROOT),
        "inputs": {name: dict(value) for name, value in inputs.items()},
        "outputs": {name: dict(value) for name, value in outputs.items()},
        "stages": [dict(stage) for stage in stages],
        "effective_worker_counts": worker_counts,
        "code_identity": dict(code_identity),
        "native_identity": dict(native_identity),
        "terminal_classification": terminal_classification,
        "regeneration_commands": list(regeneration_commands),
        "retention": {
            "reason": retention_reason,
            "deletion_conditions": list(deletion_conditions),
            "raw_files_outside_git": True,
        },
    }


def _required_mapping(value: object, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise T085EvaluationIntegrityError(f"{label} must be a mapping")
    return value


__all__ = [
    "T085_ARTIFACT_ROOT",
    "T085_BOOTSTRAP_COUNT",
    "T085_BOOTSTRAP_SEED",
    "T085_COHORT_B_RUN_COUNT",
    "T085_COHORT_B_SELECTED_COUNT",
    "T085_COHORT_C_MIN_SELECTED_COUNT",
    "T085_COHORT_C_RUN_COUNT",
    "T085_REQUIRED_RETENTION_OUTPUT_ROLES",
    "T085_SEARCH_400_BUDGET",
    "T085_SEARCH_BUDGET",
    "T085_SELECTION_EVIDENCE_SCHEMA_ID",
    "T085_T052_COHORT_BYTE_COUNT",
    "T085_T052_COHORT_PATH",
    "T085_T052_COHORT_SCHEMA_ID",
    "T085_TERMINAL_CLASSIFICATIONS",
    "T085BattleStartRecord",
    "T085EvaluationIntegrityError",
    "T085OutcomeRecord",
    "T085SourceRunRecord",
    "aggregate_paired_outcomes",
    "artifact_reference",
    "audit_cohort_b_source_overlap",
    "bootstrap_mean_percentile",
    "build_t085_cohort_selection",
    "build_t085_evaluation_selection_evidence",
    "build_t085_paired_evaluation_report",
    "build_t085_retention_manifest",
    "build_t085_terminal_report",
    "classify_t085_terminal",
    "load_t085_t052_cohort_records",
    "run_t085_paired_evaluation",
    "select_cohort_b",
    "select_cohort_c",
    "select_search_400_subset",
    "sha256_file",
    "validate_cohort_a",
    "validate_t085_evaluation_selection_evidence",
    "validate_t085_restore_parity",
    "validate_t085_retention_manifest",
    "validate_t085_source_generation_contract",
    "write_t085_json_artifact",
]
