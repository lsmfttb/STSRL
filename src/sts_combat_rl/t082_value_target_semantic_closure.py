"""Bounded, deterministic audit of the retained T064 target lineage."""
from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any
from types import SimpleNamespace
from sts_combat_rl.sim.source_identity import complete_source_identity, canonical_sha256, action_trace_identity_sha256

SCHEMA = "t082-value-target-semantic-closure-v1"
EXPECTED_INPUTS = {
    "t064-curriculum-manifest.json": ("a111e082d4bc11e03bc5b785a814c422619404245ddda55c2954be09dded46c7", "t064-curriculum-manifest-v1"),
    "t064-training-run-report.json": ("3e838bed72f5ca565532d39d77b1991e0d32919dcd9b1d6afe4d2c8f8ecdc38c", "t064-training-run-report-v1"),
    "t064-stage-summary.json": ("5748e79a23152fa51475f8cb7359c81816d6bbdd26ed2a10d7489f1853b6b880", "t064-stage-summary-v1"),
    "t064-transfer-decision.json": ("f8407acbc17cb13bba53009c91009fea961e7307071d54b0ff82147ff092603f", "t064-transfer-decision-v1"),
    "../t042-assisted-source-scale-pr39/runs1000_s20_workers16/scale-manifest.json": ("25efae30dc9a61c8b97cb09e1844b93b9ffe693bde51c0f494f0f65203a1d327", "t042-assisted-source-scale-manifest-v2"),
}
CLASSIFICATIONS = {"VALUE_TARGET_SEMANTIC_MISMATCH_CONFIRMED", "VALUE_TARGET_SEMANTICS_ALIGNED", "VALUE_TARGET_SEMANTICS_UNRESOLVED", "INCOMPLETE"}
EXPECTED_TEACHER_SHA = "1352eb301509f258ae92509b804125d59d2da17ef5f7f6e5b81131f11e1d0d72"
EXPECTED_TRAINER_SHA = "aae847505ece7c4d535d08cffc9e24bc2aaead334234332f41c69f0b2c99bada"


def semantic_proof() -> dict[str, Any]:
    """Return repository-backed proof of the three target consumers.

    Text checks are intentional: they keep this offline audit deterministic and
    make a semantic change visible without importing or executing training.
    """
    checks = {
        "policy_target_from_oracle": (
            Path(__file__).parent / "sim/oracle_teacher_search_guidance.py",
            "_trainer_record_from_teacher_row",
            "_policy_target_from_teacher_row",
        ),
        "value_target_from_source_outcome": (
            Path(__file__).parent / "sim/oracle_teacher_search_guidance.py",
            "_battle_survived",
            "source.battle_outcome",
        ),
        "search_v2_leaf_survival_consumer": (
            Path(__file__).parent / "sim/battle_search_v2.py",
            "value_callback",
            "battle_survival_probability",
        ),
    }
    proof: dict[str, Any] = {}
    for name, (module, symbol, evidence) in checks.items():
        path = module
        source = path.read_text(encoding="utf-8")
        verified = f"def {symbol}" in source and evidence in source
        proof[name] = {
            "verified": verified,
            "file": str(path),
            "symbol": symbol,
            "evidence": evidence,
            "source_sha256": hashlib.sha256(source.encode()).hexdigest(),
        }
    proof["continuation_alignment"] = {
        "verified": False,
        "status": "unavailable",
        "reason": "retained T064 provenance contains no same-continuation proof",
    }
    return proof

def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()

def _identity(action: Any) -> dict[str, Any] | None:
    if not isinstance(action, Mapping):
        return None
    if not isinstance(action.get("stable_id"), str) or not action["stable_id"]:
        return None
    if isinstance(action.get("occurrence"), bool) or not isinstance(action.get("occurrence"), int) or action["occurrence"] < 0:
        return None
    return dict(action)

def recover_behavior(current: Mapping[str, Any], successor: Mapping[str, Any] | None) -> dict[str, Any]:
    if successor is None:
        return {"status": "unavailable", "reason": "final/no immediate record", "successor_exists": False}
    before = current.get("action_trace", ())
    after = successor.get("action_trace", ())
    if not isinstance(before, list | tuple) or not isinstance(after, list | tuple):
        return {"status": "unavailable", "reason": "action trace unavailable"}
    try:
        action_trace_identity_sha256(SimpleNamespace(action_trace=before))
        action_trace_identity_sha256(SimpleNamespace(action_trace=after))
    except ValueError:
        return {"status": "unavailable", "reason": "unstable identity", "successor_exists": True}
    for key in ("source_run_id", "source_seed"):
        if key in current or key in successor:
            if successor.get(key) != current.get(key):
                return {"status": "unavailable", "reason": f"malformed/{key} linkage mismatch", "successor_exists": True}
    if "source_battle_index" in current or "source_battle_index" in successor:
        if successor.get("source_battle_index") != current.get("source_battle_index", -1) + 1:
            return {"status": "unavailable", "reason": "non-adjacent battle", "successor_exists": True}
    current_meta = current.get("structural_metadata", {})
    successor_meta = successor.get("structural_metadata", {})
    if isinstance(current_meta, Mapping) and isinstance(successor_meta, Mapping):
        if current_meta.get("assistance_level") != successor_meta.get("assistance_level"):
            return {"status": "unavailable", "reason": "malformed/component linkage mismatch", "successor_exists": True}
    before_ids = [_identity(item) for item in before]
    after_ids = [_identity(item) for item in after]
    if None in before_ids or None in after_ids:
        return {"status": "unavailable", "reason": "unstable identity", "successor_exists": True}
    if len(after_ids) <= len(before_ids) or after_ids[: len(before_ids)] != before_ids:
        return {"status": "unavailable", "reason": "non-prefix", "successor_exists": True}
    return {"status": "available", "identity": after_ids[len(before_ids)], "source_link_valid": True}

