"""Raw native public-projection capability audit helpers.

This module deliberately does not define a public controller context.  It
parses the versioned, raw ``StepSimulator.public_projection()`` payload into a
small immutable audit view, checks native candidate-action parity against the
adapter, and reports capability/coverage evidence.  T015 owns any sanitized
public-context schema and controller integration.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
import json
from typing import Any, Protocol

from sts_combat_rl.sim.contract import (
    CheckpointingSimulatorAdapter,
    SimulatorAction,
    SimulatorSnapshot,
)
from sts_combat_rl.sim.decision_record import action_identity_dicts_for_actions


NATIVE_PUBLIC_PROJECTION_SCHEMA_ID = "native-public-projection-v1"
NATIVE_PUBLIC_PROJECTION_PATCH_ID = "sts_lightspeed_public_projection.patch"
NATIVE_PUBLIC_PROJECTION_EXTERNAL_BASE_COMMIT = "7476a81"
NATIVE_PUBLIC_PROJECTION_REPORT_SCHEMA_ID = (
    "native-public-projection-capability-report-v1"
)

PROJECTION_FIELD_NAMES = (
    "screen_identity",
    "visible_act_boss",
    "visible_map_graph",
    "current_map_node",
    "immediately_legal_routes",
    "persistent_resources",
    "screen_payload",
    "candidate_actions",
)
PROJECTION_AVAILABILITY_VALUES = frozenset({"available", "unavailable", "unsupported"})
RESOURCE_FIELD_NAMES = (
    "current_hp",
    "max_hp",
    "gold",
    "potion_count",
    "potion_capacity",
    "deck",
    "relics",
    "potion_identities",
    "keys",
)
KNOWN_SCREEN_STATES = frozenset(
    {
        "BATTLE",
        "BOSS_RELIC_REWARDS",
        "CARD_SELECT",
        "EVENT_SCREEN",
        "MAP_SCREEN",
        "REWARDS",
        "REST_ROOM",
        "SHOP_ROOM",
        "TREASURE_ROOM",
    }
)


@dataclass(frozen=True)
class NativeProjectionField:
    """One declared native field with explicit availability and provenance."""

    availability: str
    source: str | None = None
    reason: str | None = None


@dataclass(frozen=True)
class NativeProjectionAction:
    """One exact candidate emitted by the native ``legalActions`` source."""

    scope: str
    bits: int
    kind: str
    label: str
    idx1: int
    idx2: int
    idx3: int

    def to_simulator_action(self) -> SimulatorAction:
        """Adapt this audited native candidate for identity comparison only."""

        return SimulatorAction(
            action_id=f"{self.scope}:{self.bits}",
            label=self.label,
            kind=self.kind,
            raw={
                "scope": self.scope,
                "bits": self.bits,
                "idx1": self.idx1,
                "idx2": self.idx2,
                "idx3": self.idx3,
            },
        )


@dataclass(frozen=True)
class NativePublicProjection:
    """Restricted parsed view of the native raw capability payload.

    ``canonical_payload`` is retained only for exact checkpoint comparison.
    The source dictionary is intentionally not exposed, preventing a raw
    capability surface from becoming an accidental controller input.
    """

    schema_id: str
    external_base_commit: str
    patch_identity: str
    screen_identity: str
    fields: Mapping[str, NativeProjectionField]
    resource_fields: Mapping[str, NativeProjectionField]
    candidate_actions: tuple[NativeProjectionAction, ...]
    canonical_payload: str

    @property
    def candidate_source(self) -> str | None:
        return self.fields["candidate_actions"].source

    def candidate_action_identities(self) -> list[dict[str, Any]]:
        return action_identity_dicts_for_actions(
            [action.to_simulator_action() for action in self.candidate_actions]
        )


class NativePublicProjectionAdapter(CheckpointingSimulatorAdapter, Protocol):
    """Optional adapter extension used only by the T014 capability audit."""

    def public_projection(self, snapshot: SimulatorSnapshot) -> NativePublicProjection:
        """Read the current raw native projection for audit purposes."""


@dataclass(frozen=True)
class ProjectionCheckpointResult:
    """Checkpoint comparison result for one audited decision."""

    screen_identity_matches: bool
    projection_matches: bool
    candidate_actions_match: bool


@dataclass
class NativePublicProjectionCapabilityReport:
    """Versioned audit report; it is diagnostic, not a persisted run artifact."""

    report_schema_id: str = NATIVE_PUBLIC_PROJECTION_REPORT_SCHEMA_ID
    api_schema_id: str = NATIVE_PUBLIC_PROJECTION_SCHEMA_ID
    external_base_commit: str = NATIVE_PUBLIC_PROJECTION_EXTERNAL_BASE_COMMIT
    patch_identity: str = NATIVE_PUBLIC_PROJECTION_PATCH_ID
    requested_episodes: int = 0
    completed_episodes: int = 0
    max_steps: int = 0
    decisions_observed: int = 0
    screen_counts: Counter[str] = field(default_factory=Counter)
    field_availability_counts: dict[str, Counter[str]] = field(
        default_factory=lambda: defaultdict(Counter)
    )
    screen_capability_matrix: dict[str, dict[str, Counter[str]]] = field(
        default_factory=lambda: defaultdict(lambda: defaultdict(Counter))
    )
    resource_availability_counts: dict[str, Counter[str]] = field(
        default_factory=lambda: defaultdict(Counter)
    )
    candidate_sources_by_screen: dict[str, Counter[str]] = field(
        default_factory=lambda: defaultdict(Counter)
    )
    candidate_parity_passes: int = 0
    checkpoint_passes: int = 0
    checkpoint_failures: int = 0
    coverage_gaps: list[str] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        """Whether all projection, parity, checkpoint, and run checks passed."""

        return not self.problems

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-safe current report shape for command/report consumers."""

        return {
            "report_schema_id": self.report_schema_id,
            "api_schema_id": self.api_schema_id,
            "external_base_commit": self.external_base_commit,
            "patch_identity": self.patch_identity,
            "requested_episodes": self.requested_episodes,
            "completed_episodes": self.completed_episodes,
            "max_steps": self.max_steps,
            "decisions_observed": self.decisions_observed,
            "screen_counts": dict(sorted(self.screen_counts.items())),
            "field_availability_counts": _counter_table(self.field_availability_counts),
            "screen_capability_matrix": _screen_capability_matrix(
                self.screen_capability_matrix
            ),
            "resource_availability_counts": _counter_table(
                self.resource_availability_counts
            ),
            "candidate_sources_by_screen": _counter_table(
                self.candidate_sources_by_screen
            ),
            "candidate_parity_passes": self.candidate_parity_passes,
            "checkpoint_passes": self.checkpoint_passes,
            "checkpoint_failures": self.checkpoint_failures,
            "coverage_gaps": list(self.coverage_gaps),
            "problems": list(self.problems),
            "passed": self.passed,
        }


