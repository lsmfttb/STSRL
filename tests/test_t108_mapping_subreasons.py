from __future__ import annotations

from collections import Counter
from copy import deepcopy

import pytest

from sts_combat_rl.sim.t101_particle_convergence import derive_t101_sampler_seed
from sts_combat_rl.sim.t105_native_stage_observability import TRACE_SCHEMA
from sts_combat_rl.sim.t107_native_root_mapping_observability import DIAGNOSTIC_SCHEMA
from sts_combat_rl.sim.t108_mapping_subreasons import (
    FAILURE_SUBREASONS,
    NATIVE_IDENTITY,
    T106_IMPLEMENTATION_HEAD,
    T106_NATIVE_IDENTITY,
    T106_SHA256,
    T108IncompleteError,
    _ImmediateMappingTraceAdapter,
    aggregate_t108,
    classify_mapping_replay,
    select_t106_root_mapping_failures,
)


def _stages(*, failed: bool) -> dict[str, str]:
    return {
        "hidden_future_sample_construction": "completed" if failed else "not_reached",
        "public_fidelity_validation": "completed" if failed else "not_reached",
        "search_setup": "completed" if failed else "not_reached",
        "search_execution": "completed" if failed else "not_reached",
        "root_occurrence_mapping": "failed" if failed else "not_reached",
        "sanitized_root_report": "not_reached",
    }


def _mapping_diagnostic(
    subreason: str,
    *,
    overrides: dict[str, object] | None = None,
) -> dict[str, object]:
    counts: dict[str, object] = {
        "public_legal_occurrence_count": 1,
        "search_root_edge_count": 1,
        "public_occurrences_mapped": 0,
        "search_root_edges_covered": 0,
        "direct_mapping_count": 0,
        "mechanical_duplicate_mapping_count": 0,
    }
    diagnostic: dict[str, object] = {
        "schema_id": DIAGNOSTIC_SCHEMA,
        "status": "failed",
        "mapping_subreason": subreason,
    }
    if subreason == "no_public_legal_action_surface":
        counts.update(public_legal_occurrence_count=0)
    elif subreason == "uncovered_search_root_edge":
        counts.update(
            search_root_edge_count=2,
            public_occurrences_mapped=1,
            search_root_edges_covered=1,
            direct_mapping_count=1,
        )
    else:
        diagnostic.update(
            public_occurrence_index=0,
            public_action_kind=(
                "end_turn"
                if subreason == "missing_non_card_direct_search_root_match"
                else "card"
            ),
            direct_match_multiplicity=(
                "multiple"
                if subreason == "multiple_direct_search_root_matches"
                else "zero"
            ),
        )
        if subreason == "representative_search_root_match_zero":
            diagnostic["representative_match_multiplicity"] = "zero"
        elif subreason == "representative_search_root_match_multiple":
            diagnostic["representative_match_multiplicity"] = "multiple"
    diagnostic.update(counts)
    if overrides:
        diagnostic.update(overrides)
    return diagnostic


def _native_trace(
    diagnostic: dict[str, object] | None,
    *,
    failed_stage: str = "root_occurrence_mapping",
    failure_code: str = "root_occurrence_mapping_failed",
    accepted: bool = False,
) -> dict[str, object]:
    first_stages = _stages(failed=failed_stage == "root_occurrence_mapping")
    if failed_stage == "public_fidelity_validation":
        first_stages.update(
            search_setup="not_reached",
            search_execution="not_reached",
            root_occurrence_mapping="not_reached",
        )
        first_stages["public_fidelity_validation"] = "failed"
    first = {
        "particle_index": 0,
        "stages": first_stages,
        "first_failed_stage": failed_stage,
        "failure_code": failure_code,
    }
    if diagnostic is not None:
        first["root_occurrence_mapping_diagnostic"] = diagnostic
    second = {
        "particle_index": 1,
        "stages": _stages(failed=False),
        "first_failed_stage": None,
        "failure_code": None,
    }
    return {
        "schema_id": TRACE_SCHEMA,
        "attempt_status": "accepted" if accepted else "failed_closed",
        "first_failed_stage": None if accepted else failed_stage,
        "failure_code": None if accepted else failure_code,
        "accepted_root_report_returned": accepted,
        "particles": [first, second],
    }


