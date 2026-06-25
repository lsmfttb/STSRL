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
    decision_record_identity_problems,
    decision_record_kwargs,
    decision_record_problems,
    legacy_index_action_identities,
)
from sts_combat_rl.sim.features import (
    IDENTITY_VOCABULARY_VERSION,
    LEGACY_FEATURE_SCHEMA_ID,
    TACTICAL_FEATURE_SCHEMA_ID,
    TACTICAL_FEATURE_SCHEMA_VERSION,
)
from sts_combat_rl.sim.public_context_artifacts import (
    PUBLIC_CONTEXT_LEGACY_LOSS,
    PUBLIC_CONTEXT_LEGACY_UNAVAILABLE,
)
from sts_combat_rl.sim.reward_labeling import (
    BattleDecisionRewardLabel,
    RewardLabeledBattleDecisionBatch,
)
from sts_combat_rl.sim.resource_outcome import (
    BATTLE_RESOURCE_OUTCOME_AVAILABLE,
    BATTLE_RESOURCE_OUTCOME_LEGACY_LOSS,
    BATTLE_RESOURCE_OUTCOME_SCHEMA_ID,
    BATTLE_RESOURCE_OUTCOME_SCHEMA_VERSION,
    battle_resource_outcome_problems,
    legacy_unavailable_battle_resource_outcome,
)
from sts_combat_rl.sim.trainer_input_contract import (
    build_trainer_input_contract_report,
)


