#!/usr/bin/env python3
"""Collect the bounded T084 native internal-leaf candidate pool.

This is the executable native collection stage, not successor generation or
training.  It restores the exact T064 roots by their accepted seed/action
traces, runs each of the three frozen Search v2 arms for 100 simulations, and
retains the callback-boundary provenance emitted by the T084 native surface.
The selected-leaf replay is a second pass in this same executable: the first
pass retains an occupancy pool, then selected occurrence keys are replayed and
their callback-boundary checkpoints are consumed immediately for continuation
targets.  No process-local checkpoint from the first pass is serialized or
used by the second pass.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import multiprocessing
import os
import subprocess
import sys
import tempfile
import time
from collections import Counter
from collections.abc import Iterable, Mapping
from concurrent.futures import FIRST_COMPLETED, ProcessPoolExecutor, wait
from datetime import UTC, datetime
from heapq import heappop, heappush
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from sts_combat_rl.sim.action_space import ActionSpaceConfig
from sts_combat_rl.sim.assisted_source_generation import (
    ASSISTED_RUN_DISTRIBUTION_KIND,
    restore_assisted_battle_start_record,
)
from sts_combat_rl.sim.battle_start_pool import (
    record_from_manifest,
)
from sts_combat_rl.sim.contract import SimulatorAction
from sts_combat_rl.sim.controlled_run import build_decision_context
from sts_combat_rl.sim.lightspeed import LightSpeedAdapter
from sts_combat_rl.sim.public_context_model_input import (
    PUBLIC_CONTEXT_MODEL_INPUT_FEATURE_SIZE,
    PUBLIC_CONTEXT_MODEL_INPUT_SCHEMA_ID,
    PUBLIC_CONTEXT_MODEL_INPUT_SCHEMA_VERSION,
    public_context_features,
)
from sts_combat_rl.t084_search_v2_internal_leaf_target_generation import (
    ARMS,
    CALIBRATION_COUNT,
    CALIBRATION_REPLICATES,
    CANDIDATE_REPETITIONS,
    COLLECTOR_SCHEMA_ID,
    EXPECTED_STATIC_CHECKPOINTS,
    EXPECTED_T064_ARTIFACTS,
    PUBLIC_MODEL_INPUT_SCHEMA_ID,
    PUBLIC_MODEL_INPUT_SCHEMA_VERSION,
    PUBLIC_TACTICAL_FEATURE_SCHEMA_ID,
    PUBLIC_TACTICAL_FEATURE_SCHEMA_VERSION,
    WORKER_COUNT,
    derive_replicate_seed,
    select_repetition_count,
    sha256_file,
    validate_replicate,
)

PROGRESS_SCHEMA_ID = "t084-native-collector-progress-v1"
PROGRESS_TASK_SCHEMA_ID = "t084-native-collector-progress-task-v1"
PROGRESS_SCHEMA_VERSION = 1

_ROOT_ROWS: list[dict[str, Any]] = []
_NATIVE_COMMIT = ""
_NATIVE_MODULE: Any | None = None
_SCORERS: dict[str, Any] = {}
_CHECKPOINT_PATHS: dict[str, str] = {}
_PASS_MODE = "candidate"
_TARGET_SPECS: dict[str, dict[str, Any]] = {}
_SELECTION_POLICY = "canonical-hidden-payload-v1-root-first-hash-v1"


def _validate_worker_count(value: object) -> int:
    """Validate the bounded native worker range without changing the default."""

    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or not 1 <= value <= WORKER_COUNT
    ):
        raise ValueError(f"workers must be an integer in the range 1..{WORKER_COUNT}")
    return value


def _worker_count_argument(value: str) -> int:
    try:
        return _validate_worker_count(int(value))
    except (TypeError, ValueError) as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc


def _iter_json_values(path: Path) -> Iterable[object]:
    """Stream concatenated JSON values, including very long retained rows."""

    decoder = json.JSONDecoder()
    buffer = ""
    eof = False
    with path.open("r", encoding="utf-8", buffering=4 * 1024 * 1024) as stream:
        while True:
            if not eof:
                chunk = stream.read(4 * 1024 * 1024)
                if chunk:
                    buffer += chunk
                else:
                    eof = True
            position = 0
            while True:
                while position < len(buffer) and buffer[position].isspace():
                    position += 1
                if position == len(buffer):
                    buffer = ""
                    break
                try:
                    value, end = decoder.raw_decode(buffer, position)
                except json.JSONDecodeError:
                    if eof:
                        raise ValueError(f"{path}: truncated or invalid JSON value")
                    buffer = buffer[position:]
                    break
                yield value
                position = end
            if eof and not buffer:
                return


def _iter_selected_record_lines(
    path: Path, selected_indices: set[int]
) -> Iterable[tuple[int, Mapping[str, Any]]]:
    """Scan accepted JSONL bytes but decode only the bounded selected rows."""

    found: set[int] = set()
    record_index = -1
    with path.open("rb", buffering=4 * 1024 * 1024) as stream:
        for line in stream:
            if b'"type": "record"' not in line:
                continue
            record_index += 1
            if record_index not in selected_indices:
                continue
            value = json.loads(line)
            if not isinstance(value, Mapping) or value.get("type") != "record":
                raise ValueError(f"{path}: selected record line is malformed")
            record = value.get("record")
            if not isinstance(record, Mapping):
                raise TypeError(f"{path}: selected record payload is malformed")
            found.add(record_index)
            yield record_index, record
            if found == selected_indices:
                return


def _source_path(raw: str) -> Path:
    return Path(raw.replace("D:\\", "/mnt/d/").replace("\\", "/"))


def _load_selected_roots(manifest_path: Path) -> list[dict[str, Any]]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    selected = manifest.get("selected_sources")
    if not isinstance(selected, list) or len(selected) != 460:
        raise ValueError("T064 manifest must contain exactly 460 selected sources")
    wanted: dict[Path, set[int]] = {}
    for row in selected:
        if not isinstance(row, Mapping):
            raise TypeError("T064 selected source row is malformed")
        path = _source_path(str(row["source_path"]))
        wanted.setdefault(path, set()).add(int(row["source_record_index"]))

    found: dict[tuple[Path, int], dict[str, Any]] = {}
    wanted_count = sum(len(items) for items in wanted.values())
    for path, indexes in wanted.items():
        for record_index, record in _iter_selected_record_lines(path, indexes):
            selected_identity = next(
                item["complete_identity_sha256"]
                for item in selected
                if _source_path(str(item["source_path"])) == path
                and int(item["source_record_index"]) == record_index
            )
            found[(path, record_index)] = {
                **dict(record),
                "_t084_source_identity": selected_identity,
            }
        if len(found) >= wanted_count:
            break
    roots: list[dict[str, Any]] = []
    for selected_row in selected:
        path = _source_path(str(selected_row["source_path"]))
        index = int(selected_row["source_record_index"])
        raw = found.get((path, index))
        if raw is None:
            raise ValueError(f"missing selected T064 source record: {path}:{index}")
        roots.append(raw)
    return roots


def _native_actions(raw_actions: object) -> list[SimulatorAction]:
    if not isinstance(raw_actions, list):
        raise TypeError("native callback legal actions are not a list")
    actions: list[SimulatorAction] = []
    for index, raw in enumerate(raw_actions):
        if not isinstance(raw, Mapping):
            raise TypeError(f"native callback action {index} is malformed")
        scope, bits, kind = raw.get("scope"), raw.get("bits"), raw.get("kind")
        if (
            not isinstance(scope, str)
            or not isinstance(bits, int)
            or not isinstance(kind, str)
        ):
            raise TypeError(f"native callback action {index} lacks identity fields")
        actions.append(
            SimulatorAction(
                action_id=f"{scope}:{bits}",
                label=str(raw.get("label", "")),
                kind=kind,
                raw={
                    "scope": scope,
                    "bits": bits,
                    "idx1": raw.get("idx1"),
                    "idx2": raw.get("idx2"),
                    "idx3": raw.get("idx3"),
                },
            )
        )
    if not actions:
        raise ValueError("native callback exposed no legal actions")
    return actions


def _public_input(
    raw: Mapping[str, Any], actions: list[SimulatorAction], context: Any
) -> dict[str, Any]:
    del raw, actions
    snapshot_features = [float(value) for value in context.snapshot_features]
    action_features = [
        [float(value) for value in row] for row in context.legal_action_features
    ]
    context_features = public_context_features(context.public_run_context)
    state_features = snapshot_features + context_features
    action_widths = {len(row) for row in action_features}
    if len(action_widths) > 1:
        raise ValueError("native callback public action features have mixed widths")
    action_feature_size = next(iter(action_widths), 0)
    return {
        "schema_id": PUBLIC_MODEL_INPUT_SCHEMA_ID,
        "schema_version": PUBLIC_MODEL_INPUT_SCHEMA_VERSION,
        "feature_schema_id": PUBLIC_TACTICAL_FEATURE_SCHEMA_ID,
        "feature_schema_version": PUBLIC_TACTICAL_FEATURE_SCHEMA_VERSION,
        "snapshot_features": snapshot_features,
        "public_context_features": context_features,
        "state_features": state_features,
        "legal_action_features": action_features,
        "eligible_action_indices": [
            int(index) for index in context.eligible_action_indices
        ],
        "public_context_feature_schema_id": PUBLIC_CONTEXT_MODEL_INPUT_SCHEMA_ID,
        "public_context_feature_schema_version": PUBLIC_CONTEXT_MODEL_INPUT_SCHEMA_VERSION,
        "public_context_feature_size": PUBLIC_CONTEXT_MODEL_INPUT_FEATURE_SIZE,
        "shape": {
            "snapshot_features": [len(snapshot_features)],
            "public_context_features": [len(context_features)],
            "state_features": [len(state_features)],
            "legal_action_features": [len(action_features), action_feature_size],
        },
        "hidden_state_excluded": True,
    }


def _scorer_for_arm(arm: str) -> Any | None:
    if arm == ARMS[0]:
        return None
    scorer = _SCORERS.get(arm)
    if scorer is None:
        from sts_combat_rl.sim.torch_policy_value import (
            TorchPolicyValueGuidanceScorer,
        )

        path = _CHECKPOINT_PATHS[arm]
        scorer = TorchPolicyValueGuidanceScorer.from_checkpoint_path(path)
        _SCORERS[arm] = scorer
    return scorer


def _native_policy_prior_scores(scorer: Any, context: Any) -> list[float]:
    """Adapt the public SearchGuidance scorer result to native prior scores."""

    result = scorer.score_decision_context(context)
    action_scores = getattr(result, "action_scores", None)
    if not isinstance(action_scores, list):
        raise TypeError("search guidance result action_scores must be a list")
    legal_action_count = len(context.legal_action_features)
    if len(action_scores) != legal_action_count:
        raise ValueError(
            "search guidance action score count "
            f"{len(action_scores)} does not match native legal action count "
            f"{legal_action_count}"
        )
    scores_by_index: dict[int, float] = {}
    for action_score in action_scores:
        index = getattr(action_score, "legal_action_index", None)
        if not isinstance(index, int) or index < 0 or index >= legal_action_count:
            raise ValueError("search guidance action score index is invalid")
        if index in scores_by_index:
            raise ValueError(
                f"search guidance has duplicate action score index {index}"
            )
        try:
            probability = float(action_score.policy_probability)
        except (AttributeError, TypeError, ValueError) as exc:
            raise ValueError(
                "search guidance action score probability is invalid"
            ) from exc
        if not math.isfinite(probability) or not 0.0 <= probability <= 1.0:
            raise ValueError(
                "search guidance action score probability must be finite in [0, 1]"
            )
        scores_by_index[index] = probability
    if set(scores_by_index) != set(range(legal_action_count)):
        raise ValueError("search guidance action scores do not cover legal actions")
    return [scores_by_index[index] for index in range(legal_action_count)]


def _work_one(task: tuple[int, str]) -> dict[str, Any]:
    root_index, arm = task
    started = time.monotonic()
    root_raw = _ROOT_ROWS[root_index]
    root = record_from_manifest(
        root_raw,
        label=f"T084 root {root_index}",
        allowed_distribution_kinds=frozenset({ASSISTED_RUN_DISTRIBUTION_KIND}),
        allow_assistance_history=True,
    )
    adapter = LightSpeedAdapter(
        seed=root.source_seed,
        ascension=int(root.snapshot_raw.get("ascension", 20)),
        module=_NATIVE_MODULE,
    )
    snapshot, restoration_method = restore_assisted_battle_start_record(adapter, root)
    source_identity = str(root_raw.get("_t084_source_identity", ""))
    if not source_identity:
        source_identity = hashlib.sha256(
            json.dumps(root_raw, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
    candidates: list[dict[str, Any]] = []
    target_rows: list[dict[str, Any]] = []
    consumed_target_ids: set[str] = set()
    callback_count = 0
    scorer = _scorer_for_arm(arm)

    def policy_callback(raw: object, native_actions: object) -> list[float]:
        if scorer is None:
            raise AssertionError("unguided arm must not invoke a policy callback")
        actions = _native_actions(native_actions)
        if not isinstance(raw, Mapping):
            raise TypeError("native policy callback snapshot is malformed")
        context = build_decision_context(
            raw,
            actions,
            ActionSpaceConfig.initial_no_potions(),
            public_run_context=root.public_run_context,
        )
        return _native_policy_prior_scores(scorer, context)

    def collect(
        checkpoint: object,
        raw: object,
        native_actions: object,
        depth: int,
        ordinal: int,
        path_fingerprint: str,
        digest: str,
        payload: str,
        rng: object,
    ) -> None:
        nonlocal callback_count
        callback_count += 1
        if not isinstance(raw, Mapping) or not isinstance(rng, Mapping):
            raise TypeError("native collector callback omitted structured state/RNG")
        if not isinstance(payload, str) or not payload:
            raise ValueError(
                "native collector callback omitted canonical hidden payload"
            )
        actions = _native_actions(native_actions)
        context = build_decision_context(
            raw,
            actions,
            ActionSpaceConfig.initial_no_potions(),
            public_run_context=root.public_run_context,
        )
        payload_value: object = payload
        try:
            decoded = json.loads(payload)
        except (TypeError, json.JSONDecodeError):
            decoded = None
        if isinstance(decoded, Mapping):
            payload_value = dict(decoded)
        # The native canonical payload is the formal hidden-state identity.  The
        # native digest is only an index; validate_collector_execution performs
        # the digest-bucket collision check.  Ordinal/path remain occupancy
        # provenance and must not create independent formal states.
        leaf_identity = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        exact_identity = f"t084-hidden-state-{leaf_identity}"
        occurrence_seed = "|".join(
            (source_identity, arm, digest, str(ordinal), path_fingerprint)
        )
        occurrence_key = hashlib.sha256(occurrence_seed.encode()).hexdigest()
        base_row = {
            "sampling_arm": arm,
            "act": int(raw.get("act", root.snapshot_raw.get("act", 0))),
            "root_identity": source_identity,
            "exact_leaf_identity": exact_identity,
            "exact_hidden_state_payload": {
                "canonical_native_payload": payload_value,
                "canonical_native_payload_json": payload,
                "identity_definition": "sha256(canonical_native_payload UTF-8 bytes)",
                "occupancy_duplicate": False,
                "retention_boundary": "opaque native checkpoint captured at callback boundary",
                "restoration_status": "candidate_only_until_selected",
            },
            "exact_state_digest": digest,
            "public_projection": dict(raw),
            "public_model_input": _public_input(raw, actions, context),
            "legal_actions": [
                {"stable_id": action.action_id, "occurrence": index}
                for index, action in enumerate(actions)
            ],
            "source_complete_identity_sha256": source_identity,
            "depth": depth,
            "callback_ordinal": ordinal,
            "path_fingerprint": path_fingerprint,
            "occurrence_key": occurrence_key,
            "occupancy": {
                "native_digest_index": digest,
                "callback_ordinal": ordinal,
                "path_fingerprint": path_fingerprint,
            },
            "rng_provenance": dict(rng),
        }
        if _PASS_MODE == "candidate":
            candidates.append(base_row)
            return
        target_spec = _selected_target_for_occurrence(
            _TARGET_SPECS, exact_identity, occurrence_key, consumed_target_ids
        )
        if target_spec is None:
            return
        consumed_target_ids.add(exact_identity)
        base_row["exact_hidden_state_payload"]["restoration_status"] = (
            "consumed_in_callback_for_continuation_replicates"
        )
        replicates: list[dict[str, Any]] = []
        for replicate_index in range(1, 257):
            seed_provenance = derive_replicate_seed(
                _NATIVE_COMMIT,
                source_identity,
                arm,
                exact_identity,
                replicate_index,
            )
            continuation = adapter.evaluate_leaf_continuation(
                checkpoint,
                search_action_seed=seed_provenance["seed"],
                max_transitions=2048,
                include_potions=False,
            )
            replicates.append(
                {
                    **dict(continuation),
                    "replicate_index": replicate_index,
                    "seed_provenance": seed_provenance,
                    "terminal": continuation.get("terminal") is True,
                    "cap_hit": continuation.get("cap_hit") is True,
                    "transition_count": continuation.get("transition_count"),
                    "terminal_evaluate_end_state": continuation.get(
                        "terminal_evaluate_end_state"
                    ),
                }
            )
        base_row["target_kind"] = target_spec["target_kind"]
        base_row["replicates"] = replicates
        base_row["selected_repetition_count"] = 256
        target_rows.append(base_row)

    result = adapter.battle_search_v2_with_leaf_collection(
        snapshot,
        simulations=100,
        include_potions=False,
        policy_prior_callback=policy_callback if scorer is not None else None,
        collector_config={
            "schema_id": COLLECTOR_SCHEMA_ID,
            "sampling_arm": arm,
            "native_commit": _NATIVE_COMMIT,
        },
        leaf_collector_callback=collect,
    )
    row = {
        "worker_pid": os.getpid(),
        "sampling_arm": arm,
        "root_index": root_index,
        "source_root_index": root_raw.get("_t084_parity_source_index", root_index),
        "root_identity": source_identity,
        "source_complete_identity_sha256": source_identity,
        "simulations": 100,
        "status": "complete",
        "restoration_method": restoration_method,
        "candidate_count": callback_count,
        "root_action": result.get("root_action"),
        "root_statistics": result.get("root_rows"),
        "native_root_statistics": result.get("root_rows"),
        "candidate_rows": candidates,
        "target_rows": target_rows,
        "native_commit": _NATIVE_COMMIT,
        "wall_clock_seconds": time.monotonic() - started,
    }
    return row


def _worker_init(
    roots: list[dict[str, Any]],
    native_commit: str,
    checkpoint_paths: dict[str, str],
    pass_mode: str,
    target_specs: dict[str, dict[str, Any]],
) -> None:
    global _ROOT_ROWS, _NATIVE_COMMIT, _NATIVE_MODULE, _CHECKPOINT_PATHS
    global _PASS_MODE, _TARGET_SPECS
    _ROOT_ROWS = roots
    _NATIVE_COMMIT = native_commit
    _CHECKPOINT_PATHS = checkpoint_paths
    _PASS_MODE = pass_mode
    _TARGET_SPECS = target_specs
    import slaythespire

    _NATIVE_MODULE = slaythespire


def _timestamp() -> str:
    return datetime.now(UTC).isoformat()


def _json_bytes(value: object) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n").encode(
        "utf-8"
    )


def _canonical_json_digest(value: object) -> str:
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _atomic_write_json(path: Path, value: object) -> None:
    """Write one JSON document with a same-directory atomic replace."""

    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_fd, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent)
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(temporary_fd, "wb") as stream:
            stream.write(_json_bytes(value))
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        try:
            directory_fd = os.open(path.parent, os.O_RDONLY)
        except OSError:
            directory_fd = None
        if directory_fd is not None:
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
    finally:
        if temporary.exists():
            temporary.unlink()


def _write_json(path: Path, value: object) -> None:
    _atomic_write_json(path, value)


def _task_key(task: tuple[int, str]) -> str:
    root_index, arm = task
    return f"root-{int(root_index):04d}-{arm}"


def _task_descriptor(task: tuple[int, str]) -> dict[str, Any]:
    root_index, arm = task
    return {"root_index": int(root_index), "sampling_arm": str(arm)}


def _validate_task_result(result: object, task: tuple[int, str]) -> dict[str, Any]:
    if not isinstance(result, Mapping):
        raise TypeError("worker result must be a mapping")
    expected = _task_descriptor(task)
    if result.get("root_index") != expected["root_index"]:
        raise ValueError("worker result root index does not match task")
    if result.get("sampling_arm") != expected["sampling_arm"]:
        raise ValueError("worker result sampling arm does not match task")
    return dict(result)


def _error_payload(exc: BaseException) -> dict[str, str]:
    return {
        "type": type(exc).__name__,
        "message": str(exc)[:2000],
    }


class _ProgressStore:
    """Atomic, fail-closed index for resumable T084 task results."""

    def __init__(
        self,
        path: Path,
        *,
        identity: Mapping[str, Any],
        configuration: Mapping[str, Any],
        output_path: Path,
        resume: bool,
    ) -> None:
        self.path = path.resolve()
        self.parts_directory = self.path.with_name(f"{self.path.stem}.parts").resolve()
        self.output_path = output_path.resolve()
        if resume:
            if not self.path.is_file():
                raise ValueError(f"resume progress file is missing: {self.path}")
            try:
                raw = json.loads(self.path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                raise ValueError(
                    f"resume progress file is unreadable: {self.path}"
                ) from exc
            if not isinstance(raw, Mapping):
                raise TypeError("resume progress document must be a JSON object")
            self.document = dict(raw)
            self._validate_document(identity, configuration)
            self._recover_or_validate_final_output()
        else:
            if self.path.exists():
                raise ValueError(
                    f"progress already exists; use --resume or choose a new path: {self.path}"
                )
            if self.output_path.exists():
                raise ValueError(
                    f"output already exists; use the matching --resume run: {self.output_path}"
                )
            self.document = {
                "schema_id": PROGRESS_SCHEMA_ID,
                "schema_version": PROGRESS_SCHEMA_VERSION,
                "task_id": "T084",
                "state": "RUNNING",
                "identity": dict(identity),
                "configuration": dict(configuration),
                "output_path": str(self.output_path),
                "progress_path": str(self.path),
                "parts_directory": str(self.parts_directory),
                "created_at": _timestamp(),
                "updated_at": _timestamp(),
                "stages": {},
                "final_output": None,
                "last_error": None,
            }
            self._save()

    @property
    def already_complete(self) -> bool:
        return self.document.get("state") == "COMPLETE"

    def _save(self) -> None:
        self.document["updated_at"] = _timestamp()
        _atomic_write_json(self.path, self.document)

    def _validate_document(
        self,
        identity: Mapping[str, Any],
        configuration: Mapping[str, Any],
    ) -> None:
        required = {
            "schema_id",
            "schema_version",
            "task_id",
            "state",
            "identity",
            "configuration",
            "output_path",
            "progress_path",
            "parts_directory",
            "stages",
        }
        missing = sorted(required - set(self.document))
        if missing:
            raise ValueError("resume progress is missing: " + ", ".join(missing))
        if self.document.get("schema_id") != PROGRESS_SCHEMA_ID:
            raise ValueError("resume progress schema_id mismatch")
        if self.document.get("schema_version") != PROGRESS_SCHEMA_VERSION:
            raise ValueError("resume progress schema_version mismatch")
        if self.document.get("task_id") != "T084":
            raise ValueError("resume progress task_id mismatch")
        if self.document.get("identity") != dict(identity):
            raise ValueError("resume progress code/native/input identity mismatch")
        if self.document.get("configuration") != dict(configuration):
            raise ValueError("resume progress task configuration mismatch")
        if self.document.get("output_path") != str(self.output_path):
            raise ValueError("resume progress output path mismatch")
        if self.document.get("progress_path") != str(self.path):
            raise ValueError("resume progress path mismatch")
        if self.document.get("parts_directory") != str(self.parts_directory):
            raise ValueError("resume progress parts directory mismatch")
        if self.document.get("state") not in {
            "RUNNING",
            "FAILED",
            "FINALIZING",
            "COMPLETE",
        }:
            raise ValueError("resume progress state is invalid")
        stages = self.document.get("stages")
        if not isinstance(stages, Mapping):
            raise TypeError("resume progress stages must be a mapping")
        for stage_key, raw_stage in stages.items():
            if not isinstance(stage_key, str) or not isinstance(raw_stage, Mapping):
                raise TypeError("resume progress stage entry is malformed")
            task_keys = raw_stage.get("task_keys")
            tasks = raw_stage.get("tasks")
            if (
                not isinstance(task_keys, list)
                or len(set(task_keys)) != len(task_keys)
                or not all(isinstance(item, str) for item in task_keys)
                or not isinstance(tasks, Mapping)
                or any(key not in task_keys for key in tasks)
            ):
                raise TypeError(
                    f"resume progress task inventory is malformed: {stage_key}"
                )
            for task_key, raw_entry in tasks.items():
                if not isinstance(raw_entry, Mapping):
                    raise TypeError(
                        f"resume progress task entry is malformed: {stage_key}/{task_key}"
                    )
                if raw_entry.get("status") not in {"success", "failed"}:
                    raise ValueError(
                        f"resume progress task status is invalid: {stage_key}/{task_key}"
                    )
                history = raw_entry.get("attempt_history")
                if not isinstance(history, list) or not history:
                    raise ValueError(
                        f"resume progress task history is missing: {stage_key}/{task_key}"
                    )

    def _artifact_path(self, value: object) -> Path:
        if not isinstance(value, str) or not value or Path(value).is_absolute():
            raise TypeError("progress task artifact path must be relative")
        candidate = (self.path.parent / value).resolve()
        try:
            candidate.relative_to(self.parts_directory)
        except ValueError as exc:
            raise ValueError("progress task artifact escapes parts directory") from exc
        return candidate

    def _validated_artifact_path(
        self,
        stage_key: str,
        task: tuple[int, str],
        entry: Mapping[str, Any],
    ) -> Path:
        artifact = entry.get("artifact")
        if not isinstance(artifact, Mapping):
            raise TypeError(
                f"progress task artifact reference is missing: {stage_key}/{_task_key(task)}"
            )
        path = self._artifact_path(artifact.get("path"))
        if not path.is_file():
            raise ValueError(f"progress task artifact is missing: {path}")
        if artifact.get("bytes") != path.stat().st_size:
            raise ValueError(f"progress task artifact size mismatch: {path}")
        if artifact.get("sha256") != sha256_file(path):
            raise ValueError(f"progress task artifact hash mismatch: {path}")
        return path

    def _artifact_ref(self, path: Path) -> dict[str, Any]:
        return {
            "path": str(path.resolve().relative_to(self.path.parent)),
            "bytes": path.stat().st_size,
            "sha256": sha256_file(path),
        }

    def _read_task_artifact(
        self,
        stage_key: str,
        task: tuple[int, str],
        entry: Mapping[str, Any],
    ) -> dict[str, Any]:
        path = self._validated_artifact_path(stage_key, task, entry)
        try:
            with path.open("r", encoding="utf-8") as stream:
                raw = json.load(stream)
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f"progress task artifact is unreadable: {path}") from exc
        expected_key = _task_key(task)
        if not isinstance(raw, Mapping):
            raise TypeError(f"progress task artifact document is malformed: {path}")
        if (
            raw.get("schema_id") != PROGRESS_TASK_SCHEMA_ID
            or raw.get("schema_version") != PROGRESS_SCHEMA_VERSION
            or raw.get("stage_key") != stage_key
            or raw.get("task_key") != expected_key
            or raw.get("task") != _task_descriptor(task)
            or raw.get("status") != "success"
        ):
            raise ValueError(f"progress task artifact identity mismatch: {path}")
        result = raw.get("result")
        return _validate_task_result(result, task)

    def ensure_stage(
        self,
        stage_key: str,
        tasks: list[tuple[int, str]],
        *,
        pass_index: int,
        task_ranges: str,
        plan: object = None,
    ) -> None:
        task_keys = [_task_key(task) for task in tasks]
        if len(set(task_keys)) != len(task_keys):
            raise ValueError(f"duplicate progress task key in {stage_key}")
        stages = self.document["stages"]
        if not isinstance(stages, dict):
            raise TypeError("progress stages are not mutable")
        expected_plan_digest = _canonical_json_digest(plan)
        existing = stages.get(stage_key)
        if existing is None:
            stages[stage_key] = {
                "schema_id": PROGRESS_SCHEMA_ID,
                "schema_version": PROGRESS_SCHEMA_VERSION,
                "stage_key": stage_key,
                "pass_index": pass_index,
                "task_keys": task_keys,
                "task_descriptors": [_task_descriptor(task) for task in tasks],
                "task_count": len(tasks),
                "task_ranges": task_ranges,
                "plan": plan,
                "plan_sha256": expected_plan_digest,
                "status": "RUNNING",
                "tasks": {},
                "worker_pids": [],
                "worker_evidence": None,
                "worker_evidence_history": [],
                "wall_clock_seconds": 0.0,
                "last_failures": [],
            }
            self._save()
            return
        if not isinstance(existing, Mapping):
            raise TypeError(f"progress stage is malformed: {stage_key}")
        for key, expected in (
            ("schema_id", PROGRESS_SCHEMA_ID),
            ("schema_version", PROGRESS_SCHEMA_VERSION),
            ("stage_key", stage_key),
            ("pass_index", pass_index),
            ("task_keys", task_keys),
            ("task_count", len(tasks)),
            ("task_ranges", task_ranges),
            ("plan_sha256", expected_plan_digest),
        ):
            if existing.get(key) != expected:
                raise ValueError(
                    f"resume progress stage configuration mismatch: {stage_key}"
                )
        if existing.get("plan") != plan:
            raise ValueError(f"resume progress stage plan mismatch: {stage_key}")
        if existing.get("status") not in {"RUNNING", "FAILED", "COMPLETE"}:
            raise ValueError(f"resume progress stage status is invalid: {stage_key}")
        if existing.get("status") == "FAILED":
            existing["status"] = "RUNNING"
            self._save()

    def successful_task_keys(
        self,
        stage_key: str,
        tasks: list[tuple[int, str]],
    ) -> set[str]:
        """Return successful task keys without loading any task result rows."""

        stages = self.document.get("stages")
        stage = stages.get(stage_key) if isinstance(stages, Mapping) else None
        if not isinstance(stage, Mapping):
            raise TypeError(f"progress stage is missing: {stage_key}")
        raw_tasks = stage.get("tasks")
        if not isinstance(raw_tasks, Mapping):
            raise TypeError(f"progress stage task map is malformed: {stage_key}")
        successful: set[str] = set()
        for task in tasks:
            key = _task_key(task)
            entry = raw_tasks.get(key)
            if not isinstance(entry, Mapping):
                continue
            status = entry.get("status")
            if status == "success":
                # Validate the bounded artifact reference now, but defer JSON
                # decoding until the caller asks for this particular result.
                self._validated_artifact_path(stage_key, task, entry)
                successful.add(key)
            elif status != "failed":
                raise ValueError(f"progress task status is invalid: {stage_key}/{key}")
        return successful

    def iter_successful_results(
        self,
        stage_key: str,
        tasks: list[tuple[int, str]],
    ) -> Iterable[tuple[tuple[int, str], dict[str, Any]]]:
        """Yield one verified task result at a time from progress parts."""

        stages = self.document.get("stages")
        stage = stages.get(stage_key) if isinstance(stages, Mapping) else None
        if not isinstance(stage, Mapping):
            raise TypeError(f"progress stage is missing: {stage_key}")
        raw_tasks = stage.get("tasks")
        if not isinstance(raw_tasks, Mapping):
            raise TypeError(f"progress stage task map is malformed: {stage_key}")
        for task in tasks:
            key = _task_key(task)
            entry = raw_tasks.get(key)
            if not isinstance(entry, Mapping):
                continue
            status = entry.get("status")
            if status == "success":
                yield task, self._read_task_artifact(stage_key, task, entry)
            elif status != "failed":
                raise ValueError(f"progress task status is invalid: {stage_key}/{key}")

    def successful_results(
        self,
        stage_key: str,
        tasks: list[tuple[int, str]],
    ) -> dict[str, dict[str, Any]]:
        """Compatibility helper; new collection paths use the lazy iterator."""

        return {
            _task_key(task): result
            for task, result in self.iter_successful_results(stage_key, tasks)
        }

    def record_success(
        self,
        stage_key: str,
        task: tuple[int, str],
        result: Mapping[str, Any],
    ) -> None:
        self._record_task(stage_key, task, "success", result=dict(result), error=None)

    def record_failure(
        self,
        stage_key: str,
        task: tuple[int, str],
        exc: BaseException,
    ) -> None:
        self._record_task(
            stage_key, task, "failed", result=None, error=_error_payload(exc)
        )

    def _record_task(
        self,
        stage_key: str,
        task: tuple[int, str],
        status: str,
        *,
        result: dict[str, Any] | None,
        error: dict[str, str] | None,
    ) -> None:
        stages = self.document.get("stages")
        stage = stages.get(stage_key) if isinstance(stages, dict) else None
        if not isinstance(stage, dict):
            raise TypeError(f"progress stage is missing: {stage_key}")
        key = _task_key(task)
        if key not in stage.get("task_keys", []):
            raise ValueError(
                f"task is not registered in progress stage: {stage_key}/{key}"
            )
        task_map = stage.get("tasks")
        if not isinstance(task_map, dict):
            raise TypeError(f"progress stage task map is malformed: {stage_key}")
        previous = task_map.get(key)
        previous_history = (
            previous.get("attempt_history", []) if isinstance(previous, Mapping) else []
        )
        if not isinstance(previous_history, list):
            raise TypeError(f"progress task history is malformed: {stage_key}/{key}")
        attempt = len(previous_history) + 1
        part_path = (
            self.parts_directory / stage_key / f"{key}.attempt-{attempt:04d}.json"
        )
        document: dict[str, Any] = {
            "schema_id": PROGRESS_TASK_SCHEMA_ID,
            "schema_version": PROGRESS_SCHEMA_VERSION,
            "stage_key": stage_key,
            "pass_index": stage.get("pass_index"),
            "task_key": key,
            "task": _task_descriptor(task),
            "attempt": attempt,
            "status": status,
        }
        if status == "success":
            if result is None:
                raise ValueError("successful progress task has no result")
            document["result"] = result
        elif status == "failed":
            document["error"] = error or {
                "type": "UnknownError",
                "message": "unknown failure",
            }
        else:
            raise ValueError(f"unsupported progress task status: {status}")
        _atomic_write_json(part_path, document)
        artifact = self._artifact_ref(part_path)
        history_entry: dict[str, Any] = {
            "attempt": attempt,
            "status": status,
            "artifact": artifact,
        }
        if error is not None:
            history_entry["error"] = error
        task_map[key] = {
            "task": _task_descriptor(task),
            "status": status,
            "attempt": attempt,
            "artifact": artifact,
            "error": error,
            "attempt_history": [*previous_history, history_entry],
        }
        if status == "success" and isinstance(result, Mapping):
            worker_pid = result.get("worker_pid")
            worker_pids = stage.get("worker_pids")
            if (
                isinstance(worker_pid, int)
                and not isinstance(worker_pid, bool)
                and isinstance(worker_pids, list)
                and worker_pid not in worker_pids
            ):
                worker_pids.append(worker_pid)
        self._save()

    def stage_failures(self, stage_key: str) -> list[str]:
        stages = self.document.get("stages")
        stage = stages.get(stage_key) if isinstance(stages, Mapping) else None
        if not isinstance(stage, Mapping):
            raise TypeError(f"progress stage is missing: {stage_key}")
        task_map = stage.get("tasks")
        if not isinstance(task_map, Mapping):
            raise TypeError(f"progress stage task map is malformed: {stage_key}")
        descriptors = stage.get("task_descriptors")
        if not isinstance(descriptors, list):
            raise TypeError(f"progress stage task descriptors are missing: {stage_key}")
        by_key = {
            _task_key((int(item["root_index"]), str(item["sampling_arm"]))): item
            for item in descriptors
            if isinstance(item, Mapping)
            and isinstance(item.get("root_index"), int)
            and isinstance(item.get("sampling_arm"), str)
        }
        failures: list[str] = []
        for key in stage.get("task_keys", []):
            entry = task_map.get(key)
            if not isinstance(entry, Mapping) or entry.get("status") != "failed":
                continue
            descriptor = by_key.get(key, {})
            error = entry.get("error")
            if isinstance(error, Mapping):
                message = f"{error.get('type', 'Error')}: {error.get('message', '')}"
            else:
                message = "unknown failure"
            failures.append(
                f"{descriptor.get('sampling_arm', key)}/root{descriptor.get('root_index', '?')}: {message}"
            )
        return failures

    def finish_stage(
        self,
        stage_key: str,
        *,
        failures: list[str],
        worker_evidence: Mapping[str, Any],
        wall_clock_seconds: float,
    ) -> None:
        stages = self.document.get("stages")
        stage = stages.get(stage_key) if isinstance(stages, dict) else None
        if not isinstance(stage, dict):
            raise TypeError(f"progress stage is missing: {stage_key}")
        task_map = stage.get("tasks")
        task_keys = stage.get("task_keys")
        if not isinstance(task_map, Mapping) or not isinstance(task_keys, list):
            raise TypeError(f"progress stage inventory is malformed: {stage_key}")
        was_complete = stage.get("status") == "COMPLETE"
        complete = not failures and all(
            isinstance(task_map.get(key), Mapping)
            and task_map[key].get("status") == "success"
            for key in task_keys
        )
        stage["status"] = "COMPLETE" if complete else "FAILED"
        stage["last_failures"] = list(failures)
        if not was_complete:
            previous_wall = stage.get("wall_clock_seconds", 0.0)
            stage["wall_clock_seconds"] = float(previous_wall or 0.0) + float(
                wall_clock_seconds
            )
            stage["worker_evidence"] = dict(worker_evidence)
            history = stage.get("worker_evidence_history")
            if not isinstance(history, list):
                history = []
                stage["worker_evidence_history"] = history
            history.append(dict(worker_evidence))
            self._save()

    def stage_plan(self, stage_key: str) -> object | None:
        stages = self.document.get("stages")
        stage = stages.get(stage_key) if isinstance(stages, Mapping) else None
        if not isinstance(stage, Mapping):
            return None
        return stage.get("plan")

    def has_stage(self, stage_key: str) -> bool:
        stages = self.document.get("stages")
        return isinstance(stages, Mapping) and stage_key in stages

    def stage_wall_clock(self, stage_key: str) -> float:
        stages = self.document.get("stages")
        stage = stages.get(stage_key) if isinstance(stages, Mapping) else None
        if not isinstance(stage, Mapping):
            return 0.0
        value = stage.get("wall_clock_seconds", 0.0)
        return float(value) if isinstance(value, (int, float)) else 0.0

    def stage_worker_pids(self, stage_key: str) -> list[int]:
        stages = self.document.get("stages")
        stage = stages.get(stage_key) if isinstance(stages, Mapping) else None
        if not isinstance(stage, Mapping):
            return []
        values = stage.get("worker_pids")
        if not isinstance(values, list):
            return []
        return sorted(
            int(value)
            for value in values
            if isinstance(value, int) and not isinstance(value, bool)
        )

    def mark_failed(self, exc: BaseException) -> None:
        self.document["state"] = "FAILED"
        self.document["last_error"] = _error_payload(exc)
        self._save()

    def prepare_final(self, expected_output: Mapping[str, Any]) -> None:
        self.document["state"] = "FINALIZING"
        self.document["final_output"] = dict(expected_output)
        self._save()

    def mark_complete(self, output_ref: Mapping[str, Any]) -> None:
        expected = self.document.get("final_output")
        if expected != dict(output_ref):
            raise ValueError(
                "final output identity does not match progress reservation"
            )
        self.document["state"] = "COMPLETE"
        self.document["final_output"] = dict(output_ref)
        self.document["last_error"] = None
        self._save()

    def _recover_or_validate_final_output(self) -> None:
        state = self.document.get("state")
        if state == "COMPLETE":
            self._validate_final_output()
            return
        if self.output_path.exists() and state != "FINALIZING":
            raise ValueError(
                "resume progress is incomplete but final output already exists; refusing to mix outputs"
            )
        if state == "FINALIZING":
            if self.output_path.exists():
                self._validate_final_output()
                self.document["state"] = "COMPLETE"
                self._save()
            else:
                self.document["state"] = "RUNNING"
                self._save()

    def _validate_final_output(self) -> None:
        expected = self.document.get("final_output")
        if not isinstance(expected, Mapping):
            raise TypeError("resume progress final output reservation is missing")
        if not self.output_path.is_file():
            raise ValueError(f"resume final output is missing: {self.output_path}")
        if expected.get("bytes") != self.output_path.stat().st_size:
            raise ValueError("resume final output size mismatch")
        if expected.get("sha256") != sha256_file(self.output_path):
            raise ValueError("resume final output hash mismatch")


def _run_parallel_tasks(
    roots: list[dict[str, Any]],
    checkpoint_paths: dict[str, str],
    native_commit: str,
    workers: int,
    pass_mode: str,
    target_specs: dict[str, dict[str, Any]],
    *,
    worker_function: Any,
    progress: _ProgressStore | None,
    stage_key: str,
    pass_index: int,
    task_ranges: str,
    plan: object = None,
    retain_results: bool = True,
) -> tuple[list[dict[str, Any]], list[str], float, dict[str, Any]]:
    workers = _validate_worker_count(workers)
    tasks = [(root_index, arm) for root_index in range(len(roots)) for arm in ARMS]

    def iter_worker_results(
        scheduled_tasks: list[tuple[int, str]],
    ) -> Iterable[tuple[tuple[int, str], dict[str, Any] | None, BaseException | None]]:
        """Keep at most ``workers`` native results live in the parent process."""

        context = multiprocessing.get_context("fork")
        with ProcessPoolExecutor(
            max_workers=workers,
            mp_context=context,
            initializer=_worker_init,
            initargs=(roots, native_commit, checkpoint_paths, pass_mode, target_specs),
        ) as pool:
            task_iterator = iter(scheduled_tasks)
            futures: dict[Any, tuple[int, str]] = {}
            for _ in range(min(workers, len(scheduled_tasks))):
                task = next(task_iterator, None)
                if task is None:
                    break
                futures[pool.submit(worker_function, task)] = task
            while futures:
                done, _ = wait(set(futures), return_when=FIRST_COMPLETED)
                for future in done:
                    task = futures.pop(future)
                    try:
                        result = _validate_task_result(future.result(), task)
                    except Exception as exc:  # noqa: BLE001 - retained per-task evidence
                        yield task, None, exc
                    else:
                        yield task, result, None
                    next_task = next(task_iterator, None)
                    if next_task is not None:
                        futures[pool.submit(worker_function, next_task)] = next_task

    if progress is None:
        started = time.monotonic()
        rows: list[dict[str, Any]] = []
        failures: list[str] = []
        for completed, (task, result, error) in enumerate(
            iter_worker_results(tasks), start=1
        ):
            if error is not None:
                root_index, arm = task
                failures.append(
                    f"{arm}/root{root_index}: {type(error).__name__}: {error}"
                )
            elif result is not None:
                rows.append(result)
            if completed % 16 == 0 or completed == len(tasks):
                print(
                    json.dumps(
                        {
                            "pass": pass_mode,
                            "completed": completed,
                            "total": len(tasks),
                            "failures": len(failures),
                            "wall_clock_seconds": time.monotonic() - started,
                        },
                        sort_keys=True,
                    ),
                    flush=True,
                )
        rows.sort(
            key=lambda row: (
                str(row.get("sampling_arm")),
                int(row.get("root_index", -1)),
            )
        )
        worker_pids = sorted(
            {
                int(row["worker_pid"])
                for row in rows
                if isinstance(row.get("worker_pid"), int)
                and not isinstance(row.get("worker_pid"), bool)
            }
        )
        worker_evidence = {
            "configured_worker_count": workers,
            "observed_worker_count": len(worker_pids),
            "effective_worker_count": len(worker_pids),
            "worker_pids": worker_pids,
            "host_logical_cpu_count": os.cpu_count(),
        }
        return rows, failures, time.monotonic() - started, worker_evidence
    progress.ensure_stage(
        stage_key,
        tasks,
        pass_index=pass_index,
        task_ranges=task_ranges,
        plan=plan,
    )
    started = time.monotonic()
    cached_keys = progress.successful_task_keys(stage_key, tasks)
    pending = [task for task in tasks if _task_key(task) not in cached_keys]
    completed = len(cached_keys)
    session_worker_pids: set[int] = set()
    if pending:
        for task, result, error in iter_worker_results(pending):
            if error is not None:
                progress.record_failure(stage_key, task, error)
            elif result is not None:
                progress.record_success(stage_key, task, result)
                worker_pid = result.get("worker_pid")
                if isinstance(worker_pid, int) and not isinstance(worker_pid, bool):
                    session_worker_pids.add(worker_pid)
            completed += 1
            if completed % 16 == 0 or completed == len(tasks):
                print(
                    json.dumps(
                        {
                            "pass": pass_mode,
                            "completed": completed,
                            "total": len(tasks),
                            "failures": len(progress.stage_failures(stage_key)),
                            "wall_clock_seconds": time.monotonic() - started,
                        },
                        sort_keys=True,
                    ),
                    flush=True,
                )
    rows: list[dict[str, Any]] = []
    if retain_results:
        rows = [
            result for _, result in progress.iter_successful_results(stage_key, tasks)
        ]
    failures = progress.stage_failures(stage_key)
    stored_worker_pids = set(progress.stage_worker_pids(stage_key))
    worker_pids = sorted(stored_worker_pids | session_worker_pids)
    existing_stage = progress.document["stages"][stage_key]
    prior_evidence = existing_stage.get("worker_evidence")
    prior_observed = (
        int(prior_evidence.get("observed_worker_count", 0))
        if isinstance(prior_evidence, Mapping)
        and isinstance(prior_evidence.get("observed_worker_count"), int)
        else 0
    )
    observed_worker_count = max(prior_observed, len(session_worker_pids))
    if not pending and isinstance(prior_evidence, Mapping):
        observed_worker_count = int(prior_evidence.get("observed_worker_count", 0))
    worker_evidence = {
        "configured_worker_count": workers,
        "observed_worker_count": observed_worker_count,
        "effective_worker_count": observed_worker_count,
        "worker_pids": worker_pids,
        "host_logical_cpu_count": os.cpu_count(),
        "resume_cached_task_count": len(cached_keys),
        "newly_executed_task_count": len(pending),
    }
    wall_clock_seconds = time.monotonic() - started
    progress.finish_stage(
        stage_key,
        failures=failures,
        worker_evidence=worker_evidence,
        wall_clock_seconds=wall_clock_seconds,
    )
    return rows, failures, progress.stage_wall_clock(stage_key), worker_evidence


def _run_pass(
    roots: list[dict[str, Any]],
    checkpoint_paths: dict[str, str],
    native_commit: str,
    workers: int,
    pass_mode: str,
    target_specs: dict[str, dict[str, Any]],
    *,
    progress: _ProgressStore | None = None,
    stage_key: str = "candidate",
    pass_index: int = 0,
    plan: object = None,
) -> tuple[list[dict[str, Any]], list[str], float, dict[str, Any]]:
    return _run_parallel_tasks(
        roots,
        checkpoint_paths,
        native_commit,
        workers,
        pass_mode,
        target_specs,
        worker_function=_work_one,
        progress=progress,
        stage_key=stage_key,
        pass_index=pass_index,
        task_ranges=(
            "candidate pass: root indices 0..459 x three arms"
            if pass_mode == "candidate"
            else "selected_leaf_continuation pass: root indices 0..459 x three arms"
        ),
        plan=plan,
        retain_results=progress is None,
    )


def _work_parity_one(task: tuple[int, str]) -> dict[str, Any]:
    root_index, arm = task
    root_raw = _ROOT_ROWS[root_index]
    root = record_from_manifest(
        root_raw,
        label=f"T084 parity root {root_index}",
        allowed_distribution_kinds=frozenset({ASSISTED_RUN_DISTRIBUTION_KIND}),
        allow_assistance_history=True,
    )
    source_identity = str(root_raw["_t084_source_identity"])
    scorer = _scorer_for_arm(arm)

    def policy_callback(raw: object, native_actions: object) -> list[float]:
        if scorer is None:
            raise AssertionError("unguided arm must not invoke a policy callback")
        actions = _native_actions(native_actions)
        if not isinstance(raw, Mapping):
            raise TypeError("native parity policy snapshot is malformed")
        context = build_decision_context(
            raw,
            actions,
            ActionSpaceConfig.initial_no_potions(),
            public_run_context=root.public_run_context,
        )
        return _native_policy_prior_scores(scorer, context)

    off_adapter = LightSpeedAdapter(
        seed=root.source_seed,
        ascension=int(root.snapshot_raw.get("ascension", 20)),
        module=_NATIVE_MODULE,
    )
    off_snapshot, _ = restore_assisted_battle_start_record(off_adapter, root)
    on_adapter = LightSpeedAdapter(
        seed=root.source_seed,
        ascension=int(root.snapshot_raw.get("ascension", 20)),
        module=_NATIVE_MODULE,
    )
    on_snapshot, _ = restore_assisted_battle_start_record(on_adapter, root)
    observed_rng: list[dict[str, Any]] = []

    def collect_rng(*values: object) -> None:
        if values and isinstance(values[-1], Mapping):
            observed_rng.append(dict(values[-1]))

    off = off_adapter.battle_search_v2(
        off_snapshot,
        simulations=100,
        include_potions=False,
        policy_prior_callback=policy_callback if scorer is not None else None,
    )
    on = on_adapter.battle_search_v2_with_leaf_collection(
        on_snapshot,
        simulations=100,
        include_potions=False,
        policy_prior_callback=policy_callback if scorer is not None else None,
        collector_config={
            "schema_id": COLLECTOR_SCHEMA_ID,
            "sampling_arm": arm,
            "native_commit": _NATIVE_COMMIT,
            "parity_preflight": True,
        },
        leaf_collector_callback=collect_rng,
    )
    expected_rng = {
        "battle_context_seed": root.source_seed,
        "battle_context_floor_num": int(off_snapshot.raw["floor_num"]),
        "search_action_rng_seed_rule": (
            "BattleScumSearcher2::randGen seeded from BattleContext.seed+floorNum"
        ),
    }
    rng_equal = bool(observed_rng) and all(
        value == expected_rng for value in observed_rng
    )
    return {
        "root_index": root_index,
        "worker_pid": os.getpid(),
        "root_identity": source_identity,
        "sampling_arm": arm,
        "act": int(root_raw["act"]),
        "root_action_equal": off.get("root_action") == on.get("root_action"),
        "root_statistics_equal": off.get("root_rows") == on.get("root_rows"),
        "native_root_statistics_equal": off.get("root_rows") == on.get("root_rows"),
        "rng_semantics_equal": rng_equal,
        "off_native_root_statistics": off.get("root_rows"),
        "on_native_root_statistics": on.get("root_rows"),
        "material_outputs_equal": (
            off.get("root_action") == on.get("root_action")
            and off.get("root_rows") == on.get("root_rows")
            and rng_equal
        ),
        "off_root_action": off.get("root_action"),
        "on_root_action": on.get("root_action"),
        "observed_rng_count": len(observed_rng),
        "expected_rng": expected_rng,
    }


def _run_parity(
    roots: list[dict[str, Any]],
    checkpoint_paths: dict[str, str],
    native_commit: str,
    workers: int,
    *,
    progress: _ProgressStore | None = None,
) -> tuple[dict[str, Any], list[str], float]:
    source_indices = _select_parity_root_indices(roots)
    parity_roots = [roots[index] for index in source_indices]
    for parity_index, source_index in enumerate(source_indices):
        parity_roots[parity_index] = {
            **parity_roots[parity_index],
            "_t084_parity_source_index": source_index,
        }
    tasks = [
        (root_index, arm) for root_index in range(len(parity_roots)) for arm in ARMS
    ]
    rows, failures, wall_clock_seconds, worker_evidence = _run_parallel_tasks(
        parity_roots,
        checkpoint_paths,
        native_commit,
        workers,
        "parity",
        {},
        worker_function=_work_parity_one,
        progress=progress,
        stage_key="parity_preflight",
        pass_index=0,
        task_ranges="parity_preflight: first eight Act1 and first eight Act2 source roots x three arms",
        plan={"source_indices": source_indices},
    )
    parity = {
        "available": not failures,
        "passed": (
            not failures
            and len(rows) == len(tasks)
            and all(row["material_outputs_equal"] for row in rows)
        ),
        "checked_root_count": len({row["root_index"] for row in rows}),
        "arms": sorted({row["sampling_arm"] for row in rows}),
        "acts": sorted({row["act"] for row in rows}),
        "worker_count": workers,
        "effective_worker_count": worker_evidence["effective_worker_count"],
        "worker_evidence": worker_evidence,
        "task_count": len(tasks),
        "task_ranges": "first eight Act1 and first eight Act2 source roots x three arms",
        "root_identities": [row["root_identity"] for row in rows],
        "act_counts": {
            str(act): sum(1 for row in rows if row["act"] == act) for act in (1, 2)
        },
        "material_outputs_equal": bool(rows)
        and all(row["material_outputs_equal"] for row in rows),
        "root_action_equal": bool(rows)
        and all(row["root_action_equal"] for row in rows),
        "root_statistics_equal": bool(rows)
        and all(row["root_statistics_equal"] for row in rows),
        "rng_semantics_equal": bool(rows)
        and all(row["rng_semantics_equal"] for row in rows),
        "rows": rows,
        "failures": failures,
        "wall_clock_seconds": wall_clock_seconds,
    }
    return parity, failures, wall_clock_seconds


def _select_parity_root_indices(roots: list[dict[str, Any]]) -> list[int]:
    """Choose a stable 8+8 Act parity subset, independent of source ordering."""

    act1 = [index for index, root in enumerate(roots) if int(root.get("act", 0)) == 1]
    act2 = [index for index, root in enumerate(roots) if int(root.get("act", 0)) == 2]
    if len(act1) < 8 or len(act2) < 8:
        raise ValueError("T084 parity requires at least eight roots from each Act")
    return act1[:8] + act2[:8]


def _stage_tasks(root_count: int) -> list[tuple[int, str]]:
    return [(root_index, arm) for root_index in range(root_count) for arm in ARMS]


def _sorted_stage_tasks(tasks: Iterable[tuple[int, str]]) -> list[tuple[int, str]]:
    return sorted(tasks, key=lambda task: (str(task[1]), int(task[0])))


def _iter_stage_field_rows(
    progress: _ProgressStore,
    stage_key: str,
    tasks: list[tuple[int, str]],
    field: str,
) -> Iterable[tuple[tuple[int, str], int, Mapping[str, Any]]]:
    """Read one task part at a time and yield rows without stage accumulation."""

    for task, result in progress.iter_successful_results(
        stage_key, _sorted_stage_tasks(tasks)
    ):
        raw_rows = result.get(field)
        if not isinstance(raw_rows, list):
            raise TypeError(f"progress task result field is not a list: {field}")
        for row_index, raw_row in enumerate(raw_rows):
            if not isinstance(raw_row, Mapping):
                raise TypeError(f"progress task row is malformed: {field}/{row_index}")
            yield task, row_index, raw_row


def _candidate_metadata(row: Mapping[str, Any]) -> dict[str, Any]:
    """Keep only selection metadata after a candidate task part is read."""

    identity = row.get("exact_leaf_identity")
    digest = row.get("exact_state_digest")
    if not isinstance(identity, str) or not identity:
        raise ValueError("candidate exact hidden identity is missing")
    if not isinstance(digest, str) or not digest:
        raise ValueError("candidate exact state digest is missing")
    hidden = row.get("exact_hidden_state_payload")
    payload_sha256 = row.get("canonical_native_payload_sha256")
    if isinstance(hidden, Mapping):
        payload = hidden.get("canonical_native_payload_json")
        if isinstance(payload, str) and payload:
            payload_sha256 = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    if not isinstance(payload_sha256, str) or not payload_sha256:
        raise ValueError("candidate lacks canonical hidden payload identity")
    expected_identity = f"t084-hidden-state-{payload_sha256}"
    if identity != expected_identity:
        raise ValueError(
            "candidate exact hidden identity is not derived from canonical payload"
        )
    source_identity = row.get(
        "source_complete_identity_sha256", row.get("root_identity")
    )
    occurrence_key = row.get("occurrence_key")
    if not isinstance(source_identity, str) or not source_identity:
        raise ValueError("candidate source identity is missing")
    if not isinstance(occurrence_key, str) or not occurrence_key:
        raise ValueError("candidate occurrence key is missing")
    act = row.get("act")
    if isinstance(act, bool) or not isinstance(act, int):
        raise TypeError("candidate Act is invalid")
    return {
        "sampling_arm": str(row.get("sampling_arm")),
        "act": act,
        "root_identity": str(row.get("root_identity", source_identity)),
        "exact_leaf_identity": identity,
        "exact_state_digest": digest,
        "source_complete_identity_sha256": source_identity,
        "occurrence_key": occurrence_key,
        "canonical_native_payload_sha256": payload_sha256,
        "depth": row.get("depth"),
        "callback_ordinal": row.get("callback_ordinal"),
        "path_fingerprint": row.get("path_fingerprint"),
    }


def _iter_candidate_metadata(
    progress: _ProgressStore,
    stage_key: str,
    tasks: list[tuple[int, str]],
) -> Iterable[dict[str, Any]]:
    for _, _, row in _iter_stage_field_rows(
        progress, stage_key, tasks, "candidate_rows"
    ):
        yield _candidate_metadata(row)


def _iter_candidate_rows_with_occupancy(
    progress: _ProgressStore,
    stage_key: str,
    tasks: list[tuple[int, str]],
    occupancy_counts: Mapping[str, int],
) -> Iterable[dict[str, Any]]:
    """Stream full candidate rows and add the existing occupancy annotations."""

    for _, _, raw_row in _iter_stage_field_rows(
        progress, stage_key, tasks, "candidate_rows"
    ):
        metadata = _candidate_metadata(raw_row)
        identity = str(metadata["exact_leaf_identity"])
        expected_count = occupancy_counts.get(identity)
        if expected_count is None:
            raise ValueError("candidate occupancy metadata is incomplete")
        row = dict(raw_row)
        hidden = row.get("exact_hidden_state_payload")
        if not isinstance(hidden, Mapping):
            raise TypeError("candidate lacks exact hidden state payload")
        annotated_hidden = dict(hidden)
        annotated_hidden["occupancy_duplicate"] = expected_count > 1
        annotated_hidden["occupancy_count"] = expected_count
        row["exact_hidden_state_payload"] = annotated_hidden
        yield row


def _iter_root_runs(
    progress: _ProgressStore,
    stage_key: str,
    tasks: list[tuple[int, str]],
) -> Iterable[dict[str, Any]]:
    for _, result in progress.iter_successful_results(
        stage_key, _sorted_stage_tasks(tasks)
    ):
        yield {
            key: value
            for key, value in result.items()
            if key not in ("candidate_rows", "target_rows")
        }


def _target_location(descriptor: Mapping[str, Any]) -> tuple[str, str, int]:
    stage_key = descriptor.get("_stage_key")
    task_key = descriptor.get("_task_key")
    row_index = descriptor.get("_row_index")
    if (
        not isinstance(stage_key, str)
        or not isinstance(task_key, str)
        or isinstance(row_index, bool)
        or not isinstance(row_index, int)
    ):
        raise TypeError("accepted target row has no valid progress locator")
    return stage_key, task_key, row_index


def _iter_located_target_rows(
    progress: _ProgressStore,
    stage_keys: list[str],
    tasks: list[tuple[int, str]],
    descriptors: Iterable[Mapping[str, Any]],
) -> Iterable[tuple[Mapping[str, Any], Mapping[str, Any]]]:
    descriptor_list = list(descriptors)
    wanted = {
        _target_location(descriptor): descriptor for descriptor in descriptor_list
    }
    if len(wanted) != len(descriptor_list):
        raise ValueError("accepted target row locators are not unique")
    found: set[tuple[str, str, int]] = set()
    for stage_key in stage_keys:
        for task, row_index, row in _iter_stage_field_rows(
            progress, stage_key, tasks, "target_rows"
        ):
            location = (stage_key, _task_key(task), row_index)
            descriptor = wanted.get(location)
            if descriptor is None:
                continue
            if location in found:
                raise ValueError("accepted target row locator was emitted twice")
            found.add(location)
            yield descriptor, row
    missing = set(wanted) - found
    if missing:
        raise ValueError(
            "accepted target row parts are missing: "
            + ", ".join(
                f"{stage}/{task}/{index}" for stage, task, index in sorted(missing)
            )
        )


def _accepted_descriptors(
    accepted_by_cell: Mapping[tuple[str, int, str], list[dict[str, Any]]],
    target_kind: str,
) -> list[dict[str, Any]]:
    descriptors: list[dict[str, Any]] = []
    for arm in ARMS:
        for act in (1, 2):
            descriptors.extend(
                descriptor
                for descriptor in accepted_by_cell.get((arm, act, target_kind), [])
                if descriptor.get("target_kind") == target_kind
            )
    return descriptors


def _write_streaming_json_temp(
    path: Path,
    execution: Mapping[str, Any],
    row_streams: Mapping[str, Iterable[object]],
) -> tuple[Path, dict[str, Any]]:
    """Encode the final object while retaining at most one row at a time."""

    path = path.resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_fd, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent)
    )
    temporary = Path(temporary_name)
    encoder = json.JSONEncoder(indent=2, sort_keys=True, allow_nan=False)
    try:
        with os.fdopen(temporary_fd, "w", encoding="utf-8", newline="\n") as stream:
            stream.write("{")
            first = True
            for key in sorted(execution):
                if not first:
                    stream.write(",")
                first = False
                stream.write("\n  ")
                for chunk in encoder.iterencode(key):
                    stream.write(chunk)
                stream.write(": ")
                row_stream = row_streams.get(key)
                if row_stream is None:
                    for chunk in encoder.iterencode(execution[key]):
                        stream.write(chunk)
                    continue
                stream.write("[")
                first_row = True
                for row in row_stream:
                    if not first_row:
                        stream.write(",")
                    first_row = False
                    for chunk in encoder.iterencode(row):
                        stream.write(chunk)
                stream.write("]")
            stream.write("\n}\n")
            stream.flush()
            os.fsync(stream.fileno())
        output_ref = {
            "path": str(path),
            "bytes": temporary.stat().st_size,
            "sha256": sha256_file(temporary),
        }
        return temporary, output_ref
    except BaseException:
        if temporary.exists():
            temporary.unlink()
        raise


def _publish_streaming_json(
    path: Path,
    execution: Mapping[str, Any],
    row_streams: Mapping[str, Iterable[object]],
    progress: _ProgressStore,
) -> None:
    temporary, expected = _write_streaming_json_temp(path, execution, row_streams)
    try:
        progress.prepare_final(expected)
        os.replace(temporary, path)
        directory_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
        actual = {
            "path": str(path.resolve()),
            "bytes": path.stat().st_size,
            "sha256": sha256_file(path),
        }
        progress.mark_complete(actual)
    finally:
        if temporary.exists():
            temporary.unlink()


def _leaf_rank(row: Mapping[str, Any]) -> str:
    value = "|".join(
        (
            str(row["source_complete_identity_sha256"]),
            str(row["sampling_arm"]),
            str(row["exact_leaf_identity"]),
        )
    )
    return hashlib.sha256(value.encode()).hexdigest()


def _canonical_payload(row: Mapping[str, Any]) -> str:
    hidden = row.get("exact_hidden_state_payload")
    if not isinstance(hidden, Mapping):
        raise TypeError("candidate lacks exact hidden state payload")
    payload = hidden.get("canonical_native_payload_json")
    if not isinstance(payload, str) or not payload:
        raise ValueError("candidate lacks retained canonical native payload bytes")
    expected_identity = (
        f"t084-hidden-state-{hashlib.sha256(payload.encode('utf-8')).hexdigest()}"
    )
    if str(row.get("exact_leaf_identity")) != expected_identity:
        raise ValueError(
            "candidate exact hidden identity is not derived from canonical payload"
        )
    return payload


def _selected_target_for_occurrence(
    target_specs: Mapping[str, Mapping[str, Any]],
    exact_identity: str,
    occurrence_key: str,
    consumed_target_ids: set[str],
) -> Mapping[str, Any] | None:
    """Return a target only for its selected occurrence, once per replay."""

    spec = target_specs.get(exact_identity)
    if (
        not isinstance(spec, Mapping)
        or spec.get("occurrence_key") != occurrence_key
        or exact_identity in consumed_target_ids
    ):
        return None
    return spec


def _ordered_cell_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return unique states in deterministic root-first then hash order."""

    by_identity: dict[str, list[dict[str, Any]]] = {}
    digest_identities: dict[str, str] = {}
    identity_digests: dict[str, str] = {}
    ranked_rows: list[tuple[str, str, str, int, dict[str, Any]]] = []
    available_rows: list[tuple[str, str, str, int, dict[str, Any]]] = []
    for ordinal, raw_row in enumerate(rows):
        row = _candidate_metadata(raw_row)
        identity = str(row["exact_leaf_identity"])
        digest = str(row["exact_state_digest"])
        previous_identity = digest_identities.setdefault(digest, identity)
        if previous_identity != identity:
            raise ValueError(f"native digest collision for {digest}")
        previous_digest = identity_digests.setdefault(identity, digest)
        if previous_digest != digest:
            raise ValueError(
                "candidate exact hidden identity maps to conflicting state digests"
            )
        by_identity.setdefault(identity, []).append(row)
        ranked_row = (
            _leaf_rank(row),
            str(row.get("root_identity", "")),
            identity,
            ordinal,
            row,
        )
        heappush(ranked_rows, ranked_row)
        heappush(available_rows, ranked_row)

    remaining = set(by_identity)
    chosen: list[dict[str, Any]] = []
    used_roots: set[str] = set()

    def pop_valid(
        heap: list[tuple[str, str, str, int, dict[str, Any]]],
        *,
        require_unused_root: bool,
    ) -> tuple[str, str, str, int, dict[str, Any]] | None:
        while heap:
            ranked_row = heap[0]
            identity = ranked_row[2]
            root_identity = ranked_row[1]
            if identity not in remaining or (
                require_unused_root and root_identity in used_roots
            ):
                heappop(heap)
                continue
            return heappop(heap)
        return None

    while remaining:
        ranked_row = pop_valid(available_rows, require_unused_root=True)
        if ranked_row is None:
            ranked_row = pop_valid(ranked_rows, require_unused_root=False)
        if ranked_row is None:
            raise RuntimeError("candidate ranking heaps lost a remaining identity")
        _, root_identity, identity, _, row = ranked_row
        chosen.append(row)
        remaining.remove(identity)
        used_roots.add(root_identity)
    return chosen


