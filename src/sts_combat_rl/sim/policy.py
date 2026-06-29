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
    tactical_state: Mapping[str, Any] = field(default_factory=dict)
    tactical_legal_actions: list[Mapping[str, Any]] = field(default_factory=list)
    tactical_feature_schema_id: str = "public-tactical-v2"
    public_run_context: Mapping[str, Any] = field(default_factory=dict)


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

EXPERT_NON_COMBAT_V1_SCREEN_CATEGORY_RELATIVE_WEIGHTS: dict[str, dict[str, float]] = {
    "MAP_SCREEN": {
        "map": 1.00,
        "skip": 0.05,
    },
    "REST_ROOM": {
        "rest_heal": 0.35,
        "rest_upgrade": 0.90,
        "rest_other": 0.20,
    },
    "SHOP_ROOM": {
        "shop_card_remove": 0.70,
        "shop_reward_card": 0.35,
        "shop_reward_potion": 0.25,
        "shop_reward_relic": 0.55,
        "shop_skip": 0.08,
        "game_potion_use": 0.05,
    },
    "EVENT_SCREEN": {
        "event": 0.90,
        "skip": 0.10,
        "game_potion_use": 0.04,
    },
    "CARD_SELECT": {
        "card_select": 0.90,
        "single_card_select": 0.90,
        "multi_card_select": 0.90,
        "skip": 0.10,
    },
    "REWARDS": {
        "reward_card": 1.20,
        "reward_gold": 1.00,
        "reward_key": 0.18,
        "reward_potion": 0.90,
        "ordinary_relic_take": 1.00,
        "ordinary_relic_skip": 0.08,
        "skip": 0.20,
        "game_potion_use": 0.05,
    },
    "BOSS_RELIC_REWARDS": {
        "boss_relic_take": 1.00,
        "boss_relic_skip": 0.03,
    },
    "TREASURE_ROOM": {
        "treasure_open": 1.00,
        "treasure_leave": 0.03,
    },
}
"""Base hierarchical priors for ``expert_non_combat_v1``.

The expert driver keeps the same category-first structure as the stochastic
driver, but applies public-state multipliers to these priors and then samples
within the chosen category with public action scores.
"""

EXPERT_NON_COMBAT_V1_GLOBAL_CATEGORY_RELATIVE_WEIGHTS: dict[str, float] = {
    "game_potion_use": 0.04,
    "game_potion_discard": 0.03,
}

EXPERT_NON_COMBAT_V1_RULE_GROUPS: dict[str, str] = {
    "card_rewards": (
        "prefer early damage, draw, energy, and scaling; prefer defense when "
        "visible HP is low; keep skips and weak cards reachable"
    ),
    "route_choices": (
        "use action labels and public resources as route proxies; prefer elites "
        "with healthy HP or potions, prefer rests/shops when low"
    ),
    "rest_sites": ("prefer upgrades by default, but boost rest when current HP is low"),
    "shops": (
        "prefer removals, high-impact relic/cards, useful potions with empty "
        "slots, and retain some gold by keeping skip reachable"
    ),
    "events": (
        "conservative label-based priors avoid visible damage/curse costs when "
        "low HP while keeping legal branches reachable"
    ),
    "resources": (
        "take relics/treasure by default; keep skips, potion discards, and keys "
        "as low-probability legal alternatives"
    ),
    "fallback": (
        "unknown or missing public payloads use positive fallback weights rather "
        "than deterministic first-action behavior"
    ),
}

EXPERT_NON_COMBAT_V1_VISIBLE_INPUTS: tuple[str, ...] = (
    "DecisionContext.screen_state",
    "DecisionContext.legal_action_kinds",
    "DecisionContext.eligible_action_indices",
    "DecisionContext.snapshot_metadata.potion_count",
    "DecisionContext.snapshot_metadata.potion_capacity",
    "DecisionContext.tactical_state.scalars.current_hp",
    "DecisionContext.tactical_state.scalars.max_hp",
    "DecisionContext.tactical_state.scalars.gold",
    "DecisionContext.tactical_state.scalars.act",
    "DecisionContext.tactical_state.scalars.floor_num",
    "DecisionContext.tactical_state.cards",
    "DecisionContext.tactical_state.relics",
    "DecisionContext.tactical_state.potions",
    "DecisionContext.tactical_legal_actions",
    "DecisionContext.public_run_context.current.location",
    "DecisionContext.public_run_context.visible_act_boss",
    "DecisionContext.public_run_context.persistent_resources",
    "DecisionContext.public_run_context.history",
)

