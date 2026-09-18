"""Fail-closed, file-only T094 source-start attrition audit.

The audit deliberately reuses the accepted T092 retained records and the
accepted T093 corpus identity.  It neither restores a checkpoint nor imports
the simulator/Search boundary.  SQLite is only a temporary, bounded spill
index for the T093 n_min=4 fingerprint rule; no source record is rewritten.
"""

from __future__ import annotations

import hashlib
import json
import math
import sqlite3
import tempfile
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

from sts_combat_rl.sim.t090_battle_student import canonical_sha256
from sts_combat_rl.sim.t092_internal_search_state import (
    T092Occurrence,
    validate_retained_occurrence,
)
from sts_combat_rl.sim.t093_internal_state_student import (
    T093_EXACT_T092_EVIDENCE_SHA256,
    T093_EXACT_T092_RETENTION_SHA256,
    T093Error,
    _validate_t093_inputs,
    validate_t093_source_record,
)

T094_TASK_ID = "T094"
T094_REPORT_SCHEMA_ID = "t094-a-cohort-supervision-attrition-report-v1"
T094_RETENTION_SCHEMA_ID = "t094-a-cohort-supervision-attrition-retention-manifest-v1"
T094_SOURCE_RECORD_COUNT = 413
T094_SOURCE_GROUPS = ("A", "B", "C")
T094_SPLITS = ("train", "validation", "heldout")
T094_SOURCE_GROUP_COUNTS = {"A": 93, "B": 192, "C": 128}
T094_N_MINS = (1, 2, 4)
T094_PAIR_TOLERANCE = 1e-9
T094_A_DIAGNOSTIC_MINIMUM = 70
T094_EXACT_T093_CORPUS_SHA256 = (
    "c6ea76b149b54502eed1da0741914b80ca13cdd84cad5e518eae410399c90ca9"
)
T094_EXACT_T093_RETENTION_SHA256 = (
    "5c42482003611878a0c56108fea0a3c8f8a287e6ec7ab1d1f8817bd741fb71b6"
)
T094_EXACT_T093_CORPUS_SIZE_BYTES = 854_505_301
T094_EXPECTED_S3_FINGERPRINTS = {
    "train": 25_825,
    "validation": 5_842,
    "heldout": 8_383,
}
T094_EXPECTED_S3_STARTS = {
    "train": {"A": 30, "B": 119, "C": 77},
    "validation": {"A": 6, "B": 30, "C": 20},
    "heldout": {"A": 9, "B": 43, "C": 27},
}


class T094Incomplete(ValueError):
    """A required accepted fact is unavailable or the T093 pipeline diverges."""


