"""T087 dense Combat diagnostics and bounded rescue/audit workflow.

This module owns only repository-side evidence handling.  Native restore,
Search-v2, battle transitions, and HP transforms remain delegated to the
accepted T085/T078 simulator seams.  The public functions deliberately accept
plain mappings so that formal jobs can stream current-schema artifacts without
coupling the diagnostic formulas to a simulator wrapper.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections import Counter
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from statistics import mean

from sts_combat_rl.commands.t085_native_execution import (
    T085NativeExecutionError,
    T085NativeTerminalSearchAdapter,
    T085UnguidedBattleSearchV2Controller,
    _validate_t085_native_source_manifest,
    restore_t085_canonical_record,
)
from sts_combat_rl.sim.action_space import ActionSpaceConfig
from sts_combat_rl.sim.battle_start_pool import BattleStartCheckpointRecord
from sts_combat_rl.sim.controlled_run import ControlledRun, execute_controlled_run
from sts_combat_rl.t085_corrected_leaf_value_search_evaluation import (
    T085_NATIVE_IDENTITY,
    T085BattleStartRecord,
    validate_t085_evaluation_selection_evidence,
)

T087_TASK_ID = "T087"
T087_APPROVED_SPEC = "81509bd426c9d0980e9a60ad28e9abb0ee0444e4"
T087_BASE_COMMIT = "b38c0584e4aac9172f9da4426004bfb64a13a41d"
T085_NATIVE_COMMIT = "d62ff35579b54d70a7428afdf84743c94df3fe0c"
T087_NATIVE_COMMIT = "96052d24b9c2c16ff25b6f7241edd972613be997"
T087_NATIVE_IDENTITY = {
    "repository": "lsmfttb/sts_lightspeed",
    "ref": "refs/heads/stsrl/main",
    "commit": T087_NATIVE_COMMIT,
}
T085_SCIENTIFIC_HEAD = "5edaa255959d34d4d31bbfae7e6b6bed9758024d"
T085_SELECTION_SHA256 = "d5c335cd6e1f96e72ae3b302eebca17a5f6531fa0aac97ee2febec2c41c2e752"
T085_RESTORE_SHA256 = "0adbdc4e055bd8d53680757a395e3e7973b7242b06db1c5053281ef883b679ef"
T052_COHORT_SHA256 = "b7f8e9b85b53bbf8e37adfe6cc90d0579937661309b26bce2a8f2921604a8608"
T085_B_SOURCE_MANIFEST_SHA256 = "11b7a55cc1bca52481699c6ebe10f16af2ad1cdf1765b565fdfdbfe5aad93e06"
T085_C_SOURCE_MANIFEST_SHA256 = "2a9986972764197d0c9b4927617c15a71221358364823d3f0f9687433face376"
T087_NATURAL_RECORD_COUNT = 413
T087_COHORT_COUNTS = {"A": 93, "B": 192, "C": 128}
T087_HP_SAMPLE_PER_COHORT = 8
T087_AUDIT_SAMPLE_PER_STRATUM = 8
T087_HP_DOMAIN = "T087-hp-rescue-v1\n"
T087_AUDIT_DOMAIN = "T087-human-audit-v1\n"
T087_AUDIT_NEAR_THRESHOLDS = (0.25, 0.35, 0.50, 0.65, 0.75, 1.00)
T087_AUDIT_DEEP_THRESHOLDS = (0.75, 0.65, 0.50, 0.35, 0.25, 0.00)
T087_TERMINAL_CLASSES = frozenset({"PLAYER_VICTORY", "PLAYER_LOSS"})
T087_POTION_ACTION_KINDS = frozenset(
    {"potion", "potion_discard", "game_potion_use", "game_potion_discard"}
)
T085_SELECTION_SCHEMA_ID = "t085-native-selection-artifact-v1"
T085_RESTORE_SCHEMA_ID = "t085-native-selection-restore-evidence-v1"
T085_CANONICAL_SOURCE_SCHEMA_IDS = {
    "A": "fixed-cohort-v3-jsonl",
    "B": "assisted-run-source-pool-v1",
    "C": "natural-battle-start-pool-v4-jsonl",
}
T085_SOURCE_MANIFEST_SCHEMA_ID = "t085-source-generation-manifest-v1"
T087_SEARCH_API = "StepSimulator.battle_search_v2.v1"
T087_ACTION_SPACE = ActionSpaceConfig.initial_no_potions().to_dict()
T087_REQUIRED_ARTIFACT_ROLES = frozenset(
    {
        "natural_evidence",
        "dense_diagnostic_table",
        "hp_rescue_selection",
        "hp_rescue_ladder",
        "blind_audit_selection",
        "blind_audit_bundle",
        "blind_audit_hidden_provenance",
        "human_review_rubric",
    }
)
_T087_VERIFIED_GATE_TOKEN = object()


class T087IncompleteError(ValueError):
    """A frozen T087 boundary cannot be satisfied from the retained evidence."""


@dataclass(frozen=True)
class T087T085InputGate:
    """Explicit, hash-bound T085 inputs admitted to T087 natural execution."""

    cohorts: Mapping[str, tuple[T085BattleStartRecord, ...]]
    canonical_records_by_cohort: Mapping[str, Mapping[str, object]]
    artifact_references: Mapping[str, Mapping[str, object]]
    source_selection_manifest_identity: Mapping[str, object]
    canonical_artifact_references: Mapping[str, Mapping[str, object]]
    source_manifest_artifact_references: Mapping[str, Mapping[str, object]] = field(
        default_factory=dict
    )
    _validation_token: object | None = field(
        default=None, init=False, repr=False, compare=False
    )


def _verified_gate(
    *,
    cohorts: Mapping[str, tuple[T085BattleStartRecord, ...]],
    canonical_records_by_cohort: Mapping[str, Mapping[str, object]],
    artifact_references: Mapping[str, Mapping[str, object]],
    source_selection_manifest_identity: Mapping[str, object],
    canonical_artifact_references: Mapping[str, Mapping[str, object]],
    source_manifest_artifact_references: Mapping[str, Mapping[str, object]],
) -> T087T085InputGate:
    gate = T087T085InputGate(
        cohorts=cohorts,
        canonical_records_by_cohort=canonical_records_by_cohort,
        artifact_references=artifact_references,
        source_selection_manifest_identity=source_selection_manifest_identity,
        canonical_artifact_references=canonical_artifact_references,
        source_manifest_artifact_references=source_manifest_artifact_references,
    )
    object.__setattr__(gate, "_validation_token", _T087_VERIFIED_GATE_TOKEN)
    return gate


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _read_hash_bound_json(
    path: str | Path,
    *,
    expected_sha256: str,
    schema_id: str,
    label: str,
) -> tuple[dict[str, object], dict[str, object]]:
    resolved = Path(path).resolve()
    if not resolved.is_file():
        raise T087IncompleteError(f"{label} path is not an explicit readable file")
    actual = _sha256_file(resolved)
    if actual != expected_sha256:
        raise T087IncompleteError(f"{label} SHA-256 does not match pinned identity")
    try:
        value = json.loads(resolved.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise T087IncompleteError(f"{label} is not readable current JSON") from exc
    if not isinstance(value, Mapping) or value.get("schema_id") != schema_id:
        raise T087IncompleteError(f"{label} schema is not current")
    reference = {
        "path": str(resolved),
        "sha256": actual,
        "schema_id": schema_id,
        "byte_count": resolved.stat().st_size,
    }
    return dict(value), reference


def _ref_path_equal(left: object, right: object) -> bool:
    if not isinstance(left, str) or not isinstance(right, str):
        return False
    try:
        return Path(left).resolve() == Path(right).resolve()
    except OSError:
        return left == right


def _verify_artifact_reference(reference: Mapping[str, object], label: str) -> None:
    """Verify a supplied T085 source reference instead of trusting its filename."""

    path = reference.get("path")
    expected_sha = reference.get("sha256")
    byte_count = reference.get("byte_count")
    if (
        not isinstance(path, str)
        or not isinstance(expected_sha, str)
        or len(expected_sha) != 64
        or any(character not in "0123456789abcdef" for character in expected_sha)
        or isinstance(byte_count, bool)
        or not isinstance(byte_count, int)
    ):
        raise T087IncompleteError(f"{label} reference is malformed")
    resolved = Path(path).resolve()
    if not resolved.is_file() or resolved.stat().st_size != byte_count:
        raise T087IncompleteError(f"{label} reference is unavailable or size-mismatched")
    if _sha256_file(resolved) != expected_sha:
        raise T087IncompleteError(f"{label} reference SHA-256 is substituted")


def _validate_gate_reference_shape(value: object, label: str) -> Mapping[str, object]:
    """Validate the exact file-identity shape before any mapping access."""

    if not isinstance(value, Mapping):
        raise T087IncompleteError(f"{label} reference is malformed")
    if set(value) != {"path", "sha256", "schema_id", "byte_count"}:
        raise T087IncompleteError(f"{label} reference has an unexpected shape")
    _verify_artifact_reference(value, label)
    if not isinstance(value.get("schema_id"), str) or not value["schema_id"]:
        raise T087IncompleteError(f"{label} reference schema is missing")
    return value


def _record_field(record: object, name: str) -> object:
    if isinstance(record, Mapping):
        return record.get(name)
    return getattr(record, name, None)


def _selected_battle_index(record: T085BattleStartRecord) -> int:
    prefix = f"{record.source_run_identity}:"
    if not record.battle_identity.startswith(prefix):
        raise T087IncompleteError("T085 battle identity is not source-run qualified")
    try:
        index = int(record.battle_identity.removeprefix(prefix))
    except ValueError as exc:
        raise T087IncompleteError("T085 battle identity index is invalid") from exc
    if index < 0:
        raise T087IncompleteError("T085 battle identity index is negative")
    return index


def _validate_canonical_binding(
    *,
    cohort: str,
    selected: Sequence[T085BattleStartRecord],
    canonical: Mapping[str, object],
    restore_rows: Mapping[str, Mapping[str, object]],
) -> None:
    selected_by_id = {record.selection_identity: record for record in selected}
    if len(selected_by_id) != len(selected):
        raise T087IncompleteError(f"canonical {cohort} selection contains duplicate identities")
    if set(canonical) != set(selected_by_id):
        raise T087IncompleteError(
            f"canonical {cohort} map does not cover exactly the pinned selected identities"
        )
    if set(restore_rows) != set(selected_by_id):
        raise T087IncompleteError(
            f"restore evidence {cohort} does not cover exactly the pinned identities"
        )
    for identity, record in selected_by_id.items():
        full = canonical[identity]
        source_checkpoint_id = _record_field(full, "source_checkpoint_id")
        source_run_id = _record_field(full, "source_run_id")
        source_seed = _record_field(full, "source_seed")
        source_battle_index = _record_field(full, "source_battle_index")
        structural = _record_field(full, "structural_metadata")
        if (
            source_checkpoint_id != identity
            or source_run_id != record.source_run_identity
            or source_seed != record.source_run_seed
            or source_battle_index != _selected_battle_index(record)
            or not isinstance(structural, Mapping)
            or structural.get("act") != record.act
            or str(structural.get("room_type", "")).upper() != record.room_type
        ):
            raise T087IncompleteError(
                f"canonical {cohort} record is substituted or identity-mismatched: {identity}"
            )
        restore = restore_rows[identity]
        if (
            restore.get("selection_identity") != identity
            or restore.get("complete_source_identity") != record.complete_source_identity
            or restore.get("battle_identity") != record.battle_identity
            or restore.get("source_run_identity") != record.source_run_identity
            or restore.get("source_run_seed") != record.source_run_seed
            or restore.get("act") != record.act
            or str(restore.get("room_type", "")).upper() != record.room_type
            or restore.get("restore_ok") is not True
            or restore.get("public_context_match") is not True
        ):
            raise T087IncompleteError(
                f"restore evidence is not bound to canonical record {identity}"
            )


def _validate_canonical_record_map(
    value: object, label: str
) -> Mapping[str, BattleStartCheckpointRecord]:
    """Admit only the full restore-record objects consumed by T085 helpers."""

    if not isinstance(value, Mapping):
        raise T087IncompleteError(f"{label} map is malformed")
    if any(not isinstance(identity, str) or not identity for identity in value):
        raise T087IncompleteError(f"{label} map has malformed identities")
    if any(
        not isinstance(record, BattleStartCheckpointRecord)
        for record in value.values()
    ):
        raise T087IncompleteError(f"{label} map contains an incomplete restore record")
    return value


def _reference_identity(value: object, label: str) -> dict[str, object]:
    """Project an embedded artifact reference to its authenticated identity."""

    if not isinstance(value, Mapping):
        raise T087IncompleteError(f"{label} reference is malformed")
    required = {"path", "sha256", "schema_id", "byte_count"}
    if not required.issubset(value):
        raise T087IncompleteError(f"{label} reference is incomplete")
    projected = {key: value[key] for key in required}
    _validate_gate_reference_shape(projected, label)
    return projected


def _same_reference(left: object, right: object) -> bool:
    if not isinstance(left, Mapping) or not isinstance(right, Mapping):
        return False
    return (
        left.get("sha256") == right.get("sha256")
        and left.get("schema_id") == right.get("schema_id")
        and left.get("byte_count") == right.get("byte_count")
        and _ref_path_equal(left.get("path"), right.get("path"))
    )


def _validate_t085_selection_document(
    selection_document: Mapping[str, object],
) -> dict[str, tuple[T085BattleStartRecord, ...]]:
    """Validate the complete four-key retained T085 selection matrix."""

    if (
        selection_document.get("schema_id") != T085_SELECTION_SCHEMA_ID
        or selection_document.get("task_id") != "T085"
    ):
        raise T087IncompleteError("T085 selection artifact schema/task identity is wrong")
    native = selection_document.get("native_identity")
    if not isinstance(native, Mapping) or dict(native) != dict(T085_NATIVE_IDENTITY):
        raise T087IncompleteError("T085 selection native identity is not historical")
    raw_cohorts = selection_document.get("cohorts")
    raw_evidence = selection_document.get("selection_evidence")
    if not isinstance(raw_cohorts, Mapping) or not isinstance(raw_evidence, Mapping):
        raise T087IncompleteError("T085 selection artifact lacks current cohorts/evidence")
    if set(raw_cohorts) != {"A", "B", "C", "B@400"}:
        raise T087IncompleteError("T085 selection cohort matrix is incomplete")
    try:
        cohorts = {
            str(cohort): tuple(
                T085BattleStartRecord.from_mapping(item)
                for item in records
            )
            for cohort, records in raw_cohorts.items()
            if isinstance(records, Sequence) and not isinstance(records, (str, bytes))
        }
    except (AttributeError, KeyError, TypeError, ValueError) as exc:
        raise T087IncompleteError("T085 selection cohort rows are malformed") from exc
    if set(cohorts) != {"A", "B", "C", "B@400"}:
        raise T087IncompleteError("T085 selection cohort rows are malformed")
    try:
        validate_t085_evaluation_selection_evidence(cohorts, raw_evidence)
    except (TypeError, ValueError) as exc:
        raise T087IncompleteError("T085 selection evidence failed its accepted gate") from exc
    expected_counts = {**T087_COHORT_COUNTS, "B@400": 48}
    if any(len(cohorts[name]) != count for name, count in expected_counts.items()):
        raise T087IncompleteError("T085 four-key selection counts are not exact")
    primary_ids = [
        record.selection_identity
        for cohort in ("A", "B", "C")
        for record in cohorts[cohort]
    ]
    if len(set(primary_ids)) != T087_NATURAL_RECORD_COUNT:
        raise T087IncompleteError(
            "T085 A/B/C selection identities are not globally occurrence-safe"
        )
    return cohorts


def _validate_t085_restore_document(
    restore_document: Mapping[str, object],
    *,
    selection_document: Mapping[str, object],
    selected_cohorts: Mapping[str, Sequence[T085BattleStartRecord]],
    selection_reference: Mapping[str, object],
) -> tuple[dict[str, dict[str, Mapping[str, object]]], dict[str, dict[str, object]], dict[str, dict[str, object]]]:
    """Validate restore evidence and derive its canonical source chain."""

    if (
        restore_document.get("schema_id") != T085_RESTORE_SCHEMA_ID
        or restore_document.get("task_id") != "T085"
        or not isinstance(restore_document.get("native_identity"), Mapping)
        or dict(restore_document["native_identity"]) != dict(T085_NATIVE_IDENTITY)
    ):
        raise T087IncompleteError("T085 restore artifact schema/task/native identity is wrong")
    if not (
        restore_document.get("complete") is True
        and restore_document.get("partial") is False
        and restore_document.get("restore_parity_passed") is True
        and restore_document.get("outcome_blind_selection") is True
        and restore_document.get("search_invoked") is False
    ):
        raise T087IncompleteError("T085 restore evidence is not a complete outcome-blind gate")
    restore_selection = _reference_identity(
        restore_document.get("selection_artifact"),
        "T085 restore selection artifact",
    )
    if not _same_reference(restore_selection, selection_reference):
        raise T087IncompleteError("T085 restore evidence points to a different selection artifact")
    raw_restore_rows = restore_document.get("restore_evidence")
    if not isinstance(raw_restore_rows, Sequence) or isinstance(raw_restore_rows, (str, bytes)):
        raise T087IncompleteError("T085 restore evidence rows are unavailable")
    if len(raw_restore_rows) != T087_NATURAL_RECORD_COUNT:
        raise T087IncompleteError("T085 restore evidence does not contain exactly 413 rows")
    restore_by_cohort: dict[str, dict[str, Mapping[str, object]]] = {
        "A": {},
        "B": {},
        "C": {},
    }
    for raw in raw_restore_rows:
        if not isinstance(raw, Mapping) or raw.get("cohort") not in restore_by_cohort:
            raise T087IncompleteError("T085 restore evidence row is malformed")
        identity = raw.get("selection_identity")
        cohort = str(raw["cohort"])
        if not isinstance(identity, str) or not identity or identity in restore_by_cohort[cohort]:
            raise T087IncompleteError("T085 restore evidence contains duplicate identity")
        restore_by_cohort[cohort][identity] = dict(raw)

    for cohort in ("A", "B", "C"):
        selected_ids = {
            record.selection_identity
            for record in selected_cohorts.get(cohort, ())
        }
        if (
            len(restore_by_cohort[cohort]) != T087_COHORT_COUNTS[cohort]
            or set(restore_by_cohort[cohort]) != selected_ids
        ):
            raise T087IncompleteError(
                f"T085 restore evidence does not cover the exact selected {cohort} identities"
            )

    selection_evidence = selection_document.get("selection_evidence")
    source_bindings = restore_document.get("source_bindings")
    if not isinstance(selected_cohorts, Mapping) or not isinstance(selection_evidence, Mapping):
        raise T087IncompleteError("T085 selection source evidence is unavailable")
    if not isinstance(source_bindings, Mapping) or set(source_bindings) != {"A", "B", "C"}:
        raise T087IncompleteError("T085 restore canonical source bindings are incomplete")

    canonical_refs: dict[str, dict[str, object]] = {}
    source_manifest_refs: dict[str, dict[str, object]] = {}
    for cohort in ("A", "B", "C"):
        binding = source_bindings.get(cohort)
        if not isinstance(binding, Mapping):
            raise T087IncompleteError(f"T085 restore source binding {cohort} is malformed")
        expected_keys = {"map"} if cohort == "A" else {"map", "source_manifest"}
        if set(binding) != expected_keys:
            raise T087IncompleteError(f"T085 restore source binding {cohort} is incomplete")
        map_reference = _reference_identity(
            binding.get("map"), f"T085 canonical {cohort} source"
        )
        if map_reference.get("schema_id") != T085_CANONICAL_SOURCE_SCHEMA_IDS[cohort]:
            raise T087IncompleteError(f"T085 canonical {cohort} source schema is not current")
        if cohort == "A":
            evidence = selection_evidence.get("A")
            if not isinstance(evidence, Mapping):
                raise T087IncompleteError("T085 selection evidence A is missing")
            a_reference = _reference_identity(
                evidence.get("artifact"), "T085 selection evidence A artifact"
            )
            if not _same_reference(map_reference, a_reference) or map_reference.get(
                "sha256"
            ) != T052_COHORT_SHA256:
                raise T087IncompleteError("T085 canonical A source is not the accepted T052 artifact")
        else:
            evidence = selection_evidence.get(cohort)
            if not isinstance(evidence, Mapping):
                raise T087IncompleteError(f"T085 selection evidence {cohort} is missing")
            manifest_reference = _reference_identity(
                binding.get("source_manifest"),
                f"T085 canonical {cohort} source manifest",
            )
            evidence_manifest = _reference_identity(
                evidence.get("source_manifest"),
                f"T085 selection evidence {cohort} source manifest",
            )
            expected_manifest_sha = (
                T085_B_SOURCE_MANIFEST_SHA256
                if cohort == "B"
                else T085_C_SOURCE_MANIFEST_SHA256
            )
            if (
                not _same_reference(manifest_reference, evidence_manifest)
                or manifest_reference.get("sha256") != expected_manifest_sha
                or manifest_reference.get("schema_id") != T085_SOURCE_MANIFEST_SCHEMA_ID
            ):
                raise T087IncompleteError(
                    f"T085 canonical {cohort} source manifest is substituted"
                )
            source_manifest_refs[cohort] = manifest_reference
        _validate_gate_reference_shape(map_reference, f"T085 canonical {cohort} source")
        canonical_refs[cohort] = map_reference
    return restore_by_cohort, canonical_refs, source_manifest_refs


def _validate_t085_document_chain(
    *,
    selection_document: Mapping[str, object],
    restore_document: Mapping[str, object],
    artifact_references: Mapping[str, Mapping[str, object]],
) -> tuple[
    dict[str, tuple[T085BattleStartRecord, ...]],
    dict[str, dict[str, Mapping[str, object]]],
    dict[str, dict[str, object]],
    dict[str, dict[str, object]],
    dict[str, object],
]:
    """Validate the minimum direct selection/restore/source dependency chain."""

    if not isinstance(artifact_references, Mapping) or set(artifact_references) != {
        "selection",
        "restore",
    }:
        raise T087IncompleteError("T085 input artifact references must be selection and restore only")
    selection_reference = _validate_gate_reference_shape(
        artifact_references.get("selection"), "T085 selection artifact"
    )
    restore_reference = _validate_gate_reference_shape(
        artifact_references.get("restore"), "T085 restore evidence"
    )
    if (
        selection_reference.get("sha256") != T085_SELECTION_SHA256
        or selection_reference.get("schema_id") != T085_SELECTION_SCHEMA_ID
        or restore_reference.get("sha256") != T085_RESTORE_SHA256
        or restore_reference.get("schema_id") != T085_RESTORE_SCHEMA_ID
    ):
        raise T087IncompleteError("T085 selection/restore artifact reference is not pinned")
    cohorts = _validate_t085_selection_document(selection_document)
    restore_by_cohort, canonical_refs, source_manifest_refs = _validate_t085_restore_document(
        restore_document,
        selection_document=selection_document,
        selected_cohorts=cohorts,
        selection_reference=selection_reference,
    )
    return (
        cohorts,
        restore_by_cohort,
        canonical_refs,
        source_manifest_refs,
        dict(selection_reference),
    )


def validate_t087_t085_input_documents(
    *,
    selection_document: Mapping[str, object],
    restore_document: Mapping[str, object],
    artifact_references: Mapping[str, Mapping[str, object]],
    canonical_records_by_cohort: Mapping[str, Mapping[str, object]],
    canonical_artifact_references: Mapping[str, Mapping[str, object]],
) -> T087T085InputGate:
    """Validate loaded T085 documents and exact canonical record bindings."""

    if not isinstance(selection_document, Mapping) or not isinstance(restore_document, Mapping):
        raise T087IncompleteError("T085 input documents are malformed")
    if not isinstance(canonical_records_by_cohort, Mapping) or set(
        canonical_records_by_cohort
    ) != {"A", "B", "C"}:
        raise T087IncompleteError("T085 canonical record maps are incomplete")
    if not isinstance(canonical_artifact_references, Mapping) or set(
        canonical_artifact_references
    ) != {"A", "B", "C"}:
        raise T087IncompleteError("T085 canonical artifact references are incomplete")
    (
        cohorts,
        restore_by_cohort,
        bound_canonical_refs,
        source_manifest_refs,
        selection_reference,
    ) = (
        _validate_t085_document_chain(
            selection_document=selection_document,
            restore_document=restore_document,
            artifact_references=artifact_references,
        )
    )
    for cohort in ("A", "B", "C"):
        canonical = canonical_records_by_cohort.get(cohort)
        if canonical is None:
            raise T087IncompleteError(f"canonical {cohort} restore map is not supplied")
        canonical = _validate_canonical_record_map(
            canonical, f"T085 canonical {cohort}"
        )
        _validate_canonical_binding(
            cohort=cohort,
            selected=cohorts[cohort],
            canonical=canonical,
            restore_rows=restore_by_cohort[cohort],
        )
        expected_ref = _validate_gate_reference_shape(
            canonical_artifact_references.get(cohort),
            f"T085 canonical {cohort} artifact",
        )
        if not _same_reference(expected_ref, bound_canonical_refs[cohort]):
            raise T087IncompleteError(f"T085 canonical {cohort} artifact was substituted")
    return _verified_gate(
        cohorts=cohorts,
        canonical_records_by_cohort=canonical_records_by_cohort,
        artifact_references=artifact_references,
        source_selection_manifest_identity=selection_reference,
        canonical_artifact_references=canonical_artifact_references,
        source_manifest_artifact_references=source_manifest_refs,
    )


def load_t087_t085_input_gate(
    *,
    selection_artifact_path: str | Path,
    restore_evidence_path: str | Path,
    canonical_records_by_cohort: Mapping[str, Mapping[str, object]],
    canonical_artifact_references: Mapping[str, Mapping[str, object]],
) -> T087T085InputGate:
    """Load and hash-check explicit T085 artifacts before natural execution."""

    selection, selection_ref = _read_hash_bound_json(
        selection_artifact_path,
        expected_sha256=T085_SELECTION_SHA256,
        schema_id=T085_SELECTION_SCHEMA_ID,
        label="T085 selection artifact",
    )
    restore, restore_ref = _read_hash_bound_json(
        restore_evidence_path,
        expected_sha256=T085_RESTORE_SHA256,
        schema_id=T085_RESTORE_SCHEMA_ID,
        label="T085 restore evidence",
    )
    return validate_t087_t085_input_documents(
        selection_document=selection,
        restore_document=restore,
        artifact_references={
            "selection": selection_ref,
            "restore": restore_ref,
        },
        canonical_records_by_cohort=canonical_records_by_cohort,
        canonical_artifact_references=canonical_artifact_references,
    )


def _revalidate_t085_gate(gate: T087T085InputGate) -> T087T085InputGate:
    """Re-open the pinned T085 files at each execution boundary.

    The private token prevents public dataclass construction from becoming an
    admission path.  Re-opening the hash-bound documents and every canonical
    source reference also detects a changed retained file or stale gate before
    a simulator call.
    """

    try:
        if (
            not isinstance(gate, T087T085InputGate)
            or gate._validation_token is not _T087_VERIFIED_GATE_TOKEN
        ):
            raise T087IncompleteError(
                "T085 input gate was not created by the verified loader"
            )
        refs = gate.artifact_references
        if not isinstance(refs, Mapping) or set(refs) != {"selection", "restore"}:
            raise T087IncompleteError(
                "T085 input gate artifact reference set is incomplete"
            )
        expected_documents = {
            "selection": (T085_SELECTION_SHA256, T085_SELECTION_SCHEMA_ID),
            "restore": (T085_RESTORE_SHA256, T085_RESTORE_SCHEMA_ID),
        }
        live_documents: dict[str, dict[str, object]] = {}
        live_refs: dict[str, dict[str, object]] = {}
        for role, (expected_sha256, schema_id) in expected_documents.items():
            reference = _validate_gate_reference_shape(refs.get(role), f"T085 {role} artifact")
            if (
                reference.get("sha256") != expected_sha256
                or reference.get("schema_id") != schema_id
            ):
                raise T087IncompleteError(f"T085 {role} artifact reference is substituted")
            document, live_reference = _read_hash_bound_json(
                reference["path"],
                expected_sha256=expected_sha256,
                schema_id=schema_id,
                label=f"T085 {role} artifact",
            )
            live_documents[role] = document
            live_refs[role] = live_reference
        if dict(refs) != live_refs:
            raise T087IncompleteError(
                "T085 input gate artifact references are stale or substituted"
            )

        raw_cohorts = gate.cohorts
        if not isinstance(raw_cohorts, Mapping) or set(raw_cohorts) != {
            "A",
            "B",
            "C",
            "B@400",
        }:
            raise T087IncompleteError("T085 input gate cohorts are malformed")
        for cohort, records in raw_cohorts.items():
            if not isinstance(records, Sequence) or isinstance(records, (str, bytes)):
                raise T087IncompleteError(f"T085 input gate cohort {cohort} is malformed")
            if any(not isinstance(record, T085BattleStartRecord) for record in records):
                raise T087IncompleteError(
                    f"T085 input gate cohort {cohort} contains an unbound record"
                )
        canonical_maps = gate.canonical_records_by_cohort
        if not isinstance(canonical_maps, Mapping) or set(canonical_maps) != {
            "A",
            "B",
            "C",
        }:
            raise T087IncompleteError("T085 canonical record maps are malformed")
        for cohort, records in canonical_maps.items():
            _validate_canonical_record_map(records, f"T085 canonical {cohort}")
        canonical_refs = gate.canonical_artifact_references
        if not isinstance(canonical_refs, Mapping) or set(canonical_refs) != {
            "A",
            "B",
            "C",
        }:
            raise T087IncompleteError("T085 canonical artifact reference set is incomplete")
        for cohort, reference in canonical_refs.items():
            _validate_gate_reference_shape(reference, f"T085 canonical {cohort} artifact")
        source_manifest_refs = gate.source_manifest_artifact_references
        if not isinstance(source_manifest_refs, Mapping) or set(source_manifest_refs) != {
            "B",
            "C",
        }:
            raise T087IncompleteError("T085 source-manifest artifact reference set is incomplete")
        for cohort, reference in source_manifest_refs.items():
            _validate_gate_reference_shape(
                reference, f"T085 canonical {cohort} source manifest"
            )
        source_identity = gate.source_selection_manifest_identity
        source_reference = _validate_gate_reference_shape(
            source_identity, "T085 selection-manifest identity"
        )
        if (
            dict(source_reference) != live_refs["selection"]
            or source_reference.get("sha256") != T085_SELECTION_SHA256
            or source_reference.get("schema_id") != T085_SELECTION_SCHEMA_ID
        ):
            raise T087IncompleteError(
                "T085 input gate source selection-manifest identity is substituted"
            )
        live = validate_t087_t085_input_documents(
            selection_document=live_documents["selection"],
            restore_document=live_documents["restore"],
            artifact_references=live_refs,
            canonical_records_by_cohort=canonical_maps,
            canonical_artifact_references=canonical_refs,
        )
        if (
            live.cohorts != gate.cohorts
            or live.canonical_records_by_cohort != gate.canonical_records_by_cohort
            or dict(live.artifact_references) != dict(gate.artifact_references)
            or dict(live.canonical_artifact_references)
            != dict(gate.canonical_artifact_references)
            or dict(live.source_manifest_artifact_references)
            != dict(gate.source_manifest_artifact_references)
            or dict(live.source_selection_manifest_identity) != dict(source_reference)
        ):
            raise T087IncompleteError(
                "T085 input gate contents differ from live pinned artifacts"
            )
        return live
    except T087IncompleteError:
        raise
    except (AttributeError, IndexError, KeyError, OSError, TypeError, ValueError) as exc:
        raise T087IncompleteError("T085 verified gate is malformed") from exc


def load_t087_t085_selection_binding(
    path: str | Path,
) -> tuple[dict[str, tuple[str, ...]], dict[str, object]]:
    """Load the pinned T085 selection identity order for report finalization."""

    document, reference = _read_hash_bound_json(
        path,
        expected_sha256=T085_SELECTION_SHA256,
        schema_id=T085_SELECTION_SCHEMA_ID,
        label="T085 selection artifact",
    )
    cohorts = _validate_t085_selection_document(document)
    return (
        {cohort: tuple(record.selection_identity for record in records) for cohort, records in cohorts.items()},
        reference,
    )


def load_t087_t085_report_binding(
    *,
    selection_artifact_path: str | Path,
    restore_evidence_path: str | Path,
) -> tuple[dict[str, tuple[str, ...]], dict[str, dict[str, object]]]:
    """Verify the direct T085 selection/restore/canonical source chain."""

    selection, selection_ref = _read_hash_bound_json(
        selection_artifact_path,
        expected_sha256=T085_SELECTION_SHA256,
        schema_id=T085_SELECTION_SCHEMA_ID,
        label="T085 selection artifact",
    )
    restore, restore_ref = _read_hash_bound_json(
        restore_evidence_path,
        expected_sha256=T085_RESTORE_SHA256,
        schema_id=T085_RESTORE_SCHEMA_ID,
        label="T085 restore evidence",
    )
    cohorts, _restore_rows, canonical_refs, source_manifest_refs, selection_identity = (
        _validate_t085_document_chain(
            selection_document=selection,
            restore_document=restore,
            artifact_references={"selection": selection_ref, "restore": restore_ref},
        )
    )
    return (
        {
            cohort: tuple(record.selection_identity for record in records)
            for cohort, records in cohorts.items()
        },
        {
            "selection": selection_identity,
            "restore": dict(restore_ref),
            "canonical": canonical_refs,
            "source_manifests": source_manifest_refs,
        },
    )


def canonical_json_bytes(value: object) -> bytes:
    """Return exactly the amendment's digest-bearing JSON serialization."""

    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def selection_identity_bytes(selection_identity: str) -> bytes:
    """Return the exact occurrence-safe T085 identity byte representation."""

    if not isinstance(selection_identity, str) or not selection_identity:
        raise T087IncompleteError("selection_identity must be a non-empty string")
    return selection_identity.encode("utf-8")


