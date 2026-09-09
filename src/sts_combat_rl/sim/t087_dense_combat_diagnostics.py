"""T087 dense Combat diagnostics and bounded rescue/audit workflow.

This module owns only repository-side evidence handling.  Native restore,
Search-v2, battle transitions, and HP transforms remain delegated to the
accepted T085/T078 simulator seams.  The public functions deliberately accept
plain mappings so that formal jobs can stream current-schema artifacts without
coupling the diagnostic formulas to a simulator wrapper.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Iterable, Mapping, Sequence
import hashlib
import json
import math
from pathlib import Path
from statistics import mean

from sts_combat_rl.sim.action_space import ActionSpaceConfig
from sts_combat_rl.sim.controlled_run import ControlledRun, execute_controlled_run
from sts_combat_rl.commands.t085_native_execution import (
    T085NativeTerminalSearchAdapter,
    T085NativeExecutionError,
    T085UnguidedBattleSearchV2Controller,
    restore_t085_canonical_record,
)


T087_TASK_ID = "T087"
T087_APPROVED_SPEC = "4bec26c0ea43116d2ea369e16cbffe9cc5f07e61"
T087_BASE_COMMIT = "b38c0584e4aac9172f9da4426004bfb64a13a41d"
T087_NATIVE_COMMIT = "d62ff35579b54d70a7428afdf84743c94df3fe0c"
T085_SCIENTIFIC_HEAD = "5edaa255959d34d4d31bbfae7e6b6bed9758024d"
T085_SELECTION_SHA256 = "d5c335cd6e1f96e72ae3b302eebca17a5f6531fa0aac97ee2febec2c41c2e752"
T085_RESTORE_SHA256 = "0adbdc4e055bd8d53680757a395e3e7973b7242b06db1c5053281ef883b679ef"
T085_PAIRED_REPORT_SHA256 = "f756c9f4ac885c61c2a73ff9b2d0e05a15b317df2cce9c9bf5dbd374f7afcec3"
T052_COHORT_SHA256 = "b7f8e9b85b53bbf8e37adfe6cc90d0579937661309b26bce2a8f2921604a8608"
T087_NATURAL_RECORD_COUNT = 413
T087_COHORT_COUNTS = {"A": 93, "B": 192, "C": 128}
T087_HP_SAMPLE_PER_COHORT = 8
T087_AUDIT_SAMPLE_PER_STRATUM = 8
T087_HP_DOMAIN = "T087-hp-rescue-v1\n"
T087_AUDIT_DOMAIN = "T087-human-audit-v1\n"
T087_AUDIT_NEAR_THRESHOLDS = (0.25, 0.35, 0.50, 0.65, 0.75, 1.00)
T087_AUDIT_DEEP_THRESHOLDS = (0.75, 0.65, 0.50, 0.35, 0.25, 0.00)
T087_TERMINAL_CLASSES = frozenset({"PLAYER_VICTORY", "PLAYER_LOSS"})
T087_POTION_ACTION_KINDS = frozenset(
    {"potion", "potion_discard", "game_potion_use", "game_potion_discard"}
)


class T087IncompleteError(ValueError):
    """A frozen T087 boundary cannot be satisfied from the retained evidence."""


def canonical_json_bytes(value: object) -> bytes:
    """Return exactly the amendment's digest-bearing JSON serialization."""

    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def selection_identity_bytes(selection_identity: str) -> bytes:
    """Return the exact occurrence-safe T085 identity byte representation."""

    if not isinstance(selection_identity, str) or not selection_identity:
        raise T087IncompleteError("selection_identity must be a non-empty string")
    return selection_identity.encode("utf-8")


def selection_digest(selection_identity: str, *, domain: str) -> str:
    """Hash an identity using a T087 domain prefix and no other representation."""

    if domain not in {"hp", "human_audit"}:
        raise ValueError("T087 selection digest domain is unsupported")
    prefix = T087_HP_DOMAIN if domain == "hp" else T087_AUDIT_DOMAIN
    return hashlib.sha256(
        prefix.encode("ascii") + selection_identity_bytes(selection_identity)
    ).hexdigest()


