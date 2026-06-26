from __future__ import annotations

from dataclasses import replace
import hashlib
from io import StringIO
import math
from typing import Any

import pytest

from sts_combat_rl.sim.search_guidance_inference import (
    SearchGuidanceActionScore,
    SearchGuidanceCheckpointProvenance,
    SearchGuidanceInferenceResult,
)
from sts_combat_rl.sim.teacher_guidance_calibration import (
    TEACHER_GUIDANCE_CALIBRATION_REPORT_SCHEMA_ID,
    build_teacher_guidance_calibration_report,
    dump_teacher_guidance_calibration_report_json,
    format_teacher_guidance_calibration_report,
)
from sts_combat_rl.sim.trainer_input import (
    BEHAVIOR_ACTION_AVAILABLE,
    POLICY_TARGET_KIND_ORACLE_SOFT_VISIT,
    POLICY_TARGET_KIND_ORACLE_TEACHER_ACTION,
    trainer_input_dataset_to_jsonl_text,
)

from t009_helpers import make_trainer_dataset


def test_calibration_reports_teacher_one_hot_metrics() -> None:
    dataset = _teacher_dataset(POLICY_TARGET_KIND_ORACLE_TEACHER_ACTION, count=2)
    identity = _trainer_identity(dataset)
    scorer = _FixedScorer(
        _checkpoint_provenance(
            identity["sha256"],
            kind=POLICY_TARGET_KIND_ORACLE_TEACHER_ACTION,
            source="oracle_teacher_row.teacher_action",
            count=2,
        ),
        probabilities_by_record=[
            [0.2, 0.8],
            [0.3, 0.7],
        ],
    )

    report = build_teacher_guidance_calibration_report(
        dataset,
        [scorer],
        trainer_input_artifact_identity=identity,
        top_k=1,
    )
    text = format_teacher_guidance_calibration_report(report, detail_limit=1)
    checkpoint = report.checkpoint_reports[0]

    assert report.schema_id == TEACHER_GUIDANCE_CALIBRATION_REPORT_SCHEMA_ID
    assert report.command_passed is True
    assert checkpoint.teacher_target_metrics["top1_agreement_count"] == 2
    assert checkpoint.teacher_target_metrics["top1_agreement_rate"] == pytest.approx(
        1.0
    )
    assert checkpoint.teacher_target_metrics["mean_cross_entropy"] is not None
    assert checkpoint.calibration["action_row_count"] == 4
    assert checkpoint.source_coverage["unique_source_count"] == 2
    assert checkpoint.source_coverage["repeated_row_count"] == 0
    assert checkpoint.decision_metrics[0]["teacher_target_action_index"] == 1
    assert checkpoint.decision_metrics[0]["model_top_action_index"] == 1
    assert checkpoint.decision_metrics[0]["action_score_rows"][1][
        "target_probability"
    ] == pytest.approx(1.0)
    assert report.evidence_boundary["not_normal_information"] is True
    assert "not normal-information" in text


def test_calibration_reports_soft_visit_targets() -> None:
    dataset = _teacher_dataset(POLICY_TARGET_KIND_ORACLE_SOFT_VISIT, count=1)
    identity = _trainer_identity(dataset)
    scorer = _FixedScorer(
        _checkpoint_provenance(
            identity["sha256"],
            kind=POLICY_TARGET_KIND_ORACLE_SOFT_VISIT,
            source="oracle_teacher_row.soft_visit_target",
            count=1,
        ),
        probabilities_by_record=[[0.4, 0.6]],
    )

    report = build_teacher_guidance_calibration_report(
        dataset,
        [scorer],
        trainer_input_artifact_identity=identity,
    )
    checkpoint = report.checkpoint_reports[0]
    decision = checkpoint.decision_metrics[0]

    assert report.dataset_summary["policy_target_kind"] == (
        POLICY_TARGET_KIND_ORACLE_SOFT_VISIT
    )
    assert checkpoint.teacher_target_metrics["top1_agreement_count"] == 1
    assert checkpoint.teacher_target_metrics["mean_kl_divergence"] is not None
    assert decision["teacher_target_probability"] == pytest.approx(0.75)
    assert decision["action_score_rows"][1]["target_probability"] == pytest.approx(0.75)


