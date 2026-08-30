from __future__ import annotations

import hashlib
from pathlib import Path
from types import SimpleNamespace

import pytest

from sts_combat_rl.commands.t077_continuation import (
    StageResult,
    T077ScientificFailure,
    run_t077_workflow,
)
from sts_combat_rl.sim.non_combat_acceptance import (
    T075_SOURCE_IDENTITIES,
    ArtifactIdentity,
)
from sts_combat_rl.sim.t077_continuation import (
    T077_ACCEPTED_T076_INTEGRATION,
    T077_EARLIEST_STAGE,
    artifact_identity,
    build_t077_continuation_plan,
    validate_selected_states_320,
    verify_t075_retained_inputs,
    verify_t076_source_manifest,
)


def test_t077_continuation_plan_binds_exact_retained_t075_inputs() -> None:
    plan = build_t077_continuation_plan("3690149970b342fab62bd67c564a84bbd293b134")

    assert plan.accepted_t076_integration == T077_ACCEPTED_T076_INTEGRATION
    assert plan.earliest_stage == T077_EARLIEST_STAGE
    assert tuple(identity.to_dict() for identity in plan.retained_t075_sources) == (
        T075_SOURCE_IDENTITIES
    )


def test_verify_t075_retained_inputs_checks_path_hash_and_size(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    payload = b"retained T075 input"
    artifact_path = tmp_path / "artifacts" / "t075" / "source.json"
    artifact_path.parent.mkdir(parents=True)
    artifact_path.write_bytes(payload)
    identity = ArtifactIdentity(
        role="current_output",
        path="artifacts/t075/source.json",
        sha256=hashlib.sha256(payload).hexdigest(),
        size_bytes=len(payload),
    )

    def reject_unbounded_read(_path: Path) -> bytes:
        raise AssertionError("retained inputs must be hashed by streaming reads")

    with monkeypatch.context() as patch_context:
        patch_context.setattr(Path, "read_bytes", reject_unbounded_read)
        assert verify_t075_retained_inputs(
            tmp_path, retained_t075_sources=(identity,)
        ) == (identity,)

    bad_identity = ArtifactIdentity(
        role="current_output",
        path="artifacts/t075/source.json",
        sha256="0" * 64,
        size_bytes=len(payload),
    )

    with pytest.raises(ValueError, match="identity mismatch"):
        verify_t075_retained_inputs(tmp_path, retained_t075_sources=(bad_identity,))


def test_selected_cohort_validation_is_streaming_and_exact(tmp_path: Path) -> None:
    families = ("MAP_SCREEN", "REST_ROOM", "REWARDS", "TREASURE_ROOM")

    def states(_path: Path):
        for index in range(320):
            offset = index % 80
            split = (
                "train" if offset < 48 else ("validation" if offset < 64 else "heldout")
            )
            yield SimpleNamespace(
                selected_state_index=index,
                family=families[index // 80],
                split=split,
                public_state_identity=f"state-{index}",
                legal_action_identities=({"stable_id": f"action-{index}"},),
            )

    summary = validate_selected_states_320(
        tmp_path / "selected.jsonl", state_iterator=states
    )

    assert summary["selected_state_count"] == 320
    assert summary["unique_replay_key_count"] == 320
    assert summary["counts_by_family_split"]["MAP_SCREEN"] == {
        "train": 48,
        "validation": 16,
        "heldout": 16,
    }


def test_source_manifest_binds_t076_integration() -> None:
    manifest = verify_t076_source_manifest(Path(__file__).parents[1])

    assert manifest["integration_commit"] == T077_ACCEPTED_T076_INTEGRATION
    assert manifest["integration_branch"] == "stsrl/main"


def test_callable_workflow_stops_at_valid_gate_failure_with_t077_lineage(
    tmp_path: Path,
) -> None:
    run_head = "1" * 40
    calls: list[str] = []
    artifact_root = tmp_path / "stable"

    def output(stage: str, role: str) -> StageResult:
        calls.append(stage)
        path = artifact_root / "artifacts" / "t077" / f"{stage}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f'{{"stage":"{stage}"}}\n', encoding="utf-8")
        return StageResult(outputs=(artifact_identity(path, artifact_root, role),))

    result = run_t077_workflow(
        tmp_path,
        run_head,
        artifact_repository_root=artifact_root,
        validate_checkout=False,
        reuse_verifier=lambda _root: {
            "selected_summary": {"selected_state_count": 320}
        },
        manifest_verifier=lambda _root: {
            "integration_commit": T077_ACCEPTED_T076_INTEGRATION
        },
        target_runner=lambda _root, _run_root: output("TARGET", "target_table"),
        train_runner=lambda _root, _run_root: output("TRAIN", "training_selection"),
        gate_runner=lambda _root, _run_root: StageResult(
            outputs=output("GATE", "stage5_report").outputs,
            passed=False,
        ),
        eval_runner=lambda _root, _run_root: pytest.fail("EVAL must be skipped"),
    )

    assert result["terminal_case"] == "C"
    assert result["terminal_stage"] == "GATE"
    assert calls == ["TARGET", "TRAIN", "GATE"]
    terminal = (
        artifact_root
        / "artifacts"
        / "t077-t075-same-experiment-continuation"
        / "terminal-decision.json"
    )
    retention = terminal.with_name("retention.json")
    assert '"terminal_case":"C"' in terminal.read_text(encoding="utf-8")
    assert '"retention_owner":"T077"' in retention.read_text(encoding="utf-8")


def test_target_scientific_failure_is_case_d_without_replacement(
    tmp_path: Path,
) -> None:
    result = run_t077_workflow(
        tmp_path,
        "2" * 40,
        validate_checkout=False,
        reuse_verifier=lambda _root: {
            "selected_summary": {"selected_state_count": 320}
        },
        manifest_verifier=lambda _root: {
            "integration_commit": T077_ACCEPTED_T076_INTEGRATION
        },
        target_runner=lambda _root, _run_root: (_ for _ in ()).throw(
            T077ScientificFailure("TARGET", ("state 67 restore mismatch",))
        ),
        train_runner=lambda _root, _run_root: pytest.fail("TRAIN must be skipped"),
    )

    assert result["terminal_case"] == "D"
    outcome = (
        tmp_path
        / "artifacts/t077-t075-same-experiment-continuation/outcomes/00-target.json"
    ).read_text(encoding="utf-8")
    assert '"failure_code":"TARGET_INVALID"' in outcome
    assert '"no_replacement":true' in outcome
