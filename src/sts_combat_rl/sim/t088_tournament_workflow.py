"""Fail-closed, non-executing evidence workflow for the T088 tournament.

This module deliberately knows nothing about a simulator implementation.  It
turns explicitly supplied restored-record and execution evidence into a
deterministic plan, paired analyses, and a blinded review surface.  A caller
which actually restores or plays a battle remains responsible for obtaining
the separate Maintainer authorizations required by T088.
"""

from __future__ import annotations

import hashlib
import json
import math
import random
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from statistics import mean, median

from sts_combat_rl.sim.t087_dense_combat_diagnostics import (
    T087_COHORT_COUNTS,
    T087_NATIVE_IDENTITY,
    T087_NATURAL_RECORD_COUNT,
    T087IncompleteError,
    build_dense_diagnostic_row,
    build_review_rubric,
)

T088_TASK_ID = "T088"
T088_ARMS = ("A", "B", "C", "D")
T088_BOOTSTRAP_SEED = 880088
T088_BOOTSTRAP_RESAMPLES = 20_000
T088_FORMAL_EXECUTIONS = T087_NATURAL_RECORD_COUNT * len(T088_ARMS)
T088_T087_FORMAL_NATURAL_EVIDENCE_SHA256 = (
    "7931a118a4bf921f695db769f05fd77a5ae364484f5646f02d5be05329ad297f"
)
T088_T087_FINAL_REPORT_SHA256 = (
    "9a0eba7eed03a1ba4801c3019e9d14a2aa61214a76299a63ed9ab5a0192f3ea0"
)
T088_T087_RETENTION_MANIFEST_SHA256 = (
    "5afe39476965a192c9bdd8d6bed121cd0169e68925cabfe9b8366ee320938adc"
)
T088_T085_SOURCE_SELECTION_SHA256 = (
    "d5c335cd6e1f96e72ae3b302eebca17a5f6531fa0aac97ee2febec2c41c2e752"
)
T088_REQUIRED_ARTIFACT_ROLES = frozenset(
    {
        "specification",
        "controller_definitions",
        "native_verifier",
        "formal_cohort",
        "canary_evidence",
        "formal_rows",
        "cost_rows",
        "statistics_report",
        "blind_bundle",
        "blind_provenance",
        "final_report",
    }
)


class T088IncompleteError(ValueError):
    """Required T088 evidence is absent, malformed, or inconsistent."""


def _identity(value: Mapping[str, object]) -> str:
    identity = value.get("selection_identity")
    if not isinstance(identity, str) or not identity:
        raise T088IncompleteError("selection_identity is missing")
    return identity


def _cohort(value: Mapping[str, object]) -> str:
    cohort = value.get("cohort")
    if cohort not in T087_COHORT_COUNTS:
        raise T088IncompleteError("row cohort is not one of T087 A/B/C")
    return str(cohort)


