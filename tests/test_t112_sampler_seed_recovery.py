from __future__ import annotations

import hashlib
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pytest
from test_t110_configuration_aware_mapping import _v2_report

from sts_combat_rl.commands import t112_sampler_seed_recovery as workflow
from sts_combat_rl.commands.t112_sampler_seed_recovery import (
    T112_AUTH_SCHEMA,
    T112_PREPARATION_SCHEMA,
    T112_QUALIFICATION_SCHEMA,
    T112_WITNESS_TERMINAL_SCHEMA,
    T112WorkflowError,
)
from sts_combat_rl.sim.t101_particle_convergence import (
    T101_SOURCE_COUNTS,
    derive_t101_sampler_seed,
)
from sts_combat_rl.sim.t111_configured_search_support import (
    T111_NATIVE_COMMIT,
    T111_NATIVE_REF,
    T111SupportExclusion,
    select_t111_configured_search_cohort,
)
from sts_combat_rl.sim.t112_sampler_seed_recovery import (
    T112_COHORT_SCHEMA,
    T112_NATIVE_IDENTITY,
    T112_REPAIR_FACTS,
    T112_REPAIR_PROVENANCE_SCHEMA,
    T112RecoveryError,
    safe_t112_native_witness_seed_metadata,
    safe_t112_seed_metadata,
    t112_cohort_from_t111,
    validate_t112_cohort,
)

_NATIVE = {
    "repository": "lsmfttb/sts_lightspeed",
    "ref": T111_NATIVE_REF,
    "commit": T111_NATIVE_COMMIT,
}
_HEAD = "a" * 40
_WITNESS_SHA = "b" * 64


def _source_population() -> list[dict[str, object]]:
    return [
        {"selection_identity": f"{stratum}:{index:03d}", "cohort": stratum}
        for stratum, count in T101_SOURCE_COUNTS.items()
        for index in range(count)
    ]


def _report(seed: int) -> dict[str, object]:
    report = _v2_report()
    first = report["particles"][0]
    first["sampler_seed"] = 0xA5100000
    first["root_evaluation"]["simulations_requested"] = 400
    first["root_evaluation"]["root_visits"] = 800
    second = deepcopy(first)
    second["particle_index"] = 1
    second["sampler_seed"] = 0xA5100001
    second["hidden_future_fingerprint"] = "private-fingerprint-never-retained"
    report.update(
        {
            "search_simulations": 400,
            "sampler_seed_input": seed,
            "particle_count": 2,
            "particles": [first, second],
        }
    )
    return report


def _recovered_t111_and_t112(*, prebridge_exclusion_limits=None):
    seed_metadata: dict[str, dict[str, object]] = {}
    call_counts: dict[str, int] = {}
    prebridge_exclusion_limits = prebridge_exclusion_limits or {}
    prebridge_seen: dict[str, int] = {}

    def admit(row):
        identity = row["selection_identity"]
        stratum = row["cohort"]
        seen = prebridge_seen.get(stratum, 0)
        prebridge_seen[stratum] = seen + 1
        if seen < prebridge_exclusion_limits.get(stratum, 0):
            raise T111SupportExclusion(
                "public_projection_parity_failure",
                evidence={"boundary": "projection_candidate_parity"},
            )
        call_counts[identity] = call_counts.get(identity, 0) + 1
        seed = derive_t101_sampler_seed(identity, 0)
        report = _report(seed)
        from sts_combat_rl.sim.t111_configured_search_support import (
            validate_t111_configured_search_report,
        )

        summary = validate_t111_configured_search_report(
            report, expected_sampler_seed=seed
        )
        seed_metadata[identity] = safe_t112_seed_metadata(
            report,
            expected_sampler_seed=seed,
            bridge_report_sha256=summary["bridge_report_sha256"],
        )
        return {
            "restore_exact_accepted_state": True,
            "public_projection_parity": True,
            "ordered_legal_action_parity": True,
            "search_configuration_unchanged": True,
            "bridge_report": report,
        }

    selected = select_t111_configured_search_cohort(
        _source_population(), native_identity=_NATIVE, admit=admit
    )
    cohort = t112_cohort_from_t111(
        selected,
        implementation_head=_HEAD,
        witness_sha256=_WITNESS_SHA,
        seed_metadata_by_identity=seed_metadata,
        bridge_call_count_by_identity=call_counts,
    )
    return selected, cohort, call_counts


def _insufficient_t111_and_t112():
    bridge_calls: dict[str, int] = {}

    def reject(row):
        identity = row["selection_identity"]
        bridge_calls[identity] = bridge_calls.get(identity, 0) + 1
        raise T111SupportExclusion(
            "searched_value_unavailable_nonfinite_or_unvisited",
            evidence={
                "boundary": "strict_t110_configured_search_validation",
                "field": "mean_value",
            },
        )

    selected = select_t111_configured_search_cohort(
        _source_population(), native_identity=_NATIVE, admit=reject
    )
    cohort = t112_cohort_from_t111(
        selected,
        implementation_head=_HEAD,
        witness_sha256=_WITNESS_SHA,
        bridge_call_count_by_identity=bridge_calls,
    )
    return selected, cohort, bridge_calls


@pytest.mark.parametrize("merge_base_returncode", [0, 1])
def test_t112_current_worktree_uses_wsl_windows_git_fallback_for_ancestry(
    monkeypatch, tmp_path: Path, merge_base_returncode: int
):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    (repo_root / ".git").write_text(
        "gitdir: D:/DeadlyCatCoding/STSRL/.git/worktrees/STSRL-T112\n",
        encoding="utf-8",
    )
    windows_root = "D:\\DeadlyCatCoding\\STSRL-T112"
    head = "a" * 40
    calls = []

    def fake_run(command, **_kwargs):
        calls.append(command)
        if command[0] == "git":
            raise workflow.t111_preparation.subprocess.CalledProcessError(128, command)
        if command[:2] == ["wslpath", "-w"]:
            return SimpleNamespace(stdout=f"{windows_root}\n")
        if command[0] == "git.exe":
            arguments = command[3:]
            if arguments == ["rev-parse", "HEAD"]:
                return SimpleNamespace(stdout=f"{head}\n")
            if arguments == ["branch", "--show-current"]:
                return SimpleNamespace(stdout=f"{workflow.T112_BRANCH}\n")
            if arguments == ["status", "--porcelain"]:
                return SimpleNamespace(stdout="")
            if arguments == [
                "merge-base",
                "--is-ancestor",
                workflow.T112_APPROVED_SPEC_COMMIT,
                head,
            ]:
                if merge_base_returncode == 0:
                    return SimpleNamespace(stdout="")
                raise workflow.t111_preparation.subprocess.CalledProcessError(
                    merge_base_returncode, command
                )
        raise AssertionError(f"unexpected subprocess command: {command!r}")

    monkeypatch.setattr(workflow.t111_preparation.sys, "platform", "linux")
    monkeypatch.setattr(workflow.t111_preparation.subprocess, "run", fake_run)

    if merge_base_returncode == 0:
        assert workflow._verify_current_worktree(repo_root, head) == {
            "head": head,
            "branch": workflow.T112_BRANCH,
            "clean": True,
        }
    else:
        with pytest.raises(T112WorkflowError):
            workflow._verify_current_worktree(repo_root, head)

    merge_calls = [
        call for call in calls if call[0] == "git.exe" and "merge-base" in call
    ]
    assert len(merge_calls) == 1
    assert merge_calls[0][2] == windows_root


