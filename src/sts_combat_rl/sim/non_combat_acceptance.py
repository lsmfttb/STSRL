"""Neutral acceptance and artifact boundaries for the T075 recovery run.

This module owns only the small, durable control boundary described by the
approved T075 contract.  It does not run the simulator or reimplement any T065
scientific reducer.  Stage adapters receive already-classified payloads,
validate the T075-owned envelopes, and commit one canonical ``StageOutcome``.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import pickle
import re
import tempfile
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

T075_TASK_ID = "T075"
T075_APPROVED_SPEC_COMMIT = "66e6f7aabb8176eebf05013992d4ec0840809860"
T075_RECOVERY_BASE = "bc9a6790f36ff036f90dc7f03ba0ff026a16788d"
T075_STS_LIGHTSPEED_INTEGRATION = "fee272f1ae21c283ad2161f55293cfe6d714134a"
T075_ROOT_RELATIVE = "artifacts/t075-leakage-safe-non-combat-cohort-repair"
T075_STAGES = (
    "PREFLIGHT",
    "SOURCE_REUSE",
    "SELECTION_REPLAY",
    "TARGET",
    "TRAIN",
    "GATE",
    "EVAL",
)
T075_FAILURE_CODES = frozenset(
    {
        "PREFLIGHT_INVALID",
        "SOURCE_REUSE_INVALID",
        "SELECTION_MEMBER_ORDER_TIE",
        "SELECTION_OWNER_QUOTA_SHORTAGE",
        "SELECTION_REPLAY_INVALID",
        "TARGET_INVALID",
        "TRAIN_INVALID",
        "GATE_EVIDENCE_INVALID",
        "EVAL_EVIDENCE_INVALID",
    }
)
T075_PREFLIGHT_CHECKS = (
    "runtime_imports",
    "simulator_identity",
    "checkpoint_roundtrip",
    "frozen_controller_action_space",
    "model_input_schema",
    "public_input_firewall",
    "torch_runtime",
)
T075_SOURCE_IDENTITIES = (
    {
        "role": "current_output",
        "path": "artifacts/t065-learned-non-combat-policy-v1/source-stochastic-650001-650256-c57b2ee.json",
        "sha256": "40a29e2cc8042efc15a46e9c50f6a50f889c94a1d7def24e91b62718eaaa8f61",
        "size_bytes": 5352891044,
    },
    {
        "role": "current_output",
        "path": "artifacts/t065-learned-non-combat-policy-v1/source-expert-650001-650256-deeaa46.json",
        "sha256": "29d4155e543b024e741230b5bcefad3116c44610b370b666f46a65571348ad4c",
        "size_bytes": 3710180244,
    },
)
T075_REUSED_T065_RETENTION = {
    T075_SOURCE_IDENTITIES[0]["path"]: {
        "source_kind": "reused_t065",
        "producer_task": "T065",
        "producer_stage": "stage1-source-collection",
        "producer_git_commit": "c57b2eef8615df2f43fb4dcf52af19ff44fe6108",
        "regeneration_commands": [
            (
                "$PY -m sts_combat_rl.commands.non_combat_learning collect "
                "--arm stochastic_non_combat_v1 --output <stable-source-path> "
                "--seed-start 650001 --seed-end 650256 --sim-seed 1 "
                "--ascension 20 --preflight <validated-t065-preflight>"
            )
        ],
    },
    T075_SOURCE_IDENTITIES[1]["path"]: {
        "source_kind": "reused_t065",
        "producer_task": "T065",
        "producer_stage": "stage1-source-collection",
        "producer_git_commit": "deeaa461c138db80f4393310d97d5d44d5fa8fd3",
        "regeneration_commands": [
            (
                "$PY -m sts_combat_rl.commands.non_combat_learning collect "
                "--arm expert_non_combat_v1 --output <stable-source-path> "
                "--seed-start 650001 --seed-end 650256 --sim-seed 1 "
                "--ascension 20 --preflight <validated-t065-preflight>"
            )
        ],
    },
}
T075_OUTCOME_FILENAMES = {
    stage: f"{index:02d}-{stage.lower()}.json"
    for index, stage in enumerate(T075_STAGES)
}
T075_OUTPUT_LAYOUT = {
    "PREFLIGHT": (("preflight_audit", "preflight-audit.json"),),
    "SOURCE_REUSE": (("source_reuse_audit", "source-reuse-audit.json"),),
    "SELECTION_REPLAY": (
        ("ownership_audit", "ownership-audit.json"),
        ("selected_states", "selected-states.jsonl"),
    ),
    "TARGET": (("target_table", "target-table.json"),),
    "TRAIN": (
        ("checkpoint", "checkpoints/653001.pt"),
        ("checkpoint", "checkpoints/653002.pt"),
        ("training_selection", "training-selection.json"),
    ),
    "GATE": (("stage5_report", "heldout-gate-report.json"),),
    "EVAL": (("stage6_report", "complete-run-report.json"),),
}
T075_TERMINAL_MAPPING = {
    "A": (
        "experimental_public_with_expert_fallback",
        "review_joint_policy",
    ),
    "B": ("no_promotion", "narrow_transfer_followup"),
    "C": ("no_promotion", "close_v1"),
    "D": ("no_promotion", "repair_same_experiment"),
}
_GIT_COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_STAGE_FAILURE_CODES = {
    "PREFLIGHT": frozenset({"PREFLIGHT_INVALID"}),
    "SOURCE_REUSE": frozenset({"SOURCE_REUSE_INVALID"}),
    "SELECTION_REPLAY": frozenset(
        {
            "SELECTION_MEMBER_ORDER_TIE",
            "SELECTION_OWNER_QUOTA_SHORTAGE",
            "SELECTION_REPLAY_INVALID",
        }
    ),
    "TARGET": frozenset({"TARGET_INVALID"}),
    "TRAIN": frozenset({"TRAIN_INVALID"}),
    "GATE": frozenset({"GATE_EVIDENCE_INVALID"}),
    "EVAL": frozenset({"EVAL_EVIDENCE_INVALID"}),
}
_STAGE_OUTCOME_KEYS = frozenset(
    {
        "schema_id",
        "schema_version",
        "task_id",
        "run_head",
        "stage",
        "valid",
        "passed",
        "parents",
        "outputs",
        "failure_code",
    }
)


class T075OperationalError(ValueError):
    """A structural/control-plane rejection that must leave state unchanged."""


class T075StageClassificationError(ValueError):
    """A reached-stage classifier result that should commit Case D."""

    def __init__(self, failure_code: str, message: str) -> None:
        if failure_code not in T075_FAILURE_CODES:
            raise ValueError(f"unknown T075 failure code: {failure_code!r}")
        self.failure_code = failure_code
        super().__init__(message)


class T075CommitInterrupted(RuntimeError):
    """The normative outputs were promoted but the outcome marker was not."""


def canonical_json_bytes(value: Any) -> bytes:
    """Return the contract's canonical JSON bytes without a newline."""

    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def canonical_json_document(value: Any) -> bytes:
    """Return one canonical JSON document with the required trailing newline."""

    return canonical_json_bytes(value) + b"\n"


def _strict_keys(value: Mapping[str, Any], expected: set[str], label: str) -> None:
    observed = set(value)
    if observed != expected:
        missing = sorted(expected - observed)
        unknown = sorted(observed - expected)
        raise ValueError(f"{label} keys mismatch; missing={missing}, unknown={unknown}")


def _nonempty_string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{label} must be a non-empty string")
    return value


def _integer(value: Any, label: str, *, minimum: int | None = None) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{label} must be an integer")
    if minimum is not None and value < minimum:
        raise ValueError(f"{label} must be >= {minimum}")
    return value


def _boolean(value: Any, label: str) -> bool:
    if not isinstance(value, bool):
        raise TypeError(f"{label} must be a boolean")
    return value


def _git_commit(value: Any, label: str) -> str:
    if not isinstance(value, str) or not _GIT_COMMIT_RE.fullmatch(value):
        raise ValueError(f"{label} must be 40 lowercase hexadecimal characters")
    return value


@dataclass(frozen=True, slots=True)
class ArtifactIdentity:
    """The four-field identity used by all T075 lineage checks."""

    role: str
    path: str
    sha256: str
    size_bytes: int

    def __post_init__(self) -> None:
        _nonempty_string(self.role, "artifact role")
        if (
            not self.path.startswith("artifacts/")
            or "\\" in self.path
            or not self.path.split("/")[-1]
            or any(part in {"", ".", ".."} for part in self.path.split("/"))
        ):
            raise ValueError(
                "artifact path must be a repository-relative POSIX path under artifacts/"
            )
        if not _SHA256_RE.fullmatch(self.sha256):
            raise ValueError(
                "artifact sha256 must be 64 lowercase hexadecimal characters"
            )
        _integer(self.size_bytes, "artifact size_bytes", minimum=0)

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> ArtifactIdentity:
        if not isinstance(value, Mapping):
            raise TypeError("artifact identity must be an object")
        _strict_keys(
            value, {"role", "path", "sha256", "size_bytes"}, "artifact identity"
        )
        return cls(
            role=_nonempty_string(value["role"], "artifact role"),
            path=_nonempty_string(value["path"], "artifact path"),
            sha256=value["sha256"],
            size_bytes=value["size_bytes"],
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "role": self.role,
            "path": self.path,
            "sha256": self.sha256,
            "size_bytes": self.size_bytes,
        }


def _identity_tuple(
    values: Sequence[ArtifactIdentity | Mapping[str, Any]],
) -> tuple[ArtifactIdentity, ...]:
    return tuple(
        value
        if isinstance(value, ArtifactIdentity)
        else ArtifactIdentity.from_mapping(value)
        for value in values
    )