def _finite(value: object, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise T088IncompleteError(f"{label} must be finite numeric")
    result = float(value)
    if not math.isfinite(result):
        raise T088IncompleteError(f"{label} must be finite numeric")
    return result


def _sha_key(identity: str, domain: str) -> str:
    return hashlib.sha256(f"{domain}\n{identity}".encode()).hexdigest()


def _order_sha256(entries: Sequence[Mapping[str, object]]) -> str:
    encoded = json.dumps(
        [dict(entry) for entry in entries],
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def _artifact_reference(
    value: object, *, expected_sha256: str, expected_schema_id: str, label: str
) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise T088IncompleteError(f"{label} artifact identity is missing")
    required = {"path", "sha256", "size_bytes", "schema_id"}
    if (
        not required.issubset(value)
        or not isinstance(value.get("path"), str)
        or not value["path"]
        or value.get("sha256") != expected_sha256
        or value.get("schema_id") != expected_schema_id
        or isinstance(value.get("size_bytes"), bool)
        or not isinstance(value.get("size_bytes"), int)
        or value["size_bytes"] < 0
    ):
        raise T088IncompleteError(f"{label} artifact identity is not accepted")
    return value


def _source_selection_reference(value: object) -> Mapping[str, object]:
    """Validate the inherited T085 source identity in its established shape."""

    if not isinstance(value, Mapping) or set(value) != {
        "path",
        "sha256",
        "schema_id",
        "byte_count",
    }:
        raise T088IncompleteError("T087 inherited source selection identity is invalid")
    if (
        not isinstance(value["path"], str)
        or not value["path"]
        or value["sha256"] != T088_T085_SOURCE_SELECTION_SHA256
        or value["schema_id"] != "t085-native-selection-artifact-v1"
        or isinstance(value["byte_count"], bool)
        or not isinstance(value["byte_count"], int)
        or value["byte_count"] < 0
    ):
        raise T088IncompleteError("T087 inherited source selection identity is invalid")
    return value


def _binding_identity(binding: Mapping[str, object]) -> dict[str, object]:
    """Retain only the binding facts needed to associate downstream artifacts."""

    return {
        "ordered_cohort_entries_sha256": binding["ordered_cohort_entries_sha256"],
        "t087_artifacts": dict(binding["t087_artifacts"]),
        "source_selection_manifest_identity": dict(
            binding["source_selection_manifest_identity"]
        ),
        "t087_native_identity": dict(T087_NATIVE_IDENTITY),
    }


def validate_t088_t087_cohort_binding(
    binding: Mapping[str, object], cohort_rows: Iterable[Mapping[str, object]]
) -> list[dict[str, object]]:
    """Bind all T088 work to the accepted, ordered T087 formal evidence.

    The entry list is an order commitment derived from the hash-checked T087
    natural-evidence document.  It prevents a same-count replacement cohort
    from entering any plan, canary, arm, report, or retention workflow.
    """

    if (
        binding.get("schema_id") != "t088-t087-cohort-binding-v1"
        or binding.get("task_id") != T088_TASK_ID
        or binding.get("t087_task_id") != "T087"
        or binding.get("t087_native_identity") != T087_NATIVE_IDENTITY
    ):
        raise T088IncompleteError("T087 cohort binding provenance is invalid")
    artifacts = binding.get("t087_artifacts")
    if not isinstance(artifacts, Mapping) or set(artifacts) != {
        "formal_natural_evidence",
        "final_report",
        "retention_manifest",
    }:
        raise T088IncompleteError("T087 cohort binding artifact set is incomplete")
    _artifact_reference(
        artifacts["formal_natural_evidence"],
        expected_sha256=T088_T087_FORMAL_NATURAL_EVIDENCE_SHA256,
        expected_schema_id="t087-natural-evidence-v1",
        label="T087 formal natural evidence",
    )
    _artifact_reference(
        artifacts["final_report"],
        expected_sha256=T088_T087_FINAL_REPORT_SHA256,
        expected_schema_id="t087-dense-combat-diagnostics-report-v1",
        label="T087 final report",
    )
    _artifact_reference(
        artifacts["retention_manifest"],
        expected_sha256=T088_T087_RETENTION_MANIFEST_SHA256,
        expected_schema_id="t087-retention-manifest-v1",
        label="T087 retention manifest",
    )
    _source_selection_reference(binding.get("source_selection_manifest_identity"))
    entries = binding.get("ordered_cohort_entries")
    if not isinstance(entries, Sequence) or isinstance(entries, (str, bytes)):
        raise T088IncompleteError("T087 cohort binding ordered entries are missing")
    normalized = [
        {"selection_identity": _identity(entry), "cohort": _cohort(entry)}
        for entry in entries
        if isinstance(entry, Mapping)
    ]
    if len(normalized) != len(entries) or _order_sha256(normalized) != binding.get(
        "ordered_cohort_entries_sha256"
    ):
        raise T088IncompleteError("T087 cohort binding order commitment is invalid")
    cohort = _canonical_cohort_rows(cohort_rows)
    actual = [
        {"selection_identity": _identity(row), "cohort": _cohort(row)} for row in cohort
    ]
    if actual != normalized:
        raise T088IncompleteError(
            "cohort differs from accepted T087 identity/order binding"
        )
    source_identity = binding["source_selection_manifest_identity"]
    for row in cohort:
        if row.get("source_selection_manifest_identity") != source_identity:
            raise T088IncompleteError(
                "cohort row source provenance differs from T087 binding"
            )
        provenance = row.get("provenance")
        if (
            not isinstance(provenance, Mapping)
            or provenance.get("native_commit") != T087_NATIVE_IDENTITY["commit"]
        ):
            raise T088IncompleteError(
                "cohort row native provenance differs from T087 binding"
            )
    return cohort


def _canonical_cohort_rows(
    rows: Iterable[Mapping[str, object]],
) -> list[dict[str, object]]:
    """Validate the exact 413-record T087 membership while retaining its order."""

    result = [dict(row) for row in rows]
    if len(result) != T087_NATURAL_RECORD_COUNT:
        raise T088IncompleteError(
            f"formal cohort has {len(result)} records, expected {T087_NATURAL_RECORD_COUNT}"
        )
    counts = Counter(_cohort(row) for row in result)
    if dict(counts) != T087_COHORT_COUNTS:
        raise T088IncompleteError("formal cohort does not have exact T087 A/B/C counts")
    identities = [_identity(row) for row in result]
    if len(set(identities)) != len(identities):
        raise T088IncompleteError("formal cohort has duplicate selection identities")
    return result


def build_t088_formal_plan(
    cohort_rows: Iterable[Mapping[str, object]], *, cohort_binding: Mapping[str, object]
) -> dict[str, object]:
    """Build the deterministic 413 x 4 plan; this never runs an arm."""

    cohort = validate_t088_t087_cohort_binding(cohort_binding, cohort_rows)
    rows = [
        {
            "ordinal": ordinal,
            "arm": arm,
            "selection_identity": _identity(record),
            "cohort": _cohort(record),
        }
        for arm in T088_ARMS
        for ordinal, record in enumerate(cohort)
    ]
    return {
        "schema_id": "t088-formal-execution-plan-v1",
        "task_id": T088_TASK_ID,
        "execution_authorized": False,
        "arm_order": list(T088_ARMS),
        "t087_cohort_binding": _binding_identity(cohort_binding),
        "record_count": len(cohort),
        "planned_execution_count": len(rows),
        "rows": rows,
    }


def validate_t088_formal_plan(
    plan: Mapping[str, object],
    cohort_rows: Iterable[Mapping[str, object]],
    *,
    cohort_binding: Mapping[str, object],
) -> None:
    """Reject reordered, omitted, substituted, or prematurely-authorized plans."""

    expected = build_t088_formal_plan(cohort_rows, cohort_binding=cohort_binding)
    if (
        plan.get("schema_id") != expected["schema_id"]
        or plan.get("task_id") != T088_TASK_ID
    ):
        raise T088IncompleteError("formal plan schema/task identity is invalid")
    if plan.get("execution_authorized") is not False:
        raise T088IncompleteError("formal plan must not claim execution authorization")
    for name in (
        "arm_order",
        "t087_cohort_binding",
        "record_count",
        "planned_execution_count",
        "rows",
    ):
        if plan.get(name) != expected[name]:
            raise T088IncompleteError(
                "formal plan differs from canonical cohort/arm order"
            )


def select_t088_canary_records(
    cohort_rows: Iterable[Mapping[str, object]], *, cohort_binding: Mapping[str, object]
) -> dict[str, object]:
    """Select the required bounded canary surface from explicit pre-run facts.

    The task freezes required *properties*, not record identities.  The caller
    supplies those facts from retained T087 evidence; deterministic SHA ordering
    prevents outcome-driven choice among multiple qualifying records.
    """

    cohort = validate_t088_t087_cohort_binding(cohort_binding, cohort_rows)
    predicates = {
        "escaping_mugger": lambda row: row.get("is_escaping_mugger_case") is True,
        "ordinary_victory": lambda row: row.get("is_ordinary_victory") is True,
        "ordinary_loss": lambda row: row.get("is_ordinary_loss") is True,
        "later_act_or_boss": lambda row: row.get("is_later_act_or_boss") is True,
        "multiple_root_actions": lambda row: row.get("legal_root_action_count", 0) > 1,
    }
    selected: list[dict[str, object]] = []
    for role, predicate in predicates.items():
        choices = [row for row in cohort if predicate(row)]
        if not choices:
            raise T088IncompleteError(f"canary selection has no {role} record")
        chosen = min(
            choices, key=lambda row: _sha_key(_identity(row), f"T088-canary-{role}")
        )
        selected.append(
            {
                "role": role,
                "selection_identity": _identity(chosen),
                "cohort": _cohort(chosen),
                "selection_digest": _sha_key(_identity(chosen), f"T088-canary-{role}"),
            }
        )
    return {
        "schema_id": "t088-canary-selection-v1",
        "task_id": T088_TASK_ID,
        "execution_authorized": False,
        "t087_cohort_binding": _binding_identity(cohort_binding),
        "selected": selected,
    }


def validate_t088_canary_evidence(
    selection: Mapping[str, object],
    rows: Iterable[Mapping[str, object]],
    *,
    cohort_binding: Mapping[str, object],
) -> list[dict[str, object]]:
    """Validate a bounded canary without treating it as formal evidence.

    The function deliberately does not confer authorization or readiness.  It
    only makes omissions, substituted identities, learned calls, and malformed
    runtime facts impossible to overlook in a retained canary artifact.
    """

    if (
        selection.get("schema_id") != "t088-canary-selection-v1"
        or selection.get("task_id") != T088_TASK_ID
        or selection.get("execution_authorized") is not False
    ):
        raise T088IncompleteError("canary selection identity/authorization is invalid")
    entries = cohort_binding.get("ordered_cohort_entries")
    if not isinstance(entries, Sequence) or isinstance(entries, (str, bytes)):
        raise T088IncompleteError("canary cohort binding entries are missing")
    validate_t088_t087_cohort_binding(
        cohort_binding,
        (
            {
                "selection_identity": _identity(entry),
                "cohort": _cohort(entry),
                "source_selection_manifest_identity": cohort_binding.get(
                    "source_selection_manifest_identity"
                ),
                "provenance": {"native_commit": T087_NATIVE_IDENTITY["commit"]},
            }
            for entry in entries
            if isinstance(entry, Mapping)
        ),
    )
    # The selected records were bound when constructed.  Require the same
    # explicit binding at validation so a canary cannot be relabeled later.
    if selection.get("t087_cohort_binding") != _binding_identity(cohort_binding):
        raise T088IncompleteError("canary selection differs from T087 cohort binding")
    selected = selection.get("selected")
    if not isinstance(selected, Sequence) or isinstance(selected, (str, bytes)):
        raise T088IncompleteError("canary selection is malformed")
    required_roles = {
        "escaping_mugger",
        "ordinary_victory",
        "ordinary_loss",
        "later_act_or_boss",
        "multiple_root_actions",
    }
    if (
        len(selected) != len(required_roles)
        or any(not isinstance(item, Mapping) for item in selected)
        or {item.get("role") for item in selected if isinstance(item, Mapping)}
        != required_roles
    ):
        raise T088IncompleteError(
            "canary selection does not contain its exact five roles"
        )
    expected = {
        (arm, _identity(item))
        for item in selected
        if isinstance(item, Mapping)
        for arm in T088_ARMS
    }
    result = [dict(row) for row in rows]
    observed: set[tuple[str, str]] = set()
    for row in result:
        arm = row.get("arm")
        if arm not in T088_ARMS:
            raise T088IncompleteError("canary row arm is invalid")
        key = (str(arm), _identity(row))
        if key not in expected or key in observed:
            raise T088IncompleteError("canary rows are substituted or duplicated")
        if row.get("restore_public_legal_parity") is not True:
            raise T088IncompleteError("canary row lacks restore/public/legal parity")
        if not _valid_outcome(row.get("outcome")):
            raise T088IncompleteError("canary row lacks terminal outcome")
        for name in (
            "controller_definition_verified",
            "dense_diagnostic_recomputed",
            "native_game_mechanics_parity",
        ):
            if row.get(name) is not True:
                raise T088IncompleteError(f"canary row lacks {name}")
        if arm in {"A", "B"} and row.get("search_v2_parity_verified") is not True:
            raise T088IncompleteError("canary A/B row lacks Search-v2 parity evidence")
        if arm == "C" and row.get("beam_deterministic_replay_verified") is not True:
            raise T088IncompleteError("canary C row lacks Beam replay evidence")
        if (
            arm == "D"
            and row.get("progressive_bias_depth_gt_zero_verified") is not True
        ):
            raise T088IncompleteError("canary D row lacks beyond-root bias evidence")
        _validate_work(row)
        observed.add(key)
    if observed != expected:
        raise T088IncompleteError(
            "canary does not exercise every selected record and arm"
        )
    return result


def _valid_outcome(value: object) -> bool:
    return value in {"PLAYER_VICTORY", "PLAYER_LOSS"}


def _validate_work(row: Mapping[str, object]) -> None:
    counters = row.get("work_counters")
    if not isinstance(counters, Mapping):
        raise T088IncompleteError("work_counters are missing")
    for name in ("successor_transition_count", "action_execution_count", "model_calls"):
        value = counters.get(name)
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise T088IncompleteError(f"work_counters.{name} is invalid")
    if counters["model_calls"] != 0:
        raise T088IncompleteError("T088 row has learned model calls")
    _finite(row.get("wall_clock_time_s"), "wall_clock_time_s")


def _validate_t088_dense_execution_diagnostic(
    diagnostic: Mapping[str, object],
    *,
    identity: str,
    cohort: str,
    source_identity: Mapping[str, object],
) -> None:
    """Recompute amended T087 diagnostics without inheriting T087-only provenance.

    T087's full-row validator intentionally freezes that task's controller and
    search provenance.  T088 reuses its raw/equation semantics across four
    different controllers, so it must recompute the same dense payload while
    retaining each formal row's own provenance rather than pretending it was a
    T087 Search-v2@100 execution.
    """

    if (
        diagnostic.get("selection_identity") != identity
        or diagnostic.get("cohort") != cohort
        or not isinstance(diagnostic.get("entry"), Mapping)
        or not isinstance(diagnostic.get("terminal"), Mapping)
        or not isinstance(diagnostic.get("action_trace"), Sequence)
        or isinstance(diagnostic.get("action_trace"), (str, bytes))
    ):
        raise T088IncompleteError("execution row dense diagnostic is malformed")
    outcome = diagnostic.get("outcome")
    if not _valid_outcome(outcome):
        raise T088IncompleteError("execution row dense diagnostic lacks outcome")
    provenance = diagnostic.get("provenance")
    try:
        rebuilt = build_dense_diagnostic_row(
            selection_identity=identity,
            cohort=cohort,
            entry=diagnostic["entry"],  # type: ignore[arg-type]
            terminal=diagnostic["terminal"],  # type: ignore[arg-type]
            outcome=outcome,
            action_trace=diagnostic["action_trace"],  # type: ignore[arg-type]
            provenance=provenance if isinstance(provenance, Mapping) else None,
            source_selection_manifest_identity=source_identity,
        )
    except (T087IncompleteError, TypeError, ValueError) as exc:
        raise T088IncompleteError(
            "execution row dense diagnostic does not recompute"
        ) from exc
    if dict(diagnostic) != rebuilt:
        raise T088IncompleteError(
            "execution row dense diagnostic has scalar or raw-evidence drift"
        )


def validate_t088_execution_rows(
    rows: Iterable[Mapping[str, object]],
    cohort_rows: Iterable[Mapping[str, object]],
    *,
    cohort_binding: Mapping[str, object],
) -> list[dict[str, object]]:
    """Validate complete formal evidence before any report is allowed.

    This is intentionally all-or-nothing: partial per-arm data cannot become a
    report, a retry input, or a substitute cohort.
    """

    cohort = validate_t088_t087_cohort_binding(cohort_binding, cohort_rows)
    result = [dict(row) for row in rows]
    for arm in T088_ARMS:
        validate_t088_arm_execution_rows(
            (row for row in result if row.get("arm") == arm),
            cohort,
            arm=arm,
            cohort_binding=cohort_binding,
        )
    if len(result) != T088_FORMAL_EXECUTIONS:
        raise T088IncompleteError("formal execution count is not exactly 1652")
    return result


def validate_t088_arm_execution_rows(
    rows: Iterable[Mapping[str, object]],
    cohort_rows: Iterable[Mapping[str, object]],
    *,
    arm: str,
    cohort_binding: Mapping[str, object],
) -> list[dict[str, object]]:
    """Validate one complete, independently retained formal arm.

    This is the per-arm staging boundary.  It rejects a partial arm before it
    can be merged with other arms, while `validate_t088_execution_rows` is the
    all-four-arm final gate.
    """

    if arm not in T088_ARMS:
        raise T088IncompleteError("formal arm is invalid")
    cohort = validate_t088_t087_cohort_binding(cohort_binding, cohort_rows)
    expected = {_identity(record): _cohort(record) for record in cohort}
    source_identity = cohort_binding.get("source_selection_manifest_identity")
    if not isinstance(source_identity, Mapping):
        raise T088IncompleteError("formal source identity is unavailable")
    result = [dict(row) for row in rows]
    observed: dict[str, dict[str, object]] = {}
    for row in result:
        if row.get("arm") != arm:
            raise T088IncompleteError("row belongs to a different formal arm")
        identity = _identity(row)
        if identity in observed:
            raise T088IncompleteError("formal arm contains a retry or duplicate")
        if identity not in expected or _cohort(row) != expected[identity]:
            raise T088IncompleteError("formal arm row is not in the formal plan")
        if row.get("restore_public_legal_parity") is not True:
            raise T088IncompleteError("execution row lacks restore/public/legal parity")
        if not isinstance(row.get("controller_provenance"), Mapping):
            raise T088IncompleteError("execution row lacks controller provenance")
        if not isinstance(row.get("native_identity"), Mapping):
            raise T088IncompleteError("execution row lacks native identity")
        if not _valid_outcome(row.get("outcome")):
            raise T088IncompleteError(
                "execution row lacks authoritative terminal outcome"
            )
        diagnostics = row.get("dense_diagnostic")
        if not isinstance(diagnostics, Mapping):
            raise T088IncompleteError("execution row lacks dense diagnostic row")
        _validate_t088_dense_execution_diagnostic(
            diagnostics,
            identity=identity,
            cohort=expected[identity],
            source_identity=source_identity,
        )
        if (
            _identity(diagnostics) != identity
            or diagnostics.get("outcome") != row["outcome"]
        ):
            raise T088IncompleteError(
                "dense diagnostic identity/outcome differs from execution"
            )
        _validate_work(row)
        observed[identity] = row
    if set(observed) != set(expected) or len(result) != T087_NATURAL_RECORD_COUNT:
        raise T088IncompleteError(
            "formal arm does not cover exactly 413 cohort records"
        )
    return result


def _percentile(values: Sequence[float], q: float) -> float:
    index = (len(values) - 1) * q
    low, high = math.floor(index), math.ceil(index)
    if low == high:
        return values[low]
    return values[low] + (values[high] - values[low]) * (index - low)


def paired_bootstrap(values: Sequence[float]) -> dict[str, object]:
    """Fixed 20,000-resample paired bootstrap over exact record positions."""

    clean = [_finite(value, "paired bootstrap value") for value in values]
    if not clean:
        raise T088IncompleteError("paired bootstrap has no records")
    rng = random.Random(T088_BOOTSTRAP_SEED)
    samples = [
        sum(clean[rng.randrange(len(clean))] for _ in clean) / len(clean)
        for _ in range(T088_BOOTSTRAP_RESAMPLES)
    ]
    samples.sort()
    return {
        "seed": T088_BOOTSTRAP_SEED,
        "resample_count": T088_BOOTSTRAP_RESAMPLES,
        "sampling_unit": "exact_selection_identity",
        "observed_mean": mean(clean),
        "ci_95": [_percentile(samples, 0.025), _percentile(samples, 0.975)],
    }


def _mcnemar_exact(candidate_only: int, reference_only: int) -> float | None:
    total = candidate_only + reference_only
    if total == 0:
        return None
    smaller = min(candidate_only, reference_only)
    # Two-sided exact binomial probability under p=0.5, clamped for roundoff.
    probability = (
        sum(math.comb(total, index) for index in range(smaller + 1)) / 2**total
    )
    return min(1.0, 2.0 * probability)


def _diagnostic(row: Mapping[str, object], name: str) -> float:
    value = row.get("dense_diagnostic")
    if not isinstance(value, Mapping) or not isinstance(
        value.get("diagnostics"), Mapping
    ):
        raise T088IncompleteError("dense diagnostic payload is invalid")
    return _finite(value["diagnostics"].get(name), f"diagnostics.{name}")


def _paired_continuous(values: Sequence[float]) -> dict[str, object]:
    if not values:
        return {"sample_count": 0, "mean": None, "median": None, "bootstrap": None}
    return {
        "sample_count": len(values),
        "mean": mean(values),
        "median": median(values),
        "bootstrap": paired_bootstrap(values),
    }


def paired_t088_comparison(
    rows: Iterable[Mapping[str, object]], *, candidate_arm: str, reference_arm: str
) -> dict[str, object]:
    """Compute T088's paired binary and decomposed dense summaries."""

    if (
        candidate_arm not in T088_ARMS
        or reference_arm not in T088_ARMS
        or candidate_arm == reference_arm
    ):
        raise T088IncompleteError(
            "paired comparison requires two distinct tournament arms"
        )
    grouped: dict[str, dict[str, Mapping[str, object]]] = {}
    for row in rows:
        if row.get("arm") in {candidate_arm, reference_arm}:
            grouped.setdefault(_identity(row), {})[str(row["arm"])] = row
    if not grouped or any(
        set(pair) != {candidate_arm, reference_arm} for pair in grouped.values()
    ):
        raise T088IncompleteError("paired comparison is incomplete")
    candidate_only = reference_only = 0
    transitions: Counter[str] = Counter()
    win_delta: list[float] = []
    both_loss: list[float] = []
    both_win: list[float] = []
    margins: list[float] = []
    cohort_loss: dict[str, list[float]] = {cohort: [] for cohort in T087_COHORT_COUNTS}
    cohort_win: dict[str, list[float]] = {cohort: [] for cohort in T087_COHORT_COUNTS}
    cohort_margin: dict[str, list[float]] = {
        cohort: [] for cohort in T087_COHORT_COUNTS
    }
    by_cohort: dict[str, Counter[str]] = {
        cohort: Counter() for cohort in T087_COHORT_COUNTS
    }
    for identity in sorted(grouped):
        candidate, reference = (
            grouped[identity][candidate_arm],
            grouped[identity][reference_arm],
        )
        c_win, r_win = (
            candidate["outcome"] == "PLAYER_VICTORY",
            reference["outcome"] == "PLAYER_VICTORY",
        )
        win_delta.append(float(c_win) - float(r_win))
        label = ("win" if r_win else "loss") + "->" + ("win" if c_win else "loss")
        transitions[label] += 1
        by_cohort[_cohort(candidate)][label] += 1
        candidate_only += int(c_win and not r_win)
        reference_only += int(r_win and not c_win)
        margin = _diagnostic(candidate, "combat_terminal_margin_v1") - _diagnostic(
            reference, "combat_terminal_margin_v1"
        )
        margins.append(margin)
        cohort_margin[_cohort(candidate)].append(margin)
        if not c_win and not r_win:
            loss_delta = _diagnostic(
                candidate, "enemy_hp_remaining_fraction"
            ) - _diagnostic(reference, "enemy_hp_remaining_fraction")
            both_loss.append(loss_delta)
            cohort_loss[_cohort(candidate)].append(loss_delta)
        if c_win and r_win:
            win_delta_value = _diagnostic(
                candidate, "player_hp_remaining_fraction_of_max"
            ) - _diagnostic(reference, "player_hp_remaining_fraction_of_max")
            both_win.append(win_delta_value)
            cohort_win[_cohort(candidate)].append(win_delta_value)
    binary = paired_bootstrap(win_delta)
    lower, upper = binary["ci_95"]  # type: ignore[misc]
    outcome_class = (
        "CLEAR_OUTCOME_SUPERIORITY"
        if lower > 0
        else "CLEAR_OUTCOME_HARM"
        if upper < 0
        else "OUTCOME_INCONCLUSIVE"
    )
    loss_summary, win_summary = (
        _paired_continuous(both_loss),
        _paired_continuous(both_win),
    )
    dense = "DENSE_MIXED"
    loss_ci = (
        loss_summary.get("bootstrap", {}).get("ci_95")
        if isinstance(loss_summary.get("bootstrap"), Mapping)
        else None
    )
    win_ci = (
        win_summary.get("bootstrap", {}).get("ci_95")
        if isinstance(win_summary.get("bootstrap"), Mapping)
        else None
    )
    loss_good = (
        isinstance(loss_ci, Sequence) and loss_summary["mean"] < 0 and loss_ci[1] < 0
    )
    win_ok = loss_summary is not None and (
        win_summary["sample_count"] < 8
        or (
            win_summary["mean"] >= 0
            or (isinstance(win_ci, Sequence) and win_ci[0] <= 0 <= win_ci[1])
        )
    )
    if loss_good and win_ok:
        dense = "DENSE_DIRECTIONALLY_BETTER"
    return {
        "schema_id": "t088-paired-comparison-v1",
        "candidate_arm": candidate_arm,
        "reference_arm": reference_arm,
        "record_count": len(grouped),
        "binary_outcome": {
            "candidate_wins": sum(
                row["outcome"] == "PLAYER_VICTORY"
                for pair in grouped.values()
                for arm, row in pair.items()
                if arm == candidate_arm
            ),
            "reference_wins": sum(
                row["outcome"] == "PLAYER_VICTORY"
                for pair in grouped.values()
                for arm, row in pair.items()
                if arm == reference_arm
            ),
            "candidate_win_reference_loss": candidate_only,
            "candidate_loss_reference_win": reference_only,
            "win_rate_difference": binary,
            "exact_mcnemar_two_sided_p": _mcnemar_exact(candidate_only, reference_only),
            "classification": outcome_class,
        },
        "dense_diagnostics": {
            "both_loss_enemy_hp_remaining_fraction_delta": loss_summary,
            "both_win_player_hp_remaining_fraction_delta": win_summary,
            "all_record_combat_terminal_margin_v1_delta_diagnostic_only": _paired_continuous(
                margins
            ),
            "classification": dense,
        },
        "outcome_transitions": dict(transitions),
        "cohort_breakdown": {
            cohort: {
                "outcome_transitions": dict(by_cohort[cohort]),
                "both_loss_enemy_hp_remaining_fraction_delta": _paired_continuous(
                    cohort_loss[cohort]
                ),
                "both_win_player_hp_remaining_fraction_delta": _paired_continuous(
                    cohort_win[cohort]
                ),
                "all_record_combat_terminal_margin_v1_delta_diagnostic_only": _paired_continuous(
                    cohort_margin[cohort]
                ),
            }
            for cohort in T087_COHORT_COUNTS
        },
    }


def select_t088_blind_audit(
    rows: Iterable[Mapping[str, object]], *, candidate_arm: str, reference_arm: str
) -> dict[str, object]:
    """Choose up to 8/8/8 disjoint rows and hide arm assignment by SHA parity."""

    paired: dict[str, dict[str, Mapping[str, object]]] = {}
    for row in rows:
        if row.get("arm") in {candidate_arm, reference_arm}:
            paired.setdefault(_identity(row), {})[str(row["arm"])] = row
    if any(set(value) != {candidate_arm, reference_arm} for value in paired.values()):
        raise T088IncompleteError("blind audit pairs are incomplete")
    discordant, losses, wins = [], [], []
    for identity, pair in paired.items():
        candidate, reference = pair[candidate_arm], pair[reference_arm]
        c_win, r_win = (
            candidate["outcome"] == "PLAYER_VICTORY",
            reference["outcome"] == "PLAYER_VICTORY",
        )
        if c_win != r_win:
            discordant.append((0.0, identity, pair))
        elif not c_win:
            losses.append(
                (
                    abs(
                        _diagnostic(candidate, "enemy_hp_remaining_fraction")
                        - _diagnostic(reference, "enemy_hp_remaining_fraction")
                    ),
                    identity,
                    pair,
                )
            )
        else:
            wins.append(
                (
                    abs(
                        _diagnostic(candidate, "player_hp_remaining_fraction_of_max")
                        - _diagnostic(reference, "player_hp_remaining_fraction_of_max")
                    ),
                    identity,
                    pair,
                )
            )
    chosen: list[tuple[str, str, Mapping[str, object]]] = []
    for stratum, candidates in (
        ("outcome_discordant", discordant),
        ("both_loss", losses),
        ("both_win", wins),
    ):
        ordered = sorted(
            candidates,
            key=lambda item: (-item[0], _sha_key(item[1], f"T088-blind-{stratum}")),
        )[:8]
        chosen.extend((stratum, identity, pair) for _, identity, pair in ordered)
    public, hidden = [], []
    for trace_id, (stratum, identity, pair) in enumerate(chosen):
        x_arm = (
            candidate_arm
            if int(_sha_key(identity, "T088-blind-label")[-1], 16) % 2 == 0
            else reference_arm
        )
        y_arm = reference_arm if x_arm == candidate_arm else candidate_arm

        def trace(
            arm: str, *, source: Mapping[str, Mapping[str, object]] = pair
        ) -> object:
            raw = source[arm].get("public_trace")
            if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes)):
                raise T088IncompleteError(
                    "blind audit requires an explicit public trace"
                )
            return list(raw)

        public.append(
            {
                "trace_id": trace_id,
                "stratum": stratum,
                "X": trace(x_arm),
                "Y": trace(y_arm),
            }
        )
        hidden.append(
            {
                "trace_id": trace_id,
                "selection_identity": identity,
                "stratum": stratum,
                "X_arm": x_arm,
                "Y_arm": y_arm,
            }
        )
    return {
        "bundle": {
            "schema_id": "t088-blind-audit-bundle-v1",
            "rubric": build_review_rubric(),
            "pairs": public,
        },
        "hidden_provenance": {
            "schema_id": "t088-blind-audit-hidden-provenance-v1",
            "pairs": hidden,
        },
    }