def test_t112_prebridge_exclusion_is_retained_and_recovery_continues():
    t111, cohort, call_counts = _recovered_t111_and_t112(
        prebridge_exclusion_limits={"A": 1}
    )

    result = validate_t112_cohort(cohort)
    first_a = next(row for row in result["attempted"] if row["stratum"] == "A")

    assert (
        result["terminal_classification"]
        == "CONFIGURED_SEARCH_DOMAIN_SUPPORT_RECOVERED"
    )
    assert result["selected_counts"] == {"A": 8, "B": 8, "C": 8}
    assert len(result["attempted"]) == 25
    assert first_a["admitted"] is False
    assert first_a["failure_retry_status"] == "failed_no_retry"
    assert first_a["candidate_execution_started"] is False
    assert first_a["native_bridge_call_count"] == 0
    assert first_a["exclusion_reason"] == "public_projection_parity_failure"
    assert first_a["exclusion_evidence"]["boundary"] == "projection_candidate_parity"
    assert first_a["particle_sampler_seed_metadata"] == {
        "schema_id": None,
        "bridge_report_sha256": None,
        "sampler_seed_input": None,
        "particles": None,
    }
    attempts_jsonl_row = workflow._t112_attempt_row(
        next(row for row in t111["attempted"] if row["stratum"] == "A"),
        seed_metadata_by_identity={},
        bridge_call_count_by_identity=call_counts,
        shard={
            "worker_id": "worker-0",
            "shard_id": "shard-0",
            "candidate_range": [0, 413],
        },
    )
    assert attempts_jsonl_row["candidate_execution_started"] is False
    assert attempts_jsonl_row["native_bridge_call_count"] == 0
    assert (
        attempts_jsonl_row["exclusion_evidence"]["boundary"]
        == "projection_candidate_parity"
    )
    assert len(call_counts) == 24 and set(call_counts.values()) == {1}
    assert t111["selected_counts"] == {"A": 8, "B": 8, "C": 8}
    assert workflow._t112_exclusion_distributions(result["attempted"]) == (
        {"public_projection_parity_failure": 1},
        {"public_projection_parity_failure|projection_candidate_parity": 1},
    )


def test_t112_exhaustion_retains_prebridge_blocking_distribution():
    _t111, cohort, call_counts = _recovered_t111_and_t112(
        prebridge_exclusion_limits={"A": T101_SOURCE_COUNTS["A"]}
    )

    result = validate_t112_cohort(cohort)
    a_rows = [row for row in result["attempted"] if row["stratum"] == "A"]
    reason_counts, boundary_counts = workflow._t112_exclusion_distributions(
        result["attempted"]
    )

    assert (
        result["terminal_classification"]
        == "CONFIGURED_SEARCH_DOMAIN_SUPPORT_STILL_INSUFFICIENT"
    )
    assert result["selected_counts"] == {"A": 0, "B": 8, "C": 8}
    assert result["exhausted_strata"] == ["A"]
    assert len(a_rows) == T101_SOURCE_COUNTS["A"]
    assert all(
        row["candidate_execution_started"] is False
        and row["native_bridge_call_count"] == 0
        and row["admitted"] is False
        for row in a_rows
    )
    assert set(call_counts.values()) == {1}
    assert reason_counts == {
        "public_projection_parity_failure": T101_SOURCE_COUNTS["A"]
    }
    assert boundary_counts == {
        "public_projection_parity_failure|projection_candidate_parity": T101_SOURCE_COUNTS[
            "A"
        ]
    }


def test_t112_cohort_uses_t111_hash_order_first_eight_and_explicit_seed_semantics():
    t111, cohort, call_counts = _recovered_t111_and_t112()

    result = validate_t112_cohort(cohort)

    assert result["schema_id"] == T112_COHORT_SCHEMA
    assert result["task_id"] == "T112"
    assert result["approved_spec_commit"] == "2b45eab755ee0b528b7816d0f2b4089095c0776a"
    assert (
        result["terminal_classification"]
        == "CONFIGURED_SEARCH_DOMAIN_SUPPORT_RECOVERED"
    )
    assert result["selected_counts"] == {"A": 8, "B": 8, "C": 8}
    assert len(result["attempted"]) == 24
    assert len(result["selected"]) == 24
    assert len(call_counts) == 24 and set(call_counts.values()) == {1}
    assert all(row.get("sampler_seed") is None for row in result["attempted"])
    for row in result["attempted"]:
        assert row["sampler_seed_input"] == derive_t101_sampler_seed(
            row["selection_identity"], 0
        )
        assert row["native_bridge_call_count"] == 1
        assert row["failure_retry_status"] == "success_no_retry"
        assert (
            row["particle_sampler_seed_metadata"]["sampler_seed_input"]
            == row["sampler_seed_input"]
        )
        assert row["particle_sampler_seed_metadata"]["particles"] == [
            {"particle_index": 0, "sampler_seed": 0xA5100000},
            {"particle_index": 1, "sampler_seed": 0xA5100001},
        ]
        assert "hidden_future_fingerprint" not in row["particle_sampler_seed_metadata"]
    assert t111["selected_counts"] == {"A": 8, "B": 8, "C": 8}


def test_t112_insufficient_selector_exhausts_without_historical_label_admission():
    _t111, cohort, bridge_calls = _insufficient_t111_and_t112()

    result = validate_t112_cohort(cohort)

    assert (
        result["terminal_classification"]
        == "CONFIGURED_SEARCH_DOMAIN_SUPPORT_STILL_INSUFFICIENT"
    )
    assert result["selected_counts"] == {"A": 0, "B": 0, "C": 0}
    assert result["exhausted_strata"] == ["A", "B", "C"]
    assert len(result["attempted"]) == 413
    assert result["historical_t111_attempts_used_for_admission"] is False
    assert set(bridge_calls.values()) == {1}
    assert all(
        row["particle_sampler_seed_metadata"]
        == {
            "schema_id": None,
            "bridge_report_sha256": None,
            "sampler_seed_input": None,
            "particles": None,
        }
        for row in result["attempted"]
    )


