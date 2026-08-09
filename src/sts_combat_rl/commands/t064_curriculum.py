"""T064 reuse-first curriculum manifest and source-audit workflow helpers."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
import hashlib
import json
from pathlib import Path
from typing import Any

from sts_combat_rl.sim.assisted_source_generation import (
    ASSISTED_SOURCE_POOL_FORMAT_VERSION,
    ASSISTED_SOURCE_POOL_SCHEMA_ID,
)
from sts_combat_rl.sim.battle_start_pool import (
    ASSISTED_RUN_DISTRIBUTION_KIND,
    BattleStartCheckpointRecord,
    NaturalBattleStartPool,
    record_from_manifest,
)
from sts_combat_rl.sim.fixed_evaluation_set import load_fixed_cohort_jsonl
from sts_combat_rl.sim.t064_curriculum import (
    BUCKETS,
    COMPACT_FILENAMES,
    CURRICULUM_MANIFEST_FILENAME,
    CURRICULUM_MANIFEST_SCHEMA_ID,
    T064_FORMAT_VERSION,
    TRAINING_RUN_ORDER,
    build_ordered_batch_plan,
    complete_source_identity,
    contiguous_ranges,
    select_curriculum_buckets,
    source_adequacy,
    source_descriptor,
    validate_exposure_parity,
    write_compact_json,
)


NATIVE_COMMIT = "fee272f1ae21c283ad2161f55293cfe6d714134a"


def build_curriculum_manifest(
    *,
    pool_paths: Mapping[str, Path],
    pool_sha256s: Mapping[str, str],
    scale_manifest_path: Path,
    scale_manifest_sha256: str,
    holdouts: Sequence[Mapping[str, Any]],
    initialization_checkpoint_path: Path,
    initialization_checkpoint_sha256: str,
    code_commit: str,
    output_path: Path,
) -> dict[str, Any]:
    """Verify frozen inputs and write the pre-teacher T064 curriculum manifest."""

    if output_path.name != CURRICULUM_MANIFEST_FILENAME:
        raise ValueError("T064 curriculum manifest path is frozen")
    input_artifacts = {
        "t042_scale_manifest": _identity(scale_manifest_path, scale_manifest_sha256),
        "initialization_checkpoint": _identity(
            initialization_checkpoint_path, initialization_checkpoint_sha256
        ),
    }
    descriptors: list[dict[str, Any]] = []
    for component in (
        "assist_0",
        "assist_hp50",
        "assist_hp50_potion_elite_boss",
        "assist_hp75_potion",
    ):
        path = pool_paths[component]
        input_artifacts[component] = _identity(path, pool_sha256s[component])
        metadata, rows = stream_assisted_pool_records(path, component=component)
        descriptors.extend(rows)
        input_artifacts[component].update(
            {
                "schema_id": metadata["schema_id"],
                "format_version": metadata["format_version"],
                "record_count": metadata["record_count"],
            }
        )

    holdout_artifacts: list[dict[str, Any]] = []
    holdout_identity_hashes: set[str] = set()
    for raw in holdouts:
        path = Path(raw["path"])
        artifact_identity = _identity(path, str(raw["sha256"]))
        with path.open("r", encoding="utf-8") as stream:
            cohort = load_fixed_cohort_jsonl(stream)
        expected_count = int(raw["record_count"])
        if len(cohort.records) != expected_count:
            raise ValueError("frozen holdout record count mismatch")
        record_identities = [
            complete_source_identity(record) for record in cohort.records
        ]
        hashes = [
            str(identity["complete_identity_sha256"]) for identity in record_identities
        ]
        if len(hashes) != len(set(hashes)):
            raise ValueError("frozen holdout contains duplicate complete identities")
        overlap = holdout_identity_hashes.intersection(hashes)
        if overlap:
            raise ValueError("frozen holdouts overlap each other")
        holdout_identity_hashes.update(hashes)
        artifact_identity.update(
            {
                "identity": raw.get("identity"),
                "record_count": expected_count,
                "complete_identity_sha256s": hashes,
            }
        )
        holdout_artifacts.append(artifact_identity)

    selected = select_curriculum_buckets(
        descriptors,
        holdout_identity_sha256s=holdout_identity_hashes,
    )
    selected_sources = [row for bucket in BUCKETS for row in selected[bucket]]
    duplicate_complete_identity_count = _duplicate_count(descriptors)
    holdout_overlap_count = sum(
        descriptor["complete_identity_sha256"] in holdout_identity_hashes
        for descriptor in descriptors
    )
    adequate = source_adequacy(
        selected,
        duplicate_complete_identity_count=duplicate_complete_identity_count,
        holdout_overlap_count=holdout_overlap_count,
    )
    plans = (
        [
            build_ordered_batch_plan(selected, seed=seed, arm=arm)
            for arm, seed in TRAINING_RUN_ORDER
        ]
        if adequate
        else []
    )
    if plans:
        validate_exposure_parity(plans)
    plan_summaries = [
        {key: value for key, value in plan.items() if key != "ordered_batches"}
        for plan in plans
    ]
    manifest = {
        "schema_id": CURRICULUM_MANIFEST_SCHEMA_ID,
        "format_version": T064_FORMAT_VERSION,
        "task_id": "T064",
        "code_commit": code_commit,
        "native_commit": NATIVE_COMMIT,
        "input_artifacts": input_artifacts,
        "frozen_holdouts": holdout_artifacts,
        "complete_source_audit": {
            "status": "static_complete_selected_restore_pending",
            "source_count": len(descriptors),
            "sources": descriptors,
            "duplicate_complete_identity_count": duplicate_complete_identity_count,
            "holdout_overlap_count": holdout_overlap_count,
        },
        "selected_buckets": selected,
        "selected_sources": selected_sources,
        "selected_bucket_counts": {bucket: len(selected[bucket]) for bucket in BUCKETS},
        "source_adequacy": adequate,
        "teacher_shard_ranges": list(contiguous_ranges(len(selected_sources))),
        "teacher_worker_count": 16,
        "batch_plans": plan_summaries,
        "batch_plan_status": "complete" if adequate else "not_run_source_inadequate",
        "exposure_parity": True if adequate else None,
        "t070_stage_manifest": None,
        "problems": [],
    }
    write_compact_json(output_path, manifest)
    return manifest


def stream_assisted_pool_records(
    path: Path, *, component: str
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Reuse the current record reader while retaining only compact descriptors."""

    metadata: dict[str, Any] | None = None
    descriptors: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as stream:
        for line_number, raw_line in enumerate(stream, start=1):
            if not raw_line.strip():
                continue
            row = json.loads(raw_line)
            if not isinstance(row, Mapping):
                raise ValueError(f"{path}:{line_number}: row must be an object")
            if row.get("type") == "metadata":
                if metadata is not None or not isinstance(row.get("metadata"), Mapping):
                    raise ValueError(
                        f"{path}:{line_number}: invalid duplicate metadata"
                    )
                metadata = dict(row["metadata"])
                if (
                    metadata.get("schema_id") != ASSISTED_SOURCE_POOL_SCHEMA_ID
                    or metadata.get("format_version")
                    != ASSISTED_SOURCE_POOL_FORMAT_VERSION
                    or metadata.get("assistance_level") != component
                ):
                    raise ValueError(f"{path}: incompatible assisted source metadata")
            elif row.get("type") == "record":
                if metadata is None or not isinstance(row.get("record"), Mapping):
                    raise ValueError(f"{path}:{line_number}: invalid record ordering")
                record = record_from_manifest(
                    row["record"],
                    label=f"{component} record {len(descriptors)}",
                    allowed_distribution_kinds=frozenset(
                        {ASSISTED_RUN_DISTRIBUTION_KIND}
                    ),
                    allow_assistance_history=True,
                )
                descriptors.append(
                    source_descriptor(
                        record,
                        component=component,
                        source_path=str(path),
                    )
                )
            else:
                raise ValueError(f"{path}:{line_number}: unknown row type")
    if metadata is None or metadata.get("record_count") != len(descriptors):
        raise ValueError(f"{path}: record count mismatch")
    return metadata, descriptors