def _select_cell(
    rows: list[dict[str, Any]],
    count: int,
    selected: dict[str, dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Select unique hidden states with distinct source roots as the first phase."""

    ordered = [
        row
        for row in _ordered_cell_rows(rows)
        if str(row["exact_leaf_identity"]) not in selected
    ]
    chosen = ordered[:count]
    used_roots = {str(row.get("root_identity", "")) for row in chosen}
    for row in chosen:
        selected[str(row["exact_leaf_identity"])] = {
            "target_kind": "pending",
            "occurrence_key": str(row["occurrence_key"]),
            "root_identity": str(row["root_identity"]),
            "sampling_arm": str(row["sampling_arm"]),
            "act": int(row["act"]),
        }
    return chosen, {
        "requested": count,
        "selected": len(chosen),
        "distinct_source_roots": len(used_roots),
        "root_first_phase_completed": len(used_roots) == len(chosen),
        "hash_tie_break": "sha256(source_complete_identity_sha256|sampling_arm|exact_leaf_identity)",
    }


def _select_target_specs_with_policy(
    candidate_rows: list[dict[str, Any]],
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    """Select calibration/formal identities, never counting occupancy duplicates."""

    selected: dict[str, dict[str, Any]] = {}
    cells: list[dict[str, Any]] = []
    for arm in ARMS:
        for act, count, kind in ((1, 18, "calibration"), (2, 14, "calibration")):
            chosen, detail = _select_cell(
                [
                    row
                    for row in candidate_rows
                    if row.get("sampling_arm") == arm and row.get("act") == act
                ],
                count,
                selected,
            )
            for row in chosen:
                identity = str(row["exact_leaf_identity"])
                selected[identity] = {**selected[identity], "target_kind": kind}
            cells.append({"arm": arm, "act": act, "kind": kind, **detail})
        for act, count in ((1, 178), (2, 142)):
            chosen, detail = _select_cell(
                [
                    row
                    for row in candidate_rows
                    if row.get("sampling_arm") == arm and row.get("act") == act
                ],
                count,
                selected,
            )
            for row in chosen:
                identity = str(row["exact_leaf_identity"])
                selected[identity] = {**selected[identity], "target_kind": "formal"}
            cells.append({"arm": arm, "act": act, "kind": "formal", **detail})
    return selected, {
        "schema_id": _SELECTION_POLICY,
        "identity": "sha256(canonical_native_payload UTF-8 bytes)",
        "digest_role": "index-only-with-canonical-payload-collision-check",
        "occupancy_duplicates": "retained in candidate_rows, excluded from identity counts and target selection",
        "root_policy": "distinct source roots first, then versioned hash ranking",
        "selected_occurrences": [
            {
                "exact_leaf_identity": identity,
                "target_kind": spec["target_kind"],
                "occurrence_key": spec["occurrence_key"],
                "root_identity": spec["root_identity"],
            }
            for identity, spec in sorted(selected.items())
        ],
        "cells": cells,
    }


def _select_target_specs(candidate_rows: list[dict[str, Any]]) -> dict[str, str]:
    """Compatibility wrapper for focused callers."""

    selected, _ = _select_target_specs_with_policy(candidate_rows)
    return {identity: str(spec["target_kind"]) for identity, spec in selected.items()}


def _target_row_has_full_replicates(row: Mapping[str, Any]) -> bool:
    replicates = row.get("replicates")
    return (
        isinstance(replicates, list)
        and len(replicates) == 256
        and all(
            isinstance(replica, Mapping) and validate_replicate(replica)
            for replica in replicates
        )
    )


def _target_spec_for_row(row: Mapping[str, Any], target_kind: str) -> dict[str, Any]:
    return {
        "exact_leaf_identity": str(row["exact_leaf_identity"]),
        "target_kind": target_kind,
        "occurrence_key": str(row["occurrence_key"]),
        "root_identity": str(row["root_identity"]),
        "sampling_arm": str(row["sampling_arm"]),
        "act": int(row["act"]),
    }


def _backfill_specs(
    candidate_rows: list[dict[str, Any]],
    attempted_ids: set[str],
    accepted_by_cell: Mapping[tuple[str, int, str], list[dict[str, Any]]],
    reserved_ids: set[str],
) -> dict[str, dict[str, Any]]:
    quotas = {
        **{
            (arm, act, "calibration"): count
            for arm in ARMS
            for act, count in ((1, 18), (2, 14))
        },
        **{
            (arm, act, "formal"): count
            for arm in ARMS
            for act, count in ((1, 178), (2, 142))
        },
    }
    specs: dict[str, dict[str, Any]] = {}
    for (arm, act, target_kind), quota in quotas.items():
        deficit = quota - len(accepted_by_cell.get((arm, act, target_kind), []))
        if deficit <= 0:
            continue
        cell_rows = _ordered_cell_rows(
            [
                row
                for row in candidate_rows
                if row.get("sampling_arm") == arm and row.get("act") == act
            ]
        )
        for row in cell_rows:
            identity = str(row["exact_leaf_identity"])
            if identity in attempted_ids or identity in reserved_ids:
                continue
            specs[identity] = _target_spec_for_row(row, target_kind)
            reserved_ids.add(identity)
            if (
                len(
                    [
                        spec
                        for spec in specs.values()
                        if spec["sampling_arm"] == arm
                        and spec["act"] == act
                        and spec["target_kind"] == target_kind
                    ]
                )
                >= deficit
            ):
                break
    return specs


def _git_head(repo_root: Path) -> str:
    try:
        value = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_root,
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
    except (OSError, subprocess.CalledProcessError) as exc:
        raise ValueError("cannot resolve STSRL collector code identity") from exc
    if not value:
        raise ValueError("STSRL collector code identity is empty")
    return value


def _root_cohort_digest(roots: list[dict[str, Any]]) -> str:
    identities = [str(root.get("_t084_source_identity", "")) for root in roots]
    if len(identities) != 460 or any(not identity for identity in identities):
        raise ValueError("T084 root cohort identities are incomplete")
    return hashlib.sha256("\n".join(identities).encode("utf-8")).hexdigest()


def _checkpoint_identities(
    checkpoint_paths: Mapping[str, str],
) -> dict[str, dict[str, Any]]:
    identities: dict[str, dict[str, Any]] = {}
    for arm in ARMS[1:]:
        path = Path(checkpoint_paths[arm]).resolve()
        if not path.is_file():
            raise ValueError(f"checkpoint is missing: {path}")
        actual = sha256_file(path)
        expected, filename = EXPECTED_STATIC_CHECKPOINTS[arm]
        if actual != expected:
            raise ValueError(f"checkpoint identity mismatch: {arm}")
        identities[arm] = {
            "path": str(path),
            "filename": filename,
            "sha256": actual,
            "bytes": path.stat().st_size,
        }
    return identities


def _run_identity(
    repo_root: Path,
    manifest_path: Path,
    roots: list[dict[str, Any]],
    native_build: Path,
    native_commit: str,
    checkpoint_paths: Mapping[str, str],
    output_path: Path,
    workers: int,
) -> tuple[dict[str, Any], dict[str, Any]]:
    workers = _validate_worker_count(workers)
    manifest_sha = sha256_file(manifest_path)
    expected_manifest_sha = EXPECTED_T064_ARTIFACTS["t064-curriculum-manifest.json"][0]
    if manifest_sha != expected_manifest_sha:
        raise ValueError("T064 curriculum manifest identity mismatch")
    checkpoint_identity = _checkpoint_identities(checkpoint_paths)
    code_identity = {
        "git_head": _git_head(repo_root),
        "collector_script_sha256": sha256_file(Path(__file__).resolve()),
        "target_module_sha256": sha256_file(
            repo_root
            / "src"
            / "sts_combat_rl"
            / "t084_search_v2_internal_leaf_target_generation.py"
        ),
    }
    identity = {
        "t064_manifest_sha256": manifest_sha,
        "root_cohort_sha256": _root_cohort_digest(roots),
        "native_commit": native_commit,
        "native_build": str(native_build.resolve()),
        "checkpoint_identities": checkpoint_identity,
        "code": code_identity,
    }
    configuration = {
        "task_id": "T084",
        "collector_schema_id": COLLECTOR_SCHEMA_ID,
        "progress_schema_id": PROGRESS_SCHEMA_ID,
        "root_count": 460,
        "acts": {"1": 256, "2": 204},
        "arms": list(ARMS),
        "search_simulations_per_root": 100,
        "include_potions": False,
        "workers": workers,
        "action_cap": 2048,
        "calibration_count": CALIBRATION_COUNT,
        "calibration_replicates": CALIBRATION_REPLICATES,
        "candidate_repetitions": list(CANDIDATE_REPETITIONS),
        "selection_policy": _SELECTION_POLICY,
        "target_replicates_per_attempt": CALIBRATION_REPLICATES,
        "parity_root_policy": "first eight Act1 and first eight Act2 source roots",
        "output_path": str(output_path.resolve()),
    }
    return identity, configuration


def _run_progress_collection(
    roots: list[dict[str, Any]],
    checkpoint_paths: dict[str, str],
    native_commit: str,
    workers: int,
    output_path: Path,
    progress: _ProgressStore,
) -> int:
    """Run the resumable path with bounded parent-memory aggregation."""

    workers = _validate_worker_count(workers)
    tasks = _stage_tasks(len(roots))
    _, candidate_failures, candidate_wall, candidate_workers = _run_pass(
        roots,
        checkpoint_paths,
        native_commit,
        workers,
        "candidate",
        {},
        progress=progress,
        stage_key="candidate",
        pass_index=0,
    )
    if candidate_failures:
        raise RuntimeError(
            "candidate pass incomplete: " + "; ".join(candidate_failures[:8])
        )
    candidate_successes = progress.successful_task_keys("candidate", tasks)
    if len(candidate_successes) != len(tasks):
        raise RuntimeError(
            "candidate pass incomplete: "
            f"{len(candidate_successes)}/{len(tasks)} task parts are successful"
        )

    # Candidate rows are decoded one task part at a time and reduced to the
    # fields needed for deterministic selection.  Full candidate rows remain
    # on disk until the final JSON encoder asks for them.
    candidate_metadata = list(_iter_candidate_metadata(progress, "candidate", tasks))
    occupancy_counts = Counter(
        str(row["exact_leaf_identity"]) for row in candidate_metadata
    )
    target_specs, selection_policy = _select_target_specs_with_policy(
        candidate_metadata
    )

    replay_passes: list[dict[str, Any]] = []
    target_stage_keys: list[str] = []
    target_worker_evidence: list[dict[str, Any]] = []
    attempted_ids: set[str] = set()
    accepted_by_cell: dict[tuple[str, int, str], list[dict[str, Any]]] = {}
    accepted_ids: set[str] = set()
    target_attempts: list[dict[str, Any]] = []
    current_specs = target_specs
    pass_index = 1
    while current_specs:
        scheduled_ids = set(current_specs)
        stage_key = f"selected_leaf_continuation_pass_{pass_index:04d}"
        _, pass_failures, pass_wall, pass_workers = _run_pass(
            roots,
            checkpoint_paths,
            native_commit,
            workers,
            "selected_leaf_continuation",
            current_specs,
            progress=progress,
            stage_key=stage_key,
            pass_index=pass_index,
            plan={"target_specs": current_specs},
        )
        if pass_failures:
            raise RuntimeError(
                f"selected-leaf replay pass {pass_index} incomplete: "
                + "; ".join(pass_failures[:8])
            )
        pass_successes = progress.successful_task_keys(stage_key, tasks)
        if len(pass_successes) != len(tasks):
            raise RuntimeError(
                f"selected-leaf replay pass {pass_index} incomplete: "
                f"{len(pass_successes)}/{len(tasks)} task parts are successful"
            )
        target_stage_keys.append(stage_key)
        attempted_ids.update(scheduled_ids)
        target_worker_evidence.append(pass_workers)
        returned_ids: set[str] = set()
        valid_rows = 0
        invalid_rows = 0
        for task, row_index, row in _iter_stage_field_rows(
            progress, stage_key, tasks, "target_rows"
        ):
            leaf_id = row.get("exact_leaf_identity")
            if not isinstance(leaf_id, str) or leaf_id not in current_specs:
                raise ValueError(
                    f"target row is not in scheduled target specs: {leaf_id}"
                )
            spec = current_specs[leaf_id]
            if row.get("target_kind") != spec.get("target_kind"):
                raise ValueError(f"target kind mismatch for {leaf_id}")
            returned_ids.add(leaf_id)
            usable = _target_row_has_full_replicates(row)
            if usable:
                valid_rows += 1
            else:
                invalid_rows += 1
            target_attempts.append(
                {
                    "exact_leaf_identity": leaf_id,
                    "occurrence_key": row.get("occurrence_key"),
                    "root_identity": row.get("root_identity"),
                    "sampling_arm": row.get("sampling_arm"),
                    "act": row.get("act"),
                    "target_kind": row.get("target_kind"),
                    "valid_256_replicates": usable,
                    "replay_pass": pass_index,
                    "backfill_used": pass_index > 1,
                }
            )
            if usable and leaf_id not in accepted_ids:
                descriptor = _target_spec_for_row(row, str(row.get("target_kind")))
                descriptor.update(
                    {
                        "_stage_key": stage_key,
                        "_task_key": _task_key(task),
                        "_row_index": row_index,
                    }
                )
                cell = (
                    str(row["sampling_arm"]),
                    int(row["act"]),
                    str(row["target_kind"]),
                )
                accepted_by_cell.setdefault(cell, []).append(descriptor)
                accepted_ids.add(leaf_id)
        for leaf_id, spec in current_specs.items():
            if leaf_id not in returned_ids:
                target_attempts.append(
                    {
                        "exact_leaf_identity": leaf_id,
                        "occurrence_key": spec.get("occurrence_key"),
                        "root_identity": spec.get("root_identity"),
                        "sampling_arm": spec.get("sampling_arm"),
                        "act": spec.get("act"),
                        "target_kind": spec.get("target_kind"),
                        "valid_256_replicates": False,
                        "replay_pass": pass_index,
                        "backfill_used": pass_index > 1,
                        "error": "scheduled occurrence produced no target row; see collector evidence",
                    }
                )
        replay_passes.append(
            {
                "pass_index": pass_index,
                "candidate_occurrence_count": len(current_specs),
                "worker_count": workers,
                "task_count": len(tasks),
                "task_ranges": "root indices 0..459 x three arms",
                "wall_clock_seconds": pass_wall,
                "worker_evidence": pass_workers,
                "valid_rows": valid_rows,
                "invalid_rows": invalid_rows,
            }
        )
        current_specs = _backfill_specs(
            candidate_metadata, attempted_ids, accepted_by_cell, set()
        )
        pass_index += 1

    calibration_descriptors = _accepted_descriptors(accepted_by_cell, "calibration")
    formal_descriptors = _accepted_descriptors(accepted_by_cell, "formal")
    calibration_by_identity: dict[str, Mapping[str, Any]] = {}
    for descriptor, row in _iter_located_target_rows(
        progress, target_stage_keys, tasks, calibration_descriptors
    ):
        identity = str(row.get("exact_leaf_identity"))
        if identity in calibration_by_identity:
            raise ValueError(f"duplicate calibration target row: {identity}")
        if row.get("target_kind") != "calibration":
            raise ValueError(
                f"calibration locator returned non-calibration row: {identity}"
            )
        calibration_by_identity[identity] = row
    calibration_rows = [
        calibration_by_identity[str(descriptor["exact_leaf_identity"])]
        for descriptor in calibration_descriptors
        if str(descriptor["exact_leaf_identity"]) in calibration_by_identity
    ]
    calibration = (
        select_repetition_count(calibration_rows)
        if len(calibration_rows) == CALIBRATION_COUNT
        else {"qualified": False, "reason": "exact 96 calibration rows unavailable"}
    )
    selected_n = calibration.get("selected_repetition_count")

    parity, parity_failures, parity_wall = _run_parity(
        roots,
        checkpoint_paths,
        native_commit,
        workers,
        progress=progress,
    )
    if parity_failures:
        raise RuntimeError(
            "parity preflight incomplete: " + "; ".join(parity_failures[:8])
        )

    target_wall = sum(item["wall_clock_seconds"] for item in replay_passes)
    total_wall = candidate_wall + target_wall + parity_wall
    selected_worker_summary = {
        "configured_worker_count": workers,
        "observed_worker_count": min(
            [item["observed_worker_count"] for item in target_worker_evidence]
            or [candidate_workers["observed_worker_count"]]
        ),
        "effective_worker_count": min(
            [item["effective_worker_count"] for item in target_worker_evidence]
            or [candidate_workers["effective_worker_count"]]
        ),
        "worker_pids": sorted(
            {pid for item in target_worker_evidence for pid in item["worker_pids"]}
        ),
        "host_logical_cpu_count": os.cpu_count(),
    }
    root_stage_key = target_stage_keys[-1] if target_stage_keys else "candidate"
    execution = {
        "schema_id": COLLECTOR_SCHEMA_ID,
        "generation_mode": "native_runtime_collector",
        "native_commit": native_commit,
        "search_simulations_per_root": 100,
        "worker_count": workers,
        "effective_worker_count": min(
            [candidate_workers["effective_worker_count"]]
            + [item["effective_worker_count"] for item in target_worker_evidence]
            + [parity["effective_worker_count"]]
        ),
        # These four arrays are supplied by row_streams below.  The placeholders
        # keep the final object schema identical without retaining their rows.
        "root_runs": None,
        "candidate_rows": None,
        "calibration_rows": None,
        "formal_rows": None,
        "calibration": calibration,
        "generation_passes": {
            "candidate": {
                "worker_count": workers,
                "effective_worker_count": candidate_workers["effective_worker_count"],
                "worker_evidence": candidate_workers,
                "task_count": len(tasks),
                "wall_clock_seconds": candidate_wall,
            },
            "selected_leaf_continuation": {
                "worker_count": workers,
                "task_count": len(tasks) * max(1, len(replay_passes)),
                "tasks_per_pass": len(tasks),
                "wall_clock_seconds": target_wall,
                "target_identity_count": len(target_specs),
                "worker_evidence": target_worker_evidence,
                "replay_passes": replay_passes,
                "target_attempts": target_attempts,
            },
            "parity_preflight": {
                "worker_count": workers,
                "effective_worker_count": parity["effective_worker_count"],
                "worker_evidence": parity["worker_evidence"],
                "task_count": 16 * len(ARMS),
                "task_ranges": "first eight Act1 and first eight Act2 source roots x three arms",
                "wall_clock_seconds": parity_wall,
            },
            "selection_policy": selection_policy,
            "backfill": {
                "policy": "same arm/Act cell; next root-first/canonical candidate only after 256-replicate failure",
                "target_attempts": target_attempts,
            },
        },
        "arm_configs": {
            "unguided_search_v2": {
                "policy_prior": False,
                "leaf_value": False,
                "checkpoint_sha256": None,
            },
            "prior_only_static_64001": {
                "policy_prior": True,
                "leaf_value": False,
                "checkpoint_sha256": EXPECTED_STATIC_CHECKPOINTS[
                    "prior_only_static_64001"
                ][0],
            },
            "prior_only_static_64002": {
                "policy_prior": True,
                "leaf_value": False,
                "checkpoint_sha256": EXPECTED_STATIC_CHECKPOINTS[
                    "prior_only_static_64002"
                ][0],
            },
        },
        "parity": parity,
        "failures": [],
        "shards": [
            {
                "worker_count": workers,
                "effective_worker_count": candidate_workers["effective_worker_count"],
                "task_count": len(tasks),
                "task_ranges": "candidate pass: root indices 0..459 x three arms",
                "wall_clock_seconds": candidate_wall,
                "worker_evidence": candidate_workers,
            },
            {
                "worker_count": workers,
                "effective_worker_count": min(
                    item["effective_worker_count"] for item in target_worker_evidence
                )
                if target_worker_evidence
                else 0,
                "task_count": len(tasks) * max(1, len(replay_passes)),
                "task_ranges": "selected_leaf_continuation pass: root indices 0..459 x three arms",
                "wall_clock_seconds": target_wall,
                "worker_evidence": selected_worker_summary,
            },
            {
                "worker_count": workers,
                "effective_worker_count": parity["effective_worker_count"],
                "task_count": 16 * len(ARMS),
                "task_ranges": "parity_preflight: first eight Act1 and first eight Act2 source roots x three arms",
                "wall_clock_seconds": parity_wall,
                "worker_evidence": parity["worker_evidence"],
            },
        ],
        "result_aggregation": {
            "mode": "progress_parts_streaming",
            "candidate_task_results": "read_one_verified_part_at_a_time",
            "target_task_results": "read_one_verified_part_at_a_time",
            "candidate_rows_in_memory_during_selection": 0,
            "formal_rows_in_memory_during_aggregation": 0,
            "calibration_rows_in_memory_during_metrics": len(calibration_rows),
            "selection_metadata_rows_in_memory": len(candidate_metadata),
        },
        "wall_clock_seconds": total_wall,
    }

    def formal_row_stream() -> Iterable[Mapping[str, Any]]:
        for _, row in _iter_located_target_rows(
            progress, target_stage_keys, tasks, formal_descriptors
        ):
            formal_row = dict(row)
            if isinstance(selected_n, int):
                replicates = formal_row.get("replicates")
                if not isinstance(replicates, list):
                    raise TypeError(
                        f"formal target row has no replicate list: {formal_row.get('exact_leaf_identity')}"
                    )
                formal_row["selected_repetition_count"] = selected_n
                formal_row["replicates"] = replicates[:selected_n]
            yield formal_row

    row_streams: dict[str, Iterable[object]] = {
        "root_runs": _iter_root_runs(progress, root_stage_key, tasks),
        "candidate_rows": _iter_candidate_rows_with_occupancy(
            progress, "candidate", tasks, occupancy_counts
        ),
        "calibration_rows": iter(calibration_rows),
        "formal_rows": formal_row_stream(),
    }
    _publish_streaming_json(output_path, execution, row_streams, progress)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--t064-manifest", type=Path, required=True)
    parser.add_argument("--native-build", type=Path, required=True)
    parser.add_argument("--native-commit", required=True)
    parser.add_argument("--static-64001", type=Path, required=True)
    parser.add_argument("--static-64002", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--progress-dir",
        type=Path,
        help=("ignored atomic checkpoint directory; omit for the original fresh run"),
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="resume the exact run recorded under --progress-dir",
    )
    parser.add_argument("--workers", type=_worker_count_argument, default=WORKER_COUNT)
    args = parser.parse_args()
    args.workers = _validate_worker_count(args.workers)
    if not args.native_build.is_dir():
        raise SystemExit(f"native build directory is missing: {args.native_build}")
    args.output = args.output.resolve()
    if args.resume and args.progress_dir is None:
        raise SystemExit("--resume requires --progress-dir")
    sys.path.insert(0, str(args.native_build))
    progress: _ProgressStore | None = None
    try:
        roots = _load_selected_roots(args.t064_manifest)
        checkpoint_paths = {
            "prior_only_static_64001": str(args.static_64001),
            "prior_only_static_64002": str(args.static_64002),
        }
        if args.progress_dir is not None:
            progress_dir = args.progress_dir.resolve()
            progress_path = progress_dir / "t084-native-collector.progress.json"
            identity, configuration = _run_identity(
                Path(__file__).resolve().parents[1],
                args.t064_manifest.resolve(),
                roots,
                args.native_build,
                args.native_commit,
                checkpoint_paths,
                args.output,
                args.workers,
            )
            progress = _ProgressStore(
                progress_path,
                identity=identity,
                configuration=configuration,
                output_path=args.output,
                resume=args.resume,
            )
            if progress.already_complete:
                return 0
            return _run_progress_collection(
                roots,
                checkpoint_paths,
                args.native_commit,
                args.workers,
                args.output,
                progress,
            )
        tasks = len(roots) * len(ARMS)
        candidate_runs, candidate_failures, candidate_wall, candidate_workers = (
            _run_pass(
                roots,
                checkpoint_paths,
                args.native_commit,
                args.workers,
                "candidate",
                {},
                progress=progress,
                stage_key="candidate",
                pass_index=0,
            )
        )
        if candidate_failures or len(candidate_runs) != tasks:
            raise RuntimeError(
                "candidate pass incomplete: " + "; ".join(candidate_failures[:8])
            )
        candidate_rows = [
            candidate
            for run in candidate_runs
            for candidate in run.get("candidate_rows", [])
        ]
        occupancy_counts = Counter(
            str(row.get("exact_leaf_identity")) for row in candidate_rows
        )
        for row in candidate_rows:
            hidden = row.get("exact_hidden_state_payload")
            if isinstance(hidden, dict):
                leaf_identity = str(row.get("exact_leaf_identity"))
                hidden["occupancy_duplicate"] = occupancy_counts[leaf_identity] > 1
                hidden["occupancy_count"] = occupancy_counts[leaf_identity]
        target_specs, selection_policy = _select_target_specs_with_policy(
            candidate_rows
        )
        target_runs: list[dict[str, Any]] = []
        replay_passes: list[dict[str, Any]] = []
        target_worker_evidence: list[dict[str, Any]] = []
        attempted_ids: set[str] = set()
        accepted_by_cell: dict[tuple[str, int, str], list[dict[str, Any]]] = {}
        accepted_ids: set[str] = set()
        target_attempts: list[dict[str, Any]] = []
        current_specs = target_specs
        pass_index = 1
        while current_specs:
            scheduled_ids = set(current_specs)
            stage_key = f"selected_leaf_continuation_pass_{pass_index:04d}"
            pass_runs, pass_failures, pass_wall, pass_workers = _run_pass(
                roots,
                checkpoint_paths,
                args.native_commit,
                args.workers,
                "selected_leaf_continuation",
                current_specs,
                progress=progress,
                stage_key=stage_key,
                pass_index=pass_index,
                plan={"target_specs": current_specs},
            )
            if pass_failures or len(pass_runs) != tasks:
                raise RuntimeError(
                    f"selected-leaf replay pass {pass_index} incomplete: "
                    + "; ".join(pass_failures[:8])
                )
            target_runs = pass_runs
            attempted_ids.update(scheduled_ids)
            target_worker_evidence.append(pass_workers)
            pass_rows = [
                target for run in pass_runs for target in run.get("target_rows", [])
            ]
            returned_ids = {str(row["exact_leaf_identity"]) for row in pass_rows}
            for leaf_id, spec in current_specs.items():
                if leaf_id not in returned_ids:
                    target_attempts.append(
                        {
                            "exact_leaf_identity": leaf_id,
                            "occurrence_key": spec.get("occurrence_key"),
                            "root_identity": spec.get("root_identity"),
                            "sampling_arm": spec.get("sampling_arm"),
                            "act": spec.get("act"),
                            "target_kind": spec.get("target_kind"),
                            "valid_256_replicates": False,
                            "replay_pass": pass_index,
                            "backfill_used": pass_index > 1,
                            "error": "scheduled occurrence produced no target row; see collector evidence",
                        }
                    )
            for row in pass_rows:
                leaf_id = str(row["exact_leaf_identity"])
                cell = (
                    str(row["sampling_arm"]),
                    int(row["act"]),
                    str(row["target_kind"]),
                )
                attempted_ids.add(leaf_id)
                usable = _target_row_has_full_replicates(row)
                target_attempts.append(
                    {
                        "exact_leaf_identity": leaf_id,
                        "occurrence_key": row.get("occurrence_key"),
                        "root_identity": row.get("root_identity"),
                        "sampling_arm": row.get("sampling_arm"),
                        "act": row.get("act"),
                        "target_kind": row.get("target_kind"),
                        "valid_256_replicates": usable,
                        "replay_pass": pass_index,
                        "backfill_used": pass_index > 1,
                    }
                )
                if usable and leaf_id not in accepted_ids:
                    accepted_by_cell.setdefault(cell, []).append(row)
                    accepted_ids.add(leaf_id)
            replay_passes.append(
                {
                    "pass_index": pass_index,
                    "candidate_occurrence_count": len(current_specs),
                    "worker_count": args.workers,
                    "task_count": tasks,
                    "task_ranges": "root indices 0..459 x three arms",
                    "wall_clock_seconds": pass_wall,
                    "worker_evidence": pass_workers,
                    "valid_rows": sum(
                        1 for row in pass_rows if _target_row_has_full_replicates(row)
                    ),
                    "invalid_rows": sum(
                        1
                        for row in pass_rows
                        if not _target_row_has_full_replicates(row)
                    ),
                }
            )
            current_specs = _backfill_specs(
                candidate_rows, attempted_ids, accepted_by_cell, set()
            )
            pass_index += 1
        calibration_rows = [
            row
            for rows in accepted_by_cell.values()
            for row in rows
            if row.get("target_kind") == "calibration"
        ]
        formal_rows = [
            row
            for rows in accepted_by_cell.values()
            for row in rows
            if row.get("target_kind") == "formal"
        ]
        calibration = (
            select_repetition_count(calibration_rows)
            if len(calibration_rows) == 96
            else {"qualified": False, "reason": "exact 96 calibration rows unavailable"}
        )
        selected_n = calibration.get("selected_repetition_count")
        if isinstance(selected_n, int):
            for row in formal_rows:
                row["selected_repetition_count"] = selected_n
                row["replicates"] = row["replicates"][:selected_n]
        parity, parity_failures, parity_wall = _run_parity(
            roots,
            checkpoint_paths,
            args.native_commit,
            args.workers,
            progress=progress,
        )
        if parity_failures:
            raise RuntimeError(
                "parity preflight incomplete: " + "; ".join(parity_failures[:8])
            )
        root_runs = target_runs or candidate_runs
        failures: list[str] = []
        target_wall = sum(item["wall_clock_seconds"] for item in replay_passes)
        total_wall = candidate_wall + target_wall + parity_wall
        selected_worker_summary = {
            "configured_worker_count": args.workers,
            "observed_worker_count": min(
                [item["observed_worker_count"] for item in target_worker_evidence]
                or [candidate_workers["observed_worker_count"]]
            ),
            "effective_worker_count": min(
                [item["effective_worker_count"] for item in target_worker_evidence]
                or [candidate_workers["effective_worker_count"]]
            ),
            "worker_pids": sorted(
                {pid for item in target_worker_evidence for pid in item["worker_pids"]}
            ),
            "host_logical_cpu_count": os.cpu_count(),
        }
        execution = {
            "schema_id": COLLECTOR_SCHEMA_ID,
            "generation_mode": "native_runtime_collector",
            "native_commit": args.native_commit,
            "search_simulations_per_root": 100,
            "worker_count": args.workers,
            "effective_worker_count": min(
                [candidate_workers["effective_worker_count"]]
                + [item["effective_worker_count"] for item in target_worker_evidence]
                + [parity["effective_worker_count"]]
            ),
            "root_runs": [
                {
                    key: value
                    for key, value in run.items()
                    if key not in ("candidate_rows", "target_rows")
                }
                for run in root_runs
            ],
            "candidate_rows": candidate_rows,
            "calibration_rows": calibration_rows,
            "formal_rows": formal_rows,
            "calibration": calibration,
            "generation_passes": {
                "candidate": {
                    "worker_count": args.workers,
                    "effective_worker_count": candidate_workers[
                        "effective_worker_count"
                    ],
                    "worker_evidence": candidate_workers,
                    "task_count": tasks,
                    "wall_clock_seconds": candidate_wall,
                },
                "selected_leaf_continuation": {
                    "worker_count": args.workers,
                    "task_count": tasks * max(1, len(replay_passes)),
                    "tasks_per_pass": tasks,
                    "wall_clock_seconds": target_wall,
                    "target_identity_count": len(target_specs),
                    "worker_evidence": target_worker_evidence,
                    "replay_passes": replay_passes,
                    "target_attempts": target_attempts,
                },
                "parity_preflight": {
                    "worker_count": args.workers,
                    "effective_worker_count": parity["effective_worker_count"],
                    "worker_evidence": parity["worker_evidence"],
                    "task_count": 16 * len(ARMS),
                    "task_ranges": "first eight Act1 and first eight Act2 source roots x three arms",
                    "wall_clock_seconds": parity_wall,
                },
                "selection_policy": selection_policy,
                "backfill": {
                    "policy": "same arm/Act cell; next root-first/canonical candidate only after 256-replicate failure",
                    "target_attempts": target_attempts,
                },
            },
            "arm_configs": {
                "unguided_search_v2": {
                    "policy_prior": False,
                    "leaf_value": False,
                    "checkpoint_sha256": None,
                },
                "prior_only_static_64001": {
                    "policy_prior": True,
                    "leaf_value": False,
                    "checkpoint_sha256": EXPECTED_STATIC_CHECKPOINTS[
                        "prior_only_static_64001"
                    ][0],
                },
                "prior_only_static_64002": {
                    "policy_prior": True,
                    "leaf_value": False,
                    "checkpoint_sha256": EXPECTED_STATIC_CHECKPOINTS[
                        "prior_only_static_64002"
                    ][0],
                },
            },
            "parity": parity,
            "failures": failures + parity_failures,
            "shards": [
                {
                    "worker_count": args.workers,
                    "effective_worker_count": candidate_workers[
                        "effective_worker_count"
                    ],
                    "task_count": tasks,
                    "task_ranges": "candidate pass: root indices 0..459 x three arms",
                    "wall_clock_seconds": candidate_wall,
                    "worker_evidence": candidate_workers,
                },
                {
                    "worker_count": args.workers,
                    "effective_worker_count": min(
                        item["effective_worker_count"]
                        for item in target_worker_evidence
                    )
                    if target_worker_evidence
                    else 0,
                    "task_count": tasks * max(1, len(replay_passes)),
                    "task_ranges": "selected_leaf_continuation pass: root indices 0..459 x three arms",
                    "wall_clock_seconds": target_wall,
                    "worker_evidence": selected_worker_summary,
                },
                {
                    "worker_count": args.workers,
                    "effective_worker_count": parity["effective_worker_count"],
                    "task_count": 16 * len(ARMS),
                    "task_ranges": "parity_preflight: first eight Act1 and first eight Act2 source roots x three arms",
                    "wall_clock_seconds": parity_wall,
                    "worker_evidence": parity["worker_evidence"],
                },
            ],
            "wall_clock_seconds": total_wall,
        }
        final_bytes = _json_bytes(execution)
        expected_output = {
            "path": str(args.output),
            "bytes": len(final_bytes),
            "sha256": hashlib.sha256(final_bytes).hexdigest(),
        }
        if progress is not None:
            progress.prepare_final(expected_output)
        _write_json(args.output, execution)
        if progress is not None:
            actual_output = {
                "path": str(args.output),
                "bytes": args.output.stat().st_size,
                "sha256": sha256_file(args.output),
            }
            progress.mark_complete(actual_output)
        return 0
    except Exception as exc:  # noqa: BLE001 - leave resumable failure evidence
        if progress is not None:
            progress.mark_failed(exc)
        print(f"T084 collector failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
