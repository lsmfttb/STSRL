#!/usr/bin/env python3
"""Compare cached and accepted T062 outputs on one retained smoke battle."""

from __future__ import annotations

import argparse
from collections.abc import Mapping
from dataclasses import dataclass, field
import hashlib
import json
import math
from pathlib import Path
import re
import subprocess
from time import perf_counter
from typing import Any

from sts_combat_rl.commands.model_guided_oracle_search import (
    build_torch_guidance_scorer_from_checkpoint,
)
from sts_combat_rl.commands.t062_battle_search_v2 import (
    run_t062_comparison_from_cohort_path,
    run_t062_input_preflight_from_paths,
)
from sts_combat_rl.sim.action_space import ActionSpaceConfig
from sts_combat_rl.sim.battle_search_v2 import BattleSearchV2Controller
from sts_combat_rl.sim.battle_search_v2_cost import public_node_cache_key
from sts_combat_rl.sim.lightspeed import LightSpeedAdapter
from sts_combat_rl.sim.policy import DecisionContext
from sts_combat_rl.sim.search_guidance_inference import (
    SearchGuidanceCheckpointProvenance,
    SearchGuidanceInferenceResult,
    SearchGuidanceScorer,
)


SCHEMA_ID = "t067-battle-search-v2-semantic-equivalence-v1"
NATIVE_COMMIT = "3cb9ebecb87c38044b34aa0e013d42b222a04087"
SOURCE_MANIFEST_SHA256 = (
    "2f4bd6710a152b080a2c6e4cfbaf509148ffb27d0139a9250f1a0ee19efd6631"
)
GUIDED_ARMS = ("prior_only", "value_only", "prior_value")


