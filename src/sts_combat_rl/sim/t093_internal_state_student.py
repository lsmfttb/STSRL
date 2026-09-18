"""Fail-closed, offline T093 materialization and evaluation primitives.

T093 consumes retained T092 records only.  In particular this module has no
simulator import or Search call: ``mean_value`` and ``visits`` are labels and
admission facts, while the scorer receives only public-tactical-v2 encodings.
"""

from __future__ import annotations

import hashlib
import math
import random
import statistics
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from typing import Any

from sts_combat_rl.sim.contract import SimulatorAction
from sts_combat_rl.sim.features import encode_lightspeed_battle_snapshot, encode_simulator_actions
from sts_combat_rl.sim.t090_battle_student import canonical_sha256
from sts_combat_rl.sim.t092_internal_search_state import (
    T092_FROZEN_TEACHER_CONFIG,
    T092_NATIVE_IDENTITY,
    validate_retained_occurrence,
)

T093_TASK_ID = "T093"
T093_N_MIN = 4
T093_PAIR_TOLERANCE = 1e-9
T093_MODEL_SEEDS = (930093, 930094, 930095)
T093_BOOTSTRAP_SEED = 930293
T093_BOOTSTRAP_REPLICATES = 20_000
T093_LABEL_DOMAIN = "T093-LABEL-DESTRUCTION-V1"
T093_MATERIALIZATION_SCHEMA_ID = "t093-internal-partial-ranking-corpus-v1"
T093_CONFIG_SCHEMA_ID = "t093-internal-state-student-config-v1"
T093_REPORT_SCHEMA_ID = "t093-internal-state-student-report-v1"
T093_SOURCE_GROUPS = ("A", "B", "C")
T093_SPLITS = ("train", "validation", "heldout")
T093_EXACT_T092_EVIDENCE_SHA256 = (
    "ac6d03ccce403c3474a75221e547a6058d5b7f419af7d8df9ddd8dbb225c562a"
)
T093_EXACT_T092_RETENTION_SHA256 = (
    "32f4b04f31c91cf58928503d51023ba53c98f310bcb96644503040b2fd9d18b7"
)
T093_MIN_FINGERPRINTS = {"train": 10_000, "validation": 2_000, "heldout": 3_000}
T093_MIN_CONTRIBUTING_STARTS = {
    "train": {"A": 44, "B": 90, "C": 60},
    "validation": {"A": 11, "B": 23, "C": 15},
    "heldout": {"A": 16, "B": 33, "C": 22},
}


class T093Error(ValueError):
    """A retained-artifact, public-boundary, or gate violation."""


