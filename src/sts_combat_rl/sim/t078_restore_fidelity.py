"""Restore-only public-context fidelity audit for the retained T075 cohort."""

from __future__ import annotations

import os
import time
from collections.abc import Mapping, Sequence
from typing import Any

from sts_combat_rl.sim.decision_record import action_identity_dicts_for_actions
from sts_combat_rl.sim.lightspeed import LightSpeedAdapter
from sts_combat_rl.sim.non_combat_learning import T065SourceState, replay_source_state
from sts_combat_rl.sim.public_run_context import (
    build_public_run_context,
    read_native_public_projection,
)


def first_difference(
    expected: Any,
    actual: Any,
    *,
    path: str = "$",
) -> dict[str, Any] | None:
    """Return the first deterministic field-level difference, if any."""

    if type(expected) is not type(actual):
        return {
            "path": path,
            "kind": "type",
            "expected_type": type(expected).__name__,
            "actual_type": type(actual).__name__,
        }
    if isinstance(expected, Mapping):
        for key in sorted(set(expected) | set(actual), key=str):
            child_path = f"{path}.{key}"
            if key not in expected:
                return {"path": child_path, "kind": "unexpected_key"}
            if key not in actual:
                return {"path": child_path, "kind": "missing_key"}
            difference = first_difference(expected[key], actual[key], path=child_path)
            if difference is not None:
                return difference
        return None
    if isinstance(expected, (list, tuple)):
        if len(expected) != len(actual):
            return {
                "path": path,
                "kind": "length",
                "expected": len(expected),
                "actual": len(actual),
            }
        for index, (left, right) in enumerate(zip(expected, actual)):
            difference = first_difference(left, right, path=f"{path}[{index}]")
            if difference is not None:
                return difference
        return None
    if expected != actual:
        return {"path": path, "kind": "value", "expected": expected, "actual": actual}
    return None


def _action_identities(actions: Sequence[Any]) -> tuple[dict[str, Any], ...]:
    return tuple(dict(item) for item in action_identity_dicts_for_actions(actions))


def audit_restored_source_state(
    adapter: LightSpeedAdapter,
    state: T065SourceState,
    *,
    exercise_branch_restore: bool = False,
) -> dict[str, Any]:
    """Compare one replayed source state and checkpoint restore with retention.

    This deliberately executes no counterfactual continuation.  The optional
    branch probe takes one already-eligible root action solely to confirm that
    the checkpoint remains reusable after the same kind of mutation performed
    by the frozen target path.
    """

    snapshot, actions, context, checkpoint = replay_source_state(adapter, state)
    expected_context = dict(state.public_run_context)
    expected_actions = tuple(dict(item) for item in state.legal_action_identities)
    source_actions = _action_identities(actions)
    failures: list[dict[str, Any]] = []
    for label, expected, actual in (
        ("replay_public_context", expected_context, context.public_run_context),
        ("replay_ordered_legal_actions", expected_actions, source_actions),
    ):
        difference = first_difference(expected, actual)
        if difference is not None:
            failures.append({"boundary": label, "difference": difference})

    restore_count = 2 if exercise_branch_restore else 1
    for restore_index in range(restore_count):
        restored = adapter.restore_checkpoint(checkpoint)
        restored_actions = tuple(adapter.legal_actions(restored))
        restored_context = build_public_run_context(
            restored.raw,
            restored_actions,
            projection=read_native_public_projection(adapter, restored),
            history=[
                item
                for item in context.public_run_context["history"]
                if isinstance(item, Mapping)
            ],
        )
        for label, expected, actual in (
            ("restore_public_context", expected_context, restored_context),
            (
                "restore_ordered_legal_actions",
                expected_actions,
                _action_identities(restored_actions),
            ),
        ):
            difference = first_difference(expected, actual)
            if difference is not None:
                failures.append(
                    {
                        "boundary": label,
                        "restore_index": restore_index,
                        "difference": difference,
                    }
                )
        if restore_index == 0 and exercise_branch_restore:
            action_index = state.eligible_action_indices[0]
            adapter.step(restored_actions[action_index])

    return {
        "selected_state_index": state.selected_state_index,
        "family": state.family,
        "simulator_seed": state.simulator_seed,
        "source_step_index": state.source_step_index,
        "restore_count": restore_count,
        "passed": not failures,
        "failures": failures,
        "snapshot_transition_annotation_present": (
            "completed_battle_outcome" in snapshot.raw
        ),
    }


def audit_restore_fidelity_shard(
    states: Sequence[T065SourceState],
    *,
    exercise_branch_restore: bool = False,
) -> dict[str, Any]:
    """Audit one contiguous shard in one native adapter process."""

    started = time.process_time()
    adapter = LightSpeedAdapter(seed=1, ascension=20, player_class="IRONCLAD")
    rows: list[dict[str, Any]] = []
    for state in states:
        try:
            rows.append(
                audit_restored_source_state(
                    adapter, state, exercise_branch_restore=exercise_branch_restore
                )
            )
        except Exception as exc:  # noqa: BLE001 - retain every fidelity diagnostic
            rows.append(
                {
                    "selected_state_index": state.selected_state_index,
                    "family": state.family,
                    "simulator_seed": state.simulator_seed,
                    "source_step_index": state.source_step_index,
                    "restore_count": 0,
                    "passed": False,
                    "failures": [
                        {
                            "boundary": "replay_or_restore_exception",
                            "error_type": type(exc).__name__,
                            "message": str(exc),
                        }
                    ],
                    "snapshot_transition_annotation_present": False,
                }
            )
    return {
        "pid": os.getpid(),
        "cpu_seconds": time.process_time() - started,
        "selected_state_start": states[0].selected_state_index if states else None,
        "selected_state_end": states[-1].selected_state_index if states else None,
        "rows": rows,
    }