def _rows(path: Path) -> Iterable[dict[str, Any]]:
    with path.open(encoding="utf-8") as stream:
        for number, line in enumerate(stream, 1):
            item = json.loads(line)
            if not isinstance(item, Mapping):
                raise ValueError(f"invalid JSONL row {number}")
            if item.get("type") == "metadata":
                continue
            yield dict(item.get("record", item))

def _source_rows(path: Path) -> Iterable[dict[str, Any]]:
    """Stream only fields needed for T082, excluding raw snapshots/features."""
    if not path.exists():
        return
    keep = {"record_index", "source_checkpoint_id", "source_run_id", "source_seed", "source_battle_index", "action_trace", "battle_outcome", "checkpoint_information_regime", "distribution_kind", "structural_metadata", "source_battle_controller_provenance", "source_controller_provenance"}
    previous_index = -1
    with path.open(encoding="utf-8") as stream:
        for number, line in enumerate(stream, 1):
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                raise ValueError(f"malformed source JSON at {path}:{number}")
            if item.get("type") == "metadata":
                continue
            row = item.get("record", item)
            if not isinstance(row, Mapping):
                raise ValueError(f"malformed non-object source row {number}")
            index = row.get("record_index")
            if not isinstance(index, int) or index <= previous_index:
                raise ValueError(f"malformed or duplicate source record_index in {path}")
            previous_index = index
            yield {key: row[key] for key in keep if key in row}


def _safe_source_rows(path: Path) -> Iterable[dict[str, Any]]:
    try:
        yield from _source_rows(path)
    except (OSError, ValueError, TypeError, AttributeError, json.JSONDecodeError) as exc:
        yield {"_audit_source_error": str(exc)}

def _validate_pool(path: Path, expected: Mapping[str, Any], component: str) -> dict[str, Any]:
    digest = hashlib.sha256(); size = 0; count = 0; previous = -1; duplicate = False; schema = None; metadata = {}
    if not path.exists():
        return {"path": str(path), "component": component, "schema": None, "metadata": {}, "record_count": 0, "bytes": 0, "sha256": None, "expected": dict(expected), "valid": False, "ordering_valid": False, "reason": "missing artifact"}
    with path.open("rb") as stream:
        for raw in iter(lambda: stream.readline(), b""):
            digest.update(raw); size += len(raw)
            item = json.loads(raw)
            if not isinstance(item, Mapping):
                raise ValueError(f"malformed pool envelope row in {path}")
            if item.get("type") == "metadata":
                metadata = dict(item.get("metadata", {})); schema = metadata.get("schema_id")
                continue
            row = item.get("record", item)
            if not isinstance(row, Mapping) or not isinstance(row.get("structural_metadata"), Mapping) or row["structural_metadata"].get("assistance_level") != component:
                duplicate = True
                continue
            index = row.get("record_index")
            if not isinstance(index, int) or index <= previous: duplicate = True
            previous = index if isinstance(index, int) else previous; count += 1
            if row.get("structural_metadata", {}).get("assistance_level", component) != component:
                duplicate = True
    valid = (schema == expected.get("schema_id") and isinstance(metadata, Mapping) and metadata.get("record_count") == count and metadata.get("format_version") == expected.get("format_version") and metadata.get("assistance_level") == component and count == expected.get("record_count") and size == expected.get("bytes") and digest.hexdigest() == expected.get("sha256") and not duplicate)
    return {"path": str(path), "component": component, "schema": schema, "metadata": metadata, "record_count": count, "bytes": size, "sha256": digest.hexdigest(), "expected": dict(expected), "valid": valid, "ordering_valid": not duplicate}

def _record_identity(row: Mapping[str, Any], component: str) -> tuple[dict[str, Any], str]:
    metadata = dict(row.get("structural_metadata", {}))
    if metadata.get("assistance_level") != component:
        raise ValueError("source assistance_level is missing or does not match component")
    obj = SimpleNamespace(
        structural_metadata=metadata,
        action_trace=tuple(row.get("action_trace", ())),
        source_checkpoint_id=row.get("source_checkpoint_id"),
        source_seed=row.get("source_seed"), source_run_id=row.get("source_run_id"),
        source_battle_index=row.get("source_battle_index"),
        checkpoint_information_regime=row.get("checkpoint_information_regime"),
        distribution_kind=row.get("distribution_kind"),
    )
    identity = complete_source_identity(obj, source_arm="")
    return identity, identity["complete_identity_sha256"]

