"""Bounded, fail-closed audit of the Search v2 leaf-value target contract.

The audit is intentionally diagnostic.  It reads the accepted T064/T082
artifacts, streams the large JSONL files one record at a time, and never
trains a model or changes a simulator/controller contract.
"""

from __future__ import annotations

import hashlib
import json
import math
import subprocess
from collections import Counter
from collections.abc import Iterator, Mapping, Sequence
from pathlib import Path
from statistics import median
from typing import Any

SCHEMA_ID = "t083-battle-search-v2-leaf-value-target-contract-v1"
EXPECTED_MAIN_COMMIT = "2a0b36b5e7ea700f34ebde8288b0b1cf809ee080"
EXPECTED_MAIN_REF = "refs/heads/main"
EXPECTED_NATIVE_COMMIT = "1555348535d66e3035aac80933a60949d4bd850f"
EXPECTED_NATIVE_REF = "refs/heads/stsrl/main"
EXPECTED_T082_REPORT_SHA = (
    "e1435812abed86d9ddb4c857cba1863edf852f1e956db9fc002e043a4eb2febc"
)
EXPECTED_T064_TEACHER_SHA = (
    "1352eb301509f258ae92509b804125d59d2da17ef5f7f6e5b81131f11e1d0d72"
)
EXPECTED_T064_TRAINER_SHA = (
    "aae847505ece7c4d535d08cffc9e24bc2aaead334234332f41c69f0b2c99bada"
)
EXPECTED_COMPACT = {
    "t064-curriculum-manifest.json": (
        "a111e082d4bc11e03bc5b785a814c422619404245ddda55c2954be09dded46c7",
        "t064-curriculum-manifest-v1",
    ),
    "t064-training-run-report.json": (
        "3e838bed72f5ca565532d39d77b1991e0d32919dcd9b1d6afe4d2c8f8ecdc38c",
        "t064-training-run-report-v1",
    ),
    "t064-stage-summary.json": (
        "5748e79a23152fa51475f8cb7359c81816d6bbdd26ed2a10d7489f1853b6b880",
        "t064-stage-summary-v1",
    ),
    "t064-transfer-decision.json": (
        "f8407acbc17cb13bba53009c91009fea961e7307071d54b0ff82147ff092603f",
        "t064-transfer-decision-v1",
    ),
}
EXPECTED_POOL_COMPONENTS = (
    "assist_0",
    "assist_hp50",
    "assist_hp50_potion_elite_boss",
    "assist_hp75_potion",
)
EXPECTED_ACT_COUNTS = {1: 256, 2: 204}
EXPECTED_COMPONENT_COUNTS = {
    "assist_0": 256,
    "assist_hp50": 12,
    "assist_hp50_potion_elite_boss": 32,
    "assist_hp75_potion": 160,
}
EXPECTED_NATIVE_FILES = (
    "include/sim/search/BattleScumSearcher2.h",
    "src/sim/search/BattleScumSearcher2.cpp",
    "bindings/slaythespire.cpp",
)
GATE_NAMES = (
    "utility_gate",
    "continuation_gate",
    "state_target_gate",
    "leaf_support_gate",
    "information_provenance_gate",
    "artifact_gate",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, Mapping):
        raise TypeError(f"{path} is not a JSON object")
    return dict(value)


def _path(raw: Any) -> Path:
    if not isinstance(raw, str) or not raw:
        raise ValueError("artifact path is missing")
    return Path(raw.replace("D:\\", "/mnt/d/").replace("\\", "/"))


def _finite(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    numeric = float(value)
    return numeric if math.isfinite(numeric) else None


def _stats(values: Sequence[float], *, available_rows: int) -> dict[str, Any]:
    finite = [float(value) for value in values if math.isfinite(float(value))]
    if not finite:
        return {
            "available_rows": available_rows,
            "finite_value_count": 0,
            "min": None,
            "median": None,
            "mean": None,
            "p05": None,
            "p95": None,
            "max": None,
        }
    ordered = sorted(finite)

    def percentile(fraction: float) -> float:
        if len(ordered) == 1:
            return ordered[0]
        position = fraction * (len(ordered) - 1)
        lower = math.floor(position)
        upper = math.ceil(position)
        if lower == upper:
            return ordered[lower]
        return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)

    return {
        "available_rows": available_rows,
        "finite_value_count": len(finite),
        "min": min(finite),
        "median": median(finite),
        "mean": sum(finite) / len(finite),
        "p05": percentile(0.05),
        "p95": percentile(0.95),
        "max": max(finite),
    }


def _record_rows(path: Path) -> Iterator[dict[str, Any]]:
    with path.open(encoding="utf-8") as stream:
        for number, line in enumerate(stream, 1):
            try:
                item = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"malformed JSON at {path}:{number}: {exc}") from exc
            if not isinstance(item, Mapping):
                raise TypeError(f"non-object JSON at {path}:{number}")
            if item.get("type") == "metadata":
                continue
            if item.get("type") != "record" or not isinstance(
                item.get("record"), Mapping
            ):
                raise ValueError(f"invalid envelope row at {path}:{number}")
            yield dict(item["record"])


def _metadata_and_rows(path: Path) -> tuple[dict[str, Any], Iterator[dict[str, Any]]]:
    def iterator() -> Iterator[dict[str, Any]]:
        metadata: dict[str, Any] | None = None
        metadata_count = 0
        with path.open(encoding="utf-8") as stream:
            for number, line in enumerate(stream, 1):
                try:
                    item = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise ValueError(
                        f"malformed JSON at {path}:{number}: {exc}"
                    ) from exc
                if not isinstance(item, Mapping):
                    raise TypeError(f"non-object JSON at {path}:{number}")
                if item.get("type") == "metadata":
                    metadata_count += 1
                    if not isinstance(item.get("metadata"), Mapping):
                        raise TypeError(f"metadata is not an object at {path}:{number}")
                    metadata = dict(item["metadata"])
                    continue
                if item.get("type") != "record" or not isinstance(
                    item.get("record"), Mapping
                ):
                    raise ValueError(f"invalid envelope row at {path}:{number}")
                if metadata_count != 1 or metadata is None:
                    raise ValueError(f"record precedes metadata at {path}:{number}")
                yield dict(item["record"])
        if metadata_count != 1 or metadata is None:
            raise ValueError(f"missing or duplicate metadata in {path}")

    # Metadata is needed before records, but the iterator cannot expose it until
    # consumed.  The files are immutable retained artifacts, so parse the first
    # line only here and let the streaming iterator validate it again.
    with path.open(encoding="utf-8") as stream:
        first = json.loads(next(stream))
    if not isinstance(first, Mapping) or first.get("type") != "metadata":
        raise ValueError(f"missing metadata envelope in {path}")
    raw_metadata = first.get("metadata")
    if not isinstance(raw_metadata, Mapping):
        raise TypeError(f"metadata is not an object in {path}")
    return dict(raw_metadata), iterator()


