"""Framework-neutral policy selection over decision batches.

This module defines the smallest policy/model boundary needed before training:
given one variable-action decision example, choose a legal-action index. It
does not implement RL, a trainer, a Gymnasium environment, or game mechanics.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
import math
import random
from typing import Any, Protocol

from sts_combat_rl.sim.action_space import DEFAULT_PREFERRED_ACTION_KINDS
from sts_combat_rl.sim.batching import DecisionBatch, DecisionExample


@dataclass(frozen=True)
class DecisionContext:
    """Policy input without rollout labels or training-framework assumptions."""

    screen_state: str
    snapshot_features: list[float]
    legal_action_features: list[list[float]]
    legal_action_kinds: list[str]
    eligible_action_indices: list[int]


@dataclass(frozen=True)
class PolicyDecision:
    """One policy choice expressed as an index into legal actions."""

    legal_action_index: int
    score: float | None = None
    reason: str = ""


@dataclass(frozen=True)
class PolicySelection:
    """One evaluated policy choice with action-kind metadata."""

    example_index: int
    rollout_index: int
    step_index: int
    selected_action_index: int
    selected_action_kind: str
    rollout_action_index: int
    rollout_action_kind: str
    score: float | None = None
    reason: str = ""


@dataclass(frozen=True)
class PolicyEvaluation:
    """Summary of applying a policy to a framework-neutral batch."""

    policy_name: str
    examples: int
    selections: list[PolicySelection] = field(default_factory=list)
    rollout_agreement: int = 0
    problems: list[str] = field(default_factory=list)


class DecisionPolicy(Protocol):
    """Policy interface for variable-action simulator decision examples."""

    name: str

    @property
    def provenance_config(self) -> Mapping[str, Any]:
        """Behavior-changing config this policy should publish as provenance.

        A short policy name is not sufficient provenance, so each policy exposes
        the settings that change its behavior (seed, preferred kinds, scorer
        identity, ...). The ``OnlineController`` adapters fold this into the
        controller provenance identity so two policies differing only in seed
        get different identities. The default for policies that do not override
        is an empty mapping.
        """

    def select_action(self, context: DecisionContext) -> PolicyDecision:
        """Select one legal-action index for ``context``."""


class ActionScorer(Protocol):
    """Scorer interface for future model wrappers over variable actions."""

    name: str

    @property
    def provenance_config(self) -> Mapping[str, Any]:
        """Behavior-changing config this scorer should publish as provenance.

        Two scorers with different weights must produce different provenance
        so that controllers wrapping them get different identities. The default
        returns an empty mapping; concrete scorers must override this to
        include all behavior-distinguishing settings.
        """

    def score_actions(self, context: DecisionContext) -> Sequence[float]:
        """Return one score for each legal action in ``context``."""


@dataclass(frozen=True)
class FirstEligiblePolicy:
    """Baseline policy that selects the first currently eligible action."""

    name: str = "first_eligible"

    @property
    def provenance_config(self) -> Mapping[str, Any]:
        return {}

    def select_action(self, context: DecisionContext) -> PolicyDecision:
        return PolicyDecision(
            legal_action_index=_valid_eligible_indices(context)[0],
            reason="first_eligible",
        )


@dataclass(frozen=True)
class PreferredKindPolicy:
    """Baseline policy that prefers useful action kinds, then first eligible."""

    preferred_kinds: tuple[str, ...] = DEFAULT_PREFERRED_ACTION_KINDS
    name: str = "preferred_kind"

    @property
    def provenance_config(self) -> Mapping[str, Any]:
        return {"preferred_kinds": tuple(self.preferred_kinds)}

    def select_action(self, context: DecisionContext) -> PolicyDecision:
        eligible_indices = _valid_eligible_indices(context)
        for preferred_kind in self.preferred_kinds:
            for index in eligible_indices:
                if context.legal_action_kinds[index] == preferred_kind:
                    return PolicyDecision(
                        legal_action_index=index,
                        reason=f"preferred_kind:{preferred_kind}",
                    )

        return PolicyDecision(
            legal_action_index=eligible_indices[0],
            reason="preferred_kind:fallback_first_eligible",
        )


@dataclass(frozen=True)
class ReplayChosenPolicy:
    """Policy that replays the rollout collector's recorded choice."""

    name: str = "replay_chosen"

    @property
    def provenance_config(self) -> Mapping[str, Any]:
        return {}

    def select_action(
        self,
        example: DecisionContext | DecisionExample,
    ) -> PolicyDecision:
        if not isinstance(example, DecisionExample):
            raise ValueError("replay_chosen requires a rollout decision example")
        return PolicyDecision(
            legal_action_index=example.chosen_action_index,
            reason="rollout_choice",
        )


class RandomEligiblePolicy:
    """Seeded random baseline over eligible legal-action indices."""

    name = "random_eligible"

    def __init__(self, seed: int | None = None) -> None:
        self._seed = seed
        self._rng = random.Random(seed)

    @property
    def provenance_config(self) -> Mapping[str, Any]:
        return {"seed": self._seed}

    def select_action(self, context: DecisionContext) -> PolicyDecision:
        return PolicyDecision(
            legal_action_index=self._rng.choice(_valid_eligible_indices(context)),
            reason="random_eligible",
        )