def test_t112_safe_seed_metadata_keeps_bridge_and_derived_fields_distinct():
    identity = "A:fixture"
    expected = derive_t101_sampler_seed(identity, 0)
    report = _report(expected)
    from sts_combat_rl.sim.t111_configured_search_support import (
        validate_t111_configured_search_report,
    )

    report_sha = validate_t111_configured_search_report(
        report, expected_sampler_seed=expected
    )["bridge_report_sha256"]

    metadata = safe_t112_seed_metadata(
        report, expected_sampler_seed=expected, bridge_report_sha256=report_sha
    )

    assert metadata == {
        "schema_id": "native-battle-public-particle-search-v2",
        "sampler_seed_input": expected,
        "bridge_report_sha256": report_sha,
        "particles": [
            {"particle_index": 0, "sampler_seed": 0xA5100000},
            {"particle_index": 1, "sampler_seed": 0xA5100001},
        ],
    }
    assert all(row["sampler_seed"] != expected for row in metadata["particles"])


@pytest.mark.parametrize(
    "mutation",
    [
        lambda report: report.update(sampler_seed_input=True),
        lambda report: report["particles"][0].pop("sampler_seed"),
        lambda report: report["particles"][0].update(sampler_seed="derived"),
        lambda report: report["particles"][0].update(sampler_seed=True),
        lambda report: report["particles"][1].update(particle_index=0),
        lambda report: report["particles"].reverse(),
    ],
)
def test_t112_safe_seed_metadata_rejects_wrong_bridge_or_particle_schema(mutation):
    expected = derive_t101_sampler_seed("A:fixture", 0)
    report = _report(expected)
    mutation(report)

    with pytest.raises(T112RecoveryError):
        safe_t112_seed_metadata(
            report, expected_sampler_seed=expected, bridge_report_sha256="c" * 64
        )


def test_t112_native_witness_validator_ignores_non_seed_t111_support_failure():
    from sts_combat_rl.sim.t111_configured_search_support import (
        validate_t111_configured_search_report,
    )

    expected = derive_t101_sampler_seed("A:fixture", 0)
    report = _report(expected)
    report["particles"][0]["root_rows"][0]["mean_value"] = None
    with pytest.raises(T111SupportExclusion):
        validate_t111_configured_search_report(report, expected_sampler_seed=expected)

    metadata = safe_t112_native_witness_seed_metadata(
        report,
        expected_sampler_seed=expected,
        bridge_report_sha256="c" * 64,
    )
    assert metadata["sampler_seed_input"] == expected
    assert metadata["particles"] == [
        {"particle_index": 0, "sampler_seed": 0xA5100000},
        {"particle_index": 1, "sampler_seed": 0xA5100001},
    ]


@pytest.mark.parametrize(
    "mutation",
    [
        lambda report: report.update(sampler_seed_input=True),
        lambda report: report.update(sampler_seed_input=0),
        lambda report: report.update(schema_id="unknown"),
        lambda report: report.update(native_api="wrong-native-api"),
        lambda report: report.update(particle_start=True),
        lambda report: report["particles"][0].update(particle_index=True),
        lambda report: report["particles"].reverse(),
        lambda report: report["particles"][1].update(sampler_seed=True),
        lambda report: report["particles"][1].update(sampler_seed="native"),
    ],
)
def test_t112_native_witness_validator_rejects_seed_or_native_identity_mutation(
    mutation,
):
    expected = derive_t101_sampler_seed("A:fixture", 0)
    report = _report(expected)
    mutation(report)
    with pytest.raises(T112RecoveryError):
        safe_t112_native_witness_seed_metadata(
            report,
            expected_sampler_seed=expected,
            bridge_report_sha256="c" * 64,
        )


def test_t112_bridge_seed_integer_mutation_fails_closed():
    expected = derive_t101_sampler_seed("A:fixture", 0)
    report = _report(expected)
    report["sampler_seed_input"] = (expected + 1) % 2**64
    with pytest.raises(T112RecoveryError):
        safe_t112_seed_metadata(
            report, expected_sampler_seed=expected, bridge_report_sha256="c" * 64
        )


def test_t112_artifact_does_not_accept_a_t111_terminal_label_or_schema():
    _t111, cohort, _calls = _recovered_t111_and_t112()
    cohort["schema_id"] = "t111-configured-search-cohort-admission-v1"

    with pytest.raises(T112RecoveryError):
        validate_t112_cohort(cohort)


def test_t112_cohort_rejects_attempt_after_eighth_success():
    _t111, cohort, _calls = _recovered_t111_and_t112()
    cohort["attempted"][7]["source_ordinal"] = 8

    with pytest.raises(T112RecoveryError):
        validate_t112_cohort(cohort)


@pytest.mark.parametrize(
    ("bridge_call_count", "candidate_execution_started"),
    [(2, True), (True, True), (0, True), (1, False)],
)
def test_t112_cohort_rejects_impossible_bridge_boundary_combinations(
    bridge_call_count, candidate_execution_started
):
    _t111, cohort, _calls = _recovered_t111_and_t112()
    cohort["attempted"][0]["native_bridge_call_count"] = bridge_call_count
    cohort["attempted"][0]["candidate_execution_started"] = candidate_execution_started

    with pytest.raises(T112RecoveryError):
        validate_t112_cohort(cohort)


@pytest.mark.parametrize(
    ("bridge_call_count", "candidate_execution_started", "boundary"),
    [
        (0, False, "single_n2_search_v2_bridge_call"),
        (1, True, "projection_candidate_parity"),
        (0, False, "unrecognized_boundary"),
    ],
)
def test_t112_cohort_rejects_impossible_exclusion_boundary_call_pairs(
    bridge_call_count, candidate_execution_started, boundary
):
    _t111, cohort, _calls = _recovered_t111_and_t112()
    row = cohort["attempted"][0]
    row["admitted"] = False
    row["failure_retry_status"] = "failed_no_retry"
    row["native_bridge_call_count"] = bridge_call_count
    row["candidate_execution_started"] = candidate_execution_started
    row["exclusion_reason"] = "restore_or_provenance_incompatible"
    row["exclusion_evidence"] = {"boundary": boundary}
    row["particle_sampler_seed_metadata"] = {
        "schema_id": None,
        "bridge_report_sha256": None,
        "sampler_seed_input": None,
        "particles": None,
    }

    with pytest.raises(T112RecoveryError):
        validate_t112_cohort(cohort)


def test_t112_insufficient_cohort_requires_full_exhausted_stratum():
    _t111, cohort, _calls = _insufficient_t111_and_t112()
    first_a = next(
        index for index, row in enumerate(cohort["attempted"]) if row["stratum"] == "A"
    )
    del cohort["attempted"][first_a + 1]

    with pytest.raises(T112RecoveryError):
        validate_t112_cohort(cohort)


