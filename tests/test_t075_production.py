"""Production-boundary checks for T075-derived T065 evidence classification."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from sts_combat_rl.sim import non_combat_acceptance as acceptance

RUN_HEAD = "1" * 40
HELDOUT_FAMILIES = (
    "MAP_SCREEN",
    "REST_ROOM",
    "REWARDS",
    "TREASURE_ROOM",
)


def _identity(role: str, filename: str) -> acceptance.ArtifactIdentity:
    return acceptance.ArtifactIdentity(
        role=role,
        path=f"artifacts/t075-fixture/{filename}",
        sha256="a" * 64,
        size_bytes=1,
    )


def _checkpoint_identity(payload: bytes, model_seed: int) -> dict[str, Any]:
    return {
        "role": "checkpoint",
        "path": (
            "artifacts/t075-leakage-safe-non-combat-cohort-repair/"
            f"checkpoints/{model_seed}.pt"
        ),
        "sha256": hashlib.sha256(payload).hexdigest(),
        "size_bytes": len(payload),
    }


def _training_selection(
    checkpoint_payloads: tuple[bytes, bytes],
    *,
    validation_mae: tuple[float, float] = (0.25, 0.5),
    selected_model_seed: int = 653001,
) -> dict[str, Any]:
    checkpoints = [
        _checkpoint_identity(payload, model_seed)
        for payload, model_seed in zip(checkpoint_payloads, (653001, 653002))
    ]
    return {
        "schema_id": "t075-training-selection-v1",
        "schema_version": 1,
        "task_id": "T075",
        "run_head": RUN_HEAD,
        "model_seeds": [653001, 653002],
        "checkpoints": checkpoints,
        "validation_mae": list(validation_mae),
        "selected_model_seed": selected_model_seed,
        "selected_checkpoint": checkpoints[0]
        if selected_model_seed == 653001
        else checkpoints[1],
    }


def _patch_stage_capture(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    calls: list[dict[str, Any]] = []

    def capture(state, repository_root, **kwargs):
        del state, repository_root
        calls.append(kwargs)
        return kwargs

    monkeypatch.setattr(acceptance, "_stage_payload_outcome", capture)
    monkeypatch.setattr(
        acceptance,
        "_committed_output",
        lambda _state, role, filename: _identity(role, filename),
    )
    monkeypatch.setattr(
        acceptance,
        "_selected_training_checkpoint",
        lambda _state, _root: (
            _identity("training_selection", "training-selection.json"),
            _identity("checkpoint", "checkpoints/653001.pt"),
        ),
    )
    return calls


def _json_payload(value: dict[str, Any]) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode(
        "utf-8"
    )


def _heldout_row(
    *,
    index: int,
    family: str,
    model_seed: int,
    positive: bool,
) -> dict[str, Any]:
    if positive:
        empirical_values = {"0": 1.0, "1": 2.0}
        model_action_index = 1
        model_q_floor = 2.0
        expert_q_floor = 1.0
        delta = 1.0
    else:
        empirical_values = {"0": 1.0, "1": 0.0}
        model_action_index = 1
        model_q_floor = 0.0
        expert_q_floor = 1.0
        delta = -1.0
    return {
        "selected_state_index": index,
        "family": family,
        "split": "heldout",
        "source_behavior": "expert_non_combat_v1",
        "screen_state": "fixture",
        "source_act": 1.0,
        "source_floor": 1.0,
        "public_state_identity": f"fixture-state-{index}",
        "source_behavior_action_index": 0,
        "source_behavior_action_identity": {"action_id": f"action:{index}:0"},
        "model_seed": model_seed,
        "model_action_index": model_action_index,
        "model_action_identity": {"action_id": f"action:{index}:1"},
        "expert_action_index": 0,
        "expert_action_identity": {"action_id": f"action:{index}:0"},
        "model_q_floor": model_q_floor,
        "expert_q_floor": expert_q_floor,
        "delta": delta,
        "predicted_action_values": {"0": 0.1, "1": 0.2},
        "empirical_best_action_indices": [1 if positive else 0],
        "empirical_action_values": empirical_values,
        "rank_correlation": 1.0,
    }


def _stage5_payload(*, positive: bool) -> bytes:
    rows_by_seed = {
        str(model_seed): [
            _heldout_row(
                index=256 + family_index * 16 + offset,
                family=family,
                model_seed=model_seed,
                positive=positive,
            )
            for family_index, family in enumerate(HELDOUT_FAMILIES)
            for offset in range(16)
        ]
        for model_seed in (653001, 653002)
    }
    if positive:
        aggregate = 1.0
        problems: list[str] = []
    else:
        aggregate = -1.0
        problems = [
            "aggregate mean delta is not positive",
            "median delta is negative",
            "fewer than three family mean deltas are non-negative",
            "Stage 5 bootstrap probability is below 0.90",
            "non-selected model seed has a negative aggregate delta",
        ]
    return _json_payload(
        {
            "schema_id": "t065-heldout-gate-report-v1",
            "schema_version": 1,
            "selected_model_seed": 653001,
            "selected_validation_mae": 0.5,
            "model_results": rows_by_seed,
            "aggregate_mean_delta": aggregate,
            "median_delta": aggregate,
            "family_mean_deltas": {family: aggregate for family in HELDOUT_FAMILIES},
            "p_positive": 1.0 if positive else 0.0,
            "non_selected_model_mean_delta": aggregate,
            "passed": positive,
            "problems": problems,
        }
    )


def _stage6_payload(*, positive: bool) -> bytes:
    delta = 1.0 if positive else -1.0
    return _json_payload(
        {
            "schema_id": "t065-complete-run-report-v1",
            "schema_version": 1,
            "paired_terminal_floor_deltas": [delta] * 256,
            "learned_terminal_floor_mean": 10.0 if positive else 9.0,
            "expert_terminal_floor_mean": 9.0 if positive else 10.0,
            "mean_terminal_floor_delta": delta,
            "p_positive": 1.0 if positive else 0.0,
            "coverage": {
                "D": 100,
                "L": 60,
                "M": 100,
                "F": 0,
                "learned_coverage": 0.6,
                "mandatory_failure_rate": 0.0,
                "passed": True,
            },
            "learned_act2_entry_count": 2 if positive else 1,
            "expert_act2_entry_count": 1,
            "controller_error_count": 0,
            "truncation_count": 0,
            "valid": True,
            "passed": positive,
            "problems": []
            if positive
            else ["one or more frozen Stage 6 gate conditions failed"],
            "execution_evidence": {},
        }
    )


def test_target_rejects_malformed_t065_payload_as_case_d(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = _patch_stage_capture(monkeypatch)
    state = acceptance.initial_acceptance_state(RUN_HEAD)

    acceptance.run_t075_target(state, b"{}", tmp_path, valid=True)

    assert calls[-1] == {
        "stage": "TARGET",
        "parents": (
            _identity("preflight_audit", "preflight-audit.json"),
            _identity("selected_states", "selected-states.jsonl"),
        ),
        "payloads": (),
        "valid": False,
        "passed": False,
        "failure_code": "TARGET_INVALID",
    }


def test_train_rejects_malformed_t065_checkpoint_as_case_d(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = _patch_stage_capture(monkeypatch)
    checkpoint_payloads = (b"not a T065 checkpoint", b"second checkpoint")
    state = acceptance.initial_acceptance_state(RUN_HEAD)

    acceptance.run_t075_train(
        state,
        checkpoint_payloads,
        _training_selection(checkpoint_payloads),
        tmp_path,
    )

    assert calls[-1] == {
        "stage": "TRAIN",
        "parents": (_identity("target_table", "target-table.json"),),
        "payloads": (),
        "valid": False,
        "passed": False,
        "failure_code": "TRAIN_INVALID",
    }


def test_train_rejects_selection_mae_disagreement_with_t065_checkpoints(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import sts_combat_rl.sim.non_combat_learning as t065

    calls = _patch_stage_capture(monkeypatch)
    checkpoint_payloads = (b"checkpoint 653001", b"checkpoint 653002")
    loaded_runs = (
        SimpleNamespace(
            model_seed=653001,
            validation_mae=0.25,
            checkpoint_artifact_id=hashlib.sha256(checkpoint_payloads[0]).hexdigest(),
        ),
        SimpleNamespace(
            model_seed=653002,
            validation_mae=0.5,
            checkpoint_artifact_id=hashlib.sha256(checkpoint_payloads[1]).hexdigest(),
        ),
    )
    loaded_payloads: list[bytes] = []
    selected_inputs: list[tuple[object, ...]] = []

    def fake_loader(path: Path) -> object:
        loaded_payloads.append(path.read_bytes())
        return loaded_runs[len(loaded_payloads) - 1]

    def fake_select(runs: object) -> object:
        selected_inputs.append(tuple(runs))
        return tuple(runs)[0]

    monkeypatch.setattr(t065, "load_non_combat_checkpoint", fake_loader)
    monkeypatch.setattr(t065, "select_validation_checkpoint", fake_select)
    selection = _training_selection(checkpoint_payloads, validation_mae=(9.0, 10.0))
    state = acceptance.initial_acceptance_state(RUN_HEAD)

    acceptance.run_t075_train(state, checkpoint_payloads, selection, tmp_path)

    assert loaded_payloads == list(checkpoint_payloads)
    assert selected_inputs == [loaded_runs]
    assert calls[-1]["valid"] is False
    assert calls[-1]["passed"] is False
    assert calls[-1]["failure_code"] == "TRAIN_INVALID"
    assert calls[-1]["payloads"] == ()


@pytest.mark.parametrize("operation", ["target", "gate", "eval"])
def test_invalid_adapter_cannot_classify_supplied_scientific_payload(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, operation: str
) -> None:
    calls = _patch_stage_capture(monkeypatch)
    state = acceptance.initial_acceptance_state(RUN_HEAD)
    payload = {
        "target": b"{}",
        "gate": _stage5_payload(positive=True),
        "eval": _stage6_payload(positive=True),
    }[operation]

    with pytest.raises(acceptance.T075OperationalError, match="scientific evidence"):
        if operation == "target":
            acceptance.run_t075_target(
                state,
                payload,
                tmp_path,
                valid=False,
                failure_code="TARGET_INVALID",
            )
        elif operation == "gate":
            acceptance.run_t075_gate(
                state,
                payload,
                tmp_path,
                passed=True,
                valid=False,
                failure_code="GATE_EVIDENCE_INVALID",
            )
        else:
            acceptance.run_t075_eval(
                state,
                payload,
                tmp_path,
                passed=True,
                valid=False,
                failure_code="EVAL_EVIDENCE_INVALID",
            )
    assert calls == []


@pytest.mark.parametrize("positive", [True, False])
def test_gate_derives_t065_pass_result_from_report(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, positive: bool
) -> None:
    calls = _patch_stage_capture(monkeypatch)
    state = acceptance.initial_acceptance_state(RUN_HEAD)

    acceptance.run_t075_gate(
        state,
        _stage5_payload(positive=positive),
        tmp_path,
        passed=not positive,
        valid=True,
    )

    assert calls[-1]["valid"] is True
    assert calls[-1]["passed"] is positive
    assert calls[-1]["failure_code"] is None


def test_gate_rejects_malformed_t065_report_as_case_d(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = _patch_stage_capture(monkeypatch)
    state = acceptance.initial_acceptance_state(RUN_HEAD)

    acceptance.run_t075_gate(state, b"{}", tmp_path, passed=True, valid=True)

    assert calls[-1]["valid"] is False
    assert calls[-1]["passed"] is False
    assert calls[-1]["failure_code"] == "GATE_EVIDENCE_INVALID"


@pytest.mark.parametrize("positive", [True, False])
def test_eval_derives_t065_pass_result_from_report(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, positive: bool
) -> None:
    calls = _patch_stage_capture(monkeypatch)
    state = acceptance.initial_acceptance_state(RUN_HEAD)

    acceptance.run_t075_eval(
        state,
        _stage6_payload(positive=positive),
        tmp_path,
        passed=not positive,
        valid=True,
    )

    assert calls[-1]["valid"] is True
    assert calls[-1]["passed"] is positive
    assert calls[-1]["failure_code"] is None


def test_eval_rejects_malformed_t065_report_as_case_d(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = _patch_stage_capture(monkeypatch)
    state = acceptance.initial_acceptance_state(RUN_HEAD)

    acceptance.run_t075_eval(state, b"{}", tmp_path, passed=True, valid=True)

    assert calls[-1]["valid"] is False
    assert calls[-1]["passed"] is False
    assert calls[-1]["failure_code"] == "EVAL_EVIDENCE_INVALID"