_EXPERT_LOW_PROBABILITY_CATEGORY_FLOOR = 0.02
_EXPERT_LOW_PROBABILITY_ACTION_FLOOR = 0.02
_EXPERT_UNKNOWN_CATEGORY_WEIGHT = 0.35
_EXPERT_ACTION_FALLBACK_WEIGHT = 1.0

_FORBIDDEN_PUBLIC_INPUT_KEY_FRAGMENTS = (
    "hidden_rng",
    "rng_state",
    "random_state",
    "draw_order",
    "draw_pile_order",
    "unrevealed",
    "future_encounter",
    "future_encounters",
    "second_boss",
    "act3_second_boss",
    "checkpoint",
    "native_object",
    "native_payload",
    "simulator_state",
)


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


class ExpertNonCombatDriver:
    """Versioned seeded A20 source-generation non-combat driver.

    The driver remains stochastic and legal-action based. It samples a public
    decision category first, then samples an action inside that category using
    visible action/resource heuristics. Missing payloads and unknown categories
    receive positive fallback weights, so legal low-probability alternatives
    remain reachable.
    """

    name = "expert_non_combat_v1"
    version = 1
    _unknown_category_weight = _EXPERT_UNKNOWN_CATEGORY_WEIGHT
    _category_floor = _EXPERT_LOW_PROBABILITY_CATEGORY_FLOOR
    _action_floor = _EXPERT_LOW_PROBABILITY_ACTION_FLOOR

    def __init__(self, seed: int) -> None:
        if isinstance(seed, bool) or not isinstance(seed, int):
            raise ValueError("expert non-combat driver seed must be an integer")
        self._seed = seed
        self._rng = random.Random(_driver_run_seed(seed, None))

    @property
    def provenance_config(self) -> Mapping[str, Any]:
        return {
            "seed": self._seed,
            "version": self.version,
            "screen_category_relative_weights": _copy_weight_table(
                EXPERT_NON_COMBAT_V1_SCREEN_CATEGORY_RELATIVE_WEIGHTS
            ),
            "global_category_relative_weights": dict(
                EXPERT_NON_COMBAT_V1_GLOBAL_CATEGORY_RELATIVE_WEIGHTS
            ),
            "rule_groups": dict(EXPERT_NON_COMBAT_V1_RULE_GROUPS),
            "visible_state_inputs": list(EXPERT_NON_COMBAT_V1_VISIBLE_INPUTS),
            "forbidden_public_input_key_fragments": list(
                _FORBIDDEN_PUBLIC_INPUT_KEY_FRAGMENTS
            ),
            "category_floor": self._category_floor,
            "action_floor": self._action_floor,
            "unknown_category_relative_weight": self._unknown_category_weight,
            "normalization_rule": (
                "group eligible actions by public category; apply public-state "
                "category multipliers; normalize positive category weights; "
                "then sample within the chosen category by public action score"
            ),
            "within_category_selection": "weighted_by_public_action_score",
            "missing_public_payload_behavior": (
                "explicit fallback weights; no hidden future or simulator state "
                "fields are read"
            ),
            "random_stream": "sha256(driver_seed, simulator_seed)",
            "reproducible": True,
        }

    def reset_for_run(self, simulator_seed: int | None) -> None:
        """Reset the stream for one authoritative controlled run."""

        self._rng = random.Random(_driver_run_seed(self._seed, simulator_seed))

    def select_action(self, context: DecisionContext) -> PolicyDecision:
        _validate_expert_public_inputs(context)
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
        profile = _expert_public_profile(context)
        selected_category = _weighted_choice(
            self._rng,
            categories,
            [
                _expert_category_weight(context, category, categories, profile)
                for category in categories
            ],
        )
        action_indices = groups[selected_category]
        selected_index = _weighted_index_choice(
            self._rng,
            action_indices,
            [
                _expert_action_weight(context, index, selected_category, profile)
                for index in action_indices
            ],
        )
        return PolicyDecision(
            legal_action_index=selected_index,
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
        tactical_state=example.tactical_state,
        tactical_legal_actions=example.tactical_legal_actions,
        tactical_feature_schema_id=example.feature_schema_id,
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


def _validate_expert_public_inputs(context: DecisionContext) -> None:
    problems: list[str] = []
    for label, value in (
        ("snapshot_metadata", context.snapshot_metadata),
        ("legal_action_metadata", context.legal_action_metadata),
        ("tactical_state", context.tactical_state),
        ("tactical_legal_actions", context.tactical_legal_actions),
        ("public_run_context", context.public_run_context),
    ):
        _append_forbidden_public_input_keys(value, f"$.{label}", problems)
    if problems:
        raise ValueError(
            "expert_non_combat_v1 public input contains forbidden field(s): "
            + "; ".join(problems)
        )


def _append_forbidden_public_input_keys(
    value: object,
    path: str,
    problems: list[str],
) -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            key_text = str(key)
            normalized = key_text.lower().replace("-", "_")
            if any(
                fragment in normalized
                for fragment in _FORBIDDEN_PUBLIC_INPUT_KEY_FRAGMENTS
            ):
                problems.append(f"{path}.{key_text}")
            _append_forbidden_public_input_keys(item, f"{path}.{key_text}", problems)
        return
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        for index, item in enumerate(value):
            _append_forbidden_public_input_keys(item, f"{path}[{index}]", problems)


def _expert_public_profile(context: DecisionContext) -> dict[str, Any]:
    scalars = _mapping_value(context.tactical_state.get("scalars"))
    current_hp = _first_public_number(
        scalars.get("current_hp"),
        _persistent_resource_value(context, "current_hp"),
    )
    max_hp = _first_public_number(
        scalars.get("max_hp"),
        _persistent_resource_value(context, "max_hp"),
    )
    gold = _first_public_number(
        scalars.get("gold"),
        _persistent_resource_value(context, "gold"),
    )
    potion_count = _first_public_number(
        context.snapshot_metadata.get("potion_count"),
        scalars.get("potion_count"),
        _persistent_resource_value(context, "potion_count"),
    )
    potion_capacity = _first_public_number(
        context.snapshot_metadata.get("potion_capacity"),
        scalars.get("potion_capacity"),
        _persistent_resource_value(context, "potion_capacity"),
    )
    act = _first_public_number(
        scalars.get("act"),
        _context_field_value(context.public_run_context, "current", "location", "act"),
    )
    floor = _first_public_number(
        scalars.get("floor_num"),
        _context_field_value(
            context.public_run_context,
            "current",
            "location",
            "floor",
        ),
    )
    hp_ratio = (
        max(0.0, min(1.0, current_hp / max_hp))
        if current_hp is not None and max_hp is not None and max_hp > 0
        else None
    )
    relics = _sequence_value(context.tactical_state.get("relics"))
    cards = _sequence_value(context.tactical_state.get("cards"))
    potions = _sequence_value(context.tactical_state.get("potions"))
    visible_boss = _context_field_value(context.public_run_context, "visible_act_boss")
    return {
        "current_hp": current_hp,
        "max_hp": max_hp,
        "hp_ratio": hp_ratio,
        "gold": gold,
        "potion_count": potion_count,
        "potion_capacity": potion_capacity,
        "potion_slots_full": (
            potion_count is not None
            and potion_capacity is not None
            and potion_capacity > 0
            and potion_count >= potion_capacity
        ),
        "potion_slots_empty": (
            potion_count is not None
            and potion_capacity is not None
            and potion_count < potion_capacity
        ),
        "act": int(act) if act is not None else None,
        "floor": int(floor) if floor is not None else None,
        "visible_card_count": len(cards),
        "visible_relic_count": len(relics),
        "visible_potion_slot_count": len(potions),
        "visible_act_boss": (
            str(visible_boss) if isinstance(visible_boss, str) else None
        ),
    }


def _expert_category_weight(
    context: DecisionContext,
    category: str,
    available_categories: Sequence[str],
    profile: Mapping[str, Any],
) -> float:
    screen_weights = EXPERT_NON_COMBAT_V1_SCREEN_CATEGORY_RELATIVE_WEIGHTS.get(
        context.screen_state.upper(), {}
    )
    weight = screen_weights.get(
        category,
        EXPERT_NON_COMBAT_V1_GLOBAL_CATEGORY_RELATIVE_WEIGHTS.get(
            category,
            ExpertNonCombatDriver._unknown_category_weight,
        ),
    )
    hp_ratio = _optional_float(profile.get("hp_ratio"))
    gold = _optional_float(profile.get("gold"))
    floor = _optional_int_value(profile.get("floor"))
    act = _optional_int_value(profile.get("act"))
    potion_slots_full = bool(profile.get("potion_slots_full"))
    potion_slots_empty = bool(profile.get("potion_slots_empty"))

    if hp_ratio is not None:
        if category == "rest_heal":
            weight *= 4.0 if hp_ratio <= 0.35 else 0.65
        elif category == "rest_upgrade":
            weight *= 0.35 if hp_ratio <= 0.35 else 1.25
        elif category in {"shop_reward_potion", "reward_potion"} and hp_ratio <= 0.45:
            weight *= 1.20

    if floor is not None and floor <= 6:
        if category == "reward_card":
            weight *= 1.45
        elif category in {"skip", "ordinary_relic_skip"}:
            weight *= 0.55

    if gold is not None and context.screen_state.upper() == "SHOP_ROOM":
        if category == "shop_card_remove":
            weight *= 1.50 if gold >= 75 else 0.45
        elif category in {"shop_reward_card", "shop_reward_potion"}:
            weight *= 1.15 if gold >= 45 else 0.40
        elif category == "shop_reward_relic":
            weight *= 1.25 if gold >= 120 else 0.45
        elif category == "shop_skip" and gold < 50:
            weight *= 1.80

    if category == "reward_potion":
        weight *= 0.35 if potion_slots_full else 1.20 if potion_slots_empty else 1.0
    if category == "game_potion_discard":
        if potion_slots_full and (
            "reward_potion" in available_categories
            or "shop_reward_potion" in available_categories
        ):
            weight = max(weight, 0.35)
        else:
            weight *= 0.40
    if category == "reward_key":
        weight *= 2.00 if act is not None and act >= 3 else 0.55
    return max(_EXPERT_LOW_PROBABILITY_CATEGORY_FLOOR, float(weight))


def _expert_action_weight(
    context: DecisionContext,
    index: int,
    category: str,
    profile: Mapping[str, Any],
) -> float:
    kind = context.legal_action_kinds[index]
    label = _action_text(context, index)
    weight = _EXPERT_ACTION_FALLBACK_WEIGHT
    if category in {"reward_card", "shop_reward_card", "card_select"} or kind in {
        "reward_card",
        "shop_reward_card",
        "card_select",
        "single_card_select",
        "multi_card_select",
    }:
        weight = _expert_card_action_weight(context, index, profile)
    elif category == "map" or kind == "map":
        weight = _expert_route_action_weight(label, profile)
    elif category.startswith("rest_"):
        weight = _expert_rest_action_weight(category, profile)
    elif category in {"event", "game_unknown"} or kind == "event":
        weight = _expert_event_action_weight(label, profile)
    elif category == "shop_card_remove":
        weight = _expert_shop_remove_weight(profile)
    elif category in {"shop_reward_relic", "ordinary_relic_take", "boss_relic_take"}:
        weight = _expert_relic_action_weight(label)
    elif category in {"reward_potion", "shop_reward_potion"}:
        weight = _expert_potion_reward_weight(profile)
    elif category == "game_potion_discard":
        weight = 1.40 if profile.get("potion_slots_full") else 0.35
    elif category in {"treasure_open", "reward_gold"}:
        weight = 1.40
    elif category in {"treasure_leave", "ordinary_relic_skip", "boss_relic_skip"}:
        weight = 0.20
    elif category == "reward_key":
        act = _optional_int_value(profile.get("act"))
        weight = 0.80 if act is not None and act >= 3 else 0.25
    elif category in {"shop_skip", "skip"}:
        weight = _expert_skip_weight(context, profile)
    return max(_EXPERT_LOW_PROBABILITY_ACTION_FLOOR, float(weight))


def _expert_card_action_weight(
    context: DecisionContext,
    index: int,
    profile: Mapping[str, Any],
) -> float:
    action = _action_payload(context, index)
    card = _mapping_value(action.get("selected_card"))
    identity = _mapping_value(card.get("identity"))
    name = _normalized_label(identity.get("value") if identity else action.get("label"))
    label = _normalized_label(_action_text(context, index))
    card_type = str(card.get("type", "")).upper()
    rarity = str(card.get("rarity", "")).upper()
    scalars = _mapping_value(card.get("scalars"))
    damage = _optional_float(scalars.get("damage"))
    block = _optional_float(scalars.get("block"))
    cost = _optional_float(scalars.get("cost"))
    floor = _optional_int_value(profile.get("floor"))
    hp_ratio = _optional_float(profile.get("hp_ratio"))

    score = 1.0
    if card_type in {"CURSE", "STATUS"} or _contains_any(name, ("curse", "wound")):
        score *= 0.08
    if name in {"strike_r", "strike", "defend_r", "defend"}:
        score *= 0.30
    if rarity == "RARE":
        score *= 1.25
    elif rarity == "UNCOMMON":
        score *= 1.10

    text = f"{name} {label}"
    if (damage is not None and damage > 0) or _contains_any(
        text,
        (
            "anger",
            "bash",
            "bludgeon",
            "carnage",
            "cleave",
            "damage",
            "immolate",
            "pommel",
            "strike",
            "twin_strike",
            "wild_strike",
        ),
    ):
        score *= 2.20 if floor is not None and floor <= 6 else 1.35
    if (block is not None and block > 0) or _contains_any(
        text,
        ("block", "shrug", "impervious", "flame_barrier", "true_grit"),
    ):
        score *= 1.60 if hp_ratio is not None and hp_ratio <= 0.45 else 1.15
    if _contains_any(text, ("draw", "pommel", "shrug", "battle_trance", "offering")):
        score *= 1.45
    if _contains_any(text, ("energy", "bloodletting", "seeing_red", "offering")):
        score *= 1.45
    if _contains_any(
        text,
        (
            "demon_form",
            "feel_no_pain",
            "inflame",
            "limit_break",
            "metallicize",
            "rupture",
            "scaling",
            "spot_weakness",
        ),
    ):
        score *= 1.55
    if _contains_any(text, ("cleave", "immolate", "whirlwind")):
        score *= 1.25
    if (
        cost is not None
        and cost >= 3
        and not _contains_any(
            text,
            ("bludgeon", "demon_form", "impervious", "immolate"),
        )
    ):
        score *= 0.70
    if _contains_any(text, ("clash", "perfected_strike", "searing_blow")):
        score *= 0.55
    return score


def _expert_route_action_weight(label: str, profile: Mapping[str, Any]) -> float:
    hp_ratio = _optional_float(profile.get("hp_ratio"))
    gold = _optional_float(profile.get("gold"))
    potion_count = _optional_float(profile.get("potion_count"))
    visible_boss = _normalized_label(profile.get("visible_act_boss"))
    healthy = hp_ratio is None or hp_ratio >= 0.60
    has_potion = potion_count is not None and potion_count > 0
    score = 1.0
    if _contains_any(label, ("elite",)):
        score *= 1.75 if healthy or has_potion else 0.35
    if _contains_any(label, ("rest", "campfire")):
        score *= 2.00 if hp_ratio is not None and hp_ratio <= 0.45 else 1.10
    if _contains_any(label, ("shop",)):
        score *= 1.40 if gold is not None and gold >= 90 else 0.75
    if _contains_any(label, ("treasure", "chest")):
        score *= 1.25
    if _contains_any(label, ("monster", "enemy")):
        score *= 1.20 if healthy else 0.80
    if "hexaghost" in visible_boss and _contains_any(label, ("rest", "campfire")):
        score *= 0.85
    return score


def _expert_rest_action_weight(
    category: str,
    profile: Mapping[str, Any],
) -> float:
    hp_ratio = _optional_float(profile.get("hp_ratio"))
    if category == "rest_heal":
        return 2.50 if hp_ratio is not None and hp_ratio <= 0.35 else 0.55
    if category == "rest_upgrade":
        return 0.55 if hp_ratio is not None and hp_ratio <= 0.35 else 1.80
    return 0.45


def _expert_event_action_weight(label: str, profile: Mapping[str, Any]) -> float:
    hp_ratio = _optional_float(profile.get("hp_ratio"))
    score = 1.0
    if _contains_any(label, ("remove", "upgrade", "transform", "relic", "heal")):
        score *= 1.35
    if _contains_any(label, ("gold", "card")):
        score *= 1.10
    if _contains_any(label, ("curse", "lose_hp", "damage", "lose hp")):
        score *= 0.35 if hp_ratio is not None and hp_ratio <= 0.50 else 0.70
    if _contains_any(label, ("leave", "ignore", "decline")):
        score *= 0.75
    return score


def _expert_shop_remove_weight(profile: Mapping[str, Any]) -> float:
    gold = _optional_float(profile.get("gold"))
    if gold is None:
        return 1.0
    if gold >= 150:
        return 2.10
    if gold >= 75:
        return 1.70
    return 0.45


def _expert_relic_action_weight(label: str) -> float:
    score = 1.20
    if _contains_any(
        label,
        (
            "black_star",
            "coffee_dripper",
            "cursed_key",
            "energy",
            "fusion_hammer",
            "lantern",
            "relic",
            "sozu",
            "vajra",
        ),
    ):
        score *= 1.35
    if _contains_any(label, ("busted_crown", "ectoplasm", "runic_dome")):
        score *= 0.80
    return score


def _expert_potion_reward_weight(profile: Mapping[str, Any]) -> float:
    if profile.get("potion_slots_full"):
        return 0.30
    if profile.get("potion_slots_empty"):
        return 1.35
    return 1.0


def _expert_skip_weight(
    context: DecisionContext,
    profile: Mapping[str, Any],
) -> float:
    floor = _optional_int_value(profile.get("floor"))
    if context.screen_state.upper() == "REWARDS" and floor is not None and floor <= 6:
        return 0.30
    return 0.70


def _action_payload(context: DecisionContext, index: int) -> Mapping[str, Any]:
    if index < 0 or index >= len(context.tactical_legal_actions):
        return {}
    return _mapping_value(context.tactical_legal_actions[index])


def _action_text(context: DecisionContext, index: int) -> str:
    action = _action_payload(context, index)
    pieces = [
        str(context.legal_action_kinds[index])
        if 0 <= index < len(context.legal_action_kinds)
        else "",
        str(action.get("label", "")),
    ]
    card = _mapping_value(action.get("selected_card"))
    card_identity = _mapping_value(card.get("identity"))
    if card_identity.get("value") is not None:
        pieces.append(str(card_identity.get("value")))
    target = _mapping_value(action.get("selected_target"))
    target_identity = _mapping_value(target.get("identity"))
    if target_identity.get("value") is not None:
        pieces.append(str(target_identity.get("value")))
    return _normalized_label(" ".join(pieces))


def _persistent_resource_value(
    context: DecisionContext,
    field_name: str,
) -> object | None:
    resources = _mapping_value(context.public_run_context.get("persistent_resources"))
    fields = _mapping_value(resources.get("fields"))
    return _field_wrapper_value(fields.get(field_name))


def _context_field_value(
    context: Mapping[str, Any],
    *path: str,
) -> object | None:
    current: object = context
    for key in path:
        current = _mapping_value(current).get(key)
    return _field_wrapper_value(current)


def _field_wrapper_value(value: object) -> object | None:
    wrapper = _mapping_value(value)
    if wrapper.get("availability") == "available":
        return wrapper.get("value")
    return None


def _first_public_number(*values: object) -> float | None:
    for value in values:
        parsed = _optional_float(value)
        if parsed is not None:
            return parsed
    return None


def _optional_float(value: object) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        converted = float(value)
        return converted if math.isfinite(converted) else None
    return None


def _optional_int_value(value: object) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return None


def _mapping_value(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _sequence_value(value: object) -> Sequence[Any]:
    return (
        value
        if isinstance(value, Sequence) and not isinstance(value, (str, bytes))
        else ()
    )


def _normalized_label(value: object) -> str:
    return (
        str(value)
        .strip()
        .casefold()
        .replace(" ", "_")
        .replace("-", "_")
        .replace("'", "")
    )


def _contains_any(text: str, needles: Sequence[str]) -> bool:
    normalized = _normalized_label(text)
    return any(_normalized_label(needle) in normalized for needle in needles)


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


def _weighted_index_choice(
    rng: random.Random,
    values: Sequence[int],
    weights: Sequence[float],
) -> int:
    if len(values) != len(weights) or not values:
        raise ValueError("weighted index choice requires aligned non-empty values")
    if any(not math.isfinite(weight) or weight <= 0.0 for weight in weights):
        raise ValueError("weighted index choice weights must be finite and positive")

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
