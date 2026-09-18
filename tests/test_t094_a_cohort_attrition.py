"""Focused contracts for the T094 file-only source-start attrition audit."""

from __future__ import annotations

from copy import deepcopy

import pytest

from sts_combat_rl.commands.t094_a_cohort_attrition import build_parser
from sts_combat_rl.sim.t092_internal_search_state import (
    T092_FROZEN_TEACHER_CONFIG,
    T092_NATIVE_API,
    T092_NATIVE_IDENTITY,
)
from sts_combat_rl.sim.t094_a_cohort_attrition import (
    T094Incomplete,
    _audit_records,
    write_t094_artifacts,
)


def _occurrence(
    *, source: str, group: str, split: str, node: str, visits: int = 4
) -> dict[str, object]:
    action = lambda kind, index: {
        "scope": "battle",
        "bits": index + 1,
        "kind": kind,
        "idx1": index,
        "idx2": 0,
        "idx3": 0,
        "label": f"{kind}-{index}",
    }
    return {
        "schema_id": "t092-internal-search-state-occurrence-v1",
        "schema_version": 1,
        "native_identity": dict(T092_NATIVE_IDENTITY),
        "frozen_teacher_config": dict(T092_FROZEN_TEACHER_CONFIG),
        "source_identity": source,
        "source_group": group,
        "split": split,
        "parent_root_decision_identity": f"{source}:root",
        "occurrence_identity": node,
        "tree_depth": 1,
        "expansion_ordinal": 1,
        "public_battle_projection": {
            "battle_player": {"cur_hp": 10},
            "battle_hand": [],
            "battle_discard_pile": [],
            "battle_exhaust_pile": [],
            "battle_monsters": [],
            "battle_potions": [],
            "battle_relics": [],
        },
        "input_state": "PLAYER_NORMAL",
        "searchable_actions": [
            {"action": action("card", 0), "visits": visits, "mean_value": 1.0},
            {"action": action("end", 1), "visits": visits, "mean_value": 0.0},
        ],
        "excluded_actions": [],
        "search_work": {
            "root_visits": 400,
            "native_simulator_steps": 1,
            "simulations_requested": 400,
        },
        "telemetry_cost": {
            "telemetry_extraction_transition_count": 0,
            "collection_phase": "post_search_private_state_replay",
        },
    }


def _record(
    source: str, group: str, split: str, occurrence: dict[str, object]
) -> dict[str, object]:
    return {
        "schema_id": "t092-paired-canary-arm-record-v2",
        "schema_version": 1,
        "task_id": "T092",
        "arm": "ON",
        "implementation_head": "1e3dff2665d38dfd6acc786666c1889bc8327508",
        "native_identity": dict(T092_NATIVE_IDENTITY),
        "native_api": T092_NATIVE_API,
        "teacher_config": dict(T092_FROZEN_TEACHER_CONFIG),
        "source_identity": source,
        "source_group": group,
        "split": split,
        "canonical_position": {"a": 0, "b": 1, "c": 2}[source],
        "decision_records": [],
        "internal_occurrences": [occurrence],
    }


