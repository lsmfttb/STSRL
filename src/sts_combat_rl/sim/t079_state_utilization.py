"""Pure reducers and fail-closed gates for the T079 search diagnostic."""

from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

T079_STATE_UTILIZATION_REPORT_SCHEMA_ID = "t079-state-utilization-report-v1"
T079_CLASSIFICATIONS = (
    "MATERIAL_EXACT_TRANSPOSITION_SIGNAL",
    "EXACT_TRANSPOSITION_SIGNAL_WEAK",
    "AMBIGUOUS",
)
T079_BUDGETS = (100, 400, 1600)
T079_RECORD_COUNT = 16
T079_WORKER_COUNT = 16
T079_PATH_FINGERPRINT_SCHEMA = "occurrence_safe_action_path_v1"
T079_IDENTITY_CLASSES = ("exact_comparable", "opaque")


def flatten_t079_call_records(value: object) -> list[Mapping[str, Any]]:
    """Flatten fixed-evaluation telemetry lists without accepting malformed rows."""

    flattened: list[Mapping[str, Any]] = []

    def flatten(item: object) -> None:
        if isinstance(item, Mapping):
            flattened.append(item)
            return
        if isinstance(item, Sequence) and not isinstance(item, (str, bytes)):
            for nested in item:
                flatten(nested)
            return
        raise TypeError("T079 state-utilization call row is malformed")

    flatten(value)
    if not flattened:
        raise ValueError("T079 state-utilization call records are empty")
    return flattened


def t079_result_is_complete(
    termination_status: object,
    result_problems: object,
    report_problems: object,
) -> bool:
    """Return whether one restored battle is safe for T079 science."""

    return (
        termination_status in {"win", "loss"}
        and isinstance(result_problems, list)
        and not result_problems
        and isinstance(report_problems, list)
        and not report_problems
    )


def build_search_call_identity(
    raw_identity: Mapping[str, Any],
    *,
    cohort_identity: str,
    record_index: int,
    decision_step_index: int,
) -> dict[str, Any]:
    """Validate and complete the controller-emitted stable call identity."""

    expected = {"schema_id", "controller_identity", "decision_step_index"}
    if set(raw_identity) != expected:
        raise ValueError("T079 search-call identity fields are incomplete")
    if raw_identity["schema_id"] != "t079-search-call-identity-v1":
        raise ValueError("T079 search-call identity schema is invalid")
    controller_identity = raw_identity["controller_identity"]
    if not isinstance(controller_identity, str) or not controller_identity:
        raise ValueError("T079 search-call controller identity is missing")
    if raw_identity["decision_step_index"] != decision_step_index:
        raise ValueError("T079 search-call decision step identity disagrees")
    if not isinstance(cohort_identity, str) or not cohort_identity:
        raise ValueError("T079 cohort identity is missing")
    if (
        isinstance(record_index, bool)
        or not isinstance(record_index, int)
        or record_index < 0
    ):
        raise ValueError("T079 search-call record identity is invalid")
    return {
        "schema_id": raw_identity["schema_id"],
        "cohort_identity": cohort_identity,
        "record_index": record_index,
        "decision_step_index": decision_step_index,
        "controller_identity": controller_identity,
    }


def _median_16(values: Sequence[float]) -> float:
    """Return the literal median of the frozen 16-record cohort."""

    if len(values) != T079_RECORD_COUNT:
        raise ValueError("T079 median requires exactly 16 samples")
    ordered = sorted(float(value) for value in values)
    return (ordered[7] + ordered[8]) / 2.0


def validate_canonical_digest_buckets(
    canonical_payloads: Mapping[str, Sequence[str] | str],
) -> None:
    """Fail closed if one digest is associated with unequal canonical states."""

    for digest, payloads in canonical_payloads.items():
        values = [payloads] if isinstance(payloads, str) else list(payloads)
        if not values or any(not isinstance(value, str) for value in values):
            raise ValueError(f"T079 canonical payload bucket is malformed: {digest}")
        if len(set(values)) != 1:
            raise ValueError(f"T079 digest bucket failed canonical equality: {digest}")


