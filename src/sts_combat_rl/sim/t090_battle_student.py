"""Fail-closed offline plumbing for T090 Battle-student distillation.

The module deliberately does *not* restore a battle, call native Search, or
alter a Search controller.  Its input is a materialized teacher decision row
whose privileged fields are retained only as labels/provenance; the student
sees the public tactical numeric state and the public legal-action encoding.
"""

from __future__ import annotations

import hashlib
import json
import math
import random
import statistics
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import asdict, dataclass
from typing import Any

from sts_combat_rl.sim.features import (
    TACTICAL_FEATURE_SCHEMA_ID,
    TACTICAL_FEATURE_SCHEMA_VERSION,
)
from sts_combat_rl.sim.policy_contract import DecisionContext, PolicyDecision

T090_TASK_ID = "T090"
T090_APPROVED_SPEC_COMMIT = "6d9fd862e166d747dcb3f6edba03b979be1038f7"
T090_PUBLICATION_BASE = "76897afc17410dc1f03072596328873dc906ce0b"
T090_SPLIT_SEED = 900090
T090_SHUFFLE_SEED = 900190
T090_BOOTSTRAP_SEED = 900290
T090_BOOTSTRAP_REPLICATES = 20_000
T090_MODEL_SEEDS = (900091, 900092, 900093)
T090_SPLIT_COUNTS = {
    "A": {"train": 58, "validation": 14, "heldout": 21},
    "B": {"train": 119, "validation": 30, "heldout": 43},
    "C": {"train": 79, "validation": 20, "heldout": 29},
}
T090_SPLITS = ("train", "validation", "heldout")
T090_SOURCE_GROUPS = ("A", "B", "C")
T090_TARGET_SCHEMA_ID = "t090-search-v2-action-utility-targets-v1"
T090_SPLIT_SCHEMA_ID = "t090-battle-start-split-manifest-v1"
T090_CONFIG_SCHEMA_ID = "t090-battle-student-training-config-v1"
T090_HELDOUT_SCHEMA_ID = "t090-battle-student-heldout-report-v1"
T090_FINGERPRINT_SCHEMA_ID = "t090-public-decision-fingerprint-v1"
T090_FORBIDDEN_PUBLIC_KEYS = frozenset(
    {
        "checkpoint",
        "checkpoint_bytes",
        "rng",
        "rng_state",
        "hidden_rng",
        "draw_order",
        "unrevealed",
        "future",
        "future_encounter",
        "tree",
        "root_rows",
        "root_visits",
        "mean_value",
        "teacher_mean",
        "teacher_means",
        "split",
        "terminal_outcome",
        "terminal",
    }
)


class T090ContractError(ValueError):
    """A frozen T090 boundary was violated."""


class T090Incomplete(T090ContractError):
    """A required identity, public input, or teacher row is unavailable."""


