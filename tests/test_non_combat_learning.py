"""Focused contract tests for the T065 learned non-combat workflow."""

from __future__ import annotations

from dataclasses import replace
from io import StringIO
import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest

from sts_combat_rl.sim.contract import (
    SimulatorAction,
    SimulatorCheckpoint,
    SimulatorSnapshot,
    SimulatorTransition,
)
from sts_combat_rl.sim.decision_record import action_identity_dicts_for_actions
from sts_combat_rl.sim.non_combat_learning import (
    T065_APPROVED_SPEC_COMMIT,
    T065CounterfactualTarget,
    T065CompleteRunArmReport,
    T065ExperimentConfig,
    T065HeldoutReport,
    T065_MANDATORY_FAMILIES,
    T065_NATIVE_PROBE_MAX_STEPS,
    T065CaseD,
    T065Coverage,
    T065SourceArmReport,
    T065SourceState,
    build_stage6_report,
    build_t065_preflight_report,
    canonical_source_selection_key,
    compute_learned_coverage,
    collect_source_arm_sharded,
    collect_source_arm_sharded_to_path,
    continuation_seeds_for_split,
    file_sha256,
    frozen_action_space,
    frozen_battle_provenance,
    inclusive_range,
    matched_bootstrap_probability,
    train_frozen_model_seeds,
    LearnedNonCombatPolicy,
    load_non_combat_checkpoint,
    screen_family,
    select_source_states,
    select_t075_source_candidates,
    split_for_source_seed,
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
from sts_combat_rl.commands.non_combat_learning import (
    T075WorkflowError,
    _portable_path,
    _handle_t075_case_d,
    _run_t075_finalize,
    _t075_path_matches,
    _t075_preceding_manifest_path,
    _t075_pinned_simulator_identity,
    _t075_require_pinned_simulator_identity,
    _t075_resolve_reuse_manifest,
    _run_t075_select,
    _t075_target_row_completeness,
    _t075_write_stage3_report,
    _write_t075_stage_retention,
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


def _write_source_fixture(path: Path, arm: str, states: list[T065SourceState]) -> None:
    from sts_combat_rl.sim.lightspeed_source import lightspeed_source_identity_dict

    payload = {
        "schema_id": "t065-learned-non-combat-policy-v1",
        "schema_version": 1,
        "arm": arm,
        "driver_seed": 654001,
        "requested_seed_count": 256,
        "terminal_run_count": 256,
        "truncated_run_count": 0,
        "failed_run_count": 0,
        "selected_candidate_count": len(states),
        "run_summaries": [
            {
                "simulator_seed": seed,
                "source_arm": arm,
                "source_run_id": f"{arm}:{seed}",
                "terminal": True,
                "problems": [],
            }
            for seed in range(650001, 650257)
        ],
        "problems": [],
        "approved_spec_commit": T065_APPROVED_SPEC_COMMIT,
        "frozen_config": T065ExperimentConfig().to_dict(),
        "simulator_identity": lightspeed_source_identity_dict(),
        "action_space": frozen_action_space().to_dict(),
        "battle_controller_provenance": frozen_battle_provenance(),
        "worker_count": 16,
        "shard_count": 16,
        "shard_specs": [
            {
                **spec,
                "requested_seed_count": 16,
                "terminal_run_count": 16,
                "truncated_run_count": 0,
                "failed_run_count": 0,
                "problems": [],
            }
            for spec in source_shard_ranges(arm=arm)
        ],
        "records": [state.to_dict() for state in states],
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def _fake_source_shard_report(
    source_arm: str,
    seeds: tuple[int, ...],
    record: T065SourceState,
    record_sink,
) -> T065SourceArmReport:
    from sts_combat_rl.sim.lightspeed_source import lightspeed_source_identity_dict

    if record_sink is not None:
        record_sink(record)
        records = ()
    else:
        records = (record,)
    action_space = frozen_action_space().to_dict()
    return T065SourceArmReport(
        arm=source_arm,
        driver_seed=654001,
        requested_seed_count=len(seeds),
        terminal_run_count=len(seeds),
        truncated_run_count=0,
        failed_run_count=0,
        selected_candidate_count=len(records) if record_sink is None else 1,
        records=records,
        run_summaries=tuple(
            {
                "source_run_id": f"{source_arm}:{seed}",
                "simulator_seed": seed,
                "source_arm": source_arm,
                "terminal": True,
                "outcome": "PLAYER_VICTORY",
                "step_count": 1,
                "terminal_floor": 2.0,
                "problems": [],
                "controller_provenance": {},
                "action_space": action_space,
                "simulator_cost": {},
            }
            for seed in seeds
        ),
        problems=(),
        simulator_identity=lightspeed_source_identity_dict(),
        action_space=action_space,
        battle_controller_provenance=frozen_battle_provenance(),
        wall_clock_seconds=0.1,
    )


def test_bounded_shard_writer_preserves_order_and_skips_aggregate_to_dict(
    tmp_path, monkeypatch
) -> None:
    import sts_combat_rl.sim.non_combat_learning as learning

    expected_states = [None] * 16

    def fake_collect(
        adapter_factory,
        *,
        source_arm,
        seeds,
        record_sink=None,
    ) -> T065SourceArmReport:
        del adapter_factory
        seed_values = tuple(seeds)
        shard_index = (seed_values[0] - 650001) // 16
        state = replace(
            _state(
                shard_index,
                T065_MANDATORY_FAMILIES[shard_index % len(T065_MANDATORY_FAMILIES)],
                split_for_source_seed(seed_values[0]),
                seed_values[0],
            ),
            source_arm=source_arm,
            source_run_id=f"{source_arm}:{seed_values[0]}",
        )
        expected_states[shard_index] = state
        return _fake_source_shard_report(source_arm, seed_values, state, record_sink)

    monkeypatch.setattr(learning, "collect_source_arm", fake_collect)

    def aggregate_to_dict_must_not_run(self):
        raise AssertionError("bounded writer must not call aggregate to_dict")

    monkeypatch.setattr(T065SourceArmReport, "to_dict", aggregate_to_dict_must_not_run)
    output_path = tmp_path / "source.json"
    report = collect_source_arm_sharded_to_path(
        lambda: None, output_path, source_arm="stochastic_non_combat_v1"
    )

    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert list(payload) == sorted(payload)
    assert payload["records"] == [
        state.to_dict() for state in expected_states if state is not None
    ]
    assert [row["simulator_seed"] for row in payload["run_summaries"]] == list(
        range(650001, 650257)
    )
    assert report.records == ()
    assert report.selected_candidate_count == 16


def test_bounded_shard_writer_rejects_invalid_fragment_record(
    tmp_path, monkeypatch
) -> None:
    import sts_combat_rl.sim.non_combat_learning as learning

    def fake_collect(
        adapter_factory,
        *,
        source_arm,
        seeds,
        record_sink=None,
    ) -> T065SourceArmReport:
        del adapter_factory
        seed_values = tuple(seeds)
        shard_index = (seed_values[0] - 650001) // 16
        state = replace(
            _state(
                shard_index,
                T065_MANDATORY_FAMILIES[shard_index % len(T065_MANDATORY_FAMILIES)],
                split_for_source_seed(seed_values[0]),
                seed_values[0],
            ),
            source_arm=source_arm,
            source_run_id=f"{source_arm}:{seed_values[0]}",
            terminal=False if shard_index == 4 else True,
        )
        return _fake_source_shard_report(source_arm, seed_values, state, record_sink)

    monkeypatch.setattr(learning, "collect_source_arm", fake_collect)
    output_path = tmp_path / "source.json"
    with pytest.raises(ValueError, match="invalid source semantics"):
        collect_source_arm_sharded_to_path(
            lambda: None, output_path, source_arm="stochastic_non_combat_v1"
        )
    assert not output_path.exists()
    assert not list(tmp_path.glob(".source.json.shards-*"))


def test_bounded_shard_writer_rejects_truncated_fragment_json(
    tmp_path, monkeypatch
) -> None:
    import sts_combat_rl.sim.non_combat_learning as learning

    def fake_collect(
        adapter_factory,
        *,
        source_arm,
        seeds,
        record_sink=None,
    ) -> T065SourceArmReport:
        del adapter_factory
        seed_values = tuple(seeds)
        shard_index = (seed_values[0] - 650001) // 16
        state = replace(
            _state(
                shard_index,
                T065_MANDATORY_FAMILIES[shard_index % len(T065_MANDATORY_FAMILIES)],
                split_for_source_seed(seed_values[0]),
                seed_values[0],
            ),
            source_arm=source_arm,
            source_run_id=f"{source_arm}:{seed_values[0]}",
        )
        return _fake_source_shard_report(source_arm, seed_values, state, record_sink)

    original_dumps = learning.json.dumps

    def write_truncated_source_state(value, *args, **kwargs):
        if isinstance(value, dict) and "state_features" in value:
            return '{"truncated":'
        return original_dumps(value, *args, **kwargs)

    monkeypatch.setattr(learning, "collect_source_arm", fake_collect)
    monkeypatch.setattr(learning.json, "dumps", write_truncated_source_state)
    output_path = tmp_path / "source.json"
    with pytest.raises(ValueError, match="record 1 is invalid JSON"):
        collect_source_arm_sharded_to_path(
            lambda: None, output_path, source_arm="stochastic_non_combat_v1"
        )
    assert not output_path.exists()
    assert not list(tmp_path.glob(".source.json.shards-*"))


def test_bounded_shard_writer_requires_frozen_worker_count(tmp_path) -> None:
    with pytest.raises(ValueError, match="exactly 16 workers"):
        collect_source_arm_sharded_to_path(
            lambda: None,
            tmp_path / "source.json",
            source_arm="stochastic_non_combat_v1",
            worker_count=8,
        )


def test_bounded_shard_writer_checks_each_fragment_count(tmp_path, monkeypatch) -> None:
    import sts_combat_rl.sim.non_combat_learning as learning

    def fake_collect(
        adapter_factory,
        *,
        source_arm,
        seeds,
        record_sink=None,
    ) -> T065SourceArmReport:
        del adapter_factory
        seed_values = tuple(seeds)
        shard_index = (seed_values[0] - 650001) // 16
        actual_count = 2 if shard_index == 1 else 1
        states = [
            replace(
                _state(
                    shard_index * 10 + offset,
                    T065_MANDATORY_FAMILIES[
                        (shard_index + offset) % len(T065_MANDATORY_FAMILIES)
                    ],
                    split_for_source_seed(seed_values[0]),
                    seed_values[0],
                ),
                source_arm=source_arm,
                source_run_id=f"{source_arm}:{seed_values[0]}",
            )
            for offset in range(actual_count)
        ]
        if record_sink is not None:
            for state in states:
                record_sink(state)
        reported_count = (
            2 if shard_index == 0 else 1 if shard_index == 1 else actual_count
        )
        report = _fake_source_shard_report(
            source_arm, seed_values, states[0], record_sink=None
        )
        return replace(
            report,
            records=(),
            selected_candidate_count=reported_count,
        )

    monkeypatch.setattr(learning, "collect_source_arm", fake_collect)
    output_path = tmp_path / "source.json"
    with pytest.raises(ValueError, match="shard 0.*record count"):
        collect_source_arm_sharded_to_path(
            lambda: None, output_path, source_arm="stochastic_non_combat_v1"
        )
    assert not output_path.exists()
    assert not list(tmp_path.glob(".source.json.shards-*"))


def test_legacy_sharded_collection_api_is_documented_as_non_full_scale() -> None:
    docstring = collect_source_arm_sharded.__doc__ or ""
    assert "small/legacy" in docstring
    assert "collect_source_arm_sharded_to_path" in docstring


def test_bounded_shard_writer_cleans_fragments_on_shard_failure(
    tmp_path, monkeypatch
) -> None:
    import sts_combat_rl.sim.non_combat_learning as learning

    def failing_collect(
        adapter_factory,
        *,
        source_arm,
        seeds,
        record_sink=None,
    ) -> T065SourceArmReport:
        del adapter_factory
        seed_values = tuple(seeds)
        shard_index = (seed_values[0] - 650001) // 16
        state = replace(
            _state(
                shard_index,
                T065_MANDATORY_FAMILIES[shard_index % len(T065_MANDATORY_FAMILIES)],
                split_for_source_seed(seed_values[0]),
                seed_values[0],
            ),
            source_arm=source_arm,
            source_run_id=f"{source_arm}:{seed_values[0]}",
        )
        if shard_index == 3:
            # Leave one partial record in the failing shard fragment so the
            # writer's cleanup path is exercised without duplicating records
            # in successful shards.
            if record_sink is not None:
                record_sink(state)
            raise RuntimeError("fixture shard failure")
        return _fake_source_shard_report(source_arm, seed_values, state, record_sink)

    monkeypatch.setattr(learning, "collect_source_arm", failing_collect)
    output_path = tmp_path / "source.json"
    with pytest.raises(RuntimeError, match="fixture shard failure"):
        collect_source_arm_sharded_to_path(
            lambda: None, output_path, source_arm="stochastic_non_combat_v1"
        )
    assert not output_path.exists()
    assert not list(tmp_path.glob(".source.json.shards-*"))


def test_bounded_shard_writer_rejects_existing_output(tmp_path, monkeypatch) -> None:
    import sts_combat_rl.sim.non_combat_learning as learning

    output_path = tmp_path / "source.json"
    output_path.write_text('{"old": true}\n', encoding="utf-8")

    def unexpected_collect(*args, **kwargs):
        raise AssertionError("an existing output must be rejected before collection")

    monkeypatch.setattr(learning, "collect_source_arm", unexpected_collect)
    with pytest.raises(FileExistsError, match="already exists"):
        collect_source_arm_sharded_to_path(
            lambda: None,
            output_path,
            source_arm="stochastic_non_combat_v1",
        )
    assert output_path.read_text(encoding="utf-8") == '{"old": true}\n'
    assert not list(tmp_path.glob(".source.json.shards-*"))


def test_run_collect_full_range_dispatches_bounded_writer_without_report_to_dict(
    tmp_path, monkeypatch
) -> None:
    import sts_combat_rl.commands.non_combat_learning as command

    report = T065SourceArmReport(
        arm="stochastic_non_combat_v1",
        driver_seed=654001,
        requested_seed_count=256,
        terminal_run_count=256,
        truncated_run_count=0,
        failed_run_count=0,
        selected_candidate_count=0,
    )
    calls = []

    def bounded_writer(adapter_factory, output_path, *, source_arm, worker_count):
        calls.append((output_path, source_arm, worker_count))
        return report

    monkeypatch.setattr(command, "collect_source_arm_sharded_to_path", bounded_writer)
    monkeypatch.setattr(command, "_require_preflight", lambda args: None)
    monkeypatch.setattr(command, "_require_preceding_manifests", lambda args: None)
    monkeypatch.setattr(command, "_require_frozen_simulator_args", lambda args: None)
    monkeypatch.setattr(command, "_write_workflow_manifest", lambda args, stage: None)

    def aggregate_to_dict_must_not_run(self):
        raise AssertionError("full-range collect must not call aggregate to_dict")

    monkeypatch.setattr(T065SourceArmReport, "to_dict", aggregate_to_dict_must_not_run)
    output_path = tmp_path / "source.json"
    assert (
        command._run_collect(
            SimpleNamespace(
                command="collect",
                arm="stochastic_non_combat_v1",
                output=output_path,
                seed_start=650001,
                seed_end=650256,
                sim_seed=1,
                ascension=20,
                preflight=tmp_path / "preflight.json",
                preceding_manifest=(),
                retention_manifest=None,
            )
        )
        == 0
    )
    assert calls == [(output_path, "stochastic_non_combat_v1", 16)]


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


def test_cross_split_case_d_reports_sorted_candidate_provenance() -> None:
    map_previous = _state(1, "MAP_SCREEN", "train", 650001)
    map_current = replace(
        map_previous,
        simulator_seed=650155,
        split="validation",
        source_run_id="stochastic_non_combat_v1:650155",
    )
    rest_previous = _state(2, "REST_ROOM", "train", 650002)
    rest_current = replace(
        rest_previous,
        simulator_seed=650156,
        split="validation",
        source_run_id="expert_non_combat_v1:650156",
    )
    candidates = [rest_previous, rest_current, map_previous, map_current]

    with pytest.raises(T065CaseD) as caught:
        select_source_states(candidates)

    failure = caught.value
    report = failure.to_decision_report()
    details = report["failure_details"]
    assert [detail["family"] for detail in details] == [
        "MAP_SCREEN",
        "REST_ROOM",
    ]
    assert all(
        detail["failure_type"] == "replay-equivalent-cross-split" for detail in details
    )
    assert all(
        detail["previous"]["split"] == "train"
        and detail["current"]["split"] == "validation"
        and detail["previous"]["public_state_identity"]
        == detail["current"]["public_state_identity"]
        and detail["previous"]["replay_identity_digest"]
        == detail["current"]["replay_identity_digest"]
        for detail in details
    )
    assert details[0]["previous"]["source_run_id"] == "source:1"
    assert details[0]["current"]["source_run_id"] == ("stochastic_non_combat_v1:650155")
    assert details[1]["current"]["source_run_id"] == ("expert_non_combat_v1:650156")
    assert report["failure_ids"] == [detail["failure_id"] for detail in details]
    assert report["problems"] == [detail["problem"] for detail in details]
    assert report["failure_counts"] == {
        "failure_count": 2,
        "replay_equivalent_cross_split": 2,
    }
    assert report["failure_detail_counts"] == {
        "total": 2,
        "by_type": {"replay-equivalent-cross-split": 2},
        "by_family": {"MAP_SCREEN": 1, "REST_ROOM": 1},
        "by_split_pair": {"train->validation": 2},
    }

    with pytest.raises(T065CaseD) as reversed_caught:
        select_source_states([map_previous, map_current, rest_previous, rest_current])
    assert reversed_caught.value.failure_details == failure.failure_details


def test_streamed_two_arm_selection_matches_in_memory_without_json_load(
    tmp_path, monkeypatch
) -> None:
    import sts_combat_rl.commands.non_combat_learning as command

    stochastic = []
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
            stochastic.append(_state(family_index * 100 + offset, family, split, seed))
    expert = [replace(state, source_arm="expert_non_combat_v1") for state in stochastic]

    stochastic_path = tmp_path / "stochastic.json"
    expert_path = tmp_path / "expert.json"
    _write_source_fixture(stochastic_path, "stochastic_non_combat_v1", stochastic)
    _write_source_fixture(expert_path, "expert_non_combat_v1", expert)

    original_json_loads = command.json.loads
    loaded_document_sizes = []

    def reject_whole_source_load(document, *args, **kwargs):
        loaded_document_sizes.append(len(document))
        if len(document) > 100_000:
            raise AssertionError("streaming selection must not load a whole source")
        return original_json_loads(document, *args, **kwargs)

    monkeypatch.setattr(command.json, "loads", reject_whole_source_load)
    expected = select_source_states(stochastic + expert)

    def streamed_candidates():
        yield from command._iter_source_arm_states(stochastic_path)
        yield from command._iter_source_arm_states(expert_path)

    actual = select_source_states(streamed_candidates())
    assert [state.to_dict() for state in actual] == [
        state.to_dict() for state in expected
    ]
    assert max(loaded_document_sizes, default=0) <= 100_000


def test_run_select_streams_two_arms_and_records_source_sizes(
    tmp_path, monkeypatch
) -> None:
    import sts_combat_rl.commands.non_combat_learning as command

    stochastic = [
        _state(
            family_index * 100 + offset,
            family,
            "train" if offset < 48 else "validation" if offset < 64 else "heldout",
            650001 if offset < 48 else 650155 if offset < 64 else 650206,
        )
        for family_index, family in enumerate(T065_MANDATORY_FAMILIES)
        for offset in range(80)
    ]
    expert = [replace(state, source_arm="expert_non_combat_v1") for state in stochastic]
    stochastic_path = tmp_path / "stochastic.json"
    expert_path = tmp_path / "expert.json"
    _write_source_fixture(stochastic_path, "stochastic_non_combat_v1", stochastic)
    _write_source_fixture(expert_path, "expert_non_combat_v1", expert)
    output_path = tmp_path / "selected.jsonl"
    manifest_path = tmp_path / "selected.manifest.json"

    monkeypatch.setattr(command, "_require_preflight", lambda args: None)
    monkeypatch.setattr(command, "_require_preceding_manifests", lambda args: None)
    monkeypatch.setattr(command, "_write_workflow_manifest", lambda args, stage: None)
    monkeypatch.setattr(command._StreamingJsonReader, "_CHUNK_SIZE", 4096)

    assert (
        command._run_select(
            SimpleNamespace(
                input=[stochastic_path, expert_path],
                output=output_path,
                manifest=manifest_path,
            )
        )
        == 0
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["selected_state_count"] == 320
    assert [item["size_bytes"] for item in manifest["source_artifacts"]] == [
        stochastic_path.stat().st_size,
        expert_path.stat().st_size,
    ]
    assert len(output_path.read_text(encoding="utf-8").splitlines()) == 320


def test_run_select_rejects_source_tail_change_between_passes(
    tmp_path, monkeypatch
) -> None:
    import sts_combat_rl.commands.non_combat_learning as command

    stochastic = [
        _state(
            family_index * 100 + offset,
            family,
            "train" if offset < 48 else "validation" if offset < 64 else "heldout",
            650001 if offset < 48 else 650155 if offset < 64 else 650206,
        )
        for family_index, family in enumerate(T065_MANDATORY_FAMILIES)
        for offset in range(80)
    ]
    expert = [replace(state, source_arm="expert_non_combat_v1") for state in stochastic]
    stochastic_path = tmp_path / "stochastic.json"
    expert_path = tmp_path / "expert.json"
    _write_source_fixture(stochastic_path, "stochastic_non_combat_v1", stochastic)
    _write_source_fixture(expert_path, "expert_non_combat_v1", expert)

    original_init = command._SourceArmArtifactReader.__init__
    init_counts: dict[Path, int] = {}

    def init_with_controlled_tail_change(reader, path):
        original_init(reader, path)
        normalized_path = Path(path)
        init_counts[normalized_path] = init_counts.get(normalized_path, 0) + 1
        if normalized_path == expert_path and init_counts[normalized_path] == 2:
            with normalized_path.open("a", encoding="utf-8") as stream:
                stream.write("\n")

    monkeypatch.setattr(
        command._SourceArmArtifactReader, "__init__", init_with_controlled_tail_change
    )
    monkeypatch.setattr(command, "_require_preflight", lambda args: None)
    monkeypatch.setattr(command, "_require_preceding_manifests", lambda args: None)

    with pytest.raises(T065CaseD, match="changed between selection passes"):
        command._run_select(
            SimpleNamespace(
                input=[stochastic_path, expert_path],
                output=tmp_path / "selected.jsonl",
                manifest=tmp_path / "selected.manifest.json",
            )
        )
    assert not (tmp_path / "selected.jsonl").exists()
    assert not (tmp_path / "selected.manifest.json").exists()


def test_streaming_json_reader_handles_split_scalar_and_record(monkeypatch) -> None:
    import sts_combat_rl.commands.non_combat_learning as command

    monkeypatch.setattr(command._StreamingJsonReader, "_CHUNK_SIZE", 2)
    scalar_reader = command._StreamingJsonReader(StringIO("650001"))
    assert scalar_reader.value() == 650001
    record_reader = command._StreamingJsonReader(
        StringIO('[{"simulator_seed": 650001, "source_arm": "expert"}]')
    )
    assert list(record_reader.array_values()) == [
        {"simulator_seed": 650001, "source_arm": "expert"}
    ]


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("schema_version", 999, "schema version"),
        ("frozen_config", {}, "frozen config"),
        ("selected_candidate_count", 0, "candidate count"),
    ],
)
def test_streaming_source_reader_validates_report_metadata(
    tmp_path, field, value, message
) -> None:
    import sts_combat_rl.commands.non_combat_learning as command

    path = tmp_path / "source.json"
    _write_source_fixture(
        path,
        "stochastic_non_combat_v1",
        [_state(1, "MAP_SCREEN", "train", 650001)],
    )
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload[field] = value
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(T065CaseD, match=message):
        list(command._iter_source_arm_states(path))


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("source_arm", "expert_non_combat_v1"),
        ("source_run_id", "wrong-run-id"),
        ("terminal", 1),
    ],
)
def test_streaming_source_reader_rejects_tampered_summary_identity(
    tmp_path, field, value
) -> None:
    import sts_combat_rl.commands.non_combat_learning as command

    path = tmp_path / "source.json"
    _write_source_fixture(
        path,
        "stochastic_non_combat_v1",
        [_state(1, "MAP_SCREEN", "train", 650001)],
    )
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["run_summaries"][0][field] = value
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(T065CaseD, match="source summary is not valid"):
        list(command._iter_source_arm_states(path))