def selection_digest(selection_identity: str, *, domain: str) -> str:
    """Hash an identity using a T087 domain prefix and no other representation."""

    if domain not in {"hp", "human_audit"}:
        raise ValueError("T087 selection digest domain is unsupported")
    prefix = T087_HP_DOMAIN if domain == "hp" else T087_AUDIT_DOMAIN
    return hashlib.sha256(
        prefix.encode("ascii") + selection_identity_bytes(selection_identity)
    ).hexdigest()


def _finite(value: object, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise T087IncompleteError(f"{label} must be numeric")
    result = float(value)
    if not math.isfinite(result):
        raise T087IncompleteError(f"{label} must be finite")
    return result


def _positive(value: object, label: str) -> float:
    result = _finite(value, label)
    if result <= 0:
        raise T087IncompleteError(f"{label} must be positive")
    return result


def _enemy_rows(
    value: object, label: str, *, require_terminal_fields: bool = False
) -> list[dict[str, object]]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise T087IncompleteError(f"{label} must be an ordered enemy sequence")
    result: list[dict[str, object]] = []
    for index, raw in enumerate(value):
        if not isinstance(raw, Mapping):
            raise T087IncompleteError(f"{label}[{index}] is not an object")
        identity = next(
            (
                raw[key].strip()
                for key in ("id_label", "identity", "monster_id", "name", "id")
                if isinstance(raw.get(key), str) and raw[key].strip()
            ),
            None,
        )
        if not isinstance(identity, str) or not identity:
            raise T087IncompleteError(f"{label}[{index}] lacks enemy identity")
        hp = _finite(raw.get("current_hp"), f"{label}[{index}].current_hp")
        if hp < 0:
            raise T087IncompleteError(f"{label}[{index}].current_hp is negative")
        max_hp = raw.get("max_hp")
        if require_terminal_fields:
            max_hp_value = _positive(max_hp, f"{label}[{index}].max_hp")
            for field_name in ("alive", "targetable", "half_dead"):
                if not isinstance(raw.get(field_name), bool):
                    raise T087IncompleteError(
                        f"{label}[{index}].{field_name} is not boolean"
                    )
            if raw["targetable"] and not raw["alive"]:
                raise T087IncompleteError(
                    f"{label}[{index}].targetable requires alive=true"
                )
        elif max_hp is None:
            max_hp_value = None
        else:
            max_hp_value = _positive(max_hp, f"{label}[{index}].max_hp")
        item = dict(raw)
        item["identity"] = identity
        item["current_hp"] = hp
        if max_hp_value is not None:
            item["max_hp"] = max_hp_value
        result.append(item)
    return result


def _explicit_enemy_occurrence_metadata(
    raw: Mapping[str, object],
    enemies: Sequence[Mapping[str, object]],
    label: str,
    *,
    count_key: str,
    alive_key: str | None = None,
    require_alive: bool = False,
    count_targetable: bool = False,
) -> tuple[int, tuple[str, ...]]:
    """Require an explicit occurrence-completeness witness from the adapter.

    The accepted native occurrence count, ordered monster list, and active
    count must come from the same snapshot surface.  The count is
    required for both entry and terminal snapshots; an uncounted sequence or
    an entry without the native alive-count witness is never enough.
    """

    count = raw.get(count_key)
    if isinstance(count, bool) or not isinstance(count, int) or count != len(enemies):
        raise T087IncompleteError(f"{label} enemy occurrence count is absent or inconsistent")
    normalized = tuple(item.get("identity") for item in enemies)
    if len(normalized) != count or any(not isinstance(identity, str) for identity in normalized):
        raise T087IncompleteError(f"{label} native monster identities are incomplete")
    indices = tuple(item.get("monster_index") for item in enemies)
    if any(index is not None for index in indices) and indices != tuple(range(count)):
        raise T087IncompleteError(f"{label} native monster occurrence order is inconsistent")
    if alive_key is not None:
        alive_value = raw.get(alive_key)
        if (
            (
                isinstance(alive_value, bool)
                or not isinstance(alive_value, int)
                or alive_value
                != sum(
                    bool(enemy.get("targetable"))
                    if count_targetable
                    else _alive(enemy)
                    for enemy in enemies
                )
            )
            and (require_alive or alive_value is not None)
        ):
            raise T087IncompleteError(f"{label} native active count is absent or inconsistent")
    return count, normalized


def _player_value(raw: Mapping[str, object], key: str) -> object:
    if key in raw:
        return raw[key]
    for container in ("player", "battle_player", "persistent_resources"):
        nested = raw.get(container)
        if isinstance(nested, Mapping) and key in nested:
            return nested[key]
    aliases = {
        "current_hp": ("cur_hp", "battle_player_hp"),
        "max_hp": ("player_max_hp",),
    }
    for alias in aliases.get(key, ()):
        if alias in raw:
            return raw[alias]
    return None


def battle_snapshot_evidence(
    raw: Mapping[str, object], *, require_positive_enemy_hp: bool = True
) -> dict[str, object]:
    """Normalize accepted raw snapshot fields without inventing missing state."""

    if not isinstance(raw, Mapping):
        raise T087IncompleteError("battle snapshot is not an accepted mapping")
    completed_keys = {
        "completed_battle_monsters",
        "completed_battle_monster_count",
        "completed_battle_monsters_alive",
    }
    is_terminal = "completed_battle_outcome" in raw or completed_keys.intersection(raw)
    if is_terminal:
        if not completed_keys.issubset(raw):
            raise T087IncompleteError(
                "accepted terminal snapshot lacks complete post-action monster telemetry"
            )
        monster_key = "completed_battle_monsters"
        count_key = "completed_battle_monster_count"
        alive_key = "completed_battle_monsters_alive"
        label = "completed terminal snapshot"
        require_alive = True
    else:
        monster_key = "battle_monsters" if "battle_monsters" in raw else "monsters"
        count_key = "battle_monster_count"
        alive_key = "battle_monsters_alive"
        label = "battle snapshot"
        require_alive = True
    monsters = raw.get(monster_key)
    enemies = _enemy_rows(
        monsters,
        f"{label} enemies",
        require_terminal_fields=is_terminal,
    )
    current_hp = _finite(_player_value(raw, "current_hp"), "player current_hp")
    max_hp = _positive(_player_value(raw, "max_hp"), "player max_hp")
    total = sum(float(enemy["current_hp"]) for enemy in enemies)
    if not math.isfinite(total) or (
        require_positive_enemy_hp and total <= 0
    ):
        raise T087IncompleteError("battle_start_total_enemy_hp must be positive")
    occurrence_count, occurrence_identities = _explicit_enemy_occurrence_metadata(
        raw,
        enemies,
        label,
        count_key=count_key,
        alive_key=alive_key,
        require_alive=require_alive,
        count_targetable=is_terminal,
    )
    return {
        "player_current_hp": current_hp,
        "player_max_hp": max_hp,
        "enemies": enemies,
        "battle_start_total_enemy_hp": total,
        "enemy_occurrences_complete": True,
        "enemy_occurrence_count": occurrence_count,
        "enemy_occurrence_identities": occurrence_identities,
        "visible_terminal_resources": dict(
            raw.get("completed_battle_resource_outcome", {})
        )
        if isinstance(raw.get("completed_battle_resource_outcome"), Mapping)
        else {},
        "raw_snapshot": dict(raw),
    }


def _terminal_outcome_from_raw(raw: Mapping[str, object]) -> str:
    """Read the accepted native terminal outcome keys without choosing silently."""

    if not isinstance(raw, Mapping):
        raise T087IncompleteError("terminal raw snapshot is not an accepted mapping")
    values: list[str] = []
    for key in ("completed_battle_outcome", "battle_outcome", "outcome"):
        if key in raw:
            value = raw[key]
            # After exitBattle the native GameContext snapshot may retain the
            # non-terminal game outcome label UNDECIDED.  It is not a battle
            # outcome witness; only terminal-class values participate.
            if value == "UNDECIDED" and key == "outcome":
                continue
            if not isinstance(value, str) or value not in T087_TERMINAL_CLASSES:
                raise T087IncompleteError(f"terminal raw outcome {key} is invalid")
            values.append(value)
    if not values:
        raise T087IncompleteError("terminal raw outcome is missing")
    if len(set(values)) != 1:
        raise T087IncompleteError("terminal raw outcome keys conflict")
    return values[0]


def _validate_terminal_raw_matches_evidence(
    terminal: Mapping[str, object], raw_terminal: Mapping[str, object]
) -> None:
    """Require normalized terminal fields to be a lossless raw projection."""

    raw_evidence = battle_snapshot_evidence(
        raw_terminal, require_positive_enemy_hp=False
    )
    for key in ("player_current_hp", "player_max_hp"):
        if terminal.get(key) != raw_evidence[key]:
            raise T087IncompleteError(
                f"terminal {key} disagrees with retained raw terminal snapshot"
            )
    terminal_enemies = _enemy_rows(
        terminal.get("enemies"),
        "terminal.enemies",
        require_terminal_fields=True,
    )
    raw_enemies = raw_evidence["enemies"]
    if not isinstance(raw_enemies, Sequence) or len(terminal_enemies) != len(raw_enemies):
        raise T087IncompleteError(
            "terminal enemies disagree with retained raw terminal snapshot"
        )
    terminal_pairs = tuple(
        (
            enemy["identity"],
            enemy["current_hp"],
            enemy["max_hp"],
            enemy["alive"],
            enemy["targetable"],
            enemy["half_dead"],
        )
        for enemy in terminal_enemies
    )
    raw_pairs = tuple(
        (
            enemy["identity"],
            enemy["current_hp"],
            enemy["max_hp"],
            enemy["alive"],
            enemy["targetable"],
            enemy["half_dead"],
        )
        for enemy in raw_enemies
        if isinstance(enemy, Mapping)
    )
    if terminal_pairs != raw_pairs:
        raise T087IncompleteError(
            "terminal enemy HP/alive/targetable/half-dead status/occurrence order "
            "disagrees with retained raw terminal snapshot"
        )
    if (
        terminal.get("enemy_occurrences_complete") is not True
        or terminal.get("enemy_occurrence_count") != raw_evidence["enemy_occurrence_count"]
        or tuple(terminal.get("enemy_occurrence_identities") or ())
        != tuple(raw_evidence["enemy_occurrence_identities"])
    ):
        raise T087IncompleteError(
            "terminal occurrence metadata disagrees with retained raw terminal snapshot"
        )


def _validate_entry_raw_matches_evidence(
    entry: Mapping[str, object], raw_entry: Mapping[str, object]
) -> dict[str, object]:
    """Require normalized Battle-start fields to be a lossless raw projection."""

    completed_keys = {
        "completed_battle_outcome",
        "completed_battle_monster_count",
        "completed_battle_monsters_alive",
        "completed_battle_monsters",
    }
    if completed_keys.intersection(raw_entry):
        raise T087IncompleteError(
            "retained raw entry snapshot unexpectedly contains terminal telemetry"
        )
    raw_evidence = battle_snapshot_evidence(raw_entry)
    for key in ("player_current_hp", "player_max_hp"):
        if entry.get(key) != raw_evidence[key]:
            raise T087IncompleteError(
                f"entry {key} disagrees with retained raw entry snapshot"
            )
    entry_enemies = _enemy_rows(entry.get("enemies"), "entry.enemies")
    raw_enemies = raw_evidence["enemies"]
    if not isinstance(raw_enemies, Sequence):
        raise T087IncompleteError("retained raw entry enemies are unavailable")
    entry_pairs = tuple(
        (enemy["identity"], enemy["current_hp"], _alive(enemy))
        for enemy in entry_enemies
    )
    raw_pairs = tuple(
        (enemy["identity"], enemy["current_hp"], _alive(enemy))
        for enemy in raw_enemies
        if isinstance(enemy, Mapping)
    )
    if entry_pairs != raw_pairs:
        raise T087IncompleteError(
            "entry enemy HP/alive status/occurrence order disagrees with retained raw entry snapshot"
        )
    if (
        entry.get("battle_start_total_enemy_hp")
        != raw_evidence["battle_start_total_enemy_hp"]
        or entry.get("enemy_occurrences_complete") is not True
        or entry.get("enemy_occurrence_count")
        != raw_evidence["enemy_occurrence_count"]
        or tuple(entry.get("enemy_occurrence_identities") or ())
        != tuple(raw_evidence["enemy_occurrence_identities"])
    ):
        raise T087IncompleteError(
            "entry occurrence/HP totals disagree with retained raw entry snapshot"
        )
    return raw_evidence


def _alive(enemy: Mapping[str, object]) -> bool:
    if isinstance(enemy.get("alive"), bool):
        return enemy["alive"]
    if enemy.get("is_gone") is True or enemy.get("dead") is True:
        return False
    return float(enemy["current_hp"]) > 0.0


def _action_potion_count(action_trace: Sequence[Mapping[str, object]]) -> int:
    count = 0
    for action in action_trace:
        if not isinstance(action, Mapping):
            raise T087IncompleteError("action trace contains a non-object step")
        kind = action.get("chosen_action_kind", action.get("kind"))
        if isinstance(kind, str) and kind in T087_POTION_ACTION_KINDS:
            count += 1
    return count


def build_dense_diagnostic_row(
    *,
    selection_identity: str,
    cohort: str,
    entry: Mapping[str, object],
    terminal: Mapping[str, object],
    outcome: str,
    action_trace: Sequence[Mapping[str, object]] = (),
    provenance: Mapping[str, object] | None = None,
    source_selection_manifest_identity: Mapping[str, object] | None = None,
) -> dict[str, object]:
    """Build one recomputable T087 dense row from raw entry/terminal evidence."""

    if not isinstance(entry, Mapping) or not isinstance(terminal, Mapping):
        raise T087IncompleteError("entry and terminal evidence must be mappings")
    if cohort not in T087_COHORT_COUNTS:
        raise T087IncompleteError(f"unknown T087 cohort {cohort!r}")
    if outcome not in T087_TERMINAL_CLASSES:
        raise T087IncompleteError("outcome is not authoritative PLAYER_VICTORY/LOSS")
    raw_terminal = terminal.get("raw_snapshot")
    if not isinstance(raw_terminal, Mapping):
        raise T087IncompleteError("retained raw terminal snapshot is missing")
    raw_entry = entry.get("raw_snapshot")
    if not isinstance(raw_entry, Mapping):
        raise T087IncompleteError("retained raw entry snapshot is missing")
    if _terminal_outcome_from_raw(raw_terminal) != outcome:
        raise T087IncompleteError("row outcome disagrees with retained raw terminal outcome")
    if not {
        "completed_battle_monsters",
        "completed_battle_monster_count",
        "completed_battle_monsters_alive",
    }.issubset(raw_terminal):
        raise T087IncompleteError(
            "retained raw terminal lacks complete post-action monster telemetry"
        )
    _validate_terminal_raw_matches_evidence(terminal, raw_terminal)
    entry_evidence = _validate_entry_raw_matches_evidence(entry, raw_entry)
    identity = selection_identity_bytes(selection_identity)
    del identity  # Validate the exact string before retaining it.
    start_enemies = [
        dict(enemy)
        for enemy in entry_evidence["enemies"]
        if isinstance(enemy, Mapping)
    ]
    terminal_enemies = _enemy_rows(
        terminal.get("enemies"),
        "terminal.enemies",
        require_terminal_fields=True,
    )
    if terminal.get("enemy_occurrences_complete") is not True:
        raise T087IncompleteError("terminal enemy occurrence completeness is unavailable")
    start_total = _positive(
        entry_evidence["battle_start_total_enemy_hp"], "battle_start_total_enemy_hp"
    )
    terminal_total = sum(float(enemy["current_hp"]) for enemy in terminal_enemies)
    if not math.isfinite(terminal_total) or terminal_total < 0:
        raise T087IncompleteError("terminal enemy HP total is invalid")
    initial_count = len(start_enemies)
    terminal_occurrence_count = terminal.get("enemy_occurrence_count")
    terminal_occurrence_identities = terminal.get("enemy_occurrence_identities")
    if (
        terminal_occurrence_count != initial_count
        or tuple(terminal_occurrence_identities or ())
        != tuple(enemy["identity"] for enemy in start_enemies)
    ):
        raise T087IncompleteError(
            "terminal enemy occurrence metadata does not cover the entry occurrences"
        )
    active_terminal = sum(bool(enemy["targetable"]) for enemy in terminal_enemies)
    hp_alive_terminal = sum(bool(enemy["alive"]) for enemy in terminal_enemies)
    non_targetable_hp_alive_terminal = sum(
        bool(enemy["alive"]) and not bool(enemy["targetable"])
        for enemy in terminal_enemies
    )
    if initial_count <= 0:
        raise T087IncompleteError("enemy_count_initial must be positive")
    active_enemy_hp = sum(
        float(enemy["current_hp"])
        for enemy in terminal_enemies
        if bool(enemy["targetable"])
    )
    if not math.isfinite(active_enemy_hp) or active_enemy_hp < 0:
        raise T087IncompleteError("active terminal enemy HP total is invalid")

    start_player_hp = _finite(entry.get("player_current_hp"), "entry.player_current_hp")
    start_max_hp = _positive(entry.get("player_max_hp"), "entry.player_max_hp")
    terminal_player_hp = _finite(
        terminal.get("player_current_hp"), "terminal.player_current_hp"
    )
    remaining_fraction = active_enemy_hp / start_total
    progress_fraction = 1.0 - remaining_fraction
    player_fraction = terminal_player_hp / start_max_hp
    margin = player_fraction if outcome == "PLAYER_VICTORY" else -remaining_fraction
    for label, value in (
        ("enemy_hp_remaining_fraction", remaining_fraction),
        ("enemy_hp_progress_fraction_v1", progress_fraction),
        ("player_hp_remaining_fraction_of_max", player_fraction),
        ("combat_terminal_margin_v1", margin),
    ):
        if not math.isfinite(value):
            raise T087IncompleteError(f"{label} is not finite")
    if remaining_fraction < 0.0:
        raise T087IncompleteError("enemy_hp_remaining_fraction is negative")
    if outcome == "PLAYER_VICTORY" and margin < 0.0:
        raise T087IncompleteError("victory margin is negative")
    if outcome == "PLAYER_LOSS" and margin > 0.0:
        raise T087IncompleteError("loss margin is positive")

    if not isinstance(action_trace, Sequence) or isinstance(
        action_trace, (str, bytes)
    ):
        raise T087IncompleteError("action trace must be an ordered sequence")
    trace: list[dict[str, object]] = []
    for index, item in enumerate(action_trace):
        if not isinstance(item, Mapping):
            raise T087IncompleteError(f"action trace step {index} is not an object")
        trace.append(dict(item))
    if provenance is not None and not isinstance(provenance, Mapping):
        raise T087IncompleteError("execution provenance must be a mapping")
    return {
        "schema_id": "t087-dense-combat-diagnostic-row-v1",
        "task_id": T087_TASK_ID,
        "selection_identity": selection_identity,
        "cohort": cohort,
        "outcome": outcome,
        "entry": dict(entry),
        "terminal": dict(terminal),
        "raw_entry": dict(raw_entry),
        "raw_terminal": dict(raw_terminal),
        "action_trace": trace,
        "diagnostics": {
            "enemy_count_initial": initial_count,
            "enemy_occurrence_count_terminal": terminal_occurrence_count,
            "enemy_count_active_terminal": active_terminal,
            "enemy_count_hp_alive_terminal": hp_alive_terminal,
            "enemy_count_non_targetable_hp_alive_terminal": (
                non_targetable_hp_alive_terminal
            ),
            "battle_start_total_enemy_hp": start_total,
            "terminal_total_enemy_hp_all_occurrences": terminal_total,
            "terminal_total_enemy_hp_active": active_enemy_hp,
            "enemy_hp_remaining_fraction": remaining_fraction,
            "enemy_hp_progress_fraction_v1": progress_fraction,
            "player_hp_remaining_fraction_of_max": player_fraction,
            "net_player_hp_delta": terminal_player_hp - start_player_hp,
            "combat_terminal_margin_v1": margin,
        },
        "action_count": len(trace),
        "potion_action_count": _action_potion_count(trace),
        "provenance": dict(provenance or {}),
        "source_selection_manifest_identity": (
            dict(source_selection_manifest_identity)
            if source_selection_manifest_identity is not None
            else None
        ),
    }


def _row_identity(row: Mapping[str, object]) -> str:
    identity = row.get("selection_identity", row.get("record_identity"))
    if not isinstance(identity, str) or not identity:
        raise T087IncompleteError("diagnostic row lacks selection_identity")
    return identity


def _source_selection_manifest_identity(row: Mapping[str, object]) -> dict[str, object]:
    value = row.get("source_selection_manifest_identity")
    if not isinstance(value, Mapping):
        raise T087IncompleteError(
            f"{_row_identity(row)} lacks inherited T085 selection-manifest identity"
        )
    required = {"path", "sha256", "schema_id", "byte_count"}
    if set(value) != required:
        raise T087IncompleteError(
            f"{_row_identity(row)} has malformed T085 selection-manifest identity"
        )
    if (
        not isinstance(value["path"], str)
        or value["sha256"] != T085_SELECTION_SHA256
        or value["schema_id"] != T085_SELECTION_SCHEMA_ID
        or isinstance(value["byte_count"], bool)
        or not isinstance(value["byte_count"], int)
        or value["byte_count"] < 0
    ):
        raise T087IncompleteError(
            f"{_row_identity(row)} has mismatched T085 selection-manifest identity"
        )
    return dict(value)


def _validate_unique_rows(rows: Iterable[Mapping[str, object]]) -> tuple[dict[str, object], ...]:
    raw_rows = tuple(rows)
    if any(not isinstance(row, Mapping) for row in raw_rows):
        raise T087IncompleteError("T087 diagnostic rows are malformed")
    normalized = tuple(dict(row) for row in raw_rows)
    identities = [_row_identity(row) for row in normalized]
    if len(set(identities)) != len(identities):
        raise T087IncompleteError("duplicate selection_identity in T087 ranking domain")
    return normalized


def validate_dense_diagnostic_row(row: Mapping[str, object]) -> None:
    """Recompute a retained row and fail closed on any scalar drift."""

    identity = _row_identity(row)
    source_manifest_identity = _source_selection_manifest_identity(row)
    if row.get("schema_id") != "t087-dense-combat-diagnostic-row-v1" or row.get("task_id") != T087_TASK_ID:
        raise T087IncompleteError(f"{identity}: diagnostic row schema/task identity is not current")
    if row.get("cohort") not in T087_COHORT_COUNTS:
        raise T087IncompleteError(f"{identity}: diagnostic row cohort is invalid")
    entry = row.get("entry")
    terminal = row.get("terminal")
    outcome = row.get("outcome")
    if not isinstance(entry, Mapping) or not isinstance(terminal, Mapping):
        raise T087IncompleteError(f"{identity}: raw entry/terminal evidence is missing")
    if not isinstance(outcome, str):
        raise T087IncompleteError(f"{identity}: authoritative outcome is missing")
    raw_terminal = terminal.get("raw_snapshot")
    if not isinstance(raw_terminal, Mapping):
        raise T087IncompleteError(f"{identity}: retained raw terminal snapshot is missing")
    raw_entry = entry.get("raw_snapshot")
    if not isinstance(raw_entry, Mapping):
        raise T087IncompleteError(f"{identity}: retained raw entry snapshot is missing")
    if (
        not isinstance(row.get("raw_entry"), Mapping)
        or dict(row["raw_entry"]) != dict(raw_entry)
        or not isinstance(row.get("raw_terminal"), Mapping)
        or dict(row["raw_terminal"]) != dict(raw_terminal)
    ):
        raise T087IncompleteError(
            f"{identity}: retained raw entry/terminal surfaces are inconsistent"
        )
    if _terminal_outcome_from_raw(raw_terminal) != outcome:
        raise T087IncompleteError(f"{identity}: row outcome disagrees with retained raw terminal outcome")
    action_trace = row.get("action_trace")
    if not isinstance(action_trace, Sequence) or isinstance(action_trace, (str, bytes)):
        raise T087IncompleteError(f"{identity}: action trace is malformed")
    rebuilt = build_dense_diagnostic_row(
        selection_identity=identity,
        cohort=str(row.get("cohort", "")),
        entry=entry,
        terminal=terminal,
        outcome=outcome,
        action_trace=action_trace,
        provenance=row.get("provenance")  # type: ignore[arg-type]
        if isinstance(row.get("provenance"), Mapping)
        else None,
    )
    expected = rebuilt["diagnostics"]
    observed = row.get("diagnostics")
    if not isinstance(observed, Mapping) or dict(observed) != dict(expected):
        raise T087IncompleteError(f"{identity}: diagnostics do not recompute from raw evidence")
    if row.get("action_count") != len(action_trace):
        raise T087IncompleteError(f"{identity}: action_count does not recompute from action_trace")
    if row.get("potion_action_count") != _action_potion_count(action_trace):
        raise T087IncompleteError(
            f"{identity}: potion_action_count does not recompute from action_trace"
        )
    provenance = row.get("provenance")
    if not isinstance(provenance, Mapping):
        raise T087IncompleteError(f"{identity}: execution provenance is missing")
    if provenance.get("source_selection_manifest_identity") != source_manifest_identity:
        raise T087IncompleteError(f"{identity}: source selection-manifest provenance is mismatched")
    for key, expected_value in (
        ("task_id", T087_TASK_ID),
        ("native_commit", T087_NATIVE_COMMIT),
        ("search_api", T087_SEARCH_API),
        ("search_budget", 100),
        ("root_selection_rule", "highest_mean"),
        ("seed", None),
        ("max_steps", 200),
        ("policy_prior_callback", False),
        ("learned_leaf_value_callback", False),
        ("no_additional_search_seed", True),
    ):
        if provenance.get(key) != expected_value:
            raise T087IncompleteError(f"{identity}: provenance {key} is not frozen")
    if provenance.get("restore_source_identity") != identity:
        raise T087IncompleteError(f"{identity}: restore/source identity is missing")
    if not isinstance(provenance.get("restore_method"), str) or not provenance["restore_method"]:
        raise T087IncompleteError(f"{identity}: restore method provenance is missing")
    if provenance.get("action_space") != T087_ACTION_SPACE:
        raise T087IncompleteError(f"{identity}: action-space provenance is not initial_no_potions")


def _manifest_payload(
    *, domain: str, selections: Sequence[Mapping[str, object]]
) -> dict[str, object]:
    payload = {
        "schema_id": "t087-selection-manifest-v1",
        "task_id": T087_TASK_ID,
        "selection_domain": domain,
        "selected": [dict(selection) for selection in selections],
    }
    digest = hashlib.sha256(canonical_json_bytes(payload)).hexdigest()
    return {**payload, "canonical_sha256": digest}


def select_hp_rescue_losses(
    rows: Iterable[Mapping[str, object]],
) -> dict[str, object]:
    """Select exactly eight natural losses from each A/B/C cohort."""

    normalized = _validate_unique_rows(rows)
    source_manifest_identities = {
        json.dumps(_source_selection_manifest_identity(row), sort_keys=True)
        for row in normalized
    }
    if len(source_manifest_identities) != 1:
        raise T087IncompleteError(
            "T087 HP rescue ranking lacks one inherited T085 selection-manifest identity"
        )
    selected: list[dict[str, object]] = []
    for cohort in ("A", "B", "C"):
        eligible = [
            row
            for row in normalized
            if row.get("cohort") == cohort and row.get("outcome") == "PLAYER_LOSS"
        ]
        if len(eligible) < T087_HP_SAMPLE_PER_COHORT:
            raise T087IncompleteError(f"cohort {cohort} has fewer than eight losses")
        ranked = sorted(
            eligible,
            key=lambda row: (
                selection_digest(_row_identity(row), domain="hp"),
                selection_identity_bytes(_row_identity(row)),
            ),
        )
        source_manifest_identity = _source_selection_manifest_identity(normalized[0])
        for rank, row in enumerate(ranked[:T087_HP_SAMPLE_PER_COHORT]):
            identity = _row_identity(row)
            selected.append(
                {
                    "selection_role": "hp_rescue_loss",
                    "cohort": cohort,
                    "selected_rank": rank,
                    "selection_identity": identity,
                    "selection_digest": selection_digest(identity, domain="hp"),
                    "source_selection_manifest_identity": dict(source_manifest_identity),
                }
            )
    return _manifest_payload(domain="hp_rescue", selections=selected)


def _rank_audit(rows: Sequence[Mapping[str, object]]) -> list[Mapping[str, object]]:
    return sorted(
        rows,
        key=lambda row: (
            selection_digest(_row_identity(row), domain="human_audit"),
            selection_identity_bytes(_row_identity(row)),
        ),
    )


def select_blind_audit_rows(rows: Iterable[Mapping[str, object]]) -> dict[str, object]:
    """Freeze the exact 8/8/8 blind-audit identities before trace inspection."""

    normalized = _validate_unique_rows(rows)
    wins = [row for row in normalized if row.get("outcome") == "PLAYER_VICTORY"]
    losses = [row for row in normalized if row.get("outcome") == "PLAYER_LOSS"]
    if len(wins) < 8:
        raise T087IncompleteError("fewer than eight natural victories for blind audit")
    selected: list[dict[str, object]] = []
    source_manifest_identities = {
        json.dumps(_source_selection_manifest_identity(row), sort_keys=True)
        for row in normalized
    }
    if len(source_manifest_identities) != 1:
        raise T087IncompleteError("blind audit rows lack one inherited T085 selection-manifest identity")
    source_manifest_identity = _source_selection_manifest_identity(normalized[0])
    for rank, row in enumerate(_rank_audit(wins)[:8]):
        identity = _row_identity(row)
        selected.append(
            {
                "selection_role": "human_audit_win",
                "audit_stratum": "wins",
                "selected_rank": rank,
                "selection_identity": identity,
                "selection_digest": selection_digest(identity, domain="human_audit"),
                "threshold": None,
                "source_selection_manifest_identity": dict(source_manifest_identity),
            }
        )
    near: list[Mapping[str, object]] = []
    near_threshold = None
    for threshold in T087_AUDIT_NEAR_THRESHOLDS:
        candidate = [
            row
            for row in losses
            if _diagnostic(row, "enemy_hp_remaining_fraction") <= threshold
        ]
        if len(candidate) >= 8:
            near = candidate
            near_threshold = threshold
            break
    if near_threshold is None:
        raise T087IncompleteError("no near-boundary loss threshold supplies eight rows")
    near_ids = {_row_identity(row) for row in _rank_audit(near)[:8]}
    for rank, row in enumerate(_rank_audit(near)[:8]):
        identity = _row_identity(row)
        selected.append(
            {
                "selection_role": "human_audit_near_loss",
                "audit_stratum": "near_boundary_losses",
                "selected_rank": rank,
                "selection_identity": identity,
                "selection_digest": selection_digest(identity, domain="human_audit"),
                "threshold": near_threshold,
                "source_selection_manifest_identity": dict(source_manifest_identity),
            }
        )
    deep: list[Mapping[str, object]] = []
    deep_threshold = None
    for threshold in T087_AUDIT_DEEP_THRESHOLDS:
        candidate = [
            row
            for row in losses
            if _row_identity(row) not in near_ids
            and _diagnostic(row, "enemy_hp_remaining_fraction") >= threshold
        ]
        if len(candidate) >= 8:
            deep = candidate
            deep_threshold = threshold
            break
    if deep_threshold is None:
        raise T087IncompleteError("no deep-loss threshold supplies eight rows")
    for rank, row in enumerate(_rank_audit(deep)[:8]):
        identity = _row_identity(row)
        selected.append(
            {
                "selection_role": "human_audit_deep_loss",
                "audit_stratum": "deep_losses",
                "selected_rank": rank,
                "selection_identity": identity,
                "selection_digest": selection_digest(identity, domain="human_audit"),
                "threshold": deep_threshold,
                "source_selection_manifest_identity": dict(source_manifest_identity),
            }
        )
    if len({_row_identity(row) for row in selected}) != 24:
        raise T087IncompleteError("blind audit groups are not pairwise disjoint")
    return _manifest_payload(domain="human_audit", selections=selected)


def _diagnostic(row: Mapping[str, object], name: str) -> float:
    diagnostics = row.get("diagnostics")
    value = diagnostics.get(name) if isinstance(diagnostics, Mapping) else row.get(name)
    return _finite(value, f"row diagnostics.{name}")


def hp_rescue_ladder(player_start_hp: object, player_max_hp: object) -> tuple[int, ...]:
    """Return the exact unique sorted bounded HP-addition ladder."""

    start = _finite(player_start_hp, "player_start_hp")
    maximum = _finite(player_max_hp, "player_max_hp")
    if start < 0 or maximum < start:
        raise T087IncompleteError("invalid HP bounds for rescue ladder")
    if not start.is_integer() or not maximum.is_integer():
        raise T087IncompleteError("HP start and maximum must be integral")
    gap_value = maximum - start
    if not gap_value.is_integer():
        raise T087IncompleteError("HP gap must be integral")
    gap = int(gap_value)
    return tuple(sorted({0, min(5, gap), min(10, gap), min(20, gap), gap}))


def build_review_rubric() -> dict[str, object]:
    return {
        "schema_id": "t087-human-review-rubric-v1",
        "task_id": T087_TASK_ID,
        "fields": [
            {"name": "start_winnability", "values": ["clearly_winnable", "difficult_but_winnable", "likely_doomed", "uncertain"]},
            {"name": "combat_execution_quality", "values": ["major_tactical_error", "minor_tactical_error", "no_obvious_major_error", "uncertain"]},
            {"name": "dominant_failure_source", "values": ["combat_execution", "precombat_state", "mixed", "uncertain"]},
            {"name": "earliest_decisive_step_or_turn", "optional": True, "type": "string"},
            {"name": "confidence", "type": "integer", "minimum": 1, "maximum": 5},
            {"name": "notes", "optional": True, "type": "string"},
        ],
        "human_labels_are_algorithmically_unused": True,
    }


def _public_state(raw: object) -> dict[str, object]:
    """Project a trace snapshot to fields a player can observe in battle."""

    if not isinstance(raw, Mapping):
        return {}
    allowed = {
        "screen_state",
        "act",
        "floor",
        "floor_num",
        "room_type",
        "encounter_id",
        "current_hp",
        "max_hp",
        "battle_player_hp",
        "player_max_hp",
        "energy",
        "block",
        "gold",
    }
    state = {key: raw[key] for key in allowed if key in raw}
    monsters = raw.get("battle_monsters", raw.get("monsters"))
    if isinstance(monsters, Sequence) and not isinstance(monsters, (str, bytes)):
        public_monsters = []
        for monster in monsters:
            if not isinstance(monster, Mapping):
                continue
            public_monsters.append(
                {
                    key: monster[key]
                    for key in ("id", "name", "current_hp", "intent", "is_gone")
                    if key in monster
                }
            )
        state["battle_monsters"] = public_monsters
    return state


def build_blind_trace_bundle(
    *,
    selected_manifest: Mapping[str, object],
    rows: Iterable[Mapping[str, object]],
) -> tuple[dict[str, object], dict[str, object]]:
    """Build a public trace bundle and a separate hidden identity/provenance map."""

    row_by_identity = {_row_identity(row): row for row in rows}
    public_traces: list[dict[str, object]] = []
    hidden_map: list[dict[str, object]] = []
    selected = selected_manifest.get("selected")
    if not isinstance(selected, Sequence) or isinstance(selected, (str, bytes)):
        raise T087IncompleteError("blind-audit manifest has no selected rows")
    for trace_id, selection in enumerate(selected):
        if not isinstance(selection, Mapping):
            raise T087IncompleteError("blind-audit manifest selection is malformed")
        identity = selection.get("selection_identity")
        if not isinstance(identity, str) or identity not in row_by_identity:
            raise T087IncompleteError("blind-audit trace identity is unavailable")
        row = row_by_identity[identity]
        raw_trace = row.get("action_trace", row.get("trace", []))
        if not isinstance(raw_trace, Sequence) or isinstance(raw_trace, (str, bytes)):
            raise T087IncompleteError(f"blind-audit trace {identity} is unavailable")
        steps: list[dict[str, object]] = []
        for raw_step in raw_trace:
            if not isinstance(raw_step, Mapping):
                raise T087IncompleteError(f"blind-audit trace {identity} has malformed step")
            public_state = raw_step.get("public_state", raw_step.get("tactical_state"))
            if not isinstance(public_state, Mapping):
                public_state = _public_state(raw_step.get("snapshot_raw"))
            steps.append(
                {
                    "step_index": raw_step.get("step_index"),
                    "chosen_action_kind": raw_step.get("chosen_action_kind", raw_step.get("kind")),
                    "chosen_action_identity": dict(raw_step.get("chosen_action_identity", {}))
                    if isinstance(raw_step.get("chosen_action_identity", {}), Mapping)
                    else {},
                    "public_state": dict(public_state),
                    "terminal_after_step": raw_step.get("terminal_after_step"),
                }
            )
        if not steps:
            raise T087IncompleteError(f"blind-audit trace {identity} has no steps")
        public_traces.append({"trace_id": trace_id, "steps": steps})
        hidden_map.append(
            {
                "trace_id": trace_id,
                "selection_identity": identity,
                "cohort": row.get("cohort"),
                "provenance": dict(row.get("provenance", {}))
                if isinstance(row.get("provenance"), Mapping)
                else {},
            }
        )
    return (
        {"schema_id": "t087-blind-audit-bundle-v1", "traces": public_traces},
        {
            "schema_id": "t087-blind-audit-hidden-provenance-v1",
            "trace_map": hidden_map,
        },
    )


def _trace_for_controlled_run(controlled: ControlledRun) -> list[dict[str, object]]:
    return [
        {
            "step_index": step.step_index,
            "chosen_action_kind": step.chosen_action_kind,
            "chosen_action_identity": dict(step.chosen_action_identity),
            "public_state": dict(step.tactical_state),
            "snapshot_raw": dict(step.snapshot_raw),
            "next_snapshot_raw": dict(step.next_snapshot_raw),
            "terminal_after_step": step.terminal_after_step,
        }
        for step in controlled.steps
    ]


def _terminal_raw(controlled: ControlledRun) -> Mapping[str, object]:
    if controlled.steps:
        candidate = controlled.steps[-1].next_snapshot_raw
        if candidate:
            return candidate
    return controlled.final_raw


def _validate_t087_current_native_identity() -> dict[str, object]:
    """Re-verify the current native source at every T087 execution boundary."""

    try:
        actual = _validate_t085_native_source_manifest(
            "battle_search_v2",
            expected_native_identity=T087_NATIVE_IDENTITY,
        )
    except (T085NativeExecutionError, OSError, RuntimeError, ValueError) as exc:
        raise T087IncompleteError(
            "T087 current-native lineage/source verification failed"
        ) from exc
    if actual != T087_NATIVE_IDENTITY:
        raise T087IncompleteError(
            "T087 current-native identity differs from the approved 960 identity"
        )
    return dict(actual)


def _validate_t087_evaluator_contract(
    *,
    adapter: object,
    controller: object,
    seed: object,
    max_steps: object,
    action_space: object,
) -> None:
    """Check the frozen Search-v2 evaluator after construction and before run."""

    if seed is not None or max_steps != 200:
        raise T087IncompleteError("T087 evaluator seed/max_steps contract drifted")
    if not isinstance(action_space, ActionSpaceConfig) or action_space.to_dict() != T087_ACTION_SPACE:
        raise T087IncompleteError("T087 evaluator action space drifted")
    adapter_values = (
        getattr(adapter, "_search_simulations", None),
        getattr(adapter, "_search_backend", None),
        getattr(adapter, "_policy_prior_callback", object()),
        getattr(adapter, "_leaf_value_callback", object()),
        getattr(adapter, "_expected_native_identity", None),
    )
    if adapter_values != (100, "battle_search_v2", None, None, T087_NATIVE_IDENTITY):
        raise T087IncompleteError("T087 native Search-v2 adapter contract drifted")
    if (
        getattr(controller, "simulations", None) != 100
        or not isinstance(getattr(controller, "action_space", None), ActionSpaceConfig)
        or controller.action_space.to_dict() != T087_ACTION_SPACE
    ):
        raise T087IncompleteError("T087 native Search-v2 controller contract drifted")
    provenance = getattr(controller, "provenance", None)
    provenance_values = provenance.to_dict() if hasattr(provenance, "to_dict") else None
    if not isinstance(provenance_values, Mapping):
        raise T087IncompleteError("T087 evaluator controller provenance is unavailable")
    config = provenance_values.get("config")
    if not isinstance(config, Mapping):
        raise T087IncompleteError("T087 evaluator controller provenance config is unavailable")
    if (
        config.get("search_budget") != 100
        or config.get("root_selection_rule") != "highest_mean"
        or config.get("policy_prior_callback") is not None
        or config.get("leaf_value_callback") is not None
        or config.get("native_identity") != T087_NATIVE_IDENTITY
    ):
        raise T087IncompleteError("T087 evaluator provenance contract drifted")


def _run_t087_native_record_verified(
    *,
    record: object,
    cohort: str,
    canonical_records: Mapping[str, object],
    adapter_factory: Callable[[], object],
    source_selection_manifest_identity: Mapping[str, object],
) -> dict[str, object]:
    """Evaluate one restored record through the accepted T085 boundary.

    The function is intentionally one-record granular so formal jobs can shard
    it externally.  It never supplies a simulator/controller/per-record seed.
    """

    _validate_t087_current_native_identity()
    try:
        restored_adapter = adapter_factory()
        restored, restore_method = restore_t085_canonical_record(
            restored_adapter, record, canonical_records
        )
        entry = battle_snapshot_evidence(restored.raw)
        adapter = T085NativeTerminalSearchAdapter(
            restored_adapter,
            search_simulations=100,
            search_backend="battle_search_v2",
            policy_prior_callback=None,
            leaf_value_callback=None,
            expected_native_identity=T087_NATIVE_IDENTITY,
        )
        adapter.prime_restored_snapshot(restored)
        controller = T085UnguidedBattleSearchV2Controller(
            simulations=100,
            expected_native_identity=T087_NATIVE_IDENTITY,
        )
        _validate_t087_evaluator_contract(
            adapter=adapter,
            controller=controller,
            seed=None,
            max_steps=200,
            action_space=ActionSpaceConfig.initial_no_potions(),
        )
        controlled = execute_controlled_run(
            adapter,
            controller,
            seed=None,
            max_steps=200,
            action_space=ActionSpaceConfig.initial_no_potions(),
        )
    except (T085NativeExecutionError, T087IncompleteError, RuntimeError, ValueError) as exc:
        raise T087IncompleteError(f"{_record_identity(record)}: {exc}") from exc
    if not controlled.terminal or controlled.problems:
        raise T087IncompleteError(
            f"{_record_identity(record)}: controlled Battle did not terminate: "
            + "; ".join(controlled.problems)
        )
    terminal = battle_snapshot_evidence(
        _terminal_raw(controlled), require_positive_enemy_hp=False
    )
    outcome = _terminal_outcome_from_raw(terminal["raw_snapshot"])
    identity = _record_identity(record)
    return build_dense_diagnostic_row(
        selection_identity=identity,
        cohort=cohort,
        entry=entry,
        terminal=terminal,
        outcome=outcome,
        action_trace=_trace_for_controlled_run(controlled),
        provenance={
            "task_id": T087_TASK_ID,
            "restore_method": restore_method,
            "native_commit": T087_NATIVE_COMMIT,
            "search_api": T087_SEARCH_API,
            "search_budget": 100,
            "root_selection_rule": "highest_mean",
            "policy_prior_callback": False,
            "learned_leaf_value_callback": False,
            "action_space": ActionSpaceConfig.initial_no_potions().to_dict(),
            "seed": None,
            "max_steps": 200,
            "no_additional_search_seed": True,
            "restore_source_identity": identity,
            "source_selection_manifest_identity": dict(source_selection_manifest_identity),
        },
        source_selection_manifest_identity=source_selection_manifest_identity,
    )


def _t085_record_signature(record: object) -> tuple[object, ...]:
    """Return the public T085 identity fields used for occurrence-safe binding."""

    if isinstance(record, T085BattleStartRecord):
        value = record
    elif isinstance(record, Mapping):
        try:
            value = T085BattleStartRecord.from_mapping(record)
        except (TypeError, ValueError) as exc:
            raise T087IncompleteError("caller T085 record is malformed") from exc
    else:
        raise T087IncompleteError("caller T085 record has no accepted public shape")
    return (
        value.selection_identity,
        value.source_run_seed,
        value.source_run_identity,
        value.complete_source_identity,
        value.battle_identity,
        value.act,
        value.room_type,
    )


def _assert_t085_execution_binding(
    *,
    gate: T087T085InputGate,
    record: object,
    cohort: str,
    canonical_records: Mapping[str, object],
    source_selection_manifest_identity: Mapping[str, object],
) -> None:
    """Bind one sharded execution call to the already-verified T085 gate."""

    if cohort not in {"A", "B", "C"}:
        raise T087IncompleteError(f"T087 execution cohort {cohort!r} is invalid")
    if not isinstance(record, T085BattleStartRecord):
        raise T087IncompleteError("T085 execution record is not a typed selected record")
    identity = _record_identity(record)
    gate_records = gate.cohorts.get(cohort)
    gate_canonical = gate.canonical_records_by_cohort.get(cohort)
    if (
        not isinstance(gate_records, Sequence)
        or isinstance(gate_records, (str, bytes))
        or not isinstance(gate_canonical, Mapping)
        or not isinstance(canonical_records, Mapping)
    ):
        raise T087IncompleteError(f"T085 execution binding for {cohort} is malformed")
    _validate_canonical_record_map(
        canonical_records, f"T085 execution canonical {cohort}"
    )
    matching = [
        candidate
        for candidate in gate_records
        if _record_identity(candidate) == identity
    ]
    if len(matching) != 1 or _t085_record_signature(record) != _t085_record_signature(matching[0]):
        raise T087IncompleteError(f"T085 execution record {identity} was substituted")
    if dict(canonical_records) != dict(gate_canonical):
        raise T087IncompleteError(f"T085 execution canonical map for {cohort} was substituted")
    if (
        not isinstance(source_selection_manifest_identity, Mapping)
        or dict(source_selection_manifest_identity)
        != dict(gate.source_selection_manifest_identity)
    ):
        raise T087IncompleteError(
            f"T085 execution source selection artifact for {identity} was substituted"
        )


def run_t087_native_record(
    *,
    record: object,
    cohort: str,
    canonical_records: Mapping[str, object],
    adapter_factory: Callable[[], object],
    source_selection_manifest_identity: Mapping[str, object],
    t085_input_gate: T087T085InputGate | None = None,
) -> dict[str, object]:
    """Run one record only after the hash-bound T085 gate is revalidated."""

    if t085_input_gate is None:
        raise T087IncompleteError("T085 hash-bound input gate is required before execution")
    verified_gate = _revalidate_t085_gate(t085_input_gate)
    _assert_t085_execution_binding(
        gate=verified_gate,
        record=record,
        cohort=cohort,
        canonical_records=canonical_records,
        source_selection_manifest_identity=source_selection_manifest_identity,
    )
    return _run_t087_native_record_verified(
        record=record,
        cohort=cohort,
        canonical_records=canonical_records,
        adapter_factory=adapter_factory,
        source_selection_manifest_identity=source_selection_manifest_identity,
    )


def run_t087_natural_evaluation(
    *,
    records_by_cohort: Mapping[str, Sequence[object]],
    canonical_records_by_cohort: Mapping[str, Mapping[str, object]],
    adapter_factory: Callable[[], object],
    t085_input_gate: T087T085InputGate | None = None,
) -> list[dict[str, object]]:
    """Evaluate the exact A/B/C selection without drop, replacement, or reselection."""

    verified_gate = _revalidate_t085_gate(t085_input_gate) if t085_input_gate is not None else None
    if verified_gate is None:
        raise T087IncompleteError("T085 hash-bound input gate is required before natural execution")
    _validate_t087_current_native_identity()
    if not isinstance(records_by_cohort, Mapping) or not isinstance(
        canonical_records_by_cohort, Mapping
    ):
        raise T087IncompleteError("T087 natural execution inputs are malformed")
    if set(records_by_cohort) != set(T087_COHORT_COUNTS):
        raise T087IncompleteError("T087 natural evaluation requires exactly A, B, and C")
    if set(verified_gate.cohorts) != {"A", "B", "C", "B@400"}:
        raise T087IncompleteError("T085 input gate cohort matrix is incomplete")
    rows: list[dict[str, object]] = []
    for cohort, expected_count in T087_COHORT_COUNTS.items():
        supplied_records = records_by_cohort[cohort]
        if not isinstance(supplied_records, Sequence) or isinstance(
            supplied_records, (str, bytes)
        ):
            raise T087IncompleteError(f"T087 {cohort} records are malformed")
        records = tuple(supplied_records)
        if len(records) != expected_count:
            raise T087IncompleteError(
                f"cohort {cohort} contains {len(records)} records, expected {expected_count}"
            )
        gate_records = verified_gate.cohorts.get(cohort)
        canonical = canonical_records_by_cohort.get(cohort)
        gate_canonical = verified_gate.canonical_records_by_cohort.get(cohort)
        if canonical is None or gate_records is None or gate_canonical is None:
            raise T087IncompleteError(f"canonical restore map for cohort {cohort} is unavailable")
        if canonical != gate_canonical:
            raise T087IncompleteError(f"canonical restore map for cohort {cohort} was substituted")
        if [_t085_record_signature(record) for record in records] != [
            _t085_record_signature(record) for record in gate_records
        ]:
            raise T087IncompleteError(f"T085 {cohort} records differ from the pinned occurrence-safe selection")
        for record in records:
            _assert_t085_execution_binding(
                gate=verified_gate,
                record=record,
                cohort=cohort,
                canonical_records=canonical,
                source_selection_manifest_identity=verified_gate.source_selection_manifest_identity,
            )
            rows.append(
                _run_t087_native_record_verified(
                    record=record,
                    cohort=cohort,
                    canonical_records=canonical,
                    adapter_factory=adapter_factory,
                    source_selection_manifest_identity=verified_gate.source_selection_manifest_identity,
                )
            )
    return rows


def _run_t087_hp_rescue_variant_verified(
    *,
    record: object,
    cohort: str,
    extra_hp: int,
    canonical_records: Mapping[str, object],
    adapter_factory: Callable[[], object],
    source_selection_manifest_identity: Mapping[str, object],
) -> dict[str, object]:
    """Run one accepted native current-HP-only rescue variant."""

    if isinstance(extra_hp, bool) or not isinstance(extra_hp, int) or extra_hp < 0:
        raise T087IncompleteError("HP rescue extra_hp must be a non-negative integer")
    identity = _record_identity(record)
    _validate_t087_current_native_identity()
    try:
        restored_adapter = adapter_factory()
        restored, restore_method = restore_t085_canonical_record(
            restored_adapter, record, canonical_records
        )
        entry_snapshot = restored
        if extra_hp:
            rebuild = getattr(restored_adapter, "rebuild_battle_start", None)
            if not callable(rebuild):
                raise T087IncompleteError("accepted native HP-addition transform is unavailable")
            transformed = rebuild(
                restored,
                hp_bonus=extra_hp,
                add_random_potion=False,
                encounter_id=None,
            )
            before_hp = _finite(_player_value(restored.raw, "current_hp"), "restored current_hp")
            after_hp = _finite(_player_value(transformed.raw, "current_hp"), "transformed current_hp")
            if after_hp - before_hp != extra_hp:
                raise T087IncompleteError("native HP transform did not apply the requested exact delta")
            entry_snapshot = transformed
        entry = battle_snapshot_evidence(entry_snapshot.raw)
        adapter = T085NativeTerminalSearchAdapter(
            restored_adapter,
            search_simulations=100,
            search_backend="battle_search_v2",
            policy_prior_callback=None,
            leaf_value_callback=None,
            expected_native_identity=T087_NATIVE_IDENTITY,
        )
        adapter.prime_restored_snapshot(entry_snapshot)
        controller = T085UnguidedBattleSearchV2Controller(
            simulations=100,
            expected_native_identity=T087_NATIVE_IDENTITY,
        )
        _validate_t087_evaluator_contract(
            adapter=adapter,
            controller=controller,
            seed=None,
            max_steps=200,
            action_space=ActionSpaceConfig.initial_no_potions(),
        )
        controlled = execute_controlled_run(
            adapter,
            controller,
            seed=None,
            max_steps=200,
            action_space=ActionSpaceConfig.initial_no_potions(),
        )
    except (T085NativeExecutionError, T087IncompleteError, RuntimeError, ValueError) as exc:
        raise T087IncompleteError(f"{identity} HP rescue +{extra_hp}: {exc}") from exc
    if not controlled.terminal or controlled.problems:
        raise T087IncompleteError(
            f"{identity} HP rescue +{extra_hp} did not terminate: "
            + "; ".join(controlled.problems)
        )
    terminal = battle_snapshot_evidence(
        _terminal_raw(controlled), require_positive_enemy_hp=False
    )
    outcome = _terminal_outcome_from_raw(terminal["raw_snapshot"])
    return build_dense_diagnostic_row(
        selection_identity=identity,
        cohort=cohort,
        entry=entry,
        terminal=terminal,
        outcome=outcome,
        action_trace=_trace_for_controlled_run(controlled),
        provenance={
            "task_id": T087_TASK_ID,
            "natural_selection_identity": identity,
            "restore_method": restore_method,
            "native_commit": T087_NATIVE_COMMIT,
            "search_api": T087_SEARCH_API,
            "search_budget": 100,
            "root_selection_rule": "highest_mean",
            "policy_prior_callback": False,
            "learned_leaf_value_callback": False,
            "action_space": ActionSpaceConfig.initial_no_potions().to_dict(),
            "hp_transform": "current_hp_addition" if extra_hp else "none",
            "extra_hp": extra_hp,
            "add_random_potion": False,
            "encounter_id": None,
            "intervention_scope": "current_hp_only",
            "seed": None,
            "max_steps": 200,
            "no_additional_search_seed": True,
            "restore_source_identity": identity,
            "source_selection_manifest_identity": dict(source_selection_manifest_identity),
        },
        source_selection_manifest_identity=source_selection_manifest_identity,
    )


def run_t087_hp_rescue_variant(
    *,
    record: object,
    cohort: str,
    extra_hp: int,
    canonical_records: Mapping[str, object],
    adapter_factory: Callable[[], object],
    source_selection_manifest_identity: Mapping[str, object],
    t085_input_gate: T087T085InputGate | None = None,
) -> dict[str, object]:
    """Run one HP variant only from the verified T085 execution binding."""

    if t085_input_gate is None:
        raise T087IncompleteError("T085 hash-bound input gate is required before HP rescue")
    verified_gate = _revalidate_t085_gate(t085_input_gate)
    _assert_t085_execution_binding(
        gate=verified_gate,
        record=record,
        cohort=cohort,
        canonical_records=canonical_records,
        source_selection_manifest_identity=source_selection_manifest_identity,
    )
    return _run_t087_hp_rescue_variant_verified(
        record=record,
        cohort=cohort,
        extra_hp=extra_hp,
        canonical_records=canonical_records,
        adapter_factory=adapter_factory,
        source_selection_manifest_identity=source_selection_manifest_identity,
    )


def run_t087_hp_rescue(
    *,
    natural_rows: Iterable[Mapping[str, object]],
    records_by_identity: Mapping[str, object],
    canonical_records_by_cohort: Mapping[str, Mapping[str, object]],
    adapter_factory: Callable[[], object],
    t085_input_gate: T087T085InputGate | None = None,
) -> tuple[dict[str, object], list[dict[str, object]]]:
    """Run the exact 24-record, non-monotone HP rescue ladder."""

    verified_gate = _revalidate_t085_gate(t085_input_gate) if t085_input_gate is not None else None
    if verified_gate is None:
        raise T087IncompleteError("T085 hash-bound input gate is required before HP rescue")
    _validate_t087_current_native_identity()
    if not isinstance(records_by_identity, Mapping) or not isinstance(
        canonical_records_by_cohort, Mapping
    ):
        raise T087IncompleteError("HP rescue record maps are malformed")
    if canonical_records_by_cohort != verified_gate.canonical_records_by_cohort:
        raise T087IncompleteError("HP rescue canonical restore maps were substituted")
    raw_rows = tuple(natural_rows)
    if any(not isinstance(row, Mapping) for row in raw_rows):
        raise T087IncompleteError("HP rescue natural rows are malformed")
    rows = tuple(dict(row) for row in raw_rows)
    if len(rows) != T087_NATURAL_RECORD_COUNT:
        raise T087IncompleteError("HP rescue natural rows do not contain exactly 413 records")
    expected_primary = {
        record.selection_identity: record
        for cohort in ("A", "B", "C")
        for record in verified_gate.cohorts[cohort]
    }
    if set(records_by_identity) != set(expected_primary):
        raise T087IncompleteError("HP rescue records are not exactly the pinned A/B/C selection")
    for identity, expected_record in expected_primary.items():
        if _t085_record_signature(records_by_identity[identity]) != _t085_record_signature(expected_record):
            raise T087IncompleteError(f"HP rescue record {identity} was substituted")
    observed_by_cohort: dict[str, list[str]] = {"A": [], "B": [], "C": []}
    for row in rows:
        try:
            validate_dense_diagnostic_row(row)
        except T087IncompleteError as exc:
            raise T087IncompleteError("HP rescue natural evidence is invalid") from exc
        cohort = row.get("cohort")
        if cohort in observed_by_cohort:
            observed_by_cohort[cohort].append(_row_identity(row))
        try:
            source = _source_selection_manifest_identity(row)
        except T087IncompleteError as exc:
            raise T087IncompleteError("HP rescue natural rows lack T085 selection provenance") from exc
        if (
            source.get("sha256") != verified_gate.source_selection_manifest_identity.get("sha256")
            or source.get("schema_id") != verified_gate.source_selection_manifest_identity.get("schema_id")
            or source.get("byte_count") != verified_gate.source_selection_manifest_identity.get("byte_count")
            or not _ref_path_equal(source.get("path"), verified_gate.source_selection_manifest_identity.get("path"))
        ):
            raise T087IncompleteError("HP rescue natural row source selection artifact was substituted")
    for cohort in ("A", "B", "C"):
        expected_ids = [record.selection_identity for record in verified_gate.cohorts[cohort]]
        if observed_by_cohort[cohort] != expected_ids:
            raise T087IncompleteError(f"HP rescue natural rows differ from pinned {cohort} selection")
    manifest = select_hp_rescue_losses(rows)
    result_rows: list[dict[str, object]] = []
    for selected in manifest["selected"]:  # type: ignore[index]
        identity = str(selected["selection_identity"])
        record = records_by_identity.get(identity)
        if record is None:
            raise T087IncompleteError(f"HP rescue record {identity} is unavailable")
        cohort = str(selected["cohort"])
        natural = next(row for row in rows if _row_identity(row) == identity)
        diagnostics = natural.get("entry")
        if not isinstance(diagnostics, Mapping):
            raise T087IncompleteError(f"natural row {identity} lacks entry evidence")
        ladder = hp_rescue_ladder(
            diagnostics.get("player_current_hp"), diagnostics.get("player_max_hp")
        )
        _assert_t085_execution_binding(
            gate=verified_gate,
            record=record,
            cohort=cohort,
            canonical_records=canonical_records_by_cohort[cohort],
            source_selection_manifest_identity=verified_gate.source_selection_manifest_identity,
        )
        for extra_hp in ladder:
            row = _run_t087_hp_rescue_variant_verified(
                record=record,
                cohort=cohort,
                extra_hp=extra_hp,
                canonical_records=canonical_records_by_cohort[cohort],
                adapter_factory=adapter_factory,
                source_selection_manifest_identity=verified_gate.source_selection_manifest_identity,
            )
            row["hp_rescue_selection"] = dict(selected)
            row["extra_hp"] = extra_hp
            result_rows.append(row)
    return manifest, result_rows


def _record_identity(record: object) -> str:
    identity = getattr(record, "selection_identity", None)
    if not isinstance(identity, str) and isinstance(record, Mapping):
        identity = record.get("selection_identity", record.get("record_identity"))
    if not isinstance(identity, str) or not identity:
        raise T087IncompleteError("record lacks exact selection identity")
    return identity


def _quantiles(values: Sequence[float]) -> dict[str, float | None]:
    if not values:
        return {"p25": None, "p50": None, "p75": None}
    ordered = sorted(values)
    def pick(fraction: float) -> float:
        return ordered[min(len(ordered) - 1, int((len(ordered) - 1) * fraction))]
    return {"p25": pick(0.25), "p50": pick(0.50), "p75": pick(0.75)}


def _distribution_summary(
    rows: Sequence[Mapping[str, object]],
    metric: str,
    *,
    include: Callable[[Mapping[str, object]], bool] | None = None,
) -> dict[str, object]:
    """Summarize one retained diagnostic across fixed cohort/outcome groups."""

    def selected(values: Sequence[Mapping[str, object]]) -> list[float]:
        return [
            _finite(
                row.get("diagnostics", {}).get(metric)
                if isinstance(row.get("diagnostics"), Mapping)
                and metric in row["diagnostics"]
                else row.get(metric),
                f"row summary.{metric}",
            )
            for row in values
            if include is None or include(row)
        ]

    by_cohort = {
        cohort: _quantiles(
            selected([row for row in rows if row.get("cohort") == cohort])
        )
        for cohort in T087_COHORT_COUNTS
    }
    outcomes = ("PLAYER_VICTORY", "PLAYER_LOSS")
    by_outcome = {
        outcome: _quantiles(
            selected([row for row in rows if row.get("outcome") == outcome])
        )
        for outcome in outcomes
    }
    by_cohort_outcome = {
        cohort: {
            outcome: _quantiles(
                selected(
                    [
                        row
                        for row in rows
                        if row.get("cohort") == cohort
                        and row.get("outcome") == outcome
                    ]
                )
            )
            for outcome in outcomes
        }
        for cohort in T087_COHORT_COUNTS
    }
    return {
        **_quantiles(selected(rows)),
        "by_cohort": by_cohort,
        "by_outcome": by_outcome,
        "by_cohort_outcome": by_cohort_outcome,
    }


T087_ARTIFACT_SCHEMAS = {
    "natural_evidence": "t087-natural-evidence-v1",
    "dense_diagnostic_table": "t087-dense-diagnostic-table-v1",
    "hp_rescue_selection": "t087-hp-rescue-selection-v1",
    "hp_rescue_ladder": "t087-hp-rescue-ladder-v1",
    "blind_audit_selection": "t087-blind-audit-selection-v1",
    "blind_audit_bundle": "t087-blind-audit-bundle-v1",
    "blind_audit_hidden_provenance": "t087-blind-audit-hidden-provenance-v1",
    "human_review_rubric": "t087-human-review-rubric-v1",
}


def _manifest_digest_is_current(manifest: Mapping[str, object]) -> bool:
    try:
        digest = manifest.get("canonical_sha256")
        payload = {
            key: value
            for key, value in manifest.items()
            if key != "canonical_sha256"
        }
        return isinstance(digest, str) and digest == hashlib.sha256(
            canonical_json_bytes(payload)
        ).hexdigest()
    except (TypeError, ValueError):
        return False


def _validate_reference_identity_shape(value: object) -> bool:
    """Validate an embedded reference without rehashing a large source file."""

    if not isinstance(value, Mapping) or set(value) != {
        "path",
        "sha256",
        "schema_id",
        "byte_count",
    }:
        return False
    return (
        isinstance(value.get("path"), str)
        and bool(value.get("path"))
        and isinstance(value.get("sha256"), str)
        and len(value["sha256"]) == 64
        and all(character in "0123456789abcdef" for character in value["sha256"])
        and isinstance(value.get("schema_id"), str)
        and bool(value.get("schema_id"))
        and isinstance(value.get("byte_count"), int)
        and not isinstance(value.get("byte_count"), bool)
        and value["byte_count"] >= 0
    )


def _validate_t087_input_reference_container(
    value: object,
    label: str,
    problems: list[str],
) -> bool:
    """Validate the direct T085 selection/restore/source reference shape."""

    expected_keys = {"selection", "restore", "canonical", "source_manifests"}
    if not isinstance(value, Mapping) or set(value) != expected_keys:
        problems.append(
            f"{label} must contain selection, restore, canonical, and source-manifests references"
        )
        return False
    expected_documents = {
        "selection": (T085_SELECTION_SHA256, T085_SELECTION_SCHEMA_ID),
        "restore": (T085_RESTORE_SHA256, T085_RESTORE_SCHEMA_ID),
    }
    for role, (expected_sha, expected_schema) in expected_documents.items():
        reference = value.get(role)
        if not isinstance(reference, Mapping):
            problems.append(f"{label}.{role} reference is malformed")
            continue
        if reference.get("sha256") != expected_sha or reference.get("schema_id") != expected_schema:
            problems.append(f"{label}.{role} reference is not pinned")
            continue
        if not _validate_reference_identity_shape(reference):
            problems.append(f"{label}.{role} reference identity is malformed")

    canonical = value.get("canonical")
    if not isinstance(canonical, Mapping) or set(canonical) != {"A", "B", "C"}:
        problems.append(f"{label}.canonical references are incomplete")
    else:
        for cohort in ("A", "B", "C"):
            reference = canonical.get(cohort)
            if not isinstance(reference, Mapping):
                problems.append(f"{label}.canonical.{cohort} reference is malformed")
                continue
            if reference.get("schema_id") != T085_CANONICAL_SOURCE_SCHEMA_IDS[cohort]:
                problems.append(f"{label}.canonical.{cohort} schema is not current")
            if not _validate_reference_identity_shape(reference):
                problems.append(
                    f"{label}.canonical.{cohort} reference identity is malformed"
                )

    manifests = value.get("source_manifests")
    if not isinstance(manifests, Mapping) or set(manifests) != {"B", "C"}:
        problems.append(f"{label}.source_manifests references are incomplete")
    else:
        expected_manifests = {
            "B": T085_B_SOURCE_MANIFEST_SHA256,
            "C": T085_C_SOURCE_MANIFEST_SHA256,
        }
        for cohort, expected_sha in expected_manifests.items():
            reference = manifests.get(cohort)
            if not isinstance(reference, Mapping):
                problems.append(f"{label}.source_manifests.{cohort} reference is malformed")
                continue
            if (
                reference.get("sha256") != expected_sha
                or reference.get("schema_id") != T085_SOURCE_MANIFEST_SCHEMA_ID
            ):
                problems.append(f"{label}.source_manifests.{cohort} reference is not pinned")
            if not _validate_reference_identity_shape(reference):
                problems.append(
                    f"{label}.source_manifests.{cohort} reference identity is malformed"
                )
    return True


def _is_t087_commit_sha(value: object) -> bool:
    return isinstance(value, str) and len(value) == 40 and all(
        character in "0123456789abcdef" for character in value
    )


def _is_t087_lineage_source_verification(value: object) -> bool:
    return (
        isinstance(value, Mapping)
        and value.get("passed") is True
        and value.get("historical_native_identity") == T085_NATIVE_IDENTITY
        and value.get("current_native_identity") == T087_NATIVE_IDENTITY
        and value.get("historical_is_ancestor") is True
        and value.get("source_verifier_passed") is True
    )


def _validate_artifact_surfaces(
    artifact_references: Mapping[str, Mapping[str, object]] | None,
    retention_inputs: Mapping[str, object] | None,
    problems: list[str],
) -> None:
    if artifact_references is not None and not isinstance(artifact_references, Mapping):
        problems.append("T087 artifact references are malformed")
        references: Mapping[str, Mapping[str, object]] = {}
    else:
        references = artifact_references or {}
    missing = T087_REQUIRED_ARTIFACT_ROLES - set(references)
    if missing:
        problems.append("required T087 artifact references are missing: " + ",".join(sorted(missing)))
    for role, schema_id in T087_ARTIFACT_SCHEMAS.items():
        reference = references.get(role)
        if not isinstance(reference, Mapping):
            continue
        if reference.get("schema_id") != schema_id:
            problems.append(f"artifact reference {role} has the wrong current schema")
        if (
            not isinstance(reference.get("path"), str)
            or not reference.get("path")
            or not isinstance(reference.get("sha256"), str)
            or len(reference["sha256"]) != 64
            or any(character not in "0123456789abcdef" for character in reference["sha256"])
            or isinstance(reference.get("size_bytes"), bool)
            or not isinstance(reference.get("size_bytes"), int)
            or reference["size_bytes"] < 0
        ):
            problems.append(f"artifact reference {role} lacks a valid path/hash/size identity")
            continue
        path = Path(reference["path"])
        try:
            if not path.is_file() or path.stat().st_size != reference["size_bytes"]:
                raise OSError("missing or size-mismatched artifact")
            if _sha256_file(path) != reference["sha256"]:
                raise OSError("artifact SHA-256 mismatch")
            document = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(document, Mapping) or document.get("schema_id") != schema_id:
                raise OSError("artifact schema mismatch")
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            problems.append(f"artifact reference {role} does not verify: {exc}")
    if not isinstance(retention_inputs, Mapping):
        problems.append("T087 retention inputs are missing")
        return
    for key in (
        "stable_root",
        "regeneration_command",
        "raw_deletion_condition",
        "native_lineage_source_verification_path",
    ):
        if not isinstance(retention_inputs.get(key), str) or not retention_inputs[key]:
            problems.append(f"T087 retention input {key} is missing")
    run_head = retention_inputs.get("t087_run_head")
    if not _is_t087_commit_sha(run_head):
        problems.append("T087 retention implementation/run head is missing or malformed")
    if not _is_t087_lineage_source_verification(
        retention_inputs.get("native_lineage_source_verification")
    ):
        problems.append("T087 retention lineage/source-verifier result is not the accepted chain")
    regeneration_command = retention_inputs.get("regeneration_command")
    required_arguments = (
        "--natural",
        "--hp-ladder",
        "--audit-traces",
        "--t085-selection",
        "--t085-restore",
        "--run-head",
        "--native-lineage-source-verification",
        "--report",
        "--artifact-root",
    )
    if isinstance(regeneration_command, str) and any(
        argument not in regeneration_command for argument in required_arguments
    ):
        problems.append("T087 regeneration command does not bind every required input")
    t085_references = retention_inputs.get("t085_input_artifact_references")
    _validate_t087_input_reference_container(
        t085_references, "T087 retention T085 input", problems
    )


def _validate_t085_report_inputs(
    references: Mapping[str, Mapping[str, object]] | None,
    rows: Sequence[Mapping[str, object]],
    problems: list[str],
    selection_identity_order: Mapping[str, Sequence[str]] | None = None,
) -> None:
    if not _validate_t087_input_reference_container(
        references, "T087 report T085 input", problems
    ):
        return
    selection_reference = references.get("selection")
    restore_reference = references.get("restore")
    if not isinstance(selection_reference, Mapping) or not isinstance(restore_reference, Mapping):
        return
    try:
        selection_document, live_selection = _read_hash_bound_json(
            selection_reference["path"],
            expected_sha256=T085_SELECTION_SHA256,
            schema_id=T085_SELECTION_SCHEMA_ID,
            label="T085 selection artifact",
        )
        restore_document, live_restore = _read_hash_bound_json(
            restore_reference["path"],
            expected_sha256=T085_RESTORE_SHA256,
            schema_id=T085_RESTORE_SCHEMA_ID,
            label="T085 restore evidence",
        )
        if dict(live_selection) != dict(selection_reference) or dict(live_restore) != dict(restore_reference):
            raise T087IncompleteError("T087 report T085 selection/restore references are stale")
        expected_order, _restore_rows, canonical_refs, source_manifest_refs, _selection = (
            _validate_t085_document_chain(
                selection_document=selection_document,
                restore_document=restore_document,
                artifact_references={
                    "selection": dict(selection_reference),
                    "restore": dict(restore_reference),
                },
            )
        )
        supplied_canonical = references.get("canonical")
        supplied_manifests = references.get("source_manifests")
        if not isinstance(supplied_canonical, Mapping) or any(
            not _same_reference(supplied_canonical.get(cohort), canonical_refs[cohort])
            for cohort in ("A", "B", "C")
        ):
            raise T087IncompleteError("T087 report canonical source references are not restore-bound")
        if not isinstance(supplied_manifests, Mapping) or any(
            not _same_reference(supplied_manifests.get(cohort), source_manifest_refs[cohort])
            for cohort in ("B", "C")
        ):
            raise T087IncompleteError("T087 report source-manifest references are not restore-bound")
        if selection_identity_order is not None and {
            cohort: tuple(values)
            for cohort, values in selection_identity_order.items()
        } != {
            cohort: tuple(record.selection_identity for record in records)
            for cohort, records in expected_order.items()
        }:
            raise T087IncompleteError(
                "T087 report selection order is not bound to the pinned artifact"
            )
    except (KeyError, TypeError, T087IncompleteError, ValueError, OSError) as exc:
        problems.append(f"T087 report T085 direct input chain is invalid: {exc}")
        return
    selection = references.get("selection")
    if not isinstance(selection, Mapping):
        return
    for row in rows:
        try:
            source = _source_selection_manifest_identity(row)
        except T087IncompleteError as exc:
            problems.append(str(exc))
            continue
        if (
            source.get("sha256") != selection.get("sha256")
            or source.get("schema_id") != selection.get("schema_id")
            or source.get("byte_count") != selection.get("byte_count")
            or not _ref_path_equal(source.get("path"), selection.get("path"))
        ):
            problems.append(
                f"natural row {_row_identity(row)} is not bound to the verified T085 selection artifact"
            )


def _validate_hp_surface(
    manifest: Mapping[str, object] | None,
    rows: Sequence[Mapping[str, object]],
    natural_by_id: Mapping[str, Mapping[str, object]],
    problems: list[str],
) -> dict[str, object] | None:
    if manifest is None:
        return None
    selected = manifest.get("selected")
    if (
        manifest.get("schema_id") != "t087-selection-manifest-v1"
        or manifest.get("selection_domain") != "hp_rescue"
        or not isinstance(selected, Sequence)
        or isinstance(selected, (str, bytes))
        or len(selected) != 24
        or not _manifest_digest_is_current(manifest)
    ):
        problems.append("HP rescue selection manifest is not the exact current 24-row surface")
        return None
    selections = [item for item in selected if isinstance(item, Mapping)]
    if len(selections) != 24:
        problems.append("HP rescue selection manifest contains malformed rows")
        return None
    by_id: dict[str, Mapping[str, object]] = {}
    for item in selections:
        identity = item.get("selection_identity")
        cohort = item.get("cohort")
        rank = item.get("selected_rank")
        if (
            not isinstance(identity, str)
            or identity in by_id
            or cohort not in T087_COHORT_COUNTS
            or isinstance(rank, bool)
            or not isinstance(rank, int)
            or not isinstance(item.get("source_selection_manifest_identity"), Mapping)
            or item.get("selection_digest") != selection_digest(identity, domain="hp")
        ):
            problems.append("HP rescue selection contains invalid identity/rank/provenance")
            continue
        by_id[identity] = item
    for cohort in ("A", "B", "C"):
        ranks = sorted(
            item["selected_rank"]
            for item in selections
            if item.get("cohort") == cohort
            and isinstance(item.get("selected_rank"), int)
            and not isinstance(item.get("selected_rank"), bool)
        )
        if ranks != list(range(8)):
            problems.append(f"HP rescue selection ranks are not exact for cohort {cohort}")
    # The selected set is allowed to be a strict subset of natural rows.
    if set(by_id) != set(natural_by_id) and any(
        identity not in natural_by_id for identity in by_id
    ):
        problems.append("HP rescue selection contains an identity outside natural evidence")
    try:
        expected_manifest = select_hp_rescue_losses(natural_by_id.values())
    except T087IncompleteError as exc:
        problems.append(f"HP rescue selection cannot be recomputed: {exc}")
    else:
        if selected != expected_manifest.get("selected"):
            problems.append("HP rescue selection is not the frozen digest-ranked surface")
    expected_keys: set[tuple[str, int]] = set()
    observed_keys: set[tuple[str, int]] = set()
    validation_rows: list[dict[str, object]] = []
    validated_variant_rows: dict[tuple[str, int], Mapping[str, object]] = {}
    for identity, item in by_id.items():
        natural = natural_by_id.get(identity)
        if natural is None or natural.get("outcome") != "PLAYER_LOSS":
            problems.append(f"HP rescue identity {identity} is not an accepted natural loss")
            continue
        entry = natural.get("entry")
        if not isinstance(entry, Mapping):
            problems.append(f"HP rescue identity {identity} lacks entry HP evidence")
            continue
        try:
            ladder = hp_rescue_ladder(entry.get("player_current_hp"), entry.get("player_max_hp"))
        except T087IncompleteError as exc:
            problems.append(str(exc))
            continue
        expected_keys.update((identity, extra_hp) for extra_hp in ladder)
        source_identity = _source_selection_manifest_identity(natural)
        if item.get("source_selection_manifest_identity") != source_identity:
            problems.append(f"HP rescue identity {identity} has substituted source provenance")
    for row in rows:
        identity = row.get("selection_identity")
        extra_hp = row.get("extra_hp")
        if not isinstance(identity, str) or isinstance(extra_hp, bool) or not isinstance(extra_hp, int):
            problems.append("HP rescue row has invalid identity or non-integral extra_hp")
            continue
        row_is_valid = True
        variant_key = (identity, extra_hp)
        if variant_key in observed_keys:
            problems.append(f"HP rescue row {identity} +{extra_hp} is duplicated")
            row_is_valid = False
        observed_keys.add(variant_key)
        selection = row.get("hp_rescue_selection")
        if not isinstance(selection, Mapping) or by_id.get(identity) != selection:
            problems.append(f"HP rescue row {identity} is not bound to the frozen selection")
            row_is_valid = False
        natural = natural_by_id.get(identity)
        if natural is None:
            problems.append(f"HP rescue row {identity} is outside the natural evidence")
            row_is_valid = False
        else:
            try:
                natural_source = _source_selection_manifest_identity(natural)
                row_source = _source_selection_manifest_identity(row)
            except T087IncompleteError as exc:
                problems.append(str(exc))
                row_is_valid = False
            else:
                if row_source != natural_source:
                    problems.append(
                        f"HP rescue row {identity} has substituted source provenance"
                    )
                    row_is_valid = False
        try:
            validate_dense_diagnostic_row(row)
        except T087IncompleteError as exc:
            problems.append(str(exc))
            row_is_valid = False
        provenance = row.get("provenance")
        expected_transform = "current_hp_addition" if extra_hp > 0 else "none"
        if (
            not isinstance(provenance, Mapping)
            or provenance.get("natural_selection_identity") != identity
            or provenance.get("extra_hp") != extra_hp
            or provenance.get("hp_transform") != expected_transform
            or provenance.get("add_random_potion") is not False
            or provenance.get("encounter_id") is not None
            or provenance.get("intervention_scope") != "current_hp_only"
        ):
            problems.append(f"HP rescue row {identity} has invalid execution provenance")
            row_is_valid = False
        try:
            terminal_margin = _diagnostic(row, "combat_terminal_margin_v1")
        except T087IncompleteError as exc:
            problems.append(str(exc))
            terminal_margin = None
            row_is_valid = False
        if row_is_valid:
            validated_variant_rows[variant_key] = row
            validation_rows.append(
                {
                    "selection_identity": identity,
                    "extra_hp": extra_hp,
                    "outcome": row.get("outcome"),
                    "terminal_margin": terminal_margin,
                    "selection_digest": selection_digest(identity, domain="hp"),
                }
            )
    if observed_keys != expected_keys or len(rows) != len(expected_keys):
        problems.append("HP rescue ladder rows do not exactly cover the frozen integral ladders")
    selection_outcomes: list[dict[str, object]] = []
    if (
        observed_keys == expected_keys
        and len(rows) == len(expected_keys)
        and len(validated_variant_rows) == len(expected_keys)
    ):
        try:
            for selection in selections:
                identity = selection["selection_identity"]
                natural = natural_by_id[identity]
                entry = natural.get("entry")
                if not isinstance(entry, Mapping):
                    raise T087IncompleteError(
                        f"HP rescue identity {identity} lacks entry HP evidence"
                    )
                ladder = hp_rescue_ladder(
                    entry.get("player_current_hp"), entry.get("player_max_hp")
                )
                sequence: list[dict[str, object]] = []
                for extra_hp in ladder:
                    variant = validated_variant_rows.get((identity, extra_hp))
                    if variant is None:
                        raise T087IncompleteError(
                            f"HP rescue identity {identity} lacks ladder variant +{extra_hp}"
                        )
                    outcome = variant.get("outcome")
                    if outcome not in T087_TERMINAL_CLASSES:
                        raise T087IncompleteError(
                            f"HP rescue identity {identity} +{extra_hp} has no authoritative outcome"
                        )
                    sequence.append(
                        {
                            "extra_hp": extra_hp,
                            "outcome": outcome,
                            "terminal_margin": _diagnostic(
                                variant, "combat_terminal_margin_v1"
                            ),
                        }
                    )
                positive_wins = [
                    item["extra_hp"]
                    for item in sequence
                    if item["extra_hp"] > 0
                    and item["outcome"] == "PLAYER_VICTORY"
                ]
                selection_outcomes.append(
                    {
                        "selection_identity": identity,
                        "cohort": selection["cohort"],
                        "extra_hp_ladder": list(ladder),
                        "outcome_sequence": sequence,
                        "min_observed_extra_hp_with_win": (
                            min(positive_wins) if positive_wins else None
                        ),
                        "censored_no_win_at_max_hp": sequence[-1]["outcome"]
                        == "PLAYER_LOSS",
                    }
                )
        except (KeyError, TypeError, T087IncompleteError) as exc:
            problems.append(f"HP rescue ladder outcomes cannot be summarized: {exc}")
            selection_outcomes = []
    censoring_count = (
        sum(
            item["censored_no_win_at_max_hp"] is True
            for item in selection_outcomes
        )
        if len(selection_outcomes) == 24
        else None
    )
    return {
        "selected_count": len(by_id),
        "expected_variant_count": len(expected_keys),
        "observed_variant_count": len(observed_keys),
        "validated_variant_count": len(validated_variant_rows),
        "variants": sorted(
            validation_rows,
            key=lambda item: (
                str(item["selection_identity"]),
                int(item["extra_hp"]),
            ),
        ),
        "record_count": len(selection_outcomes),
        "selection_outcomes": selection_outcomes,
        "censoring_count": censoring_count,
    }


def _validate_audit_surface(
    manifest: Mapping[str, object] | None,
    trace_rows: Sequence[Mapping[str, object]],
    natural_by_id: Mapping[str, Mapping[str, object]],
    problems: list[str],
) -> tuple[Mapping[str, object] | None, Mapping[str, object] | None, dict[str, object] | None]:
    if manifest is None:
        return None, None, None
    selected = manifest.get("selected")
    if (
        manifest.get("schema_id") != "t087-selection-manifest-v1"
        or manifest.get("selection_domain") != "human_audit"
        or not isinstance(selected, Sequence)
        or isinstance(selected, (str, bytes))
        or len(selected) != 24
        or not _manifest_digest_is_current(manifest)
    ):
        problems.append("blind audit selection manifest is not the exact current 24-row surface")
        return None, None, None
    selections = [item for item in selected if isinstance(item, Mapping)]
    ids = {item.get("selection_identity") for item in selections}
    if len(selections) != 24 or len(ids) != 24 or any(not isinstance(identity, str) for identity in ids):
        problems.append("blind audit selection identities are not exact and pairwise disjoint")
    expected_groups = {
        "wins": ("human_audit_win", "PLAYER_VICTORY", None),
        "near_boundary_losses": ("human_audit_near_loss", "PLAYER_LOSS", "near"),
        "deep_losses": ("human_audit_deep_loss", "PLAYER_LOSS", "deep"),
    }
    for group, (expected_role, expected_outcome, threshold_kind) in expected_groups.items():
        group_items = [item for item in selections if item.get("audit_stratum") == group]
        if len(group_items) != 8:
            problems.append(f"blind audit group {group} does not contain exactly eight rows")
        ranks = sorted(
            item.get("selected_rank")
            for item in group_items
            if isinstance(item.get("selected_rank"), int)
            and not isinstance(item.get("selected_rank"), bool)
        )
        if ranks != list(range(8)):
            problems.append(f"blind audit group {group} ranks are not exact")
        for item in group_items:
            if item.get("selection_role") != expected_role:
                problems.append(f"blind audit group {group} has an invalid selection role")
            threshold = item.get("threshold")
            if threshold_kind is None and threshold is not None:
                problems.append("blind audit wins must not carry a threshold")
            if threshold_kind == "near" and threshold not in T087_AUDIT_NEAR_THRESHOLDS:
                problems.append("blind audit near-loss threshold is not frozen")
            if threshold_kind == "deep" and threshold not in T087_AUDIT_DEEP_THRESHOLDS:
                problems.append("blind audit deep-loss threshold is not frozen")
            identity = item.get("selection_identity")
            natural = natural_by_id.get(identity) if isinstance(identity, str) else None
            if natural is not None and natural.get("outcome") != expected_outcome:
                problems.append(
                    f"blind audit identity {identity} has the wrong authoritative outcome"
                )
    for item in selections:
        identity = item.get("selection_identity")
        if not isinstance(identity, str) or item.get("selection_digest") != selection_digest(identity, domain="human_audit"):
            problems.append("blind audit selection digest is invalid")
        natural = natural_by_id.get(identity) if isinstance(identity, str) else None
        if natural is None:
            problems.append("blind audit selection contains an identity outside natural evidence")
        elif item.get("source_selection_manifest_identity") != _source_selection_manifest_identity(natural):
            problems.append("blind audit selection source provenance is substituted")
    try:
        expected_manifest = select_blind_audit_rows(natural_by_id.values())
    except T087IncompleteError as exc:
        problems.append(f"blind audit selection cannot be recomputed: {exc}")
    else:
        if selected != expected_manifest.get("selected"):
            problems.append("blind audit selection is not the frozen threshold-ranked surface")
    required_ids = {identity for identity in ids if isinstance(identity, str)}
    observed_ids: set[str] = set()
    for row in trace_rows:
        try:
            observed_ids.add(_row_identity(row))
        except T087IncompleteError as exc:
            problems.append(str(exc))
    if len(trace_rows) != 24 or observed_ids != required_ids:
        problems.append("blind audit traces do not exactly cover the frozen 24 identities")
    for row in trace_rows:
        try:
            identity = _row_identity(row)
        except T087IncompleteError:
            continue
        natural = natural_by_id.get(identity)
        if natural is not None:
            try:
                if _source_selection_manifest_identity(row) != _source_selection_manifest_identity(natural):
                    problems.append(
                        f"blind audit trace {identity} has substituted source provenance"
                    )
            except T087IncompleteError as exc:
                problems.append(str(exc))
        try:
            validate_dense_diagnostic_row(row)
        except T087IncompleteError as exc:
            problems.append(str(exc))
    if len(trace_rows) != 24 or observed_ids != required_ids:
        return None, None, None
    try:
        bundle, hidden = build_blind_trace_bundle(selected_manifest=manifest, rows=trace_rows)
    except T087IncompleteError as exc:
        problems.append(str(exc))
        return None, None, None
    traces = bundle.get("traces") if isinstance(bundle, Mapping) else None
    hidden_rows = hidden.get("trace_map") if isinstance(hidden, Mapping) else None
    if (
        bundle.get("schema_id") != "t087-blind-audit-bundle-v1"
        or hidden.get("schema_id") != "t087-blind-audit-hidden-provenance-v1"
        or not isinstance(traces, Sequence)
        or len(traces) != 24
        or not isinstance(hidden_rows, Sequence)
        or len(hidden_rows) != 24
    ):
        problems.append("blind audit bundle/hidden provenance is not the exact current 24-row surface")
        return bundle, hidden, None
    trace_ids = {item.get("trace_id") for item in traces if isinstance(item, Mapping)}
    hidden_ids = {item.get("trace_id") for item in hidden_rows if isinstance(item, Mapping)}
    if trace_ids != set(range(24)) or hidden_ids != set(range(24)):
        problems.append("blind audit trace ids are not exactly 0..23")
    return bundle, hidden, {"trace_count": 24, "trace_ids": sorted(trace_ids), "hidden_trace_ids": sorted(hidden_ids)}


def build_t087_report(
    *,
    natural_rows: Iterable[Mapping[str, object]],
    hp_ladder_rows: Iterable[Mapping[str, object]] = (),
    audit_traces: Iterable[Mapping[str, object]] = (),
    artifact_references: Mapping[str, Mapping[str, object]] | None = None,
    retention_inputs: Mapping[str, object] | None = None,
    t085_selection_identity_order: Mapping[str, Sequence[str]] | None = None,
    t085_input_artifact_references: Mapping[str, object] | None = None,
    t087_run_head: str | None = None,
    native_lineage_source_verification: Mapping[str, object] | None = None,
) -> dict[str, object]:
    """Build a current-schema report and exactly one T087 terminal class."""

    rows = _validate_unique_rows(natural_rows)
    problems: list[str] = []
    if len(rows) != T087_NATURAL_RECORD_COUNT:
        problems.append(f"natural row count is {len(rows)}, expected 413")
    if t085_selection_identity_order is None:
        problems.append("T085 pinned selection identity order is missing")
    elif not isinstance(t085_selection_identity_order, Mapping):
        problems.append("T085 pinned selection identity order is malformed")
    else:
        if set(t085_selection_identity_order) != {"A", "B", "C", "B@400"}:
            problems.append("T085 pinned four-cohort selection identity order is incomplete")
        for cohort in ("A", "B", "C", "B@400"):
            supplied = t085_selection_identity_order.get(cohort)
            if not isinstance(supplied, Sequence) or isinstance(supplied, (str, bytes)):
                problems.append(f"T085 pinned {cohort} selection identity order is malformed")
            elif any(not isinstance(identity, str) or not identity for identity in supplied):
                problems.append(f"T085 pinned {cohort} selection identity is malformed")
        for cohort in ("A", "B", "C"):
            expected_ids = tuple(t085_selection_identity_order.get(cohort, ()))
            observed_ids = tuple(
                _row_identity(row) for row in rows if row.get("cohort") == cohort
            )
            if observed_ids != expected_ids:
                problems.append(f"natural {cohort} identities differ from the pinned T085 selection")
        if len(tuple(t085_selection_identity_order.get("B@400", ()))) != 48:
            problems.append("T085 pinned B@400 selection identity order is not exact")
    for cohort, expected in T087_COHORT_COUNTS.items():
        observed = sum(row.get("cohort") == cohort for row in rows)
        if observed != expected:
            problems.append(f"cohort {cohort} count is {observed}, expected {expected}")
    valid_rows: list[dict[str, object]] = []
    for row in rows:
        try:
            validate_dense_diagnostic_row(row)
        except T087IncompleteError as exc:
            problems.append(str(exc))
        else:
            valid_rows.append(row)
    hp_manifest: Mapping[str, object] | None = None
    audit_manifest: Mapping[str, object] | None = None
    try:
        hp_manifest = select_hp_rescue_losses(valid_rows)
    except T087IncompleteError as exc:
        problems.append(str(exc))
    try:
        audit_manifest = select_blind_audit_rows(valid_rows)
    except T087IncompleteError as exc:
        problems.append(str(exc))
    hp_rows = tuple(dict(row) for row in hp_ladder_rows)
    trace_rows = tuple(dict(row) for row in audit_traces)
    natural_by_id = {_row_identity(row): row for row in valid_rows}
    hp_validation = _validate_hp_surface(hp_manifest, hp_rows, natural_by_id, problems)
    blind_bundle: Mapping[str, object] | None = None
    hidden_provenance: Mapping[str, object] | None = None
    audit_validation = None
    if audit_manifest is not None:
        blind_bundle, hidden_provenance, audit_validation = _validate_audit_surface(
            audit_manifest, trace_rows, natural_by_id, problems
        )
    _validate_t085_report_inputs(
        t085_input_artifact_references,
        rows,
        problems,
        t085_selection_identity_order,
    )
    _validate_artifact_surfaces(artifact_references, retention_inputs, problems)
    if (
        isinstance(retention_inputs, Mapping)
        and retention_inputs.get("t085_input_artifact_references")
        != t085_input_artifact_references
    ):
        problems.append("T087 retention and report T085 input references are not identical")
    if not _is_t087_commit_sha(t087_run_head):
        problems.append("T087 exact implementation/run head is missing or malformed")
    if not isinstance(native_lineage_source_verification, Mapping):
        problems.append("T087 native lineage/source-verifier result is missing")
    elif not _is_t087_lineage_source_verification(
        native_lineage_source_verification
    ):
        problems.append("T087 native lineage/source-verifier result is not the accepted chain")
    if isinstance(retention_inputs, Mapping):
        if retention_inputs.get("t087_run_head") != t087_run_head:
            problems.append("T087 retention and report implementation/run heads differ")
        if retention_inputs.get("native_lineage_source_verification") != native_lineage_source_verification:
            problems.append(
                "T087 retention and report lineage/source-verifier results differ"
            )
    outcome_counts = Counter(str(row.get("outcome")) for row in rows)
    by_cohort = {
        cohort: {
            "rows": sum(row.get("cohort") == cohort for row in rows),
            "wins": sum(row.get("cohort") == cohort and row.get("outcome") == "PLAYER_VICTORY" for row in rows),
            "losses": sum(row.get("cohort") == cohort and row.get("outcome") == "PLAYER_LOSS" for row in rows),
        }
        for cohort in T087_COHORT_COUNTS
    }
    margin_distribution = _distribution_summary(
        valid_rows, "combat_terminal_margin_v1"
    )
    margin_distribution["components"] = {
        "enemy_occurrence_count_terminal": _distribution_summary(
            valid_rows, "enemy_occurrence_count_terminal"
        ),
        "enemy_count_active_terminal": _distribution_summary(
            valid_rows, "enemy_count_active_terminal"
        ),
        "enemy_count_hp_alive_terminal": _distribution_summary(
            valid_rows, "enemy_count_hp_alive_terminal"
        ),
        "enemy_count_non_targetable_hp_alive_terminal": _distribution_summary(
            valid_rows, "enemy_count_non_targetable_hp_alive_terminal"
        ),
        "terminal_total_enemy_hp_all_occurrences": _distribution_summary(
            valid_rows, "terminal_total_enemy_hp_all_occurrences"
        ),
        "terminal_total_enemy_hp_active": _distribution_summary(
            valid_rows, "terminal_total_enemy_hp_active"
        ),
        "enemy_hp_remaining_fraction": _distribution_summary(
            valid_rows,
            "enemy_hp_remaining_fraction",
            include=lambda row: row.get("outcome") == "PLAYER_LOSS",
        ),
        "enemy_hp_progress_fraction_v1": _distribution_summary(
            valid_rows,
            "enemy_hp_progress_fraction_v1",
            include=lambda row: row.get("outcome") == "PLAYER_LOSS",
        ),
        "player_hp_remaining_fraction_of_max": _distribution_summary(
            valid_rows,
            "player_hp_remaining_fraction_of_max",
            include=lambda row: row.get("outcome") == "PLAYER_VICTORY",
        ),
    }
    loss_enemy_distribution = _distribution_summary(
        valid_rows,
        "enemy_hp_remaining_fraction",
        include=lambda row: row.get("outcome") == "PLAYER_LOSS",
    )
    win_player_distribution = _distribution_summary(
        valid_rows,
        "player_hp_remaining_fraction_of_max",
        include=lambda row: row.get("outcome") == "PLAYER_VICTORY",
    )
    action_distribution = _distribution_summary(valid_rows, "action_count")
    potion_action_distribution = _distribution_summary(
        valid_rows, "potion_action_count"
    )
    report = {
        "schema_id": "t087-dense-combat-diagnostics-report-v1",
        "task_id": T087_TASK_ID,
        "approved_spec": T087_APPROVED_SPEC,
        "base_commit": T087_BASE_COMMIT,
        "implementation_run_head": t087_run_head,
        "native_change_required": False,
        "native_base_commit": T085_NATIVE_COMMIT,
        "native_identity": {
            **T087_NATIVE_IDENTITY,
        },
        "frozen_controller": {
            "name": "unguided_native_search_v2",
            "simulations": 100,
            "root_selection_rule": "highest_mean",
            "policy_prior_callback": False,
            "learned_leaf_value_callback": False,
            "action_space": ActionSpaceConfig.initial_no_potions().to_dict(),
            "seed": None,
            "max_steps": 200,
        },
        "t085_binding": {
            "scientific_head": T085_SCIENTIFIC_HEAD,
            "native_commit": T085_NATIVE_COMMIT,
            "selection_sha256": T085_SELECTION_SHA256,
            "restore_evidence_sha256": T085_RESTORE_SHA256,
            "t052_cohort_sha256": T052_COHORT_SHA256,
            "selection_identity_order_bound": t085_selection_identity_order is not None,
            "selection_identity_order": dict(t085_selection_identity_order or {}),
            "canonical_source_artifacts": (
                dict(t085_input_artifact_references.get("canonical", {}))
                if isinstance(t085_input_artifact_references, Mapping)
                and isinstance(t085_input_artifact_references.get("canonical"), Mapping)
                else {}
            ),
            "source_manifest_artifacts": (
                dict(t085_input_artifact_references.get("source_manifests", {}))
                if isinstance(t085_input_artifact_references, Mapping)
                and isinstance(t085_input_artifact_references.get("source_manifests"), Mapping)
                else {}
            ),
        },
        "t085_input_artifact_references": dict(t085_input_artifact_references or {}),
        "native_lineage_source_verification": (
            dict(native_lineage_source_verification)
            if isinstance(native_lineage_source_verification, Mapping)
            else None
        ),
        "natural_execution": {
            "expected_count": T087_NATURAL_RECORD_COUNT,
            "observed_count": len(rows),
            "outcome_counts": dict(sorted(outcome_counts.items())),
            "by_cohort": by_cohort,
            "restore_and_execution_complete": len(valid_rows) == T087_NATURAL_RECORD_COUNT,
        },
        "diagnostic_summary": {
            "combat_terminal_margin_v1": margin_distribution,
            "loss_enemy_hp_remaining_fraction": loss_enemy_distribution,
            "win_player_hp_remaining_fraction_of_max": win_player_distribution,
            "action_count": action_distribution,
            "potion_action_count": potion_action_distribution,
            "mean_action_count": mean([float(row.get("action_count", 0)) for row in valid_rows]) if valid_rows else None,
            "mean_potion_action_count": mean([float(row.get("potion_action_count", 0)) for row in valid_rows]) if valid_rows else None,
        },
        "hp_rescue": {
            "selection_manifest": hp_manifest,
            "rows": list(hp_rows),
            "validation": hp_validation,
        },
        "blind_human_audit": {
            "selection_manifest": audit_manifest,
            "bundle": blind_bundle,
            "hidden_provenance": hidden_provenance,
            "hidden_provenance_separate": True,
        },
        "human_review_rubric": build_review_rubric(),
        "human_labels_used_by_algorithm": False,
        "artifact_references": dict(artifact_references or {}),
        "retention_inputs": dict(retention_inputs or {}),
        "audit_validation": audit_validation,
        "problems": problems,
        "terminal_classification": (
            "DENSE_COMBAT_DIAGNOSTICS_READY" if not problems else "INCOMPLETE"
        ),
    }
    return report


def write_t087_json_artifact(
    path: str | Path,
    payload: Mapping[str, object],
    *,
    schema_id: str,
) -> dict[str, object]:
    """Write a current T087 JSON artifact and return its file identity."""

    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    document = {"schema_id": schema_id, **dict(payload)}
    target.write_text(
        json.dumps(document, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False)
        + "\n",
        encoding="utf-8",
    )
    data = target.read_bytes()
    return {"path": str(target), "sha256": hashlib.sha256(data).hexdigest(), "size_bytes": len(data), "schema_id": schema_id}


__all__ = [
    "T085_NATIVE_COMMIT",
    "T085_RESTORE_SHA256",
    "T085_SELECTION_SHA256",
    "T087_APPROVED_SPEC",
    "T087_NATIVE_COMMIT",
    "T087_NATIVE_IDENTITY",
    "T087_NATURAL_RECORD_COUNT",
    "T087IncompleteError",
    "T087T085InputGate",
    "battle_snapshot_evidence",
    "build_blind_trace_bundle",
    "build_dense_diagnostic_row",
    "build_review_rubric",
    "build_t087_report",
    "canonical_json_bytes",
    "hp_rescue_ladder",
    "load_t087_t085_input_gate",
    "load_t087_t085_report_binding",
    "load_t087_t085_selection_binding",
    "run_t087_hp_rescue",
    "run_t087_hp_rescue_variant",
    "run_t087_native_record",
    "run_t087_natural_evaluation",
    "select_blind_audit_rows",
    "select_hp_rescue_losses",
    "selection_digest",
    "selection_identity_bytes",
    "validate_dense_diagnostic_row",
    "validate_t087_t085_input_documents",
    "write_t087_json_artifact",
]
