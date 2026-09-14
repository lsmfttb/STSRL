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
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any

from sts_combat_rl.sim.action_space import ActionSpaceConfig
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
T090_CHECKPOINT_SCHEMA_ID = "t090-public-action-scorer-checkpoint-v1"
T090_SOURCE_EXECUTION_SCHEMA_ID = "t090-source-execution-ledger-v1"
T090_SOURCE_MANIFEST_SCHEMA_ID = "sts-lightspeed-source-manifest-v1"
T090_NATIVE_IDENTITY = {
    "repository": "lsmfttb/sts_lightspeed",
    "ref": "refs/heads/stsrl/main",
    "commit": "20a6c2b3a9cea817c988178b814f083ff889853f",
}
T090_TEACHER_CONFIG = {
    "implementation": "BattleScumSearcher2",
    "search_api": "StepSimulator.battle_search_v2",
    "information_regime": "full_simulator_state_oracle_like",
    "simulations": 400,
    "root_selection": "highest_mean",
    "policy_prior": None,
    "learned_leaf_value": None,
    "rollout": "playoutRandom",
    "terminal_utility": "evaluateEndState",
    "action_space": ActionSpaceConfig.initial_no_potions().to_dict(),
}
T090_PUBLIC_INPUT_CONTRACT = {
    "schema_id": TACTICAL_FEATURE_SCHEMA_ID,
    "schema_version": TACTICAL_FEATURE_SCHEMA_VERSION,
    "legal_action_identity_contract": "ordered-public-legal-action-identity-v1",
    "action_features": "public-tactical-v2-derived",
}
T090_PUBLIC_INPUT_FIELDS = frozenset(
    {
        "schema_id",
        "schema_version",
        "state_features",
        "legal_action_features",
        "legal_action_identities",
        "legal_action_kinds",
    }
)
T090_FORBIDDEN_PUBLIC_KEYS = frozenset(
    {
        "checkpoint",
        "checkpointbytes",
        "rng",
        "rngstate",
        "hiddenrng",
        "draworder",
        "unrevealed",
        "future",
        "futureencounter",
        "tree",
        "rootrows",
        "rootvisits",
        "meanvalue",
        "teachermean",
        "teachermeans",
        "split",
        "terminaloutcome",
        "terminal",
        "hiddenstate",
        "simulatorstate",
        "fullsimulatorstate",
        "hiddensimulatorstate",
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
            normalized = "".join(
                character for character in str(key).lower() if character.isalnum()
            )
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
class T090ObservedDecision:
    """Raw observed decision retained even when its Search target is ineligible."""

    source_identity: str
    source_group: str
    split: str
    decision_identity: str
    public_fingerprint: str
    legal_action_count: int
    multi_action: bool
    target_eligible: bool
    ineligible_reasons: tuple[str, ...]


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
    normalization: str = "identity_public_features_v1"
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
        if (
            self.output != "scalar_action_score"
            or self.optimizer != "AdamW"
            or self.normalization != "identity_public_features_v1"
        ):
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


def _source_identity_digests(
    records: Sequence[Mapping[str, object]],
) -> tuple[str, str]:
    identities = [
        _identity(row.get("source_identity"), "source_identity") for row in records
    ]
    return canonical_sha256(identities), canonical_sha256(sorted(identities))


def validate_t090_t087_source_cohort_identity(
    value: Mapping[str, object], *, records: Sequence[Mapping[str, object]]
) -> None:
    """Bind a T090 split to one retained, exact T087 source artifact."""

    expected_ordered, expected_set = _source_identity_digests(records)
    if (
        value.get("task_id") != "T087"
        or value.get("record_count") != 413
        or value.get("source_group_counts") != {"A": 93, "B": 192, "C": 128}
        or value.get("ordered_source_identities_sha256") != expected_ordered
        or value.get("source_identity_set_sha256") != expected_set
    ):
        raise T090Incomplete(
            "T090 source cohort is not the exact T087 413-record identity"
        )
    artifact = _mapping(value.get("artifact"), "T087 source cohort artifact")
    if (
        not isinstance(artifact.get("path"), str)
        or not artifact["path"]
        or not isinstance(artifact.get("sha256"), str)
        or len(artifact["sha256"]) != 64
        or not isinstance(artifact.get("schema_id"), str)
        or not artifact["schema_id"]
        or isinstance(artifact.get("size_bytes"), bool)
        or not isinstance(artifact.get("size_bytes"), int)
        or artifact["size_bytes"] < 0
    ):
        raise T090Incomplete("T087 source cohort artifact identity is incomplete")


def build_t090_split_manifest(
    records: Iterable[Mapping[str, object]],
    *,
    t087_source_cohort_identity: Mapping[str, object],
) -> dict[str, object]:
    """Materialize the preregistered group-local split before labels are used."""

    record_list = list(records)
    validate_t090_t087_source_cohort_identity(
        t087_source_cohort_identity, records=record_list
    )
    grouped: dict[str, list[str]] = {group: [] for group in T090_SOURCE_GROUPS}
    seen: set[str] = set()
    for row in record_list:
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
        "t087_source_cohort_identity": dict(t087_source_cohort_identity),
        "t087_ordered_source_identities_sha256": _source_identity_digests(record_list)[
            0
        ],
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
    identity = _mapping(
        value.get("t087_source_cohort_identity"), "T087 source cohort identity"
    )
    expected_set = canonical_sha256(sorted(entry.source_identity for entry in entries))
    if (
        identity.get("task_id") != "T087"
        or identity.get("record_count") != 413
        or identity.get("source_group_counts") != {"A": 93, "B": 192, "C": 128}
        or identity.get("source_identity_set_sha256") != expected_set
        or value.get("t087_ordered_source_identities_sha256")
        != identity.get("ordered_source_identities_sha256")
        or not isinstance(identity.get("ordered_source_identities_sha256"), str)
    ):
        raise T090Incomplete("T090 split manifest T087 cohort binding is invalid")
    artifact = _mapping(identity.get("artifact"), "T087 source cohort artifact")
    if not isinstance(artifact.get("sha256"), str) or len(artifact["sha256"]) != 64:
        raise T090Incomplete("T090 split manifest lacks T087 artifact identity")
    return tuple(entries)


def validate_t090_source_execution_ledger(
    value: Mapping[str, object],
    *,
    split_manifest: Mapping[str, object],
) -> None:
    """Require one valid terminal execution for every frozen source start."""

    if (
        value.get("schema_id") != T090_SOURCE_EXECUTION_SCHEMA_ID
        or value.get("schema_version") != 1
        or value.get("task_id") != T090_TASK_ID
    ):
        raise T090Incomplete("unsupported T090 source execution ledger schema")
    rows = _sequence(value.get("entries"), "source execution entries")
    if value.get("entries_sha256") != canonical_sha256(rows):
        raise T090Incomplete("T090 source execution ledger entry hash mismatch")
    entries = validate_t090_split_manifest(split_manifest)
    if len(rows) != len(entries):
        raise T090Incomplete(
            "T090 source execution ledger must cover exactly 413 starts"
        )
    for expected, raw in zip(entries, rows, strict=True):
        row = _mapping(raw, "source execution row")
        if (
            _identity(row.get("source_identity"), "source_identity")
            != expected.source_identity
            or row.get("source_group") != expected.source_group
            or row.get("split") != expected.split
            or row.get("canonical_position") != expected.canonical_position
            or row.get("restore_public_legal_parity") is not True
            or row.get("completed") is not True
            or row.get("terminal_reached") is not True
            or row.get("status") != "COMPLETED_VALID"
        ):
            raise T090Incomplete(
                "T090 source execution ledger differs from frozen split or is incomplete"
            )


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


def _validate_public_input_fields(public_input: Mapping[str, object]) -> None:
    unknown = set(public_input) - T090_PUBLIC_INPUT_FIELDS
    if unknown:
        raise T090Incomplete(
            "T090 public input has unknown fields: " + ", ".join(sorted(unknown))
        )
    _check_public_tree(public_input)


def build_t090_target_provenance(
    split_manifest: Mapping[str, object],
    *,
    native_source_manifest: Mapping[str, object],
) -> dict[str, object]:
    """Freeze the non-row identities required to consume a target table."""

    validate_t090_split_manifest(split_manifest)
    if native_source_manifest.get("schema_id") != T090_SOURCE_MANIFEST_SCHEMA_ID:
        raise T090Incomplete("T090 native source manifest schema is unsupported")
    integration = _mapping(
        native_source_manifest.get("integration"), "native integration"
    )
    if (
        integration.get("repository_url")
        not in {
            "https://github.com/lsmfttb/sts_lightspeed",
            "https://github.com/lsmfttb/sts_lightspeed.git",
        }
        or integration.get("ref") != T090_NATIVE_IDENTITY["ref"]
        or integration.get("commit") != T090_NATIVE_IDENTITY["commit"]
    ):
        raise T090Incomplete("T090 native source manifest does not bind current native")
    value = {
        "task_id": T090_TASK_ID,
        "approved_spec_commit": T090_APPROVED_SPEC_COMMIT,
        "publication_base": T090_PUBLICATION_BASE,
        "split_manifest_sha256": canonical_sha256(split_manifest),
        "split_entries_sha256": split_manifest["entries_sha256"],
        "t087_source_cohort_identity": dict(
            split_manifest["t087_source_cohort_identity"]
        ),
        "native_source_manifest": {
            "schema_id": T090_SOURCE_MANIFEST_SCHEMA_ID,
            "sha256": canonical_sha256(native_source_manifest),
            "native_identity": dict(T090_NATIVE_IDENTITY),
        },
        "teacher_config": dict(T090_TEACHER_CONFIG),
        "public_input_contract": dict(T090_PUBLIC_INPUT_CONTRACT),
    }
    value["provenance_sha256"] = canonical_sha256(value)
    return value


def validate_t090_target_provenance(
    value: Mapping[str, object],
    *,
    split_manifest: Mapping[str, object],
    native_source_manifest: Mapping[str, object],
) -> None:
    expected = build_t090_target_provenance(
        split_manifest, native_source_manifest=native_source_manifest
    )
    if dict(value) != expected:
        raise T090Incomplete("T090 target provenance is not the expected exact binding")


def materialize_t090_decision(
    row: Mapping[str, object], *, split_entry: T090SplitEntry
) -> tuple[T090DecisionExample | None, T090ObservedDecision]:
    """Validate an action-aligned Search target row and discard hidden inputs."""

    if (
        _identity(row.get("source_identity"), "source_identity")
        != split_entry.source_identity
    ):
        raise T090Incomplete("teacher row source identity differs from frozen split")
    if _string(row.get("source_group"), "source_group") != split_entry.source_group:
        raise T090Incomplete("teacher row source group differs from frozen split")
    public_input = _mapping(row.get("public_input"), "public_input")
    _validate_public_input_fields(public_input)
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
    ineligible_reasons: list[str] = []
    row_identities: set[str] = set()
    for action_index, (action_identity, root_raw) in enumerate(
        zip(action_identities, root_rows, strict=True)
    ):
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
            ineligible_reasons.append(f"action_{action_index}_unvisited")
        try:
            mean = _finite(root.get("mean_value"), "Search root mean")
        except T090Incomplete:
            ineligible_reasons.append(f"action_{action_index}_nonfinite_mean")
        else:
            means.append(mean)
    decision_identity = _identity(row.get("decision_identity"), "decision_identity")
    fingerprint = public_decision_fingerprint(state_features, action_identities)
    multi_action = len(action_identities) > 1
    target_eligible = multi_action and not ineligible_reasons
    observed = T090ObservedDecision(
        source_identity=split_entry.source_identity,
        source_group=split_entry.source_group,
        split=split_entry.split,
        decision_identity=decision_identity,
        public_fingerprint=fingerprint,
        legal_action_count=len(action_identities),
        multi_action=multi_action,
        target_eligible=target_eligible,
        ineligible_reasons=tuple(
            ineligible_reasons or (() if multi_action else ("single_action",))
        ),
    )
    if not target_eligible:
        return None, observed
    return T090DecisionExample(
        source_identity=split_entry.source_identity,
        source_group=split_entry.source_group,
        split=split_entry.split,
        decision_identity=decision_identity,
        public_state_features=state_features,
        legal_action_features=action_features,
        legal_action_identities=action_identities,
        legal_action_kinds=action_kinds,
        teacher_means=tuple(means),
        public_fingerprint=fingerprint,
    ), observed


def materialize_t090_targets(
    rows: Iterable[Mapping[str, object]],
    split_manifest: Mapping[str, object],
    *,
    native_source_manifest: Mapping[str, object],
    source_execution_ledger: Mapping[str, object],
) -> dict[str, object]:
    target_provenance = build_t090_target_provenance(
        split_manifest, native_source_manifest=native_source_manifest
    )
    entries = {
        entry.source_identity: entry
        for entry in validate_t090_split_manifest(split_manifest)
    }
    validate_t090_source_execution_ledger(
        source_execution_ledger, split_manifest=split_manifest
    )
    examples: list[T090DecisionExample] = []
    observed: list[T090ObservedDecision] = []
    observed_keys: set[tuple[str, str]] = set()
    for row in rows:
        source = _identity(row.get("source_identity"), "source_identity")
        if source not in entries:
            raise T090Incomplete("teacher row is not in the exact T090 source cohort")
        example, observed_row = materialize_t090_decision(
            row, split_entry=entries[source]
        )
        decision_key = (observed_row.source_identity, observed_row.decision_identity)
        if decision_key in observed_keys:
            raise T090Incomplete("T090 observed decision identity is duplicated")
        observed_keys.add(decision_key)
        observed.append(observed_row)
        if example is not None:
            examples.append(example)
    deduped, collision_report = deduplicate_t090_examples(examples)
    collision_report["materialized_decision_count"] = len(observed)
    collision_report["materialized_eligible_multi_action_count"] = sum(
        item.target_eligible and item.multi_action for item in observed
    )
    # State-count quotas use final leakage-excluded/deduplicated support.  The
    # eligibility denominator deliberately remains every raw observed
    # multi-action decision, before that deduplication.
    coverage = t090_coverage_report(deduped, observed_decisions=observed)
    return {
        "schema_id": T090_TARGET_SCHEMA_ID,
        "schema_version": 1,
        "task_id": T090_TASK_ID,
        "split_manifest_sha256": canonical_sha256(split_manifest),
        "target_provenance": target_provenance,
        "source_execution_ledger": dict(source_execution_ledger),
        "observed_decisions": [
            serialize_t090_observed_decision(item) for item in observed
        ],
        "examples": [serialize_t090_example(item) for item in deduped],
        "collision_deduplication": collision_report,
        "coverage": coverage,
    }


def serialize_t090_observed_decision(item: T090ObservedDecision) -> dict[str, object]:
    return {
        "source_identity": item.source_identity,
        "source_group": item.source_group,
        "split": item.split,
        "decision_identity": item.decision_identity,
        "public_fingerprint": item.public_fingerprint,
        "legal_action_count": item.legal_action_count,
        "multi_action": item.multi_action,
        "target_eligible": item.target_eligible,
        "ineligible_reasons": list(item.ineligible_reasons),
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
    observed_decisions: Sequence[T090ObservedDecision] | None = None,
) -> dict[str, object]:
    observed = tuple(observed_decisions or ())
    if not observed:
        observed = tuple(
            T090ObservedDecision(
                source_identity=item.source_identity,
                source_group=item.source_group,
                split=item.split,
                decision_identity=item.decision_identity,
                public_fingerprint=item.public_fingerprint,
                legal_action_count=len(item.legal_action_identities),
                multi_action=item.eligible,
                target_eligible=item.eligible,
                ineligible_reasons=(),
            )
            for item in examples
        )
    eligible = [item for item in examples if item.eligible]
    observed_multi = [item for item in observed if item.multi_action]
    raw_eligible_multi = [item for item in observed_multi if item.target_eligible]
    per_split = {
        split: [item for item in eligible if item.split == split]
        for split in T090_SPLITS
    }
    per_group = {
        split: sorted({item.source_group for item in values})
        for split, values in per_split.items()
    }
    rate = len(raw_eligible_multi) / len(observed_multi) if observed_multi else 0.0
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
        "raw_target_eligible_multi_action_count": len(raw_eligible_multi),
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
        _validate_public_input_fields(public)
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
    *,
    expected_split_manifest: Mapping[str, object],
    expected_native_source_manifest: Mapping[str, object],
) -> tuple[T090DecisionExample, ...]:
    """Validate the current target schema without trusting its summaries."""

    if (
        value.get("schema_id") != T090_TARGET_SCHEMA_ID
        or value.get("schema_version") != 1
        or value.get("task_id") != T090_TASK_ID
    ):
        raise T090Incomplete("unsupported T090 target schema")
    split_entries = {
        entry.source_identity: entry
        for entry in validate_t090_split_manifest(expected_split_manifest)
    }
    if value.get("split_manifest_sha256") != canonical_sha256(expected_split_manifest):
        raise T090Incomplete(
            "T090 target table is not bound to the supplied split manifest"
        )
    provenance = _mapping(value.get("target_provenance"), "target provenance")
    validate_t090_target_provenance(
        provenance,
        split_manifest=expected_split_manifest,
        native_source_manifest=expected_native_source_manifest,
    )
    ledger = _mapping(value.get("source_execution_ledger"), "source execution ledger")
    validate_t090_source_execution_ledger(
        ledger, split_manifest=expected_split_manifest
    )
    examples = deserialize_t090_examples(value)
    seen_decisions: set[tuple[str, str]] = set()
    for example in examples:
        expected_entry = split_entries.get(example.source_identity)
        if expected_entry is None:
            raise T090Incomplete(
                "T090 target example source is outside the frozen split"
            )
        if (
            example.source_group != expected_entry.source_group
            or example.split != expected_entry.split
        ):
            raise T090Incomplete(
                "T090 target example split/group differs from frozen split"
            )
        decision_key = (example.source_identity, example.decision_identity)
        if decision_key in seen_decisions:
            raise T090Incomplete(
                "T090 target decision identity is not unique per source"
            )
        seen_decisions.add(decision_key)
    observed = deserialize_t090_observed_decisions(value)
    observed_keys: set[tuple[str, str]] = set()
    eligible_keys: set[tuple[str, str]] = set()
    eligible_observed_by_key: dict[tuple[str, str], T090ObservedDecision] = {}
    for item in observed:
        expected_entry = split_entries.get(item.source_identity)
        if expected_entry is None or (
            item.source_group != expected_entry.source_group
            or item.split != expected_entry.split
        ):
            raise T090Incomplete("T090 observed decision differs from frozen split")
        key = (item.source_identity, item.decision_identity)
        if key in observed_keys:
            raise T090Incomplete("T090 observed decision identity is duplicated")
        observed_keys.add(key)
        if item.target_eligible:
            eligible_keys.add(key)
            eligible_observed_by_key[key] = item
    if not seen_decisions.issubset(eligible_keys):
        raise T090Incomplete("T090 retained target lacks an eligible observed decision")
    for example in examples:
        observed_item = eligible_observed_by_key[
            (example.source_identity, example.decision_identity)
        ]
        if (
            observed_item.public_fingerprint != example.public_fingerprint
            or observed_item.legal_action_count != len(example.legal_action_identities)
        ):
            raise T090Incomplete(
                "T090 observed decision does not bind the retained target payload"
            )
    collision = _mapping(value.get("collision_deduplication"), "collision report")
    if collision.get("fingerprint_schema_id") != T090_FINGERPRINT_SCHEMA_ID:
        raise T090Incomplete("T090 collision report fingerprint schema is invalid")
    if int(collision.get("retained_count", -1)) != len(examples):
        raise T090Incomplete("T090 collision report retained count is inconsistent")
    if len({item.public_fingerprint for item in examples}) != len(examples):
        raise T090Incomplete(
            "T090 target table still contains duplicate public fingerprints"
        )
    expected_coverage = t090_coverage_report(examples, observed_decisions=observed)
    coverage = _mapping(value.get("coverage"), "coverage report")
    if dict(coverage) != expected_coverage:
        raise T090Incomplete("T090 target coverage report is inconsistent")
    return examples


def deserialize_t090_observed_decisions(
    value: Mapping[str, object],
) -> tuple[T090ObservedDecision, ...]:
    observed: list[T090ObservedDecision] = []
    for raw in _sequence(value.get("observed_decisions"), "observed decisions"):
        row = _mapping(raw, "observed decision")
        legal_action_count = row.get("legal_action_count")
        if (
            isinstance(legal_action_count, bool)
            or not isinstance(legal_action_count, int)
            or legal_action_count < 1
        ):
            raise T090Incomplete("T090 observed decision legal action count is invalid")
        multi_action = row.get("multi_action")
        target_eligible = row.get("target_eligible")
        if not isinstance(multi_action, bool) or not isinstance(target_eligible, bool):
            raise T090Incomplete("T090 observed decision eligibility flags are invalid")
        reasons = tuple(
            _string(item, "ineligible reason")
            for item in _sequence(row.get("ineligible_reasons"), "ineligible reasons")
        )
        if multi_action != (legal_action_count > 1):
            raise T090Incomplete("T090 observed decision multi-action flag is invalid")
        if target_eligible and (not multi_action or reasons):
            raise T090Incomplete("T090 eligible observed decision has invalid reasons")
        if not target_eligible and not reasons:
            raise T090Incomplete("T090 ineligible observed decision lacks a reason")
        observed.append(
            T090ObservedDecision(
                source_identity=_identity(
                    row.get("source_identity"), "source_identity"
                ),
                source_group=_string(row.get("source_group"), "source_group"),
                split=_string(row.get("split"), "split"),
                decision_identity=_identity(
                    row.get("decision_identity"), "decision_identity"
                ),
                public_fingerprint=_string(
                    row.get("public_fingerprint"), "public_fingerprint"
                ),
                legal_action_count=legal_action_count,
                multi_action=multi_action,
                target_eligible=target_eligible,
                ineligible_reasons=reasons,
            )
        )
    return tuple(observed)


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


def t090_validation_target_sha256(
    examples: Sequence[T090DecisionExample],
) -> str:
    """Identify the exact validation labels used for seed selection."""

    return canonical_sha256(
        [
            {
                "public_fingerprint": item.public_fingerprint,
                "teacher_means": list(item.teacher_means),
            }
            for item in examples
        ]
    )


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
    validation_target_regime = (
        "shuffled_validation_teacher_means" if shuffled else "true_teacher_means"
    )
    validation_target_examples = (
        tuple(
            replace(item, teacher_means=shuffled_teacher_means(item))
            for item in validation
        )
        if shuffled
        else tuple(validation)
    )
    validation_metrics = t090_rank_metrics(validation_target_examples, scorer)
    return scorer, {
        "schema_id": "t090-battle-student-training-summary-v1",
        "task_id": T090_TASK_ID,
        "seed": seed,
        "shuffled_target_control": shuffled,
        "validation_target_regime": validation_target_regime,
        "validation_target_seed": T090_SHUFFLE_SEED if shuffled else None,
        "validation_target_sha256": t090_validation_target_sha256(
            validation_target_examples
        ),
        "config": config.to_dict(),
        "epoch_pairwise_losses": epoch_losses,
        "validation": validation_metrics,
    }


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _target_table_identity(
    target_table: Mapping[str, object],
    *,
    expected_split_manifest: Mapping[str, object],
    expected_native_source_manifest: Mapping[str, object],
) -> tuple[tuple[T090DecisionExample, ...], dict[str, object]]:
    examples = validate_t090_target_table(
        target_table,
        expected_split_manifest=expected_split_manifest,
        expected_native_source_manifest=expected_native_source_manifest,
    )
    return examples, {
        "target_table_sha256": canonical_sha256(target_table),
        "target_provenance": dict(target_table["target_provenance"]),
    }


def save_t090_checkpoint(
    scorer: T090TorchScorer,
    path: str | Path,
    *,
    role: str,
    seed: int,
    target_table: Mapping[str, object],
    expected_split_manifest: Mapping[str, object],
    expected_native_source_manifest: Mapping[str, object],
    selection_provenance: Mapping[str, object],
) -> dict[str, object]:
    """Serialize a selected public scorer with all target/config bindings."""

    if role not in {"student", "shuffled_target_control"}:
        raise T090ContractError("T090 checkpoint role is invalid")
    if seed not in T090_MODEL_SEEDS:
        raise T090ContractError("T090 checkpoint seed is not preregistered")
    examples, target_identity = _target_table_identity(
        target_table,
        expected_split_manifest=expected_split_manifest,
        expected_native_source_manifest=expected_native_source_manifest,
    )
    if scorer.config != build_t090_training_config(examples):
        raise T090Incomplete("T090 checkpoint scorer config differs from target table")
    _validate_selection_provenance(selection_provenance, role=role, seed=seed)
    import torch

    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_id": T090_CHECKPOINT_SCHEMA_ID,
        "schema_version": 1,
        "task_id": T090_TASK_ID,
        "role": role,
        "seed": seed,
        "training_config": scorer.config.to_dict(),
        "target_identity": target_identity,
        "selection_provenance": dict(selection_provenance),
        "model_state_dict": scorer.model.state_dict(),
    }
    torch.save(payload, destination)
    return {
        "path": str(destination.resolve()),
        "sha256": sha256_file(destination),
        "size_bytes": destination.stat().st_size,
        "schema_id": T090_CHECKPOINT_SCHEMA_ID,
        "role": role,
        "seed": seed,
        "target_table_sha256": target_identity["target_table_sha256"],
        "training_config_sha256": canonical_sha256(scorer.config.to_dict()),
        "validation_target_regime": selection_provenance["validation_target_regime"],
        "validation_target_seed": selection_provenance["validation_target_seed"],
        "validation_target_sha256": selection_provenance["validation_target_sha256"],
        "selection_provenance_sha256": canonical_sha256(selection_provenance),
    }