def _artifact_check(
    path: Path, expected_sha: str, expected_schema: str | None
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "path": str(path),
        "expected_sha256": expected_sha,
        "sha256": None,
        "bytes": None,
        "schema_id": None,
        "expected_schema_id": expected_schema,
        "valid": False,
    }
    if not path.exists():
        result["reason"] = "missing artifact"
        return result
    result["bytes"] = path.stat().st_size
    try:
        result["sha256"] = sha256(path)
        if expected_schema is None:
            result["valid"] = result["sha256"] == expected_sha
        else:
            parsed = _json(path)
            result["schema_id"] = parsed.get("schema_id")
            result["valid"] = (
                result["sha256"] == expected_sha
                and result["schema_id"] == expected_schema
            )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        result["reason"] = str(exc)
    return result


def _git_show(
    native_root: Path, commit: str, relative: str
) -> tuple[str | None, str | None]:
    try:
        process = subprocess.run(
            ["git", "-C", str(native_root), "show", f"{commit}:{relative}"],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
    except (OSError, subprocess.CalledProcessError):
        return None, None
    source = process.stdout
    return source, hashlib.sha256(source.encode("utf-8")).hexdigest()


def _git_ref_commit(repository: Path, ref: str) -> str | None:
    try:
        process = subprocess.run(
            [
                "git",
                "-C",
                str(repository),
                "rev-parse",
                "--verify",
                f"{ref}^{{commit}}",
            ],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return process.stdout.strip()


def native_evidence(native_root: Path) -> dict[str, Any]:
    resolved_ref = _git_ref_commit(native_root, EXPECTED_NATIVE_REF)
    files: dict[str, Any] = {}
    for relative in EXPECTED_NATIVE_FILES:
        source, source_sha = _git_show(native_root, EXPECTED_NATIVE_REF, relative)
        if source is None:
            files[relative] = {"available": False, "sha256": None}
            continue
        lines = source.splitlines()
        matches = {
            "evaluate_end_state": [
                index + 1
                for index, line in enumerate(lines)
                if "evaluateEndState" in line
            ],
            "update_from_evaluation": [
                index + 1
                for index, line in enumerate(lines)
                if "updateFromEvaluation" in line
            ],
            "learned_leaf_value": [
                index + 1
                for index, line in enumerate(lines)
                if "learnedLeafValue" in line or "leafValueCallback" in line
            ],
        }
        files[relative] = {
            "available": True,
            "sha256": source_sha,
            "line_evidence": matches,
        }
    cpp, _ = _git_show(
        native_root, EXPECTED_NATIVE_REF, "src/sim/search/BattleScumSearcher2.cpp"
    )
    header, _ = _git_show(
        native_root, EXPECTED_NATIVE_REF, "include/sim/search/BattleScumSearcher2.h"
    )
    binding, _ = _git_show(
        native_root, EXPECTED_NATIVE_REF, "bindings/slaythespire.cpp"
    )
    all_source = "\n".join(
        value for value in (cpp, header, binding) if value is not None
    )
    formula_tokens = (
        "bc.outcome == Outcome::PLAYER_VICTORY",
        "100 * (35 + bc.player.curHp + potionScore - (bc.turn * 0.01))",
        "getNonMinionMonsterCurHpRatio(bc)",
        "bc.energyWasted * -0.2",
        "bc.cardsDrawn * 0.03",
        "bc.turn * .2",
        "updateFromEvaluation(searchStack, actionStack, evaluation)",
        "node.evaluationSum += evaluation",
    )
    generator_tokens = (
        "void search::BattleScumSearcher2::playoutRandom",
        "while (!isTerminalState(state))",
        "enumerateActionsForNode(tempNode, state, false)",
        "std::uniform_int_distribution<int>(0, static_cast<int>(tempNode.edges.size())-1)",
        "const int selectedIdx = dist(randGen)",
        "action.execute(state)",
        "randGen(bc.seed+bc.floorNum)",
        "edgeTaken.action.execute(curState)",
        "searchStack.push_back(&edgeTaken.node)",
        "learnedLeafValueFnc(curState, legalActions)",
        "playoutRandom(curState, actionStack)",
    )
    materialization_tokens = (
        "const BattleContext &state",
        "battleSearchNodeSnapshot(state)",
        "exactStateDigest",
        'telemetry["expanded_states"] = rows',
    )
    generator_proven = all(token in all_source for token in generator_tokens)
    materialization_evidence_available = all(
        token in all_source for token in materialization_tokens
    )
    return {
        "repository": "https://github.com/lsmfttb/sts_lightspeed.git",
        "ref": EXPECTED_NATIVE_REF,
        "commit": EXPECTED_NATIVE_COMMIT,
        "resolved_ref": EXPECTED_NATIVE_REF,
        "resolved_commit": resolved_ref,
        "identity_valid": resolved_ref == EXPECTED_NATIVE_COMMIT,
        "files": files,
        "formula_evidence": {
            "all_required_tokens_present": all(
                token in all_source for token in formula_tokens
            ),
            "required_tokens": list(formula_tokens),
            "victory_formula": "100 * (35 + current_hp + 4*potion_count - 0.01*turn)",
            "non_victory_formula": (
                "(1 - remaining_non_minion_monster_hp_ratio) * 10 - monsters_alive "
                "- 0.2 * energy_wasted (except THREE_SHAPES/FOUR_SHAPES) "
                "+ 0.03 * cards_drawn + 2 * potion_count + 0.2 * turn"
            ),
            "inputs": [
                "outcome",
                "player.curHp",
                "potionCount",
                "turn",
                "non-minion monster current/max HP",
                "monstersAlive",
                "energyWasted",
                "encounter",
                "cardsDrawn",
            ],
        },
        "generator_evidence": {
            "name": "BattleScumSearcher2::playoutRandom",
            "precise_generator_proven": generator_proven,
            "required_tokens": list(generator_tokens),
            "post_first_action_boundary": {
                "proven": all(
                    token in all_source
                    for token in (
                        "edgeTaken.action.execute(curState)",
                        "searchStack.push_back(&edgeTaken.node)",
                        "learnedLeafValueFnc(curState, legalActions)",
                    )
                ),
                "semantics": "execute the selected first action, push its child, then request the learned value on the post-action state",
            },
            "eligible_action_enumeration": {
                "proven": "enumerateActionsForNode(tempNode, state, false)"
                in all_source,
                "semantics": "playoutRandom enumerates actions without priors and samples the eligible action vector",
            },
            "uniform_random_action": {
                "proven": all(
                    token in all_source
                    for token in (
                        "std::uniform_int_distribution<int>(0, static_cast<int>(tempNode.edges.size())-1)",
                        "const int selectedIdx = dist(randGen)",
                    )
                ),
                "semantics": "uniform_int_distribution over the enumerated eligible actions",
            },
            "terminal_loop": {
                "proven": all(
                    token in all_source
                    for token in (
                        "while (!isTerminalState(state))",
                        "action.execute(state)",
                    )
                ),
                "semantics": "continue random action execution until isTerminalState(state)",
            },
            "random_rng_producer": {
                "proven": "randGen(bc.seed+bc.floorNum)" in all_source,
                "semantics": "BattleScumSearcher2::randGen is a std::default_random_engine seeded from battle seed plus floor",
            },
            "accepted_surfaces_can_materialize_hidden_internal_state": (
                generator_proven and materialization_evidence_available
            ),
            "materialization_evidence_available": materialization_evidence_available,
            "materialization_boundary": "the accepted native search surface has the hidden BattleContext at the callback boundary; the current Python callback receives only battleSearchNodeSnapshot(state), and T079 telemetry exports exactStateDigest/expanded_states metadata rather than the canonical payload",
            "current_python_projection_can_materialize_hidden_internal_state": False,
            "python_callback_receives_hidden_internal_state": False,
            "materialization_reason": "a successor native-side collector can copy the exact post-action BattleContext before the Python projection, restore that copy for each replicate, and run the pinned continuation; exactStateDigest is retained as provenance but is not used to reconstruct state",
            "successor_data_generation_surface": {
                "specified": generator_proven and materialization_evidence_available,
                "executed_by_t083": False,
                "kind": "native-side read-only collector/instrumentation at the existing callback boundary",
                "capture": "immediately after edgeTaken.action.execute(curState) and searchStack.push_back(&edgeTaken.node), copy the exact post-action BattleContext before invoking the Python callback or any continuation",
                "search_behavior_change": "none: collector observes/copies state and runs an offline target-generation path; it does not change Search topology, allocation, backup, root selection, or the production Python callback contract",
                "repetitions_per_leaf": 100,
                "per_replica_action_budget": 512,
                "budget_failure": "mark the replica/leaf unavailable if terminal state is not reached within 512 native action transitions; never truncate and score a non-terminal state",
                "seed_policy": "for each leaf and replicate index, derive a uint32 seed from the first 8 hex digits of SHA256(native_commit|source_complete_identity_sha256|leaf_ordinal|replicate_index), record it, and initialize an independent native continuation RNG",
                "continuation": "restore the copied full BattleContext for every replicate, run pinned playoutRandom with enumerateActionsForNode(..., false) and uniform eligible-action selection until terminal, then call exact evaluateEndState on the terminal state",
                "target": "mean of the 100 finite terminal evaluateEndState utilities; retain every replicate utility and seed for auditability",
                "emission": "emit the public battleSearchNodeSnapshot and legal-action input for the model, plus full-state provenance (canonical hidden-state payload/digest, all RNG state, source identity, leaf identity, replicate seeds, repetition count, action budget, native identity, and terminal utility values)",
                "python_boundary": "Python callback remains public-projection-only; it is not given hidden state and does not generate the target",
                "provenance_boundary": "the native collector must emit the full-state provenance itself; exactStateDigest alone is insufficient",
            },
            "target_definition": "V_leaf=E[evaluateEndState | post-action state, pinned playoutRandom]",
        },
        "backup_path": {
            "terminal_playout": "updateFromPlayout -> evaluateEndState -> updateFromEvaluation",
            "learned_leaf": "first action from newly expanded node -> learnedLeafValueFnc -> updateFromEvaluation",
            "accumulator": "Node.evaluationSum and Node.simulationCount",
            "learned_leaf_transformation": "none: Python float is cast to double and added directly",
            "root_mean_value_units": "evaluationSum / simulationCount; same accumulator, but finite-search action conditional",
        },
    }


def code_evidence(repo_root: Path, resolved_main: str | None = None) -> dict[str, Any]:
    files = {
        "src/sts_combat_rl/sim/battle_search_v2.py": (
            "value_callback",
            "prediction.battle_survival_probability",
            "native_result = float(value)",
            "leaf_value_callback=value_callback if self.uses_leaf_value else None",
        ),
        "src/sts_combat_rl/sim/torch_policy_value.py": (
            'OUTCOME_TARGET_KIND = "terminal_battle_survival_probability"',
            "F.binary_cross_entropy_with_logits",
            "torch.sigmoid(outcome_logit)",
        ),
        "src/sts_combat_rl/sim/oracle_teacher_search_guidance.py": (
            "def _battle_survived",
            "oracle_teacher_row.soft_visit_target",
        ),
    }
    result: dict[str, Any] = {}
    source_matches_main = resolved_main == EXPECTED_MAIN_COMMIT
    for relative, tokens in files.items():
        path = repo_root / relative
        try:
            source = path.read_text(encoding="utf-8")
        except OSError:
            result[relative] = {
                "available": False,
                "sha256": None,
                "main_sha256": None,
                "source_matches_main": False,
                "tokens": {},
            }
            source_matches_main = False
            continue
        main_source, main_sha = _git_show(repo_root, EXPECTED_MAIN_REF, relative)
        matches = (
            main_source is not None
            and hashlib.sha256(source.encode("utf-8")).hexdigest() == main_sha
        )
        source_matches_main = source_matches_main and matches
        result[relative] = {
            "available": True,
            "sha256": hashlib.sha256(source.encode("utf-8")).hexdigest(),
            "main_sha256": main_sha,
            "source_matches_main": matches,
            "tokens": {token: token in source for token in tokens},
        }
    result["main_ref"] = EXPECTED_MAIN_REF
    result["main_resolved_commit"] = resolved_main
    result["source_matches_main"] = source_matches_main
    result["contract"] = {
        "value_head_target_kind": "terminal_battle_survival_probability",
        "producer": "outcome_head logits trained with binary_cross_entropy_with_logits",
        "inference": "sigmoid(outcome_logit)",
        "theoretical_range": "[0,1]",
        "consumer_field": "SearchGuidanceValuePrediction.battle_survival_probability",
        "native_callback_boundary": "Python scorer result -> float -> pybind double -> learnedLeafValueFnc -> updateFromEvaluation",
        "native_utility_units": "not [0,1]; evaluateEndState native utility",
        "current_leaf_utility_alignment": False,
    }
    return result


def _selected_sources(
    manifest: Mapping[str, Any], expected_rows: int
) -> list[dict[str, Any]]:
    selected = manifest.get("selected_sources")
    if not isinstance(selected, list) or len(selected) != expected_rows:
        raise ValueError(f"selected_sources must contain exactly {expected_rows} rows")
    result = []
    for index, item in enumerate(selected):
        if not isinstance(item, Mapping):
            raise TypeError(f"selected source {index} is not an object")
        required = (
            "component",
            "source_record_index",
            "complete_identity",
            "complete_identity_sha256",
        )
        if any(key not in item for key in required):
            raise ValueError(f"selected source {index} is missing identity fields")
        if not isinstance(item["component"], str) or not isinstance(
            item["source_record_index"], int
        ):
            raise TypeError(f"selected source {index} has malformed component/index")
        result.append(dict(item))
    return result


def _validate_t064_artifacts(
    t064_root: Path, expected_rows: int
) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]], list[str]]:
    checks: list[dict[str, Any]] = []
    problems: list[str] = []
    for name, (expected_sha, schema) in EXPECTED_COMPACT.items():
        check = _artifact_check(t064_root / name, expected_sha, schema)
        checks.append(check)
        if not check["valid"]:
            problems.append(f"invalid compact artifact: {name}")
    manifest = _json(t064_root / "t064-curriculum-manifest.json")
    selected = _selected_sources(manifest, expected_rows)
    transfer = _json(t064_root / "t064-transfer-decision.json")
    if not all(
        transfer.get(key) is True
        for key in ("experiment_complete", "source_adequacy", "source_integrity_valid")
    ):
        problems.append(
            "T064 transfer decision is not complete/adequate/integrity-valid"
        )
    if transfer.get("terminal_case") != "Case B":
        problems.append("T064 transfer decision is not Case B")
    if Counter(item.get("act") for item in selected) != Counter(EXPECTED_ACT_COUNTS):
        problems.append(
            "T064 selected Act distribution does not match accepted lineage"
        )
    if Counter(item.get("component") for item in selected) != Counter(
        EXPECTED_COMPONENT_COUNTS
    ):
        problems.append(
            "T064 selected component distribution does not match accepted lineage"
        )
    artifact_specs = manifest.get("input_artifacts")
    if not isinstance(artifact_specs, Mapping):
        problems.append("T064 input_artifacts is missing")
        artifact_specs = {}
    pool_checks: list[dict[str, Any]] = []
    for component in EXPECTED_POOL_COMPONENTS:
        spec = artifact_specs.get(component)
        if not isinstance(spec, Mapping):
            problems.append(f"missing T042 pool spec: {component}")
            continue
        path = _path(spec.get("path"))
        check = {
            "path": str(path),
            "expected_sha256": spec.get("sha256"),
            "sha256": spec.get("sha256"),
            "bytes": path.stat().st_size if path.exists() else None,
            "schema_id": spec.get("schema_id"),
            "expected_schema_id": spec.get("schema_id"),
            "hash_verified": False,
            "verification_mode": "accepted_T064_manifest_identity_plus_size",
            "valid": bool(
                path.exists()
                and isinstance(spec.get("sha256"), str)
                and len(spec["sha256"]) == 64
                and path.stat().st_size == spec.get("bytes")
                and spec.get("schema_id") == "assisted-run-source-pool-v1"
            ),
        }
        check.update(
            {
                "component": component,
                "record_count": spec.get("record_count"),
                "expected_bytes": spec.get("bytes"),
            }
        )
        check["valid"] = bool(check["valid"] and check["bytes"] == spec.get("bytes"))
        pool_checks.append(check)
        if not check["valid"]:
            problems.append(f"invalid T042 pool identity: {component}")
    t042 = artifact_specs.get("t042_scale_manifest")
    if not isinstance(t042, Mapping):
        problems.append("missing T042 scale manifest spec")
    else:
        check = _artifact_check(_path(t042.get("path")), str(t042.get("sha256")), None)
        check["artifact_kind"] = "t042_scale_manifest"
        checks.append(check)
        if not check["valid"]:
            problems.append("invalid T042 scale manifest identity")
    return (
        {"artifact_checks": checks, "pool_checks": pool_checks},
        manifest,
        selected,
        problems,
    )