class NativePublicProjectionAuditCollector:
    """Collect exactly one current native projection per executor decision."""

    def __init__(self, adapter: NativePublicProjectionAdapter) -> None:
        self._adapter = adapter
        self.report = NativePublicProjectionCapabilityReport()

    def observe_decision(
        self,
        snapshot: SimulatorSnapshot,
        actions: Sequence[SimulatorAction],
        *,
        seed: int | None,
        step_index: int,
    ) -> None:
        """Audit the current decision without replaying stored history entries."""

        label = _decision_label(seed, step_index)
        try:
            projection = self._adapter.public_projection(snapshot)
        except (RuntimeError, ValueError) as exc:
            self.report.problems.append(f"{label}: projection error: {exc}")
            return

        self.report.decisions_observed += 1
        self._record_projection_metadata(projection, label)
        self._record_candidate_parity(projection, actions, label)
        self._record_checkpoint_parity(projection, snapshot, label)

    def record_run_problems(self, *, seed: int | None, problems: Sequence[str]) -> None:
        """Propagate authoritative executor failures into the capability gate."""

        for problem in problems:
            self.report.problems.append(f"seed {seed}: run error: {problem}")

    def finalize(
        self, *, requested_episodes: int, completed_episodes: int, max_steps: int
    ) -> NativePublicProjectionCapabilityReport:
        """Attach run bounds and explicit, non-failing coverage gaps."""

        self.report.requested_episodes = requested_episodes
        self.report.completed_episodes = completed_episodes
        self.report.max_steps = max_steps
        self.report.coverage_gaps = sorted(
            KNOWN_SCREEN_STATES.difference(self.report.screen_counts)
        )
        if self.report.decisions_observed == 0:
            self.report.problems.append("audit observed no current decision screens")
        return self.report

    def _record_projection_metadata(
        self,
        projection: NativePublicProjection,
        label: str,
    ) -> None:
        if (
            projection.external_base_commit
            != NATIVE_PUBLIC_PROJECTION_EXTERNAL_BASE_COMMIT
        ):
            self.report.problems.append(
                f"{label}: projection external base commit "
                f"{projection.external_base_commit!r} does not match "
                f"{NATIVE_PUBLIC_PROJECTION_EXTERNAL_BASE_COMMIT!r}"
            )
        if projection.patch_identity != NATIVE_PUBLIC_PROJECTION_PATCH_ID:
            self.report.problems.append(
                f"{label}: projection patch identity {projection.patch_identity!r} "
                f"does not match {NATIVE_PUBLIC_PROJECTION_PATCH_ID!r}"
            )
        self.report.screen_counts[projection.screen_identity] += 1
        for field_name, field_value in projection.fields.items():
            self.report.field_availability_counts[field_name][
                field_value.availability
            ] += 1
            self.report.screen_capability_matrix[projection.screen_identity][
                field_name
            ][field_value.availability] += 1
        for field_name, field_value in projection.resource_fields.items():
            self.report.resource_availability_counts[field_name][
                field_value.availability
            ] += 1
        source = projection.candidate_source
        if source is None:
            self.report.problems.append(
                f"{label}: candidate_actions is not backed by a native source"
            )
        else:
            self.report.candidate_sources_by_screen[projection.screen_identity][
                source
            ] += 1

    def _record_candidate_parity(
        self,
        projection: NativePublicProjection,
        actions: Sequence[SimulatorAction],
        label: str,
    ) -> None:
        candidate_field = projection.fields["candidate_actions"]
        if candidate_field.availability != "available":
            self.report.problems.append(
                f"{label}: candidate_actions is {candidate_field.availability}, "
                "so adapter parity cannot be demonstrated"
            )
            return
        expected = action_identity_dicts_for_actions(actions)
        actual = projection.candidate_action_identities()
        if expected != actual:
            self.report.problems.append(
                f"{label}: candidate-action parity mismatch: "
                f"adapter={expected!r}, projection={actual!r}"
            )
            return
        self.report.candidate_parity_passes += 1

    def _record_checkpoint_parity(
        self,
        projection: NativePublicProjection,
        snapshot: SimulatorSnapshot,
        label: str,
    ) -> None:
        if not self._adapter.supports_checkpoint_restore:
            self.report.checkpoint_failures += 1
            self.report.problems.append(
                f"{label}: adapter does not support native checkpoint restore"
            )
            return
        try:
            checkpoint = self._adapter.capture_checkpoint(snapshot)
            restored = self._adapter.restore_checkpoint(checkpoint)
            restored_projection = self._adapter.public_projection(restored)
        except (RuntimeError, ValueError) as exc:
            self.report.checkpoint_failures += 1
            self.report.problems.append(f"{label}: checkpoint error: {exc}")
            return

        result = ProjectionCheckpointResult(
            screen_identity_matches=(
                projection.screen_identity == restored_projection.screen_identity
            ),
            projection_matches=(
                projection.canonical_payload == restored_projection.canonical_payload
            ),
            candidate_actions_match=(
                projection.candidate_action_identities()
                == restored_projection.candidate_action_identities()
            ),
        )
        if (
            result.screen_identity_matches
            and result.projection_matches
            and result.candidate_actions_match
        ):
            self.report.checkpoint_passes += 1
            return
        self.report.checkpoint_failures += 1
        self.report.problems.append(
            f"{label}: checkpoint projection mismatch "
            f"(screen={result.screen_identity_matches}, "
            f"projection={result.projection_matches}, "
            f"candidate_actions={result.candidate_actions_match})"
        )


