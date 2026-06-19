"""Framework-neutral trainer input dataset helpers.

This module only packages already-collected, reward-labeled battle decisions
into a serializable shape. It does not implement a trainer, replay buffer,
Gymnasium environment, RL algorithm, or game mechanics.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass, field, replace
import json
import math
from typing import Any, TextIO

from sts_combat_rl.sim.artifact_versioning import (
    ArtifactDocument,
    ArtifactMigration,
    ArtifactMigrationReport,
    migrate_artifact_document,
    preserved_migration_report,
)
from sts_combat_rl.sim.decision_record import (
    DECISION_RECORD_SCHEMA_VERSION,
    DecisionRecord,
    decision_record_kwargs,
    decision_record_problems,
    legacy_index_action_identities,
)
from sts_combat_rl.sim.reward_labeling import (
    BattleDecisionRewardLabel,
    RewardLabeledBattleDecisionBatch,
)
from sts_combat_rl.sim.trainer_input_contract import (
    build_trainer_input_contract_report,
)


TRAINER_INPUT_DATASET_FORMAT_VERSION = 2
TRAINER_INPUT_DATASET_MIGRATIONS = (
    ArtifactMigration(
        source_version=1,
        target_version=TRAINER_INPUT_DATASET_FORMAT_VERSION,
        migrate=lambda document: _migrate_trainer_input_v1_to_v2(document),
        losses=(
            "v1 omitted per-decision controller provenance",
            "v1 omitted legal action ids; migrated action identities are index-only",
            "v1 omitted source distribution metadata beyond seed",
        ),
    ),
)


@dataclass(frozen=True, kw_only=True)
class TrainerInputRecord(DecisionRecord):
    """One serializable future-trainer input row."""

    example_index: int
    rollout_index: int
    segment_index: int
    segment_step_index: int
    segment_decision_count: int
    segment_end_reason: str
    is_segment_final_step: bool
    segment_reward: float
    step_reward: float
    return_to_go: float
    reward_contributions: dict[str, float] = field(default_factory=dict)
    raw_reward_components: dict[str, float | None] = field(default_factory=dict)


@dataclass(frozen=True)
class TrainerInputDataset:
    """A framework-neutral trainer input dataset with variable legal actions."""

    format_version: int
    reward_allocation: str
    source_rollout_count: int
    segment_count: int
    snapshot_feature_size: int | None
    action_feature_size: int | None
    decision_record_schema_version: int = DECISION_RECORD_SCHEMA_VERSION
    generation_metadata: dict[str, Any] = field(default_factory=dict)
    records: list[TrainerInputRecord] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)
    migration_report: ArtifactMigrationReport = field(
        default_factory=lambda: ArtifactMigrationReport(
            source_version=TRAINER_INPUT_DATASET_FORMAT_VERSION,
            target_version=TRAINER_INPUT_DATASET_FORMAT_VERSION,
        )
    )


@dataclass(frozen=True)
class TrainerInputDatasetSmokeReport:
    """Serialization/loader smoke report for future trainer input data."""

    format_version: int
    reward_allocation: str
    source_rollout_count: int
    segment_count: int
    record_count: int
    round_trip_ok: bool
    contract_ok: bool
    snapshot_feature_size: int | None
    action_feature_size: int | None
    step_reward_total: float
    return_to_go_total: float
    max_legal_actions: int
    max_eligible_actions: int
    terminal_after_step_count: int
    migration_losses: tuple[str, ...] = ()
    generation_metadata: dict[str, Any] = field(default_factory=dict)
    screen_state_counts: Counter[str] = field(default_factory=Counter)
    chosen_action_kind_counts: Counter[str] = field(default_factory=Counter)
    label_end_reason_counts: Counter[str] = field(default_factory=Counter)
    problems: list[str] = field(default_factory=list)


def build_trainer_input_dataset(
    batch: RewardLabeledBattleDecisionBatch,
    *,
    generation_metadata: Mapping[str, Any] | None = None,
) -> TrainerInputDataset:
    """Build a serializable dataset from aligned battle examples and labels."""

    contract = build_trainer_input_contract_report(batch)
    records = [
        _record_from_pair(index, example, label)
        for index, (example, label) in enumerate(
            zip(batch.decision_batch.examples, batch.reward_labels)
        )
    ]
    return TrainerInputDataset(
        format_version=TRAINER_INPUT_DATASET_FORMAT_VERSION,
        reward_allocation=batch.reward_allocation,
        source_rollout_count=batch.source_rollout_count,
        segment_count=batch.segment_count,
        snapshot_feature_size=batch.decision_batch.snapshot_feature_size,
        action_feature_size=batch.decision_batch.action_feature_size,
        decision_record_schema_version=DECISION_RECORD_SCHEMA_VERSION,
        generation_metadata=_json_safe_dict(generation_metadata or {}),
        records=records,
        problems=list(contract.problems),
    )


def build_trainer_input_dataset_smoke_report(
    batch: RewardLabeledBattleDecisionBatch,
    *,
    generation_metadata: Mapping[str, Any] | None = None,
) -> TrainerInputDatasetSmokeReport:
    """Validate dataset packaging and a JSONL round trip."""

    contract = build_trainer_input_contract_report(batch)
    dataset = build_trainer_input_dataset(
        batch,
        generation_metadata=generation_metadata,
    )
    encoded = trainer_input_dataset_to_jsonl_text(dataset)
    loaded = load_trainer_input_dataset_jsonl_text(encoded)
    round_trip_ok = dataset == loaded
    problems = list(dataset.problems)
    problems.extend(_dataset_shape_problems(dataset))
    if not round_trip_ok:
        problems.append("JSONL round trip changed trainer input dataset")

    return TrainerInputDatasetSmokeReport(
        format_version=dataset.format_version,
        reward_allocation=dataset.reward_allocation,
        source_rollout_count=dataset.source_rollout_count,
        segment_count=dataset.segment_count,
        record_count=len(dataset.records),
        round_trip_ok=round_trip_ok,
        contract_ok=contract.contract_ok,
        snapshot_feature_size=dataset.snapshot_feature_size,
        action_feature_size=dataset.action_feature_size,
        step_reward_total=sum(record.step_reward for record in dataset.records),
        return_to_go_total=sum(record.return_to_go for record in dataset.records),
        max_legal_actions=max(
            (len(record.legal_action_features) for record in dataset.records),
            default=0,
        ),
        max_eligible_actions=max(
            (len(record.eligible_action_indices) for record in dataset.records),
            default=0,
        ),
        terminal_after_step_count=sum(
            1 for record in dataset.records if record.terminal_after_step
        ),
        migration_losses=dataset.migration_report.losses,
        generation_metadata=dataset.generation_metadata,
        screen_state_counts=Counter(record.screen_state for record in dataset.records),
        chosen_action_kind_counts=Counter(
            record.chosen_action_kind for record in dataset.records
        ),
        label_end_reason_counts=Counter(
            record.segment_end_reason for record in dataset.records
        ),
        problems=problems,
    )


def format_trainer_input_dataset_smoke_report(
    report: TrainerInputDatasetSmokeReport,
) -> str:
    """Format the dataset packaging smoke report for stderr."""

    lines = [
        "Trainer input dataset smoke summary",
        "scope: dataset packaging only; no trainer, environment, or RL algorithm",
        f"format version: {report.format_version}",
        f"reward allocation: {report.reward_allocation}",
        f"source rollouts: {report.source_rollout_count}",
        f"segments: {report.segment_count}",
        f"records: {report.record_count}",
        f"contract ok: {_yes_no(report.contract_ok)}",
        f"JSONL round trip ok: {_yes_no(report.round_trip_ok)}",
        f"snapshot feature size: {_optional_int(report.snapshot_feature_size)}",
        f"action feature size: {_optional_int(report.action_feature_size)}",
        f"max legal actions: {report.max_legal_actions}",
        f"max eligible actions: {report.max_eligible_actions}",
        f"terminal_after_step records: {report.terminal_after_step_count}",
        f"step reward total: {report.step_reward_total:.3f}",
        f"return-to-go total: {report.return_to_go_total:.3f}",
    ]
    _append_counter(lines, "screen states", report.screen_state_counts)
    _append_counter(lines, "chosen action kinds", report.chosen_action_kind_counts)
    _append_counter(lines, "label end reasons", report.label_end_reason_counts)
    lines.append("migration losses:")
    if report.migration_losses:
        lines.extend(f"  {loss}" for loss in report.migration_losses)
    else:
        lines.append("  (none)")
    lines.append("generation metadata:")
    if report.generation_metadata:
        for key in sorted(report.generation_metadata):
            lines.append(f"  {key}: {report.generation_metadata[key]}")
    else:
        lines.append("  (none)")

    lines.append("problems:")
    if report.problems:
        lines.extend(f"  {problem}" for problem in report.problems)
    else:
        lines.append("  (none)")

    return "\n".join(lines)


def dump_trainer_input_dataset_jsonl(
    dataset: TrainerInputDataset,
    stream: TextIO,
) -> None:
    """Write a trainer input dataset as JSONL."""

    _require_current_dataset_schema(dataset)
    stream.write(
        json.dumps(
            _metadata_row(dataset),
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
    )
    stream.write("\n")
    for record in dataset.records:
        stream.write(
            json.dumps(
                {"type": "record", "record": _record_to_dict(record)},
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            )
        )
        stream.write("\n")


def load_trainer_input_dataset_jsonl(stream: TextIO) -> TrainerInputDataset:
    """Load a trainer input dataset from JSONL."""

    metadata: dict[str, Any] | None = None
    raw_records: list[dict[str, Any]] = []
    problems: list[str] = []

    for line_number, raw_line in enumerate(stream, start=1):
        line = raw_line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"line {line_number}: invalid JSONL row: {exc}") from exc
        if not isinstance(row, dict):
            raise ValueError(f"line {line_number}: JSONL row must be an object")

        row_type = row.get("type")
        if row_type == "metadata":
            if metadata is not None:
                raise ValueError(f"line {line_number}: duplicate metadata row")
            metadata_raw = row.get("metadata")
            if not isinstance(metadata_raw, dict):
                raise ValueError(f"line {line_number}: metadata must be an object")
            metadata = dict(metadata_raw)
        elif row_type == "record":
            record_raw = row.get("record")
            if not isinstance(record_raw, dict):
                raise ValueError(f"line {line_number}: record must be an object")
            raw_records.append(dict(record_raw))
        else:
            raise ValueError(f"line {line_number}: unknown row type {row_type!r}")

    if metadata is None:
        raise ValueError("missing metadata row")

    migrated = migrate_artifact_document(
        metadata,
        raw_records,
        current_version=TRAINER_INPUT_DATASET_FORMAT_VERSION,
        migrations=TRAINER_INPUT_DATASET_MIGRATIONS,
        artifact_name="trainer input dataset",
    )
    metadata = migrated.document.metadata
    records = [_record_from_dict(record) for record in migrated.document.records]

    problems_raw = metadata.get("problems", [])
    if isinstance(problems_raw, list):
        problems = [str(problem) for problem in problems_raw]
    dataset = TrainerInputDataset(
        format_version=_int(metadata.get("format_version")),
        reward_allocation=str(metadata.get("reward_allocation", "")),
        source_rollout_count=_int(metadata.get("source_rollout_count")),
        segment_count=_int(metadata.get("segment_count")),
        snapshot_feature_size=_optional_int_value(
            metadata.get("snapshot_feature_size")
        ),
        action_feature_size=_optional_int_value(metadata.get("action_feature_size")),
        decision_record_schema_version=_int(
            metadata.get(
                "decision_record_schema_version",
                DECISION_RECORD_SCHEMA_VERSION,
            )
        ),
        generation_metadata=_dict(metadata.get("generation_metadata")),
        records=records,
        problems=problems,
        migration_report=preserved_migration_report(
            metadata,
            migrated.report,
            artifact_name="trainer input dataset",
        ),
    )
    shape_problems = _dataset_shape_problems(dataset)
    if shape_problems:
        return replace(
            dataset,
            problems=_unique_problems([*dataset.problems, *shape_problems]),
        )
    return dataset


def trainer_input_dataset_to_jsonl_text(dataset: TrainerInputDataset) -> str:
    """Serialize a dataset to JSONL text."""

    from io import StringIO

    stream = StringIO()
    dump_trainer_input_dataset_jsonl(dataset, stream)
    return stream.getvalue()


def load_trainer_input_dataset_jsonl_text(text: str) -> TrainerInputDataset:
    """Load a dataset from JSONL text."""

    from io import StringIO

    return load_trainer_input_dataset_jsonl(StringIO(text))


def _record_from_pair(
    index: int,
    example: Any,
    label: BattleDecisionRewardLabel,
) -> TrainerInputRecord:
    return TrainerInputRecord(
        **decision_record_kwargs(example),
        example_index=index,
        rollout_index=example.rollout_index,
        segment_index=label.segment_index,
        segment_step_index=label.segment_step_index,
        segment_decision_count=label.segment_decision_count,
        segment_end_reason=label.segment_end_reason,
        is_segment_final_step=label.is_segment_final_step,
        segment_reward=float(label.segment_reward),
        step_reward=float(label.step_reward),
        return_to_go=float(label.return_to_go),
        reward_contributions={
            str(name): float(value)
            for name, value in label.reward_contributions.items()
        },
        raw_reward_components={
            str(name): None if value is None else float(value)
            for name, value in label.raw_reward_components.items()
        },
    )


def _metadata_row(dataset: TrainerInputDataset) -> dict[str, Any]:
    return {
        "type": "metadata",
        "metadata": {
            "format_version": dataset.format_version,
            "reward_allocation": dataset.reward_allocation,
            "source_rollout_count": dataset.source_rollout_count,
            "segment_count": dataset.segment_count,
            "snapshot_feature_size": dataset.snapshot_feature_size,
            "action_feature_size": dataset.action_feature_size,
            "decision_record_schema_version": dataset.decision_record_schema_version,
            "generation_metadata": dataset.generation_metadata,
            "record_count": len(dataset.records),
            "migration_report": dataset.migration_report.to_dict(),
            "problems": dataset.problems,
        },
    }


def _require_current_dataset_schema(dataset: TrainerInputDataset) -> None:
    if dataset.format_version != TRAINER_INPUT_DATASET_FORMAT_VERSION:
        raise ValueError(
            "trainer input writer only emits current format version "
            f"{TRAINER_INPUT_DATASET_FORMAT_VERSION}, got {dataset.format_version}"
        )
    if dataset.decision_record_schema_version != DECISION_RECORD_SCHEMA_VERSION:
        raise ValueError(
            "trainer input writer only emits current decision record schema "
            f"{DECISION_RECORD_SCHEMA_VERSION}, got "
            f"{dataset.decision_record_schema_version}"
        )


def _migrate_trainer_input_v1_to_v2(
    document: ArtifactDocument,
) -> ArtifactDocument:
    metadata = dict(document.metadata)
    metadata["format_version"] = TRAINER_INPUT_DATASET_FORMAT_VERSION
    metadata["decision_record_schema_version"] = DECISION_RECORD_SCHEMA_VERSION
    metadata.setdefault("generation_metadata", {})

    migrated_records: list[dict[str, Any]] = []
    for raw_record in document.records:
        record = dict(raw_record)
        legal_action_kinds = [
            str(kind) for kind in _list(record.get("legal_action_kinds"))
        ]
        identities = legacy_index_action_identities(legal_action_kinds)
        chosen_index = _int(record.get("chosen_action_index"))
        record["record_schema_version"] = DECISION_RECORD_SCHEMA_VERSION
        record["legal_action_identities"] = identities
        record["chosen_action_id"] = None
        record["chosen_action_identity"] = (
            identities[chosen_index] if 0 <= chosen_index < len(identities) else {}
        )
        record["controller_provenance"] = {}
        record["source_metadata"] = _legacy_source_metadata(record)
        migrated_records.append(record)

    return ArtifactDocument(metadata=metadata, records=migrated_records)


def _legacy_source_metadata(record: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "source_kind": "unknown",
        "distribution_kind": "unknown",
        "seed": _optional_int_value(record.get("seed")),
        "ascension": None,
        "act": None,
        "floor": None,
        "room_type": None,
        "encounter_id": None,
    }


def _record_to_dict(record: TrainerInputRecord) -> dict[str, Any]:
    return {
        "example_index": record.example_index,
        "rollout_index": record.rollout_index,
        "seed": record.seed,
        "step_index": record.step_index,
        "screen_state": record.screen_state,
        "record_schema_version": record.record_schema_version,
        "snapshot_features": record.snapshot_features,
        "legal_action_features": record.legal_action_features,
        "legal_action_kinds": record.legal_action_kinds,
        "legal_action_identities": record.legal_action_identities,
        "eligible_action_indices": record.eligible_action_indices,
        "chosen_action_index": record.chosen_action_index,
        "chosen_action_id": record.chosen_action_id,
        "chosen_action_identity": record.chosen_action_identity,
        "chosen_action_kind": record.chosen_action_kind,
        "terminal_after_step": record.terminal_after_step,
        "controller_provenance": record.controller_provenance,
        "source_metadata": record.source_metadata,
        "segment_index": record.segment_index,
        "segment_step_index": record.segment_step_index,
        "segment_decision_count": record.segment_decision_count,
        "segment_end_reason": record.segment_end_reason,
        "is_segment_final_step": record.is_segment_final_step,
        "segment_reward": record.segment_reward,
        "step_reward": record.step_reward,
        "return_to_go": record.return_to_go,
        "reward_contributions": record.reward_contributions,
        "raw_reward_components": record.raw_reward_components,
    }


def _record_from_dict(raw: dict[str, Any]) -> TrainerInputRecord:
    return TrainerInputRecord(
        example_index=_int(raw.get("example_index")),
        rollout_index=_int(raw.get("rollout_index")),
        seed=_optional_int_value(raw.get("seed")),
        step_index=_int(raw.get("step_index")),
        screen_state=str(raw.get("screen_state", "")),
        record_schema_version=_int(
            raw.get("record_schema_version", DECISION_RECORD_SCHEMA_VERSION)
        ),
        snapshot_features=_float_list(raw.get("snapshot_features")),
        legal_action_features=[
            _float_list(action) for action in _list(raw.get("legal_action_features"))
        ],
        legal_action_kinds=[str(kind) for kind in _list(raw.get("legal_action_kinds"))],
        legal_action_identities=[
            _dict(identity) for identity in _list(raw.get("legal_action_identities"))
        ],
        eligible_action_indices=[
            _int(index) for index in _list(raw.get("eligible_action_indices"))
        ],
        chosen_action_index=_int(raw.get("chosen_action_index")),
        chosen_action_id=raw.get("chosen_action_id"),
        chosen_action_identity=_dict(raw.get("chosen_action_identity")),
        chosen_action_kind=str(raw.get("chosen_action_kind", "")),
        terminal_after_step=bool(raw.get("terminal_after_step")),
        controller_provenance=_dict(raw.get("controller_provenance")),
        source_metadata=_dict(raw.get("source_metadata")),
        segment_index=_int(raw.get("segment_index")),
        segment_step_index=_int(raw.get("segment_step_index")),
        segment_decision_count=_int(raw.get("segment_decision_count")),
        segment_end_reason=str(raw.get("segment_end_reason", "")),
        is_segment_final_step=bool(raw.get("is_segment_final_step")),
        segment_reward=_float(raw.get("segment_reward")),
        step_reward=_float(raw.get("step_reward")),
        return_to_go=_float(raw.get("return_to_go")),
        reward_contributions={
            str(name): _float(value)
            for name, value in _dict(raw.get("reward_contributions")).items()
        },
        raw_reward_components={
            str(name): None if value is None else _float(value)
            for name, value in _dict(raw.get("raw_reward_components")).items()
        },
    )


def _dataset_shape_problems(dataset: TrainerInputDataset) -> list[str]:
    problems: list[str] = []
    if dataset.format_version != TRAINER_INPUT_DATASET_FORMAT_VERSION:
        problems.append(
            f"unsupported trainer input format version: {dataset.format_version}"
        )
    if dataset.decision_record_schema_version != DECISION_RECORD_SCHEMA_VERSION:
        problems.append(
            "unsupported decision record schema version: "
            f"{dataset.decision_record_schema_version}"
        )
    for record in dataset.records:
        if record.record_schema_version != dataset.decision_record_schema_version:
            problems.append(
                f"record {record.example_index}: record schema "
                f"{record.record_schema_version} does not match dataset schema "
                f"{dataset.decision_record_schema_version}"
            )
        problems.extend(
            decision_record_problems(
                record,
                label=f"record {record.example_index}",
            )
        )
        if (
            dataset.snapshot_feature_size is not None
            and len(record.snapshot_features) != dataset.snapshot_feature_size
        ):
            problems.append(
                f"record {record.example_index}: snapshot feature size "
                f"{len(record.snapshot_features)} does not match "
                f"{dataset.snapshot_feature_size}"
            )
        if len(record.legal_action_features) != len(record.legal_action_kinds):
            problems.append(
                f"record {record.example_index}: {len(record.legal_action_features)} "
                f"action rows but {len(record.legal_action_kinds)} action kinds"
            )
        for action_index, action_features in enumerate(record.legal_action_features):
            if (
                dataset.action_feature_size is not None
                and len(action_features) != dataset.action_feature_size
            ):
                problems.append(
                    f"record {record.example_index} action {action_index}: "
                    f"action feature size {len(action_features)} does not match "
                    f"{dataset.action_feature_size}"
                )
        for label, value in (
            ("segment_reward", record.segment_reward),
            ("step_reward", record.step_reward),
            ("return_to_go", record.return_to_go),
        ):
            if not math.isfinite(value):
                problems.append(
                    f"record {record.example_index}: {label} is not finite: {value!r}"
                )
    return problems


def _unique_problems(problems: list[str]) -> list[str]:
    return list(dict.fromkeys(problems))


def _float_list(value: Any) -> list[float]:
    return [_float(item) for item in _list(value)]


def _list(value: Any) -> list[Any]:
    return list(value) if isinstance(value, list) else []


def _dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _json_safe_dict(raw: Mapping[str, Any]) -> dict[str, Any]:
    return {str(key): _json_safe_value(value) for key, value in raw.items()}


def _json_safe_value(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Mapping):
        return _json_safe_dict(value)
    if isinstance(value, (list, tuple)):
        return [_json_safe_value(item) for item in value]
    return str(value)


def _int(value: Any) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)):
        return int(value)
    return 0


def _optional_int_value(value: Any) -> int | None:
    if value is None:
        return None
    return _int(value)


def _float(value: Any) -> float:
    if isinstance(value, bool):
        return 1.0 if value else 0.0
    if isinstance(value, (int, float)):
        return float(value)
    return 0.0


def _append_counter(lines: list[str], title: str, counter: Counter[str]) -> None:
    lines.append(f"{title}:")
    if not counter:
        lines.append("  (none)")
        return

    for key, count in counter.most_common():
        lines.append(f"  {key}: {count}")


def _yes_no(value: bool) -> str:
    return "yes" if value else "no"


def _optional_int(value: Any) -> str:
    return str(value) if value is not None else "(none)"