def validate_occurrence_rows(
    rows: Sequence[Mapping[str, Any]], *, count: int
) -> list[dict[str, Any]]:
    """Validate occurrence evidence, including the recovery identity partition.

    Native T079 v1 rows predate the recovery partition and therefore omit the
    class fields.  Such rows are accepted as exact-comparable fixtures only;
    native adapter output must pass through :func:`normalize_native_state_utilization`
    so an incomplete native identity becomes explicitly opaque.
    """

    if len(rows) != count or count < 1:
        raise ValueError("T079 expanded-state row count is invalid")
    normalized: list[dict[str, Any]] = []
    first_by_digest: dict[str, tuple[int, int]] = {}
    paths: set[str] = set()
    for ordinal, raw_row in enumerate(rows, 1):
        if not isinstance(raw_row, Mapping):
            raise TypeError("T079 expanded-state row is malformed")
        row = dict(raw_row)
        expected = {
            "expansion_ordinal",
            "depth",
            "exact_state_digest",
            "first_seen",
            "first_seen_expansion_ordinal",
            "first_seen_depth",
            "path_fingerprint",
        }
        extra = set(row) - expected
        if extra - {"identity_evidence_class", "opaque_reason"}:
            raise ValueError("T079 expanded-state row fields mismatch")
        identity_class = row.get("identity_evidence_class", "exact_comparable")
        if identity_class not in T079_IDENTITY_CLASSES:
            raise ValueError("T079 identity evidence class is invalid")
        if identity_class == "opaque":
            reason = row.get("opaque_reason")
            if not isinstance(reason, str) or not reason:
                raise ValueError("T079 opaque identity reason is missing")
        elif "opaque_reason" in row and row["opaque_reason"] is not None:
            raise ValueError("T079 exact-comparable row has opaque reason")
        if row["expansion_ordinal"] != ordinal:
            raise ValueError("T079 expansion ordinals are not contiguous")
        depth = row["depth"]
        if isinstance(depth, bool) or not isinstance(depth, int) or depth < 0:
            raise ValueError("T079 expansion depth is invalid")
        digest = row["exact_state_digest"]
        if identity_class == "exact_comparable":
            if not isinstance(digest, str) or len(digest) != 32:
                raise ValueError("T079 exact-state digest is invalid")
        elif digest is not None:
            raise ValueError("T079 opaque row contains an equality digest")
        path = row["path_fingerprint"]
        if not isinstance(path, str) or not path.startswith("p") or path in paths:
            raise ValueError("T079 occurrence/path evidence is invalid")
        paths.add(path)
        first_seen = row["first_seen"]
        if identity_class == "opaque":
            if any(
                row[key] is not None
                for key in (
                    "first_seen",
                    "first_seen_expansion_ordinal",
                    "first_seen_depth",
                )
            ):
                raise ValueError(
                    "T079 opaque row contains equality occurrence evidence"
                )
            normalized.append(row)
            continue
        if not isinstance(first_seen, bool):
            raise TypeError("T079 first_seen flag is invalid")
        first_ordinal = row["first_seen_expansion_ordinal"]
        first_depth = row["first_seen_depth"]
        if (
            isinstance(first_ordinal, bool)
            or not isinstance(first_ordinal, int)
            or first_ordinal < 1
            or first_ordinal > ordinal
            or isinstance(first_depth, bool)
            or not isinstance(first_depth, int)
            or first_depth < 0
        ):
            raise ValueError("T079 first-seen evidence is invalid")
        previous = first_by_digest.get(digest)
        if previous is None:
            if not first_seen or first_ordinal != ordinal or first_depth != depth:
                raise ValueError("T079 first-seen evidence disagrees with order")
            first_by_digest[digest] = (ordinal, depth)
        else:
            if (
                first_seen
                or first_ordinal >= ordinal
                or (first_ordinal, first_depth) != previous
            ):
                raise ValueError("T079 duplicate occurrence evidence is invalid")
        normalized.append(row)
    return normalized