def _linkage_ok(item: Mapping[str, Any], teacher: Mapping[str, Any], trainer: Mapping[str, Any], index: int, record_index: int) -> tuple[bool, list[str]]:
    if not isinstance(item, Mapping) or not isinstance(teacher, Mapping) or not isinstance(trainer, Mapping):
        return False, ["non_mapping_linkage_record"]
    identity = item.get("complete_identity", {})
    teacher_metadata = teacher.get("structural_metadata", {})
    metadata = trainer.get("source_metadata", {})
    if not isinstance(identity, Mapping) or not isinstance(teacher_metadata, Mapping) or not isinstance(metadata, Mapping):
        return False, ["non_mapping_linkage_metadata"]
    checks = {
        "teacher_index": teacher.get("row_index") == index,
        "trainer_index": trainer.get("example_index") == index,
        "teacher_source": all(teacher.get(key) == identity.get(key) for key in ("source_checkpoint_id", "source_run_id", "source_seed", "source_battle_index")) and teacher.get("source_pool_record_index") == record_index,
        "teacher_shape": all(isinstance(teacher_metadata, Mapping) and teacher_metadata.get(key) == item.get(key) for key in ("act", "room_type", "encounter_id", "assistance_level")),
        "trainer_source": all(metadata.get(key) == identity.get(key) for key in ("source_checkpoint_id", "source_run_id", "source_seed", "source_battle_index")) and metadata.get("t064_complete_identity_sha256") == identity.get("complete_identity_sha256"),
        "trainer_shape": all(metadata.get(key) == item.get(key) for key in ("act", "room_type", "encounter_id", "assistance_level")),
        "policy_lineage": trainer.get("policy_target_kind") == "oracle_soft_visit_distribution" and trainer.get("policy_target_source") == "oracle_teacher_row.soft_visit_target",
    }
    return all(checks.values()), [name for name, valid in checks.items() if not valid]


def _controller_key(value: Any) -> str:
    if not isinstance(value, Mapping):
        return "unavailable"
    name = value.get("name", value.get("controller_name", "unavailable"))
    version = value.get("version", value.get("controller_version", "unavailable"))
    return f"{name}/{version}#{canonical_sha256(value)}"