TRAINER_INPUT_DATASET_FORMAT_VERSION = 6
TRAINER_POLICY_TARGET_SCHEMA_ID = "trainer-policy-target-v1"
TRAINER_POLICY_TARGET_SCHEMA_VERSION = 1
POLICY_TARGET_KIND_BEHAVIOR = "behavior_chosen_action_one_hot"
POLICY_TARGET_KIND_ORACLE_TEACHER_ACTION = "oracle_teacher_action_one_hot"
POLICY_TARGET_KIND_ORACLE_SOFT_VISIT = "oracle_soft_visit_distribution"
POLICY_TARGET_KINDS = (
    POLICY_TARGET_KIND_BEHAVIOR,
    POLICY_TARGET_KIND_ORACLE_TEACHER_ACTION,
    POLICY_TARGET_KIND_ORACLE_SOFT_VISIT,
)
POLICY_TARGET_SOURCE_BEHAVIOR = "trainer_input_record.chosen_action_index"
BEHAVIOR_ACTION_AVAILABLE = "available"
BEHAVIOR_ACTION_UNAVAILABLE = "unavailable"
BEHAVIOR_ACTION_STATUSES = (
    BEHAVIOR_ACTION_AVAILABLE,
    BEHAVIOR_ACTION_UNAVAILABLE,
)
TRAINER_INPUT_DATASET_MIGRATIONS = (
    ArtifactMigration(
        source_version=1,
        target_version=2,
        migrate=lambda document: _migrate_trainer_input_v1_to_v2(document),
        losses=(
            "v1 omitted per-decision controller provenance",
            "v1 omitted legal action ids; migrated action identities are index-only",
            "v1 omitted source distribution metadata beyond seed",
        ),
    ),
    ArtifactMigration(
        source_version=2,
        target_version=3,
        migrate=lambda document: _migrate_trainer_input_v2_to_v3(document),
        losses=(
            "v2 fixed numeric features cannot reconstruct v2 structured tactical inputs",
            "v2 omitted tactical feature-schema and identity-vocabulary provenance",
        ),
    ),
    ArtifactMigration(
        source_version=3,
        target_version=4,
        migrate=lambda document: _migrate_trainer_input_v3_to_v4(document),
        losses=(PUBLIC_CONTEXT_LEGACY_LOSS,),
    ),
    ArtifactMigration(
        source_version=4,
        target_version=5,
        migrate=lambda document: _migrate_trainer_input_v4_to_v5(document),
        losses=(BATTLE_RESOURCE_OUTCOME_LEGACY_LOSS,),
    ),
    ArtifactMigration(
        source_version=5,
        target_version=TRAINER_INPUT_DATASET_FORMAT_VERSION,
        migrate=lambda document: _migrate_trainer_input_v5_to_v6(document),
        losses=(),
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
    structured_battle_outcome_status: str = "legacy_unavailable"
    structured_battle_outcome: dict[str, Any] = field(default_factory=dict)
    policy_target_kind: str = POLICY_TARGET_KIND_BEHAVIOR
    policy_target: list[float] = field(default_factory=list)
    policy_target_source: str = POLICY_TARGET_SOURCE_BEHAVIOR
    policy_target_action_index: int | None = None
    policy_target_action_identity: dict[str, Any] = field(default_factory=dict)
    behavior_action_status: str = BEHAVIOR_ACTION_AVAILABLE
    behavior_action: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Fill explicit v6 target fields for in-memory legacy constructors."""

        if not self.policy_target:
            object.__setattr__(self, "policy_target", _behavior_policy_target(self))
        if self.policy_target_action_index is None:
            object.__setattr__(
                self,
                "policy_target_action_index",
                _default_policy_target_action_index(self),
            )
        if not self.policy_target_action_identity:
            object.__setattr__(
                self,
                "policy_target_action_identity",
                _default_policy_target_action_identity(self),
            )
        if not self.behavior_action and (
            self.behavior_action_status == BEHAVIOR_ACTION_AVAILABLE
        ):
            object.__setattr__(self, "behavior_action", _behavior_action_dict(self))


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
    tactical_feature_schema_id: str = TACTICAL_FEATURE_SCHEMA_ID
    tactical_feature_schema_version: int = TACTICAL_FEATURE_SCHEMA_VERSION
    identity_vocabulary_version: str = IDENTITY_VOCABULARY_VERSION
    policy_target_schema_id: str = TRAINER_POLICY_TARGET_SCHEMA_ID
    policy_target_schema_version: int = TRAINER_POLICY_TARGET_SCHEMA_VERSION
    structured_battle_outcome_schema_id: str = BATTLE_RESOURCE_OUTCOME_SCHEMA_ID
    structured_battle_outcome_schema_version: int = (
        BATTLE_RESOURCE_OUTCOME_SCHEMA_VERSION
    )
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
    structured_outcome_status_counts: Counter[str] = field(default_factory=Counter)
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
        tactical_feature_schema_id=TACTICAL_FEATURE_SCHEMA_ID,
        tactical_feature_schema_version=TACTICAL_FEATURE_SCHEMA_VERSION,
        identity_vocabulary_version=IDENTITY_VOCABULARY_VERSION,
        policy_target_schema_id=TRAINER_POLICY_TARGET_SCHEMA_ID,
        policy_target_schema_version=TRAINER_POLICY_TARGET_SCHEMA_VERSION,
        structured_battle_outcome_schema_id=BATTLE_RESOURCE_OUTCOME_SCHEMA_ID,
        structured_battle_outcome_schema_version=BATTLE_RESOURCE_OUTCOME_SCHEMA_VERSION,
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
        structured_outcome_status_counts=Counter(
            record.structured_battle_outcome_status for record in dataset.records
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
    _append_counter(
        lines,
        "structured outcome statuses",
        report.structured_outcome_status_counts,
    )
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
        tactical_feature_schema_id=str(
            metadata.get("tactical_feature_schema_id", LEGACY_FEATURE_SCHEMA_ID)
        ),
        tactical_feature_schema_version=_int(
            metadata.get("tactical_feature_schema_version")
        ),
        identity_vocabulary_version=str(
            metadata.get("identity_vocabulary_version", "")
        ),
        policy_target_schema_id=str(
            metadata.get("policy_target_schema_id", TRAINER_POLICY_TARGET_SCHEMA_ID)
        ),
        policy_target_schema_version=_int(
            metadata.get(
                "policy_target_schema_version",
                TRAINER_POLICY_TARGET_SCHEMA_VERSION,
            )
        ),
        structured_battle_outcome_schema_id=str(
            metadata.get(
                "structured_battle_outcome_schema_id",
                BATTLE_RESOURCE_OUTCOME_SCHEMA_ID,
            )
        ),
        structured_battle_outcome_schema_version=_int(
            metadata.get(
                "structured_battle_outcome_schema_version",
                BATTLE_RESOURCE_OUTCOME_SCHEMA_VERSION,
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
        structured_battle_outcome_status=label.structured_battle_outcome_status,
        structured_battle_outcome=_json_safe_dict(label.structured_battle_outcome),
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
            "tactical_feature_schema_id": dataset.tactical_feature_schema_id,
            "tactical_feature_schema_version": dataset.tactical_feature_schema_version,
            "identity_vocabulary_version": dataset.identity_vocabulary_version,
            "policy_target_schema_id": dataset.policy_target_schema_id,
            "policy_target_schema_version": dataset.policy_target_schema_version,
            "structured_battle_outcome_schema_id": (
                dataset.structured_battle_outcome_schema_id
            ),
            "structured_battle_outcome_schema_version": (
                dataset.structured_battle_outcome_schema_version
            ),
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
    if dataset.tactical_feature_schema_id != TACTICAL_FEATURE_SCHEMA_ID:
        raise ValueError(
            "trainer input writer only emits tactical feature schema "
            f"{TACTICAL_FEATURE_SCHEMA_ID!r}, got "
            f"{dataset.tactical_feature_schema_id!r}"
        )
    if dataset.tactical_feature_schema_version != TACTICAL_FEATURE_SCHEMA_VERSION:
        raise ValueError(
            "trainer input writer only emits tactical feature schema version "
            f"{TACTICAL_FEATURE_SCHEMA_VERSION}, got "
            f"{dataset.tactical_feature_schema_version}"
        )
    if dataset.identity_vocabulary_version != IDENTITY_VOCABULARY_VERSION:
        raise ValueError(
            "trainer input writer only emits identity vocabulary version "
            f"{IDENTITY_VOCABULARY_VERSION!r}, got "
            f"{dataset.identity_vocabulary_version!r}"
        )
    if dataset.policy_target_schema_id != TRAINER_POLICY_TARGET_SCHEMA_ID:
        raise ValueError(
            "trainer input writer only emits policy target schema "
            f"{TRAINER_POLICY_TARGET_SCHEMA_ID!r}, got "
            f"{dataset.policy_target_schema_id!r}"
        )
    if dataset.policy_target_schema_version != TRAINER_POLICY_TARGET_SCHEMA_VERSION:
        raise ValueError(
            "trainer input writer only emits policy target schema version "
            f"{TRAINER_POLICY_TARGET_SCHEMA_VERSION}, got "
            f"{dataset.policy_target_schema_version}"
        )
    if dataset.structured_battle_outcome_schema_id != BATTLE_RESOURCE_OUTCOME_SCHEMA_ID:
        raise ValueError(
            "trainer input writer only emits structured battle outcome schema "
            f"{BATTLE_RESOURCE_OUTCOME_SCHEMA_ID!r}, got "
            f"{dataset.structured_battle_outcome_schema_id!r}"
        )
    if (
        dataset.structured_battle_outcome_schema_version
        != BATTLE_RESOURCE_OUTCOME_SCHEMA_VERSION
    ):
        raise ValueError(
            "trainer input writer only emits structured battle outcome schema "
            "version "
            f"{BATTLE_RESOURCE_OUTCOME_SCHEMA_VERSION}, got "
            f"{dataset.structured_battle_outcome_schema_version}"
        )
    for record in dataset.records:
        if record.record_schema_version != DECISION_RECORD_SCHEMA_VERSION:
            raise ValueError(
                "trainer input writer only emits current decision record schema "
                f"{DECISION_RECORD_SCHEMA_VERSION}, got "
                f"record {record.example_index} schema "
                f"{record.record_schema_version}"
            )
        if record.record_schema_version != dataset.decision_record_schema_version:
            raise ValueError(
                f"record {record.example_index} schema "
                f"{record.record_schema_version} does not match dataset schema "
                f"{dataset.decision_record_schema_version}"
            )
        if record.feature_schema_id != dataset.tactical_feature_schema_id:
            raise ValueError(
                f"record {record.example_index} feature schema "
                f"{record.feature_schema_id!r} does not match dataset schema "
                f"{dataset.tactical_feature_schema_id!r}"
            )
        identity_problems = decision_record_identity_problems(
            record,
            label=f"record {record.example_index}",
        )
        if identity_problems:
            raise ValueError(
                "trainer input writer requires complete current action identities: "
                + "; ".join(identity_problems)
            )
        record_problems = decision_record_problems(
            record,
            label=f"record {record.example_index}",
        )
        if record_problems:
            raise ValueError(
                "trainer input writer requires complete current tactical inputs: "
                + "; ".join(record_problems)
            )
        outcome_problems = battle_resource_outcome_problems(
            record.structured_battle_outcome_status,
            record.structured_battle_outcome,
            label=f"record {record.example_index} structured battle outcome",
            require_available=(
                record.structured_battle_outcome_status
                == BATTLE_RESOURCE_OUTCOME_AVAILABLE
            ),
        )
        if outcome_problems:
            raise ValueError(
                "trainer input writer requires valid structured battle outcomes: "
                + "; ".join(outcome_problems)
            )
        target_problems = _policy_target_problems(record)
        if target_problems:
            raise ValueError(
                "trainer input writer requires valid policy targets: "
                + "; ".join(target_problems)
            )


def _migrate_trainer_input_v1_to_v2(
    document: ArtifactDocument,
) -> ArtifactDocument:
    metadata = dict(document.metadata)
    metadata["format_version"] = 2
    metadata["decision_record_schema_version"] = 1
    metadata.setdefault("generation_metadata", {})

    migrated_records: list[dict[str, Any]] = []
    for raw_record in document.records:
        record = dict(raw_record)
        legal_action_kinds = [
            str(kind) for kind in _list(record.get("legal_action_kinds"))
        ]
        identities = legacy_index_action_identities(legal_action_kinds)
        chosen_index = _int(record.get("chosen_action_index"))
        record["record_schema_version"] = 1
        record["legal_action_identities"] = identities
        record["chosen_action_id"] = None
        record["chosen_action_identity"] = (
            identities[chosen_index] if 0 <= chosen_index < len(identities) else {}
        )
        record["controller_provenance"] = {}
        record["source_metadata"] = _legacy_source_metadata(record)
        migrated_records.append(record)

    return ArtifactDocument(metadata=metadata, records=migrated_records)


def _migrate_trainer_input_v2_to_v3(
    document: ArtifactDocument,
) -> ArtifactDocument:
    """Add explicit v2 tactical contract placeholders to old numeric rows."""

    metadata = dict(document.metadata)
    metadata["format_version"] = 3
    metadata["decision_record_schema_version"] = DECISION_RECORD_SCHEMA_VERSION
    metadata["tactical_feature_schema_id"] = LEGACY_FEATURE_SCHEMA_ID
    metadata["tactical_feature_schema_version"] = 0
    metadata["identity_vocabulary_version"] = ""
    migrated_records: list[dict[str, Any]] = []
    for raw_record in document.records:
        record = dict(raw_record)
        record["record_schema_version"] = DECISION_RECORD_SCHEMA_VERSION
        record["feature_schema_id"] = LEGACY_FEATURE_SCHEMA_ID
        record["tactical_state"] = {}
        record["tactical_legal_actions"] = []
        migrated_records.append(record)
    return ArtifactDocument(metadata=metadata, records=migrated_records)


def _migrate_trainer_input_v3_to_v4(
    document: ArtifactDocument,
) -> ArtifactDocument:
    """Add explicit public-context legacy-loss markers to old rows."""

    metadata = dict(document.metadata)
    metadata["format_version"] = 4
    metadata["decision_record_schema_version"] = DECISION_RECORD_SCHEMA_VERSION
    migrated_records: list[dict[str, Any]] = []
    for raw_record in document.records:
        record = dict(raw_record)
        record["record_schema_version"] = DECISION_RECORD_SCHEMA_VERSION
        record["public_context_status"] = PUBLIC_CONTEXT_LEGACY_UNAVAILABLE
        record["public_run_context"] = {}
        migrated_records.append(record)
    return ArtifactDocument(metadata=metadata, records=migrated_records)


def _migrate_trainer_input_v4_to_v5(
    document: ArtifactDocument,
) -> ArtifactDocument:
    """Add explicit structured battle outcome legacy-loss markers."""

    metadata = dict(document.metadata)
    metadata["format_version"] = 5
    metadata["structured_battle_outcome_schema_id"] = BATTLE_RESOURCE_OUTCOME_SCHEMA_ID
    metadata["structured_battle_outcome_schema_version"] = (
        BATTLE_RESOURCE_OUTCOME_SCHEMA_VERSION
    )
    status, payload = legacy_unavailable_battle_resource_outcome()
    migrated_records: list[dict[str, Any]] = []
    for raw_record in document.records:
        record = dict(raw_record)
        record["structured_battle_outcome_status"] = status
        record["structured_battle_outcome"] = payload
        migrated_records.append(record)
    return ArtifactDocument(metadata=metadata, records=migrated_records)


def _migrate_trainer_input_v5_to_v6(
    document: ArtifactDocument,
) -> ArtifactDocument:
    """Make legacy behavior-action policy targets explicit."""

    metadata = dict(document.metadata)
    metadata["format_version"] = TRAINER_INPUT_DATASET_FORMAT_VERSION
    metadata["policy_target_schema_id"] = TRAINER_POLICY_TARGET_SCHEMA_ID
    metadata["policy_target_schema_version"] = TRAINER_POLICY_TARGET_SCHEMA_VERSION
    migrated_records: list[dict[str, Any]] = []
    for raw_record in document.records:
        record = dict(raw_record)
        target, action_index, action_identity = _behavior_policy_target_from_raw(record)
        record["policy_target_kind"] = POLICY_TARGET_KIND_BEHAVIOR
        record["policy_target"] = target
        record["policy_target_source"] = POLICY_TARGET_SOURCE_BEHAVIOR
        record["policy_target_action_index"] = action_index
        record["policy_target_action_identity"] = action_identity
        record["behavior_action_status"] = BEHAVIOR_ACTION_AVAILABLE
        record["behavior_action"] = {
            "source": POLICY_TARGET_SOURCE_BEHAVIOR,
            "legal_action_index": action_index,
            "action_identity": action_identity,
            "action_kind": str(record.get("chosen_action_kind", "")),
            "action_id": record.get("chosen_action_id"),
        }
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
        "feature_schema_id": record.feature_schema_id,
        "tactical_state": record.tactical_state,
        "tactical_legal_actions": record.tactical_legal_actions,
        "public_context_status": record.public_context_status,
        "public_run_context": record.public_run_context,
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
        "structured_battle_outcome_status": record.structured_battle_outcome_status,
        "structured_battle_outcome": record.structured_battle_outcome,
        "policy_target_kind": record.policy_target_kind,
        "policy_target": record.policy_target,
        "policy_target_source": record.policy_target_source,
        "policy_target_action_index": record.policy_target_action_index,
        "policy_target_action_identity": record.policy_target_action_identity,
        "behavior_action_status": record.behavior_action_status,
        "behavior_action": record.behavior_action,
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
        feature_schema_id=str(raw.get("feature_schema_id", LEGACY_FEATURE_SCHEMA_ID)),
        tactical_state=_dict(raw.get("tactical_state")),
        tactical_legal_actions=[
            _dict(action) for action in _list(raw.get("tactical_legal_actions"))
        ],
        public_context_status=str(
            raw.get("public_context_status", PUBLIC_CONTEXT_LEGACY_UNAVAILABLE)
        ),
        public_run_context=_dict(raw.get("public_run_context")),
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
        structured_battle_outcome_status=str(
            raw.get(
                "structured_battle_outcome_status",
                "legacy_unavailable",
            )
        ),
        structured_battle_outcome=_dict(raw.get("structured_battle_outcome")),
        policy_target_kind=str(
            raw.get("policy_target_kind", POLICY_TARGET_KIND_BEHAVIOR)
        ),
        policy_target=_float_list(raw.get("policy_target")),
        policy_target_source=str(
            raw.get("policy_target_source", POLICY_TARGET_SOURCE_BEHAVIOR)
        ),
        policy_target_action_index=_optional_int_value(
            raw.get("policy_target_action_index")
        ),
        policy_target_action_identity=_dict(raw.get("policy_target_action_identity")),
        behavior_action_status=str(
            raw.get("behavior_action_status", BEHAVIOR_ACTION_AVAILABLE)
        ),
        behavior_action=_dict(raw.get("behavior_action")),
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
    if dataset.tactical_feature_schema_id != TACTICAL_FEATURE_SCHEMA_ID:
        problems.append(
            "unsupported tactical feature schema: "
            f"{dataset.tactical_feature_schema_id!r}"
        )
    if dataset.tactical_feature_schema_version != TACTICAL_FEATURE_SCHEMA_VERSION:
        problems.append(
            "unsupported tactical feature schema version: "
            f"{dataset.tactical_feature_schema_version}"
        )
    if dataset.identity_vocabulary_version != IDENTITY_VOCABULARY_VERSION:
        problems.append(
            "unsupported identity vocabulary version: "
            f"{dataset.identity_vocabulary_version!r}"
        )
    if dataset.policy_target_schema_id != TRAINER_POLICY_TARGET_SCHEMA_ID:
        problems.append(
            f"unsupported policy target schema: {dataset.policy_target_schema_id!r}"
        )
    if dataset.policy_target_schema_version != TRAINER_POLICY_TARGET_SCHEMA_VERSION:
        problems.append(
            "unsupported policy target schema version: "
            f"{dataset.policy_target_schema_version}"
        )
    if dataset.structured_battle_outcome_schema_id != BATTLE_RESOURCE_OUTCOME_SCHEMA_ID:
        problems.append(
            "unsupported structured battle outcome schema: "
            f"{dataset.structured_battle_outcome_schema_id!r}"
        )
    if (
        dataset.structured_battle_outcome_schema_version
        != BATTLE_RESOURCE_OUTCOME_SCHEMA_VERSION
    ):
        problems.append(
            "unsupported structured battle outcome schema version: "
            f"{dataset.structured_battle_outcome_schema_version}"
        )
    for record in dataset.records:
        if record.record_schema_version != dataset.decision_record_schema_version:
            problems.append(
                f"record {record.example_index}: record schema "
                f"{record.record_schema_version} does not match dataset schema "
                f"{dataset.decision_record_schema_version}"
            )
        if record.feature_schema_id != dataset.tactical_feature_schema_id:
            problems.append(
                f"record {record.example_index}: tactical feature schema "
                f"{record.feature_schema_id!r} does not match dataset schema "
                f"{dataset.tactical_feature_schema_id!r}"
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
        problems.extend(
            battle_resource_outcome_problems(
                record.structured_battle_outcome_status,
                record.structured_battle_outcome,
                label=f"record {record.example_index} structured battle outcome",
                require_available=(
                    record.structured_battle_outcome_status
                    == BATTLE_RESOURCE_OUTCOME_AVAILABLE
                ),
            )
        )
        problems.extend(_policy_target_problems(record))
    return problems


def _behavior_policy_target(record: TrainerInputRecord) -> list[float]:
    target = [0.0 for _ in record.legal_action_features]
    if 0 <= record.chosen_action_index < len(target):
        target[record.chosen_action_index] = 1.0
    return target


def _behavior_policy_target_from_raw(
    record: Mapping[str, Any],
) -> tuple[list[float], int | None, dict[str, Any]]:
    legal_count = len(_list(record.get("legal_action_features")))
    target = [0.0 for _ in range(legal_count)]
    action_index = _optional_int_value(record.get("chosen_action_index"))
    if action_index is not None and 0 <= action_index < legal_count:
        target[action_index] = 1.0
    identities = [
        _dict(identity) for identity in _list(record.get("legal_action_identities"))
    ]
    action_identity = (
        identities[action_index]
        if action_index is not None and 0 <= action_index < len(identities)
        else {}
    )
    return target, action_index, action_identity


def _default_policy_target_action_index(record: TrainerInputRecord) -> int | None:
    if record.policy_target_kind == POLICY_TARGET_KIND_BEHAVIOR:
        return record.chosen_action_index
    if not record.policy_target:
        return None
    return max(range(len(record.policy_target)), key=record.policy_target.__getitem__)


def _default_policy_target_action_identity(
    record: TrainerInputRecord,
) -> dict[str, Any]:
    action_index = (
        record.chosen_action_index
        if record.policy_target_action_index is None
        else record.policy_target_action_index
    )
    if 0 <= action_index < len(record.legal_action_identities):
        return dict(record.legal_action_identities[action_index])
    return {}


def _behavior_action_dict(record: TrainerInputRecord) -> dict[str, Any]:
    return {
        "source": POLICY_TARGET_SOURCE_BEHAVIOR,
        "legal_action_index": record.chosen_action_index,
        "action_identity": dict(record.chosen_action_identity),
        "action_kind": record.chosen_action_kind,
        "action_id": record.chosen_action_id,
    }


def _policy_target_problems(record: TrainerInputRecord) -> list[str]:
    problems: list[str] = []
    label = f"record {record.example_index}"
    legal_count = len(record.legal_action_features)
    if record.policy_target_kind not in POLICY_TARGET_KINDS:
        problems.append(
            f"{label}: unsupported policy target kind {record.policy_target_kind!r}"
        )
    if len(record.policy_target) != legal_count:
        problems.append(
            f"{label}: policy target length {len(record.policy_target)} does not "
            f"match {legal_count} legal actions"
        )
        return problems
    for index, value in enumerate(record.policy_target):
        if not math.isfinite(value):
            problems.append(f"{label}: policy target {index} is not finite")
        elif value < 0.0:
            problems.append(f"{label}: policy target {index} is negative")
    eligible_sum = sum(
        record.policy_target[index]
        for index in record.eligible_action_indices
        if 0 <= index < len(record.policy_target)
    )
    if legal_count and eligible_sum <= 0.0:
        problems.append(f"{label}: policy target has no positive eligible weight")
    if not record.policy_target_source:
        problems.append(f"{label}: policy target source is missing")
    if record.behavior_action_status not in BEHAVIOR_ACTION_STATUSES:
        problems.append(
            f"{label}: unsupported behavior action status "
            f"{record.behavior_action_status!r}"
        )
    if (
        record.behavior_action_status == BEHAVIOR_ACTION_AVAILABLE
        and not record.behavior_action
    ):
        problems.append(f"{label}: behavior action is marked available but missing")
    if record.policy_target_kind in {
        POLICY_TARGET_KIND_BEHAVIOR,
        POLICY_TARGET_KIND_ORACLE_TEACHER_ACTION,
    }:
        positive_indices = [
            index for index, value in enumerate(record.policy_target) if value > 0.0
        ]
        if len(positive_indices) != 1:
            problems.append(
                f"{label}: one-hot policy target has {len(positive_indices)} "
                "positive entries"
            )
        elif not math.isclose(record.policy_target[positive_indices[0]], 1.0):
            problems.append(f"{label}: one-hot policy target value is not 1.0")
        if record.policy_target_action_index != (
            positive_indices[0] if len(positive_indices) == 1 else None
        ):
            problems.append(
                f"{label}: policy target action index does not match target"
            )
    _append_policy_target_identity_problems(record, label, problems)
    return problems


def _append_policy_target_identity_problems(
    record: TrainerInputRecord,
    label: str,
    problems: list[str],
) -> None:
    action_index = record.policy_target_action_index
    if action_index is None:
        if record.policy_target_kind != POLICY_TARGET_KIND_ORACLE_SOFT_VISIT:
            problems.append(f"{label}: policy target action index is missing")
        return
    if action_index < 0 or action_index >= len(record.legal_action_identities):
        problems.append(f"{label}: policy target action index outside legal actions")
        return
    if not record.policy_target_action_identity:
        problems.append(f"{label}: policy target action identity is missing")
        return
    try:
        expected = record.legal_action_identities[action_index]
        from sts_combat_rl.sim.decision_record import action_identity_from_dict

        observed = action_identity_from_dict(record.policy_target_action_identity)
        expected_parsed = action_identity_from_dict(expected)
    except ValueError as exc:
        problems.append(f"{label}: policy target action identity is invalid: {exc}")
        return
    if observed.stable_id != expected_parsed.stable_id:
        problems.append(f"{label}: policy target action identity does not match index")


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
