"""Read-only localization of the frozen accepted T103 failure population.

Only accepted public payloads and T103 structured observations inform classes.
Native exceptions are hashed for audit; their words never inform a decision.
"""

from __future__ import annotations

import json
import math
import time
from collections import Counter
from collections.abc import Mapping, Sequence

from sts_combat_rl.sim.t096_public_information_sampler import (
    _FORBIDDEN_PRIVATE_KEY_FRAGMENTS,
    _REQUIRED_PROJECTION_KEYS_V2,
    validate_public_information_projection,
)
from sts_combat_rl.sim.t099_particle_search_bridge import _action_identity
from sts_combat_rl.sim.t101_particle_convergence import derive_t101_sampler_seed
from sts_combat_rl.sim.t103_particle_diagnostic import (
    T103NativeRecordRunner,
    _bridge_observations,
    exception_signature,
)

PART_A_CLASSES = (
    "ANCHOR_CAPTURE_DRIFT",
    "PARTICLE_PUBLIC_STATE_DRIFT",
    "STRUCTURED_PARITY_FLAG_INCONSISTENCY",
    "ORDERED_PUBLIC_ACTION_DRIFT",
    "PROJECTION_FAILURE_LOCALIZATION_OPAQUE",
)
PART_B_CLASSES = (
    "PRE_BRIDGE_CONTEXT_FAILURE",
    "STANDALONE_SAMPLER_FAILURE",
    "STANDALONE_SAMPLER_PUBLIC_FIDELITY_FAILURE",
    "BRIDGE_FAILURE_AFTER_STANDALONE_SAMPLER_SUCCESS",
    "STRUCTURED_MAPPING_FAILURE",
    "STRUCTURED_SEARCH_SETUP_OR_EXECUTION_FAILURE",
    "STRUCTURED_ROOT_REPORT_FAILURE",
    "NATIVE_STAGE_OPAQUE",
)
INTERNAL_STAGES = (
    "monolithic_sample_construction",
    "monolithic_public_fidelity_validation",
    "occurrence_mapping",
    "search_setup",
    "search_execution",
    "sanitized_root_report",
)
SOURCE_COUNTS = {"A": 93, "B": 192, "C": 128}
_HIDDEN_INTENT_FIELDS = frozenset(
    {
        "attacking",
        "intent_category",
        "current_move",
        "move_id",
        "move_base_damage",
        "move_hits",
    }
)
CLASS_COUNTS = {
    "PUBLIC_PROJECTION_PARITY_FAILURE": {"A": 4, "B": 3, "C": 63},
    "OPAQUE_BRIDGE_FAILURE": {"A": 89, "B": 189, "C": 65},
}


class T104IncompleteError(ValueError):
    """Required evidence is unavailable or inconsistent; fail closed."""


def validate_t103_population(rows: object) -> list[dict[str, object]]:
    if not isinstance(rows, list) or len(rows) != 413:
        raise T104IncompleteError("accepted T103 population is not complete")
    identities: set[str] = set()
    counts: dict[str, Counter] = {key: Counter() for key in CLASS_COUNTS}
    result = []
    for row in rows:
        if not isinstance(row, Mapping):
            raise T104IncompleteError("accepted T103 row is malformed")
        identity = row.get("selection_identity")
        kind = row.get("diagnostic_class")
        stratum = row.get("stratum")
        if (
            not isinstance(identity, str)
            or not identity
            or identity in identities
            or kind not in CLASS_COUNTS
            or stratum not in SOURCE_COUNTS
            or row.get("replicate_index") != 0
            or row.get("sampler_seed") != derive_t101_sampler_seed(identity, 0)
            or row.get("particle_count") != 2
            or row.get("search_simulations") != 400
            or row.get("include_potions") is not False
            or row.get("admitted") is not False
        ):
            raise T104IncompleteError("accepted T103 identity/configuration changed")
        identities.add(identity)
        counts[kind][stratum] += 1
        result.append(dict(row))
    if {key: dict(value) for key, value in counts.items()} != CLASS_COUNTS:
        raise T104IncompleteError("accepted T103 70/343 census changed")
    return result


