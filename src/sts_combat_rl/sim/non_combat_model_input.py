"""Frozen public input contract for the T065 non-combat ranker.

The T065 model intentionally composes the two existing public encoders instead
of creating a second feature vocabulary.  This module owns only the join,
strict size checks, and the small amount of status plumbing needed when a
``DecisionContext`` is used by an online policy.

No simulator object, native checkpoint, future state, or expert decision is
accepted by this boundary.  The optional ``public_context_status`` argument is
explicit because ``DecisionContext`` predates the T033 status field; when it is
omitted, the status is derived only from the explicit T015 projection marker.
An otherwise non-empty context is never guessed to be available.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
import math
from typing import Any

from sts_combat_rl.sim.features import (
    IDENTITY_VOCABULARY_VERSION,
    TACTICAL_FEATURE_SCHEMA_ID,
    TACTICAL_FEATURE_SCHEMA_VERSION,
    encode_lightspeed_battle_snapshot,
    encode_simulator_actions,
)
from sts_combat_rl.sim.policy_contract import DecisionContext
from sts_combat_rl.sim.public_context_artifacts import (
    PUBLIC_CONTEXT_AVAILABLE,
    PUBLIC_CONTEXT_LEGACY_UNAVAILABLE,
    PUBLIC_CONTEXT_STATUS_VALUES,
)
from sts_combat_rl.sim.public_context_model_input import (
    PUBLIC_CONTEXT_MODEL_INPUT_FEATURE_NAMES,
    PUBLIC_CONTEXT_MODEL_INPUT_FEATURE_SIZE,
    PUBLIC_CONTEXT_MODEL_INPUT_SCHEMA_ID,
    PUBLIC_CONTEXT_MODEL_INPUT_SCHEMA_VERSION,
    encode_public_context_model_input,
)


NON_COMBAT_MODEL_INPUT_SCHEMA_ID = "non-combat-model-input-v1"
NON_COMBAT_MODEL_INPUT_SCHEMA_VERSION = 1
NON_COMBAT_SNAPSHOT_FEATURE_SIZE = 4634
NON_COMBAT_CONTEXT_FEATURE_SIZE = PUBLIC_CONTEXT_MODEL_INPUT_FEATURE_SIZE
NON_COMBAT_STATE_FEATURE_SIZE = (
    NON_COMBAT_SNAPSHOT_FEATURE_SIZE + NON_COMBAT_CONTEXT_FEATURE_SIZE
)
NON_COMBAT_ACTION_FEATURE_SIZE = 92


@dataclass(frozen=True)
class NonCombatModelInput:
    """One validated state and its aligned legal-action rows."""

    state_features: tuple[float, ...]
    action_features: tuple[tuple[float, ...], ...]
    eligible_action_indices: tuple[int, ...]
    public_context_status: str
    context_missingness_summary: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": NON_COMBAT_MODEL_INPUT_SCHEMA_ID,
            "schema_version": NON_COMBAT_MODEL_INPUT_SCHEMA_VERSION,
            "state_features": list(self.state_features),
            "action_features": [list(row) for row in self.action_features],
            "eligible_action_indices": list(self.eligible_action_indices),
            "public_context_status": self.public_context_status,
            "context_missingness_summary": dict(self.context_missingness_summary),
        }


def non_combat_model_input_schema() -> dict[str, Any]:
    """Return the complete immutable schema identity used in artifacts."""

    return {
        "schema_id": NON_COMBAT_MODEL_INPUT_SCHEMA_ID,
        "schema_version": NON_COMBAT_MODEL_INPUT_SCHEMA_VERSION,
        "tactical_feature_schema_id": TACTICAL_FEATURE_SCHEMA_ID,
        "tactical_feature_schema_version": TACTICAL_FEATURE_SCHEMA_VERSION,
        "identity_vocabulary_version": IDENTITY_VOCABULARY_VERSION,
        "public_context_feature_schema_id": PUBLIC_CONTEXT_MODEL_INPUT_SCHEMA_ID,
        "public_context_feature_schema_version": (
            PUBLIC_CONTEXT_MODEL_INPUT_SCHEMA_VERSION
        ),
        "snapshot_feature_size": NON_COMBAT_SNAPSHOT_FEATURE_SIZE,
        "public_context_feature_size": NON_COMBAT_CONTEXT_FEATURE_SIZE,
        "state_feature_size": NON_COMBAT_STATE_FEATURE_SIZE,
        "action_feature_size": NON_COMBAT_ACTION_FEATURE_SIZE,
        "public_context_feature_names": list(PUBLIC_CONTEXT_MODEL_INPUT_FEATURE_NAMES),
    }


def infer_public_context_status(context: DecisionContext) -> str:
    """Infer status only from an explicit T015 marker.

    The canonical executor places ``projection_status`` in every public
    context.  A missing marker is an explicit legacy/unavailable condition,
    even when a caller supplied a partial dictionary.  This prevents a model
    from treating an unproven context as available by accident.
    """

    value = context.public_run_context.get("public_context_status")
    if value in PUBLIC_CONTEXT_STATUS_VALUES:
        return str(value)
    projection_status = context.public_run_context.get("projection_status")
    if projection_status == PUBLIC_CONTEXT_AVAILABLE:
        return PUBLIC_CONTEXT_AVAILABLE
    if projection_status in {"unavailable", PUBLIC_CONTEXT_LEGACY_UNAVAILABLE}:
        return PUBLIC_CONTEXT_LEGACY_UNAVAILABLE
    return PUBLIC_CONTEXT_LEGACY_UNAVAILABLE


def _t033_context_with_screen_aliases(
    public_run_context: Mapping[str, Any],
) -> Mapping[str, Any]:
    """Adapt simulator screen enum aliases to the existing T033 categories."""

    aliases = {
        "MAP": "map",
        "MAP_SCREEN": "map",
        "REST": "rest",
        "REST_ROOM": "rest",
        "REWARDS": "rewards",
        "TREASURE": "treasure",
        "TREASURE_ROOM": "treasure",
    }
    current = public_run_context.get("current")
    if not isinstance(current, Mapping):
        return public_run_context
    screen = current.get("screen")
    if not isinstance(screen, Mapping) or screen.get("availability") != "available":
        return public_run_context
    raw_value = screen.get("value")
    if not isinstance(raw_value, str):
        return public_run_context
    normalized = aliases.get(raw_value.strip().upper())
    if normalized is None or normalized == raw_value:
        return public_run_context
    adapted_screen = dict(screen)
    adapted_screen["value"] = normalized
    adapted_current = dict(current)
    adapted_current["screen"] = adapted_screen
    adapted_context = dict(public_run_context)
    adapted_context["current"] = adapted_current
    return adapted_context


def encode_non_combat_decision_context(
    context: DecisionContext,
    *,
    public_context_status: str | None = None,
) -> NonCombatModelInput:
    """Encode one canonical decision context under the exact T065 join."""

    status = (
        infer_public_context_status(context)
        if public_context_status is None
        else public_context_status
    )
    if status not in PUBLIC_CONTEXT_STATUS_VALUES:
        raise ValueError(
            "non-combat public_context_status must be one of "
            f"{sorted(PUBLIC_CONTEXT_STATUS_VALUES)!r}"
        )
    if len(context.snapshot_features) != NON_COMBAT_SNAPSHOT_FEATURE_SIZE:
        raise ValueError(
            "non-combat snapshot feature size "
            f"{len(context.snapshot_features)} does not match "
            f"{NON_COMBAT_SNAPSHOT_FEATURE_SIZE}"
        )
    if context.tactical_feature_schema_id != TACTICAL_FEATURE_SCHEMA_ID:
        raise ValueError(
            "non-combat tactical feature schema id is "
            f"{context.tactical_feature_schema_id!r}, expected "
            f"{TACTICAL_FEATURE_SCHEMA_ID!r}"
        )
    encoded_context = encode_public_context_model_input(
        public_context_status=status,
        public_run_context=_t033_context_with_screen_aliases(
            context.public_run_context
        ),
    )
    if encoded_context.problems:
        raise ValueError("; ".join(encoded_context.problems))
    state = tuple(
        _finite_values(
            [*context.snapshot_features, *encoded_context.public_context_features],
            label="non-combat state",
        )
    )
    if len(state) != NON_COMBAT_STATE_FEATURE_SIZE:
        raise ValueError(
            f"non-combat state feature size {len(state)} does not match "
            f"{NON_COMBAT_STATE_FEATURE_SIZE}"
        )

    action_rows = tuple(
        tuple(_finite_values(row, label=f"non-combat action {index}"))
        for index, row in enumerate(context.legal_action_features)
    )
    for index, row in enumerate(action_rows):
        if len(row) != NON_COMBAT_ACTION_FEATURE_SIZE:
            raise ValueError(
                f"non-combat action feature size for row {index} is {len(row)}, "
                f"expected {NON_COMBAT_ACTION_FEATURE_SIZE}"
            )
    eligible = tuple(int(index) for index in context.eligible_action_indices)
    if not eligible:
        raise ValueError("non-combat context has no eligible legal actions")
    if any(index < 0 or index >= len(action_rows) for index in eligible):
        raise ValueError("non-combat eligible action index is outside legal actions")
    if len(set(eligible)) != len(eligible):
        raise ValueError("non-combat eligible action indices contain duplicates")
    return NonCombatModelInput(
        state_features=state,
        action_features=action_rows,
        eligible_action_indices=eligible,
        public_context_status=status,
        context_missingness_summary=dict(
            encoded_context.public_context_missingness_summary
        ),
    )


def encode_non_combat_raw_context(
    *,
    snapshot_features: Sequence[float],
    legal_action_features: Sequence[Sequence[float]],
    eligible_action_indices: Sequence[int],
    public_context_status: str,
    public_run_context: Mapping[str, Any],
) -> NonCombatModelInput:
    """Encode already-separated public rows for artifact/replay tooling."""

    context = DecisionContext(
        screen_state="(non-combat)",
        snapshot_features=list(snapshot_features),
        legal_action_features=[list(row) for row in legal_action_features],
        legal_action_kinds=["unknown"] * len(legal_action_features),
        eligible_action_indices=list(eligible_action_indices),
        tactical_feature_schema_id=TACTICAL_FEATURE_SCHEMA_ID,
        public_run_context=dict(public_run_context),
    )
    return encode_non_combat_decision_context(
        context,
        public_context_status=public_context_status,
    )


def encode_non_combat_snapshot_and_actions(
    *,
    raw_snapshot: Mapping[str, Any],
    public_run_context: Mapping[str, Any],
    actions: Sequence[Any],
    eligible_action_indices: Sequence[int],
    public_context_status: str = PUBLIC_CONTEXT_AVAILABLE,
) -> NonCombatModelInput:
    """Build the exact input from public raw snapshot/action contracts."""

    snapshot_features = encode_lightspeed_battle_snapshot(raw_snapshot)
    action_features = encode_simulator_actions(actions, raw_snapshot)
    return encode_non_combat_raw_context(
        snapshot_features=snapshot_features,
        legal_action_features=action_features,
        eligible_action_indices=eligible_action_indices,
        public_context_status=public_context_status,
        public_run_context=public_run_context,
    )


def validate_non_combat_model_input_schema(metadata: Mapping[str, Any]) -> list[str]:
    """Return strict schema mismatches without guessing legacy fields."""

    expected = non_combat_model_input_schema()
    problems: list[str] = []
    for key, expected_value in expected.items():
        actual = metadata.get(key)
        if key == "public_context_feature_names":
            actual = list(actual) if isinstance(actual, Sequence) else actual
        if actual != expected_value:
            problems.append(
                f"{key}={actual!r} does not match frozen value {expected_value!r}"
            )
    return problems


def validate_non_combat_model_input(value: NonCombatModelInput) -> list[str]:
    """Validate row dimensions and finiteness before training or inference."""

    problems: list[str] = []
    if len(value.state_features) != NON_COMBAT_STATE_FEATURE_SIZE:
        problems.append("state feature size mismatch")
    if not _all_finite(value.state_features):
        problems.append("state features contain non-finite values")
    if not value.action_features:
        problems.append("legal action rows are empty")
    for index, row in enumerate(value.action_features):
        if len(row) != NON_COMBAT_ACTION_FEATURE_SIZE:
            problems.append(f"action row {index} feature size mismatch")
        elif not _all_finite(row):
            problems.append(f"action row {index} contains non-finite values")
    if not value.eligible_action_indices:
        problems.append("eligible action indices are empty")
    elif any(
        index < 0 or index >= len(value.action_features)
        for index in value.eligible_action_indices
    ):
        problems.append("eligible action index is outside legal action rows")
    if value.public_context_status not in PUBLIC_CONTEXT_STATUS_VALUES:
        problems.append("public context status is unsupported")
    return problems


def _finite_values(values: Sequence[float], *, label: str) -> list[float]:
    converted = [float(value) for value in values]
    if any(not math.isfinite(value) for value in converted):
        raise ValueError(f"{label} contains non-finite values")
    return converted


def _all_finite(values: Sequence[float]) -> bool:
    return all(math.isfinite(float(value)) for value in values)
