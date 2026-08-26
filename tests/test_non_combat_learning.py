"""Focused contract tests for the T065 learned non-combat workflow."""

from __future__ import annotations

from dataclasses import replace
import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest

from sts_combat_rl.sim.contract import SimulatorAction
from sts_combat_rl.sim.non_combat_learning import (
    T065_APPROVED_SPEC_COMMIT,
    T065CounterfactualTarget,
    T065CompleteRunArmReport,
    T065HeldoutReport,
    T065_MANDATORY_FAMILIES,
    T065CaseD,
    T065Coverage,
    T065SourceState,
    build_stage6_report,
    build_t065_preflight_report,
    canonical_source_selection_key,
    compute_learned_coverage,
    continuation_seeds_for_split,
    inclusive_range,
    matched_bootstrap_probability,
    train_frozen_model_seeds,
    LearnedNonCombatPolicy,
    load_non_combat_checkpoint,
    screen_family,
    select_source_states,
    source_shard_ranges,
    stage6_shard_ranges,
    target_shard_ranges,
    _spearman_rank_correlation,
    terminal_decision_report,
    validate_t065_preflight,
    write_t065_terminal_decision_report,
    write_t065_manifest,
    write_source_selection_manifest,
)
from sts_combat_rl.sim.non_combat_model_input import (
    NON_COMBAT_ACTION_FEATURE_SIZE,
    NON_COMBAT_CONTEXT_FEATURE_SIZE,
    NON_COMBAT_MODEL_INPUT_SCHEMA_ID,
    NON_COMBAT_MODEL_INPUT_SCHEMA_VERSION,
    NON_COMBAT_SNAPSHOT_FEATURE_SIZE,
    encode_non_combat_snapshot_and_actions,
    non_combat_model_input_schema,
)
from sts_combat_rl.sim.public_context_model_input import (
    PUBLIC_CONTEXT_MODEL_INPUT_FEATURE_NAMES,
)


def _state(index: int, family: str, split: str, seed: int) -> T065SourceState:
    identity = {
        "action_id": f"map:{index}",
        "occurrence": 0,
        "kind": "map",
        "label": "map",
        "stable_id": f"map:{index}",
    }
    context_features = [0.0] * NON_COMBAT_CONTEXT_FEATURE_SIZE
    family_feature = {
        "MAP_SCREEN": "run_position.screen.map",
        "REST_ROOM": "run_position.screen.rest",
        "REWARDS": "run_position.screen.rewards",
        "TREASURE_ROOM": "run_position.screen.treasure",
    }[family]
    context_features[PUBLIC_CONTEXT_MODEL_INPUT_FEATURE_NAMES.index(family_feature)] = (
        1.0
    )
    return T065SourceState(
        selected_state_index=-1,
        family=family,
        split=split,
        simulator_seed=seed,
        source_arm="stochastic_non_combat_v1",
        source_run_id=f"source:{index}",
        source_step_index=index,
        source_floor=1.0,
        source_act=1.0,
        screen_state=family,
        snapshot_features=(0.0,) * NON_COMBAT_SNAPSHOT_FEATURE_SIZE,
        public_context_features=tuple(context_features),
        state_features=(0.0,) * NON_COMBAT_SNAPSHOT_FEATURE_SIZE
        + tuple(context_features),
        legal_action_features=((0.0,) * NON_COMBAT_ACTION_FEATURE_SIZE,),
        legal_action_kinds=("map",),
        eligible_action_indices=(0,),
        legal_action_identities=(identity,),
        action_trace=(),
        public_state_identity=f"state:{index}",
        public_context_status="legacy_unavailable",
        public_run_context={},
        behavior_action_index=0,
        behavior_action_identity=identity,
        terminal=True,
        terminal_status="PLAYER_VICTORY",
        terminal_floor=2.0,
    )