def _fixture(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "sts_combat_rl.sim.t094_a_cohort_attrition.T094_SOURCE_RECORD_COUNT", 3
    )
    monkeypatch.setattr(
        "sts_combat_rl.sim.t094_a_cohort_attrition.T094_SOURCE_GROUP_COUNTS",
        {"A": 1, "B": 1, "C": 1},
    )
    monkeypatch.setattr(
        "sts_combat_rl.sim.t094_a_cohort_attrition.T094_A_DIAGNOSTIC_MINIMUM", 2
    )
    monkeypatch.setattr(
        "sts_combat_rl.sim.t094_a_cohort_attrition.T094_EXPECTED_S3_FINGERPRINTS",
        {"train": 1, "validation": 0, "heldout": 1},
    )
    monkeypatch.setattr(
        "sts_combat_rl.sim.t094_a_cohort_attrition.T094_EXPECTED_S3_STARTS",
        {
            "train": {"A": 1, "B": 0, "C": 0},
            "validation": {"A": 0, "B": 0, "C": 0},
            "heldout": {"A": 0, "B": 0, "C": 1},
        },
    )
    a = _occurrence(source="a", group="A", split="train", node="z")
    b = deepcopy(a)
    b.update(
        {
            "source_identity": "b",
            "source_group": "B",
            "parent_root_decision_identity": "b:root",
            "occurrence_identity": "a",
        }
    )
    c = _occurrence(source="c", group="C", split="heldout", node="one")
    c["public_battle_projection"]["battle_player"]["cur_hp"] = 20
    records = {
        "a": _record("a", "A", "train", a),
        "b": _record("b", "B", "train", b),
        "c": _record("c", "C", "heldout", c),
    }
    artifacts = [
        {"path": source, "schema_id": "t092-paired-canary-arm-record-v2"}
        for source in records
    ]
    ledger = {
        source: {
            "source_identity": source,
            "source_group": record["source_group"],
            "split": record["split"],
            "canonical_position": record["canonical_position"],
            "terminal": {"battle_decision_count": 0},
        }
        for source, record in records.items()
    }
    return artifacts, ledger, records, tmp_path


def test_t094_uses_t093_cross_split_and_canonical_ownership_rules(
    monkeypatch, tmp_path
):
    artifacts, ledger, records, spill = _fixture(monkeypatch, tmp_path)
    report = _audit_records(
        artifacts=artifacts,
        ledger=ledger,
        load_record=lambda artifact: records[str(artifact["path"])],
        spill_directory=spill,
    )
    assert (
        report["terminal_classification"]
        == "A_COHORT_LOW_SUPERVISION_BEFORE_SUPPORT_THRESHOLD"
    )
    assert report["reproduction"]["passed"] is True
    train = report["coverage_by_split_and_group"]["train"]
    assert (
        train["A"]["s2_after_cross_split_exclusion_n_min_4"]["contributing_start_count"]
        == 1
    )
    assert (
        train["B"]["s2_after_cross_split_exclusion_n_min_4"]["contributing_start_count"]
        == 1
    )
    assert (
        train["B"]["s3_final_t093_canonical_n_min_4"]["contributing_start_count"] == 0
    )
    assert (
        report["s3_concentration_by_source_group"]["A"][
            "maximum_canonical_pair_bearing_fingerprints_per_contributing_start"
        ]
        == 1
    )


def test_t094_fails_closed_when_the_same_n_min_four_fingerprint_crosses_splits(
    monkeypatch, tmp_path
):
    artifacts, ledger, records, spill = _fixture(monkeypatch, tmp_path)
    records["b"] = deepcopy(records["b"])
    records["b"]["split"] = "validation"
    records["b"]["internal_occurrences"][0]["split"] = "validation"
    ledger["b"] = dict(ledger["b"], split="validation")
    with pytest.raises(T094Incomplete, match="does not reproduce"):
        _audit_records(
            artifacts=artifacts,
            ledger=ledger,
            load_record=lambda artifact: records[str(artifact["path"])],
            spill_directory=spill,
        )


def test_t094_unavailable_inputs_write_an_incomplete_report(tmp_path):
    report = write_t094_artifacts(
        t092_retention_manifest_path=tmp_path / "missing-t092-retention.json",
        t092_evidence_path=tmp_path / "missing-t092-evidence.json",
        t093_retention_manifest_path=tmp_path / "missing-t093-retention.json",
        t093_corpus_path=tmp_path / "missing-t093-corpus.json",
        output_dir=tmp_path / "out",
    )
    assert report["terminal_classification"] == "INCOMPLETE"
    assert (tmp_path / "out" / "t094-retention-manifest.json").is_file()


def test_t094_cli_accepts_only_retained_file_inputs():
    destinations = {action.dest for action in build_parser()._actions}
    assert {
        "t092_retention_manifest",
        "t092_formal_evidence",
        "t093_retention_manifest",
        "t093_corpus",
        "output_dir",
    } <= destinations
    assert (
        "simulator" not in destinations
        and "search" not in destinations
        and "train" not in destinations
    )