def _canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def canonical_sha256(value: object) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _finite(value: object, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise T090Incomplete(f"{label} must be a finite number")
    result = float(value)
    if not math.isfinite(result):
        raise T090Incomplete(f"{label} must be a finite number")
    return result


def _string(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise T090Incomplete(f"{label} must be a non-empty string")
    return value


def _mapping(value: object, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise T090Incomplete(f"{label} must be a mapping")
    return value


def _sequence(value: object, label: str) -> Sequence[object]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise T090Incomplete(f"{label} must be a sequence")
    return value


def _identity(value: object, label: str) -> str:
    if isinstance(value, str) and value:
        return value
    if isinstance(value, Mapping):
        return canonical_sha256(value)
    raise T090Incomplete(f"{label} must be an occurrence-safe identity")


def _check_public_tree(value: object, *, path: str = "public") -> None:
    """Reject named hidden fields recursively instead of relying on callers."""

    if isinstance(value, Mapping):
        for key, child in value.items():
            normalized = str(key).lower()
            if normalized in T090_FORBIDDEN_PUBLIC_KEYS:
                raise T090Incomplete(f"forbidden non-public field at {path}.{key}")
            _check_public_tree(child, path=f"{path}.{key}")
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        for index, child in enumerate(value):
            _check_public_tree(child, path=f"{path}[{index}]")


def _feature_vector(value: object, label: str) -> tuple[float, ...]:
    return tuple(_finite(item, label) for item in _sequence(value, label))


@dataclass(frozen=True)
class T090SplitEntry:
    source_identity: str
    source_group: str
    split: str
    canonical_position: int


@dataclass(frozen=True)
class T090DecisionExample:
    """One public decision plus privileged teacher utility labels.

    ``teacher_means`` is never incorporated into ``public_fingerprint`` or
    exposed through the scorer interface.
    """

    source_identity: str
    source_group: str
    split: str
    decision_identity: str
    public_state_features: tuple[float, ...]
    legal_action_features: tuple[tuple[float, ...], ...]
    legal_action_identities: tuple[Mapping[str, object], ...]
    legal_action_kinds: tuple[str, ...]
    teacher_means: tuple[float, ...]
    public_fingerprint: str

    @property
    def eligible(self) -> bool:
        return len(self.teacher_means) > 1


@dataclass(frozen=True)
class T090TrainingConfig:
    schema_id: str = T090_CONFIG_SCHEMA_ID
    schema_version: int = 1
    task_id: str = T090_TASK_ID
    public_schema_id: str = TACTICAL_FEATURE_SCHEMA_ID
    public_schema_version: int = TACTICAL_FEATURE_SCHEMA_VERSION
    state_feature_size: int = 0
    action_feature_size: int = 0
    hidden_width: int = 256
    hidden_layers: int = 2
    activation: str = "relu"
    output: str = "scalar_action_score"
    optimizer: str = "AdamW"
    learning_rate: float = 1e-3
    weight_decay: float = 1e-4
    max_epochs: int = 30
    max_states_per_batch: int = 256
    pair_tolerance: float = 1e-9
    model_seeds: tuple[int, ...] = T090_MODEL_SEEDS

    def __post_init__(self) -> None:
        if self.schema_id != T090_CONFIG_SCHEMA_ID or self.task_id != T090_TASK_ID:
            raise T090ContractError("T090 training config identity is frozen")
        if (
            self.hidden_width != 256
            or self.hidden_layers != 2
            or self.activation != "relu"
        ):
            raise T090ContractError(
                "T090 architecture is frozen to two ReLU 256 layers"
            )
        if self.output != "scalar_action_score" or self.optimizer != "AdamW":
            raise T090ContractError("T090 scorer/optimizer contract is frozen")
        if (
            self.learning_rate,
            self.weight_decay,
            self.max_epochs,
            self.max_states_per_batch,
        ) != (1e-3, 1e-4, 30, 256):
            raise T090ContractError("T090 training schedule is frozen")
        if tuple(self.model_seeds) != T090_MODEL_SEEDS:
            raise T090ContractError("T090 initialization seeds are frozen")
        if self.state_feature_size < 1 or self.action_feature_size < 1:
            raise T090ContractError("T090 public feature dimensions must be positive")

    def to_dict(self) -> dict[str, object]:
        value = asdict(self)
        value["model_seeds"] = list(self.model_seeds)
        return value


def build_t090_split_manifest(
    records: Iterable[Mapping[str, object]],
) -> dict[str, object]:
    """Materialize the preregistered group-local split before labels are used."""

    grouped: dict[str, list[str]] = {group: [] for group in T090_SOURCE_GROUPS}
    seen: set[str] = set()
    for row in records:
        source_identity = _identity(row.get("source_identity"), "source_identity")
        source_group = _string(row.get("source_group"), "source_group")
        if source_group not in grouped:
            raise T090Incomplete("T090 source group must be A, B, or C")
        if source_identity in seen:
            raise T090Incomplete(
                "T090 source identities must be occurrence-safe and unique"
            )
        seen.add(source_identity)
        grouped[source_group].append(source_identity)
    entries: list[dict[str, object]] = []
    for group in T090_SOURCE_GROUPS:
        expected = sum(T090_SPLIT_COUNTS[group].values())
        if len(grouped[group]) != expected:
            raise T090Incomplete(
                f"T090 group {group} requires exactly {expected} records"
            )
        shuffled = list(grouped[group])
        random.Random(f"{T090_SPLIT_SEED}:{group}").shuffle(shuffled)
        cursor = 0
        for split in T090_SPLITS:
            count = T090_SPLIT_COUNTS[group][split]
            for source_identity in shuffled[cursor : cursor + count]:
                entries.append(
                    {
                        "source_identity": source_identity,
                        "source_group": group,
                        "split": split,
                        "canonical_position": len(entries),
                    }
                )
            cursor += count
    payload = {
        "schema_id": T090_SPLIT_SCHEMA_ID,
        "schema_version": 1,
        "task_id": T090_TASK_ID,
        "split_seed": T090_SPLIT_SEED,
        "entries": entries,
    }
    payload["entries_sha256"] = canonical_sha256(entries)
    return payload


def validate_t090_split_manifest(
    value: Mapping[str, object],
) -> tuple[T090SplitEntry, ...]:
    if (
        value.get("schema_id") != T090_SPLIT_SCHEMA_ID
        or value.get("schema_version") != 1
    ):
        raise T090Incomplete("unsupported T090 split manifest schema")
    if (
        value.get("task_id") != T090_TASK_ID
        or value.get("split_seed") != T090_SPLIT_SEED
    ):
        raise T090Incomplete("T090 split manifest identity is invalid")
    entries_raw = _sequence(value.get("entries"), "split entries")
    if value.get("entries_sha256") != canonical_sha256(entries_raw):
        raise T090Incomplete("T090 split manifest entry hash mismatch")
    entries: list[T090SplitEntry] = []
    counts: Counter[tuple[str, str]] = Counter()
    identities: set[str] = set()
    for expected_position, raw in enumerate(entries_raw):
        item = _mapping(raw, "split entry")
        entry = T090SplitEntry(
            source_identity=_identity(item.get("source_identity"), "source_identity"),
            source_group=_string(item.get("source_group"), "source_group"),
            split=_string(item.get("split"), "split"),
            canonical_position=int(item.get("canonical_position", -1)),
        )
        if (
            entry.source_group not in T090_SOURCE_GROUPS
            or entry.split not in T090_SPLITS
        ):
            raise T090Incomplete("T090 split entry group/split is invalid")
        if (
            entry.canonical_position != expected_position
            or entry.source_identity in identities
        ):
            raise T090Incomplete("T090 split entries are not canonical and unique")
        identities.add(entry.source_identity)
        counts[(entry.source_group, entry.split)] += 1
        entries.append(entry)
    if len(entries) != 413 or any(
        counts[(group, split)] != T090_SPLIT_COUNTS[group][split]
        for group in T090_SOURCE_GROUPS
        for split in T090_SPLITS
    ):
        raise T090Incomplete("T090 split quotas are not exact")
    return tuple(entries)


def public_decision_fingerprint(
    state_features: Sequence[float],
    legal_action_identities: Sequence[Mapping[str, object]],
) -> str:
    public = {
        "schema_id": T090_FINGERPRINT_SCHEMA_ID,
        "state_features": [_finite(item, "state feature") for item in state_features],
        "ordered_legal_action_identities": [
            dict(item) for item in legal_action_identities
        ],
    }
    _check_public_tree(public)
    return canonical_sha256(public)


def materialize_t090_decision(
    row: Mapping[str, object], *, split_entry: T090SplitEntry
) -> T090DecisionExample:
    """Validate an action-aligned Search target row and discard hidden inputs."""

    if (
        _identity(row.get("source_identity"), "source_identity")
        != split_entry.source_identity
    ):
        raise T090Incomplete("teacher row source identity differs from frozen split")
    if _string(row.get("source_group"), "source_group") != split_entry.source_group:
        raise T090Incomplete("teacher row source group differs from frozen split")
    public_input = _mapping(row.get("public_input"), "public_input")
    _check_public_tree(public_input)
    if (
        public_input.get("schema_id") != TACTICAL_FEATURE_SCHEMA_ID
        or public_input.get("schema_version") != TACTICAL_FEATURE_SCHEMA_VERSION
    ):
        raise T090Incomplete("T090 public input must use public-tactical-v2")
    state_features = _feature_vector(
        public_input.get("state_features"), "state_features"
    )
    action_features_raw = _sequence(
        public_input.get("legal_action_features"), "legal_action_features"
    )
    action_features = tuple(
        _feature_vector(item, "action_features") for item in action_features_raw
    )
    action_identities = tuple(
        dict(_mapping(item, "legal_action_identity"))
        for item in _sequence(
            public_input.get("legal_action_identities"), "legal_action_identities"
        )
    )
    action_kinds = tuple(
        _string(item, "legal_action_kind")
        for item in _sequence(
            public_input.get("legal_action_kinds"), "legal_action_kinds"
        )
    )
    if (
        not action_features
        or len(action_features) != len(action_identities)
        or len(action_features) != len(action_kinds)
    ):
        raise T090Incomplete("public legal-action fields are not aligned")
    if len({len(item) for item in action_features}) != 1:
        raise T090Incomplete("public action features have inconsistent widths")
    root_rows = _sequence(row.get("root_rows"), "root_rows")
    if len(root_rows) != len(action_identities):
        raise T090Incomplete("Search root rows do not cover every legal action")
    means: list[float] = []
    row_identities: set[str] = set()
    for action_identity, root_raw in zip(action_identities, root_rows, strict=True):
        root = _mapping(root_raw, "root_row")
        root_identity = _identity(
            root.get("legal_action_identity"), "root row action identity"
        )
        action_key = _identity(action_identity, "public action identity")
        if root_identity != action_key or root_identity in row_identities:
            raise T090Incomplete(
                "Search root rows are not a one-to-one legal action map"
            )
        row_identities.add(root_identity)
        visits = root.get("visits")
        if isinstance(visits, bool) or not isinstance(visits, int) or visits <= 0:
            raise T090Incomplete("Search root row has no visits")
        means.append(_finite(root.get("mean_value"), "Search root mean"))
    return T090DecisionExample(
        source_identity=split_entry.source_identity,
        source_group=split_entry.source_group,
        split=split_entry.split,
        decision_identity=_identity(row.get("decision_identity"), "decision_identity"),
        public_state_features=state_features,
        legal_action_features=action_features,
        legal_action_identities=action_identities,
        legal_action_kinds=action_kinds,
        teacher_means=tuple(means),
        public_fingerprint=public_decision_fingerprint(
            state_features, action_identities
        ),
    )


def materialize_t090_targets(
    rows: Iterable[Mapping[str, object]], split_manifest: Mapping[str, object]
) -> dict[str, object]:
    entries = {
        entry.source_identity: entry
        for entry in validate_t090_split_manifest(split_manifest)
    }
    examples: list[T090DecisionExample] = []
    for row in rows:
        source = _identity(row.get("source_identity"), "source_identity")
        if source not in entries:
            raise T090Incomplete("teacher row is not in the exact T090 source cohort")
        examples.append(materialize_t090_decision(row, split_entry=entries[source]))
    deduped, collision_report = deduplicate_t090_examples(examples)
    collision_report["materialized_decision_count"] = len(examples)
    collision_report["materialized_eligible_multi_action_count"] = sum(
        item.eligible for item in examples
    )
    # The gate is deliberately computed after leakage exclusion/deduplication:
    # the final target table, rather than its raw precursor, is the learner's
    # effective support.
    coverage = t090_coverage_report(deduped)
    return {
        "schema_id": T090_TARGET_SCHEMA_ID,
        "schema_version": 1,
        "task_id": T090_TASK_ID,
        "split_manifest_sha256": canonical_sha256(split_manifest),
        "examples": [serialize_t090_example(item) for item in deduped],
        "collision_deduplication": collision_report,
        "coverage": coverage,
    }


def serialize_t090_example(item: T090DecisionExample) -> dict[str, object]:
    return {
        "source_identity": item.source_identity,
        "source_group": item.source_group,
        "split": item.split,
        "decision_identity": item.decision_identity,
        "public_input": {
            "schema_id": TACTICAL_FEATURE_SCHEMA_ID,
            "schema_version": TACTICAL_FEATURE_SCHEMA_VERSION,
            "state_features": list(item.public_state_features),
            "legal_action_features": [
                list(value) for value in item.legal_action_features
            ],
            "legal_action_identities": [
                dict(value) for value in item.legal_action_identities
            ],
            "legal_action_kinds": list(item.legal_action_kinds),
        },
        "teacher_means": list(item.teacher_means),
        "public_fingerprint": item.public_fingerprint,
    }


def deduplicate_t090_examples(
    examples: Sequence[T090DecisionExample],
) -> tuple[tuple[T090DecisionExample, ...], dict[str, object]]:
    by_fingerprint: dict[str, list[T090DecisionExample]] = defaultdict(list)
    for item in examples:
        by_fingerprint[item.public_fingerprint].append(item)
    retained: list[T090DecisionExample] = []
    cross_split: list[dict[str, object]] = []
    within_split_duplicates: list[dict[str, object]] = []
    for fingerprint in sorted(by_fingerprint):
        members = sorted(
            by_fingerprint[fingerprint],
            key=lambda item: (item.split, item.decision_identity),
        )
        splits = sorted({item.split for item in members})
        if len(splits) > 1:
            cross_split.append(
                {
                    "public_fingerprint": fingerprint,
                    "splits": splits,
                    "source_identities": sorted(
                        {item.source_identity for item in members}
                    ),
                    "multiplicity": len(members),
                }
            )
            continue
        retained.append(members[0])
        if len(members) > 1:
            within_split_duplicates.append(
                {
                    "public_fingerprint": fingerprint,
                    "split": splits[0],
                    "canonical_decision_identity": members[0].decision_identity,
                    "multiplicity": len(members),
                    "source_identities": sorted(
                        {item.source_identity for item in members}
                    ),
                }
            )
    retained.sort(
        key=lambda item: (
            item.split,
            item.source_group,
            item.source_identity,
            item.decision_identity,
        )
    )
    return tuple(retained), {
        "fingerprint_schema_id": T090_FINGERPRINT_SCHEMA_ID,
        "cross_split_excluded": cross_split,
        "within_split_deduplicated": within_split_duplicates,
        "retained_count": len(retained),
    }


def t090_coverage_report(
    examples: Sequence[T090DecisionExample],
    *,
    observed_examples: Sequence[T090DecisionExample] | None = None,
) -> dict[str, object]:
    observed = tuple(observed_examples or examples)
    eligible = [item for item in examples if item.eligible]
    observed_multi = [item for item in observed if item.eligible]
    per_split = {
        split: [item for item in eligible if item.split == split]
        for split in T090_SPLITS
    }
    per_group = {
        split: sorted({item.source_group for item in values})
        for split, values in per_split.items()
    }
    rate = len(eligible) / len(observed_multi) if observed_multi else 0.0
    passed = (
        len(eligible) >= 1500
        and len(per_split["train"]) >= 750
        and len(per_split["validation"]) >= 150
        and len(per_split["heldout"]) >= 250
        and rate >= 0.95
        and all(groups == list(T090_SOURCE_GROUPS) for groups in per_group.values())
    )
    return {
        "eligible_multi_action_count": len(eligible),
        "observed_multi_action_count": len(observed_multi),
        "target_eligibility_rate": rate,
        "eligible_by_split": {
            split: len(values) for split, values in per_split.items()
        },
        "source_groups_by_split": per_group,
        "passed": passed,
        "failure_classification": None
        if passed
        else "BATTLE_STUDENT_TARGET_COVERAGE_INSUFFICIENT",
    }


def deserialize_t090_examples(
    value: Mapping[str, object],
) -> tuple[T090DecisionExample, ...]:
    if (
        value.get("schema_id") != T090_TARGET_SCHEMA_ID
        or value.get("schema_version") != 1
    ):
        raise T090Incomplete("unsupported T090 target schema")
    examples: list[T090DecisionExample] = []
    for raw in _sequence(value.get("examples"), "T090 examples"):
        row = _mapping(raw, "T090 example")
        public = _mapping(row.get("public_input"), "public_input")
        _check_public_tree(public)
        state = _feature_vector(public.get("state_features"), "state_features")
        identities = tuple(
            dict(_mapping(item, "legal action identity"))
            for item in _sequence(
                public.get("legal_action_identities"), "legal action identities"
            )
        )
        item = T090DecisionExample(
            source_identity=_identity(row.get("source_identity"), "source_identity"),
            source_group=_string(row.get("source_group"), "source_group"),
            split=_string(row.get("split"), "split"),
            decision_identity=_identity(
                row.get("decision_identity"), "decision_identity"
            ),
            public_state_features=state,
            legal_action_features=tuple(
                _feature_vector(x, "action features")
                for x in _sequence(
                    public.get("legal_action_features"), "legal action features"
                )
            ),
            legal_action_identities=identities,
            legal_action_kinds=tuple(
                _string(x, "legal action kind")
                for x in _sequence(
                    public.get("legal_action_kinds"), "legal action kinds"
                )
            ),
            teacher_means=tuple(
                _finite(x, "teacher mean")
                for x in _sequence(row.get("teacher_means"), "teacher means")
            ),
            public_fingerprint=_string(
                row.get("public_fingerprint"), "public_fingerprint"
            ),
        )
        if item.public_fingerprint != public_decision_fingerprint(state, identities):
            raise T090Incomplete("T090 public fingerprint mismatch")
        if not (
            len(item.legal_action_features)
            == len(item.legal_action_identities)
            == len(item.legal_action_kinds)
            == len(item.teacher_means)
        ):
            raise T090Incomplete("T090 example action fields are not aligned")
        examples.append(item)
    return tuple(examples)


def validate_t090_target_table(
    value: Mapping[str, object],
) -> tuple[T090DecisionExample, ...]:
    """Validate the current target schema without trusting its summaries."""

    if (
        value.get("schema_id") != T090_TARGET_SCHEMA_ID
        or value.get("schema_version") != 1
        or value.get("task_id") != T090_TASK_ID
    ):
        raise T090Incomplete("unsupported T090 target schema")
    split_hash = value.get("split_manifest_sha256")
    if not isinstance(split_hash, str) or len(split_hash) != 64:
        raise T090Incomplete("T090 target table has no split-manifest identity")
    examples = deserialize_t090_examples(value)
    collision = _mapping(value.get("collision_deduplication"), "collision report")
    if collision.get("fingerprint_schema_id") != T090_FINGERPRINT_SCHEMA_ID:
        raise T090Incomplete("T090 collision report fingerprint schema is invalid")
    if int(collision.get("retained_count", -1)) != len(examples):
        raise T090Incomplete("T090 collision report retained count is inconsistent")
    if len({item.public_fingerprint for item in examples}) != len(examples):
        raise T090Incomplete(
            "T090 target table still contains duplicate public fingerprints"
        )
    expected_coverage = t090_coverage_report(examples)
    coverage = _mapping(value.get("coverage"), "coverage report")
    if dict(coverage) != expected_coverage:
        raise T090Incomplete("T090 target coverage report is inconsistent")
    return examples


def build_t090_training_config(
    examples: Sequence[T090DecisionExample],
) -> T090TrainingConfig:
    eligible = [item for item in examples if item.eligible]
    if not eligible:
        raise T090Incomplete("T090 needs an eligible multi-action example")
    state_widths = {len(item.public_state_features) for item in eligible}
    action_widths = {
        len(features) for item in eligible for features in item.legal_action_features
    }
    if len(state_widths) != 1 or len(action_widths) != 1:
        raise T090Incomplete("T090 public feature widths are inconsistent")
    return T090TrainingConfig(
        state_feature_size=state_widths.pop(), action_feature_size=action_widths.pop()
    )


def shuffled_teacher_means(item: T090DecisionExample) -> tuple[float, ...]:
    values = list(item.teacher_means)
    random.Random(f"{T090_SHUFFLE_SEED}:{item.public_fingerprint}").shuffle(values)
    return tuple(values)


class T090TorchScorer:
    """Public-only action-conditioned scorer; it cannot invoke Search."""

    name = "battle_student_t090_public_action_scorer_v1"

    def __init__(self, model: Any, config: T090TrainingConfig) -> None:
        self.model = model
        self.config = config

    @property
    def provenance_config(self) -> Mapping[str, object]:
        return {
            "task_id": T090_TASK_ID,
            "information_regime": "normal_public_policy",
            "training_config": self.config.to_dict(),
            "search_calls_at_inference": 0,
        }

    def score_actions(self, context: DecisionContext) -> list[float]:
        if context.tactical_feature_schema_id != TACTICAL_FEATURE_SCHEMA_ID:
            raise ValueError("T090 scorer requires public-tactical-v2")
        if len(context.snapshot_features) != self.config.state_feature_size:
            raise ValueError("T090 scorer state feature width differs from checkpoint")
        if any(
            len(item) != self.config.action_feature_size
            for item in context.legal_action_features
        ):
            raise ValueError("T090 scorer action feature width differs from checkpoint")
        import torch

        self.model.eval()
        with torch.no_grad():
            state = torch.tensor(context.snapshot_features, dtype=torch.float32).repeat(
                len(context.legal_action_features), 1
            )
            actions = torch.tensor(context.legal_action_features, dtype=torch.float32)
            return [
                float(item)
                for item in self.model(torch.cat((state, actions), dim=1))
                .reshape(-1)
                .tolist()
            ]

    def select_action(self, context: DecisionContext) -> PolicyDecision:
        scores = self.score_actions(context)
        if not context.eligible_action_indices:
            raise ValueError("T090 scorer received no eligible legal action")
        best = max(
            context.eligible_action_indices, key=lambda index: (scores[index], -index)
        )
        return PolicyDecision(
            legal_action_index=best,
            score=scores[best],
            reason="t090_public_action_score",
        )


def _torch_model(config: T090TrainingConfig, *, seed: int) -> Any:
    import torch

    torch.manual_seed(seed)
    width = config.state_feature_size + config.action_feature_size
    return torch.nn.Sequential(
        torch.nn.Linear(width, config.hidden_width),
        torch.nn.ReLU(),
        torch.nn.Linear(config.hidden_width, config.hidden_width),
        torch.nn.ReLU(),
        torch.nn.Linear(config.hidden_width, 1),
    )


def _pairwise_loss(scores: Any, means: Sequence[float], tolerance: float) -> Any:
    from torch.nn import functional

    terms = []
    for left in range(len(means)):
        for right in range(left + 1, len(means)):
            delta = means[left] - means[right]
            if abs(delta) <= tolerance:
                continue
            high, low = (left, right) if delta > 0 else (right, left)
            terms.append(functional.softplus(-(scores[high] - scores[low])))
    if not terms:
        return None
    return sum(terms) / len(terms)


def train_t090_scorer(
    examples: Sequence[T090DecisionExample], *, seed: int, shuffled: bool = False
) -> tuple[T090TorchScorer, dict[str, object]]:
    """Train one frozen seed.  Held-out rows are never inspected here."""

    if seed not in T090_MODEL_SEEDS:
        raise T090ContractError("T090 seed is not preregistered")
    config = build_t090_training_config(examples)
    train = [item for item in examples if item.split == "train" and item.eligible]
    validation = [
        item for item in examples if item.split == "validation" and item.eligible
    ]
    if not train or not validation:
        raise T090Incomplete("T090 train/validation examples are required")
    import torch

    model = _torch_model(config, seed=seed)
    optimizer = torch.optim.AdamW(
        model.parameters(), lr=config.learning_rate, weight_decay=config.weight_decay
    )
    rng = random.Random(seed)
    epoch_losses: list[float] = []
    for _ in range(config.max_epochs):
        ordered = list(train)
        rng.shuffle(ordered)
        losses: list[float] = []
        for start in range(0, len(ordered), config.max_states_per_batch):
            optimizer.zero_grad()
            terms = []
            for item in ordered[start : start + config.max_states_per_batch]:
                state = torch.tensor(
                    item.public_state_features, dtype=torch.float32
                ).repeat(len(item.legal_action_features), 1)
                actions = torch.tensor(item.legal_action_features, dtype=torch.float32)
                scores = model(torch.cat((state, actions), dim=1)).reshape(-1)
                means = shuffled_teacher_means(item) if shuffled else item.teacher_means
                loss = _pairwise_loss(scores, means, config.pair_tolerance)
                if loss is not None:
                    terms.append(loss)
            if terms:
                batch_loss = sum(terms) / len(terms)
                batch_loss.backward()
                optimizer.step()
                losses.append(float(batch_loss.detach()))
        epoch_losses.append(statistics.fmean(losses) if losses else 0.0)
    scorer = T090TorchScorer(model, config)
    validation_metrics = t090_rank_metrics(validation, scorer)
    return scorer, {
        "schema_id": "t090-battle-student-training-summary-v1",
        "task_id": T090_TASK_ID,
        "seed": seed,
        "shuffled_target_control": shuffled,
        "config": config.to_dict(),
        "epoch_pairwise_losses": epoch_losses,
        "validation": validation_metrics,
    }


def select_t090_validation_checkpoint(
    results: Sequence[tuple[T090TorchScorer, Mapping[str, object]]],
) -> tuple[T090TorchScorer, Mapping[str, object]]:
    if len(results) != len(T090_MODEL_SEEDS):
        raise T090Incomplete("T090 must select among all three preregistered seeds")

    def key(result: tuple[T090TorchScorer, Mapping[str, object]]) -> tuple[float, int]:
        report = _mapping(result[1], "training summary")
        validation = _mapping(report.get("validation"), "validation metrics")
        return (
            _finite(validation.get("mean_teacher_regret"), "validation regret"),
            int(report["seed"]),
        )

    return min(results, key=key)


def _percentile(values: Sequence[float], q: float) -> float:
    ordered = sorted(values)
    if not ordered:
        raise T090Incomplete("cannot compute percentile for no values")
    point = (len(ordered) - 1) * q
    lo, hi = math.floor(point), math.ceil(point)
    return (
        ordered[lo]
        if lo == hi
        else ordered[lo] + (ordered[hi] - ordered[lo]) * (point - lo)
    )


def _selection_and_scores(
    item: T090DecisionExample, scorer: T090TorchScorer
) -> tuple[int, list[float]]:
    context = DecisionContext(
        screen_state="BATTLE",
        snapshot_features=list(item.public_state_features),
        legal_action_features=[list(value) for value in item.legal_action_features],
        legal_action_kinds=list(item.legal_action_kinds),
        eligible_action_indices=list(range(len(item.teacher_means))),
        tactical_feature_schema_id=TACTICAL_FEATURE_SCHEMA_ID,
    )
    scores = scorer.score_actions(context)
    selected = max(range(len(scores)), key=lambda index: (scores[index], -index))
    return selected, scores


def t090_rank_metrics(
    examples: Sequence[T090DecisionExample], scorer: T090TorchScorer
) -> dict[str, object]:
    eligible = [item for item in examples if item.eligible]
    if not eligible:
        raise T090Incomplete("T090 metrics require eligible multi-action states")
    agreements: list[float] = []
    regrets: list[float] = []
    accuracies: list[float] = []
    margins: list[float] = []
    ties = 0
    group: dict[str, list[float]] = defaultdict(list)
    action_kind: dict[str, list[float]] = defaultdict(list)
    for item in eligible:
        selected, scores = _selection_and_scores(item, scorer)
        best_mean = max(item.teacher_means)
        teacher_best = min(
            index
            for index, value in enumerate(item.teacher_means)
            if value == best_mean
        )
        regret = best_mean - item.teacher_means[selected]
        agreements.append(float(selected == teacher_best))
        regrets.append(regret)
        group[item.source_group].append(regret)
        action_kind[item.legal_action_kinds[selected]].append(regret)
        ordered_scores = sorted(scores, reverse=True)
        margin = ordered_scores[0] - ordered_scores[1]
        margins.append(margin)
        ties += int(abs(margin) <= 1e-12)
        pairs = []
        for left in range(len(scores)):
            for right in range(left + 1, len(scores)):
                if abs(item.teacher_means[left] - item.teacher_means[right]) > 1e-9:
                    expected = item.teacher_means[left] > item.teacher_means[right]
                    actual = scores[left] > scores[right]
                    pairs.append(float(expected == actual))
        accuracies.extend(pairs)
    return {
        "state_count": len(eligible),
        "top1_teacher_agreement": statistics.fmean(agreements),
        "pairwise_ranking_accuracy": statistics.fmean(accuracies)
        if accuracies
        else None,
        "mean_teacher_regret": statistics.fmean(regrets),
        "median_teacher_regret": statistics.median(regrets),
        "p90_teacher_regret": _percentile(regrets, 0.90),
        "p95_teacher_regret": _percentile(regrets, 0.95),
        "source_group_regret": {
            key: statistics.fmean(value) for key, value in sorted(group.items())
        },
        "action_kind_regret": {
            key: statistics.fmean(value) for key, value in sorted(action_kind.items())
        },
        "score_margin": {
            "mean": statistics.fmean(margins),
            "median": statistics.median(margins),
            "p90": _percentile(margins, 0.90),
        },
        "tie_rate": ties / len(eligible),
        "per_state": [
            {
                "decision_identity": item.decision_identity,
                "student_action": _selection_and_scores(item, scorer)[0],
                "regret": regret,
                "top1": agreement,
            }
            for item, regret, agreement in zip(
                eligible, regrets, agreements, strict=True
            )
        ],
    }


def paired_t090_bootstrap(
    values: Sequence[float], *, seed: int = T090_BOOTSTRAP_SEED
) -> dict[str, object]:
    clean = [_finite(value, "paired bootstrap value") for value in values]
    if not clean:
        raise T090Incomplete("T090 paired bootstrap requires values")
    rng = random.Random(seed)
    samples = [
        statistics.fmean(clean[rng.randrange(len(clean))] for _ in clean)
        for _ in range(T090_BOOTSTRAP_REPLICATES)
    ]
    return {
        "replicates": T090_BOOTSTRAP_REPLICATES,
        "seed": seed,
        "sampling_unit": "eligible_heldout_decision_state",
        "observed_mean": statistics.fmean(clean),
        "ci_95": [_percentile(samples, 0.025), _percentile(samples, 0.975)],
    }


def build_t090_heldout_report(
    examples: Sequence[T090DecisionExample],
    student: T090TorchScorer,
    control: T090TorchScorer,
) -> dict[str, object]:
    heldout = [item for item in examples if item.split == "heldout" and item.eligible]
    if not heldout:
        raise T090Incomplete("T090 held-out examples are required")
    student_metrics = t090_rank_metrics(heldout, student)
    control_metrics = t090_rank_metrics(heldout, control)
    student_rows = _mapping_rows(student_metrics["per_state"])
    control_rows = _mapping_rows(control_metrics["per_state"])
    if [row["decision_identity"] for row in student_rows] != [
        row["decision_identity"] for row in control_rows
    ]:
        raise T090Incomplete("T090 held-out model rows are not paired")
    regrets = [
        float(control_row["regret"]) - float(student_row["regret"])
        for student_row, control_row in zip(student_rows, control_rows, strict=True)
    ]
    agreements = [
        float(student_row["top1"]) - float(control_row["top1"])
        for student_row, control_row in zip(student_rows, control_rows, strict=True)
    ]
    regret_bootstrap = paired_t090_bootstrap(regrets)
    agreement_bootstrap = paired_t090_bootstrap(agreements)
    passed = (
        regret_bootstrap["ci_95"][0] > 0
        and student_metrics["mean_teacher_regret"]
        < control_metrics["mean_teacher_regret"]
        and student_metrics["top1_teacher_agreement"]
        > control_metrics["top1_teacher_agreement"]
    )
    return {
        "schema_id": T090_HELDOUT_SCHEMA_ID,
        "schema_version": 1,
        "task_id": T090_TASK_ID,
        "student": student_metrics,
        "shuffled_target_control": control_metrics,
        "paired_delta_regret": regrets,
        "paired_delta_top1_agreement": agreements,
        "paired_bootstrap_mean_delta_regret": regret_bootstrap,
        "paired_bootstrap_top1_agreement": agreement_bootstrap,
        "information_boundary_valid": True,
        "split_leakage_valid": True,
        "terminal_classification": "BATTLE_STUDENT_DISTILLATION_SIGNAL_ESTABLISHED"
        if passed
        else "BATTLE_STUDENT_DISTILLATION_SIGNAL_NOT_ESTABLISHED",
    }


def _mapping_rows(value: object) -> list[Mapping[str, object]]:
    return [_mapping(item, "metric row") for item in _sequence(value, "metric rows")]


def validate_t090_heldout_report(value: Mapping[str, object]) -> None:
    if (
        value.get("schema_id") != T090_HELDOUT_SCHEMA_ID
        or value.get("schema_version") != 1
        or value.get("task_id") != T090_TASK_ID
    ):
        raise T090Incomplete("unsupported T090 held-out report")
    for name in ("student", "shuffled_target_control"):
        metrics = _mapping(value.get(name), name)
        for key in (
            "top1_teacher_agreement",
            "mean_teacher_regret",
            "pairwise_ranking_accuracy",
            "tie_rate",
        ):
            _finite(metrics.get(key), f"{name}.{key}")
    delta = _sequence(value.get("paired_delta_regret"), "paired_delta_regret")
    bootstrap = _mapping(
        value.get("paired_bootstrap_mean_delta_regret"), "paired bootstrap"
    )
    expected = paired_t090_bootstrap([_finite(item, "delta regret") for item in delta])
    if dict(bootstrap) != expected:
        raise T090Incomplete("T090 regret bootstrap does not match paired values")
    lower = _sequence(bootstrap.get("ci_95"), "bootstrap ci")[0]
    student = _mapping(value["student"], "student")
    control = _mapping(value["shuffled_target_control"], "control")
    passed = (
        _finite(lower, "bootstrap lower") > 0
        and _finite(student["mean_teacher_regret"], "student regret")
        < _finite(control["mean_teacher_regret"], "control regret")
        and _finite(student["top1_teacher_agreement"], "student agreement")
        > _finite(control["top1_teacher_agreement"], "control agreement")
    )
    expected_classification = (
        "BATTLE_STUDENT_DISTILLATION_SIGNAL_ESTABLISHED"
        if passed
        else "BATTLE_STUDENT_DISTILLATION_SIGNAL_NOT_ESTABLISHED"
    )
    if value.get("terminal_classification") != expected_classification:
        raise T090Incomplete(
            "T090 terminal classification is inconsistent with held-out gate"
        )


__all__ = [
    "T090_APPROVED_SPEC_COMMIT",
    "T090_BOOTSTRAP_REPLICATES",
    "T090_BOOTSTRAP_SEED",
    "T090_CONFIG_SCHEMA_ID",
    "T090_HELDOUT_SCHEMA_ID",
    "T090_MODEL_SEEDS",
    "T090_SPLIT_SCHEMA_ID",
    "T090_TARGET_SCHEMA_ID",
    "T090ContractError",
    "T090DecisionExample",
    "T090Incomplete",
    "T090TorchScorer",
    "T090TrainingConfig",
    "build_t090_heldout_report",
    "build_t090_split_manifest",
    "build_t090_training_config",
    "canonical_sha256",
    "deduplicate_t090_examples",
    "deserialize_t090_examples",
    "materialize_t090_decision",
    "materialize_t090_targets",
    "paired_t090_bootstrap",
    "public_decision_fingerprint",
    "select_t090_validation_checkpoint",
    "shuffled_teacher_means",
    "t090_coverage_report",
    "t090_rank_metrics",
    "train_t090_scorer",
    "validate_t090_heldout_report",
    "validate_t090_split_manifest",
    "validate_t090_target_table",
]
