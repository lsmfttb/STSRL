from __future__ import annotations

import copy
import json

import pytest

import sts_combat_rl.sim.t089_non_combat_policy as t089_module
from sts_combat_rl.commands.t089_non_combat_policy import main
from sts_combat_rl.sim.action_space import ActionSpaceConfig
from sts_combat_rl.sim.non_combat_learning import T065CompleteRunArmReport
from sts_combat_rl.sim.t089_non_combat_policy import (
    T089_FRESH_DRIVER_SEED,
    T089_NATIVE_COMMIT,
    T089_NATIVE_REF,
    T089_NATIVE_REPOSITORY,
    T089ContractError,
    T089ExperimentConfig,
    T089Incomplete,
    T089WorkflowState,
    advance_t089_workflow,
    build_t089_fresh_report,
    build_t089_retention_manifest,
    t089_battle_provenance,
    t089_model_input_contract,
    t089_terminal_report,
    validate_t089_fresh_report,
    validate_t089_public_model_input,
)


def test_t089_freezes_new_seed_schedule_and_search_provenance() -> None:
    config = T089ExperimentConfig().to_dict()
    assert config["model_seeds"] == [893001, 893002]
    assert config["continuation_seeds"]["heldout"] == [892201, 892202, 892203, 892204]
    battle = t089_battle_provenance()
    assert battle["implementation"] == "BattleScumSearcher2"
    assert battle["search_budget"]["simulations"] == 400
    assert battle["policy_prior_callback"] is None
    assert battle["learned_leaf_value_callback"] is None


def test_t089_reuses_exact_public_model_input_contract() -> None:
    schema = t089_model_input_contract()
    assert schema["schema_id"] == "non-combat-model-input-v1"
    assert schema["state_feature_size"] == 4737
    assert schema["action_feature_size"] == 92
    validate_t089_public_model_input(
        state_features=[0.0] * 4737,
        action_features=[0.0] * 92,
        context={"public": {"screen": "MAP_SCREEN"}},
    )
    with pytest.raises(T089Incomplete):
        validate_t089_public_model_input(
            state_features=[0.0] * 4737,
            action_features=[0.0] * 92,
            context={"checkpoint_payload": "hidden"},
        )


def _fresh_controller_provenance(arm: str) -> dict[str, object]:
    action_space = ActionSpaceConfig.initial_no_potions().to_dict()
    non_combat_name = (
        "expert_non_combat_v1" if arm == "baseline" else "learned_non_combat_t089_v1"
    )
    return {
        "schema_version": 1,
        "kind": "routed_run",
        "name": f"oracle_search_v1_highest_mean_s400+{non_combat_name}",
        "config": {
            "reproducible": True,
            "battle": {
                "schema_version": 1,
                "kind": "oracle_battle_search",
                "name": "oracle_search_v1_highest_mean_s400",
                "config": {
                    "information_regime": "full_simulator_state_oracle_like",
                    "native_source_identity": {
                        "repository": T089_NATIVE_REPOSITORY,
                        "ref": T089_NATIVE_REF,
                        "commit": T089_NATIVE_COMMIT,
                    },
                    "search_budget": {
                        "simulations": 400,
                        "budget_unit": "native_random_terminal_playouts",
                    },
                    "root_selection_rule": "highest_mean",
                    "action_space": action_space,
                    "include_potions": False,
                    "rollout_configuration": {
                        "rollout_policy": "BattleScumSearcher2::playoutRandom",
                        "leaf_value": "BattleScumSearcher2::evaluateEndState",
                        "model_calls": 0,
                    },
                },
            },
            "non_combat": {
                "name": non_combat_name,
                "config": {"seed": T089_FRESH_DRIVER_SEED},
            },
        },
    }


