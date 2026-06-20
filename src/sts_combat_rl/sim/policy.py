"""Framework-neutral policy selection over decision batches.

This module defines the smallest policy/model boundary needed before training:
given one variable-action decision example, choose a legal-action index. It
does not implement RL, a trainer, a Gymnasium environment, or game mechanics.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
import hashlib
import json
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
    snapshot_metadata: Mapping[str, Any] = field(default_factory=dict)
    legal_action_metadata: list[Mapping[str, Any]] = field(default_factory=list)


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
    """Seeded random baseline over eligible legal-action indices.

    Provenance marks this policy non-reproducible. Although the seed is
    published, the policy object's RNG advances on every decision and the
    initial seed alone is not enough to reconstruct the controller's starting
    RNG state for a run that begins mid-sequence (for example a battle policy
    reused across a multi-seed sweep). For T002's provenance contract a
    controller is reproducible only if its published provenance is sufficient
    to reconstruct the controller's starting state; serializing the full Python
    RNG state (or an equivalent deterministic per-run sequence contract) is
    deferred to a later task. The seed is still recorded so the provenance
    identity distinguishes differently-seeded policies.
    """

    name = "random_eligible"

    def __init__(self, seed: int | None = None) -> None:
        self._seed = seed
        self._rng = random.Random(seed)

    @property
    def provenance_config(self) -> Mapping[str, Any]:
        return {"seed": self._seed, "reproducible": False}

    def select_action(self, context: DecisionContext) -> PolicyDecision:
        return PolicyDecision(
            legal_action_index=self._rng.choice(_valid_eligible_indices(context)),
            reason="random_eligible",
        )


NON_COMBAT_DRIVER_V1_SCREEN_CATEGORY_RELATIVE_WEIGHTS: dict[str, dict[str, float]] = {
    "REST_ROOM": {
        "rest_heal": 0.30,
        "rest_upgrade": 0.70,
        "rest_other": 0.10,
    },
    "SHOP_ROOM": {
        "shop_card_remove": 0.25,
        "shop_reward_card": 0.25,
        "shop_reward_potion": 0.15,
        "shop_reward_relic": 0.25,
        "shop_skip": 0.10,
        "game_potion_use": 0.05,
    },
    "REWARDS": {
        "reward_card": 1.00,
        "reward_gold": 1.00,
        "reward_key": 0.25,
        "reward_potion": 1.00,
        "ordinary_relic_take": 1.00,
        "ordinary_relic_skip": 0.25,
        "skip": 0.25,
        "game_potion_use": 0.05,
    },
    "BOSS_RELIC_REWARDS": {
        "boss_relic_take": 0.95,
        "boss_relic_skip": 0.05,
    },
    "TREASURE_ROOM": {
        "treasure_open": 0.90,
        "treasure_leave": 0.10,
    },
}
"""Relative category weights for the ``stochastic_non_combat_v1`` contract.