def test_mixed_teacher_target_kinds_fail_closed() -> None:
    teacher = _teacher_dataset(POLICY_TARGET_KIND_ORACLE_TEACHER_ACTION, count=1)
    soft = _teacher_dataset(POLICY_TARGET_KIND_ORACLE_SOFT_VISIT, count=1)
    dataset = replace(teacher, records=[teacher.records[0], soft.records[0]])
    identity = _trainer_identity(dataset)
    scorer = _FixedScorer(
        _checkpoint_provenance(
            identity["sha256"],
            kind=POLICY_TARGET_KIND_ORACLE_TEACHER_ACTION,
            source="oracle_teacher_row.teacher_action",
            count=2,
        ),
        probabilities_by_record=[[0.5, 0.5], [0.5, 0.5]],
    )

    with pytest.raises(ValueError, match="mixed policy target kinds"):
        build_teacher_guidance_calibration_report(
            dataset,
            [scorer],
            trainer_input_artifact_identity=identity,
        )


def test_behavior_action_metrics_are_separate_from_teacher_target() -> None:
    dataset = _teacher_dataset(POLICY_TARGET_KIND_ORACLE_TEACHER_ACTION, count=1)
    identity = _trainer_identity(dataset)
    scorer = _FixedScorer(
        _checkpoint_provenance(
            identity["sha256"],
            kind=POLICY_TARGET_KIND_ORACLE_TEACHER_ACTION,
            source="oracle_teacher_row.teacher_action",
            count=1,
        ),
        probabilities_by_record=[[0.9, 0.1]],
    )

    report = build_teacher_guidance_calibration_report(
        dataset,
        [scorer],
        trainer_input_artifact_identity=identity,
    )
    metrics = report.checkpoint_reports[0].teacher_target_metrics
    behavior = report.checkpoint_reports[0].behavior_action_metrics
    decision = report.checkpoint_reports[0].decision_metrics[0]

    assert metrics["top1_agreement_count"] == 0
    assert behavior["top1_agreement_count"] == 1
    assert behavior["teacher_target_agreement_count"] == 0
    assert decision["behavior_action_index"] == 0
    assert decision["teacher_target_action_index"] == 1
    assert decision["model_top_action_index"] == 0


def test_checkpoint_trainer_mismatch_fails_closed() -> None:
    dataset = _teacher_dataset(POLICY_TARGET_KIND_ORACLE_TEACHER_ACTION, count=1)
    identity = _trainer_identity(dataset)
    scorer = _FixedScorer(
        _checkpoint_provenance(
            "0" * 64,
            kind=POLICY_TARGET_KIND_ORACLE_TEACHER_ACTION,
            source="oracle_teacher_row.teacher_action",
            count=1,
        ),
        probabilities_by_record=[[0.2, 0.8]],
    )

    with pytest.raises(ValueError, match="trainer_input_sha256"):
        build_teacher_guidance_calibration_report(
            dataset,
            [scorer],
            trainer_input_artifact_identity=identity,
        )


def test_report_json_output_is_deterministic() -> None:
    dataset = _teacher_dataset(POLICY_TARGET_KIND_ORACLE_TEACHER_ACTION, count=2)
    identity = _trainer_identity(dataset)

    def build_text() -> str:
        scorer = _FixedScorer(
            _checkpoint_provenance(
                identity["sha256"],
                kind=POLICY_TARGET_KIND_ORACLE_TEACHER_ACTION,
                source="oracle_teacher_row.teacher_action",
                count=2,
            ),
            probabilities_by_record=[
                [0.2, 0.8],
                [0.3, 0.7],
            ],
        )
        report = build_teacher_guidance_calibration_report(
            dataset,
            [scorer],
            trainer_input_artifact_identity=identity,
        )
        stream = StringIO()
        dump_teacher_guidance_calibration_report_json(report, stream)
        return stream.getvalue()

    assert build_text() == build_text()