def normalize_native_state_utilization(
    native_state_utilization: Mapping[str, Any],
) -> tuple[list[dict[str, Any]], str]:
    """Partition native rows without inventing identity for opaque nodes.

    Native v1 exposes completeness at the telemetry-call level.  If that gate
    is false, no per-row claim can be recovered from the payload, so all rows
    are conservatively classified opaque.  Their native digest and first-seen
    fields are deliberately discarded rather than reused as equality evidence.
    """

    rows = native_state_utilization.get("expanded_states")
    count = native_state_utilization.get("expanded_path_node_count")
    if not isinstance(rows, Sequence) or isinstance(rows, (str, bytes)):
        raise TypeError("T079 expanded-state rows are missing")
    if isinstance(count, bool) or not isinstance(count, int) or count != len(rows):
        raise ValueError("T079 expanded-state row count is invalid")
    complete = native_state_utilization.get("identity_complete")
    if not isinstance(complete, bool):
        raise TypeError("T079 identity completeness flag is invalid")
    reason = native_state_utilization.get("identity_unavailable_reason")
    if complete:
        if reason not in (None, ""):
            raise ValueError("T079 complete identity has an unavailable reason")
        normalized = []
        for row in rows:
            if not isinstance(row, Mapping):
                raise TypeError("T079 expanded-state row is malformed")
            item = dict(row)
            item["identity_evidence_class"] = "exact_comparable"
            item["opaque_reason"] = None
            normalized.append(item)
        return validate_occurrence_rows(normalized, count=count), "exact_comparable"
    if not isinstance(reason, str) or not reason:
        raise ValueError("T079 incomplete identity has no reason")
    normalized = []
    for row in rows:
        if not isinstance(row, Mapping):
            raise TypeError("T079 expanded-state row is malformed")
        item = dict(row)
        item.update(
            {
                "identity_evidence_class": "opaque",
                "opaque_reason": reason,
                "exact_state_digest": None,
                "first_seen": None,
                "first_seen_expansion_ordinal": None,
                "first_seen_depth": None,
            }
        )
        normalized.append(item)
    return validate_occurrence_rows(normalized, count=count), "opaque"


