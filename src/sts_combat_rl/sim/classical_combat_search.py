"""T088's fixed H1 and Beam baseline over authoritative simulator transitions.

No game mechanics, rollout policy, or terminal utility is implemented here.
The adapter owns transitions and checkpoint state, including hidden RNG state.
Only the explicitly projected H1 quantities participate in heuristic scoring.
"""

from __future__ import annotations

import math
import time
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass, field

from sts_combat_rl.sim.action_space import ActionSpaceConfig, eligible_indices
from sts_combat_rl.sim.contract import (
    CheckpointingSimulatorAdapter,
    SimulatorAction,
    SimulatorCheckpoint,
    SimulatorSnapshot,
)
from sts_combat_rl.sim.controller_contract import (
    ControllerDecision,
    ControllerProvenance,
)
from sts_combat_rl.sim.decision_record import action_identity_dicts_for_actions
from sts_combat_rl.sim.lightspeed_source import lightspeed_source_identity_dict
from sts_combat_rl.sim.online_controller import NATIVE_SEARCH_INFORMATION_REGIME
from sts_combat_rl.sim.policy_contract import DecisionContext

H1_NAME = "combat_handcrafted_h1"
BEAM_NAME = "beam_h1_w32_b400_v1"
BEAM_WIDTH = 32
BEAM_TRANSITION_BUDGET = 400
BATTLE_ACTION_LIMIT = 200


class ClassicalSearchUnavailableError(ValueError):
    """A required controller or authoritative state field is unavailable."""


@dataclass(frozen=True)
class H1Components:
    player_hp_fraction: float
    active_enemy_hp_fraction: float
    block_fraction: float
    turn_fraction: float
    h_raw: float
    value: float


def _number(value: object, name: str, *, minimum: float = 0.0) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ClassicalSearchUnavailableError(f"H1 {name} must be numeric")
    result = float(value)
    if not math.isfinite(result) or result < minimum:
        raise ClassicalSearchUnavailableError(f"H1 {name} is out of range")
    return result


def combat_handcrafted_h1(raw: Mapping[str, object]) -> H1Components:
    """Score only the frozen public HP/block/turn/targetable-enemy projection.

    Input keys follow the canonical native battle snapshot. Missing required
    fields fail closed; unrelated raw fields are neither copied nor traversed.
    This function is defined for nonterminal hypothetical battle states only.
    """

    player = raw.get("battle_player")
    enemies = raw.get("battle_monsters")
    if not isinstance(player, Mapping) or not isinstance(enemies, (list, tuple)):
        raise ClassicalSearchUnavailableError("H1 requires player and enemy evidence")
    hp = _number(player.get("current_hp"), "player current_hp")
    maximum = _number(player.get("max_hp"), "player max_hp")
    block = _number(player.get("block"), "player block")
    turn = _number(raw.get("battle_turn"), "turn", minimum=-math.inf)
    if maximum <= 0:
        raise ClassicalSearchUnavailableError("H1 player max_hp must be positive")
    enemy_hp = enemy_maximum = 0.0
    for enemy in enemies:
        if not isinstance(enemy, Mapping) or not isinstance(
            enemy.get("targetable"), bool
        ):
            raise ClassicalSearchUnavailableError("H1 requires enemy targetable flags")
        if enemy["targetable"]:
            enemy_hp += _number(enemy.get("current_hp"), "enemy current_hp")
            max_hp = _number(enemy.get("max_hp"), "enemy max_hp")
            if max_hp <= 0:
                raise ClassicalSearchUnavailableError(
                    "H1 enemy max_hp must be positive"
                )
            enemy_maximum += max_hp
    player_fraction = hp / maximum
    enemy_fraction = enemy_hp / enemy_maximum if enemy_maximum else 0.0
    block_fraction = block / (maximum + block)
    turn_fraction = min(max(turn, 0.0), 20.0) / 20.0
    h_raw = (
        2.0 * player_fraction
        - 2.0 * enemy_fraction
        + 0.5 * block_fraction
        - 0.1 * turn_fraction
    )
    return H1Components(
        player_fraction,
        enemy_fraction,
        block_fraction,
        turn_fraction,
        h_raw,
        math.tanh(h_raw),
    )


