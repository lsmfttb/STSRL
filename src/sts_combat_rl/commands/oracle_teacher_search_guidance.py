"""Oracle teacher search-guidance trainer/checkpoint artifact workflow."""

from __future__ import annotations

from collections.abc import Callable, Mapping
import hashlib
import json
from pathlib import Path
from typing import Any

from sts_combat_rl.commands.pytorch_search_guidance import (
    build_pytorch_search_guidance_training_data_provenance,
)
from sts_combat_rl.sim.assisted_source_generation import load_assisted_source_pool_jsonl
from sts_combat_rl.sim.battle_start_pool import load_natural_battle_start_pool_jsonl
from sts_combat_rl.sim.contract import CheckpointingSimulatorAdapter
from sts_combat_rl.sim.oracle_teacher import load_oracle_teacher_dataset_jsonl
from sts_combat_rl.sim.oracle_teacher_search_guidance import (
    OracleTeacherSearchGuidanceBridgeReport,
    attach_checkpoint_summary,
    attach_trainer_artifact_identity,
    build_oracle_teacher_search_guidance_dataset,
    dump_oracle_teacher_search_guidance_bridge_report_json,
    format_oracle_teacher_search_guidance_bridge_report,
    load_oracle_teacher_scaleup_manifest_json,
)
from sts_combat_rl.sim.trainer_input import dump_trainer_input_dataset_jsonl
from sts_combat_rl.sim.training_gate import (
    TrainingScaleGateConfig,
    build_training_gate_report,
)