def test_t065_source_artifact_battle_provenance_is_cwd_stable(
    tmp_path, monkeypatch
) -> None:
    import sts_combat_rl.commands.non_combat_learning as command

    path = tmp_path / "source.json"
    _write_source_fixture(
        path,
        "stochastic_non_combat_v1",
        [_state(1, "MAP_SCREEN", "train", 650001)],
    )
    original_cwd = Path.cwd()
    alternate_cwd = tmp_path / "other-worktree"
    alternate_cwd.mkdir()
    monkeypatch.chdir(alternate_cwd)

    assert (
        frozen_battle_provenance()
        == json.loads(path.read_text(encoding="utf-8"))["battle_controller_provenance"]
    )
    assert len(list(command._iter_source_arm_states(path))) == 1
    assert Path.cwd() == alternate_cwd
    assert original_cwd != alternate_cwd


def test_run_select_rejects_corrupt_source_tail_without_output(
    tmp_path, monkeypatch
) -> None:
    import sts_combat_rl.commands.non_combat_learning as command

    states = [
        _state(
            family_index * 100 + offset,
            family,
            "train" if offset < 48 else "validation" if offset < 64 else "heldout",
            650001 if offset < 48 else 650155 if offset < 64 else 650206,
        )
        for family_index, family in enumerate(T065_MANDATORY_FAMILIES)
        for offset in range(80)
    ]
    valid_path = tmp_path / "stochastic.json"
    corrupt_path = tmp_path / "expert.json"
    _write_source_fixture(valid_path, "stochastic_non_combat_v1", states)
    _write_source_fixture(
        corrupt_path,
        "expert_non_combat_v1",
        [replace(state, source_arm="expert_non_combat_v1") for state in states],
    )
    corrupt_path.write_text(
        corrupt_path.read_text(encoding="utf-8") + " trailing",
        encoding="utf-8",
    )
    output_path = tmp_path / "selected.jsonl"
    monkeypatch.setattr(command, "_require_preflight", lambda args: None)
    monkeypatch.setattr(command, "_require_preceding_manifests", lambda args: None)

    with pytest.raises(ValueError, match="trailing"):
        command._run_select(
            SimpleNamespace(
                input=[valid_path, corrupt_path],
                output=output_path,
                manifest=tmp_path / "selected.manifest.json",
            )
        )
    assert not output_path.exists()


