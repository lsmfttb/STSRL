"""T061 matched budget and reachability bottleneck reports.

This module is deliberately an offline reducer.  Simulator collection remains
owned by the existing lightspeed workflows; this reducer validates their
immutable arm manifests and computes the matched statistics without loading
large source pools.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
import hashlib
import json
import random
from typing import Any


T061_SCHEMA_ID = "t061-a20-reachability-bottleneck-decomposition-v1"
T061_BUDGET_SCHEMA_ID = "t061-restored-battle-budget-curve-v1"
T061_FACTORIAL_SCHEMA_ID = "t061-complete-run-factorial-report-v1"
T061_EVIDENCE_BOUNDARY = (
    "T061 simulator-only diagnostic; all battle arms are "
    "full_simulator_state_oracle_like and this is not normal-information, "
    "live-game, broad-training, or controller-promotion evidence"
)
_REQUIRED_BUDGETS = (20, 100, 300)
_REQUIRED_DRIVERS = ("stochastic_non_combat_v1", "expert_non_combat_v1")
_REQUIRED_REACHABILITY_FIELDS = (
    "act1_boss_start",
    "act2_entry",
    "act3_entry",
    "act4_entry",
    "heart_start",
    "heart_victory",
    "shield_spear_start",
    "shield_spear_outcome",
)


def load_json_object(path: str) -> dict[str, Any]:
    with open(path, encoding="utf-8") as stream:
        value = json.load(stream)
    if not isinstance(value, dict):
        raise ValueError(f"{path}: JSON root must be an object")
    return {str(key): item for key, item in value.items()}


def build_t061_budget_curve_report(
    arms: Sequence[tuple[str, Mapping[str, Any]]],
) -> dict[str, Any]:
    """Validate three matched restored-battle arms and summarize outcomes."""

    if {int(_required_label(label, "budget")) for label, _ in arms} != set(
        _REQUIRED_BUDGETS
    ):
        raise ValueError("T061 budget curve requires exactly budgets 20, 100, and 300")
    by_budget = {int(label): _mapping(payload) for label, payload in arms}
    ids_by_budget = {
        budget: _unique_ids(_records(payload, "records"), f"budget {budget}")
        for budget, payload in by_budget.items()
    }
    reference_ids = ids_by_budget[20]
    if any(ids != reference_ids for ids in ids_by_budget.values()):
        raise ValueError("T061 budget arms must contain the same cohort identities")
    provenance = _common_provenance(by_budget.values())
    reports: dict[str, Any] = {}
    for budget in _REQUIRED_BUDGETS:
        rows = _records(by_budget[budget], "records")
        reports[str(budget)] = {
            "record_count": len(rows),
            "win_count": sum(_truth(row.get("won")) for row in rows),
            "loss_count": sum(not _truth(row.get("won")) for row in rows),
            "mean_terminal_absolute_hp": _mean(
                [_number(row.get("terminal_absolute_hp")) for row in rows]
            ),
            "simulator_steps": sum(
                _number(row.get("simulator_steps")) or 0 for row in rows
            ),
            "wall_clock_seconds": sum(
                _number(row.get("wall_clock_seconds")) or 0.0 for row in rows
            ),
            "truncation_count": sum(_status(row) == "truncated" for row in rows),
            "error_count": sum(
                _status(row) in {"error", "unsupported"} for row in rows
            ),
            "potion_outcome_counts": _outcome_counts(rows, "potion_outcome"),
            "structured_terminal_resource_outcome_counts": _outcome_counts(
                rows, "structured_terminal_resource_outcome"
            ),
            "strata": _strata(rows),
        }
    pairwise = {}
    for left, right in ((20, 100), (100, 300), (20, 300)):
        left_rows = {
            str(row["record_id"]): row for row in _records(by_budget[left], "records")
        }
        right_rows = {
            str(row["record_id"]): row for row in _records(by_budget[right], "records")
        }
        pairwise[f"{right}_vs_{left}"] = {
            "win_delta": sum(
                _truth(right_rows[key].get("won")) - _truth(left_rows[key].get("won"))
                for key in reference_ids
            ),
            "win_effect": {
                "mean": _mean(
                    [
                        _truth(right_rows[key].get("won"))
                        - _truth(left_rows[key].get("won"))
                        for key in reference_ids
                    ]
                ),
                "bootstrap_95ci": _bootstrap_ci(
                    [
                        _truth(right_rows[key].get("won"))
                        - _truth(left_rows[key].get("won"))
                        for key in reference_ids
                    ],
                    2000,
                    6101 + right,
                ),
            },
            "terminal_hp_delta_mean": _paired_mean(
                left_rows, right_rows, "terminal_absolute_hp", reference_ids
            ),
            "first_action_disagreement_count": sum(
                _action_key(left_rows[key]) != _action_key(right_rows[key])
                for key in reference_ids
            ),
        }
    return {
        "schema_id": T061_BUDGET_SCHEMA_ID,
        "format_version": 1,
        "task_id": "T061",
        "evidence_boundary": T061_EVIDENCE_BOUNDARY,
        "cohort": {
            "record_count": len(reference_ids),
            "record_ids_sha256": _ids_hash(reference_ids),
        },
        "arms": reports,
        "pairwise": pairwise,
        "provenance": provenance,
        "command_passed": all(
            reports[str(budget)]["truncation_count"] == 0
            and reports[str(budget)]["error_count"] == 0
            for budget in _REQUIRED_BUDGETS
        ),
    }


def build_t061_factorial_report(
    arms: Sequence[tuple[str, str, Mapping[str, Any]]],
    *,
    expected_run_count: int = 256,
    bootstrap_resamples: int = 2000,
    bootstrap_seed: int = 6101,
) -> dict[str, Any]:
    """Validate six matched seed arms and compute paired factorial effects."""

    if expected_run_count < 1 or bootstrap_resamples < 100:
        raise ValueError(
            "T061 expected run count must be positive and bootstrap >= 100"
        )
    expected = {
        (driver, budget) for driver in _REQUIRED_DRIVERS for budget in _REQUIRED_BUDGETS
    }
    keys = {(driver, int(budget)) for driver, budget, _ in arms}
    if keys != expected:
        raise ValueError(
            "T061 factorial requires both drivers at budgets 20, 100, and 300"
        )
    by_key = {
        (driver, int(budget)): _mapping(payload) for driver, budget, payload in arms
    }
    seed_lists = {
        key: _unique_seed_rows(payload, key) for key, payload in by_key.items()
    }
    reference_seeds = seed_lists[(_REQUIRED_DRIVERS[0], 20)]
    if len(reference_seeds) != expected_run_count:
        raise ValueError(f"T061 factorial requires {expected_run_count} runs per arm")
    if any(seeds != reference_seeds for seeds in seed_lists.values()):
        raise ValueError("T061 factorial arms must contain the same seeds")
    provenance = _common_provenance(by_key.values())
    arm_summary = {}
    for key, payload in by_key.items():
        rows = _records(payload, "runs")
        arm_summary[f"{key[0]}@{key[1]}"] = _run_summary(rows)
    effects = _factorial_effects(
        by_key, reference_seeds, bootstrap_resamples, bootstrap_seed
    )
    return {
        "schema_id": T061_FACTORIAL_SCHEMA_ID,
        "format_version": 1,
        "task_id": "T061",
        "evidence_boundary": T061_EVIDENCE_BOUNDARY,
        "expected_run_count_per_arm": expected_run_count,
        "total_run_count": expected_run_count * 6,
        "seed_sha256": _ids_hash(reference_seeds),
        "arms": arm_summary,
        "effects": effects,
        "provenance": provenance,
        "command_passed": all(
            _run_summary(_records(payload, "runs"))["truncation_count"] == 0
            and _run_summary(_records(payload, "runs"))["error_count"] == 0
            for payload in by_key.values()
        ),
    }


def build_t061_bottleneck_report(
    budget_report: Mapping[str, Any], factorial_report: Mapping[str, Any]
) -> dict[str, Any]:
    """Apply the published decision table and return exactly one next task."""

    battle_signal = _meaningful_budget_signal(budget_report)
    driver_signal = _meaningful_driver_signal(factorial_report)
    if battle_signal:
        recommendation = "T062"
        rationale = "higher battle budget has a positive paired effect with uncertainty excluding zero"
    elif driver_signal:
        recommendation = "T065"
        rationale = "non-combat driver has the dominant positive matched effect"
    elif not _any_later_act(factorial_report):
        recommendation = "T064"
        rationale = "neither intervention created useful later-act reachability"
    else:
        recommendation = "T061-followup-provenance-diagnostic"
        rationale = "intervention attribution is inconclusive or incomplete"
    return {
        "schema_id": T061_SCHEMA_ID,
        "format_version": 1,
        "task_id": "T061",
        "evidence_boundary": T061_EVIDENCE_BOUNDARY,
        "restored_battle_budget_curve": dict(budget_report),
        "complete_run_factorial": dict(factorial_report),
        "decision": {
            "recommended_next_task": recommendation,
            "rationale": rationale,
            "battle_budget_signal": battle_signal,
            "non_combat_driver_signal": driver_signal,
            "decision_table": "battle_effect_then_driver_effect_then_curriculum_then_followup",
        },
        "command_passed": bool(budget_report.get("command_passed"))
        and bool(factorial_report.get("command_passed")),
    }


def _factorial_effects(
    by_key: Mapping[tuple[str, int], Mapping[str, Any]],
    seeds: Sequence[str],
    resamples: int,
    seed: int,
) -> dict[str, Any]:
    def rows(driver: str, budget: int) -> dict[str, Mapping[str, Any]]:
        return {
            str(row["seed"]): row for row in _records(by_key[(driver, budget)], "runs")
        }

    def effect(
        left: Mapping[str, Mapping[str, Any]],
        right: Mapping[str, Mapping[str, Any]],
        metric: str,
    ) -> dict[str, Any]:
        values = [
            _metric_number(left[s].get(metric)) - _metric_number(right[s].get(metric))
            for s in seeds
        ]
        return {
            "mean": _mean(values),
            "bootstrap_95ci": _bootstrap_ci(values, resamples, seed),
        }

    result: dict[str, Any] = {
        "driver_effects": {},
        "budget_effects": {},
        "interaction_effects": {},
    }
    for budget in _REQUIRED_BUDGETS:
        result["driver_effects"][str(budget)] = {
            metric: effect(
                rows(_REQUIRED_DRIVERS[1], budget),
                rows(_REQUIRED_DRIVERS[0], budget),
                metric,
            )
            for metric in ("won", "act2_entry", "act3_entry", "heart_victory")
        }
    for driver in _REQUIRED_DRIVERS:
        result["budget_effects"][driver] = {
            metric: effect(rows(driver, 300), rows(driver, 20), metric)
            for metric in ("won", "act2_entry", "act3_entry", "heart_victory")
        }
    for metric in ("won", "act2_entry", "act3_entry", "heart_victory"):
        high = effect(
            rows(_REQUIRED_DRIVERS[1], 300), rows(_REQUIRED_DRIVERS[1], 20), metric
        )
        low = effect(
            rows(_REQUIRED_DRIVERS[0], 300), rows(_REQUIRED_DRIVERS[0], 20), metric
        )
        result["interaction_effects"][metric] = {
            "mean": (high["mean"] or 0) - (low["mean"] or 0),
            "bootstrap_95ci": _bootstrap_ci(
                [
                    (
                        _metric_number(rows(_REQUIRED_DRIVERS[1], 300)[s].get(metric))
                        - _metric_number(rows(_REQUIRED_DRIVERS[1], 20)[s].get(metric))
                    )
                    - (
                        _metric_number(rows(_REQUIRED_DRIVERS[0], 300)[s].get(metric))
                        - _metric_number(rows(_REQUIRED_DRIVERS[0], 20)[s].get(metric))
                    )
                    for s in seeds
                ],
                resamples,
                seed,
            ),
        }
    return result


def _run_summary(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    counts = {
        field: sum(_truth(row.get(field)) for row in rows)
        for field in _REQUIRED_REACHABILITY_FIELDS
    }
    counts["act1_boss_start"] = sum(_truth(row.get("act1_boss_start")) for row in rows)
    return {
        "run_count": len(rows),
        "reachability": {
            field: counts.get(field, 0) for field in _REQUIRED_REACHABILITY_FIELDS
        },
        "terminal_status_counts": dict(Counter(_status(row) for row in rows)),
        "terminal_floor_counts": dict(
            Counter(str(row.get("terminal_floor", "unavailable")) for row in rows)
        ),
        "death_encounter_counts": dict(
            Counter(str(row.get("death_encounter", "unavailable")) for row in rows)
        ),
        "pre_death_resource_snapshot_available_count": sum(
            isinstance(row.get("pre_death_public_resource_snapshot"), Mapping)
            for row in rows
        ),
        "truncation_count": sum(_status(row) == "truncated" for row in rows),
        "error_count": sum(_status(row) in {"error", "unsupported"} for row in rows),
        "natural_battle_start_counts": _count_field(rows, "natural_battle_starts"),
        "unique_source_counts": _count_field(rows, "unique_source_starts"),
        "compute": {
            "simulator_steps": sum(
                _number(row.get("simulator_steps")) or 0 for row in rows
            ),
            "wall_clock_seconds": sum(
                _number(row.get("wall_clock_seconds")) or 0.0 for row in rows
            ),
        },
    }


def _strata(rows: Sequence[Mapping[str, Any]]) -> dict[str, dict[str, int]]:
    return {
        field: dict(Counter(str(row.get(field, "unavailable")) for row in rows))
        for field in ("act", "room_type", "encounter_id", "boss")
    }


def _common_provenance(payloads: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    values = [_mapping(payload.get("provenance")) for payload in payloads]
    if not values or any(value != values[0] for value in values[1:]):
        raise ValueError(
            "T061 arms must preserve identical simulator/action/information provenance"
        )
    return values[0]


def _unique_ids(rows: Sequence[Mapping[str, Any]], label: str) -> list[str]:
    ids = [str(row.get("record_id")) for row in rows]
    if any(value in {"None", ""} for value in ids) or len(set(ids)) != len(ids):
        raise ValueError(f"{label}: records must have unique record_id values")
    return ids


def _unique_seed_rows(payload: Mapping[str, Any], key: tuple[str, int]) -> list[str]:
    rows = _records(payload, "runs")
    seeds = [str(row.get("seed")) for row in rows]
    if any(value in {"None", ""} for value in seeds) or len(set(seeds)) != len(seeds):
        raise ValueError(f"{key}: runs must have unique seed values")
    return seeds


def _records(payload: Mapping[str, Any], field: str) -> list[dict[str, Any]]:
    rows = payload.get(field)
    if not isinstance(rows, list) or not all(isinstance(row, Mapping) for row in rows):
        raise ValueError(f"T061 arm requires a list of object rows named {field}")
    return [{str(key): value for key, value in row.items()} for row in rows]


def _count_field(rows: Sequence[Mapping[str, Any]], field: str) -> dict[str, int]:
    total = 0
    for row in rows:
        value = row.get(field, 0)
        total += (
            int(value)
            if isinstance(value, (int, float)) and not isinstance(value, bool)
            else 0
        )
    return {"total": total}


def _outcome_counts(rows: Sequence[Mapping[str, Any]], field: str) -> dict[str, int]:
    return dict(Counter(_json_value_key(row.get(field)) for row in rows))


def _json_value_key(value: Any) -> str:
    if isinstance(value, (Mapping, list)):
        return json.dumps(value, sort_keys=True)
    return str(value if value is not None else "unavailable")


def _paired_mean(
    left: Mapping[str, Mapping[str, Any]],
    right: Mapping[str, Mapping[str, Any]],
    field: str,
    ids: Sequence[str],
) -> float | None:
    values = [
        (_number(right[key].get(field)) or 0.0) - (_number(left[key].get(field)) or 0.0)
        for key in ids
    ]
    return _mean(values)


def _bootstrap_ci(values: Sequence[float], resamples: int, seed: int) -> list[float]:
    if not values:
        return [0.0, 0.0]
    rng = random.Random(seed)
    means = sorted(
        sum(rng.choice(values) for _ in values) / len(values) for _ in range(resamples)
    )
    return [means[int(0.025 * (len(means) - 1))], means[int(0.975 * (len(means) - 1))]]


def _meaningful_budget_signal(report: Mapping[str, Any]) -> bool:
    effects = _mapping(report.get("pairwise")).get("300_vs_20", {})
    return (
        isinstance(effects, Mapping)
        and _number(effects.get("win_delta")) is not None
        and float(effects["win_delta"]) > 0
    )


def _meaningful_driver_signal(report: Mapping[str, Any]) -> bool:
    effects = _mapping(report.get("effects")).get("driver_effects", {})
    return any(
        _positive_ci(_mapping(_mapping(effects).get(str(budget))).get("won"))
        for budget in _REQUIRED_BUDGETS
    )


def _positive_ci(value: Any) -> bool:
    if not isinstance(value, Mapping):
        return False
    ci = value.get("bootstrap_95ci")
    return isinstance(ci, list) and len(ci) == 2 and float(ci[0]) > 0


def _any_later_act(report: Mapping[str, Any]) -> bool:
    arms = _mapping(report.get("arms"))
    return any(
        _mapping(value).get("reachability", {}).get("act2_entry", 0) > 0
        for value in arms.values()
        if isinstance(value, Mapping)
    )


def _action_key(row: Mapping[str, Any]) -> str:
    return json.dumps(
        row.get("selected_root_action", row.get("first_action")), sort_keys=True
    )


def _status(row: Mapping[str, Any]) -> str:
    return str(row.get("status", row.get("termination_status", "completed")))


def _truth(value: Any) -> int:
    return int(value is True or value == 1 or value == "true" or value == "win")


def _number(value: Any) -> float | None:
    return (
        float(value)
        if isinstance(value, (int, float)) and not isinstance(value, bool)
        else None
    )


def _metric_number(value: Any) -> float:
    if isinstance(value, bool):
        return float(value)
    return _number(value) or 0.0


def _mean(values: Sequence[float | None]) -> float | None:
    clean = [float(value) for value in values if value is not None]
    return sum(clean) / len(clean) if clean else None


def _mapping(value: Any) -> dict[str, Any]:
    return (
        {str(key): item for key, item in value.items()}
        if isinstance(value, Mapping)
        else {}
    )


def _required_label(label: str, field: str) -> int:
    try:
        return int(label)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"T061 {field} arm label must be an integer") from exc


def _ids_hash(values: Sequence[str]) -> str:
    return hashlib.sha256("\n".join(values).encode()).hexdigest()
