"""Framework-neutral online decision and policy contracts."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(frozen=True)
class DecisionContext:
    screen_state: str
    snapshot_features: list[float]
    legal_action_features: list[list[float]]
    legal_action_kinds: list[str]
    eligible_action_indices: list[int]
    snapshot_metadata: Mapping[str, Any] = field(default_factory=dict)
    legal_action_metadata: list[Mapping[str, Any]] = field(default_factory=list)
    tactical_state: Mapping[str, Any] = field(default_factory=dict)
    tactical_legal_actions: list[Mapping[str, Any]] = field(default_factory=list)
    tactical_feature_schema_id: str = "public-tactical-v2"
    public_run_context: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PolicyDecision:
    legal_action_index: int
    score: float | None = None
    reason: str = ""


class DecisionPolicy(Protocol):
    name: str

    @property
    def provenance_config(self) -> Mapping[str, Any]: ...

    def select_action(self, context: DecisionContext) -> PolicyDecision: ...


class ActionScorer(Protocol):
    name: str

    @property
    def provenance_config(self) -> Mapping[str, Any]: ...

    def score_actions(self, context: DecisionContext) -> Sequence[float]: ...


def _valid_eligible_indices(context: DecisionContext) -> list[int]:
    legal_count = len(context.legal_action_features)
    if not context.eligible_action_indices:
        raise ValueError("example has no eligible legal actions")

    invalid = [
        index
        for index in context.eligible_action_indices
        if index < 0 or index >= legal_count
    ]
    if invalid:
        raise ValueError(
            f"eligible action index {invalid[0]} outside {legal_count} legal actions"
        )
    return list(context.eligible_action_indices)


def _finite_score(score: float, action_index: int) -> float:
    if not math.isfinite(float(score)):
        raise ValueError(f"score for action {action_index} is not finite")
    return float(score)