def _finite(value: object, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise T087IncompleteError(f"{label} must be numeric")
    result = float(value)
    if not math.isfinite(result):
        raise T087IncompleteError(f"{label} must be finite")
    return result


def _positive(value: object, label: str) -> float:
    result = _finite(value, label)
    if result <= 0:
        raise T087IncompleteError(f"{label} must be positive")
    return result


def _enemy_rows(value: object, label: str) -> list[dict[str, object]]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise T087IncompleteError(f"{label} must be an ordered enemy sequence")
    result: list[dict[str, object]] = []
    for index, raw in enumerate(value):
        if not isinstance(raw, Mapping):
            raise T087IncompleteError(f"{label}[{index}] is not an object")
        identity = raw.get("identity", raw.get("id", raw.get("name")))
        if not isinstance(identity, str) or not identity:
            raise T087IncompleteError(f"{label}[{index}] lacks enemy identity")
        hp = _finite(raw.get("current_hp"), f"{label}[{index}].current_hp")
        if hp < 0:
            raise T087IncompleteError(f"{label}[{index}].current_hp is negative")
        item = dict(raw)
        item["identity"] = identity
        item["current_hp"] = hp
        result.append(item)
    return result


def _player_value(raw: Mapping[str, object], key: str) -> object:
    if key in raw:
        return raw[key]
    for container in ("player", "battle_player", "persistent_resources"):
        nested = raw.get(container)
        if isinstance(nested, Mapping) and key in nested:
            return nested[key]
    aliases = {
        "current_hp": ("cur_hp", "battle_player_hp"),
        "max_hp": ("player_max_hp",),
    }
    for alias in aliases.get(key, ()):
        if alias in raw:
            return raw[alias]
    return None


def battle_snapshot_evidence(
    raw: Mapping[str, object], *, require_positive_enemy_hp: bool = True
) -> dict[str, object]:
    """Normalize accepted raw snapshot fields without inventing missing state."""

    monsters = raw.get("battle_monsters", raw.get("monsters"))
    enemies = _enemy_rows(monsters, "battle snapshot enemies")
    current_hp = _finite(_player_value(raw, "current_hp"), "player current_hp")
    max_hp = _positive(_player_value(raw, "max_hp"), "player max_hp")
    total = sum(float(enemy["current_hp"]) for enemy in enemies)
    if not math.isfinite(total) or (
        require_positive_enemy_hp and total <= 0
    ):
        raise T087IncompleteError("battle_start_total_enemy_hp must be positive")
    return {
        "player_current_hp": current_hp,
        "player_max_hp": max_hp,
        "enemies": enemies,
        "battle_start_total_enemy_hp": total,
        "enemy_occurrences_complete": True,
        "visible_terminal_resources": dict(
            raw.get("completed_battle_resource_outcome", {})
        )
        if isinstance(raw.get("completed_battle_resource_outcome"), Mapping)
        else {},
        "raw_snapshot": dict(raw),
    }


def _alive(enemy: Mapping[str, object]) -> bool:
    if enemy.get("is_gone") is True or enemy.get("dead") is True:
        return False
    return float(enemy["current_hp"]) > 0.0


def _action_potion_count(action_trace: Sequence[Mapping[str, object]]) -> int:
    count = 0
    for action in action_trace:
        if not isinstance(action, Mapping):
            raise T087IncompleteError("action trace contains a non-object step")
        kind = action.get("chosen_action_kind", action.get("kind"))
        if isinstance(kind, str) and kind in T087_POTION_ACTION_KINDS:
            count += 1
    return count


def build_dense_diagnostic_row(
    *,
    selection_identity: str,
    cohort: str,
    entry: Mapping[str, object],
    terminal: Mapping[str, object],
    outcome: str,
    action_trace: Sequence[Mapping[str, object]] = (),
    provenance: Mapping[str, object] | None = None,
) -> dict[str, object]:
    """Build one recomputable T087 dense row from raw entry/terminal evidence."""

    if cohort not in T087_COHORT_COUNTS:
        raise T087IncompleteError(f"unknown T087 cohort {cohort!r}")
    if outcome not in T087_TERMINAL_CLASSES:
        raise T087IncompleteError("outcome is not authoritative PLAYER_VICTORY/LOSS")
    identity = selection_identity_bytes(selection_identity)
    del identity  # Validate the exact string before retaining it.
    start_enemies = _enemy_rows(entry.get("enemies"), "entry.enemies")
    terminal_enemies = _enemy_rows(terminal.get("enemies"), "terminal.enemies")
    if terminal.get("enemy_occurrences_complete") is not True:
        raise T087IncompleteError("terminal enemy occurrence completeness is unavailable")
    start_total = _positive(
        entry.get("battle_start_total_enemy_hp"), "battle_start_total_enemy_hp"
    )
    terminal_total = sum(float(enemy["current_hp"]) for enemy in terminal_enemies)
    if not math.isfinite(terminal_total) or terminal_total < 0:
        raise T087IncompleteError("terminal enemy HP total is invalid")
    initial_count = len(start_enemies)
    alive_terminal = sum(_alive(enemy) for enemy in terminal_enemies)
    if initial_count <= 0:
        raise T087IncompleteError("enemy_count_initial must be positive")
    killed = initial_count - alive_terminal
    if killed < 0 or killed > initial_count:
        raise T087IncompleteError("terminal enemy occurrence count is inconsistent")

    start_player_hp = _finite(entry.get("player_current_hp"), "entry.player_current_hp")
    start_max_hp = _positive(entry.get("player_max_hp"), "entry.player_max_hp")
    terminal_player_hp = _finite(
        terminal.get("player_current_hp"), "terminal.player_current_hp"
    )
    remaining_fraction = terminal_total / start_total
    damage_fraction = 1.0 - remaining_fraction
    player_fraction = terminal_player_hp / start_max_hp
    margin = player_fraction if outcome == "PLAYER_VICTORY" else -remaining_fraction
    for label, value in (
        ("enemy_kill_fraction", killed / initial_count),
        ("enemy_hp_remaining_fraction", remaining_fraction),
        ("enemy_damage_fraction", damage_fraction),
        ("player_hp_remaining_fraction_of_max", player_fraction),
        ("combat_terminal_margin_v1", margin),
    ):
        if not math.isfinite(value):
            raise T087IncompleteError(f"{label} is not finite")
    if not 0.0 <= killed / initial_count <= 1.0:
        raise T087IncompleteError("enemy_kill_fraction is outside [0,1]")
    if outcome == "PLAYER_VICTORY" and margin < 0.0:
        raise T087IncompleteError("victory margin is negative")
    if outcome == "PLAYER_LOSS" and margin > 0.0:
        raise T087IncompleteError("loss margin is positive")

    trace = [dict(item) for item in action_trace]
    return {
        "schema_id": "t087-dense-combat-diagnostic-row-v1",
        "task_id": T087_TASK_ID,
        "selection_identity": selection_identity,
        "cohort": cohort,
        "outcome": outcome,
        "entry": dict(entry),
        "terminal": dict(terminal),
        "raw_entry": entry.get("raw_snapshot", dict(entry)),
        "raw_terminal": terminal.get("raw_snapshot", dict(terminal)),
        "action_trace": trace,
        "diagnostics": {
            "enemy_count_initial": initial_count,
            "enemy_count_alive_terminal": alive_terminal,
            "enemy_count_killed": killed,
            "enemy_kill_fraction": killed / initial_count,
            "battle_start_total_enemy_hp": start_total,
            "terminal_total_enemy_hp": terminal_total,
            "enemy_hp_remaining_fraction": remaining_fraction,
            "enemy_damage_fraction": damage_fraction,
            "player_hp_remaining_fraction_of_max": player_fraction,
            "net_player_hp_delta": terminal_player_hp - start_player_hp,
            "combat_terminal_margin_v1": margin,
        },
        "action_count": len(trace),
        "potion_action_count": _action_potion_count(trace),
        "provenance": dict(provenance or {}),
    }


def _row_identity(row: Mapping[str, object]) -> str:
    identity = row.get("selection_identity", row.get("record_identity"))
    if not isinstance(identity, str) or not identity:
        raise T087IncompleteError("diagnostic row lacks selection_identity")
    return identity


def _validate_unique_rows(rows: Iterable[Mapping[str, object]]) -> tuple[dict[str, object], ...]:
    normalized = tuple(dict(row) for row in rows)
    identities = [_row_identity(row) for row in normalized]
    if len(set(identities)) != len(identities):
        raise T087IncompleteError("duplicate selection_identity in T087 ranking domain")
    return normalized


def validate_dense_diagnostic_row(row: Mapping[str, object]) -> None:
    """Recompute a retained row and fail closed on any scalar drift."""

    identity = _row_identity(row)
    entry = row.get("entry")
    terminal = row.get("terminal")
    outcome = row.get("outcome")
    if not isinstance(entry, Mapping) or not isinstance(terminal, Mapping):
        raise T087IncompleteError(f"{identity}: raw entry/terminal evidence is missing")
    if not isinstance(outcome, str):
        raise T087IncompleteError(f"{identity}: authoritative outcome is missing")
    rebuilt = build_dense_diagnostic_row(
        selection_identity=identity,
        cohort=str(row.get("cohort", "")),
        entry=entry,
        terminal=terminal,
        outcome=outcome,
        action_trace=row.get("action_trace", ())  # type: ignore[arg-type]
        if isinstance(row.get("action_trace", ()), Sequence)
        else (),
        provenance=row.get("provenance")  # type: ignore[arg-type]
        if isinstance(row.get("provenance"), Mapping)
        else None,
    )
    expected = rebuilt["diagnostics"]
    observed = row.get("diagnostics")
    if not isinstance(observed, Mapping) or dict(observed) != dict(expected):
        raise T087IncompleteError(f"{identity}: diagnostics do not recompute from raw evidence")
    provenance = row.get("provenance")
    if not isinstance(provenance, Mapping):
        raise T087IncompleteError(f"{identity}: execution provenance is missing")
    for key, expected_value in (
        ("seed", None),
        ("max_steps", 200),
        ("policy_prior_callback", False),
        ("learned_leaf_value_callback", False),
        ("no_additional_search_seed", True),
    ):
        if provenance.get(key) != expected_value:
            raise T087IncompleteError(f"{identity}: provenance {key} is not frozen")


def _manifest_payload(
    *, domain: str, selections: Sequence[Mapping[str, object]]
) -> dict[str, object]:
    payload = {
        "schema_id": "t087-selection-manifest-v1",
        "task_id": T087_TASK_ID,
        "selection_domain": domain,
        "selected": [dict(selection) for selection in selections],
    }
    digest = hashlib.sha256(canonical_json_bytes(payload)).hexdigest()
    return {**payload, "canonical_sha256": digest}


def select_hp_rescue_losses(
    rows: Iterable[Mapping[str, object]],
) -> dict[str, object]:
    """Select exactly eight natural losses from each A/B/C cohort."""

    normalized = _validate_unique_rows(rows)
    selected: list[dict[str, object]] = []
    for cohort in ("A", "B", "C"):
        eligible = [
            row
            for row in normalized
            if row.get("cohort") == cohort and row.get("outcome") == "PLAYER_LOSS"
        ]
        if len(eligible) < T087_HP_SAMPLE_PER_COHORT:
            raise T087IncompleteError(f"cohort {cohort} has fewer than eight losses")
        ranked = sorted(
            eligible,
            key=lambda row: (
                selection_digest(_row_identity(row), domain="hp"),
                selection_identity_bytes(_row_identity(row)),
            ),
        )
        for rank, row in enumerate(ranked[:T087_HP_SAMPLE_PER_COHORT]):
            identity = _row_identity(row)
            selected.append(
                {
                    "selection_role": "hp_rescue_loss",
                    "cohort": cohort,
                    "selected_rank": rank,
                    "selection_identity": identity,
                    "selection_digest": selection_digest(identity, domain="hp"),
                    "source_selection_manifest_identity": identity,
                }
            )
    return _manifest_payload(domain="hp_rescue", selections=selected)


def _rank_audit(rows: Sequence[Mapping[str, object]]) -> list[Mapping[str, object]]:
    return sorted(
        rows,
        key=lambda row: (
            selection_digest(_row_identity(row), domain="human_audit"),
            selection_identity_bytes(_row_identity(row)),
        ),
    )


def select_blind_audit_rows(rows: Iterable[Mapping[str, object]]) -> dict[str, object]:
    """Freeze the exact 8/8/8 blind-audit identities before trace inspection."""

    normalized = _validate_unique_rows(rows)
    wins = [row for row in normalized if row.get("outcome") == "PLAYER_VICTORY"]
    losses = [row for row in normalized if row.get("outcome") == "PLAYER_LOSS"]
    if len(wins) < 8:
        raise T087IncompleteError("fewer than eight natural victories for blind audit")
    selected: list[dict[str, object]] = []
    for rank, row in enumerate(_rank_audit(wins)[:8]):
        identity = _row_identity(row)
        selected.append(
            {
                "selection_role": "human_audit_win",
                "audit_stratum": "wins",
                "selected_rank": rank,
                "selection_identity": identity,
                "selection_digest": selection_digest(identity, domain="human_audit"),
                "threshold": None,
            }
        )
    near: list[Mapping[str, object]] = []
    near_threshold = None
    for threshold in T087_AUDIT_NEAR_THRESHOLDS:
        candidate = [
            row
            for row in losses
            if _diagnostic(row, "enemy_hp_remaining_fraction") <= threshold
        ]
        if len(candidate) >= 8:
            near = candidate
            near_threshold = threshold
            break
    if near_threshold is None:
        raise T087IncompleteError("no near-boundary loss threshold supplies eight rows")
    near_ids = {_row_identity(row) for row in _rank_audit(near)[:8]}
    for rank, row in enumerate(_rank_audit(near)[:8]):
        identity = _row_identity(row)
        selected.append(
            {
                "selection_role": "human_audit_near_loss",
                "audit_stratum": "near_boundary_losses",
                "selected_rank": rank,
                "selection_identity": identity,
                "selection_digest": selection_digest(identity, domain="human_audit"),
                "threshold": near_threshold,
            }
        )
    deep: list[Mapping[str, object]] = []
    deep_threshold = None
    for threshold in T087_AUDIT_DEEP_THRESHOLDS:
        candidate = [
            row
            for row in losses
            if _row_identity(row) not in near_ids
            and _diagnostic(row, "enemy_hp_remaining_fraction") >= threshold
        ]
        if len(candidate) >= 8:
            deep = candidate
            deep_threshold = threshold
            break
    if deep_threshold is None:
        raise T087IncompleteError("no deep-loss threshold supplies eight rows")
    for rank, row in enumerate(_rank_audit(deep)[:8]):
        identity = _row_identity(row)
        selected.append(
            {
                "selection_role": "human_audit_deep_loss",
                "audit_stratum": "deep_losses",
                "selected_rank": rank,
                "selection_identity": identity,
                "selection_digest": selection_digest(identity, domain="human_audit"),
                "threshold": deep_threshold,
            }
        )
    if len({_row_identity(row) for row in selected}) != 24:
        raise T087IncompleteError("blind audit groups are not pairwise disjoint")
    return _manifest_payload(domain="human_audit", selections=selected)


def _diagnostic(row: Mapping[str, object], name: str) -> float:
    diagnostics = row.get("diagnostics")
    value = diagnostics.get(name) if isinstance(diagnostics, Mapping) else row.get(name)
    return _finite(value, f"row diagnostics.{name}")


def hp_rescue_ladder(player_start_hp: object, player_max_hp: object) -> tuple[int, ...]:
    """Return the exact unique sorted bounded HP-addition ladder."""

    start = _finite(player_start_hp, "player_start_hp")
    maximum = _finite(player_max_hp, "player_max_hp")
    if start < 0 or maximum < start:
        raise T087IncompleteError("invalid HP bounds for rescue ladder")
    gap = int(maximum - start)
    return tuple(sorted({0, min(5, gap), min(10, gap), min(20, gap), gap}))


def build_review_rubric() -> dict[str, object]:
    return {
        "schema_id": "t087-human-review-rubric-v1",
        "task_id": T087_TASK_ID,
        "fields": [
            {"name": "start_winnability", "values": ["clearly_winnable", "difficult_but_winnable", "likely_doomed", "uncertain"]},
            {"name": "combat_execution_quality", "values": ["major_tactical_error", "minor_tactical_error", "no_obvious_major_error", "uncertain"]},
            {"name": "dominant_failure_source", "values": ["combat_execution", "precombat_state", "mixed", "uncertain"]},
            {"name": "earliest_decisive_step_or_turn", "optional": True, "type": "string"},
            {"name": "confidence", "type": "integer", "minimum": 1, "maximum": 5},
            {"name": "notes", "optional": True, "type": "string"},
        ],
        "human_labels_are_algorithmically_unused": True,
    }


def _public_state(raw: object) -> dict[str, object]:
    """Project a trace snapshot to fields a player can observe in battle."""

    if not isinstance(raw, Mapping):
        return {}
    allowed = {
        "screen_state",
        "act",
        "floor",
        "floor_num",
        "room_type",
        "encounter_id",
        "current_hp",
        "max_hp",
        "battle_player_hp",
        "player_max_hp",
        "energy",
        "block",
        "gold",
    }
    state = {key: raw[key] for key in allowed if key in raw}
    monsters = raw.get("battle_monsters", raw.get("monsters"))
    if isinstance(monsters, Sequence) and not isinstance(monsters, (str, bytes)):
        public_monsters = []
        for monster in monsters:
            if not isinstance(monster, Mapping):
                continue
            public_monsters.append(
                {
                    key: monster[key]
                    for key in ("id", "name", "current_hp", "intent", "is_gone")
                    if key in monster
                }
            )
        state["battle_monsters"] = public_monsters
    return state


def build_blind_trace_bundle(
    *,
    selected_manifest: Mapping[str, object],
    rows: Iterable[Mapping[str, object]],
) -> tuple[dict[str, object], dict[str, object]]:
    """Build a public trace bundle and a separate hidden identity/provenance map."""

    row_by_identity = {_row_identity(row): row for row in rows}
    public_traces: list[dict[str, object]] = []
    hidden_map: list[dict[str, object]] = []
    selected = selected_manifest.get("selected")
    if not isinstance(selected, Sequence) or isinstance(selected, (str, bytes)):
        raise T087IncompleteError("blind-audit manifest has no selected rows")
    for trace_id, selection in enumerate(selected):
        if not isinstance(selection, Mapping):
            raise T087IncompleteError("blind-audit manifest selection is malformed")
        identity = selection.get("selection_identity")
        if not isinstance(identity, str) or identity not in row_by_identity:
            raise T087IncompleteError("blind-audit trace identity is unavailable")
        row = row_by_identity[identity]
        raw_trace = row.get("action_trace", row.get("trace", []))
        if not isinstance(raw_trace, Sequence) or isinstance(raw_trace, (str, bytes)):
            raise T087IncompleteError(f"blind-audit trace {identity} is unavailable")
        steps: list[dict[str, object]] = []
        for raw_step in raw_trace:
            if not isinstance(raw_step, Mapping):
                raise T087IncompleteError(f"blind-audit trace {identity} has malformed step")
            public_state = raw_step.get("public_state", raw_step.get("tactical_state"))
            if not isinstance(public_state, Mapping):
                public_state = _public_state(raw_step.get("snapshot_raw"))
            steps.append(
                {
                    "step_index": raw_step.get("step_index"),
                    "chosen_action_kind": raw_step.get("chosen_action_kind", raw_step.get("kind")),
                    "chosen_action_identity": dict(raw_step.get("chosen_action_identity", {}))
                    if isinstance(raw_step.get("chosen_action_identity", {}), Mapping)
                    else {},
                    "public_state": dict(public_state),
                    "terminal_after_step": raw_step.get("terminal_after_step"),
                }
            )
        if not steps:
            raise T087IncompleteError(f"blind-audit trace {identity} has no steps")
        public_traces.append({"trace_id": trace_id, "steps": steps})
        hidden_map.append(
            {
                "trace_id": trace_id,
                "selection_identity": identity,
                "cohort": row.get("cohort"),
                "provenance": dict(row.get("provenance", {}))
                if isinstance(row.get("provenance"), Mapping)
                else {},
            }
        )
    return (
        {"schema_id": "t087-blind-audit-bundle-v1", "traces": public_traces},
        {
            "schema_id": "t087-blind-audit-hidden-provenance-v1",
            "trace_map": hidden_map,
        },
    )


def _trace_for_controlled_run(controlled: ControlledRun) -> list[dict[str, object]]:
    return [
        {
            "step_index": step.step_index,
            "chosen_action_kind": step.chosen_action_kind,
            "chosen_action_identity": dict(step.chosen_action_identity),
            "public_state": dict(step.tactical_state),
            "snapshot_raw": dict(step.snapshot_raw),
            "next_snapshot_raw": dict(step.next_snapshot_raw),
            "terminal_after_step": step.terminal_after_step,
        }
        for step in controlled.steps
    ]


def _terminal_raw(controlled: ControlledRun) -> Mapping[str, object]:
    if controlled.steps:
        candidate = controlled.steps[-1].next_snapshot_raw
        if candidate:
            return candidate
    return controlled.final_raw


def run_t087_native_record(
    *,
    record: object,
    cohort: str,
    canonical_records: Mapping[str, object],
    adapter_factory: Callable[[], object],
) -> dict[str, object]:
    """Evaluate one restored record through the accepted T085 boundary.

    The function is intentionally one-record granular so formal jobs can shard
    it externally.  It never supplies a simulator/controller/per-record seed.
    """

    try:
        restored_adapter = adapter_factory()
        restored, restore_method = restore_t085_canonical_record(
            restored_adapter, record, canonical_records
        )
        entry = battle_snapshot_evidence(restored.raw)
        adapter = T085NativeTerminalSearchAdapter(
            restored_adapter,
            search_simulations=100,
            search_backend="battle_search_v2",
            policy_prior_callback=None,
            leaf_value_callback=None,
        )
        adapter.prime_restored_snapshot(restored)
        controller = T085UnguidedBattleSearchV2Controller(simulations=100)
        controlled = execute_controlled_run(
            adapter,
            controller,
            seed=None,
            max_steps=200,
            action_space=ActionSpaceConfig.initial_no_potions(),
        )
    except (T085NativeExecutionError, T087IncompleteError, RuntimeError, ValueError) as exc:
        raise T087IncompleteError(f"{_record_identity(record)}: {exc}") from exc
    if not controlled.terminal or controlled.problems:
        raise T087IncompleteError(
            f"{_record_identity(record)}: controlled Battle did not terminate: "
            + "; ".join(controlled.problems)
        )
    terminal = battle_snapshot_evidence(
        _terminal_raw(controlled), require_positive_enemy_hp=False
    )
    outcome = str(terminal["raw_snapshot"].get("completed_battle_outcome", ""))
    if outcome not in T087_TERMINAL_CLASSES:
        outcome = str(
            terminal["raw_snapshot"].get(
                "battle_outcome", terminal["raw_snapshot"].get("outcome", "")
            )
        )
    if outcome not in T087_TERMINAL_CLASSES:
        raise T087IncompleteError(f"{_record_identity(record)}: terminal outcome unavailable")
    identity = _record_identity(record)
    return build_dense_diagnostic_row(
        selection_identity=identity,
        cohort=cohort,
        entry=entry,
        terminal=terminal,
        outcome=outcome,
        action_trace=_trace_for_controlled_run(controlled),
        provenance={
            "task_id": T087_TASK_ID,
            "restore_method": restore_method,
            "native_commit": T087_NATIVE_COMMIT,
            "search_api": "StepSimulator.battle_search_v2.v1",
            "search_budget": 100,
            "root_selection_rule": "highest_mean",
            "policy_prior_callback": False,
            "learned_leaf_value_callback": False,
            "action_space": ActionSpaceConfig.initial_no_potions().to_dict(),
            "seed": None,
            "max_steps": 200,
            "no_additional_search_seed": True,
        },
    )


def run_t087_natural_evaluation(
    *,
    records_by_cohort: Mapping[str, Sequence[object]],
    canonical_records_by_cohort: Mapping[str, Mapping[str, object]],
    adapter_factory: Callable[[], object],
) -> list[dict[str, object]]:
    """Evaluate the exact A/B/C selection without drop, replacement, or reselection."""

    if set(records_by_cohort) != set(T087_COHORT_COUNTS):
        raise T087IncompleteError("T087 natural evaluation requires exactly A, B, and C")
    rows: list[dict[str, object]] = []
    for cohort, expected_count in T087_COHORT_COUNTS.items():
        records = tuple(records_by_cohort[cohort])
        if len(records) != expected_count:
            raise T087IncompleteError(
                f"cohort {cohort} contains {len(records)} records, expected {expected_count}"
            )
        canonical = canonical_records_by_cohort.get(cohort)
        if canonical is None:
            raise T087IncompleteError(f"canonical restore map for cohort {cohort} is unavailable")
        for record in records:
            rows.append(
                run_t087_native_record(
                    record=record,
                    cohort=cohort,
                    canonical_records=canonical,
                    adapter_factory=adapter_factory,
                )
            )
    return rows


def run_t087_hp_rescue_variant(
    *,
    record: object,
    cohort: str,
    extra_hp: int,
    canonical_records: Mapping[str, object],
    adapter_factory: Callable[[], object],
) -> dict[str, object]:
    """Run one accepted native current-HP-only rescue variant."""

    if isinstance(extra_hp, bool) or not isinstance(extra_hp, int) or extra_hp < 0:
        raise T087IncompleteError("HP rescue extra_hp must be a non-negative integer")
    identity = _record_identity(record)
    try:
        restored_adapter = adapter_factory()
        restored, restore_method = restore_t085_canonical_record(
            restored_adapter, record, canonical_records
        )
        entry_snapshot = restored
        if extra_hp:
            rebuild = getattr(restored_adapter, "rebuild_battle_start", None)
            if not callable(rebuild):
                raise T087IncompleteError("accepted native HP-addition transform is unavailable")
            transformed = rebuild(
                restored,
                hp_bonus=extra_hp,
                add_random_potion=False,
                encounter_id=None,
            )
            before_hp = _finite(_player_value(restored.raw, "current_hp"), "restored current_hp")
            after_hp = _finite(_player_value(transformed.raw, "current_hp"), "transformed current_hp")
            if after_hp - before_hp != extra_hp:
                raise T087IncompleteError("native HP transform did not apply the requested exact delta")
            entry_snapshot = transformed
        entry = battle_snapshot_evidence(entry_snapshot.raw)
        adapter = T085NativeTerminalSearchAdapter(
            restored_adapter,
            search_simulations=100,
            search_backend="battle_search_v2",
            policy_prior_callback=None,
            leaf_value_callback=None,
        )
        adapter.prime_restored_snapshot(entry_snapshot)
        controller = T085UnguidedBattleSearchV2Controller(simulations=100)
        controlled = execute_controlled_run(
            adapter,
            controller,
            seed=None,
            max_steps=200,
            action_space=ActionSpaceConfig.initial_no_potions(),
        )
    except (T085NativeExecutionError, T087IncompleteError, RuntimeError, ValueError) as exc:
        raise T087IncompleteError(f"{identity} HP rescue +{extra_hp}: {exc}") from exc
    if not controlled.terminal or controlled.problems:
        raise T087IncompleteError(
            f"{identity} HP rescue +{extra_hp} did not terminate: "
            + "; ".join(controlled.problems)
        )
    terminal = battle_snapshot_evidence(
        _terminal_raw(controlled), require_positive_enemy_hp=False
    )
    terminal_raw = terminal["raw_snapshot"]
    outcome = str(
        terminal_raw.get(
            "completed_battle_outcome",
            terminal_raw.get("battle_outcome", terminal_raw.get("outcome", "")),
        )
    )
    if outcome not in T087_TERMINAL_CLASSES:
        raise T087IncompleteError(f"{identity} HP rescue +{extra_hp} lacks terminal outcome")
    return build_dense_diagnostic_row(
        selection_identity=identity,
        cohort=cohort,
        entry=entry,
        terminal=terminal,
        outcome=outcome,
        action_trace=_trace_for_controlled_run(controlled),
        provenance={
            "task_id": T087_TASK_ID,
            "natural_selection_identity": identity,
            "restore_method": restore_method,
            "native_commit": T087_NATIVE_COMMIT,
            "search_api": "StepSimulator.battle_search_v2.v1",
            "search_budget": 100,
            "root_selection_rule": "highest_mean",
            "policy_prior_callback": False,
            "learned_leaf_value_callback": False,
            "action_space": ActionSpaceConfig.initial_no_potions().to_dict(),
            "hp_transform": "current_hp_addition" if extra_hp else "none",
            "extra_hp": extra_hp,
            "seed": None,
            "max_steps": 200,
            "no_additional_search_seed": True,
        },
    )


def run_t087_hp_rescue(
    *,
    natural_rows: Iterable[Mapping[str, object]],
    records_by_identity: Mapping[str, object],
    canonical_records_by_cohort: Mapping[str, Mapping[str, object]],
    adapter_factory: Callable[[], object],
) -> tuple[dict[str, object], list[dict[str, object]]]:
    """Run the exact 24-record, non-monotone HP rescue ladder."""

    rows = tuple(dict(row) for row in natural_rows)
    manifest = select_hp_rescue_losses(rows)
    result_rows: list[dict[str, object]] = []
    for selected in manifest["selected"]:  # type: ignore[index]
        identity = str(selected["selection_identity"])
        record = records_by_identity.get(identity)
        if record is None:
            raise T087IncompleteError(f"HP rescue record {identity} is unavailable")
        cohort = str(selected["cohort"])
        natural = next(row for row in rows if _row_identity(row) == identity)
        diagnostics = natural.get("entry")
        if not isinstance(diagnostics, Mapping):
            raise T087IncompleteError(f"natural row {identity} lacks entry evidence")
        ladder = hp_rescue_ladder(
            diagnostics.get("player_current_hp"), diagnostics.get("player_max_hp")
        )
        for extra_hp in ladder:
            row = run_t087_hp_rescue_variant(
                record=record,
                cohort=cohort,
                extra_hp=extra_hp,
                canonical_records=canonical_records_by_cohort[cohort],
                adapter_factory=adapter_factory,
            )
            row["hp_rescue_selection"] = dict(selected)
            row["extra_hp"] = extra_hp
            result_rows.append(row)
    return manifest, result_rows


def _record_identity(record: object) -> str:
    identity = getattr(record, "selection_identity", None)
    if not isinstance(identity, str):
        if isinstance(record, Mapping):
            identity = record.get("selection_identity", record.get("record_identity"))
    if not isinstance(identity, str) or not identity:
        raise T087IncompleteError("record lacks exact selection identity")
    return identity


def _quantiles(values: Sequence[float]) -> dict[str, float | None]:
    if not values:
        return {"p25": None, "p50": None, "p75": None}
    ordered = sorted(values)
    def pick(fraction: float) -> float:
        return ordered[min(len(ordered) - 1, int((len(ordered) - 1) * fraction))]
    return {"p25": pick(0.25), "p50": pick(0.50), "p75": pick(0.75)}


def build_t087_report(
    *,
    natural_rows: Iterable[Mapping[str, object]],
    hp_ladder_rows: Iterable[Mapping[str, object]] = (),
    audit_traces: Iterable[Mapping[str, object]] = (),
    artifact_references: Mapping[str, Mapping[str, object]] | None = None,
) -> dict[str, object]:
    """Build a current-schema report and exactly one T087 terminal class."""

    rows = _validate_unique_rows(natural_rows)
    problems: list[str] = []
    if len(rows) != T087_NATURAL_RECORD_COUNT:
        problems.append(f"natural row count is {len(rows)}, expected 413")
    for cohort, expected in T087_COHORT_COUNTS.items():
        observed = sum(row.get("cohort") == cohort for row in rows)
        if observed != expected:
            problems.append(f"cohort {cohort} count is {observed}, expected {expected}")
    valid_rows: list[dict[str, object]] = []
    for row in rows:
        try:
            validate_dense_diagnostic_row(row)
        except T087IncompleteError as exc:
            problems.append(str(exc))
        else:
            valid_rows.append(row)
    hp_manifest: Mapping[str, object] | None = None
    audit_manifest: Mapping[str, object] | None = None
    try:
        hp_manifest = select_hp_rescue_losses(valid_rows)
    except T087IncompleteError as exc:
        problems.append(str(exc))
    try:
        audit_manifest = select_blind_audit_rows(valid_rows)
    except T087IncompleteError as exc:
        problems.append(str(exc))
    hp_rows = tuple(dict(row) for row in hp_ladder_rows)
    if len(hp_rows) != 24:
        problems.append(f"HP rescue row count is {len(hp_rows)}, expected 24")
    trace_rows = tuple(dict(row) for row in audit_traces)
    if len(trace_rows) != 24:
        problems.append(f"blind audit trace count is {len(trace_rows)}, expected 24")
    blind_bundle: Mapping[str, object] | None = None
    hidden_provenance: Mapping[str, object] | None = None
    if audit_manifest is not None:
        required_ids = {str(item["selection_identity"]) for item in audit_manifest["selected"]}  # type: ignore[index]
        observed_ids = {_row_identity(row) for row in trace_rows}
        if observed_ids != required_ids:
            problems.append("blind audit trace identities do not match frozen manifest")
        else:
            try:
                blind_bundle, hidden_provenance = build_blind_trace_bundle(
                    selected_manifest=audit_manifest,
                    rows=trace_rows,
                )
            except T087IncompleteError as exc:
                problems.append(str(exc))
    outcome_counts = Counter(str(row.get("outcome")) for row in rows)
    by_cohort = {
        cohort: {
            "rows": sum(row.get("cohort") == cohort for row in rows),
            "wins": sum(row.get("cohort") == cohort and row.get("outcome") == "PLAYER_VICTORY" for row in rows),
            "losses": sum(row.get("cohort") == cohort and row.get("outcome") == "PLAYER_LOSS" for row in rows),
        }
        for cohort in T087_COHORT_COUNTS
    }
    margins = [_diagnostic(row, "combat_terminal_margin_v1") for row in valid_rows]
    losses = [row for row in valid_rows if row.get("outcome") == "PLAYER_LOSS"]
    wins = [row for row in valid_rows if row.get("outcome") == "PLAYER_VICTORY"]
    report = {
        "schema_id": "t087-dense-combat-diagnostics-report-v1",
        "task_id": T087_TASK_ID,
        "approved_spec": T087_APPROVED_SPEC,
        "base_commit": T087_BASE_COMMIT,
        "native_identity": {
            "repository": "lsmfttb/sts_lightspeed",
            "ref": "refs/heads/stsrl/main",
            "commit": T087_NATIVE_COMMIT,
        },
        "frozen_controller": {
            "name": "unguided_native_search_v2",
            "simulations": 100,
            "root_selection_rule": "highest_mean",
            "policy_prior_callback": False,
            "learned_leaf_value_callback": False,
            "action_space": ActionSpaceConfig.initial_no_potions().to_dict(),
            "seed": None,
            "max_steps": 200,
        },
        "t085_binding": {
            "scientific_head": T085_SCIENTIFIC_HEAD,
            "selection_sha256": T085_SELECTION_SHA256,
            "restore_evidence_sha256": T085_RESTORE_SHA256,
            "paired_report_sha256": T085_PAIRED_REPORT_SHA256,
            "t052_cohort_sha256": T052_COHORT_SHA256,
        },
        "natural_execution": {
            "expected_count": T087_NATURAL_RECORD_COUNT,
            "observed_count": len(rows),
            "outcome_counts": dict(sorted(outcome_counts.items())),
            "by_cohort": by_cohort,
            "restore_and_execution_complete": len(valid_rows) == T087_NATURAL_RECORD_COUNT,
        },
        "diagnostic_summary": {
            "combat_terminal_margin_v1": _quantiles(margins),
            "loss_enemy_hp_remaining_fraction": _quantiles([_diagnostic(row, "enemy_hp_remaining_fraction") for row in losses]),
            "win_player_hp_remaining_fraction_of_max": _quantiles([_diagnostic(row, "player_hp_remaining_fraction_of_max") for row in wins]),
            "enemy_kill_fraction": _quantiles([_diagnostic(row, "enemy_kill_fraction") for row in rows]),
            "mean_action_count": mean([float(row.get("action_count", 0)) for row in valid_rows]) if valid_rows else None,
        },
        "hp_rescue": {"selection_manifest": hp_manifest, "rows": list(hp_rows)},
        "blind_human_audit": {
            "selection_manifest": audit_manifest,
            "bundle": blind_bundle,
            "hidden_provenance": hidden_provenance,
            "hidden_provenance_separate": True,
        },
        "human_review_rubric": build_review_rubric(),
        "human_labels_used_by_algorithm": False,
        "artifact_references": dict(artifact_references or {}),
        "problems": problems,
        "terminal_classification": (
            "DENSE_COMBAT_DIAGNOSTICS_READY" if not problems else "INCOMPLETE"
        ),
    }
    return report


def write_t087_json_artifact(
    path: str | Path,
    payload: Mapping[str, object],
    *,
    schema_id: str,
) -> dict[str, object]:
    """Write a current T087 JSON artifact and return its file identity."""

    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    document = {"schema_id": schema_id, **dict(payload)}
    target.write_text(
        json.dumps(document, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False)
        + "\n",
        encoding="utf-8",
    )
    data = target.read_bytes()
    return {"path": str(target), "sha256": hashlib.sha256(data).hexdigest(), "size_bytes": len(data), "schema_id": schema_id}


__all__ = [
    "T087IncompleteError",
    "T087_APPROVED_SPEC",
    "T087_NATIVE_COMMIT",
    "T087_NATURAL_RECORD_COUNT",
    "battle_snapshot_evidence",
    "build_dense_diagnostic_row",
    "build_review_rubric",
    "build_blind_trace_bundle",
    "build_t087_report",
    "canonical_json_bytes",
    "hp_rescue_ladder",
    "run_t087_native_record",
    "run_t087_natural_evaluation",
    "run_t087_hp_rescue",
    "run_t087_hp_rescue_variant",
    "select_blind_audit_rows",
    "select_hp_rescue_losses",
    "selection_digest",
    "selection_identity_bytes",
    "validate_dense_diagnostic_row",
    "write_t087_json_artifact",
]