def parse_native_public_projection(raw: object) -> NativePublicProjection:
    """Validate one raw native payload and retain only audit-safe information."""

    payload = _mapping(raw, "native public projection")
    schema_id = _required_string(payload, "schema_id", "native public projection")
    if schema_id != NATIVE_PUBLIC_PROJECTION_SCHEMA_ID:
        raise ValueError(f"unsupported native public projection schema {schema_id!r}")
    external_base_commit = _required_string(
        payload, "external_base_commit", "native public projection"
    )
    patch_identity = _required_string(
        payload, "patch_identity", "native public projection"
    )
    fields = {
        field_name: _parse_field(
            payload.get(field_name), f"native projection field {field_name}"
        )
        for field_name in PROJECTION_FIELD_NAMES
    }
    screen_field = fields["screen_identity"]
    if screen_field.availability != "available":
        raise ValueError("native projection screen_identity must be available")
    screen_value = _field_value(payload["screen_identity"], "screen_identity")
    if not isinstance(screen_value, str) or not screen_value:
        raise ValueError(
            "native projection screen_identity value must be a non-empty string"
        )

    persistent_resources_field = fields["persistent_resources"]
    if persistent_resources_field.availability == "available":
        resources_value = _field_value(
            payload["persistent_resources"], "persistent_resources"
        )
        resource_values = _mapping(resources_value, "persistent_resources value")
        resource_fields = {
            field_name: _parse_field(
                resource_values.get(field_name),
                f"persistent resource field {field_name}",
            )
            for field_name in RESOURCE_FIELD_NAMES
        }
    else:
        resource_fields = {
            field_name: NativeProjectionField(
                availability=persistent_resources_field.availability,
                reason=persistent_resources_field.reason,
            )
            for field_name in RESOURCE_FIELD_NAMES
        }

    candidates: tuple[NativeProjectionAction, ...] = ()
    if fields["candidate_actions"].availability == "available":
        candidate_values = _field_value(
            payload["candidate_actions"], "candidate_actions"
        )
        if not isinstance(candidate_values, Sequence) or isinstance(
            candidate_values, (str, bytes)
        ):
            raise ValueError("candidate_actions value must be a list")
        candidates = tuple(
            _parse_candidate_action(value, index)
            for index, value in enumerate(candidate_values)
        )

    return NativePublicProjection(
        schema_id=schema_id,
        external_base_commit=external_base_commit,
        patch_identity=patch_identity,
        screen_identity=screen_value,
        fields=fields,
        resource_fields=resource_fields,
        candidate_actions=candidates,
        canonical_payload=_canonical_payload(payload),
    )


