from __future__ import annotations

# ruff: noqa: E402

from dataclasses import replace

import pytest

torch = pytest.importorskip("torch")

from sts_combat_rl.commands.pytorch_search_guidance import (
    build_pytorch_search_guidance_training_data_provenance,
)
from sts_combat_rl.sim.model_input import build_model_input_batch
from sts_combat_rl.sim.policy import DecisionContext
from sts_combat_rl.sim.trainer_input import trainer_input_dataset_to_jsonl_text
from sts_combat_rl.sim.trainer_input import (
    POLICY_TARGET_KIND_ORACLE_TEACHER_ACTION,
    POLICY_TARGET_SOURCE_BEHAVIOR,
)
from sts_combat_rl.sim.torch_policy_value import (
    SEARCH_GUIDED_FIXED_EVAL_STATUS_NOT_RUN,
    TorchPolicyValueActionScorer,
    TorchPolicyValueTrainingConfig,
    evaluate_torch_policy_value,
    format_torch_policy_value_training_report,
    load_torch_policy_value_checkpoint,
    save_torch_policy_value_checkpoint,
    train_torch_policy_value,
)
from sts_combat_rl.sim.training_gate import (
    TrainingScaleGateConfig,
    build_training_gate_report,
)

from t009_helpers import make_trainer_dataset