def load_selected_source_pool(
    manifest: Mapping[str, Any],
) -> tuple[NaturalBattleStartPool, list[dict[str, Any]]]:
    """Load only manifest-selected records in the exact frozen order."""

    raw_selected = manifest.get("selected_sources")
    if not isinstance(raw_selected, list) or not raw_selected:
        raise ValueError("T064 manifest has no selected sources")
    selected = [dict(item) for item in raw_selected if isinstance(item, Mapping)]
    if len(selected) != len(raw_selected):
        raise ValueError("T064 selected source descriptor is invalid")
    wanted_by_path: dict[str, set[int]] = {}
    for item in selected:
        wanted_by_path.setdefault(str(item["source_path"]), set()).add(
            int(item["source_record_index"])
        )
    records_by_key: dict[tuple[str, int], BattleStartCheckpointRecord] = {}
    source_controller: dict[str, Any] | None = None
    for source_path, indices in wanted_by_path.items():
        path = Path(source_path)
        with path.open("r", encoding="utf-8") as stream:
            for raw_line in stream:
                row = json.loads(raw_line)
                if row.get("type") == "metadata":
                    metadata = row.get("metadata", {})
                    if source_controller is None:
                        source_controller = dict(
                            metadata.get("source_controller_provenance", {})
                        )
                    continue
                if row.get("type") != "record":
                    continue
                raw_record = row.get("record", {})
                index = raw_record.get("record_index")
                if index not in indices:
                    continue
                record = record_from_manifest(
                    raw_record,
                    label=f"selected record {source_path}:{index}",
                    allowed_distribution_kinds=frozenset(
                        {ASSISTED_RUN_DISTRIBUTION_KIND}
                    ),
                    allow_assistance_history=True,
                )
                records_by_key[(source_path, int(index))] = record
    ordered_records = [
        records_by_key[(str(item["source_path"]), int(item["source_record_index"]))]
        for item in selected
    ]
    pool = NaturalBattleStartPool(
        source_run_count=4000,
        terminal_run_count=4000,
        truncated_run_count=0,
        source_controller_provenance=source_controller or {},
        records=ordered_records,
    )
    return pool, selected


