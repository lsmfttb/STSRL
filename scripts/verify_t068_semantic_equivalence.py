#!/usr/bin/env python3
"""Prove that observing the T068 callback boundary does not change T067."""

from __future__ import annotations

import argparse
from collections.abc import Mapping
from dataclasses import dataclass, field
import hashlib
import json
import math
from pathlib import Path
import re
from time import perf_counter
from typing import Any

from sts_combat_rl.commands.model_guided_oracle_search import (
    build_torch_guidance_scorer_from_checkpoint,
)
from sts_combat_rl.commands.t062_battle_search_v2 import (
    run_t062_comparison_from_cohort_path,
    run_t062_input_preflight_from_paths,
)
from sts_combat_rl.commands.t068_checkout import verify_exact_git_checkout
from sts_combat_rl.sim.action_space import ActionSpaceConfig
from sts_combat_rl.sim.battle_search_v2 import BattleSearchV2Controller
from sts_combat_rl.sim.battle_search_v2_cost import public_node_cache_key
from sts_combat_rl.sim.lightspeed import LightSpeedAdapter
from sts_combat_rl.sim.policy import DecisionContext
from sts_combat_rl.sim.search_guidance_inference import SearchGuidanceInferenceResult


SCHEMA_ID = "t068-native-boundary-semantic-equivalence-v1"
NATIVE_COMMIT = "3cb9ebecb87c38044b34aa0e013d42b222a04087"
SOURCE_MANIFEST_SHA256 = (
    "2f4bd6710a152b080a2c6e4cfbaf509148ffb27d0139a9250f1a0ee19efd6631"
)
GUIDED_ARMS = ("prior_only", "value_only", "prior_value")


