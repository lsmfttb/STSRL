from __future__ import annotations

import sts_combat_rl.sim as sim

EXPECTED_SIM_EXPORT_COUNT = 305
KEY_COMPATIBILITY_EXPORTS = {
    "ActionSpaceConfig",
    "BattleStartCheckpointRecord",
    "DecisionContext",
    "FixedEvaluationReport",
    "LightSpeedAdapter",
    "OracleSearchController",
    "SimulatorAction",
    "SimulatorAdapter",
    "SimulatorSnapshot",
    "SimulatorTransition",
    "build_decision_context",
    "build_model_input_batch",
    "execute_controlled_run",
    "format_fixed_evaluation_report",
    "load_trainer_input_dataset_jsonl",
}


def test_sim_all_export_surface_is_explicit_and_stable() -> None:
    assert len(sim.__all__) == EXPECTED_SIM_EXPORT_COUNT
    assert len(set(sim.__all__)) == EXPECTED_SIM_EXPORT_COUNT
    assert all(hasattr(sim, name) for name in sim.__all__)


def test_sim_star_import_retains_key_compatibility_exports() -> None:
    namespace: dict[str, object] = {}
    exec("from sts_combat_rl.sim import *", namespace)  # noqa: S102

    assert KEY_COMPATIBILITY_EXPORTS <= set(namespace)