def public_projection(value: object) -> dict[str, object] | None:
    """Retain only a public JSON tree, including incomplete public fields.

    Reject the whole observation on any private/malformed nested key. Error
    messages and rejected key names are deliberately never retained as paths.
    T014 candidate bits are replay identities and are omitted from public output.
    """

    if not isinstance(value, Mapping):
        return None
    allowed = _REQUIRED_PROJECTION_KEYS_V2 | {
        "external_base_commit",
        "patch_identity",
        "visible_act_boss",
        "visible_map_graph",
        "current_map_node",
        "immediately_legal_routes",
        "screen_payload",
        "candidate_actions",
    }
    if any(not isinstance(key, str) or key not in allowed for key in value):
        return None

    def clean(node: object) -> object:
        if isinstance(node, Mapping):
            result = {}
            for key, child in node.items():
                if not isinstance(key, str) or any(
                    fragment in key.casefold()
                    for fragment in (
                        *_FORBIDDEN_PRIVATE_KEY_FRAGMENTS,
                        "hidden",
                        "future",
                    )
                ):
                    raise T104IncompleteError("unsafe public observation")
                if key == "bits":
                    continue
                result[key] = clean(child)
            return result
        if isinstance(node, list):
            return [clean(child) for child in node]
        if node is None or isinstance(node, (str, bool, int)):
            if isinstance(node, str) and "bits=" in node:
                raise T104IncompleteError("unsafe public observation")
            return node
        if isinstance(node, float) and math.isfinite(node):
            return node
        raise T104IncompleteError("malformed public observation")

    try:
        cleaned = clean(value)
        visibility = cleaned.get("visibility", {})
        intent = (
            visibility.get("enemy_intent", {})
            if isinstance(visibility, Mapping)
            else {}
        )
        if isinstance(intent, Mapping) and intent.get("classification") == "hidden":
            monsters = cleaned.get("monsters")
            if (
                not isinstance(monsters, list)
                or not monsters
                or any(
                    not isinstance(m, Mapping) or _HIDDEN_INTENT_FIELDS & set(m)
                    for m in monsters
                )
            ):
                return None
        return cleaned
    except T104IncompleteError:
        return None


def public_differences(left: object, right: object) -> list[dict[str, object]]:
    """Canonical public paths, with stable JSON types and array order."""

    a, b = public_projection(left), public_projection(right)
    if a is None or b is None:
        return []
    result: list[dict[str, object]] = []
    missing = object()

    def kind(value: object) -> str:
        if value is missing:
            return "missing"
        if value is None:
            return "null"
        if isinstance(value, bool):
            return "boolean"
        if isinstance(value, int):
            return "integer"
        if isinstance(value, float):
            return "number"
        if isinstance(value, str):
            return "string"
        return "object" if isinstance(value, dict) else "array"

    def visit(x: object, y: object, path: str) -> None:
        xkind, ykind = kind(x), kind(y)
        if xkind != ykind or x is missing or y is missing:
            reason = (
                "missing_left"
                if x is missing
                else "missing_right"
                if y is missing
                else "type_difference"
            )
            result.append(
                {
                    "path": path,
                    "difference": reason,
                    "left_type": xkind,
                    "right_type": ykind,
                }
            )
        elif isinstance(x, dict) and isinstance(y, dict):
            for key in sorted(set(x) | set(y)):
                escaped = key.replace("~", "~0").replace("/", "~1")
                visit(x.get(key, missing), y.get(key, missing), f"{path}/{escaped}")
        elif isinstance(x, list) and isinstance(y, list):
            for index in range(max(len(x), len(y))):
                visit(
                    x[index] if index < len(x) else missing,
                    y[index] if index < len(y) else missing,
                    f"{path}/{index}",
                )
        elif x != y:
            result.append(
                {
                    "path": path,
                    "difference": "unequal",
                    "left_type": xkind,
                    "right_type": ykind,
                }
            )

    visit(a, b, "")
    return result