def _qualification_and_readiness(tmp_path: Path, head: str):
    native_manifest_path = tmp_path / "native-manifest.json"
    native_manifest_path.write_text("{}\n", encoding="utf-8")
    source_ref = workflow._artifact_ref(
        native_manifest_path, schema_id="sts-lightspeed-source-manifest-v1"
    )
    repair = {
        "schema_id": T112_REPAIR_PROVENANCE_SCHEMA,
        "task_id": "T112",
        "implementation_head": head,
        "approved_spec_commit": "2b45eab755ee0b528b7816d0f2b4089095c0776a",
        "native_identity": T112_NATIVE_IDENTITY,
        **T112_REPAIR_FACTS,
    }
    repair_ref = workflow._write_new_json(
        tmp_path / "t112-validator-repair-provenance.json", repair
    )
    qualification = {
        "schema_id": T112_QUALIFICATION_SCHEMA,
        "task_id": "T112",
        "approved_spec_commit": "2b45eab755ee0b528b7816d0f2b4089095c0776a",
        "implementation_head": head,
        "implementation_worktree_path": str(tmp_path.resolve()),
        "validator_repair_provenance_artifact": repair_ref,
        "eligible": True,
        "candidate_execution_started": False,
        "native_identity": T112_NATIVE_IDENTITY,
        "current_native_source_manifest": source_ref,
        "source_population": {
            "record_count": 413,
            "source_counts": dict(T101_SOURCE_COUNTS),
            "historical_t101_attempt_order_exact": True,
        },
        "raw_bridge_reports": {
            "eligible_for_reuse": False,
            "reason": workflow.T112_RAW_REPORTS_INELIGIBLE,
            "candidate_rows_with_null_bridge_report_sha256": 413,
            "historical_exclusion_labels_used_for_admission": False,
        },
    }
    qualification_path = tmp_path / "t112-input-qualification.json"
    qualification_ref = workflow._write_new_json(qualification_path, qualification)
    readiness = {
        "schema_id": T112_PREPARATION_SCHEMA,
        "task_id": "T112",
        "preparation_only": True,
        "implementation_head": head,
        "approved_spec_commit": "2b45eab755ee0b528b7816d0f2b4089095c0776a",
        "candidate_execution_started": False,
        "qualification_sha256": qualification_ref["sha256"],
        "validator_repair_provenance_artifact": repair_ref,
        "candidate_execution_authorized": False,
        "raw_t111_report_reuse": False,
        "frozen_configuration": {
            "source_counts": dict(T101_SOURCE_COUNTS),
            "particle_start": 0,
            "particle_count": 2,
            "replicate_index": 0,
            "search_simulations_per_particle": 400,
            "include_potions": False,
            "policy_prior": False,
            "learned_leaf_value": False,
            "progressive_bias": False,
            "retry_count": 0,
        },
    }
    readiness_path = tmp_path / "t112-readiness-preparation.json"
    readiness_ref = workflow._write_new_json(readiness_path, readiness)
    return (
        qualification,
        qualification_path,
        qualification_ref,
        readiness,
        readiness_path,
        readiness_ref,
        source_ref,
        native_manifest_path,
    )


def _stage_authorization(
    tmp_path: Path,
    *,
    stage: str,
    head: str,
    qualification_ref,
    readiness_ref,
    source_ref,
    binary_path: Path,
    resource_status_path: Path,
    witness_terminal_ref=None,
):
    guard = {
        "memory_budget_mib": 4096,
        "memory_request_mib": 3072,
        "runtime_rss_limit_mib": 2048,
        "runtime_memavailable_floor_mib": 1024,
        "runtime_sample_seconds": 1,
        "status_path": str(resource_status_path.resolve()),
        "resource_root": str(tmp_path.resolve()),
        "batch_id": f"t112-{stage}-batch",
        "job_id": f"t112-{stage}-job",
    }
    shard = {
        "worker_id": "worker-0",
        "shard_id": "shard-0",
        "candidate_range": [0, 1] if stage == "witness" else [0, 413],
    }
    if stage == "cohort":
        shard["stratum_ranges"] = {"A": [0, 93], "B": [93, 285], "C": [285, 413]}
    value = {
        "schema_id": T112_AUTH_SCHEMA,
        "task_id": "T112",
        "stage": stage,
        "authorization_id": f"auth-{stage}",
        "authorized": True,
        "decision": (
            "N2_NATIVE_WITNESS_AUTHORIZED"
            if stage == "witness"
            else "BOUNDED_COHORT_EXECUTION_AUTHORIZED"
        ),
        "approval": {
            "kind": "github_pr_comment",
            "reference": f"https://github.com/lsmfttb/STSRL/pull/130#issuecomment-{121 if stage == 'witness' else 122}",
            "approved_stage": stage,
            "implementation_head": head,
            "decision": "APPROVED",
        },
        "implementation_worktree_path": str(tmp_path.resolve()),
        "implementation_head": head,
        "approved_spec_commit": "2b45eab755ee0b528b7816d0f2b4089095c0776a",
        "qualification_artifact": qualification_ref,
        "readiness_artifact": readiness_ref,
        "native_identity": T112_NATIVE_IDENTITY,
        "native_source_manifest_artifact": source_ref,
        "native_binary": {
            "path": str(binary_path.resolve()),
            "sha256": workflow._sha256_file(binary_path),
            "size_bytes": binary_path.stat().st_size,
        },
        "resource_plan": {
            "effective_worker_count": 1,
            "shard_count": 1,
            "shards": [shard],
            "resource_guard": guard,
        },
    }
    if stage == "cohort":
        value["witness_terminal_artifact"] = witness_terminal_ref
    return value