def test_model_input_schema_and_composed_dimensions() -> None:
    action = SimulatorAction(
        action_id="reward:0",
        label="skip",
        kind="skip",
        raw={"scope": "game", "idx1": 0, "idx2": 0, "idx3": 0},
    )
    encoded = encode_non_combat_snapshot_and_actions(
        raw_snapshot={"screen_state": "REWARDS", "battle_active": False},
        public_run_context={},
        actions=[action],
        eligible_action_indices=[0],
        public_context_status="legacy_unavailable",
    )
    assert NON_COMBAT_MODEL_INPUT_SCHEMA_ID == "non-combat-model-input-v1"
    assert NON_COMBAT_MODEL_INPUT_SCHEMA_VERSION == 1
    assert len(encoded.state_features) == 4737
    assert len(encoded.action_features) == 1
    assert len(encoded.action_features[0]) == 92
    assert non_combat_model_input_schema()["public_context_feature_size"] == 103


def test_model_input_rejects_hidden_context_fields() -> None:
    action = SimulatorAction(
        action_id="reward:0",
        label="skip",
        kind="skip",
        raw={"scope": "game", "idx1": 0, "idx2": 0, "idx3": 0},
    )
    with pytest.raises(ValueError, match="forbidden|unsupported"):
        encode_non_combat_snapshot_and_actions(
            raw_snapshot={"screen_state": "REWARDS", "battle_active": False},
            public_run_context={"checkpoint": {"native_payload": "secret"}},
            actions=[action],
            eligible_action_indices=[0],
            public_context_status="available",
        )


def test_exact_shard_layout_and_frozen_seed_mapping() -> None:
    source = source_shard_ranges(arm="expert_non_combat_v1")
    assert len(source) == 16
    assert (source[0]["seed_start"], source[0]["seed_end"]) == (650001, 650016)
    assert (source[-1]["seed_start"], source[-1]["seed_end"]) == (650241, 650256)
    target = target_shard_ranges()
    assert len(target) == 16
    assert (target[0]["selected_state_start"], target[-1]["selected_state_end"]) == (
        0,
        319,
    )
    learned = stage6_shard_ranges(arm="learned")
    assert len(learned) == 16
    assert (learned[0]["seed_start"], learned[-1]["seed_end"]) == (651001, 651256)
    assert continuation_seeds_for_split("heldout") == (652201, 652202, 652203, 652204)


def test_deterministic_selection_uses_family_split_quotas() -> None:
    candidates = []
    for family_index, family in enumerate(T065_MANDATORY_FAMILIES):
        for offset in range(80):
            split = (
                "train" if offset < 48 else "validation" if offset < 64 else "heldout"
            )
            seed = (
                650001
                if split == "train"
                else 650155
                if split == "validation"
                else 650206
            )
            candidates.append(_state(family_index * 100 + offset, family, split, seed))
    selected = select_source_states(candidates)
    assert len(selected) == 320
    assert [selected[index].family for index in (0, 48, 64)] == [
        "MAP_SCREEN",
        "MAP_SCREEN",
        "MAP_SCREEN",
    ]
    assert all(state.selection_digest for state in selected)
    assert (
        canonical_source_selection_key(selected[0])[0] == selected[0].selection_digest
    )


def test_selection_manifest_retains_compact_identity(tmp_path) -> None:
    candidates = []
    for family_index, family in enumerate(T065_MANDATORY_FAMILIES):
        for offset in range(80):
            split = (
                "train" if offset < 48 else "validation" if offset < 64 else "heldout"
            )
            seed = (
                650001
                if split == "train"
                else 650155
                if split == "validation"
                else 650206
            )
            candidates.append(_state(family_index * 100 + offset, family, split, seed))
    selected = select_source_states(candidates)
    path = tmp_path / "selection.manifest.json"
    manifest = write_source_selection_manifest(
        path,
        selected_states=selected,
        selected_artifact_identity={"path": "selected.jsonl", "sha256": "abc"},
        source_artifacts=[{"arm": "expert_non_combat_v1", "sha256": "def"}],
    )
    assert path.exists()
    assert manifest["selected_state_count"] == 320
    assert manifest["counts_by_family_split"]["MAP_SCREEN"]["train"] == 48
    with pytest.raises(ValueError, match="frozen head"):
        write_source_selection_manifest(
            tmp_path / "wrong-spec.manifest.json",
            selected_states=selected,
            selected_artifact_identity={"path": "selected.jsonl", "sha256": "abc"},
            source_artifacts=[],
            approved_spec_commit="wrong-spec-commit",
        )


