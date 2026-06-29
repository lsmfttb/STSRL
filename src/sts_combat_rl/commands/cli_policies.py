"""CLI adapters for simulator policy construction."""

from __future__ import annotations

import argparse

from sts_combat_rl.sim.model_scoring import ActionKindPriorScorer
from sts_combat_rl.sim.policy import (
    ExpertNonCombatDriver,
    FirstEligiblePolicy,
    PreferredKindPolicy,
    RandomEligiblePolicy,
    ReplayChosenPolicy,
    ScoredActionPolicy,
    StochasticNonCombatDriver,
)
from sts_combat_rl.sim.training_gate import TrainingScaleGateConfig


def build_pytorch_gate_config(args: argparse.Namespace) -> TrainingScaleGateConfig:
    """Build the T009 broad-training gate config from parsed CLI arguments."""

    return TrainingScaleGateConfig(
        required_ascensions=tuple(args.pytorch_gate_required_ascensions),
        required_acts=tuple(args.pytorch_gate_required_acts),
        min_records_per_ascension_act=args.pytorch_gate_min_records,
        min_unique_sources_per_ascension_act=args.pytorch_gate_min_sources,
    )


def build_sim_policy(
    policy_name: str,
    seed: int,
) -> (
    FirstEligiblePolicy
    | PreferredKindPolicy
    | ReplayChosenPolicy
    | RandomEligiblePolicy
    | ScoredActionPolicy
):
    """Build a framework-neutral simulator policy selected by CLI name."""

    if policy_name == "preferred-kind":
        return PreferredKindPolicy()
    if policy_name == "first-eligible":
        return FirstEligiblePolicy()
    if policy_name == "replay-chosen":
        return ReplayChosenPolicy()
    if policy_name == "random-eligible":
        return RandomEligiblePolicy(seed=seed)
    if policy_name == "action-kind-prior-scorer":
        return ScoredActionPolicy(
            ActionKindPriorScorer(),
            name="action_kind_prior_scorer",
        )
    raise ValueError(f"unknown simulator policy: {policy_name}")


def build_online_sim_policy(
    policy_name: str,
    seed: int,
) -> (
    FirstEligiblePolicy
    | PreferredKindPolicy
    | RandomEligiblePolicy
    | ScoredActionPolicy
):
    """Build a simulator policy that can act online without chosen labels."""

    if policy_name == "replay-chosen":
        raise ValueError(
            "replay-chosen is only valid for --lightspeed-policy-smoke, "
            "because online rollouts do not have recorded chosen labels"
        )
    policy = build_sim_policy(policy_name, seed)
    if isinstance(policy, ReplayChosenPolicy):
        raise ValueError("replay-chosen is not valid for online policy rollouts")
    return policy


def build_non_combat_driver_policy(
    policy_name: str,
    seed: int,
) -> (
    FirstEligiblePolicy
    | PreferredKindPolicy
    | RandomEligiblePolicy
    | ExpertNonCombatDriver
    | StochasticNonCombatDriver
):
    """Build the separately named non-combat driver selected by CLI name."""

    if policy_name == "stochastic-v1":
        return StochasticNonCombatDriver(seed=seed)
    if policy_name in {"expert-v1", "expert_non_combat_v1"}:
        return ExpertNonCombatDriver(seed=seed)
    if policy_name == "preferred-kind":
        return PreferredKindPolicy()
    if policy_name == "first-eligible":
        return FirstEligiblePolicy()
    if policy_name == "random-eligible":
        return RandomEligiblePolicy(seed=seed)
    raise ValueError(f"unknown non-combat driver policy: {policy_name}")