def run_oracle_teacher_search_guidance_from_paths(
    *,
    adapter_factory: Callable[[], CheckpointingSimulatorAdapter],
    manifest_path: Path,
    selected_budget: int,
    output_path: Path,
    target: str,
    stability_filter: str,
    report_output_path: Path | None = None,
    checkpoint_output_path: Path | None = None,
    training_config: Any | None = None,
    gate_config: TrainingScaleGateConfig | None = None,
    gate_override: str = "none",
) -> OracleTeacherSearchGuidanceBridgeReport:
    """Convert one teacher budget artifact and optionally train a checkpoint."""

    manifest_bytes = manifest_path.read_bytes()
    with manifest_path.open("r", encoding="utf-8") as stream:
        manifest = load_oracle_teacher_scaleup_manifest_json(stream)
    budget_artifact = _budget_artifact(manifest, selected_budget)
    teacher_path = _resolve_manifest_path(
        manifest_path,
        _required_path_string(
            _mapping(budget_artifact.get("teacher_artifact")).get("path"),
            "teacher artifact path",
        ),
    )
    t022_report_path = _resolve_manifest_path(
        manifest_path,
        _required_path_string(
            _mapping(budget_artifact.get("t022_report_artifact")).get("path"),
            "T022 report path",
        ),
    )
    source_pool_key, source_pool_artifact = _source_pool_artifact(manifest)
    source_pool_path = _resolve_manifest_path(
        manifest_path,
        _required_path_string(source_pool_artifact.get("path"), "source pool path"),
    )

    teacher_bytes = teacher_path.read_bytes()
    with teacher_path.open("r", encoding="utf-8") as stream:
        teacher_dataset = load_oracle_teacher_dataset_jsonl(stream)
    t022_report_bytes = t022_report_path.read_bytes()
    with t022_report_path.open("r", encoding="utf-8") as stream:
        t022_report = _load_json_object(stream, "T022 report")
    source_pool_bytes = source_pool_path.read_bytes()
    with source_pool_path.open("r", encoding="utf-8") as stream:
        if source_pool_key == "assisted_pool":
            assisted_artifact = load_assisted_source_pool_jsonl(stream)
            source_pool = assisted_artifact.pool
            source_pool_extra_identity = {
                "schema_id": assisted_artifact.schema_id,
                "format_version": assisted_artifact.format_version,
                "source_pool_format_version": assisted_artifact.pool.format_version,
                "assistance_level": assisted_artifact.assistance_level,
                "assistance_schedule": (
                    assisted_artifact.assistance_schedule.to_dict()
                ),
                "distribution_kind": "assisted_run",
                "source_shard_count": len(assisted_artifact.source_shards),
            }
        else:
            source_pool = load_natural_battle_start_pool_jsonl(stream)
            source_pool_extra_identity = {
                "format_version": source_pool.format_version,
            }

    dataset, report = build_oracle_teacher_search_guidance_dataset(
        adapter_factory=adapter_factory,
        manifest=manifest,
        teacher_dataset=teacher_dataset,
        source_pool=source_pool,
        selected_budget=selected_budget,
        target=target,
        stability_filter=stability_filter,
        manifest_identity=_artifact_identity(
            manifest_path,
            manifest_bytes,
            schema_id=manifest.get("schema_id"),
            format_version=manifest.get("format_version"),
        ),
        teacher_artifact_identity=_artifact_identity(
            teacher_path,
            teacher_bytes,
            schema_id=teacher_dataset.artifact_schema_id,
            format_version=teacher_dataset.format_version,
            record_count=len(teacher_dataset.records),
        ),
        t022_report_identity=_artifact_identity(
            t022_report_path,
            t022_report_bytes,
            schema_id=t022_report.get("schema_id"),
            format_version=t022_report.get("format_version"),
        ),
        source_pool_identity=_artifact_identity(
            source_pool_path,
            source_pool_bytes,
            source_pool_kind=source_pool_key,
            record_count=len(source_pool.records),
            **source_pool_extra_identity,
        ),
    )
    if report.problems:
        if report_output_path is not None:
            report_output_path.parent.mkdir(parents=True, exist_ok=True)
            with report_output_path.open("w", encoding="utf-8", newline="\n") as stream:
                dump_oracle_teacher_search_guidance_bridge_report_json(report, stream)
        return report

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="\n") as stream:
        dump_trainer_input_dataset_jsonl(dataset, stream)
    trainer_bytes = output_path.read_bytes()
    report = attach_trainer_artifact_identity(
        report,
        _artifact_identity(
            output_path,
            trainer_bytes,
            format_version=dataset.format_version,
            record_count=len(dataset.records),
        ),
    )

    if checkpoint_output_path is not None:
        report = _train_optional_checkpoint(
            report,
            dataset=dataset,
            trainer_input_path=output_path,
            trainer_input_bytes=trainer_bytes,
            checkpoint_output_path=checkpoint_output_path,
            training_config=training_config,
            gate_config=gate_config,
            gate_override=gate_override,
        )

    if report_output_path is not None:
        report_output_path.parent.mkdir(parents=True, exist_ok=True)
        with report_output_path.open("w", encoding="utf-8", newline="\n") as stream:
            dump_oracle_teacher_search_guidance_bridge_report_json(report, stream)
    return report


def format_oracle_teacher_search_guidance_command(
    report: OracleTeacherSearchGuidanceBridgeReport,
) -> str:
    return format_oracle_teacher_search_guidance_bridge_report(report)