def test_selection_reports_case_d_when_a_frozen_bucket_is_short() -> None:
    with pytest.raises(T065CaseD, match="requires 48"):
        select_source_states([_state(1, "MAP_SCREEN", "train", 650001)])


def test_stage6_coverage_excludes_battle_and_unsupported_fallback() -> None:
    coverage = compute_learned_coverage(
        [
            {"battle": True, "screen_family": "REWARDS", "status": "learned_failure"},
            {"screen_family": "MAP_SCREEN", "status": "learned_success"},
            {"screen_family": "SHOP_ROOM", "status": "unsupported_fallback"},
            {"screen_family": "REST_ROOM", "status": "learned_failure"},
        ]
    )
    assert coverage == T065Coverage(D=3, L=1, M=2, F=1)
    assert coverage.learned_coverage == pytest.approx(1 / 3)
    assert coverage.mandatory_failure_rate == pytest.approx(0.5)
    assert not coverage.passed


def test_stage6_matched_bootstrap_is_deterministic() -> None:
    probability = matched_bootstrap_probability([1.0] * 256)
    assert probability == 1.0


def test_stage6_invalid_cohort_is_not_interpreted_as_a_gate_failure() -> None:
    report = build_stage6_report([], T065Coverage(D=1, L=1, M=1, F=0))
    assert not report.valid
    assert not report.passed
    assert report.problems


def test_stage6_arm_reducer_requires_exact_simulator_identity() -> None:
    reports = tuple(
        T065CompleteRunArmReport(
            arm=arm,
            driver_seed=654002,
            requested_seeds=(),
            rows=(),
            simulator_identity={"integration_commit": "not-the-pinned-build"},
        )
        for arm in ("stochastic", "expert", "learned")
    )
    report = build_stage6_report(
        [], T065Coverage(D=1, L=1, M=1, F=0), arm_reports=reports
    )
    assert not report.valid
    assert any("simulator identity" in problem for problem in report.problems)


def test_stage6_reducer_requires_each_shard_seed_set_to_match_range() -> None:
    expected_specs = []
    for spec in stage6_shard_ranges(arm="learned"):
        seeds = list(range(spec["seed_start"], spec["seed_end"] + 1))
        expected_specs.append(
            {
                **spec,
                "requested_seeds": seeds,
                "completed_seeds": seeds,
                "requested_seed_count": 16,
                "completed_row_count": 16,
            }
        )
    expected_specs[1]["completed_seeds"] = expected_specs[0]["completed_seeds"]
    reports = tuple(
        T065CompleteRunArmReport(
            arm=arm,
            driver_seed=654002,
            requested_seeds=tuple(range(651001, 651257)),
            rows=(),
            simulator_identity={},
            shard_specs=tuple({**spec, "arm": arm} for spec in expected_specs),
        )
        for arm in ("stochastic", "expert", "learned")
    )
    report = build_stage6_report(
        [], T065Coverage(D=1, L=1, M=1, F=0), arm_reports=reports
    )
    assert not report.valid
    assert any("completed_seeds" in problem for problem in report.problems)


def test_stage6_zero_coverage_denominators_are_invalid() -> None:
    report = build_stage6_report([], T065Coverage(D=0, L=0, M=0, F=0))
    assert not report.valid
    assert any("denominator D is zero" in problem for problem in report.problems)
    assert any("denominator M is zero" in problem for problem in report.problems)


