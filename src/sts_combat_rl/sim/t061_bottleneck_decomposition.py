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
import math
from pathlib import Path
import random
import re
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
    "act1_boss_victory",
    "act2_boss_start",
    "act2_boss_victory",
    "act3_boss_start",
    "act3_boss_victory",
    "act2_entry",
    "act3_entry",
    "act4_entry",
    "heart_start",
    "heart_victory",
    "shield_spear_start",
    "shield_spear_outcome",
)
_REQUIRED_PROVENANCE_FIELDS = (
    "simulator",
    "source_manifest",
    "integration_commit",
    "action_space",
    "root_selection_rule",
    "information_regime",
    "search_api",
    "distribution_kind",
    "controller_name",
)
_REQUIRED_FACTORIAL_ROW_FIELDS = (
    "seed",
    "source_run_id",
    "status",
    "terminal_floor",
    "terminal_status",
    "won",
    *_REQUIRED_REACHABILITY_FIELDS,
    "death_encounter",
    "pre_death_public_resource_snapshot",
    "natural_battle_starts",
    "unique_source_starts",
    "act_counts",
    "room_type_counts",
    "encounter_id_counts",
    "unique_act_counts",
    "unique_room_type_counts",
    "unique_encounter_id_counts",
    "outer_simulator_steps",
    "outer_wall_clock_seconds",
    "search_telemetry_summary",
    "search_simulations_completed",
    "search_simulations_completed_unavailable_reason",
    "truncation",
    "controller_error",
    "unsupported_state",
    "problems",
)
_REQUIRED_BUDGET_ROW_FIELDS = (
    "record_id",
    "won",
    "terminal_absolute_hp",
    "status",
    "selected_root_action",
    "outer_simulator_steps",
    "outer_wall_clock_seconds",
    "search_telemetry_summary",
    "search_simulations_completed",
    "search_simulations_completed_unavailable_reason",
    "potion_outcome",
    "structured_terminal_resource_outcome",
    "act",
    "room_type",
    "encounter_id",
    "boss",
    "truncation",
    "controller_error",
    "unsupported_state",
    "problems",
)
_ALLOWED_STATUSES = {
    "completed",
    "win",
    "loss",
    "truncated",
    "error",
    "unsupported",
}
_PINNED_INTEGRATION_COMMIT = "9dd8f75bd5d2b1aa8a8b5cf1db18f899825f326a"
_PINNED_SOURCE_MANIFEST = "docs/sts_lightspeed_source_manifest.json"
_SEARCH_SUMMARY_METRICS = (
    "simulations_requested",
    "root_visits",
    "root_action_count",
    "legal_action_count",
    "native_simulator_steps",
    "model_calls",
    "wall_clock_time_s",
    "root_value_spread",
    "root_decision_gap",
    "unsearched_legal_action_count",
    "unmapped_search_edge_count",
    "unmapped_root_row_count",
    "root_mapping_failure_count",
)
_SEARCH_MANDATORY_METRICS = {
    "simulations_requested",
    "root_visits",
    "native_simulator_steps",
    "model_calls",
    "wall_clock_time_s",
}


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
    for label, payload in arms:
        budget = _required_label(label, "budget")
        _validate_common_provenance(payload, f"budget {budget}")
        _validate_budget_arm(payload, budget)
    ids_by_budget = {
        budget: _unique_ids(_records(payload, "records"), f"budget {budget}")
        for budget, payload in by_budget.items()
    }
    reference_ids = ids_by_budget[20]
    if any(ids != reference_ids for ids in ids_by_budget.values()):
        raise ValueError("T061 budget arms must contain the same cohort identities")
    for budget, payload in by_budget.items():
        arm = _mapping(payload["arm_provenance"])
        if arm.get("cohort_record_ids_sha256") != _ids_hash(reference_ids):
            raise ValueError(
                f"budget {budget}: cohort identity hash does not match records"
            )
    provenance = _common_provenance(by_budget.values())
    reports: dict[str, Any] = {}
    for budget in _REQUIRED_BUDGETS:
        rows = _records(by_budget[budget], "records")
        reports[str(budget)] = {
            "record_count": len(rows),
            "arm_provenance": _mapping(by_budget[budget]["arm_provenance"]),
            "input_artifact": _artifact_identity(by_budget[budget]),
            "records": rows,
            "win_count": sum(_truth(row.get("won")) for row in rows),
            "loss_count": sum(not _truth(row.get("won")) for row in rows),
            "mean_terminal_absolute_hp": _mean(
                [_number(row.get("terminal_absolute_hp")) for row in rows]
            ),
            "outer_simulator_steps": sum(
                _number(row.get("outer_simulator_steps")) or 0 for row in rows
            ),
            "outer_wall_clock_seconds": sum(
                _number(row.get("outer_wall_clock_seconds")) or 0.0 for row in rows
            ),
            "search_compute": _search_compute_summary(rows),
            "truncation_count": sum(_status(row) == "truncated" for row in rows),
            "error_count": sum(
                _row_failed(row) and _status(row) != "truncated" for row in rows
            ),
            "failure_count": sum(_row_failed(row) for row in rows),
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
            "input_artifacts": {
                "left": _artifact_identity(by_budget[left]),
                "right": _artifact_identity(by_budget[right]),
            },
            "records": [
                {
                    "record_id": key,
                    "left_won": _truth(left_rows[key]["won"]),
                    "right_won": _truth(right_rows[key]["won"]),
                    "left_terminal_absolute_hp": left_rows[key]["terminal_absolute_hp"],
                    "right_terminal_absolute_hp": right_rows[key][
                        "terminal_absolute_hp"
                    ],
                    "first_action_disagreement": _action_key(left_rows[key])
                    != _action_key(right_rows[key]),
                }
                for key in reference_ids
            ],
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
            reports[str(budget)]["failure_count"] == 0 for budget in _REQUIRED_BUDGETS
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
    for driver, budget, payload in arms:
        _validate_common_provenance(payload, f"{driver}@{budget}")
        _validate_factorial_arm(payload, driver, int(budget), expected_run_count)
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
        arm_summary[f"{key[0]}@{key[1]}"] = {
            **_run_summary(rows),
            "arm_provenance": _mapping(payload.get("arm_provenance")),
            "input_artifact": _artifact_identity(payload),
            "run_results": rows,
        }
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
            _run_summary(_records(payload, "runs"))["failure_count"] == 0
            for payload in by_key.values()
        ),
    }