def _validate_selection_provenance(
    value: Mapping[str, object], *, role: str, seed: int
) -> None:
    candidates = _mapping(
        value.get("candidate_checkpoint_sha256_by_seed"),
        "candidate checkpoint hashes",
    )
    if (
        value.get("selection_split") != "validation"
        or value.get("selection_metric") != "mean_teacher_regret"
        or value.get("selected_seed") != seed
        or value.get("role") != role
        or set(candidates) != {str(item) for item in T090_MODEL_SEEDS}
        or any(
            not isinstance(digest, str) or len(digest) != 64
            for digest in candidates.values()
        )
        or not isinstance(value.get("validation_summaries_sha256"), str)
        or len(value["validation_summaries_sha256"]) != 64
        or not isinstance(value.get("validation_target_sha256"), str)
        or len(value["validation_target_sha256"]) != 64
        or value.get("validation_target_regime")
        != (
            "shuffled_validation_teacher_means"
            if role == "shuffled_target_control"
            else "true_teacher_means"
        )
        or value.get("validation_target_seed")
        != (T090_SHUFFLE_SEED if role == "shuffled_target_control" else None)
    ):
        raise T090Incomplete("T090 checkpoint selection provenance is invalid")


def load_t090_checkpoint(
    path: str | Path,
    *,
    expected_identity: Mapping[str, object],
    expected_role: str,
    expected_split_manifest: Mapping[str, object],
    expected_native_source_manifest: Mapping[str, object],
    expected_target_table: Mapping[str, object],
) -> T090TorchScorer:
    """Load only a checkpoint whose bytes and scientific bindings are exact."""

    resolved = Path(path).resolve(strict=True)
    if (
        expected_identity.get("path") != str(resolved)
        or expected_identity.get("sha256") != sha256_file(resolved)
        or expected_identity.get("size_bytes") != resolved.stat().st_size
        or expected_identity.get("schema_id") != T090_CHECKPOINT_SCHEMA_ID
        or expected_identity.get("role") != expected_role
        or expected_identity.get("seed") not in T090_MODEL_SEEDS
    ):
        raise T090Incomplete("T090 checkpoint artifact identity is invalid")
    examples, target_identity = _target_table_identity(
        expected_target_table,
        expected_split_manifest=expected_split_manifest,
        expected_native_source_manifest=expected_native_source_manifest,
    )
    import torch

    payload = torch.load(resolved, map_location="cpu", weights_only=True)
    if not isinstance(payload, Mapping):
        raise T090Incomplete("T090 checkpoint payload is not a mapping")
    if (
        payload.get("schema_id") != T090_CHECKPOINT_SCHEMA_ID
        or payload.get("schema_version") != 1
        or payload.get("task_id") != T090_TASK_ID
        or payload.get("role") != expected_role
        or payload.get("seed") not in T090_MODEL_SEEDS
        or payload.get("seed") != expected_identity.get("seed")
        or payload.get("target_identity") != target_identity
    ):
        raise T090Incomplete("T090 checkpoint payload binding is invalid")
    config_raw = _mapping(payload.get("training_config"), "checkpoint training config")
    config = T090TrainingConfig(
        **{
            key: tuple(value) if key == "model_seeds" else value
            for key, value in config_raw.items()
        }
    )
    if config != build_t090_training_config(examples):
        raise T090Incomplete("T090 checkpoint training config differs from target")
    selection = _mapping(payload.get("selection_provenance"), "selection provenance")
    _validate_selection_provenance(
        selection, role=expected_role, seed=int(payload["seed"])
    )
    model = _torch_model(config, seed=int(payload["seed"]))
    state_dict = payload.get("model_state_dict")
    if not isinstance(state_dict, Mapping):
        raise T090Incomplete("T090 checkpoint lacks model parameters")
    model.load_state_dict(state_dict)
    return T090TorchScorer(model, config)


