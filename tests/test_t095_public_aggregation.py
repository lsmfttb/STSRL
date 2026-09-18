"""Focused T095 macro-aggregation and artifact-firewall contracts."""

from __future__ import annotations

from copy import deepcopy

from sts_combat_rl.commands.t095_public_aggregation import build_parser
from sts_combat_rl.sim.t092_internal_search_state import (
    T092_FROZEN_TEACHER_CONFIG,
    T092_NATIVE_API,
    T092_NATIVE_IDENTITY,
)
from sts_combat_rl.sim.t095_public_aggregation import (
    _audit_records,
    _public_action_identity,
    _public_fingerprint_from_t092,
    _split_half,
    write_t095_artifacts,
)


def _action(kind: str, index: int) -> dict[str, object]:
    return {
        "scope": "battle",
        "bits": index + 99,
        "kind": kind,
        "idx1": index,
        "idx2": 0,
        "idx3": 0,
        "label": f"{kind}-{index}",
    }


def _occurrence(
    source: str, node: str, delta: float, *, native_bits_offset: int = 0
) -> dict[str, object]:
    left, right = _action("card", 0), _action("end", 1)
    left["bits"] = int(left["bits"]) + native_bits_offset
    right["bits"] = int(right["bits"]) + native_bits_offset
    return {
        "schema_id": "t092-internal-search-state-occurrence-v1",
        "schema_version": 1,
        "native_identity": dict(T092_NATIVE_IDENTITY),
        "frozen_teacher_config": dict(T092_FROZEN_TEACHER_CONFIG),
        "source_identity": source,
        "source_group": "A",
        "split": "train",
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
            {"action": left, "visits": 4, "mean_value": delta},
            {"action": right, "visits": 4, "mean_value": 0.0},
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


def _record(source: str, occurrences: list[dict[str, object]]) -> dict[str, object]:
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
        "source_group": "A",
        "split": "train",
        "canonical_position": source,
        "decision_records": [],
        "internal_occurrences": occurrences,
    }


def _fixture(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "sts_combat_rl.sim.t095_public_aggregation.T095_SOURCE_RECORD_COUNT", 8
    )
    monkeypatch.setattr(
        "sts_combat_rl.sim.t095_public_aggregation.T095_SOURCE_GROUP_COUNTS", {"A": 8}
    )
    records = {}
    for index in range(8):
        source = f"source-{index}"
        # Source 0 revisits the exact state twice; its macro delta is (4 + 0)/2.
        deltas = [4.0, 0.0] if index == 0 else [2.0 if index % 2 else -2.0]
        records[source] = _record(
            source,
            [
                _occurrence(
                    source,
                    f"{source}-{node}",
                    delta,
                    native_bits_offset=index * 100,
                )
                for node, delta in enumerate(deltas)
            ],
        )
    ledger = {
        source: {
            "source_identity": source,
            "source_group": "A",
            "split": "train",
            "canonical_position": source,
            "terminal": {"battle_decision_count": 0},
        }
        for source in records
    }
    artifacts = [
        {"path": source, "schema_id": "t092-paired-canary-arm-record-v2"}
        for source in records
    ]
    return artifacts, ledger, records, tmp_path


def test_t095_uses_equal_source_macro_cells_and_retains_disagreement(
    monkeypatch, tmp_path
):
    artifacts, ledger, records, spill = _fixture(monkeypatch, tmp_path)
    report = _audit_records(
        artifacts=artifacts,
        ledger=ledger,
        load_record=lambda artifact: records[str(artifact["path"])],
        spill_directory=spill,
    )
    primary = report["primary_k_min_8"]
    assert (
        report["support_surface"]["8"]["distinct_fingerprint_action_pair_aggregates"]
        == 1
    )
    row = primary["aggregate_rows"][0]
    # Raw occurrences would yield 9 values; source 0 has exactly one equal-weight macro cell.
    assert row["source_start_count"] == 8
    assert row["mean_delta"] == 0.5
    assert row["positive_source_cells"] > 0 and row["negative_source_cells"] > 0
    assert row["observed_conditional_variation"] is True
    assert primary["source_cell_occurrence_multiplicity_quantiles"]["p100"] == 2.0


def test_t095_split_assignment_is_deterministic_and_source_disjoint():
    cells = [(f"source-{index}", float(index - 2)) for index in range(8)]
    first = _split_half("fingerprint", "pair", cells)
    second = _split_half("fingerprint", "pair", list(reversed(cells)))
    assert first == second


def test_t095_private_native_bits_do_not_enter_public_action_pair_identity():
    action = _action("card", 0)
    changed = deepcopy(action)
    changed["bits"] = 2_147_483_647
    assert _public_action_identity(action) == _public_action_identity(changed)


def test_t095_private_native_bits_do_not_split_public_fingerprint():
    first = _occurrence("one", "node", 1.0)
    second = _occurrence("two", "node", 1.0, native_bits_offset=100)
    from sts_combat_rl.sim.t092_internal_search_state import (
        validate_retained_occurrence,
    )

    first_row = validate_retained_occurrence(first)
    second_row = validate_retained_occurrence(second)
    assert first_row.fingerprint != second_row.fingerprint
    assert _public_fingerprint_from_t092(first_row) == _public_fingerprint_from_t092(
        second_row
    )


def test_t095_missing_accepted_source_bytes_write_incomplete(tmp_path, monkeypatch):
    import sts_combat_rl.sim.t095_public_aggregation as aggregation

    retention, evidence = tmp_path / "retention.json", tmp_path / "evidence.json"
    retention.write_text("{}", encoding="utf-8")
    evidence.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(aggregation, "T095_SOURCE_RECORD_COUNT", 1)
    monkeypatch.setattr(aggregation, "T095_SOURCE_GROUP_COUNTS", {"A": 1})
    monkeypatch.setattr(aggregation, "_read_bound_json", lambda *args: {})
    monkeypatch.setattr(
        aggregation,
        "_validate_t093_inputs",
        lambda *_: (
            [{"path": str(tmp_path / "missing-source.json")}],
            {
                "source": {
                    "source_identity": "source",
                    "source_group": "A",
                    "split": "train",
                    "canonical_position": 1,
                    "terminal": {"battle_decision_count": 0},
                }
            },
        ),
    )
    report = write_t095_artifacts(
        t092_retention_manifest_path=retention,
        t092_evidence_path=evidence,
        output_dir=tmp_path / "out-source-missing",
    )
    assert report["terminal_classification"] == "INCOMPLETE"
    assert report["incomplete_reason"] == "T092 source artifact is unavailable"


def test_t095_missing_exact_lineage_writes_incomplete_artifacts(tmp_path):
    report = write_t095_artifacts(
        t092_retention_manifest_path=tmp_path / "missing-retention.json",
        t092_evidence_path=tmp_path / "missing-evidence.json",
        output_dir=tmp_path / "out",
    )
    assert report["terminal_classification"] == "INCOMPLETE"
    assert (tmp_path / "out" / "t095-retention-manifest.json").is_file()


def test_t095_cli_is_file_only():
    destinations = {action.dest for action in build_parser()._actions}
    assert {
        "t092_retention_manifest",
        "t092_formal_evidence",
        "output_dir",
    } <= destinations
    assert not {"simulator", "search", "train"} & destinations
