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
            "--valid",
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
    if operation == "preflight":
        args += ["--audit", str(tmp_path / f"{operation}.json")]
    elif operation == "validate-reuse":
        args += [
            "--audit",
            str(tmp_path / f"{operation}.json"),
            "--source-stochastic",
            str(tmp_path / "source-stochastic.json"),
            "--source-expert",
            str(tmp_path / "source-expert.json"),
        ]
    elif operation == "select":
        args += [
            "--source-stochastic",
            str(tmp_path / "source-stochastic.json"),
            "--source-expert",
            str(tmp_path / "source-expert.json"),
            "--source-reuse-audit",
            str(tmp_path / "source-reuse-audit.json"),
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
    if operation != "finalize":
        args += ["--valid"]
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
                "ownership_audit": None,
                "selected_states": None,
                "source_stochastic": tmp_path / "source-stochastic.json"
                if operation in {"select", "validate-reuse"}
                else None,
                "source_expert": tmp_path / "source-expert.json"
                if operation in {"select", "validate-reuse"}
                else None,
                "source_reuse_audit": tmp_path / "source-reuse-audit.json"
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


def _invalid_operation_argv(tmp_path, operation: str, failure_code: str) -> list[str]:
    return [
        "t075",
        operation,
        "--repository-root",
        str(tmp_path),
        "--run-head",
        RUN_HEAD,
        "--invalid",
        "--failure-code",
        failure_code,
    ]


@pytest.mark.parametrize(
    ("operation", "failure_code"),
    [
        ("preflight", "PREFLIGHT_INVALID"),
        ("validate-reuse", "SOURCE_REUSE_INVALID"),
        ("select", "SELECTION_MEMBER_ORDER_TIE"),
        ("target", "TARGET_INVALID"),
        ("train", "TRAIN_INVALID"),
        ("gate", "GATE_EVIDENCE_INVALID"),
        ("eval", "EVAL_EVIDENCE_INVALID"),
    ],
)
def test_t075_invalid_dispatch_omits_normative_payload_paths(
    tmp_path, monkeypatch, operation: str, failure_code: str
) -> None:
    import sts_combat_rl.commands.non_combat_learning as command

    calls: list[tuple[str, dict[str, object]]] = []

    def fake_operation(name: str, **kwargs: object) -> object:
        calls.append((name, kwargs))
        return SimpleNamespace(current_stage=operation, terminal_case="D")

    monkeypatch.setattr(command, "run_t075_operation", fake_operation)
    assert command.main(_invalid_operation_argv(tmp_path, operation, failure_code)) == 0
    assert len(calls) == 1
    name, kwargs = calls[0]
    assert name == operation
    assert kwargs["valid"] is False
    assert kwargs["failure_code"] == failure_code
    assert kwargs["passed"] is None
    for path_name in (
        "audit",
        "ownership_audit",
        "selected_states",
        "source_stochastic",
        "source_expert",
        "source_reuse_audit",
        "target_table",
        "checkpoint_653001",
        "checkpoint_653002",
        "training_selection",
        "stage5_report",
        "stage6_report",
    ):
        assert kwargs[path_name] is None


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

    def fake_preflight(state, audit, root, **kwargs):
        calls.append((state, audit, root))
        assert kwargs == {"valid": True, "failure_code": None}
        return "committed"

    monkeypatch.setattr(command, "reconstruct_t075_state", fake_reconstruct)
    monkeypatch.setattr(command, "_validate_t075_checkout", lambda *_args: None)
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


def test_t075_validate_reuse_checks_frozen_sources_before_public_adapter(
    tmp_path, monkeypatch
) -> None:
    import sts_combat_rl.commands.non_combat_learning as command

    source_paths = (
        tmp_path / "artifacts/t065-learned-non-combat-policy-v1/"
        "source-stochastic-650001-650256-c57b2ee.json",
        tmp_path / "artifacts/t065-learned-non-combat-policy-v1/"
        "source-expert-650001-650256-deeaa46.json",
    )
    audit = {
        "schema_id": "t075-source-reuse-audit-v1",
        "schema_version": 1,
        "task_id": "T075",
        "run_head": RUN_HEAD,
        "sources": [
            {
                "role": "current_output",
                "path": "artifacts/t065-learned-non-combat-policy-v1/"
                "source-stochastic-650001-650256-c57b2ee.json",
                "sha256": "40a29e2cc8042efc15a46e9c50f6a50f889c94a1d7def24e91b62718eaaa8f61",
                "size_bytes": 5352891044,
            },
            {
                "role": "current_output",
                "path": "artifacts/t065-learned-non-combat-policy-v1/"
                "source-expert-650001-650256-deeaa46.json",
                "sha256": "29d4155e543b024e741230b5bcefad3116c44610b370b666f46a65571348ad4c",
                "size_bytes": 3710180244,
            },
        ],
        "strict_reader_passed": True,
        "metadata_passed": True,
    }
    audit_path = tmp_path / "source-reuse.json"
    audit_path.write_bytes(command.canonical_json_document(audit))
    state = SimpleNamespace(run_head=RUN_HEAD)
    checked: list[tuple[object, object]] = []
    calls: list[tuple[object, object, object, dict[str, object]]] = []

    def fake_source_check(root, path, identity):
        checked.append((path, identity))

    def fake_reader_check(root, paths, source_audit):
        assert root == tmp_path
        assert paths == source_paths
        assert source_audit == audit
        for path, identity in zip(paths, command.T075_SOURCE_IDENTITIES, strict=True):
            fake_source_check(root, path, identity)

    def fake_reconstruct(root, run_head):
        assert root == tmp_path
        assert run_head == RUN_HEAD
        return state

    def fake_reuse(received_state, received_audit, root, **kwargs):
        calls.append((received_state, received_audit, root, kwargs))
        return "committed"

    monkeypatch.setattr(command, "_validate_t075_checkout", lambda *_args: None)
    monkeypatch.setattr(
        command, "_validate_t075_source_reuse_inputs", fake_reader_check
    )
    monkeypatch.setattr(command, "reconstruct_t075_state", fake_reconstruct)
    monkeypatch.setattr(command, "run_t075_validate_reuse", fake_reuse)
    assert (
        command.run_t075_operation(
            "validate-reuse",
            repository_root=tmp_path,
            run_head=RUN_HEAD,
            audit=audit_path,
            source_stochastic=source_paths[0],
            source_expert=source_paths[1],
        )
        == "committed"
    )
    assert checked == list(
        zip(source_paths, command.T075_SOURCE_IDENTITIES, strict=True)
    )
    assert calls == [(state, audit, tmp_path, {"valid": True, "failure_code": None})]


def test_t075_validate_reuse_source_failure_commits_invalid_outcome(
    tmp_path, monkeypatch
) -> None:
    import sts_combat_rl.commands.non_combat_learning as command

    source_paths = tuple(
        tmp_path / identity["path"] for identity in command.T075_SOURCE_IDENTITIES
    )
    audit = {
        "schema_id": "t075-source-reuse-audit-v1",
        "schema_version": 1,
        "task_id": "T075",
        "run_head": RUN_HEAD,
        "sources": [dict(identity) for identity in command.T075_SOURCE_IDENTITIES],
        "strict_reader_passed": True,
        "metadata_passed": True,
    }
    audit_path = tmp_path / "source-reuse.json"
    audit_path.write_bytes(command.canonical_json_document(audit))
    state = SimpleNamespace(run_head=RUN_HEAD)
    calls: list[tuple[object, object, object, dict[str, object]]] = []

    def fake_source_identity_check(*_args):
        raise command.T075OperationalError("frozen source identity mismatch")

    def fake_reuse(received_state, received_audit, root, **kwargs):
        calls.append((received_state, received_audit, root, kwargs))
        return "committed-invalid"

    monkeypatch.setattr(command, "_validate_t075_checkout", lambda *_args: None)
    monkeypatch.setattr(command, "reconstruct_t075_state", lambda *_args: state)
    monkeypatch.setattr(
        command, "_validate_t075_frozen_source", fake_source_identity_check
    )
    monkeypatch.setattr(command, "run_t075_validate_reuse", fake_reuse)
    assert (
        command.run_t075_operation(
            "validate-reuse",
            repository_root=tmp_path,
            run_head=RUN_HEAD,
            audit=audit_path,
            source_stochastic=source_paths[0],
            source_expert=source_paths[1],
        )
        == "committed-invalid"
    )
    assert calls == [
        (
            state,
            None,
            tmp_path,
            {"valid": False, "failure_code": "SOURCE_REUSE_INVALID"},
        )
    ]


def test_t075_validate_reuse_missing_source_path_is_control_error(
    tmp_path, monkeypatch
) -> None:
    import sts_combat_rl.commands.non_combat_learning as command

    state = SimpleNamespace(run_head=RUN_HEAD)
    monkeypatch.setattr(command, "_validate_t075_checkout", lambda *_args: None)
    monkeypatch.setattr(command, "reconstruct_t075_state", lambda *_args: state)
    with pytest.raises(command.T075OperationalError, match="stochastic source path"):
        command.run_t075_operation(
            "validate-reuse",
            repository_root=tmp_path,
            run_head=RUN_HEAD,
            source_expert=tmp_path / "expert.json",
            valid=True,
        )


@pytest.mark.parametrize(
    "failure_code",
    [
        "SELECTION_MEMBER_ORDER_TIE",
        "SELECTION_OWNER_QUOTA_SHORTAGE",
        "SELECTION_REPLAY_INVALID",
    ],
)
def test_t075_select_classification_commits_invalid_outcome(
    tmp_path, monkeypatch, failure_code: str
) -> None:
    import sts_combat_rl.commands.non_combat_learning as command

    state = SimpleNamespace(run_head=RUN_HEAD)
    calls: list[dict[str, object]] = []

    def fake_classified_selection(*_args, **_kwargs):
        raise command.T075StageClassificationError(failure_code, "classified")

    def fake_invalid_adapter(received_state, audit, selected, root, **kwargs):
        calls.append(
            {
                "state": received_state,
                "audit": audit,
                "selected": selected,
                "root": root,
                **kwargs,
            }
        )
        return "committed-invalid"

    monkeypatch.setattr(command, "_validate_t075_checkout", lambda *_args: None)
    monkeypatch.setattr(command, "reconstruct_t075_state", lambda *_args: state)
    monkeypatch.setattr(
        command, "_run_t075_source_selection", fake_classified_selection
    )
    monkeypatch.setattr(command, "run_t075_selection", fake_invalid_adapter)
    assert (
        command.run_t075_operation(
            "select",
            repository_root=tmp_path,
            run_head=RUN_HEAD,
            source_stochastic=tmp_path / "stochastic.json",
            source_expert=tmp_path / "expert.json",
            source_reuse_audit=tmp_path / "reuse.json",
        )
        == "committed-invalid"
    )
    assert calls == [
        {
            "state": state,
            "audit": None,
            "selected": None,
            "root": tmp_path,
            "valid": False,
            "failure_code": failure_code,
        }
    ]


def test_t075_operation_rejects_a_wrong_checkout_head_before_stage_work(
    tmp_path, monkeypatch
) -> None:
    import sts_combat_rl.commands.non_combat_learning as command

    def fake_git_output(_root, *arguments):
        if arguments == ("rev-parse", "--show-toplevel"):
            return str(tmp_path)
        if arguments == ("status", "--porcelain"):
            return ""
        if arguments == ("rev-parse", "HEAD"):
            return "2" * 40
        raise AssertionError(arguments)

    monkeypatch.setattr(command, "_t075_git_output", fake_git_output)
    monkeypatch.setattr(
        command,
        "reconstruct_t075_state",
        lambda *_args: pytest.fail("state reconstruction must not start"),
    )
    with pytest.raises(command.T075OperationalError, match="run_head"):
        command.run_t075_operation(
            "preflight",
            repository_root=tmp_path,
            run_head=RUN_HEAD,
            valid=False,
            failure_code="PREFLIGHT_INVALID",
        )


def test_t075_operation_rejects_a_dirty_checkout_before_stage_work(
    tmp_path, monkeypatch
) -> None:
    import sts_combat_rl.commands.non_combat_learning as command

    def fake_git_output(_root, *arguments):
        if arguments == ("rev-parse", "--show-toplevel"):
            return str(tmp_path)
        if arguments == ("status", "--porcelain"):
            return " M pending.py"
        raise AssertionError(arguments)

    monkeypatch.setattr(command, "_t075_git_output", fake_git_output)
    with pytest.raises(command.T075OperationalError, match="clean"):
        command.run_t075_operation(
            "preflight",
            repository_root=tmp_path,
            run_head=RUN_HEAD,
            valid=False,
            failure_code="PREFLIGHT_INVALID",
        )


def test_t075_operation_rejects_external_input_before_stage_work(
    tmp_path, monkeypatch
) -> None:
    import sts_combat_rl.commands.non_combat_learning as command

    repository_root = tmp_path / "repo"
    repository_root.mkdir()
    external_audit = tmp_path / "outside-audit.json"
    monkeypatch.setattr(command, "_validate_t075_checkout", lambda *_args: None)
    monkeypatch.setattr(
        command,
        "reconstruct_t075_state",
        lambda *_args: pytest.fail("state reconstruction must not start"),
    )
    with pytest.raises(command.T075OperationalError, match="within repository_root"):
        command.run_t075_operation(
            "preflight",
            repository_root=repository_root,
            run_head=RUN_HEAD,
            audit=external_audit,
            valid=True,
        )