def _accepted_identity(index: int, stratum: str = "A") -> dict[str, object]:
    identity = f"t106-id-{index}"
    seed = derive_t101_sampler_seed(identity, 0)
    return {
        "selection_identity": identity,
        "stratum": stratum,
        "source_ordinal": index,
        "selection_digest": f"digest-{index}",
        "accepted_t106_row_ordinal": index,
        "accepted_t106_producer": T106_IMPLEMENTATION_HEAD,
        "accepted_t106_artifact_hashes": dict(T106_SHA256),
        "stage_class": "ROOT_OCCURRENCE_MAPPING_FAILURE",
        "sampler_seed": seed,
    }


def _accepted_t106_row(index: int, stratum: str, stage_class: str) -> dict[str, object]:
    identity = f"t106-id-{index}"
    seed = derive_t101_sampler_seed(identity, 0)
    if stage_class == "ROOT_OCCURRENCE_MAPPING_FAILURE":
        parent_trace = _native_trace(None)
        historical_class = "BRIDGE_FAILURE_AFTER_STANDALONE_SAMPLER_SUCCESS"
        parent_code = "root_occurrence_mapping_failed"
    else:
        parent_trace = _native_trace(
            None,
            failed_stage="public_fidelity_validation",
            failure_code="anchor_unsupported_fidelity",
        )
        historical_class = "STANDALONE_SAMPLER_FAILURE"
        parent_code = "anchor_unsupported_fidelity"
    call = {
        "sampler_seed": seed,
        "particle_start": 0,
        "particle_count": 2,
        "search_simulations": 400,
        "include_potions": False,
    }
    return {
        "selection_identity": identity,
        "stratum": stratum,
        "source_ordinal": index,
        "selection_digest": f"digest-{index}",
        "accepted_t104_row_ordinal": index,
        "historical_t104_part_b_class": historical_class,
        "replicate_index": 0,
        "sampler_seed": seed,
        "current_native_identity": dict(T106_NATIVE_IDENTITY),
        "stage_class": stage_class,
        "classification_source": "native_structured_telemetry",
        "bridge_outcome": "exception",
        "bridge_invocation_status": "failed",
        "baseline_contradiction": False,
        "telemetry_contract_violation": False,
        "frozen_expected_bridge_call_parameters": call,
        "bridge_call_parameters": call,
        "native_stage_trace": parent_trace,
        "execution": {"failure_retry_status": "no_retry"},
        "parent_failure_code": parent_code,
    }


def _exact_t106_rows() -> list[dict[str, object]]:
    rows = []
    for stratum, count in (("A", 84), ("B", 174), ("C", 65)):
        rows.extend(
            _accepted_t106_row(
                index=len(rows),
                stratum=stratum,
                stage_class="ROOT_OCCURRENCE_MAPPING_FAILURE",
            )
            for _ in range(count)
        )
    rows.extend(
        _accepted_t106_row(
            index=len(rows) + i,
            stratum="A" if i < 5 else "B",
            stage_class="PUBLIC_FIDELITY_VALIDATION_FAILURE",
        )
        for i in range(20)
    )
    for ordinal, row in enumerate(rows):
        row["accepted_t104_row_ordinal"] = ordinal
    return rows


def test_exact_t106_filter_preserves_323_identity_order_and_abcs() -> None:
    rows = _exact_t106_rows()
    selected = select_t106_root_mapping_failures(rows)

    assert len(selected) == 323
    assert [row["accepted_t106_row_ordinal"] for row in selected] == list(range(323))
    assert [row["selection_identity"] for row in selected] == [
        row["selection_identity"] for row in rows[:323]
    ]
    assert Counter(row["stratum"] for row in selected) == {"A": 84, "B": 174, "C": 65}
    assert all(
        row["sampler_seed"] == derive_t101_sampler_seed(row["selection_identity"], 0)
        for row in selected
    )