def test_preflight_and_screen_aliases() -> None:
    report = build_t065_preflight_report()
    assert not report.passed
    assert report.runtime_checks["simulator_runtime"]["status"] == "deferred"
    assert report.runtime_checks["torch_runtime"]["status"] == "deferred"
    assert report.capability_checks["t074_import_isolation"]["status"] == "passed"
    assert screen_family("MAP") == "MAP_SCREEN"
    assert screen_family("REST_ROOM") == "REST_ROOM"
    assert inclusive_range((650001, 650003)) == (650001, 650002, 650003)


def test_default_import_does_not_load_optional_torch() -> None:
    source_root = Path(__file__).resolve().parents[1] / "src"
    env = os.environ.copy()
    env["PYTHONPATH"] = str(source_root)
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; import sts_combat_rl.sim.non_combat_learning; "
            "print('torch' in sys.modules)",
        ],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )
    assert result.stdout.strip() == "False"


def test_deferred_preflight_artifact_cannot_gate_workflow(tmp_path) -> None:
    path = tmp_path / "preflight.json"
    report = build_t065_preflight_report().to_dict()
    report["passed"] = True
    path.write_text(json.dumps(report), encoding="utf-8")
    with pytest.raises(T065CaseD, match="preflight"):
        validate_t065_preflight(path)


def test_retention_manifest_rejects_wrong_approved_spec_commit(tmp_path) -> None:
    artifact = tmp_path / "artifact.json"
    artifact.write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="frozen head"):
        write_t065_manifest(
            tmp_path / "retention.json",
            approved_spec_commit="wrong-spec-commit",
            simulator_identity={},
            artifacts={"current_output": artifact},
            regeneration_commands=("reproduce",),
            stage_evidence={"stage0-preflight": {"status": "completed"}},
        )


def test_preceding_manifest_chain_keeps_manifest_identities_separate(tmp_path) -> None:
    from sts_combat_rl.commands.non_combat_learning import (
        _require_preceding_manifests,
        build_parser,
    )

    preflight = tmp_path / "preflight.json"
    states = tmp_path / "states.jsonl"
    preflight.write_text("{}", encoding="utf-8")
    states.write_text("selected states", encoding="utf-8")

    def make_manifest(path: Path, stage: str, artifact: Path) -> Path:
        write_t065_manifest(
            path,
            approved_spec_commit=T065_APPROVED_SPEC_COMMIT,
            simulator_identity={},
            artifacts={"current_output": artifact},
            regeneration_commands=("wsl reproduction",),
            stage_evidence={stage: {"status": "completed"}},
        )
        return path

    preflight_manifest = make_manifest(
        tmp_path / "preflight.retention.json", "stage0-preflight", preflight
    )
    selection_manifest = make_manifest(
        tmp_path / "selection.retention.json",
        "stage1-source-selection",
        states,
    )
    args = build_parser().parse_args(
        [
            "target",
            "--states",
            str(states),
            "--output",
            str(tmp_path / "targets.json"),
            "--preflight",
            str(preflight),
            "--preceding-manifest",
            str(preflight_manifest),
            "--preceding-manifest",
            str(selection_manifest),
        ]
    )
    _require_preceding_manifests(args)
    lineage = args._preceding_manifest_identities
    assert set(lineage) == {"stage0_preflight", "stage1_source_selection"}
    assert lineage["stage0_preflight"]["path"] == str(preflight_manifest)
    assert lineage["stage0_preflight"]["sha256"]
    assert lineage["stage0_preflight"]["schema_id"] == "t065-retention-manifest-v1"
    assert "selected_states" not in lineage


