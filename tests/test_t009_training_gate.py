from __future__ import annotations

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