def test_t112_preparation_binds_contract_head_and_explicitly_rejects_old_report_reuse(
    tmp_path, monkeypatch
):
    head = "d" * 40
    t101_manifest = tmp_path / "t101-retention.json"
    t101_manifest.write_text("{}\n", encoding="utf-8")
    t111_manifest = tmp_path / "t111-retention.json"
    t111_manifest.write_text("{}\n", encoding="utf-8")
    native_manifest = tmp_path / "current-native-manifest.json"
    native_manifest.write_text("{}\n", encoding="utf-8")
    source_ref = workflow._artifact_ref(
        native_manifest, schema_id="sts-lightspeed-source-manifest-v1"
    )
    source_ref["capabilities"] = ["native_stsr009_configuration_aware_root_mapping"]
    t111_head = "e" * 40
    source_population = {
        "record_count": 413,
        "source_counts": dict(T101_SOURCE_COUNTS),
        "historical_t101_attempt_order_exact": True,
        "ordered_identity_binding_sha256": "f" * 64,
        "attempted_count": 413,
        "historical_selected_count": 0,
    }

    def fake_verify_t111(_path):
        return {
            "retention_manifest": workflow._artifact_ref(
                t111_manifest, schema_id="t111-terminal-retention-manifest-v1"
            ),
            "implementation_head": t111_head,
            "approved_spec_commit": "f" * 40,
            "terminal_classification": "CONFIGURED_SEARCH_DOMAIN_SUPPORT_INSUFFICIENT",
            "verified_artifacts": {},
            "source_counts": dict(T101_SOURCE_COUNTS),
            "attempted_count": 413,
            "selected_counts": {"A": 0, "B": 0, "C": 0},
            "raw_bridge_reports": {
                "eligible_for_reuse": False,
                "reason": workflow.T112_RAW_REPORTS_INELIGIBLE,
                "candidate_rows_with_null_bridge_report_sha256": 413,
                "historical_exclusion_labels_used_for_admission": False,
            },
        }

    def fake_prior_prepare(*, implementation_head, artifact_root, **_kwargs):
        assert implementation_head == t111_head
        qualification = {
            "schema_id": "t111-input-qualification-v1",
            "task_id": "T111",
            "implementation_head": t111_head,
            "approved_spec_commit": workflow.t111_preparation.T111_APPROVED_SPEC_COMMIT,
            "python_runtime": {"implementation": "CPython", "version": [3, 13]},
            "eligible": True,
            "candidate_execution_started": False,
            "native_identity": T112_NATIVE_IDENTITY,
            "current_source_manifest": source_ref,
            "source_population": source_population,
        }
        q_ref = workflow._write_new_json(
            artifact_root / "t111-input-qualification.json", qualification
        )
        readiness_ref = workflow._write_new_json(
            artifact_root / "t111-readiness-preparation.json",
            {"schema_id": "t111-execution-readiness-preparation-v1"},
        )
        return {
            "qualification": qualification,
            "qualification_artifact": q_ref,
            "readiness_preparation_artifact": readiness_ref,
        }

    monkeypatch.setattr(
        workflow, "_git_state", lambda _root: (head, workflow.T112_BRANCH, False)
    )
    monkeypatch.setattr(workflow, "_contract_is_ancestor", lambda _root, _head: True)
    monkeypatch.setattr(workflow, "_verify_t111_terminal_inputs", fake_verify_t111)
    monkeypatch.setattr(
        workflow.t111_preparation,
        "prepare_t111_input_qualification_from_paths",
        fake_prior_prepare,
    )
    monkeypatch.setattr(
        workflow.t111_preparation,
        "_source_manifest_identity",
        lambda _path: (T112_NATIVE_IDENTITY, source_ref),
    )

    result = workflow.prepare_t112_inputs(
        t101_retention_manifest_path=t101_manifest,
        t111_retention_manifest_path=t111_manifest,
        current_native_source_manifest_path=native_manifest,
        artifact_root=tmp_path / "t112-preparation",
        repo_root=tmp_path,
    )

    qualification = result["qualification"]
    readiness = result["readiness_preparation"]
    assert qualification["task_id"] == "T112"
    assert (
        qualification["approved_spec_commit"]
        == "2b45eab755ee0b528b7816d0f2b4089095c0776a"
    )
    assert qualification["implementation_head"] == head
    assert qualification["validator_repair_provenance_artifact"]["schema_id"] == (
        T112_REPAIR_PROVENANCE_SCHEMA
    )
    assert qualification["source_population"] == source_population
    assert qualification["raw_bridge_reports"]["eligible_for_reuse"] is False
    assert (
        qualification["raw_bridge_reports"][
            "candidate_rows_with_null_bridge_report_sha256"
        ]
        == 413
    )
    assert (
        qualification["raw_bridge_reports"][
            "historical_exclusion_labels_used_for_admission"
        ]
        is False
    )
    assert readiness["candidate_execution_authorized"] is False
    assert readiness["candidate_status"] == "BLOCKED_UNTIL_WITNESS_ACCEPTED"


