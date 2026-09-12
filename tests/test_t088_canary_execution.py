"""Fake-only tests for the explicitly authorized T088 canary seam."""

from __future__ import annotations

import hashlib
import json
from types import SimpleNamespace

import pytest

from sts_combat_rl.commands.t088_classical_combat_tournament import (
    T088_NATIVE_IDENTITY,
    t088_controller_definitions,
)
from sts_combat_rl.sim.t087_dense_combat_diagnostics import (
    battle_snapshot_evidence,
    build_dense_diagnostic_row,
)
from sts_combat_rl.sim.t088_canary_execution import (
    T088CanaryExecutionError,
    _T088CanaryRuntimeAdapter,
    _aggregate_work,
    execute_t088_canary,
    write_t088_canary_evidence,
)
from sts_combat_rl.sim.t088_tournament_workflow import (
    _binding_identity,
    select_t088_canary_records,
)


def _sha(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _source_identity() -> dict[str, object]:
    return {
        "path": "/retained/t085-selection.json",
        "sha256": "d5c335cd6e1f96e72ae3b302eebca17a5f6531fa0aac97ee2febec2c41c2e752",
        "schema_id": "t085-native-selection-artifact-v1",
        "byte_count": 1,
    }


def _cohort() -> list[dict[str, object]]:
    source = _source_identity()
    result = []
    for cohort, count in (("A", 93), ("B", 192), ("C", 128)):
        result.extend(
            {
                "selection_identity": f"{cohort}:{index}",
                "cohort": cohort,
                "source_selection_manifest_identity": source,
                "provenance": {
                    "native_commit": "96052d24b9c2c16ff25b6f7241edd972613be997"
                },
            }
            for index in range(count)
        )
    result[0].update(is_escaping_mugger_case=True, legal_root_action_count=2)
    result[1].update(is_ordinary_victory=True, legal_root_action_count=2)
    result[2].update(is_ordinary_loss=True, legal_root_action_count=2)
    result[93].update(is_later_act_or_boss=True, legal_root_action_count=2)
    result[94].update(legal_root_action_count=3)
    return result


def _binding(cohort: list[dict[str, object]]) -> dict[str, object]:
    entries = [
        {"selection_identity": row["selection_identity"], "cohort": row["cohort"]}
        for row in cohort
    ]
    reference = lambda sha, schema: {
        "path": f"/retained/{schema}.json",
        "sha256": sha,
        "size_bytes": 1,
        "schema_id": schema,
    }
    return {
        "schema_id": "t088-t087-cohort-binding-v1",
        "task_id": "T088",
        "t087_task_id": "T087",
        "t087_native_identity": {
            "repository": "lsmfttb/sts_lightspeed",
            "ref": "refs/heads/stsrl/main",
            "commit": "96052d24b9c2c16ff25b6f7241edd972613be997",
        },
        "source_selection_manifest_identity": _source_identity(),
        "t087_artifacts": {
            "formal_natural_evidence": reference(
                "7931a118a4bf921f695db769f05fd77a5ae364484f5646f02d5be05329ad297f",
                "t087-natural-evidence-v1",
            ),
            "final_report": reference(
                "9a0eba7eed03a1ba4801c3019e9d14a2aa61214a76299a63ed9ab5a0192f3ea0",
                "t087-dense-combat-diagnostics-report-v1",
            ),
            "retention_manifest": reference(
                "5afe39476965a192c9bdd8d6bed121cd0169e68925cabfe9b8366ee320938adc",
                "t087-retention-manifest-v1",
            ),
        },
        "ordered_cohort_entries": entries,
        "ordered_cohort_entries_sha256": _sha(entries),
    }


def _authorization(
    *, head: str, selection: dict[str, object], binding: dict[str, object]
) -> dict[str, object]:
    definitions = t088_controller_definitions()
    return {
        "schema_id": "t088-maintainer-canary-authorization-v1",
        "task_id": "T088",
        "authorization_kind": "bounded_canary",
        "authorized": True,
        "authorization_id": "test-maintainer-auth-1",
        "implementation_head": head,
        "canary_selection_sha256": _sha(selection),
        "t087_cohort_binding": _binding_identity(binding),
        "controller_definitions_sha256": _sha(definitions),
        "maintainer_attestation": {
            "role": "maintainer",
            "decision": "CANARY_AUTHORIZED",
            "exact_head": head,
        },
    }


def _controller(arm: str) -> object:
    return SimpleNamespace(provenance={"kind": "fake", "arm": arm})


def _diagnostic(
    identity: str, cohort: str, *, source: dict[str, object]
) -> dict[str, object]:
    entry = battle_snapshot_evidence(
        {
            "battle_player": {"current_hp": 40, "max_hp": 80},
            "battle_monsters": [{"id_label": "Cultist", "current_hp": 20}],
            "battle_monster_count": 1,
            "battle_monsters_alive": 1,
        }
    )
    terminal_raw = {
        "cur_hp": 60,
        "max_hp": 80,
        "completed_battle_outcome": "PLAYER_VICTORY",
        "outcome": "UNDECIDED",
        "completed_battle_monster_count": 1,
        "completed_battle_monsters_alive": 0,
        "completed_battle_monsters": [
            {
                "id_label": "Cultist",
                "current_hp": 0,
                "max_hp": 20,
                "alive": False,
                "targetable": False,
                "half_dead": False,
            }
        ],
    }
    terminal = battle_snapshot_evidence(terminal_raw, require_positive_enemy_hp=False)
    return build_dense_diagnostic_row(
        selection_identity=identity,
        cohort=cohort,
        entry=entry,
        terminal=terminal,
        outcome="PLAYER_VICTORY",
        action_trace=[],
        provenance={"task_id": "T088", "restore_method": "fake"},
        source_selection_manifest_identity=source,
    )


def _runner(record, arm, controller):
    return {
        "arm": arm,
        "selection_identity": record["selection_identity"],
        "cohort": record["cohort"],
        "native_identity": T088_NATIVE_IDENTITY,
        "controller_provenance": controller.provenance,
        "restore_public_legal_parity": True,
        "outcome": "PLAYER_VICTORY",
        "controller_definition_verified": True,
        "dense_diagnostic_recomputed": True,
        "native_game_mechanics_parity": True,
        "search_v2_parity_verified": arm in {"A", "B"},
        "beam_deterministic_replay_verified": arm == "C",
        "progressive_bias_depth_gt_zero_verified": arm == "D",
        "wall_clock_time_s": 0.01,
        "work_counters": {
            "successor_transition_count": 1,
            "action_execution_count": 1,
            "model_calls": 0,
            "root_decision_count": 1,
            "native_simulator_step_count": 1,
            "tree_node_expansion_count": 1,
            "rollout_count": 1,
            "terminal_utility_evaluation_count": 1,
        },
        "dense_diagnostic": _diagnostic(
            record["selection_identity"],
            record["cohort"],
            source=_source_identity(),
        ),
    }


def test_canary_refuses_to_invoke_runner_without_exact_authorization() -> None:
    cohort = _cohort()
    binding = _binding(cohort)
    selection = select_t088_canary_records(cohort, cohort_binding=binding)
    invoked = False

    def never(*args):
        nonlocal invoked
        invoked = True
        return _runner(*args)

    with pytest.raises(T088CanaryExecutionError, match="authorization is required"):
        execute_t088_canary(
            authorization=None,
            implementation_head="a" * 40,
            cohort_rows=cohort,
            cohort_binding=binding,
            selection=selection,
            runner=never,
            controller_factory=_controller,
        )
    assert invoked is False


def test_authorized_fake_canary_binds_all_arms_and_writes_once(tmp_path) -> None:
    cohort = _cohort()
    binding = _binding(cohort)
    selection = select_t088_canary_records(cohort, cohort_binding=binding)
    head = "b" * 40
    evidence = execute_t088_canary(
        authorization=_authorization(head=head, selection=selection, binding=binding),
        implementation_head=head,
        cohort_rows=cohort,
        cohort_binding=binding,
        selection=selection,
        runner=_runner,
        controller_factory=_controller,
    )
    assert evidence["formal_execution_authorized"] is False
    assert {row["arm"] for row in evidence["rows"]} == {"A", "B", "C", "D"}
    reference = write_t088_canary_evidence(tmp_path / "fake-canary.json", evidence)
    assert reference["schema_id"] == "t088-canary-evidence-v1"
    with pytest.raises(T088CanaryExecutionError, match="overwrite"):
        write_t088_canary_evidence(tmp_path / "fake-canary.json", evidence)


def test_canary_rejects_authorization_or_amended_dense_evidence_drift() -> None:
    cohort = _cohort()
    binding = _binding(cohort)
    selection = select_t088_canary_records(cohort, cohort_binding=binding)
    head = "c" * 40
    authorization = _authorization(head=head, selection=selection, binding=binding)
    authorization["implementation_head"] = "d" * 40
    with pytest.raises(T088CanaryExecutionError, match="exact approved binding"):
        execute_t088_canary(
            authorization=authorization,
            implementation_head=head,
            cohort_rows=cohort,
            cohort_binding=binding,
            selection=selection,
            runner=_runner,
            controller_factory=_controller,
        )

    def drifting_runner(*args):
        row = _runner(*args)
        row["dense_diagnostic"]["diagnostics"]["combat_terminal_margin_v1"] = 99
        return row

    with pytest.raises(T088CanaryExecutionError, match="scalar or raw-evidence drift"):
        execute_t088_canary(
            authorization=_authorization(
                head=head, selection=selection, binding=binding
            ),
            implementation_head=head,
            cohort_rows=cohort,
            cohort_binding=binding,
            selection=selection,
            runner=drifting_runner,
            controller_factory=_controller,
        )


def test_runtime_proxy_uses_only_additive_search_v2_counter_surface() -> None:
    class FakeAdapter:
        def battle_search_v2_with_work_counters(self, snapshot, **kwargs):
            assert snapshot == "restored"
            assert kwargs == {"simulations": 100, "include_potions": False}
            return {
                "native_api": "StepSimulator.battle_search_v2.v1",
                "work_counters": {"schema_id": "native-battle-search-work-v1"},
            }

    proxy = _T088CanaryRuntimeAdapter(FakeAdapter(), "restored")
    assert proxy.reset(seed=None) == "restored"
    assert proxy.battle_search_v2("restored", simulations=100) == {
        "native_api": "StepSimulator.battle_search_v2.v1",
        "work_counters": {"schema_id": "native-battle-search-work-v1"},
    }
    assert proxy._runtime_work_rows == [
        {"schema_id": "native-battle-search-work-v1"}
    ]
    with pytest.raises(T088CanaryExecutionError, match="reused"):
        proxy.reset(seed=None)


def test_aggregate_work_retains_exact_counts_and_marks_unavailable_steps() -> None:
    work = _aggregate_work(
        [
            {
                "schema_id": "native-battle-search-work-v1",
                "successor_transition_count": 7,
                "action_execution_count": 7,
                "tree_node_expansion_count": 3,
                "rollout_count": 2,
                "terminal_utility_evaluation_count": 2,
                "model_calls": 0,
            }
        ],
        arm="A",
        controlled_steps=1,
    )
    assert work["successor_transition_count"] == 7
    assert work["native_simulator_step_count"] is None
    assert "cross-algorithm" in work["native_simulator_step_count_unavailable_reason"]
