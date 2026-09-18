"""Fail-closed, offline T095 repeated-public-state aggregation audit.

The implementation consumes the immutable T092 retained occurrence records.  It
does not import a simulator or Search surface: teacher child means are retained
Oracle-like observations, never a public-policy target.
"""

from __future__ import annotations

import hashlib
import json
import math
import sqlite3
import statistics
import tempfile
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path

from sts_combat_rl.sim.t090_battle_student import canonical_sha256
from sts_combat_rl.sim.t092_internal_search_state import validate_retained_occurrence
from sts_combat_rl.sim.t093_internal_state_student import (
    T093_EXACT_T092_EVIDENCE_SHA256,
    T093_EXACT_T092_RETENTION_SHA256,
    T093Error,
    _validate_t093_inputs,
    validate_t093_source_record,
)

T095_TASK_ID = "T095"
T095_REPORT_SCHEMA_ID = "t095-repeated-public-state-oracle-aggregation-report-v1"
T095_RETENTION_SCHEMA_ID = (
    "t095-repeated-public-state-oracle-aggregation-retention-manifest-v1"
)
T095_SOURCE_RECORD_COUNT = 413
T095_SOURCE_GROUP_COUNTS = {"A": 93, "B": 192, "C": 128}
T095_SOURCE_GROUPS = ("A", "B", "C")
T095_N_MIN = 4
T095_SUPPORT_LEVELS = (2, 4, 8, 16)
T095_TIE_TOLERANCE = 1e-9
T095_SPLIT_DOMAIN = "T095-PUBLIC-AGGREGATION-SPLIT-V1"


class T095Incomplete(ValueError):
    """An exact-artifact, public-boundary, or aggregation predicate failed."""


def _canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _sha256_file(path: Path) -> tuple[str, int]:
    digest, size = hashlib.sha256(), 0
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
            size += len(block)
    return digest.hexdigest(), size


def _read_bound_json(path: Path, expected_sha256: str, label: str) -> dict[str, object]:
    actual, _ = _sha256_file(path)
    if actual != expected_sha256:
        raise T095Incomplete(f"{label} SHA-256 is not the accepted identity")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise T095Incomplete(f"{label} is not readable accepted JSON") from error
    if not isinstance(value, dict):
        raise T095Incomplete(f"{label} must be a JSON object")
    return value


def _validate_ledger(ledger: Mapping[str, Mapping[str, object]]) -> None:
    if len(ledger) != T095_SOURCE_RECORD_COUNT:
        raise T095Incomplete(
            "accepted source ledger does not contain exactly 413 starts"
        )
    groups: Counter[str] = Counter()
    for source, row in ledger.items():
        if not isinstance(source, str) or not source or not isinstance(row, Mapping):
            raise T095Incomplete("accepted source ledger is malformed")
        if (
            row.get("source_identity") != source
            or row.get("source_group") not in T095_SOURCE_GROUPS
        ):
            raise T095Incomplete("accepted source ledger ownership is unavailable")
        groups[str(row["source_group"])] += 1
    if dict(groups) != T095_SOURCE_GROUP_COUNTS:
        raise T095Incomplete("accepted source ledger does not reproduce 93/192/128")


def _public_action_identity(action: Mapping[str, object]) -> dict[str, object]:
    """Use only T092's public action fields; native ``bits`` never groups cells."""

    required = {"scope", "bits", "kind", "idx1", "idx2", "idx3", "label"}
    if set(action) != required or action.get("scope") != "battle":
        raise T095Incomplete("T092 searchable action is not the accepted public shape")
    if not isinstance(action.get("kind"), str) or not isinstance(
        action.get("label"), str
    ):
        raise T095Incomplete("T092 public action identity is malformed")
    if not all(
        isinstance(action.get(key), int) and not isinstance(action.get(key), bool)
        for key in ("idx1", "idx2", "idx3")
    ):
        raise T095Incomplete("T092 public action parameters are malformed")
    # ``bits`` is intentionally validated by T092 but excluded from every T095 key.
    return {
        "scope": "battle",
        "kind": action["kind"],
        "label": action["label"],
        "parameters": {key: action[key] for key in ("idx1", "idx2", "idx3")},
    }