def _fresh_arm(offset: float, *, learned: bool, arm: str) -> dict[str, object]:
    action_space = ActionSpaceConfig.initial_no_potions().to_dict()
    controller = _fresh_controller_provenance(arm)
    rows = []
    decision_events = []
    for seed in range(891001, 891257):
        family_counts = {
            "MAP_SCREEN": 32 if learned and 891001 <= seed <= 891004 else 0,
            "REST_ROOM": 1 if learned and seed == 891002 else 0,
            "REWARDS": 32 if learned and seed == 891003 else 0,
            "TREASURE_ROOM": 1 if learned and seed == 891004 else 0,
        }
        rows.append(
            {
                "simulator_seed": seed,
                "arm": arm,
                "terminal": True,
                "terminal_floor": float(seed - 891000) + offset,
                "terminal_status": "VICTORY",
                "truncated": False,
                "controller_failure": False,
                "act2_plus": learned,
                "learned_decision_count": sum(family_counts.values()),
                "learned_decisions_by_family": family_counts,
                "supported_inference_failures": 0,
                "fallback_decisions_by_family": {},
                "controller_provenance": controller,
                "action_space": action_space,
                "simulator_steps": 4,
                "simulator_cost": {"simulator_steps": 4.0},
            }
        )
        ordinal = 0
        for family, count in family_counts.items():
            for _ in range(count):
                decision_events.append(
                    {
                        "simulator_seed": seed,
                        "decision_ordinal": ordinal,
                        "screen_family": family,
                        "status": "learned_success",
                        "action_index": 0,
                        "score": 1.0,
                    }
                )
                ordinal += 1
    driver_name = "learned_non_combat_t089_v1" if learned else "expert_non_combat_v1"
    shard_specs = []
    for shard_index in range(16):
        seed_start = 891001 + shard_index * 16
        seed_end = seed_start + 15
        shard_seeds = list(range(seed_start, seed_end + 1))
        shard_decisions = sum(
            event["simulator_seed"] in shard_seeds for event in decision_events
        )
        shard_specs.append(
            {
                "arm": arm,
                "shard_index": shard_index,
                "seed_start": seed_start,
                "seed_end": seed_end,
                "seed_count": 16,
                "worker_count": 16,
                "requested_seeds": shard_seeds,
                "requested_seed_count": 16,
                "completed_seeds": shard_seeds,
                "completed_seed_count": 16,
                "completed_row_count": 16,
                "decision_count": shard_decisions,
                "wall_clock_seconds": 1.0,
                "problem_count": 0,
                "problems": [],
                "simulator_cost": {"simulator_steps": 64.0},
            }
        )
    return {
        "schema_id": "t065-complete-run-report-v1",
        "schema_version": 1,
        "arm": arm,
        "driver_seed": T089_FRESH_DRIVER_SEED,
        "requested_seeds": list(range(891001, 891257)),
        "rows": rows,
        "decision_events": decision_events,
        "wall_clock_seconds": 1.0,
        "worker_count": 16,
        "shard_count": 16,
        "shard_specs": shard_specs,
        "problems": [],
        "simulator_identity": {
            "repository": T089_NATIVE_REPOSITORY,
            "ref": T089_NATIVE_REF,
            "commit": T089_NATIVE_COMMIT,
        },
        "action_space": action_space,
        "controller_provenance": controller,
        "driver_provenance": {
            "name": driver_name,
            "version": 1,
            "config": {"seed": T089_FRESH_DRIVER_SEED},
        },
    }


def test_t089_fresh_gate_is_paired_and_support_is_not_expandable() -> None:
    report = build_t089_fresh_report(
        _fresh_arm(0.0, learned=False, arm="baseline"),
        _fresh_arm(1.0, learned=True, arm="candidate"),
    )
    assert report["classification"] == "NON_COMBAT_POLICY_IMPROVEMENT_ESTABLISHED"
    assert report["support"]["passed"] is True
    assert len(report["paired_rows"]) == 256
    with pytest.raises(T089Incomplete):
        build_t089_fresh_report(
            _fresh_arm(0.0, learned=False, arm="baseline") | {"rows": []},
            _fresh_arm(1.0, learned=True, arm="candidate"),
        )