At each decision the driver normalizes the positive weights only across the
currently legal categories, then samples uniformly within the selected
category. The values are therefore not unconditional probabilities.
"""

NON_COMBAT_DRIVER_V1_GLOBAL_CATEGORY_RELATIVE_WEIGHTS: dict[str, float] = {
    "game_potion_use": 0.05,
    "game_potion_discard": 0.01,
}

NON_COMBAT_DRIVER_V1_CONDITIONAL_CATEGORY_RELATIVE_WEIGHTS: dict[
    str, dict[str, dict[str, object]]
] = {
    "REWARDS": {
        "game_potion_discard": {
            "when_present": "reward_potion",
            "when_potion_slots_full": True,
            "weight": 0.35,
        },
    },
    "SHOP_ROOM": {
        "game_potion_discard": {
            "when_present": "shop_reward_potion",
            "when_potion_slots_full": True,
            "weight": 0.15,
        },
    },
}


class StochasticNonCombatDriver:
    """Versioned seeded non-combat driver with hierarchical action sampling.

    ``v1`` first chooses a visible decision category according to the published
    screen-level priors, then samples uniformly among legal actions in that
    category.  The random stream is reset for every controlled run from the
    driver seed and simulator seed, so fresh and reused driver instances have
    the same behavior for the same run configuration.

    This is deliberately not a hand-written route policy.  Categories omitted
    from the table receive the positive ``unknown_category_weight`` rather than
    being filtered out.
    """

    name = "stochastic_non_combat_v1"
    version = 1
    _unknown_category_weight = 1.0

    def __init__(self, seed: int) -> None:
        if isinstance(seed, bool) or not isinstance(seed, int):
            raise ValueError("stochastic non-combat driver seed must be an integer")
        self._seed = seed
        self._rng = random.Random(_driver_run_seed(seed, None))

    @property
    def provenance_config(self) -> Mapping[str, Any]:
        return {
            "seed": self._seed,
            "version": self.version,
            "screen_category_relative_weights": _copy_weight_table(
                NON_COMBAT_DRIVER_V1_SCREEN_CATEGORY_RELATIVE_WEIGHTS
            ),
            "global_category_relative_weights": dict(
                NON_COMBAT_DRIVER_V1_GLOBAL_CATEGORY_RELATIVE_WEIGHTS
            ),
            "conditional_category_relative_weights": _copy_conditional_weight_table(
                NON_COMBAT_DRIVER_V1_CONDITIONAL_CATEGORY_RELATIVE_WEIGHTS
            ),
            "rest_option_categories": {
                "0": "rest_heal",
                "1": "rest_upgrade",
                "other": "rest_other",
            },
            "boss_relic_option_categories": {
                "0..2": "boss_relic_take",
                "3": "boss_relic_skip",
                "other": "boss_relic_unknown",
            },
            "within_category_selection": "uniform",
            "unknown_category_relative_weight": self._unknown_category_weight,
            "normalization_rule": (
                "group eligible actions by category; normalize positive relative "
                "weights across the currently legal categories; then sample "
                "uniformly within the selected category"
            ),
            "random_stream": "sha256(driver_seed, simulator_seed)",
            "reproducible": True,
        }

    def reset_for_run(self, simulator_seed: int | None) -> None:
        """Reset the stream for one authoritative controlled run."""

        self._rng = random.Random(_driver_run_seed(self._seed, simulator_seed))

    def select_action(self, context: DecisionContext) -> PolicyDecision:
        if _has_non_combat_potion_action(context) and not _has_potion_slot_metadata(
            context
        ):
            raise ValueError(
                "non-combat potion actions require visible potion_count and "
                "potion_capacity from the simulator"
            )

        groups: dict[str, list[int]] = {}
        for index in _valid_eligible_indices(context):
            category = non_combat_action_category(context, index)
            groups.setdefault(category, []).append(index)

        categories = list(groups)
        screen_weights = NON_COMBAT_DRIVER_V1_SCREEN_CATEGORY_RELATIVE_WEIGHTS.get(
            context.screen_state.upper(), {}
        )
        selected_category = _weighted_choice(
            self._rng,
            categories,
            [
                _non_combat_category_weight(
                    context,
                    category,
                    categories,
                    screen_weights,
                )
                for category in categories
            ],
        )
        return PolicyDecision(
            legal_action_index=self._rng.choice(groups[selected_category]),
            reason=f"{self.name}:{selected_category}",
        )


@dataclass(frozen=True)
class ScoredActionPolicy:
    """Policy wrapper that chooses the highest-scored eligible action."""

    scorer: ActionScorer
    name: str = "scored_action"

    @property
    def provenance_config(self) -> Mapping[str, Any]:
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


def non_combat_action_category(context: DecisionContext, index: int) -> str:
    """Return the public, versioned category for one legal non-combat action."""

    kind = context.legal_action_kinds[index]
    screen_state = context.screen_state.upper()
    metadata = _action_metadata(context, index)

    if screen_state == "REST_ROOM" and kind == "rest":
        option = metadata.get("idx1")
        if option == 0:
            return "rest_heal"
        if option == 1:
            return "rest_upgrade"
        return "rest_other"

    if screen_state == "BOSS_RELIC_REWARDS" and kind == "boss_relic":
        option = metadata.get("idx1")
        if option in {0, 1, 2}:
            return "boss_relic_take"
        if option == 3:
            return "boss_relic_skip"
        return "boss_relic_unknown"

    if screen_state == "REWARDS":
        if kind == "reward_relic":
            return "ordinary_relic_take"
        if kind == "skip" and "reward_relic" in context.legal_action_kinds:
            return "ordinary_relic_skip"

    return kind


def _action_metadata(context: DecisionContext, index: int) -> Mapping[str, Any]:
    if index < 0 or index >= len(context.legal_action_metadata):
        return {}
    metadata = context.legal_action_metadata[index]
    return metadata if isinstance(metadata, Mapping) else {}


def _non_combat_category_weight(
    context: DecisionContext,
    category: str,
    available_categories: Sequence[str],
    screen_weights: Mapping[str, float],
) -> float:
    conditional = NON_COMBAT_DRIVER_V1_CONDITIONAL_CATEGORY_RELATIVE_WEIGHTS.get(
        context.screen_state.upper(), {}
    ).get(category)
    if conditional is not None:
        required = str(conditional["when_present"])
        requires_full_slots = bool(conditional.get("when_potion_slots_full"))
        if required in available_categories and (
            not requires_full_slots or _potion_slots_full(context)
        ):
            return float(conditional["weight"])

    return screen_weights.get(
        category,
        NON_COMBAT_DRIVER_V1_GLOBAL_CATEGORY_RELATIVE_WEIGHTS.get(
            category,
            StochasticNonCombatDriver._unknown_category_weight,
        ),
    )


def _potion_slots_full(context: DecisionContext) -> bool:
    count = context.snapshot_metadata.get("potion_count")
    capacity = context.snapshot_metadata.get("potion_capacity")
    if (
        isinstance(count, bool)
        or isinstance(capacity, bool)
        or not isinstance(count, (int, float))
        or not isinstance(capacity, (int, float))
    ):
        return False
    return capacity > 0 and count >= capacity


def _has_non_combat_potion_action(context: DecisionContext) -> bool:
    return any(
        kind in {"game_potion_use", "game_potion_discard"}
        for kind in context.legal_action_kinds
    )


def _has_potion_slot_metadata(context: DecisionContext) -> bool:
    count = context.snapshot_metadata.get("potion_count")
    capacity = context.snapshot_metadata.get("potion_capacity")
    return (
        isinstance(count, (int, float))
        and not isinstance(count, bool)
        and isinstance(capacity, (int, float))
        and not isinstance(capacity, bool)
    )


def _weighted_choice(
    rng: random.Random,
    values: Sequence[str],
    weights: Sequence[float],
) -> str:
    if len(values) != len(weights) or not values:
        raise ValueError("weighted choice requires aligned non-empty values")
    if any(not math.isfinite(weight) or weight <= 0.0 for weight in weights):
        raise ValueError("weighted choice weights must be finite and positive")

    threshold = rng.random() * sum(weights)
    cumulative = 0.0
    for value, weight in zip(values, weights, strict=True):
        cumulative += weight
        if threshold < cumulative:
            return value
    return values[-1]


def _driver_run_seed(driver_seed: int, simulator_seed: int | None) -> int:
    encoded = json.dumps(
        {"driver_seed": driver_seed, "simulator_seed": simulator_seed},
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return int.from_bytes(hashlib.sha256(encoded).digest(), "big")


def _copy_weight_table(
    source: Mapping[str, Mapping[str, float]],
) -> dict[str, dict[str, float]]:
    return {screen: dict(weights) for screen, weights in source.items()}


def _copy_conditional_weight_table(
    source: Mapping[str, Mapping[str, Mapping[str, object]]],
) -> dict[str, dict[str, dict[str, object]]]:
    return {
        screen: {
            category: dict(condition) for category, condition in categories.items()
        }
        for screen, categories in source.items()
    }


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