def test_t106_filter_rejects_part_a_or_public_fidelity_leakage() -> None:
    rows = _exact_t106_rows()
    rows[0]["stage_class"] = "PUBLIC_PROJECTION_PARITY_FAILURE"
    with pytest.raises(T108IncompleteError, match="out-of-scope"):
        select_t106_root_mapping_failures(rows)


def test_t106_filter_rejects_a_changed_replicate_zero_seed() -> None:
    rows = _exact_t106_rows()
    rows[0]["sampler_seed"] += 1

    with pytest.raises(T108IncompleteError, match="row is inconsistent"):
        select_t106_root_mapping_failures(rows)


@pytest.mark.parametrize("subreason", sorted(FAILURE_SUBREASONS))
def test_only_validated_native_failure_subreason_sets_class(subreason: str) -> None:
    accepted = _accepted_identity(4, "B")
    trace = _native_trace(_mapping_diagnostic(subreason))
    call = {
        "sampler_seed": accepted["sampler_seed"],
        "particle_start": 0,
        "particle_count": 2,
        "search_simulations": 400,
        "include_potions": False,
    }

    row = classify_mapping_replay(
        accepted=accepted,
        bridge_outcome="exception",
        bridge_call_parameters=call,
        raw_trace=trace,
        exception_type="DiagnosticOnlyException",
        exception_signature_audit_only="safe-hash",
    )

    assert row["subreason_class"] == subreason
    assert row["mapping_subreason"] == subreason
    assert row["classification_source"] == "structured_native_mapping_diagnostic"
    assert row["diagnostic_safe_metadata_role"] == "diagnostic_only"
    assert row["baseline_contradiction"] is False
    assert row["mapping_telemetry_contract_violation"] is False
    assert "exception_message" not in row
    assert row["current_native_identity"] == NATIVE_IDENTITY


@pytest.mark.parametrize(
    "diagnostic",
    [
        None,
        _mapping_diagnostic("unknown_branch"),
        _mapping_diagnostic(
            "multiple_direct_search_root_matches",
            overrides={"raw_action_bits": "private"},
        ),
        _mapping_diagnostic(
            "no_public_legal_action_surface",
            overrides={"schema_id": "wrong-schema"},
        ),
        {
            key: value
            for key, value in _mapping_diagnostic(
                "no_public_legal_action_surface"
            ).items()
            if key != "search_root_edge_count"
        },
        {
            "schema_id": DIAGNOSTIC_SCHEMA,
            "status": "failed",
            "mapping_subreason": "mapping_completed",
            "public_legal_occurrence_count": 1,
            "search_root_edge_count": 1,
            "public_occurrences_mapped": 0,
            "search_root_edges_covered": 0,
            "direct_mapping_count": 0,
            "mechanical_duplicate_mapping_count": 0,
        },
    ],
)
def test_missing_unknown_unsafe_and_mapping_completed_diagnostics_fail_closed(
    diagnostic: dict[str, object] | None,
) -> None:
    accepted = _accepted_identity(5)
    call = {
        "sampler_seed": accepted["sampler_seed"],
        "particle_start": 0,
        "particle_count": 2,
        "search_simulations": 400,
        "include_potions": False,
    }
    row = classify_mapping_replay(
        accepted=accepted,
        bridge_outcome="exception",
        bridge_call_parameters=call,
        raw_trace=_native_trace(diagnostic),
    )
    assert row["mapping_telemetry_contract_violation"] is True
    assert row["subreason_class"] is None
    assert row["classification_source"] is None