def _outcome(snapshot: SimulatorSnapshot) -> str:
    # A winning transition may already have advanced the game to rewards.
    value = snapshot.raw.get("completed_battle_outcome")
    if value is None:
        value = snapshot.raw.get("battle_outcome")
    if value not in {"PLAYER_VICTORY", "UNDECIDED", "PLAYER_LOSS"}:
        raise ClassicalSearchUnavailableError(
            "Beam requires authoritative battle outcome"
        )
    return str(value)


@dataclass(frozen=True)
class _BeamPath:
    checkpoint: SimulatorCheckpoint | None
    indices: tuple[int, ...]
    outcome: str
    heuristic: H1Components | None

    @property
    def rank(self) -> tuple[int, float, int, tuple[int, ...]]:
        return (
            {"PLAYER_VICTORY": 0, "UNDECIDED": 1, "PLAYER_LOSS": 2}[self.outcome],
            -self.heuristic.value if self.heuristic is not None else 0.0,
            len(self.indices),
            self.indices,
        )


@dataclass(frozen=True)
class BeamH1Controller:
    """The fixed 32-wide, 400-transition T088 layerwise Beam controller."""

    provenance: ControllerProvenance = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "provenance",
            ControllerProvenance(
                kind="classical_battle_search",
                name=BEAM_NAME,
                config={
                    "task_id": "T088",
                    "information_regime": NATIVE_SEARCH_INFORMATION_REGIME,
                    "native_source_identity": lightspeed_source_identity_dict(),
                    "heuristic": H1_NAME,
                    "heuristic_formula": "tanh(2*hp/max_hp-2*active_hp/active_max_hp"
                    "+0.5*block/(max_hp+block)-0.1*clamp(turn,0,20)/20)",
                    "beam_width": BEAM_WIDTH,
                    "successor_transition_budget": BEAM_TRANSITION_BUDGET,
                    "controlled_action_limit": BATTLE_ACTION_LIMIT,
                    "action_space": ActionSpaceConfig.initial_no_potions().to_dict(),
                    "root_selection": "first_action_of_highest_ranked_retained_path",
                    "tie_break": ["shorter_path", "ordered_action_index_sequence"],
                    "policy_prior": None,
                    "learned_leaf_value": None,
                    "controller_seed": None,
                },
            ),
        )

    def select_action(
        self,
        adapter: CheckpointingSimulatorAdapter,
        snapshot: SimulatorSnapshot,
        actions: Sequence[SimulatorAction],
        context: DecisionContext,
        step_index: int,
    ) -> ControllerDecision:
        del context
        if (
            isinstance(step_index, bool)
            or not isinstance(step_index, int)
            or not 0 <= step_index < BATTLE_ACTION_LIMIT
        ):
            raise ClassicalSearchUnavailableError(
                "Beam exceeded controlled action boundary"
            )
        if not getattr(adapter, "supports_checkpoint_restore", False):
            raise ClassicalSearchUnavailableError(
                "Beam requires native checkpoint/restore"
            )
        if _outcome(snapshot) != "UNDECIDED":
            raise ClassicalSearchUnavailableError(
                "Beam root must be an undecided battle"
            )
        root_h1 = combat_handcrafted_h1(snapshot.raw)
        action_space = ActionSpaceConfig.initial_no_potions()
        if not eligible_indices(actions, action_space):
            raise ClassicalSearchUnavailableError("Beam root has no eligible actions")
        root_action_identities = action_identity_dicts_for_actions(actions)

        started = time.perf_counter()
        root = adapter.capture_checkpoint(snapshot)
        frontier = [_BeamPath(root, (), "UNDECIDED", root_h1)]
        transitions = expansions = layers = 0
        stop_reason = "controlled_action_boundary"
        try:
            for _ in range(BATTLE_ACTION_LIMIT - step_index):
                successors: list[_BeamPath] = []
                for path in frontier:
                    if path.outcome != "UNDECIDED":
                        successors.append(path)
                        continue
                    if transitions == BEAM_TRANSITION_BUDGET:
                        break
                    assert path.checkpoint is not None
                    state = adapter.restore_checkpoint(path.checkpoint)
                    legal = list(adapter.legal_actions(state))
                    # Root indices refer to the caller's complete ordered legal
                    # list, including duplicate ids and excluded potion entries.
                    if (
                        not path.indices
                        and action_identity_dicts_for_actions(legal)
                        != root_action_identities
                    ):
                        raise ClassicalSearchUnavailableError(
                            "Beam root legal order mismatch"
                        )
                    indices = eligible_indices(legal, action_space)
                    if not indices:
                        raise ClassicalSearchUnavailableError(
                            "Beam undecided state has no eligible actions"
                        )
                    expansions += 1
                    for index in indices:
                        if transitions == BEAM_TRANSITION_BUDGET:
                            break
                        adapter.restore_checkpoint(path.checkpoint)
                        transition = adapter.step(legal[index])
                        transitions += 1
                        child = transition.snapshot
                        outcome = _outcome(child)
                        if transition.terminal and outcome == "UNDECIDED":
                            raise ClassicalSearchUnavailableError(
                                "Beam terminal transition has no battle outcome"
                            )
                        heuristic = (
                            combat_handcrafted_h1(child.raw)
                            if outcome == "UNDECIDED"
                            else None
                        )
                        checkpoint = (
                            adapter.capture_checkpoint(child)
                            if outcome == "UNDECIDED"
                            else None
                        )
                        successors.append(
                            _BeamPath(
                                checkpoint, (*path.indices, index), outcome, heuristic
                            )
                        )
                if not successors:
                    stop_reason = "no_frontier"
                    break
                frontier = sorted(successors, key=lambda path: path.rank)[:BEAM_WIDTH]
                layers += 1
                if frontier[0].outcome == "PLAYER_VICTORY":
                    stop_reason = "victory"
                    break
                if not any(path.outcome == "UNDECIDED" for path in frontier):
                    stop_reason = "no_searchable_frontier"
                    break
                if transitions == BEAM_TRANSITION_BUDGET:
                    stop_reason = "transition_budget"
                    break
        finally:
            adapter.restore_checkpoint(root)

        best = frontier[0]
        if not best.indices:
            raise ClassicalSearchUnavailableError("Beam retained no root action")
        return ControllerDecision(
            selected_index=best.indices[0],
            provenance=self.provenance,
            reason=f"{BEAM_NAME}:{stop_reason}",
            score=best.heuristic.value if best.heuristic is not None else None,
            metadata={
                "classical_search": {
                    "controller_step_index": step_index,
                    "root_decision_count": 1,
                    "selected_action_identity": root_action_identities[best.indices[0]],
                    "selected_action_indices": list(best.indices),
                    "selected_path_outcome": best.outcome,
                    "selected_path_h1": asdict(best.heuristic)
                    if best.heuristic
                    else None,
                    "layers": layers,
                    "stop_reason": stop_reason,
                    "successor_transition_count": transitions,
                    "tree_node_expansion_count": expansions,
                    "action_execution_count": transitions,
                    "nominal_successor_transition_budget": BEAM_TRANSITION_BUDGET,
                    "native_simulator_steps": None,
                    "native_simulator_steps_unavailable_reason": "StepSimulator.step does not expose the Search-v2 actionExecutionCount counter",
                    "rollout_count": 0,
                    "terminal_utility_evaluation_count": 0,
                    "model_calls": 0,
                    "wall_clock_seconds": time.perf_counter() - started,
                }
            },
        )