def _teacher_inventory(
    path: Path, selected: Sequence[Mapping[str, Any]], expected_rows: int
) -> tuple[dict[str, Any], list[str]]:
    metadata, rows = _metadata_and_rows(path)
    problems: list[str] = []
    expected = {
        "artifact_schema_id": "oracle-search-teacher-v1",
        "record_count": expected_rows,
    }
    for key, value in expected.items():
        if metadata.get(key) != value:
            problems.append(f"teacher metadata {key} mismatch")
    controller = metadata.get("controller_provenance")
    config = controller.get("config", {}) if isinstance(controller, Mapping) else {}
    for key, value in (
        ("information_regime", "full_simulator_state_oracle_like"),
        ("search_budget", {"simulations": 100}),
        ("root_selection_rule", "highest_mean"),
        ("include_potions", False),
    ):
        actual = config.get(key)
        if key == "search_budget":
            actual = actual if isinstance(actual, Mapping) else {}
            actual = {"simulations": actual.get("simulations")}
        if actual != value:
            problems.append(f"teacher controller {key} mismatch")
    values: dict[str, list[float]] = {
        name: []
        for name in (
            "selected_teacher_action_mean_value",
            "root_max_eligible_mean_value",
            "native_search_report_best_action_value",
            "soft_visit_weighted_root_mean",
        )
    }
    availability = Counter()
    equality = Counter()
    row_count = 0
    for row_count, row in enumerate(rows, 1):
        row_index = row.get("row_index")
        if row_index != row_count - 1:
            problems.append(f"teacher row index mismatch at stream row {row_count}")
        if row_count > expected_rows:
            problems.append("teacher has more than expected rows")
            break
        selected_item = selected[row_count - 1]
        identity = selected_item.get("complete_identity", {})
        for key in (
            "source_checkpoint_id",
            "source_run_id",
            "source_seed",
            "source_battle_index",
        ):
            if row.get(key) != identity.get(key):
                problems.append(
                    f"teacher/source identity mismatch row {row_count - 1}: {key}"
                )
        if row.get("source_pool_record_index") != selected_item.get(
            "source_record_index"
        ):
            problems.append(f"teacher/source pool index mismatch row {row_count - 1}")
        teacher_action = row.get("teacher_action")
        root = row.get("root_statistics")
        report = row.get("native_search_report")
        if (
            not isinstance(teacher_action, Mapping)
            or not isinstance(root, list)
            or not isinstance(report, Mapping)
        ):
            problems.append(f"malformed teacher candidate fields row {row_count - 1}")
            continue
        selected_value = _finite(teacher_action.get("mean_value"))
        root_values = [
            _finite(item.get("mean_value"))
            for item in root
            if isinstance(item, Mapping) and item.get("eligible") is True
        ]
        root_values = [value for value in root_values if value is not None]
        root_max = max(root_values) if root_values else None
        best = _finite(report.get("best_action_value"))
        weighted = 0.0
        weight = 0.0
        weighted_ok = True
        for item in root:
            if not isinstance(item, Mapping):
                weighted_ok = False
                continue
            probability = _finite(item.get("visit_probability"))
            value = _finite(item.get("mean_value"))
            if probability is None or value is None:
                if probability not in (None, 0.0):
                    weighted_ok = False
                continue
            weighted += probability * value
            weight += probability
        soft = (
            weighted
            if weighted_ok and weight > 0.0 and abs(weight - 1.0) <= 1e-8
            else None
        )
        candidate_values = (selected_value, root_max, best, soft)
        for name, value in zip(values, candidate_values, strict=True):
            if value is not None:
                values[name].append(value)
                availability[name] += 1
        if (
            selected_value is not None
            and root_max is not None
            and math.isclose(selected_value, root_max, rel_tol=0.0, abs_tol=1e-12)
        ):
            equality["selected_teacher_equals_root_max"] += 1
        if (
            selected_value is not None
            and _finite(teacher_action.get("score")) is not None
            and math.isclose(
                selected_value,
                float(teacher_action["score"]),
                rel_tol=0.0,
                abs_tol=1e-12,
            )
        ):
            equality["teacher_mean_equals_score"] += 1
        if root_values and selected_value is not None:
            equality["selected_teacher_is_root_max"] += int(
                math.isclose(selected_value, root_max, rel_tol=0.0, abs_tol=1e-12)
            )
    if row_count != expected_rows:
        problems.append(f"teacher record count {row_count} != {expected_rows}")
    candidates = {
        name: {
            "field": {
                "selected_teacher_action_mean_value": "teacher_action.mean_value",
                "root_max_eligible_mean_value": "max(root_statistics[*].mean_value where eligible=true)",
                "native_search_report_best_action_value": "native_search_report.best_action_value",
                "soft_visit_weighted_root_mean": "sum(root_statistics[*].visit_probability * mean_value), requiring exact finite probabilities summing to 1",
            }[name],
            "schema": "oracle-search-teacher-v1 / native-battle-search-root-v1",
            "units": "native evaluateEndState utility units"
            if name != "soft_visit_weighted_root_mean"
            else "native evaluateEndState utility units, finite-budget root distribution weighted",
            "value_kind": "action-value conditional"
            if name
            in {
                "selected_teacher_action_mean_value",
                "root_max_eligible_mean_value",
                "native_search_report_best_action_value",
            }
            else "root action-mixture value estimate",
            "search_budget": 100,
            "root_selection": "highest_mean"
            if name
            in {"selected_teacher_action_mean_value", "root_max_eligible_mean_value"}
            else "not root-selected"
            if name == "soft_visit_weighted_root_mean"
            else "best terminal path tracked by native search",
            "continuation_semantics": "native random terminal playout under full-simulator-state Oracle-like search; no continuation-policy proof for the intended learned leaf evaluator",
            "statistics": _stats(values[name], available_rows=availability[name]),
        }
        for name in values
    }
    return {
        "metadata": {
            "artifact_schema_id": metadata.get("artifact_schema_id"),
            "record_count": metadata.get("record_count"),
            "controller": config,
        },
        "row_count": row_count,
        "candidates": candidates,
        "equality_consistency": dict(equality),
        "problems": problems,
    }, problems


