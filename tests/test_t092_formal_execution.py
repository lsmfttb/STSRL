"""Mock-only T092 formal authorization and root-reference boundary tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from sts_combat_rl.sim.t092_formal_execution import (
    T092FormalError,
    execute_t092_authorized_formal_shard,
    validate_t092_t090_root_reference,
)
from sts_combat_rl.sim.t090_battle_student import canonical_sha256
from sts_combat_rl.commands.t092_formal import build_parser


def _root_reference(*, complete_s0: bool = True) -> dict[str, object]:
    rows = []
    for index in range(6369):
        action_count = 2 if index < 6210 else 1
        actions = []
        for action in range(action_count):
            visited = complete_s0 and index < 309
            actions.append({"action_identity": {"stable_id": f"{index}:{action}"},
                            "visits": 1 if visited else 0,
                            "mean_value": 0.0 if visited else None})
        rows.append({"decision_identity": f"decision:{index}", "ordered_root_actions": actions,
                     "selected_action_identity": {"stable_id": f"{index}:0"}})
    split = {"entries": []}
    return {"schema_id": "t092-t090-root-reproduction-reference-v1", "schema_version": 1,
            "task_id": "T092", "split_manifest_sha256": canonical_sha256(split),
            "source_ledger": {"path": "/ledger.json", "sha256": "a" * 64, "size_bytes": 1, "schema_id": "t090-source-execution-ledger-v1"},
            "rows": rows, "rows_sha256": canonical_sha256(rows)}


def test_t092_root_reference_requires_frozen_6369_6210_309_counts() -> None:
    split = {"entries": []}
    assert validate_t092_t090_root_reference(_root_reference(), split_manifest=split)["rows_sha256"]
    with pytest.raises(T092FormalError, match="frozen T090 counts"):
        validate_t092_t090_root_reference(_root_reference(complete_s0=False), split_manifest=split)


def test_formal_authorization_failure_cannot_invoke_runner() -> None:
    invoked = False

    def runner(_source, _worker):
        nonlocal invoked
        invoked = True
        raise AssertionError("must not run")

    with pytest.raises(T092FormalError, match="authorization is required"):
        execute_t092_authorized_formal_shard(authorization=None, implementation_head="a" * 40,
            split_manifest={}, root_reference={}, canary_evidence={}, input_identities={"x": "y"},
            output_root="/tmp/t092", shard_index=0, shard_count=8, worker_count=8, runner=runner)
    assert invoked is False


def test_formal_command_exposes_native_free_restore_preparation() -> None:
    parser = build_parser()
    operations = parser._subparsers._group_actions[0].choices
    assert "prepare-restore-inputs" in operations
    assert "prepare-root-reference" in operations


def test_detached_formal_launcher_waits_before_finalization() -> None:
    script = (Path(__file__).parents[1] / "scripts/run_t092_formal_detached.sh").read_text()
    assert "wait_for_success" in script
    assert script.index("wait_for_success \"$ARTIFACT_ROOT/jobs") < script.index("formal finalize")
    assert "env PYTHONPATH=src /usr/bin/python3.14 -m sts_combat_rl.commands.t092_formal finalize" in script