@dataclass(frozen=True, slots=True)
class StageOutcome:
    """One canonical, small stage commit record."""

    run_head: str
    stage: str
    valid: bool
    passed: bool
    parents: tuple[ArtifactIdentity, ...] = ()
    outputs: tuple[ArtifactIdentity, ...] = ()
    failure_code: str | None = None

    def __post_init__(self) -> None:
        _git_commit(self.run_head, "stage outcome run_head")
        if self.stage not in T075_STAGES:
            raise ValueError(f"unsupported T075 stage: {self.stage!r}")
        _boolean(self.valid, "stage outcome valid")
        _boolean(self.passed, "stage outcome passed")
        if self.failure_code is not None:
            if not isinstance(self.failure_code, str):
                raise ValueError("stage outcome failure_code must be a string or null")
            if self.failure_code not in T075_FAILURE_CODES:
                raise ValueError(f"unknown T075 failure code: {self.failure_code!r}")
            if self.failure_code not in _STAGE_FAILURE_CODES[self.stage]:
                raise ValueError(
                    f"failure code {self.failure_code!r} is not valid for {self.stage}"
                )
        if self.valid and self.failure_code is not None:
            raise ValueError("valid stage outcome must not carry a failure code")
        if not self.valid and (
            self.passed or self.outputs or self.failure_code is None
        ):
            raise ValueError(
                "invalid stage outcome must be failed, output-free, and coded"
            )
        if self.valid and self.stage not in {"GATE", "EVAL"} and not self.passed:
            raise ValueError("pre-gate valid stage outcome must pass")

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> StageOutcome:
        if not isinstance(value, Mapping):
            raise TypeError("stage outcome must be an object")
        _strict_keys(value, set(_STAGE_OUTCOME_KEYS), "stage outcome")
        if value["schema_id"] != "t075-stage-outcome-v1":
            raise ValueError("unsupported T075 stage-outcome schema")
        if value["schema_version"] != 1:
            raise ValueError("unsupported T075 stage-outcome schema version")
        if value["task_id"] != T075_TASK_ID:
            raise ValueError("T075 stage-outcome task id is invalid")
        if not isinstance(value["parents"], list) or not isinstance(
            value["outputs"], list
        ):
            raise TypeError("stage outcome parents and outputs must be arrays")
        return cls(
            run_head=value["run_head"],
            stage=value["stage"],
            valid=value["valid"],
            passed=value["passed"],
            parents=_identity_tuple(value["parents"]),
            outputs=_identity_tuple(value["outputs"]),
            failure_code=value["failure_code"],
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": "t075-stage-outcome-v1",
            "schema_version": 1,
            "task_id": T075_TASK_ID,
            "run_head": self.run_head,
            "stage": self.stage,
            "valid": self.valid,
            "passed": self.passed,
            "parents": [identity.to_dict() for identity in self.parents],
            "outputs": [identity.to_dict() for identity in self.outputs],
            "failure_code": self.failure_code,
        }

    def canonical_bytes(self) -> bytes:
        return canonical_json_document(self.to_dict())


@dataclass(frozen=True, slots=True)
class CommittedOutcome:
    outcome: StageOutcome
    report_identity: ArtifactIdentity

    def __post_init__(self) -> None:
        if self.report_identity.role != "stage_outcome":
            raise ValueError("committed outcome report role must be stage_outcome")
        if self.report_identity.path != _expected_report_path(self.outcome.stage):
            raise ValueError("committed outcome report path is invalid")
        expected_report = _artifact_identity_for_bytes(
            "stage_outcome",
            self.report_identity.path,
            self.outcome.canonical_bytes(),
        )
        if self.report_identity != expected_report:
            raise ValueError("committed outcome report identity does not match outcome")
        _validate_stage_outputs(self.outcome)


@dataclass(frozen=True, slots=True)
class AcceptanceState:
    run_head: str
    committed_outcomes: tuple[CommittedOutcome, ...] = ()
    current_stage: str | None = "PREFLIGHT"
    terminal_case: str | None = None
    terminal_stage: str | None = None

    def __post_init__(self) -> None:
        _git_commit(self.run_head, "acceptance state run_head")
        if self.current_stage is not None and self.current_stage not in T075_STAGES:
            raise ValueError("acceptance state current_stage is invalid")
        if self.terminal_case is not None and self.terminal_case not in {
            "A",
            "B",
            "C",
            "D",
        }:
            raise ValueError("acceptance state terminal_case is invalid")
        if (self.terminal_case is None) != (self.terminal_stage is None):
            raise ValueError("terminal case and stage must be set together")
        if self.terminal_stage is not None and self.terminal_stage not in T075_STAGES:
            raise ValueError("acceptance state terminal_stage is invalid")
        stages = tuple(row.outcome.stage for row in self.committed_outcomes)
        if len(set(stages)) != len(stages) or stages != tuple(
            T075_STAGES[: len(stages)]
        ):
            raise ValueError("committed outcomes must be a canonical stage prefix")
        if any(
            row.outcome.run_head != self.run_head for row in self.committed_outcomes
        ):
            raise ValueError("committed outcome run_head does not match state")
        if self.terminal_case is None:
            if len(stages) == len(T075_STAGES):
                raise ValueError("seven committed stages must be terminal")
            expected_current = T075_STAGES[len(stages)]
            if self.current_stage != expected_current:
                raise ValueError("acceptance state current_stage is inconsistent")
        else:
            if self.current_stage is not None or not stages:
                raise ValueError("terminal acceptance state is inconsistent")
            if self.terminal_stage != stages[-1]:
                raise ValueError("terminal acceptance state stage is inconsistent")


def initial_acceptance_state(run_head: str) -> AcceptanceState:
    return AcceptanceState(run_head=run_head)


def artifact_index(state: AcceptanceState) -> tuple[ArtifactIdentity, ...]:
    """Return committed report/output identities in deterministic commit order."""

    identities: list[ArtifactIdentity] = []
    for committed in state.committed_outcomes:
        identities.append(committed.report_identity)
        if committed.outcome.valid:
            identities.extend(committed.outcome.outputs)
    return tuple(identities)


def _expected_report_path(stage: str) -> str:
    return f"{T075_ROOT_RELATIVE}/outcomes/{T075_OUTCOME_FILENAMES[stage]}"


def _expected_output_path(stage: str, filename: str) -> str:
    return f"{T075_ROOT_RELATIVE}/{filename}"


def _identity_has_path(identity: ArtifactIdentity, *, role: str, filename: str) -> bool:
    return identity.role == role and identity.path == _expected_output_path(
        "", filename
    )


def _find_identity(
    identities: Sequence[ArtifactIdentity], role: str, filename: str
) -> ArtifactIdentity:
    matches = [
        identity
        for identity in identities
        if _identity_has_path(identity, role=role, filename=filename)
    ]
    if len(matches) != 1:
        raise T075OperationalError(
            f"expected exactly one committed {role} at {filename}, found {len(matches)}"
        )
    return matches[0]


def _expected_parent_roles(stage: str, valid: bool) -> tuple[str, ...]:
    if stage == "PREFLIGHT":
        return ()
    if stage == "SOURCE_REUSE":
        return (
            (
                "preflight_audit",
                "current_output",
                "current_output",
            )
            if valid
            else ("preflight_audit",)
        )
    if stage == "SELECTION_REPLAY":
        return ("source_reuse_audit",)
    if stage == "TARGET":
        return ("preflight_audit", "selected_states")
    if stage == "TRAIN":
        return ("target_table",)
    if stage in {"GATE", "EVAL"}:
        return (
            (
                "target_table",
                "training_selection",
                "checkpoint",
            )
            if stage == "GATE"
            else (
                "stage5_report",
                "training_selection",
                "checkpoint",
            )
        )
    raise T075OperationalError(f"unsupported stage {stage!r}")


def _validate_report_identity(stage: str, identity: ArtifactIdentity) -> None:
    if identity.role != "stage_outcome" or identity.path != _expected_report_path(
        stage
    ):
        raise T075OperationalError(
            "stage-outcome report identity has the wrong role/path"
        )


def _validate_report_bytes(outcome: StageOutcome, identity: ArtifactIdentity) -> None:
    expected = _artifact_identity_for_bytes(
        "stage_outcome", identity.path, outcome.canonical_bytes()
    )
    if identity != expected:
        raise T075OperationalError(
            "stage-outcome report identity does not match canonical outcome bytes"
        )


def _validate_stage_lineage(state: AcceptanceState, outcome: StageOutcome) -> None:
    expected_roles = _expected_parent_roles(outcome.stage, outcome.valid)
    if tuple(parent.role for parent in outcome.parents) != expected_roles:
        raise T075OperationalError(
            f"{outcome.stage} parents do not match the frozen role/order shape"
        )
    committed = artifact_index(state)
    if outcome.stage == "SOURCE_REUSE" and outcome.valid:
        expected_external = _identity_tuple(T075_SOURCE_IDENTITIES)
        if outcome.parents[1:] != expected_external:
            raise T075OperationalError(
                "SOURCE_REUSE external source identities are not exact"
            )
        if outcome.parents[0] not in committed:
            raise T075OperationalError("SOURCE_REUSE preflight parent is not committed")
        return
    if any(parent not in committed for parent in outcome.parents):
        raise T075OperationalError(
            "stage parent identity is not in artifact_index(state)"
        )