def _trainer_check(
    path: Path, expected_rows: int, selected: Sequence[Mapping[str, Any]]
) -> tuple[dict[str, Any], list[str]]:
    metadata, rows = _metadata_and_rows(path)
    problems: list[str] = []
    required = {
        "format_version": 6,
        "record_count": expected_rows,
        "policy_target_schema_id": "trainer-policy-target-v1",
        "policy_target_schema_version": 1,
        "structured_battle_outcome_schema_id": "structured-battle-outcome-v1",
        "structured_battle_outcome_schema_version": 1,
    }
    for key, value in required.items():
        if metadata.get(key) != value:
            problems.append(f"trainer metadata {key} mismatch")
    count = 0
    outcomes = Counter()
    for count, row in enumerate(rows, 1):
        if row.get("example_index") != count - 1:
            problems.append(f"trainer example index mismatch at row {count - 1}")
        if count > expected_rows:
            break
        source = row.get("source_metadata")
        if not isinstance(source, Mapping):
            problems.append(f"trainer source_metadata missing row {count - 1}")
            continue
        identity = selected[count - 1].get("complete_identity", {})
        if source.get("t064_complete_identity_sha256") != identity.get(
            "complete_identity_sha256"
        ):
            problems.append(f"trainer complete identity mismatch row {count - 1}")
        if (
            row.get("policy_target_kind") != "oracle_soft_visit_distribution"
            or row.get("policy_target_source") != "oracle_teacher_row.soft_visit_target"
        ):
            problems.append(f"trainer policy target lineage mismatch row {count - 1}")
        outcome = row.get("structured_battle_outcome", {})
        survived = (
            outcome.get("battle_survived", {}) if isinstance(outcome, Mapping) else {}
        )
        if (
            isinstance(survived, Mapping)
            and survived.get("status") == "available"
            and isinstance(survived.get("value"), bool)
        ):
            outcomes["survived" if survived["value"] else "lost"] += 1
        else:
            outcomes["unavailable"] += 1
    if count != expected_rows:
        problems.append(f"trainer record count {count} != {expected_rows}")
    return {
        "metadata": {key: metadata.get(key) for key in required},
        "row_count": count,
        "outcome_counts": dict(outcomes),
        "problems": problems,
    }, problems


