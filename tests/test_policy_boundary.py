from __future__ import annotations

import ast
from pathlib import Path
import subprocess
import sys

from sts_combat_rl.sim.non_combat_policy import (
    ExpertNonCombatDriver,
    StochasticNonCombatDriver,
)
from sts_combat_rl.sim.policy_contract import DecisionContext


ROOT = Path(__file__).parents[1]


def _imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    return modules


def _decision_context() -> DecisionContext:
    return DecisionContext(
        screen_state="REWARDS",
        snapshot_features=[0.0],
        legal_action_features=[[0.0], [0.0], [0.0]],
        legal_action_kinds=["reward_card", "reward_gold", "skip"],
        eligible_action_indices=[0, 1, 2],
        snapshot_metadata={"potion_count": 1, "potion_capacity": 3},
    )


def test_policy_contract_has_no_upward_runtime_dependencies() -> None:
    modules = _imported_modules(ROOT / "src/sts_combat_rl/sim/policy_contract.py")
    forbidden = (
        "sts_combat_rl.sim.batching",
        "sts_combat_rl.sim.controlled_run",
        "sts_combat_rl.sim.trainer_input",
        "sts_combat_rl.sim.trainer_input_contract",
        "sts_combat_rl.sim.trainer_input_preflight",
        "sts_combat_rl.sim.torch_policy_value",
        "sts_combat_rl.sim.fixed_battle_evaluation",
        "sts_combat_rl.sim.fixed_evaluation_set",
        "sts_combat_rl.sim.evaluation",
        "sts_combat_rl.commands",
        "sts_combat_rl.cli",
        "torch",
    )
    assert not any(
        module == path or module.startswith(f"{path}.")
        for module in modules
        for path in forbidden
    )

    policy_source = (ROOT / "src/sts_combat_rl/sim/policy.py").read_text(
        encoding="utf-8"
    )
    assert "DecisionBatch" not in policy_source
    assert "DecisionExample" not in policy_source
    assert "controlled_run" not in policy_source


def test_controlled_run_uses_eager_policy_contract_import() -> None:
    source = (ROOT / "src/sts_combat_rl/sim/controlled_run.py").read_text(
        encoding="utf-8"
    )
    assert "TYPE_CHECKING" not in source
    assert "from sts_combat_rl.sim.policy import DecisionContext" not in source
    assert "from sts_combat_rl.sim.policy_contract import DecisionContext" in source


def test_default_sim_import_is_torch_free() -> None:
    script = """
import sys
import sts_combat_rl.sim.policy_contract
assert 'torch' not in sys.modules
import sts_combat_rl.sim
assert 'torch' not in sys.modules
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=ROOT,
        env={"PYTHONPATH": str(ROOT / "src")},
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr


def test_fixed_seed_non_combat_selection_and_provenance_are_stable() -> None:
    expected = {
        StochasticNonCombatDriver: (
            [1, 1, 0, 1, 2, 0, 0, 0],
            [
                "stochastic_non_combat_v1:reward_gold",
                "stochastic_non_combat_v1:reward_gold",
                "stochastic_non_combat_v1:reward_card",
                "stochastic_non_combat_v1:reward_gold",
                "stochastic_non_combat_v1:skip",
                "stochastic_non_combat_v1:reward_card",
                "stochastic_non_combat_v1:reward_card",
                "stochastic_non_combat_v1:reward_card",
            ],
        ),
        ExpertNonCombatDriver: (
            [1, 0, 0, 1, 0, 0, 0, 1],
            [
                "expert_non_combat_v1:reward_gold",
                "expert_non_combat_v1:reward_card",
                "expert_non_combat_v1:reward_card",
                "expert_non_combat_v1:reward_gold",
                "expert_non_combat_v1:reward_card",
                "expert_non_combat_v1:reward_card",
                "expert_non_combat_v1:reward_card",
                "expert_non_combat_v1:reward_gold",
            ],
        ),
    }
    for driver_type, (indices, reasons) in expected.items():
        driver = driver_type(seed=17)
        driver.reset_for_run(23)
        decisions = [driver.select_action(_decision_context()) for _ in range(8)]
        assert [decision.legal_action_index for decision in decisions] == indices
        assert [decision.reason for decision in decisions] == reasons
        assert driver.provenance_config == driver_type(seed=17).provenance_config