def _validate_stage_outputs(outcome: StageOutcome) -> None:
    expected = T075_OUTPUT_LAYOUT[outcome.stage] if outcome.valid else ()
    if len(outcome.outputs) != len(expected):
        raise T075OperationalError("stage output count does not match the frozen shape")
    for identity, (role, filename) in zip(outcome.outputs, expected, strict=True):
        if not _identity_has_path(identity, role=role, filename=filename):
            raise T075OperationalError(
                "stage output identity has the wrong role/path/order"
            )


def _require_matching_run_head(
    value: Mapping[str, Any], state: AcceptanceState, label: str
) -> None:
    if value["run_head"] != state.run_head:
        raise T075OperationalError(f"{label} run_head does not match acceptance state")


def _report_file(repository_root: Path, stage: str) -> Path:
    return _repository_path(
        repository_root,
        ArtifactIdentity(
            role="stage_outcome",
            path=_expected_report_path(stage),
            sha256="0" * 64,
            size_bytes=0,
        ),
    )


def reconstruct_t075_state(
    repository_root: Path,
    run_head: str,
) -> AcceptanceState:
    """Rebuild canonical state solely by replaying ordered outcome files."""

    _git_commit(run_head, "T075 reconstruction run_head")
    state = initial_acceptance_state(run_head)
    for index, stage in enumerate(T075_STAGES):
        report_file = _report_file(repository_root, stage)
        if not report_file.exists():
            later_reports = [
                _report_file(repository_root, later_stage)
                for later_stage in T075_STAGES[index + 1 :]
                if _report_file(repository_root, later_stage).exists()
            ]
            if later_reports:
                raise T075OperationalError(
                    "T075 outcome files are not a canonical stage prefix"
                )
            break
        try:
            report_payload = report_file.read_bytes()
            value = json.loads(report_payload.decode("utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise T075OperationalError(
                f"cannot read canonical T075 outcome for {stage}"
            ) from exc
        if not isinstance(value, Mapping):
            raise T075OperationalError(f"T075 outcome for {stage} is not an object")
        outcome = StageOutcome.from_mapping(value)
        if outcome.canonical_bytes() != report_payload:
            raise T075OperationalError(
                f"T075 outcome for {stage} is not canonical JSON"
            )
        report_identity = _artifact_identity_for_bytes(
            "stage_outcome", _expected_report_path(stage), report_payload
        )
        state = advance(state, outcome, report_identity)
    return state


# The second name keeps the restart seam discoverable without adding another
# state authority.  Both names execute the same replay implementation.
load_t075_state = reconstruct_t075_state


def advance(
    state: AcceptanceState,
    outcome: StageOutcome | Mapping[str, Any],
    report_identity: ArtifactIdentity | Mapping[str, Any],
) -> AcceptanceState:
    """Apply the sole T075 transition authority to one prospective outcome."""

    if isinstance(outcome, Mapping) and outcome.get("run_head") != state.run_head:
        raise T075OperationalError("wrong T075 run_head")
    parsed_outcome = (
        outcome
        if isinstance(outcome, StageOutcome)
        else StageOutcome.from_mapping(outcome)
    )
    if parsed_outcome.run_head != state.run_head:
        raise T075OperationalError("wrong T075 run_head")
    parsed_report = (
        report_identity
        if isinstance(report_identity, ArtifactIdentity)
        else ArtifactIdentity.from_mapping(report_identity)
    )
    existing = next(
        (
            committed
            for committed in state.committed_outcomes
            if committed.outcome.stage == parsed_outcome.stage
        ),
        None,
    )
    if existing is not None:
        if (
            existing.outcome.canonical_bytes() == parsed_outcome.canonical_bytes()
            and existing.report_identity == parsed_report
        ):
            return state
        raise T075OperationalError("conflicting duplicate stage outcome")
    if state.terminal_case is not None:
        raise T075OperationalError("new stage is not allowed after terminal")
    if parsed_outcome.stage != state.current_stage:
        raise T075OperationalError("outcome stage is not current_stage")
    _validate_report_identity(parsed_outcome.stage, parsed_report)
    _validate_report_bytes(parsed_outcome, parsed_report)
    _validate_stage_lineage(state, parsed_outcome)
    _validate_stage_outputs(parsed_outcome)
    next_stage = (
        T075_STAGES[T075_STAGES.index(parsed_outcome.stage) + 1]
        if parsed_outcome.stage != "EVAL"
        else None
    )
    terminal_case: str | None = None
    terminal_stage: str | None = None
    if not parsed_outcome.valid:
        terminal_case, terminal_stage, next_stage = "D", parsed_outcome.stage, None
    elif parsed_outcome.stage == "GATE" and not parsed_outcome.passed:
        terminal_case, terminal_stage, next_stage = "C", parsed_outcome.stage, None
    elif parsed_outcome.stage == "EVAL":
        terminal_case, terminal_stage = (
            "A" if parsed_outcome.passed else "B",
            parsed_outcome.stage,
        )
    return replace(
        state,
        committed_outcomes=state.committed_outcomes
        + (CommittedOutcome(parsed_outcome, parsed_report),),
        current_stage=next_stage,
        terminal_case=terminal_case,
        terminal_stage=terminal_stage,
    )


def _artifact_identity_for_bytes(
    role: str, path: str, payload: bytes
) -> ArtifactIdentity:
    return ArtifactIdentity(
        role=role,
        path=path,
        sha256=hashlib.sha256(payload).hexdigest(),
        size_bytes=len(payload),
    )


def _repository_path(repository_root: Path, identity: ArtifactIdentity) -> Path:
    path = repository_root.joinpath(*identity.path.split("/"))
    resolved_root = repository_root.resolve()
    resolved_path = path.resolve()
    if resolved_root not in resolved_path.parents:
        raise T075OperationalError("artifact path escapes repository root")
    return path


def _atomic_write(repository_root: Path, path: Path, payload: bytes) -> None:
    tmp_root = repository_root / T075_ROOT_RELATIVE / ".tmp"
    tmp_root.mkdir(parents=True, exist_ok=True)
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix="t075-", suffix=".tmp", dir=tmp_root
    )
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_name, path)
    except BaseException:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
        raise


def atomic_commit_stage(
    state: AcceptanceState,
    outcome: StageOutcome | Mapping[str, Any],
    repository_root: Path,
    output_payloads: Sequence[tuple[ArtifactIdentity | Mapping[str, Any], bytes]] = (),
    *,
    interrupt_before_outcome: bool = False,
) -> AcceptanceState:
    """Promote outputs, then atomically write the sole StageOutcome marker."""

    repository_root = Path(repository_root)
    persisted = reconstruct_t075_state(repository_root, state.run_head)
    if persisted != state:
        raise T075OperationalError(
            "caller state does not match the committed T075 outcome files"
        )
    parsed_outcome = (
        outcome
        if isinstance(outcome, StageOutcome)
        else StageOutcome.from_mapping(outcome)
    )
    report_path = _expected_report_path(parsed_outcome.stage)
    report_payload = parsed_outcome.canonical_bytes()
    report_identity = _artifact_identity_for_bytes(
        "stage_outcome", report_path, report_payload
    )
    advance(state, parsed_outcome, report_identity)
    provided = tuple(
        (
            identity
            if isinstance(identity, ArtifactIdentity)
            else ArtifactIdentity.from_mapping(identity),
            payload,
        )
        for identity, payload in output_payloads
    )
    if tuple(identity for identity, _ in provided) != parsed_outcome.outputs:
        raise T075OperationalError(
            "output payload identities do not match StageOutcome outputs"
        )
    for identity, payload in provided:
        if not isinstance(payload, bytes):
            raise TypeError("output payloads must be bytes")
        if (
            hashlib.sha256(payload).hexdigest() != identity.sha256
            or len(payload) != identity.size_bytes
        ):
            raise T075OperationalError("output payload does not match ArtifactIdentity")
    if not parsed_outcome.valid and provided:
        raise T075OperationalError("invalid StageOutcome cannot promote outputs")
    existing = next(
        (
            committed
            for committed in state.committed_outcomes
            if committed.outcome.stage == parsed_outcome.stage
        ),
        None,
    )
    if existing is not None:
        # ``advance`` has already established identical canonical bytes and
        # identity.  Do not rewrite immutable committed files on a retry.
        return persisted
    for identity, payload in provided:
        _atomic_write(
            repository_root, _repository_path(repository_root, identity), payload
        )
    if interrupt_before_outcome:
        raise T075CommitInterrupted(
            "normative outputs promoted without a committed StageOutcome marker"
        )
    report_file = _repository_path(repository_root, report_identity)
    if report_file.exists():
        if report_file.read_bytes() != report_payload:
            raise T075OperationalError(
                "existing T075 outcome conflicts with canonical outcome"
            )
    else:
        _atomic_write(repository_root, report_file, report_payload)
    return reconstruct_t075_state(repository_root, state.run_head)


def _write_t075_payload(
    repository_root: Path, role: str, filename: str, payload: bytes
) -> ArtifactIdentity:
    identity = _artifact_identity_for_bytes(
        role, _expected_output_path("", filename), payload
    )
    _atomic_write(repository_root, _repository_path(repository_root, identity), payload)
    return identity


def _t075_payload_identity(
    role: str, filename: str, payload: bytes
) -> ArtifactIdentity:
    return _artifact_identity_for_bytes(
        role, _expected_output_path("", filename), payload
    )


