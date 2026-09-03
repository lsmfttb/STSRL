#!/usr/bin/env python3
"""Probe the exact native runtime required by the T084 collector contract."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--native-commit", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    import slaythespire

    methods = {
        name: hasattr(slaythespire.StepSimulator, name)
        for name in (
            "battle_search_v2_with_leaf_collection",
            "evaluate_leaf_continuation",
            "capture_checkpoint",
            "restore_checkpoint",
        )
    }
    simulator = slaythespire.StepSimulator(slaythespire.CharacterClass.IRONCLAD, 1, 20)
    battle_steps = 0
    for battle_steps in range(200):
        snapshot = simulator.snapshot()
        if snapshot.get("screen_state") == "BATTLE":
            break
        actions = simulator.legal_actions()
        if not actions:
            raise RuntimeError(
                "native probe reached a non-battle screen without actions"
            )
        simulator.step(actions[0])
    else:
        raise RuntimeError("native probe did not reach a battle")

    captured: list[tuple[object, ...]] = []

    def collect(*values: object) -> None:
        captured.append(values)

    off = simulator.battle_search_v2(4, False, None, None)
    on = simulator.battle_search_v2_with_leaf_collection(
        4,
        False,
        None,
        None,
        {"schema_id": "t084-native-internal-leaf-collector-v1"},
        collect,
    )
    if not captured:
        raise RuntimeError("native collector produced no callback records")
    checkpoint = captured[0][0]
    first = simulator.evaluate_leaf_continuation(checkpoint, 987654321, 2048, False)
    second = simulator.evaluate_leaf_continuation(checkpoint, 987654321, 2048, False)
    probe = {
        "schema_id": "t084-native-runtime-probe-v1",
        "python_executable": sys.executable,
        "python_version": sys.version.split()[0],
        "extension": str(Path(slaythespire.__file__).resolve()),
        "native_commit": args.native_commit,
        "api_methods": methods,
        "smoke": {
            "battle_steps_to_probe": battle_steps,
            "collector_rows": len(captured),
            "collector_payload_bytes": len(captured[0][7]),
            "collector_has_checkpoint": checkpoint is not None,
            "collector_has_digest": bool(captured[0][6]),
            "collector_has_rng": bool(captured[0][8]),
            "collector_off_on_root_rows_equal": off.get("root_rows")
            == on.get("root_rows"),
            "collector_off_on_material_outputs_equal": off.get("root_rows")
            == on.get("root_rows"),
            "restore_replay_equal": first == second,
            "replay_terminal": first.get("terminal") is True,
            "replay_cap_hit": first.get("cap_hit") is True,
            "replay_transition_count": first.get("transition_count"),
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(probe, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(probe, sort_keys=True))
    return (
        0
        if all(methods.values())
        and probe["smoke"]["collector_off_on_root_rows_equal"]
        and probe["smoke"]["restore_replay_equal"]
        else 2
    )


if __name__ == "__main__":
    raise SystemExit(main())