def test_regeneration_command_is_full_pinned_wsl_command(tmp_path) -> None:
    from sts_combat_rl.commands.non_combat_learning import (
        _regeneration_command,
        build_parser,
    )

    args = build_parser().parse_args(
        [
            "evaluate",
            "--target-table",
            str(tmp_path / "targets.json"),
            "--checkpoint-directory",
            str(tmp_path / "checkpoints"),
            "--output",
            str(tmp_path / "evaluate.json"),
            "--run-stage6",
            "--preflight",
            str(tmp_path / "preflight.json"),
            "--preceding-manifest",
            str(tmp_path / "preflight.retention.json"),
            "--preceding-manifest",
            str(tmp_path / "target.retention.json"),
            "--preceding-manifest",
            str(tmp_path / "train.retention.json"),
        ]
    )
    command = _regeneration_command(args)
    assert "/home/lsmft/stsrl-spikes/py313-torch/bin/python" in command
    assert "/home/lsmft/stsrl-spikes/sts_lightspeed/build-py313-torch" in command
    assert "/mnt/d/DeadlycatCoding/STSRL/.claude/worktrees/" in command
    assert "651001..651256" in command
    assert "frozen_shards=16" in command
    assert "frozen_worker_count=16" in command
    assert "/evaluate.json" in command


def test_train_preflight_failure_writes_terminal_report_and_retention_manifest(
    tmp_path,
) -> None:
    from sts_combat_rl.commands.non_combat_learning import main

    preflight = tmp_path / "preflight.json"
    preflight.write_text(json.dumps({"schema_id": "wrong"}), encoding="utf-8")
    output = tmp_path / "train.json"
    assert (
        main(
            [
                "train",
                "--target-table",
                str(tmp_path / "targets.json"),
                "--checkpoint-directory",
                str(tmp_path / "checkpoints"),
                "--output",
                str(output),
                "--preflight",
                str(preflight),
            ]
        )
        == 1
    )
    decision_path = tmp_path / "train.t065-terminal-decision-report.json"
    manifest_path = tmp_path / "train.t065-retention-manifest.json"
    decision = json.loads(decision_path.read_text(encoding="utf-8"))
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert decision["schema_id"] == "t065-terminal-decision-report-v1"
    assert decision["case"] == "D"
    assert decision["approved_spec_commit"]
    assert decision["failure_ids"]
    assert decision["failure_counts"]["failure_count"] >= 1
    assert decision["no_replacement"] is True
    assert "stage5" in decision["downstream_skipped"]
    assert any(
        artifact["role"] == "failed_preflight_artifact"
        for artifact in manifest["artifacts"]
    )
    assert "failed_preflight_artifact" in decision["failed_stage_artifacts"]
    assert decision["preceding_stage_manifests"] == {}
    assert manifest["stage_evidence"]["stage0-preflight"]["terminal"] is True


def test_case_c_terminal_report_keeps_failure_metadata() -> None:
    stage5 = T065HeldoutReport(
        selected_model_seed=653001,
        selected_validation_mae=1.0,
        model_results={},
        aggregate_mean_delta=-1.0,
        median_delta=-1.0,
        family_mean_deltas={},
        p_positive=0.0,
        non_selected_model_mean_delta=-1.0,
        passed=False,
        problems=("aggregate paired delta is not positive",),
    )
    decision = terminal_decision_report(
        stage5=stage5,
        simulator_identity={"integration_commit": "fixture"},
        preceding_stage_manifests={"target_table": {"sha256": "abc"}},
    )
    assert decision["case"] == "C"
    assert decision["approved_spec_commit"]
    assert decision["simulator_identity"]["integration_commit"] == "fixture"
    assert decision["failure_ids"]
    assert decision["failure_counts"]["failure_count"] == 1
    assert decision["no_replacement"] is True
    assert decision["downstream_skipped"] == ["stage6"]


def test_learned_driver_and_fallback_provenance_keep_frozen_seed() -> None:
    policy = LearnedNonCombatPolicy(
        SimpleNamespace(checkpoint_artifact_id="checkpoint", model_seed=653001)
    )
    config = policy.provenance_config
    assert config["seed"] == 654002
    assert config["fallback_provenance"]["seed"] == 654002