def _canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _sha256_file(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
            size += len(block)
    return digest.hexdigest(), size


def _read_json_bound(path: Path, expected_sha256: str, label: str) -> dict[str, Any]:
    actual_sha256, _ = _sha256_file(path)
    if actual_sha256 != expected_sha256:
        raise T094Incomplete(f"{label} SHA-256 is not the accepted identity")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise T094Incomplete(f"{label} is not readable accepted JSON") from error
    if not isinstance(value, dict):
        raise T094Incomplete(f"{label} must be a JSON object")
    return value


def _validate_t093_retention(
    retention: Mapping[str, object],
    *,
    corpus_path: Path,
    artifacts: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    corpus_sha256, corpus_size = _sha256_file(corpus_path)
    if (
        corpus_sha256 != T094_EXACT_T093_CORPUS_SHA256
        or corpus_size != T094_EXACT_T093_CORPUS_SIZE_BYTES
        or retention.get("schema_id")
        != "t093-internal-state-student-retention-manifest-v1"
        or retention.get("schema_version") != 1
        or retention.get("task_id") != "T093"
        or retention.get("t092_evidence_sha256") != T093_EXACT_T092_EVIDENCE_SHA256
        or retention.get("t092_retention_manifest_sha256")
        != T093_EXACT_T092_RETENTION_SHA256
        or retention.get("source_artifact_inventory_sha256")
        != canonical_sha256(artifacts)
    ):
        raise T094Incomplete("T093 retained corpus/lineage identity is not accepted")
    derived = retention.get("derived_corpus")
    if not isinstance(derived, Mapping) or (
        derived.get("schema_id") != "t093-internal-partial-ranking-corpus-v1"
        or derived.get("sha256") != corpus_sha256
        or derived.get("size_bytes") != corpus_size
        or Path(str(derived.get("path", ""))).resolve() != corpus_path.resolve()
    ):
        raise T094Incomplete(
            "T093 retention manifest does not bind the supplied corpus"
        )
    return {
        "path": str(corpus_path),
        "sha256": corpus_sha256,
        "size_bytes": corpus_size,
        "schema_id": str(derived["schema_id"]),
    }


def _validate_ledger(ledger: Mapping[str, Mapping[str, object]]) -> None:
    if len(ledger) != T094_SOURCE_RECORD_COUNT:
        raise T094Incomplete(
            "accepted source ledger does not contain exactly 413 starts"
        )
    counts: Counter[str] = Counter()
    for source, row in ledger.items():
        if not isinstance(source, str) or not source or not isinstance(row, Mapping):
            raise T094Incomplete("accepted source ledger is malformed")
        if (
            row.get("source_identity") != source
            or row.get("source_group") not in T094_SOURCE_GROUPS
        ):
            raise T094Incomplete("accepted source ledger ownership is unavailable")
        if row.get("split") not in T094_SPLITS:
            raise T094Incomplete(
                "accepted source ledger split ownership is unavailable"
            )
        counts[str(row["source_group"])] += 1
    if dict(counts) != T094_SOURCE_GROUP_COUNTS:
        raise T094Incomplete(
            "accepted A/B/C source-start ledger does not reproduce 93/192/128"
        )


def _pair_bearing(occurrence: T092Occurrence, n_min: int) -> bool:
    means = [
        float(row["mean_value"])
        for row in occurrence.searchable_actions
        if int(row["visits"]) >= n_min and row["mean_value"] is not None
    ]
    return any(
        abs(left - right) > T094_PAIR_TOLERANCE
        for offset, left in enumerate(means)
        for right in means[offset + 1 :]
    )


def _empty_start_sets() -> dict[int, set[str]]:
    return {n_min: set() for n_min in T094_N_MINS}


def _percentile(values: Sequence[int], quantile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    point = (len(ordered) - 1) * quantile
    low, high = math.floor(point), math.ceil(point)
    return float(
        ordered[low]
        if low == high
        else ordered[low] + (ordered[high] - ordered[low]) * (point - low)
    )


def _cell(
    denominator: set[str],
    s1: Mapping[int, set[str]],
    s2: set[str],
    s3: set[str],
) -> dict[str, object]:
    if not all(values <= denominator for values in [*s1.values(), s2, s3]):
        raise T094Incomplete("stage ownership escapes the accepted source ledger")

    def coverage(values: set[str]) -> dict[str, float | int]:
        return {
            "contributing_start_count": len(values),
            "fraction": len(values) / len(denominator) if denominator else 0.0,
        }

    stages = [s1[1], s1[2], s1[4], s2, s3]
    transition_names = (
        "s1_n_min_1_to_2",
        "s1_n_min_2_to_4",
        "s1_n_min_4_to_s2",
        "s2_to_s3",
    )
    losses: dict[str, dict[str, float | int]] = {}
    for name, before, after in zip(transition_names, stages, stages[1:]):
        if not after <= before:
            raise T094Incomplete("later audit stage gains source ownership")
        loss = len(before) - len(after)
        losses[name] = {
            "absolute_start_loss": loss,
            "fraction_of_prior_stage": loss / len(before) if before else 0.0,
            "fraction_of_denominator": loss / len(denominator) if denominator else 0.0,
        }
    return {
        "source_start_denominator": len(denominator),
        "s1_pre_dedup": {str(n_min): coverage(s1[n_min]) for n_min in T094_N_MINS},
        "s2_after_cross_split_exclusion_n_min_4": coverage(s2),
        "s3_final_t093_canonical_n_min_4": coverage(s3),
        "start_loss": losses,
    }


def _terminal_classification(a_all: Mapping[str, object]) -> tuple[str, str]:
    s1 = a_all["s1_pre_dedup"]
    assert isinstance(s1, Mapping)
    s1_one = int(dict(s1["1"])["contributing_start_count"])
    s1_four = int(dict(s1["4"])["contributing_start_count"])
    s3 = int(dict(a_all["s3_final_t093_canonical_n_min_4"])["contributing_start_count"])
    if s1_one < T094_A_DIAGNOSTIC_MINIMUM:
        return (
            "A_COHORT_LOW_SUPERVISION_BEFORE_SUPPORT_THRESHOLD",
            "Treat A as a separately specified hard/stress transfer or downstream Battle population; do not tune T093 or lower its frozen threshold.",
        )
    if s1_four < T094_A_DIAGNOSTIC_MINIMUM:
        return (
            "A_COHORT_VISIT_SUPPORT_LIMITING",
            "Consider a separate supervision-reliability or teacher/data-generation task; T094 does not authorize T093 training at n_min=1 or 2.",
        )
    if s3 < T094_A_DIAGNOSTIC_MINIMUM:
        return (
            "A_COHORT_CANONICALIZATION_LIMITING",
            "Inspect a future leakage-safe split/fingerprint/canonical-ownership redesign without weakening public-information or leakage firewalls.",
        )
    raise T094Incomplete(
        "A attrition does not enter a preregistered T094 successor route"
    )


def _audit_records(
    *,
    artifacts: Sequence[Mapping[str, object]],
    ledger: Mapping[str, Mapping[str, object]],
    load_record: Callable[[Mapping[str, object]], Mapping[str, object]],
    spill_directory: Path,
) -> dict[str, object]:
    """Audit validated record loaders with a temporary T093-equivalent index.

    This seam keeps fixture tests small while production still supplies only
    hash-verified accepted artifact records.
    """

    _validate_ledger(ledger)
    by_source = {source: _empty_start_sets() for source in ledger}
    with tempfile.NamedTemporaryFile(
        prefix="t094-attrition-", suffix=".sqlite3", dir=spill_directory, delete=False
    ) as temporary:
        database_path = Path(temporary.name)
    connection = sqlite3.connect(database_path)
    try:
        connection.executescript(
            "PRAGMA journal_mode=OFF; PRAGMA synchronous=OFF; PRAGMA temp_store=FILE;"
            "CREATE TABLE fingerprint (fingerprint TEXT PRIMARY KEY, split TEXT NOT NULL, collision INTEGER NOT NULL, ordering TEXT, source_identity TEXT, source_group TEXT);"
            "CREATE TABLE source_fingerprint (source_identity TEXT NOT NULL, fingerprint TEXT NOT NULL, PRIMARY KEY (source_identity, fingerprint));"
        )
        seen_sources: set[str] = set()
        for artifact in artifacts:
            record = load_record(artifact)
            source = (
                record.get("source_identity") if isinstance(record, Mapping) else None
            )
            expected = ledger.get(source) if isinstance(source, str) else None
            if expected is None or source in seen_sources:
                raise T094Incomplete(
                    "retained source record provenance is unavailable or duplicated"
                )
            try:
                validate_t093_source_record(
                    record, artifact=artifact, expected_source=expected
                )
            except T093Error as error:
                raise T094Incomplete(
                    "retained source record does not match accepted T092 provenance"
                ) from error
            seen_sources.add(source)
            candidates: list[tuple[str, str]] = []
            for raw in record["internal_occurrences"]:
                if not isinstance(raw, Mapping):
                    raise T094Incomplete("retained internal occurrence is malformed")
                try:
                    occurrence = validate_retained_occurrence(raw)
                except ValueError as error:
                    raise T094Incomplete(
                        "retained internal occurrence violates the accepted public boundary"
                    ) from error
                if (
                    occurrence.source_identity != source
                    or occurrence.source_group != expected["source_group"]
                    or occurrence.split != expected["split"]
                ):
                    raise T094Incomplete(
                        "retained occurrence ownership differs from its accepted source"
                    )
                for n_min in T094_N_MINS:
                    if _pair_bearing(occurrence, n_min):
                        by_source[source][n_min].add(source)
                if not _pair_bearing(occurrence, 4):
                    continue
                fingerprint = occurrence.fingerprint
                candidates.append((source, fingerprint))
                ordering = _canonical(
                    [
                        source,
                        occurrence.parent_root_decision_identity,
                        occurrence.occurrence_identity,
                    ]
                )
                prior = connection.execute(
                    "SELECT split, collision, ordering FROM fingerprint WHERE fingerprint = ?",
                    (fingerprint,),
                ).fetchone()
                if prior is None:
                    connection.execute(
                        "INSERT INTO fingerprint VALUES (?, ?, 0, ?, ?, ?)",
                        (
                            fingerprint,
                            occurrence.split,
                            ordering,
                            source,
                            occurrence.source_group,
                        ),
                    )
                elif prior[1]:
                    pass
                elif prior[0] != occurrence.split:
                    connection.execute(
                        "UPDATE fingerprint SET collision = 1, ordering = NULL, source_identity = NULL, source_group = NULL WHERE fingerprint = ?",
                        (fingerprint,),
                    )
                elif ordering < prior[2]:
                    connection.execute(
                        "UPDATE fingerprint SET ordering = ?, source_identity = ?, source_group = ? WHERE fingerprint = ?",
                        (ordering, source, occurrence.source_group, fingerprint),
                    )
            connection.executemany(
                "INSERT OR IGNORE INTO source_fingerprint VALUES (?, ?)", candidates
            )
        if seen_sources != set(ledger):
            raise T094Incomplete(
                "not every accepted T092 source record was processed exactly once"
            )
        connection.commit()
        s2_sources = {
            source
            for (source,) in connection.execute(
                "SELECT DISTINCT source_fingerprint.source_identity FROM source_fingerprint "
                "JOIN fingerprint USING (fingerprint) WHERE fingerprint.collision = 0"
            )
        }
        s3_sources: dict[str, set[str]] = {split: set() for split in T094_SPLITS}
        s3_counts: dict[str, int] = {split: 0 for split in T094_SPLITS}
        s3_starts: dict[str, dict[str, set[str]]] = {
            split: {group: set() for group in T094_SOURCE_GROUPS}
            for split in T094_SPLITS
        }
        pair_counts: dict[str, Counter[str]] = {
            group: Counter() for group in T094_SOURCE_GROUPS
        }
        for split, source, group in connection.execute(
            "SELECT split, source_identity, source_group FROM fingerprint WHERE collision = 0"
        ):
            if (
                split not in s3_sources
                or not isinstance(source, str)
                or group not in T094_SOURCE_GROUPS
            ):
                raise T094Incomplete("T093 canonical index has invalid ownership")
            s3_counts[split] += 1
            s3_sources[split].add(source)
            s3_starts[split][group].add(source)
            pair_counts[group][source] += 1
        if (
            s3_counts != T094_EXPECTED_S3_FINGERPRINTS
            or {
                split: {
                    group: len(s3_starts[split][group]) for group in T094_SOURCE_GROUPS
                }
                for split in T094_SPLITS
            }
            != T094_EXPECTED_S3_STARTS
        ):
            raise T094Incomplete(
                "T094 n_min=4 canonicalization does not reproduce accepted T093 S3"
            )
        denominator: dict[str, dict[str, set[str]]] = {
            split: {group: set() for group in T094_SOURCE_GROUPS}
            for split in (*T094_SPLITS, "all")
        }
        for source, row in ledger.items():
            split, group = str(row["split"]), str(row["source_group"])
            denominator[split][group].add(source)
            denominator["all"][group].add(source)
        report_cells: dict[str, dict[str, dict[str, object]]] = {}
        all_s3 = set().union(*s3_sources.values())
        for scope in (*T094_SPLITS, "all"):
            report_cells[scope] = {}
            for group in T094_SOURCE_GROUPS:
                eligible = denominator[scope][group]
                s1 = {
                    n_min: {
                        source
                        for source in eligible
                        if source in by_source and by_source[source][n_min]
                    }
                    for n_min in T094_N_MINS
                }
                s2 = eligible & s2_sources
                s3 = eligible & (all_s3 if scope == "all" else s3_sources[scope])
                report_cells[scope][group] = _cell(eligible, s1, s2, s3)
        concentration: dict[str, dict[str, object]] = {}
        for group in T094_SOURCE_GROUPS:
            values = list(pair_counts[group].values())
            top_count = math.ceil(len(values) * 0.1)
            top_examples = (
                sum(sorted(values, reverse=True)[:top_count]) if top_count else 0
            )
            total_examples = sum(values)
            concentration[group] = {
                "contributing_start_count": len(values),
                "median_canonical_pair_bearing_fingerprints_per_contributing_start": _percentile(
                    values, 0.5
                ),
                "p90_canonical_pair_bearing_fingerprints_per_contributing_start": _percentile(
                    values, 0.9
                ),
                "maximum_canonical_pair_bearing_fingerprints_per_contributing_start": max(
                    values
                )
                if values
                else None,
                "top_10_percent_contributing_starts": top_count,
                "fraction_of_group_examples_from_top_10_percent_contributing_starts": top_examples
                / total_examples
                if total_examples
                else 0.0,
            }
        terminal, recommendation = _terminal_classification(report_cells["all"]["A"])
        return {
            "schema_id": T094_REPORT_SCHEMA_ID,
            "schema_version": 1,
            "task_id": T094_TASK_ID,
            "terminal_classification": terminal,
            "successor_recommendation": recommendation,
            "claim_boundary": "source-start attrition only; no student learnability, teacher correctness, Search improvement, or controller claim",
            "audit_definition": {
                "candidate_boundary": "accepted T092 depth>=1 stable public state with teacher-searchable actions",
                "pair_bearing": "at least one non-tie unordered supported-action comparison",
                "pair_tolerance": T094_PAIR_TOLERANCE,
                "support_thresholds": list(T094_N_MINS),
                "cross_split_rule": "exclude every n_min=4 candidate fingerprint observed in more than one inherited split",
                "canonical_rule": "minimum (source_identity, parent_root_decision_identity, occurrence_identity) within one inherited split",
            },
            "reproduction": {
                "passed": True,
                "source_group_counts": dict(T094_SOURCE_GROUP_COUNTS),
                "s3_canonical_fingerprint_counts": s3_counts,
                "s3_contributing_source_starts": {
                    split: {
                        group: len(s3_starts[split][group])
                        for group in T094_SOURCE_GROUPS
                    }
                    for split in T094_SPLITS
                },
            },
            "coverage_by_split_and_group": report_cells,
            "s3_concentration_by_source_group": concentration,
            "resource_topology": {
                "source_record_processing": "one accepted source record at a time",
                "canonicalization_store": "temporary sqlite spill index",
                "simulator_or_search_invocation": False,
            },
        }
    finally:
        connection.close()
        database_path.unlink(missing_ok=True)


def audit_t094_from_paths(
    *,
    t092_retention_manifest_path: str | Path,
    t092_evidence_path: str | Path,
    t093_retention_manifest_path: str | Path,
    t093_corpus_path: str | Path,
    spill_directory: str | Path | None = None,
) -> dict[str, object]:
    """Validate exact artifacts and calculate the three-stage audit report."""

    try:
        t092_retention_path = Path(t092_retention_manifest_path).resolve(strict=True)
        t092_evidence_path = Path(t092_evidence_path).resolve(strict=True)
        t093_retention_path = Path(t093_retention_manifest_path).resolve(strict=True)
        corpus_path = Path(t093_corpus_path).resolve(strict=True)
    except OSError as error:
        raise T094Incomplete(
            "a required accepted T092/T093 input path is unavailable"
        ) from error
    retention = _read_json_bound(
        t092_retention_path, T093_EXACT_T092_RETENTION_SHA256, "T092 retention manifest"
    )
    evidence = _read_json_bound(
        t092_evidence_path, T093_EXACT_T092_EVIDENCE_SHA256, "T092 formal evidence"
    )
    t093_retention = _read_json_bound(
        t093_retention_path, T094_EXACT_T093_RETENTION_SHA256, "T093 retention manifest"
    )
    try:
        artifacts, ledger = _validate_t093_inputs(retention, evidence)
    except T093Error as error:
        raise T094Incomplete(
            "accepted T092 artifact inventory/evidence is invalid"
        ) from error
    corpus_identity = _validate_t093_retention(
        t093_retention, corpus_path=corpus_path, artifacts=artifacts
    )

    def load_record(artifact: Mapping[str, object]) -> Mapping[str, object]:
        raw_path = artifact.get("path")
        if not isinstance(raw_path, str):
            raise T094Incomplete("T092 source artifact lacks a path")
        path = Path(raw_path).resolve(strict=True)
        actual_sha256, size = _sha256_file(path)
        if (
            actual_sha256 != artifact.get("sha256")
            or size != artifact.get("size_bytes")
            or artifact.get("schema_id") != "t092-paired-canary-arm-record-v2"
        ):
            raise T094Incomplete(
                "T092 source artifact is not the accepted retained byte stream"
            )
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise T094Incomplete("T092 source artifact is unreadable JSON") from error
        if not isinstance(record, Mapping):
            raise T094Incomplete("T092 source artifact is not a JSON object")
        return record

    spill_path = (
        Path(tempfile.gettempdir())
        if spill_directory is None
        else Path(spill_directory).resolve()
    )
    spill_path.mkdir(parents=True, exist_ok=True)
    report = _audit_records(
        artifacts=artifacts,
        ledger=ledger,
        load_record=load_record,
        spill_directory=spill_path,
    )
    report["input_identities"] = {
        "t092_formal_evidence": {
            "path": str(t092_evidence_path),
            "sha256": T093_EXACT_T092_EVIDENCE_SHA256,
        },
        "t092_retention_manifest": {
            "path": str(t092_retention_path),
            "sha256": T093_EXACT_T092_RETENTION_SHA256,
        },
        "t093_retention_manifest": {
            "path": str(t093_retention_path),
            "sha256": T094_EXACT_T093_RETENTION_SHA256,
        },
        "t093_derived_corpus": corpus_identity,
    }
    return report


def write_t094_artifacts(
    *,
    t092_retention_manifest_path: str | Path,
    t092_evidence_path: str | Path,
    t093_retention_manifest_path: str | Path,
    t093_corpus_path: str | Path,
    output_dir: str | Path,
) -> dict[str, object]:
    """Write a compact report and lightweight retention manifest outside Git."""

    destination = Path(output_dir).resolve()
    destination.mkdir(parents=True, exist_ok=True)
    report_path = destination / "t094-a-cohort-attrition-report.json"
    try:
        report = audit_t094_from_paths(
            t092_retention_manifest_path=t092_retention_manifest_path,
            t092_evidence_path=t092_evidence_path,
            t093_retention_manifest_path=t093_retention_manifest_path,
            t093_corpus_path=t093_corpus_path,
            spill_directory=destination,
        )
    except T094Incomplete as error:
        report = {
            "schema_id": T094_REPORT_SCHEMA_ID,
            "schema_version": 1,
            "task_id": T094_TASK_ID,
            "terminal_classification": "INCOMPLETE",
            "successor_recommendation": None,
            "incomplete_reason": str(error),
            "claim_boundary": "no route interpretation is allowed because required accepted facts did not validate",
        }
    report_path.write_text(
        json.dumps(report, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )
    report_sha256, report_size = _sha256_file(report_path)
    manifest = {
        "schema_id": T094_RETENTION_SCHEMA_ID,
        "schema_version": 1,
        "task_id": T094_TASK_ID,
        "report": {
            "path": str(report_path),
            "sha256": report_sha256,
            "size_bytes": report_size,
            "schema_id": T094_REPORT_SCHEMA_ID,
        },
        "regeneration_command": "python -m sts_combat_rl.commands.t094_a_cohort_attrition --t092-retention-manifest <accepted-t092-retention> --t092-formal-evidence <accepted-t092-evidence> --t093-retention-manifest <accepted-t093-retention> --t093-corpus <accepted-t093-corpus> --output-dir <ignored-local-t094-output>",
        "retention_reason": "T094 exact-artifact source-start attrition decision audit",
    }
    (destination / "t094-retention-manifest.json").write_text(
        json.dumps(manifest, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )
    return report
