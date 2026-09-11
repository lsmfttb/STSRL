"""T088 controller construction; no canary or formal execution is enabled yet."""

from __future__ import annotations

from sts_combat_rl.commands.t085_native_execution import (
    T085UnguidedBattleSearchV2Controller,
)
from sts_combat_rl.sim.classical_combat_search import (
    BEAM_NAME,
    BeamH1Controller,
    ClassicalSearchUnavailableError,
)
from sts_combat_rl.sim.controller_contract import OnlineController

T088_ARM_ORDER = ("A", "B", "C", "D")
T088_PROGRESSIVE_BIAS_NAME = "progressive_bias_mcts_h1_400_v1"


def build_t088_controller(arm: str) -> OnlineController:
    """Construct a frozen arm, never substituting a baseline for unavailable D.

    A/B use the accepted controller class unchanged, so both callbacks remain
    absent and the terminal-edge handoff remains the accepted T085/T087 path.
    D requires an independently reviewed canonical native search extension.
    """

    if arm in ("A", "B"):
        return T085UnguidedBattleSearchV2Controller(
            simulations=100 if arm == "A" else 400
        )
    if arm == "C":
        return BeamH1Controller()
    if arm == "D":
        raise ClassicalSearchUnavailableError(
            f"{T088_PROGRESSIVE_BIAS_NAME} requires a governed native all-node "
            "progressive-bias surface; the pinned Search-v2 API has no such hook"
        )
    raise ValueError(f"unknown T088 arm {arm!r}; expected {T088_ARM_ORDER}")


def t088_controller_definitions() -> dict[str, object]:
    """Expose the four fixed definitions without claiming tournament readiness."""

    return {
        "task": "T088",
        "schema_id": "t088-controller-definitions-v1",
        "arm_order": list(T088_ARM_ORDER),
        "tournament_execution_ready": False,
        "arms": {
            "A": {"controller": "Search-v2", "simulations": 100},
            "B": {"controller": "Search-v2", "simulations": 400},
            "C": {"controller": BEAM_NAME, "width": 32, "transition_budget": 400},
            "D": {
                "controller": T088_PROGRESSIVE_BIAS_NAME,
                "simulations": 400,
                "progressive_bias_weight": 0.50,
                "progressive_bias": "0.50 * combat_handcrafted_h1(child_state) / (1 + child_visit_count)",
                "availability": "requires_governed_native_extension",
            },
        },
    }
