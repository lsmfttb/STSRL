"""Batch-level action scoring smoke for packed model input.

This module validates the future model-output contract: one finite score per
flattened legal-action row, then eligible-only argmax per decision example. It
does not implement a trainer, replay buffer, Gymnasium environment, RL
algorithm, or game mechanics.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
import math
from typing import Protocol

from sts_combat_rl.sim.model_input import ModelInputBatch
from sts_combat_rl.sim.policy import DecisionContext


DEFAULT_ACTION_KIND_SCORE_PRIOR: Mapping[str, float] = {
    "card": 3.0,
    "single_card_select": 2.0,
    "multi_card_select": 2.0,
    "end_turn": 1.0,
}


class BatchActionScorer(Protocol):
    """Future model scorer boundary over flattened action rows."""

    name: str

    def score_action_rows(self, batch: ModelInputBatch) -> Sequence[float]:
        """Return one score per flattened legal-action row."""


@dataclass(frozen=True)
class ActionKindPriorScorer:
    """Deterministic scorer used only to smoke-test the model-output contract."""

    kind_scores: Mapping[str, float] = field(
        default_factory=lambda: dict(DEFAULT_ACTION_KIND_SCORE_PRIOR)
    )
    default_score: float = 0.0
    name: str = "action_kind_prior"

    def score_actions(self, context: DecisionContext) -> list[float]:
        return [
            float(self.kind_scores.get(kind, self.default_score))
            for kind in context.legal_action_kinds
        ]

    def score_action_rows(self, batch: ModelInputBatch) -> list[float]:
        scores: list[float] = []
        for kinds in batch.action_kinds:
            scores.extend(
                float(self.kind_scores.get(kind, self.default_score)) for kind in kinds
            )
        return scores


@dataclass(frozen=True)
class LinearActionScorer:
    """Fixed-weight scorer used to validate the future model adapter shape.

    The weights are not learned here. Training can later replace this object
    with a model-backed implementation exposing the same methods.
    """

    snapshot_weights: Sequence[float] = ()
    action_weights: Sequence[float] = ()
    bias: float = 0.0
    name: str = "linear_action"

    def score_actions(self, context: DecisionContext) -> list[float]:
        base_score = self._snapshot_score(context.snapshot_features)
        return [
            base_score + self._action_score(action_features)
            for action_features in context.legal_action_features
        ]

    def score_action_rows(self, batch: ModelInputBatch) -> list[float]:
        scores: list[float] = []
        for example_index, snapshot_features in enumerate(batch.snapshot_features):
            if example_index + 1 >= len(batch.action_offsets):
                raise ValueError(f"example {example_index}: missing action offset")
            base_score = self._snapshot_score(snapshot_features)
            action_start = batch.action_offsets[example_index]
            action_end = batch.action_offsets[example_index + 1]
            scores.extend(
                base_score + self._action_score(action_features)
                for action_features in batch.action_features[action_start:action_end]
            )
        return scores

    def _snapshot_score(self, features: Sequence[float]) -> float:
        if not self.snapshot_weights:
            return float(self.bias)
        if len(self.snapshot_weights) != len(features):
            raise ValueError(
                f"snapshot weight size {len(self.snapshot_weights)} does not "
                f"match {len(features)} snapshot features"
            )
        return float(self.bias) + _dot(self.snapshot_weights, features)

    def _action_score(self, features: Sequence[float]) -> float:
        if not self.action_weights:
            return 0.0
        if len(self.action_weights) != len(features):
            raise ValueError(
                f"action weight size {len(self.action_weights)} does not "
                f"match {len(features)} action features"
            )
        return _dot(self.action_weights, features)


@dataclass(frozen=True)
class ModelScoreSelection:
    """One eligible-argmax selection from flattened action-row scores."""

    example_index: int
    selected_action_index: int
    selected_action_row: int
    selected_action_kind: str
    selected_score: float
    chosen_action_index: int
    chosen_action_row: int
    chosen_action_kind: str
    chosen_score: float | None = None
    matches_chosen_action: bool = False


@dataclass(frozen=True)
class ModelScoreSmokeReport:
    """Summary of scorer-output shape and eligible argmax checks."""

    scorer_name: str
    reward_allocation: str
    scoring_ok: bool
    example_count: int
    action_rows: int
    score_count: int
    selection_count: int
    chosen_action_agreement: int
    min_score: float | None = None
    max_score: float | None = None
    selected_action_kind_counts: Counter[str] = field(default_factory=Counter)
    chosen_action_kind_counts: Counter[str] = field(default_factory=Counter)
    selected_score_counts: Counter[str] = field(default_factory=Counter)
    selections: list[ModelScoreSelection] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)


def score_model_input_batch(
    batch: ModelInputBatch,
    scorer: BatchActionScorer | None = None,
) -> ModelScoreSmokeReport:
    """Score flattened action rows and choose eligible argmax per example."""

    active_scorer = scorer or ActionKindPriorScorer()
    problems = list(batch.problems)
    try:
        raw_scores = active_scorer.score_action_rows(batch)
        scores = [float(score) for score in raw_scores]
    except ValueError as exc:
        scores = []
        problems.append(f"scorer {active_scorer.name}: {exc}")
    problems.extend(_score_shape_problems(batch, scores))
    selections = _select_eligible_argmax(batch, scores, problems)
    finite_scores = [score for score in scores if math.isfinite(score)]
    return ModelScoreSmokeReport(
        scorer_name=active_scorer.name,
        reward_allocation=batch.reward_allocation,
        scoring_ok=not problems,
        example_count=len(batch.example_refs),
        action_rows=len(batch.action_features),
        score_count=len(scores),
        selection_count=len(selections),
        chosen_action_agreement=sum(
            1 for selection in selections if selection.matches_chosen_action
        ),
        min_score=min(finite_scores) if finite_scores else None,
        max_score=max(finite_scores) if finite_scores else None,
        selected_action_kind_counts=Counter(
            selection.selected_action_kind for selection in selections
        ),
        chosen_action_kind_counts=Counter(
            selection.chosen_action_kind for selection in selections
        ),
        selected_score_counts=Counter(
            _score_label(selection.selected_score) for selection in selections
        ),
        selections=selections,
        problems=problems,
    )


def format_model_score_smoke_report(
    report: ModelScoreSmokeReport,
    *,
    detail_limit: int = 8,
) -> str:
    """Format scorer-output smoke results for stderr."""

    agreement_denominator = report.selection_count if report.selection_count else 0
    lines = [
        "Model score smoke summary",
        "scope: scoring contract only; no trainer, environment, or RL algorithm",
        f"scorer: {report.scorer_name}",
        f"reward allocation: {report.reward_allocation}",
        f"scoring ok: {_yes_no(report.scoring_ok)}",
        f"examples: {report.example_count}",
        f"action rows: {report.action_rows}",
        f"scores: {report.score_count}",
        f"selections: {report.selection_count}",
        (
            "agreement with collected actions: "
            f"{report.chosen_action_agreement}/{agreement_denominator}"
        ),
        f"min score: {_optional_score(report.min_score)}",
        f"max score: {_optional_score(report.max_score)}",
    ]
    _append_counter(lines, "selected action kinds", report.selected_action_kind_counts)
    _append_counter(lines, "collected action kinds", report.chosen_action_kind_counts)
    _append_counter(lines, "selected score values", report.selected_score_counts)
    _append_selection_details(lines, report.selections, detail_limit)

    lines.append("problems:")
    if report.problems:
        lines.extend(f"  {problem}" for problem in report.problems)
    else:
        lines.append("  (none)")

    return "\n".join(lines)


def _score_shape_problems(
    batch: ModelInputBatch,
    scores: list[float],
) -> list[str]:
    problems: list[str] = []
    action_row_count = len(batch.action_features)
    if len(scores) != action_row_count:
        problems.append(
            f"score count {len(scores)} does not match {action_row_count} action rows"
        )
        return problems
    for action_row, score in enumerate(scores):
        if not math.isfinite(score):
            problems.append(
                f"score for action row {action_row} is not finite: {score!r}"
            )
    return problems


def _select_eligible_argmax(
    batch: ModelInputBatch,
    scores: list[float],
    problems: list[str],
) -> list[ModelScoreSelection]:
    selections: list[ModelScoreSelection] = []
    if len(scores) != len(batch.action_features):
        return selections

    for example_index, eligible_rows in enumerate(batch.eligible_action_rows):
        if example_index + 1 >= len(batch.action_offsets):
            problems.append(f"example {example_index}: missing action offset")
            continue
        action_start = batch.action_offsets[example_index]
        action_end = batch.action_offsets[example_index + 1]
        if not eligible_rows:
            problems.append(f"example {example_index}: empty eligible action rows")
            continue
        invalid_rows = [
            row for row in eligible_rows if row < action_start or row >= action_end
        ]
        if invalid_rows:
            problems.append(
                f"example {example_index}: eligible action row {invalid_rows[0]} "
                f"outside [{action_start}, {action_end})"
            )
            continue

        selected_row = _best_row(eligible_rows, scores)
        selected_index = selected_row - action_start
        selected_kind = _action_kind(batch, example_index, selected_index)
        chosen_index = _item(batch.chosen_action_indices, example_index, -1)
        chosen_row = _item(batch.chosen_action_rows, example_index, -1)
        chosen_kind = _item(batch.chosen_action_kinds, example_index, "(missing)")
        chosen_score = scores[chosen_row] if 0 <= chosen_row < len(scores) else None
        selections.append(
            ModelScoreSelection(
                example_index=example_index,
                selected_action_index=selected_index,
                selected_action_row=selected_row,
                selected_action_kind=selected_kind,
                selected_score=scores[selected_row],
                chosen_action_index=chosen_index,
                chosen_action_row=chosen_row,
                chosen_action_kind=chosen_kind,
                chosen_score=chosen_score,
                matches_chosen_action=selected_row == chosen_row,
            )
        )
    return selections


def _best_row(eligible_rows: list[int], scores: list[float]) -> int:
    best_row = eligible_rows[0]
    best_score = scores[best_row]
    for row in eligible_rows[1:]:
        score = scores[row]
        if score > best_score:
            best_row = row
            best_score = score
    return best_row


def _action_kind(
    batch: ModelInputBatch,
    example_index: int,
    action_index: int,
) -> str:
    kinds = _item(batch.action_kinds, example_index, [])
    if action_index < 0 or action_index >= len(kinds):
        return "(invalid)"
    return str(kinds[action_index])


def _append_selection_details(
    lines: list[str],
    selections: list[ModelScoreSelection],
    detail_limit: int,
) -> None:
    lines.append(f"selection examples (limit {detail_limit}):")
    if detail_limit <= 0:
        lines.append("  (disabled)")
        return
    if not selections:
        lines.append("  (none)")
        return

    for selection in selections[:detail_limit]:
        lines.append(
            "  "
            f"example={selection.example_index} "
            f"selected={selection.selected_action_kind}"
            f"[{selection.selected_action_index}] "
            f"score={selection.selected_score:.3f} "
            f"collected={selection.chosen_action_kind}"
            f"[{selection.chosen_action_index}] "
            f"match={_yes_no(selection.matches_chosen_action)}"
        )


def _append_counter(lines: list[str], title: str, counter: Counter[str]) -> None:
    lines.append(f"{title}:")
    if not counter:
        lines.append("  (none)")
        return

    for key, count in counter.most_common():
        lines.append(f"  {key}: {count}")


def _item(values: list[object], index: int, default: object) -> object:
    if index < 0 or index >= len(values):
        return default
    return values[index]


def _dot(weights: Sequence[float], features: Sequence[float]) -> float:
    total = 0.0
    for weight, feature in zip(weights, features, strict=True):
        total += float(weight) * float(feature)
    return total


def _score_label(score: float) -> str:
    return f"{score:.3f}"


def _optional_score(value: float | None) -> str:
    return f"{value:.3f}" if value is not None else "(none)"


def _yes_no(value: bool) -> str:
    return "yes" if value else "no"
