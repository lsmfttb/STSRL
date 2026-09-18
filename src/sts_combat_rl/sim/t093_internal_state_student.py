"""Fail-closed, offline T093 materialization and evaluation primitives.

T093 consumes retained T092 records only.  In particular this module has no
simulator import or Search call: ``mean_value`` and ``visits`` are labels and
admission facts, while the scorer receives only public-tactical-v2 encodings.
"""

from __future__ import annotations

import hashlib
import json
import math
import random
import sqlite3
import statistics
import tempfile
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from sts_combat_rl.sim.contract import SimulatorAction
from sts_combat_rl.sim.features import encode_lightspeed_battle_snapshot, encode_simulator_actions
from sts_combat_rl.sim.t090_battle_student import canonical_sha256
from sts_combat_rl.sim.t092_internal_search_state import (
    T092_FROZEN_TEACHER_CONFIG,
    T092_NATIVE_API,
    T092_NATIVE_IDENTITY,
    validate_retained_occurrence,
)

T093_TASK_ID = "T093"
T093_N_MIN = 4
T093_PAIR_TOLERANCE = 1e-9
T093_MODEL_SEEDS = (930093, 930094, 930095)
T093_BOOTSTRAP_SEED = 930293
T093_BOOTSTRAP_REPLICATES = 20_000
T093_LABEL_DOMAIN = "T093-LABEL-DESTRUCTION-V1"
T093_MATERIALIZATION_SCHEMA_ID = "t093-internal-partial-ranking-corpus-v1"
T093_CONFIG_SCHEMA_ID = "t093-internal-state-student-config-v1"
T093_REPORT_SCHEMA_ID = "t093-internal-state-student-report-v1"
T093_CHECKPOINT_SCHEMA_ID = "t093-public-action-scorer-checkpoint-v1"
T093_RETENTION_SCHEMA_ID = "t093-internal-state-student-retention-manifest-v1"
T093_SOURCE_GROUPS = ("A", "B", "C")
T093_SPLITS = ("train", "validation", "heldout")
T093_EXACT_T092_EVIDENCE_SHA256 = (
    "ac6d03ccce403c3474a75221e547a6058d5b7f419af7d8df9ddd8dbb225c562a"
)
T093_EXACT_T092_RETENTION_SHA256 = (
    "32f4b04f31c91cf58928503d51023ba53c98f310bcb96644503040b2fd9d18b7"
)
T093_MIN_FINGERPRINTS = {"train": 10_000, "validation": 2_000, "heldout": 3_000}
T093_MIN_CONTRIBUTING_STARTS = {
    "train": {"A": 44, "B": 90, "C": 60},
    "validation": {"A": 11, "B": 23, "C": 15},
    "heldout": {"A": 16, "B": 33, "C": 22},
}
T093_ACCEPTED_T092_IMPLEMENTATION_HEAD = "1e3dff2665d38dfd6acc786666c1889bc8327508"
T093_T092_SOURCE_RECORD_SCHEMA_ID = "t092-paired-canary-arm-record-v2"


class T093Error(ValueError):
    """A retained-artifact, public-boundary, or gate violation."""


def _canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def t093_checkpoint_identity(
    state_dict: Mapping[str, object], *, config: T093TrainingConfig,
    arm: str, seed: int, selected_epoch: int,
) -> dict[str, object]:
    """Stable selected-checkpoint identity; serialization remains external/Git-ignored."""

    if arm not in {"true", "label_destruction", "state_ablated"} or seed not in T093_MODEL_SEEDS or selected_epoch not in range(1, 31):
        raise T093Error("checkpoint identity has invalid frozen arm/seed/epoch")
    digest = hashlib.sha256()
    for key in sorted(state_dict):
        value = state_dict[key]
        digest.update(key.encode()); digest.update(b"\0")
        if hasattr(value, "detach"):
            value = value.detach().cpu().contiguous().numpy().tobytes()
        if isinstance(value, bytes):
            digest.update(value)
        else:
            digest.update(_canonical(value).encode())
    return {"schema_id": T093_CHECKPOINT_SCHEMA_ID, "task_id": T093_TASK_ID,
            "arm": arm, "seed": seed, "selected_epoch": selected_epoch,
            "training_config_sha256": canonical_sha256(config.to_dict()),
            "state_dict_sha256": digest.hexdigest(), "external_checkpoint_required": True,
            "retention": "write serialized checkpoint outside Git and bind its file identity before scientific evaluation"}


