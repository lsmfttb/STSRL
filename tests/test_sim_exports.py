from __future__ import annotations

import sts_combat_rl.sim as sim

FOUNDATIONAL_EXPORTS = {
    "ActionSpaceConfig",
    "CheckpointingSimulatorAdapter",
    "ControllerProvenance",
    "DecisionContext",
    "DecisionPolicy",
    "SimulatorAction",
    "SimulatorAdapter",
    "build_decision_context",
    "execute_controlled_run",
}


def test_sim_all_is_small_and_foundational() -> None:
    assert len(sim.__all__) <= 32
    assert len(set(sim.__all__)) == len(sim.__all__)
    assert all(hasattr(sim, name) for name in sim.__all__)
    assert FOUNDATIONAL_EXPORTS <= set(sim.__all__)
    assert "DecisionBatch" not in sim.__all__
    assert "FixedEvaluationReport" not in sim.__all__
    assert "TrainerInputDataset" not in sim.__all__


def test_sim_star_import_matches_documented_surface() -> None:
    namespace: dict[str, object] = {}
    exec("from sts_combat_rl.sim import *", namespace)  # noqa: S102

    assert {name for name in namespace if not name.startswith("_")} == set(sim.__all__)