def _sign(value: float) -> int:
    return 1 if value > T095_TIE_TOLERANCE else -1 if value < -T095_TIE_TOLERANCE else 0


def _quantiles(values: Sequence[float]) -> dict[str, float | None]:
    if not values:
        return {
            "p00": None,
            "p25": None,
            "p50": None,
            "p75": None,
            "p90": None,
            "p100": None,
        }
    ordered = sorted(values)

    def percentile(q: float) -> float:
        point = (len(ordered) - 1) * q
        low, high = math.floor(point), math.ceil(point)
        return float(
            ordered[low]
            if low == high
            else ordered[low] + (ordered[high] - ordered[low]) * (point - low)
        )

    return {f"p{int(q * 100):02d}": percentile(q) for q in (0, 0.25, 0.5, 0.75, 0.9, 1)}


def _split_half(
    fingerprint: str, pair_identity: str, cells: Sequence[tuple[str, float]]
) -> tuple[float, float, float, bool]:
    ranked = sorted(
        (
            hashlib.sha256(
                _canonical(
                    [T095_SPLIT_DOMAIN, fingerprint, pair_identity, source]
                ).encode()
            ).hexdigest(),
            source,
            delta,
        )
        for source, delta in cells
    )
    if len({source for _, source, _ in ranked}) != len(ranked):
        raise T095Incomplete("source identity occurs in both split-half candidates")
    halves = [
        [delta for _, _, delta in ranked[::2]],
        [delta for _, _, delta in ranked[1::2]],
    ]
    if not halves[0] or not halves[1]:
        raise T095Incomplete("primary aggregate lacks both deterministic split halves")
    full = statistics.fmean(delta for _, _, delta in ranked)
    first, second = statistics.fmean(halves[0]), statistics.fmean(halves[1])
    stable = _sign(full) != 0 and _sign(full) == _sign(first) == _sign(second)
    return full, first, second, stable


def _classification(
    *,
    fingerprints: int,
    aggregates: int,
    stable_fraction: float,
    varying: int,
    varying_stable_fraction: float,
) -> tuple[str, str, dict[str, bool]]:
    predicates = {
        "repeated_public_fingerprints_at_least_100": fingerprints >= 100,
        "aggregate_pairs_at_least_500": aggregates >= 500,
        "overall_direction_stability_at_least_70_percent": stable_fraction >= 0.70,
        "conditional_variation_pairs_at_least_100": varying >= 100,
        "varying_pair_direction_stability_at_least_60_percent": varying_stable_fraction
        >= 0.60,
    }
    if all(predicates.values()):
        return (
            "EMPIRICAL_PUBLIC_AGGREGATION_FEASIBLE",
            "A separately published T034 public-consistent hidden-future sampler investment may be prioritized; T095 does not authorize it.",
            predicates,
        )
    if not (
        predicates["repeated_public_fingerprints_at_least_100"]
        and predicates["aggregate_pairs_at_least_500"]
        and predicates["conditional_variation_pairs_at_least_100"]
    ):
        return (
            "EMPIRICAL_PUBLIC_AGGREGATION_TOO_SPARSE",
            "Do not infer hidden-future averaging is wrong; Planner must decide whether a separately specified sampler/data effort is justified.",
            predicates,
        )
    return (
        "EMPIRICAL_PUBLIC_AGGREGATION_NOT_STABLE",
        "Do not train a student from these aggregates; a successor may investigate public representation, sampling, continuation information, or a principled T034 design.",
        predicates,
    )