def _finite(value: object, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        raise T093Error(f"{label} must be finite")
    return float(value)


def _percentile(values: Sequence[float], quantile: float) -> float:
    ordered = sorted(values)
    if not ordered:
        raise T093Error("cannot calculate percentile of no values")
    point = (len(ordered) - 1) * quantile
    low, high = math.floor(point), math.ceil(point)
    return ordered[low] if low == high else ordered[low] + (ordered[high] - ordered[low]) * (point - low)


@dataclass(frozen=True)
class T093Example:
    source_identity: str
    source_group: str
    split: str
    parent_root_decision_identity: str
    occurrence_identity: str
    public_fingerprint: str
    tree_depth: int
    state_features: tuple[float, ...]
    action_features: tuple[tuple[float, ...], ...]
    action_identities: tuple[Mapping[str, object], ...]
    action_kinds: tuple[str, ...]
    teacher_means: tuple[float, ...]

    @property
    def pairs(self) -> tuple[tuple[int, int], ...]:
        rows: list[tuple[int, int]] = []
        for left in range(len(self.teacher_means)):
            for right in range(left + 1, len(self.teacher_means)):
                delta = self.teacher_means[left] - self.teacher_means[right]
                if abs(delta) > T093_PAIR_TOLERANCE:
                    rows.append((left, right) if delta > 0 else (right, left))
        return tuple(rows)


def _public_action(action: Mapping[str, object]) -> SimulatorAction:
    # ``bits`` is intentionally omitted: it is a simulator-native field, not
    # a public student feature. T092 separately established idx parameters as
    # part of its public action identity boundary.
    required = {"scope", "bits", "kind", "idx1", "idx2", "idx3", "label"}
    if set(action) != required or action.get("scope") != "battle":
        raise T093Error("T092 searchable action is not the registered public shape")
    raw = {key: action[key] for key in ("scope", "idx1", "idx2", "idx3")}
    if not all(isinstance(raw[key], int) and not isinstance(raw[key], bool) for key in ("idx1", "idx2", "idx3")):
        raise T093Error("T092 public action parameters are invalid")
    public_identity = _public_action_identity(action)
    return SimulatorAction(
        action_id=canonical_sha256(public_identity),
        label=str(action["label"]), kind=str(action["kind"]), raw=raw,
    )


def _public_action_identity(action: Mapping[str, object]) -> dict[str, object]:
    """Return the entire persisted student-side action surface.

    Native ``bits`` identifies an internal replay action and must not influence
    either the public encoding or an action identity hash.
    """

    return {
        "scope": str(action["scope"]),
        "kind": str(action["kind"]),
        "label": str(action["label"]),
        "parameters": {key: int(action[key]) for key in ("idx1", "idx2", "idx3")},
    }


def example_from_t092_occurrence(value: Mapping[str, object]) -> T093Example | None:
    """Turn one validated T092 row into the n_min=4 public-only example."""

    occurrence = validate_retained_occurrence(value)
    if occurrence.tree_depth < 1:
        raise T093Error("T093 admits only T092 depth>=1 occurrences")
    supported = [
        row for row in occurrence.searchable_actions
        if int(row["visits"]) >= T093_N_MIN and row["mean_value"] is not None
    ]
    if len(supported) < 2:
        return None
    actions = [_public_action(dict(row["action"])) for row in supported]
    state = tuple(float(item) for item in encode_lightspeed_battle_snapshot(occurrence.public_battle_projection))
    action_features = tuple(
        tuple(float(item) for item in row)
        for row in encode_simulator_actions(actions, occurrence.public_battle_projection)
    )
    means = tuple(_finite(row["mean_value"], "T092 teacher mean") for row in supported)
    result = T093Example(
        occurrence.source_identity, occurrence.source_group, occurrence.split,
        occurrence.parent_root_decision_identity, occurrence.occurrence_identity,
        occurrence.fingerprint, occurrence.tree_depth, state, action_features,
        tuple(_public_action_identity(row["action"]) for row in supported),
        tuple(str(row["action"]["kind"]) for row in supported), means,
    )
    return result if result.pairs else None


def _canonicalize(examples: Sequence[T093Example]) -> tuple[list[T093Example], dict[str, object]]:
    grouped: dict[str, list[T093Example]] = defaultdict(list)
    for example in examples:
        grouped[example.public_fingerprint].append(example)
    retained: list[T093Example] = []
    collisions: list[dict[str, object]] = []
    duplicates: list[dict[str, object]] = []
    for fingerprint, rows in grouped.items():
        splits = sorted({row.split for row in rows})
        if len(splits) > 1:
            collisions.append({"public_fingerprint": fingerprint, "splits": splits, "source_identities": sorted({r.source_identity for r in rows})})
            continue
        chosen = min(rows, key=lambda row: (row.source_identity, row.parent_root_decision_identity, row.occurrence_identity))
        retained.append(chosen)
        if len(rows) > 1:
            duplicates.append({"public_fingerprint": fingerprint, "split": chosen.split, "canonical_occurrence": chosen.occurrence_identity, "multiplicity": len(rows)})
    retained.sort(key=lambda row: (row.split, row.source_group, row.source_identity, row.parent_root_decision_identity, row.occurrence_identity))
    return retained, {"cross_split_excluded": collisions, "within_split_deduplicated": duplicates}


def _sha256_file(path: Path) -> tuple[str, int]:
    digest, size = hashlib.sha256(), 0
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
            size += len(block)
    return digest.hexdigest(), size


def _read_bound_json(path: Path, expected_sha: str, label: str) -> dict[str, object]:
    digest, _ = _sha256_file(path)
    if digest != expected_sha:
        raise T093Error(f"{label} is not the accepted T092 artifact")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise T093Error(f"{label} must be a JSON object")
    return value


def _validate_t093_inputs(
    retention_manifest: Mapping[str, object], evidence: Mapping[str, object]
) -> tuple[list[Mapping[str, object]], dict[str, Mapping[str, object]]]:
    if (
        retention_manifest.get("schema_id") != "t092-formal-retention-manifest-v1"
        or evidence.get("schema_id") != "t092-formal-telemetry-evidence-v1"
        or evidence.get("terminal_classification")
        != "INTERNAL_SEARCH_SURFACE_DENSE_ENOUGH"
    ):
        raise T093Error("T092 accepted evidence/retention schema is invalid")
    bound = retention_manifest.get("formal_evidence")
    shards = retention_manifest.get("source_shards")
    ledger = evidence.get("source_worker_ledger")
    if (
        not isinstance(bound, Mapping)
        or bound.get("sha256") != T093_EXACT_T092_EVIDENCE_SHA256
        or not isinstance(shards, list)
        or not isinstance(ledger, list)
        or evidence.get("internal_shard_manifest") != shards
        or len(ledger) != 413
        or sum(shard.get("record_count", -1) for shard in shards if isinstance(shard, Mapping)) != 413
    ):
        raise T093Error("T092 corpus does not bind the exact 413-start retention set")
    by_source: dict[str, Mapping[str, object]] = {}
    for row in ledger:
        if not isinstance(row, Mapping) or not isinstance(row.get("source_identity"), str):
            raise T093Error("T092 evidence source ledger is malformed")
        source = str(row["source_identity"])
        if source in by_source or row.get("source_group") not in T093_SOURCE_GROUPS or row.get("split") not in T093_SPLITS:
            raise T093Error("T092 evidence source ownership is invalid")
        by_source[source] = row
    if len(by_source) != 413:
        raise T093Error("T092 evidence does not own exactly 413 source starts")
    artifacts: list[Mapping[str, object]] = []
    paths: set[str] = set()
    for shard in shards:
        if not isinstance(shard, Mapping) or not isinstance(shard.get("source_artifacts"), list):
            raise T093Error("T092 retention shard is malformed")
        rows = shard["source_artifacts"]
        if shard.get("record_count") != len(rows) or shard.get("source_artifacts_sha256") != canonical_sha256(rows):
            raise T093Error("T092 retention shard count/hash is invalid")
        for artifact in rows:
            if not isinstance(artifact, Mapping) or not isinstance(artifact.get("path"), str):
                raise T093Error("T092 retained source artifact is malformed")
            path = str(Path(str(artifact["path"])).resolve())
            if path in paths:
                raise T093Error("T092 retention source artifact is aliased")
            paths.add(path)
            artifacts.append(artifact)
    if len(artifacts) != 413:
        raise T093Error("T092 retention manifest does not contain all 413 source records")
    return artifacts, by_source


def validate_t093_source_record(
    record: Mapping[str, object], *, artifact: Mapping[str, object],
    expected_source: Mapping[str, object],
) -> None:
    """Check T092 internal consistency in addition to retention file hashes."""

    if (
        record.get("schema_id") != T093_T092_SOURCE_RECORD_SCHEMA_ID
        or record.get("schema_version") != 1
        or record.get("task_id") != "T092"
        or record.get("arm") != "ON"
        or record.get("implementation_head") != T093_ACCEPTED_T092_IMPLEMENTATION_HEAD
        or record.get("native_identity") != T092_NATIVE_IDENTITY
        or record.get("native_api") != T092_NATIVE_API
        or record.get("teacher_config") != T092_FROZEN_TEACHER_CONFIG
        or record.get("schema_id") != artifact.get("schema_id")
        or record.get("source_identity") != expected_source.get("source_identity")
        or record.get("source_group") != expected_source.get("source_group")
        or record.get("split") != expected_source.get("split")
        or record.get("canonical_position") != expected_source.get("canonical_position")
        or not isinstance(record.get("decision_records"), list)
        or not isinstance(expected_source.get("terminal"), Mapping)
        or len(record["decision_records"])
        != expected_source["terminal"].get("battle_decision_count")
        or not isinstance(record.get("internal_occurrences"), list)
    ):
        raise T093Error("retained source record provenance mismatches accepted T092")


def materialize_t093_from_paths(
    *, retention_manifest_path: str | Path, formal_evidence_path: str | Path,
    output_path: str | Path,
) -> dict[str, object]:
    """Stream the exact retained 413-record corpus through a SQLite spill store.

    This is the only scientific materialization API.  It verifies bound file
    bytes before decoding each source record, processes one record at a time,
    and keeps only canonical fingerprints in the spill database.
    """

    retention_path = Path(retention_manifest_path).resolve(strict=True)
    evidence_path = Path(formal_evidence_path).resolve(strict=True)
    retention = _read_bound_json(
        retention_path, T093_EXACT_T092_RETENTION_SHA256, "retention manifest"
    )
    evidence = _read_bound_json(
        evidence_path, T093_EXACT_T092_EVIDENCE_SHA256, "formal evidence"
    )
    artifacts, ledger = _validate_t093_inputs(retention, evidence)
    destination = Path(output_path).resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        prefix="t093-materialization-", suffix=".sqlite3", dir=destination.parent,
        delete=False,
    ) as temporary:
        database_path = Path(temporary.name)
    connection = sqlite3.connect(database_path)
    raw_pair_bearing, processed_records = 0, 0
    try:
        connection.execute(
            "CREATE TABLE candidate (fingerprint TEXT PRIMARY KEY, split TEXT NOT NULL, "
            "collision INTEGER NOT NULL, ordering TEXT, payload TEXT)"
        )
        seen_sources: set[str] = set()
        for artifact in artifacts:
            path = Path(str(artifact["path"])).resolve(strict=True)
            digest, size = _sha256_file(path)
            if (
                digest != artifact.get("sha256")
                or size != artifact.get("size_bytes")
                or artifact.get("schema_id") != "t092-paired-canary-arm-record-v2"
            ):
                raise T093Error("retained source record hash/size/schema mismatches")
            record = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(record, Mapping):
                raise T093Error("retained source record is malformed")
            source = record.get("source_identity")
            expected = ledger.get(source) if isinstance(source, str) else None
            if (
                expected is None
                or source in seen_sources
            ):
                raise T093Error("retained source record provenance mismatches evidence")
            validate_t093_source_record(
                record, artifact=artifact, expected_source=expected
            )
            seen_sources.add(source)
            processed_records += 1
            for occurrence in record["internal_occurrences"]:
                if not isinstance(occurrence, Mapping):
                    raise T093Error("retained internal occurrence is malformed")
                if (
                    occurrence.get("source_identity") != source
                    or occurrence.get("source_group") != expected.get("source_group")
                    or occurrence.get("split") != expected.get("split")
                ):
                    raise T093Error("internal occurrence source ownership mismatches record")
                example = example_from_t092_occurrence(occurrence)
                if example is None:
                    continue
                raw_pair_bearing += 1
                ordering = _canonical(
                    [example.source_identity, example.parent_root_decision_identity, example.occurrence_identity]
                )
                payload = _canonical(asdict(example))
                prior = connection.execute(
                    "SELECT split, collision, ordering FROM candidate WHERE fingerprint = ?",
                    (example.public_fingerprint,),
                ).fetchone()
                if prior is None:
                    connection.execute(
                        "INSERT INTO candidate VALUES (?, ?, 0, ?, ?)",
                        (example.public_fingerprint, example.split, ordering, payload),
                    )
                elif prior[1]:
                    continue
                elif prior[0] != example.split:
                    connection.execute(
                        "UPDATE candidate SET collision = 1, ordering = NULL, payload = NULL "
                        "WHERE fingerprint = ?", (example.public_fingerprint,)
                    )
                elif ordering < prior[2]:
                    connection.execute(
                        "UPDATE candidate SET ordering = ?, payload = ? WHERE fingerprint = ?",
                        (ordering, payload, example.public_fingerprint),
                    )
            del record
        if set(seen_sources) != set(ledger) or processed_records != 413:
            raise T093Error("T093 did not process the complete exact source set")
        connection.commit()
        split_counts = {
            split: connection.execute(
                "SELECT COUNT(*) FROM candidate WHERE collision = 0 AND split = ?", (split,)
            ).fetchone()[0]
            for split in T093_SPLITS
        }
        source_counts = {
            split: {
                group: connection.execute(
                    "SELECT COUNT(DISTINCT json_extract(payload, '$.source_identity')) "
                    "FROM candidate WHERE collision = 0 AND split = ? "
                    "AND json_extract(payload, '$.source_group') = ?", (split, group),
                ).fetchone()[0]
                for group in T093_SOURCE_GROUPS
            }
            for split in T093_SPLITS
        }
        diversity = {
            "canonical_pair_bearing_fingerprints": split_counts,
            "contributing_source_starts": source_counts,
            "required_minima": {
                "fingerprints": dict(T093_MIN_FINGERPRINTS),
                "source_starts": T093_MIN_CONTRIBUTING_STARTS,
            },
            "passed": all(split_counts[s] >= T093_MIN_FINGERPRINTS[s] for s in T093_SPLITS)
            and all(source_counts[s][g] >= T093_MIN_CONTRIBUTING_STARTS[s][g] for s in T093_SPLITS for g in T093_SOURCE_GROUPS),
        }
        deduplication = {
            "cross_split_excluded_count": connection.execute(
                "SELECT COUNT(*) FROM candidate WHERE collision = 1"
            ).fetchone()[0],
            "raw_candidate_discard_count": raw_pair_bearing - sum(split_counts.values()),
        }
        report = {
            "schema_id": T093_MATERIALIZATION_SCHEMA_ID, "schema_version": 1,
            "task_id": T093_TASK_ID, "primary_n_min": T093_N_MIN,
            "pair_tolerance": T093_PAIR_TOLERANCE,
            "t092_evidence_sha256": T093_EXACT_T092_EVIDENCE_SHA256,
            "t092_retention_manifest_sha256": T093_EXACT_T092_RETENTION_SHA256,
            "t092_native_identity": dict(T092_NATIVE_IDENTITY),
            "teacher_config": dict(T092_FROZEN_TEACHER_CONFIG),
            "raw_pair_bearing_occurrence_count": raw_pair_bearing,
            "deduplication": deduplication, "effective_diversity": diversity,
            "resource_topology": {
                "source_record_count": processed_records,
                "materialization_workers": 1,
                "processing_mode": "one_hash_verified_source_record_then_one_occurrence",
                "canonicalization_store": "sqlite_temp_spill",
                "max_retained_python_source_records": 1,
                "spill_database_retained": False,
                "spill_database_cleanup": "removed after output serialization",
            },
        }
        with destination.open("w", encoding="utf-8") as stream:
            stream.write("{")
            for index, key in enumerate(sorted(report)):
                if index:
                    stream.write(",")
                stream.write(json.dumps(key)); stream.write(":")
                json.dump(report[key], stream, sort_keys=True)
            stream.write(',"examples":[')
            cursor = connection.execute(
                "SELECT payload FROM candidate WHERE collision = 0 ORDER BY split, "
                "json_extract(payload, '$.source_group'), json_extract(payload, '$.source_identity'), ordering"
            )
            for index, (payload,) in enumerate(cursor):
                if index:
                    stream.write(",")
                stream.write(payload)
            stream.write("]}\n")
        output_sha, output_size = _sha256_file(destination)
        retention_path = destination.with_name("t093-retention-manifest.json")
        retention = {
            "schema_id": T093_RETENTION_SCHEMA_ID, "schema_version": 1,
            "task_id": T093_TASK_ID,
            "derived_corpus": {"path": str(destination), "sha256": output_sha,
                               "size_bytes": output_size,
                               "schema_id": T093_MATERIALIZATION_SCHEMA_ID},
            "t092_evidence_sha256": T093_EXACT_T092_EVIDENCE_SHA256,
            "t092_retention_manifest_sha256": T093_EXACT_T092_RETENTION_SHA256,
            "source_artifact_inventory_sha256": canonical_sha256(artifacts),
            "training_config": "t093-internal-state-student-config-v1",
            "regeneration_command": "python -m sts_combat_rl.commands.t093_internal_state_student --retention-manifest <accepted-t092-retention> --formal-evidence <accepted-t092-evidence> --output <derived-corpus>",
            "retention_reason": "scientific-quality T093 materialized n_min=4 corpus",
            "resource_topology": report["resource_topology"],
        }
        retention_path.write_text(json.dumps(retention, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        report["retention_manifest"] = {"path": str(retention_path), "sha256": _sha256_file(retention_path)[0], "schema_id": T093_RETENTION_SCHEMA_ID}
        return report
    finally:
        connection.close()
        database_path.unlink(missing_ok=True)


def effective_diversity_report(examples: Sequence[T093Example]) -> dict[str, object]:
    by_split = {split: [row for row in examples if row.split == split] for split in T093_SPLITS}
    cells = {
        split: {group: len({row.source_identity for row in rows if row.source_group == group}) for group in T093_SOURCE_GROUPS}
        for split, rows in by_split.items()
    }
    passed = all(len(by_split[split]) >= T093_MIN_FINGERPRINTS[split] for split in T093_SPLITS) and all(
        cells[split][group] >= T093_MIN_CONTRIBUTING_STARTS[split][group]
        for split in T093_SPLITS for group in T093_SOURCE_GROUPS
    )
    return {
        "canonical_pair_bearing_fingerprints": {split: len(by_split[split]) for split in T093_SPLITS},
        "contributing_source_starts": cells,
        "required_minima": {"fingerprints": dict(T093_MIN_FINGERPRINTS), "source_starts": T093_MIN_CONTRIBUTING_STARTS},
        "passed": passed,
    }


def _occurrence_key(example: T093Example) -> str:
    return _canonical(
        [example.source_identity, example.parent_root_decision_identity, example.occurrence_identity]
    )


def repeated_public_state_diagnostics(
    occurrences: Sequence[Mapping[str, object]], *,
    performance_rows: Sequence[Mapping[str, object]] = (),
) -> dict[str, object]:
    """Diagnostic-only T034 ambiguity lower bounds on pre-dedup n_min=4 rows.

    Conflict/multiplicity are reporting fields only: this function never
    returns weights or model inputs, and callers must not feed them to training.
    """

    grouped: dict[str, list[T093Example]] = defaultdict(list)
    for raw in occurrences:
        if not isinstance(raw, Mapping):
            raise T093Error("ambiguity occurrence is malformed")
        example = example_from_t092_occurrence(raw)
        if example is not None:
            grouped[example.public_fingerprint].append(example)
    repeated = {key: rows for key, rows in grouped.items() if len(rows) > 1}
    conflict: set[str] = set()
    best_disagreement = 0
    pair_support, pair_conflicts = 0, 0
    pair_sign_support: dict[str, dict[str, int]] = {}
    for fingerprint, rows in repeated.items():
        best_sets = {
            tuple(sorted(_canonical(row.action_identities[index]) for index, mean in enumerate(row.teacher_means) if mean == max(row.teacher_means)))
            for row in rows
        }
        best_disagreement += int(len(best_sets) > 1)
        signs: dict[tuple[str, str], dict[int, int]] = defaultdict(lambda: defaultdict(int))
        for row in rows:
            for high, low in row.pairs:
                key = tuple(sorted((_canonical(row.action_identities[high]), _canonical(row.action_identities[low]))))
                signs[key][1 if key[0] == _canonical(row.action_identities[high]) else -1] += 1
        pair_support += len(signs)
        conflicts = sum(len(value) > 1 for value in signs.values())
        for pair, values in signs.items():
            key = _canonical([fingerprint, *pair])
            pair_sign_support[key] = {"positive": values[1], "negative": values[-1], "support_count": sum(values.values())}
        pair_conflicts += conflicts
        if conflicts:
            conflict.add(fingerprint)
    strata: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    for row in performance_rows:
        if not isinstance(row, Mapping) or not isinstance(row.get("public_fingerprint"), str) or not isinstance(row.get("arm"), str):
            raise T093Error("ambiguity performance row is malformed")
        value = _finite(row.get("source_start_macro_accuracy"), "ambiguity performance")
        category = "conflict_bearing" if row["public_fingerprint"] in conflict else "singleton_or_no_observed_conflict"
        strata[str(row["arm"])][category].append(value)
    return {
        "surface": "pre_dedup_t092_n_min_4_diagnostic_only",
        "student_input_or_weight_use": "forbidden",
        "canonical_fingerprint_count": len(grouped),
        "repeated_canonical_fingerprint_count": len(repeated),
        "repeated_canonical_fingerprint_fraction": len(repeated) / len(grouped) if grouped else 0.0,
        "best_supported_action_disagreement_count": best_disagreement,
        "best_supported_action_disagreement_fraction": best_disagreement / len(repeated) if repeated else 0.0,
        "supported_public_action_pair_count": pair_support,
        "pair_sign_conflict_count": pair_conflicts,
        "pair_sign_conflict_rate": pair_conflicts / pair_support if pair_support else 0.0,
        "pair_sign_support_by_public_pair": pair_sign_support,
        "ownership": "each row remains bound to source_identity/source_group/split; diagnostics never reassign ownership",
        "conflict_bearing_fingerprint_count": len(conflict),
        "performance_by_arm_and_stratum": {
            arm: {stratum: statistics.fmean(values) for stratum, values in values_by_stratum.items() if values}
            for arm, values_by_stratum in strata.items()
        },
    }


def secondary_stratified_report(
    examples: Sequence[T093Example], *, scores_by_arm: Mapping[str, Mapping[str, Sequence[float]]],
    split: str, seed_metrics: Mapping[str, Sequence[float]] | None = None,
) -> dict[str, object]:
    """Required descriptive metrics; none of these create a promotion gate."""

    rows = [example for example in examples if example.split == split]
    if split not in T093_SPLITS or not rows:
        raise T093Error("secondary report needs one non-empty registered split")
    result: dict[str, object] = {"split": split, "chance_reference": 0.5, "promotion_gate": False,
                                  "metric_identity": "true_n_min_4_supported_action_pairwise_source_start_macro",
                                  "arms": {}}
    for arm, score_rows in scores_by_arm.items():
        per_group: dict[str, list[float]] = defaultdict(list)
        per_depth: dict[str, list[float]] = defaultdict(list)
        per_branching: dict[str, list[float]] = defaultdict(list)
        per_kind: dict[str, list[float]] = defaultdict(list)
        per_margin: dict[str, list[float]] = defaultdict(list)
        regrets: list[float] = []; agreements: list[float] = []; accuracies: list[float] = []
        per_start: dict[str, int] = defaultdict(int)
        for example in rows:
            scores = score_rows.get(example.public_fingerprint)
            if scores is None or len(scores) != len(example.teacher_means):
                raise T093Error("secondary score rows do not align with supported actions")
            selected = max(range(len(scores)), key=lambda index: (float(scores[index]), -index))
            best = max(example.teacher_means)
            top_set = {index for index, value in enumerate(example.teacher_means) if value == best}
            accuracy = statistics.fmean(float(scores[high]) > float(scores[low]) for high, low in example.pairs)
            regret = best - example.teacher_means[selected]
            margin = max(example.teacher_means) - min(example.teacher_means)
            bucket = "0-0.01" if margin <= .01 else "0.01-0.1" if margin <= .1 else ">0.1"
            agreements.append(float(selected in top_set)); regrets.append(regret); accuracies.append(accuracy)
            per_group[example.source_group].append(accuracy); per_depth[str(example.tree_depth)].append(accuracy)
            per_branching[str(len(example.teacher_means))].append(accuracy); per_kind[example.action_kinds[selected]].append(accuracy)
            per_margin[bucket].append(accuracy); per_start[example.source_identity] += 1
        result["arms"][arm] = {
            "pairwise_ranking_accuracy": statistics.fmean(accuracies),
            "supported_action_top_set_agreement": statistics.fmean(agreements),
            "supported_action_teacher_regret": statistics.fmean(regrets),
            "source_group": {key: statistics.fmean(value) for key, value in per_group.items()},
            "depth": {key: statistics.fmean(value) for key, value in per_depth.items()},
            "supported_branching": {key: statistics.fmean(value) for key, value in per_branching.items()},
            "teacher_action_kind": {key: statistics.fmean(value) for key, value in per_kind.items()},
            "teacher_margin": {key: statistics.fmean(value) for key, value in per_margin.items()},
            "per_start_example_concentration": dict(per_start),
            "mean_examples_per_start": statistics.fmean(per_start.values()),
        }
    result["seed_arm_summaries"] = {arm: {"count": len(values), "min": min(values), "max": max(values), "mean": statistics.fmean(values)} for arm, values in (seed_metrics or {}).items() if values}
    return result


@dataclass(frozen=True)
class T093TrainingConfig:
    state_feature_size: int
    action_feature_size: int
    schema_id: str = T093_CONFIG_SCHEMA_ID
    schema_version: int = 1
    task_id: str = T093_TASK_ID
    hidden_width: int = 256
    hidden_layers: int = 2
    activation: str = "relu"
    optimizer: str = "AdamW"
    learning_rate: float = 1e-3
    weight_decay: float = 1e-4
    max_epochs: int = 30
    model_seeds: tuple[int, ...] = T093_MODEL_SEEDS

    def __post_init__(self) -> None:
        if (
            self.schema_id != T093_CONFIG_SCHEMA_ID
            or self.schema_version != 1
            or self.task_id != T093_TASK_ID
        ):
            raise T093Error("T093 training config identity is frozen")
        if (self.hidden_width, self.hidden_layers, self.activation, self.optimizer, self.learning_rate, self.weight_decay, self.max_epochs, self.model_seeds) != (256, 2, "relu", "AdamW", 1e-3, 1e-4, 30, T093_MODEL_SEEDS):
            raise T093Error("T093 model/optimization configuration is frozen")
        if self.state_feature_size < 1 or self.action_feature_size < 1:
            raise T093Error("T093 public encoding widths must be positive")

    def to_dict(self) -> dict[str, object]:
        value = asdict(self); value["model_seeds"] = list(self.model_seeds); return value


def build_t093_training_config(examples: Sequence[T093Example]) -> T093TrainingConfig:
    state_sizes = {len(item.state_features) for item in examples}
    action_sizes = {len(action) for item in examples for action in item.action_features}
    if len(state_sizes) != 1 or len(action_sizes) != 1:
        raise T093Error("T093 public feature widths are inconsistent")
    return T093TrainingConfig(state_sizes.pop(), action_sizes.pop())


def label_destruction_means(example: T093Example) -> tuple[float, ...]:
    """Cyclically remap supported targets; identity shifts are never allowed."""

    size = len(example.teacher_means)
    if size < 2:
        raise T093Error("label destruction requires at least two supported actions")
    digest = hashlib.sha256(f"{T093_LABEL_DOMAIN}:{example.public_fingerprint}".encode()).digest()
    shift = (int.from_bytes(digest[:8], "big") % (size - 1)) + 1
    return tuple(example.teacher_means[(index + shift) % size] for index in range(size))


class T093TorchScorer:
    """Fixed public-only action scorer; it has no Search or simulator handle."""

    def __init__(self, model: Any, config: T093TrainingConfig, *, arm: str) -> None:
        self.model, self.config, self.arm = model, config, arm

    def score(self, example: T093Example) -> list[float]:
        import torch

        if (
            len(example.state_features) != self.config.state_feature_size
            or any(
                len(action) != self.config.action_feature_size
                for action in example.action_features
            )
        ):
            raise T093Error("held-out public feature width differs from train/validation")
        state = (0.0,) * len(example.state_features) if self.arm == "state_ablated" else example.state_features
        self.model.eval()
        with torch.no_grad():
            states = torch.tensor(state, dtype=torch.float32).repeat(len(example.action_features), 1)
            actions = torch.tensor(example.action_features, dtype=torch.float32)
            return [float(value) for value in self.model(torch.cat((states, actions), dim=1)).reshape(-1).tolist()]


def _model(config: T093TrainingConfig, seed: int) -> Any:
    import torch

    torch.manual_seed(seed)
    width = config.state_feature_size + config.action_feature_size
    return torch.nn.Sequential(
        torch.nn.Linear(width, 256), torch.nn.ReLU(), torch.nn.Linear(256, 256),
        torch.nn.ReLU(), torch.nn.Linear(256, 1),
    )


def _arm_means(example: T093Example, arm: str) -> tuple[float, ...]:
    if arm == "true" or arm == "state_ablated":
        return example.teacher_means
    if arm == "label_destruction":
        return label_destruction_means(example)
    raise T093Error("T093 arm is invalid")


def _loss_for_example(model: Any, example: T093Example, arm: str) -> Any:
    import torch
    from torch.nn import functional

    state = (0.0,) * len(example.state_features) if arm == "state_ablated" else example.state_features
    states = torch.tensor(state, dtype=torch.float32).repeat(len(example.action_features), 1)
    actions = torch.tensor(example.action_features, dtype=torch.float32)
    scores = model(torch.cat((states, actions), dim=1)).reshape(-1)
    means = _arm_means(example, arm)
    terms = [functional.softplus(-(scores[high] - scores[low])) for high, low in T093Example(
        example.source_identity, example.source_group, example.split,
        example.parent_root_decision_identity, example.occurrence_identity,
        example.public_fingerprint, example.tree_depth, example.state_features,
        example.action_features, example.action_identities, example.action_kinds, means,
    ).pairs]
    if not terms:
        raise T093Error("pair-bearing T093 example has no non-tied pairs")
    return sum(terms) / len(terms)


def _macro_loss(model: Any, examples: Sequence[T093Example], arm: str) -> Any:
    """Exact fingerprint -> source-start macro hierarchy for one split."""

    by_source: dict[str, list[T093Example]] = defaultdict(list)
    for item in examples:
        by_source[item.source_identity].append(item)
    if not by_source:
        raise T093Error("T093 loss requires pair-bearing examples")
    source_losses = [sum(_loss_for_example(model, item, arm) for item in rows) / len(rows) for rows in by_source.values()]
    return sum(source_losses) / len(source_losses)


def train_t093_scorer(
    examples: Sequence[T093Example], *, seed: int, arm: str,
) -> tuple[T093TorchScorer, dict[str, object]]:
    """Train one registered arm without reading held-out rows.

    Validation selects the minimum loss checkpoint.  The label-destruction arm
    uses its cyclically destroyed validation labels; the other arms use true
    labels, exactly as preregistered.
    """

    if seed not in T093_MODEL_SEEDS or arm not in {"true", "label_destruction", "state_ablated"}:
        raise T093Error("T093 seed or arm is invalid")
    train = [item for item in examples if item.split == "train"]
    validation = [item for item in examples if item.split == "validation"]
    if not train or not validation:
        raise T093Error("T093 training requires train and validation examples")
    # Do not open held-out examples merely to construct the model. Evaluation
    # separately checks that its already-frozen public widths match this config.
    config = build_t093_training_config(train + validation)
    import torch

    model = _model(config, seed)
    optimizer = torch.optim.AdamW(model.parameters(), lr=1e-3, weight_decay=1e-4)
    curves: list[dict[str, float]] = []
    selected_epoch, selected_loss, selected_state = 0, math.inf, None
    for epoch in range(1, 31):
        model.train(); optimizer.zero_grad()
        loss = _macro_loss(model, train, arm)
        loss.backward(); optimizer.step()
        model.eval()
        with torch.no_grad():
            validation_loss = float(_macro_loss(model, validation, arm))
        curves.append({"epoch": epoch, "train_loss": float(loss.detach()), "validation_loss": validation_loss})
        if validation_loss < selected_loss:
            selected_epoch, selected_loss = epoch, validation_loss
            selected_state = {key: value.detach().clone() for key, value in model.state_dict().items()}
    if selected_state is None:
        raise T093Error("T093 checkpoint selection failed")
    model.load_state_dict(selected_state)
    scorer = T093TorchScorer(model, config, arm=arm)
    checkpoint = t093_checkpoint_identity(
        model.state_dict(), config=config, arm=arm, seed=seed,
        selected_epoch=selected_epoch,
    )
    return scorer, {"schema_id": "t093-training-summary-v1", "task_id": T093_TASK_ID,
                    "arm": arm, "seed": seed, "selected_epoch": selected_epoch,
                    "selection_split": "validation", "selection_metric": "pairwise_logistic_ranking_loss",
                    "selection_labels": "destroyed" if arm == "label_destruction" else "true",
                    "learning_curve": curves, "selected_validation_loss": selected_loss,
                    "training_config": config.to_dict(), "selected_checkpoint": checkpoint}


def evaluate_t093_scorer(examples: Sequence[T093Example], scorer: T093TorchScorer) -> dict[str, object]:
    scores = {item.public_fingerprint: scorer.score(item) for item in examples}
    return source_start_macro_accuracy(examples, scores)


def train_validation_adequacy(
    *, train_true: Sequence[Mapping[str, object]], validation_true: Sequence[Mapping[str, object]],
    validation_label_destruction: Sequence[Mapping[str, object]], validation_state_ablated: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    """Apply the frozen admission test before any held-out metric is opened."""

    def by_seed(rows: Sequence[Mapping[str, object]]) -> dict[int, float]:
        result: dict[int, float] = {}
        for row in rows:
            seed, value = row.get("seed"), row.get("source_start_macro_accuracy")
            if seed not in T093_MODEL_SEEDS or seed in result or value is None:
                raise T093Error("adequacy rows must contain each registered seed once")
            result[int(seed)] = _finite(value, "source-start macro accuracy")
        if set(result) != set(T093_MODEL_SEEDS):
            raise T093Error("adequacy requires all three registered seeds")
        return result
    train = by_seed(train_true); true = by_seed(validation_true)
    destroyed = by_seed(validation_label_destruction); ablated = by_seed(validation_state_ablated)
    fit = sum(value >= .70 for value in train.values()) >= 2
    transfer = sum(true[seed] > .5 and true[seed] > destroyed[seed] and true[seed] > ablated[seed] for seed in T093_MODEL_SEEDS) >= 2
    return {"train_true_by_seed": train, "validation_true_by_seed": true,
            "validation_label_destruction_by_seed": destroyed,
            "validation_state_ablated_by_seed": ablated,
            "fit_predicate_passed": fit, "transfer_predicate_passed": transfer,
            "passed": fit and transfer, "heldout_opened": fit and transfer}


def heldout_t093_gate(
    *, true_by_seed: Mapping[int, Mapping[str, object]],
    label_destruction_by_seed: Mapping[int, Mapping[str, object]],
    state_ablated_by_seed: Mapping[int, Mapping[str, object]],
) -> dict[str, object]:
    """Compute the held-out gate from already-admitted per-seed start rows."""

    def rows_by_seed(values: Mapping[int, Mapping[str, object]]) -> tuple[dict[str, float], dict[str, str]]:
        if set(values) != set(T093_MODEL_SEEDS):
            raise T093Error("held-out report requires all registered seeds")
        per_seed: list[dict[str, float]] = []
        groups: dict[str, str] = {}
        for seed in T093_MODEL_SEEDS:
            rows = values[seed].get("source_start_rows")
            if not isinstance(rows, Sequence):
                raise T093Error("held-out source-start rows are unavailable")
            table: dict[str, float] = {}
            for row in rows:
                if not isinstance(row, Mapping):
                    raise T093Error("held-out source-start row is malformed")
                source, group = row.get("source_identity"), row.get("source_group")
                if not isinstance(source, str) or group not in T093_SOURCE_GROUPS:
                    raise T093Error("held-out source ownership is invalid")
                table[source] = _finite(row.get("accuracy"), "held-out accuracy")
                prior = groups.setdefault(source, str(group))
                if prior != group:
                    raise T093Error("held-out source group changes between seeds")
            per_seed.append(table)
        if any(set(table) != set(per_seed[0]) for table in per_seed):
            raise T093Error("held-out seeds are not paired on source starts")
        return ({source: statistics.fmean(table[source] for table in per_seed) for source in per_seed[0]}, groups)
    true, groups = rows_by_seed(true_by_seed)
    destroyed, destroyed_groups = rows_by_seed(label_destruction_by_seed)
    ablated, ablated_groups = rows_by_seed(state_ablated_by_seed)
    if groups != destroyed_groups or groups != ablated_groups or set(true) != set(destroyed) or set(true) != set(ablated):
        raise T093Error("held-out arms are not exactly paired")
    bootstrap = stratified_start_bootstrap({
        "true_student": true, "label_destruction": destroyed, "state_ablated": ablated,
        "true_minus_label_destruction": {source: true[source] - destroyed[source] for source in true},
        "true_minus_state_ablated": {source: true[source] - ablated[source] for source in true},
        "__groups__": groups,
    })
    arms = bootstrap["arms"]
    matched_seed_passes = sum(
        true_by_seed[seed]["source_start_macro_accuracy"] > .5
        and true_by_seed[seed]["source_start_macro_accuracy"] > label_destruction_by_seed[seed]["source_start_macro_accuracy"]
        and true_by_seed[seed]["source_start_macro_accuracy"] > state_ablated_by_seed[seed]["source_start_macro_accuracy"]
        for seed in T093_MODEL_SEEDS
    )
    passed = (
        arms["true_student"]["ci_95"][0] > .5
        and arms["true_minus_label_destruction"]["ci_95"][0] > 0
        and arms["true_minus_state_ablated"]["ci_95"][0] > 0
        and matched_seed_passes >= 2
    )
    return {"schema_id": T093_REPORT_SCHEMA_ID, "sampling": bootstrap,
            "matched_seed_pass_count": matched_seed_passes, "chance_reference": .5,
            "passed": passed}


def conflict_limiting_gate(evidence: Mapping[str, object]) -> dict[str, object]:
    """Validate T093's sole preregistered conflict-limiting diagnosis path."""

    adequacy = evidence.get("adequacy")
    rows = evidence.get("paired_source_start_rows")
    counts = evidence.get("canonical_fingerprint_counts")
    starts = evidence.get("contributing_start_counts")
    if (
        not isinstance(adequacy, Mapping) or adequacy.get("passed") is not True
        or not isinstance(rows, Sequence) or not isinstance(counts, Mapping)
        or not isinstance(starts, Mapping)
        or counts.get("conflict_bearing", 0) < 500
        or counts.get("singleton_or_no_observed_conflict", 0) < 500
        or starts.get("conflict_bearing", 0) < 15
        or starts.get("singleton_or_no_observed_conflict", 0) < 15
    ):
        return {"validated": True, "passed": False, "reason": "required adequacy/stratum evidence is unavailable"}
    groups: dict[str, str] = {}
    values: dict[str, dict[str, float]] = {name: {} for name in (
        "singleton_true", "singleton_label", "singleton_ablated", "conflict_true",
        "singleton_minus_label", "singleton_minus_ablated", "singleton_minus_conflict",
    )}
    for row in rows:
        if not isinstance(row, Mapping) or not isinstance(row.get("source_identity"), str) or row.get("source_group") not in T093_SOURCE_GROUPS:
            raise T093Error("conflict diagnostic source-start row is ambiguous")
        source = str(row["source_identity"])
        if source in groups:
            raise T093Error("conflict diagnostic source-start row is duplicate")
        groups[source] = str(row["source_group"])
        for name in ("singleton_true", "singleton_label", "singleton_ablated", "conflict_true"):
            values[name][source] = _finite(row.get(name), name)
        values["singleton_minus_label"][source] = values["singleton_true"][source] - values["singleton_label"][source]
        values["singleton_minus_ablated"][source] = values["singleton_true"][source] - values["singleton_ablated"][source]
        values["singleton_minus_conflict"][source] = values["singleton_true"][source] - values["conflict_true"][source]
    bootstrap = stratified_start_bootstrap({**values, "__groups__": groups})
    arms = bootstrap["arms"]
    passed = (
        arms["singleton_true"]["ci_95"][0] > .5
        and arms["singleton_minus_label"]["ci_95"][0] > 0
        and arms["singleton_minus_ablated"]["ci_95"][0] > 0
        and arms["singleton_minus_conflict"]["ci_95"][0] > 0
    )
    return {"validated": True, "passed": passed, "bootstrap": bootstrap,
            "diagnostic_only": True, "no_student_input_or_reweight": True}


def source_start_macro_accuracy(
    examples: Sequence[T093Example], score: Mapping[str, Sequence[float]],
) -> dict[str, object]:
    """Macro average pairs->fingerprints->starts, retaining paired start rows."""

    fingerprints: dict[str, list[float]] = defaultdict(list)
    source_for_fingerprint: dict[str, tuple[str, str]] = {}
    for example in examples:
        values = score.get(example.public_fingerprint)
        if values is None or len(values) != len(example.teacher_means):
            raise T093Error("score rows do not cover aligned public actions")
        comparisons = [float(values[high]) > float(values[low]) for high, low in example.pairs]
        fingerprints[example.public_fingerprint].append(statistics.fmean(comparisons))
        source_for_fingerprint[example.public_fingerprint] = (example.source_identity, example.source_group)
    starts: dict[str, list[float]] = defaultdict(list)
    groups: dict[str, str] = {}
    for fingerprint, values in fingerprints.items():
        source, group = source_for_fingerprint[fingerprint]
        starts[source].append(statistics.fmean(values)); groups[source] = group
    rows = [{"source_identity": source, "source_group": groups[source], "accuracy": statistics.fmean(values)} for source, values in sorted(starts.items())]
    return {"source_start_rows": rows, "source_start_macro_accuracy": statistics.fmean(row["accuracy"] for row in rows) if rows else None}


def stratified_start_bootstrap(
    values: Mapping[str, Mapping[str, float]], *, seed: int = T093_BOOTSTRAP_SEED,
    replicates: int = T093_BOOTSTRAP_REPLICATES,
) -> dict[str, object]:
    """Paired A/B/C source-start bootstrap; values are arm -> source -> metric."""

    if replicates != T093_BOOTSTRAP_REPLICATES or seed != T093_BOOTSTRAP_SEED:
        raise T093Error("T093 bootstrap configuration is frozen")
    arms = tuple(values)
    if not arms or any(set(values[arm]) != set(values[arms[0]]) for arm in arms):
        raise T093Error("bootstrap arms must be paired on identical source starts")
    groups: dict[str, list[str]] = defaultdict(list)
    # The report callers supply source groups under the reserved __groups__ arm
    group_values = values.get("__groups__")
    if not isinstance(group_values, Mapping):
        raise T093Error("bootstrap requires explicit source-group ownership")
    metric_arms = tuple(arm for arm in arms if arm != "__groups__")
    for source, group in group_values.items():
        if group not in T093_SOURCE_GROUPS or source not in values[metric_arms[0]]:
            raise T093Error("bootstrap source group is invalid")
        groups[str(group)].append(str(source))
    if any(not groups[group] for group in T093_SOURCE_GROUPS):
        raise T093Error("bootstrap requires contributing starts in every source group")
    rng = random.Random(seed)
    samples: dict[str, list[float]] = {arm: [] for arm in metric_arms}
    for _ in range(replicates):
        sampled = [rng.choice(groups[group]) for group in T093_SOURCE_GROUPS for _ in groups[group]]
        for arm in metric_arms:
            samples[arm].append(statistics.fmean(float(values[arm][source]) for source in sampled))
    return {"sampling_unit": "heldout_source_battle_start", "strata": {group: len(rows) for group, rows in groups.items()}, "seed": seed, "replicates": replicates,
            "arms": {arm: {"point": statistics.fmean(float(v) for v in values[arm].values()), "ci_95": [_percentile(samples[arm], .025), _percentile(samples[arm], .975)]} for arm in metric_arms}}


def classify_t093(
    *, information_valid: bool, evidence_valid: bool, diversity: Mapping[str, object],
    adequacy: Mapping[str, object], heldout: Mapping[str, object] | None = None,
    conflict_diagnostic: Mapping[str, object] | None = None,
) -> str:
    if not information_valid:
        return "INTERNAL_STATE_STUDENT_INFORMATION_BOUNDARY_INVALID"
    if not evidence_valid:
        return "INCOMPLETE"
    if diversity.get("passed") is not True:
        return "INTERNAL_STATE_STUDENT_EFFECTIVE_DIVERSITY_INSUFFICIENT"
    if adequacy.get("passed") is not True:
        return "INTERNAL_STATE_STUDENT_MODEL_OR_TARGET_INADEQUATE"
    if heldout is None:
        raise T093Error("held-out result is required after adequacy admission")
    if heldout.get("passed") is True:
        return "INTERNAL_STATE_BATTLE_STUDENT_SIGNAL_ESTABLISHED"
    if conflict_diagnostic is not None and conflict_limiting_gate(conflict_diagnostic).get("passed") is True:
        return "INTERNAL_STATE_STUDENT_REPEATED_PUBLIC_CONFLICT_LIMITING"
    return "INTERNAL_STATE_STUDENT_GENERALIZATION_NOT_ESTABLISHED"


__all__ = [
    "T093_BOOTSTRAP_REPLICATES", "T093_BOOTSTRAP_SEED", "T093_CHECKPOINT_SCHEMA_ID", "T093_CONFIG_SCHEMA_ID",
    "T093Error", "T093Example", "T093TrainingConfig", "build_t093_training_config",
    "classify_t093", "effective_diversity_report", "example_from_t092_occurrence",
    "evaluate_t093_scorer", "heldout_t093_gate", "label_destruction_means",
    "materialize_t093_from_paths", "source_start_macro_accuracy", "stratified_start_bootstrap",
    "conflict_limiting_gate", "repeated_public_state_diagnostics", "secondary_stratified_report", "t093_checkpoint_identity",
    "train_t093_scorer", "train_validation_adequacy", "validate_t093_source_record",
]
