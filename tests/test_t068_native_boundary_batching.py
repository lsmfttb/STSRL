from __future__ import annotations

from copy import deepcopy
import importlib.util
from pathlib import Path
import sys

import pytest

from sts_combat_rl.commands.t068_native_boundary_batching import (
    T068_AUDIT_SCHEMA_ID,
    T068_FEASIBILITY_SCHEMA_ID,
    T068_GUIDED_ARMS,
    T068_NEXT_RECOMMENDATION,
    build_t068_batch_feasibility_report,
    build_t068_callback_dependency_audit,
    build_t068_decision_report,
)
from sts_combat_rl.sim.action_space import ActionSpaceConfig
from sts_combat_rl.sim.search_guidance_inference import (
    SearchGuidanceCheckpointProvenance,
)


def _request(request_id: str) -> dict[str, object]:
    return {
        "request_id": request_id,
        "response_count": 1,
        "response_order_exact": True,
        "simultaneously_ready_batch_size": 1,
        "callback_kind": "policy",
        "required_outputs": ["policy"],
        "public_input_identity": "sha256:test",
        "public_input_identity_schema_id": "t067-public-node-cache-key-v1",
        "public_input_canonical_byte_count": 1,
        "ordered_legal_action_identities": [{"stable_id": "battle:1", "occurrence": 0}],
        "dependency_edges": ["request_ready -> python_callback_response"],
        "flush_reason": "native callback requires this response before traversal continues",
        "callback_elapsed_ms": 0.1,
    }


def _shards() -> list[dict[str, object]]:
    return [
        {
            "arms": {
                arm: [_request(f"shard-{shard:02d}-{arm}")] for arm in T068_GUIDED_ARMS
            }
        }
        for shard in range(16)
    ]


def test_t068_synchronous_singletons_fail_closed_and_select_one_next_path() -> None:
    audit = build_t068_callback_dependency_audit(
        shard_traces=_shards(),
        input_identities={"t067": {"sha256": "accepted"}},
        native_source_audit={"synchronous_return_required": True},
        code_commit="a" * 40,
    )

    assert audit["schema_id"] == T068_AUDIT_SCHEMA_ID
    assert audit["feasibility_gate"]["passed"] is False
    assert audit["execution_layout"]["worker_count"] == 16
    assert all(
        audit["arms"][arm]["batch_size_distribution"] == {"1": 16}
        for arm in T068_GUIDED_ARMS
    )
    feasibility = build_t068_batch_feasibility_report(
        audit,
        prototype_costs={
            arm: {
                "component_cost_ms": {
                    "checkpoint_feature_encoding_ms": 2.0,
                    "policy_value_forward_pass_ms": 1.0,
                }
            }
            for arm in T068_GUIDED_ARMS
        },
    )
    assert feasibility["schema_id"] == T068_FEASIBILITY_SCHEMA_ID
    decision = build_t068_decision_report(audit, feasibility)
    assert decision["calibration_authorized"] is False
    assert decision["outcome_comparison_authorized"] is False
    assert decision["recommendation"] == T068_NEXT_RECOMMENDATION
    assert decision["recommendation_count"] == 1


def test_t068_rejects_duplicate_or_incomplete_callback_responses() -> None:
    shards = _shards()
    duplicate = deepcopy(shards)
    duplicate[0]["arms"]["prior_only"].append(_request("shard-00-prior_only"))
    with pytest.raises(ValueError, match="duplicate request"):
        build_t068_callback_dependency_audit(
            shard_traces=duplicate,
            input_identities={},
            native_source_audit={"synchronous_return_required": True},
            code_commit="a" * 40,
        )

    incomplete = deepcopy(shards)
    incomplete[0]["arms"]["value_only"][0]["response_count"] = 0
    with pytest.raises(ValueError, match="lacks one response"):
        build_t068_callback_dependency_audit(
            shard_traces=incomplete,
            input_identities={},
            native_source_audit={"synchronous_return_required": True},
            code_commit="a" * 40,
        )

    missing_identity = deepcopy(shards)
    del missing_identity[0]["arms"]["value_only"][0]["public_input_identity"]
    with pytest.raises(ValueError, match="lacks public identity"):
        build_t068_callback_dependency_audit(
            shard_traces=missing_identity,
            input_identities={},
            native_source_audit={"synchronous_return_required": True},
            code_commit="a" * 40,
        )


def test_t068_runner_constructs_exact_t062_arm_contract() -> None:
    script = (
        Path(__file__).resolve().parents[1]
        / "scripts"
        / "run_t068_callback_dependency_audit.py"
    )
    spec = importlib.util.spec_from_file_location("t068_runner", script)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    checkpoint = SearchGuidanceCheckpointProvenance(
        checkpoint_schema_id="torch-policy-value-checkpoint-v1",
        checkpoint_format_version=1,
        checkpoint_artifact_id="test",
        checkpoint_path="/tmp/test.pt",
        model_class="TestModel",
        model_config={},
        trainer_input_artifact_id="trainer-input-sha256:test",
        trainer_input_sha256="test",
        policy_target_kind="oracle_teacher_action_one_hot",
        policy_target_source="test",
    )

    class Scorer:
        name = "test"
        checkpoint_provenance = checkpoint

    arms = module._build_arms(Scorer(), ActionSpaceConfig.initial_no_potions())
    assert tuple(label for label, _ in arms) == (
        "baseline",
        "prior_only",
        "value_only",
        "prior_value",
    )
    assert arms[0][1].callback_dependency_trace_enabled is False
    assert all(
        controller.callback_dependency_trace_enabled for _, controller in arms[1:]
    )

    comparison_problems = module._comparison_problems(
        {
            "source_match_problems": ["source mismatch"],
            "arms": {
                "prior_only": {
                    "evaluation_problems": ["evaluation failure"],
                    "records": [{"problems": ["record failure"]}],
                }
            },
        }
    )
    assert comparison_problems == [
        "source mismatch",
        "prior_only: evaluation failure",
        "prior_only: record failure",
    ]


def test_t068_semantic_probe_retains_t062_four_arm_contract() -> None:
    script = (
        Path(__file__).resolve().parents[1]
        / "scripts"
        / "verify_t068_semantic_equivalence.py"
    )
    spec = importlib.util.spec_from_file_location("t068_semantic", script)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)

    class Scorer:
        name = "test"
        checkpoint_provenance = SearchGuidanceCheckpointProvenance(
            checkpoint_schema_id="torch-policy-value-checkpoint-v1",
            checkpoint_format_version=1,
            checkpoint_artifact_id="test",
            checkpoint_path="/tmp/test.pt",
            model_class="TestModel",
            model_config={},
            trainer_input_artifact_id="trainer-input-sha256:test",
            trainer_input_sha256="test",
            policy_target_kind="oracle_teacher_action_one_hot",
            policy_target_source="test",
        )

    # Avoid checkpoint loading: this asserts the exact controller-arm shape
    # that T062 will validate before the WSL semantic smoke is launched.
    original = module.build_torch_guidance_scorer_from_checkpoint
    module.build_torch_guidance_scorer_from_checkpoint = lambda _: Scorer()
    try:
        arms, _ = module._arms(Path("/tmp/checkpoint.pt"), trace=True)
    finally:
        module.build_torch_guidance_scorer_from_checkpoint = original
    assert tuple(label for label, _ in arms) == (
        "baseline",
        "prior_only",
        "value_only",
        "prior_value",
    )
    assert arms[0][1].callback_dependency_trace_enabled is False
    assert all(
        controller.callback_dependency_trace_enabled for _, controller in arms[1:]
    )