def test_torch_policy_value_trains_and_checkpoint_round_trips(tmp_path) -> None:
    dataset = make_trainer_dataset([(20, 1), (20, 1)])
    gate = build_training_gate_report(
        dataset,
        TrainingScaleGateConfig(
            required_ascensions=(20,),
            required_acts=(1,),
            min_records_per_ascension_act=2,
            min_unique_sources_per_ascension_act=2,
        ),
    )

    result = train_torch_policy_value(
        dataset,
        TorchPolicyValueTrainingConfig(
            epochs=8,
            learning_rate=0.01,
            hidden_size=16,
            batch_size=1,
            seed=3,
        ),
        gate_report=gate,
    )
    text = format_torch_policy_value_training_report(result.report)

    assert result.report.training_ok is True
    assert result.report.parameter_count > 0
    assert result.report.final_evaluation.example_count == 2
    assert result.report.final_evaluation.resource_target_record_count == 2
    assert result.report.search_guided_fixed_evaluation_status == (
        SEARCH_GUIDED_FIXED_EVAL_STATUS_NOT_RUN
    )
    assert "raw policy diagnostic final" in text
    assert "public context feature schema: public-context-model-input-v1 v1" in text
    assert "not max-HP normalization" in text
    assert "search-guided fixed evaluation: not_run" in text

    checkpoint_path = tmp_path / "policy_value.pt"
    training_data_provenance = _training_data_provenance(
        dataset,
        gate,
        tmp_path / "trainer.jsonl",
    )
    save_torch_policy_value_checkpoint(
        result,
        str(checkpoint_path),
        training_data_provenance=training_data_provenance,
    )
    loaded = load_torch_policy_value_checkpoint(str(checkpoint_path))

    assert (
        loaded.training_data_provenance["trainer_input_sha256"]
        == (training_data_provenance["trainer_input_sha256"])
    )
    assert loaded.training_data_provenance["trainer_input_artifact_id"] == (
        f"trainer-input-sha256:{training_data_provenance['trainer_input_sha256']}"
    )
    assert (
        loaded.training_data_provenance["controller_provenance_summary"][
            "unique_controller_provenance_count"
        ]
        == 1
    )
    assert loaded.training_data_provenance["information_regime_counts"] == {
        "normal_public_policy": 2
    }
    assert (
        loaded.training_data_provenance["target_source_summary"]["policy_target_source"]
        == "trainer_input_record.chosen_action_index"
    )
    assert loaded.training_data_provenance["distribution_counts"] == {"natural_run": 2}
    assert (
        loaded.training_data_provenance["stable_source_identity_summary"][
            "unique_source_count"
        ]
        == 2
    )

    raw = torch.load(checkpoint_path, map_location="cpu", weights_only=True)
    raw["identity_vocabulary_version"] = "different"
    bad_schema_path = tmp_path / "bad_identity.pt"
    torch.save(raw, bad_schema_path)
    with pytest.raises(ValueError, match="identity_vocabulary_version"):
        load_torch_policy_value_checkpoint(str(bad_schema_path))

    raw = torch.load(checkpoint_path, map_location="cpu", weights_only=True)
    raw["public_context_feature_schema_version"] = 999
    bad_context_version_path = tmp_path / "bad_context_version.pt"
    torch.save(raw, bad_context_version_path)
    with pytest.raises(ValueError, match="public_context_feature_schema_version"):
        load_torch_policy_value_checkpoint(str(bad_context_version_path))

    raw = torch.load(checkpoint_path, map_location="cpu", weights_only=True)
    raw["public_context_feature_names"] = [
        "different",
        *raw["public_context_feature_names"][1:],
    ]
    bad_context_names_path = tmp_path / "bad_context_names.pt"
    torch.save(raw, bad_context_names_path)
    with pytest.raises(ValueError, match="public_context_feature_names"):
        load_torch_policy_value_checkpoint(str(bad_context_names_path))

    raw = torch.load(checkpoint_path, map_location="cpu", weights_only=True)
    raw["training_data_provenance"] = {"trainer_input_path": "trainer.jsonl"}
    bad_provenance_path = tmp_path / "bad_provenance.pt"
    torch.save(raw, bad_provenance_path)
    with pytest.raises(
        ValueError,
        match="training_data_provenance.trainer_input_sha256",
    ):
        load_torch_policy_value_checkpoint(str(bad_provenance_path))

    loaded_eval = evaluate_torch_policy_value(loaded.model, dataset, loaded.config)
    assert loaded_eval.example_count == result.report.final_evaluation.example_count
    assert loaded_eval.resource_target_record_count == 2

    batch = build_model_input_batch(dataset)
    scores = TorchPolicyValueActionScorer(loaded.model).score_action_rows(batch)
    assert len(scores) == len(batch.action_features)

    first = dataset.records[0]
    context = DecisionContext(
        screen_state="BATTLE",
        snapshot_features=first.snapshot_features,
        legal_action_features=first.legal_action_features,
        legal_action_kinds=first.legal_action_kinds,
        eligible_action_indices=first.eligible_action_indices,
        tactical_feature_schema_id=first.feature_schema_id,
        public_run_context=first.public_run_context,
    )
    assert len(TorchPolicyValueActionScorer(loaded.model).score_actions(context)) == 2


def test_torch_policy_value_fails_closed_without_gate_or_override(tmp_path) -> None:
    dataset = make_trainer_dataset([(20, 1), (20, 1)])

    result = train_torch_policy_value(
        dataset,
        TorchPolicyValueTrainingConfig(epochs=1, hidden_size=8),
    )

    assert result.report.training_ok is False
    assert result.report.gate_report.training_allowed is False
    assert any("broad training gate failed" in item for item in result.report.problems)
    with pytest.raises(ValueError, match="refusing to save"):
        save_torch_policy_value_checkpoint(result, str(tmp_path / "bad.pt"))


def test_torch_policy_value_rejects_mismatched_public_schema_context() -> None:
    dataset = make_trainer_dataset([(20, 1), (20, 1)])
    gate = build_training_gate_report(
        dataset,
        TrainingScaleGateConfig(
            required_ascensions=(20,),
            required_acts=(1,),
            min_records_per_ascension_act=1,
            min_unique_sources_per_ascension_act=1,
        ),
    )
    result = train_torch_policy_value(
        dataset,
        TorchPolicyValueTrainingConfig(epochs=1, hidden_size=8),
        gate_report=gate,
    )
    first = dataset.records[0]
    context = DecisionContext(
        screen_state="BATTLE",
        snapshot_features=first.snapshot_features,
        legal_action_features=first.legal_action_features,
        legal_action_kinds=first.legal_action_kinds,
        eligible_action_indices=first.eligible_action_indices,
        tactical_feature_schema_id="different-schema",
        public_run_context=first.public_run_context,
    )

    with pytest.raises(ValueError, match="tactical feature schema"):
        TorchPolicyValueActionScorer(result.model).score_actions(context)