def test_t112_stage_authorization_requires_independent_approved_witness_and_exact_resources(
    tmp_path, monkeypatch
):
    head = "d" * 40
    (
        qualification,
        qualification_path,
        qualification_ref,
        readiness,
        readiness_path,
        readiness_ref,
        source_ref,
        _native_manifest,
    ) = _qualification_and_readiness(tmp_path, head)
    del qualification, readiness
    binary = tmp_path / "native-extension.pyd"
    binary.write_bytes(b"native image placeholder")
    monkeypatch.setattr(
        workflow,
        "_git_state",
        lambda _root: (head, workflow.T112_BRANCH, False),
    )
    monkeypatch.setattr(workflow, "_contract_is_ancestor", lambda _root, _head: True)
    monkeypatch.setattr(
        workflow.t111_preparation,
        "_python_runtime_fingerprint",
        lambda: {"implementation": "CPython", "version": [3, 13]},
    )
    monkeypatch.setattr(
        workflow.t111_preparation,
        "_validate_native_binary_abi_path",
        lambda path, _runtime: path.resolve(),
    )
    resource_status = tmp_path / "witness-status.json"
    auth = _stage_authorization(
        tmp_path,
        stage="witness",
        head=head,
        qualification_ref=qualification_ref,
        readiness_ref=readiness_ref,
        source_ref=source_ref,
        binary_path=binary,
        resource_status_path=resource_status,
    )
    auth_path = tmp_path / "witness-authorization.json"
    workflow._write_new_json(auth_path, auth)
    validated = workflow.validate_t112_stage_authorization(
        auth,
        authorization_path=auth_path,
        stage="witness",
        qualification_path=qualification_path,
        readiness_path=readiness_path,
        resource_status_path=resource_status,
        repo_root=tmp_path,
    )
    assert validated["authorization"]["stage"] == "witness"

    candidate_status = tmp_path / "candidate-status.json"
    witness_terminal = {
        "schema_id": T112_WITNESS_TERMINAL_SCHEMA,
        "task_id": "T112",
        "implementation_head": head,
        "approved_spec_commit": "2b45eab755ee0b528b7816d0f2b4089095c0776a",
        "stage_outcome": "N2_WITNESS_SEED_CONTRACT_ACCEPTED",
        "native_identity": T112_NATIVE_IDENTITY,
        "native_binary": auth["native_binary"],
        "native_source_manifest_artifact": source_ref,
        "qualification_artifact": qualification_ref,
        "witness_status": "ACCEPTED",
        "terminal_classification": None,
        "bridge_call_count": 1,
        "retry_count": 0,
    }
    witness_path = tmp_path / "witness-terminal.json"
    witness_ref = workflow._write_new_json(witness_path, witness_terminal)
    cohort_auth = _stage_authorization(
        tmp_path,
        stage="cohort",
        head=head,
        qualification_ref=qualification_ref,
        readiness_ref=readiness_ref,
        source_ref=source_ref,
        binary_path=binary,
        resource_status_path=candidate_status,
        witness_terminal_ref=witness_ref,
    )
    cohort_auth_path = tmp_path / "cohort-authorization.json"
    workflow._write_new_json(cohort_auth_path, cohort_auth)
    validated_cohort = workflow.validate_t112_stage_authorization(
        cohort_auth,
        authorization_path=cohort_auth_path,
        stage="cohort",
        qualification_path=qualification_path,
        readiness_path=readiness_path,
        resource_status_path=candidate_status,
        repo_root=tmp_path,
        witness_terminal_path=witness_path,
    )
    assert validated_cohort["witness_terminal"]["witness_status"] == "ACCEPTED"

    nonseed_terminal = dict(witness_terminal)
    nonseed_terminal.update(
        {
            "stage_outcome": "N2_WITNESS_NON_SEED_SUPPORT_EXCLUSION",
            "witness_status": "REJECTED",
        }
    )
    nonseed_path = tmp_path / "nonseed-witness-terminal.json"
    nonseed_ref = workflow._write_new_json(nonseed_path, nonseed_terminal)
    blocked_auth = _stage_authorization(
        tmp_path,
        stage="cohort",
        head=head,
        qualification_ref=qualification_ref,
        readiness_ref=readiness_ref,
        source_ref=source_ref,
        binary_path=binary,
        resource_status_path=tmp_path / "blocked-candidate-status.json",
        witness_terminal_ref=nonseed_ref,
    )
    blocked_auth_path = tmp_path / "blocked-cohort-authorization.json"
    workflow._write_new_json(blocked_auth_path, blocked_auth)
    with pytest.raises(T112WorkflowError):
        workflow.validate_t112_stage_authorization(
            blocked_auth,
            authorization_path=blocked_auth_path,
            stage="cohort",
            qualification_path=qualification_path,
            readiness_path=readiness_path,
            resource_status_path=tmp_path / "blocked-candidate-status.json",
            repo_root=tmp_path,
            witness_terminal_path=nonseed_path,
        )

    rejected = dict(cohort_auth)
    rejected["implementation_head"] = "e" * 40
    with pytest.raises(T112WorkflowError):
        workflow.validate_t112_stage_authorization(
            rejected,
            authorization_path=cohort_auth_path,
            stage="cohort",
            qualification_path=qualification_path,
            readiness_path=readiness_path,
            resource_status_path=candidate_status,
            repo_root=tmp_path,
            witness_terminal_path=witness_path,
        )


def test_t112_repair_provenance_fails_closed_if_false_equality_returns(tmp_path):
    qualification, _, _, readiness, _, _, _, _ = _qualification_and_readiness(
        tmp_path, _HEAD
    )
    changed = {
        "schema_id": T112_REPAIR_PROVENANCE_SCHEMA,
        "task_id": "T112",
        "implementation_head": _HEAD,
        "approved_spec_commit": "2b45eab755ee0b528b7816d0f2b4089095c0776a",
        "native_identity": T112_NATIVE_IDENTITY,
        **T112_REPAIR_FACTS,
    }
    changed["corrected_invariants"] = dict(changed["corrected_invariants"])
    changed["corrected_invariants"]["particle_seed_equals_bridge_input_required"] = True
    ref = workflow._write_new_json(tmp_path / "changed-repair-provenance.json", changed)
    qualification["validator_repair_provenance_artifact"] = ref
    readiness["validator_repair_provenance_artifact"] = ref

    with pytest.raises(T112WorkflowError):
        workflow._verify_repair_provenance(
            qualification, readiness, implementation_head=_HEAD
        )


