from __future__ import annotations

# ruff: noqa: E402

from dataclasses import replace

import pytest

torch = pytest.importorskip("torch")

from sts_combat_rl.sim.model_input import build_model_input_batch
from sts_combat_rl.sim.policy import DecisionContext
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
    assert "not max-HP normalization" in text
    assert "search-guided fixed evaluation: not_run" in text

    checkpoint_path = tmp_path / "policy_value.pt"
    save_torch_policy_value_checkpoint(
        result,
        str(checkpoint_path),
        training_data_provenance={"unit_test": True},
    )
    loaded = load_torch_policy_value_checkpoint(str(checkpoint_path))

    assert loaded.training_data_provenance == {"unit_test": True}
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