def _audit_records(
    *,
    artifacts: Sequence[Mapping[str, object]],
    ledger: Mapping[str, Mapping[str, object]],
    load_record: Callable[[Mapping[str, object]], Mapping[str, object]],
    spill_directory: Path,
) -> dict[str, object]:
    """Aggregate validated source records, preserving every supported pair sign."""

    _validate_ledger(ledger)
    with tempfile.NamedTemporaryFile(
        prefix="t095-public-aggregation-",
        suffix=".sqlite3",
        dir=spill_directory,
        delete=False,
    ) as temporary:
        database_path = Path(temporary.name)
    connection = sqlite3.connect(database_path)
    try:
        connection.executescript(
            "PRAGMA journal_mode=OFF; PRAGMA synchronous=OFF; PRAGMA temp_store=FILE;"
            "CREATE TABLE cells (fingerprint TEXT NOT NULL, pair_identity TEXT NOT NULL, source_identity TEXT NOT NULL, source_group TEXT NOT NULL, occurrence_count INTEGER NOT NULL, total REAL NOT NULL, minimum REAL NOT NULL, maximum REAL NOT NULL, positive INTEGER NOT NULL, tie INTEGER NOT NULL, negative INTEGER NOT NULL, PRIMARY KEY(fingerprint,pair_identity,source_identity));"
        )
        seen: set[str] = set()
        for artifact in artifacts:
            record = load_record(artifact)
            source = (
                record.get("source_identity") if isinstance(record, Mapping) else None
            )
            expected = ledger.get(source) if isinstance(source, str) else None
            if expected is None or source in seen:
                raise T095Incomplete(
                    "retained source record provenance is unavailable or duplicated"
                )
            try:
                validate_t093_source_record(
                    record, artifact=artifact, expected_source=expected
                )
            except T093Error as error:
                raise T095Incomplete(
                    "retained source record does not match accepted T092 provenance"
                ) from error
            seen.add(source)
            for raw in record["internal_occurrences"]:
                if not isinstance(raw, Mapping):
                    raise T095Incomplete("retained internal occurrence is malformed")
                try:
                    occurrence = validate_retained_occurrence(raw)
                except ValueError as error:
                    raise T095Incomplete(
                        "retained occurrence violates the accepted public boundary"
                    ) from error
                if (
                    occurrence.source_identity != source
                    or occurrence.source_group != expected["source_group"]
                    or occurrence.split != expected["split"]
                ):
                    raise T095Incomplete(
                        "retained occurrence ownership differs from accepted source"
                    )
                supported = [
                    (
                        _canonical(_public_action_identity(dict(row["action"]))),
                        float(row["mean_value"]),
                    )
                    for row in occurrence.searchable_actions
                    if int(row["visits"]) >= T095_N_MIN
                    and row["mean_value"] is not None
                    and math.isfinite(float(row["mean_value"]))
                ]
                for left_index, (left_id, left_mean) in enumerate(supported):
                    for right_id, right_mean in supported[left_index + 1 :]:
                        first_id, first_mean, second_id, second_mean = (
                            (left_id, left_mean, right_id, right_mean)
                            if left_id < right_id
                            else (right_id, right_mean, left_id, left_mean)
                        )
                        pair_identity, delta = (
                            _canonical([first_id, second_id]),
                            first_mean - second_mean,
                        )
                        sign = _sign(delta)
                        connection.execute(
                            "INSERT INTO cells VALUES (?, ?, ?, ?, 1, ?, ?, ?, ?, ?, ?) ON CONFLICT(fingerprint,pair_identity,source_identity) DO UPDATE SET occurrence_count=occurrence_count+1,total=total+excluded.total,minimum=MIN(minimum,excluded.minimum),maximum=MAX(maximum,excluded.maximum),positive=positive+excluded.positive,tie=tie+excluded.tie,negative=negative+excluded.negative",
                            (
                                occurrence.fingerprint,
                                pair_identity,
                                source,
                                occurrence.source_group,
                                delta,
                                delta,
                                delta,
                                int(sign > 0),
                                int(sign == 0),
                                int(sign < 0),
                            ),
                        )
        if seen != set(ledger):
            raise T095Incomplete(
                "not every accepted T092 source record was processed exactly once"
            )
        connection.commit()
        aggregates: list[dict[str, object]] = []
        source_counts: list[float] = []
        multiplicities: list[float] = []
        occurrence_pair_observations = 0
        for fingerprint, pair_identity in connection.execute(
            "SELECT DISTINCT fingerprint, pair_identity FROM cells ORDER BY fingerprint, pair_identity"
        ):
            rows = list(
                connection.execute(
                    "SELECT source_identity, source_group, occurrence_count, total, minimum, maximum, positive, tie, negative FROM cells WHERE fingerprint=? AND pair_identity=? ORDER BY source_identity",
                    (fingerprint, pair_identity),
                )
            )
            if not rows:
                raise T095Incomplete("aggregation index lost a public pair")
            cells = [
                (str(source), float(total) / int(count))
                for source, _, count, total, *_ in rows
            ]
            source_counts.append(float(len(cells)))
            multiplicities.extend(float(count) for _, _, count, *_ in rows)
            occurrence_pair_observations += sum(int(count) for _, _, count, *_ in rows)
            aggregates.append(
                {
                    "fingerprint": fingerprint,
                    "pair_identity": pair_identity,
                    "cells": cells,
                    "groups": sorted({str(group) for _, group, *_ in rows}),
                    "cell_summaries": [
                        {
                            "source_identity": source,
                            "source_group": group,
                            "occurrence_count": count,
                            "mean_delta": float(total) / int(count),
                            "minimum_delta": minimum,
                            "maximum_delta": maximum,
                            "positive_occurrences": positive,
                            "tie_occurrences": tie,
                            "negative_occurrences": negative,
                        }
                        for (
                            source,
                            group,
                            count,
                            total,
                            minimum,
                            maximum,
                            positive,
                            tie,
                            negative,
                        ) in rows
                    ],
                }
            )
        support: dict[str, object] = {}
        for level in T095_SUPPORT_LEVELS:
            eligible = [row for row in aggregates if len(row["cells"]) >= level]
            composition = Counter(
                "mixed" if len(row["groups"]) > 1 else f"{row['groups'][0]}-only"
                for row in eligible
            )
            stability_count = varying_count_at_level = varying_stable_count_at_level = 0
            for row in eligible:
                values = [delta for _, delta in row["cells"]]
                _, _, _, stable = _split_half(
                    str(row["fingerprint"]), str(row["pair_identity"]), row["cells"]
                )
                varying = any(_sign(value) > 0 for value in values) and any(
                    _sign(value) < 0 for value in values
                )
                stability_count += int(stable)
                varying_count_at_level += int(varying)
                varying_stable_count_at_level += int(varying and stable)
            support[str(level)] = {
                "distinct_repeated_public_fingerprints": len(
                    {str(row["fingerprint"]) for row in eligible}
                ),
                "distinct_fingerprint_action_pair_aggregates": len(eligible),
                "source_group_composition": {
                    key: composition.get(key, 0)
                    for key in ("A-only", "B-only", "C-only", "mixed")
                },
                "direction_stability": {
                    "direction_stable_count": stability_count,
                    "direction_stable_fraction": stability_count / len(eligible)
                    if eligible
                    else 0.0,
                    "observed_conditional_variation_count": varying_count_at_level,
                    "varying_direction_stable_count": varying_stable_count_at_level,
                    "varying_direction_stable_fraction": varying_stable_count_at_level
                    / varying_count_at_level
                    if varying_count_at_level
                    else 0.0,
                },
            }
        primary = [row for row in aggregates if len(row["cells"]) >= 8]
        variation_rows: list[dict[str, object]] = []
        stable_count = varying_count = varying_stable_count = 0
        deltas: list[float] = []
        for row in primary:
            cells = row["cells"]
            values = [delta for _, delta in cells]
            full, half0, half1, stable = _split_half(
                str(row["fingerprint"]), str(row["pair_identity"]), cells
            )
            positive, ties, negative = (
                sum(_sign(value) > 0 for value in values),
                sum(_sign(value) == 0 for value in values),
                sum(_sign(value) < 0 for value in values),
            )
            varying = positive > 0 and negative > 0
            stable_count += int(stable)
            varying_count += int(varying)
            varying_stable_count += int(varying and stable)
            deltas.append(full)
            variation_rows.append(
                {
                    "public_fingerprint": row["fingerprint"],
                    "action_pair_identity": json.loads(str(row["pair_identity"])),
                    "source_start_count": len(values),
                    "mean_delta": full,
                    "median_delta": statistics.median(values),
                    "standard_deviation": statistics.stdev(values)
                    if len(values) > 1
                    else 0.0,
                    "minimum_delta": min(values),
                    "maximum_delta": max(values),
                    "positive_source_cells": positive,
                    "tie_source_cells": ties,
                    "negative_source_cells": negative,
                    "positive_fraction_among_non_ties": positive / (positive + negative)
                    if positive + negative
                    else None,
                    "observed_conditional_variation": varying,
                    "split_half_means": {"half_0": half0, "half_1": half1},
                    "direction_stable": stable,
                    "source_macro_cells": row["cell_summaries"],
                }
            )
        total = len(primary)
        stable_fraction = stable_count / total if total else 0.0
        varying_stable_fraction = (
            varying_stable_count / varying_count if varying_count else 0.0
        )
        terminal, recommendation, predicates = _classification(
            fingerprints=len({str(row["fingerprint"]) for row in primary}),
            aggregates=total,
            stable_fraction=stable_fraction,
            varying=varying_count,
            varying_stable_fraction=varying_stable_fraction,
        )
        return {
            "schema_id": T095_REPORT_SCHEMA_ID,
            "schema_version": 1,
            "task_id": T095_TASK_ID,
            "terminal_classification": terminal,
            "successor_recommendation": recommendation,
            "claim_boundary": "observed T092 Oracle-conditioned empirical deltas only; not hidden-future posterior sampling, public-only continuation values, normal-information optimality, student learnability, controller improvement, or T034 closure",
            "audit_definition": {
                "source_macro_weighting": "each (public fingerprint, public action pair, source start) contributes exactly one arithmetic-mean cell",
                "n_min": T095_N_MIN,
                "support_levels": list(T095_SUPPORT_LEVELS),
                "tie_tolerance": T095_TIE_TOLERANCE,
                "split_domain_separator": T095_SPLIT_DOMAIN,
                "private_fields_in_grouping_weighting_split_or_target": False,
            },
            "source_inventory": [dict(ledger[source]) for source in sorted(ledger)],
            "support_surface": support,
            "occurrence_pair_observation_count": occurrence_pair_observations,
            "primary_k_min_8": {
                "distinct_repeated_public_fingerprints": len(
                    {str(row["fingerprint"]) for row in primary}
                ),
                "distinct_fingerprint_action_pair_aggregates": total,
                "direction_stable_count": stable_count,
                "direction_stable_fraction": stable_fraction,
                "observed_conditional_variation_count": varying_count,
                "varying_direction_stable_count": varying_stable_count,
                "varying_direction_stable_fraction": varying_stable_fraction,
                "source_start_count_quantiles": _quantiles(source_counts),
                "source_cell_occurrence_multiplicity_quantiles": _quantiles(
                    multiplicities
                ),
                "aggregate_mean_delta_quantiles": _quantiles(deltas),
                "aggregate_rows": variation_rows,
            },
            "primary_gate_predicates": predicates,
            "resource_topology": {
                "source_record_processing": "one accepted source record at a time",
                "macro_aggregation_store": "temporary sqlite spill index",
                "simulator_or_search_invocation": False,
            },
        }
    finally:
        connection.close()
        database_path.unlink(missing_ok=True)