def _load_envelope(path: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    metadata: dict[str, Any] | None = None
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as stream:
        for number, line in enumerate(stream, 1):
            item = json.loads(line)
            if item.get("type") == "metadata":
                metadata = dict(item.get("metadata", {}))
            elif item.get("type") == "record":
                rows.append(dict(item["record"]))
            else:
                raise ValueError(f"invalid envelope row {number}")
    if metadata is None:
        raise ValueError(f"missing metadata envelope: {path}")
    return metadata, rows

def _load_selected_envelope(path: Path, expected: int, index_field: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    metadata: dict[str, Any] | None = None
    rows: dict[int, dict[str, Any]] = {}
    expected_next = 0
    with path.open(encoding="utf-8") as stream:
        for number, line in enumerate(stream, 1):
            item = json.loads(line)
            if item.get("type") == "metadata":
                metadata = dict(item.get("metadata", {}))
            elif item.get("type") == "record":
                raw = item["record"]
                if not isinstance(raw, Mapping):
                    raise ValueError(f"record {number} is not an object")
                keep = {"row_index", "example_index", "source_checkpoint_id", "source_run_id", "source_seed", "source_battle_index", "source_pool_record_index", "teacher_action", "policy_target_action_identity", "policy_target_kind", "policy_target_source", "source_metadata", "structural_metadata", "controller_provenance", "raw_reward_components", "structured_battle_outcome", "behavior_action", "behavior_action_status"}
                row = {key: raw[key] for key in keep if key in raw}
                index = row.get(index_field)
                if not isinstance(index, int) or index != expected_next:
                    raise ValueError(f"missing or invalid {index_field}: row {number}")
                if isinstance(index, int) and 0 <= index < expected:
                    if index in rows: raise ValueError(f"duplicate {index_field}: {index}")
                    rows[index] = row
                    expected_next += 1
            else:
                raise ValueError(f"invalid envelope row {number}")
    if metadata is None or len(rows) != expected:
        raise ValueError(f"{path} does not contain exactly {expected} indexed rows")
    if metadata.get("record_count") != expected:
        raise ValueError(f"{path} metadata record_count is not {expected}")
    return metadata, [rows[index] for index in range(expected)]

def audit_t064(manifest_path: Path, output: Path, *, expected_rows: int = 460) -> dict[str, Any]:
    input_checks: list[dict[str, Any]] = []
    def incomplete(problem: str) -> dict[str, Any]:
        report = {"schema_version": SCHEMA, "qualification_mode": "formal_460" if expected_rows == 460 else "compact_non_qualifying", "execution": {"mode": "offline_streaming", "worker_count": 1, "reason": "non-simulator aggregation/single stream"}, "regeneration": {"command": f"PYTHONPATH=src python scripts/run_t082_value_target_semantic_closure.py --manifest {manifest_path} --output {output}"}, "inputs": {"manifest": {"path": str(manifest_path), "valid": False, "reason": problem}, "control_artifacts": input_checks, "pool_checks": [{"valid": False, "reason": "unavailable before pool read"}], "teacher": {"path": str(manifest_path.parent / "teacher/merged.jsonl"), "valid": False, "reason": "unavailable before teacher read"}, "trainer": {"path": str(manifest_path.parent / "trainer/trainer-input.jsonl"), "valid": False, "reason": "unavailable before trainer read"}, "terminal_case_valid": False}, "integrity": {"valid": False, "problems": [problem]}, "rows": []}
        report["regeneration"]["command"] = f"PYTHONPATH=src python scripts/run_t082_value_target_semantic_closure.py --manifest {manifest_path} --output {output}"
        report["inputs"]["pool_checks"] = [{"component": c, "observed": None, "valid": False, "reason": "unavailable before pool read"} for c in ("assist_0", "assist_hp50", "assist_hp50_potion_elite_boss", "assist_hp75_potion")]
        report["inputs"]["terminal"] = {"observed": None, "valid": False, "reason": "unavailable before decision read"}
        output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return report
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return incomplete(f"manifest unavailable: {exc}")
    for name, (expected_hash, schema) in EXPECTED_INPUTS.items():
        path = manifest_path.parent / name
        actual = sha256(path) if path.exists() else None
        try:
            document = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        except (OSError, json.JSONDecodeError) as exc:
            document = {"parse_error": str(exc)}
        input_checks.append({"name": name, "path": str(path), "expected_sha256": expected_hash, "sha256": actual, "schema": document.get("schema_id"), "expected_schema": schema, "valid": actual == expected_hash and document.get("schema_id") == schema})
    decision_path = manifest_path.parent / "t064-transfer-decision.json"
    try:
        decision = json.loads(decision_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        decision = {}
    terminal_valid = all(decision.get(key) is True for key in ("experiment_complete", "source_adequacy", "source_integrity_valid")) and decision.get("terminal_case") == "Case B"
    selected = manifest.get("selected_sources", []) if isinstance(manifest, Mapping) else []
    if len(selected) != expected_rows or any(not isinstance(item, Mapping) or not isinstance(item.get("complete_identity"), Mapping) or item.get("complete_identity", {}).get("schema_id") != "t064-complete-source-identity-v1" or not isinstance(item.get("complete_identity_sha256"), str) for item in selected):
        return incomplete(f"selected inventory does not contain exactly {expected_rows} valid rows")
    selected_hashes = [item["complete_identity_sha256"] for item in selected]
    selected_indexes = [(item.get("component"), item.get("source_record_index")) for item in selected]
    if len(set(selected_hashes)) != len(selected_hashes) or len(set(selected_indexes)) != len(selected_indexes):
        return incomplete("selected inventory contains duplicate identity hashes or component/index pairs")
    root = manifest_path.parent
    if not isinstance(manifest.get("input_artifacts"), Mapping):
        return incomplete("manifest input_artifacts is missing or not an object")
    teacher_path, trainer_path = root / "teacher/merged.jsonl", root / "trainer/trainer-input.jsonl"
    try:
        teacher_meta, teachers = _load_selected_envelope(teacher_path, expected_rows, "row_index")
        trainer_meta, trainers = _load_selected_envelope(trainer_path, expected_rows, "example_index")
    except (OSError, ValueError, TypeError, AttributeError, json.JSONDecodeError) as exc:
        return incomplete(f"teacher/trainer artifact unavailable or malformed: {exc}")
    input_checks.extend([
        {"name": "teacher", "sha256": sha256(teacher_path), "expected_sha256": EXPECTED_TEACHER_SHA, "schema": teacher_meta.get("artifact_schema_id"), "record_count": teacher_meta.get("record_count"), "controller_provenance": teacher_meta.get("controller_provenance"), "valid": (expected_rows != 460 or sha256(teacher_path) == EXPECTED_TEACHER_SHA) and teacher_meta.get("artifact_schema_id") == "oracle-search-teacher-v1" and teacher_meta.get("record_count") == expected_rows and isinstance(teacher_meta.get("controller_provenance"), Mapping) and teacher_meta["controller_provenance"].get("config", {}).get("information_regime") == "full_simulator_state_oracle_like" and teacher_meta["controller_provenance"].get("config", {}).get("search_budget", {}).get("simulations") == 100 and teacher_meta["controller_provenance"].get("config", {}).get("root_selection_rule") == "highest_mean" and teacher_meta["controller_provenance"].get("config", {}).get("include_potions") is False},
        {"name": "trainer", "sha256": sha256(trainer_path), "expected_sha256": EXPECTED_TRAINER_SHA, "schema": trainer_meta.get("format_version"), "record_count": trainer_meta.get("record_count"), "policy_target_schema_id": trainer_meta.get("policy_target_schema_id"), "policy_target_schema_version": trainer_meta.get("policy_target_schema_version"), "structured_battle_outcome_schema_id": trainer_meta.get("structured_battle_outcome_schema_id"), "structured_battle_outcome_schema_version": trainer_meta.get("structured_battle_outcome_schema_version"), "valid": (expected_rows != 460 or sha256(trainer_path) == EXPECTED_TRAINER_SHA) and trainer_meta.get("record_count") == expected_rows and trainer_meta.get("format_version") in (6, "6") and trainer_meta.get("policy_target_schema_id") == "trainer-policy-target-v1" and trainer_meta.get("policy_target_schema_version") == 1 and trainer_meta.get("structured_battle_outcome_schema_id") == "structured-battle-outcome-v1" and trainer_meta.get("structured_battle_outcome_schema_version") == 1},
    ])
    if len(teachers) != expected_rows or len(trainers) != expected_rows:
        return incomplete("teacher/trainer row count mismatch")
    by_component: defaultdict[str, set[int]] = defaultdict(set)
    for index, item in enumerate(selected): by_component[item["component"]].add(item["source_record_index"])
    pool_checks = []
    for component, spec in manifest["input_artifacts"].items():
        if component in by_component:
            if not isinstance(spec, Mapping) or not isinstance(spec.get("path"), str):
                pool_checks.append({"component": component, "valid": False, "reason": "malformed input artifact specification"})
                continue
            pool = Path(spec["path"].replace("D:\\", "/mnt/d/").replace("\\", "/"))
            try:
                pool_checks.append(_validate_pool(pool, spec, component))
            except (OSError, ValueError, TypeError, AttributeError, json.JSONDecodeError) as exc:
                pool_checks.append({"path": str(pool), "component": component, "valid": False, "reason": f"malformed artifact: {exc}"})
    coverage = Counter((item.get("act"), item.get("component")) for item in selected)
    found: dict[tuple[str, int], tuple[dict[str, Any], dict[str, Any] | None]] = {}
    source_reader_errors: list[str] = []
    for component, indexes in by_component.items():
        previous = None
        pool = Path(manifest["input_artifacts"][component]["path"].replace("D:\\", "/mnt/d/").replace("\\", "/"))
        if not pool.exists():
            continue
        for record in _safe_source_rows(pool):
            if "_audit_source_error" in record:
                source_reader_errors.append(f"{component}: {record['_audit_source_error']}")
                continue
            record_index = record.get("record_index")
            if record_index in indexes:
                found[(component, record_index)] = (record, None)
            if previous is not None and previous.get("record_index") in indexes:
                key = (component, previous["record_index"])
                if key in found: found[key] = (previous, record)
            previous = record
    rows = []
    row_problems: list[str] = []
    for index, item in enumerate(selected):
        component, record_index = item["component"], item["source_record_index"]
        source, successor = found.get((component, record_index), ({}, None))
        try: derived, derived_sha = _record_identity(source, component)
        except (ValueError, KeyError, TypeError, AttributeError) as exc: derived, derived_sha = {}, None; source_error = str(exc)
        else: source_error = None
        selected_identity = item.get("complete_identity")
        identity_ok = isinstance(selected_identity, Mapping) and selected_identity == derived and item.get("complete_identity_sha256") == derived_sha and selected_identity.get("complete_identity_sha256") == item.get("complete_identity_sha256")
        source_meta = source.get("structural_metadata", {}) if isinstance(source, Mapping) else {}
        selected_source_path = item.get("source_path")
        expected_path = str(manifest["input_artifacts"].get(component, {}).get("path", ""))
        path_ok = isinstance(selected_source_path, str) and selected_source_path == expected_path
        shape_ok = isinstance(source_meta, Mapping) and all(source_meta.get(key) == item.get(key) for key in ("act", "room_type", "encounter_id", "assistance_level"))
        behavior = recover_behavior(source, successor) if source else {"status": "unavailable", "reason": "source record missing"}
        teacher_action = _identity(teachers[index].get("teacher_action", {}).get("action_identity"))
        teacher_source = teachers[index].get("source_metadata", teachers[index].get("structural_metadata", {}))
        teacher_for_link = dict(teachers[index])
        teacher_for_link.update(teacher_source)
        linkage_valid, linkage_problems = _linkage_ok(item, teacher_for_link, trainers[index], index, record_index)
        trainer_meta = trainers[index].get("source_metadata", {})
        trainer_action = _identity(trainers[index].get("policy_target_action_identity"))
        trainer_action = _identity(trainers[index].get("policy_target_action_identity"))
        same = teacher_action == trainer_action
        comparison = "unavailable" if behavior.get("status") != "available" or teacher_action is None else "same" if behavior["identity"] == teacher_action else "different"
        outcome = source.get("battle_outcome")
        outcome_status = "available" if outcome in ("PLAYER_VICTORY", "PLAYER_DEFEAT") else "unavailable"
        rows.append({"index": index, "selected_identity": item["complete_identity"], "selected_identity_sha256": item.get("complete_identity_sha256"), "derived_identity_sha256": derived_sha, "identity_valid": identity_ok, "identity_error": source_error, "component": component, "source_record_index": record_index, "source_checkpoint_id": source.get("source_checkpoint_id"), "source_run_id": source.get("source_run_id"), "source_seed": source.get("source_seed"), "source_battle_index": source.get("source_battle_index"), "act": item.get("act"), "room_type": item.get("room_type"), "trace_length": len(source.get("action_trace", ())), "successor": {"record_index": successor.get("record_index"), "trace_length": len(successor.get("action_trace", ())), "battle_index": successor.get("source_battle_index")} if successor else None, "behavior": behavior, "teacher_action": teacher_action, "trainer_policy_action": trainer_action, "comparison": comparison, "outcome": outcome_status, "source_battle_outcome": outcome if isinstance(outcome, str) else None, "trainer_value_lineage": trainers[index].get("raw_reward_components", {}).get("battle_outcome"), "source_controller": source.get("source_battle_controller_provenance"), "teacher_controller": teachers[index].get("controller_provenance"), "policy_target_source": trainers[index].get("policy_target_source"), "value_target_source": "trainer_input_record.raw_reward_components.battle_outcome"})
        trainer_outcome = trainers[index].get("structured_battle_outcome", {}).get("battle_survived", {})
        try:
            successor_identity = _record_identity(successor, component)[0] if successor else None
        except (ValueError, KeyError, TypeError, AttributeError) as exc:
            successor_identity = None
            row_problems.append(f"row {index}: successor identity failure: {exc}")
        rows[-1].update({
            "selected_source_path": selected_source_path,
            "source_path_exact": path_ok,
            "source_shape_exact": shape_ok,
            "strict_prefix_validation": {"status": behavior.get("status"), "reason": behavior.get("reason"), "successor_exists": behavior.get("successor_exists", successor is not None)},
            "linkage_valid": linkage_valid, "linkage_problems": linkage_problems,
            "source_pool": {"component": component, "path": str(manifest["input_artifacts"][component]["path"]), "sha256": manifest["input_artifacts"][component].get("sha256")},
            "current_complete_identity": derived,
            "successor_complete_identity": successor_identity,
            "successor_exists": successor is not None,
            "successor_reason": behavior.get("reason"),
            "source_act": source.get("structural_metadata", {}).get("act"),
            "source_encounter": source.get("structural_metadata", {}).get("encounter_id"),
            "source_controller_provenance": source.get("source_controller_provenance"),
            "source_battle_controller_provenance": source.get("source_battle_controller_provenance"),
            "source_battle_outcome": outcome if isinstance(outcome, str) else "unavailable",
            "trainer_battle_survived": {"status": "available" if isinstance(trainer_outcome, Mapping) and "value" in trainer_outcome else "unavailable", "value": trainer_outcome.get("value") if isinstance(trainer_outcome, Mapping) else None},
            "outcome_consistency": "unavailable" if not isinstance(trainer_outcome, Mapping) or "value" not in trainer_outcome or outcome not in ("PLAYER_VICTORY", "PLAYER_DEFEAT") else "consistent" if ((outcome == "PLAYER_VICTORY") == bool(trainer_outcome["value"])) else "mismatch",
            "value_target_source": "trainer_input_record.structured_battle_outcome.battle_survived",
            "raw_reward_components_battle_outcome": trainers[index].get("raw_reward_components", {}).get("battle_outcome"),
        })
        rows[-1].pop("trainer_value_lineage", None)
        if not path_ok: row_problems.append(f"row {index}: selected source_path does not match pool path")
        if not shape_ok: row_problems.append(f"row {index}: source structural metadata does not match selected metadata")
        if teacher_action is None: row_problems.append(f"row {index}: teacher action identity missing or malformed")
        if not (isinstance(trainer_outcome, Mapping) and trainer_outcome.get("status") == "available" and isinstance(trainer_outcome.get("value"), bool)):
            row_problems.append(f"row {index}: structured battle-survived target unavailable or malformed")
    all_integrity = all(row["identity_valid"] and row["linkage_valid"] for row in rows) and all(item["valid"] for item in input_checks) and all(item["valid"] for item in pool_checks) and terminal_valid
    observed_acts = Counter(item.get("act") for item in selected)
    observed_components = Counter(item.get("component") for item in selected)
    coverage_valid = (expected_rows != 460) or (observed_acts == Counter({1: 256, 2: 204}) and observed_components == Counter({"assist_0": 256, "assist_hp50": 12, "assist_hp50_potion_elite_boss": 32, "assist_hp75_potion": 160}))
    all_integrity = all_integrity and coverage_valid
    divergent = [row for row in rows if row["comparison"] == "different"]
    row_problems.extend(source_reader_errors)
    row_problems.extend(f"row {row['index']}: {row['successor_reason']}" for row in rows if row.get("successor_reason") and not row["successor_reason"].startswith("final/"))
    row_problems.extend(f"row {row['index']}: outcome lineage mismatch" for row in rows if row.get("source_battle_outcome") not in ("unavailable", None) and row.get("trainer_battle_survived", {}).get("status") == "available" and ((row["source_battle_outcome"] == "PLAYER_VICTORY") != bool(row["trainer_battle_survived"].get("value"))))
    proof = semantic_proof()
    source_outcomes = Counter("survived" if row["source_battle_outcome"] == "PLAYER_VICTORY" else "lost" if row["source_battle_outcome"] == "PLAYER_DEFEAT" else "unavailable" for row in rows)
    divergent_outcomes = Counter("survived" if row["source_battle_outcome"] == "PLAYER_VICTORY" else "lost" if row["source_battle_outcome"] == "PLAYER_DEFEAT" else "unavailable" for row in divergent)
    trainer_outcomes = Counter("survived" if row.get("trainer_battle_survived", {}).get("status") == "available" and row["trainer_battle_survived"].get("value") is True else "lost" if row.get("trainer_battle_survived", {}).get("status") == "available" and row["trainer_battle_survived"].get("value") is False else "unavailable" for row in rows)
    divergent_trainer_outcomes = Counter("survived" if row.get("trainer_battle_survived", {}).get("status") == "available" and row["trainer_battle_survived"].get("value") is True else "lost" if row.get("trainer_battle_survived", {}).get("status") == "available" and row["trainer_battle_survived"].get("value") is False else "unavailable" for row in divergent)
    strata = {name: {str(key): value for key, value in Counter(((_controller_key(row[field]) if field == "source_battle_controller_provenance" else row[field]), row["comparison"]) for row in rows).items()} for name, field in (("act", "act"), ("room_type", "room_type"), ("component", "component"), ("source_battle_controller_provenance", "source_battle_controller_provenance"))}
    report = {"schema_version": SCHEMA, "qualification_mode": "formal_460" if expected_rows == 460 else "compact_non_qualifying", "execution": {"mode": "offline_streaming", "worker_count": 1, "reason": "non-simulator aggregation/single stream"}, "regeneration": {"command": f"python -m sts_combat_rl.t082_value_target_semantic_closure --manifest {manifest_path} --output {output}"}, "inputs": {"manifest": str(manifest_path), "manifest_sha256": sha256(manifest_path), "control_artifacts": input_checks, "pool_checks": pool_checks, "terminal_case_valid": terminal_valid, "teacher": {"path": str(teacher_path), "sha256": sha256(teacher_path)}, "trainer": {"path": str(trainer_path), "sha256": sha256(trainer_path)}, "source_components": {component: {"path": str(manifest["input_artifacts"][component]["path"]), "sha256": manifest["input_artifacts"][component].get("sha256")} for component in sorted(by_component)}}, "coverage": {"observed": {str(key): value for key, value in sorted(coverage.items())}, "expected_acts": {"1": 256, "2": 204}, "expected_components": {"assist_0": 256, "assist_hp50": 12, "assist_hp50_potion_elite_boss": 32, "assist_hp75_potion": 160}, "valid": coverage_valid}, "integrity": {"valid": all_integrity and not row_problems, "selected_teacher_trainer_counts": len(rows) == 460, "source_identity_valid": all(row["identity_valid"] for row in rows), "problems": row_problems + ([] if all_integrity else ["one or more identity, coverage, control-artifact, or terminal predicates failed"])}, "counts": {"total_rows": len(rows), "behavior_recoverable": sum(row["behavior"]["status"] == "available" for row in rows), "behavior_unavailable": sum(row["behavior"]["status"] != "available" for row in rows), "comparison_denominator": sum(row["comparison"] != "unavailable" for row in rows), "comparisons": dict(Counter(row["comparison"] for row in rows)), "divergence_rate": len(divergent) / max(1, sum(row["comparison"] != "unavailable" for row in rows)), "outcomes": dict(source_outcomes), "divergent_outcomes": dict(divergent_outcomes), "divergent_with_available_outcome": sum(row["source_battle_outcome"] in ("PLAYER_VICTORY", "PLAYER_DEFEAT") for row in divergent)}, "strata": strata, "classification": classify(integrity_valid=all_integrity and not row_problems, rows=rows, proof=proof), "semantic_proof": proof, "rows": rows}
    report["regeneration"]["command"] = f"PYTHONPATH=src python scripts/run_t082_value_target_semantic_closure.py --manifest {manifest_path} --output {output}"
    report["counts"]["trainer_value_labels"] = dict(trainer_outcomes)
    report["counts"]["divergent_trainer_value_labels"] = dict(divergent_trainer_outcomes)
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    report["regeneration"].update({"output_sha256": hashlib.sha256(rendered.encode()).hexdigest(), "output_size": len(rendered.encode())})
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report

def _join_successors(path: Path, selected: set[tuple[Any, ...]]) -> dict[tuple[Any, ...], dict[str, Any]]:
    found: dict[tuple[Any, ...], dict[str, Any]] = {}
    previous: dict[tuple[Any, ...], dict[str, Any]] = {}
    for row in _source_rows(path):
        key = (row.get("source_pool_sha256"), row.get("source_run_id"), row.get("source_seed"))
        prior = previous.get(key)
        if prior is not None and (prior.get("source_battle_index", -1) + 1 == row.get("source_battle_index")):
            try:
                identity = _record_identity(prior, path.stem)[1]
            except (ValueError, KeyError):
                identity = None
            if identity in selected:
                found[identity] = row
        previous[key] = row
    return found

def classify(*, integrity_valid: bool, rows: list[dict[str, Any]], proof: Mapping[str, Any]) -> str:
    if not integrity_valid:
        return "INCOMPLETE"
    divergent = [row for row in rows if row.get("comparison") == "different"]
    semantic = all(
        proof.get(key, {}).get("verified") is True
        for key in (
            "policy_target_from_oracle",
            "value_target_from_source_outcome",
            "search_v2_leaf_survival_consumer",
        )
    )
    aligned = proof.get("continuation_alignment", {}).get("verified") is True
    if semantic and not aligned and divergent and any(
        row.get("outcome") != "unavailable" for row in divergent
    ):
        return "VALUE_TARGET_SEMANTIC_MISMATCH_CONFIRMED"
    if semantic and aligned and not divergent:
        return "VALUE_TARGET_SEMANTICS_ALIGNED"
    return "VALUE_TARGET_SEMANTICS_UNRESOLVED"

def audit(selected: list[Mapping[str, Any]], teacher: list[Mapping[str, Any]], trainer: list[Mapping[str, Any]], source_path: Path, *, expected_rows: int = 460) -> dict[str, Any]:
    problems: list[str] = []
    integrity = len(selected) == len(teacher) == len(trainer) == expected_rows
    if not integrity:
        problems.append("selected/teacher/trainer row counts are not all 460")
    selected_keys = [row.get("complete_identity_sha256") or canonical_sha256(row.get("complete_identity", {})) for row in selected]
    if len(set(selected_keys)) != len(selected_keys):
        integrity = False; problems.append("selected source identities are duplicated")
    source_successors = _join_successors(source_path, set(selected_keys))
    rows: list[dict[str, Any]] = []
    strata: defaultdict[str, Counter[str]] = defaultdict(Counter)
    for index, (source, teach, train) in enumerate(zip(selected, teacher, trainer, strict=True)):
        successor = source_successors.get(selected_keys[index])
        behavior = recover_behavior(source, successor)
        teacher_id = _identity(teach.get("teacher_action") or teach.get("policy_target_action_identity"))
        comparison = "unavailable" if behavior.get("status") != "available" or teacher_id is None else "same" if behavior["identity"] == teacher_id else "different"
        outcome = train.get("battle_survived", train.get("structured_battle_outcome", {}).get("battle_survived"))
        outcome_status = "available" if isinstance(outcome, bool) else "unavailable"
        row = {"index": index, "source_identity": source.get("complete_identity"), "behavior": behavior, "teacher_action": teacher_id, "comparison": comparison, "outcome": outcome_status, "assistance_level": source.get("assistance_level"), "act": source.get("act"), "room_type": source.get("room_type"), "source_battle_controller": source.get("battle_controller_provenance")}
        rows.append(row)
        for key in ("act", "room_type", "assistance_level", "source_battle_controller"):
            strata[f"{key}={row.get(key, 'unavailable')}"][comparison] += 1
    classification = classify(integrity_valid=integrity, rows=rows, proof=semantic_proof())
    return {"schema_version": SCHEMA, "classification": classification, "integrity": {"valid": integrity, "problems": problems}, "counts": {"total_rows": len(rows), "behavior_recoverable": sum(row["behavior"]["status"] == "available" for row in rows), "behavior_unavailable": sum(row["behavior"]["status"] != "available" for row in rows), "comparisons": dict(Counter(row["comparison"] for row in rows)), "outcomes": dict(Counter(row["outcome"] for row in rows))}, "strata": {key: dict(sorted(value.items())) for key, value in sorted(strata.items())}, "rows": rows}

def main() -> None:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--selected", type=Path, required=True); parser.add_argument("--teacher", type=Path, required=True); parser.add_argument("--trainer", type=Path, required=True); parser.add_argument("--sources", type=Path, required=True); parser.add_argument("--output", type=Path, required=True)
    def load(path: Path) -> list[dict[str, Any]]: return list(_rows(path))
    report = audit(load(parser.parse_args().selected), load(parser.parse_args().teacher), load(parser.parse_args().trainer), parser.parse_args().sources)
    parser.parse_args().output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")

if __name__ == "__main__": main()
