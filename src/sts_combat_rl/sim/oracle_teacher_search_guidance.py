"""Bridge Oracle teacher scale-up artifacts into explicit trainer input.

The bridge is deliberately narrow: it converts one T023 budget artifact into
T009-compatible public feature rows with explicit Oracle-derived policy
targets. It does not implement a controller or claim model strength.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field, replace
import json
import math
from typing import Any, TextIO

from sts_combat_rl.sim.action_space import ActionSpaceConfig
from sts_combat_rl.sim.battle_start_pool import (
    BattleStartCheckpointRecord,
    NaturalBattleStartPool,
    restore_battle_start_record,
)
from sts_combat_rl.sim.contract import CheckpointingSimulatorAdapter
from sts_combat_rl.sim.controlled_run import build_decision_context
from sts_combat_rl.sim.decision_record import (
    action_identity_dicts_for_actions,
    action_identity_from_dict,
)
from sts_combat_rl.sim.features import (
    IDENTITY_VOCABULARY_VERSION,
    TACTICAL_FEATURE_SCHEMA_ID,
    TACTICAL_FEATURE_SCHEMA_VERSION,
)
from sts_combat_rl.sim.oracle_teacher import OracleTeacherDataset, OracleTeacherRow
from sts_combat_rl.sim.oracle_teacher_scaleup import (
    ORACLE_TEACHER_SCALEUP_MANIFEST_FORMAT_VERSION,
    ORACLE_TEACHER_SCALEUP_MANIFEST_SCHEMA_ID,
)
from sts_combat_rl.sim.public_context_artifacts import (
    PUBLIC_CONTEXT_AVAILABLE,
    PUBLIC_CONTEXT_LEGACY_UNAVAILABLE,
    sanitize_public_context_artifact,
)
from sts_combat_rl.sim.resource_outcome import (
    BATTLE_RESOURCE_OUTCOME_SCHEMA_ID,
    BATTLE_RESOURCE_OUTCOME_SCHEMA_VERSION,
)
from sts_combat_rl.sim.trainer_input import (
    BEHAVIOR_ACTION_AVAILABLE,
    BEHAVIOR_ACTION_UNAVAILABLE,
    POLICY_TARGET_KIND_ORACLE_SOFT_VISIT,
    POLICY_TARGET_KIND_ORACLE_TEACHER_ACTION,
    TRAINER_INPUT_DATASET_FORMAT_VERSION,
    TRAINER_POLICY_TARGET_SCHEMA_ID,
    TRAINER_POLICY_TARGET_SCHEMA_VERSION,
    TrainerInputDataset,
    TrainerInputRecord,
)


ORACLE_TEACHER_SEARCH_GUIDANCE_BRIDGE_REPORT_SCHEMA_ID = (
    "oracle-teacher-search-guidance-bridge-report-v1"
)
ORACLE_TEACHER_SEARCH_GUIDANCE_BRIDGE_REPORT_FORMAT_VERSION = 1
CLI_TARGET_TEACHER_ACTION_ONE_HOT = "teacher_action_one_hot"
CLI_TARGET_SOFT_VISIT_DISTRIBUTION = "soft_visit_distribution"
ORACLE_TEACHER_SEARCH_GUIDANCE_TARGETS = (
    CLI_TARGET_TEACHER_ACTION_ONE_HOT,
    CLI_TARGET_SOFT_VISIT_DISTRIBUTION,
)
ORACLE_TEACHER_SEARCH_GUIDANCE_STABILITY_FILTERS = ("none",)
POLICY_TARGET_SOURCE_ORACLE_TEACHER_ACTION = "oracle_teacher_row.teacher_action"
POLICY_TARGET_SOURCE_ORACLE_SOFT_VISIT = "oracle_teacher_row.soft_visit_target"
TERMINAL_STEP_REWARD_ALLOCATION = "terminal_step"
EVIDENCE_BOUNDARY = {
    "information_regime": "full_simulator_state_oracle_like",
    "not_normal_information": True,
    "not_live_game_evidence": True,
    "not_broad_training_evidence": True,
    "not_controller_strength_evidence": True,
}


@dataclass(frozen=True)
class OracleTeacherSearchGuidanceBridgeReport:
    """Machine-readable report for one T024 bridge conversion."""

    selected_budget: int
    requested_target: str
    policy_target_kind: str
    policy_target_source: str
    stability_filter: str
    t023_manifest_identity: dict[str, Any]
    selected_teacher_artifact_identity: dict[str, Any]
    selected_t022_report_identity: dict[str, Any]
    source_pool_identity: dict[str, Any]
    trainer_artifact_identity: dict[str, Any] = field(default_factory=dict)
    checkpoint_identity: dict[str, Any] = field(default_factory=dict)
    teacher_row_count: int = 0
    emitted_trainer_row_count: int = 0
    restore_counts: dict[str, int] = field(default_factory=dict)
    skipped_row_counts: dict[str, int] = field(default_factory=dict)
    policy_target_coverage: dict[str, Any] = field(default_factory=dict)
    behavior_action_availability: dict[str, int] = field(default_factory=dict)
    structured_outcome_availability: dict[str, int] = field(default_factory=dict)
    public_context_availability: dict[str, int] = field(default_factory=dict)
    information_regime_summary: dict[str, Any] = field(default_factory=dict)
    training_gate_override: str = "none"
    broad_training_gate_status: dict[str, Any] = field(default_factory=dict)
    raw_diagnostic_metrics: dict[str, Any] = field(default_factory=dict)
    warnings: tuple[str, ...] = ()
    problems: tuple[str, ...] = ()
    schema_id: str = ORACLE_TEACHER_SEARCH_GUIDANCE_BRIDGE_REPORT_SCHEMA_ID
    format_version: int = ORACLE_TEACHER_SEARCH_GUIDANCE_BRIDGE_REPORT_FORMAT_VERSION

    @property
    def command_passed(self) -> bool:
        return self.emitted_trainer_row_count > 0 and not self.problems

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "format_version": self.format_version,
            "command_passed": self.command_passed,
            "selected_budget": self.selected_budget,
            "requested_target": self.requested_target,
            "policy_target_kind": self.policy_target_kind,
            "policy_target_source": self.policy_target_source,
            "stability_filter": self.stability_filter,
            "t023_manifest_identity": _json_safe_mapping(self.t023_manifest_identity),
            "selected_teacher_artifact_identity": _json_safe_mapping(
                self.selected_teacher_artifact_identity
            ),
            "selected_t022_report_identity": _json_safe_mapping(
                self.selected_t022_report_identity
            ),
            "source_pool_identity": _json_safe_mapping(self.source_pool_identity),
            "trainer_artifact_identity": _json_safe_mapping(
                self.trainer_artifact_identity
            ),
            "checkpoint_identity": _json_safe_mapping(self.checkpoint_identity),
            "teacher_row_count": self.teacher_row_count,
            "emitted_trainer_row_count": self.emitted_trainer_row_count,
            "restore_counts": _counter_dict(self.restore_counts),
            "skipped_row_counts": _counter_dict(self.skipped_row_counts),
            "policy_target_coverage": _json_safe_mapping(self.policy_target_coverage),
            "behavior_action_availability": _counter_dict(
                self.behavior_action_availability
            ),
            "structured_outcome_availability": _counter_dict(
                self.structured_outcome_availability
            ),
            "public_context_availability": _counter_dict(
                self.public_context_availability
            ),
            "information_regime_summary": _json_safe_mapping(
                self.information_regime_summary
            ),
            "training_gate_override": self.training_gate_override,
            "broad_training_gate_status": _json_safe_mapping(
                self.broad_training_gate_status
            ),
            "raw_diagnostic_metrics": _json_safe_mapping(self.raw_diagnostic_metrics),
            "evidence_boundary": dict(EVIDENCE_BOUNDARY),
            "warnings": list(self.warnings),
            "problems": list(self.problems),
        }


def load_oracle_teacher_scaleup_manifest_json(stream: TextIO) -> dict[str, Any]:
    """Load the current T023 manifest as a strict JSON object."""

    raw = json.load(stream)
    if not isinstance(raw, dict):
        raise ValueError("Oracle teacher scale-up manifest must be a JSON object")
    if raw.get("schema_id") != ORACLE_TEACHER_SCALEUP_MANIFEST_SCHEMA_ID:
        raise ValueError("unsupported Oracle teacher scale-up manifest schema")
    if raw.get("format_version") != ORACLE_TEACHER_SCALEUP_MANIFEST_FORMAT_VERSION:
        raise ValueError("unsupported Oracle teacher scale-up manifest format version")
    return raw


def dump_oracle_teacher_search_guidance_bridge_report_json(
    report: OracleTeacherSearchGuidanceBridgeReport,
    stream: TextIO,
) -> None:
    """Write a deterministic bridge report JSON document."""

    json.dump(report.to_dict(), stream, indent=2, sort_keys=True, allow_nan=False)
    stream.write("\n")


def build_oracle_teacher_search_guidance_dataset(
    *,
    adapter_factory: Callable[[], CheckpointingSimulatorAdapter],
    manifest: Mapping[str, Any],
    teacher_dataset: OracleTeacherDataset,
    source_pool: NaturalBattleStartPool,
    selected_budget: int,
    target: str,
    stability_filter: str,
    manifest_identity: Mapping[str, Any],
    teacher_artifact_identity: Mapping[str, Any],
    t022_report_identity: Mapping[str, Any],
    source_pool_identity: Mapping[str, Any],
) -> tuple[TrainerInputDataset, OracleTeacherSearchGuidanceBridgeReport]:
    """Convert one selected T023 budget into explicit trainer input records."""

    policy_target_kind, policy_target_source = _policy_target_config(target)
    problems = _manifest_identity_problems(
        manifest,
        selected_budget=selected_budget,
        teacher_artifact_identity=teacher_artifact_identity,
        t022_report_identity=t022_report_identity,
        source_pool_identity=source_pool_identity,
    )
    if stability_filter not in ORACLE_TEACHER_SEARCH_GUIDANCE_STABILITY_FILTERS:
        problems.append(f"unsupported stability filter {stability_filter!r}")

    source_by_checkpoint = _source_records_by_checkpoint(source_pool)
    action_space = _action_space_from_mapping(teacher_dataset.action_space_config)
    records: list[TrainerInputRecord] = []
    skipped = Counter()
    restore_counts = Counter()
    public_context_counts = Counter()
    outcome_counts = Counter()
    target_positive_counts = Counter()
    behavior_counts = Counter()
    conversion_warnings: list[str] = []

    for row in teacher_dataset.records:
        source = source_by_checkpoint.get(row.source_checkpoint_id)
        if source is None:
            skipped["missing_source_pool_record"] += 1
            problems.append(
                f"teacher row {row.row_index}: source checkpoint "
                f"{row.source_checkpoint_id!r} is not in source pool"
            )
            continue
        if source.record_index != row.source_pool_record_index:
            skipped["source_pool_record_index_mismatch"] += 1
            problems.append(
                f"teacher row {row.row_index}: source pool record index "
                f"{row.source_pool_record_index} does not match pool record "
                f"{source.record_index}"
            )
            continue
        try:
            record, method = _trainer_record_from_teacher_row(
                adapter_factory=adapter_factory,
                source=source,
                row=row,
                target=target,
                policy_target_kind=policy_target_kind,
                policy_target_source=policy_target_source,
                action_space=action_space,
                example_index=len(records),
                teacher_artifact_identity=teacher_artifact_identity,
                selected_budget=selected_budget,
            )
        except (RuntimeError, ValueError) as exc:
            skipped["conversion_error"] += 1
            problems.append(f"teacher row {row.row_index}: {exc}")
            continue
        records.append(record)
        restore_counts[method] += 1
        public_context_counts[record.public_context_status] += 1
        outcome_counts[record.structured_battle_outcome_status] += 1
        target_positive_counts[str(_positive_target_count(record.policy_target))] += 1
        behavior_counts[record.behavior_action_status] += 1

    if not records:
        problems.append("no trainer rows were emitted")
    if any(
        record.public_context_status != PUBLIC_CONTEXT_AVAILABLE for record in records
    ):
        conversion_warnings.append(
            "one or more emitted rows have unavailable public context"
        )
    if any(
        record.structured_battle_outcome_status != "available" for record in records
    ):
        conversion_warnings.append(
            "one or more emitted rows have unavailable structured battle outcomes"
        )

    dataset = TrainerInputDataset(
        format_version=TRAINER_INPUT_DATASET_FORMAT_VERSION,
        reward_allocation=TERMINAL_STEP_REWARD_ALLOCATION,
        source_rollout_count=len(
            {record.source_run_id for record in source_pool.records}
        ),
        segment_count=len(records),
        snapshot_feature_size=len(records[0].snapshot_features) if records else None,
        action_feature_size=(
            len(records[0].legal_action_features[0])
            if records and records[0].legal_action_features
            else None
        ),
        tactical_feature_schema_id=TACTICAL_FEATURE_SCHEMA_ID,
        tactical_feature_schema_version=TACTICAL_FEATURE_SCHEMA_VERSION,
        identity_vocabulary_version=IDENTITY_VOCABULARY_VERSION,
        policy_target_schema_id=TRAINER_POLICY_TARGET_SCHEMA_ID,
        policy_target_schema_version=TRAINER_POLICY_TARGET_SCHEMA_VERSION,
        structured_battle_outcome_schema_id=BATTLE_RESOURCE_OUTCOME_SCHEMA_ID,
        structured_battle_outcome_schema_version=BATTLE_RESOURCE_OUTCOME_SCHEMA_VERSION,
        generation_metadata={
            "task_id": "T024",
            "workflow": "oracle_teacher_search_guidance_bridge",
            "selected_budget": selected_budget,
            "requested_target": target,
            "policy_target_kind": policy_target_kind,
            "policy_target_source": policy_target_source,
            "stability_filter": stability_filter,
            "evidence_boundary": dict(EVIDENCE_BOUNDARY),
            "t023_manifest_identity": _json_safe_mapping(manifest_identity),
            "teacher_artifact_identity": _json_safe_mapping(teacher_artifact_identity),
            "t022_report_identity": _json_safe_mapping(t022_report_identity),
            "source_pool_identity": _json_safe_mapping(source_pool_identity),
        },
        records=records,
        problems=[],
    )
    report = OracleTeacherSearchGuidanceBridgeReport(
        selected_budget=selected_budget,
        requested_target=target,
        policy_target_kind=policy_target_kind,
        policy_target_source=policy_target_source,
        stability_filter=stability_filter,
        t023_manifest_identity=dict(manifest_identity),
        selected_teacher_artifact_identity=dict(teacher_artifact_identity),
        selected_t022_report_identity=dict(t022_report_identity),
        source_pool_identity=dict(source_pool_identity),
        teacher_row_count=len(teacher_dataset.records),
        emitted_trainer_row_count=len(records),
        restore_counts=dict(sorted(restore_counts.items())),
        skipped_row_counts=dict(sorted(skipped.items())),
        policy_target_coverage={
            "target_kind": policy_target_kind,
            "target_source": policy_target_source,
            "record_count": len(records),
            "positive_entry_counts": _counter_dict(target_positive_counts),
        },
        behavior_action_availability=dict(sorted(behavior_counts.items())),
        structured_outcome_availability=dict(sorted(outcome_counts.items())),
        public_context_availability=dict(sorted(public_context_counts.items())),
        information_regime_summary=_information_regime_summary(
            teacher_dataset,
            records,
        ),
        warnings=tuple(dict.fromkeys(conversion_warnings)),
        problems=tuple(dict.fromkeys(problems)),
    )
    return dataset, report


def attach_trainer_artifact_identity(
    report: OracleTeacherSearchGuidanceBridgeReport,
    identity: Mapping[str, Any],
) -> OracleTeacherSearchGuidanceBridgeReport:
    return replace(report, trainer_artifact_identity=dict(identity))


def attach_checkpoint_summary(
    report: OracleTeacherSearchGuidanceBridgeReport,
    *,
    checkpoint_identity: Mapping[str, Any],
    training_gate_override: str,
    broad_training_gate_status: Mapping[str, Any],
    raw_diagnostic_metrics: Mapping[str, Any],
    problems: Sequence[str] = (),
) -> OracleTeacherSearchGuidanceBridgeReport:
    return replace(
        report,
        checkpoint_identity=dict(checkpoint_identity),
        training_gate_override=training_gate_override,
        broad_training_gate_status=dict(broad_training_gate_status),
        raw_diagnostic_metrics=dict(raw_diagnostic_metrics),
        problems=tuple(dict.fromkeys([*report.problems, *problems])),
    )


def format_oracle_teacher_search_guidance_bridge_report(
    report: OracleTeacherSearchGuidanceBridgeReport,
) -> str:
    """Format deterministic stderr evidence for the bridge command."""

    lines = [
        "Oracle teacher search-guidance bridge",
        f"schema: {report.schema_id} v{report.format_version}",
        f"command passed: {_yes_no(report.command_passed)}",
        (
            "evidence boundary: full_simulator_state_oracle_like teacher "
            "supervision; not normal-information, live-game, broad-training, "
            "or controller-strength evidence"
        ),
        f"selected budget: {report.selected_budget}",
        f"requested target: {report.requested_target}",
        f"policy target kind: {report.policy_target_kind}",
        f"policy target source: {report.policy_target_source}",
        f"stability filter: {report.stability_filter}",
        f"teacher rows consumed: {report.teacher_row_count}",
        f"trainer rows emitted: {report.emitted_trainer_row_count}",
        f"manifest sha256: {report.t023_manifest_identity.get('sha256', '(missing)')}",
        (
            "teacher artifact sha256: "
            f"{report.selected_teacher_artifact_identity.get('sha256', '(missing)')}"
        ),
        (
            "T022 report sha256: "
            f"{report.selected_t022_report_identity.get('sha256', '(missing)')}"
        ),
        (
            "source pool sha256: "
            f"{report.source_pool_identity.get('sha256', '(missing)')}"
        ),
        (
            "trainer artifact sha256: "
            f"{report.trainer_artifact_identity.get('sha256', '(missing)')}"
        ),
        (f"checkpoint sha256: {report.checkpoint_identity.get('sha256', '(none)')}"),
    ]
    _append_counter(lines, "restore counts", report.restore_counts)
    _append_counter(lines, "skipped rows", report.skipped_row_counts)
    _append_counter(
        lines,
        "structured outcome statuses",
        report.structured_outcome_availability,
    )
    _append_counter(
        lines,
        "behavior action statuses",
        report.behavior_action_availability,
    )
    _append_counter(
        lines,
        "public-context statuses",
        report.public_context_availability,
    )
    lines.extend(
        [
            "policy target coverage:",
            f"  records: {report.policy_target_coverage.get('record_count', 0)}",
            "  positive entry counts:",
        ]
    )
    _append_counter(
        lines,
        "  counts",
        report.policy_target_coverage.get("positive_entry_counts", {}),
    )
    lines.append("information regimes:")
    for key in sorted(report.information_regime_summary):
        lines.append(f"  {key}: {report.information_regime_summary[key]}")
    lines.append("broad-training gate:")
    if report.broad_training_gate_status:
        for key in sorted(report.broad_training_gate_status):
            lines.append(f"  {key}: {report.broad_training_gate_status[key]}")
    else:
        lines.append("  (not run)")
    lines.append("raw diagnostics:")
    if report.raw_diagnostic_metrics:
        for key in sorted(report.raw_diagnostic_metrics):
            lines.append(f"  {key}: {report.raw_diagnostic_metrics[key]}")
    else:
        lines.append("  (not run)")
    lines.append("warnings:")
    if report.warnings:
        lines.extend(f"  - {warning}" for warning in report.warnings)
    else:
        lines.append("  (none)")
    lines.append("problems:")
    if report.problems:
        lines.extend(f"  - {problem}" for problem in report.problems)
    else:
        lines.append("  (none)")
    return "\n".join(lines)


def _trainer_record_from_teacher_row(
    *,
    adapter_factory: Callable[[], CheckpointingSimulatorAdapter],
    source: BattleStartCheckpointRecord,
    row: OracleTeacherRow,
    target: str,
    policy_target_kind: str,
    policy_target_source: str,
    action_space: ActionSpaceConfig,
    example_index: int,
    teacher_artifact_identity: Mapping[str, Any],
    selected_budget: int,
) -> tuple[TrainerInputRecord, str]:
    adapter = adapter_factory()
    snapshot, restoration_method = restore_battle_start_record(adapter, source)
    actions = list(adapter.legal_actions(snapshot))
    current_identities = action_identity_dicts_for_actions(actions)
    _require_teacher_legal_identities(row, current_identities)
    public_context = _public_context_for_source(source)
    context = build_decision_context(
        snapshot.raw,
        actions,
        action_space,
        public_run_context=public_context,
    )
    (
        policy_target,
        policy_target_action_index,
        policy_target_action_identity,
    ) = _policy_target_from_teacher_row(row, target, current_identities)
    behavior_status, behavior_action, chosen_index = _behavior_action_for_row(
        row,
        current_identities,
        fallback_index=policy_target_action_index,
    )
    selected_action = actions[chosen_index]
    survived = _battle_survived(source)
    segment_reward = 1.0 if survived else 0.0
    return (
        TrainerInputRecord(
            example_index=example_index,
            rollout_index=example_index,
            seed=source.source_seed,
            step_index=0,
            screen_state=context.screen_state,
            snapshot_features=list(context.snapshot_features),
            legal_action_features=[list(row) for row in context.legal_action_features],
            legal_action_kinds=[str(kind) for kind in context.legal_action_kinds],
            legal_action_identities=current_identities,
            eligible_action_indices=list(context.eligible_action_indices),
            chosen_action_index=chosen_index,
            chosen_action_id=selected_action.action_id,
            chosen_action_identity=dict(current_identities[chosen_index]),
            chosen_action_kind=str(selected_action.kind),
            terminal_after_step=source.battle_completed,
            controller_provenance=dict(row.controller_provenance),
            source_metadata=_source_metadata(
                source,
                row,
                teacher_artifact_identity=teacher_artifact_identity,
                selected_budget=selected_budget,
            ),
            feature_schema_id=TACTICAL_FEATURE_SCHEMA_ID,
            tactical_state=dict(context.tactical_state),
            tactical_legal_actions=[
                dict(action) for action in context.tactical_legal_actions
            ],
            public_context_status=source.public_context_status,
            public_run_context=public_context,
            segment_index=example_index,
            segment_step_index=0,
            segment_decision_count=1,
            segment_end_reason=_segment_end_reason(source),
            is_segment_final_step=True,
            segment_reward=segment_reward,
            step_reward=segment_reward,
            return_to_go=segment_reward,
            reward_contributions={"battle_survived": segment_reward},
            raw_reward_components={"battle_outcome": None},
            structured_battle_outcome_status=(
                source.completed_battle_resource_outcome_status
            ),
            structured_battle_outcome=dict(source.completed_battle_resource_outcome),
            policy_target_kind=policy_target_kind,
            policy_target=policy_target,
            policy_target_source=policy_target_source,
            policy_target_action_index=policy_target_action_index,
            policy_target_action_identity=dict(policy_target_action_identity),
            behavior_action_status=behavior_status,
            behavior_action=behavior_action,
        ),
        restoration_method,
    )


def _policy_target_config(target: str) -> tuple[str, str]:
    if target == CLI_TARGET_TEACHER_ACTION_ONE_HOT:
        return (
            POLICY_TARGET_KIND_ORACLE_TEACHER_ACTION,
            POLICY_TARGET_SOURCE_ORACLE_TEACHER_ACTION,
        )
    if target == CLI_TARGET_SOFT_VISIT_DISTRIBUTION:
        return (
            POLICY_TARGET_KIND_ORACLE_SOFT_VISIT,
            POLICY_TARGET_SOURCE_ORACLE_SOFT_VISIT,
        )
    raise ValueError(f"unsupported Oracle teacher search-guidance target {target!r}")


def _policy_target_from_teacher_row(
    row: OracleTeacherRow,
    target: str,
    current_identities: Sequence[Mapping[str, Any]],
) -> tuple[list[float], int, dict[str, Any]]:
    if target == CLI_TARGET_TEACHER_ACTION_ONE_HOT:
        action_identity = _required_mapping(
            row.teacher_action.get("action_identity"),
            "teacher action identity",
        )
        action_index = _index_by_stable_identity(action_identity, current_identities)
        if action_index not in row.eligible_action_indices:
            raise ValueError("teacher action identity matched an ineligible action")
        policy_target = [0.0 for _ in current_identities]
        policy_target[action_index] = 1.0
        return policy_target, action_index, dict(current_identities[action_index])
    if target == CLI_TARGET_SOFT_VISIT_DISTRIBUTION:
        probabilities = _float_list(row.soft_visit_target.get("probabilities"))
        if len(probabilities) != len(row.legal_action_identities):
            raise ValueError("soft visit target length does not match teacher actions")
        policy_target = [0.0 for _ in current_identities]
        for probability, teacher_identity in zip(
            probabilities,
            row.legal_action_identities,
            strict=True,
        ):
            action_index = _index_by_stable_identity(
                teacher_identity, current_identities
            )
            policy_target[action_index] = probability
        eligible = [
            index
            for index in row.eligible_action_indices
            if 0 <= index < len(policy_target)
        ]
        if not eligible:
            raise ValueError("soft visit target row has no eligible actions")
        target_index = max(eligible, key=lambda index: policy_target[index])
        if sum(policy_target[index] for index in eligible) <= 0.0:
            raise ValueError("soft visit target has no positive eligible weight")
        return policy_target, target_index, dict(current_identities[target_index])
    raise ValueError(f"unsupported target {target!r}")


def _behavior_action_for_row(
    row: OracleTeacherRow,
    current_identities: Sequence[Mapping[str, Any]],
    *,
    fallback_index: int,
) -> tuple[str, dict[str, Any], int]:
    if not row.behavior_action:
        return BEHAVIOR_ACTION_UNAVAILABLE, {}, fallback_index
    behavior_identity = _required_mapping(
        row.behavior_action.get("action_identity"),
        "behavior action identity",
    )
    behavior_index = _index_by_stable_identity(behavior_identity, current_identities)
    return (
        BEHAVIOR_ACTION_AVAILABLE,
        {
            "source": "oracle_teacher_row.behavior_action",
            "legal_action_index": behavior_index,
            "action_identity": dict(current_identities[behavior_index]),
            "action_kind": row.behavior_action.get("action_kind"),
            "action_id": row.behavior_action.get("action_id"),
        },
        behavior_index,
    )


def _manifest_identity_problems(
    manifest: Mapping[str, Any],
    *,
    selected_budget: int,
    teacher_artifact_identity: Mapping[str, Any],
    t022_report_identity: Mapping[str, Any],
    source_pool_identity: Mapping[str, Any],
) -> list[str]:
    problems: list[str] = []
    if manifest.get("schema_id") != ORACLE_TEACHER_SCALEUP_MANIFEST_SCHEMA_ID:
        problems.append("T023 manifest schema id is unsupported")
    if manifest.get("format_version") != ORACLE_TEACHER_SCALEUP_MANIFEST_FORMAT_VERSION:
        problems.append("T023 manifest format version is unsupported")
    requested = _int_list(manifest.get("requested_budgets"))
    if selected_budget not in requested:
        problems.append(f"selected teacher budget {selected_budget} is absent")
    artifact = _generated_artifact_for_budget(manifest, selected_budget)
    if artifact is None:
        problems.append(f"selected teacher budget {selected_budget} has no artifact")
        return problems
    teacher = _mapping(artifact.get("teacher_artifact"))
    report = _mapping(artifact.get("t022_report_artifact"))
    natural_pool = _mapping(
        _mapping(manifest.get("input_artifacts")).get("natural_pool")
    )
    _append_identity_match_problem(
        problems,
        "teacher artifact",
        teacher.get("sha256"),
        teacher_artifact_identity.get("sha256"),
    )
    _append_identity_match_problem(
        problems,
        "T022 report artifact",
        report.get("sha256"),
        t022_report_identity.get("sha256"),
    )
    if not natural_pool:
        problems.append("T023 manifest is missing natural_pool source identity")
    else:
        _append_identity_match_problem(
            problems,
            "source pool artifact",
            natural_pool.get("sha256"),
            source_pool_identity.get("sha256"),
        )
    return problems


def _append_identity_match_problem(
    problems: list[str],
    label: str,
    expected: Any,
    actual: Any,
) -> None:
    if not expected:
        problems.append(f"T023 manifest is missing {label} sha256")
    elif actual != expected:
        problems.append(f"{label} sha256 does not match T023 manifest")


def _generated_artifact_for_budget(
    manifest: Mapping[str, Any],
    budget: int,
) -> dict[str, Any] | None:
    for artifact in _mapping_list(manifest.get("generated_artifacts")):
        if artifact.get("budget") == budget:
            return artifact
    return None


def _source_records_by_checkpoint(
    pool: NaturalBattleStartPool,
) -> dict[str, BattleStartCheckpointRecord]:
    result: dict[str, BattleStartCheckpointRecord] = {}
    for record in pool.records:
        if record.source_checkpoint_id in result:
            raise ValueError(
                f"source pool duplicate checkpoint id {record.source_checkpoint_id!r}"
            )
        result[record.source_checkpoint_id] = record
    return result


def _require_teacher_legal_identities(
    row: OracleTeacherRow,
    current_identities: Sequence[Mapping[str, Any]],
) -> None:
    teacher_ids = [
        _stable_identity(identity) for identity in row.legal_action_identities
    ]
    current_ids = [_stable_identity(identity) for identity in current_identities]
    if Counter(teacher_ids) != Counter(current_ids):
        raise ValueError("restored legal action identities do not match teacher row")


def _index_by_stable_identity(
    identity: Mapping[str, Any],
    current_identities: Sequence[Mapping[str, Any]],
) -> int:
    target = _stable_identity(identity)
    matches = [
        index
        for index, current in enumerate(current_identities)
        if _stable_identity(current) == target
    ]
    if len(matches) != 1:
        raise ValueError(
            f"action identity matched {len(matches)} legal actions, expected 1"
        )
    return matches[0]


def _stable_identity(identity: Mapping[str, Any]) -> str:
    return action_identity_from_dict(identity).stable_id


def _public_context_for_source(source: BattleStartCheckpointRecord) -> dict[str, Any]:
    if source.public_context_status == PUBLIC_CONTEXT_AVAILABLE:
        return sanitize_public_context_artifact(
            source.public_run_context,
            label=f"source record {source.record_index}",
        )
    if source.public_context_status == PUBLIC_CONTEXT_LEGACY_UNAVAILABLE:
        return {}
    raise ValueError(
        f"unsupported public context status {source.public_context_status!r}"
    )


def _source_metadata(
    source: BattleStartCheckpointRecord,
    row: OracleTeacherRow,
    *,
    teacher_artifact_identity: Mapping[str, Any],
    selected_budget: int,
) -> dict[str, Any]:
    metadata = dict(source.structural_metadata)
    metadata.update(
        {
            "source_kind": source.distribution_kind,
            "distribution_kind": source.distribution_kind,
            "sampling_component": row.sampling_component,
            "source_checkpoint_id": source.source_checkpoint_id,
            "source_run_id": source.source_run_id,
            "source_seed": source.source_seed,
            "seed": source.source_seed,
            "source_battle_index": source.source_battle_index,
            "checkpoint_information_regime": source.checkpoint_information_regime,
            "teacher_information_regime": row.information_regime,
            "teacher_budget": selected_budget,
            "teacher_artifact_sha256": teacher_artifact_identity.get("sha256"),
        }
    )
    return _json_safe_mapping(metadata)


def _segment_end_reason(source: BattleStartCheckpointRecord) -> str:
    if not source.battle_completed:
        return "source_battle_incomplete"
    if source.battle_outcome:
        return f"source_battle_{source.battle_outcome.lower()}"
    return "source_battle_completed"


def _battle_survived(source: BattleStartCheckpointRecord) -> bool:
    outcome = _mapping(source.completed_battle_resource_outcome)
    survived = _mapping(outcome.get("battle_survived"))
    if survived.get("status") == "available":
        return bool(survived.get("value"))
    return source.battle_outcome == "PLAYER_VICTORY"


def _action_space_from_mapping(raw: Mapping[str, Any]) -> ActionSpaceConfig:
    excluded_raw = raw.get("excluded_kinds", [])
    preferred_raw = raw.get("preferred_kinds", [])
    return ActionSpaceConfig(
        excluded_kinds=frozenset(str(item) for item in _list(excluded_raw)),
        preferred_kinds=tuple(str(item) for item in _list(preferred_raw)),
        allow_excluded_fallback=bool(raw.get("allow_excluded_fallback", True)),
        include_non_combat_potions=bool(raw.get("include_non_combat_potions", True)),
    )


def _information_regime_summary(
    teacher_dataset: OracleTeacherDataset,
    records: Sequence[TrainerInputRecord],
) -> dict[str, Any]:
    return {
        "expected_information_regime": "full_simulator_state_oracle_like",
        "teacher_dataset_information_regime": teacher_dataset.information_regime,
        "teacher_row_counts": _counter_dict(
            Counter(row.information_regime for row in teacher_dataset.records)
        ),
        "trainer_controller_regime_counts": _counter_dict(
            Counter(_controller_information_regime(record) for record in records)
        ),
        "source_checkpoint_regime_counts": _counter_dict(
            Counter(
                str(
                    record.source_metadata.get(
                        "checkpoint_information_regime", "missing"
                    )
                )
                for record in records
            )
        ),
    }


def _controller_information_regime(record: TrainerInputRecord) -> str:
    config = _mapping(_mapping(record.controller_provenance).get("config"))
    return str(config.get("information_regime", "missing"))


def _positive_target_count(values: Sequence[float]) -> int:
    return sum(1 for value in values if value > 0.0)


def _int_list(value: Any) -> list[int]:
    return [int(item) for item in _list(value) if not isinstance(item, bool)]


def _float_list(value: Any) -> list[float]:
    result: list[float] = []
    for item in _list(value):
        if isinstance(item, bool) or not isinstance(item, (int, float)):
            raise ValueError("target probabilities must be numeric")
        number = float(item)
        if not math.isfinite(number) or number < 0.0:
            raise ValueError("target probabilities must be finite and non-negative")
        result.append(number)
    return result


def _required_mapping(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} must be a mapping")
    return dict(value)


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _mapping_list(value: Any) -> list[dict[str, Any]]:
    return [dict(item) for item in _list(value) if isinstance(item, Mapping)]


def _list(value: Any) -> list[Any]:
    return list(value) if isinstance(value, list) else []


def _counter_dict(values: Mapping[Any, int]) -> dict[str, int]:
    return {str(key): int(values[key]) for key in sorted(values, key=str)}


def _json_safe_mapping(value: Mapping[str, Any]) -> dict[str, Any]:
    return {str(key): _json_safe_value(item) for key, item in value.items()}


def _json_safe_value(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Mapping):
        return {str(key): _json_safe_value(item) for key, item in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return [_json_safe_value(item) for item in value]
    return str(value)


def _append_counter(
    lines: list[str],
    title: str,
    counter: Mapping[Any, int],
) -> None:
    lines.append(f"{title}:")
    if not counter:
        lines.append("  (none)")
        return
    for key in sorted(counter, key=str):
        lines.append(f"  {key}: {counter[key]}")


def _yes_no(value: bool) -> str:
    return "yes" if value else "no"