def select_t090_validation_checkpoint(
    results: Sequence[tuple[T090TorchScorer, Mapping[str, object]]],
    *,
    expected_validation_target_regime: str,
    expected_validation_target_sha256: str,
) -> tuple[T090TorchScorer, Mapping[str, object]]:
    if len(results) != len(T090_MODEL_SEEDS):
        raise T090Incomplete("T090 must select among all three preregistered seeds")
    if expected_validation_target_regime not in {
        "true_teacher_means",
        "shuffled_validation_teacher_means",
    }:
        raise T090ContractError("T090 selection validation target regime is invalid")
    if (
        not isinstance(expected_validation_target_sha256, str)
        or len(expected_validation_target_sha256) != 64
    ):
        raise T090ContractError("T090 selection validation target identity is invalid")

    seeds: list[int] = []
    for _, raw_report in results:
        report = _mapping(raw_report, "training summary")
        seed = report.get("seed")
        if isinstance(seed, bool) or not isinstance(seed, int):
            raise T090Incomplete("T090 training summary seed is invalid")
        seeds.append(seed)
        if report.get("validation_target_regime") != expected_validation_target_regime:
            raise T090Incomplete(
                "T090 selection validation target regime is inconsistent"
            )
        expected_seed = (
            T090_SHUFFLE_SEED
            if expected_validation_target_regime == "shuffled_validation_teacher_means"
            else None
        )
        if report.get("validation_target_seed") != expected_seed:
            raise T090Incomplete(
                "T090 selection validation target seed is inconsistent"
            )
        if report.get("validation_target_sha256") != expected_validation_target_sha256:
            raise T090Incomplete(
                "T090 selection validation target identity is inconsistent"
            )
    if tuple(sorted(seeds)) != T090_MODEL_SEEDS:
        raise T090Incomplete(
            "T090 selection requires each preregistered seed exactly once"
        )

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
    rows: list[dict[str, object]] = []
    for item in eligible:
        selected, scores = _selection_and_scores(item, scorer)
        best_mean = max(item.teacher_means)
        teacher_best = min(
            index
            for index, value in enumerate(item.teacher_means)
            if value == best_mean
        )
        regret = best_mean - item.teacher_means[selected]
        rows.append(
            {
                "decision_identity": item.decision_identity,
                "source_group": item.source_group,
                "selected_action_kind": item.legal_action_kinds[selected],
                "student_action": selected,
                "teacher_means": list(item.teacher_means),
                "scores": scores,
                "legal_action_identities": [
                    dict(identity) for identity in item.legal_action_identities
                ],
                "legal_action_kinds": list(item.legal_action_kinds),
                "regret": regret,
                "top1": float(selected == teacher_best),
            }
        )
    return _metric_summary_from_rows(rows)