def build_t061_bottleneck_report(
    budget_report: Mapping[str, Any], factorial_report: Mapping[str, Any]
) -> dict[str, Any]:
    """Apply the published decision table and return exactly one next task."""

    battle_signal = _meaningful_budget_signal(budget_report, factorial_report)
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
            "battle_budget_signal_sources": _budget_signal_sources(
                budget_report, factorial_report
            ),
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
        "act_boss_reachability": {
            f"act{act}": {
                "entry_count": counts[f"act{act}_boss_start"],
                "victory_count": counts[f"act{act}_boss_victory"],
            }
            for act in (1, 2, 3)
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
        "error_count": sum(
            _row_failed(row) and _status(row) != "truncated" for row in rows
        ),
        "failure_count": sum(_row_failed(row) for row in rows),
        "natural_battle_start_counts": _count_field(rows, "natural_battle_starts"),
        "unique_source_counts": _count_field(rows, "unique_source_starts"),
        "natural_battle_start_counts_by_act": _nested_count_field(rows, "act_counts"),
        "natural_battle_start_counts_by_room_type": _nested_count_field(
            rows, "room_type_counts"
        ),
        "natural_battle_start_counts_by_encounter": _nested_count_field(
            rows, "encounter_id_counts"
        ),
        "unique_source_counts_by_act": _nested_count_field(rows, "unique_act_counts"),
        "unique_source_counts_by_room_type": _nested_count_field(
            rows, "unique_room_type_counts"
        ),
        "unique_source_counts_by_encounter": _nested_count_field(
            rows, "unique_encounter_id_counts"
        ),
        "compute": {
            "outer_simulator_steps": sum(
                _number(row["outer_simulator_steps"]) or 0 for row in rows
            ),
            "outer_wall_clock_seconds": sum(
                _number(row["outer_wall_clock_seconds"]) or 0.0 for row in rows
            ),
            "search_compute": _search_compute_summary(rows),
            "outer_simulator_steps_observed": True,
            "search_cost_observed": True,
        },
    }