def test_t112_witness_is_seed_only_one_call_and_never_uses_t111_runner_or_selector(
    tmp_path, monkeypatch
):
    head = "d" * 40
    auth_path = tmp_path / "authorization.json"
    authorization = {
        "schema_id": T112_AUTH_SCHEMA,
        "stage": "witness",
        "authorization_id": "witness-auth",
        "implementation_head": head,
    }
    authorization_ref = workflow._write_new_json(auth_path, authorization)
    identity = "A:fixture"
    seed = derive_t101_sampler_seed(identity, 0)
    report = _report(seed)
    # The Stage-1 causal boundary deliberately ignores these T111 support
    # details. The original T111 validator remains exercised by its own tests
    # and by the separately authorized Stage-2 selector.
    report["particles"][0]["root_rows"][0]["mean_value"] = None
    bridge_calls = []

    class Adapter:
        def sample_hidden_future_particles_search(self, restored, **kwargs):
            bridge_calls.append((restored, kwargs))
            return report

        def close(self):
            return None

    adapter = Adapter()

    def fake_source_records(_validated, *, t101_manifest_path):
        assert t101_manifest_path == tmp_path / "t101.json"
        return (
            [{"selection_identity": identity, "cohort": "A"}],
            {"A": {identity: object()}},
            {identity: object()},
            {"source_population": {"record_count": 413}},
        )

    def fake_factory(_binary):
        return lambda: adapter, [adapter]

    def fake_validate(_auth, **_kwargs):
        return {
            "authorization": {
                **authorization,
                "authorization_id": "witness-auth",
                "implementation_head": head,
                "native_binary": {
                    "path": "binary",
                    "sha256": "e" * 64,
                    "size_bytes": 1,
                },
            },
            "authorization_sha256": authorization_ref["sha256"],
            "authorization_artifact": authorization_ref,
            "qualification_artifact": {"path": "qualification", "sha256": "b" * 64},
            "readiness_artifact": {"path": "readiness", "sha256": "c" * 64},
            "native_source_manifest_artifact": {"path": "manifest", "sha256": "d" * 64},
            "native_binary": {"path": "binary", "sha256": "e" * 64, "size_bytes": 1},
            "resource_plan": {
                "resource_guard": {
                    "batch_id": "batch",
                    "job_id": "job",
                    "resource_root": str(tmp_path),
                }
            },
        }

    monkeypatch.setattr(
        workflow, "os", SimpleNamespace(name="posix", getpid=lambda: 123)
    )
    monkeypatch.setattr(workflow, "validate_t112_stage_authorization", fake_validate)
    monkeypatch.setattr(
        workflow, "_active_guard", lambda *_args, **_kwargs: {"state": "ARMED"}
    )
    monkeypatch.setattr(workflow, "_source_records_for_run", fake_source_records)
    monkeypatch.setattr(workflow, "_adapter_factory_for_binary", fake_factory)
    monkeypatch.setattr(
        workflow,
        "restore_t085_canonical_record",
        lambda _adapter, _selected, _canonical: (object(), "mock_restore"),
    )
    monkeypatch.setattr(
        workflow,
        "_runner_for",
        lambda *_args, **_kwargs: pytest.fail(
            "Stage-1 witness must not invoke T111NativeRecordRunner"
        ),
    )
    monkeypatch.setattr(
        workflow,
        "_validate_t112_guard_status",
        lambda *_args, **_kwargs: (
            {},
            {
                "state": "COMPLETED",
                "sample_count": 1,
                "peak_rss_mib": 1,
                "lowest_memavailable_mib": 1,
                "rss_limit_mib": 8192,
                "memavailable_floor_mib": 8192,
                "sample_interval_seconds": 1,
            },
        ),
    )
    monkeypatch.setattr(
        workflow,
        "select_t111_configured_search_cohort",
        lambda *_args, **_kwargs: pytest.fail("witness must never invoke selector"),
    )

    result = workflow.execute_t112_witness(
        authorization_path=auth_path,
        qualification_path=tmp_path / "qualification.json",
        readiness_path=tmp_path / "readiness.json",
        resource_status_path=tmp_path / "resource-status.json",
        t101_manifest_path=tmp_path / "t101.json",
        witness_output_root=tmp_path / "witness-output",
        repo_root=tmp_path,
    )
    finalized = workflow.finalize_t112_witness(
        witness_output_root=tmp_path / "witness-output",
        resource_status_path=tmp_path / "resource-status.json",
    )

    import json

    witness = json.loads(
        Path(result["witness_artifact"]["path"]).read_text(encoding="utf-8")
    )
    assert len(bridge_calls) == 1
    assert bridge_calls[0][1] == {
        "sampler_seed": seed,
        "particle_start": 0,
        "particle_count": 2,
        "search_simulations": 400,
        "include_potions": False,
    }
    assert witness["schema_id"] == "t112-native-n2-witness-v3"
    assert witness["bridge_call_count"] == 1
    assert witness["retry_count"] == 0
    assert witness["candidate_selector_invoked"] is False
    assert witness["witness_status"] == "ACCEPTED"
    assert witness["stage_outcome"] == "N2_WITNESS_SEED_CONTRACT_ACCEPTED"
    assert "support_summary" not in witness
    assert witness["safe_seed_metadata"]["particles"] == [
        {"particle_index": 0, "sampler_seed": 0xA5100000},
        {"particle_index": 1, "sampler_seed": 0xA5100001},
    ]
    assert all(
        row["sampler_seed"] != seed
        for row in witness["safe_seed_metadata"]["particles"]
    )
    assert "private-fingerprint-never-retained" not in str(witness)
    terminal = finalized["witness_terminal"]
    assert terminal["witness_status"] == "ACCEPTED"
    assert terminal["stage_outcome"] == "N2_WITNESS_SEED_CONTRACT_ACCEPTED"
    assert terminal["terminal_classification"] is None
    assert terminal["candidate_execution_authorized"] is False