def _p90(values: Sequence[int]) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    return float(ordered[max(0, (9 * len(ordered) + 9) // 10 - 1)])


def summarize_state_utilization(
    native_state_utilization: Mapping[str, Any],
    *,
    geometry: Mapping[str, Any] | None = None,
    compute: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Reduce one native state-utilization payload without changing semantics."""

    if native_state_utilization.get("digest_collision_count") != 0:
        raise ValueError("T079 exact-state digest collision was rejected")
    if (
        native_state_utilization.get("collision_check")
        != "canonical_payload_equality_within_digest_bucket"
    ):
        raise ValueError("T079 canonical digest equality was not established")
    normalized_rows, _ = normalize_native_state_utilization(native_state_utilization)
    count = len(normalized_rows)
    if count < 1:
        raise ValueError("T079 expanded-state row count is invalid")
    canonical_payloads = native_state_utilization.get("canonical_payloads")
    if canonical_payloads is not None:
        if not isinstance(canonical_payloads, Mapping):
            raise ValueError("T079 canonical payload evidence is malformed")
        validate_canonical_digest_buckets(canonical_payloads)
    comparable_rows = [
        row
        for row in normalized_rows
        if row["identity_evidence_class"] == "exact_comparable"
    ]
    opaque_rows = [
        row for row in normalized_rows if row["identity_evidence_class"] == "opaque"
    ]
    groups: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in comparable_rows:
        digest = row["exact_state_digest"]
        groups[digest].append(row)
    comparable = len(comparable_rows)
    opaque = len(opaque_rows)
    unique = len(groups)
    duplicate = comparable - unique
    multiplicities = [len(group) for group in groups.values()]
    duplicate_groups = [group for group in groups.values() if len(group) > 1]
    distinct_path_groups = [
        group
        for group in duplicate_groups
        if len({row.get("path_fingerprint") for row in group}) > 1
    ]
    duplicate_by_depth = Counter(
        int(row["depth"]) for group in duplicate_groups for row in group[1:]
    )
    first_seen_depth = Counter(int(group[0]["depth"]) for group in groups.values())
    duplicate_depth = Counter(
        int(row["depth"]) for group in duplicate_groups for row in group[1:]
    )
    top_groups = []
    for digest, group in sorted(
        groups.items(), key=lambda item: (-len(item[1]), item[0])
    )[:10]:
        if len(group) < 2:
            continue
        top_groups.append(
            {
                "exact_state_digest": digest,
                "multiplicity": len(group),
                "occurrences": [
                    {
                        "expansion_ordinal": row["expansion_ordinal"],
                        "depth": row["depth"],
                        "path_fingerprint": row["path_fingerprint"],
                    }
                    for row in group
                ],
            }
        )
    result: dict[str, Any] = {
        "schema_id": T079_STATE_UTILIZATION_REPORT_SCHEMA_ID,
        "expanded_states": normalized_rows,
        "expanded_path_nodes": count,
        "unique_exact_states": unique,
        "exact_duplicate_path_nodes": duplicate,
        "comparable_nodes": comparable,
        "opaque_nodes": opaque,
        "identity_evidence_class_counts": {
            "exact_comparable": comparable,
            "opaque": opaque,
        },
        "identity_partition_valid": count == comparable + opaque,
        "exact_duplicate_fraction_lower": duplicate / count,
        "exact_duplicate_fraction_upper": (duplicate + opaque) / count,
        "unique_state_yield_lower": unique / count,
        "unique_state_yield_upper": (unique + opaque) / count,
        # Compatibility aliases retain the conservative, opaque-unfavorable
        # side for consumers that only understand the original field names.
        "exact_duplicate_fraction": duplicate / count,
        "unique_state_yield": unique / count,
        "duplicate_group_count": len(duplicate_groups),
        "paths_per_exact_state": {
            "mean": sum(multiplicities) / len(multiplicities)
            if multiplicities
            else 0.0,
            "median": (
                float(sorted(multiplicities)[(len(multiplicities) - 1) // 2])
                if multiplicities
                else 0.0
            ),
            "p90": _p90(multiplicities),
            "max": max(multiplicities) if multiplicities else 0.0,
        },
        "distinct_path_duplicate_group_count": len(distinct_path_groups),
        "distinct_path_duplicate_group_fraction": (
            len(distinct_path_groups) / len(duplicate_groups)
            if duplicate_groups
            else 0.0
        ),
        "duplicate_expansions_by_depth": dict(sorted(duplicate_by_depth.items())),
        "first_seen_depth": dict(sorted(first_seen_depth.items())),
        "duplicate_depth": dict(sorted(duplicate_depth.items())),
        "top_repeated_exact_states": top_groups,
        "opaque_reason_counts": dict(
            sorted(Counter(str(row["opaque_reason"]) for row in opaque_rows).items())
        ),
        "opaque_depth_counts": dict(
            sorted(Counter(str(row["depth"]) for row in opaque_rows).items())
        ),
    }
    if geometry is not None:
        result["tree_geometry"] = dict(geometry)
    if compute is not None:
        result["compute"] = dict(compute)
    return result


def compare_prefix_sequences(
    sequences: Mapping[int, Sequence[object]],
) -> dict[str, Any]:
    """Compare traversal prefixes and bound first-appearance state yield.

    Mapping entries carry path/action evidence plus optional exact identity
    evidence.  Plain strings remain supported as exact-comparable test
    fixtures.  Path evidence establishes the prefix; only exact-comparable
    digests contribute to the lower-bound ``K`` and opaque entries contribute
    only to the upper-bound uncertainty.
    """

    normalized = {int(budget): list(sequence) for budget, sequence in sequences.items()}

    def path_token(entry: object) -> object:
        if isinstance(entry, Mapping):
            token = entry.get("path_fingerprint")
            if not isinstance(token, str) or not token:
                raise ValueError("T079 prefix path evidence is malformed")
            return token
        if not isinstance(entry, str):
            raise TypeError("T079 prefix sequence entry is malformed")
        return entry

    def exact_token(entry: object) -> str | None:
        if not isinstance(entry, Mapping):
            return str(entry)
        if entry.get("identity_evidence_class") != "exact_comparable":
            return None
        digest = entry.get("exact_state_digest")
        if not isinstance(digest, str) or len(digest) != 32:
            raise ValueError("T079 exact-comparable prefix digest is invalid")
        return digest

    result: dict[str, Any] = {}
    for shorter, longer, label, width in (
        (100, 400, "100_400", 300),
        (400, 1600, "400_1600", 1200),
    ):
        left = normalized.get(shorter, [])
        right = normalized.get(longer, [])
        comparable = (
            len(left) >= shorter
            and len(right) >= longer
            and [path_token(item) for item in right[:shorter]]
            == [path_token(item) for item in left[:shorter]]
        )
        entry: dict[str, Any] = {
            "prefix_comparable": comparable,
            "shorter_budget": shorter,
            "longer_budget": longer,
        }
        if comparable:
            interval = right[shorter:longer]
            seen = {
                token
                for item in right[:shorter]
                if (token := exact_token(item)) is not None
            }
            first_appearing_unique = 0
            opaque_count = 0
            for item in interval:
                token = exact_token(item)
                if token is None:
                    opaque_count += 1
                elif token not in seen:
                    first_appearing_unique += 1
                    seen.add(token)
            lower = first_appearing_unique / width
            upper = (first_appearing_unique + opaque_count) / width
            entry["marginal_unique_yield_lower"] = lower
            entry["marginal_unique_yield_upper"] = upper
            entry["marginal_opaque_expansions"] = opaque_count
            entry["marginal_unique_yield"] = lower
            entry["marginal_duplicate_fraction"] = 1.0 - lower
        else:
            entry["marginal_unique_yield_lower"] = None
            entry["marginal_unique_yield_upper"] = None
            entry["marginal_opaque_expansions"] = None
            entry["marginal_unique_yield"] = None
            entry["marginal_duplicate_fraction"] = None
        result[label] = entry
    result["prefix_comparable"] = bool(
        result["100_400"]["prefix_comparable"]
        and result["400_1600"]["prefix_comparable"]
    )
    return result


def classify_t079(
    first_root_1600: Sequence[Mapping[str, Any]], *, comparable_count: int
) -> dict[str, Any]:
    """Apply the frozen T079 bands to the required conservative sides."""

    if len(first_root_1600) != T079_RECORD_COUNT:
        raise ValueError("T079 classification requires 16 first-root records")
    if comparable_count < 12:
        classification = "AMBIGUOUS"
    else:

        def metric(row: Mapping[str, Any], preferred: str, fallback: str) -> float:
            value = row.get(preferred)
            if value is None:
                value = row.get(fallback)
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise TypeError(f"T079 classification metric is missing: {preferred}")
            return float(value)

        material_fractions = [
            metric(row, "exact_duplicate_fraction_lower", "exact_duplicate_fraction")
            for row in first_root_1600
        ]
        weak_fractions = [
            metric(row, "exact_duplicate_fraction_upper", "exact_duplicate_fraction")
            for row in first_root_1600
        ]
        material_marginal = [
            metric(
                row,
                "marginal_unique_yield_upper",
                "marginal_unique_yield_400_1600",
            )
            for row in first_root_1600
        ]
        weak_marginal = [
            metric(
                row,
                "marginal_unique_yield_lower",
                "marginal_unique_yield_400_1600",
            )
            for row in first_root_1600
        ]
        distinct = [
            int(row["distinct_path_duplicate_group_count"]) > 0
            for row in first_root_1600
        ]
        material = (
            _median_16(material_fractions) >= 0.20
            and _median_16(material_marginal) <= 0.80
            and sum(value >= 0.15 for value in material_fractions) >= 8
            and sum(distinct) >= 8
        )
        weak = (
            _median_16(weak_fractions) <= 0.05
            and sum(value <= 0.10 for value in weak_fractions) >= 12
            and _median_16(weak_marginal) >= 0.90
            and sum(value > 0.20 for value in weak_fractions) <= 2
        )
        classification = (
            "MATERIAL_EXACT_TRANSPOSITION_SIGNAL"
            if material
            else "EXACT_TRANSPOSITION_SIGNAL_WEAK"
            if weak
            else "AMBIGUOUS"
        )
    return {
        "schema_id": "t079-terminal-diagnostic-classification-v1",
        "classification": classification,
        "comparable_first_root_count": comparable_count,
        "bands_frozen": True,
        "threshold_retuned": False,
    }


def validate_stage_inventory(
    stage_rows: Sequence[Mapping[str, Any]], *, worker_count: int = T079_WORKER_COUNT
) -> None:
    """Reject incomplete or incorrectly parallelized stage evidence."""

    if len(stage_rows) != T079_RECORD_COUNT:
        raise ValueError("T079 stage must contain exactly 16 record rows")
    indices = [row.get("record_index") for row in stage_rows]
    if sorted(indices) != list(range(T079_RECORD_COUNT)):
        raise ValueError("T079 stage records are not an exact ordered cohort")
    for row in stage_rows:
        if (
            row.get("worker_count") != worker_count
            or row.get("effective_worker_count") != worker_count
            or row.get("shard_count") != T079_RECORD_COUNT
            or row.get("shard_index") != row.get("record_index")
            or row.get("shard_range")
            != [row.get("record_index"), row.get("record_index") + 1]
        ):
            raise ValueError(
                "T079 stage does not report 16 effective workers and shards"
            )
        if row.get("status") not in {"completed", "success"}:
            raise ValueError("T079 stage contains an incomplete record")
        result = row.get("result")
        if not isinstance(result, Mapping) or not t079_result_is_complete(
            result.get("termination_status"),
            result.get("problems"),
            row.get("problems"),
        ):
            raise ValueError("T079 stage contains an incomplete restored battle")
        exit_code = row.get("worker_exit_code")
        if exit_code != 0:
            raise ValueError(f"T079 worker exited nonzero: {exit_code!r}")
        pid = row.get("worker_pid")
        if isinstance(pid, bool) or not isinstance(pid, int) or pid <= 0:
            raise ValueError("T079 stage worker PID evidence is invalid")
        if row.get("spawned_process_pid") != pid:
            raise ValueError("T079 worker PID does not match spawned Process.pid")
        cpu_count = row.get("worker_logical_cpu_count")
        if (
            isinstance(cpu_count, bool)
            or not isinstance(cpu_count, int)
            or cpu_count < worker_count
        ):
            raise ValueError("T079 worker logical CPU evidence is invalid")
        affinity = row.get("worker_cpu_affinity")
        if not isinstance(affinity, list) or not affinity:
            raise ValueError("T079 worker CPU affinity evidence is missing")
        host_cpu_count = row.get("host_logical_cpu_count")
        if (
            isinstance(host_cpu_count, bool)
            or not isinstance(host_cpu_count, int)
            or host_cpu_count < worker_count
        ):
            raise ValueError("T079 host logical CPU evidence is invalid")
        host_affinity = row.get("host_cpu_affinity")
        if not isinstance(host_affinity, list) or not host_affinity:
            raise ValueError("T079 host CPU affinity evidence is missing")
        start = row.get("worker_started_monotonic")
        end = row.get("worker_finished_monotonic")
        if (
            not isinstance(start, (int, float))
            or isinstance(start, bool)
            or not isinstance(end, (int, float))
            or isinstance(end, bool)
            or end <= start
        ):
            raise ValueError("T079 stage worker interval evidence is invalid")
    pids = {row["worker_pid"] for row in stage_rows}
    if len(pids) != worker_count:
        raise ValueError("T079 stage effective worker PID topology is incomplete")
    events = sorted(
        [(row["worker_started_monotonic"], 1) for row in stage_rows]
        + [(row["worker_finished_monotonic"], -1) for row in stage_rows]
    )
    active = peak = 0
    for _, delta in events:
        active += delta
        peak = max(peak, active)
    if peak != worker_count:
        raise ValueError("T079 stage evidence does not prove 16-way concurrency")
    if any(row.get("observed_peak_concurrency") != peak for row in stage_rows):
        raise ValueError("T079 stage observed concurrency does not match topology")


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path: str | Path, payload: Mapping[str, Any]) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