def _source_terminal_support(
    t064_manifest: Mapping[str, Any], selected: Sequence[Mapping[str, Any]]
) -> tuple[dict[str, Any], list[str]]:
    # The source pools are multi-GB.  The accepted T064 manifest supplies exact
    # pool identities and selected complete identities; this audit does not
    # reopen raw pool records.  The retained source schema separates terminal
    # resource outcomes from the restored start snapshot and lacks the native
    # terminal fields required by evaluateEndState.
    specs = t064_manifest.get("input_artifacts", {})
    if not isinstance(specs, Mapping):
        return {"available": False, "reason": "T064 input_artifacts missing"}, [
            "source input_artifacts missing"
        ]
    return {
        "available": False,
        "reason": "selected source rows retain terminal resources/outcome but not terminal turn, energy_wasted, cards_drawn, or terminal monster HP; start snapshot is not terminal",
        "bounded_scan": False,
        "bounded_scan_reason": "multi-GB T042 pools are accepted by their frozen T064 manifest identities; raw source reopening is outside this 460-row contract audit",
        "selected_rows_found": "not_reopened",
        "selected_rows_expected": len(selected),
        "source_pool_components": sorted(specs),
        "terminal_resource_fields_observed": [
            "battle_result",
            "battle_survived",
            "terminal_absolute_current_hp",
            "terminal_max_hp",
        ],
        "source_outcome_counts": "not_reopened",
        "reconstructed_exact_native_utility_rows": 0,
        "statistics": _stats([], available_rows=0),
    }, []


