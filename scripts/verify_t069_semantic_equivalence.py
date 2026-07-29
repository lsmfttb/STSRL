#!/usr/bin/env python3
"""Compare accepted T068/T067 Search v2 with the T069 projection on 0:1."""

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
from sts_combat_rl.commands.t069_public_context_projection import (
    T069_SEMANTIC_SCHEMA_ID,
)
from sts_combat_rl.sim.action_space import ActionSpaceConfig
from sts_combat_rl.sim.battle_search_v2 import BattleSearchV2Controller
from sts_combat_rl.sim.battle_search_v2_cost import public_node_cache_key
from sts_combat_rl.sim.lightspeed import LightSpeedAdapter
from sts_combat_rl.sim.policy import DecisionContext
from sts_combat_rl.sim.search_guidance_inference import SearchGuidanceInferenceResult


NATIVE_COMMIT = "3cb9ebecb87c38044b34aa0e013d42b222a04087"
SOURCE_MANIFEST_SHA256 = (
    "2f4bd6710a152b080a2c6e4cfbaf509148ffb27d0139a9250f1a0ee19efd6631"
)
T068_MANIFEST_SHA256 = (
    "bf974134343cea06e9f58e227f4752002ee3cebc14902206991f9fe81752c678"
)
GUIDED_ARMS = ("prior_only", "value_only", "prior_value")