def test_selection_manifest_retains_compact_identity(tmp_path) -> None:
    from sts_combat_rl.sim.lightspeed_source import lightspeed_source_identity_dict

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
    assert manifest["simulator_identity"] == lightspeed_source_identity_dict()
    with pytest.raises(T065CaseD, match="simulator identity"):
        write_source_selection_manifest(
            tmp_path / "wrong-identity.manifest.json",
            selected_states=selected,
            selected_artifact_identity={"path": "selected.jsonl", "sha256": "abc"},
            source_artifacts=[],
            simulator_identity={"integration_commit": "not-pinned"},
        )
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


def test_preflight_rejects_non_frozen_simulator_arguments(tmp_path) -> None:
    from sts_combat_rl.commands.non_combat_learning import main

    output = tmp_path / "preflight.json"
    assert (
        main(
            [
                "preflight",
                "--output",
                str(output),
                "--sim-seed",
                "2",
            ]
        )
        == 1
    )
    assert not output.exists()


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


def test_evaluate_preceding_training_manifest_requires_both_checkpoints(
    tmp_path,
) -> None:
    from sts_combat_rl.commands.non_combat_learning import (
        _require_preceding_manifests,
        build_parser,
    )

    preflight = tmp_path / "preflight.json"
    target = tmp_path / "targets.json"
    checkpoint_directory = tmp_path / "checkpoints"
    checkpoint_directory.mkdir()
    preflight.write_text("{}", encoding="utf-8")
    target.write_text("{}", encoding="utf-8")
    checkpoint_one = checkpoint_directory / "model-653001.pt"
    checkpoint_two = checkpoint_directory / "model-653002.pt"
    checkpoint_one.write_bytes(b"checkpoint-one")
    checkpoint_two.write_bytes(b"checkpoint-two")

    def make_manifest(path: Path, artifacts: dict[str, Path], stage: str) -> Path:
        write_t065_manifest(
            path,
            approved_spec_commit=T065_APPROVED_SPEC_COMMIT,
            simulator_identity={},
            artifacts=artifacts,
            regeneration_commands=("wsl reproduction",),
            stage_evidence={stage: {"status": "completed"}},
        )
        return path

    preflight_manifest = make_manifest(
        tmp_path / "preflight.retention.json",
        {"preflight": preflight},
        "stage0-preflight",
    )
    target_manifest = make_manifest(
        tmp_path / "target.retention.json",
        {"target": target},
        "stage2-counterfactual-targets",
    )
    train_manifest = make_manifest(
        tmp_path / "train.retention.json",
        {
            "checkpoint_653001": checkpoint_one,
            "checkpoint_653002": checkpoint_two,
        },
        "stage4-training",
    )
    args = build_parser().parse_args(
        [
            "evaluate",
            "--target-table",
            str(target),
            "--checkpoint-directory",
            str(checkpoint_directory),
            "--output",
            str(tmp_path / "evaluate.json"),
            "--preflight",
            str(preflight),
            "--preceding-manifest",
            str(preflight_manifest),
            "--preceding-manifest",
            str(target_manifest),
            "--preceding-manifest",
            str(train_manifest),
        ]
    )
    _require_preceding_manifests(args)
    assert args._preceding_manifest_identities["stage4_training"]["size_bytes"]

    train_payload = json.loads(train_manifest.read_text(encoding="utf-8"))
    train_payload["artifacts"] = [
        artifact
        for artifact in train_payload["artifacts"]
        if artifact["role"] == "checkpoint_653001"
    ]
    train_payload["stage_evidence"]["stage4-training"]["artifact_roles"] = [
        "checkpoint_653001"
    ]
    train_manifest.write_text(json.dumps(train_payload), encoding="utf-8")
    with pytest.raises(T065CaseD, match="path/hash/size/seed identity"):
        _require_preceding_manifests(args)