def _validate_search_telemetry(
    row: Mapping[str, Any],
    label: str,
    provenance: Mapping[str, Any],
    budget: int,
) -> None:
    summary = row["search_telemetry_summary"]
    if not isinstance(summary, Mapping):
        raise ValueError(f"{label}: search telemetry summary is missing")
    required_summary_fields = {
        "schema_id",
        "schema_version",
        "decision_telemetry_schema_id",
        "decision_telemetry_schema_version",
        "decision_count",
        "information_regime_counts",
        "controller_kind_counts",
        "search_kind_counts",
        "backend_counts",
        "budget_unit_counts",
        *_SEARCH_SUMMARY_METRICS,
        "unavailable_field_counts",
        "unavailable_reasons",
        "decision_problem_count",
        "problem_count",
    }
    missing = sorted(required_summary_fields.difference(summary))
    if missing:
        raise ValueError(f"{label}: search telemetry missing fields {missing}")
    if summary["schema_id"] != "search-telemetry-summary-v1":
        raise ValueError(f"{label}: unsupported search telemetry summary schema")
    if summary["schema_version"] != 1:
        raise ValueError(f"{label}: unsupported search telemetry summary version")
    if summary["decision_telemetry_schema_id"] != "search-decision-telemetry-v1":
        raise ValueError(f"{label}: unsupported decision telemetry schema")
    if summary["decision_telemetry_schema_version"] != 1:
        raise ValueError(f"{label}: unsupported decision telemetry version")
    decision_count = summary.get("decision_count")
    if not isinstance(decision_count, int) or decision_count <= 0:
        raise ValueError(f"{label}: search telemetry requires decisions")
    _validate_search_counter(
        summary["information_regime_counts"],
        {str(provenance["information_regime"]): decision_count},
        f"{label} information regime counts",
    )
    _validate_search_counter(
        summary["controller_kind_counts"],
        {"oracle_battle_search": decision_count},
        f"{label} controller kind counts",
    )
    _validate_search_counter(
        summary["search_kind_counts"],
        {"native_random_terminal_playout": decision_count},
        f"{label} search kind counts",
    )
    _validate_search_counter(
        summary["backend_counts"],
        {str(provenance["search_api"]): decision_count},
        f"{label} search backend counts",
    )
    _validate_search_counter(
        summary["budget_unit_counts"],
        {"native_random_terminal_playouts": decision_count},
        f"{label} search budget unit counts",
    )
    for metric_name in _SEARCH_SUMMARY_METRICS:
        _validate_search_metric(
            summary[metric_name],
            decision_count,
            metric_name in _SEARCH_MANDATORY_METRICS,
            f"{label} {metric_name}",
        )
    unavailable_counts = _validate_non_negative_counter(
        summary["unavailable_field_counts"],
        f"{label} unavailable field counts",
    )
    reasons = summary["unavailable_reasons"]
    if not isinstance(reasons, Mapping) or any(
        not isinstance(key, str)
        or not isinstance(value, list)
        or not all(isinstance(item, str) for item in value)
        for key, value in reasons.items()
    ):
        raise ValueError(f"{label}: unavailable reasons must be string lists")
    for metric_name in _SEARCH_SUMMARY_METRICS:
        metric = _mapping(summary[metric_name])
        missing_count = metric["missing_count"]
        if missing_count:
            if unavailable_counts.get(metric_name) != missing_count:
                raise ValueError(
                    f"{label}: unavailable count disagrees for {metric_name}"
                )
    for field_name in unavailable_counts:
        if unavailable_counts[field_name] > decision_count:
            raise ValueError(f"{label}: unavailable count exceeds decisions")
    if summary["decision_problem_count"] != 0 or summary["problem_count"] != 0:
        raise ValueError(f"{label}: search telemetry contains decision problems")
    expected_total = float(decision_count * budget)
    for metric_name in ("simulations_requested", "root_visits"):
        total = float(_mapping(summary[metric_name])["total"])
        if not math.isclose(total, expected_total, rel_tol=0.0, abs_tol=1e-9):
            raise ValueError(
                f"{label}: {metric_name} disagrees with decision_count*budget"
            )
    completed = row["search_simulations_completed"]
    reason = row["search_simulations_completed_unavailable_reason"]
    if completed is None:
        if not isinstance(reason, str) or not reason:
            raise ValueError(
                f"{label}: unavailable completed-simulation evidence needs a reason"
            )
    elif not isinstance(completed, int) or completed < 0:
        raise ValueError(f"{label}: completed simulations must be non-negative")