def _stage_payload_outcome(
    state: AcceptanceState,
    repository_root: Path,
    *,
    stage: str,
    parents: Sequence[ArtifactIdentity],
    payloads: Sequence[tuple[str, bytes]],
    valid: bool = True,
    passed: bool = True,
    failure_code: str | None = None,
) -> AcceptanceState:
    expected_layout = T075_OUTPUT_LAYOUT[stage] if valid else ()
    if tuple(role for role, _ in payloads) != tuple(
        role for role, _ in expected_layout
    ):
        raise T075OperationalError(
            "stage adapter payload roles do not match frozen layout"
        )
    identities = tuple(
        _t075_payload_identity(role, filename, payload)
        for (role, payload), (_, filename) in zip(
            payloads, expected_layout, strict=True
        )
    )
    outcome = StageOutcome(
        run_head=state.run_head,
        stage=stage,
        valid=valid,
        passed=passed,
        parents=tuple(parents),
        outputs=identities,
        failure_code=failure_code,
    )
    return atomic_commit_stage(
        state,
        outcome,
        repository_root,
        tuple(zip(identities, (payload for _, payload in payloads), strict=True)),
    )


def select_t075_source_candidates(
    candidates: Iterable[Any],
    *,
    run_head: str,
) -> tuple[tuple[Any, ...], dict[str, Any]]:
    """Apply T075 global replay ownership before the frozen quotas.

    ``T065SourceState`` remains the source row type.  This function adds only
    the approved ownership step and emits the T075 ownership audit; it does
    not alter the source reader, split ranges, replay key, or downstream
    payload schemas.
    """

    from sts_combat_rl.sim.non_combat_learning import (
        T065_MANDATORY_FAMILIES,
        T065_SELECTION_DOMAIN,
        T065_SPLIT_QUOTAS,
        T065_SPLITS,
        canonical_source_candidate,
        replay_equivalence_key,
        split_for_source_seed,
    )

    _git_commit(run_head, "T075 selection run_head")
    admitted: list[dict[str, Any]] = []
    for row_index, candidate in enumerate(candidates):
        if candidate.family not in T065_MANDATORY_FAMILIES or not candidate.terminal:
            continue
        if (
            candidate.split not in T065_SPLITS
            or split_for_source_seed(candidate.simulator_seed) != candidate.split
        ):
            raise T075StageClassificationError(
                "SELECTION_REPLAY_INVALID",
                f"candidate {row_index} has an invalid frozen seed split",
            )
        candidate_json = canonical_source_candidate(candidate)
        payload = canonical_json_bytes(candidate_json)
        selection_digest = hashlib.sha256(T065_SELECTION_DOMAIN + payload).hexdigest()
        replay_key = replay_equivalence_key(candidate)
        group_key = {
            "family": candidate.family,
            "public_state_identity": candidate.public_state_identity,
            "ordered_legal_action_identities": [
                dict(item) for item in candidate.legal_action_identities
            ],
        }
        group_digest = hashlib.sha256(
            b"T075-replay-group-v1\n" + canonical_json_bytes(group_key)
        ).hexdigest()
        admitted.append(
            {
                "row_index": row_index,
                "candidate": candidate,
                "candidate_json": candidate_json,
                "payload": payload,
                "candidate_sha256": hashlib.sha256(payload).hexdigest(),
                "selection_digest": selection_digest,
                "member_order": (selection_digest, payload),
                "replay_key": replay_key,
                "group_digest": group_digest,
            }
        )

    groups: dict[tuple[Any, ...], list[dict[str, Any]]] = {}
    for member in admitted:
        group = groups.setdefault(member["replay_key"], [])
        if any(
            prior["member_order"] == member["member_order"]
            and prior["row_index"] != member["row_index"]
            for prior in group
        ):
            raise T075StageClassificationError(
                "SELECTION_MEMBER_ORDER_TIE",
                "distinct replay-equivalent rows have an identical member-order key",
            )
        group.append(member)

    owners: list[dict[str, Any]] = []
    audit_groups: list[dict[str, Any]] = []
    cross_split_group_count = 0
    for group in groups.values():
        ordered = sorted(group, key=lambda member: member["member_order"])
        if len({member["candidate"].split for member in ordered}) > 1:
            cross_split_group_count += 1
        owner = ordered[0]
        owners.append(owner)
        audit_groups.append(
            {
                "group_digest": owner["group_digest"],
                "family": owner["candidate"].family,
                "members": [
                    {
                        "source_arm": member["candidate"].source_arm,
                        "simulator_seed": member["candidate"].simulator_seed,
                        "split": member["candidate"].split,
                        "selection_digest": member["selection_digest"],
                        "candidate_sha256": member["candidate_sha256"],
                        "owner": member is owner,
                    }
                    for member in ordered
                ],
            }
        )
    audit_groups.sort(key=lambda group: group["group_digest"])

    available: dict[tuple[str, str], list[dict[str, Any]]] = {
        (family, split): []
        for family in T065_MANDATORY_FAMILIES
        for split in T065_SPLITS
    }
    for owner in owners:
        available[(owner["candidate"].family, owner["candidate"].split)].append(owner)
    selected: list[Any] = []
    availability_rows: list[dict[str, Any]] = []
    for family in T065_MANDATORY_FAMILIES:
        for split in T065_SPLITS:
            bucket = sorted(
                available[(family, split)], key=lambda member: member["member_order"]
            )
            availability_rows.append(
                {"family": family, "split": split, "count": len(bucket)}
            )
            quota = T065_SPLIT_QUOTAS[split]
            if len(bucket) < quota:
                raise T075StageClassificationError(
                    "SELECTION_OWNER_QUOTA_SHORTAGE",
                    f"{family}/{split} has {len(bucket)} owners, requires {quota}",
                )
            for member in bucket[:quota]:
                selected.append(
                    replace(
                        member["candidate"],
                        selected_state_index=len(selected),
                        selection_digest=member["selection_digest"],
                        selection_canonical_json=member["payload"].decode("utf-8"),
                    )
                )
    audit = {
        "schema_id": "t075-ownership-audit-v1",
        "schema_version": 1,
        "task_id": T075_TASK_ID,
        "run_head": run_head,
        "strategy_id": "leakage-safe-global-owner-v1",
        "replay_group_domain": "T075-replay-group-v1",
        "raw_candidate_count": len(admitted),
        "group_count": len(groups),
        "cross_split_group_count": cross_split_group_count,
        "excluded_non_owner_count": len(admitted) - len(owners),
        "available_after_ownership": availability_rows,
        "groups": audit_groups,
    }
    validate_t075_ownership_audit(audit)
    return tuple(selected), audit


def _committed_output(
    state: AcceptanceState, role: str, filename: str
) -> ArtifactIdentity:
    return _find_identity(artifact_index(state), role, filename)


def _committed_report(state: AcceptanceState, stage: str) -> ArtifactIdentity:
    return _find_identity(
        artifact_index(state),
        "stage_outcome",
        f"outcomes/{T075_OUTCOME_FILENAMES[stage]}",
    )


def _read_committed_json(
    repository_root: Path, identity: ArtifactIdentity, label: str
) -> Mapping[str, Any]:
    path = _repository_path(repository_root, identity)
    try:
        payload = path.read_bytes()
    except OSError as exc:
        raise T075OperationalError(f"{label} committed payload is unreadable") from exc
    if (
        len(payload) != identity.size_bytes
        or hashlib.sha256(payload).hexdigest() != identity.sha256
    ):
        raise T075OperationalError(f"{label} committed payload identity is stale")
    try:
        value = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise T075OperationalError(
            f"{label} committed payload is invalid JSON"
        ) from exc
    if not isinstance(value, Mapping) or canonical_json_document(value) != payload:
        raise T075OperationalError(f"{label} committed payload is not canonical JSON")
    return value


def _selected_training_checkpoint(
    state: AcceptanceState, repository_root: Path
) -> tuple[ArtifactIdentity, ArtifactIdentity]:
    selection_identity = _committed_output(
        state, "training_selection", "training-selection.json"
    )
    selection = validate_t075_training_selection(
        _read_committed_json(
            repository_root, selection_identity, "training-selection summary"
        )
    )
    _require_matching_run_head(selection, state, "training-selection summary")
    selected_checkpoint = _identity_tuple((selection["selected_checkpoint"],))[0]
    train = next(
        committed
        for committed in state.committed_outcomes
        if committed.outcome.stage == "TRAIN"
    )
    committed_checkpoints = tuple(
        identity for identity in train.outcome.outputs if identity.role == "checkpoint"
    )
    summary_checkpoints = _identity_tuple(selection["checkpoints"])
    if summary_checkpoints != committed_checkpoints:
        raise T075OperationalError(
            "training-selection checkpoints do not match committed TRAIN outputs"
        )
    if selected_checkpoint not in committed_checkpoints:
        raise T075OperationalError(
            "selected training checkpoint is not a committed TRAIN output"
        )
    return selection_identity, selected_checkpoint


def _read_t065_payload(payload: bytes, reader: Any, label: str) -> Any:
    """Run an existing T065 path reader against an in-memory command payload."""

    if not isinstance(payload, bytes):
        raise TypeError(f"{label} payload must be bytes")
    with tempfile.TemporaryDirectory(prefix="t075-t065-") as temporary_directory:
        path = Path(temporary_directory) / "payload.json"
        path.write_bytes(payload)
        return reader(path)


def _invalid_t075_evidence(
    state: AcceptanceState,
    repository_root: Path,
    *,
    stage: str,
    parents: Sequence[ArtifactIdentity],
    failure_code: str,
) -> AcceptanceState:
    return _stage_payload_outcome(
        state,
        repository_root,
        stage=stage,
        parents=parents,
        payloads=(),
        valid=False,
        passed=False,
        failure_code=failure_code,
    )