def test_retention_reader_rejects_corrupt_entries_and_unknown_stage_roles(
    tmp_path,
) -> None:
    from sts_combat_rl.commands.non_combat_learning import _read_retention_manifest

    artifact = tmp_path / "artifact.json"
    manifest_path = tmp_path / "retention.json"

    def write_manifest() -> dict:
        artifact.write_text("{}", encoding="utf-8")
        return write_t065_manifest(
            manifest_path,
            approved_spec_commit=T065_APPROVED_SPEC_COMMIT,
            simulator_identity={},
            artifacts={"current_output": artifact},
            regeneration_commands=("wsl reproduction",),
            stage_evidence={"stage0-preflight": {"status": "completed"}},
        )

    for field, value in (
        ("role", ""),
        ("path", str(tmp_path / "missing.json")),
        ("sha256", "0" * 64),
        ("size_bytes", 999),
    ):
        manifest = write_manifest()
        manifest["artifacts"][0][field] = value
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        with pytest.raises(ValueError):
            _read_retention_manifest(manifest_path)

    manifest = write_manifest()
    manifest["stage_evidence"]["stage0-preflight"]["artifact_roles"] = [
        "not-an-artifact"
    ]
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="unknown artifact roles"):
        _read_retention_manifest(manifest_path)


def test_preflight_validator_requires_native_evidence_for_all_families(
    tmp_path,
) -> None:
    report = build_t065_preflight_report().to_dict()
    report["passed"] = True
    path = tmp_path / "preflight.json"
    path.write_text(json.dumps(report), encoding="utf-8")
    with pytest.raises(T065CaseD, match="mandatory-family evidence"):
        validate_t065_preflight(path)