@dataclass
class RecordingScorer:
    base: SearchGuidanceScorer
    name: str = field(init=False)
    checkpoint_provenance: SearchGuidanceCheckpointProvenance = field(init=False)
    call_count: int = 0
    outputs: dict[tuple[str, bytes], dict[str, Any]] = field(default_factory=dict)
    problems: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.name = self.base.name
        self.checkpoint_provenance = self.base.checkpoint_provenance

    @property
    def provenance_config(self) -> Mapping[str, Any]:
        return self.checkpoint_provenance.to_dict()

    def score_decision_context(
        self, context: DecisionContext
    ) -> SearchGuidanceInferenceResult:
        result = self.base.score_decision_context(context)
        self.call_count += 1
        key = public_node_cache_key(context)
        if key is None:
            self.problems.append("retained smoke node was not exactly cacheable")
            return result
        payload = _result_payload(result)
        previous = self.outputs.get(key)
        if previous is not None:
            mismatch = _first_mismatch(previous, payload, tolerance=1e-6)
            if mismatch is not None:
                self.problems.append(
                    f"same public node produced changing output: {mismatch}"
                )
        else:
            self.outputs[key] = payload
        return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cohort", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--t061-retention-manifest", type=Path, required=True)
    parser.add_argument("--preflight-output", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--code-commit", required=True)
    parser.add_argument("--record-range", default="0:1")
    parser.add_argument("--cache-capacity", type=int, default=4096)
    args = parser.parse_args()
    if not re.fullmatch(r"[0-9a-f]{40}", args.code_commit):
        raise SystemExit("T067 semantics requires an exact 40-character code commit")
    _verify_code_commit(Path.cwd(), args.code_commit)
    if args.record_range != "0:1":
        raise SystemExit("T067 semantic smoke is fixed to retained record 0")
    _verify_source_manifest(Path("docs/sts_lightspeed_source_manifest.json"))
    preflight = run_t062_input_preflight_from_paths(
        output_path=args.preflight_output,
        t061_retention_manifest_path=args.t061_retention_manifest,
        t052_cohort_path=args.cohort,
        t043_checkpoint_path=args.checkpoint,
    )
    if not preflight["command_passed"]:
        raise SystemExit("T067 semantic input preflight failed")

    started = perf_counter()
    uncached_arms, uncached_recorders = _arms(
        args.checkpoint, cache_enabled=False, cache_capacity=args.cache_capacity
    )
    cached_arms, cached_recorders = _arms(
        args.checkpoint, cache_enabled=True, cache_capacity=args.cache_capacity
    )
    common = {
        "adapter_factory": lambda: LightSpeedAdapter(seed=1, ascension=20),
        "cohort_path": args.cohort,
        "action_space": ActionSpaceConfig.initial_no_potions(),
        "max_battle_steps": 200,
        "family": "nominal",
        "worker_count": 1,
        "shard_count": 1,
        "record_range": args.record_range,
    }
    uncached_report = run_t062_comparison_from_cohort_path(
        controller_arms=uncached_arms,
        **common,
    )
    cached_report = run_t062_comparison_from_cohort_path(
        controller_arms=cached_arms,
        **common,
    )

    arm_results: dict[str, Any] = {}
    problems: list[str] = []
    for label in GUIDED_ARMS:
        uncached = uncached_recorders[label]
        cached = cached_recorders[label]
        arm_problems = [*uncached.problems, *cached.problems]
        uncached_keys = set(uncached.outputs)
        cached_keys = set(cached.outputs)
        if uncached_keys != cached_keys:
            arm_problems.append("cached and uncached unique public node sets differ")
        for key in sorted(uncached_keys & cached_keys, key=lambda item: item[0]):
            mismatch = _first_mismatch(
                uncached.outputs[key], cached.outputs[key], tolerance=1e-6
            )
            if mismatch is not None:
                arm_problems.append(f"node {key[0]} output mismatch: {mismatch}")
        uncached_actions = _selected_action_identities(uncached_report["arms"][label])
        cached_actions = _selected_action_identities(cached_report["arms"][label])
        if uncached_actions != cached_actions:
            arm_problems.append("selected legal-action identities differ")
        uncached_record = uncached_report["arms"][label]["records"][0]
        cached_record = cached_report["arms"][label]["records"][0]
        for field_name in (
            "source_checkpoint_id",
            "termination_status",
            "terminal_absolute_hp",
            "decision_count",
            "outer_simulator_steps",
        ):
            if uncached_record.get(field_name) != cached_record.get(field_name):
                arm_problems.append(f"battle record field differs: {field_name}")
        arm_results[label] = {
            "uncached_scorer_call_count": uncached.call_count,
            "cached_scorer_call_count": cached.call_count,
            "unique_public_node_count": len(uncached_keys),
            "selected_action_identity_count": len(uncached_actions),
            "policy_value_tolerance": 1e-6,
            "selected_action_identity_exact": uncached_actions == cached_actions,
            "problems": arm_problems,
            "command_passed": not arm_problems,
        }
        problems.extend(f"{label}: {problem}" for problem in arm_problems)

    report = {
        "schema_id": SCHEMA_ID,
        "schema_version": 1,
        "task_id": "T067",
        "code_commit": args.code_commit,
        "native_commit": NATIVE_COMMIT,
        "repair_identity": "exact-public-node-inference-cache-v1",
        "record_range": args.record_range,
        "retained_source_checkpoint_id": uncached_report["arms"]["baseline"]["records"][
            0
        ]["source_checkpoint_id"],
        "stage_classification": "small_semantic_smoke",
        "worker_count": 1,
        "shard_count": 1,
        "single_worker_reason": (
            "one retained battle semantic smoke; not a substantial calibration "
            "or outcome-comparison stage"
        ),
        "arm_results": arm_results,
        "elapsed_wall_clock_seconds": perf_counter() - started,
        "problems": problems,
        "command_passed": not problems,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return 0 if report["command_passed"] else 1


def _verify_code_commit(repo_root: Path, code_commit: str) -> None:
    result = subprocess.run(
        ["git", "-C", str(repo_root), "rev-parse", "HEAD"],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise SystemExit(f"T067 cannot resolve source checkout HEAD: {repo_root}")
    if result.stdout.strip() != code_commit:
        raise SystemExit(
            "T067 source checkout HEAD differs from --code-commit: "
            f"{result.stdout.strip()} != {code_commit}"
        )


def _arms(
    checkpoint: Path, *, cache_enabled: bool, cache_capacity: int
) -> tuple[list[tuple[str, BattleSearchV2Controller]], dict[str, RecordingScorer]]:
    base = build_torch_guidance_scorer_from_checkpoint(checkpoint)
    recorders = {
        label: RecordingScorer(base)
        for label in ("baseline", "prior_only", "value_only", "prior_value")
    }
    arms = [
        (
            label,
            BattleSearchV2Controller(
                simulations=100 if label == "baseline" else 1,
                scorer=recorders[label],
                ablation=label,  # type: ignore[arg-type]
                action_space=ActionSpaceConfig.initial_no_potions(),
                inference_cache_enabled=cache_enabled and label != "baseline",
                inference_cache_capacity=cache_capacity,
            ),
        )
        for label in ("baseline", "prior_only", "value_only", "prior_value")
    ]
    return arms, recorders


def _result_payload(result: SearchGuidanceInferenceResult) -> dict[str, Any]:
    return {
        "action_scores": [
            {
                "legal_action_index": score.legal_action_index,
                "action_identity": dict(score.action_identity),
                "policy_probability": score.policy_probability,
            }
            for score in result.action_scores
        ],
        "value_prediction": (
            None
            if result.value_prediction is None
            else result.value_prediction.to_dict()
        ),
    }


def _selected_action_identities(arm: Mapping[str, Any]) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []

    def visit(value: Any) -> None:
        if isinstance(value, Mapping):
            if value.get("schema_id") == "native-battle-search-root-v1" and isinstance(
                value.get("selected_action_identity"), Mapping
            ):
                selected.append(dict(value["selected_action_identity"]))
            for child in value.values():
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)

    visit(arm.get("records"))
    return selected


def _first_mismatch(
    left: Any, right: Any, *, tolerance: float, path: str = ""
) -> str | None:
    if (
        isinstance(left, (int, float))
        and not isinstance(left, bool)
        and isinstance(right, (int, float))
        and not isinstance(right, bool)
    ):
        if not math.isclose(float(left), float(right), rel_tol=0.0, abs_tol=tolerance):
            return f"{path}: {left!r} != {right!r}"
        return None
    if isinstance(left, Mapping) and isinstance(right, Mapping):
        if set(left) != set(right):
            return f"{path}: mapping keys differ"
        for key in sorted(left):
            mismatch = _first_mismatch(
                left[key],
                right[key],
                tolerance=tolerance,
                path=f"{path}.{key}",
            )
            if mismatch is not None:
                return mismatch
        return None
    if isinstance(left, list) and isinstance(right, list):
        if len(left) != len(right):
            return f"{path}: list lengths differ"
        for index, (left_item, right_item) in enumerate(zip(left, right, strict=True)):
            mismatch = _first_mismatch(
                left_item,
                right_item,
                tolerance=tolerance,
                path=f"{path}[{index}]",
            )
            if mismatch is not None:
                return mismatch
        return None
    if left != right:
        return f"{path}: {left!r} != {right!r}"
    return None


def _verify_source_manifest(path: Path) -> None:
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual != SOURCE_MANIFEST_SHA256:
        raise SystemExit("T067 source manifest hash does not match T062")
    raw = json.loads(path.read_text(encoding="utf-8"))
    if raw.get("integration", {}).get("commit") != NATIVE_COMMIT:
        raise SystemExit("T067 source manifest native commit does not match T062")


if __name__ == "__main__":
    raise SystemExit(main())
