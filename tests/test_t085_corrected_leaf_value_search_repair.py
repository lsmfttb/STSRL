from __future__ import annotations

import copy

import pytest

torch = pytest.importorskip("torch")

from sts_combat_rl.sim.torch_policy_value import (
    PolicyValueNetwork,
    load_torch_policy_value_checkpoint,
)
from sts_combat_rl.t085_corrected_leaf_value_search_repair import (
    T085_BATCH_SIZE,
    T085_COLLECTOR_SHA256,
    T085_FORMAL_ROW_COUNT,
    T085_OPTIMIZER_STEPS,
    T085LeafValueExample,
    T085TrainingConfig,
    T085TrainingReport,
    T085TrainingResult,
    audit_t085_policy_invariance,
    build_t085_batch_plan,
    native_leaf_utility_from_prediction,
    save_t085_corrected_checkpoint,
)


def _model() -> PolicyValueNetwork:
    return PolicyValueNetwork(
        state_feature_size=104,
        snapshot_feature_size=1,
        public_context_feature_size=103,
        action_feature_size=2,
        hidden_size=16,
    )


def _example(index: int, label: float = 1.0) -> T085LeafValueExample:
    return T085LeafValueExample(
        state_features=(float(index), *(0.0 for _ in range(103))),
        legal_action_features=((0.0, 1.0), (1.0, 0.0)),
        eligible_action_indices=(0, 1),
        native_utility=label,
        exact_leaf_identity=f"leaf-{index}",
        sampling_arm="unguided_search_v2",
        act=1,
    )


def test_t085_batch_plan_is_exact_and_seeded() -> None:
    first = build_t085_batch_plan(repair_seed=85001)
    repeated = build_t085_batch_plan(repair_seed=85001)
    other = build_t085_batch_plan(repair_seed=85002)

    assert len(first) == T085_OPTIMIZER_STEPS
    assert all(len(batch) == T085_BATCH_SIZE for batch in first)
    assert first == repeated
    assert first != other
    assert sorted(first[: T085_FORMAL_ROW_COUNT // T085_BATCH_SIZE][0]) != []


def test_native_leaf_utility_de_normalizes_once_and_fails_closed() -> None:
    assert native_leaf_utility_from_prediction(
        2.0,
        target_mean=10.0,
        target_std=3.0,
    ) == pytest.approx(16.0)
    with pytest.raises(ValueError, match="target_std"):
        native_leaf_utility_from_prediction(1.0, target_mean=0.0, target_std=0.0)


def test_policy_invariance_audit_ignores_only_outcome_head() -> None:
    parent = _model()
    repaired = copy.deepcopy(parent)
    with torch.no_grad():
        repaired.outcome_head[-1].bias.add_(1.0)
    result = audit_t085_policy_invariance(parent, repaired, [_example(1)])
    assert result["valid"] is True
    assert result["policy_mismatch_count"] == 0

    with torch.no_grad():
        repaired.policy_head[-1].bias.add_(1.0)
    result = audit_t085_policy_invariance(parent, repaired, [_example(1)])
    assert result["valid"] is False
    assert result["policy_mismatch_count"] == 1


def test_corrected_checkpoint_round_trips_explicit_native_utility_gate(
    tmp_path,
) -> None:
    model = _model()
    report = T085TrainingReport(
        training_ok=True,
        example_count=T085_FORMAL_ROW_COUNT,
        repair_seed=85001,
        target_mean=12.0,
        target_std=4.0,
        optimizer_steps=T085_OPTIMIZER_STEPS,
        batch_size=T085_BATCH_SIZE,
        batch_plan_sha256="a" * 64,
        initial_mse=1.0,
        final_mse=0.1,
        initial_mae=0.8,
        final_mae=0.2,
    )
    result = T085TrainingResult(
        model=model,
        report=report,
        config=T085TrainingConfig(),
        training_data_provenance={
            "task_id": "T085",
            "training_input_artifact_id": (
                "t084-formal-dataset-sha256:" + T085_COLLECTOR_SHA256
            ),
            "training_input_sha256": T085_COLLECTOR_SHA256,
            "training_input_path": "retained/t084-collector.json",
            "training_input_byte_count": 123,
            "training_record_count": 960,
            "target_kind": "search_v2_leaf_continuation_native_utility_v1",
            "target_source": "T084 formal post-first-action internal-leaf native utility",
            "parent_checkpoint_sha256": (
                "c0c38c239047f6be67e983768e53bd680007e9cba117e17c7d226583ed751193"
            ),
            "repair_seed": 85001,
            "optimizer_steps": 900,
            "batch_size": 32,
            "target_mean": 12.0,
            "target_std": 4.0,
            "batch_plan_sha256": "a" * 64,
            "policy_target_kind": "behavior_chosen_action_one_hot",
            "policy_target_source": "frozen_parent_checkpoint_policy_path",
        },
        policy_target_kind="behavior_chosen_action_one_hot",
        policy_target_source="frozen_parent_checkpoint_policy_path",
    )
    path = tmp_path / "corrected.pt"
    save_t085_corrected_checkpoint(
        result,
        path,
        parent_checkpoint_sha256=(
            "c0c38c239047f6be67e983768e53bd680007e9cba117e17c7d226583ed751193"
        ),
    )
    loaded = load_torch_policy_value_checkpoint(str(path))
    assert loaded.metadata["outcome_target_kind"] == (
        "search_v2_leaf_continuation_native_utility_v1"
    )
    assert loaded.metadata["t085_value_target"]["target_std"] == 4.0
    assert loaded.training_data_provenance["task_id"] == "T085"

    raw = torch.load(path, map_location="cpu", weights_only=True)
    raw["metadata"]["t085_value_target"]["de_normalization"] = "sigmoid"
    bad = tmp_path / "bad.pt"
    torch.save(raw, bad)
    with pytest.raises(ValueError, match="de_normalization"):
        load_torch_policy_value_checkpoint(str(bad))