def _validate_search_counter(
    value: Any, expected: Mapping[str, int], label: str
) -> None:
    if not isinstance(value, Mapping) or dict(value) != dict(expected):
        raise ValueError(f"{label} disagree with pinned arm provenance")


def _validate_non_negative_counter(value: Any, label: str) -> dict[str, int]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} must be an object")
    result: dict[str, int] = {}
    for key, count in value.items():
        if not isinstance(key, str) or not isinstance(count, int) or count < 0:
            raise ValueError(f"{label} must contain non-negative integer counts")
        result[key] = count
    return result


def _validate_search_metric(
    value: Any, decision_count: int, mandatory: bool, label: str
) -> None:
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} must be an object")
    required = {"count", "missing_count", "total", "minimum", "maximum", "mean"}
    missing = sorted(required.difference(value))
    if missing:
        raise ValueError(f"{label} missing fields {missing}")
    count = value["count"]
    missing_count = value["missing_count"]
    if (
        not isinstance(count, int)
        or count < 0
        or not isinstance(missing_count, int)
        or missing_count < 0
        or count + missing_count != decision_count
    ):
        raise ValueError(f"{label} count fields are inconsistent")
    if mandatory and (count != decision_count or missing_count != 0):
        raise ValueError(f"{label} is missing mandatory observations")
    numeric = [value[field] for field in ("total", "minimum", "maximum", "mean")]
    if count == 0:
        if any(item is not None for item in numeric):
            raise ValueError(f"{label} has values with zero observations")
        return
    if any(
        not isinstance(item, (int, float))
        or isinstance(item, bool)
        or not math.isfinite(float(item))
        or float(item) < 0
        for item in numeric
    ):
        raise ValueError(f"{label} has invalid negative or non-finite values")
    total, minimum, maximum, mean = (float(item) for item in numeric)
    if minimum > maximum or not minimum <= mean <= maximum:
        raise ValueError(f"{label} min/max/mean are inconsistent")
    if not math.isclose(total, mean * count, rel_tol=1e-9, abs_tol=1e-9):
        raise ValueError(f"{label} total and mean are inconsistent")