def _finite(value: object, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        raise T093Error(f"{label} must be finite")
    return float(value)


def _percentile(values: Sequence[float], quantile: float) -> float:
    ordered = sorted(values)
    if not ordered:
        raise T093Error("cannot calculate percentile of no values")
    point = (len(ordered) - 1) * quantile
    low, high = math.floor(point), math.ceil(point)
    return ordered[low] if low == high else ordered[low] + (ordered[high] - ordered[low]) * (point - low)


@dataclass(frozen=True)
class T093Example:
    source_identity: str
    source_group: str
    split: str
    parent_root_decision_identity: str
    occurrence_identity: str
    public_fingerprint: str
    tree_depth: int
    state_features: tuple[float, ...]
    action_features: tuple[tuple[float, ...], ...]
    action_identities: tuple[Mapping[str, object], ...]
    action_kinds: tuple[str, ...]
    teacher_means: tuple[float, ...]

    @property
    def pairs(self) -> tuple[tuple[int, int], ...]:
        rows: list[tuple[int, int]] = []
        for left in range(len(self.teacher_means)):
            for right in range(left + 1, len(self.teacher_means)):
                delta = self.teacher_means[left] - self.teacher_means[right]
                if abs(delta) > T093_PAIR_TOLERANCE:
                    rows.append((left, right) if delta > 0 else (right, left))
        return tuple(rows)


def _public_action(action: Mapping[str, object]) -> SimulatorAction:
    # ``bits`` is intentionally omitted: it is a simulator-native field, not
    # a public student feature. T092 separately established idx parameters as
    # part of its public action identity boundary.
    required = {"scope", "bits", "kind", "idx1", "idx2", "idx3", "label"}
    if set(action) != required or action.get("scope") != "battle":
        raise T093Error("T092 searchable action is not the registered public shape")
    raw = {key: action[key] for key in ("scope", "idx1", "idx2", "idx3")}
    if not all(isinstance(raw[key], int) and not isinstance(raw[key], bool) for key in ("idx1", "idx2", "idx3")):
        raise T093Error("T092 public action parameters are invalid")
    return SimulatorAction(
        action_id=canonical_sha256({"public_action": dict(action)}),
        label=str(action["label"]), kind=str(action["kind"]), raw=raw,
    )


def example_from_t092_occurrence(value: Mapping[str, object]) -> T093Example | None:
    """Turn one validated T092 row into the n_min=4 public-only example."""

    occurrence = validate_retained_occurrence(value)
    if occurrence.tree_depth < 1:
        raise T093Error("T093 admits only T092 depth>=1 occurrences")
    supported = [
        row for row in occurrence.searchable_actions
        if int(row["visits"]) >= T093_N_MIN and row["mean_value"] is not None
    ]
    if len(supported) < 2:
        return None
    actions = [_public_action(dict(row["action"])) for row in supported]
    state = tuple(float(item) for item in encode_lightspeed_battle_snapshot(occurrence.public_battle_projection))
    action_features = tuple(
        tuple(float(item) for item in row)
        for row in encode_simulator_actions(actions, occurrence.public_battle_projection)
    )
    means = tuple(_finite(row["mean_value"], "T092 teacher mean") for row in supported)
    result = T093Example(
        occurrence.source_identity, occurrence.source_group, occurrence.split,
        occurrence.parent_root_decision_identity, occurrence.occurrence_identity,
        occurrence.fingerprint, occurrence.tree_depth, state, action_features,
        tuple(dict(row["action"]) for row in supported),
        tuple(str(row["action"]["kind"]) for row in supported), means,
    )
    return result if result.pairs else None


def _canonicalize(examples: Sequence[T093Example]) -> tuple[list[T093Example], dict[str, object]]:
    grouped: dict[str, list[T093Example]] = defaultdict(list)
    for example in examples:
        grouped[example.public_fingerprint].append(example)
    retained: list[T093Example] = []
    collisions: list[dict[str, object]] = []
    duplicates: list[dict[str, object]] = []
    for fingerprint, rows in grouped.items():
        splits = sorted({row.split for row in rows})
        if len(splits) > 1:
            collisions.append({"public_fingerprint": fingerprint, "splits": splits, "source_identities": sorted({r.source_identity for r in rows})})
            continue
        chosen = min(rows, key=lambda row: (row.source_identity, row.parent_root_decision_identity, row.occurrence_identity))
        retained.append(chosen)
        if len(rows) > 1:
            duplicates.append({"public_fingerprint": fingerprint, "split": chosen.split, "canonical_occurrence": chosen.occurrence_identity, "multiplicity": len(rows)})
    retained.sort(key=lambda row: (row.split, row.source_group, row.source_identity, row.parent_root_decision_identity, row.occurrence_identity))
    return retained, {"cross_split_excluded": collisions, "within_split_deduplicated": duplicates}


def materialize_t093_corpus(
    occurrences: Sequence[Mapping[str, object]], *, t092_evidence: Mapping[str, object],
    t092_retention_manifest: Mapping[str, object],
) -> dict[str, object]:
    """Materialize rows after exact T092 evidence/manifest bindings are checked."""

    if t092_evidence.get("schema_id") != "t092-formal-telemetry-evidence-v1" or t092_evidence.get("terminal_classification") != "INTERNAL_SEARCH_SURFACE_DENSE_ENOUGH":
        raise T093Error("T092 evidence is not the accepted dense internal surface")
    if t092_retention_manifest.get("schema_id") != "t092-formal-retention-manifest-v1":
        raise T093Error("T092 retention manifest schema is invalid")
    evidence = t092_retention_manifest.get("formal_evidence")
    if not isinstance(evidence, Mapping) or evidence.get("sha256") != T093_EXACT_T092_EVIDENCE_SHA256:
        raise T093Error("T092 retention manifest does not bind accepted evidence")
    raw: list[T093Example] = []
    for occurrence in occurrences:
        if not isinstance(occurrence, Mapping):
            raise T093Error("T092 occurrence is malformed")
        example = example_from_t092_occurrence(occurrence)
        if example is not None:
            raw.append(example)
    examples, deduplication = _canonicalize(raw)
    report = effective_diversity_report(examples)
    return {
        "schema_id": T093_MATERIALIZATION_SCHEMA_ID, "schema_version": 1, "task_id": T093_TASK_ID,
        "primary_n_min": T093_N_MIN, "pair_tolerance": T093_PAIR_TOLERANCE,
        "t092_evidence_sha256": T093_EXACT_T092_EVIDENCE_SHA256,
        "t092_retention_manifest_sha256": T093_EXACT_T092_RETENTION_SHA256,
        "t092_native_identity": dict(T092_NATIVE_IDENTITY), "teacher_config": dict(T092_FROZEN_TEACHER_CONFIG),
        "raw_pair_bearing_occurrence_count": len(raw), "examples": [asdict(item) for item in examples],
        "deduplication": deduplication, "effective_diversity": report,
    }


def effective_diversity_report(examples: Sequence[T093Example]) -> dict[str, object]:
    by_split = {split: [row for row in examples if row.split == split] for split in T093_SPLITS}
    cells = {
        split: {group: len({row.source_identity for row in rows if row.source_group == group}) for group in T093_SOURCE_GROUPS}
        for split, rows in by_split.items()
    }
    passed = all(len(by_split[split]) >= T093_MIN_FINGERPRINTS[split] for split in T093_SPLITS) and all(
        cells[split][group] >= T093_MIN_CONTRIBUTING_STARTS[split][group]
        for split in T093_SPLITS for group in T093_SOURCE_GROUPS
    )
    return {
        "canonical_pair_bearing_fingerprints": {split: len(by_split[split]) for split in T093_SPLITS},
        "contributing_source_starts": cells,
        "required_minima": {"fingerprints": dict(T093_MIN_FINGERPRINTS), "source_starts": T093_MIN_CONTRIBUTING_STARTS},
        "passed": passed,
    }


@dataclass(frozen=True)
class T093TrainingConfig:
    state_feature_size: int
    action_feature_size: int
    schema_id: str = T093_CONFIG_SCHEMA_ID
    schema_version: int = 1
    task_id: str = T093_TASK_ID
    hidden_width: int = 256
    hidden_layers: int = 2
    activation: str = "relu"
    optimizer: str = "AdamW"
    learning_rate: float = 1e-3
    weight_decay: float = 1e-4
    max_epochs: int = 30
    model_seeds: tuple[int, ...] = T093_MODEL_SEEDS

    def __post_init__(self) -> None:
        if (
            self.schema_id != T093_CONFIG_SCHEMA_ID
            or self.schema_version != 1
            or self.task_id != T093_TASK_ID
        ):
            raise T093Error("T093 training config identity is frozen")
        if (self.hidden_width, self.hidden_layers, self.activation, self.optimizer, self.learning_rate, self.weight_decay, self.max_epochs, self.model_seeds) != (256, 2, "relu", "AdamW", 1e-3, 1e-4, 30, T093_MODEL_SEEDS):
            raise T093Error("T093 model/optimization configuration is frozen")
        if self.state_feature_size < 1 or self.action_feature_size < 1:
            raise T093Error("T093 public encoding widths must be positive")

    def to_dict(self) -> dict[str, object]:
        value = asdict(self); value["model_seeds"] = list(self.model_seeds); return value


def build_t093_training_config(examples: Sequence[T093Example]) -> T093TrainingConfig:
    state_sizes = {len(item.state_features) for item in examples}
    action_sizes = {len(action) for item in examples for action in item.action_features}
    if len(state_sizes) != 1 or len(action_sizes) != 1:
        raise T093Error("T093 public feature widths are inconsistent")
    return T093TrainingConfig(state_sizes.pop(), action_sizes.pop())


def label_destruction_means(example: T093Example) -> tuple[float, ...]:
    """Cyclically remap supported targets; identity shifts are never allowed."""

    size = len(example.teacher_means)
    if size < 2:
        raise T093Error("label destruction requires at least two supported actions")
    digest = hashlib.sha256(f"{T093_LABEL_DOMAIN}:{example.public_fingerprint}".encode()).digest()
    shift = (int.from_bytes(digest[:8], "big") % (size - 1)) + 1
    return tuple(example.teacher_means[(index + shift) % size] for index in range(size))


class T093TorchScorer:
    """Fixed public-only action scorer; it has no Search or simulator handle."""

    def __init__(self, model: Any, config: T093TrainingConfig, *, arm: str) -> None:
        self.model, self.config, self.arm = model, config, arm

    def score(self, example: T093Example) -> list[float]:
        import torch

        if (
            len(example.state_features) != self.config.state_feature_size
            or any(
                len(action) != self.config.action_feature_size
                for action in example.action_features
            )
        ):
            raise T093Error("held-out public feature width differs from train/validation")
        state = (0.0,) * len(example.state_features) if self.arm == "state_ablated" else example.state_features
        self.model.eval()
        with torch.no_grad():
            states = torch.tensor(state, dtype=torch.float32).repeat(len(example.action_features), 1)
            actions = torch.tensor(example.action_features, dtype=torch.float32)
            return [float(value) for value in self.model(torch.cat((states, actions), dim=1)).reshape(-1).tolist()]


def _model(config: T093TrainingConfig, seed: int) -> Any:
    import torch

    torch.manual_seed(seed)
    width = config.state_feature_size + config.action_feature_size
    return torch.nn.Sequential(
        torch.nn.Linear(width, 256), torch.nn.ReLU(), torch.nn.Linear(256, 256),
        torch.nn.ReLU(), torch.nn.Linear(256, 1),
    )


def _arm_means(example: T093Example, arm: str) -> tuple[float, ...]:
    if arm == "true" or arm == "state_ablated":
        return example.teacher_means
    if arm == "label_destruction":
        return label_destruction_means(example)
    raise T093Error("T093 arm is invalid")


def _loss_for_example(model: Any, example: T093Example, arm: str) -> Any:
    import torch
    from torch.nn import functional

    state = (0.0,) * len(example.state_features) if arm == "state_ablated" else example.state_features
    states = torch.tensor(state, dtype=torch.float32).repeat(len(example.action_features), 1)
    actions = torch.tensor(example.action_features, dtype=torch.float32)
    scores = model(torch.cat((states, actions), dim=1)).reshape(-1)
    means = _arm_means(example, arm)
    terms = [functional.softplus(-(scores[high] - scores[low])) for high, low in T093Example(
        example.source_identity, example.source_group, example.split,
        example.parent_root_decision_identity, example.occurrence_identity,
        example.public_fingerprint, example.tree_depth, example.state_features,
        example.action_features, example.action_identities, example.action_kinds, means,
    ).pairs]
    if not terms:
        raise T093Error("pair-bearing T093 example has no non-tied pairs")
    return sum(terms) / len(terms)


def _macro_loss(model: Any, examples: Sequence[T093Example], arm: str) -> Any:
    """Exact fingerprint -> source-start macro hierarchy for one split."""

    by_source: dict[str, list[T093Example]] = defaultdict(list)
    for item in examples:
        by_source[item.source_identity].append(item)
    if not by_source:
        raise T093Error("T093 loss requires pair-bearing examples")
    source_losses = [sum(_loss_for_example(model, item, arm) for item in rows) / len(rows) for rows in by_source.values()]
    return sum(source_losses) / len(source_losses)


def train_t093_scorer(
    examples: Sequence[T093Example], *, seed: int, arm: str,
) -> tuple[T093TorchScorer, dict[str, object]]:
    """Train one registered arm without reading held-out rows.

    Validation selects the minimum loss checkpoint.  The label-destruction arm
    uses its cyclically destroyed validation labels; the other arms use true
    labels, exactly as preregistered.
    """

    if seed not in T093_MODEL_SEEDS or arm not in {"true", "label_destruction", "state_ablated"}:
        raise T093Error("T093 seed or arm is invalid")
    train = [item for item in examples if item.split == "train"]
    validation = [item for item in examples if item.split == "validation"]
    if not train or not validation:
        raise T093Error("T093 training requires train and validation examples")
    # Do not open held-out examples merely to construct the model. Evaluation
    # separately checks that its already-frozen public widths match this config.
    config = build_t093_training_config(train + validation)
    import torch

    model = _model(config, seed)
    optimizer = torch.optim.AdamW(model.parameters(), lr=1e-3, weight_decay=1e-4)
    curves: list[dict[str, float]] = []
    selected_epoch, selected_loss, selected_state = 0, math.inf, None
    for epoch in range(1, 31):
        model.train(); optimizer.zero_grad()
        loss = _macro_loss(model, train, arm)
        loss.backward(); optimizer.step()
        model.eval()
        with torch.no_grad():
            validation_loss = float(_macro_loss(model, validation, arm))
        curves.append({"epoch": epoch, "train_loss": float(loss.detach()), "validation_loss": validation_loss})
        if validation_loss < selected_loss:
            selected_epoch, selected_loss = epoch, validation_loss
            selected_state = {key: value.detach().clone() for key, value in model.state_dict().items()}
    if selected_state is None:
        raise T093Error("T093 checkpoint selection failed")
    model.load_state_dict(selected_state)
    scorer = T093TorchScorer(model, config, arm=arm)
    return scorer, {"schema_id": "t093-training-summary-v1", "task_id": T093_TASK_ID,
                    "arm": arm, "seed": seed, "selected_epoch": selected_epoch,
                    "selection_split": "validation", "selection_metric": "pairwise_logistic_ranking_loss",
                    "selection_labels": "destroyed" if arm == "label_destruction" else "true",
                    "learning_curve": curves, "selected_validation_loss": selected_loss,
                    "training_config": config.to_dict()}


def evaluate_t093_scorer(examples: Sequence[T093Example], scorer: T093TorchScorer) -> dict[str, object]:
    scores = {item.public_fingerprint: scorer.score(item) for item in examples}
    return source_start_macro_accuracy(examples, scores)


def train_validation_adequacy(
    *, train_true: Sequence[Mapping[str, object]], validation_true: Sequence[Mapping[str, object]],
    validation_label_destruction: Sequence[Mapping[str, object]], validation_state_ablated: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    """Apply the frozen admission test before any held-out metric is opened."""

    def by_seed(rows: Sequence[Mapping[str, object]]) -> dict[int, float]:
        result: dict[int, float] = {}
        for row in rows:
            seed, value = row.get("seed"), row.get("source_start_macro_accuracy")
            if seed not in T093_MODEL_SEEDS or seed in result or value is None:
                raise T093Error("adequacy rows must contain each registered seed once")
            result[int(seed)] = _finite(value, "source-start macro accuracy")
        if set(result) != set(T093_MODEL_SEEDS):
            raise T093Error("adequacy requires all three registered seeds")
        return result
    train = by_seed(train_true); true = by_seed(validation_true)
    destroyed = by_seed(validation_label_destruction); ablated = by_seed(validation_state_ablated)
    fit = sum(value >= .70 for value in train.values()) >= 2
    transfer = sum(true[seed] > .5 and true[seed] > destroyed[seed] and true[seed] > ablated[seed] for seed in T093_MODEL_SEEDS) >= 2
    return {"train_true_by_seed": train, "validation_true_by_seed": true,
            "validation_label_destruction_by_seed": destroyed,
            "validation_state_ablated_by_seed": ablated,
            "fit_predicate_passed": fit, "transfer_predicate_passed": transfer,
            "passed": fit and transfer, "heldout_opened": fit and transfer}


def heldout_t093_gate(
    *, true_by_seed: Mapping[int, Mapping[str, object]],
    label_destruction_by_seed: Mapping[int, Mapping[str, object]],
    state_ablated_by_seed: Mapping[int, Mapping[str, object]],
) -> dict[str, object]:
    """Compute the held-out gate from already-admitted per-seed start rows."""

    def rows_by_seed(values: Mapping[int, Mapping[str, object]]) -> tuple[dict[str, float], dict[str, str]]:
        if set(values) != set(T093_MODEL_SEEDS):
            raise T093Error("held-out report requires all registered seeds")
        per_seed: list[dict[str, float]] = []
        groups: dict[str, str] = {}
        for seed in T093_MODEL_SEEDS:
            rows = values[seed].get("source_start_rows")
            if not isinstance(rows, Sequence):
                raise T093Error("held-out source-start rows are unavailable")
            table: dict[str, float] = {}
            for row in rows:
                if not isinstance(row, Mapping):
                    raise T093Error("held-out source-start row is malformed")
                source, group = row.get("source_identity"), row.get("source_group")
                if not isinstance(source, str) or group not in T093_SOURCE_GROUPS:
                    raise T093Error("held-out source ownership is invalid")
                table[source] = _finite(row.get("accuracy"), "held-out accuracy")
                prior = groups.setdefault(source, str(group))
                if prior != group:
                    raise T093Error("held-out source group changes between seeds")
            per_seed.append(table)
        if any(set(table) != set(per_seed[0]) for table in per_seed):
            raise T093Error("held-out seeds are not paired on source starts")
        return ({source: statistics.fmean(table[source] for table in per_seed) for source in per_seed[0]}, groups)
    true, groups = rows_by_seed(true_by_seed)
    destroyed, destroyed_groups = rows_by_seed(label_destruction_by_seed)
    ablated, ablated_groups = rows_by_seed(state_ablated_by_seed)
    if groups != destroyed_groups or groups != ablated_groups or set(true) != set(destroyed) or set(true) != set(ablated):
        raise T093Error("held-out arms are not exactly paired")
    bootstrap = stratified_start_bootstrap({
        "true_student": true, "label_destruction": destroyed, "state_ablated": ablated,
        "true_minus_label_destruction": {source: true[source] - destroyed[source] for source in true},
        "true_minus_state_ablated": {source: true[source] - ablated[source] for source in true},
        "__groups__": groups,
    })
    arms = bootstrap["arms"]
    matched_seed_passes = sum(
        true_by_seed[seed]["source_start_macro_accuracy"] > .5
        and true_by_seed[seed]["source_start_macro_accuracy"] > label_destruction_by_seed[seed]["source_start_macro_accuracy"]
        and true_by_seed[seed]["source_start_macro_accuracy"] > state_ablated_by_seed[seed]["source_start_macro_accuracy"]
        for seed in T093_MODEL_SEEDS
    )
    passed = (
        arms["true_student"]["ci_95"][0] > .5
        and arms["true_minus_label_destruction"]["ci_95"][0] > 0
        and arms["true_minus_state_ablated"]["ci_95"][0] > 0
        and matched_seed_passes >= 2
    )
    return {"schema_id": T093_REPORT_SCHEMA_ID, "sampling": bootstrap,
            "matched_seed_pass_count": matched_seed_passes, "chance_reference": .5,
            "passed": passed}


def source_start_macro_accuracy(
    examples: Sequence[T093Example], score: Mapping[str, Sequence[float]],
) -> dict[str, object]:
    """Macro average pairs->fingerprints->starts, retaining paired start rows."""

    fingerprints: dict[str, list[float]] = defaultdict(list)
    source_for_fingerprint: dict[str, tuple[str, str]] = {}
    for example in examples:
        values = score.get(example.public_fingerprint)
        if values is None or len(values) != len(example.teacher_means):
            raise T093Error("score rows do not cover aligned public actions")
        comparisons = [float(values[high]) > float(values[low]) for high, low in example.pairs]
        fingerprints[example.public_fingerprint].append(statistics.fmean(comparisons))
        source_for_fingerprint[example.public_fingerprint] = (example.source_identity, example.source_group)
    starts: dict[str, list[float]] = defaultdict(list)
    groups: dict[str, str] = {}
    for fingerprint, values in fingerprints.items():
        source, group = source_for_fingerprint[fingerprint]
        starts[source].append(statistics.fmean(values)); groups[source] = group
    rows = [{"source_identity": source, "source_group": groups[source], "accuracy": statistics.fmean(values)} for source, values in sorted(starts.items())]
    return {"source_start_rows": rows, "source_start_macro_accuracy": statistics.fmean(row["accuracy"] for row in rows) if rows else None}


def stratified_start_bootstrap(
    values: Mapping[str, Mapping[str, float]], *, seed: int = T093_BOOTSTRAP_SEED,
    replicates: int = T093_BOOTSTRAP_REPLICATES,
) -> dict[str, object]:
    """Paired A/B/C source-start bootstrap; values are arm -> source -> metric."""

    if replicates != T093_BOOTSTRAP_REPLICATES or seed != T093_BOOTSTRAP_SEED:
        raise T093Error("T093 bootstrap configuration is frozen")
    arms = tuple(values)
    if not arms or any(set(values[arm]) != set(values[arms[0]]) for arm in arms):
        raise T093Error("bootstrap arms must be paired on identical source starts")
    groups: dict[str, list[str]] = defaultdict(list)
    # The report callers supply source groups under the reserved __groups__ arm
    group_values = values.get("__groups__")
    if not isinstance(group_values, Mapping):
        raise T093Error("bootstrap requires explicit source-group ownership")
    metric_arms = tuple(arm for arm in arms if arm != "__groups__")
    for source, group in group_values.items():
        if group not in T093_SOURCE_GROUPS or source not in values[metric_arms[0]]:
            raise T093Error("bootstrap source group is invalid")
        groups[str(group)].append(str(source))
    if any(not groups[group] for group in T093_SOURCE_GROUPS):
        raise T093Error("bootstrap requires contributing starts in every source group")
    rng = random.Random(seed)
    samples: dict[str, list[float]] = {arm: [] for arm in metric_arms}
    for _ in range(replicates):
        sampled = [rng.choice(groups[group]) for group in T093_SOURCE_GROUPS for _ in groups[group]]
        for arm in metric_arms:
            samples[arm].append(statistics.fmean(float(values[arm][source]) for source in sampled))
    return {"sampling_unit": "heldout_source_battle_start", "strata": {group: len(rows) for group, rows in groups.items()}, "seed": seed, "replicates": replicates,
            "arms": {arm: {"point": statistics.fmean(float(v) for v in values[arm].values()), "ci_95": [_percentile(samples[arm], .025), _percentile(samples[arm], .975)]} for arm in metric_arms}}


def classify_t093(
    *, information_valid: bool, evidence_valid: bool, diversity: Mapping[str, object],
    adequacy: Mapping[str, object], heldout: Mapping[str, object] | None = None,
    conflict_limited: bool = False,
) -> str:
    if not information_valid:
        return "INTERNAL_STATE_STUDENT_INFORMATION_BOUNDARY_INVALID"
    if not evidence_valid:
        return "INCOMPLETE"
    if diversity.get("passed") is not True:
        return "INTERNAL_STATE_STUDENT_EFFECTIVE_DIVERSITY_INSUFFICIENT"
    if adequacy.get("passed") is not True:
        return "INTERNAL_STATE_STUDENT_MODEL_OR_TARGET_INADEQUATE"
    if heldout is None:
        raise T093Error("held-out result is required after adequacy admission")
    if heldout.get("passed") is True:
        return "INTERNAL_STATE_BATTLE_STUDENT_SIGNAL_ESTABLISHED"
    return "INTERNAL_STATE_STUDENT_REPEATED_PUBLIC_CONFLICT_LIMITING" if conflict_limited else "INTERNAL_STATE_STUDENT_GENERALIZATION_NOT_ESTABLISHED"


__all__ = [
    "T093_BOOTSTRAP_REPLICATES", "T093_BOOTSTRAP_SEED", "T093_CONFIG_SCHEMA_ID",
    "T093Error", "T093Example", "T093TrainingConfig", "build_t093_training_config",
    "classify_t093", "effective_diversity_report", "example_from_t092_occurrence",
    "evaluate_t093_scorer", "heldout_t093_gate", "label_destruction_means",
    "materialize_t093_corpus", "source_start_macro_accuracy", "stratified_start_bootstrap",
    "train_t093_scorer", "train_validation_adequacy",
]
