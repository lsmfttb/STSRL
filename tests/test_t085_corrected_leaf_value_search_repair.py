from __future__ import annotations

import copy
import shutil
from pathlib import Path

import pytest

torch = pytest.importorskip("torch")

import sts_combat_rl.t085_corrected_leaf_value_search_repair as t085_repair
from sts_combat_rl.sim.torch_policy_value import (
    PolicyValueNetwork,
    load_torch_policy_value_checkpoint,
)
from sts_combat_rl.t085_corrected_leaf_value_search_repair import (
    T085_ARTIFACT_ROOT,
    T085_BATCH_SIZE,
    T085_COLLECTOR_SHA256,
    T085_FORMAL_ROW_COUNT,
    T085_OPTIMIZER_STEPS,
    T085_PARENT_CHECKPOINT_PATH_BY_SEED,
    T085FormalDataset,
    T085LeafValueExample,
    T085TrainingConfig,
    T085TrainingReport,
    T085TrainingResult,
    _formal_example,
    audit_t085_policy_invariance,
    build_t085_batch_plan,
    load_t085_verified_parent_checkpoint,
    native_leaf_utility_from_prediction,
    resolve_t084_formal_dataset,
    save_t085_corrected_checkpoint,
    train_t085_corrected_value_head,
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
    parent_path = T085_PARENT_CHECKPOINT_PATH_BY_SEED[85001]
    if not Path(parent_path).is_file():
        pytest.skip("retained T064 parent checkpoint is not mounted")
    parent = load_t085_verified_parent_checkpoint(parent_path, repair_seed=85001)
    model = copy.deepcopy(parent.model)
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
            "parent_checkpoint_path": parent.path,
            "parent_checkpoint_computed_sha256": parent.sha256,
            "repair_seed": 85001,
            "optimizer_steps": 900,
            "batch_size": 32,
            "target_mean": 12.0,
            "target_std": 4.0,
            "batch_plan_sha256": "a" * 64,
            "policy_target_kind": "behavior_chosen_action_one_hot",
            "policy_target_source": "frozen_parent_checkpoint_policy_path",
            "parent_guidance_provenance": dict(parent.training_data_provenance),
            "policy_invariance_audit": {
                "schema_id": "t085-policy-invariance-audit-v1",
                "example_count": T085_FORMAL_ROW_COUNT,
                "policy_mismatch_count": 0,
                "parameter_group_mismatch_counts": {
                    "policy": 0,
                    "encoder": 0,
                    "hp": 0,
                    "resource": 0,
                },
                "valid": True,
            },
        },
        policy_target_kind="behavior_chosen_action_one_hot",
        policy_target_source="frozen_parent_checkpoint_policy_path",
        parent_model=copy.deepcopy(parent.model),
        parent_checkpoint_path=parent.path,
        invariance_audit={
            "schema_id": "t085-policy-invariance-audit-v1",
            "example_count": T085_FORMAL_ROW_COUNT,
            "policy_mismatch_count": 0,
            "parameter_group_mismatch_counts": {
                "policy": 0,
                "encoder": 0,
                "hp": 0,
                "resource": 0,
            },
            "valid": True,
        },
    )
    path = T085_ARTIFACT_ROOT / f".pytest-t085-{tmp_path.name}.pt"
    try:
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

        raw = torch.load(path, map_location="cpu", weights_only=True)
        raw["metadata"]["t085_value_target"]["target_mean"] = 13.0
        bad_cross = tmp_path / "bad-cross-fields.pt"
        torch.save(raw, bad_cross)
        with pytest.raises(ValueError, match="target_mean disagrees"):
            load_torch_policy_value_checkpoint(str(bad_cross))

        raw = torch.load(path, map_location="cpu", weights_only=True)
        raw["outcome_target_kind"] = "terminal_battle_survival_probability"
        raw["metadata"]["outcome_target_kind"] = "terminal_battle_survival_probability"
        bad_historical = tmp_path / "bad-historical-t085-envelope.pt"
        torch.save(raw, bad_historical)
        with pytest.raises(ValueError, match="historical outcome_target_kind"):
            load_torch_policy_value_checkpoint(str(bad_historical))
    finally:
        path.unlink(missing_ok=True)


