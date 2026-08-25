"""Occurrence-safe source identities for persisted battle-start records."""

from __future__ import annotations

from collections.abc import Mapping
import hashlib
import json
from typing import Any


COMPLETE_SOURCE_IDENTITY_SCHEMA_ID = "t064-complete-source-identity-v1"


def canonical_json_bytes(value: Any) -> bytes:
    """Return the canonical JSON representation used by source identities."""

    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def action_trace_identity_sha256(record: Any) -> str:
    """Hash occurrence-safe selected action identities for one trace."""

    rows: list[dict[str, Any]] = []
    for decision_index, raw in enumerate(record.action_trace):
        if not isinstance(raw, Mapping):
            raise ValueError("action trace identity must be an object")
        stable_id = raw.get("stable_id")
        occurrence = raw.get("occurrence")
        if not isinstance(stable_id, str) or not stable_id:
            raise ValueError("action trace identity is missing stable_id")
        if isinstance(occurrence, bool) or not isinstance(occurrence, int):
            raise ValueError("action trace identity occurrence must be an integer")
        if occurrence < 0:
            raise ValueError("action trace identity occurrence cannot be negative")
        identity = dict(raw)
        if (
            identity.get("stable_id") != stable_id
            or identity.get("occurrence") != occurrence
        ):
            raise ValueError("action trace identity is not occurrence-safe")
        rows.append({"decision_index": decision_index, "selected_action": identity})
    return canonical_sha256(rows)


def complete_source_identity(
    record: Any,
    *,
    source_arm: str | None = None,
) -> dict[str, Any]:
    """Build a complete source identity without guessing absent provenance."""

    metadata = getattr(record, "structural_metadata", None)
    if not isinstance(metadata, Mapping):
        raise ValueError("structural_metadata must be an object")
    existing_trace = metadata.get("action_trace_identity")
    if existing_trace is None:
        trace_identity = action_trace_identity_sha256(record)
    elif isinstance(existing_trace, str) and existing_trace:
        trace_identity = existing_trace
    else:
        raise ValueError("existing action_trace_identity must be a non-empty string")
    assistance_level = metadata.get("assistance_level", "")
    if not isinstance(assistance_level, str):
        raise ValueError("assistance_level must be a string when present")
    mapped_source_arm = (
        metadata.get("source_arm", "") if source_arm is None else source_arm
    )
    if not isinstance(mapped_source_arm, str):
        raise ValueError("source_arm must be a string when present")
    identity = {
        "schema_id": COMPLETE_SOURCE_IDENTITY_SCHEMA_ID,
        "source_checkpoint_id": record.source_checkpoint_id,
        "source_seed": record.source_seed,
        "source_run_id": record.source_run_id,
        "source_battle_index": record.source_battle_index,
        "action_trace_identity": trace_identity,
        "distribution_kind": getattr(
            record,
            "distribution_kind",
            getattr(record, "source_distribution_kind", None),
        ),
        "assistance_level": assistance_level,
        "source_arm": mapped_source_arm,
        "checkpoint_information_regime": record.checkpoint_information_regime,
    }
    _validate_complete_identity(identity)
    identity["complete_identity_sha256"] = canonical_sha256(identity)
    return identity


def _validate_complete_identity(identity: Mapping[str, Any]) -> None:
    required = (
        "schema_id",
        "source_checkpoint_id",
        "source_seed",
        "source_run_id",
        "source_battle_index",
        "action_trace_identity",
        "distribution_kind",
        "assistance_level",
        "source_arm",
        "checkpoint_information_regime",
    )
    missing = [field for field in required if field not in identity]
    if missing:
        raise ValueError(
            "complete source identity is missing required fields: " + ", ".join(missing)
        )
    if identity["schema_id"] != COMPLETE_SOURCE_IDENTITY_SCHEMA_ID:
        raise ValueError("complete source identity schema is invalid")
    for field in (
        "source_checkpoint_id",
        "source_run_id",
        "action_trace_identity",
        "distribution_kind",
        "checkpoint_information_regime",
    ):
        if not isinstance(identity[field], str) or not identity[field]:
            raise ValueError(f"complete source identity {field} must be a string")
    for field in ("assistance_level", "source_arm"):
        if not isinstance(identity[field], str):
            raise ValueError(f"complete source identity {field} must be a string")
    for field in ("source_seed", "source_battle_index"):
        value = identity[field]
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError(f"complete source identity {field} must be an integer")