@dataclass
class RecordingScorer:
    base: Any
    projected: bool
    outputs: list[dict[str, Any]] = field(default_factory=list)
    input_identities: list[str] = field(default_factory=list)
    complete_inputs: list[bytes] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)

    @property
    def name(self) -> str:
        return self.base.name

    @property
    def checkpoint_provenance(self) -> Any:
        return self.base.checkpoint_provenance

    @property
    def provenance_config(self) -> Mapping[str, Any]:
        return self.base.provenance_config

    def prepare_public_context_projection(self, public_run_context: Mapping[str, Any]):
        return self.base.prepare_public_context_projection(public_run_context)

    def score_decision_context(
        self,
        context: DecisionContext,
    ) -> SearchGuidanceInferenceResult:
        result = self.base.score_decision_context(context)
        self._record(context, result)
        return result

    def score_decision_context_with_projection(
        self,
        context: DecisionContext,
        projection: Any,
    ) -> SearchGuidanceInferenceResult:
        result = self.base.score_decision_context_with_projection(
            context,
            projection,
        )
        self._record(context, result)
        return result

    def _record(
        self,
        context: DecisionContext,
        result: SearchGuidanceInferenceResult,
    ) -> None:
        key = public_node_cache_key(context)
        if key is None:
            self.problems.append("scorer input lacks complete public-node identity")
            return
        self.input_identities.append(key[0])
        self.complete_inputs.append(key[1])
        self.outputs.append(_result_payload(result))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cohort", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--t061-retention-manifest", type=Path, required=True)
    parser.add_argument("--t068-retention-manifest", type=Path, required=True)
    parser.add_argument("--preflight-output", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--code-commit", required=True)
    args = parser.parse_args()
    if not re.fullmatch(r"[0-9a-f]{40}", args.code_commit):
        raise SystemExit("T069 semantic gate requires an exact code commit")
    if args.output.exists() or args.preflight_output.exists():
        raise SystemExit("T069 semantic gate refuses to overwrite output")
    try:
        verify_exact_git_checkout(Path.cwd(), args.code_commit)
    except ValueError as exc:
        raise SystemExit(f"T069 semantic {exc}") from exc
    _verify_sha256(
        Path("docs/sts_lightspeed_source_manifest.json"),
        SOURCE_MANIFEST_SHA256,
    )
    _verify_sha256(args.t068_retention_manifest, T068_MANIFEST_SHA256)
    preflight = run_t062_input_preflight_from_paths(
        output_path=args.preflight_output,
        t061_retention_manifest_path=args.t061_retention_manifest,
        t052_cohort_path=args.cohort,
        t043_checkpoint_path=args.checkpoint,
    )
    if preflight.get("command_passed") is not True:
        raise SystemExit("T069 semantic input preflight failed")

    started = perf_counter()
    before_arms, before_recorders = _arms(args.checkpoint, projected=False)
    after_arms, after_recorders = _arms(args.checkpoint, projected=True)
    common = {
        "adapter_factory": lambda: LightSpeedAdapter(seed=1, ascension=20),
        "cohort_path": args.cohort,
        "action_space": ActionSpaceConfig.initial_no_potions(),
        "max_battle_steps": 200,
        "family": "nominal",
        "worker_count": 1,
        "shard_count": 1,
        "record_range": "0:1",
    }
    before = run_t062_comparison_from_cohort_path(
        controller_arms=before_arms,
        **common,
    )
    after = run_t062_comparison_from_cohort_path(
        controller_arms=after_arms,
        **common,
    )
    problems: list[str] = []
    arm_reports: dict[str, Any] = {}
    for arm in GUIDED_ARMS:
        arm_problems = [
            *before_recorders[arm].problems,
            *after_recorders[arm].problems,
        ]
        left_recorder = before_recorders[arm]
        right_recorder = after_recorders[arm]
        if left_recorder.complete_inputs != right_recorder.complete_inputs:
            arm_problems.append("complete public-node scorer inputs differ")
        if len(left_recorder.outputs) != len(right_recorder.outputs):
            arm_problems.append("scorer output occurrence counts differ")
        else:
            for left, right in zip(
                left_recorder.outputs,
                right_recorder.outputs,
                strict=True,
            ):
                mismatch = _mismatch(left, right, 1e-6)
                if mismatch is not None:
                    arm_problems.append("policy/value output mismatch: " + mismatch)
                    break
        left_record = before["arms"][arm]["records"][0]
        right_record = after["arms"][arm]["records"][0]
        for field_name in (
            "source_checkpoint_id",
            "termination_status",
            "terminal_absolute_hp",
            "decision_count",
            "outer_simulator_steps",
            "structured_battle_outcome",
            "terminal_battle_resources",
        ):
            if left_record.get(field_name) != right_record.get(field_name):
                arm_problems.append(f"battle field differs: {field_name}")
        selected_left = _selected_identities(left_record)
        selected_right = _selected_identities(right_record)
        if not selected_left or selected_left != selected_right:
            arm_problems.append("selected occurrence-safe action identities differ")
        if _native_semantics(left_record) != _native_semantics(right_record):
            arm_problems.append("native traversal/chance/RNG semantics differ")
        arm_reports[arm] = {
            "request_count": len(left_recorder.outputs),
            "complete_scorer_input_exact": (
                left_recorder.complete_inputs == right_recorder.complete_inputs
            ),
            "policy_value_tolerance": 1e-6,
            "policy_value_outputs_match": not any(
                "output mismatch" in problem for problem in arm_problems
            ),
            "selected_action_identity_exact": (
                bool(selected_left) and selected_left == selected_right
            ),
            "native_traversal_rng_terminal_exact": not any(
                "semantics differ" in problem or "battle field" in problem
                for problem in arm_problems
            ),
            "problems": arm_problems,
            "command_passed": not arm_problems,
        }
        problems.extend(f"{arm}: {problem}" for problem in arm_problems)

    report = {
        "schema_id": T069_SEMANTIC_SCHEMA_ID,
        "schema_version": 1,
        "task_id": "T069",
        "code_commit": args.code_commit,
        "native_commit": NATIVE_COMMIT,
        "record_range": "0:1",
        "worker_count": 1,
        "shard_count": 1,
        "single_worker_reason": (
            "one retained battle semantic smoke; not a substantial calibration stage"
        ),
        "compared_controller_pairs": (
            "accepted_t068_t067_unprojected_vs_t069_search_scope_projection"
        ),
        "elapsed_wall_clock_seconds": perf_counter() - started,
        "arms": arm_reports,
        "preflight": preflight,
        "problems": problems,
        "command_passed": not problems,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return 0 if report["command_passed"] else 1


def _arms(
    checkpoint: Path,
    *,
    projected: bool,
) -> tuple[
    list[tuple[str, BattleSearchV2Controller]],
    dict[str, RecordingScorer],
]:
    recorders = {
        arm: RecordingScorer(
            build_torch_guidance_scorer_from_checkpoint(checkpoint),
            projected=projected,
        )
        for arm in ("baseline", *GUIDED_ARMS)
    }
    return [
        (
            arm,
            BattleSearchV2Controller(
                simulations=1,
                scorer=recorders[arm],
                ablation=arm,  # type: ignore[arg-type]
                action_space=ActionSpaceConfig.initial_no_potions(),
                inference_cache_enabled=arm != "baseline",
                inference_cache_capacity=32768,
                public_context_projection_enabled=projected and arm != "baseline",
            ),
        )
        for arm in ("baseline", *GUIDED_ARMS)
    ], recorders


def _result_payload(result: SearchGuidanceInferenceResult) -> dict[str, Any]:
    return {
        "action_scores": [
            {
                "legal_action_index": item.legal_action_index,
                "action_identity": dict(item.action_identity),
                "policy_logit": item.policy_logit,
                "policy_probability": item.policy_probability,
            }
            for item in result.action_scores
        ],
        "value_prediction": (
            None
            if result.value_prediction is None
            else result.value_prediction.to_dict()
        ),
    }


def _selected_identities(value: Mapping[str, Any]) -> list[dict[str, Any]]:
    return [
        dict(item["selected_action_identity"])
        for item in _schema_values(value, "native-battle-search-root-v1")
        if isinstance(item.get("selected_action_identity"), Mapping)
    ]


def _schema_values(value: Any, schema_id: str) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    if isinstance(value, Mapping):
        if value.get("schema_id") == schema_id:
            found.append(dict(value))
        for child in value.values():
            found.extend(_schema_values(child, schema_id))
    elif isinstance(value, list):
        for child in value:
            found.extend(_schema_values(child, schema_id))
    return found


def _native_semantics(value: Any) -> list[dict[str, Any]]:
    values: list[dict[str, Any]] = []
    if isinstance(value, Mapping):
        schema_id = value.get("schema_id")
        if isinstance(schema_id, str) and schema_id.startswith("native-battle-search"):
            values.append(_without_timing(value))
        for child in value.values():
            values.extend(_native_semantics(child))
    elif isinstance(value, list):
        for child in value:
            values.extend(_native_semantics(child))
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


def _mismatch(
    left: Any,
    right: Any,
    tolerance: float,
    path: str = "",
) -> str | None:
    if (
        isinstance(left, (int, float))
        and not isinstance(left, bool)
        and isinstance(right, (int, float))
        and not isinstance(right, bool)
    ):
        if math.isclose(float(left), float(right), abs_tol=tolerance, rel_tol=0.0):
            return None
        return f"{path}: {left!r} != {right!r}"
    if isinstance(left, Mapping) and isinstance(right, Mapping):
        if set(left) != set(right):
            return f"{path}: mapping keys differ"
        for key in sorted(left):
            mismatch = _mismatch(
                left[key],
                right[key],
                tolerance,
                f"{path}.{key}",
            )
            if mismatch is not None:
                return mismatch
        return None
    if isinstance(left, list) and isinstance(right, list):
        if len(left) != len(right):
            return f"{path}: list lengths differ"
        for index, (a, b) in enumerate(zip(left, right, strict=True)):
            mismatch = _mismatch(a, b, tolerance, f"{path}[{index}]")
            if mismatch is not None:
                return mismatch
        return None
    return None if left == right else f"{path}: {left!r} != {right!r}"


def _verify_sha256(path: Path, expected: str) -> None:
    if not path.is_file():
        raise SystemExit(f"T069 missing input: {path}")
    if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
        raise SystemExit(f"T069 input hash changed: {path}")


if __name__ == "__main__":
    raise SystemExit(main())