def audit_t095_from_paths(
    *,
    t092_retention_manifest_path: str | Path,
    t092_evidence_path: str | Path,
    spill_directory: str | Path | None = None,
) -> dict[str, object]:
    try:
        retention_path, evidence_path = (
            Path(t092_retention_manifest_path).resolve(strict=True),
            Path(t092_evidence_path).resolve(strict=True),
        )
    except OSError as error:
        raise T095Incomplete(
            "a required accepted T092 input path is unavailable"
        ) from error
    retention = _read_bound_json(
        retention_path, T093_EXACT_T092_RETENTION_SHA256, "T092 retention manifest"
    )
    evidence = _read_bound_json(
        evidence_path, T093_EXACT_T092_EVIDENCE_SHA256, "T092 formal evidence"
    )
    try:
        artifacts, ledger = _validate_t093_inputs(retention, evidence)
    except T093Error as error:
        raise T095Incomplete(
            "accepted T092 artifact inventory/evidence is invalid"
        ) from error

    def load_record(artifact: Mapping[str, object]) -> Mapping[str, object]:
        raw_path = artifact.get("path")
        if not isinstance(raw_path, str):
            raise T095Incomplete("T092 source artifact lacks a path")
        path = Path(raw_path).resolve(strict=True)
        actual, size = _sha256_file(path)
        if (
            actual != artifact.get("sha256")
            or size != artifact.get("size_bytes")
            or artifact.get("schema_id") != "t092-paired-canary-arm-record-v2"
        ):
            raise T095Incomplete(
                "T092 source artifact is not the accepted retained byte stream"
            )
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise T095Incomplete("T092 source artifact is unreadable JSON") from error
        if not isinstance(record, Mapping):
            raise T095Incomplete("T092 source artifact is not a JSON object")
        return record

    spill = (
        Path(tempfile.gettempdir())
        if spill_directory is None
        else Path(spill_directory).resolve()
    )
    spill.mkdir(parents=True, exist_ok=True)
    report = _audit_records(
        artifacts=artifacts,
        ledger=ledger,
        load_record=load_record,
        spill_directory=spill,
    )
    report["input_identities"] = {
        "t092_formal_evidence": {
            "path": str(evidence_path),
            "sha256": T093_EXACT_T092_EVIDENCE_SHA256,
        },
        "t092_retention_manifest": {
            "path": str(retention_path),
            "sha256": T093_EXACT_T092_RETENTION_SHA256,
        },
        "source_artifact_inventory_sha256": canonical_sha256(artifacts),
    }
    return report