def test_preflight_validator_rejects_tampered_native_probe_contract(tmp_path) -> None:
    from sts_combat_rl.sim import non_combat_learning as learning

    report = build_t065_preflight_report().to_dict()
    simulator = {
        "status": "passed",
        "execution_environment": "wsl",
        "python_interpreter": learning.T065_TRAINING_INTERPRETER,
        "native_build_pythonpath": learning.T065_LIGHTSPEED_BUILD_PYTHONPATH,
        "native_module": "slaythespire",
        "simulator_class": "StepSimulator",
        "player_class": "IRONCLAD",
        "ascension": 20,
        "simulator_seed": 1,
        "simulator_identity": dict(report["simulator_identity"]),
        "checkpoint_restore": True,
        "public_projection": True,
        "decision_context_schema_id": "public-run-context-v1",
        "observed_screen": "MAP_SCREEN",
        "checkpoint_restores": 1,
        "nodes_examined": 1,
        "checkpoint_restore_equal": True,
        "probe_max_steps": T065_NATIVE_PROBE_MAX_STEPS,
        "probe_strategy": "execute_controlled_run_before_decision_observer",
        "battle_controller_name": learning.T065_FROZEN_BATTLE_CONTROLLER_NAME,
        "non_combat_driver_seed": learning.T065_SOURCE_DRIVER_SEED,
        "mandatory_families": {},
    }
    for family in T065_MANDATORY_FAMILIES:
        simulator["mandatory_families"][family] = {
            "status": "passed",
            "screen_family": family,
            "projection_schema_id": learning.NATIVE_PUBLIC_PROJECTION_SCHEMA_ID,
            "projection_digest": "a" * 64,
            "action_identity_digest": "b" * 64,
            "state_feature_digest": "c" * 64,
            "action_feature_digest": "d" * 64,
            "public_context_digest": "e" * 64,
            "decision_context_schema_id": "public-run-context-v1",
            "state_feature_size": 4737,
            "action_feature_size": 92,
            "decision_context_screen": family,
            "projection_screen_identity": family,
            "action_count": 1,
        }
    simulator["evidence_digest"] = learning._preflight_evidence_digest(simulator)
    report["runtime_checks"]["simulator_runtime"] = simulator
    report["passed"] = True

    for key, tampered_value in (
        ("probe_max_steps", T065_NATIVE_PROBE_MAX_STEPS - 1),
        ("probe_strategy", "synthetic_frontier"),
        ("battle_controller_name", "unfrozen_controller"),
        ("non_combat_driver_seed", 654002),
    ):
        tampered = json.loads(json.dumps(report))
        tampered["runtime_checks"]["simulator_runtime"][key] = tampered_value
        tampered["runtime_checks"]["simulator_runtime"]["evidence_digest"] = (
            learning._preflight_evidence_digest(
                tampered["runtime_checks"]["simulator_runtime"]
            )
        )
        path = tmp_path / f"tampered-{key}.json"
        path.write_text(json.dumps(tampered), encoding="utf-8")
        with pytest.raises(T065CaseD, match="simulator runtime evidence is not frozen"):
            validate_t065_preflight(path)


def test_runtime_family_probe_rejects_projectionless_synthetic_context(
    monkeypatch,
) -> None:
    from sts_combat_rl.sim import non_combat_learning as learning

    class Adapter:
        supports_checkpoint_restore = True
        checkpoint_fingerprint_transition_only_raw_keys = frozenset(
            {"completed_battle_outcome"}
        )

        def checkpoint_fingerprint(self, snapshot):
            return (
                tuple(snapshot.observation),
                {
                    key: value
                    for key, value in snapshot.raw.items()
                    if key not in self.checkpoint_fingerprint_transition_only_raw_keys
                },
            )

        def reset(self, seed=None):
            del seed
            return snapshot

        def capture_checkpoint(self, snapshot):
            return SimulatorCheckpoint("fixture", "checkpoint", snapshot)

        def restore_checkpoint(self, checkpoint):
            return checkpoint.payload

        def legal_actions(self, snapshot):
            del snapshot
            return [SimulatorAction(action_id="map", label="map", kind="map")]

        def step(self, action):  # pragma: no cover - projection check stops first
            del action
            raise AssertionError("projectionless probe must fail before stepping")

    monkeypatch.setattr(learning, "read_native_public_projection", lambda *_: None)
    snapshot = SimulatorSnapshot(
        observation=(), raw={"screen_state": "MAP_SCREEN", "battle_active": False}
    )
    with pytest.raises(ValueError, match="native public projection"):
        learning._probe_native_mandatory_families(Adapter(), snapshot)


def test_runtime_family_probe_rejects_undeclared_fingerprint_boundary() -> None:
    from sts_combat_rl.sim import non_combat_learning as learning

    snapshot = SimulatorSnapshot(
        observation=(0,), raw={"screen_state": "MAP_SCREEN", "battle_active": False}
    )

    class Adapter:
        supports_checkpoint_restore = True

    with pytest.raises(ValueError, match="transition-only boundary"):
        learning._probe_native_mandatory_families(Adapter(), snapshot)