def _candidate_table(
    source_support: Mapping[str, Any], artifact_valid: bool
) -> list[dict[str, Any]]:
    base = {
        "utility_gate": False,
        "continuation_gate": False,
        "state_target_gate": False,
        "leaf_support_gate": False,
        "information_provenance_gate": True,
        "artifact_gate": artifact_valid,
    }
    definitions = [
        (
            "current_battle_survival_probability",
            "checkpoint sigmoid outcome head; [0,1]",
            "state-value probability",
            "not native utility; no conversion",
        ),
        (
            "selected_teacher_action_mean_value",
            "finite-budget root edge mean",
            "action-value conditional on selected root action",
            "native random rollout/Oracle-like, 100 simulations",
        ),
        (
            "root_max_eligible_mean_value",
            "maximum eligible root edge mean",
            "action-value with max aggregation",
            "native random rollout/Oracle-like, 100 simulations",
        ),
        (
            "native_search_report_best_action_value",
            "best terminal path value tracked by native search",
            "path/action-conditioned terminal utility",
            "best path, not state value",
        ),
        (
            "soft_visit_weighted_root_mean",
            "root visit-probability weighted mean",
            "root action-mixture estimate",
            "100-visit root distribution; root-only",
        ),
        (
            "source_realized_terminal_utility",
            "evaluateEndState reconstructed from terminal source state",
            "terminal outcome value",
            "source behavior continuation, not retained exactly",
        ),
    ]
    table = []
    for name, definition, value_kind, semantics in definitions:
        gates = dict(base)
        if name in {
            "selected_teacher_action_mean_value",
            "root_max_eligible_mean_value",
            "native_search_report_best_action_value",
            "soft_visit_weighted_root_mean",
        }:
            gates["utility_gate"] = True
        if name == "source_realized_terminal_utility":
            gates["utility_gate"] = bool(
                source_support.get("reconstructed_exact_native_utility_rows", 0)
            )
        if name == "source_realized_terminal_utility" or name in {
            "root_max_eligible_mean_value",
            "soft_visit_weighted_root_mean",
        }:
            gates["state_target_gate"] = True
        table.append(
            {
                "candidate": name,
                "definition": definition,
                "value_kind": value_kind,
                "proven_continuation_semantics": semantics,
                "gates": gates,
                "definition_reusable": all(gates.values()),
                "retained_labels_sufficient": False,
                "rejection_or_limit": "action-specific/root-only finite-search quantity lacks internal-leaf support and a continuation contract"
                if name
                in {
                    "selected_teacher_action_mean_value",
                    "root_max_eligible_mean_value",
                    "native_search_report_best_action_value",
                    "soft_visit_weighted_root_mean",
                }
                else "direct [0,1] probability is not native utility"
                if name == "current_battle_survival_probability"
                else str(source_support.get("reason")),
            }
        )
    return table