def write_t095_artifacts(
    *,
    t092_retention_manifest_path: str | Path,
    t092_evidence_path: str | Path,
    output_dir: str | Path,
) -> dict[str, object]:
    destination = Path(output_dir).resolve()
    destination.mkdir(parents=True, exist_ok=True)
    report_path = (
        destination / "t095-repeated-public-state-oracle-aggregation-report.json"
    )
    try:
        report = audit_t095_from_paths(
            t092_retention_manifest_path=t092_retention_manifest_path,
            t092_evidence_path=t092_evidence_path,
            spill_directory=destination,
        )
    except T095Incomplete as error:
        report = {
            "schema_id": T095_REPORT_SCHEMA_ID,
            "schema_version": 1,
            "task_id": T095_TASK_ID,
            "terminal_classification": "INCOMPLETE",
            "successor_recommendation": None,
            "incomplete_reason": str(error),
            "claim_boundary": "no empirical aggregation interpretation is allowed because required accepted facts did not validate",
        }
    report_path.write_text(
        json.dumps(report, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )
    sha256, size = _sha256_file(report_path)
    manifest = {
        "schema_id": T095_RETENTION_SCHEMA_ID,
        "schema_version": 1,
        "task_id": T095_TASK_ID,
        "report": {
            "path": str(report_path),
            "sha256": sha256,
            "size_bytes": size,
            "schema_id": T095_REPORT_SCHEMA_ID,
        },
        "regeneration_command": "python -m sts_combat_rl.commands.t095_public_aggregation --t092-retention-manifest <accepted-t092-retention> --t092-formal-evidence <accepted-t092-evidence> --output-dir <ignored-local-t095-output>",
        "retention_reason": "T095 exact-artifact repeated-public-state Oracle aggregation feasibility audit",
    }
    (destination / "t095-retention-manifest.json").write_text(
        json.dumps(manifest, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )
    return report
