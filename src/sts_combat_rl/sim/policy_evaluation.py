"""Offline policy selection evaluation over rollout decision batches."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

from sts_combat_rl.sim.batching import DecisionBatch, DecisionExample
from sts_combat_rl.sim.policy_contract import (
    DecisionContext,
    DecisionPolicy,
    PolicyDecision,
)


@dataclass(frozen=True)
class PolicySelection:
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
    policy_name: str
    examples: int
    selections: list[PolicySelection] = field(default_factory=list)
    rollout_agreement: int = 0
    problems: list[str] = field(default_factory=list)


class ReplayChosenPolicy:
    name = "replay_chosen"

    @property
    def provenance_config(self) -> dict[str, object]:
        return {}

    def select_action(self, example: DecisionExample) -> PolicyDecision:
        return PolicyDecision(
            legal_action_index=example.chosen_action_index,
            reason="rollout_choice",
        )


def decision_context_from_example(example: DecisionExample) -> DecisionContext:
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
    selections: list[PolicySelection] = []
    problems = [f"batch: {problem}" for problem in batch.problems]
    rollout_agreement = 0

    for example_index, example in enumerate(batch.examples):
        try:
            decision = policy.select_action(example)  # type: ignore[arg-type]
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


def _append_counter(lines: list[str], title: str, counter: Counter[str]) -> None:
    lines.append(f"{title}:")
    if not counter:
        lines.append("  (none)")
        return

    for key, count in counter.most_common():
        lines.append(f"  {key}: {count}")