def test_malformed_parent_trace_is_incomplete_and_parent_contradiction_is_distinct() -> (
    None
):
    accepted = _accepted_identity(6)
    call = {
        "sampler_seed": accepted["sampler_seed"],
        "particle_start": 0,
        "particle_count": 2,
        "search_simulations": 400,
        "include_potions": False,
    }
    contradictory = classify_mapping_replay(
        accepted=accepted,
        bridge_outcome="exception",
        bridge_call_parameters=call,
        raw_trace=_native_trace(
            None,
            failed_stage="public_fidelity_validation",
            failure_code="public_fidelity_failed",
        ),
    )
    assert contradictory["baseline_contradiction"] is True
    assert contradictory["mapping_telemetry_contract_violation"] is False

    returned = classify_mapping_replay(
        accepted=accepted,
        bridge_outcome="returned",
        bridge_call_parameters=call,
        raw_trace=_native_trace(_mapping_diagnostic("no_public_legal_action_surface")),
    )
    assert returned["baseline_contradiction"] is True
    assert returned["parent_first_failed_stage"] == "root_occurrence_mapping"
    assert returned["parent_failure_code"] == "root_occurrence_mapping_failed"
    assert returned["contradictory_mapping_diagnostics_role"] == (
        "validated_t107_trace_only_not_classification"
    )
    assert returned["contradictory_mapping_diagnostics"] == [
        {
            "particle_index": 0,
            "schema_id": DIAGNOSTIC_SCHEMA,
            "status": "failed",
            "mapping_subreason": "no_public_legal_action_surface",
            "diagnostic_safe_metadata": {
                "public_legal_occurrence_count": 0,
                "search_root_edge_count": 1,
                "public_occurrences_mapped": 0,
                "search_root_edges_covered": 0,
                "direct_mapping_count": 0,
                "mechanical_duplicate_mapping_count": 0,
            },
        }
    ]
    assert returned["subreason_class"] is None
    assert returned["classification_source"] is None

    completed_stages = {stage: "completed" for stage in _stages(failed=False)}
    completed_diagnostic = {
        "schema_id": DIAGNOSTIC_SCHEMA,
        "status": "completed",
        "mapping_subreason": "mapping_completed",
        "public_legal_occurrence_count": 1,
        "search_root_edge_count": 1,
        "public_occurrences_mapped": 1,
        "search_root_edges_covered": 1,
        "direct_mapping_count": 1,
        "mechanical_duplicate_mapping_count": 0,
    }
    completed_trace = {
        "schema_id": TRACE_SCHEMA,
        "attempt_status": "accepted",
        "first_failed_stage": None,
        "failure_code": None,
        "accepted_root_report_returned": True,
        "particles": [
            {
                "particle_index": index,
                "stages": completed_stages,
                "first_failed_stage": None,
                "failure_code": None,
                "root_occurrence_mapping_diagnostic": completed_diagnostic,
            }
            for index in range(2)
        ],
    }
    accepted_bridge = classify_mapping_replay(
        accepted=accepted,
        bridge_outcome="returned",
        bridge_call_parameters=call,
        raw_trace=completed_trace,
    )
    assert accepted_bridge["baseline_contradiction"] is True
    assert accepted_bridge["accepted_root_report_returned"] is True
    assert accepted_bridge["contradictory_mapping_diagnostics"] == [
        {
            "particle_index": index,
            "schema_id": DIAGNOSTIC_SCHEMA,
            "status": "completed",
            "mapping_subreason": "mapping_completed",
            "diagnostic_safe_metadata": {
                "public_legal_occurrence_count": 1,
                "search_root_edge_count": 1,
                "public_occurrences_mapped": 1,
                "search_root_edges_covered": 1,
                "direct_mapping_count": 1,
                "mechanical_duplicate_mapping_count": 0,
            },
        }
        for index in range(2)
    ]
    assert accepted_bridge["subreason_class"] is None
    assert accepted_bridge["classification_source"] is None

    malformed = _native_trace(_mapping_diagnostic("no_public_legal_action_surface"))
    malformed["private_payload"] = "must not be retained"
    invalid = classify_mapping_replay(
        accepted=accepted,
        bridge_outcome="exception",
        bridge_call_parameters=call,
        raw_trace=malformed,
    )
    assert invalid["parent_stage_contract_violation"] is True
    assert invalid["baseline_contradiction"] is False
    assert invalid["subreason_class"] is None


