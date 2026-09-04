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
        )

    @property
    def selection_identity(self) -> str:
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
        )


def _coerce_source_runs(
    records: Iterable[T085SourceRunRecord | Mapping[str, object]],
) -> tuple[T085SourceRunRecord, ...]:
    return tuple(
        record
        if isinstance(record, T085SourceRunRecord)
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
    artifact_sha256: str,
) -> dict[str, object]:
    """Validate the unchanged 93-record T052 stress boundary."""

    if artifact_sha256 != T085_T052_COHORT_SHA256:
        raise T085EvaluationIntegrityError("Cohort A is not the accepted T052 artifact")
    normalized = _coerce_battle_starts(records)
    if len(normalized) != 93:
        raise T085EvaluationIntegrityError("Cohort A requires exactly 93 records")
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
        "artifact_sha256": artifact_sha256,
        "record_count": len(normalized),
        "room_type_counts": dict(Counter(record.room_type for record in normalized)),
    }


def audit_cohort_b_source_overlap(
    cohort_b_records: Sequence[T085BattleStartRecord | T085SourceRunRecord],
    *,
    t084_complete_source_identities: Iterable[str],
    t052_complete_source_identities: Iterable[str],
) -> dict[str, object]:
    """Prove fresh Cohort-B complete sources are disjoint from prior roots."""

    b_identities = [record.complete_source_identity for record in cohort_b_records]
    if len(set(b_identities)) != len(b_identities):
        raise T085EvaluationIntegrityError(
            "Cohort B complete_source_identity values are not unique"
        )
    t084 = set(t084_complete_source_identities)
    t052 = set(t052_complete_source_identities)
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
        "ascension": 20,
        "max_outer_steps": 500,
        "action_space": "initial_no_potions",
        "non_combat_controller": "expert_non_combat_v1",
        "non_combat_policy_seed": 42042,
        "source_outcome_independent": True,
        "repaired_checkpoint_used": False,
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
    return {
        "cohort": cohort,
        "validated": True,
        "source_run_count": expected["source_run_count"],
        "source_run_seed_range": {
            "start": expected["source_run_seeds"][0],
            "end": expected["source_run_seeds"][-1],
        },
        "frozen_fields": dict(required_common) | dict(expected),
    }


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
) -> dict[str, object]:
    """Build primary, secondary, guard, and fixed-bootstrap reports."""

    normalized = _validated_outcomes(records)
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
    if len({record.record_identity for record in b_rows}) != cohort_b_record_count:
        raise T085EvaluationIntegrityError(
            "Cohort B outcome record count is incomplete"
        )
    if len({record.record_identity for record in c_rows}) != cohort_c_record_count:
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
    guard_rows = [record for record in normalized if record.cohort == "B@400"]
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
    return {
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
        "outcome_record_count": len(normalized),
    }


def run_t085_paired_evaluation(
    cohorts: Mapping[str, Sequence[T085BattleStartRecord]],
    *,
    evaluate_record: Callable[
        [T085BattleStartRecord, str, int], T085OutcomeRecord | Mapping[str, object]
    ],
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
                ):
                    raise T085EvaluationIntegrityError(
                        "evaluator returned a row not bound to its requested "
                        "cohort, record, and arm"
                    )
                rows.append(row)
    return build_t085_paired_evaluation_report(
        rows,
        cohort_b_record_count=len(cohorts["B"]),
        cohort_c_record_count=len(cohorts["C"]),
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
    except T085EvaluationIntegrityError:
        return "INCOMPLETE"
    if not cohort_b_supported or not cohort_c_supported:
        return "VALUE_REPAIR_EVAL_SUPPORT_INSUFFICIENT"
    try:
        _verify_paired_report_reproducible(evaluation_report)
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
) -> None:
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
        "outcome_record_count",
    ):
        if report.get(key) != rebuilt.get(key):
            raise T085EvaluationIntegrityError(
                f"T085 paired report {key} does not match retained outcome rows"
            )


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
    "T085_TERMINAL_CLASSIFICATIONS",
    "T085BattleStartRecord",
    "T085EvaluationIntegrityError",
    "T085OutcomeRecord",
    "T085SourceRunRecord",
    "aggregate_paired_outcomes",
    "artifact_reference",
    "audit_cohort_b_source_overlap",
    "bootstrap_mean_percentile",
    "build_t085_paired_evaluation_report",
    "build_t085_retention_manifest",
    "build_t085_terminal_report",
    "classify_t085_terminal",
    "run_t085_paired_evaluation",
    "select_cohort_b",
    "select_cohort_c",
    "select_search_400_subset",
    "sha256_file",
    "validate_cohort_a",
    "validate_t085_restore_parity",
    "validate_t085_retention_manifest",
    "validate_t085_source_generation_contract",
    "write_t085_json_artifact",
]
