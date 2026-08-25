"""Concrete framework-neutral online policies and scorer adapters."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import random

from sts_combat_rl.sim.action_space import DEFAULT_PREFERRED_ACTION_KINDS
from sts_combat_rl.sim.policy_contract import (
    ActionScorer,
    DecisionContext,
    PolicyDecision,
    _finite_score,
    _valid_eligible_indices,
)


@dataclass(frozen=True)
class FirstEligiblePolicy:
    name: str = "first_eligible"

    @property
    def provenance_config(self) -> Mapping[str, object]:
        return {}

    def select_action(self, context: DecisionContext) -> PolicyDecision:
        return PolicyDecision(
            legal_action_index=_valid_eligible_indices(context)[0],
            reason="first_eligible",
        )


@dataclass(frozen=True)
class PreferredKindPolicy:
    preferred_kinds: tuple[str, ...] = DEFAULT_PREFERRED_ACTION_KINDS
    name: str = "preferred_kind"

    @property
    def provenance_config(self) -> Mapping[str, object]:
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


class RandomEligiblePolicy:
    name = "random_eligible"

    def __init__(self, seed: int | None = None) -> None:
        self._seed = seed
        self._rng = random.Random(seed)

    @property
    def provenance_config(self) -> Mapping[str, object]:
        return {"seed": self._seed, "reproducible": False}

    def select_action(self, context: DecisionContext) -> PolicyDecision:
        return PolicyDecision(
            legal_action_index=self._rng.choice(_valid_eligible_indices(context)),
            reason="random_eligible",
        )


@dataclass(frozen=True)
class ScoredActionPolicy:
    scorer: ActionScorer
    name: str = "scored_action"

    @property
    def provenance_config(self) -> Mapping[str, object]:
        scorer_config = getattr(self.scorer, "provenance_config", None)
        if scorer_config is None:
            raise ValueError(
                f"scorer {self.scorer.name!r} does not expose provenance_config; "
                "all scorers used in controlled runs must publish their "
                "behavior-changing settings for reproducible identity"
            )
        if not isinstance(scorer_config, Mapping):
            raise ValueError(
                f"scorer {self.scorer.name!r}.provenance_config must be a mapping, "
                f"got {type(scorer_config).__name__}"
            )
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
