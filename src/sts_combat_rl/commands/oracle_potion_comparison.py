"""Command helpers for T041 no-potion vs potion-enabled Oracle comparison."""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable
from pathlib import Path

from sts_combat_rl.sim.action_space import ActionSpaceConfig
from sts_combat_rl.sim.contract import CheckpointingSimulatorAdapter
from sts_combat_rl.sim.fixed_battle_evaluation import (
    FixedEvaluationReport,
    evaluate_fixed_cohort,
)
from sts_combat_rl.sim.fixed_evaluation_set import FixedCohort, load_fixed_cohort_jsonl
from sts_combat_rl.sim.oracle_potion_comparison import (
    OraclePotionFixedComparisonReport,
    build_oracle_potion_fixed_comparison_report,
    dump_oracle_potion_fixed_comparison_jsonl,
)
from sts_combat_rl.sim.oracle_search import OracleSearchController


def run_oracle_potion_fixed_comparison_from_cohort_path(
    adapter_factory: Callable[[], CheckpointingSimulatorAdapter],
    cohort_path: Path,
    *,
    simulations: int,
    root_selection_rule: str,
    max_battle_steps: int,
    run_scale: str,
) -> OraclePotionFixedComparisonReport:
    """Evaluate no-potion and potion-enabled Oracle search on one cohort."""

    with cohort_path.open("r", encoding="utf-8") as stream:
        cohort = load_fixed_cohort_jsonl(stream)

    no_potion_action_space = ActionSpaceConfig.initial_no_potions()
    potion_action_space = ActionSpaceConfig.include_all()
    no_potion_controller = OracleSearchController(
        simulations=simulations,
        root_selection_rule=root_selection_rule,
        action_space=no_potion_action_space,
    )
    potion_controller = OracleSearchController(
        simulations=simulations,
        root_selection_rule=root_selection_rule,
        action_space=potion_action_space,
    )

    no_potion_report = _evaluate_with_cohort_counts(
        adapter_factory=adapter_factory,
        cohort=cohort,
        controller=no_potion_controller,
        action_space=no_potion_action_space,
        max_battle_steps=max_battle_steps,
    )
    potion_report = _evaluate_with_cohort_counts(
        adapter_factory=adapter_factory,
        cohort=cohort,
        controller=potion_controller,
        action_space=potion_action_space,
        max_battle_steps=max_battle_steps,
    )
    return build_oracle_potion_fixed_comparison_report(
        no_potion_report=no_potion_report,
        potion_report=potion_report,
        comparison_config={
            "task_id": "T041",
            "run_scale": run_scale,
            "cohort_path": str(cohort_path),
            "cohort_identity": cohort.identity,
            "cohort_record_count": len(cohort.records),
            "root_selection_rule": root_selection_rule,
            "simulations": simulations,
            "max_battle_steps": max_battle_steps,
            "no_potion_action_space": no_potion_action_space.to_dict(),
            "potion_action_space": potion_action_space.to_dict(),
            "no_potion_controller_provenance": (
                no_potion_controller.provenance.to_dict()
            ),
            "potion_controller_provenance": potion_controller.provenance.to_dict(),
        },
    )


def write_oracle_potion_fixed_comparison_report(
    path: Path,
    report: OraclePotionFixedComparisonReport,
) -> None:
    """Write a current-schema T041 comparison JSONL artifact."""

    with path.open("w", encoding="utf-8", newline="\n") as stream:
        dump_oracle_potion_fixed_comparison_jsonl(report, stream)


def _evaluate_with_cohort_counts(
    *,
    adapter_factory: Callable[[], CheckpointingSimulatorAdapter],
    cohort: FixedCohort,
    controller: OracleSearchController,
    action_space: ActionSpaceConfig,
    max_battle_steps: int,
) -> FixedEvaluationReport:
    evaluation = evaluate_fixed_cohort(
        adapter_factory=adapter_factory,
        cohort_records=cohort.records,
        controller=controller,
        cohort_identity=cohort.identity,
        source_pool_format_version=cohort.source_pool_format_version,
        selection_config=cohort.selection_config.to_dict(),
        action_space=action_space,
        max_battle_steps=max_battle_steps,
    )
    per_stratum_counts = Counter(
        "/".join(str(value) for value in record.structural_stratum)
        for record in cohort.records
    )
    return FixedEvaluationReport(
        cohort_identity=evaluation.cohort_identity,
        controller_provenance=evaluation.controller_provenance,
        information_regime=evaluation.information_regime,
        action_space_config=evaluation.action_space_config,
        max_battle_steps=evaluation.max_battle_steps,
        source_pool_format_version=evaluation.source_pool_format_version,
        selection_config=evaluation.selection_config,
        per_stratum_source_counts=dict(per_stratum_counts),
        battle_results=evaluation.battle_results,
        problems=evaluation.problems,
    )