def format_native_public_projection_capability_report(
    report: NativePublicProjectionCapabilityReport,
) -> str:
    """Format the T014 audit evidence for stderr and pull-request reporting."""

    lines = [
        "Native public-projection capability audit",
        f"report schema: {report.report_schema_id}",
        f"native API schema: {report.api_schema_id}",
        f"external base commit: {report.external_base_commit}",
        f"patch identity: {report.patch_identity}",
        f"episodes: {report.completed_episodes}/{report.requested_episodes}",
        f"max steps per episode: {report.max_steps}",
        f"current decision screens observed: {report.decisions_observed}",
        f"candidate-action parity passes: {report.candidate_parity_passes}",
        f"checkpoint projection passes: {report.checkpoint_passes}",
        f"checkpoint projection failures: {report.checkpoint_failures}",
        f"audit passed: {_bool_label(report.passed)}",
    ]
    _append_counter(lines, "observed screen counts", report.screen_counts)
    _append_counter_table(lines, "field availability", report.field_availability_counts)
    _append_screen_capability_matrix(
        lines,
        "observed screen capability matrix",
        report.screen_capability_matrix,
    )
    _append_counter_table(
        lines, "persistent-resource availability", report.resource_availability_counts
    )
    _append_counter_table(
        lines, "candidate-action sources by screen", report.candidate_sources_by_screen
    )
    _append_values(lines, "coverage gaps", report.coverage_gaps)
    _append_values(lines, "problems", report.problems)
    return "\n".join(lines)