def test_corrected_top_level_requires_t085_training_provenance(tmp_path) -> None:
    path = T085_PARENT_CHECKPOINT_PATH_BY_SEED[85001]
    if not Path(path).is_file():
        pytest.skip("retained T064 parent checkpoint is not mounted")
    parent = load_torch_policy_value_checkpoint(path)
    raw = torch.load(path, map_location="cpu", weights_only=True)
    raw["outcome_target_kind"] = "search_v2_leaf_continuation_native_utility_v1"
    raw["metadata"]["t085_value_target"] = {
        "task_id": "T085",
        "target_kind": "search_v2_leaf_continuation_native_utility_v1",
        "native_utility_units": "BattleScumSearcher2.evaluateEndState",
        "de_normalization": "z_pred * target_std + target_mean",
        "target_mean": 0.0,
        "target_std": 1.0,
        "parent_checkpoint_sha256": (
            "c0c38c239047f6be67e983768e53bd680007e9cba117e17c7d226583ed751193"
        ),
        "label_count": 960,
    }
    forged = tmp_path / "corrected-with-generic-provenance.pt"
    torch.save(raw, forged)
    assert parent.training_data_provenance.get("task_id") != "T085"
    with pytest.raises(ValueError, match="requires T085 training provenance"):
        load_torch_policy_value_checkpoint(str(forged))


def test_parent_identity_is_computed_from_exact_qualified_path(tmp_path) -> None:
    path = T085_PARENT_CHECKPOINT_PATH_BY_SEED[85001]
    if not Path(path).is_file():
        pytest.skip("retained T064 parent checkpoint is not mounted")
    parent = load_t085_verified_parent_checkpoint(path, repair_seed=85001)
    assert parent.sha256 == (
        "c0c38c239047f6be67e983768e53bd680007e9cba117e17c7d226583ed751193"
    )
    alternate = tmp_path / "static_mixture_v1-64001-copy.pt"
    shutil.copyfile(path, alternate)
    with pytest.raises(ValueError, match="exact qualified T064"):
        load_t085_verified_parent_checkpoint(alternate, repair_seed=85001)


def test_training_requires_bound_parent_and_runs_invariance_audit(monkeypatch) -> None:
    path = T085_PARENT_CHECKPOINT_PATH_BY_SEED[85001]
    if not Path(path).is_file():
        pytest.skip("retained T064 parent checkpoint is not mounted")
    parent = load_t085_verified_parent_checkpoint(path, repair_seed=85001)
    collector_path = Path(
        "/mnt/d/DeadlyCatCoding/STSRL/artifacts/"
        "t084-search-v2-internal-leaf-target-generation/"
        "t084-native-leaf-target-generation-v13-repair.json"
    )
    if not collector_path.is_file():
        pytest.skip("retained T084 collector is not mounted")
    examples = [
        T085LeafValueExample(
            state_features=(
                float(index),
                *(0.0 for _ in range(parent.model.state_feature_size - 1)),
            ),
            legal_action_features=(
                tuple(0.0 for _ in range(parent.model.action_feature_size)),
                tuple(1.0 for _ in range(parent.model.action_feature_size)),
            ),
            eligible_action_indices=(0, 1),
            native_utility=float(index % 17),
            exact_leaf_identity=f"training-leaf-{index}",
            sampling_arm="unguided_search_v2",
            act=1,
        )
        for index in range(960)
    ]
    actual_collector_byte_count = collector_path.stat().st_size
    real_sha256_file = t085_repair.sha256_file

    def sha256_file_for_test(candidate):
        if Path(candidate).resolve() == collector_path.resolve():
            return T085_COLLECTOR_SHA256
        return real_sha256_file(candidate)

    monkeypatch.setattr(t085_repair, "sha256_file", sha256_file_for_test)
    formal_dataset = T085FormalDataset(
        examples=tuple(examples),
        retention_manifest_path="retained/t084-retention-manifest.json",
        collector_path=str(collector_path),
        collector_sha256=T085_COLLECTOR_SHA256,
        collector_byte_count=actual_collector_byte_count,
        _verification_token=t085_repair._T085_FORMAL_DATASET_VERIFICATION_TOKEN,
    )
    result = train_t085_corrected_value_head(
        parent.model,
        examples,
        repair_seed=85001,
        parent_checkpoint_sha256=parent.sha256,
        parent_checkpoint_path=parent.path,
        training_input_sha256=T085_COLLECTOR_SHA256,
        training_input_path=str(collector_path),
        training_input_byte_count=actual_collector_byte_count,
        parent_guidance_provenance=parent.training_data_provenance,
        formal_dataset=formal_dataset,
    )
    assert result.invariance_audit["valid"] is True
    assert result.invariance_audit["example_count"] == T085_FORMAL_ROW_COUNT
    assert (
        result.training_data_provenance["parent_checkpoint_computed_sha256"]
        == parent.sha256
    )


