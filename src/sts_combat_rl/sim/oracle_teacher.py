"""Versioned Oracle-search teacher JSONL artifacts."""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
import json
import time
from typing import Any, TextIO

from sts_combat_rl.sim.action_space import ActionSpaceConfig
from sts_combat_rl.sim.artifact_versioning import (
    ArtifactMigrationReport,
    migrate_artifact_document,
    preserved_migration_report,
)
from sts_combat_rl.sim.battle_start_pool import (
    NATURAL_SAMPLING_COMPONENT,
    NaturalBattleStartPool,
    restore_battle_start_record,
)
from sts_combat_rl.sim.contract import CheckpointingSimulatorAdapter
from sts_combat_rl.sim.controlled_run import build_decision_context
from sts_combat_rl.sim.controller_contract import controller_provenance_from_dict
from sts_combat_rl.sim.decision_record import action_identity_dicts_for_actions
from sts_combat_rl.sim.lightspeed_source import (
    format_lightspeed_source_identity,
    lightspeed_source_identity_dict,
)
from sts_combat_rl.sim.online_controller import NATIVE_SEARCH_INFORMATION_REGIME
from sts_combat_rl.sim.oracle_search import (
    ORACLE_SEARCH_SCHEMA_ID,
    OracleSearchController,
    build_oracle_search_report,
    oracle_visit_target_dict,
    select_oracle_root_action,
)
from sts_combat_rl.sim.public_context_artifacts import (
    PUBLIC_CONTEXT_AVAILABLE,
    PUBLIC_CONTEXT_LEGACY_UNAVAILABLE,
    public_context_artifact_problems,
    sanitize_public_context_artifact,
)


ORACLE_TEACHER_ARTIFACT_SCHEMA_ID = "oracle-search-teacher-v1"
ORACLE_TEACHER_ARTIFACT_FORMAT_VERSION = 1
ORACLE_TEACHER_ROW_SCHEMA_ID = "oracle-search-teacher-row-v1"
ORACLE_TEACHER_MIGRATIONS = ()


@dataclass(frozen=True)
class OracleTeacherRow:
    """One pre-decision Oracle-search teacher row."""

    row_index: int
    source_checkpoint_id: str
    source_pool_record_index: int
    source_run_id: str
    source_seed: int
    source_battle_index: int
    source_distribution_kind: str
    sampling_component: str
    restoration_method: str
    structural_metadata: dict[str, Any]
    checkpoint_information_regime: str
    legal_action_identities: list[dict[str, Any]]
    legal_action_kinds: list[str]
    eligible_action_indices: list[int]
    root_statistics: list[dict[str, Any]]
    teacher_action: dict[str, Any]
    soft_visit_target: dict[str, Any]
    behavior_action: dict[str, Any] | None
    controller_provenance: dict[str, Any]
    information_regime: str
    public_context_status: str
    public_run_context: dict[str, Any]
    native_search_report: dict[str, Any]
    row_schema_id: str = ORACLE_TEACHER_ROW_SCHEMA_ID

    def to_dict(self) -> dict[str, Any]:
        return {
            "row_schema_id": self.row_schema_id,
            "row_index": self.row_index,
            "source_checkpoint_id": self.source_checkpoint_id,
            "source_pool_record_index": self.source_pool_record_index,
            "source_run_id": self.source_run_id,
            "source_seed": self.source_seed,
            "source_battle_index": self.source_battle_index,
            "source_distribution_kind": self.source_distribution_kind,
            "sampling_component": self.sampling_component,
            "restoration_method": self.restoration_method,
            "structural_metadata": _json_safe_mapping(self.structural_metadata),
            "checkpoint_information_regime": self.checkpoint_information_regime,
            "legal_action_identities": [
                _json_safe_mapping(identity)
                for identity in self.legal_action_identities
            ],
            "legal_action_kinds": list(self.legal_action_kinds),
            "eligible_action_indices": list(self.eligible_action_indices),
            "root_statistics": [
                _json_safe_mapping(row) for row in self.root_statistics
            ],
            "teacher_action": _json_safe_mapping(self.teacher_action),
            "soft_visit_target": _json_safe_mapping(self.soft_visit_target),
            "behavior_action": (
                None
                if self.behavior_action is None
                else _json_safe_mapping(self.behavior_action)
            ),
            "controller_provenance": _json_safe_mapping(self.controller_provenance),
            "information_regime": self.information_regime,
            "public_context_status": self.public_context_status,
            "public_run_context": _json_safe_mapping(self.public_run_context),
            "native_search_report": _json_safe_mapping(self.native_search_report),
        }