def run_t075_preflight(
    state: AcceptanceState,
    audit: Mapping[str, Any] | None,
    repository_root: Path,
    *,
    valid: bool = True,
    failure_code: str | None = None,
) -> AcceptanceState:
    if not valid:
        if failure_code != "PREFLIGHT_INVALID":
            raise T075OperationalError(
                "invalid T075 preflight requires PREFLIGHT_INVALID failure code"
            )
        return _stage_payload_outcome(
            state,
            repository_root,
            stage="PREFLIGHT",
            parents=(),
            payloads=(),
            valid=False,
            passed=False,
            failure_code=failure_code,
        )
    if audit is None:
        raise T075OperationalError("valid T075 preflight requires an audit")
    validate_t075_preflight_audit(audit)
    _require_matching_run_head(audit, state, "preflight audit")
    return _stage_payload_outcome(
        state,
        repository_root,
        stage="PREFLIGHT",
        parents=(),
        payloads=(("preflight_audit", canonical_json_document(audit)),),
    )


def run_t075_validate_reuse(
    state: AcceptanceState,
    audit: Mapping[str, Any] | None,
    repository_root: Path,
    *,
    valid: bool = True,
    failure_code: str | None = None,
) -> AcceptanceState:
    if not valid:
        if failure_code != "SOURCE_REUSE_INVALID":
            raise T075OperationalError(
                "invalid T075 source reuse requires SOURCE_REUSE_INVALID failure code"
            )
        return _stage_payload_outcome(
            state,
            repository_root,
            stage="SOURCE_REUSE",
            parents=(
                _committed_output(state, "preflight_audit", "preflight-audit.json"),
            ),
            payloads=(),
            valid=False,
            passed=False,
            failure_code=failure_code,
        )
    if audit is None:
        raise T075OperationalError("valid T075 source reuse requires an audit")
    validate_t075_source_reuse_audit(audit)
    _require_matching_run_head(audit, state, "source-reuse audit")
    return _stage_payload_outcome(
        state,
        repository_root,
        stage="SOURCE_REUSE",
        parents=(
            _committed_output(state, "preflight_audit", "preflight-audit.json"),
            *_identity_tuple(audit["sources"]),
        ),
        payloads=(("source_reuse_audit", canonical_json_document(audit)),),
    )


def run_t075_selection(
    state: AcceptanceState,
    ownership_audit: Mapping[str, Any] | None,
    selected_states_payload: bytes | None,
    repository_root: Path,
    *,
    valid: bool = True,
    failure_code: str | None = None,
) -> AcceptanceState:
    if not valid:
        if failure_code not in {
            "SELECTION_MEMBER_ORDER_TIE",
            "SELECTION_OWNER_QUOTA_SHORTAGE",
            "SELECTION_REPLAY_INVALID",
        }:
            raise T075OperationalError(
                "invalid T075 selection requires a selection failure code"
            )
        return _stage_payload_outcome(
            state,
            repository_root,
            stage="SELECTION_REPLAY",
            parents=(
                _committed_output(
                    state, "source_reuse_audit", "source-reuse-audit.json"
                ),
            ),
            payloads=(),
            valid=False,
            passed=False,
            failure_code=failure_code,
        )
    if ownership_audit is None or selected_states_payload is None:
        raise T075OperationalError(
            "valid T075 selection requires audit and selected states"
        )
    validate_t075_ownership_audit(ownership_audit)
    _require_matching_run_head(ownership_audit, state, "ownership audit")
    return _stage_payload_outcome(
        state,
        repository_root,
        stage="SELECTION_REPLAY",
        parents=(
            _committed_output(state, "source_reuse_audit", "source-reuse-audit.json"),
        ),
        payloads=(
            ("ownership_audit", canonical_json_document(ownership_audit)),
            ("selected_states", selected_states_payload),
        ),
    )


def run_t075_target(
    state: AcceptanceState,
    target_table_payload: bytes | None,
    repository_root: Path,
    *,
    valid: bool = True,
    failure_code: str | None = None,
) -> AcceptanceState:
    parents = (
        _committed_output(state, "preflight_audit", "preflight-audit.json"),
        _committed_output(state, "selected_states", "selected-states.jsonl"),
    )
    if not valid:
        if target_table_payload is not None:
            raise T075OperationalError(
                "invalid target adapter cannot carry scientific evidence"
            )
        if failure_code != "TARGET_INVALID":
            raise T075OperationalError(
                "invalid T075 target requires TARGET_INVALID failure code"
            )
        return _invalid_t075_evidence(
            state,
            repository_root,
            stage="TARGET",
            parents=parents,
            failure_code=failure_code,
        )
    if failure_code is not None:
        raise T075OperationalError("valid target adapter cannot carry a failure code")
    if target_table_payload is None:
        return _invalid_t075_evidence(
            state,
            repository_root,
            stage="TARGET",
            parents=parents,
            failure_code="TARGET_INVALID",
        )
    try:
        from sts_combat_rl.sim.non_combat_learning import read_target_table

        _read_t065_payload(target_table_payload, read_target_table, "T065 target table")
    except (AttributeError, IndexError, KeyError, OSError, TypeError, ValueError):
        return _invalid_t075_evidence(
            state,
            repository_root,
            stage="TARGET",
            parents=parents,
            failure_code="TARGET_INVALID",
        )
    return _stage_payload_outcome(
        state,
        repository_root,
        stage="TARGET",
        parents=parents,
        payloads=(("target_table", target_table_payload),),
        valid=True,
        passed=True,
        failure_code=failure_code,
    )


def run_t075_train(
    state: AcceptanceState,
    checkpoint_payloads: tuple[bytes, bytes] | None,
    training_selection: Mapping[str, Any] | None,
    repository_root: Path,
    *,
    valid: bool = True,
    failure_code: str | None = None,
) -> AcceptanceState:
    parents = (_committed_output(state, "target_table", "target-table.json"),)
    if not valid:
        if checkpoint_payloads is not None or training_selection is not None:
            raise T075OperationalError(
                "invalid train adapter cannot carry checkpoint or selection evidence"
            )
        if failure_code != "TRAIN_INVALID":
            raise T075OperationalError(
                "invalid T075 train requires TRAIN_INVALID failure code"
            )
        return _stage_payload_outcome(
            state,
            repository_root,
            stage="TRAIN",
            parents=parents,
            payloads=(),
            valid=False,
            passed=False,
            failure_code=failure_code,
        )
    if failure_code is not None:
        raise T075OperationalError("valid T075 train cannot carry a failure code")
    if checkpoint_payloads is None or training_selection is None:
        return _invalid_t075_evidence(
            state,
            repository_root,
            stage="TRAIN",
            parents=parents,
            failure_code="TRAIN_INVALID",
        )
    try:
        if len(checkpoint_payloads) != 2:
            raise ValueError("TRAIN requires exactly two checkpoint payloads")
        from sts_combat_rl.sim.non_combat_learning import (
            T065_MODEL_SEEDS,
            load_non_combat_checkpoint,
            select_validation_checkpoint,
        )

        expected_checkpoints = tuple(
            _t075_payload_identity("checkpoint", filename, payload)
            for (_, filename), payload in zip(
                T075_OUTPUT_LAYOUT["TRAIN"][:2], checkpoint_payloads, strict=True
            )
        )
        loaded_runs = tuple(
            _read_t065_payload(
                payload,
                load_non_combat_checkpoint,
                f"T065 checkpoint {model_seed}",
            )
            for model_seed, payload in zip(
                T065_MODEL_SEEDS, checkpoint_payloads, strict=True
            )
        )
        if tuple(run.model_seed for run in loaded_runs) != T065_MODEL_SEEDS:
            raise ValueError("TRAIN checkpoints must use both frozen T065 model seeds")
        if any(
            run.checkpoint_artifact_id != identity.sha256
            for run, identity in zip(loaded_runs, expected_checkpoints, strict=True)
        ):
            raise ValueError("T065 checkpoint loader identity does not match payload")
        selected_run = select_validation_checkpoint(loaded_runs)
        selection = validate_t075_training_selection(training_selection)
        _require_matching_run_head(selection, state, "training-selection summary")
        if _identity_tuple(selection["checkpoints"]) != expected_checkpoints:
            raise ValueError(
                "training-selection checkpoints do not match checkpoint payload identities"
            )
        expected_validation_mae = [run.validation_mae for run in loaded_runs]
        if selection["validation_mae"] != expected_validation_mae:
            raise ValueError(
                "training-selection validation MAE does not match T065 checkpoints"
            )
        if selection["selected_model_seed"] != selected_run.model_seed:
            raise ValueError(
                "training-selection selected model does not match T065 selection"
            )
        selected_index = T065_MODEL_SEEDS.index(selected_run.model_seed)
        expected_selected_checkpoint = expected_checkpoints[selected_index]
        if (
            _identity_tuple((selection["selected_checkpoint"],))[0]
            != expected_selected_checkpoint
        ):
            raise ValueError(
                "training-selection selected checkpoint does not match T065 selection"
            )
        derived_selection = dict(selection)
        derived_selection.update(
            {
                "validation_mae": expected_validation_mae,
                "selected_model_seed": selected_run.model_seed,
                "selected_checkpoint": expected_selected_checkpoint.to_dict(),
            }
        )
        validate_t075_training_selection(derived_selection)
    except (
        AttributeError,
        EOFError,
        IndexError,
        KeyError,
        ModuleNotFoundError,
        OSError,
        OverflowError,
        pickle.UnpicklingError,
        RuntimeError,
        TypeError,
        ValueError,
    ):
        return _invalid_t075_evidence(
            state,
            repository_root,
            stage="TRAIN",
            parents=parents,
            failure_code="TRAIN_INVALID",
        )
    return _stage_payload_outcome(
        state,
        repository_root,
        stage="TRAIN",
        parents=parents,
        payloads=(
            ("checkpoint", checkpoint_payloads[0]),
            ("checkpoint", checkpoint_payloads[1]),
            ("training_selection", canonical_json_document(derived_selection)),
        ),
    )


