"""Small foundational public surface for simulator contracts.

The package root exposes only contracts and adapters that an external caller
can reasonably discover: simulator/action contracts, online decision and
controller contracts, controlled-run advancement, and the named baseline
policies.  Batching, training, evaluation, reports, artifact helpers, search
implementations, and experiment-specific constants remain available from
their owning modules and are intentionally not star-exported here.
"""

from sts_combat_rl.sim.action_space import (
    ActionChooser,
    ActionSpaceConfig,
    action_is_eligible,
    action_space_for_screen,
    eligible_indices,
    filter_eligible_actions,
)
from sts_combat_rl.sim.contract import (
    CheckpointingSimulatorAdapter,
    SimulatorAction,
    SimulatorAdapter,
    SimulatorCheckpoint,
    SimulatorSnapshot,
    SimulatorTransition,
)
from sts_combat_rl.sim.controller_contract import (
    ControllerDecision,
    ControllerProvenance,
    OnlineController,
)
from sts_combat_rl.sim.controlled_run import (
    ControlledRun,
    ControlledRunStep,
    build_decision_context,
    execute_controlled_run,
)
from sts_combat_rl.sim.non_combat_policy import (
    ExpertNonCombatDriver,
    StochasticNonCombatDriver,
)
from sts_combat_rl.sim.online_controller import PolicyController, RoutedRunController
from sts_combat_rl.sim.policy import (
    FirstEligiblePolicy,
    PreferredKindPolicy,
    RandomEligiblePolicy,
    ScoredActionPolicy,
)
from sts_combat_rl.sim.policy_contract import (
    ActionScorer,
    DecisionContext,
    DecisionPolicy,
    PolicyDecision,
)


__all__ = [
    "ActionChooser",
    "ActionScorer",
    "ActionSpaceConfig",
    "CheckpointingSimulatorAdapter",
    "ControllerDecision",
    "ControllerProvenance",
    "ControlledRun",
    "ControlledRunStep",
    "DecisionContext",
    "DecisionPolicy",
    "ExpertNonCombatDriver",
    "FirstEligiblePolicy",
    "PolicyController",
    "PolicyDecision",
    "PreferredKindPolicy",
    "RandomEligiblePolicy",
    "OnlineController",
    "RoutedRunController",
    "ScoredActionPolicy",
    "SimulatorAction",
    "SimulatorAdapter",
    "SimulatorCheckpoint",
    "SimulatorSnapshot",
    "SimulatorTransition",
    "StochasticNonCombatDriver",
    "action_is_eligible",
    "action_space_for_screen",
    "build_decision_context",
    "eligible_indices",
    "execute_controlled_run",
    "filter_eligible_actions",
]
