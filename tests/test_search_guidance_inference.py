from __future__ import annotations

# ruff: noqa: E402

from dataclasses import replace

import pytest

torch = pytest.importorskip("torch")

from sts_combat_rl.commands.pytorch_search_guidance import (
    build_pytorch_search_guidance_training_data_provenance,
)
from sts_combat_rl.sim.model_input import (
    build_model_input_batch,
    decision_context_from_model_input_batch,
)
from sts_combat_rl.sim.search_guidance_inference import (
    SEARCH_GUIDANCE_INFERENCE_SCHEMA_ID,
    format_search_guidance_inference_result,
)
from sts_combat_rl.sim.torch_policy_value import (
    TorchPolicyValueGuidanceScorer,
    TorchPolicyValueTrainingConfig,
    save_torch_policy_value_checkpoint,
    train_torch_policy_value,
)
from sts_combat_rl.sim.trainer_input import (
    POLICY_TARGET_KIND_ORACLE_TEACHER_ACTION,
    POLICY_TARGET_SOURCE_BEHAVIOR,
    TrainerInputDataset,
    trainer_input_dataset_to_jsonl_text,
)
from sts_combat_rl.sim.training_gate import (
    TrainingScaleGateConfig,
    build_training_gate_report,
)

from t009_helpers import make_trainer_dataset


def test_torch_guidance_scores_public_context_and_reports_provenance(tmp_path) -> None:
    checkpoint_path, dataset = _write_checkpoint(tmp_path)
    context = _first_context(dataset)

    scorer = TorchPolicyValueGuidanceScorer.from_checkpoint_path(checkpoint_path)
    result = scorer.score_decision_context(context)
    text = format_search_guidance_inference_result(result, detail_limit=1)

    assert result.schema_id == SEARCH_GUIDANCE_INFERENCE_SCHEMA_ID
    assert result.inference_ok is True
    assert result.legal_action_count == len(context.legal_action_features)
    assert result.eligible_action_count == len(context.eligible_action_indices)
    assert len(result.action_scores) == len(context.legal_action_features)
    assert sum(
        score.policy_probability for score in result.action_scores
    ) == pytest.approx(1.0)
    assert result.value_prediction is not None
    assert result.value_prediction.battle_survival_probability is not None
    assert result.value_prediction.terminal_absolute_current_hp is not None
    assert result.value_prediction.structured_resource_values
    assert result.checkpoint_provenance.policy_target_kind == (
        "behavior_chosen_action_one_hot"
    )
    assert result.checkpoint_provenance.policy_target_source == (
        "trainer_input_record.chosen_action_index"
    )
    assert result.checkpoint_provenance.information_regime_counts == {
        "normal_public_policy": 2
    }
    assert result.checkpoint_provenance.oracle_like_supervision is False
    assert "no controller, simulator, or action selection" in text
    assert "oracle-like supervision: no" in text


def test_torch_guidance_marks_oracle_teacher_supervision(tmp_path) -> None:
    base = make_trainer_dataset([(20, 1), (20, 1)])
    teacher_records = []
    for record in base.records:
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
    dataset = replace(base, records=teacher_records)
    checkpoint_path, dataset = _write_checkpoint(tmp_path, dataset=dataset)

    result = TorchPolicyValueGuidanceScorer.from_checkpoint_path(
        checkpoint_path
    ).score_decision_context(_first_context(dataset))

    assert result.checkpoint_provenance.policy_target_kind == (
        POLICY_TARGET_KIND_ORACLE_TEACHER_ACTION
    )
    assert result.checkpoint_provenance.policy_target_source == (
        "oracle_teacher_row.teacher_action"
    )
    assert result.checkpoint_provenance.oracle_like_supervision is True


def test_torch_guidance_fails_closed_on_bad_context_schema(tmp_path) -> None:
    checkpoint_path, dataset = _write_checkpoint(tmp_path)
    context = _first_context(dataset)
    scorer = TorchPolicyValueGuidanceScorer.from_checkpoint_path(checkpoint_path)

    with pytest.raises(ValueError, match="public_run_context schema_id"):
        scorer.score_decision_context(replace(context, public_run_context={}))

    with pytest.raises(ValueError, match="snapshot feature size"):
        scorer.score_decision_context(
            replace(context, snapshot_features=[*context.snapshot_features, 0.0])
        )


def test_torch_guidance_fails_closed_on_bad_checkpoint_schema(tmp_path) -> None:
    checkpoint_path, _ = _write_checkpoint(tmp_path)
    raw = torch.load(checkpoint_path, map_location="cpu", weights_only=True)
    raw["schema_id"] = "different"
    bad_path = tmp_path / "bad.pt"
    torch.save(raw, bad_path)

    with pytest.raises(ValueError, match="unsupported PyTorch policy/value"):
        TorchPolicyValueGuidanceScorer.from_checkpoint_path(bad_path)


def _write_checkpoint(
    tmp_path,
    *,
    dataset: TrainerInputDataset | None = None,
):
    active_dataset = dataset or make_trainer_dataset([(20, 1), (20, 1)])
    gate = build_training_gate_report(
        active_dataset,
        TrainingScaleGateConfig(
            required_ascensions=(20,),
            required_acts=(1,),
            min_records_per_ascension_act=2,
            min_unique_sources_per_ascension_act=2,
        ),
    )
    result = train_torch_policy_value(
        active_dataset,
        TorchPolicyValueTrainingConfig(
            epochs=1,
            hidden_size=8,
            batch_size=1,
            seed=3,
        ),
        gate_report=gate,
    )
    checkpoint_path = tmp_path / "policy_value.pt"
    trainer_path = tmp_path / "trainer.jsonl"
    trainer_bytes = trainer_input_dataset_to_jsonl_text(active_dataset).encode("utf-8")
    trainer_path.write_bytes(trainer_bytes)
    save_torch_policy_value_checkpoint(
        result,
        str(checkpoint_path),
        training_data_provenance=build_pytorch_search_guidance_training_data_provenance(
            active_dataset,
            trainer_path,
            trainer_input_bytes=trainer_bytes,
            gate_report=gate,
        ),
    )
    return checkpoint_path, active_dataset


def _first_context(dataset: TrainerInputDataset):
    batch = build_model_input_batch(dataset)
    return decision_context_from_model_input_batch(batch, 0)
