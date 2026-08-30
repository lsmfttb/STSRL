"""Reuse and lineage boundary for the T077 continuation of T075.

T077 starts at TARGET. It verifies, but never rewrites, the exact T075 source,
selection, control, terminal, and retention artifacts. Scientific payloads from
TARGET onward continue to use inherited T065 schemas.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sts_combat_rl.sim.lightspeed_source import load_lightspeed_source_manifest
from sts_combat_rl.sim.non_combat_acceptance import (
    T075_SOURCE_IDENTITIES,
    ArtifactIdentity,
    StageOutcome,
    canonical_json_document,
    validate_t075_ownership_audit,
    validate_t075_preflight_audit,
    validate_t075_retention_manifest,
    validate_t075_source_reuse_audit,
    validate_t075_terminal_decision,
)
from sts_combat_rl.sim.non_combat_learning import (
    T065_MANDATORY_FAMILIES,
    T065_SPLIT_QUOTAS,
    T065_SPLITS,
    T065SourceState,
    file_sha256,
)

T077_TASK_ID = "T077"
T077_APPROVED_SPEC = "3690149970b342fab62bd67c564a84bbd293b134"
T077_ACCEPTED_T076_INTEGRATION = "cc40c8cc51cc3f1e5ccb9d67bc4bccdf635ba083"
T077_INHERITED_T075_INTEGRATION = "fee272f1ae21c283ad2161f55293cfe6d714134a"
T077_INHERITED_T075_RUN_HEAD = "cb54e368c4f099ae828c2b863f4db07b4f3fcb5f"
T077_EARLIEST_STAGE = "TARGET"
T077_ROOT_RELATIVE = "artifacts/t077-t075-same-experiment-continuation"
T075_ROOT_RELATIVE = "artifacts/t075-leakage-safe-non-combat-cohort-repair"
T077_STAGES = ("TARGET", "TRAIN", "GATE", "EVAL")
_GIT_COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")


def _identity(role: str, path: str, sha256: str, size_bytes: int) -> ArtifactIdentity:
    return ArtifactIdentity(role=role, path=path, sha256=sha256, size_bytes=size_bytes)


T075_PREFLIGHT_OUTCOME = _identity(
    "stage_outcome",
    f"{T075_ROOT_RELATIVE}/outcomes/00-preflight.json",
    "215ea8f0b812040e380f77a2870df800246d5c12e4b922143d2a87b19c25ec64",
    423,
)
T075_PREFLIGHT_AUDIT = _identity(
    "preflight_audit",
    f"{T075_ROOT_RELATIVE}/preflight-audit.json",
    "682f6b08c92060d6197ba251e73c6a4322495fe452f3d5c71d47ea46e3fd13b6",
    584,
)
T075_SOURCE_REUSE_OUTCOME = _identity(
    "stage_outcome",
    f"{T075_ROOT_RELATIVE}/outcomes/01-source_reuse.json",
    "99cde3eb3d3482c759ee59de900d7bfe1de4ff07e5a59245018a58d1fd7fe29d",
    1078,
)
T075_SOURCE_REUSE_AUDIT = _identity(
    "source_reuse_audit",
    f"{T075_ROOT_RELATIVE}/source-reuse-audit.json",
    "319158ad3be2da2b1f3d31939b0e80e58a858235b9511f2ab56efb359350ba32",
    640,
)
T075_SELECTION_OUTCOME = _identity(
    "stage_outcome",
    f"{T075_ROOT_RELATIVE}/outcomes/02-selection_replay.json",
    "3d6c7c72ea1096cc47ba10dc4565167ea89f3d288fa815e67b7dd8f65d14d2e4",
    852,
)
T075_OWNERSHIP_AUDIT = _identity(
    "ownership_audit",
    f"{T075_ROOT_RELATIVE}/ownership-audit.json",
    "b6f6fc71c61747faf0f2bd33bb67e81f431ffa204f2f4a3bc1dabe3d03b1ece1",
    4536275,
)
T075_SELECTED_STATES = _identity(
    "selected_states",
    f"{T075_ROOT_RELATIVE}/selected-states.jsonl",
    "94857d0e310f34cdd2780920ec81f9dc60e179c94244b9e231952a43a5f4e8b8",
    226521456,
)
T075_TARGET_OUTCOME = _identity(
    "stage_outcome",
    f"{T075_ROOT_RELATIVE}/outcomes/03-target.json",
    "97151852fb14b175face7da77992b951ff7b3f6d4321e796ce8c55c0c1b9d9ba",
    644,
)
T075_TERMINAL_REPORT = _identity(
    "terminal_report",
    f"{T075_ROOT_RELATIVE}/terminal-decision.json",
    "fde7538a4a58ceffa7f52903d92b4cb873b2eb0902ee45632285bce3bf400886",
    1107,
)
T075_RETENTION_MANIFEST = _identity(
    "retention_manifest",
    f"{T075_ROOT_RELATIVE}/retention.json",
    "ebc6d107ba36322890a1e522a18ab5265d8003d0ba7c6529dc49d454346d4e46",
    10339,
)
T075_RETAINED_LINEAGE = (
    *(ArtifactIdentity.from_mapping(item) for item in T075_SOURCE_IDENTITIES),
    T075_PREFLIGHT_OUTCOME,
    T075_PREFLIGHT_AUDIT,
    T075_SOURCE_REUSE_OUTCOME,
    T075_SOURCE_REUSE_AUDIT,
    T075_SELECTION_OUTCOME,
    T075_OWNERSHIP_AUDIT,
    T075_SELECTED_STATES,
    T075_TARGET_OUTCOME,
    T075_TERMINAL_REPORT,
)


def _git_commit(value: str, label: str) -> str:
    if not isinstance(value, str) or not _GIT_COMMIT_RE.fullmatch(value):
        raise ValueError(f"{label} must be 40 lowercase hexadecimal characters")
    return value


def _artifact_identities(
    values: Sequence[ArtifactIdentity | Mapping[str, Any]],
) -> tuple[ArtifactIdentity, ...]:
    return tuple(
        value
        if isinstance(value, ArtifactIdentity)
        else ArtifactIdentity.from_mapping(value)
        for value in values
    )


def artifact_path(repository_root: Path, identity: ArtifactIdentity) -> Path:
    return Path(repository_root).joinpath(*identity.path.split("/"))


def verify_artifact_identity(
    repository_root: Path, identity: ArtifactIdentity
) -> ArtifactIdentity:
    """Verify one exact path/size/SHA identity with bounded memory."""

    path = artifact_path(repository_root, identity)
    if not path.is_file():
        raise FileNotFoundError(f"missing retained T075 input: {identity.path}")
    if (
        path.stat().st_size != identity.size_bytes
        or file_sha256(path) != identity.sha256
    ):
        raise ValueError(f"retained T075 input identity mismatch: {identity.path}")
    return identity


def verify_t075_retained_inputs(
    repository_root: Path,
    *,
    retained_t075_sources: Sequence[ArtifactIdentity | Mapping[str, Any]] = (
        T075_SOURCE_IDENTITIES
    ),
) -> tuple[ArtifactIdentity, ...]:
    """Verify exact retained T075 source identities with streaming SHA-256."""

    verified = _artifact_identities(retained_t075_sources)
    for identity in verified:
        verify_artifact_identity(repository_root, identity)
    return verified


def _read_json(repository_root: Path, identity: ArtifactIdentity) -> Mapping[str, Any]:
    verify_artifact_identity(repository_root, identity)
    value = json.loads(
        artifact_path(repository_root, identity).read_text(encoding="utf-8")
    )
    if not isinstance(value, Mapping):
        raise TypeError(f"retained artifact is not an object: {identity.path}")
    return value


def _outcome(
    repository_root: Path, identity: ArtifactIdentity, expected_stage: str
) -> StageOutcome:
    outcome = StageOutcome.from_mapping(_read_json(repository_root, identity))
    if outcome.run_head != T077_INHERITED_T075_RUN_HEAD:
        raise ValueError(f"T075 {expected_stage} outcome run head is not immutable")
    if outcome.stage != expected_stage:
        raise ValueError(f"T075 {expected_stage} outcome stage is not exact")
    return outcome


def iter_selected_states_strict(path: Path) -> Iterator[T065SourceState]:
    """Strictly parse retained JSONL one row at a time."""

    with path.open("r", encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, 1):
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"selected-state line {line_number} is invalid JSON"
                ) from exc
            if not isinstance(value, Mapping):
                raise TypeError(f"selected-state line {line_number} is not an object")
            yield T065SourceState.from_dict(value)


def validate_selected_states_320(
    path: Path,
    *,
    state_iterator: Callable[
        [Path], Iterator[T065SourceState]
    ] = iter_selected_states_strict,
) -> dict[str, Any]:
    """Validate exact cohort shape/order/replay uniqueness in bounded memory."""

    counts: Counter[tuple[str, str]] = Counter()
    replay_keys: set[str] = set()
    row_count = 0
    for state in state_iterator(path):
        if state.selected_state_index != row_count:
            raise ValueError("T075 selected-state indices are not exact 0..319")
        expected_family = T065_MANDATORY_FAMILIES[row_count // 80]
        split_offset = row_count % 80
        expected_split = (
            "train"
            if split_offset < 48
            else "validation"
            if split_offset < 64
            else "heldout"
        )
        if state.family != expected_family or state.split != expected_split:
            raise ValueError("T075 selected-state family/split order is not frozen")
        replay_key = json.dumps(
            [
                state.family,
                state.public_state_identity,
                [dict(item) for item in state.legal_action_identities],
            ],
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
        if replay_key in replay_keys:
            raise ValueError("T075 selected cohort contains a replay duplicate")
        replay_keys.add(replay_key)
        counts[(state.family, state.split)] += 1
        row_count += 1
    if row_count != 320:
        raise ValueError(f"T075 selected cohort has {row_count} rows, expected 320")
    expected_counts = {
        (family, split): T065_SPLIT_QUOTAS[split]
        for family in T065_MANDATORY_FAMILIES
        for split in T065_SPLITS
    }
    if dict(counts) != expected_counts:
        raise ValueError("T075 selected cohort quotas are not exact")
    return {
        "selected_state_count": row_count,
        "unique_replay_key_count": len(replay_keys),
        "counts_by_family_split": {
            family: {split: counts[(family, split)] for split in T065_SPLITS}
            for family in T065_MANDATORY_FAMILIES
        },
    }


def verify_t076_source_manifest(repository_root: Path) -> dict[str, Any]:
    """Verify committed manifest binds the accepted T076 integration."""

    manifest = load_lightspeed_source_manifest(
        Path(repository_root) / "docs/sts_lightspeed_source_manifest.json"
    )
    if manifest.integration.commit != T077_ACCEPTED_T076_INTEGRATION:
        raise ValueError("T077 source manifest does not bind accepted T076 commit")
    if manifest.integration.branch != "stsrl/main":
        raise ValueError("T077 source manifest branch is not stsrl/main")
    return {
        "manifest_path": "docs/sts_lightspeed_source_manifest.json",
        "schema_id": manifest.schema_id,
        "manifest_version": manifest.manifest_version,
        "integration_repository_url": manifest.integration.repository_url,
        "integration_branch": manifest.integration.branch,
        "integration_ref": manifest.integration.ref,
        "integration_commit": manifest.integration.commit,
    }


def verify_t075_reuse_boundary(repository_root: Path) -> dict[str, Any]:
    """Validate every authoritative T075 input needed to resume at TARGET."""

    root = Path(repository_root)
    sources = verify_t075_retained_inputs(root)
    retention = _read_json(root, T075_RETENTION_MANIFEST)
    validate_t075_retention_manifest(
        retention, expected_artifacts=T075_RETAINED_LINEAGE
    )
    if (
        retention["run_head"] != T077_INHERITED_T075_RUN_HEAD
        or retention["terminal_case"] != "D"
        or retention["terminal_report"] != T075_TERMINAL_REPORT.to_dict()
    ):
        raise ValueError("T075 retention terminal lineage is not immutable")

    preflight_outcome = _outcome(root, T075_PREFLIGHT_OUTCOME, "PREFLIGHT")
    source_outcome = _outcome(root, T075_SOURCE_REUSE_OUTCOME, "SOURCE_REUSE")
    selection_outcome = _outcome(root, T075_SELECTION_OUTCOME, "SELECTION_REPLAY")
    target_outcome = _outcome(root, T075_TARGET_OUTCOME, "TARGET")
    if not (preflight_outcome.valid and preflight_outcome.passed):
        raise ValueError("T075 PREFLIGHT was not valid/pass")
    if not (source_outcome.valid and source_outcome.passed):
        raise ValueError("T075 SOURCE_REUSE was not valid/pass")
    if not (selection_outcome.valid and selection_outcome.passed):
        raise ValueError("T075 SELECTION_REPLAY was not valid/pass")
    if (
        target_outcome.valid
        or target_outcome.passed
        or target_outcome.failure_code != "TARGET_INVALID"
        or target_outcome.outputs
    ):
        raise ValueError("T075 immutable TARGET Case D outcome changed")

    preflight = _read_json(root, T075_PREFLIGHT_AUDIT)
    validate_t075_preflight_audit(preflight)
    if (
        preflight["run_head"] != T077_INHERITED_T075_RUN_HEAD
        or preflight["sts_lightspeed_integration"] != T077_INHERITED_T075_INTEGRATION
    ):
        raise ValueError("T075 preflight producer provenance changed")
    source_audit = _read_json(root, T075_SOURCE_REUSE_AUDIT)
    validate_t075_source_reuse_audit(source_audit)
    if (
        source_audit["run_head"] != T077_INHERITED_T075_RUN_HEAD
        or source_audit["sources"] != [identity.to_dict() for identity in sources]
        or source_audit["strict_reader_passed"] is not True
        or source_audit["metadata_passed"] is not True
    ):
        raise ValueError("T075 SOURCE_REUSE control evidence changed")
    ownership = _read_json(root, T075_OWNERSHIP_AUDIT)
    validate_t075_ownership_audit(ownership)
    if ownership["run_head"] != T077_INHERITED_T075_RUN_HEAD:
        raise ValueError("T075 ownership audit producer provenance changed")

    verify_artifact_identity(root, T075_SELECTED_STATES)
    selected_summary = validate_selected_states_320(
        artifact_path(root, T075_SELECTED_STATES)
    )
    terminal = _read_json(root, T075_TERMINAL_REPORT)
    validate_t075_terminal_decision(
        terminal,
        expected_stage_outcomes=(
            T075_PREFLIGHT_OUTCOME,
            T075_SOURCE_REUSE_OUTCOME,
            T075_SELECTION_OUTCOME,
            T075_TARGET_OUTCOME,
        ),
    )
    if (
        terminal["run_head"] != T077_INHERITED_T075_RUN_HEAD
        or terminal["terminal_case"] != "D"
        or terminal["terminal_stage"] != "TARGET"
        or terminal["promotion"] != "no_promotion"
        or terminal["recommendation_code"] != "repair_same_experiment"
    ):
        raise ValueError("T075 immutable terminal decision changed")
    return {
        "sources": [identity.to_dict() for identity in sources],
        "retention_manifest": T075_RETENTION_MANIFEST.to_dict(),
        "source_reuse_outcome": T075_SOURCE_REUSE_OUTCOME.to_dict(),
        "selection_replay_outcome": T075_SELECTION_OUTCOME.to_dict(),
        "ownership_audit": T075_OWNERSHIP_AUDIT.to_dict(),
        "selected_states": T075_SELECTED_STATES.to_dict(),
        "immutable_target_outcome": T075_TARGET_OUTCOME.to_dict(),
        "immutable_terminal_report": T075_TERMINAL_REPORT.to_dict(),
        "selected_summary": selected_summary,
        "source_reuse_reused_not_rerun": True,
        "selection_replay_reused_not_rerun": True,
    }


@dataclass(frozen=True, slots=True)
class T077ContinuationPlan:
    """Frozen binding for one T077 TARGET-start run."""

    run_head: str
    accepted_t076_integration: str
    earliest_stage: str
    retained_t075_sources: tuple[ArtifactIdentity, ...]
    retained_t075_selection: ArtifactIdentity = T075_SELECTED_STATES


def build_t077_continuation_plan(
    run_head: str,
    *,
    retained_t075_sources: Sequence[
        ArtifactIdentity | Mapping[str, Any]
    ] = T075_SOURCE_IDENTITIES,
) -> T077ContinuationPlan:
    """Bind one new run to exact inherited inputs and repaired integration."""

    _git_commit(run_head, "T077 run_head")
    retained = _artifact_identities(retained_t075_sources)
    if retained != _artifact_identities(T075_SOURCE_IDENTITIES):
        raise ValueError("T077 retained T075 source identities are not exact")
    return T077ContinuationPlan(
        run_head=run_head,
        accepted_t076_integration=T077_ACCEPTED_T076_INTEGRATION,
        earliest_stage=T077_EARLIEST_STAGE,
        retained_t075_sources=retained,
    )


def artifact_identity(path: Path, repository_root: Path, role: str) -> ArtifactIdentity:
    relative = path.resolve().relative_to(Path(repository_root).resolve())
    return ArtifactIdentity(
        role=role,
        path=relative.as_posix(),
        sha256=file_sha256(path),
        size_bytes=path.stat().st_size,
    )


def write_canonical_json(
    path: Path, value: Mapping[str, Any], *, repository_root: Path, role: str
) -> ArtifactIdentity:
    """Atomically write one small T077 control record and return its identity."""

    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(canonical_json_document(value))
    temporary.replace(path)
    return artifact_identity(path, repository_root, role)