def test_case_d_report_is_persisted_with_frozen_repair_contract(tmp_path) -> None:
    failure = T065CaseD(
        "counterfactual-targets",
        ["state 7 action 2 continuation 652001 failed"],
        failure_ids=("state:7", "action:2", "continuation:652001"),
        failure_counts={"failed_branches": 1},
        simulator_identity={"integration_commit": "fixture"},
    )
    report = write_t065_terminal_decision_report(tmp_path / "decision.json", failure)
    assert report["case"] == "D"
    assert report["approved_spec_commit"]
    assert report["failure_ids"] == ["state:7", "action:2", "continuation:652001"]
    assert report["failure_counts"]["failed_branches"] == 1
    assert report["no_replacement"] is True
    assert report["downstream_skipped"] == ["stage3", "stage4", "stage5", "stage6"]
    assert (
        report["recommendation"] == "repair the frozen fidelity failure and rerun T065"
    )


def test_legacy_public_context_is_fail_closed_and_family_projection_is_rechecked() -> (
    None
):
    state = _state(7, "MAP_SCREEN", "train", 650001)
    with pytest.raises(ValueError, match="forbidden"):
        replace(state, public_run_context={"native_payload": "private"})
    with pytest.raises(T065CaseD, match="T033"):
        replace(
            state,
            public_context_features=(0.0,) * NON_COMBAT_CONTEXT_FEATURE_SIZE,
            state_features=(0.0,) * len(state.state_features),
        )


def test_spearman_rank_correlation_uses_average_ties() -> None:
    assert _spearman_rank_correlation(
        (1.0, 2.0, 3.0), (3.0, 2.0, 1.0)
    ) == pytest.approx(-1.0)
    assert _spearman_rank_correlation((1.0,), (1.0,)) is None
    assert _spearman_rank_correlation((1.0, 1.0), (1.0, 2.0)) is None


def test_two_frozen_torch_seeds_checkpoint_and_normalizer_contract(tmp_path) -> None:
    torch = pytest.importorskip("torch")
    states = []
    targets = []
    for index in range(320):
        split = "train" if index < 192 else "validation" if index < 256 else "heldout"
        seed = (
            650001 if split == "train" else 650155 if split == "validation" else 650206
        )
        state = replace(
            _state(index, T065_MANDATORY_FAMILIES[index // 80], split, seed),
            selected_state_index=index,
        )
        states.append(state)
        seeds = continuation_seeds_for_split(split)
        targets.append(
            T065CounterfactualTarget(
                selected_state_index=index,
                state_identity=state.state_identity,
                family=state.family,
                split=split,
                legal_action_index=0,
                legal_action_identity=state.legal_action_identities[0],
                continuation_seeds=seeds,
                terminal_floors=(2.0,) * len(seeds),
                terminal_acts=(1.0,) * len(seeds),
                terminal_statuses=("PLAYER_VICTORY",) * len(seeds),
                terminal_current_hps=(70.0,) * len(seeds),
                terminal_max_hps=(80.0,) * len(seeds),
                terminal_golds=(99.0,) * len(seeds),
                terminal_potion_counts=(0.0,) * len(seeds),
                q_floor=1.0,
            )
        )
    runs = train_frozen_model_seeds(
        states=states,
        targets=targets,
        checkpoint_directory=tmp_path,
    )
    assert tuple(run.model_seed for run in runs) == (653001, 653002)
    assert all(run.training_steps == 1500 for run in runs)
    assert runs[0].normalizers == runs[1].normalizers
    for seed in (653001, 653002):
        checkpoint = load_non_combat_checkpoint(tmp_path / f"model-{seed}.pt")
        assert checkpoint.model_seed == seed
        assert checkpoint.training_steps == 1500
        assert checkpoint.normalizers == runs[0].normalizers
        assert (
            checkpoint.metadata["training_config"]["minibatch_rng_seed"]
            == seed + 1_000_000
        )
        raw = torch.load(
            tmp_path / f"model-{seed}.pt", map_location="cpu", weights_only=True
        )
        assert raw["model_seed"] == raw["metadata"]["model_seed"] == seed
        assert raw["training_steps"] == raw["metadata"]["training_steps"] == 1500
        assert (
            raw["validation_q_floor_mae"] == raw["metadata"]["validation_q_floor_mae"]
        )