def test_torch_policy_value_requires_structured_outcomes() -> None:
    dataset = make_trainer_dataset([(20, 1), (20, 1)])
    bad_record = replace(
        dataset.records[0],
        structured_battle_outcome_status="legacy_unavailable",
        structured_battle_outcome={},
    )
    bad_dataset = replace(dataset, records=[bad_record, dataset.records[1]])
    gate = build_training_gate_report(
        bad_dataset,
        TrainingScaleGateConfig(
            required_ascensions=(20,),
            required_acts=(1,),
            min_records_per_ascension_act=1,
            min_unique_sources_per_ascension_act=1,
            require_structured_outcomes=False,
        ),
    )

    result = train_torch_policy_value(
        bad_dataset,
        TorchPolicyValueTrainingConfig(epochs=1, hidden_size=8),
        gate_report=gate,
    )

    assert result.report.training_ok is False
    assert any("structured battle outcome" in item for item in result.report.problems)


def test_torch_policy_value_uses_explicit_teacher_policy_target(tmp_path) -> None:
    dataset = make_trainer_dataset([(20, 1), (20, 1)])
    teacher_records = []
    for record in dataset.records:
        target_index = 1 - record.chosen_action_index
        target = [0.0 for _ in record.legal_action_features]
        target[target_index] = 1.0
        teacher_records.append(
            replace(
                record,
                policy_target_kind=POLICY_TARGET_KIND_ORACLE_TEACHER_ACTION,
                policy_target=target,
                policy_target_source="oracle_teacher_row.teacher_action",
                policy_target_action_index=target_index,
                policy_target_action_identity=record.legal_action_identities[
                    target_index
                ],
                behavior_action={
                    "source": POLICY_TARGET_SOURCE_BEHAVIOR,
                    "legal_action_index": record.chosen_action_index,
                    "action_identity": record.chosen_action_identity,
                    "action_kind": record.chosen_action_kind,
                    "action_id": record.chosen_action_id,
                },
            )
        )
    teacher_dataset = replace(dataset, records=teacher_records)
    gate = build_training_gate_report(
        teacher_dataset,
        TrainingScaleGateConfig(
            required_ascensions=(20,),
            required_acts=(1,),
            min_records_per_ascension_act=2,
            min_unique_sources_per_ascension_act=2,
        ),
    )

    result = train_torch_policy_value(
        teacher_dataset,
        TorchPolicyValueTrainingConfig(epochs=1, hidden_size=8, batch_size=1),
        gate_report=gate,
    )
    provenance = _training_data_provenance(
        teacher_dataset,
        gate,
        tmp_path / "teacher-trainer.jsonl",
    )

    assert result.report.training_ok is True
    assert result.report.policy_target_kind == POLICY_TARGET_KIND_ORACLE_TEACHER_ACTION
    assert provenance["target_source_summary"]["policy_target_kind"] == (
        POLICY_TARGET_KIND_ORACLE_TEACHER_ACTION
    )
    assert provenance["target_source_summary"]["policy_target_source"] == (
        "oracle_teacher_row.teacher_action"
    )


def _training_data_provenance(
    dataset,
    gate,
    trainer_input_path,
) -> dict[str, object]:
    trainer_input_bytes = trainer_input_dataset_to_jsonl_text(dataset).encode("utf-8")
    return build_pytorch_search_guidance_training_data_provenance(
        dataset,
        trainer_input_path,
        trainer_input_bytes=trainer_input_bytes,
        gate_report=gate,
    )