def test_exception_prose_never_selects_the_subreason() -> None:
    accepted = _accepted_identity(7, "C")
    call = {
        "sampler_seed": accepted["sampler_seed"],
        "particle_start": 0,
        "particle_count": 2,
        "search_simulations": 400,
        "include_potions": False,
    }
    trace = _native_trace(_mapping_diagnostic("representative_search_root_match_zero"))
    first = classify_mapping_replay(
        accepted=accepted,
        bridge_outcome="exception",
        bridge_call_parameters=call,
        raw_trace=trace,
        exception_type="RuntimeError",
        exception_signature_audit_only="one",
    )
    second = classify_mapping_replay(
        accepted=accepted,
        bridge_outcome="exception",
        bridge_call_parameters=call,
        raw_trace=deepcopy(trace),
        exception_type="DifferentError",
        exception_signature_audit_only="two",
    )
    assert first["subreason_class"] == second["subreason_class"]
    assert first["subreason_class"] == "representative_search_root_match_zero"


def test_frozen_bridge_configuration_mismatch_stops_without_classification() -> None:
    accepted = _accepted_identity(8)
    call = {
        "sampler_seed": accepted["sampler_seed"],
        "particle_start": 0,
        "particle_count": 4,
        "search_simulations": 400,
        "include_potions": False,
    }
    with pytest.raises(T108IncompleteError, match="frozen parameters"):
        classify_mapping_replay(
            accepted=accepted,
            bridge_outcome="exception",
            bridge_call_parameters=call,
            raw_trace=_native_trace(_mapping_diagnostic("uncovered_search_root_edge")),
        )


def test_immediate_adapter_reads_same_call_snapshot_on_return_and_exception() -> None:
    class Adapter:
        def __init__(self, *, fails: bool) -> None:
            self.fails = fails
            self.events: list[str] = []
            self.trace = _native_trace(
                _mapping_diagnostic("no_public_legal_action_surface")
            )

        def sample_hidden_future_particles_search(
            self, *_args: object, **_kwargs: object
        ) -> object:
            self.events.append("bridge")
            if self.fails:
                raise RuntimeError("message must not classify")
            return {"accepted": True}

        def last_particle_search_stage_diagnostics(self) -> dict[str, object]:
            self.events.append("snapshot")
            return self.trace

    for fails in (False, True):
        adapter = Adapter(fails=fails)
        capture: dict[str, object] = {}
        wrapped = _ImmediateMappingTraceAdapter(adapter, capture)
        try:
            wrapped.sample_hidden_future_particles_search(
                "clone", sampler_seed=1, particle_start=0
            )
        except RuntimeError:
            assert fails is True
        assert adapter.events == ["bridge", "snapshot"]
        assert capture["trace"] is adapter.trace


def _classified_row(index: int, stratum: str, subreason: str) -> dict[str, object]:
    return {
        "selection_identity": f"row-{index}",
        "stratum": stratum,
        "subreason_class": subreason,
        "classification_source": "structured_native_mapping_diagnostic",
        "mapping_diagnostic_status": "failed",
        "parent_first_failed_stage": "root_occurrence_mapping",
        "parent_failure_code": "root_occurrence_mapping_failed",
        "first_failing_particle_index": 0,
        "diagnostic_safe_metadata": {
            "public_action_kind": "card",
            "direct_match_multiplicity": "zero",
            "representative_match_multiplicity": "zero",
        },
        "baseline_contradiction": False,
        "parent_stage_contract_violation": False,
        "mapping_telemetry_contract_violation": False,
    }