def _classification_evidence(
    candidate_table: Sequence[Mapping[str, Any]],
    *,
    integrity_valid: bool,
    execution_valid: bool,
    generator_evidence: Mapping[str, Any],
) -> dict[str, Any]:
    retained_candidate_all_gates = any(
        bool(candidate.get("retained_labels_sufficient"))
        and all(bool(value) for value in (candidate.get("gates") or {}).values())
        for candidate in candidate_table
    )
    precise_generator_proven = bool(generator_evidence.get("precise_generator_proven"))
    can_materialize_hidden_state = bool(
        generator_evidence.get(
            "accepted_surfaces_can_materialize_hidden_internal_state"
        )
    )
    successor_surface_specified = bool(
        (generator_evidence.get("successor_data_generation_surface") or {}).get(
            "specified"
        )
    )
    return {
        "integrity_valid": integrity_valid,
        "execution_valid": execution_valid,
        "retained_candidate_all_gates_and_labels_sufficient": retained_candidate_all_gates,
        "accepted_native_precise_generator_proven": precise_generator_proven,
        "accepted_surfaces_can_materialize_hidden_internal_state": can_materialize_hidden_state,
        "successor_data_generation_surface_specified": successor_surface_specified,
        "new_generator_usable": precise_generator_proven
        and successor_surface_specified,
    }


def classify_contract(
    candidate_table: Sequence[Mapping[str, Any]],
    *,
    integrity_valid: bool,
    execution_valid: bool,
    generator_evidence: Mapping[str, Any],
) -> str:
    """Select exactly one classification from explicit audit evidence."""

    evidence = _classification_evidence(
        candidate_table,
        integrity_valid=integrity_valid,
        execution_valid=execution_valid,
        generator_evidence=generator_evidence,
    )
    if not evidence["integrity_valid"] or not evidence["execution_valid"]:
        return "INCOMPLETE"
    if evidence["retained_candidate_all_gates_and_labels_sufficient"]:
        return "EXISTING_T064_LEAF_VALUE_LABELS_REUSABLE"
    if evidence["new_generator_usable"]:
        return "NEW_LEAF_CONTINUATION_UTILITY_TARGET_REQUIRED"
    return "LEAF_VALUE_TARGET_CONTRACT_UNRESOLVED"


def _incomplete_report(
    problem: str, *, repo_root: Path, native_root: Path, expected_rows: int
) -> dict[str, Any]:
    return {
        "schema_id": SCHEMA_ID,
        "schema_version": 1,
        "task_id": "T083",
        "classification": "INCOMPLETE",
        "recommendation": None,
        "execution": {
            "mode": "offline_streaming",
            "worker_count": 1,
            "worker_reason": "non-simulator artifact audit; bounded single stream",
        },
        "identity": {
            "stsrl_main_commit": EXPECTED_MAIN_COMMIT,
            "native_commit": EXPECTED_NATIVE_COMMIT,
            "expected_rows": expected_rows,
        },
        "problems": [problem],
        "code_evidence": code_evidence(
            repo_root, _git_ref_commit(repo_root, EXPECTED_MAIN_REF)
        ),
        "native_evidence": native_evidence(native_root),
    }