class _FixedScorer:
    name = "fixed_fixture_guidance"

    def __init__(
        self,
        provenance: SearchGuidanceCheckpointProvenance,
        *,
        probabilities_by_record: list[list[float]],
    ) -> None:
        self.checkpoint_provenance = provenance
        self._probabilities_by_record = probabilities_by_record
        self._record_index = 0

    def score_decision_context(self, context) -> SearchGuidanceInferenceResult:
        probabilities = self._probabilities_by_record[self._record_index]
        self._record_index += 1
        return SearchGuidanceInferenceResult(
            scorer_name=self.name,
            checkpoint_provenance=self.checkpoint_provenance,
            legal_action_count=len(context.legal_action_features),
            eligible_action_count=len(context.eligible_action_indices),
            action_scores=[
                SearchGuidanceActionScore(
                    legal_action_index=index,
                    action_kind=context.legal_action_kinds[index],
                    eligible=index in context.eligible_action_indices,
                    policy_logit=math.log(max(probability, 1e-12)),
                    policy_probability=probability,
                    action_identity=dict(
                        context.tactical_legal_actions[index].get("identity", {})
                    ),
                )
                for index, probability in enumerate(probabilities)
            ],
            duration_ms=0.0,
        )


def _teacher_dataset(kind: str, *, count: int):
    base = make_trainer_dataset([(20, 1) for _ in range(count)])
    records = []
    for record in base.records:
        behavior_index = 0
        target_index = 1
        target = [0.0 for _ in record.legal_action_features]
        target[target_index] = 1.0
        target_source = "oracle_teacher_row.teacher_action"
        if kind == POLICY_TARGET_KIND_ORACLE_SOFT_VISIT:
            target = [0.25, 0.75]
            target_source = "oracle_teacher_row.soft_visit_target"
        records.append(
            replace(
                record,
                chosen_action_index=behavior_index,
                chosen_action_id=record.legal_action_identities[behavior_index][
                    "action_id"
                ],
                chosen_action_identity=record.legal_action_identities[behavior_index],
                chosen_action_kind=record.legal_action_kinds[behavior_index],
                controller_provenance={
                    "kind": "oracle_search",
                    "name": "fixture_oracle",
                    "config": {
                        "information_regime": "full_simulator_state_oracle_like"
                    },
                },
                source_metadata={
                    **record.source_metadata,
                    "checkpoint_information_regime": (
                        "full_simulator_state_oracle_like"
                    ),
                    "teacher_information_regime": "full_simulator_state_oracle_like",
                    "sampling_component": "fixture_teacher_budget_100",
                },
                policy_target_kind=kind,
                policy_target=target,
                policy_target_source=target_source,
                policy_target_action_index=target_index,
                policy_target_action_identity=record.legal_action_identities[
                    target_index
                ],
                behavior_action_status=BEHAVIOR_ACTION_AVAILABLE,
                behavior_action={
                    "source": "trainer_input_record.chosen_action_index",
                    "legal_action_index": behavior_index,
                    "action_identity": record.legal_action_identities[behavior_index],
                    "action_kind": record.legal_action_kinds[behavior_index],
                    "action_id": record.legal_action_identities[behavior_index][
                        "action_id"
                    ],
                },
            )
        )
    return replace(base, records=records)


def _trainer_identity(dataset) -> dict[str, Any]:
    text = trainer_input_dataset_to_jsonl_text(dataset)
    sha256 = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return {
        "path": "fixture-trainer.jsonl",
        "sha256": sha256,
        "artifact_id": f"trainer-input-sha256:{sha256}",
        "byte_count": len(text.encode("utf-8")),
    }


def _checkpoint_provenance(
    trainer_sha256: str,
    *,
    kind: str,
    source: str,
    count: int,
) -> SearchGuidanceCheckpointProvenance:
    return SearchGuidanceCheckpointProvenance(
        checkpoint_schema_id="torch-policy-value-checkpoint-v1",
        checkpoint_format_version=1,
        checkpoint_artifact_id=f"fixture-checkpoint:{kind}",
        checkpoint_path=None,
        model_class="fixture-policy-value",
        model_config={"fixture": True},
        trainer_input_artifact_id=f"trainer-input-sha256:{trainer_sha256}",
        trainer_input_sha256=trainer_sha256,
        policy_target_kind=kind,
        policy_target_source=source,
        policy_target_kind_counts={kind: count},
        policy_target_source_counts={source: count},
        information_regime_counts={"full_simulator_state_oracle_like": count},
        source_information_regime_counts={"full_simulator_state_oracle_like": count},
        oracle_like_supervision=True,
        training_data_provenance={
            "trainer_input_sha256": trainer_sha256,
            "target_source_summary": {
                "policy_target_kind": kind,
                "policy_target_source": source,
            },
        },
    )