def run_t075_gate(
    state: AcceptanceState,
    stage5_report_payload: bytes | None,
    repository_root: Path,
    *,
    passed: bool | None = None,
    valid: bool = True,
    failure_code: str | None = None,
) -> AcceptanceState:
    if not valid:
        if stage5_report_payload is not None:
            raise T075OperationalError(
                "invalid gate adapter cannot carry scientific evidence"
            )
        if passed is not None:
            raise T075OperationalError(
                "invalid gate adapter cannot carry a passed/failed assertion"
            )
        if failure_code != "GATE_EVIDENCE_INVALID":
            raise T075OperationalError(
                "invalid T075 gate requires GATE_EVIDENCE_INVALID failure code"
            )
    elif failure_code is not None:
        raise T075OperationalError("valid gate adapter cannot carry a failure code")
    _, selected_checkpoint = _selected_training_checkpoint(state, repository_root)
    parents = (
        _committed_output(state, "target_table", "target-table.json"),
        _committed_output(state, "training_selection", "training-selection.json"),
        selected_checkpoint,
    )
    if not valid:
        return _invalid_t075_evidence(
            state,
            repository_root,
            stage="GATE",
            parents=parents,
            failure_code=failure_code,
        )
    if stage5_report_payload is None:
        return _invalid_t075_evidence(
            state,
            repository_root,
            stage="GATE",
            parents=parents,
            failure_code="GATE_EVIDENCE_INVALID",
        )
    try:
        from sts_combat_rl.sim.non_combat_learning import read_t065_stage5_report

        stage5_report = _read_t065_payload(
            stage5_report_payload,
            read_t065_stage5_report,
            "T065 Stage-5 report",
        )
    except (AttributeError, IndexError, KeyError, OSError, TypeError, ValueError):
        return _invalid_t075_evidence(
            state,
            repository_root,
            stage="GATE",
            parents=parents,
            failure_code="GATE_EVIDENCE_INVALID",
        )
    return _stage_payload_outcome(
        state,
        repository_root,
        stage="GATE",
        parents=parents,
        payloads=(("stage5_report", stage5_report_payload),),
        valid=True,
        passed=stage5_report.passed,
        failure_code=failure_code,
    )


def run_t075_eval(
    state: AcceptanceState,
    stage6_report_payload: bytes | None,
    repository_root: Path,
    *,
    passed: bool | None = None,
    valid: bool = True,
    failure_code: str | None = None,
) -> AcceptanceState:
    if not valid:
        if stage6_report_payload is not None:
            raise T075OperationalError(
                "invalid eval adapter cannot carry scientific evidence"
            )
        if passed is not None:
            raise T075OperationalError(
                "invalid eval adapter cannot carry a passed/failed assertion"
            )
        if failure_code != "EVAL_EVIDENCE_INVALID":
            raise T075OperationalError(
                "invalid T075 eval requires EVAL_EVIDENCE_INVALID failure code"
            )
    elif failure_code is not None:
        raise T075OperationalError("valid eval adapter cannot carry a failure code")
    _, selected_checkpoint = _selected_training_checkpoint(state, repository_root)
    parents = (
        _committed_output(state, "stage5_report", "heldout-gate-report.json"),
        _committed_output(state, "training_selection", "training-selection.json"),
        selected_checkpoint,
    )
    if not valid:
        return _invalid_t075_evidence(
            state,
            repository_root,
            stage="EVAL",
            parents=parents,
            failure_code=failure_code,
        )
    if stage6_report_payload is None:
        return _invalid_t075_evidence(
            state,
            repository_root,
            stage="EVAL",
            parents=parents,
            failure_code="EVAL_EVIDENCE_INVALID",
        )
    try:
        from sts_combat_rl.sim.non_combat_learning import read_t065_stage6_report

        stage6_report = _read_t065_payload(
            stage6_report_payload,
            read_t065_stage6_report,
            "T065 Stage-6 report",
        )
    except (AttributeError, IndexError, KeyError, OSError, TypeError, ValueError):
        return _invalid_t075_evidence(
            state,
            repository_root,
            stage="EVAL",
            parents=parents,
            failure_code="EVAL_EVIDENCE_INVALID",
        )
    return _stage_payload_outcome(
        state,
        repository_root,
        stage="EVAL",
        parents=parents,
        payloads=(("stage6_report", stage6_report_payload),),
        valid=True,
        passed=stage6_report.passed,
        failure_code=failure_code,
    )