def test_t089_fresh_arm_requires_event_evidence_for_reported_decisions() -> None:
    baseline = _fresh_arm(0.0, learned=False, arm="baseline")
    candidate = _fresh_arm(1.0, learned=True, arm="candidate")
    candidate["decision_events"] = []
    with pytest.raises(T089Incomplete):
        build_t089_fresh_report(baseline, candidate)


def test_t089_fresh_arm_rejects_pseudo_serial_shard_evidence() -> None:
    baseline = _fresh_arm(0.0, learned=False, arm="baseline")
    baseline["shard_specs"] = []
    with pytest.raises(T089Incomplete):
        build_t089_fresh_report(
            baseline, _fresh_arm(1.0, learned=True, arm="candidate")
        )


def test_t089_fresh_execution_uses_exact_parallel_shards(monkeypatch) -> None:
    calls: list[tuple[int, ...]] = []

    def fake_run_complete_run_arm(adapter_factory, **kwargs):
        shard_seeds = tuple(kwargs["seeds"])
        calls.append(shard_seeds)
        rows = tuple(
            {
                "simulator_seed": seed,
                "terminal": True,
                "terminal_floor": 1.0,
                "terminal_status": "VICTORY",
                "truncated": False,
                "controller_error": False,
                "act2_entry": False,
                "simulator_steps": 1,
                "simulator_cost": {"simulator_steps": 1.0},
            }
            for seed in shard_seeds
        )
        return T065CompleteRunArmReport(
            arm="expert",
            driver_seed=T089_FRESH_DRIVER_SEED,
            requested_seeds=shard_seeds,
            rows=rows,
            wall_clock_seconds=1.0,
            worker_count=16,
            shard_count=16,
            simulator_identity={
                "repository": T089_NATIVE_REPOSITORY,
                "ref": T089_NATIVE_REF,
                "commit": T089_NATIVE_COMMIT,
            },
            action_space=ActionSpaceConfig.initial_no_potions().to_dict(),
            controller_provenance={"shard": "test"},
            driver_provenance={"name": "expert_non_combat_v1"},
        )

    monkeypatch.setattr(t089_module, "run_complete_run_arm", fake_run_complete_run_arm)
    report = t089_module.run_t089_complete_run_arm(
        lambda: None,
        arm="baseline",
        battle_controller_factory=lambda: None,
    )
    assert len(calls) == 16
    assert sorted(calls) == [
        tuple(range(891001 + index * 16, 891001 + (index + 1) * 16))
        for index in range(16)
    ]
    assert report.requested_seeds == tuple(range(891001, 891257))
    assert len(report.shard_specs) == 16
    assert [spec["worker_count"] for spec in report.shard_specs] == [16] * 16
    assert [spec["seed_count"] for spec in report.shard_specs] == [16] * 16


def test_t089_fresh_and_terminal_evidence_fail_closed() -> None:
    baseline = _fresh_arm(0.0, learned=False, arm="baseline")
    candidate = _fresh_arm(1.0, learned=True, arm="candidate")
    with pytest.raises(T089Incomplete):
        build_t089_fresh_report(baseline["rows"], candidate["rows"])
    forged = copy.deepcopy(candidate)
    forged["driver_seed"] = 999
    with pytest.raises(T089Incomplete):
        build_t089_fresh_report(baseline, forged)
    fresh = build_t089_fresh_report(baseline, candidate)
    forged_reduced = copy.deepcopy(fresh)
    forged_reduced["arm_reports"]["candidate"]["driver_seed"] = 999
    with pytest.raises(T089Incomplete):
        validate_t089_fresh_report(forged_reduced)
    with pytest.raises(T089ContractError):
        t089_terminal_report("NON_COMBAT_POLICY_IMPROVEMENT_ESTABLISHED", fresh=fresh)
    with pytest.raises(T089ContractError):
        t089_terminal_report("INCOMPLETE", fresh=fresh, reason="forged evidence")
    incomplete = t089_terminal_report("INCOMPLETE", reason="missing held-out evidence")
    assert incomplete["classification"] == "INCOMPLETE"