def _train_optional_checkpoint(
    report: OracleTeacherSearchGuidanceBridgeReport,
    *,
    dataset: Any,
    trainer_input_path: Path,
    trainer_input_bytes: bytes,
    checkpoint_output_path: Path,
    training_config: Any,
    gate_config: TrainingScaleGateConfig | None,
    gate_override: str,
) -> OracleTeacherSearchGuidanceBridgeReport:
    from sts_combat_rl.sim.torch_policy_value import (
        TorchPolicyValueTrainingConfig,
        save_torch_policy_value_checkpoint,
        train_torch_policy_value,
    )

    active_training_config = training_config or TorchPolicyValueTrainingConfig()
    gate_report = build_training_gate_report(
        dataset,
        gate_config,
        override=gate_override,
    )
    result = train_torch_policy_value(
        dataset,
        active_training_config,
        gate_report=gate_report,
    )
    checkpoint_identity: dict[str, Any] = {}
    problems: list[str] = []
    if result.report.training_ok:
        checkpoint_output_path.parent.mkdir(parents=True, exist_ok=True)
        save_torch_policy_value_checkpoint(
            result,
            str(checkpoint_output_path),
            training_data_provenance=(
                build_pytorch_search_guidance_training_data_provenance(
                    dataset,
                    trainer_input_path,
                    trainer_input_bytes=trainer_input_bytes,
                    gate_report=gate_report,
                )
            ),
            metadata={
                "task_id": dataset.generation_metadata.get("task_id"),
                "workflow": dataset.generation_metadata.get("workflow"),
                "source_pool_kind": dataset.generation_metadata.get("source_pool_kind"),
                "checkpoint_role": "oracle_teacher_search_guidance_diagnostic",
                "evidence_boundary": {
                    "information_regime": "full_simulator_state_oracle_like",
                    "not_controller_strength_evidence": True,
                },
            },
        )
        checkpoint_bytes = checkpoint_output_path.read_bytes()
        checkpoint_identity = _artifact_identity(
            checkpoint_output_path,
            checkpoint_bytes,
            schema_id="torch-policy-value-checkpoint-v1",
        )
    else:
        problems.append("diagnostic checkpoint training failed")
    return attach_checkpoint_summary(
        report,
        checkpoint_identity=checkpoint_identity,
        training_gate_override=gate_override,
        broad_training_gate_status={
            "training_allowed": gate_report.training_allowed,
            "override": gate_report.override,
            "gate_passed_without_override": gate_report.gate_passed_without_override,
        },
        raw_diagnostic_metrics={
            "training_ok": result.report.training_ok,
            "policy_target_kind": result.report.policy_target_kind,
            "initial_policy_loss": (
                result.report.initial_evaluation.average_policy_loss
            ),
            "final_policy_loss": result.report.final_evaluation.average_policy_loss,
            "final_policy_top1_agreement": (
                result.report.final_evaluation.policy_top1_agreement
            ),
            "final_survival_mean_absolute_error": (
                result.report.final_evaluation.outcome_mean_absolute_error
            ),
            "final_terminal_absolute_hp_mean_absolute_error": (
                result.report.final_evaluation.hp_mean_absolute_error
            ),
            "final_structured_resource_loss": (
                result.report.final_evaluation.average_resource_loss
            ),
            "final_structured_resource_target_record_count": (
                result.report.final_evaluation.resource_target_record_count
            ),
            "final_structured_resource_mean_absolute_errors": dict(
                result.report.final_evaluation.resource_mean_absolute_errors
            ),
            "example_count": result.report.example_count,
        },
        problems=problems,
    )


def _budget_artifact(manifest: Mapping[str, Any], budget: int) -> dict[str, Any]:
    for artifact in _mapping_list(manifest.get("generated_artifacts")):
        if artifact.get("budget") == budget:
            return artifact
    raise ValueError(f"T023 manifest has no generated artifact for budget {budget}")


def _artifact_identity(
    path: Path,
    data: bytes,
    **extra: Any,
) -> dict[str, Any]:
    result = {
        "path": str(path),
        "sha256": hashlib.sha256(data).hexdigest(),
        "byte_count": len(data),
    }
    for key, value in extra.items():
        if value is not None:
            result[key] = value
    return result


def _resolve_manifest_path(manifest_path: Path, raw_path: str) -> Path:
    path = Path(raw_path)
    if path.is_absolute():
        return path
    if path.exists():
        return path
    return manifest_path.parent / path


def _load_json_object(stream: Any, label: str) -> dict[str, Any]:
    value = json.load(stream)
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a JSON object")
    return value


def _required_path_string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"T023 manifest is missing {label}")
    return value


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _mapping_list(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [dict(item) for item in value if isinstance(item, Mapping)]


def _source_pool_artifact(manifest: Mapping[str, Any]) -> tuple[str, dict[str, Any]]:
    input_artifacts = _mapping(manifest.get("input_artifacts"))
    natural_pool = _mapping(input_artifacts.get("natural_pool"))
    assisted_pool = _mapping(input_artifacts.get("assisted_pool"))
    if natural_pool and assisted_pool:
        raise ValueError("T023/T043 manifest must not contain two source pools")
    if assisted_pool:
        return "assisted_pool", assisted_pool
    if natural_pool:
        return "natural_pool", natural_pool
    raise ValueError("T023/T043 manifest is missing source pool identity")
