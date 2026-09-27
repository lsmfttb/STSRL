"""Independent expected evidence for the T104 frozen diagnostic boundaries."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from types import SimpleNamespace

import pytest
from test_t103_particle_diagnostic import _real_action, _real_context_runner

from sts_combat_rl.commands import t104_bridge_localization as command
from sts_combat_rl.sim import t104_bridge_localization as diagnostic


def test_public_diff_nested_missing_types_and_order_are_canonical():
    left = {"player": {"hp": 7, "nested": {"a/b~c": True}}, "hand": [1, 2]}
    right = {"hand": [2, 1, 3], "player": {"hp": "7", "extra": None}}
    expected = [
        {
            "path": "/hand/0",
            "difference": "unequal",
            "left_type": "integer",
            "right_type": "integer",
        },
        {
            "path": "/hand/1",
            "difference": "unequal",
            "left_type": "integer",
            "right_type": "integer",
        },
        {
            "path": "/hand/2",
            "difference": "missing_left",
            "left_type": "missing",
            "right_type": "integer",
        },
        {
            "path": "/player/extra",
            "difference": "missing_left",
            "left_type": "missing",
            "right_type": "null",
        },
        {
            "path": "/player/hp",
            "difference": "type_difference",
            "left_type": "integer",
            "right_type": "string",
        },
        {
            "path": "/player/nested",
            "difference": "missing_right",
            "left_type": "object",
            "right_type": "missing",
        },
    ]
    assert diagnostic.public_differences(left, right) == expected
    assert (
        diagnostic.public_differences(
            {"player": {"a/b~c": 1}}, {"player": {"a/b~c": 2}}
        )[0]["path"]
        == "/player/a~1b~0c"
    )


@pytest.mark.parametrize(
    "bad",
    [
        {"player": {"nested": {"private_state": "secret"}}},
        {"hand": [{"hidden_draw_order": "secret"}]},
        {"player": {1: "secret"}},
        {"player": {"hp": object()}},
        {"unexpected_private_top": "secret"},
        {"player": {"hp": float("nan")}},
        {"player": {"label": "action bits=82781"}},
    ],
)
def test_private_and_malformed_paths_never_enter_output(bad):
    assert diagnostic.public_projection(bad) is None
    assert diagnostic.public_differences({"player": {"hp": 1}}, bad) == []
    output = diagnostic.localize_projection(
        {"player": {"hp": 1}},
        {
            "anchor_public_information_projection": bad,
            "particles": [{"public_information_projection": bad}],
        },
    )
    retained = json.dumps(output)
    assert "secret" not in retained
    assert "private_state" not in retained
    assert "hidden_draw_order" not in retained
    assert "unexpected_private_top" not in retained


def _report(anchor, particles, *, flag=True):
    return {
        "anchor_public_information_projection": anchor,
        "anchor_ordered_public_legal_actions": anchor.get(
            "ordered_public_legal_actions", []
        ),
        "particles": [
            {
                "public_information_projection": p,
                "public_projection_equal": flag,
                "ordered_public_legal_actions": p.get(
                    "ordered_public_legal_actions", []
                ),
            }
            for p in particles
        ],
    }


def _public_action(index):
    return {
        "scope": "battle",
        "kind": "card",
        "idx1": index,
        "idx2": 0,
        "idx3": 0,
        "label": f"public card {index}",
    }


@pytest.mark.parametrize(
    "p0,anchor,particle,flag,expected",
    [
        (
            {"player": {"hp": 2}},
            {"player": {"hp": 1}},
            {"player": {"hp": 0}},
            True,
            "ANCHOR_CAPTURE_DRIFT",
        ),
        (
            {"player": {"hp": 1}},
            {"player": {"hp": 1}},
            {"player": {"hp": 0}},
            True,
            "PARTICLE_PUBLIC_STATE_DRIFT",
        ),
        (
            {"player": {"hp": 1}},
            {"player": {"hp": 1}},
            {"player": {"hp": 1}},
            False,
            "STRUCTURED_PARITY_FLAG_INCONSISTENCY",
        ),
        (
            {"ordered_public_legal_actions": [_public_action(1), _public_action(2)]},
            {"ordered_public_legal_actions": [_public_action(1), _public_action(2)]},
            {"ordered_public_legal_actions": [_public_action(2), _public_action(1)]},
            True,
            "ORDERED_PUBLIC_ACTION_DRIFT",
        ),
        (
            None,
            {"player": {"hp": 1}},
            {"player": {"hp": 1}},
            True,
            "PROJECTION_FAILURE_LOCALIZATION_OPAQUE",
        ),
    ],
)
def test_all_part_a_classes_with_earliest_boundary(
    p0, anchor, particle, flag, expected
):
    row = diagnostic.localize_projection(p0, _report(anchor, [particle], flag=flag))
    assert row["part_a_class"] == expected


@pytest.mark.parametrize(
    "actions", [[], [_public_action(1), _public_action(1), _public_action(2)]]
)
def test_action_flag_only_contradiction_requires_established_equal_payloads(actions):
    projection = {"player": {"hp": 80}, "ordered_public_legal_actions": actions}
    report = _report(projection, [projection, projection])
    report["particles"][0]["ordered_public_legal_actions_equal"] = False
    observed = diagnostic.localize_projection(projection, report)
    assert observed["part_a_class"] == "STRUCTURED_PARITY_FLAG_INCONSISTENCY"
    assert observed["structured_action_parity_failed"] is True
    assert observed["public_projection_differences"] == []
    assert observed["ordered_action_differences"] == []
    assert all(
        e["ordered_identity_sequence_equal"] is True
        for e in observed["ordered_action_identity_occurrence_order_evidence"]
    )
    missing = diagnostic.localize_projection(None, report)
    assert missing["part_a_class"] == "PROJECTION_FAILURE_LOCALIZATION_OPAQUE"
    assert missing["structured_action_parity_failed"] is True


@pytest.mark.parametrize(
    "surface",
    [
        "P0_missing",
        "P0_private",
        "P0_malformed",
        "P0_empty",
        "anchor_missing",
        "anchor_private",
        "Pi_missing",
        "one_Pi_missing",
        "Pi_private",
        "Pi_empty",
    ],
)
@pytest.mark.parametrize("actual_action_difference", [False, True])
def test_unavailable_projection_boundary_never_clears_earlier_failure(
    surface, actual_action_difference
):
    actions = [_public_action(1), _public_action(2)]
    projection = {"player": {"hp": 80}, "ordered_public_legal_actions": actions}
    p0 = deepcopy(projection)
    report = _report(
        deepcopy(projection), [deepcopy(projection), deepcopy(projection)], flag=False
    )
    report["particles"][0]["ordered_public_legal_actions_equal"] = False
    if actual_action_difference:
        report["particles"][0]["ordered_public_legal_actions"] = list(reversed(actions))
    if surface.startswith("P0"):
        p0 = {
            "P0_missing": None,
            "P0_private": {"player": {"private_state": "secret"}},
            "P0_malformed": {"player": object()},
            "P0_empty": {},
        }[surface]
    elif surface == "anchor_missing":
        report.pop("anchor_public_information_projection")
    elif surface == "anchor_private":
        report["anchor_public_information_projection"] = {
            "player": {"private_state": "secret"}
        }
    elif surface == "Pi_missing":
        report["particles"] = []
    elif surface == "one_Pi_missing":
        report["particles"][1].pop("public_information_projection")
    else:
        report["particles"][1]["public_information_projection"] = (
            {"player": {"private_state": "secret"}} if surface == "Pi_private" else {}
        )
    row = diagnostic.localize_projection(p0, report)
    assert row["part_a_class"] == "PROJECTION_FAILURE_LOCALIZATION_OPAQUE"
    assert "private_state" not in json.dumps(row)
    assert "secret" not in json.dumps(row)


@pytest.mark.parametrize("boundary", ["P0 -> A", "A -> Pi"])
@pytest.mark.parametrize("change", ["order", "identity", "duplicate_occurrence"])
def test_class_four_requires_observed_valid_action_identity_occurrence_or_order_difference(
    boundary, change
):
    before = [_public_action(1), _public_action(1), _public_action(2)]
    after = {
        "order": list(reversed(before)),
        "identity": [_public_action(3), *before[1:]],
        "duplicate_occurrence": [
            _public_action(1),
            _public_action(2),
            _public_action(2),
        ],
    }[change]
    projection = {"player": {"hp": 80}, "ordered_public_legal_actions": before}
    report = _report(projection, [projection, projection])
    if boundary == "P0 -> A":
        report["anchor_ordered_public_legal_actions"] = after
        for p in report["particles"]:
            p["ordered_public_legal_actions"] = after
    else:
        report["particles"][0]["ordered_public_legal_actions"] = after
    row = diagnostic.localize_projection(projection, report)
    assert row["part_a_class"] == "ORDERED_PUBLIC_ACTION_DRIFT"
    assert row["structured_action_parity_failed"] is False
    evidence = row["ordered_action_identity_occurrence_order_evidence"]
    assert any(e.get("ordered_identity_sequence_equal") is False for e in evidence)
    if change == "order":
        assert all(e["identity_occurrence_counts_equal"] for e in evidence)
    else:
        assert any(e["identity_occurrence_counts_equal"] is False for e in evidence)


@pytest.mark.parametrize(
    "missing", ["anchor_actions", "particle_actions", "invalid_action_identity"]
)
def test_action_flag_with_unavailable_comparison_cannot_establish_drift_or_inconsistency(
    missing,
):
    actions = [_public_action(1)]
    projection = {"player": {"hp": 80}, "ordered_public_legal_actions": actions}
    report = _report(projection, [projection, projection])
    report["particles"][0]["ordered_public_legal_actions_equal"] = False
    if missing == "anchor_actions":
        report.pop("anchor_ordered_public_legal_actions")
    elif missing == "particle_actions":
        report["particles"][1].pop("ordered_public_legal_actions")
    else:
        report["particles"][0]["ordered_public_legal_actions"] = [
            {"kind": "malformed public identity"}
        ]
    row = diagnostic.localize_projection(projection, report)
    assert row["part_a_class"] == "PROJECTION_FAILURE_LOCALIZATION_OPAQUE"
    assert row["structured_action_parity_failed"] is True


def test_direct_earlier_projection_drift_remains_localized_with_missing_downstream_surfaces():
    p0 = {"player": {"hp": 80}, "ordered_public_legal_actions": []}
    anchor = {"player": {"hp": 79}, "ordered_public_legal_actions": []}
    first = diagnostic.localize_projection(p0, _report(anchor, []))
    assert first["part_a_class"] == "ANCHOR_CAPTURE_DRIFT"
    report = _report(p0, [anchor, p0])
    report["particles"][1].pop("public_information_projection")
    second = diagnostic.localize_projection(p0, report)
    assert second["part_a_class"] == "PARTICLE_PUBLIC_STATE_DRIFT"


@pytest.mark.parametrize(
    "pre,status,facts,expected,needed,boundary",
    [
        (False, "unknown", {}, "PRE_BRIDGE_CONTEXT_FAILURE", False, None),
        (True, "failed", {}, "STANDALONE_SAMPLER_FAILURE", True, None),
        (
            True,
            "public_fidelity_failed",
            {},
            "STANDALONE_SAMPLER_PUBLIC_FIDELITY_FAILURE",
            True,
            None,
        ),
        (
            True,
            "succeeded",
            {},
            "BRIDGE_FAILURE_AFTER_STANDALONE_SAMPLER_SUCCESS",
            True,
            None,
        ),
        (
            True,
            "succeeded",
            {"mapping_complete": False},
            "STRUCTURED_MAPPING_FAILURE",
            False,
            "occurrence_mapping",
        ),
        (
            True,
            "succeeded",
            {
                "mapping_complete": True,
                "mapping_ambiguous": False,
                "search_execution_reached": True,
                "search_execution_failed": True,
            },
            "STRUCTURED_SEARCH_SETUP_OR_EXECUTION_FAILURE",
            False,
            "search_execution",
        ),
        (
            True,
            "succeeded",
            {
                "mapping_complete": True,
                "mapping_ambiguous": False,
                "search_execution_reached": True,
                "required_root_values_valid": False,
            },
            "STRUCTURED_ROOT_REPORT_FAILURE",
            False,
            "sanitized_root_report",
        ),
        (True, "unknown", {}, "NATIVE_STAGE_OPAQUE", True, None),
    ],
)
def test_all_part_b_classes_and_independent_observability(
    pre, status, facts, expected, needed, boundary
):
    row = diagnostic.localize_stages(
        baseline_reproduced=pre,
        bridge_failed=pre,
        pre_bridge_passed=pre,
        sampler_status=status,
        structured=facts,
    )
    assert row["part_b_class"] == expected
    assert row["native_observability_required"] is needed
    assert row["concrete_monolithic_repair_boundary"] == boundary
    assert row["internal_stage_status"]["monolithic_sample_construction"] == "unknown"
    assert (
        row["internal_stage_status"]["monolithic_public_fidelity_validation"]
        == "unknown"
    )
    if needed:
        assert row["native_observability_missing_stages"][:2] == [
            "monolithic_sample_construction",
            "monolithic_public_fidelity_validation",
        ]


def test_exception_prose_cannot_change_class_or_predicate():
    results = [
        diagnostic.localize_stages(
            baseline_reproduced=True,
            bridge_failed=True,
            pre_bridge_passed=True,
            sampler_status="unknown",
            structured={"exception_text": text},
        )
        for text in ("Search mapping failed", "sampler failed", "root report failed")
    ]
    assert {r["part_b_class"] for r in results} == {"NATIVE_STAGE_OPAQUE"}
    assert all(r["native_observability_required"] for r in results)


def _seed(identity):
    # Independent spelling of the accepted T101 formula, not the producer helper.
    return int.from_bytes(
        hashlib.sha256(b"T101-v1" + identity.encode() + b"0").digest()[:8], "big"
    )


def _population():
    rows = []
    for stratum, projection_count, opaque_count in (
        ("A", 4, 89),
        ("B", 3, 189),
        ("C", 63, 65),
    ):
        for index in range(projection_count + opaque_count):
            identity = f"{stratum}-{index}"
            rows.append(
                {
                    "selection_identity": identity,
                    "stratum": stratum,
                    "source_ordinal": len(rows),
                    "selection_digest": hashlib.sha256(identity.encode()).hexdigest(),
                    "diagnostic_class": "PUBLIC_PROJECTION_PARITY_FAILURE"
                    if index < projection_count
                    else "OPAQUE_BRIDGE_FAILURE",
                    "replicate_index": 0,
                    "sampler_seed": _seed(identity),
                    "particle_count": 2,
                    "search_simulations": 400,
                    "include_potions": False,
                    "admitted": False,
                }
            )
    return rows


def _localized_population():
    rows = []
    for original in _population():
        row = {
            **original,
            "accepted_t103_class": original["diagnostic_class"],
            "baseline_reproduced": True,
            "diagnostic_evidence_complete": True,
        }
        if original["diagnostic_class"] == "PUBLIC_PROJECTION_PARITY_FAILURE":
            row.update(diagnostic.localize_projection(None, None))
        else:
            row.update(
                diagnostic.localize_stages(
                    baseline_reproduced=True,
                    bridge_failed=True,
                    pre_bridge_passed=True,
                    sampler_status="succeeded",
                    structured={},
                )
            )
            row["standalone_sampler"] = {"status": "succeeded"}
        rows.append(row)
    return rows


def test_complete_census_fraction_and_terminal_use_predicate_not_opaque_class():
    rows = _localized_population()
    assert len(diagnostic.validate_t103_population(_population())) == 413
    report = diagnostic.aggregate_localization(rows)
    assert report["terminal_classification"] == "NATIVE_OBSERVABILITY_REQUIRED"
    assert report["native_observability"]["required_count"] == 343
    assert report["part_b"]["native_stage_opaque_count"] == 0
    assert report["part_a"]["classes"]["PROJECTION_FAILURE_LOCALIZATION_OPAQUE"] == {
        "count": 70,
        "total": 70,
        "fraction": "70/70",
    }
    assert (
        report["part_b"]["by_stratum"]["C"][
            "BRIDGE_FAILURE_AFTER_STANDALONE_SAMPLER_SUCCESS"
        ]["count"]
        == 65
    )
    for row in rows:
        if row["accepted_t103_class"] == "OPAQUE_BRIDGE_FAILURE":
            row.update(
                diagnostic.localize_stages(
                    baseline_reproduced=True,
                    bridge_failed=True,
                    pre_bridge_passed=True,
                    sampler_status="succeeded",
                    structured={"mapping_complete": False},
                )
            )
    report = diagnostic.aggregate_localization(rows)
    assert (
        report["terminal_classification"] == "BRIDGE_FAILURE_LOCALIZATION_ESTABLISHED"
    )
    assert report["native_observability"]["required_count"] == 0
    assert (
        report["native_observability"]["concrete_monolithic_repair_boundary_count"]
        == 343
    )


def test_changed_per_identity_baseline_is_contradiction_even_same_overall_counts():
    rows = _localized_population()
    rows[0]["baseline_reproduced"] = False
    assert (
        diagnostic.aggregate_localization(rows)["terminal_classification"]
        == "T103_SUPPORT_RESULT_NOT_REPRODUCED"
    )


@pytest.mark.parametrize(
    "mutation",
    [
        lambda r: r.pop(),
        lambda r: r.__setitem__(0, r[1]),
        lambda r: r[0].__setitem__("sampler_seed", 1),
        lambda r: r[0].__setitem__("diagnostic_class", "ADMITTED"),
        lambda r: r[0].__setitem__("include_potions", True),
        lambda r: r[0].__setitem__("stratum", "B"),
    ],
)
def test_input_population_fails_closed(mutation):
    rows = _population()
    mutation(rows)
    with pytest.raises(diagnostic.T104IncompleteError):
        diagnostic.validate_t103_population(rows)


def test_aggregate_rejects_boolean_that_disagrees_with_facts():
    rows = _localized_population()
    rows[4]["native_observability_required"] = False
    with pytest.raises(diagnostic.T104IncompleteError):
        diagnostic.aggregate_localization(rows)


def _clone_runner(monkeypatch, *, bridge_exception="opaque", sampler_failure=False):
    identity, _expected, _, inherited = _real_context_runner(monkeypatch, [], [])
    adapters, calls = [], []
    projection = {"player": {"hp": 80}}
    monkeypatch.setattr(
        diagnostic, "validate_public_information_projection", lambda value: value
    )

    class Adapter:
        def __init__(self):
            self.mutated = False
            self.index = len(adapters)
            adapters.append(self)

        def legal_actions(self, snapshot):
            return []

        def public_projection(self, snapshot):
            return inherited._adapter_factory().public_projection(snapshot)

        def t096_public_information_projection(self, snapshot):
            return {**projection, "information_fidelity": "supported"}

        def sample_hidden_future_particles(self, snapshot, **kwargs):
            assert not self.mutated
            self.mutated = True
            calls.append((self.index, "sampler", kwargs))
            if sampler_failure:
                raise RuntimeError("private exception search mapping prose")
            return [
                {
                    "particle_index": index,
                    "hidden_future_fingerprint": "NEVER RETAIN",
                    "public_information_projection": self.t096_public_information_projection(
                        snapshot
                    ),
                    "private_state": "NEVER RETAIN",
                }
                for index in range(2)
            ]

        def sample_hidden_future_particles_search(self, snapshot, **kwargs):
            assert not self.mutated
            self.mutated = True
            calls.append((self.index, "bridge", kwargs))
            raise RuntimeError(bridge_exception)

    runner = diagnostic.T104NativeRecordRunner(
        adapter_factory=Adapter,
        selected_records=inherited._selected_records,
        canonical_records_by_stratum=inherited._canonical_records_by_stratum,
        native_identity=inherited._native_identity,
        historical_bindings=inherited._historical_bindings,
    )
    return identity, runner, adapters, calls


@pytest.mark.parametrize("order", [("bridge", "sampler"), ("sampler", "bridge")])
def test_independent_fresh_clones_order_and_unchanged_native_parameters(
    monkeypatch, order
):
    identity, runner, adapters, calls = _clone_runner(monkeypatch)
    row = runner.diagnose(
        {"selection_identity": identity, "cohort": "A"},
        accepted={"diagnostic_class": "OPAQUE_BRIDGE_FAILURE"},
        source_ordinal=0,
        selection_digest="d" * 64,
        probe_order=order,
    )
    assert len(adapters) == 2
    assert {c[0] for c in calls} == {0, 1}
    assert [c[1] for c in calls] == list(order)
    assert row["baseline_reproduced"] is True
    assert row["part_b_class"] == "BRIDGE_FAILURE_AFTER_STANDALONE_SAMPLER_SUCCESS"
    assert row["native_observability_required"] is True
    assert row["internal_stage_status"]["monolithic_sample_construction"] == "unknown"
    assert "NEVER RETAIN" not in json.dumps(row)
    assert "private_state" not in json.dumps(row)
    bridge = next(c[2] for c in calls if c[1] == "bridge")
    sampler = next(c[2] for c in calls if c[1] == "sampler")
    assert bridge == {
        "sampler_seed": _seed(identity),
        "particle_start": 0,
        "particle_count": 2,
        "search_simulations": 400,
        "include_potions": False,
    }
    assert sampler == {
        "sampler_seed": _seed(identity),
        "particle_start": 0,
        "particle_count": 2,
    }


@pytest.mark.parametrize("bad_guard", ["candidate", "completeness", "order"])
def test_inherited_real_guard_stops_both_lanes_before_any_native_call(
    monkeypatch, bad_guard
):
    a = _real_action("battle", 11, "play_card", "same")
    b = _real_action("battle", 22, "end_turn", "end turn")
    observed = [a] if bad_guard == "candidate" else [a, b]
    accepted_actions = [b, a] if bad_guard == "order" else None
    identity, expected, calls, inherited = _real_context_runner(
        monkeypatch, [a, b], observed, accepted_actions=accepted_actions
    )
    if bad_guard == "completeness":
        expected["missing_fields"] = ["required fixture public field"]
    runner = diagnostic.T104NativeRecordRunner(
        adapter_factory=inherited._adapter_factory,
        selected_records=inherited._selected_records,
        canonical_records_by_stratum=inherited._canonical_records_by_stratum,
        native_identity=inherited._native_identity,
        historical_bindings=inherited._historical_bindings,
    )
    row = runner.diagnose(
        {"selection_identity": identity, "cohort": "A"},
        accepted={"diagnostic_class": "OPAQUE_BRIDGE_FAILURE"},
        source_ordinal=0,
        selection_digest="x" * 64,
    )
    assert calls == []
    assert row["standalone_sampler"]["attempted"] is False
    assert row["baseline_reproduced"] is False
    assert row["part_b_class"] == "PRE_BRIDGE_CONTEXT_FAILURE"
    assert row["native_observability_required"] is False


def test_standalone_failure_does_not_prove_monolithic_boundary(monkeypatch):
    identity, runner, _, calls = _clone_runner(monkeypatch, sampler_failure=True)
    row = runner.diagnose(
        {"selection_identity": identity, "cohort": "A"},
        accepted={"diagnostic_class": "OPAQUE_BRIDGE_FAILURE"},
        source_ordinal=0,
        selection_digest="x" * 64,
    )
    assert len(calls) == 2
    assert row["part_b_class"] == "STANDALONE_SAMPLER_FAILURE"
    assert row["native_observability_required"] is True
    assert row["concrete_monolithic_repair_boundary"] is None


def test_retention_outputs_hash_schema_and_no_overwrite(tmp_path):
    refs = command.write_artifacts(
        tmp_path,
        [],
        {
            "schema_id": "t104-bridge-localization-report-v1",
            "terminal_classification": "INCOMPLETE",
        },
        {"implementation_head": "a" * 40},
        "explicit command",
    )
    for ref in refs.values():
        path = tmp_path / ref["path"].split("/")[-1]
        assert hashlib.sha256(path.read_bytes()).hexdigest() == ref["sha256"]
        assert len(path.read_bytes()) == ref["size_bytes"]
        assert json.loads(path.read_text())["schema_id"] == ref["schema_id"]
    with pytest.raises(diagnostic.T104IncompleteError):
        command.write_artifacts(tmp_path, [], {}, {}, "command")


def test_worker_plan_requires_process_runtime_and_truthful_reduction_reason(
    monkeypatch,
):
    monkeypatch.setattr(command.os, "cpu_count", lambda: 16)
    assert command.worker_plan(None, None) == (16, 16)
    assert command.worker_plan(4, "documented memory cap") == (16, 4)
    with pytest.raises(diagnostic.T104IncompleteError):
        command.worker_plan(4, None)
    monkeypatch.setattr(
        command.multiprocessing, "get_all_start_methods", lambda: ["spawn"]
    )
    with pytest.raises(diagnostic.T104IncompleteError):
        command.worker_plan(None, None)


def test_retained_manifest_hash_fails_closed_before_any_native_call(tmp_path):
    bad = tmp_path / "manifest.json"
    bad.write_text("{}")
    with pytest.raises(diagnostic.T104IncompleteError, match="hash mismatch"):
        command.load_accepted_t103(bad, tmp_path / "missing-execution.json")


def _retained_fixture(monkeypatch, tmp_path, *, mutation=None):
    native = {
        "repository": "lsmfttb/sts_lightspeed",
        "ref": "refs/heads/stsrl/main",
        "commit": "97f59b620efe5ee1571f8da298c99d1e21c1149b",
    }
    rows = _population()
    for row in rows:
        row["current_native_identity"] = native
    documents = {
        "candidate_diagnostics": {
            "schema_id": "t103-particle-support-diagnostics-v1",
            "task_id": "T103",
            "rows": rows,
        },
        "aggregate_report": {
            "schema_id": "t103-particle-support-report-v1",
            "task_id": "T103",
            "terminal_classification": "SUPPORT_DOMAIN_FAILURE_TAXONOMY_ESTABLISHED",
        },
    }
    references = {}
    bindings = {}
    for role, document in documents.items():
        path = tmp_path / f"{role}.json"
        path.write_text(json.dumps(document))
        sha = hashlib.sha256(path.read_bytes()).hexdigest()
        references[role] = {
            "path": str(path),
            "schema_id": document["schema_id"],
            "sha256": sha,
            "size_bytes": path.stat().st_size,
        }
        bindings[role] = (document["schema_id"], sha)
    manifest = {
        "schema_id": "t103-diagnostic-retention-manifest-v1",
        "task_id": "T103",
        "terminal_classification": "SUPPORT_DOMAIN_FAILURE_TAXONOMY_ESTABLISHED",
        "producer_provenance": {
            "implementation_head": "ec58e2ad396c149988ca639fd3b22244d331b9d7",
            "current_native_identity": native,
        },
        "artifact_references": references,
    }
    if mutation:
        mutation(manifest)
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest))
    execution = tmp_path / "execution.json"
    execution.write_text(
        json.dumps(
            {
                "state": "SUCCEEDED",
                "exit_code": 0,
                "command": [
                    "python",
                    "--implementation-head",
                    "ec58e2ad396c149988ca639fd3b22244d331b9d7",
                ],
            }
        )
    )
    monkeypatch.setattr(
        command, "T103_MANIFEST_SHA256", hashlib.sha256(path.read_bytes()).hexdigest()
    )
    monkeypatch.setattr(
        command,
        "T103_EXECUTION_SHA256",
        hashlib.sha256(execution.read_bytes()).hexdigest(),
    )
    monkeypatch.setattr(command, "T103_REFERENCES", bindings)
    return path, execution, references


def test_retained_complete_synthetic_inputs_qualify(monkeypatch, tmp_path):
    manifest, execution, _ = _retained_fixture(monkeypatch, tmp_path)
    rows, retained = command.load_accepted_t103(manifest, execution)
    assert len(rows) == 413
    assert (
        retained["execution_reference"]["sha256"]
        == hashlib.sha256(execution.read_bytes()).hexdigest()
    )


@pytest.mark.parametrize(
    "mutation",
    [
        lambda m: m.__setitem__("schema_id", "unknown-schema"),
        lambda m: m["producer_provenance"].__setitem__(
            "implementation_head", "6104b94" + "0" * 33
        ),
        lambda m: m["artifact_references"]["candidate_diagnostics"].__setitem__(
            "schema_id", "wrong-row-schema"
        ),
        lambda m: m["artifact_references"]["candidate_diagnostics"].__setitem__(
            "size_bytes", 1
        ),
        lambda m: m["artifact_references"]["candidate_diagnostics"].__setitem__(
            "sha256", "f" * 64
        ),
        lambda m: m["producer_provenance"]["current_native_identity"].__setitem__(
            "commit", "a" * 40
        ),
    ],
)
def test_retained_schema_producer_integrity_and_native_binding_fail_closed(
    monkeypatch, tmp_path, mutation
):
    manifest, execution, _ = _retained_fixture(monkeypatch, tmp_path, mutation=mutation)
    with pytest.raises(ValueError):
        command.load_accepted_t103(manifest, execution)


def test_retained_execution_integrity_and_corrupted_rows_fail_closed(
    monkeypatch, tmp_path
):
    manifest, execution, _refs = _retained_fixture(monkeypatch, tmp_path)
    execution.write_text("{}")
    with pytest.raises(diagnostic.T104IncompleteError, match="execution hash"):
        command.load_accepted_t103(manifest, execution)
    manifest, execution, _refs = _retained_fixture(monkeypatch, tmp_path)
    row_path = tmp_path / "candidate_diagnostics.json"
    row_path.write_text(row_path.read_text() + " ")
    with pytest.raises(ValueError, match="hash/size"):
        command.load_accepted_t103(manifest, execution)


def test_bounded_positions_preserve_global_order_and_cannot_duplicate():
    assert command.candidate_positions([0, 4, 93, 96, 285, 348]) == [
        0,
        4,
        93,
        96,
        285,
        348,
    ]
    assert command.candidate_positions(None) == list(range(413))
    for bad in ([], [1, 0], [0, 0], [-1], [413]):
        with pytest.raises(diagnostic.T104IncompleteError):
            command.candidate_positions(bad)


def test_partial_rows_cannot_claim_full_census_terminal():
    with pytest.raises(diagnostic.T104IncompleteError, match="census is incomplete"):
        diagnostic.aggregate_localization(_localized_population()[:6])


def test_comparable_projection_does_not_call_schema_difference_state_drift(monkeypatch):
    identity, runner, _, _ = _clone_runner(monkeypatch)
    factory = runner.inputs["adapter_factory"]

    def adapter_factory():
        adapter = factory()

        def bridge(snapshot, **kwargs):
            projection = adapter.t096_public_information_projection(snapshot)
            return {
                "particle_start": 0,
                "particle_count": 2,
                "search_simulations": 400,
                "include_potions": False,
                "sampler_seed_input": kwargs["sampler_seed"],
                **_report(projection, [projection, projection], flag=True),
            }

        adapter.sample_hidden_future_particles_search = bridge
        return adapter

    runner.inputs["adapter_factory"] = adapter_factory
    row = runner.diagnose(
        {"selection_identity": identity, "cohort": "A"},
        accepted={"diagnostic_class": "PUBLIC_PROJECTION_PARITY_FAILURE"},
        source_ordinal=0,
        selection_digest="x" * 64,
    )
    assert row["baseline_reproduced"] is True
    assert row["public_projection_differences"] == []
    assert row["t103_baseline_projection_differences"]
    assert row["part_a_class"] == "PROJECTION_FAILURE_LOCALIZATION_OPAQUE"
    assert (
        row["projection_surfaces"]["P0"]["api"]
        == "StepSimulator.t096_public_information_projection"
    )
    assert (
        row["projection_surfaces"]["baseline_P0"]["schema_id"]
        == "native-public-projection-v1"
    )


def test_fullbridge_observations_survive_unavailable_comparable_surface(monkeypatch):
    identity, runner, _, calls = _clone_runner(monkeypatch)
    factory = runner.inputs["adapter_factory"]

    def adapter_factory():
        adapter = factory()

        def projection(snapshot):
            raise RuntimeError("private prose says mapping failed")

        adapter.t096_public_information_projection = projection
        return adapter

    runner.inputs["adapter_factory"] = adapter_factory
    row = runner.diagnose(
        {"selection_identity": identity, "cohort": "A"},
        accepted={"diagnostic_class": "OPAQUE_BRIDGE_FAILURE"},
        source_ordinal=0,
        selection_digest="x" * 64,
    )
    assert row["baseline_reproduced"] is True
    assert len([c for c in calls if c[1] == "bridge"]) == 1
    assert "private prose" not in json.dumps(row)


def test_mock_path_workflow_qualifies_once_and_retains_honest_canary(
    monkeypatch, tmp_path
):
    accepted = _population()
    localized = {r["selection_identity"]: r for r in _localized_population()}
    native = {"repository": "fixture/native", "commit": "a" * 40, "ref": "fixture"}
    historical = {"accepted_source_hash": "b" * 64}
    attempts = [
        {
            key: r[key]
            for key in (
                "selection_identity",
                "stratum",
                "source_ordinal",
                "selection_digest",
            )
        }
        for r in accepted
    ]
    calls = []
    monkeypatch.setattr(
        command,
        "load_accepted_t103",
        lambda *_: (
            accepted,
            {
                "manifest": {
                    "producer_provenance": {
                        "current_native_identity": native,
                        "historical_t101_bindings": historical,
                    }
                }
            },
        ),
    )
    monkeypatch.setattr(
        command.predecessor, "_sha256_file", lambda *_: command.NATIVE_BINARY_SHA256
    )
    monkeypatch.setattr(
        command.importlib.util,
        "find_spec",
        lambda _: SimpleNamespace(origin=str(tmp_path / "native.so")),
    )
    monkeypatch.setattr(command.sys, "version_info", (3, 13, 13))
    monkeypatch.setattr(command.os, "cpu_count", lambda: 16)
    monkeypatch.setattr(
        command.predecessor,
        "_load_t101_terminal_inputs",
        lambda *_: ({}, {}, {"attempted": attempts}, historical, native),
    )
    monkeypatch.setattr(
        command.predecessor, "_current_native_identity", lambda *_: native
    )
    maps = {
        s: {r["selection_identity"]: object() for r in accepted if r["stratum"] == s}
        for s in ("A", "B", "C")
    }
    gate = SimpleNamespace(
        canonical_records_by_cohort=maps,
        source_selection_manifest_identity={},
        cohorts={
            s: [SimpleNamespace(selection_identity=i) for i in maps[s]] for s in maps
        },
    )

    def qualify(**kwargs):
        calls.append("qualified_once")
        assert kwargs["historical_t085_producer_only"] is True
        return {}, gate, {}

    monkeypatch.setattr(
        command.t088_canary, "_admit_t088_canary_inputs_from_paths", qualify
    )
    sources = [
        {"selection_identity": r["selection_identity"], "cohort": r["stratum"]}
        for r in accepted
    ]
    monkeypatch.setattr(command.t088_canary, "_project_t087_cohort", lambda *_: sources)

    class Runner:
        def __init__(self, **kwargs):
            assert (
                sum(len(m) for m in kwargs["canonical_records_by_stratum"].values())
                == 6
            )
            assert len(kwargs["selected_records"]) == 6

        def diagnose(self, source, *, accepted, source_ordinal, selection_digest):
            assert source_ordinal == accepted["source_ordinal"]
            assert selection_digest == accepted["selection_digest"]
            return deepcopy(localized[source["selection_identity"]])

    monkeypatch.setattr(command, "T104NativeRecordRunner", Runner)

    class Executor:
        def __init__(self, *, initializer, initargs, **kwargs):
            assert calls == ["qualified_once"]
            assert kwargs["max_workers"] == 6
            initializer(*initargs)

        def __enter__(self):
            return self

        def __exit__(self, *_):
            pass

        def submit(self, function, *args):
            value = function(*args)
            return SimpleNamespace(result=lambda: value)

    monkeypatch.setattr(command, "ProcessPoolExecutor", Executor)
    args = SimpleNamespace(
        implementation_head="c" * 40,
        worker_count=None,
        lower_worker_reason=None,
        candidate_positions=[0, 4, 93, 96, 285, 348],
        t103_retention_manifest=tmp_path / "manifest",
        t103_execution_record=tmp_path / "execution",
        native_binary=tmp_path / "native.so",
        t101_retention_manifest=tmp_path / "t101",
        output_root=tmp_path / "t104-canary",
    )
    for name in (
        "t087_formal",
        "t087_report",
        "t087_retention",
        "t085_selection",
        "t085_restore",
        "a_pool",
        "b_pool",
        "c_pool",
        "b_source_manifest",
        "c_source_manifest",
    ):
        setattr(args, name, tmp_path / name)
    result = command.run_from_paths(args)
    report = result["report"]
    assert report["terminal_classification"] == "INCOMPLETE"
    assert report["canary_baselines_reproduced"] is True
    assert report["missing_full_census_count"] == 407
    assert report["execution"]["worker_target"] == 6
    assert report["execution"]["configured_worker_count"] == 6
    assert (
        report["execution"]["effective_worker_count"] == 1
    )  # mock actually ran in one process
    assert calls == ["qualified_once"]
    rows = json.loads(
        (args.output_root / "t104-candidate-localization.json").read_text()
    )["rows"]
    assert [r["selection_identity"] for r in rows] == [
        accepted[p]["selection_identity"] for p in args.candidate_positions
    ]


@pytest.mark.parametrize(
    "defect,expected",
    [
        ("duplicate_index", "failed"),
        ("missing_index", "failed"),
        ("missing_row", "failed"),
        ("missing_audit_digest", "failed"),
        ("public_mismatch", "public_fidelity_failed"),
        ("hidden_intent_leak", "public_fidelity_failed"),
    ],
)
def test_standalone_preserves_accepted_index_and_public_fidelity_checks(
    monkeypatch, defect, expected
):
    monkeypatch.setattr(
        diagnostic, "validate_public_information_projection", lambda value: value
    )
    anchor = {
        "information_fidelity": "supported",
        "ordered_public_legal_actions": [],
        "visibility": {"enemy_intent": {"classification": "hidden"}},
        "monsters": [{"last_move_id": 4, "public_statuses": []}],
    }
    particles = [
        {
            "particle_index": i,
            "hidden_future_fingerprint": "private audit value",
            "public_information_projection": deepcopy(anchor),
        }
        for i in range(2)
    ]
    if defect == "duplicate_index":
        particles[1]["particle_index"] = 0
    elif defect == "missing_index":
        particles[1].pop("particle_index")
    elif defect == "missing_row":
        particles.pop()
    elif defect == "missing_audit_digest":
        particles[0].pop("hidden_future_fingerprint")
    elif defect == "public_mismatch":
        particles[0]["public_information_projection"]["monsters"][0]["last_move_id"] = 5
    else:
        anchor["monsters"][0]["current_move"] = "hidden secret move"
        for particle in particles:
            particle["public_information_projection"] = deepcopy(anchor)
        assert diagnostic.public_projection(anchor) is None
        assert diagnostic.public_differences({"monsters": []}, anchor) == []
    result = diagnostic.standalone_fidelity(anchor, particles)
    assert result["status"] == expected
    assert "private audit value" not in json.dumps(result)
    assert "hidden secret move" not in json.dumps(result)
    assert "current_move" not in json.dumps(result)


def test_incomplete_probe_evidence_cannot_claim_successful_diagnostic_terminal():
    rows = _localized_population()
    rows[4]["diagnostic_evidence_complete"] = False
    assert (
        diagnostic.aggregate_localization(rows)["terminal_classification"]
        == "INCOMPLETE"
    )


def test_baseline_contradiction_short_circuits_future_records_and_standalone(
    monkeypatch,
):
    identity, runner, _, calls = _clone_runner(monkeypatch)
    row = runner.diagnose(
        {"selection_identity": identity, "cohort": "A"},
        accepted={"diagnostic_class": "PUBLIC_PROJECTION_PARITY_FAILURE"},
        source_ordinal=0,
        selection_digest="x" * 64,
    )
    assert row["baseline_reproduced"] is False
    assert [c[1] for c in calls] == ["bridge"]
    seen = []

    class Runner:
        def diagnose(self, record, **kwargs):
            seen.append(record)
            return {"baseline_reproduced": False}

    stop = command.multiprocessing.get_context("fork").Event()
    monkeypatch.setattr(command, "_FORK_RUNNER", Runner())
    monkeypatch.setattr(command, "_FORK_STOP", stop)
    jobs = [
        ({"n": i}, {"source_ordinal": i, "selection_digest": "x"}) for i in range(3)
    ]
    result = command._run_shard(jobs, {"shard_index": 0}, 1)
    assert len(result) == len(seen) == 1
    assert stop.is_set()
