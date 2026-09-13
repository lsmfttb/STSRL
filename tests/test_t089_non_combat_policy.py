from __future__ import annotations

import json

import pytest

from sts_combat_rl.commands.t089_non_combat_policy import main
from sts_combat_rl.sim.t089_non_combat_policy import (
    T089ExperimentConfig,
    T089Incomplete,
    T089WorkflowState,
    advance_t089_workflow,
    build_t089_fresh_report,
    build_t089_retention_manifest,
    t089_battle_provenance,
    t089_model_input_contract,
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


def _fresh_rows(offset: float, *, learned: bool) -> list[dict[str, object]]:
    rows = []
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
                "terminal": True,
                "terminal_floor": float(seed - 891000) + offset,
                "truncated": False,
                "controller_failure": False,
                "act2_plus": learned,
                "learned_decision_count": sum(family_counts.values()),
                "learned_decisions_by_family": family_counts,
                "supported_inference_failures": 0,
            }
        )
    return rows


def test_t089_fresh_gate_is_paired_and_support_is_not_expandable() -> None:
    report = build_t089_fresh_report(
        _fresh_rows(0.0, learned=False), _fresh_rows(1.0, learned=True)
    )
    assert report["classification"] == "NON_COMBAT_POLICY_IMPROVEMENT_ESTABLISHED"
    assert report["support"]["passed"] is True
    assert len(report["paired_rows"]) == 256
    with pytest.raises(T089Incomplete):
        build_t089_fresh_report(
            _fresh_rows(0.0, learned=False)[:-1], _fresh_rows(1.0, learned=True)
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