def localize_projection(p0: object, report: object) -> dict[str, object]:
    report = report if isinstance(report, Mapping) else {}
    anchor = public_projection(report.get("anchor_public_information_projection"))
    current = public_projection(p0)
    particles = report.get("particles")
    particles = particles if isinstance(particles, list) else []
    projections = [
        public_projection(p.get("public_information_projection"))
        if isinstance(p, Mapping)
        else None
        for p in particles
    ]
    diffs: list[dict[str, object]] = []
    if current is not None and anchor is not None:
        diffs.extend(
            {**d, "boundary": "P0 -> A", "particle_index": None}
            for d in public_differences(current, anchor)
        )
    for index, projection in enumerate(projections):
        if anchor is not None and projection is not None:
            diffs.extend(
                {**d, "boundary": "A -> Pi", "particle_index": index}
                for d in public_differences(anchor, projection)
            )
    action_roots = {"ordered_public_legal_actions", "candidate_actions"}
    payload_diffs = [
        d for d in diffs if str(d["path"]).split("/")[1] not in action_roots
    ]
    flag_failed = any(
        isinstance(p, Mapping) and p.get("public_projection_equal") is False
        for p in particles
    )
    compared_payloads_established = (
        bool(current)
        and bool(anchor)
        and bool(projections)
        and all(bool(p) for p in projections)
    )
    all_equal = compared_payloads_established and not diffs
    action_evidence = []
    anchor_actions = public_projection(
        {
            "ordered_public_legal_actions": report.get(
                "anchor_ordered_public_legal_actions"
            )
        }
    )
    if (
        anchor_actions is not None
        and anchor is not None
        and isinstance(anchor.get("ordered_public_legal_actions"), list)
        and isinstance(report.get("anchor_ordered_public_legal_actions"), list)
    ):
        action_evidence.extend(
            public_differences(
                {
                    "ordered_public_legal_actions": anchor.get(
                        "ordered_public_legal_actions"
                    )
                },
                anchor_actions,
            )
        )
    for index, particle in enumerate(particles):
        if isinstance(particle, Mapping) and anchor_actions is not None:
            action_evidence.extend(
                {**d, "particle_index": index}
                for d in public_differences(
                    anchor_actions,
                    {
                        "ordered_public_legal_actions": particle.get(
                            "ordered_public_legal_actions"
                        )
                    },
                )
            )
    action_failed = any(
        isinstance(p, Mapping) and p.get("ordered_public_legal_actions_equal") is False
        for p in particles
    )

    def ordered_surface(actions: object) -> list[dict[str, object]] | None:
        sanitized = public_projection({"ordered_public_legal_actions": actions})
        public_actions = (
            sanitized.get("ordered_public_legal_actions") if sanitized else None
        )
        try:
            if not isinstance(public_actions, list):
                return None
            public_actions = [
                _action_identity(action, "T104 ordered public surface")
                for action in public_actions
            ]
        except ValueError:
            return None
        occurrences: Counter = Counter()
        result = []
        for position, identity in enumerate(public_actions):
            key = json.dumps(identity, sort_keys=True, separators=(",", ":"))
            result.append(
                {
                    "position": position,
                    "occurrence": occurrences[key],
                    "identity": identity,
                }
            )
            occurrences[key] += 1
        return result

    action_surfaces = {
        "P0": ordered_surface(current.get("ordered_public_legal_actions"))
        if current
        else None,
        "A": ordered_surface(report.get("anchor_ordered_public_legal_actions")),
        "Pi": [
            ordered_surface(p.get("ordered_public_legal_actions"))
            if isinstance(p, Mapping)
            else None
            for p in particles
        ],
    }
    order_evidence = []
    for boundary, left, right in [
        ("P0 -> A", action_surfaces["P0"], action_surfaces["A"]),
        *[
            (f"A -> Pi/{i}", action_surfaces["A"], p)
            for i, p in enumerate(action_surfaces["Pi"])
        ],
    ]:
        if left is None or right is None:
            order_evidence.append({"boundary": boundary, "status": "unknown"})
        else:
            left_ids = [json.dumps(a["identity"], sort_keys=True) for a in left]
            right_ids = [json.dumps(a["identity"], sort_keys=True) for a in right]
            order_evidence.append(
                {
                    "boundary": boundary,
                    "identity_occurrence_counts_equal": Counter(left_ids)
                    == Counter(right_ids),
                    "ordered_identity_sequence_equal": left_ids == right_ids,
                }
            )
    observed_action_drift = any(
        e.get("ordered_identity_sequence_equal") is False for e in order_evidence
    )
    # A failure flag cannot establish an action difference. Later action
    # localization additionally requires every earlier public payload boundary
    # to be observed; unavailable comparisons do not establish equality.
    action_comparisons_established = all(
        "ordered_identity_sequence_equal" in e for e in order_evidence
    )
    action_flag_inconsistent = (
        action_failed and action_comparisons_established and not observed_action_drift
    )
    if current and anchor and any(d["boundary"] == "P0 -> A" for d in payload_diffs):
        cls = PART_A_CLASSES[0]
    elif (
        bool(current)
        and anchor == current
        and any(
            d["boundary"] == "A -> Pi" and bool(projections[d["particle_index"]])
            for d in payload_diffs
        )
    ):
        cls = PART_A_CLASSES[1]
    elif all_equal and (flag_failed or action_flag_inconsistent):
        cls = PART_A_CLASSES[2]
    elif compared_payloads_established and not payload_diffs and observed_action_drift:
        cls = PART_A_CLASSES[3]
    else:
        cls = PART_A_CLASSES[4]
    return {
        "part_a_class": cls,
        "public_projection_differences": diffs,
        "public_field_families": sorted({str(d["path"]).split("/")[1] for d in diffs}),
        "particles_affected": sorted(
            {d["particle_index"] for d in diffs if d["particle_index"] is not None}
        ),
        "ordered_action_differences": action_evidence,
        "ordered_action_surfaces": action_surfaces,
        "ordered_action_identity_occurrence_order_evidence": order_evidence,
        "public_observations": {"P0": current, "A": anchor, "Pi": projections},
        "structured_public_parity_failed": flag_failed,
        "structured_action_parity_failed": action_failed,
    }