def test_runtime_family_probe_proves_all_native_families_and_feature_shapes() -> None:
    from sts_combat_rl.sim import non_combat_learning as learning
    from sts_combat_rl.sim.native_public_projection import (
        NATIVE_PUBLIC_PROJECTION_EXTERNAL_BASE_COMMIT,
        NATIVE_PUBLIC_PROJECTION_PATCH_ID,
        NATIVE_PUBLIC_PROJECTION_SCHEMA_ID,
        parse_native_public_projection,
    )

    class Adapter:
        supports_checkpoint_restore = True
        checkpoint_fingerprint_transition_only_raw_keys = frozenset(
            {"completed_battle_outcome"}
        )

        def __init__(self) -> None:
            self.index = 0

        def reset(self, seed=None):
            del seed
            self.index = 0
            return self._snapshot()

        def _snapshot(self):
            family_index = min(self.index, len(T065_MANDATORY_FAMILIES) - 1)
            family = T065_MANDATORY_FAMILIES[family_index]
            return SimulatorSnapshot(
                observation=(family_index,),
                raw={
                    "screen_state": family,
                    "battle_active": False,
                    "act": 1,
                    "floor_num": family_index + 1,
                    "room_type": family,
                    "cur_hp": 80,
                    "max_hp": 80,
                    "gold": 100,
                    "potion_count": 1,
                    "potion_capacity": 3,
                },
            )

        def legal_actions(self, snapshot):
            family = str(snapshot.raw["screen_state"])
            return [
                SimulatorAction(
                    action_id=f"game:{index}",
                    label=f"{family} action {index}",
                    kind="game_unknown",
                    raw={
                        "scope": "game",
                        "bits": index,
                        "idx1": 0,
                        "idx2": 0,
                        "idx3": 0,
                    },
                )
                for index in (1, 2)
            ]

        def capture_checkpoint(self, snapshot):
            return SimulatorCheckpoint("fixture", str(self.index), self.index)

        def checkpoint_fingerprint(self, snapshot):
            return (
                tuple(snapshot.observation),
                {
                    key: value
                    for key, value in snapshot.raw.items()
                    if key not in self.checkpoint_fingerprint_transition_only_raw_keys
                },
            )

        def restore_checkpoint(self, checkpoint):
            self.index = int(checkpoint.payload)
            return self._snapshot()

        def public_projection(self, snapshot):
            resources = {
                name: {"availability": "unavailable", "reason": "fixture"}
                for name in (
                    "deck",
                    "relics",
                    "potion_identities",
                    "keys",
                )
            }
            resources.update(
                {
                    name: {
                        "availability": "available",
                        "source": "fixture",
                        "value": value,
                    }
                    for name, value in {
                        "current_hp": 80,
                        "max_hp": 80,
                        "gold": 100,
                        "potion_count": 1,
                        "potion_capacity": 3,
                    }.items()
                }
            )
            actions = self.legal_actions(snapshot)
            native_actions = [
                SimulatorAction(
                    action_id=f"{action.raw['scope']}:{action.raw['bits']}",
                    label=action.label,
                    kind=action.kind,
                    raw=action.raw,
                )
                for action in actions
            ]
            assert action_identity_dicts_for_actions(actions) == (
                action_identity_dicts_for_actions(native_actions)
            )
            return parse_native_public_projection(
                {
                    "schema_id": NATIVE_PUBLIC_PROJECTION_SCHEMA_ID,
                    "external_base_commit": NATIVE_PUBLIC_PROJECTION_EXTERNAL_BASE_COMMIT,
                    "patch_identity": NATIVE_PUBLIC_PROJECTION_PATCH_ID,
                    "screen_identity": {
                        "availability": "available",
                        "source": "fixture",
                        "value": snapshot.raw["screen_state"],
                    },
                    "visible_act_boss": {
                        "availability": "unavailable",
                        "reason": "fixture",
                    },
                    "visible_map_graph": {
                        "availability": "unavailable",
                        "reason": "fixture",
                    },
                    "current_map_node": {
                        "availability": "unavailable",
                        "reason": "fixture",
                    },
                    "immediately_legal_routes": {
                        "availability": "unavailable",
                        "reason": "fixture",
                    },
                    "persistent_resources": {
                        "availability": "available",
                        "source": "fixture",
                        "value": resources,
                    },
                    "screen_payload": {
                        "availability": "unsupported",
                        "reason": "fixture",
                    },
                    "candidate_actions": {
                        "availability": "available",
                        "source": "fixture",
                        "value": [
                            {
                                "scope": str(action.raw["scope"]),
                                "bits": int(action.raw["bits"]),
                                "kind": action.kind,
                                "label": action.label,
                                "idx1": int(action.raw["idx1"]),
                                "idx2": int(action.raw["idx2"]),
                                "idx3": int(action.raw["idx3"]),
                            }
                            for action in actions
                        ],
                    },
                }
            )

        def step(self, action):
            del action
            self.index += 1
            return SimulatorTransition(
                snapshot=self._snapshot(),
                terminal=self.index >= len(T065_MANDATORY_FAMILIES),
            )

    adapter = Adapter()
    evidence, probe = learning._probe_native_mandatory_families(
        adapter, adapter.reset(seed=1)
    )
    assert set(evidence) == set(T065_MANDATORY_FAMILIES)
    assert probe["checkpoint_restore_equal"] is True
    assert all(
        item["state_feature_size"] == 4737
        and item["action_feature_size"] == 92
        and item["decision_context_screen"] == item["projection_screen_identity"]
        for item in evidence.values()
    )


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