def test_aggregate_exact_subreason_and_abc_parity_for_success() -> None:
    rows = []
    for stratum, count in (("A", 84), ("B", 174), ("C", 65)):
        rows.extend(
            _classified_row(
                len(rows), stratum, sorted(FAILURE_SUBREASONS)[len(rows) % 7]
            )
            for _ in range(count)
        )
    report = aggregate_t108(rows, full=True)

    assert (
        report["terminal_classification"]
        == "ROOT_OCCURRENCE_MAPPING_SUBREASON_CENSUS_ESTABLISHED"
    )
    assert report["valid_mapping_diagnostic_count"] == 323
    assert sum(value["count"] for value in report["failure_subreasons"].values()) == 323
    for stratum, expected in (("A", 84), ("B", 174), ("C", 65)):
        part = report["by_stratum"][stratum]
        assert part["selected_count"] == expected
        assert part["classified_count"] == expected
        assert sum(value["count"] for value in part["subreasons"].values()) == expected
    assert report["parent_first_failed_stage_counts"] == {
        "root_occurrence_mapping": 323
    }
    assert report["parent_failure_code_counts"] == {
        "root_occurrence_mapping_failed": 323
    }
    assert report["first_failing_particle_index_counts"] == {
        "0": {"count": 323, "fraction": {"numerator": 323, "denominator": 323}}
    }
    action_kind = report["safe_diagnostic_cross_tabs"]["public_action_kind"]
    assert action_kind["by_category"]["card"]["count"] == 323
    assert all(
        action_kind["by_subreason"][name]["available_count"]
        == report["failure_subreasons"][name]["count"]
        for name in FAILURE_SUBREASONS
    )
    expected_card = Counter(row["subreason_class"] for row in rows)
    assert {
        name: value["count"] for name, value in report["failure_subreasons"].items()
    } == {name: expected_card[name] for name in sorted(FAILURE_SUBREASONS)}


def test_aggregate_preserves_baseline_and_mapping_terminal_distinctions() -> None:
    baseline = _classified_row(1, "A", "uncovered_search_root_edge")
    baseline["baseline_contradiction"] = True
    invalid = _classified_row(2, "B", "uncovered_search_root_edge")
    invalid["mapping_telemetry_contract_violation"] = True
    assert aggregate_t108([baseline, invalid], full=True)[
        "terminal_classification"
    ] == ("T106_ROOT_MAPPING_BASELINE_NOT_REPRODUCED")
    assert aggregate_t108([invalid], full=True)["terminal_classification"] == (
        "NATIVE_MAPPING_OBSERVABILITY_CONTRACT_NOT_REPRODUCED"
    )
    assert (
        aggregate_t108(
            [_classified_row(3, "C", "uncovered_search_root_edge")], full=False
        )["terminal_classification"]
        == "INCOMPLETE"
    )


def test_aggregate_requires_exact_identity_order_and_stratum_coverage() -> None:
    rows = []
    for stratum, count in (("A", 84), ("B", 174), ("C", 65)):
        for _ in range(count):
            index = len(rows)
            rows.append(
                _classified_row(index, stratum, sorted(FAILURE_SUBREASONS)[index % 7])
            )
    expected = [row["selection_identity"] for row in rows]
    wrong_order = list(expected)
    wrong_order[0], wrong_order[1] = wrong_order[1], wrong_order[0]

    report = aggregate_t108(
        rows,
        full=True,
        expected_identities=wrong_order,
        expected_identity_digest="not-the-ordered-input-digest",
    )
    assert report["identity_order_matches"] is False
    assert report["identity_digest_matches"] is False
    assert report["terminal_classification"] == "INCOMPLETE"


def test_aggregate_reports_canary_selection_without_full_population_counts() -> None:
    rows = [
        _classified_row(0, "A", "uncovered_search_root_edge"),
        _classified_row(1, "C", "representative_search_root_match_zero"),
    ]
    report = aggregate_t108(
        rows,
        full=False,
        selected_count=2,
        expected_by_stratum={"A": 1, "B": 0, "C": 1},
        expected_identities=[row["selection_identity"] for row in rows],
    )

    assert report["terminal_classification"] == "INCOMPLETE"
    assert report["selected_count"] == 2
    assert report["stratum_coverage_matches"] is True
    assert {
        stratum: record["selected_count"]
        for stratum, record in report["by_stratum"].items()
    } == {"A": 1, "B": 0, "C": 1}