def _parse_field(value: object, label: str) -> NativeProjectionField:
    field = _mapping(value, label)
    availability = _required_string(field, "availability", label)
    if availability not in PROJECTION_AVAILABILITY_VALUES:
        raise ValueError(f"{label} has unsupported availability {availability!r}")
    if availability == "available":
        if "value" not in field:
            raise ValueError(f"{label} is available but has no value")
        return NativeProjectionField(
            availability=availability,
            source=_required_string(field, "source", label),
        )
    return NativeProjectionField(
        availability=availability,
        reason=_required_string(field, "reason", label),
    )


def _parse_candidate_action(value: object, index: int) -> NativeProjectionAction:
    action = _mapping(value, f"candidate action {index}")
    return NativeProjectionAction(
        scope=_required_string(action, "scope", f"candidate action {index}"),
        bits=_required_int(action, "bits", f"candidate action {index}"),
        kind=_required_string(action, "kind", f"candidate action {index}"),
        label=_required_string(action, "label", f"candidate action {index}"),
        idx1=_required_int(action, "idx1", f"candidate action {index}"),
        idx2=_required_int(action, "idx2", f"candidate action {index}"),
        idx3=_required_int(action, "idx3", f"candidate action {index}"),
    )


def _field_value(value: object, label: str) -> object:
    field = _mapping(value, f"native projection field {label}")
    if "value" not in field:
        raise ValueError(f"native projection field {label} has no value")
    return field["value"]


def _mapping(value: object, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} must be an object")
    return value


def _required_string(data: Mapping[str, Any], key: str, label: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"{label} {key} must be a non-empty string")
    return value


def _required_int(data: Mapping[str, Any], key: str, label: str) -> int:
    value = data.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{label} {key} must be an integer")
    return value


def _canonical_payload(payload: Mapping[str, Any]) -> str:
    try:
        return json.dumps(
            payload,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    except (TypeError, ValueError) as exc:
        raise ValueError(
            "native public projection must contain only JSON-compatible values"
        ) from exc


def _counter_table(
    values: Mapping[str, Counter[str]],
) -> dict[str, dict[str, int]]:
    return {
        key: dict(sorted(counter.items())) for key, counter in sorted(values.items())
    }


def _screen_capability_matrix(
    values: Mapping[str, Mapping[str, Counter[str]]],
) -> dict[str, dict[str, dict[str, int]]]:
    return {screen: _counter_table(fields) for screen, fields in sorted(values.items())}


def _decision_label(seed: int | None, step_index: int) -> str:
    return f"seed {seed} step {step_index}"


def _append_counter(lines: list[str], title: str, values: Counter[str]) -> None:
    lines.append(f"{title}:")
    if not values:
        lines.append("  (none)")
        return
    for key in sorted(values):
        lines.append(f"  {key}: {values[key]}")


def _append_counter_table(
    lines: list[str],
    title: str,
    values: Mapping[str, Counter[str]],
) -> None:
    lines.append(f"{title}:")
    if not values:
        lines.append("  (none)")
        return
    for key in sorted(values):
        counts = ", ".join(
            f"{name}={count}" for name, count in sorted(values[key].items())
        )
        lines.append(f"  {key}: {counts}")


def _append_screen_capability_matrix(
    lines: list[str],
    title: str,
    values: Mapping[str, Mapping[str, Counter[str]]],
) -> None:
    lines.append(f"{title}:")
    if not values:
        lines.append("  (none)")
        return
    for screen, fields in sorted(values.items()):
        capabilities = ", ".join(
            f"{field}="
            + "/".join(
                f"{availability}:{count}"
                for availability, count in sorted(counts.items())
            )
            for field, counts in sorted(fields.items())
        )
        lines.append(f"  {screen}: {capabilities}")


def _append_values(lines: list[str], title: str, values: Sequence[str]) -> None:
    lines.append(f"{title}:")
    if not values:
        lines.append("  (none)")
        return
    lines.extend(f"  {value}" for value in values)


def _bool_label(value: bool) -> str:
    return "yes" if value else "no"