@dataclass(frozen=True)
class OracleTeacherDataset:
    """Current-schema Oracle-search teacher dataset."""

    native_source_identity: dict[str, Any]
    controller_provenance: dict[str, Any]
    action_space_config: dict[str, Any]
    source_pool_format_version: int
    source_pool_controller_provenance: dict[str, Any]
    format_version: int = ORACLE_TEACHER_ARTIFACT_FORMAT_VERSION
    artifact_schema_id: str = ORACLE_TEACHER_ARTIFACT_SCHEMA_ID
    native_search_schema_id: str = ORACLE_SEARCH_SCHEMA_ID
    information_regime: str = NATIVE_SEARCH_INFORMATION_REGIME
    records: list[OracleTeacherRow] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)
    migration_report: ArtifactMigrationReport = field(
        default_factory=lambda: ArtifactMigrationReport(
            source_version=ORACLE_TEACHER_ARTIFACT_FORMAT_VERSION,
            target_version=ORACLE_TEACHER_ARTIFACT_FORMAT_VERSION,
        ),
        compare=False,
    )


@dataclass(frozen=True)
class OracleTeacherDatasetReport:
    """Human-readable summary inputs for teacher collection."""

    record_count: int
    unique_source_checkpoints: int
    information_regime: str
    native_source_identity: dict[str, Any]
    controller_identity: str
    root_row_count: int
    root_visit_count: int
    simulations_requested: int
    native_simulator_steps: int | None
    model_calls: int | None
    wall_clock_time_s: float | None
    sampling_component_counts: Counter[str] = field(default_factory=Counter)
    teacher_selection_counts: Counter[str] = field(default_factory=Counter)
    public_context_status_counts: Counter[str] = field(default_factory=Counter)
    problems: list[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return self.record_count > 0 and not self.problems


def collect_oracle_teacher_dataset_from_pool(
    adapter_factory: Callable[[], CheckpointingSimulatorAdapter],
    pool: NaturalBattleStartPool,
    controller: OracleSearchController,
    *,
    action_space: ActionSpaceConfig | None = None,
) -> OracleTeacherDataset:
    """Restore each pool record and collect one Oracle teacher row."""

    active_action_space = action_space or controller.action_space
    rows: list[OracleTeacherRow] = []
    problems: list[str] = []
    for record in pool.records:
        label = f"pool record {record.record_index}"
        try:
            adapter = adapter_factory()
            snapshot, restoration_method = restore_battle_start_record(adapter, record)
            actions = list(adapter.legal_actions(snapshot))
            public_run_context = _row_public_context(
                record.public_context_status, record
            )
            context = build_decision_context(
                snapshot.raw,
                actions,
                active_action_space,
                public_run_context=public_run_context,
            )
            start = time.perf_counter()
            raw_search = adapter.battle_search(
                snapshot,
                simulations=controller.simulations,
                include_potions=bool(
                    controller.provenance.config.get("include_potions", False)
                ),
            )
            elapsed = time.perf_counter() - start
            search_report = build_oracle_search_report(
                raw_search,
                actions,
                context,
                wall_clock_time_s=elapsed,
            )
            if not search_report.search_ok:
                raise ValueError("; ".join(search_report.problems))
            teacher_target = select_oracle_root_action(
                search_report,
                selection_rule=controller.root_selection_rule,
            )
        except (RuntimeError, ValueError) as exc:
            problems.append(f"{label}: {exc}")
            continue

        rows.append(
            OracleTeacherRow(
                row_index=len(rows),
                source_checkpoint_id=record.source_checkpoint_id,
                source_pool_record_index=record.record_index,
                source_run_id=record.source_run_id,
                source_seed=record.source_seed,
                source_battle_index=record.source_battle_index,
                source_distribution_kind=record.distribution_kind,
                sampling_component=NATURAL_SAMPLING_COMPONENT,
                restoration_method=restoration_method,
                structural_metadata=dict(record.structural_metadata),
                checkpoint_information_regime=record.checkpoint_information_regime,
                legal_action_identities=action_identity_dicts_for_actions(actions),
                legal_action_kinds=[str(action.kind) for action in actions],
                eligible_action_indices=list(context.eligible_action_indices),
                root_statistics=[
                    action.to_dict() for action in search_report.root_actions
                ],
                teacher_action=teacher_target.to_dict(),
                soft_visit_target=oracle_visit_target_dict(search_report),
                behavior_action=None,
                controller_provenance=controller.provenance.to_dict(),
                information_regime=NATIVE_SEARCH_INFORMATION_REGIME,
                public_context_status=record.public_context_status,
                public_run_context=public_run_context,
                native_search_report=search_report.to_dict(),
            )
        )

    dataset = OracleTeacherDataset(
        native_source_identity=lightspeed_source_identity_dict(),
        controller_provenance=controller.provenance.to_dict(),
        action_space_config=active_action_space.to_dict(),
        source_pool_format_version=pool.format_version,
        source_pool_controller_provenance=pool.source_controller_provenance,
        records=rows,
        problems=problems,
    )
    return OracleTeacherDataset(
        native_source_identity=dataset.native_source_identity,
        controller_provenance=dataset.controller_provenance,
        action_space_config=dataset.action_space_config,
        source_pool_format_version=dataset.source_pool_format_version,
        source_pool_controller_provenance=dataset.source_pool_controller_provenance,
        records=dataset.records,
        problems=oracle_teacher_dataset_problems(dataset),
    )


def dump_oracle_teacher_dataset_jsonl(
    dataset: OracleTeacherDataset,
    stream: TextIO,
) -> None:
    """Write current-schema Oracle teacher JSONL."""

    problems = oracle_teacher_dataset_problems(dataset)
    if problems:
        raise ValueError("invalid oracle teacher dataset: " + "; ".join(problems))
    metadata = {
        "artifact_schema_id": ORACLE_TEACHER_ARTIFACT_SCHEMA_ID,
        "format_version": ORACLE_TEACHER_ARTIFACT_FORMAT_VERSION,
        "native_search_schema_id": dataset.native_search_schema_id,
        "information_regime": dataset.information_regime,
        "native_source_identity": dataset.native_source_identity,
        "controller_provenance": dataset.controller_provenance,
        "action_space_config": dataset.action_space_config,
        "source_pool_format_version": dataset.source_pool_format_version,
        "source_pool_controller_provenance": dataset.source_pool_controller_provenance,
        "record_count": len(dataset.records),
        "migration_report": dataset.migration_report.to_dict(),
        "problems": list(dataset.problems),
    }
    _write_row(stream, {"type": "metadata", "metadata": metadata})
    for record in dataset.records:
        _write_row(stream, {"type": "record", "record": record.to_dict()})


def load_oracle_teacher_dataset_jsonl(
    stream: TextIO,
    *,
    validate: bool = True,
) -> OracleTeacherDataset:
    """Load and migrate an Oracle teacher JSONL artifact."""

    metadata: dict[str, Any] | None = None
    raw_records: list[dict[str, Any]] = []
    for line_number, raw_line in enumerate(stream, start=1):
        if not raw_line.strip():
            continue
        try:
            row = json.loads(raw_line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"line {line_number}: invalid JSON") from exc
        if not isinstance(row, dict):
            raise ValueError(f"line {line_number}: row must be an object")
        if row.get("type") == "metadata":
            if metadata is not None:
                raise ValueError(f"line {line_number}: duplicate metadata")
            metadata = _require_mapping(row.get("metadata"), "metadata")
        elif row.get("type") == "record":
            raw_records.append(_require_mapping(row.get("record"), "record"))
        else:
            raise ValueError(f"line {line_number}: unknown row type")
    if metadata is None:
        raise ValueError("missing oracle teacher metadata")

    migrated = migrate_artifact_document(
        metadata,
        raw_records,
        current_version=ORACLE_TEACHER_ARTIFACT_FORMAT_VERSION,
        migrations=ORACLE_TEACHER_MIGRATIONS,
        artifact_name="oracle teacher dataset",
    )
    metadata = migrated.document.metadata
    records = [
        oracle_teacher_row_from_dict(raw, label=f"record {index}")
        for index, raw in enumerate(migrated.document.records)
    ]
    if metadata.get("record_count") != len(records):
        raise ValueError("oracle teacher metadata record_count mismatch")
    dataset = OracleTeacherDataset(
        native_source_identity=_require_mapping(
            metadata.get("native_source_identity"), "native_source_identity"
        ),
        controller_provenance=_require_mapping(
            metadata.get("controller_provenance"), "controller_provenance"
        ),
        action_space_config=_require_mapping(
            metadata.get("action_space_config"), "action_space_config"
        ),
        source_pool_format_version=_non_negative_int(
            metadata.get("source_pool_format_version"), "source_pool_format_version"
        ),
        source_pool_controller_provenance=_require_mapping(
            metadata.get("source_pool_controller_provenance"),
            "source_pool_controller_provenance",
        ),
        artifact_schema_id=_required_string(
            metadata.get("artifact_schema_id"), "artifact_schema_id"
        ),
        native_search_schema_id=_required_string(
            metadata.get("native_search_schema_id"), "native_search_schema_id"
        ),
        information_regime=_required_string(
            metadata.get("information_regime"), "information_regime"
        ),
        records=records,
        problems=_require_string_list(metadata.get("problems", []), "problems"),
        migration_report=preserved_migration_report(
            metadata,
            migrated.report,
            artifact_name="oracle teacher dataset",
        ),
    )
    if validate:
        problems = oracle_teacher_dataset_problems(dataset)
        if problems:
            raise ValueError("invalid oracle teacher dataset: " + "; ".join(problems))
    return dataset


def oracle_teacher_row_from_dict(
    raw: Mapping[str, Any],
    *,
    label: str,
) -> OracleTeacherRow:
    """Load one current-schema teacher row."""

    public_context_status = _required_string(
        raw.get("public_context_status"), f"{label} public_context_status"
    )
    public_run_context = _public_run_context(
        raw.get("public_run_context"),
        public_context_status=public_context_status,
        label=label,
    )
    behavior_action_raw = raw.get("behavior_action")
    behavior_action = (
        None
        if behavior_action_raw is None
        else _require_mapping(behavior_action_raw, f"{label} behavior_action")
    )
    return OracleTeacherRow(
        row_schema_id=_required_string(
            raw.get("row_schema_id"), f"{label} row_schema_id"
        ),
        row_index=_non_negative_int(raw.get("row_index"), f"{label} row_index"),
        source_checkpoint_id=_required_string(
            raw.get("source_checkpoint_id"), f"{label} source_checkpoint_id"
        ),
        source_pool_record_index=_non_negative_int(
            raw.get("source_pool_record_index"),
            f"{label} source_pool_record_index",
        ),
        source_run_id=_required_string(
            raw.get("source_run_id"), f"{label} source_run_id"
        ),
        source_seed=_non_negative_int(raw.get("source_seed"), f"{label} source_seed"),
        source_battle_index=_non_negative_int(
            raw.get("source_battle_index"), f"{label} source_battle_index"
        ),
        source_distribution_kind=_required_string(
            raw.get("source_distribution_kind"),
            f"{label} source_distribution_kind",
        ),
        sampling_component=_required_string(
            raw.get("sampling_component"), f"{label} sampling_component"
        ),
        restoration_method=_required_string(
            raw.get("restoration_method"), f"{label} restoration_method"
        ),
        structural_metadata=_require_mapping(
            raw.get("structural_metadata"), f"{label} structural_metadata"
        ),
        checkpoint_information_regime=_required_string(
            raw.get("checkpoint_information_regime"),
            f"{label} checkpoint_information_regime",
        ),
        legal_action_identities=_require_mapping_list(
            raw.get("legal_action_identities"), f"{label} legal_action_identities"
        ),
        legal_action_kinds=_require_string_list(
            raw.get("legal_action_kinds"), f"{label} legal_action_kinds"
        ),
        eligible_action_indices=_require_non_negative_int_list(
            raw.get("eligible_action_indices"), f"{label} eligible_action_indices"
        ),
        root_statistics=_require_mapping_list(
            raw.get("root_statistics"), f"{label} root_statistics"
        ),
        teacher_action=_require_mapping(
            raw.get("teacher_action"), f"{label} teacher_action"
        ),
        soft_visit_target=_require_mapping(
            raw.get("soft_visit_target"), f"{label} soft_visit_target"
        ),
        behavior_action=behavior_action,
        controller_provenance=_require_mapping(
            raw.get("controller_provenance"), f"{label} controller_provenance"
        ),
        information_regime=_required_string(
            raw.get("information_regime"), f"{label} information_regime"
        ),
        public_context_status=public_context_status,
        public_run_context=public_run_context,
        native_search_report=_require_mapping(
            raw.get("native_search_report"), f"{label} native_search_report"
        ),
    )


def oracle_teacher_dataset_problems(
    dataset: OracleTeacherDataset,
) -> list[str]:
    """Return structural problems for an Oracle teacher dataset."""

    problems: list[str] = list(dataset.problems)
    if dataset.artifact_schema_id != ORACLE_TEACHER_ARTIFACT_SCHEMA_ID:
        problems.append("unsupported oracle teacher artifact schema")
    if dataset.format_version != ORACLE_TEACHER_ARTIFACT_FORMAT_VERSION:
        problems.append("unsupported oracle teacher format version")
    if dataset.native_search_schema_id != ORACLE_SEARCH_SCHEMA_ID:
        problems.append("unsupported native search schema on teacher dataset")
    if dataset.information_regime != NATIVE_SEARCH_INFORMATION_REGIME:
        problems.append("oracle teacher dataset has wrong information regime")
    try:
        provenance = controller_provenance_from_dict(dataset.controller_provenance)
        if provenance.kind != "oracle_battle_search":
            problems.append("teacher controller provenance is not oracle_battle_search")
        if (
            provenance.config.get("information_regime")
            != NATIVE_SEARCH_INFORMATION_REGIME
        ):
            problems.append("teacher controller provenance has wrong regime")
    except ValueError as exc:
        problems.append(f"teacher controller provenance invalid: {exc}")
    for index, row in enumerate(dataset.records):
        problems.extend(_oracle_teacher_row_problems(row, expected_index=index))
    return list(dict.fromkeys(problems))


def build_oracle_teacher_dataset_report(
    dataset: OracleTeacherDataset,
) -> OracleTeacherDatasetReport:
    """Build aggregate telemetry for a teacher dataset."""

    root_row_count = 0
    root_visit_count = 0
    simulations_requested = 0
    native_steps: int | None = 0
    model_calls: int | None = 0
    wall_clock: float | None = 0.0
    for row in dataset.records:
        report = row.native_search_report
        root_row_count += len(row.root_statistics)
        root_visit_count += _optional_int_value(report.get("root_visits")) or 0
        simulations_requested += (
            _optional_int_value(report.get("simulations_requested")) or 0
        )
        native_steps = _sum_optional_int(
            native_steps,
            _optional_int_value(report.get("native_simulator_steps")),
        )
        model_calls = _sum_optional_int(
            model_calls,
            _optional_int_value(report.get("model_calls")),
        )
        wall_clock = _sum_optional_float(
            wall_clock,
            _optional_float_value(report.get("wall_clock_time_s")),
        )
    return OracleTeacherDatasetReport(
        record_count=len(dataset.records),
        unique_source_checkpoints=len(
            {row.source_checkpoint_id for row in dataset.records}
        ),
        information_regime=dataset.information_regime,
        native_source_identity=dict(dataset.native_source_identity),
        controller_identity=controller_provenance_from_dict(
            dataset.controller_provenance
        ).identity,
        root_row_count=root_row_count,
        root_visit_count=root_visit_count,
        simulations_requested=simulations_requested,
        native_simulator_steps=native_steps,
        model_calls=model_calls,
        wall_clock_time_s=wall_clock,
        sampling_component_counts=Counter(
            row.sampling_component for row in dataset.records
        ),
        teacher_selection_counts=Counter(
            str(row.teacher_action.get("selection_rule")) for row in dataset.records
        ),
        public_context_status_counts=Counter(
            row.public_context_status for row in dataset.records
        ),
        problems=oracle_teacher_dataset_problems(dataset),
    )


def format_oracle_teacher_dataset_report(
    report: OracleTeacherDatasetReport,
) -> str:
    """Format teacher collection summary for stderr."""

    lines = [
        "Oracle search teacher collection",
        f"information regime: {report.information_regime}",
        f"records: {report.record_count}",
        f"unique source checkpoints: {report.unique_source_checkpoints}",
        f"controller identity: {report.controller_identity}",
        f"root rows: {report.root_row_count}",
        f"root visits: {report.root_visit_count}",
        f"simulations requested: {report.simulations_requested}",
        (
            "native simulator steps: "
            + (
                str(report.native_simulator_steps)
                if report.native_simulator_steps is not None
                else "(missing)"
            )
        ),
        (
            "model calls: "
            + (
                str(report.model_calls)
                if report.model_calls is not None
                else "(missing)"
            )
        ),
        (
            "wall-clock seconds: "
            + (
                f"{report.wall_clock_time_s:.6f}"
                if report.wall_clock_time_s is not None
                else "(missing)"
            )
        ),
        "sampling components:",
    ]
    _append_counter(lines, report.sampling_component_counts)
    lines.append("teacher selection rules:")
    _append_counter(lines, report.teacher_selection_counts)
    lines.append("public-context statuses:")
    _append_counter(lines, report.public_context_status_counts)
    lines.append("")
    lines.append(format_lightspeed_source_identity(report.native_source_identity))
    lines.append("")
    lines.append("problems:")
    if report.problems:
        lines.extend(f"  - {problem}" for problem in report.problems)
    else:
        lines.append("  (none)")
    return "\n".join(lines)


def _oracle_teacher_row_problems(
    row: OracleTeacherRow,
    *,
    expected_index: int,
) -> list[str]:
    problems: list[str] = []
    label = f"teacher row {expected_index}"
    if row.row_schema_id != ORACLE_TEACHER_ROW_SCHEMA_ID:
        problems.append(f"{label}: unsupported row schema")
    if row.row_index != expected_index:
        problems.append(f"{label}: row index is not contiguous")
    if row.information_regime != NATIVE_SEARCH_INFORMATION_REGIME:
        problems.append(f"{label}: wrong information regime")
    if row.behavior_action is not None and row.behavior_action == row.teacher_action:
        problems.append(f"{label}: behavior action must not alias teacher action")
    legal_count = len(row.legal_action_identities)
    if len(row.legal_action_kinds) != legal_count:
        problems.append(f"{label}: legal action kind count mismatch")
    if len(row.root_statistics) != legal_count:
        problems.append(f"{label}: root statistics must match legal action count")
    if not row.teacher_action:
        problems.append(f"{label}: teacher action is missing")
    else:
        selected = row.teacher_action.get("legal_action_index")
        if (
            isinstance(selected, bool)
            or not isinstance(selected, int)
            or selected < 0
            or selected >= legal_count
        ):
            problems.append(f"{label}: teacher action index is outside legal actions")
        elif selected not in row.eligible_action_indices:
            problems.append(f"{label}: teacher action is not eligible")
    probabilities = row.soft_visit_target.get("probabilities")
    if not isinstance(probabilities, list) or len(probabilities) != legal_count:
        problems.append(f"{label}: soft visit target length mismatch")
    problems.extend(
        public_context_artifact_problems(
            status=row.public_context_status,
            context=row.public_run_context,
            label=label,
            require_candidate_actions=bool(row.public_run_context),
        )
    )
    return problems


def _row_public_context(status: str, record: Any) -> dict[str, Any]:
    if status == PUBLIC_CONTEXT_AVAILABLE:
        return sanitize_public_context_artifact(
            record.public_run_context,
            label=f"pool record {record.record_index}",
        )
    if status == PUBLIC_CONTEXT_LEGACY_UNAVAILABLE:
        return {}
    raise ValueError(f"unsupported public context status {status!r}")


def _public_run_context(
    value: Any,
    *,
    public_context_status: str,
    label: str,
) -> dict[str, Any]:
    if public_context_status == PUBLIC_CONTEXT_LEGACY_UNAVAILABLE:
        if value not in (None, {}):
            raise ValueError(f"{label} legacy public context must be empty")
        return {}
    return sanitize_public_context_artifact(value, label=label)


def _write_row(stream: TextIO, row: Mapping[str, Any]) -> None:
    stream.write(json.dumps(row, sort_keys=True, allow_nan=False))
    stream.write("\n")


def _json_safe_mapping(value: Mapping[str, Any]) -> dict[str, Any]:
    return {str(key): _json_safe_value(item) for key, item in value.items()}


def _json_safe_value(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Mapping):
        return _json_safe_mapping(value)
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return [_json_safe_value(item) for item in value]
    raise ValueError(f"artifact value is not JSON-safe: {type(value).__name__}")


def _require_mapping(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} must be an object")
    return {str(key): item for key, item in value.items()}


def _require_mapping_list(value: Any, label: str) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        raise ValueError(f"{label} must be a list")
    return [
        _require_mapping(item, f"{label} {index}") for index, item in enumerate(value)
    ]


def _required_string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{label} must be a non-empty string")
    return value


def _require_string_list(value: Any, label: str) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError(f"{label} must be a string list")
    return list(value)


def _require_non_negative_int_list(value: Any, label: str) -> list[int]:
    if not isinstance(value, list):
        raise ValueError(f"{label} must be a list")
    result: list[int] = []
    for index, item in enumerate(value):
        result.append(_non_negative_int(item, f"{label} {index}"))
    return result


def _non_negative_int(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{label} must be a non-negative integer")
    return value


def _optional_int_value(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value


def _optional_float_value(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _sum_optional_int(current: int | None, value: int | None) -> int | None:
    if current is None or value is None:
        return None
    return current + value


def _sum_optional_float(current: float | None, value: float | None) -> float | None:
    if current is None or value is None:
        return None
    return current + value


def _append_counter(lines: list[str], counter: Counter[str]) -> None:
    if not counter:
        lines.append("  (none)")
        return
    for key, count in sorted(counter.items()):
        lines.append(f"  {key}: {count}")