def localize_stages(
    *,
    baseline_reproduced: bool,
    bridge_failed: bool,
    pre_bridge_passed: bool,
    sampler_status: str,
    structured: Mapping[str, object],
) -> dict[str, object]:
    """Separate observed class from monolithic repair observability."""

    stages = dict.fromkeys(INTERNAL_STAGES, "unknown")
    structured = {
        key: value
        for key, value in structured.items()
        if key
        in {
            "mapping_complete",
            "mapping_ambiguous",
            "search_execution_reached",
            "search_execution_failed",
            "required_root_values_valid",
        }
        and isinstance(value, bool)
    }
    # These are precisely the previously accepted T103 fields. No new native
    # stage-name convention or arbitrary exception attributes are interpreted.
    mapping_failed = (
        structured.get("mapping_complete") is False
        or structured.get("mapping_ambiguous") is True
    )
    mapping_passed = (
        structured.get("mapping_complete") is True
        and structured.get("mapping_ambiguous") is False
    )
    if mapping_failed:
        stages["occurrence_mapping"] = "failed"
    elif mapping_passed:
        stages["occurrence_mapping"] = "completed"
    if structured.get("search_execution_reached") is True:
        stages["search_setup"] = "completed"
        stages["search_execution"] = (
            "failed" if structured.get("search_execution_failed") is True else "reached"
        )
    if structured.get("required_root_values_valid") is False:
        stages["sanitized_root_report"] = "failed"
    elif structured.get("required_root_values_valid") is True:
        stages["sanitized_root_report"] = "completed"
    boundary = None
    if not pre_bridge_passed:
        cls = PART_B_CLASSES[0]
    elif mapping_failed:
        cls, boundary = PART_B_CLASSES[4], "occurrence_mapping"
    elif (
        mapping_passed
        and structured.get("search_execution_reached") is True
        and structured.get("search_execution_failed") is True
    ):
        cls, boundary = PART_B_CLASSES[5], "search_execution"
    elif (
        mapping_passed
        and structured.get("search_execution_reached") is True
        and structured.get("required_root_values_valid") is False
    ):
        cls, boundary = PART_B_CLASSES[6], "sanitized_root_report"
    elif sampler_status == "failed":
        cls = PART_B_CLASSES[1]
    elif sampler_status == "public_fidelity_failed":
        cls = PART_B_CLASSES[2]
    elif sampler_status == "succeeded" and bridge_failed:
        cls = PART_B_CLASSES[3]
    else:
        cls = PART_B_CLASSES[7]
    missing = [
        name for name in INTERNAL_STAGES if stages[name] in {"unknown", "reached"}
    ]
    needed = (
        baseline_reproduced and bridge_failed and boundary is None and bool(missing)
    )
    # A standalone failure is an independent surface, never proof of the
    # monolithic bridge's own repair boundary or internal sampler outcome.
    return {
        "part_b_class": cls,
        "internal_stage_status": stages,
        "concrete_monolithic_repair_boundary": boundary,
        "native_observability_required": bool(needed),
        "native_observability_missing_stages": missing if needed else [],
        "structured_stage_facts": dict(structured),
        "pre_bridge_passed": pre_bridge_passed,
        "full_bridge_failed": bridge_failed,
        "standalone_sampler_status": sampler_status,
    }


