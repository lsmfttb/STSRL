"""Focused checks for the nested T075 command surface."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

OPERATIONS = (
    "preflight",
    "validate-reuse",
    "select",
    "target",
    "train",
    "gate",
    "eval",
    "finalize",
)
RUN_HEAD = "1" * 40


def test_t075_help_lists_only_the_explicit_nested_operations(capsys) -> None:
    from sts_combat_rl.commands.non_combat_learning import build_parser

    with pytest.raises(SystemExit) as raised:
        build_parser().parse_args(["t075", "--help"])
    assert raised.value.code == 0
    help_text = capsys.readouterr().out
    assert all(operation in help_text for operation in OPERATIONS)
    assert "workflow framework" not in help_text


def test_t075_parser_is_nested_and_legacy_t065_select_remains_flat(tmp_path) -> None:
    from sts_combat_rl.commands.non_combat_learning import build_parser

    parser = build_parser()
    t075_args = parser.parse_args(
        [
            "t075",
            "preflight",
            "--repository-root",
            str(tmp_path),
            "--run-head",
            RUN_HEAD,
            "--audit",
            str(tmp_path / "preflight-audit.json"),
        ]
    )
    assert t075_args.command == "t075"
    assert t075_args.t075_operation == "preflight"
    assert t075_args.run_head == RUN_HEAD
    assert t075_args.repository_root == tmp_path

    legacy_args = parser.parse_args(
        [
            "select",
            "--input",
            str(tmp_path / "source.json"),
            "--output",
            str(tmp_path / "selected.jsonl"),
            "--preflight",
            str(tmp_path / "legacy-preflight.json"),
        ]
    )
    assert legacy_args.command == "select"
    assert not hasattr(legacy_args, "t075_operation")


def _operation_argv(tmp_path, operation: str) -> list[str]:
    root = str(tmp_path)
    args = [
        "t075",
        operation,
        "--repository-root",
        root,
        "--run-head",
        RUN_HEAD,
    ]
    if operation in {"preflight", "validate-reuse"}:
        args += ["--audit", str(tmp_path / f"{operation}.json")]
    elif operation == "select":
        args += [
            "--ownership-audit",
            str(tmp_path / "ownership.json"),
            "--selected-states",
            str(tmp_path / "selected-states.jsonl"),
        ]
    elif operation == "target":
        args += ["--target-table", str(tmp_path / "target-table.json")]
    elif operation == "train":
        args += [
            "--checkpoint-653001",
            str(tmp_path / "653001.pt"),
            "--checkpoint-653002",
            str(tmp_path / "653002.pt"),
            "--training-selection",
            str(tmp_path / "training-selection.json"),
        ]
    elif operation == "gate":
        args += ["--stage5-report", str(tmp_path / "stage5.json"), "--passed"]
    elif operation == "eval":
        args += ["--stage6-report", str(tmp_path / "stage6.json"), "--failed"]
    else:
        args += [
            "--entry-metadata",
            str(tmp_path / "retention-metadata.json"),
            "--retention-reason",
            "focused command test",
            "--downstream-consumer",
            "none currently approved",
        ]
    return args


@pytest.mark.parametrize("operation", OPERATIONS)
def test_t075_main_dispatches_each_operation_without_running_science(
    tmp_path, monkeypatch, operation: str
) -> None:
    import sts_combat_rl.commands.non_combat_learning as command

    calls: list[tuple[str, dict[str, object]]] = []

    def fake_operation(name: str, **kwargs: object) -> object:
        calls.append((name, kwargs))
        if name == "finalize":
            return (object(), object())
        return SimpleNamespace(current_stage="SOURCE_REUSE", terminal_case=None)

    monkeypatch.setattr(command, "run_t075_operation", fake_operation)
    assert command.main(_operation_argv(tmp_path, operation)) == 0
    assert calls == [
        (
            operation,
            {
                "repository_root": tmp_path,
                "run_head": RUN_HEAD,
                "audit": tmp_path / f"{operation}.json"
                if operation in {"preflight", "validate-reuse"}
                else None,
                "ownership_audit": tmp_path / "ownership.json"
                if operation == "select"
                else None,
                "selected_states": tmp_path / "selected-states.jsonl"
                if operation == "select"
                else None,
                "target_table": tmp_path / "target-table.json"
                if operation == "target"
                else None,
                "checkpoint_653001": tmp_path / "653001.pt"
                if operation == "train"
                else None,
                "checkpoint_653002": tmp_path / "653002.pt"
                if operation == "train"
                else None,
                "training_selection": tmp_path / "training-selection.json"
                if operation == "train"
                else None,
                "stage5_report": tmp_path / "stage5.json"
                if operation == "gate"
                else None,
                "stage6_report": tmp_path / "stage6.json"
                if operation == "eval"
                else None,
                "entry_metadata": tmp_path / "retention-metadata.json"
                if operation == "finalize"
                else None,
                "retention_reason": "focused command test"
                if operation == "finalize"
                else None,
                "downstream_consumers": ("none currently approved",)
                if operation == "finalize"
                else (),
                "valid": True,
                "passed": True
                if operation == "gate"
                else False
                if operation == "eval"
                else None,
                "failure_code": None,
            },
        )
    ]


def test_t075_operation_reads_canonical_input_before_public_adapter(
    tmp_path, monkeypatch
) -> None:
    import sts_combat_rl.commands.non_combat_learning as command

    audit_path = tmp_path / "preflight-audit.json"
    audit_path.write_bytes(b'{"audit":true}\n')
    committed_state = object()
    calls: list[tuple[object, object, object]] = []

    def fake_reconstruct(root, run_head):
        assert root == tmp_path
        assert run_head == RUN_HEAD
        return committed_state

    def fake_preflight(state, audit, root):
        calls.append((state, audit, root))
        return "committed"

    monkeypatch.setattr(command, "reconstruct_t075_state", fake_reconstruct)
    monkeypatch.setattr(command, "run_t075_preflight", fake_preflight)
    assert (
        command.run_t075_operation(
            "preflight",
            repository_root=tmp_path,
            run_head=RUN_HEAD,
            audit=audit_path,
        )
        == "committed"
    )
    assert calls == [(committed_state, {"audit": True}, tmp_path)]