@dataclass
class RecordingScorer:
    base: Any
    outputs: dict[tuple[str, bytes], dict[str, Any]] = field(default_factory=dict)
    input_occurrence_sequence: list[str] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)

    @property
    def name(self) -> str:
        return self.base.name

    @property
    def checkpoint_provenance(self) -> Any:
        return self.base.checkpoint_provenance

    @property
    def provenance_config(self) -> Mapping[str, Any]:
        return self.base.checkpoint_provenance.to_dict()

    def score_decision_context(
        self, context: DecisionContext
    ) -> SearchGuidanceInferenceResult:
        result = self.base.score_decision_context(context)
        key = public_node_cache_key(context)
        if key is None:
            self.problems.append(
                "model input did not produce a complete public-node identity"
            )
        else:
            self.input_occurrence_sequence.append(key[0])
            payload = _result_payload(result)
            prior = self.outputs.get(key)
            if prior is not None and _mismatch(prior, payload, 1e-6) is not None:
                self.problems.append(
                    "same public node produced non-deterministic model output"
                )
            self.outputs.setdefault(key, payload)
        return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cohort", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--t061-retention-manifest", type=Path, required=True)
    parser.add_argument("--preflight-output", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--code-commit", required=True)
    args = parser.parse_args()
    if not re.fullmatch(r"[0-9a-f]{40}", args.code_commit):
        raise SystemExit(
            "T068 semantic gate requires an exact 40-character code commit"
        )
    _verify_checkout(Path.cwd(), args.code_commit)
    _verify_source_manifest(Path("docs/sts_lightspeed_source_manifest.json"))
    if args.output.exists() or args.preflight_output.exists():
        raise SystemExit("T068 semantic gate refuses to overwrite output or preflight")
    preflight = run_t062_input_preflight_from_paths(
        output_path=args.preflight_output,
        t061_retention_manifest_path=args.t061_retention_manifest,
        t052_cohort_path=args.cohort,
        t043_checkpoint_path=args.checkpoint,
    )
    if preflight.get("command_passed") is not True:
        raise SystemExit("T068 semantic preflight failed")
    started = perf_counter()
    untraced_arms, untraced = _arms(args.checkpoint, trace=False)
    traced_arms, traced = _arms(args.checkpoint, trace=True)
    common = dict(
        adapter_factory=lambda: LightSpeedAdapter(seed=1, ascension=20),
        cohort_path=args.cohort,
        action_space=ActionSpaceConfig.initial_no_potions(),
        max_battle_steps=200,
        family="nominal",
        worker_count=1,
        shard_count=1,
        record_range="0:1",
    )
    untraced_report = run_t062_comparison_from_cohort_path(
        controller_arms=untraced_arms, **common
    )
    traced_report = run_t062_comparison_from_cohort_path(
        controller_arms=traced_arms, **common
    )
    problems: list[str] = []
    arms: dict[str, Any] = {}
    for arm in GUIDED_ARMS:
        arm_problems = [*untraced[arm].problems, *traced[arm].problems]
        if set(untraced[arm].outputs) != set(traced[arm].outputs):
            arm_problems.append("public-node request identities differ")
        for key in set(untraced[arm].outputs) & set(traced[arm].outputs):
            mismatch = _mismatch(
                untraced[arm].outputs[key], traced[arm].outputs[key], 1e-6
            )
            if mismatch:
                arm_problems.append("policy/value output mismatch: " + mismatch)
        left = untraced_report["arms"][arm]["records"][0]
        right = traced_report["arms"][arm]["records"][0]
        for field_name in (
            "source_checkpoint_id",
            "termination_status",
            "terminal_absolute_hp",
            "decision_count",
            "outer_simulator_steps",
            "structured_battle_outcome",
            "terminal_battle_resources",
        ):
            if left.get(field_name) != right.get(field_name):
                arm_problems.append(f"battle field differs: {field_name}")
        selected_left = _selected_identities(left)
        selected_right = _selected_identities(right)
        if not selected_left or not selected_right:
            arm_problems.append(
                "selected occurrence-safe legal action identities are missing"
            )
        if selected_left != selected_right:
            arm_problems.append(
                "selected occurrence-safe legal action identities differ"
            )
        if _native_semantic_values(left) != _native_semantic_values(right):
            arm_problems.append("native root/traversal/chance-RNG telemetry differs")
        requests = _schema_values(right, "t068-native-callback-request-trace-v1")
        request_items = [
            item
            for value in requests
            for item in value.get("requests", [])
            if isinstance(item, Mapping)
        ]
        if not request_items or any(
            item.get("response_count") != 1 for item in request_items
        ):
            arm_problems.append("trace has missing request or response")
        traced_request_sequence = [
            item.get("public_input_identity") for item in request_items
        ]
        if untraced[arm].input_occurrence_sequence != traced_request_sequence:
            arm_problems.append(
                "untraced scorer input and traced request occurrence sequences differ"
            )
        arms[arm] = {
            "policy_value_tolerance": 1e-6,
            "model_output_exact_within_tolerance": not any(
                "output mismatch" in item for item in arm_problems
            ),
            "selected_action_identity_exact": selected_left == selected_right
            and bool(selected_left),
            "request_occurrence_sequence_exact": untraced[arm].input_occurrence_sequence
            == traced_request_sequence,
            "request_count": len(request_items),
            "problems": arm_problems,
            "command_passed": not arm_problems,
        }
        problems.extend(f"{arm}: {problem}" for problem in arm_problems)
    report = {
        "schema_id": SCHEMA_ID,
        "schema_version": 1,
        "task_id": "T068",
        "code_commit": args.code_commit,
        "native_commit": NATIVE_COMMIT,
        "record_range": "0:1",
        "worker_count": 1,
        "shard_count": 1,
        "single_worker_reason": "one retained battle semantic smoke; not a substantial calibration or audit stage",
        "compared_controller_pairs": "accepted_t067_untraced_vs_t068_trace_probe",
        "elapsed_wall_clock_seconds": perf_counter() - started,
        "arms": arms,
        "preflight": preflight,
        "problems": problems,
        "command_passed": not problems,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return 0 if report["command_passed"] else 1


def _arms(
    checkpoint: Path, *, trace: bool
) -> tuple[list[tuple[str, BattleSearchV2Controller]], dict[str, RecordingScorer]]:
    labels = ("baseline", *GUIDED_ARMS)
    recorders = {
        arm: RecordingScorer(build_torch_guidance_scorer_from_checkpoint(checkpoint))
        for arm in labels
    }
    return [
        (
            arm,
            BattleSearchV2Controller(
                simulations=1,
                scorer=recorders[arm],
                ablation=arm,
                action_space=ActionSpaceConfig.initial_no_potions(),
                inference_cache_enabled=arm != "baseline",
                callback_dependency_trace_enabled=trace and arm != "baseline",
            ),
        )
        for arm in labels
    ], recorders


def _result_payload(result: SearchGuidanceInferenceResult) -> dict[str, Any]:
    return {
        "action_scores": [
            {
                "legal_action_index": item.legal_action_index,
                "action_identity": dict(item.action_identity),
                "policy_probability": item.policy_probability,
            }
            for item in result.action_scores
        ],
        "value_prediction": None
        if result.value_prediction is None
        else result.value_prediction.to_dict(),
    }


def _selected_identities(value: Mapping[str, Any]) -> list[dict[str, Any]]:
    return [
        dict(item["selected_action_identity"])
        for item in _schema_values(value, "native-battle-search-root-v1")
        if isinstance(item.get("selected_action_identity"), Mapping)
    ]


def _schema_values(value: Any, schema: str) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    if isinstance(value, Mapping):
        if value.get("schema_id") == schema:
            found.append(dict(value))
        for child in value.values():
            found.extend(_schema_values(child, schema))
    elif isinstance(value, list):
        for child in value:
            found.extend(_schema_values(child, schema))
    return found


def _native_semantic_values(value: Any) -> list[dict[str, Any]]:
    """Compare native traversal/chance/RNG payloads without volatile timings."""

    values: list[dict[str, Any]] = []
    if isinstance(value, Mapping):
        schema = value.get("schema_id")
        if isinstance(schema, str) and schema.startswith("native-battle-search"):
            values.append(_without_timing(value))
        for child in value.values():
            values.extend(_native_semantic_values(child))
    elif isinstance(value, list):
        for child in value:
            values.extend(_native_semantic_values(child))
    return values


def _without_timing(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            str(key): _without_timing(item)
            for key, item in value.items()
            if not any(
                token in str(key).lower() for token in ("time", "timing", "elapsed")
            )
        }
    if isinstance(value, list):
        return [_without_timing(item) for item in value]
    return value


def _mismatch(left: Any, right: Any, tolerance: float, path: str = "") -> str | None:
    if (
        isinstance(left, (int, float))
        and not isinstance(left, bool)
        and isinstance(right, (int, float))
        and not isinstance(right, bool)
    ):
        return (
            None
            if math.isclose(float(left), float(right), abs_tol=tolerance, rel_tol=0.0)
            else f"{path}: {left!r} != {right!r}"
        )
    if isinstance(left, Mapping) and isinstance(right, Mapping):
        if set(left) != set(right):
            return f"{path}: mapping keys differ"
        for key in sorted(left):
            result = _mismatch(left[key], right[key], tolerance, f"{path}.{key}")
            if result:
                return result
        return None
    if isinstance(left, list) and isinstance(right, list):
        if len(left) != len(right):
            return f"{path}: list lengths differ"
        for index, (a, b) in enumerate(zip(left, right, strict=True)):
            result = _mismatch(a, b, tolerance, f"{path}[{index}]")
            if result:
                return result
        return None
    return None if left == right else f"{path}: {left!r} != {right!r}"


def _verify_checkout(root: Path, commit: str) -> None:
    try:
        verify_exact_git_checkout(root, commit)
    except ValueError as exc:
        raise SystemExit(f"T068 semantic {exc}") from exc


def _verify_source_manifest(path: Path) -> None:
    if hashlib.sha256(path.read_bytes()).hexdigest() != SOURCE_MANIFEST_SHA256:
        raise SystemExit("T068 source manifest hash does not match T067")
    if (
        json.loads(path.read_text(encoding="utf-8"))
        .get("integration", {})
        .get("commit")
        != NATIVE_COMMIT
    ):
        raise SystemExit("T068 native source manifest commit does not match T067")


if __name__ == "__main__":
    raise SystemExit(main())