def test_t112_typed_witness_exclusion_is_non_seed_outcome_and_cannot_open_stage_two(
    tmp_path, monkeypatch
):
    import json

    from sts_combat_rl.sim.t105_native_stage_observability import TRACE_SCHEMA
    from sts_combat_rl.sim.t111_configured_search_support import (
        T111_STRUCTURAL_PREDICATES,
    )
    from sts_combat_rl.sim.t112_sampler_seed_recovery import (
        T112_WITNESS_FAILURE_DIAGNOSTIC_SCHEMA,
        T112_WITNESS_SCHEMA,
    )

    head = "f" * 40
    auth_path = tmp_path / "authorization.json"
    authorization = {
        "schema_id": T112_AUTH_SCHEMA,
        "stage": "witness",
        "authorization_id": "witness-auth",
        "implementation_head": head,
    }
    authorization_ref = workflow._write_new_json(auth_path, authorization)
    identity = "A:typed-exclusion"
    bridge_calls = []

    stage_summary = {
        "schema_id": TRACE_SCHEMA,
        "attempt_status": "failed_closed",
        "first_failed_stage": "public_fidelity_validation",
        "failure_code": "public_fidelity_failed",
        "particle_failure_codes": [
            {
                "particle_index": 0,
                "first_failed_stage": "public_fidelity_validation",
                "failure_code": "public_fidelity_failed",
            },
            {
                "particle_index": 1,
                "first_failed_stage": "public_fidelity_validation",
                "failure_code": "public_fidelity_failed",
            },
        ],
    }
    unsafe_markers = (
        "private-hidden-particle-state",
        "raw-native-report-secret",
        "exception-message-secret",
    )

    def fake_validate(_authorization, **_kwargs):
        return {
            "authorization": {
                **authorization,
                "native_binary": {
                    "path": "binary",
                    "sha256": "e" * 64,
                    "size_bytes": 1,
                },
            },
            "authorization_sha256": authorization_ref["sha256"],
            "authorization_artifact": authorization_ref,
            "qualification_artifact": {"path": "qualification", "sha256": "b" * 64},
            "readiness_artifact": {"path": "readiness", "sha256": "c" * 64},
            "native_source_manifest_artifact": {"path": "manifest", "sha256": "d" * 64},
            "native_binary": {"path": "binary", "sha256": "e" * 64, "size_bytes": 1},
            "resource_plan": {
                "resource_guard": {
                    "batch_id": "batch",
                    "job_id": "job",
                    "resource_root": str(tmp_path),
                }
            },
        }

    def fake_source_records(_validated, *, t101_manifest_path):
        assert t101_manifest_path == tmp_path / "t101.json"
        return (
            [{"selection_identity": identity, "cohort": "A"}],
            {"A": {identity: object()}},
            {identity: object()},
            {"source_population": {"record_count": 413}},
        )

    class Adapter:
        def sample_hidden_future_particles_search(self, _restored, **_kwargs):
            bridge_calls.append(identity)
            raise T111SupportExclusion(
                "accepted_structured_bridge_failure",
                evidence={
                    "boundary": "single_n2_search_v2_bridge_call",
                    "structural_admission_predicates": {
                        "restore_exact_accepted_state": True,
                        "public_projection_parity": False,
                        "strict_t110_v2_bridge_valid": None,
                        "unsafe_private_predicate": True,
                    },
                    "bridge_diagnostics": {
                        "stage_diagnostics_status": "validated_failure",
                        "structured_failure_class": "public_fidelity_failure",
                        "structured_stage_evidence": stage_summary,
                        "raw_report": unsafe_markers[1],
                        "stage_diagnostics_error_type": unsafe_markers[0],
                    },
                    "hidden_state": unsafe_markers[0],
                    "exception_text": unsafe_markers[2],
                    "arbitrary_native_payload": {"secret": unsafe_markers[1]},
                },
            )

        def close(self):
            return None

    adapter = Adapter()

    def fake_factory(_binary):
        return lambda: adapter, [adapter]

    monkeypatch.setattr(
        workflow, "os", SimpleNamespace(name="posix", getpid=lambda: 321)
    )
    monkeypatch.setattr(workflow, "validate_t112_stage_authorization", fake_validate)
    monkeypatch.setattr(
        workflow, "_active_guard", lambda *_args, **_kwargs: {"state": "ARMED"}
    )
    monkeypatch.setattr(workflow, "_source_records_for_run", fake_source_records)
    monkeypatch.setattr(workflow, "_adapter_factory_for_binary", fake_factory)
    monkeypatch.setattr(
        workflow,
        "restore_t085_canonical_record",
        lambda _adapter, _selected, _canonical: (object(), "mock_restore"),
    )
    monkeypatch.setattr(
        workflow,
        "_runner_for",
        lambda *_args, **_kwargs: pytest.fail(
            "Stage-1 witness must not invoke T111NativeRecordRunner"
        ),
    )
    monkeypatch.setattr(
        workflow,
        "_validate_t112_guard_status",
        lambda *_args, **_kwargs: (
            {},
            {
                "state": "COMPLETED",
                "sample_count": 1,
                "peak_rss_mib": 1,
                "lowest_memavailable_mib": 1,
                "rss_limit_mib": 8192,
                "memavailable_floor_mib": 8192,
                "sample_interval_seconds": 1,
            },
        ),
    )
    monkeypatch.setattr(
        workflow,
        "select_t111_configured_search_cohort",
        lambda *_args, **_kwargs: pytest.fail("witness must never invoke selector"),
    )

    result = workflow.execute_t112_witness(
        authorization_path=auth_path,
        qualification_path=tmp_path / "qualification.json",
        readiness_path=tmp_path / "readiness.json",
        resource_status_path=tmp_path / "resource-status.json",
        t101_manifest_path=tmp_path / "t101.json",
        witness_output_root=tmp_path / "witness-output",
        repo_root=tmp_path,
    )
    finalized = workflow.finalize_t112_witness(
        witness_output_root=tmp_path / "witness-output",
        resource_status_path=tmp_path / "resource-status.json",
    )
    witness = json.loads(
        Path(result["witness_artifact"]["path"]).read_text(encoding="utf-8")
    )

    assert bridge_calls == [identity]
    assert witness["schema_id"] == T112_WITNESS_SCHEMA
    assert witness["witness_status"] == "REJECTED"
    assert witness["stage_outcome"] == "N2_WITNESS_NON_SEED_SUPPORT_EXCLUSION"
    assert witness["bridge_call_count"] == 1
    assert witness["retry_count"] == 0
    assert witness["candidate_selector_invoked"] is False
    diagnostic = witness["failure_diagnostic"]
    assert diagnostic["schema_id"] == T112_WITNESS_FAILURE_DIAGNOSTIC_SCHEMA
    assert diagnostic["reason"] == "accepted_structured_bridge_failure"
    assert diagnostic["evidence"] == {
        "boundary": "single_n2_search_v2_bridge_call",
        "structural_admission_predicates": {
            **dict.fromkeys(T111_STRUCTURAL_PREDICATES),
            "restore_exact_accepted_state": True,
            "public_projection_parity": False,
        },
        "bridge_diagnostics": {
            "stage_diagnostics_status": "validated_failure",
            "structured_failure_class": "public_fidelity_failure",
            "structured_stage_evidence": stage_summary,
        },
    }
    assert not any(marker in json.dumps(witness) for marker in unsafe_markers)
    terminal = finalized["witness_terminal"]
    assert terminal["witness_status"] == "REJECTED"
    assert terminal["stage_outcome"] == "N2_WITNESS_NON_SEED_SUPPORT_EXCLUSION"
    assert terminal["terminal_classification"] is None
    assert terminal["candidate_execution_authorized"] is False


def test_t112_reloaded_source_order_revalidates_stage_one_witness_artifact():
    from sts_combat_rl.sim.t112_sampler_seed_recovery import (
        safe_t112_native_witness_seed_metadata,
    )

    # Stage 2's candidate JSONL records T101 hash order. A later independent
    # source reload may enumerate those same source rows in another order.
    reloaded_source_rows = [
        {"selection_identity": "A:later", "cohort": "A"},
        {"selection_identity": "C:only", "cohort": "C"},
        {"selection_identity": "A:first", "cohort": "A"},
        {"selection_identity": "B:only", "cohort": "B"},
        {"selection_identity": "A:middle", "cohort": "A"},
    ]
    stage2_attempt_jsonl = [
        {"selection_identity": row["selection_identity"], "stratum": "A"}
        for row in sorted(
            (row for row in reloaded_source_rows if row["cohort"] == "A"),
            key=lambda row: (
                hashlib.sha256(row["selection_identity"].encode("utf-8")).hexdigest(),
                row["selection_identity"],
            ),
        )
    ]
    expected_first_a = stage2_attempt_jsonl[0]["selection_identity"]
    seed = derive_t101_sampler_seed(expected_first_a, 0)
    report = _report(seed)
    report_sha = hashlib.sha256(workflow._canonical_json(report)).hexdigest()
    witness_artifact = {
        "source_identity": {
            "selection_identity": expected_first_a,
            "stratum": "A",
            "selection_digest": hashlib.sha256(
                expected_first_a.encode("utf-8")
            ).hexdigest(),
        },
        "requested_sampler_seed_input": seed,
        "observed_sampler_seed_input": seed,
        "bridge_report_sha256": report_sha,
        "safe_seed_metadata": safe_t112_native_witness_seed_metadata(
            report,
            expected_sampler_seed=seed,
            bridge_report_sha256=report_sha,
        ),
    }
    witness_terminal = {
        "witness_status": "ACCEPTED",
        "stage_outcome": "N2_WITNESS_SEED_CONTRACT_ACCEPTED",
        "bridge_call_count": 1,
        "retry_count": 0,
    }

    # Terminal metadata gates Stage 2 but intentionally does not duplicate
    # source_identity or sampler evidence. Revalidating that document was the
    # bug; the exact-hash-bound Stage-1 witness artifact carries those fields.
    with pytest.raises(T112WorkflowError):
        workflow._validate_t112_witness_first_a(
            witness_artifact=witness_terminal,
            source_rows=reloaded_source_rows,
        )
    workflow._validate_t112_witness_first_a(
        witness_artifact=witness_artifact,
        source_rows=reloaded_source_rows,
    )
