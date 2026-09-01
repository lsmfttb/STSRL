#!/usr/bin/env python3
"""Fail-closed offline audit for the frozen T043 value-target lineage."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
from typing import Any, Callable, Mapping

CHECKPOINT_SHA = "a2317354b24f93ff48f0408ba3fdc92056701ef16e9b3a1b8b17aa1cce2a56e4"
REPORT_SCHEMA = "t080-value-target-semantics-audit-v1"
MANIFEST_SCHEMA = "t080-retention-manifest-v1"
STRATA = (
    "assistance_level",
    "act",
    "room_type",
    "source_kind",
    "distribution_kind",
    "encounter_id",
)
OMITTED_KEYS = {"model_state_dict", "weights", "state_dict"}


def digest(path: Path) -> tuple[str, int]:
    h = hashlib.sha256()
    size = 0
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
            size += len(block)
    return h.hexdigest(), size


def _json_safe(value: Any, *, key: str | None = None) -> Any:
    """Return JSON data without checkpoint weights or tensor-like values."""
    if key in OMITTED_KEYS or key is not None and key.endswith("weights"):
        return None
    if value is None or isinstance(value, (str, int, bool, float)):
        return value
    if isinstance(value, Mapping):
        return {
            str(k): safe
            for k, item in value.items()
            if (safe := _json_safe(item, key=str(k))) is not None
        }
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    # torch.Tensor and arbitrary checkpoint objects must never enter the report.
    return None


def _required(value: Any, name: str) -> Any:
    if value is None:
        raise RuntimeError(f"T080 fail closed: missing {name}")
    return value


def _provenance_value(provenance: Mapping[str, Any], *names: str) -> Any:
    for name in names:
        if name in provenance:
            return provenance[name]
    return None


def _path_matches(recorded: str, actual: Path) -> bool:
    recorded_path = Path(recorded)
    if recorded_path.is_absolute():
        return recorded_path.resolve() == actual.resolve()
    normalized = recorded_path.as_posix().lstrip("./")
    actual_parts = actual.resolve().parts
    recorded_parts = tuple(part for part in normalized.split("/") if part)
    return bool(recorded_parts) and actual_parts[-len(recorded_parts) :] == recorded_parts


def load_checkpoint(path: Path) -> tuple[Mapping[str, Any], Mapping[str, Any]]:
    """Load the actual frozen checkpoint and return safe metadata inputs."""
    try:
        import torch
    except ImportError as exc:  # pragma: no cover - depends on environment
        raise RuntimeError("T080 fail closed: torch is required") from exc
    raw = torch.load(path, map_location="cpu", weights_only=False)
    if not isinstance(raw, Mapping):
        raise RuntimeError("T080 fail closed: checkpoint is not a mapping")
    provenance = raw.get("training_data_provenance")
    if not isinstance(provenance, Mapping):
        raise RuntimeError("T080 fail closed: checkpoint training_data_provenance missing")
    return provenance, raw


def _stable(value: Any, where: str) -> dict[str, Any]:
    if value is None:
        return {"status": "missing", "identity": None}
    if not isinstance(value, Mapping):
        raise RuntimeError(f"T080 fail closed: invalid {where} identity")
    fields = ("action_id", "occurrence", "kind", "label", "stable_id")
    if any(value.get(field) is None for field in fields):
        raise RuntimeError(f"T080 fail closed: incomplete {where} identity")
    return {"status": "available", "identity": {field: value[field] for field in fields}}


def _load_trainer(path: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    metadata: dict[str, Any] | None = None
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, 1):
            try:
                item = json.loads(line)
            except json.JSONDecodeError as exc:
                raise RuntimeError(f"T080 fail closed: invalid trainer JSON line {line_number}") from exc
            if not isinstance(item, Mapping):
                raise RuntimeError(f"T080 fail closed: invalid trainer line {line_number}")
            if item.get("type") == "metadata" and isinstance(item.get("metadata"), Mapping):
                if metadata is not None:
                    raise RuntimeError("T080 fail closed: duplicate metadata wrapper")
                metadata = dict(item["metadata"])
            elif item.get("type") == "record" and isinstance(item.get("record"), Mapping):
                rows.append(dict(item["record"]))
            else:
                raise RuntimeError(f"T080 fail closed: invalid trainer line {line_number}")
    if metadata is None or len(rows) != 4 or metadata.get("record_count") != 4:
        raise RuntimeError("T080 fail closed: trainer must be metadata plus exactly 4 records")
    return metadata, rows


def _validate_provenance(provenance: Mapping[str, Any], trainer: Path, trainer_sha: str, trainer_bytes: int, metadata: Mapping[str, Any]) -> None:
    recorded_path = _required(_provenance_value(provenance, "trainer_input_path"), "trainer_input_path")
    if not _path_matches(str(recorded_path), trainer):
        raise RuntimeError("T080 fail closed: checkpoint trainer path mismatch")
    if _provenance_value(provenance, "trainer_input_sha256") != trainer_sha:
        raise RuntimeError("T080 fail closed: checkpoint trainer SHA-256 mismatch")
    if _provenance_value(provenance, "trainer_input_byte_count", "trainer_input_bytes") != trainer_bytes:
        raise RuntimeError("T080 fail closed: checkpoint trainer bytes mismatch")
    format_version = _provenance_value(provenance, "trainer_input_format_version", "format_version")
    if format_version is None:
        raise RuntimeError("T080 fail closed: checkpoint trainer format missing")
    if metadata.get("format_version") != format_version:
        raise RuntimeError("T080 fail closed: checkpoint trainer format mismatch")
    if _provenance_value(provenance, "trainer_record_count", "record_count") != 4:
        raise RuntimeError("T080 fail closed: checkpoint trainer record count mismatch")
    expected_id = f"trainer-input-sha256:{trainer_sha}"
    if provenance.get("trainer_input_artifact_id") != expected_id:
        raise RuntimeError("T080 fail closed: checkpoint trainer artifact id mismatch")


def classify(*, provenance: Mapping[str, Any], rows: list[dict[str, Any]], comparisons: list[dict[str, Any]]) -> tuple[str, dict[str, Any]]:
    proof = provenance.get("continuation_policy_proof")
    proof_available = isinstance(proof, Mapping) and proof.get("same_as_search_v2_leaf_continuation") is True
    divergent = sum(
        item["behavior_action"]["comparison"] == "different"
        for item in comparisons
    )
    behavior_available = sum(
        item["behavior_action"]["status"] == "available" for item in comparisons
    )
    outcome_available = sum(
        item["outcome"]["status"] == "available" for item in comparisons
    )
    evidence = {
        "alignment_criteria": [
            "source outcome continuation policy is explicitly proven identical to Search v2 leaf continuation",
            "Oracle policy target and value-label provenance are contractually compatible",
            "no available row contradicts that contract",
        ],
        "mismatch_criteria": [
            "value labels are realized source/behavior outcomes",
            "Search v2 consumes the value at hypothetical learned leaves",
            "Oracle policy targets are not the source continuation policy",
            "at least one stable teacher/behavior action divergence retains an outcome label",
        ],
        "evidence": {
            "continuation_policy_proof_available": proof_available,
            "behavior_available_rows": behavior_available,
            "divergent_rows": divergent,
            "outcome_available_rows": outcome_available,
            "all_behavior_unavailable": behavior_available == 0,
        },
    }
    if proof_available and divergent == 0:
        return "VALUE_TARGET_SEMANTICS_ALIGNED", evidence
    if not proof_available and behavior_available > 0 and divergent > 0 and outcome_available > 0:
        return "VALUE_TARGET_SEMANTIC_MISMATCH_CONFIRMED", evidence
    return "VALUE_TARGET_SEMANTICS_UNRESOLVED", evidence


def audit(checkpoint: Path, trainer: Path, checkpoint_loader: Callable[[Path], Any] = load_checkpoint) -> dict[str, Any]:
    checkpoint = Path(checkpoint).resolve()
    trainer = Path(trainer).resolve()
    checkpoint_sha, checkpoint_bytes = digest(checkpoint)
    if checkpoint_sha != CHECKPOINT_SHA:
        raise RuntimeError("T080 fail closed: checkpoint SHA-256 mismatch")
    loaded = checkpoint_loader(checkpoint)
    if isinstance(loaded, tuple) and len(loaded) == 2:
        provenance, raw_checkpoint = loaded
    else:
        provenance, raw_checkpoint = loaded, {}
    if not isinstance(provenance, Mapping):
        raise RuntimeError("T080 fail closed: invalid checkpoint provenance")
    trainer_sha, trainer_bytes = digest(trainer)
    metadata, rows = _load_trainer(trainer)
    _validate_provenance(provenance, trainer, trainer_sha, trainer_bytes, metadata)

    target_kinds = Counter(str(row.get("policy_target_kind", "unavailable")) for row in rows)
    target_sources = Counter(str(row.get("policy_target_source", "unavailable")) for row in rows)
    behavior_status = Counter(str(row.get("behavior_action_status", "unavailable")) for row in rows)
    outcome_status = Counter()
    comparisons: list[dict[str, Any]] = []
    strata: dict[str, Counter[str]] = defaultdict(Counter)
    source_ids = Counter()
    for row in rows:
        outcome = row.get("structured_battle_outcome", {}).get("battle_survived", {})
        if not isinstance(outcome, Mapping) or outcome.get("status") != "available" or not isinstance(outcome.get("value"), bool):
            outcome_view = {"status": "unavailable", "value": None}
            outcome_status["unavailable"] += 1
        else:
            outcome_view = {"status": "available", "value": outcome["value"]}
            outcome_status["survived" if outcome["value"] else "lost"] += 1
        teacher = _stable(row.get("policy_target_action_identity"), "teacher")
        if row.get("behavior_action_status") == "available":
            behavior_action = row.get("behavior_action")
            behavior_identity = behavior_action.get("action_identity") if isinstance(behavior_action, Mapping) else None
            behavior = _stable(behavior_identity, "behavior")
        else:
            behavior = {"status": str(row.get("behavior_action_status", "unavailable")), "identity": None}
        same = teacher["identity"] == behavior["identity"] if teacher["status"] == behavior["status"] == "available" else None
        comparison = "same" if same is True else "different" if same is False else "unavailable"
        source_metadata = row.get("source_metadata", {})
        source_id = source_metadata.get("source_checkpoint_id") or source_metadata.get("source_run_id")
        if source_id is not None:
            source_ids[str(source_id)] += 1
        item = {
            "example_index": row.get("example_index"),
            "teacher_target_action_identity": teacher,
            "behavior_action": {"status": behavior["status"], "action_identity": behavior["identity"], "comparison": comparison},
            "outcome": outcome_view,
        }
        comparisons.append(item)
        for key in STRATA:
            strata[f"{key}={source_metadata.get(key, 'unavailable')}"][f"comparison_{comparison}"] += 1
            strata[f"{key}={source_metadata.get(key, 'unavailable')}"][f"outcome_{outcome_view['status']}"] += 1
    classification, criteria = classify(provenance=provenance, rows=rows, comparisons=comparisons)

    report = {
        "schema_id": REPORT_SCHEMA,
        "classification": classification,
        "offline_only": True,
        "top_metadata": {
            "checkpoint_schema_id": raw_checkpoint.get("schema_id") if isinstance(raw_checkpoint, Mapping) else None,
            "checkpoint_format_version": raw_checkpoint.get("format_version") if isinstance(raw_checkpoint, Mapping) else None,
            "policy_target_kind": raw_checkpoint.get("policy_target_kind") if isinstance(raw_checkpoint, Mapping) else None,
            "outcome_target_kind": raw_checkpoint.get("outcome_target_kind", "terminal_battle_survival_probability") if isinstance(raw_checkpoint, Mapping) else "terminal_battle_survival_probability",
        },
        "checkpoint": {"path": str(checkpoint), "sha256": checkpoint_sha, "bytes": checkpoint_bytes, "expected_sha256": CHECKPOINT_SHA},
        "trainer_input": {
            "path": str(trainer), "sha256": trainer_sha, "bytes": trainer_bytes,
            "schema_id": metadata.get("policy_target_schema_id"), "format_version": metadata.get("format_version"),
            "record_schema_version": metadata.get("decision_record_schema_version"), "record_count": len(rows),
            "metadata_wrapper_count": 1, "provenance": _json_safe(provenance),
            "source_identity_counts": dict(sorted(source_ids.items())),
        },
        "target_lineage": {
            "policy_target_kind_counts": dict(sorted(target_kinds.items())),
            "policy_target_source_counts": dict(sorted(target_sources.items())),
            "behavior_action_status_counts": dict(sorted(behavior_status.items())),
            "outcome_target_kind": "terminal_battle_survival_probability",
            "source_outcome_field": "record.structured_battle_outcome.battle_survived",
            "outcome_status_counts": dict(sorted(outcome_status.items())),
        },
        "action_comparisons": comparisons,
        "strata": {key: dict(sorted(value.items())) for key, value in sorted(strata.items())},
        "static_call_chain": [
            {"path": "sim/oracle_teacher_search_guidance.py", "symbol": "_trainer_record_from_teacher_row", "role": "policy/outcome producer"},
            {"path": "sim/torch_policy_value.py", "symbol": "terminal_battle_survival_probability", "role": "value head target"},
            {"path": "sim/battle_search_v2.py", "symbol": "value_callback", "role": "learned leaf consumer", "boundary": "after_first_action_from_newly_expanded_node"},
        ],
        "classification_criteria": criteria,
        "unresolved": [
            "unavailable behavior actions are not inferred",
            "available artifacts do not prove source continuation policy equals Search v2 leaf continuation policy",
        ],
        "prohibited_actions": ["retraining", "Search/model/feature/simulator changes", "successor publication"],
    }
    json.dumps(report, allow_nan=False)
    return report


def _canonical(value: Mapping[str, Any]) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False) + "\n").encode()


def _manifest_self_hash(manifest: Mapping[str, Any]) -> str:
    clone = json.loads(json.dumps(manifest))
    self_entry = clone["files"][-1]
    self_entry["sha256"] = ""
    return hashlib.sha256(_canonical(clone)).hexdigest()


def write_outputs(report: dict[str, Any], output_root: Path, command: str) -> tuple[Path, Path]:
    output_root.mkdir(parents=True, exist_ok=True)
    report_path = output_root / f"{REPORT_SCHEMA}.json"
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    report_sha, report_bytes = digest(report_path)
    manifest_path = output_root / f"{MANIFEST_SCHEMA}.json"
    files = [{"path": str(report_path), "sha256": report_sha, "bytes": report_bytes, "schema_id": REPORT_SCHEMA, "provenance": "audit output", "regeneration": command, "retention": "immutable T080 evidence", "consumer": "T080 review", "deletion_condition": "after successor decision"}]
    manifest = {"schema_id": MANIFEST_SCHEMA, "format_version": 1, "self_hash_rule": "sha256(canonical JSON with this file entry sha256 blank and its final bytes value retained)", "files": files + [{"path": str(manifest_path), "sha256": "", "bytes": None, "schema_id": MANIFEST_SCHEMA, "provenance": "generated with report", "regeneration": command, "retention": "immutable T080 evidence", "consumer": "T080 review", "deletion_condition": "after successor decision"}]}
    # The self entry is a fixed point: its byte count is the final pretty-JSON
    # file size, while its digest is over canonical JSON with only sha256 blank.
    self_entry = manifest["files"][-1]
    self_entry["bytes"] = 0
    for _ in range(4):
        self_entry["bytes"] = len(json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False).encode() + b"\n")
        self_entry["sha256"] = "0" * 64
    self_entry["sha256"] = _manifest_self_hash(manifest)
    self_entry["bytes"] = len(json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False).encode() + b"\n")
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    json.loads(report_path.read_text(encoding="utf-8")); json.loads(manifest_path.read_text(encoding="utf-8"))
    return report_path, manifest_path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--trainer", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()
    report = audit(args.checkpoint, args.trainer)
    report_path, manifest_path = write_outputs(report, args.output_root, " ".join(__import__("sys").argv))
    print(json.dumps({"classification": report["classification"], "report": str(report_path), "manifest": str(manifest_path)}, sort_keys=True))


if __name__ == "__main__":
    main()