def test_legacy_v1_terminal_report_round_trips_without_optional_details(
    tmp_path,
) -> None:
    legacy_path = tmp_path / "legacy-decision.json"
    round_trip_path = tmp_path / "round-trip-decision.json"
    legacy_report = T065CaseD(
        "source-selection",
        ["legacy source failure"],
        failure_ids=("legacy:source:1",),
        failure_counts={"failure_count": 1},
        simulator_identity={"integration_commit": "fixture"},
    ).to_decision_report()
    assert legacy_report["schema_id"] == "t065-terminal-decision-report-v1"
    assert legacy_report["schema_version"] == 1
    assert "failure_details" not in legacy_report
    assert "failure_detail_counts" not in legacy_report

    legacy_path.write_text(json.dumps(legacy_report), encoding="utf-8")
    loaded_report = json.loads(legacy_path.read_text(encoding="utf-8"))
    round_trip = write_t065_terminal_decision_report(
        round_trip_path, report=loaded_report
    )
    assert round_trip == legacy_report
    assert json.loads(round_trip_path.read_text(encoding="utf-8")) == legacy_report


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
    source_fixture = tmp_path / "source.fixture.jsonl"
    target_fixture = tmp_path / "target.fixture.json"
    source_fixture.write_text("focused fixture source\n", encoding="utf-8")
    target_fixture.write_text("focused fixture target\n", encoding="utf-8")
    source_identity = {
        "path": str(source_fixture),
        "sha256": file_sha256(source_fixture),
        "size_bytes": source_fixture.stat().st_size,
        "record_count": len(states),
    }
    target_identity = {
        "path": str(target_fixture),
        "sha256": file_sha256(target_fixture),
        "size_bytes": target_fixture.stat().st_size,
        "record_count": len(targets),
    }
    runs = train_frozen_model_seeds(
        states=states,
        targets=targets,
        source_artifact_identity=source_identity,
        target_artifact_identity=target_identity,
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


def test_checkpoint_training_rejects_empty_artifact_identity() -> None:
    with pytest.raises(ValueError, match="artifact_identity.*empty"):
        train_frozen_model_seeds(
            states=(),
            targets=(),
            source_artifact_identity={},
            target_artifact_identity={},
        )


def test_checkpoint_selection_rejects_incomplete_metadata() -> None:
    from sts_combat_rl.sim.non_combat_learning import select_validation_checkpoint

    runs = (
        SimpleNamespace(model_seed=653001, validation_mae=1.0, metadata={}),
        SimpleNamespace(model_seed=653002, validation_mae=2.0, metadata={}),
    )
    with pytest.raises(ValueError, match="artifact_identity"):
        select_validation_checkpoint(runs)


def test_t075_global_ownership_preserves_exact_family_split_quotas() -> None:
    candidates = []
    split_ranges = {
        "train": range(650001, 650049),
        "validation": range(650155, 650171),
        "heldout": range(650206, 650222),
    }
    for family in T065_MANDATORY_FAMILIES:
        for split, seeds in split_ranges.items():
            for offset, seed in enumerate(seeds):
                candidates.append(
                    SimpleNamespace(
                        family=family,
                        split=split,
                        simulator_seed=seed,
                        source_arm="stochastic_non_combat_v1",
                        source_run_id=f"stochastic_non_combat_v1:{seed}",
                        source_step_index=offset,
                        public_state_identity=f"{family}:{split}:{offset}",
                        legal_action_identities=({"action_id": f"a:{offset}"},),
                        action_trace=(),
                        terminal=True,
                    )
                )
    selected, audit = select_t075_source_candidates(candidates)
    assert len(selected) == 320
    assert audit["excluded_non_owner_count"] == 0
    assert all(
        sum(
            1
            for candidate, _digest, _payload in selected
            if candidate.family == family and candidate.split == split
        )
        == (48 if split == "train" else 16)
        for family in T065_MANDATORY_FAMILIES
        for split in ("train", "validation", "heldout")
    )


def test_t075_process_shard_plan_rejects_non_matching_worker_count() -> None:
    from sts_combat_rl.sim.non_combat_learning import (
        generate_counterfactual_targets_process_sharded,
    )

    with pytest.raises(ValueError, match="worker count must equal shard count"):
        generate_counterfactual_targets_process_sharded(
            (),
            shard_specs=(
                {
                    "shard_index": 0,
                    "selected_state_start": 0,
                    "selected_state_end": -1,
                },
            ),
            worker_count=2,
            output_directory=Path("unused"),
        )


def test_t075_process_shard_plan_rejects_non_frozen_full_plan() -> None:
    from sts_combat_rl.sim.non_combat_learning import (
        generate_counterfactual_targets_process_sharded,
    )

    with pytest.raises(T065CaseD, match="frozen 16x20"):
        generate_counterfactual_targets_process_sharded(
            (),
            shard_specs=(
                {
                    "shard_index": 0,
                    "selected_state_start": 0,
                    "selected_state_end": 19,
                },
                {
                    "shard_index": 1,
                    "selected_state_start": 20,
                    "selected_state_end": 39,
                },
            ),
            worker_count=2,
            output_directory=Path("unused"),
            require_frozen_shards=True,
        )


def test_t075_portable_path_converts_wsl_mount() -> None:
    assert _portable_path("/mnt/d/DeadlycatCoding/STSRL/artifacts/x.json") == Path(
        "D:/DeadlycatCoding/STSRL/artifacts/x.json"
    )


def test_t075_artifact_path_normalization_rejects_parent_segments() -> None:
    with pytest.raises(ValueError, match=r"contains \.\."):
        _portable_path("/mnt/d/DeadlycatCoding/STSRL/artifacts/../secret.json")
    assert not _t075_path_matches(
        "artifacts/../t075-learned-non-combat-policy-v1/report.json",
        "artifacts/t075-learned-non-combat-policy-repair/report.json",
    )

    assert not _t075_path_matches(
        "D:/DeadlycatCoding/STSRL/artifacts/../outside/report.json",
        "D:/DeadlycatCoding/STSRL/artifacts/outside/report.json",
    )


def test_t075_preceding_manifest_cli_value_is_normalized_to_one_path(tmp_path) -> None:
    from sts_combat_rl.commands.non_combat_learning import build_parser

    manifest = tmp_path / "stage1.retention.json"
    args = build_parser().parse_args(
        [
            "target",
            "--states",
            str(tmp_path / "states.jsonl"),
            "--output",
            str(tmp_path / "targets.json"),
            "--preflight",
            str(tmp_path / "preflight.json"),
            "--preceding-manifest",
            str(manifest),
        ]
    )
    assert _t075_preceding_manifest_path(args, stage="stage2-target") == manifest
    args.preceding_manifest = [manifest, tmp_path / "other.retention.json"]
    with pytest.raises(T065CaseD, match="exactly one"):
        _t075_preceding_manifest_path(args, stage="stage2-target")


def test_t075_stage3_target_completeness_uses_exact_expected_keys() -> None:
    states = [
        SimpleNamespace(selected_state_index=0, eligible_action_indices=(0, 1)),
        SimpleNamespace(selected_state_index=1, eligible_action_indices=(0, 1)),
    ]
    targets = [
        SimpleNamespace(selected_state_index=0, legal_action_index=0),
        SimpleNamespace(selected_state_index=1, legal_action_index=0),
        SimpleNamespace(selected_state_index=1, legal_action_index=1),
        SimpleNamespace(selected_state_index=2, legal_action_index=0),
    ]

    result = _t075_target_row_completeness(states, targets)

    assert result["expected_row_count"] == 4
    assert result["actual_row_count"] == 4
    assert result["missing_row_count"] == 1
    assert result["unexpected_row_count"] == 1
    assert result["duplicate_row_count"] == 0
    assert result["complete"] is False


def test_t075_retention_does_not_synthesize_completed_failure(tmp_path) -> None:
    artifact = tmp_path / "report.json"
    artifact.write_text("{}\n", encoding="utf-8")
    retention = tmp_path / "failed.retention.json"
    args = SimpleNamespace(
        retention_manifest=retention,
        _command_argv=(),
        code_head="test-head",
    )
    value = _write_t075_stage_retention(
        args,
        stage="stage5-gate",
        artifacts={"stage5_report": artifact},
        evidence={
            "executed": True,
            "status": "failed",
            "terminal": False,
            "problems": ["gate failed"],
        },
        terminal_case="C",
    )
    assert value["stage_commands"]["stage5-gate"]["status"] == "failed"
    assert value["stage_commands"]["stage5-gate"]["terminal"] is False
    assert value["stage_commands"]["stage5-gate"]["command"]
    assert value["stage_commands"]["stage5-gate"]["start_time_utc"]
    assert value["stage_commands"]["stage5-gate"]["end_time_utc"]
    assert value["stage_commands"]["stage5-gate"]["exit_code"] == 1
    assert (
        value["stage_commands"]["stage5-gate"]["command"]
        == value["stage_evidence"]["stage5-gate"]["command"]
    )
    assert value["stage_evidence"]["stage5-gate"]["problems"] == ["gate failed"]


def test_t075_stage3_reader_failure_is_materialized_as_failed_report(
    tmp_path, monkeypatch
) -> None:
    import sts_combat_rl.commands.non_combat_learning as command_module

    table_path = tmp_path / "target.json"
    states_path = tmp_path / "states.jsonl"
    selection_path = tmp_path / "selection.json"
    preflight_path = tmp_path / "preflight.json"
    report_path = tmp_path / "validation.json"
    for path in (table_path, states_path, selection_path, preflight_path):
        path.write_text("{}\n", encoding="utf-8")
    monkeypatch.setattr(
        command_module,
        "read_target_table",
        lambda _path: (_ for _ in ()).throw(ValueError("tampered target")),
    )
    args = SimpleNamespace(
        validation_report=report_path,
        preflight=preflight_path,
        preceding_manifest=tmp_path / "stage1.retention.json",
        code_head="test-head",
    )
    with pytest.raises(Exception, match="strict target reader"):
        _t075_write_stage3_report(args, table_path, states_path, selection_path)
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["passed"] is False
    assert report["checks"]["strict_target_reader"]["status"] == "failed"
    assert all(
        report["checks"][name]["status"] == expected_status
        for name, expected_status in (
            ("target_completeness", "failed"),
            ("simulator_and_preflight_lineage", "failed"),
            ("model_input_schema", "not_run"),
            ("state_action_dimensions", "not_run"),
            ("finite_numeric_values", "not_run"),
            ("legal_action_order", "not_run"),
            ("continuation_seed_contract", "not_run"),
            ("public_input_firewall", "not_run"),
        )
    )
    assert report["violation_counts"]["missing_target_rows"] == 1
    assert report["violation_counts"]["firewall_violations"] == 0


def test_t075_selection_and_stage3_share_pinned_simulator_identity() -> None:
    import sts_combat_rl.commands.non_combat_learning as command_module

    identity = _t075_pinned_simulator_identity()
    assert identity == command_module._t075_pinned_simulator_identity()
    assert identity == command_module.lightspeed_source_identity_dict()
    tampered = dict(identity)
    tampered["integration_commit"] = "not-pinned"
    assert tampered != identity
    with pytest.raises(ValueError, match="pinned identity"):
        _t075_require_pinned_simulator_identity(tampered, label="selection")


def test_t075_selection_invokes_strict_reuse_resolver(tmp_path, monkeypatch) -> None:
    import sts_combat_rl.commands.non_combat_learning as command_module

    called = []

    def resolve(path, source_paths):
        called.append((path, tuple(source_paths)))
        raise T075WorkflowError("source-input-reuse", ["fabricated reuse rejected"])

    monkeypatch.setattr(command_module, "_validate_t075_preflight", lambda _path: {})
    monkeypatch.setattr(command_module, "_t075_resolve_reuse_manifest", resolve)
    args = SimpleNamespace(
        decision_report=None,
        selection_strategy=command_module.T075_SELECTION_STRATEGY_ID,
        replay_shard_count=16,
        replay_worker_count=16,
        replay_verify=True,
        preflight=tmp_path / "preflight.json",
        reuse_manifest=tmp_path / "reuse.json",
        input=(tmp_path / "stochastic.json", tmp_path / "expert.json"),
    )
    with pytest.raises(T075WorkflowError, match="fabricated reuse rejected"):
        _run_t075_select(args)
    assert called == [(args.reuse_manifest, args.input)]


def test_t075_reuse_resolver_rejects_fabricated_new_source(tmp_path) -> None:
    reuse = tmp_path / "reuse.json"
    import sts_combat_rl.commands.non_combat_learning as command_module

    reuse.write_text(
        json.dumps(
            {
                "schema_id": command_module.T075_REUSE_MANIFEST_SCHEMA_ID,
                "schema_version": 1,
                "task_id": command_module.T075_TASK_ID,
                "approved_t075_spec_commit": command_module.T075_APPROVED_SPEC_COMMIT,
                "planner_baseline": command_module.T075_PLANNER_BASELINE,
                "code_head": "real-head",
                "pinned_simulator_identity": _t075_pinned_simulator_identity(),
                "accepted_t065_preflight_content_sha256": "a89560d037ea4555922d0e1282edb8e328ce75ab6e1d720fd05f86022b56c334",
                "accepted_t065_case_d": {},
                "sources": [],
                "validation": {
                    "status": "passed",
                    "raw_metadata_validated": True,
                    "source_count": 2,
                    "source_arms": [
                        "stochastic_non_combat_v1",
                        "expert_non_combat_v1",
                    ],
                    "source_recollection_prohibited": True,
                },
                "original_regeneration_commands": [],
                "problems": [],
            }
        ),
        encoding="utf-8",
    )
    source = tmp_path / "new-source.json"
    source.write_text("{}\n", encoding="utf-8")
    with pytest.raises(T075WorkflowError, match="not an exact frozen input"):
        _t075_resolve_reuse_manifest(reuse, (source, source))


def test_t075_stage3_missing_target_still_materializes_failed_report(tmp_path) -> None:
    import sts_combat_rl.commands.non_combat_learning as command_module

    table_path = tmp_path / "missing-target.json"
    states_path = tmp_path / "states.jsonl"
    selection_path = tmp_path / "selection.json"
    preflight_path = tmp_path / "preflight.json"
    report_path = tmp_path / "validation.json"
    for path in (states_path, selection_path, preflight_path):
        path.write_text("{}\n", encoding="utf-8")
    args = SimpleNamespace(
        validation_report=report_path,
        preflight=preflight_path,
        preceding_manifest=tmp_path / "stage1.retention.json",
        code_head="test-head",
    )
    with pytest.raises(Exception, match="strict target reader"):
        command_module._t075_write_stage3_report(
            args, table_path, states_path, selection_path
        )
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["parent_target_table_sha256"] is None
    assert report["checks"]["strict_target_reader"]["status"] == "failed"
    assert report["checks"]["finite_numeric_values"]["status"] == "not_run"
    assert report["checks"]["public_input_firewall"]["status"] == "not_run"
    assert report["violation_counts"]["firewall_violations"] == 0


def test_t075_first_terminal_decision_wins(tmp_path) -> None:
    decision_path = tmp_path / "terminal-decision-report.json"
    original = {
        "schema_id": "t075-terminal-decision-report-v1",
        "schema_version": 1,
        "terminal_case": "D",
        "marker": "first",
    }
    decision_path.write_text(json.dumps(original), encoding="utf-8")
    args = SimpleNamespace(
        decision_report=decision_path,
        retention_manifest=tmp_path / "retention.json",
    )
    _handle_t075_case_d(
        args,
        T075WorkflowError("stage1-selection-replay", ["later failure"]),
    )
    assert json.loads(decision_path.read_text(encoding="utf-8")) == original


def test_t075_t065_failure_is_routed_to_t075_case_d(monkeypatch, tmp_path) -> None:
    import sts_combat_rl.commands.non_combat_learning as command_module

    routed = []

    def fail(_args):
        raise T065CaseD("target-sharding", ["worker crashed"])

    monkeypatch.setattr(command_module, "_run_t075_target", fail)
    monkeypatch.setattr(
        command_module,
        "_handle_t075_case_d",
        lambda _args, failure: routed.append(failure),
    )
    monkeypatch.setattr(
        command_module,
        "_handle_case_d",
        lambda *_args: pytest.fail("T075 failure entered the legacy handler"),
    )
    result = command_module.main(
        [
            "target",
            "--states",
            str(tmp_path / "states.jsonl"),
            "--output",
            str(tmp_path / "target.json"),
            "--preflight",
            str(tmp_path / "preflight.json"),
            "--selection-manifest",
            str(tmp_path / "selection.json"),
        ]
    )
    assert result == 1
    assert len(routed) == 1
    assert isinstance(routed[0], T075WorkflowError)


def test_t075_unexpected_worker_exception_is_routed_to_t075_case_d(
    monkeypatch, tmp_path
) -> None:
    import sts_combat_rl.commands.non_combat_learning as command_module

    routed = []

    def fail(_args):
        raise TypeError("worker payload was malformed")

    monkeypatch.setattr(command_module, "_run_t075_target", fail)
    monkeypatch.setattr(
        command_module,
        "_handle_t075_case_d",
        lambda _args, failure: routed.append(failure),
    )
    result = command_module.main(
        [
            "target",
            "--states",
            str(tmp_path / "states.jsonl"),
            "--output",
            str(tmp_path / "target.json"),
            "--preflight",
            str(tmp_path / "preflight.json"),
            "--selection-manifest",
            str(tmp_path / "selection.json"),
        ]
    )
    assert result == 1
    assert len(routed) == 1
    assert isinstance(routed[0], T075WorkflowError)
    assert "malformed" in routed[0].problems[0]


def test_t075_finalize_rejects_fabricated_case_d_reachability(tmp_path) -> None:
    artifact_root = tmp_path / "artifacts"
    left = artifact_root / "left" / "report.json"
    right = artifact_root / "right" / "report.json"
    left.parent.mkdir(parents=True)
    right.parent.mkdir(parents=True)
    left.write_text("left\n", encoding="utf-8")
    right.write_text("right\n", encoding="utf-8")
    decision_path = artifact_root / "terminal-decision-report.json"
    decision = {
        "schema_id": "t075-terminal-decision-report-v1",
        "schema_version": 1,
        "task_id": "T075",
        "approved_t075_spec_commit": "e204c5d28cc0bee8013853e8680e8966f5c930a8",
        "planner_baseline": "95ccb6b55bc7a0214b632206ae169a533289fcf2",
        "code_head": "test-head",
        "terminal_case": "D",
        "terminal_stage": "stage0-reuse",
        "reason_code": "test",
        "summary": "test",
        "reached_stages": [],
        "skipped_stages": [
            "stage0-preflight",
            "stage0-reuse",
            "stage1-selection-replay",
            "stage2-target",
            "stage4-train",
            "stage5-gate",
            "stage6-eval",
        ],
        "parent_artifact_identities": {},
        "stage3_validation_status": "not_reached",
        "stage5_gate_status": "not_reached",
        "stage6_status": "not_reached",
        "recommendation": "test",
        "problems": ["test"],
    }
    decision_path.write_text(json.dumps(decision), encoding="utf-8")
    retention_path = artifact_root / "t075-retention-manifest.json"
    args = SimpleNamespace(
        artifact_root=artifact_root,
        decision_report=decision_path,
        retention_manifest=retention_path,
        _command_argv=(),
        code_head="test-head",
    )
    with pytest.raises(Exception, match="code_head|terminal prefix|reachability"):
        _run_t075_finalize(args)
    assert not retention_path.exists()
