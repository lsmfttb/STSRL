"""Command helpers for T028 model-guided Oracle-like search smoke runs."""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable
from pathlib import Path
from typing import Any

from sts_combat_rl.sim.action_space import ActionSpaceConfig
from sts_combat_rl.sim.contract import CheckpointingSimulatorAdapter
from sts_combat_rl.sim.fixed_battle_evaluation import (
    FixedEvaluationReport,
    evaluate_fixed_cohort,
    format_fixed_evaluation_report,
)
from sts_combat_rl.sim.fixed_evaluation_set import load_fixed_cohort_jsonl
from sts_combat_rl.sim.lightspeed_source import format_lightspeed_source_identity
from sts_combat_rl.sim.model_guided_oracle_search import (
    ModelGuidedOracleSearchController,
)
from sts_combat_rl.sim.search_guidance_inference import SearchGuidanceScorer
from sts_combat_rl.sim.search_telemetry import (
    format_search_telemetry_summary,
    iter_search_decision_telemetry_dicts,
    summarize_search_decision_telemetry_dicts,
)


def build_torch_guidance_scorer_from_checkpoint(
    checkpoint_path: Path,
) -> SearchGuidanceScorer:
    """Load a T026-compatible PyTorch checkpoint scorer lazily."""

    from sts_combat_rl.sim.torch_policy_value import TorchPolicyValueGuidanceScorer

    return TorchPolicyValueGuidanceScorer.from_checkpoint_path(checkpoint_path)


def run_model_guided_oracle_fixed_evaluation_from_cohort_path(
    adapter_factory: Callable[[], CheckpointingSimulatorAdapter],
    cohort_path: Path,
    controller: ModelGuidedOracleSearchController,
    *,
    action_space: ActionSpaceConfig,
    max_battle_steps: int,
) -> FixedEvaluationReport:
    """Load an immutable fixed cohort and run the T028 controller."""

    with cohort_path.open("r", encoding="utf-8") as stream:
        cohort = load_fixed_cohort_jsonl(stream)
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


def format_model_guided_oracle_fixed_evaluation_report(
    report: FixedEvaluationReport,
) -> str:
    """Format a T028 restored-battle smoke report."""

    return "\n\n".join(
        [
            format_lightspeed_source_identity(),
            "Model-guided Oracle fixed evaluation smoke",
            (
                "scope: full_simulator_state_oracle_like diagnostics only; "
                "not normal-information, live-game, broad-training, or "
                "controller-strength evidence"
            ),
            _format_model_guided_telemetry(report),
            format_fixed_evaluation_report(report),
        ]
    )


def _format_model_guided_telemetry(report: FixedEvaluationReport) -> str:
    telemetry_records: list[dict[str, Any]] = []
    for result in report.battle_results:
        telemetry_records.extend(
            iter_search_decision_telemetry_dicts(
                result.controller_compute_telemetry or {}
            )
        )
    if not telemetry_records:
        return "Model-guided Oracle search compute telemetry\n(no telemetry records)"
    try:
        return format_search_telemetry_summary(
            summarize_search_decision_telemetry_dicts(telemetry_records),
            title="Model-guided Oracle search compute telemetry",
        )
    except ValueError as exc:
        return "\n".join(
            [
                "Model-guided Oracle search compute telemetry",
                f"versioned telemetry summary error: {exc}",
            ]
        )