def test_t084_formal_dataset_collector_hash_bypass_is_rejected() -> None:
    with pytest.raises(ValueError, match="cannot be disabled"):
        resolve_t084_formal_dataset(
            "/path/that-is-not-consulted.json",
            verify_collector_hash=False,
        )


def _formal_row_with_replicate_mean(target_mean: float) -> dict[str, object]:
    state = [0.0, 0.0]
    public_model_input = {
        "schema_id": "t084-public-torch-policy-value-input-v1",
        "schema_version": 1,
        "feature_schema_id": "public-tactical-v2",
        "feature_schema_version": 2,
        "snapshot_features": [0.0],
        "public_context_features": [0.0],
        "state_features": state,
        "legal_action_features": [[0.0, 1.0]],
        "eligible_action_indices": [0],
        "public_context_feature_schema_id": "public-context-model-input-v1",
        "public_context_feature_schema_version": 1,
        "public_context_feature_size": 1,
        "shape": {
            "snapshot_features": [1],
            "public_context_features": [1],
            "state_features": [2],
            "legal_action_features": [1, 2],
        },
        "hidden_state_excluded": True,
    }
    return {
        "sampling_arm": "unguided_search_v2",
        "act": 1,
        "root_identity": "root",
        "exact_leaf_identity": "leaf",
        "exact_hidden_state_payload": {"opaque": True},
        "exact_state_digest": "digest",
        "public_projection": {"visible": True},
        "public_model_input": public_model_input,
        "legal_actions": [{"id": "card"}],
        "source_complete_identity_sha256": "source",
        "depth": 1,
        "target_mean": target_mean,
        "replicates": [
            {
                "terminal": True,
                "cap_hit": False,
                "transition_count": 1,
                "terminal_evaluate_end_state": 3.0,
            }
            for _ in range(100)
        ],
    }


def test_formal_target_mean_is_bound_to_replicate_population_mean() -> None:
    assert _formal_example(_formal_row_with_replicate_mean(3.0)).native_utility == 3.0
    with pytest.raises(ValueError, match="population mean"):
        _formal_example(_formal_row_with_replicate_mean(3.0 + 1e-8))


def test_loader_fails_closed_on_nested_stale_outcome_target_kind(tmp_path) -> None:
    path = T085_PARENT_CHECKPOINT_PATH_BY_SEED[85001]
    if not Path(path).is_file():
        pytest.skip("retained T064 parent checkpoint is not mounted")
    raw = torch.load(path, map_location="cpu", weights_only=True)
    raw["outcome_target_kind"] = "terminal_battle_survival_probability"
    raw["metadata"]["outcome_target_kind"] = (
        "search_v2_leaf_continuation_native_utility_v1"
    )
    stale = tmp_path / "stale_nested_corrected.pt"
    torch.save(raw, stale)
    with pytest.raises(ValueError, match="authoritative top-level"):
        load_torch_policy_value_checkpoint(str(stale))

    raw = torch.load(path, map_location="cpu", weights_only=True)
    raw["outcome_target_kind"] = "search_v2_leaf_continuation_native_utility_v1"
    raw["metadata"]["outcome_target_kind"] = "terminal_battle_survival_probability"
    stale = tmp_path / "stale_nested_survival.pt"
    torch.save(raw, stale)
    with pytest.raises(ValueError, match="authoritative top-level"):
        load_torch_policy_value_checkpoint(str(stale))