class _SamplerAdapter:
    """Route the same guarded restore boundary to only the standalone probe."""

    def __init__(self, adapter: object, observation: dict[str, object]) -> None:
        self.adapter, self.observation = adapter, observation

    def __getattr__(self, name: str) -> object:
        return getattr(self.adapter, name)

    def sample_hidden_future_particles_search(
        self, snapshot: object, **kwargs: object
    ) -> object:
        self.observation["attempted"] = True
        started = time.perf_counter()
        try:
            anchor = self.adapter.t096_public_information_projection(snapshot)
            particles = self.adapter.sample_hidden_future_particles(
                snapshot,
                sampler_seed=kwargs["sampler_seed"],
                particle_start=0,
                particle_count=2,
            )
        except Exception as exc:  # noqa: BLE001 -- native exception types vary
            self.observation.update(status="failed", **exception_signature(exc))
        else:
            self.observation.update(standalone_fidelity(anchor, particles))
        self.observation["wall_clock_time_s"] = time.perf_counter() - started
        # The enclosing T103 runner is used for its shared pre-call guard only;
        # this sentinel is never the full-bridge baseline or scientific evidence.
        raise _StandaloneProbeComplete()


class _StandaloneProbeComplete(Exception):
    pass


def standalone_fidelity(anchor: object, particles: object) -> dict[str, object]:
    """The accepted T098 index/public-fidelity checks, bounded to exactly N=2.

    Check the required private audit digest transiently, never retain it or
    next-card values, and impose no T098 N=32 witness/diversity requirement.
    """

    complete = isinstance(particles, list) and len(particles) == 2
    index_valid = complete and all(
        isinstance(p, Mapping)
        and isinstance(p.get("particle_index"), int)
        and not isinstance(p.get("particle_index"), bool)
        and p["particle_index"] == index
        for index, p in enumerate(particles)
    )
    audit_schema_valid = complete and all(
        isinstance(p, Mapping)
        and isinstance(p.get("hidden_future_fingerprint"), str)
        and bool(p["hidden_future_fingerprint"])
        for p in particles
    )
    public_valid = False
    legal_valid = False
    try:
        public_anchor = validate_public_information_projection(anchor)
        sanitized_anchor = public_projection(public_anchor)
        if complete and sanitized_anchor is not None:
            projected = [
                validate_public_information_projection(
                    p.get("public_information_projection")
                )
                for p in particles
                if isinstance(p, Mapping)
            ]
            public_valid = (
                public_anchor.get("information_fidelity") == "supported"
                and len(projected) == 2
                and all(
                    public_projection(p) is not None and p == public_anchor
                    for p in projected
                )
            )
            legal_valid = len(projected) == 2 and all(
                p.get("ordered_public_legal_actions")
                == public_anchor.get("ordered_public_legal_actions")
                for p in projected
            )
            visibility = public_anchor.get("visibility", {})
            intent = visibility.get("enemy_intent", {})
            if intent.get("classification") == "hidden":
                public_valid = public_valid and all(
                    "last_move_id" in m and "public_statuses" in m
                    for m in public_anchor.get("monsters", [])
                )
    except (ValueError, TypeError, AttributeError):
        public_valid = False
    status = (
        "failed"
        if not complete or not index_valid or not audit_schema_valid
        else "succeeded"
        if public_valid and legal_valid
        else "public_fidelity_failed"
    )
    return {
        "status": status,
        "particle_rows_returned": len(particles)
        if isinstance(particles, list)
        else None,
        "batch_complete": complete,
        "particle_indices_valid": bool(index_valid),
        "private_audit_schema_valid": bool(audit_schema_valid),
        "public_fidelity": public_valid,
        "ordered_public_action_parity": legal_valid,
    }