def finalize_source_audit(
    *,
    manifest_path: Path,
    restore_results: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Bind fresh selected-source restore results into the sole curriculum manifest."""

    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    selected = payload.get("selected_sources")
    if not isinstance(selected, list) or len(selected) != len(restore_results):
        raise ValueError("T064 restore audit cardinality mismatch")
    failures: list[str] = []
    for descriptor, result in zip(selected, restore_results, strict=True):
        if result.get("complete_identity_sha256") != descriptor.get(
            "complete_identity_sha256"
        ):
            raise ValueError("T064 restore audit source order mismatch")
        descriptor["fresh_restore_status"] = result.get("status")
        if result.get("status") != "passed":
            failure = str(result.get("problem") or "unknown restore failure")
            descriptor.setdefault("exclusion_reasons", []).append(
                "fresh_restore_or_context_mismatch"
            )
            failures.append(failure)
    payload["complete_source_audit"].update(
        {
            "status": "complete" if not failures else "failed",
            "selected_restore_count": len(restore_results),
            "selected_restore_failure_count": len(failures),
            "selected_restore_failures": failures,
        }
    )
    payload["problems"] = failures
    write_compact_json(manifest_path, payload)
    return payload


def assert_only_four_compact_paths(root: Path) -> None:
    unexpected = [
        path.name
        for path in root.glob("t064-*.json")
        if path.name not in COMPACT_FILENAMES
    ]
    if unexpected:
        raise ValueError(f"unauthorized T064 compact JSON paths: {unexpected}")


def _identity(path: Path, expected_sha256: str) -> dict[str, Any]:
    if not path.is_file():
        raise ValueError(f"required T064 input is missing: {path}")
    digest = _sha256(path)
    if digest != expected_sha256:
        raise ValueError(f"required T064 input hash mismatch: {path}")
    return {"path": str(path), "sha256": digest, "bytes": path.stat().st_size}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _duplicate_count(descriptors: Iterable[Mapping[str, Any]]) -> int:
    counts = Counter(str(item.get("complete_identity_sha256")) for item in descriptors)
    return sum(value - 1 for value in counts.values() if value > 1)