@dataclass(frozen=True)
class ScoredActionPolicy:
    """Policy wrapper that chooses the highest-scored eligible action."""

    scorer: ActionScorer
    name: str = "scored_action"

    @property
    def provenance_config(self) -> Mapping[str, Any]:
        scorer_config = getattr(self.scorer, "provenance_config", {})
        if not isinstance(scorer_config, Mapping):
            scorer_config = {}
        return {"scorer_name": self.scorer.name, "scorer_config": dict(scorer_config)}

    def select_action(self, context: DecisionContext) -> PolicyDecision:
        scores = [float(score) for score in self.scorer.score_actions(context)]
        selected_index = choose_highest_scored_eligible_index(context, scores)
        return PolicyDecision(
            legal_action_index=selected_index,
            score=scores[selected_index],
            reason=f"{self.scorer.name}:max_eligible_score",
        )


def choose_highest_scored_eligible_index(
    context: DecisionContext,
    scores: Sequence[float],
) -> int:
    """Return the eligible legal-action index with the highest score."""

    legal_count = len(context.legal_action_features)
    if len(scores) != legal_count:
        raise ValueError(
            f"score count {len(scores)} does not match {legal_count} legal actions"
        )

    eligible_indices = _valid_eligible_indices(context)
    best_index = eligible_indices[0]
    best_score = _finite_score(scores[best_index], best_index)
    for index in eligible_indices[1:]:
        score = _finite_score(scores[index], index)
        if score > best_score:
            best_index = index
            best_score = score
    return best_index


def decision_context_from_example(example: DecisionExample) -> DecisionContext:
    """Drop rollout labels from a decision example for online-style policies."""

    return DecisionContext(
        screen_state=example.screen_state,
        snapshot_features=example.snapshot_features,
        legal_action_features=example.legal_action_features,
        legal_action_kinds=example.legal_action_kinds,
        eligible_action_indices=example.eligible_action_indices,
    )


def evaluate_decision_policy(
    batch: DecisionBatch,
    policy: DecisionPolicy,
    *,
    require_eligible: bool = True,
) -> PolicyEvaluation:
    """Apply ``policy`` to a batch and validate selected legal-action indices."""

    selections: list[PolicySelection] = []
    problems = [f"batch: {problem}" for problem in batch.problems]
    rollout_agreement = 0

    for example_index, example in enumerate(batch.examples):
        try:
            decision = policy.select_action(example)
        except ValueError as exc:
            problems.append(f"example {example_index}: {exc}")
            continue

        selected_kind = _action_kind(example, decision.legal_action_index)
        selection_problems = _selection_problems(
            example_index,
            example,
            decision.legal_action_index,
            require_eligible,
        )
        problems.extend(selection_problems)
        matches_rollout = decision.legal_action_index == example.chosen_action_index
        if matches_rollout and not selection_problems:
            rollout_agreement += 1

        selections.append(
            PolicySelection(
                example_index=example_index,
                rollout_index=example.rollout_index,
                step_index=example.step_index,
                selected_action_index=decision.legal_action_index,
                selected_action_kind=selected_kind,
                rollout_action_index=example.chosen_action_index,
                rollout_action_kind=example.chosen_action_kind,
                score=decision.score,
                reason=decision.reason,
            )
        )

    return PolicyEvaluation(
        policy_name=policy.name,
        examples=len(batch.examples),
        selections=selections,
        rollout_agreement=rollout_agreement,
        problems=problems,
    )


def format_policy_evaluation_report(evaluation: PolicyEvaluation) -> str:
    """Format a compact policy-selection smoke report for stderr."""

    selected_action_kinds = Counter(
        selection.selected_action_kind for selection in evaluation.selections
    )
    rollout_action_kinds = Counter(
        selection.rollout_action_kind for selection in evaluation.selections
    )
    selection_reasons = Counter(selection.reason for selection in evaluation.selections)

    lines = [
        "Policy selection smoke summary",
        f"policy: {evaluation.policy_name}",
        f"examples: {evaluation.examples}",
        f"selections: {len(evaluation.selections)}",
        f"agreement with rollout: {evaluation.rollout_agreement}/{evaluation.examples}",
    ]
    _append_counter(lines, "selected action kinds", selected_action_kinds)
    _append_counter(lines, "rollout action kinds", rollout_action_kinds)
    _append_counter(lines, "selection reasons", selection_reasons)

    lines.append("problems:")
    if evaluation.problems:
        lines.extend(f"  {problem}" for problem in evaluation.problems)
    else:
        lines.append("  (none)")

    return "\n".join(lines)


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


def _selection_problems(
    example_index: int,
    example: DecisionExample,
    selected_index: int,
    require_eligible: bool,
) -> list[str]:
    legal_count = len(example.legal_action_features)
    problems: list[str] = []
    if selected_index < 0 or selected_index >= legal_count:
        problems.append(
            f"example {example_index}: selected action index {selected_index} "
            f"outside {legal_count} legal actions"
        )
        return problems

    if require_eligible and selected_index not in example.eligible_action_indices:
        problems.append(
            f"example {example_index}: selected action index {selected_index} "
            "is not eligible under the active action space"
        )
    return problems


def _action_kind(example: DecisionExample, selected_index: int) -> str:
    if selected_index < 0 or selected_index >= len(example.legal_action_kinds):
        return "(invalid)"
    return example.legal_action_kinds[selected_index]


def _finite_score(score: float, action_index: int) -> float:
    if not math.isfinite(float(score)):
        raise ValueError(f"score for action {action_index} is not finite")
    return float(score)


def _append_counter(lines: list[str], title: str, counter: Counter[str]) -> None:
    lines.append(f"{title}:")
    if not counter:
        lines.append("  (none)")
        return

    for key, count in counter.most_common():
        lines.append(f"  {key}: {count}")