class T104NativeRecordRunner:
    """Two separately restored adapters; never reuse sampler-mutated state."""

    def __init__(self, **runner_inputs: object) -> None:
        self.inputs = runner_inputs

    def diagnose(
        self,
        record: Mapping[str, object],
        *,
        accepted: Mapping[str, object],
        source_ordinal: int,
        selection_digest: str,
        probe_order: tuple[str, str] = ("bridge", "sampler"),
    ) -> dict[str, object]:
        if probe_order not in (("bridge", "sampler"), ("sampler", "bridge")):
            raise T104IncompleteError("invalid independent probe order")
        captured: dict[str, object] = {}
        sampler: dict[str, object] = {"attempted": False, "status": "unknown"}
        baseline: dict[str, object] = {}
        started = time.perf_counter()

        def observe(
            event: str, _adapter: object, _snapshot: object, payload: object
        ) -> None:
            if event == "pre_bridge":
                raw = getattr(payload, "canonical_payload", None)
                try:
                    captured["baseline_P0"] = (
                        public_projection(json.loads(raw))
                        if isinstance(raw, str)
                        else None
                    )
                except ValueError:
                    captured["baseline_P0"] = None
                captured["P0"] = None
                comparable = getattr(
                    _adapter, "t096_public_information_projection", None
                )
                if callable(comparable):
                    try:
                        captured["P0"] = public_projection(
                            validate_public_information_projection(
                                comparable(_snapshot)
                            )
                        )
                    except Exception as exc:  # noqa: BLE001 -- observation cannot alter baseline
                        captured["comparable_projection_audit"] = exception_signature(
                            exc
                        )
            else:
                captured["part_a"] = localize_projection(captured.get("P0"), payload)
                public_surfaces = captured["part_a"]["public_observations"]
                captured["anchor_schema_id"] = (public_surfaces["A"] or {}).get(
                    "schema_id"
                )
                captured["particle_schema_ids"] = [
                    (p or {}).get("schema_id") for p in public_surfaces["Pi"]
                ]
                anchor = (
                    payload.get("anchor_public_information_projection")
                    if isinstance(payload, Mapping)
                    else None
                )
                captured["part_a"]["t103_baseline_projection_differences"] = (
                    public_differences(captured.get("baseline_P0"), anchor)
                )
                captured["part_a"]["t103_baseline_public_projection"] = captured.get(
                    "baseline_P0"
                )
                captured["structured"] = _bridge_observations(payload)[0]

        for probe in probe_order:
            if probe == "bridge":
                runner = T103NativeRecordRunner(**self.inputs, observation_hook=observe)
                baseline = runner.diagnose(
                    record,
                    source_ordinal=source_ordinal,
                    selection_digest=selection_digest,
                )
                if baseline.get("diagnostic_class") != accepted.get("diagnostic_class"):
                    break
            elif accepted.get("diagnostic_class") == "OPAQUE_BRIDGE_FAILURE":
                factory = self.inputs["adapter_factory"]
                runner = T103NativeRecordRunner(
                    **{
                        **self.inputs,
                        "adapter_factory": lambda factory=factory: _SamplerAdapter(
                            factory(), sampler
                        ),
                    }
                )
                probe_row = runner.diagnose(
                    record,
                    source_ordinal=source_ordinal,
                    selection_digest=selection_digest,
                )
                sampler["pre_bridge_guard_passed"] = sampler["attempted"]
                sampler["restore_status"] = probe_row["restore_status"]
                sampler["restore_and_probe_wall_clock_time_s"] = probe_row[
                    "wall_clock_time_s"
                ]
        reproduced = baseline.get("diagnostic_class") == accepted.get(
            "diagnostic_class"
        )
        row = {
            **baseline,
            "accepted_t103_class": accepted["diagnostic_class"],
            "accepted_t103_exception_signature": accepted.get("exception_signature"),
            "baseline_reproduced": reproduced,
            "diagnostic_evidence_complete": (
                baseline.get("bridge_invocation_status") == "returned_report"
                if accepted["diagnostic_class"] == "PUBLIC_PROJECTION_PARITY_FAILURE"
                else baseline.get("bridge_invocation_status")
                in {"failed", "returned_report"}
                and sampler["attempted"] is True
                and sampler["status"] != "unknown"
            ),
            "standalone_sampler": sampler,
            "probes_attempted": [
                p for p in probe_order if p == "bridge" or sampler["attempted"]
            ],
            "wall_clock_time_s": time.perf_counter() - started,
            "baseline_bridge_lane_wall_clock_time_s": baseline["wall_clock_time_s"],
            "projection_surfaces": {
                "baseline_P0": {
                    "api": "StepSimulator.public_projection.v1",
                    "schema_id": (captured.get("baseline_P0") or {}).get("schema_id"),
                },
                "P0": {
                    "api": "StepSimulator.t096_public_information_projection",
                    "schema_id": (captured.get("P0") or {}).get("schema_id"),
                },
                "A_and_Pi": {
                    "api": "StepSimulator.sample_hidden_future_particles_search.v1",
                    "projection_schema_id": captured.get("anchor_schema_id"),
                    "particle_projection_schema_ids": captured.get(
                        "particle_schema_ids", []
                    ),
                },
            },
            "comparable_projection_audit": captured.get("comparable_projection_audit"),
        }
        if accepted["diagnostic_class"] == "PUBLIC_PROJECTION_PARITY_FAILURE":
            row.update(captured.get("part_a", localize_projection(None, None)))
        else:
            row.update(
                localize_stages(
                    baseline_reproduced=reproduced,
                    bridge_failed=baseline.get("bridge_invocation_status")
                    in {"failed", "returned_report"}
                    and baseline.get("diagnostic_class") != "ADMITTED",
                    pre_bridge_passed=baseline.get("bridge_invocation_status")
                    in {"failed", "returned_report"}
                    and sampler.get("pre_bridge_guard_passed") is True,
                    sampler_status=str(sampler["status"]),
                    structured=captured.get("structured", {}),
                )
            )
        return row


