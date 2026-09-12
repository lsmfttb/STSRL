"""Fake-only tests for the explicit T088 formal raw-evidence boundary."""

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
from sts_combat_rl.sim.t088_formal_execution import (
    T088_FORMAL_AUTHORIZATION_SCHEMA_ID,
    T088_FORMAL_DEFAULT_SHARD_COUNT,
    T088_FORMAL_SHARD_ASSIGNMENT,
    T088FormalExecutionError,
    _canonical_sha256,
    execute_t088_authorized_formal_shard,
    merge_t088_authorized_formal_shards,
    validate_t088_formal_shard,
    write_t088_formal_shard,
)
from sts_combat_rl.sim.t088_tournament_workflow import (
    _binding_identity,
    build_t088_formal_plan,
    select_t088_canary_records,
)


def _source() -> dict[str, object]:
    return {
        "path": "/retained/t085-selection.json",
        "sha256": "d5c335cd6e1f96e72ae3b302eebca17a5f6531fa0aac97ee2febec2c41c2e752",
        "schema_id": "t085-native-selection-artifact-v1",
        "byte_count": 1,
    }


def _cohort() -> list[dict[str, object]]:
    source = _source()
    rows: list[dict[str, object]] = []
    for cohort, count in (("A", 93), ("B", 192), ("C", 128)):
        rows.extend(
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
    rows[0].update(is_escaping_mugger_case=True, legal_root_action_count=2)
    rows[1].update(is_ordinary_victory=True, legal_root_action_count=2)
    rows[2].update(is_ordinary_loss=True, legal_root_action_count=2)
    rows[93].update(is_later_act_or_boss=True, legal_root_action_count=2)
    rows[94].update(legal_root_action_count=3)
    return rows


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
        "source_selection_manifest_identity": _source(),
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
        "ordered_cohort_entries_sha256": hashlib.sha256(
            json.dumps(entries, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest(),
    }


def _canary_evidence(
    cohort: list[dict[str, object]], binding: dict[str, object]
) -> tuple[dict[str, object], dict[str, object]]:
    selection = select_t088_canary_records(cohort, cohort_binding=binding)
    selected_by_identity = {
        selected["selection_identity"]: selected for selected in selection["selected"]
    }
    rows = [
        {
            "arm": arm,
            "selection_identity": selected["selection_identity"],
            "cohort": selected["cohort"],
            "restore_public_legal_parity": True,
            "outcome": "PLAYER_VICTORY",
            "controller_definition_verified": True,
            "dense_diagnostic_recomputed": True,
            "native_game_mechanics_parity": True,
            "search_v2_parity_verified": arm in {"A", "B"},
            "beam_deterministic_replay_verified": arm == "C",
            "progressive_bias_depth_gt_zero_verified": arm == "D",
            "wall_clock_time_s": 0.1,
            "work_counters": {
                "successor_transition_count": 1,
                "action_execution_count": 1,
                "model_calls": 0,
            },
        }
        for arm in ("A", "B", "C", "D")
        for selected in selected_by_identity.values()
    ]
    evidence = {
        "schema_id": "t088-canary-evidence-v1",
        "task_id": "T088",
        "formal_execution_authorized": False,
        "t087_cohort_binding": _binding_identity(binding),
        "canary_selection": selection,
        "controller_definitions": t088_controller_definitions(),
        "rows": rows,
    }
    encoded = json.dumps(evidence, sort_keys=True, separators=(",", ":")).encode()
    return evidence, {
        "path": "/retained/t088-canary.json",
        "sha256": hashlib.sha256(encoded).hexdigest(),
        "size_bytes": len(encoded),
        "schema_id": "t088-canary-evidence-v1",
    }


def _diagnostic(identity: str, cohort: str) -> dict[str, object]:
    entry = battle_snapshot_evidence(
        {
            "battle_player": {"current_hp": 40, "max_hp": 80},
            "battle_monsters": [{"id_label": "Cultist", "current_hp": 20}],
            "battle_monster_count": 1,
            "battle_monsters_alive": 1,
        }
    )
    terminal = battle_snapshot_evidence(
        {
            "cur_hp": 60,
            "max_hp": 80,
            "completed_battle_outcome": "PLAYER_VICTORY",
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
        },
        require_positive_enemy_hp=False,
    )
    return build_dense_diagnostic_row(
        selection_identity=identity,
        cohort=cohort,
        entry=entry,
        terminal=terminal,
        outcome="PLAYER_VICTORY",
        action_trace=[],
        provenance={
            "task_id": "T088",
            "restore_method": "fake",
            "source_selection_manifest_identity": _source(),
        },
        source_selection_manifest_identity=_source(),
    )


def _controller(arm: str) -> object:
    return SimpleNamespace(provenance={"kind": "fake", "arm": arm})


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
        "dense_diagnostic": _diagnostic(record["selection_identity"], record["cohort"]),
    }


def _authorization(
    cohort, binding, canary_reference, *, head="a" * 40, output_root="/retained"
):
    inputs = {"t087": {"sha256": "f" * 64}}
    plan = build_t088_formal_plan(cohort, cohort_binding=binding)
    return inputs, {
        "schema_id": T088_FORMAL_AUTHORIZATION_SCHEMA_ID,
        "task_id": "T088",
        "authorization_kind": "formal_tournament",
        "authorized": True,
        "authorization_id": "test-formal-auth",
        "implementation_head": head,
        "input_identities_sha256": _canonical_sha256(inputs),
        "canary_evidence": canary_reference,
        "t087_cohort_binding": _binding_identity(binding),
        "controller_definitions_sha256": _canonical_sha256(
            t088_controller_definitions()
        ),
        "formal_plan_sha256": _canonical_sha256(plan),
        "shard_topology": {
            "shard_count": T088_FORMAL_DEFAULT_SHARD_COUNT,
            "worker_count": T088_FORMAL_DEFAULT_SHARD_COUNT,
            "assignment": T088_FORMAL_SHARD_ASSIGNMENT,
        },
        "output_root": output_root,
        "maintainer_attestation": {
            "role": "maintainer",
            "decision": "FORMAL_AUTHORIZED",
            "exact_head": head,
        },
    }


def test_authorized_formal_shard_uses_canonical_modulo_plan_and_atomic_writer(tmp_path):
    cohort = _cohort()
    binding = _binding(cohort)
    canary, canary_reference = _canary_evidence(cohort, binding)
    inputs, authorization = _authorization(cohort, binding, canary_reference)
    shard = execute_t088_authorized_formal_shard(
        authorization=authorization,
        implementation_head="a" * 40,
        input_identities=inputs,
        canary_evidence_reference=canary_reference,
        canary_evidence=canary,
        cohort_rows=cohort,
        cohort_binding=binding,
        shard_index=0,
        shard_count=16,
        worker_count=16,
        output_root="/retained",
        runner=_runner,
        controller_factory=_controller,
    )
    assert shard["execution_count"] == 104
    assert shard["rows"][0]["selection_identity"] == "A:0"
    assert (
        validate_t088_formal_shard(
            shard,
            authorization=authorization,
            implementation_head="a" * 40,
            input_identities=inputs,
            canary_evidence_reference=canary_reference,
            canary_evidence=canary,
            cohort_rows=cohort,
            cohort_binding=binding,
            output_root="/retained",
        )
        == shard["rows"]
    )
    reference = write_t088_formal_shard(tmp_path / "shard-0.json", shard)
    assert reference["schema_id"] == "t088-formal-execution-shard-v1"
    with pytest.raises(T088FormalExecutionError, match="overwrite"):
        write_t088_formal_shard(tmp_path / "shard-0.json", shard)


def test_formal_authorization_failure_cannot_invoke_runner():
    cohort = _cohort()
    binding = _binding(cohort)
    canary, canary_reference = _canary_evidence(cohort, binding)
    inputs, authorization = _authorization(cohort, binding, canary_reference)
    authorization["input_identities_sha256"] = "0" * 64
    invoked = False

    def never(*args):
        nonlocal invoked
        invoked = True
        return _runner(*args)

    with pytest.raises(T088FormalExecutionError, match="exact approved binding"):
        execute_t088_authorized_formal_shard(
            authorization=authorization,
            implementation_head="a" * 40,
            input_identities=inputs,
            canary_evidence_reference=canary_reference,
            canary_evidence=canary,
            cohort_rows=cohort,
            cohort_binding=binding,
            shard_index=0,
            shard_count=16,
            worker_count=16,
            output_root="/retained",
            runner=never,
            controller_factory=_controller,
        )
    assert invoked is False


def test_finalizer_requires_every_shard_and_reorders_to_full_canonical_matrix():
    cohort = _cohort()
    binding = _binding(cohort)
    canary, canary_reference = _canary_evidence(cohort, binding)
    inputs, authorization = _authorization(cohort, binding, canary_reference)
    shards = [
        execute_t088_authorized_formal_shard(
            authorization=authorization,
            implementation_head="a" * 40,
            input_identities=inputs,
            canary_evidence_reference=canary_reference,
            canary_evidence=canary,
            cohort_rows=cohort,
            cohort_binding=binding,
            shard_index=index,
            shard_count=16,
            worker_count=16,
            output_root="/retained",
            runner=_runner,
            controller_factory=_controller,
        )
        for index in range(16)
    ]
    with pytest.raises(T088FormalExecutionError, match="shard set is incomplete"):
        merge_t088_authorized_formal_shards(
            authorization=authorization,
            implementation_head="a" * 40,
            input_identities=inputs,
            canary_evidence_reference=canary_reference,
            canary_evidence=canary,
            cohort_rows=cohort,
            cohort_binding=binding,
            output_root="/retained",
            shards=shards[:-1],
        )
    evidence = merge_t088_authorized_formal_shards(
        authorization=authorization,
        implementation_head="a" * 40,
        input_identities=inputs,
        canary_evidence_reference=canary_reference,
        canary_evidence=canary,
        cohort_rows=cohort,
        cohort_binding=binding,
        output_root="/retained",
        shards=list(reversed(shards)),
    )
    assert evidence["execution_count"] == 1652
    assert [row["arm"] for row in evidence["rows"][:413]] == ["A"] * 413
    assert evidence["rows"][0]["selection_identity"] == "A:0"