def test_t089_reduced_support_evidence_cannot_be_forged() -> None:
    fresh = build_t089_fresh_report(
        _fresh_arm(0.0, learned=False, arm="baseline"),
        _fresh_arm(1.0, learned=True, arm="candidate"),
    )
    forged_failure = copy.deepcopy(fresh)
    candidate = forged_failure["arm_reports"]["candidate"]
    evidence = candidate["per_run_decision_evidence"]["891001"]
    evidence["supported_inference_failures"] = 1
    candidate["shard_specs"][0]["decision_count"] += 1
    with pytest.raises(T089Incomplete):
        validate_t089_fresh_report(forged_failure)

    forged_fallback = copy.deepcopy(fresh)
    candidate = forged_fallback["arm_reports"]["candidate"]
    evidence = candidate["per_run_decision_evidence"]["891001"]
    evidence["fallback_decisions_by_family"]["MAP_SCREEN"] = 1
    candidate["shard_specs"][0]["decision_count"] += 1
    with pytest.raises(T089Incomplete):
        validate_t089_fresh_report(forged_fallback)


def test_t089_cli_rejects_bare_fresh_rows_and_missing_finalize_evidence(
    tmp_path,
) -> None:
    baseline_path = tmp_path / "baseline.json"
    candidate_path = tmp_path / "candidate.json"
    output_path = tmp_path / "fresh.json"
    baseline_path.write_text(json.dumps([]), encoding="utf-8")
    candidate_path.write_text(json.dumps([]), encoding="utf-8")
    assert (
        main(
            [
                "fresh",
                "--baseline",
                str(baseline_path),
                "--candidate",
                str(candidate_path),
                "--output",
                str(output_path),
            ]
        )
        == 2
    )
    assert (
        main(
            [
                "finalize",
                "--classification",
                "NON_COMBAT_POLICY_IMPROVEMENT_ESTABLISHED",
                "--output",
                str(tmp_path / "terminal.json"),
            ]
        )
        == 2
    )


def test_t089_retention_requires_all_roles() -> None:
    with pytest.raises(T089Incomplete):
        build_t089_retention_manifest(
            {}, regeneration_commands=["x"], retention_reason="test"
        )
    roles = (
        "input_eligibility",
        "current_native_revalidation",
        "target_table",
        "training_normalizers",
        "training_batch_plans",
        "checkpoint_893001",
        "checkpoint_893002",
        "validation_selection",
        "heldout_gate",
        "fresh_run",
        "terminal_report",
    )
    artifacts = {
        role: {
            "role": role,
            "path": f"artifacts/t089/{role}.json",
            "sha256": "a" * 64,
            "size_bytes": 1,
        }
        for role in roles
    }
    report = build_t089_retention_manifest(
        artifacts, regeneration_commands=["python -m ..."], retention_reason="unit test"
    )
    assert report["schema_id"] == "t089-retention-manifest-v1"
    assert {row["role"] for row in report["artifacts"]} == set(roles)


def test_t089_preflight_command_is_path_only(tmp_path) -> None:
    output = tmp_path / "preflight.json"
    assert main(["preflight", "--output", str(output)]) == 0
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["task_id"] == "T089"
    assert payload["fresh_target_generation_authorized"] is False


def test_t089_heldout_failure_closes_before_fresh_evaluation() -> None:
    state = T089WorkflowState(stage="HELDOUT_GATE")
    failed = advance_t089_workflow(state, passed=False)
    assert (
        failed.terminal_classification
        == "NON_COMBAT_POLICY_IMPROVEMENT_NOT_ESTABLISHED"
    )
    assert failed.fresh_evaluation_authorized is False
    passed = advance_t089_workflow(state, passed=True)
    assert passed.stage == "FRESH_EVAL"
    assert passed.fresh_evaluation_authorized is True