def validate_t088_retention_manifest(manifest: Mapping[str, object]) -> None:
    """Validate artifact identity surface without trusting names or defaults."""

    if (
        manifest.get("schema_id") != "t088-retention-manifest-v1"
        or manifest.get("task_id") != T088_TASK_ID
    ):
        raise T088IncompleteError("retention manifest schema/task identity is invalid")
    artifacts = manifest.get("artifact_references")
    if (
        not isinstance(artifacts, Mapping)
        or set(artifacts) != T088_REQUIRED_ARTIFACT_ROLES
    ):
        raise T088IncompleteError("retention manifest artifact roles are incomplete")
    for role, reference in artifacts.items():
        if not isinstance(reference, Mapping):
            raise T088IncompleteError(f"retention artifact {role} is malformed")
        required = {"path", "sha256", "size_bytes", "schema_id"}
        if (
            not required.issubset(reference)
            or not isinstance(reference.get("path"), str)
            or not isinstance(reference.get("schema_id"), str)
        ):
            raise T088IncompleteError(
                f"retention artifact {role} lacks identity fields"
            )
        digest, size = reference.get("sha256"), reference.get("size_bytes")
        if (
            not isinstance(digest, str)
            or len(digest) != 64
            or any(char not in "0123456789abcdef" for char in digest)
        ):
            raise T088IncompleteError(f"retention artifact {role} has invalid SHA-256")
        if isinstance(size, bool) or not isinstance(size, int) or size < 0:
            raise T088IncompleteError(
                f"retention artifact {role} has invalid byte count"
            )