def _search_compute_summary(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    summaries = [row["search_telemetry_summary"] for row in rows]

    def total(metric_name: str) -> float:
        return sum(
            float(_mapping(summary[metric_name])["total"]) for summary in summaries
        )

    completed_values = [row["search_simulations_completed"] for row in rows]
    completed = (
        sum(int(value) for value in completed_values)
        if all(value is not None for value in completed_values)
        else None
    )
    return {
        "decision_count": sum(int(summary["decision_count"]) for summary in summaries),
        "native_simulator_steps": total("native_simulator_steps"),
        "simulations_requested": total("simulations_requested"),
        "root_visits": total("root_visits"),
        "simulations_completed": completed,
        "model_calls": total("model_calls"),
        "wall_clock_seconds": total("wall_clock_time_s"),
        "simulations_completed_available": completed is not None,
        "simulations_completed_unavailable_reason": (
            None
            if completed is not None
            else "native battle_search exposes requested simulations and native "
            "simulator steps, but not completed simulation count"
        ),
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


def _validate_common_provenance(payload: Mapping[str, Any], label: str) -> None:
    provenance = payload.get("provenance")
    if not isinstance(provenance, Mapping):
        raise ValueError(f"{label}: provenance must be an object")
    missing = [
        field for field in _REQUIRED_PROVENANCE_FIELDS if field not in provenance
    ]
    if missing:
        raise ValueError(f"{label}: provenance missing fields {missing}")
    if provenance["simulator"] != "sts_lightspeed":
        raise ValueError(f"{label}: unsupported simulator provenance")
    if provenance["source_manifest"] != _PINNED_SOURCE_MANIFEST:
        raise ValueError(f"{label}: source manifest is not the pinned manifest")
    if provenance["integration_commit"] != _PINNED_INTEGRATION_COMMIT:
        raise ValueError(f"{label}: integration commit is not the pinned source")
    if provenance["controller_name"] != "oracle_search_v1":
        raise ValueError(f"{label}: unsupported controller implementation")
    if provenance["search_api"] != "StepSimulator.battle_search.v1":
        raise ValueError(f"{label}: unsupported search API")
    if provenance["information_regime"] != "full_simulator_state_oracle_like":
        raise ValueError(f"{label}: unsupported information regime")
    if provenance["root_selection_rule"] != "highest_mean":
        raise ValueError(f"{label}: unsupported root selection rule")
    if provenance["distribution_kind"] not in {"natural_run", "fixed_cohort"}:
        raise ValueError(f"{label}: unsupported distribution kind")


def _validate_arm_common(
    payload: Mapping[str, Any], label: str, budget: int, expected_distribution: str
) -> dict[str, Any]:
    arm = payload.get("arm_provenance")
    if not isinstance(arm, Mapping):
        raise ValueError(f"{label}: arm_provenance must be an object")
    required = (
        "budget",
        "controller_name",
        "search_budget",
        "root_selection_rule",
        "action_space",
        "information_regime",
        "workers",
        "shards",
        "distribution_kind",
    )
    missing = [field for field in required if field not in arm]
    if missing:
        raise ValueError(f"{label}: arm_provenance missing fields {missing}")
    expected = {
        "budget": budget,
        "controller_name": "oracle_search_v1",
        "search_budget": budget,
        "root_selection_rule": "highest_mean",
        "action_space": "initial_no_potions",
        "information_regime": "full_simulator_state_oracle_like",
        "distribution_kind": expected_distribution,
    }
    for field, value in expected.items():
        if arm[field] != value:
            raise ValueError(f"{label}: arm_provenance {field} does not match arm")
    common = _mapping(payload.get("provenance"))
    for field in (
        "root_selection_rule",
        "action_space",
        "information_regime",
        "distribution_kind",
    ):
        if arm[field] != common.get(field):
            raise ValueError(f"{label}: common and arm provenance disagree on {field}")
    if not isinstance(arm["workers"], int) or not isinstance(arm["shards"], int):
        raise ValueError(f"{label}: arm_provenance workers/shards must be integers")
    if arm["workers"] != 16 or arm["shards"] != 16:
        raise ValueError(f"{label}: T061 evidence requires 16 workers and 16 shards")
    return {str(key): value for key, value in arm.items()}


def _validate_budget_arm(payload: Mapping[str, Any], budget: int) -> None:
    arm = _validate_arm_common(payload, f"budget {budget}", budget, "fixed_cohort")
    if "cohort_record_ids_sha256" not in arm:
        raise ValueError(f"budget {budget}: cohort identity provenance is missing")
    if arm.get("controller_implementation") != (
        f"oracle_search_v1_highest_mean_s{budget}"
    ):
        raise ValueError(
            f"budget {budget}: controller implementation does not match arm"
        )
    if not isinstance(arm.get("action_space_config"), Mapping):
        raise ValueError(f"budget {budget}: action-space configuration is missing")
    for row in _records(payload, "records"):
        _validate_row_fields(row, _REQUIRED_BUDGET_ROW_FIELDS, f"budget {budget}")
        if not isinstance(row["won"], bool):
            raise ValueError("T061 budget rows require boolean won values")
        if _number(row["terminal_absolute_hp"]) is None:
            raise ValueError("T061 budget rows require numeric terminal HP")
        if not isinstance(row["selected_root_action"], Mapping):
            raise ValueError("T061 budget rows require selected_root_action objects")
        if not isinstance(row["structured_terminal_resource_outcome"], Mapping):
            raise ValueError("T061 budget rows require structured resource outcomes")
        if not isinstance(row["problems"], list):
            raise ValueError("T061 budget rows require a problems list")
        _validate_search_telemetry(
            row,
            f"budget {budget}",
            _mapping(payload["provenance"]),
            budget,
        )
        _validate_failure_state(row, f"budget {budget}", {"win", "loss"})
    if _artifact_identity(payload) is None:
        raise ValueError(f"budget {budget}: input artifact identity is missing")


def _validate_factorial_arm(
    payload: Mapping[str, Any], driver: str, budget: int, expected_run_count: int
) -> None:
    label = f"{driver}@{budget}"
    arm = _validate_arm_common(payload, label, budget, "natural_run")
    if arm.get("driver") != driver:
        raise ValueError(f"{label}: arm_provenance driver does not match arm")
    if arm.get("controller_implementation") != (
        f"oracle_search_v1_highest_mean_s{budget}"
    ):
        raise ValueError(
            f"{label}: battle controller implementation does not match arm"
        )
    if arm.get("non_combat_controller_implementation") != driver:
        raise ValueError(
            f"{label}: non-combat controller implementation does not match arm"
        )
    for field in ("seed_start", "seed_end", "sim_steps"):
        if not isinstance(arm.get(field), int):
            raise ValueError(f"{label}: arm_provenance {field} must be an integer")
    if arm["sim_steps"] != 500:
        raise ValueError(f"{label}: T061 factorial evidence requires sim_steps=500")
    rows = _records(payload, "runs")
    if len(rows) != expected_run_count:
        raise ValueError(f"{label}: expected {expected_run_count} runs")
    _validate_row_fields(rows[0] if rows else {}, _REQUIRED_FACTORIAL_ROW_FIELDS, label)
    for row in rows:
        _validate_row_fields(row, _REQUIRED_FACTORIAL_ROW_FIELDS, label)
        if not isinstance(row["won"], bool):
            raise ValueError(f"{label}: won must be boolean")
        if not isinstance(row["status"], str) or not row["status"]:
            raise ValueError(f"{label}: status must be a non-empty string")
        if not isinstance(row["terminal_status"], str):
            raise ValueError(f"{label}: terminal_status must be a string")
        if _number(row["terminal_floor"]) is None:
            raise ValueError(f"{label}: terminal_floor must be numeric")
        for field in _REQUIRED_REACHABILITY_FIELDS:
            if not isinstance(row[field], bool):
                raise ValueError(f"{label}: {field} must be boolean")
        for field in ("natural_battle_starts", "unique_source_starts"):
            if not isinstance(row[field], int) or row[field] < 0:
                raise ValueError(f"{label}: {field} must be a non-negative integer")
        for field in (
            "act_counts",
            "room_type_counts",
            "encounter_id_counts",
            "unique_act_counts",
            "unique_room_type_counts",
            "unique_encounter_id_counts",
        ):
            if not isinstance(row[field], Mapping):
                raise ValueError(f"{label}: {field} must be an object")
        if (
            _number(row["outer_simulator_steps"]) is None
            or _number(row["outer_wall_clock_seconds"]) is None
        ):
            raise ValueError(f"{label}: compute fields must be numeric")
        if (
            not isinstance(row["truncation"], bool)
            or not isinstance(row["controller_error"], bool)
            or not isinstance(row["unsupported_state"], bool)
        ):
            raise ValueError(f"{label}: failure flags must be boolean")
        if not isinstance(row["problems"], list):
            raise ValueError(f"{label}: problems must be a list")
        _validate_search_telemetry(
            row,
            label,
            _mapping(payload["provenance"]),
            budget,
        )
        _validate_failure_state(row, label, {"completed"})
    numeric_seeds = []
    for row in rows:
        try:
            numeric_seeds.append(int(str(row["seed"])))
        except (TypeError, ValueError):
            raise ValueError(f"{label}: seeds must be integers") from None
    expected_seeds = [
        int(seed) for seed in range(arm["seed_start"], arm["seed_end"] + 1)
    ]
    if numeric_seeds != expected_seeds or len(expected_seeds) != expected_run_count:
        raise ValueError(f"{label}: seed range does not match arm provenance")
    if _artifact_identity(payload) is None:
        raise ValueError(f"{label}: input artifact identity is missing")


def _validate_row_fields(
    row: Mapping[str, Any], required: Sequence[str], label: str
) -> None:
    missing = [field for field in required if field not in row]
    if missing:
        raise ValueError(f"{label}: row missing fields {missing}")


def _validate_failure_state(
    row: Mapping[str, Any], label: str, success_statuses: set[str]
) -> None:
    status = _status(row)
    if status not in _ALLOWED_STATUSES:
        raise ValueError(f"{label}: unsupported status {status!r}")
    flags = {
        "truncation": row["truncation"],
        "controller_error": row["controller_error"],
        "unsupported_state": row["unsupported_state"],
    }
    has_failure = any(flags.values()) or bool(row["problems"])
    if status in success_statuses and has_failure:
        raise ValueError(
            f"{label}: success status is inconsistent with failure evidence"
        )
    if status == "truncated" and not flags["truncation"]:
        raise ValueError(f"{label}: truncated status requires truncation=true")
    if status == "error" and not (flags["controller_error"] or bool(row["problems"])):
        raise ValueError(f"{label}: error status lacks controller failure evidence")
    if status == "unsupported" and not (
        flags["unsupported_state"] or bool(row["problems"])
    ):
        raise ValueError(f"{label}: unsupported status lacks unsupported evidence")


def _artifact_identity(payload: Mapping[str, Any]) -> dict[str, Any] | None:
    value = payload.get("artifact_identity")
    if not isinstance(value, Mapping):
        return None
    if not isinstance(value.get("sha256"), str) or not re.fullmatch(
        r"[0-9a-fA-F]{64}", value["sha256"]
    ):
        return None
    if not isinstance(value.get("path"), str) or not value["path"]:
        return None
    if not isinstance(value.get("bytes"), int) or value["bytes"] < 0:
        return None
    path = Path(str(value["path"]))
    if not path.exists():
        return None
    try:
        actual_hash, actual_bytes = _hash_retained_artifact(
            path, value.get("hash_basis")
        )
    except (OSError, ValueError):
        return None
    if actual_hash != value["sha256"].lower() or actual_bytes != value["bytes"]:
        return None
    return {str(key): item for key, item in value.items()}


def _hash_retained_artifact(path: Path, basis: Any) -> tuple[str, int]:
    digest = hashlib.sha256()
    total = 0
    if path.is_file():
        files = [path]
    elif isinstance(basis, str) and "pool.jsonl" in basis:
        files = sorted(path.glob("shards/*/pool.jsonl"))
    elif isinstance(basis, str) and "shard jsonl" in basis:
        files = sorted(path.glob("shard-*.jsonl"))
    else:
        raise ValueError(f"unsupported retained artifact hash basis for {path}")
    if not files:
        raise ValueError(f"retained artifact has no files to hash: {path}")
    for child in files:
        digest.update(child.name.encode())
        data = child.read_bytes()
        digest.update(data)
        total += len(data)
    return digest.hexdigest(), total


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


def _nested_count_field(
    rows: Sequence[Mapping[str, Any]], field: str
) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for row in rows:
        value = row.get(field)
        if isinstance(value, Mapping):
            for key, amount in value.items():
                if isinstance(amount, (int, float)) and not isinstance(amount, bool):
                    counts[str(key)] += int(amount)
    return dict(counts)


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


def _meaningful_budget_signal(
    report: Mapping[str, Any], factorial_report: Mapping[str, Any] | None = None
) -> bool:
    effects = _mapping(report.get("pairwise")).get("300_vs_20", {})
    win_effect = _mapping(effects).get("win_effect", {})
    if _positive_ci(win_effect):
        return True
    if factorial_report is None:
        return False
    budget_effects = _mapping(factorial_report.get("effects")).get("budget_effects", {})
    return any(
        _positive_ci(_mapping(budget_effects.get(driver)).get(metric))
        for driver in _REQUIRED_DRIVERS
        for metric in ("won", "act2_entry", "act3_entry", "heart_victory")
    )


def _budget_signal_sources(
    report: Mapping[str, Any], factorial_report: Mapping[str, Any]
) -> list[str]:
    sources: list[str] = []
    effects = _mapping(report.get("pairwise")).get("300_vs_20", {})
    if _positive_ci(_mapping(effects).get("win_effect")):
        sources.append("restored_battle_300_vs_20")
    budget_effects = _mapping(factorial_report.get("effects")).get("budget_effects", {})
    if any(
        _positive_ci(_mapping(budget_effects.get(driver)).get(metric))
        for driver in _REQUIRED_DRIVERS
        for metric in ("won", "act2_entry", "act3_entry", "heart_victory")
    ):
        sources.append("complete_run_factorial_budget_effect")
    return sources


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
        any(
            _mapping(value).get("reachability", {}).get(field, 0) > 0
            for field in ("act3_entry", "act4_entry", "heart_start", "heart_victory")
        )
        for value in arms.values()
        if isinstance(value, Mapping)
    )


def _action_key(row: Mapping[str, Any]) -> str:
    return json.dumps(
        row.get("selected_root_action", row.get("first_action")), sort_keys=True
    )


def _status(row: Mapping[str, Any]) -> str:
    value = row.get("status")
    if not isinstance(value, str) or value not in _ALLOWED_STATUSES:
        raise ValueError("T061 rows require an explicit non-empty status")
    return value


def _row_failed(row: Mapping[str, Any]) -> bool:
    return bool(
        row["truncation"]
        or row["controller_error"]
        or row["unsupported_state"]
        or row["problems"]
        or _status(row) in {"truncated", "error", "unsupported"}
    )


def _truth(value: Any) -> int:
    if not isinstance(value, bool):
        raise ValueError("T061 boolean evidence must be an explicit boolean")
    return int(value)


def _number(value: Any) -> float | None:
    return (
        float(value)
        if isinstance(value, (int, float)) and not isinstance(value, bool)
        else None
    )


def _metric_number(value: Any) -> float:
    if isinstance(value, bool):
        return float(value)
    number = _number(value)
    if number is None:
        raise ValueError("T061 effect metric is missing or non-numeric")
    return number


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
