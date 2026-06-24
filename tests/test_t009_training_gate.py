from __future__ import annotations

from dataclasses import replace

from sts_combat_rl.sim.trainer_input_preflight import (
    build_trainer_input_preflight_report,
    format_trainer_input_preflight_report,
)
from sts_combat_rl.sim.training_gate import (
    TRAINING_GATE_OVERRIDE_SMOKE,
    TrainingScaleGateConfig,
    build_training_gate_report,
    format_training_gate_report,
)

from t009_helpers import make_trainer_dataset


def test_broad_training_gate_fails_when_a0_hides_missing_a20() -> None:
    dataset = make_trainer_dataset([(0, 1), (0, 1)])

    report = build_training_gate_report(
        dataset,
        TrainingScaleGateConfig(
            required_ascensions=(20,),
            required_acts=(1,),
            min_records_per_ascension_act=1,
            min_unique_sources_per_ascension_act=1,
        ),
    )
    text = format_training_gate_report(report)

    assert report.training_allowed is False
    assert report.broad_training_allowed is False
    assert report.observed_ascension_counts == {0: 2}
    assert any("A20/act1" in problem for problem in report.problems)
    assert "observed ascensions:" in text
    assert "0: 2" in text
    assert "broad training allowed: no" in text


def test_smoke_override_allows_plumbing_not_broad_training() -> None:
    dataset = make_trainer_dataset([(0, 1)])

    report = build_training_gate_report(
        dataset,
        TrainingScaleGateConfig(
            required_ascensions=(20,),
            required_acts=(1,),
            min_records_per_ascension_act=1,
            min_unique_sources_per_ascension_act=1,
        ),
        override=TRAINING_GATE_OVERRIDE_SMOKE,
    )

    assert report.training_allowed is True
    assert report.broad_training_allowed is False
    assert report.gate_passed_without_override is False
    assert report.override == "smoke"


def test_gate_does_not_count_repeated_checkpoint_samples_as_unique_sources() -> None:
    dataset = make_trainer_dataset([(20, 1), (20, 1)])
    shared_metadata = dict(dataset.records[0].source_metadata)
    duplicate_records = [
        replace(
            dataset.records[0],
            example_index=0,
            segment_index=0,
            source_metadata=shared_metadata,
        ),
        replace(
            dataset.records[1],
            example_index=1,
            segment_index=99,
            source_metadata=dict(shared_metadata),
        ),
    ]
    duplicated = replace(dataset, records=duplicate_records)

    report = build_training_gate_report(
        duplicated,
        TrainingScaleGateConfig(
            required_ascensions=(20,),
            required_acts=(1,),
            min_records_per_ascension_act=2,
            min_unique_sources_per_ascension_act=2,
        ),
    )

    assert report.training_allowed is False
    assert report.cells[0].unique_source_count == 1
    assert any("unique source count 1" in problem for problem in report.problems)


def test_gate_fails_closed_when_stable_source_identity_is_missing() -> None:
    dataset = make_trainer_dataset([(20, 1)])
    metadata = dict(dataset.records[0].source_metadata)
    metadata.pop("source_checkpoint_id")
    metadata.pop("source_run_id")
    metadata.pop("source_battle_index")
    missing = replace(
        dataset,
        records=[replace(dataset.records[0], source_metadata=metadata)],
    )

    report = build_training_gate_report(
        missing,
        TrainingScaleGateConfig(
            required_ascensions=(20,),
            required_acts=(1,),
            min_records_per_ascension_act=1,
            min_unique_sources_per_ascension_act=1,
        ),
    )

    assert report.training_allowed is False
    assert report.cells[0].unique_source_count == 0
    assert any("missing stable source identity" in item for item in report.problems)


def test_trainer_input_preflight_reports_shape_and_gate_separately() -> None:
    dataset = make_trainer_dataset([(20, 1), (20, 1)])

    report = build_trainer_input_preflight_report(
        dataset,
        gate_config=TrainingScaleGateConfig(
            required_ascensions=(20,),
            required_acts=(1,),
            min_records_per_ascension_act=2,
            min_unique_sources_per_ascension_act=2,
        ),
    )
    text = format_trainer_input_preflight_report(report, detail_limit=1)

    assert report.preflight_ok is True
    assert report.training_gate_report is not None
    assert report.training_gate_report.broad_training_allowed is True
    assert "Trainer input preflight summary" in text
    assert "T009 broad training gate" in text
    assert "model score contract: yes" in text
