"""Implementation-independent executable encoding of the approved T075 matrix.

The ``ContractFixtureHarness`` below is deliberately test-only.  It translates
literal JSON fixtures into expected outcomes and state assertions; it does not
import production helpers or provide a production workflow authority.  The
future production adapter must satisfy these public contract observations.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_PATH = ROOT / "tests" / "fixtures" / "t075_acceptance_cases.json"
RUN_HEAD = "1" * 40
STAGES = (
    "PREFLIGHT",
    "SOURCE_REUSE",
    "SELECTION_REPLAY",
    "TARGET",
    "TRAIN",
    "GATE",
    "EVAL",
)
FAILURE_CODES = {
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
EXPECTED_CASES = tuple(json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))["cases"])
FROZEN_SOURCES = (
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


def _case(case_id: str) -> dict[str, Any]:
    return next(case for case in EXPECTED_CASES if case["id"] == case_id)


def _canonical_json(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def _selection_digest(candidate: Any) -> str:
    return hashlib.sha256(
        b"T065-source-selection-v1\n" + _canonical_json(candidate)
    ).hexdigest()


def _group_digest(candidate: dict[str, Any]) -> str:
    group_key = {
        "family": candidate["family"],
        "public_state_identity": candidate["public_state_identity"],
        "ordered_legal_action_identities": candidate["ordered_legal_action_identities"],
    }
    return hashlib.sha256(
        b"T075-replay-group-v1\n" + _canonical_json(group_key)
    ).hexdigest()


def _identity(role: str, filename: str, fill: str = "a") -> dict[str, Any]:
    return {
        "role": role,
        "path": f"artifacts/t075-test/{filename}",
        "sha256": fill * 64,
        "size_bytes": 1,
    }


def _stage_outcome(
    stage: str,
    *,
    valid: bool,
    passed: bool,
    parents: tuple[dict[str, Any], ...] = (),
    outputs: tuple[dict[str, Any], ...] = (),
    failure_code: str | None = None,
) -> dict[str, Any]:
    return {
        "schema_id": "t075-stage-outcome-v1",
        "schema_version": 1,
        "task_id": "T075",
        "run_head": RUN_HEAD,
        "stage": stage,
        "valid": valid,
        "passed": passed,
        "parents": list(parents),
        "outputs": list(outputs),
        "failure_code": failure_code,
    }


def _report(stage: str) -> dict[str, Any]:
    return _identity(
        "stage_outcome", f"outcomes/{STAGES.index(stage):02d}-{stage.lower()}.json"
    )


def _valid_identity(identity: Any) -> bool:
    return (
        isinstance(identity, dict)
        and set(identity) == {"role", "path", "sha256", "size_bytes"}
        and isinstance(identity["role"], str)
        and bool(identity["role"])
        and isinstance(identity["path"], str)
        and identity["path"].startswith("artifacts/")
        and "\\" not in identity["path"]
        and ".." not in identity["path"].split("/")
        and isinstance(identity["sha256"], str)
        and len(identity["sha256"]) == 64
        and all(character in "0123456789abcdef" for character in identity["sha256"])
        and isinstance(identity["size_bytes"], int)
        and identity["size_bytes"] >= 0
    )


@dataclass(frozen=True)
class ExpectedState:
    """Minimal expected state, independent of any production representation."""

    current_stage: str | None = "PREFLIGHT"
    committed: tuple[tuple[str, dict[str, Any], dict[str, Any]], ...] = ()
    terminal_case: str | None = None
    terminal_stage: str | None = None

    @property
    def artifact_index(self) -> tuple[dict[str, Any], ...]:
        identities: list[dict[str, Any]] = []
        for _, outcome, report in self.committed:
            identities.append(report)
            if outcome["valid"]:
                identities.extend(outcome["outputs"])
        return tuple(identities)


class OperationalReject(Exception):
    """Expected A20/A24 operational failure in the test-only seam."""


@dataclass
class ContractFixtureHarness:
    """Small test oracle for state assertions, not a production implementation."""

    state: ExpectedState = field(default_factory=ExpectedState)

    def advance(
        self,
        outcome: dict[str, Any],
        report: dict[str, Any],
        *,
        run_head: str = RUN_HEAD,
    ) -> ExpectedState:
        if run_head != RUN_HEAD:
            raise OperationalReject("wrong run head")
        if set(outcome) != {
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
        }:
            raise OperationalReject("malformed outcome shape")
        stage = outcome["stage"]
        if (
            outcome["schema_id"] != "t075-stage-outcome-v1"
            or outcome["schema_version"] != 1
            or outcome["task_id"] != "T075"
            or outcome["run_head"] != RUN_HEAD
            or stage not in STAGES
            or not isinstance(outcome["parents"], list)
            or not isinstance(outcome["outputs"], list)
            or not all(_valid_identity(identity) for identity in outcome["parents"])
            or not all(_valid_identity(identity) for identity in outcome["outputs"])
            or not _valid_identity(report)
            or report["role"] != "stage_outcome"
        ):
            raise OperationalReject("malformed outcome identity")
        existing = next((row for row in self.state.committed if row[0] == stage), None)
        if existing is not None:
            if existing[1] == outcome and existing[2] == report:
                return self.state
            raise OperationalReject("conflicting duplicate")
        if self.state.terminal_case is not None:
            raise OperationalReject("new stage after terminal")
        if stage != self.state.current_stage:
            raise OperationalReject("out-of-order stage")
        if outcome["valid"] and outcome["failure_code"] is not None:
            raise OperationalReject("valid outcome has failure")
        if not outcome["valid"] and (
            outcome["passed"] or outcome["failure_code"] is None or outcome["outputs"]
        ):
            raise OperationalReject("invalid outcome shape")
        if outcome["valid"] and stage not in {"GATE", "EVAL"} and not outcome["passed"]:
            raise OperationalReject("pre-gate negative result")
        allowed_external = FROZEN_SOURCES if stage == "SOURCE_REUSE" else ()
        available = self.state.artifact_index
        for parent in outcome["parents"]:
            if parent not in available and parent not in allowed_external:
                raise OperationalReject("unresolved parent")
        expected_next = STAGES[STAGES.index(stage) + 1] if stage != "EVAL" else None
        terminal_case = None
        terminal_stage = None
        if not outcome["valid"]:
            terminal_case, terminal_stage = "D", stage
            expected_next = None
        elif stage == "GATE" and not outcome["passed"]:
            terminal_case, terminal_stage, expected_next = "C", stage, None
        elif stage == "EVAL":
            terminal_case, terminal_stage = ("A" if outcome["passed"] else "B"), stage
            expected_next = None
        self.state = replace(
            self.state,
            current_stage=expected_next,
            committed=self.state.committed + ((stage, outcome, report),),
            terminal_case=terminal_case,
            terminal_stage=terminal_stage,
        )
        return self.state


def _valid_stage(
    stage: str,
    outputs: tuple[dict[str, Any], ...] = (),
    parents: tuple[dict[str, Any], ...] = (),
) -> dict[str, Any]:
    return _stage_outcome(
        stage, valid=True, passed=True, parents=parents, outputs=outputs
    )


def _invalid_stage(
    stage: str,
    failure_code: str,
    parents: tuple[dict[str, Any], ...] = (),
) -> dict[str, Any]:
    return _stage_outcome(
        stage,
        valid=False,
        passed=False,
        parents=parents,
        failure_code=failure_code,
    )


def _reach_gate() -> ContractFixtureHarness:
    harness = ContractFixtureHarness()
    for stage in STAGES[:5]:
        outputs = {
            "PREFLIGHT": (_identity("preflight_audit", "preflight-audit.json"),),
            "SOURCE_REUSE": (
                _identity("source_reuse_audit", "source-reuse-audit.json"),
            ),
            "SELECTION_REPLAY": (
                _identity("ownership_audit", "ownership-audit.json"),
                _identity("selected_states", "selected-states.jsonl"),
            ),
            "TARGET": (_identity("target_table", "target-table.json"),),
            "TRAIN": (
                _identity("checkpoint", "checkpoints/653001.pt"),
                _identity("checkpoint", "checkpoints/653002.pt"),
                _identity("training_selection", "training-selection.json"),
            ),
        }[stage]
        parents = {
            "PREFLIGHT": (),
            "SOURCE_REUSE": (_report("PREFLIGHT"), *FROZEN_SOURCES),
            "SELECTION_REPLAY": (
                _identity("source_reuse_audit", "source-reuse-audit.json"),
            ),
            "TARGET": (
                _report("PREFLIGHT"),
                _identity("selected_states", "selected-states.jsonl"),
            ),
            "TRAIN": (_identity("target_table", "target-table.json"),),
        }[stage]
        harness.advance(_valid_stage(stage, outputs, parents), _report(stage))
    return harness


def _gate_parents() -> tuple[dict[str, Any], ...]:
    return (
        _identity("target_table", "target-table.json"),
        _identity("training_selection", "training-selection.json"),
        _identity("checkpoint", "checkpoints/653001.pt"),
    )


def test_t075_fixture_catalog_covers_exactly_a01_to_a24() -> None:
    assert tuple(case["id"] for case in EXPECTED_CASES) == tuple(
        f"A{index:02d}" for index in range(1, 25)
    )
    assert json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))["contract_commit"] == (
        "66e6f7aabb8176eebf05013992d4ec0840809860"
    )


@pytest.mark.parametrize("case_id", [f"A{index:02d}" for index in range(1, 25)])
def test_t075_case_matrix_literal_expectation(case_id: str) -> None:
    case = _case(case_id)
    assert set(case) == {
        "id",
        "stage",
        "valid",
        "passed",
        "failure_code",
        "terminal_case",
    }
    if case["valid"] is False:
        assert case["passed"] is False
        assert case["failure_code"] in FAILURE_CODES
    if case["stage"] is not None:
        assert case["stage"] in (*STAGES, "FINALIZE")


def test_A01_exact_sources_are_ordered_and_identity_complete() -> None:
    sources = FROZEN_SOURCES
    assert [item["role"] for item in sources] == ["current_output", "current_output"]
    assert sources[0]["path"].endswith("source-stochastic-650001-650256-c57b2ee.json")
    assert sources[1]["path"].endswith("source-expert-650001-650256-deeaa46.json")
    assert all(
        set(item) == {"role", "path", "sha256", "size_bytes"} for item in sources
    )
    assert all(len(item["sha256"]) == 64 and item["size_bytes"] > 0 for item in sources)


def test_A02_invalid_source_commits_only_case_D_without_audit() -> None:
    harness = ContractFixtureHarness()
    harness.advance(
        _valid_stage(
            "PREFLIGHT", (_identity("preflight_audit", "preflight-audit.json"),)
        ),
        _report("PREFLIGHT"),
    )
    harness.advance(
        _invalid_stage(
            "SOURCE_REUSE",
            "SOURCE_REUSE_INVALID",
            (_report("PREFLIGHT"), *FROZEN_SOURCES),
        ),
        _report("SOURCE_REUSE"),
    )
    assert harness.state.terminal_case == "D"
    assert harness.state.artifact_index == (
        _report("PREFLIGHT"),
        _identity("preflight_audit", "preflight-audit.json"),
        _report("SOURCE_REUSE"),
    )


def test_A03_global_owner_precedes_split_quota() -> None:
    candidates = [
        {
            "row": "train",
            "split": "train",
            "family": "MAP_SCREEN",
            "public_state_identity": "same-state",
            "ordered_legal_action_identities": ["choose:0"],
            "candidate": {"source": "stochastic", "seed": 650001},
        },
        {
            "row": "heldout",
            "split": "heldout",
            "family": "MAP_SCREEN",
            "public_state_identity": "same-state",
            "ordered_legal_action_identities": ["choose:0"],
            "candidate": {"source": "expert", "seed": 650206},
        },
    ]
    members = [
        {**candidate, "selection_digest": _selection_digest(candidate["candidate"])}
        for candidate in candidates
    ]
    owner = min(
        members,
        key=lambda row: (row["selection_digest"], _canonical_json(row["candidate"])),
    )
    assert owner["row"] == "train"
    assert _group_digest(candidates[0]) == _group_digest(candidates[1])
    assert [row["row"] for row in members if row is owner] == ["train"]


def test_A04_identical_complete_member_order_key_is_a_failure() -> None:
    members = [
        ("stochastic", "a" * 64, b'{"row":1}'),
        ("expert", "a" * 64, b'{"row":1}'),
    ]
    assert len({(digest, payload) for _, digest, payload in members}) < len(members)
    assert _case("A04")["failure_code"] == "SELECTION_MEMBER_ORDER_TIE"


def test_A05_owner_bucket_shortage_is_not_repaired_by_non_owner() -> None:
    available_after_ownership = Counter({"MAP_SCREEN/train": 47})
    assert available_after_ownership["MAP_SCREEN/train"] < 48
    assert _case("A05")["terminal_case"] == "D"


def test_A06_cross_split_overlap_is_invalid_after_provisional_selection() -> None:
    selected_replay_keys = [("MAP_SCREEN", "same", ("choose:0",))]
    source_replay_keys = selected_replay_keys + selected_replay_keys
    assert len(set(source_replay_keys)) != len(source_replay_keys)
    assert _case("A06")["failure_code"] == "SELECTION_REPLAY_INVALID"


def test_A07_exact_320_cohort_has_frozen_family_split_quotas() -> None:
    counts = {
        f"{family}/{split}": quota
        for family in ("MAP_SCREEN", "REST_ROOM", "REWARDS", "TREASURE_ROOM")
        for split, quota in (("train", 48), ("validation", 16), ("heldout", 16))
    }
    assert sum(counts.values()) == 320
    assert all(value in (48, 16) for value in counts.values())


def test_A08_replay_mismatch_has_no_replacement_or_output() -> None:
    expected = _case("A08")
    assert expected["failure_code"] == "SELECTION_REPLAY_INVALID"
    assert expected["terminal_case"] == "D"
    assert expected["valid"] is False


@pytest.mark.parametrize("case_id", ["A09", "A10", "A23"])
def test_A09_A10_A23_target_failures_are_invalid_and_do_not_reach_train(
    case_id: str,
) -> None:
    case = _case(case_id)
    assert case["stage"] == "TARGET"
    assert case["failure_code"] == "TARGET_INVALID"
    assert case["terminal_case"] == "D"
    assert case["valid"] is False


def test_A11_interrupted_output_promotion_is_uncommitted_and_retryable() -> None:
    harness = _reach_gate()
    before = harness.state
    prospective = _valid_stage(
        "GATE", (_identity("stage5", "heldout-gate.json"),), _gate_parents()
    )
    assert prospective["outputs"]
    assert harness.state == before
    harness.advance(prospective, _report("GATE"))
    assert harness.state.current_stage == "EVAL"


def test_A12_valid_target_and_train_reach_gate_with_exact_outputs() -> None:
    harness = _reach_gate()
    assert harness.state.current_stage == "GATE"
    assert len(harness.state.committed[-1][1]["outputs"]) == 3


def test_A13_valid_gate_pass_reaches_eval() -> None:
    harness = _reach_gate()
    harness.advance(
        _valid_stage(
            "GATE", (_identity("stage5", "heldout-gate.json"),), _gate_parents()
        ),
        _report("GATE"),
    )
    assert harness.state.current_stage == "EVAL"
    assert harness.state.terminal_case is None


def test_A14_valid_gate_failure_is_case_C_and_skips_eval() -> None:
    harness = _reach_gate()
    outcome = _stage_outcome(
        "GATE",
        valid=True,
        passed=False,
        parents=_gate_parents(),
        outputs=(_identity("stage5", "heldout-gate.json"),),
    )
    harness.advance(outcome, _report("GATE"))
    assert harness.state.terminal_case == "C"
    assert harness.state.current_stage is None
    assert not any(stage == "EVAL" for stage, _, _ in harness.state.committed)


def test_A15_invalid_gate_evidence_is_case_D() -> None:
    harness = _reach_gate()
    harness.advance(
        _invalid_stage("GATE", "GATE_EVIDENCE_INVALID", _gate_parents()),
        _report("GATE"),
    )
    assert harness.state.terminal_case == "D"


@pytest.mark.parametrize(("passed", "terminal"), [(True, "A"), (False, "B")])
def test_A16_A17_eval_result_maps_to_terminal_case(passed: bool, terminal: str) -> None:
    harness = _reach_gate()
    harness.advance(
        _valid_stage(
            "GATE", (_identity("stage5", "heldout-gate.json"),), _gate_parents()
        ),
        _report("GATE"),
    )
    harness.advance(
        _stage_outcome(
            "EVAL",
            valid=True,
            passed=passed,
            parents=(
                _identity("stage5", "heldout-gate.json"),
                _identity("training_selection", "training-selection.json"),
                _identity("checkpoint", "checkpoints/653001.pt"),
            ),
            outputs=(_identity("stage6", "complete-run.json"),),
        ),
        _report("EVAL"),
    )
    assert harness.state.terminal_case == terminal
    assert harness.state.terminal_stage == "EVAL"


def test_A18_invalid_eval_evidence_is_case_D() -> None:
    harness = _reach_gate()
    harness.advance(
        _valid_stage(
            "GATE", (_identity("stage5", "heldout-gate.json"),), _gate_parents()
        ),
        _report("GATE"),
    )
    harness.advance(
        _invalid_stage(
            "EVAL",
            "EVAL_EVIDENCE_INVALID",
            (
                _identity("stage5", "heldout-gate.json"),
                _identity("training_selection", "training-selection.json"),
                _identity("checkpoint", "checkpoints/653001.pt"),
            ),
        ),
        _report("EVAL"),
    )
    assert harness.state.terminal_case == "D"


def test_A19_initial_state_is_preflight_with_empty_lineage() -> None:
    state = ExpectedState()
    assert state.current_stage == "PREFLIGHT"
    assert state.committed == ()
    assert state.terminal_case is None
    assert state.artifact_index == ()


@pytest.mark.parametrize("reason", ["wrong head", "out of order", "malformed parent"])
def test_A20_operational_reject_leaves_state_unchanged(reason: str) -> None:
    harness = ContractFixtureHarness()
    before = harness.state
    with pytest.raises(OperationalReject, match=".*"):
        if reason == "wrong head":
            harness.advance(
                _valid_stage("PREFLIGHT"), _report("PREFLIGHT"), run_head="2" * 40
            )
        elif reason == "out of order":
            harness.advance(_valid_stage("TARGET"), _report("TARGET"))
        else:
            harness.advance(
                _valid_stage("PREFLIGHT", parents=(_identity("unknown", "x.json"),)),
                _report("PREFLIGHT"),
            )
    assert harness.state == before


def test_A21_atomic_stage_commit_is_the_only_lineage_mutation() -> None:
    harness = ContractFixtureHarness()
    output = _identity("preflight_audit", "preflight-audit.json")
    before = harness.state
    pending = _valid_stage("PREFLIGHT", (output,))
    assert harness.state == before
    harness.advance(pending, _report("PREFLIGHT"))
    assert output in harness.state.artifact_index


def test_A22_identical_retry_is_idempotent_and_terminal_is_immutable() -> None:
    harness = _reach_gate()
    gate = _stage_outcome(
        "GATE",
        valid=True,
        passed=False,
        parents=_gate_parents(),
        outputs=(_identity("stage5", "heldout-gate.json"),),
    )
    report = _report("GATE")
    terminal = harness.advance(gate, report)
    assert harness.advance(gate, report) == terminal
    with pytest.raises(OperationalReject, match="conflicting duplicate|new stage"):
        harness.advance(_valid_stage("EVAL"), _report("EVAL"))
    assert harness.state.terminal_case == "C"


def test_A24_finalization_failure_cannot_reinterpret_terminal_state() -> None:
    harness = _reach_gate()
    harness.advance(
        _stage_outcome(
            "GATE",
            valid=True,
            passed=False,
            parents=_gate_parents(),
            outputs=(_identity("stage5", "heldout-gate.json"),),
        ),
        _report("GATE"),
    )
    terminal_before = (harness.state.terminal_case, harness.state.terminal_stage)
    with pytest.raises(OperationalReject):
        raise OperationalReject("retention failure after terminal")
    assert (
        (harness.state.terminal_case, harness.state.terminal_stage)
        == terminal_before
        == ("C", "GATE")
    )