def audit_t083(
    t064_root: Path,
    t082_report: Path,
    output: Path,
    *,
    repo_root: Path | None = None,
    native_root: Path = Path("/home/lsmft/stsrl-spikes/sts_lightspeed"),
    expected_rows: int = 460,
    code_commit: str = EXPECTED_MAIN_COMMIT,
) -> dict[str, Any]:
    repo_root = repo_root or Path(__file__).resolve().parents[2]
    try:
        if code_commit != EXPECTED_MAIN_COMMIT:
            raise ValueError(f"unexpected STSRL main identity: {code_commit}")
        resolved_main = _git_ref_commit(repo_root, EXPECTED_MAIN_REF)
        if resolved_main != EXPECTED_MAIN_COMMIT:
            raise ValueError(
                f"{EXPECTED_MAIN_REF} resolved to {resolved_main!r}, expected {EXPECTED_MAIN_COMMIT}"
            )
        t082_check = _artifact_check(t082_report, EXPECTED_T082_REPORT_SHA, None)
        t082_document = _json(t082_report)
        t082_check["schema_id"] = t082_document.get("schema_version")
        t082_check["expected_schema_id"] = "t082-value-target-semantic-closure-v1"
        t082_check["valid"] = bool(
            t082_check["valid"]
            and t082_document.get("schema_version")
            == "t082-value-target-semantic-closure-v1"
        )
        if (
            t082_document.get("classification")
            != "VALUE_TARGET_SEMANTIC_MISMATCH_CONFIRMED"
        ):
            raise ValueError("accepted T082 classification is not the frozen mismatch")
        artifact_result, manifest, selected, artifact_problems = (
            _validate_t064_artifacts(t064_root, expected_rows)
        )
        teacher_path = t064_root / "teacher/merged.jsonl"
        trainer_path = t064_root / "trainer/trainer-input.jsonl"
        teacher_check = _artifact_check(teacher_path, EXPECTED_T064_TEACHER_SHA, None)
        trainer_check = _artifact_check(trainer_path, EXPECTED_T064_TRAINER_SHA, None)
        artifact_result["artifact_checks"].extend(
            [teacher_check, trainer_check, t082_check]
        )
        if (
            not teacher_check["valid"]
            or not trainer_check["valid"]
            or not t082_check["valid"]
        ):
            artifact_problems.append(
                "T082/teacher/trainer exact hash or schema check failed"
            )
        teacher, teacher_problems = _teacher_inventory(
            teacher_path, selected, expected_rows
        )
        _trainer, trainer_problems = _trainer_check(
            trainer_path, expected_rows, selected
        )
        source_support, source_problems = _source_terminal_support(manifest, selected)
        all_problems = (
            artifact_problems + teacher_problems + trainer_problems + source_problems
        )
        artifact_valid = not all_problems and all(
            item.get("valid") for item in artifact_result["artifact_checks"]
        )
        native = native_evidence(native_root)
        code = code_evidence(repo_root, resolved_main)
        code_valid = all(
            item.get("available") and all(item.get("tokens", {}).values())
            for key, item in code.items()
            if key.startswith("src/")
        )
        code_valid = code_valid and bool(code.get("source_matches_main"))
        generator_evidence = native.get("generator_evidence", {})
        native_valid = bool(
            native.get("identity_valid")
            and native.get("formula_evidence", {}).get("all_required_tokens_present")
        )
        if not code_valid:
            all_problems.append(
                "current STSRL producer/consumer source evidence is incomplete"
            )
        if not native_valid:
            all_problems.append("pinned native identity/source evidence is incomplete")
        artifact_valid = artifact_valid and code_valid and native_valid
        table = _candidate_table(source_support, artifact_valid)
        leaf_support = {
            "t064_supervision_state_class": "restored battle-start decision rows; one source checkpoint/teacher/trainer row per selected start",
            "t064_row_count": expected_rows,
            "search_v2_invocation_state_class": "internal leaf after first action from newly expanded node; native callback receives post-action state and legal actions",
            "exact_internal_leaf_labels_retained": False,
            "deterministic_root_to_internal_leaf_transform": False,
            "reason": "T064 compact/teacher/trainer artifacts contain root decision rows and root search statistics, not the post-first-action internal leaf state/target pairs",
        }
        integrity_valid = not all_problems and artifact_valid
        classification_evidence = _classification_evidence(
            table,
            integrity_valid=integrity_valid,
            execution_valid=True,
            generator_evidence=generator_evidence,
        )
        classification = classify_contract(
            table,
            integrity_valid=integrity_valid,
            execution_valid=True,
            generator_evidence=generator_evidence,
        )
        target_definition = (
            "V_leaf=E[evaluateEndState | post-action state, pinned playoutRandom]"
        )
        if classification == "INCOMPLETE":
            recommendation = None
        elif classification == "EXISTING_T064_LEAF_VALUE_LABELS_REUSABLE":
            recommendation = {
                "kind": "bounded paired value-only repair/evaluation task",
                "target_scalar": target_definition,
                "reason": "a retained T064 candidate passed all six gates and retained_labels_sufficient",
            }
        elif classification == "NEW_LEAF_CONTINUATION_UTILITY_TARGET_REQUIRED":
            recommendation = {
                "kind": "bounded successor target-generation task",
                "minimum_data_product": "same-public-state/internal-leaf rows with native evaluateEndState-unit target and explicit terminal-utility continuation rollouts",
                "target_scalar": target_definition,
                "terminal_utility": "exact pinned BattleScumSearcher2::evaluateEndState, including victory/non-victory formulas and all native inputs",
                "continuation_policy": "pinned BattleScumSearcher2::playoutRandom",
                "data_generation_surface": generator_evidence.get(
                    "successor_data_generation_surface"
                ),
                "state_boundary": "sample post-first-action Search v2 internal leaves at the callback boundary; retain public model input and full-simulator Oracle-like target provenance",
                "checks": [
                    "identity/integrity",
                    "target finite/range/unit checks",
                    "continuation-policy reproducibility",
                    "leaf-state coverage",
                    "budget-stability/calibration",
                    "paired fixed-cohort evaluation before promotion",
                ],
                "auxiliary_only": [
                    "battle_survival_probability",
                    "T064 root action means",
                    "native best_action_value",
                    "soft root mean",
                    "terminal resource heads",
                ],
            }
        else:
            recommendation = {
                "kind": "bounded leaf-value contract resolution task",
                "target_scalar": target_definition,
                "reason": "pinned native continuation semantics are not materializable from the accepted surfaces; resolve the hidden post-action state transport before any training successor",
                "required_resolution": "add or identify an accepted read-only target-generation surface that materializes the exact post-action BattleContext without changing Search behavior",
                "no_training_authorized": True,
            }
        result = {
            "schema_id": SCHEMA_ID,
            "schema_version": 1,
            "task_id": "T083",
            "classification": classification,
            "classification_evidence": classification_evidence,
            "recommendation": recommendation,
            "execution": {
                "mode": "offline_streaming",
                "worker_count": 1,
                "worker_reason": "non-simulator artifact audit; bounded single stream",
            },
            "identity": {
                "stsrl_main_commit": EXPECTED_MAIN_COMMIT,
                "stsrl_main_ref": EXPECTED_MAIN_REF,
                "stsrl_main_resolved_commit": resolved_main,
                "native_commit": EXPECTED_NATIVE_COMMIT,
                "native_ref": EXPECTED_NATIVE_REF,
                "native_resolved_ref": native.get("resolved_ref"),
                "native_resolved_commit": native.get("resolved_commit"),
                "t082_report_sha256": EXPECTED_T082_REPORT_SHA,
                "t064_teacher_sha256": EXPECTED_T064_TEACHER_SHA,
                "t064_trainer_sha256": EXPECTED_T064_TRAINER_SHA,
                "row_count": expected_rows,
            },
            "accepted_inputs": {
                "t082": t082_check,
                "t064": artifact_result,
                "teacher": teacher_check,
                "trainer": trainer_check,
            },
            "native_utility_and_backup": native,
            "checkpoint_value_contract": code.get("contract", {}),
            "code_evidence": code,
            "candidate_inventory": teacher,
            "source_realized_terminal_utility": source_support,
            "state_support": leaf_support,
            "candidate_decision_table": table,
            "integrity": {"valid": artifact_valid, "problems": all_problems},
            "problems": all_problems,
        }
    except (
        OSError,
        ValueError,
        TypeError,
        KeyError,
        json.JSONDecodeError,
        StopIteration,
    ) as exc:
        result = _incomplete_report(
            str(exc),
            repo_root=repo_root,
            native_root=native_root,
            expected_rows=expected_rows,
        )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return result