def aggregate_localization(rows: Sequence[Mapping[str, object]]) -> dict[str, object]:
    """Complete census and the same row predicate control the terminal."""

    if len(rows) != 413 or len({r.get("selection_identity") for r in rows}) != 413:
        raise T104IncompleteError("T104 identity census is incomplete")
    a = [
        r
        for r in rows
        if r.get("accepted_t103_class") == "PUBLIC_PROJECTION_PARITY_FAILURE"
    ]
    b = [r for r in rows if r.get("accepted_t103_class") == "OPAQUE_BRIDGE_FAILURE"]
    if len(a) != 70 or len(b) != 343:
        raise T104IncompleteError("T104 Part A/B census changed")
    for part, field, classes, original in (
        (a, "part_a_class", PART_A_CLASSES, "PUBLIC_PROJECTION_PARITY_FAILURE"),
        (b, "part_b_class", PART_B_CLASSES, "OPAQUE_BRIDGE_FAILURE"),
    ):
        if Counter(r.get("stratum") for r in part) != Counter(CLASS_COUNTS[original]):
            raise T104IncompleteError("T104 stratum census changed")
        if any(r.get(field) not in classes for r in part):
            raise T104IncompleteError("T104 class is unavailable")
    if any(not isinstance(r.get("native_observability_required"), bool) for r in b):
        raise T104IncompleteError("T104 observability evidence is unavailable")
    for row in b:
        expected = localize_stages(
            baseline_reproduced=row.get("baseline_reproduced") is True,
            bridge_failed=row.get("full_bridge_failed") is True,
            pre_bridge_passed=row.get("pre_bridge_passed") is True,
            sampler_status=str(row.get("standalone_sampler_status")),
            structured=row.get("structured_stage_facts", {}),
        )
        if any(row.get(key) != value for key, value in expected.items()):
            raise T104IncompleteError(
                "row class/observability disagrees with structured facts"
            )
    needed = [r for r in b if r["native_observability_required"]]
    contradicted = any(r.get("baseline_reproduced") is not True for r in rows)
    terminal = (
        "T103_SUPPORT_RESULT_NOT_REPRODUCED"
        if contradicted
        else "INCOMPLETE"
        if any(r.get("diagnostic_evidence_complete") is not True for r in rows)
        else "NATIVE_OBSERVABILITY_REQUIRED"
        if needed
        else "BRIDGE_FAILURE_LOCALIZATION_ESTABLISHED"
    )

    def fractions(
        items: Sequence[Mapping[str, object]], field: str
    ) -> dict[str, object]:
        categories = {
            "part_a_class": PART_A_CLASSES,
            "part_b_class": PART_B_CLASSES,
            "native_observability_required": ("False", "True"),
        }.get(field, ())
        counts = Counter(dict.fromkeys(categories, 0))
        counts.update(str(r.get(field)) for r in items)
        return {
            key: {
                "count": value,
                "total": len(items),
                "fraction": f"{value}/{len(items)}",
            }
            for key, value in sorted(counts.items())
        }

    report = {
        "schema_id": "t104-bridge-localization-report-v1",
        "task_id": "T104",
        "terminal_classification": terminal,
        "part_a": {
            "classes": fractions(a, "part_a_class"),
            "by_stratum": {
                s: fractions([r for r in a if r["stratum"] == s], "part_a_class")
                for s in SOURCE_COUNTS
            },
            "field_path_signatures": dict(
                Counter(
                    json.dumps(
                        r.get("public_projection_differences", []), sort_keys=True
                    )
                    for r in a
                )
            ),
            "field_families": dict(
                Counter(f for r in a for f in r.get("public_field_families", []))
            ),
            "particles_affected": dict(
                Counter(json.dumps(r.get("particles_affected", [])) for r in a)
            ),
            "ordered_action_signatures": dict(
                Counter(
                    json.dumps(r.get("ordered_action_differences", []), sort_keys=True)
                    for r in a
                )
            ),
            "ordered_action_identity_occurrence_order_signatures": dict(
                Counter(
                    json.dumps(
                        r.get("ordered_action_identity_occurrence_order_evidence", []),
                        sort_keys=True,
                    )
                    for r in a
                )
            ),
            "t103_baseline_representation_difference_signatures": dict(
                Counter(
                    json.dumps(
                        r.get("t103_baseline_projection_differences", []),
                        sort_keys=True,
                    )
                    for r in a
                )
            ),
        },
        "part_b": {
            "classes": fractions(b, "part_b_class"),
            "by_stratum": {
                s: fractions([r for r in b if r["stratum"] == s], "part_b_class")
                for s in SOURCE_COUNTS
            },
            "standalone_sampler": dict(
                Counter(str(r.get("standalone_sampler", {}).get("status")) for r in b)
            ),
            "native_stage_opaque_count": sum(
                r["part_b_class"] == "NATIVE_STAGE_OPAQUE" for r in b
            ),
        },
        "native_observability": {
            "required": fractions(b, "native_observability_required"),
            "required_count": len(needed),
            "concrete_monolithic_repair_boundary_count": sum(
                bool(r.get("concrete_monolithic_repair_boundary")) for r in b
            ),
            "by_class": {
                c: fractions(
                    [r for r in b if r["part_b_class"] == c],
                    "native_observability_required",
                )
                for c in PART_B_CLASSES
            },
            "by_stratum": {
                s: fractions(
                    [r for r in b if r["stratum"] == s], "native_observability_required"
                )
                for s in SOURCE_COUNTS
            },
            "missing_stage_sets": dict(
                Counter(
                    json.dumps(r["native_observability_missing_stages"]) for r in needed
                )
            ),
            "minimal_future_requirement": [
                f"stable non-secret entered/completed/failed status for {s}"
                for s in INTERNAL_STAGES
                if any(s in r["native_observability_missing_stages"] for r in needed)
            ],
        },
        "audit_only_t103_exception_signatures": dict(
            Counter(str(r.get("accepted_t103_exception_signature")) for r in rows)
        ),
        "baseline_contradictions": [
            r["selection_identity"]
            for r in rows
            if r.get("baseline_reproduced") is not True
        ],
    }

    def counted_fractions(counts: Mapping[str, int], total: int) -> dict[str, object]:
        return {
            key: {"count": value, "total": total, "fraction": f"{value}/{total}"}
            for key, value in sorted(counts.items())
        }

    for field in (
        "field_path_signatures",
        "field_families",
        "particles_affected",
        "ordered_action_signatures",
        "ordered_action_identity_occurrence_order_signatures",
        "t103_baseline_representation_difference_signatures",
    ):
        report["part_a"][field] = counted_fractions(report["part_a"][field], 70)
    report["part_b"]["standalone_sampler"] = counted_fractions(
        {
            status: report["part_b"]["standalone_sampler"].get(status, 0)
            for status in ("succeeded", "failed", "public_fidelity_failed", "unknown")
        },
        343,
    )
    report["part_b"]["native_stage_opaque"] = counted_fractions(
        {"opaque": report["part_b"]["native_stage_opaque_count"]}, 343
    )
    report["native_observability"]["missing_stage_sets"] = counted_fractions(
        report["native_observability"]["missing_stage_sets"], len(needed)
    )
    concrete = report["native_observability"][
        "concrete_monolithic_repair_boundary_count"
    ]
    report["native_observability"]["concrete_repair_boundaries"] = counted_fractions(
        {"established": concrete, "not_established": 343 - concrete}, 343
    )
    report["audit_only_t103_exception_signatures"] = counted_fractions(
        report["audit_only_t103_exception_signatures"], 413
    )
    return report