def _metric_summary_from_rows(
    rows: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    if not rows:
        raise T090Incomplete("T090 metrics require rows")
    agreements: list[float] = []
    regrets: list[float] = []
    accuracies: list[float] = []
    margins: list[float] = []
    ties = 0
    group: dict[str, list[float]] = defaultdict(list)
    action_kind: dict[str, list[float]] = defaultdict(list)
    normalized_rows: list[dict[str, object]] = []
    for raw in rows:
        row = _mapping(raw, "metric row")
        _identity(row.get("decision_identity"), "decision_identity")
        source_group = _string(row.get("source_group"), "source_group")
        selected_kind = _string(row.get("selected_action_kind"), "selected_action_kind")
        selected = row.get("student_action")
        if isinstance(selected, bool) or not isinstance(selected, int):
            raise T090Incomplete("T090 metric selected action is invalid")
        means = [
            _finite(value, "teacher mean")
            for value in _sequence(row.get("teacher_means"), "teacher_means")
        ]
        scores = [
            _finite(value, "student score")
            for value in _sequence(row.get("scores"), "scores")
        ]
        action_identities = [
            dict(_mapping(value, "legal action identity"))
            for value in _sequence(
                row.get("legal_action_identities"), "legal_action_identities"
            )
        ]
        action_kinds = [
            _string(value, "legal action kind")
            for value in _sequence(row.get("legal_action_kinds"), "legal_action_kinds")
        ]
        if (
            len(means) < 2
            or len(means) != len(scores)
            or len(means) != len(action_identities)
            or len(means) != len(action_kinds)
            or selected < 0
            or selected >= len(scores)
        ):
            raise T090Incomplete("T090 metric action rows are invalid")
        if selected_kind != action_kinds[selected]:
            raise T090Incomplete("T090 metric selected action kind is inconsistent")
        best_mean = max(means)
        teacher_best = min(
            index for index, value in enumerate(means) if value == best_mean
        )
        regret = best_mean - means[selected]
        top1 = float(selected == teacher_best)
        if row.get("regret") != regret or row.get("top1") != top1:
            raise T090Incomplete("T090 metric row regret/agreement is inconsistent")
        agreements.append(top1)
        regrets.append(regret)
        group[source_group].append(regret)
        action_kind[selected_kind].append(regret)
        ordered_scores = sorted(scores, reverse=True)
        margin = ordered_scores[0] - ordered_scores[1]
        margins.append(margin)
        ties += int(abs(margin) <= 1e-12)
        for left in range(len(scores)):
            for right in range(left + 1, len(scores)):
                if abs(means[left] - means[right]) > 1e-9:
                    accuracies.append(
                        float(
                            (means[left] > means[right])
                            == (scores[left] > scores[right])
                        )
                    )
        normalized_rows.append(dict(row))
    return {
        "state_count": len(normalized_rows),
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
        "tie_rate": ties / len(normalized_rows),
        "per_state": normalized_rows,
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
    *,
    target_table: Mapping[str, object],
    expected_split_manifest: Mapping[str, object],
    expected_native_source_manifest: Mapping[str, object],
    student_checkpoint: Mapping[str, object],
    control_checkpoint: Mapping[str, object],
) -> dict[str, object]:
    target_examples, target_identity = _target_table_identity(
        target_table,
        expected_split_manifest=expected_split_manifest,
        expected_native_source_manifest=expected_native_source_manifest,
    )
    if tuple(examples) != target_examples:
        raise T090Incomplete(
            "T090 held-out examples are not the validated target table"
        )
    _validate_checkpoint_reference(
        student_checkpoint, role="student", target_identity=target_identity
    )
    _validate_checkpoint_reference(
        control_checkpoint,
        role="shuffled_target_control",
        target_identity=target_identity,
    )
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
    boundary_evidence = {
        "target_provenance_validated": True,
        "public_input_contract": target_table["target_provenance"][
            "public_input_contract"
        ],
        "teacher_config": target_table["target_provenance"]["teacher_config"],
        "student_inference_search_calls": 0,
        "control_inference_search_calls": 0,
    }
    split_evidence = {
        "target_table_validated": True,
        "unique_retained_public_fingerprints": len(
            {item.public_fingerprint for item in target_examples}
        )
        == len(target_examples),
        "heldout_source_groups": sorted({item.source_group for item in heldout}),
    }
    return {
        "schema_id": T090_HELDOUT_SCHEMA_ID,
        "schema_version": 1,
        "task_id": T090_TASK_ID,
        "target_table_sha256": target_identity["target_table_sha256"],
        "target_provenance": target_identity["target_provenance"],
        "student_checkpoint": dict(student_checkpoint),
        "shuffled_target_control_checkpoint": dict(control_checkpoint),
        "student": student_metrics,
        "shuffled_target_control": control_metrics,
        "paired_delta_regret": regrets,
        "paired_delta_top1_agreement": agreements,
        "paired_bootstrap_mean_delta_regret": regret_bootstrap,
        "paired_bootstrap_top1_agreement": agreement_bootstrap,
        "information_boundary_evidence": boundary_evidence,
        "information_boundary_valid": all(
            value is True or value == 0
            for key, value in boundary_evidence.items()
            if key != "public_input_contract" and key != "teacher_config"
        )
        and boundary_evidence["public_input_contract"] == T090_PUBLIC_INPUT_CONTRACT
        and boundary_evidence["teacher_config"] == T090_TEACHER_CONFIG,
        "split_leakage_evidence": split_evidence,
        "split_leakage_valid": all(
            value is True or value == list(T090_SOURCE_GROUPS)
            for value in split_evidence.values()
        ),
        "terminal_classification": "BATTLE_STUDENT_DISTILLATION_SIGNAL_ESTABLISHED"
        if passed
        else "BATTLE_STUDENT_DISTILLATION_SIGNAL_NOT_ESTABLISHED",
    }


def _validate_checkpoint_reference(
    value: Mapping[str, object], *, role: str, target_identity: Mapping[str, object]
) -> None:
    if (
        value.get("schema_id") != T090_CHECKPOINT_SCHEMA_ID
        or value.get("role") != role
        or value.get("target_table_sha256") != target_identity["target_table_sha256"]
        or value.get("seed") not in T090_MODEL_SEEDS
        or not isinstance(value.get("path"), str)
        or not value["path"]
        or not isinstance(value.get("sha256"), str)
        or len(value["sha256"]) != 64
        or isinstance(value.get("size_bytes"), bool)
        or not isinstance(value.get("size_bytes"), int)
        or value["size_bytes"] < 0
        or not isinstance(value.get("training_config_sha256"), str)
        or len(value["training_config_sha256"]) != 64
        or value.get("validation_target_regime")
        != (
            "shuffled_validation_teacher_means"
            if role == "shuffled_target_control"
            else "true_teacher_means"
        )
        or value.get("validation_target_seed")
        != (T090_SHUFFLE_SEED if role == "shuffled_target_control" else None)
        or not isinstance(value.get("validation_target_sha256"), str)
        or len(value["validation_target_sha256"]) != 64
        or not isinstance(value.get("selection_provenance_sha256"), str)
        or len(value["selection_provenance_sha256"]) != 64
    ):
        raise T090Incomplete(f"T090 {role} checkpoint reference is invalid")


def _mapping_rows(value: object) -> list[Mapping[str, object]]:
    return [_mapping(item, "metric row") for item in _sequence(value, "metric rows")]


def validate_t090_heldout_report(
    value: Mapping[str, object],
    *,
    expected_target_table: Mapping[str, object],
    expected_split_manifest: Mapping[str, object],
    expected_native_source_manifest: Mapping[str, object],
    expected_student_checkpoint: Mapping[str, object],
    expected_control_checkpoint: Mapping[str, object],
) -> None:
    if (
        value.get("schema_id") != T090_HELDOUT_SCHEMA_ID
        or value.get("schema_version") != 1
        or value.get("task_id") != T090_TASK_ID
    ):
        raise T090Incomplete("unsupported T090 held-out report")
    target_examples, target_identity = _target_table_identity(
        expected_target_table,
        expected_split_manifest=expected_split_manifest,
        expected_native_source_manifest=expected_native_source_manifest,
    )
    if (
        value.get("target_table_sha256") != target_identity["target_table_sha256"]
        or value.get("target_provenance") != target_identity["target_provenance"]
    ):
        raise T090Incomplete("T090 held-out report target provenance is invalid")
    student_checkpoint = _mapping(value.get("student_checkpoint"), "student checkpoint")
    control_checkpoint = _mapping(
        value.get("shuffled_target_control_checkpoint"), "control checkpoint"
    )
    _validate_checkpoint_reference(
        student_checkpoint, role="student", target_identity=target_identity
    )
    _validate_checkpoint_reference(
        control_checkpoint,
        role="shuffled_target_control",
        target_identity=target_identity,
    )
    if dict(student_checkpoint) != dict(expected_student_checkpoint) or dict(
        control_checkpoint
    ) != dict(expected_control_checkpoint):
        raise T090Incomplete("T090 held-out report checkpoint identities differ")
    summaries: dict[str, Mapping[str, object]] = {}
    for name in ("student", "shuffled_target_control"):
        metrics = _mapping(value.get(name), name)
        rows = _mapping_rows(metrics.get("per_state"))
        expected_metrics = _metric_summary_from_rows(rows)
        if dict(metrics) != expected_metrics:
            raise T090Incomplete(f"T090 {name} metric distributions are inconsistent")
        summaries[name] = metrics
    student_rows = _mapping_rows(summaries["student"]["per_state"])
    control_rows = _mapping_rows(summaries["shuffled_target_control"]["per_state"])
    if [row.get("decision_identity") for row in student_rows] != [
        row.get("decision_identity") for row in control_rows
    ]:
        raise T090Incomplete("T090 held-out per-state rows are not paired")
    expected_heldout = [
        example
        for example in target_examples
        if example.split == "heldout" and example.eligible
    ]
    if len(student_rows) != len(expected_heldout):
        raise T090Incomplete("T090 held-out rows do not cover the target table")
    for model_rows in (student_rows, control_rows):
        for row, expected in zip(model_rows, expected_heldout, strict=True):
            if (
                row.get("decision_identity") != expected.decision_identity
                or row.get("source_group") != expected.source_group
                or row.get("teacher_means") != list(expected.teacher_means)
                or row.get("legal_action_identities")
                != [dict(identity) for identity in expected.legal_action_identities]
                or row.get("legal_action_kinds") != list(expected.legal_action_kinds)
            ):
                raise T090Incomplete(
                    "T090 held-out per-state row differs from the validated target table"
                )
    expected_regret = [
        _finite(control["regret"], "control regret")
        - _finite(student["regret"], "student regret")
        for student, control in zip(student_rows, control_rows, strict=True)
    ]
    expected_agreement = [
        _finite(student["top1"], "student agreement")
        - _finite(control["top1"], "control agreement")
        for student, control in zip(student_rows, control_rows, strict=True)
    ]
    delta = [
        _finite(item, "delta regret")
        for item in _sequence(value.get("paired_delta_regret"), "paired_delta_regret")
    ]
    agreement_delta = [
        _finite(item, "delta agreement")
        for item in _sequence(
            value.get("paired_delta_top1_agreement"), "paired_delta_top1_agreement"
        )
    ]
    if delta != expected_regret or agreement_delta != expected_agreement:
        raise T090Incomplete("T090 held-out paired deltas are inconsistent")
    bootstrap = _mapping(
        value.get("paired_bootstrap_mean_delta_regret"), "paired bootstrap"
    )
    if dict(bootstrap) != paired_t090_bootstrap(delta):
        raise T090Incomplete("T090 regret bootstrap does not match paired values")
    secondary = _mapping(
        value.get("paired_bootstrap_top1_agreement"), "paired top1 bootstrap"
    )
    if dict(secondary) != paired_t090_bootstrap(agreement_delta):
        raise T090Incomplete("T090 top1 bootstrap does not match paired values")
    boundary = _mapping(
        value.get("information_boundary_evidence"), "information boundary evidence"
    )
    split = _mapping(value.get("split_leakage_evidence"), "split leakage evidence")
    if (
        value.get("information_boundary_valid") is not True
        or value.get("split_leakage_valid") is not True
        or boundary.get("target_provenance_validated") is not True
        or boundary.get("public_input_contract") != T090_PUBLIC_INPUT_CONTRACT
        or boundary.get("teacher_config") != T090_TEACHER_CONFIG
        or boundary.get("student_inference_search_calls") != 0
        or boundary.get("control_inference_search_calls") != 0
        or split.get("target_table_validated") is not True
        or split.get("unique_retained_public_fingerprints") is not True
        or split.get("heldout_source_groups") != list(T090_SOURCE_GROUPS)
    ):
        raise T090Incomplete("T090 information or split-leakage evidence is invalid")
    lower = _sequence(bootstrap.get("ci_95"), "bootstrap ci")[0]
    student = summaries["student"]
    control = summaries["shuffled_target_control"]
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
    "T090_CHECKPOINT_SCHEMA_ID",
    "T090_CONFIG_SCHEMA_ID",
    "T090_HELDOUT_SCHEMA_ID",
    "T090_MODEL_SEEDS",
    "T090_SOURCE_EXECUTION_SCHEMA_ID",
    "T090_SPLIT_SCHEMA_ID",
    "T090_TARGET_SCHEMA_ID",
    "T090ContractError",
    "T090DecisionExample",
    "T090Incomplete",
    "T090ObservedDecision",
    "T090TorchScorer",
    "T090TrainingConfig",
    "build_t090_heldout_report",
    "build_t090_split_manifest",
    "build_t090_target_provenance",
    "build_t090_training_config",
    "canonical_sha256",
    "deduplicate_t090_examples",
    "deserialize_t090_examples",
    "load_t090_checkpoint",
    "materialize_t090_decision",
    "materialize_t090_targets",
    "paired_t090_bootstrap",
    "public_decision_fingerprint",
    "save_t090_checkpoint",
    "select_t090_validation_checkpoint",
    "sha256_file",
    "shuffled_teacher_means",
    "t090_coverage_report",
    "t090_rank_metrics",
    "t090_validation_target_sha256",
    "train_t090_scorer",
    "validate_t090_heldout_report",
    "validate_t090_source_execution_ledger",
    "validate_t090_split_manifest",
    "validate_t090_t087_source_cohort_identity",
    "validate_t090_target_provenance",
    "validate_t090_target_table",
]