def validate_t088_final_report(
    report: Mapping[str, object],
    *,
    formal_rows: Iterable[Mapping[str, object]],
    cohort_rows: Iterable[Mapping[str, object]],
    cohort_binding: Mapping[str, object],
) -> None:
    """Require a complete formal matrix and all six precommitted comparisons."""

    if (
        report.get("schema_id") != "t088-final-tournament-report-v1"
        or report.get("task_id") != T088_TASK_ID
    ):
        raise T088IncompleteError("final report schema/task identity is invalid")
    validate_t088_execution_rows(
        formal_rows, cohort_rows, cohort_binding=cohort_binding
    )
    comparisons = report.get("paired_comparisons")
    if not isinstance(comparisons, Sequence) or isinstance(comparisons, (str, bytes)):
        raise T088IncompleteError("final report paired comparisons are missing")
    required_pairs = {
        ("B", "A"),
        ("C", "A"),
        ("D", "A"),
        ("B", "C"),
        ("B", "D"),
        ("C", "D"),
    }
    actual_pairs = {
        (item.get("candidate_arm"), item.get("reference_arm"))
        for item in comparisons
        if isinstance(item, Mapping)
    }
    if actual_pairs != required_pairs:
        raise T088IncompleteError(
            "final report does not contain exactly six required paired comparisons"
        )
    if report.get("terminal_classification") not in {
        "STRONGER_NONLEARNED_COMBAT_BASELINE_IDENTIFIED",
        "NO_CHALLENGER_CLEARS_PROMOTION_GATE",
        "TOURNAMENT_TIE_REQUIRES_PLANNER_DECISION",
        "INCOMPLETE",
    }:
        raise T088IncompleteError("final report terminal classification is invalid")


__all__ = [
    "T088_ARMS",
    "T088_BOOTSTRAP_RESAMPLES",
    "T088_BOOTSTRAP_SEED",
    "T088_FORMAL_EXECUTIONS",
    "T088IncompleteError",
    "build_t088_formal_plan",
    "paired_bootstrap",
    "paired_t088_comparison",
    "select_t088_blind_audit",
    "select_t088_canary_records",
    "validate_t088_arm_execution_rows",
    "validate_t088_canary_evidence",
    "validate_t088_execution_rows",
    "validate_t088_final_report",
    "validate_t088_formal_plan",
    "validate_t088_retention_manifest",
    "validate_t088_t087_cohort_binding",
]
