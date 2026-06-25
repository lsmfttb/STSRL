"""Focused T009 workflows for optional PyTorch search guidance."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
import hashlib
from io import StringIO
import json
from pathlib import Path
from typing import Any

from sts_combat_rl.sim.trainer_input import load_trainer_input_dataset_jsonl
from sts_combat_rl.sim.trainer_input_preflight import (
    TrainerInputPreflightReport,
    build_trainer_input_preflight_report,
    format_trainer_input_preflight_report,
)
from sts_combat_rl.sim.training_gate import (
    TrainingGateReport,
    TrainingScaleGateConfig,
    build_training_gate_report,
    format_training_gate_report,
)


@dataclass(frozen=True)
class PytorchSearchGuidanceTrainingWorkflowReport:
    """One offline training attempt over an exported trainer-input dataset."""

    trainer_input_path: Path
    checkpoint_path: Path | None
    gate_report: TrainingGateReport
    checkpoint_written: bool
    training_report: Any | None = None
    problems: tuple[str, ...] = ()

    @property
    def command_ok(self) -> bool:
        return (
            self.gate_report.training_allowed
            and self.training_report is not None
            and bool(getattr(self.training_report, "training_ok", False))
            and self.checkpoint_written
            and not self.problems
        )


def build_trainer_input_preflight_from_path(
    path: Path,
    *,
    gate_config: TrainingScaleGateConfig | None = None,
    gate_override: str = "none",
) -> TrainerInputPreflightReport:
    """Load a trainer-input JSONL artifact and run offline preflight checks."""

    with path.open("r", encoding="utf-8") as stream:
        dataset = load_trainer_input_dataset_jsonl(stream)
    return build_trainer_input_preflight_report(
        dataset,
        path_label=str(path),
        gate_config=gate_config,
        gate_override=gate_override,
    )


def format_trainer_input_preflight_from_path_report(
    report: TrainerInputPreflightReport,
    *,
    detail_limit: int = 8,
) -> str:
    """Format an offline trainer-input preflight report."""

    return format_trainer_input_preflight_report(report, detail_limit=detail_limit)


def run_pytorch_search_guidance_training_from_path(
    trainer_input_path: Path,
    checkpoint_path: Path,
    *,
    training_config: Any,
    gate_config: TrainingScaleGateConfig | None = None,
    gate_override: str = "none",
) -> PytorchSearchGuidanceTrainingWorkflowReport:
    """Run the T009 gate and, only if allowed, train and save a checkpoint."""

    trainer_input_bytes = trainer_input_path.read_bytes()
    dataset = load_trainer_input_dataset_jsonl(
        StringIO(trainer_input_bytes.decode("utf-8"))
    )
    gate_report = build_training_gate_report(
        dataset,
        gate_config,
        override=gate_override,
    )
    if not gate_report.training_allowed:
        return PytorchSearchGuidanceTrainingWorkflowReport(
            trainer_input_path=trainer_input_path,
            checkpoint_path=checkpoint_path,
            gate_report=gate_report,
            checkpoint_written=False,
            problems=("training gate did not allow this dataset",),
        )

    from sts_combat_rl.sim.torch_policy_value import (
        save_torch_policy_value_checkpoint,
        train_torch_policy_value,
    )

    result = train_torch_policy_value(
        dataset,
        training_config,
        gate_report=gate_report,
    )
    problems: list[str] = []
    checkpoint_written = False
    if result.report.training_ok:
        checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
        save_torch_policy_value_checkpoint(
            result,
            str(checkpoint_path),
            training_data_provenance=(
                build_pytorch_search_guidance_training_data_provenance(
                    dataset,
                    trainer_input_path,
                    trainer_input_bytes=trainer_input_bytes,
                    gate_report=gate_report,
                )
            ),
            metadata={
                "task_id": "T009",
                "checkpoint_role": "search_guidance_policy_value",
            },
        )
        checkpoint_written = True
    else:
        problems.append("training report was not ok; checkpoint was not written")
    return PytorchSearchGuidanceTrainingWorkflowReport(
        trainer_input_path=trainer_input_path,
        checkpoint_path=checkpoint_path,
        gate_report=gate_report,
        checkpoint_written=checkpoint_written,
        training_report=result.report,
        problems=tuple(problems),
    )


def format_pytorch_search_guidance_training_workflow_report(
    report: PytorchSearchGuidanceTrainingWorkflowReport,
) -> str:
    """Format the offline T009 training workflow for stderr."""

    sections = [
        format_training_gate_report(report.gate_report),
        "PyTorch search-guidance workflow",
        f"trainer input: {report.trainer_input_path}",
        f"checkpoint path: {report.checkpoint_path or '(none)'}",
        f"checkpoint written: {_yes_no(report.checkpoint_written)}",
    ]
    if report.training_report is not None:
        from sts_combat_rl.sim.torch_policy_value import (
            format_torch_policy_value_training_report,
        )

        sections.append(
            format_torch_policy_value_training_report(report.training_report)
        )
    else:
        sections.extend(
            [
                "PyTorch search-guidance training summary",
                "training ok: no",
                "raw policy diagnostic: not_run",
                "search-guided fixed evaluation: not_run",
            ]
        )
    sections.append("workflow problems:")
    if report.problems:
        sections.extend(f"  {problem}" for problem in report.problems)
    else:
        sections.append("  (none)")
    return "\n\n".join(sections)


def build_pytorch_search_guidance_training_data_provenance(
    dataset: Any,
    trainer_input_path: Path,
    *,
    trainer_input_bytes: bytes,
    gate_report: TrainingGateReport,
) -> dict[str, Any]:
    """Summarize exact trainer input provenance stored in model checkpoints."""

    from sts_combat_rl.sim.torch_policy_value import (
        HP_TARGET_KIND,
        OUTCOME_TARGET_KIND,
        RESOURCE_TARGET_NAMES,
        STRUCTURED_RESOURCE_TARGET_KIND,
    )

    trainer_input_sha256 = hashlib.sha256(trainer_input_bytes).hexdigest()
    return {
        "schema_id": "pytorch-search-guidance-training-data-provenance-v1",
        "trainer_input_path": str(trainer_input_path),
        "trainer_input_artifact_id": f"trainer-input-sha256:{trainer_input_sha256}",
        "trainer_input_sha256": trainer_input_sha256,
        "trainer_input_byte_count": len(trainer_input_bytes),
        "trainer_input_format_version": dataset.format_version,
        "trainer_record_count": len(dataset.records),
        "source_rollout_count": dataset.source_rollout_count,
        "segment_count": dataset.segment_count,
        "generation_metadata": _json_safe_value(dict(dataset.generation_metadata)),
        "dataset_migration_report": dataset.migration_report.to_dict(),
        "controller_provenance_summary": _controller_provenance_summary(
            dataset.records
        ),
        "information_regime_counts": _counter_dict(
            _controller_information_regime(record) for record in dataset.records
        ),
        "source_information_regime_counts": _counter_dict(
            _source_information_regime(record) for record in dataset.records
        ),
        "target_source_summary": {
            **_policy_target_source_summary(dataset.records),
            "outcome_target_kind": OUTCOME_TARGET_KIND,
            "outcome_target_source": (
                "trainer_input_record.structured_battle_outcome.battle_survived"
            ),
            "hp_target_kind": HP_TARGET_KIND,
            "hp_target_source": (
                "trainer_input_record.structured_battle_outcome."
                "terminal_absolute_current_hp"
            ),
            "structured_resource_target_kind": STRUCTURED_RESOURCE_TARGET_KIND,
            "structured_resource_target_source": (
                "trainer_input_record.structured_battle_outcome.terminal"
            ),
            "structured_resource_target_names": list(RESOURCE_TARGET_NAMES),
        },
        "distribution_counts": _counter_dict(
            _distribution_kind(record) for record in dataset.records
        ),
        "source_kind_counts": _counter_dict(
            _metadata_string(record, "source_kind") for record in dataset.records
        ),
        "sampling_component_counts": _counter_dict(
            _metadata_string(record, "sampling_component") for record in dataset.records
        ),
        "stable_source_identity_summary": _stable_source_identity_summary(
            dataset.records
        ),
        "gate_report": gate_report.to_dict(),
    }


def _controller_provenance_summary(records: Sequence[Any]) -> dict[str, Any]:
    by_digest: dict[str, dict[str, Any]] = {}
    counts: Counter[str] = Counter()
    for record in records:
        provenance = _mapping(getattr(record, "controller_provenance", {}))
        canonical = _canonical_json(provenance)
        digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        digest_id = f"sha256:{digest}"
        counts[digest_id] += 1
        by_digest.setdefault(digest_id, provenance)
    return {
        "unique_controller_provenance_count": len(counts),
        "provenances": [
            {
                "digest": digest_id,
                "count": counts[digest_id],
                "provenance": by_digest[digest_id],
            }
            for digest_id in sorted(counts)
        ],
    }


def _stable_source_identity_summary(records: Sequence[Any]) -> dict[str, Any]:
    identities: set[tuple[Any, ...]] = set()
    identity_kind_counts: Counter[str] = Counter()
    missing_count = 0
    for record in records:
        identity = _stable_source_identity(record)
        if identity is None:
            missing_count += 1
            continue
        identities.add(identity)
        identity_kind_counts[str(identity[0])] += 1
    return {
        "unique_source_count": len(identities),
        "missing_source_identity_count": missing_count,
        "identity_kind_counts": dict(sorted(identity_kind_counts.items())),
    }


def _stable_source_identity(record: Any) -> tuple[Any, ...] | None:
    metadata = _mapping(getattr(record, "source_metadata", {}))
    checkpoint_id = _non_empty_string(metadata.get("source_checkpoint_id"))
    if checkpoint_id is not None:
        return ("source_checkpoint_id", checkpoint_id)
    run_id = _non_empty_string(metadata.get("source_run_id"))
    battle_index = _optional_int(metadata.get("source_battle_index"))
    if run_id is not None and battle_index is not None:
        return ("source_run_battle", run_id, battle_index)
    return None


def _policy_target_source_summary(records: Sequence[Any]) -> dict[str, Any]:
    kind_counts = _counter_dict(
        _metadata_attr(record, "policy_target_kind", "missing") for record in records
    )
    source_counts = _counter_dict(
        _metadata_attr(record, "policy_target_source", "missing") for record in records
    )
    return {
        "policy_target_kind": _single_count_key(kind_counts),
        "policy_target_source": _single_count_key(source_counts),
        "policy_target_kind_counts": kind_counts,
        "policy_target_source_counts": source_counts,
    }


def _controller_information_regime(record: Any) -> str:
    provenance = _mapping(getattr(record, "controller_provenance", {}))
    config = _mapping(provenance.get("config"))
    return _non_empty_string(config.get("information_regime")) or "missing"


def _source_information_regime(record: Any) -> str:
    metadata = _mapping(getattr(record, "source_metadata", {}))
    return _non_empty_string(metadata.get("checkpoint_information_regime")) or "missing"


def _distribution_kind(record: Any) -> str:
    metadata = _mapping(getattr(record, "source_metadata", {}))
    value = metadata.get("distribution_kind", metadata.get("source_kind"))
    return _non_empty_string(value) or "unknown"


def _metadata_string(record: Any, key: str) -> str:
    metadata = _mapping(getattr(record, "source_metadata", {}))
    return _non_empty_string(metadata.get(key)) or "missing"


def _metadata_attr(record: Any, key: str, fallback: str) -> str:
    return _non_empty_string(getattr(record, key, None)) or fallback


def _counter_dict(values: Iterable[str]) -> dict[str, int]:
    counter = Counter(str(value) for value in values)
    return dict(sorted(counter.items()))


def _single_count_key(counts: Mapping[str, int]) -> str:
    if len(counts) == 1:
        return next(iter(counts))
    if not counts:
        return "missing"
    return "mixed"


def _canonical_json(value: Any) -> str:
    return json.dumps(_json_safe_value(value), sort_keys=True, separators=(",", ":"))


def _json_safe_value(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Mapping):
        return {str(key): _json_safe_value(item) for key, item in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [_json_safe_value(item) for item in value]
    return str(value)


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _non_empty_string(value: Any) -> str | None:
    if isinstance(value, str) and value:
        return value
    return None


def _optional_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return None


def _yes_no(value: bool) -> str:
    return "yes" if value else "no"
