"""Mock-only T092 formal authorization and root-reference boundary tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from sts_combat_rl.sim.t092_formal_execution import (
    T092FormalError,
    _canonical_root_rows,
    _classification,
    _metrics,
    _tree_geometry_metrics,
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


def test_formal_root_reproduction_reorders_interleaved_shards_to_global_source_order() -> None:
    sources = [
        {"source_identity": "source-0"},
        {"source_identity": "source-1"},
        {"source_identity": "source-2"},
        {"source_identity": "source-3"},
    ]
    # canonical-ordinal-modulo-2 emits shard 0 as sources 0,2 and shard 1 as
    # sources 1,3.  Finalization must compare 0,1,2,3 to T090, not shard order.
    grouped = {
        "source-0": [{"decision_identity": "source-0:decision:0"}],
        "source-1": [{"decision_identity": "source-1:decision:0"}],
        "source-2": [{"decision_identity": "source-2:decision:0"}],
        "source-3": [{"decision_identity": "source-3:decision:0"}],
    }
    assert [row["decision_identity"] for row in _canonical_root_rows(sources, grouped)] == [
        "source-0:decision:0", "source-1:decision:0",
        "source-2:decision:0", "source-3:decision:0",
    ]


def test_tree_geometry_metrics_preserve_native_totals_and_explicit_absence() -> None:
    geometry = {
        "schema_id": "native-battle-search-v2-tree-geometry-v1",
        "schema_version": 1,
        "root_depth": 0,
        "total_expanded_node_count": 2,
        "total_discovered_child_edge_count": 1,
        "total_visited_child_edge_count": 1,
        "max_expanded_depth": 1,
        "depth_rows": [
            {"depth": 0, "expanded_node_count": 1, "discovered_child_edge_count": 1,
             "visited_child_edge_count": 1, "branching_histogram": [{"child_count": 1, "node_count": 1}]},
            {"depth": 1, "expanded_node_count": 1, "discovered_child_edge_count": 0,
             "visited_child_edge_count": 0, "branching_histogram": [{"child_count": 0, "node_count": 1}]},
        ],
    }
    report = _tree_geometry_metrics([
        {"source_group": "A", "availability": "available", "expanded_node_count": 2, "geometry": geometry},
        {"source_group": "A", "availability": "unavailable", "expanded_node_count": 2, "geometry": None},
    ])
    assert report["availability"] == "partial"
    assert report["total_tree_nodes_observed"] == "UNAVAILABLE_FROM_NATIVE_TREE_GEOMETRY"
    assert report["by_source_group"]["A"]["total_tree_nodes_observed"] == "UNAVAILABLE_FROM_NATIVE_TREE_GEOMETRY"
    assert report["by_source_group"]["A"]["unavailable_observation_count"] == 1
    available = _tree_geometry_metrics([
        {"source_group": "A", "availability": "available", "expanded_node_count": 2, "geometry": geometry}
    ])
    assert available["total_tree_nodes_observed"] == 2
    unavailable = _tree_geometry_metrics([
        {"source_group": "A", "availability": "unavailable", "expanded_node_count": 2, "geometry": None}
    ])
    assert unavailable["availability"] == "unavailable"


def test_repeated_fingerprint_disagreement_is_bound_to_support_threshold() -> None:
    base = {
        "split": "train",
        "source_group": "A",
        "source_identity": "source",
        "parent": "parent",
        "depth": 1,
        "branching": 2,
        "searchable_kinds": ("card", "card"),
        "excluded_kinds": (),
        "supported": {"1": 2, "2": 0, "4": 0, "8": 0, "16": 0},
        "pairs": {"1": 1, "2": 0, "4": 0, "8": 0, "16": 0},
        "paired_kinds": {"1": ("card",), "2": (), "4": (), "8": (), "16": ()},
        "telemetry_transitions": 0,
    }
    rows = [
        {**base, "fingerprint": "same", "occurrence": "one",
         "supported_action_values": (("a", 1, 0.9), ("b", 1, 0.8))},
        {**base, "fingerprint": "same", "occurrence": "two",
         "supported_action_values": (("a", 1, 0.8), ("b", 1, 0.9))},
    ]
    metrics = _metrics(
        rows,
        [{"source_group": "A", "source_identity": "source",
          "terminal": {"battle_decision_count": 1},
          "cost": {"wall_clock_time_s": 0}}],
        [{"source_group": "A", "availability": "unavailable",
          "expanded_node_count": 1, "geometry": None}],
    )
    assert metrics["ambiguity_lower_bound"]["by_n_min"]["1"][
        "groups_with_best_supported_action_disagreement"
    ] == 1
    assert metrics["ambiguity_lower_bound"]["by_n_min"]["4"][
        "groups_with_best_supported_action_disagreement"
    ] == 0


def test_formal_geometry_absence_is_not_classified_as_a_usable_surface() -> None:
    assert _classification(
        {}, root_ok=True, canary_ok=True, firewall_ok=True, geometry_ok=False
    ) == "INCOMPLETE"


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