def validate_t075_preflight_audit(value: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise TypeError("T075 preflight audit must be an object")
    keys = {
        "schema_id",
        "schema_version",
        "task_id",
        "run_head",
        "recovery_base",
        "t065_approved_spec",
        "sts_lightspeed_integration",
        "model_input_schema_id",
        "state_dim",
        "action_dim",
        "checks_passed",
    }
    _strict_keys(value, keys, "T075 preflight audit")
    if value["schema_id"] != "t075-preflight-audit-v1" or value["schema_version"] != 1:
        raise ValueError("T075 preflight audit schema is invalid")
    if value["task_id"] != T075_TASK_ID:
        raise ValueError("T075 preflight audit task id is invalid")
    _git_commit(value["run_head"], "T075 preflight audit run_head")
    expected_identities = {
        "recovery_base": T075_RECOVERY_BASE,
        "t065_approved_spec": T075_APPROVED_SPEC_COMMIT,
        "sts_lightspeed_integration": T075_STS_LIGHTSPEED_INTEGRATION,
    }
    for field_name, expected in expected_identities.items():
        if value[field_name] != expected:
            raise ValueError(
                f"T075 preflight audit {field_name} does not match the frozen identity"
            )
    if value["model_input_schema_id"] != "non-combat-model-input-v1":
        raise ValueError("T075 preflight model-input schema is invalid")
    if value["state_dim"] != 4737 or value["action_dim"] != 92:
        raise ValueError("T075 preflight dimensions are invalid")
    if value["checks_passed"] != list(T075_PREFLIGHT_CHECKS):
        raise ValueError("T075 preflight checks_passed is not the frozen list")
    return dict(value)


def validate_t075_source_reuse_audit(value: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise TypeError("T075 source-reuse audit must be an object")
    _strict_keys(
        value,
        {
            "schema_id",
            "schema_version",
            "task_id",
            "run_head",
            "sources",
            "strict_reader_passed",
            "metadata_passed",
        },
        "T075 source-reuse audit",
    )
    if (
        value["schema_id"] != "t075-source-reuse-audit-v1"
        or value["schema_version"] != 1
    ):
        raise ValueError("T075 source-reuse audit schema is invalid")
    if value["task_id"] != T075_TASK_ID:
        raise ValueError("T075 source-reuse audit task id is invalid")
    _git_commit(value["run_head"], "T075 source-reuse audit run_head")
    if not isinstance(value["sources"], list) or _identity_tuple(
        value["sources"]
    ) != _identity_tuple(T075_SOURCE_IDENTITIES):
        raise ValueError("T075 source-reuse source identities are not exact")
    if (
        value["strict_reader_passed"] is not True
        or value["metadata_passed"] is not True
    ):
        raise ValueError("T075 source-reuse checks must both pass")
    return dict(value)


def _validate_digest(value: Any, label: str) -> str:
    if not isinstance(value, str) or not _SHA256_RE.fullmatch(value):
        raise ValueError(f"{label} must be a lowercase SHA-256 digest")
    return value


def validate_t075_ownership_audit(value: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise TypeError("T075 ownership audit must be an object")
    _strict_keys(
        value,
        {
            "schema_id",
            "schema_version",
            "task_id",
            "run_head",
            "strategy_id",
            "replay_group_domain",
            "raw_candidate_count",
            "group_count",
            "cross_split_group_count",
            "excluded_non_owner_count",
            "available_after_ownership",
            "groups",
        },
        "T075 ownership audit",
    )
    if value["schema_id"] != "t075-ownership-audit-v1" or value["schema_version"] != 1:
        raise ValueError("T075 ownership audit schema is invalid")
    if (
        value["task_id"] != T075_TASK_ID
        or value["strategy_id"] != "leakage-safe-global-owner-v1"
    ):
        raise ValueError("T075 ownership audit identity is invalid")
    if value["replay_group_domain"] != "T075-replay-group-v1":
        raise ValueError("T075 ownership audit replay domain is invalid")
    _git_commit(value["run_head"], "T075 ownership audit run_head")
    for field_name in (
        "raw_candidate_count",
        "group_count",
        "cross_split_group_count",
        "excluded_non_owner_count",
    ):
        _integer(value[field_name], f"T075 ownership audit {field_name}", minimum=0)
    if not isinstance(value["available_after_ownership"], list) or not isinstance(
        value["groups"], list
    ):
        raise TypeError("T075 ownership audit arrays are invalid")
    expected_families = ("MAP_SCREEN", "REST_ROOM", "REWARDS", "TREASURE_ROOM")
    expected_buckets = [
        (family, split)
        for family in expected_families
        for split in ("train", "validation", "heldout")
    ]
    observed_buckets: list[tuple[str, str]] = []
    for item in value["available_after_ownership"]:
        if not isinstance(item, Mapping):
            raise TypeError("T075 ownership availability row is not an object")
        _strict_keys(item, {"family", "split", "count"}, "T075 availability row")
        if item["family"] not in expected_families or item["split"] not in {
            "train",
            "validation",
            "heldout",
        }:
            raise ValueError("T075 availability stratum is invalid")
        _integer(item["count"], "T075 availability count", minimum=0)
        observed_buckets.append((item["family"], item["split"]))
    if observed_buckets != expected_buckets:
        raise ValueError("T075 availability rows are not in frozen family/split order")
    for group in value["groups"]:
        if not isinstance(group, Mapping):
            raise TypeError("T075 ownership group is not an object")
        _strict_keys(
            group, {"group_digest", "family", "members"}, "T075 ownership group"
        )
        _validate_digest(group["group_digest"], "T075 ownership group_digest")
        if group["family"] not in expected_families or not isinstance(
            group["members"], list
        ):
            raise ValueError("T075 ownership group identity is invalid")
        owners = 0
        for member in group["members"]:
            if not isinstance(member, Mapping):
                raise TypeError("T075 ownership member is not an object")
            _strict_keys(
                member,
                {
                    "source_arm",
                    "simulator_seed",
                    "split",
                    "selection_digest",
                    "candidate_sha256",
                    "owner",
                },
                "T075 ownership member",
            )
            if member["source_arm"] not in {
                "stochastic_non_combat_v1",
                "expert_non_combat_v1",
            }:
                raise ValueError("T075 ownership member source arm is invalid")
            _integer(member["simulator_seed"], "T075 ownership member seed")
            if member["split"] not in {"train", "validation", "heldout"}:
                raise ValueError("T075 ownership member split is invalid")
            _validate_digest(
                member["selection_digest"], "T075 ownership selection_digest"
            )
            _validate_digest(
                member["candidate_sha256"], "T075 ownership candidate_sha256"
            )
            owners += int(_boolean(member["owner"], "T075 ownership member owner"))
        if owners != 1:
            raise ValueError("each T075 ownership group must have exactly one owner")
    if value["group_count"] != len(value["groups"]):
        raise ValueError("T075 ownership group_count is inconsistent")
    return dict(value)


def validate_t075_training_selection(value: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise TypeError("T075 training-selection summary must be an object")
    _strict_keys(
        value,
        {
            "schema_id",
            "schema_version",
            "task_id",
            "run_head",
            "model_seeds",
            "checkpoints",
            "validation_mae",
            "selected_model_seed",
            "selected_checkpoint",
        },
        "T075 training-selection summary",
    )
    if (
        value["schema_id"] != "t075-training-selection-v1"
        or value["schema_version"] != 1
    ):
        raise ValueError("T075 training-selection schema is invalid")
    if value["task_id"] != T075_TASK_ID:
        raise ValueError("T075 training-selection task id is invalid")
    _git_commit(value["run_head"], "T075 training-selection run_head")
    if (
        value["model_seeds"] != [653001, 653002]
        or not isinstance(value["checkpoints"], list)
        or len(value["checkpoints"]) != 2
    ):
        raise ValueError("T075 training-selection seed/checkpoint arrays are invalid")
    checkpoints = _identity_tuple(value["checkpoints"])
    if any(identity.role != "checkpoint" for identity in checkpoints):
        raise ValueError("T075 training-selection checkpoint roles are invalid")
    if (
        not isinstance(value["validation_mae"], list)
        or len(value["validation_mae"]) != 2
    ):
        raise ValueError("T075 training-selection MAE array is invalid")
    if any(
        isinstance(mae, bool)
        or not isinstance(mae, (int, float))
        or not math.isfinite(float(mae))
        for mae in value["validation_mae"]
    ):
        raise ValueError("T075 training-selection MAE must be finite")
    if value["selected_model_seed"] not in {653001, 653002}:
        raise ValueError("T075 selected model seed is invalid")
    if (
        _identity_tuple((value["selected_checkpoint"],))[0]
        != checkpoints[value["model_seeds"].index(value["selected_model_seed"])]
    ):
        raise ValueError("T075 selected checkpoint does not match selected model seed")
    if (
        value["validation_mae"][0] == value["validation_mae"][1]
        and value["selected_model_seed"] != 653001
    ):
        raise ValueError("T075 tied validation MAE must select seed 653001")
    if (
        value["validation_mae"][0] < value["validation_mae"][1]
        and value["selected_model_seed"] != 653001
    ):
        raise ValueError("T075 lower validation MAE must select seed 653001")
    if (
        value["validation_mae"][1] < value["validation_mae"][0]
        and value["selected_model_seed"] != 653002
    ):
        raise ValueError("T075 lower validation MAE must select seed 653002")
    return dict(value)


def validate_t075_terminal_decision(
    value: Mapping[str, Any],
    *,
    expected_stage_outcomes: Sequence[ArtifactIdentity] | None = None,
) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise TypeError("T075 terminal decision must be an object")
    _strict_keys(
        value,
        {
            "schema_id",
            "schema_version",
            "task_id",
            "run_head",
            "terminal_case",
            "terminal_stage",
            "stage_outcomes",
            "promotion",
            "recommendation_code",
        },
        "T075 terminal decision",
    )
    if (
        value["schema_id"] != "t075-terminal-decision-v1"
        or value["schema_version"] != 1
    ):
        raise ValueError("T075 terminal decision schema is invalid")
    if value["task_id"] != T075_TASK_ID:
        raise ValueError("T075 terminal decision task id is invalid")
    _git_commit(value["run_head"], "T075 terminal decision run_head")
    if (
        value["terminal_case"] not in T075_TERMINAL_MAPPING
        or value["terminal_stage"] not in T075_STAGES
    ):
        raise ValueError("T075 terminal decision case/stage is invalid")
    if not isinstance(value["stage_outcomes"], list):
        raise TypeError("T075 terminal stage_outcomes must be an array")
    stage_outcomes = _identity_tuple(value["stage_outcomes"])
    if not stage_outcomes or len(stage_outcomes) > len(T075_STAGES):
        raise ValueError("T075 terminal stage_outcomes must be a non-empty prefix")
    expected_paths = tuple(
        _expected_report_path(stage) for stage in T075_STAGES[: len(stage_outcomes)]
    )
    if tuple(identity.path for identity in stage_outcomes) != expected_paths:
        raise ValueError("T075 terminal stage_outcomes are not a canonical prefix")
    if any(identity.role != "stage_outcome" for identity in stage_outcomes):
        raise ValueError("T075 terminal stage outcome roles are invalid")
    if value["terminal_stage"] != T075_STAGES[len(stage_outcomes) - 1]:
        raise ValueError("T075 terminal stage does not match stage_outcomes prefix")
    if value["terminal_case"] in {"A", "B"} and value["terminal_stage"] != "EVAL":
        raise ValueError("A/B terminal decisions must terminate at EVAL")
    if value["terminal_case"] == "C" and value["terminal_stage"] != "GATE":
        raise ValueError("C terminal decisions must terminate at GATE")
    if expected_stage_outcomes is not None and stage_outcomes != tuple(
        expected_stage_outcomes
    ):
        raise ValueError("T075 terminal stage_outcomes do not match committed state")
    promotion, recommendation = T075_TERMINAL_MAPPING[value["terminal_case"]]
    if (
        value["promotion"] != promotion
        or value["recommendation_code"] != recommendation
    ):
        raise ValueError("T075 terminal decision mapping is invalid")
    return dict(value)


def terminal_decision_from_state(
    state: AcceptanceState,
    terminal_report_identity: ArtifactIdentity | Mapping[str, Any],
) -> dict[str, Any]:
    if state.terminal_case is None or state.terminal_stage is None:
        raise T075OperationalError("cannot finalize a non-terminal T075 state")
    terminal_identity = (
        terminal_report_identity
        if isinstance(terminal_report_identity, ArtifactIdentity)
        else ArtifactIdentity.from_mapping(terminal_report_identity)
    )
    if terminal_identity.role != "terminal_report":
        raise T075OperationalError("terminal report identity role is invalid")
    promotion, recommendation = T075_TERMINAL_MAPPING[state.terminal_case]
    return {
        "schema_id": "t075-terminal-decision-v1",
        "schema_version": 1,
        "task_id": T075_TASK_ID,
        "run_head": state.run_head,
        "terminal_case": state.terminal_case,
        "terminal_stage": state.terminal_stage,
        "stage_outcomes": [
            committed.report_identity.to_dict()
            for committed in state.committed_outcomes
        ],
        "promotion": promotion,
        "recommendation_code": recommendation,
    }


def expected_retention_artifacts(
    state: AcceptanceState, terminal_report_identity: ArtifactIdentity
) -> tuple[ArtifactIdentity, ...]:
    identities: list[ArtifactIdentity] = list(_identity_tuple(T075_SOURCE_IDENTITIES))
    for committed in state.committed_outcomes:
        identities.append(committed.report_identity)
        if committed.outcome.valid:
            identities.extend(committed.outcome.outputs)
    identities.append(terminal_report_identity)
    return tuple(identities)


def validate_t075_retention_manifest(
    value: Mapping[str, Any],
    *,
    expected_artifacts: Sequence[ArtifactIdentity] | None = None,
) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise TypeError("T075 retention manifest must be an object")
    _strict_keys(
        value,
        {
            "schema_id",
            "schema_version",
            "task_id",
            "run_head",
            "terminal_case",
            "terminal_report",
            "retention_owner",
            "retention_reason",
            "possible_downstream_consumers",
            "deletion_condition_code",
            "entries",
        },
        "T075 retention manifest",
    )
    if value["schema_id"] != "t075-retention-v1" or value["schema_version"] != 1:
        raise ValueError("T075 retention schema is invalid")
    if value["task_id"] != T075_TASK_ID:
        raise ValueError("T075 retention task id is invalid")
    _git_commit(value["run_head"], "T075 retention run_head")
    if value["terminal_case"] not in T075_TERMINAL_MAPPING:
        raise ValueError("T075 retention terminal case is invalid")
    terminal_report = ArtifactIdentity.from_mapping(value["terminal_report"])
    if terminal_report.role != "terminal_report":
        raise ValueError("T075 retention terminal report role is invalid")
    if value["retention_owner"] != "T075":
        raise ValueError("T075 retention owner is invalid")
    _nonempty_string(value["retention_reason"], "T075 retention reason")
    consumers = value["possible_downstream_consumers"]
    if (
        not isinstance(consumers, list)
        or not consumers
        or any(not isinstance(item, str) or not item for item in consumers)
    ):
        raise ValueError("T075 retention consumers are invalid")
    if (
        value["deletion_condition_code"]
        != "after_merge_no_consumer_or_reproduction_hold"
    ):
        raise ValueError("T075 retention deletion condition is invalid")
    if not isinstance(value["entries"], list):
        raise TypeError("T075 retention entries must be an array")
    observed: list[ArtifactIdentity] = []
    for entry in value["entries"]:
        if not isinstance(entry, Mapping):
            raise TypeError("T075 retention entry is not an object")
        _strict_keys(
            entry,
            {
                "artifact",
                "provenance",
                "regeneration_commands",
                "compatibility_requirements",
                "retention_reason",
                "possible_downstream_consumers",
            },
            "T075 retention entry",
        )
        artifact = ArtifactIdentity.from_mapping(entry["artifact"])
        provenance = entry["provenance"]
        if not isinstance(provenance, Mapping):
            raise TypeError("T075 retention provenance is not an object")
        _strict_keys(
            provenance,
            {"source_kind", "producer_task", "producer_stage", "producer_git_commit"},
            "T075 retention provenance",
        )
        if provenance["source_kind"] not in {"reused_t065", "t075_committed_output"}:
            raise ValueError("T075 retention source kind is invalid")
        _nonempty_string(provenance["producer_task"], "T075 producer task")
        _nonempty_string(provenance["producer_stage"], "T075 producer stage")
        _git_commit(provenance["producer_git_commit"], "T075 producer git commit")
        for field_name in (
            "regeneration_commands",
            "compatibility_requirements",
            "possible_downstream_consumers",
        ):
            items = entry[field_name]
            if (
                not isinstance(items, list)
                or not items
                or any(not isinstance(item, str) or not item for item in items)
            ):
                raise ValueError(f"T075 retention {field_name} is invalid")
        _nonempty_string(entry["retention_reason"], "T075 entry retention reason")
        observed.append(artifact)
        frozen_source = T075_REUSED_T065_RETENTION.get(artifact.path)
        if frozen_source is not None:
            for field_name in (
                "source_kind",
                "producer_task",
                "producer_stage",
                "producer_git_commit",
            ):
                if provenance[field_name] != frozen_source[field_name]:
                    raise ValueError(
                        f"T075 reused T065 provenance {field_name} is not frozen"
                    )
            if entry["regeneration_commands"] != frozen_source["regeneration_commands"]:
                raise ValueError(
                    "T075 reused T065 regeneration commands are not frozen"
                )
        elif provenance["source_kind"] != "t075_committed_output":
            raise ValueError(
                "T075-produced retention entries must use t075_committed_output"
            )
    frozen_sources = tuple(_identity_tuple(T075_SOURCE_IDENTITIES))
    if tuple(observed[: len(frozen_sources)]) != frozen_sources:
        raise ValueError("T075 retention entries must begin with exact T065 sources")
    if any(artifact in frozen_sources for artifact in observed[len(frozen_sources) :]):
        raise ValueError("T075 frozen T065 source is duplicated in retention entries")
    if expected_artifacts is not None and tuple(observed) != tuple(expected_artifacts):
        raise ValueError("T075 retention entries do not match committed lineage order")
    return dict(value)


def build_t075_retention_manifest(
    state: AcceptanceState,
    terminal_report_identity: ArtifactIdentity,
    *,
    entry_metadata: Mapping[str, Mapping[str, Any]],
    retention_reason: str,
    possible_downstream_consumers: Sequence[str],
) -> dict[str, Any]:
    expected = expected_retention_artifacts(state, terminal_report_identity)
    entries: list[dict[str, Any]] = []
    for artifact in expected:
        metadata = entry_metadata.get(artifact.path)
        if not isinstance(metadata, Mapping):
            raise T075OperationalError(
                f"retention metadata is missing for {artifact.path}"
            )
        frozen_source = T075_REUSED_T065_RETENTION.get(artifact.path)
        if frozen_source is not None:
            for field_name in (
                "source_kind",
                "producer_task",
                "producer_stage",
                "producer_git_commit",
                "regeneration_commands",
            ):
                if (
                    field_name in metadata
                    and metadata[field_name] != frozen_source[field_name]
                ):
                    raise T075OperationalError(
                        f"retention metadata for {artifact.path} changes frozen "
                        f"T065 {field_name}"
                    )
            source_kind = frozen_source["source_kind"]
            producer_task = frozen_source["producer_task"]
            producer_stage = frozen_source["producer_stage"]
            producer_git_commit = frozen_source["producer_git_commit"]
            regeneration_commands = frozen_source["regeneration_commands"]
        else:
            source_kind = metadata.get("source_kind", "t075_committed_output")
            if source_kind != "t075_committed_output":
                raise T075OperationalError(
                    f"T075 output {artifact.path} must use t075_committed_output"
                )
            producer_task = metadata.get("producer_task")
            producer_stage = metadata.get("producer_stage")
            producer_git_commit = metadata.get("producer_git_commit")
            regeneration_commands = metadata.get("regeneration_commands")
        compatibility_requirements = metadata.get("compatibility_requirements")
        entry_reason = metadata.get("retention_reason", retention_reason)
        entry_consumers = metadata.get(
            "possible_downstream_consumers", list(possible_downstream_consumers)
        )
        entries.append(
            {
                "artifact": artifact.to_dict(),
                "provenance": {
                    "source_kind": source_kind,
                    "producer_task": producer_task,
                    "producer_stage": producer_stage,
                    "producer_git_commit": producer_git_commit,
                },
                "regeneration_commands": regeneration_commands,
                "compatibility_requirements": compatibility_requirements,
                "retention_reason": entry_reason,
                "possible_downstream_consumers": entry_consumers,
            }
        )
    manifest = {
        "schema_id": "t075-retention-v1",
        "schema_version": 1,
        "task_id": T075_TASK_ID,
        "run_head": state.run_head,
        "terminal_case": state.terminal_case,
        "terminal_report": terminal_report_identity.to_dict(),
        "retention_owner": "T075",
        "retention_reason": retention_reason,
        "possible_downstream_consumers": list(possible_downstream_consumers),
        "deletion_condition_code": "after_merge_no_consumer_or_reproduction_hold",
        "entries": entries,
    }
    return validate_t075_retention_manifest(manifest, expected_artifacts=expected)


def finalize_t075(
    state: AcceptanceState,
    repository_root: Path,
    *,
    entry_metadata: Mapping[str, Mapping[str, Any]],
    retention_reason: str,
    possible_downstream_consumers: Sequence[str],
) -> tuple[ArtifactIdentity, ArtifactIdentity]:
    """Materialize the terminal report and one final retention manifest."""

    terminal_path = f"{T075_ROOT_RELATIVE}/terminal-decision.json"
    provisional = terminal_decision_from_state(
        state,
        ArtifactIdentity("terminal_report", terminal_path, "0" * 64, 0),
    )
    terminal_payload = canonical_json_document(provisional)
    terminal_identity = _artifact_identity_for_bytes(
        "terminal_report", terminal_path, terminal_payload
    )
    terminal = terminal_decision_from_state(state, terminal_identity)
    validate_t075_terminal_decision(
        terminal,
        expected_stage_outcomes=tuple(
            committed.report_identity for committed in state.committed_outcomes
        ),
    )
    terminal_payload = canonical_json_document(terminal)
    terminal_identity = _artifact_identity_for_bytes(
        "terminal_report", terminal_path, terminal_payload
    )
    terminal_file = _repository_path(repository_root, terminal_identity)
    if terminal_file.exists():
        existing_payload = terminal_file.read_bytes()
        if existing_payload != terminal_payload:
            raise T075OperationalError(
                "existing terminal report conflicts with canonical state"
            )
    else:
        _atomic_write(repository_root, terminal_file, terminal_payload)
    manifest = build_t075_retention_manifest(
        state,
        terminal_identity,
        entry_metadata=entry_metadata,
        retention_reason=retention_reason,
        possible_downstream_consumers=possible_downstream_consumers,
    )
    retention_path = f"{T075_ROOT_RELATIVE}/retention.json"
    retention_payload = canonical_json_document(manifest)
    retention_identity = _artifact_identity_for_bytes(
        "retention_manifest", retention_path, retention_payload
    )
    retention_file = _repository_path(repository_root, retention_identity)
    if retention_file.exists() and retention_file.read_bytes() != retention_payload:
        raise T075OperationalError(
            "existing retention manifest conflicts with canonical state"
        )
    if not retention_file.exists():
        _atomic_write(repository_root, retention_file, retention_payload)
    return terminal_identity, retention_identity
